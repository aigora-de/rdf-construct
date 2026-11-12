"""Tests for the cast command and core/formats module."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from rdflib import BNode, Dataset, Graph, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID
from rdflib.namespace import OWL, RDF, RDFS, XSD
from rdflib.plugins.serializers.trig import TrigSerializer

from rdf_construct.core import preserve_literal_forms
from rdf_construct.core.literal_forms import GUARDED_FORMATS
from rdf_construct.core.formats import (
    FORMAT_ALIASES,
    FormatInfo,
    default_cast_formats,
    extension_for_format,
    infer_format,
    is_quad_format,
    normalise_format,
)
from rdf_construct.cast.converter import CastConverter, ConversionResult, GraphNameReferences

if TYPE_CHECKING:
    from click.testing import Result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EX = Namespace("http://example.org/")
DEFAULT_ID = DATASET_DEFAULT_GRAPH_ID

SIMPLE_TTL = dedent(
    """\
    @prefix ex: <http://example.org/> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

    ex:Thing a owl:Class ;
        rdfs:label "Thing" .

    ex:hasPart a owl:ObjectProperty ;
        rdfs:domain ex:Thing ;
        rdfs:range ex:Thing .
"""
)

SIMPLE_TRIG = dedent(
    """\
    @prefix ex: <http://example.org/> .

    ex:graph1 {
        ex:Thing a <http://www.w3.org/2002/07/owl#Class> .
    }

    ex:graph2 {
        ex:OtherThing a <http://www.w3.org/2002/07/owl#Class> .
    }
"""
)


@pytest.fixture()
def ttl_file(tmp_path: Path) -> Path:
    """Write a simple Turtle source file into a dedicated ``src/`` subdirectory.

    Using a subdirectory keeps the source file separate from any output
    directory used in tests, so directory listings of the output dir are
    not polluted by the source ``.ttl`` file.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    p = src_dir / "ontology.ttl"
    p.write_text(SIMPLE_TTL, encoding="utf-8")
    return p


@pytest.fixture()
def trig_file(tmp_path: Path) -> Path:
    """Write a simple TriG source file into a dedicated ``src/`` subdirectory."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    p = src_dir / "multi.trig"
    p.write_text(SIMPLE_TRIG, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# core/formats tests
# ---------------------------------------------------------------------------


class TestNormaliseFormat:
    """Tests for normalise_format()."""

    @pytest.mark.parametrize(
        "alias,expected",
        [
            ("ttl", "turtle"),
            ("turtle", "turtle"),
            ("xml", "xml"),
            ("rdf", "xml"),
            ("rdfxml", "xml"),
            ("json-ld", "json-ld"),
            ("jsonld", "json-ld"),
            ("nt", "nt"),
            ("ntriples", "nt"),
            ("n3", "n3"),
            ("trig", "trig"),
            ("nq", "nquads"),
            ("nquads", "nquads"),
            ("TTL", "turtle"),  # case-insensitive
            ("JSON-LD", "json-ld"),
        ],
    )
    def test_known_aliases(self, alias: str, expected: str) -> None:
        assert normalise_format(alias) == expected

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown format"):
            normalise_format("csv")


class TestExtensionForFormat:
    """Tests for extension_for_format()."""

    @pytest.mark.parametrize(
        "fmt,expected",
        [
            ("turtle", ".ttl"),
            ("xml", ".rdf"),
            ("json-ld", ".jsonld"),
            ("nt", ".nt"),
            ("n3", ".n3"),
            ("trig", ".trig"),
            ("nquads", ".nq"),
        ],
    )
    def test_known_formats(self, fmt: str, expected: str) -> None:
        assert extension_for_format(fmt) == expected


class TestInferFormat:
    """Tests for infer_format()."""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("ont.ttl", "turtle"),
            ("ont.turtle", "turtle"),
            ("ont.rdf", "xml"),
            ("ont.xml", "xml"),
            ("ont.owl", "xml"),
            ("ont.nt", "nt"),
            ("ont.ntriples", "nt"),
            ("ont.n3", "n3"),
            ("ont.jsonld", "json-ld"),
            ("ont.json", "json-ld"),
            ("ont.trig", "trig"),
            ("ont.nq", "nquads"),
        ],
    )
    def test_extensions(self, filename: str, expected: str) -> None:
        assert infer_format(Path(filename)) == expected

    def test_unknown_extension_defaults_to_turtle(self) -> None:
        assert infer_format(Path("ont.unknown")) == "turtle"


class TestDefaultCastFormats:
    """Tests for default_cast_formats()."""

    def test_excludes_source_format(self) -> None:
        formats = default_cast_formats(source_format="turtle")
        assert "turtle" not in formats

    def test_default_set_contains_xml_and_jsonld(self) -> None:
        formats = default_cast_formats(source_format="turtle")
        assert "xml" in formats
        assert "json-ld" in formats

    def test_n3_not_in_defaults(self) -> None:
        formats = default_cast_formats(source_format="xml")
        assert "n3" not in formats

    def test_source_xml_excludes_xml(self) -> None:
        formats = default_cast_formats(source_format="xml")
        assert "xml" not in formats
        assert "turtle" in formats


class TestIsQuadFormat:
    """Tests for is_quad_format()."""

    @pytest.mark.parametrize("fmt", ["trig", "nquads"])
    def test_quad_formats(self, fmt: str) -> None:
        assert is_quad_format(fmt) is True

    @pytest.mark.parametrize("fmt", ["turtle", "xml", "json-ld", "nt", "n3"])
    def test_non_quad_formats(self, fmt: str) -> None:
        assert is_quad_format(fmt) is False


# ---------------------------------------------------------------------------
# CastConverter tests
# ---------------------------------------------------------------------------


class TestCastConverterFileOutput:
    """Tests for CastConverter producing file output."""

    def test_single_format_writes_file(self, ttl_file: Path, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        converter = CastConverter()
        result = converter.convert(
            source=ttl_file,
            formats=["xml"],
            output_dir=out_dir,
            pipe_mode=False,
        )
        assert result.success
        assert len(result.written_files) == 1
        assert result.written_files[0].suffix == ".rdf"
        assert result.written_files[0].exists()

    def test_multiple_formats_write_files(self, ttl_file: Path, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        converter = CastConverter()
        result = converter.convert(
            source=ttl_file,
            formats=["xml", "json-ld"],
            output_dir=out_dir,
            pipe_mode=False,
        )
        assert result.success
        assert len(result.written_files) == 2
        extensions = {f.suffix for f in result.written_files}
        assert extensions == {".rdf", ".jsonld"}

    def test_default_output_dir_is_source_dir(self, ttl_file: Path) -> None:
        converter = CastConverter()
        result = converter.convert(
            source=ttl_file,
            formats=["xml"],
            output_dir=None,
            pipe_mode=False,
        )
        assert result.success
        assert result.written_files[0].parent == ttl_file.parent

    def test_output_is_valid_rdf(self, ttl_file: Path, tmp_path: Path) -> None:
        """Converted files can be re-parsed by rdflib."""
        out_dir = tmp_path / "out"
        converter = CastConverter()
        converter.convert(
            source=ttl_file,
            formats=["xml", "json-ld"],
            output_dir=out_dir,
            pipe_mode=False,
        )
        for outfile in out_dir.iterdir():
            g = Graph()
            g.parse(str(outfile))  # should not raise
            assert len(g) > 0


class TestCastConverterPipeMode:
    """Tests for CastConverter in pipe mode (stdout output)."""

    def test_pipe_mode_returns_serialised_string(self, ttl_file: Path) -> None:
        converter = CastConverter()
        result = converter.convert(
            source=ttl_file,
            formats=["xml"],
            output_dir=None,
            pipe_mode=True,
        )
        assert result.success
        assert result.stdout_content is not None
        assert len(result.stdout_content) > 0
        # XML output should start with the XML declaration or rdf:RDF
        assert "rdf:RDF" in result.stdout_content or "<?xml" in result.stdout_content

    def test_pipe_mode_no_files_written(self, ttl_file: Path, tmp_path: Path) -> None:
        converter = CastConverter()
        result = converter.convert(
            source=ttl_file,
            formats=["xml"],
            output_dir=tmp_path,
            pipe_mode=True,
        )
        assert result.success
        assert result.written_files == []

    def test_pipe_mode_turtle_output_is_parseable(self, ttl_file: Path) -> None:
        converter = CastConverter()
        result = converter.convert(
            source=ttl_file,
            formats=["xml"],
            output_dir=None,
            pipe_mode=True,
        )
        assert result.stdout_content is not None
        g = Graph()
        g.parse(data=result.stdout_content, format="xml")
        assert len(g) > 0


class TestCastConverterEdgeCases:
    """Edge case handling in CastConverter."""

    def test_source_equals_target_format_is_nothing_to_cast(
        self, ttl_file: Path, tmp_path: Path
    ) -> None:
        """Every format the source's own is reported as a failure, not a success (#330)."""
        out_dir = tmp_path / "out"
        converter = CastConverter()
        result = converter.convert(
            source=ttl_file,
            formats=["turtle"],
            output_dir=out_dir,
            pipe_mode=False,
        )
        assert not result.success
        assert result.error == (
            "nothing to cast: ontology.ttl is already turtle (from its extension), "
            "and turtle was the only format requested."
        )
        assert result.skipped_formats == ["turtle"]
        assert result.written_files == []
        assert result.stdout_content is None
        assert not out_dir.exists()

    def test_nothing_to_cast_is_reported_before_the_parse(self, tmp_path: Path) -> None:
        """A malformed source gets nothing-to-cast, not the parse error (#330)."""
        source = tmp_path / "bad.ttl"
        source.write_text("@prefix ex: <http://example.org/> .\nex:A a 'owl:Class\n")
        result = CastConverter().convert(
            source=source, formats=["turtle"], output_dir=None, pipe_mode=True
        )
        assert not result.success
        assert result.error is not None
        assert result.error.startswith("nothing to cast: bad.ttl is already turtle")
        assert result.warnings == []

    def test_pipe_mode_with_several_formats_records_skips_before_the_first_written(
        self, ttl_file: Path
    ) -> None:
        """Pipe mode attempts only the first format not skipped (documented on ``success``)."""
        result = CastConverter().convert(
            source=ttl_file, formats=["turtle", "nt"], output_dir=None, pipe_mode=True
        )
        assert result.success
        assert result.skipped_formats == ["turtle"]
        assert result.stdout_content is not None and result.written_files == []

    def test_source_format_among_others_is_skipped_and_reported(
        self, ttl_file: Path, tmp_path: Path
    ) -> None:
        """A skip beside a written format succeeds and names the skip once (#330)."""
        out_dir = tmp_path / "out"
        result = CastConverter().convert(
            source=ttl_file,
            formats=["turtle", "nt", "turtle"],
            output_dir=out_dir,
            pipe_mode=False,
        )
        assert result.success
        assert result.error is None
        assert result.skipped_formats == ["turtle"]
        assert result.written_files == [out_dir / "ontology.nt"]

    def test_quad_source_to_single_graph_raises(self, trig_file: Path, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        converter = CastConverter()
        result = converter.convert(
            source=trig_file,
            formats=["turtle"],
            output_dir=out_dir,
            pipe_mode=False,
        )
        assert not result.success
        assert result.error == (
            "Source 'multi.trig' uses a multi-graph format (trig) but the requested target "
            "format(s) are single-graph: turtle. Use --allow-flatten to merge all named graphs "
            "into the default graph, or choose a quad output format (nquads)."
        )
        assert not out_dir.exists()

    def test_quad_source_with_allow_flatten_succeeds(self, trig_file: Path, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        converter = CastConverter()
        result = converter.convert(
            source=trig_file,
            formats=["turtle"],
            output_dir=out_dir,
            pipe_mode=False,
            allow_flatten=True,
        )
        assert result.success
        assert result.written_files == [out_dir / "multi.ttl"]
        assert result.warnings == [
            "Flattened multi.trig for turtle: all named graphs merged into one graph."
        ]
        flat = Graph()
        flat.parse(out_dir / "multi.ttl", format="turtle")
        assert set(flat) == {
            (EX.Thing, RDF.type, OWL.Class),
            (EX.OtherThing, RDF.type, OWL.Class),
        }

    def test_partial_failure_reports_failed_formats(self, ttl_file: Path, tmp_path: Path) -> None:
        """When one format fails but another succeeds, result reflects partial failure."""
        out_dir = tmp_path / "out"
        converter = CastConverter()
        # Patch rdflib serialise to fail for json-ld but succeed for xml
        original_serialise = Graph.serialize

        def patched_serialise(self: Graph, destination=None, format="xml", **kwargs):  # type: ignore[misc]
            if format == "json-ld":
                raise RuntimeError("Simulated serialisation failure")
            return original_serialise(self, destination=destination, format=format, **kwargs)

        with patch.object(Graph, "serialize", patched_serialise):
            result = converter.convert(
                source=ttl_file,
                formats=["xml", "json-ld"],
                output_dir=out_dir,
                pipe_mode=False,
            )

        assert not result.success
        assert result.partial_failure
        assert len(result.written_files) == 1  # xml succeeded
        assert "json-ld" in result.failed_formats


# ---------------------------------------------------------------------------
# CLI integration (smoke tests via Click test runner)
# ---------------------------------------------------------------------------


class TestCastCLI:
    """Smoke tests for the 'cast' CLI command.

    Notes on Click's CliRunner:
    - ``mix_stderr`` was removed from ``CliRunner.__init__()`` in Click 8.2.
    - We use the plain ``CliRunner()`` constructor (default behaviour mixes
      stdout and stderr into ``result.output``) which is compatible with all
      Click 8.x versions.
    - For the stdout-purity test we call CastConverter directly instead of
      going through the CLI runner, which avoids the mixed-stream ambiguity
      entirely and is a cleaner unit test anyway.
    """

    def test_cast_help(self) -> None:
        from click.testing import CliRunner
        from rdf_construct.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["cast", "--help"])
        assert result.exit_code == 0
        assert "cast" in result.output.lower()
        assert "--format" in result.output
        assert "--output-dir" in result.output

    def test_cast_single_format_exit_zero(self, ttl_file: Path) -> None:
        from click.testing import CliRunner
        from rdf_construct.cli import cli

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["cast", str(ttl_file), "--format", "xml"],
        )
        assert result.exit_code == 0

    def test_cast_stdout_content_is_rdf(self, ttl_file: Path) -> None:
        """Single --format in pipe mode should produce parseable RDF.

        Tested at the converter level rather than through the CLI runner so
        that stdout/stderr mixing in CliRunner does not interfere with RDF
        parsing.
        """
        converter = CastConverter()
        result = converter.convert(
            source=ttl_file,
            formats=["xml"],
            output_dir=None,
            pipe_mode=True,
        )
        assert result.success
        assert result.stdout_content is not None
        g = Graph()
        g.parse(data=result.stdout_content, format="xml")
        assert len(g) > 0

    def test_cast_default_formats_writes_files(self, ttl_file: Path, tmp_path: Path) -> None:
        """Omitting --format should write xml and json-ld (not ttl) to output-dir.

        The output directory is ``tmp_path`` while the source lives in
        ``tmp_path/src/``, so the directory listing of ``tmp_path`` contains
        only the output files produced by cast.
        """
        from click.testing import CliRunner
        from rdf_construct.cli import cli

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["cast", str(ttl_file), "--output-dir", str(out_dir)],
        )
        assert result.exit_code == 0
        written = list(out_dir.iterdir())
        # Should have .rdf and .jsonld, but NOT .ttl (source format excluded)
        extensions = {f.suffix for f in written}
        assert ".rdf" in extensions
        assert ".jsonld" in extensions
        assert ".ttl" not in extensions

    def test_cast_allow_flatten_flag(self, trig_file: Path, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from rdf_construct.cli import cli

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "cast",
                str(trig_file),
                "--format",
                "turtle",
                "--output-dir",
                str(out_dir),
                "--allow-flatten",
            ],
        )
        assert result.exit_code == 0
        flat = Graph()
        flat.parse(out_dir / "multi.ttl", format="turtle")
        assert set(flat) == {
            (EX.Thing, RDF.type, OWL.Class),
            (EX.OtherThing, RDF.type, OWL.Class),
        }

    def test_cast_quad_without_flatten_exits_two(self, trig_file: Path, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from rdf_construct.cli import cli

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "cast",
                str(trig_file),
                "--format",
                "turtle",
                "--output-dir",
                str(out_dir),
            ],
        )
        assert result.exit_code == 2
        assert "or choose a quad output format (nquads).\n" in result.stderr
        assert list(out_dir.iterdir()) == []


# ---------------------------------------------------------------------------
# Every requested format the source's own (#330)
# ---------------------------------------------------------------------------

SIMPLE_NT = "<http://example.org/a> <http://example.org/p> <http://example.org/b> .\n"
# RDF/XML cannot write this predicate (no local name to shorten to); every other format can.
XML_FAILS_TTL = "<http://example.org/a> <http://example.org/123> <http://example.org/b> .\n"
MALFORMED_TTL = "@prefix ex: <http://example.org/> .\nex:A a 'owl:Class\n"

TURTLE_ACCEPTED = "Accepted: xml, json-ld, nt, n3, trig, nquads\n"


def _refusal(what: str, fmt: str, extra: str = "") -> str:
    return f"Error: nothing to cast: {what}, and {fmt} was the only format requested.{extra}\n"


class TestCastSameFormat:
    """``cast`` refuses at 2 when every requested format is the source's own (#330).

    Each refusal is checked for its exact message, an empty stdout, and that nothing was
    written: the ``-o`` directory is never created.
    """

    @staticmethod
    def _invoke(*args: str) -> Result:
        from click.testing import CliRunner

        from rdf_construct.cli import cli

        return CliRunner().invoke(cli, ["cast", *args])

    @staticmethod
    def _assert_refused(result: Result, stderr: str) -> None:
        assert result.exit_code == 2, result.output
        exc = result.exception
        assert isinstance(exc, SystemExit) and exc.__cause__ is None
        assert result.stdout == ""
        assert result.stderr == stderr

    @pytest.mark.parametrize("fmt", ["turtle", "ttl", "TURTLE", "Ttl"])
    @pytest.mark.parametrize("with_output_dir", [True, False], ids=["-o", "pipe"])
    def test_turtle_source_is_refused(
        self, ttl_file: Path, tmp_path: Path, fmt: str, with_output_dir: bool
    ) -> None:
        out_dir = tmp_path / "out"
        extra = ["-o", str(out_dir)] if with_output_dir else []
        before = sorted(ttl_file.parent.iterdir())
        result = self._invoke(str(ttl_file), "-f", fmt, *extra)
        self._assert_refused(
            result,
            _refusal("ontology.ttl is already turtle (from its extension)", "turtle")
            + TURTLE_ACCEPTED,
        )
        assert not out_dir.exists()
        assert sorted(ttl_file.parent.iterdir()) == before

    @pytest.mark.parametrize("with_output_dir", [True, False], ids=["-o", "beside-source"])
    def test_a_repeated_source_format_is_refused(
        self, ttl_file: Path, tmp_path: Path, with_output_dir: bool
    ) -> None:
        out_dir = tmp_path / "out"
        extra = ["-o", str(out_dir)] if with_output_dir else []
        before = sorted(ttl_file.parent.iterdir())
        result = self._invoke(str(ttl_file), "-f", "turtle", "-f", "ttl", *extra)
        self._assert_refused(
            result,
            _refusal("ontology.ttl is already turtle (from its extension)", "turtle")
            + TURTLE_ACCEPTED,
        )
        assert not out_dir.exists()
        assert sorted(ttl_file.parent.iterdir()) == before

    @pytest.mark.parametrize("with_output_dir", [True, False], ids=["-o", "pipe"])
    def test_ntriples_source_is_refused(self, tmp_path: Path, with_output_dir: bool) -> None:
        source = tmp_path / "data.nt"
        source.write_text(SIMPLE_NT, encoding="utf-8")
        out_dir = tmp_path / "out"
        extra = ["-o", str(out_dir)] if with_output_dir else []
        result = self._invoke(str(source), "-f", "ntriples", *extra)
        self._assert_refused(
            result,
            _refusal("data.nt is already nt (from its extension)", "nt")
            + "Accepted: turtle, xml, json-ld, n3, trig, nquads\n",
        )
        assert not out_dir.exists()

    def test_trig_source_is_refused_naming_allow_flatten(
        self, trig_file: Path, tmp_path: Path
    ) -> None:
        """Refused before the quad guard, with the formats that need the flag named."""
        out_dir = tmp_path / "out"
        result = self._invoke(str(trig_file), "-f", "trig", "-o", str(out_dir))
        self._assert_refused(
            result,
            _refusal(
                "multi.trig is already trig (from its extension)",
                "trig",
                " Every format but nquads is single-graph, and needs --allow-flatten "
                "(which merges the named graphs) from a trig source.",
            )
            + "Accepted: turtle, xml, json-ld, nt, n3, nquads\n",
        )
        assert not out_dir.exists()

    def test_trig_source_with_allow_flatten_is_refused_without_the_flag_sentence(
        self, trig_file: Path, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "out"
        result = self._invoke(str(trig_file), "-f", "trig", "--allow-flatten", "-o", str(out_dir))
        self._assert_refused(
            result,
            _refusal("multi.trig is already trig (from its extension)", "trig")
            + "Accepted: turtle, xml, json-ld, nt, n3, nquads\n",
        )
        assert not out_dir.exists()

    def test_nquads_source_names_trig_as_the_other_quad_format(self, tmp_path: Path) -> None:
        source = tmp_path / "data.nq"
        source.write_text(
            "<http://example.org/a> <http://example.org/p> <http://example.org/b> "
            "<http://example.org/g> .\n",
            encoding="utf-8",
        )
        result = self._invoke(str(source), "-f", "nq")
        self._assert_refused(
            result,
            _refusal(
                "data.nq is already nquads (from its extension)",
                "nquads",
                " Every format but trig is single-graph, and needs --allow-flatten "
                "(which merges the named graphs) from an nquads source.",
            )
            + "Accepted: turtle, xml, json-ld, nt, n3, trig\n",
        )

    @pytest.mark.parametrize(
        ("name", "rdf_format", "fmt", "canonical"),
        [
            ("data.ttl", "turtle", "ttl", "turtle"),
            ("data.turtle", "turtle", "turtle", "turtle"),
            ("DATA.TTL", "turtle", "TURTLE", "turtle"),
            ("data.rdf", "xml", "rdf", "xml"),
            ("data.owl", "xml", "owl", "xml"),
            ("data.xml", "xml", "rdfxml", "xml"),
            ("data.jsonld", "json-ld", "jsonld", "json-ld"),
            ("data.json", "json-ld", "json-ld", "json-ld"),
            ("data.nt", "nt", "n-triples", "nt"),
            ("data.ntriples", "nt", "nt", "nt"),
            ("data.n3", "n3", "N3", "n3"),
        ],
    )
    @pytest.mark.parametrize("with_output_dir", [True, False], ids=["-o", "pipe"])
    def test_every_single_graph_format_is_refused_as_its_own_target(
        self,
        tmp_path: Path,
        name: str,
        rdf_format: str,
        fmt: str,
        canonical: str,
        with_output_dir: bool,
    ) -> None:
        source = tmp_path / name
        Graph().parse(data=SIMPLE_TTL, format="turtle").serialize(source, format=rdf_format)
        out_dir = tmp_path / "out"
        extra = ["-o", str(out_dir)] if with_output_dir else []
        result = self._invoke(str(source), "-f", fmt, *extra)
        others = ["turtle", "xml", "json-ld", "nt", "n3", "trig", "nquads"]
        others.remove(canonical)
        self._assert_refused(
            result,
            _refusal(f"{name} is already {canonical} (from its extension)", canonical)
            + f"Accepted: {', '.join(others)}\n",
        )
        assert not out_dir.exists()

    def test_no_extension_names_the_guess(self, tmp_path: Path) -> None:
        source = tmp_path / "ontology"
        source.write_text(SIMPLE_TTL, encoding="utf-8")
        result = self._invoke(str(source), "-f", "turtle")
        self._assert_refused(
            result,
            _refusal("ontology is taken to be turtle (ontology has no extension)", "turtle")
            + TURTLE_ACCEPTED,
        )

    def test_unknown_extension_names_the_guess(self, tmp_path: Path) -> None:
        source = tmp_path / "ontology.ont"
        source.write_text(SIMPLE_TTL, encoding="utf-8")
        out_dir = tmp_path / "out"
        result = self._invoke(str(source), "-f", "turtle", "-o", str(out_dir))
        self._assert_refused(
            result,
            _refusal(
                "ontology.ont is taken to be turtle (cast does not recognise '.ont')", "turtle"
            )
            + TURTLE_ACCEPTED,
        )
        assert not out_dir.exists()

    def test_refused_before_the_source_is_parsed(self, tmp_path: Path) -> None:
        """A malformed source gets the refusal, not the parse error: nothing is read."""
        source = tmp_path / "bad.ttl"
        source.write_text(MALFORMED_TTL, encoding="utf-8")
        out_dir = tmp_path / "out"
        result = self._invoke(str(source), "-f", "turtle", "-o", str(out_dir))
        self._assert_refused(
            result,
            _refusal("bad.ttl is already turtle (from its extension)", "turtle") + TURTLE_ACCEPTED,
        )
        assert not out_dir.exists()

    def test_refused_without_reading_the_source(self, ttl_file: Path) -> None:
        with patch.object(CastConverter, "convert") as convert:
            result = self._invoke(str(ttl_file), "-f", "turtle")
        assert result.exit_code == 2
        convert.assert_not_called()

    def test_a_skipped_format_beside_a_written_one_exits_one(
        self, ttl_file: Path, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "out"
        result = self._invoke(str(ttl_file), "-f", "turtle", "-f", "nt", "-o", str(out_dir))
        assert result.exit_code == 1, result.output
        assert result.stdout == ""
        assert "  \u26a0 Skipping 'turtle': source and target format are the same.\n" in (
            result.stderr
        )
        assert result.stderr.endswith(
            f"\nCast 1 file(s) to {out_dir}/; skipped turtle (the source's own format).\n"
        )
        assert sorted(p.name for p in out_dir.iterdir()) == ["ontology.nt"]
        written = Graph().parse(out_dir / "ontology.nt", format="nt")
        assert len(written) == len(Graph().parse(ttl_file, format="turtle"))

    def test_a_repeated_skip_beside_a_written_format_names_it_once(
        self, ttl_file: Path, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "out"
        result = self._invoke(
            str(ttl_file), "-f", "turtle", "-f", "nt", "-f", "ttl", "-o", str(out_dir)
        )
        assert result.exit_code == 1, result.output
        assert result.stderr.endswith(
            f"\nCast 1 file(s) to {out_dir}/; skipped turtle (the source's own format).\n"
        )

    def test_a_skipped_format_without_output_dir_writes_beside_the_source(
        self, ttl_file: Path
    ) -> None:
        result = self._invoke(str(ttl_file), "-f", "turtle", "-f", "nt")
        assert result.exit_code == 1, result.output
        assert result.stdout == ""
        assert sorted(p.name for p in ttl_file.parent.iterdir()) == ["ontology.nt", "ontology.ttl"]

    def test_a_skip_beside_a_partial_failure_exits_one(self, tmp_path: Path) -> None:
        """A skip, a failure and a written file: finished, with findings.

        The failure is real: RDF/XML cannot write a predicate that has no local name, and no
        other format minds. rdflib opens the file before it fails, so a partial ``xmlfail.rdf``
        is left in the directory. That is #409's, so the directory is not asserted to hold
        nothing else.
        """
        source = tmp_path / "xmlfail.ttl"
        source.write_text(XML_FAILS_TTL, encoding="utf-8")
        out_dir = tmp_path / "out"
        result = self._invoke(
            str(source), "-f", "turtle", "-f", "nt", "-f", "xml", "-o", str(out_dir)
        )
        assert result.exit_code == 1, result.output
        assert result.stdout == ""
        lines = result.stderr.splitlines()
        failure = "  \u26a0 Failed to write xmlfail.rdf (xml): "
        assert [failure if line.startswith(failure) else line for line in lines] == [
            "Casting xmlfail.ttl...",
            "  Formats: turtle, nt, xml",
            f"  Output:  {out_dir}/",
            "  \u26a0 Skipping 'turtle': source and target format are the same.",
            failure,
            "\u2717 Partial failure: xml could not be converted.",
            "  \u2713 xmlfail.nt",
        ]
        written = Graph()
        written.parse(out_dir / "xmlfail.nt", format="nt")
        assert len(written) == 1

    def test_a_parse_error_beside_a_mixed_request_is_the_parse_error(self, tmp_path: Path) -> None:
        source = tmp_path / "bad.ttl"
        source.write_text(MALFORMED_TTL, encoding="utf-8")
        out_dir = tmp_path / "out"
        result = self._invoke(str(source), "-f", "turtle", "-f", "nt", "-o", str(out_dir))
        assert result.exit_code == 2, result.output
        assert "Failed to parse 'bad.ttl' as turtle" in result.stderr
        assert "nothing to cast" not in result.stderr
        assert not out_dir.exists()

    def test_a_clean_run_has_no_skip_suffix_and_exits_zero(
        self, ttl_file: Path, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "out"
        result = self._invoke(str(ttl_file), "-f", "xml", "-f", "nt", "-o", str(out_dir))
        assert result.exit_code == 0, result.output
        assert result.stderr.endswith(f"\nCast 2 file(s) to {out_dir}/\n")

    def test_a_skip_and_a_failure_with_nothing_written_exits_two(self, tmp_path: Path) -> None:
        """Nothing asked for was done, so 2 (#330, ruling 5).

        The failure is RDF/XML's, as above, and the partial ``xmlfail.rdf`` it leaves is #409's.
        """
        source = tmp_path / "xmlfail.ttl"
        source.write_text(XML_FAILS_TTL, encoding="utf-8")
        out_dir = tmp_path / "out"
        result = self._invoke(str(source), "-f", "turtle", "-f", "xml", "-o", str(out_dir))
        assert result.exit_code == 2, result.output
        assert result.stdout == ""
        lines = result.stderr.splitlines()
        failure = "  \u26a0 Failed to write xmlfail.rdf (xml): "
        assert [failure if line.startswith(failure) else line for line in lines] == [
            "Casting xmlfail.ttl...",
            "  Formats: turtle, xml",
            f"  Output:  {out_dir}/",
            "  \u26a0 Skipping 'turtle': source and target format are the same.",
            failure,
            "\u2717 All target format conversions failed: xml",
        ]

    def test_help_defines_a_skip_as_exit_one(self) -> None:
        result = self._invoke("--help")
        assert result.exit_code == 0
        assert "a format was skipped (the" in result.output
        assert "source's own) or failed, and at least one was written" in result.output


# ---------------------------------------------------------------------------
# What quad output holds (#540, #189), and what no format can hold (#542)
# ---------------------------------------------------------------------------

# Two default-graph triples, two named graphs, a blank node shared by both graphs, and one
# triple (ex:s ex:both ex:o) stated in the default graph and in ex:g1.
QUADS_NQ = dedent(
    """\
    <http://example.org/d> <http://example.org/p> "default" .
    <http://example.org/s> <http://example.org/both> <http://example.org/o> .
    <http://example.org/a> <http://example.org/p> "one" <http://example.org/g1> .
    _:b <http://example.org/q> <http://example.org/x> <http://example.org/g1> .
    <http://example.org/s> <http://example.org/both> <http://example.org/o> <http://example.org/g1> .
    <http://example.org/a> <http://example.org/p> "two" <http://example.org/g2> .
    _:b <http://example.org/q> <http://example.org/y> <http://example.org/g2> .
"""
)
QUADS_TRIG = dedent(
    """\
    @prefix ex: <http://example.org/> .
    ex:d ex:p "default" .
    ex:s ex:both ex:o .
    ex:g1 { ex:a ex:p "one" . _:b ex:q ex:x . ex:s ex:both ex:o . }
    ex:g2 { ex:a ex:p "two" . _:b ex:q ex:y . }
"""
)
QUADS_JSONLD = dedent(
    """\
    {
      "@context": {"ex": "http://example.org/"},
      "@graph": [
        {"@id": "ex:d", "ex:p": "default"},
        {"@id": "ex:s", "ex:both": {"@id": "ex:o"}},
        {"@id": "ex:g1", "@graph": [
          {"@id": "ex:a", "ex:p": "one"},
          {"@id": "_:b", "ex:q": {"@id": "ex:x"}},
          {"@id": "ex:s", "ex:both": {"@id": "ex:o"}}
        ]},
        {"@id": "ex:g2", "@graph": [
          {"@id": "ex:a", "ex:p": "two"},
          {"@id": "_:b", "ex:q": {"@id": "ex:y"}}
        ]}
      ]
    }
"""
)
QUAD_SOURCES = {"nquads": ("d.nq", QUADS_NQ), "trig": ("d.trig", QUADS_TRIG)}
# The default graph's size, and each named graph's.
QUADS_SHAPE = (2, {str(EX.g1): 3, str(EX.g2): 2})
# Every graph merged: ex:s ex:both ex:o is stated twice and counted once.
QUADS_UNION_SIZE = 6

SINGLE_GRAPH_FORMATS = ["turtle", "xml", "json-ld", "nt", "n3"]
SINGLE_GRAPH_SOURCES = [
    ("ontology.ttl", "turtle"),
    ("ontology.rdf", "xml"),
    ("ontology.jsonld", "json-ld"),
    ("ontology.nt", "nt"),
    ("ontology.n3", "n3"),
]
QUAD_FORMATS = ["trig", "nquads"]
EXTENSION = {
    "turtle": ".ttl",
    "xml": ".rdf",
    "json-ld": ".jsonld",
    "nt": ".nt",
    "n3": ".n3",
    "trig": ".trig",
    "nquads": ".nq",
}

FORMULA_N3 = "@prefix : <http://ex/> .\n{ :a :b :c } => { :d :e :f } .\n:x :y :z .\n"
N3_REFUSED = (
    "✗ Source '{name}' holds N3 constructs that no other format can carry: {counts}. "
    "Only N3 can hold them, so there is nothing cast can write.\n"
)


def _cast(*args: str | Path) -> Result:
    from click.testing import CliRunner

    from rdf_construct.cli import cli

    return CliRunner().invoke(cli, ["cast", *map(str, args)])


def _write(tmp_path: Path, name: str, text: str) -> Path:
    source = tmp_path / "src" / name
    source.parent.mkdir(exist_ok=True)
    source.write_text(text, encoding="utf-8")
    return source


def _read(text: str, fmt: str) -> Dataset:
    """Parse output as the CLI would read it back: literal forms kept, named graphs kept."""
    with preserve_literal_forms():
        dataset = Dataset()
        dataset.parse(data=text, format=fmt)
    return dataset


def _default(dataset: Dataset) -> Graph:
    return dataset.get_context(DATASET_DEFAULT_GRAPH_ID)


def _shape(dataset: Dataset) -> tuple[int, dict[str, int]]:
    """The default graph's size, and each named graph's by IRI (``_:`` for a blank node)."""
    named: dict[str, int] = {}
    for _s, _p, _o, graph in dataset.quads((None, None, None, None)):
        if graph != DATASET_DEFAULT_GRAPH_ID:
            key = "_:" if isinstance(graph, BNode) else str(graph)
            named[key] = named.get(key, 0) + 1
    return len(_default(dataset)), named


def _cast_to(
    source: Path, fmt: str, tmp_path: Path, *flags: str, with_output_dir: bool
) -> tuple[Result, str]:
    """Cast *source* to one format, in pipe mode or with ``-o``, and return what was written."""
    if not with_output_dir:
        result = _cast(source, "-f", fmt, *flags)
        return result, result.stdout
    out_dir = tmp_path / "out"
    result = _cast(source, "-f", fmt, *flags, "-o", out_dir)
    written = out_dir / f"{source.stem}{EXTENSION[fmt]}"
    assert result.stdout == ""
    return result, written.read_text(encoding="utf-8") if written.exists() else ""


def _assert_quads_kept(dataset: Dataset) -> None:
    """Every graph of the quad fixture is there, with its own triples and the shared node."""
    assert _shape(dataset) == QUADS_SHAPE
    source = _read(QUADS_NQ, "nquads")
    for name in (DATASET_DEFAULT_GRAPH_ID, EX.g1, EX.g2):
        assert isomorphic(dataset.get_context(name), source.get_context(name)), name
    # The blank node shared by ex:g1 and ex:g2 is still one node.
    assert len({s for s, _p, _o, _g in dataset.quads((None, EX.q, None, None))}) == 1
    # The triple stated in the default graph and in ex:g1 is still in both.
    assert {g for _s, _p, _o, g in dataset.quads((EX.s, EX.both, EX.o, None))} == {
        DATASET_DEFAULT_GRAPH_ID,
        EX.g1,
    }


def _assert_refused(result: Result, stderr: str) -> None:
    assert result.exit_code == 2, result.output
    exc = result.exception
    assert isinstance(exc, SystemExit) and exc.__cause__ is None
    assert result.stdout == ""
    assert result.stderr == stderr


class TestCastQuadTargets:
    """TriG and N-Quads are written from a dataset, so they hold what the source holds (#540)."""

    @pytest.mark.parametrize("with_output_dir", [True, False], ids=["-o", "pipe"])
    @pytest.mark.parametrize("fmt", QUAD_FORMATS)
    @pytest.mark.parametrize(("name", "source_format"), SINGLE_GRAPH_SOURCES)
    def test_single_graph_source_is_written_to_the_default_graph(
        self, tmp_path: Path, name: str, source_format: str, fmt: str, with_output_dir: bool
    ) -> None:
        expected = Graph()
        expected.parse(data=SIMPLE_TTL, format="turtle")
        source = _write(tmp_path, name, expected.serialize(format=source_format))

        result, text = _cast_to(source, fmt, tmp_path, with_output_dir=with_output_dir)

        assert result.exit_code == 0, result.output
        dataset = _read(text, fmt)
        assert _shape(dataset) == (5, {})
        assert isomorphic(_default(dataset), expected)
        # No graph is named, by a blank node (#540) or by rdflib's own default-graph IRI.
        assert not re.search(r"^_:\S+ \{", text, re.MULTILINE)
        assert "urn:x-rdflib:default" not in text

    def test_trig_default_graph_is_one_unnamed_block(self, ttl_file: Path) -> None:
        result = _cast(ttl_file, "-f", "trig")
        assert result.exit_code == 0, result.output
        assert re.findall(r"^(.*)\{$", result.stdout, re.MULTILINE) == [""]

    def test_nquads_statements_end_in_one_space_and_match_ntriples(self, ttl_file: Path) -> None:
        """rdflib leaves two spaces where the graph term would be; ``cast`` writes one (#189)."""
        nquads = _cast(ttl_file, "-f", "nq")
        ntriples = _cast(ttl_file, "-f", "nt")
        assert nquads.exit_code == 0, nquads.output
        lines = [line for line in nquads.stdout.split("\n") if line]
        assert len(lines) == 5
        assert all(line.endswith(" .") and not line.endswith("  .") for line in lines)
        assert sorted(lines) == sorted(line for line in ntriples.stdout.split("\n") if line)

    def test_nquads_named_and_default_statements_are_spaced_alike(self, tmp_path: Path) -> None:
        source = _write(tmp_path, "d.trig", QUADS_TRIG)
        result = _cast(source, "-f", "nquads")
        assert result.exit_code == 0, result.output
        assert "  ." not in result.stdout
        assert '<http://example.org/d> <http://example.org/p> "default" .\n' in result.stdout
        assert (
            '<http://example.org/a> <http://example.org/p> "one" <http://example.org/g1> .\n'
            in result.stdout
        )

    def test_a_literal_that_looks_like_a_statement_end_is_left_alone(self, tmp_path: Path) -> None:
        source = _write(
            tmp_path,
            "odd.ttl",
            '<http://example.org/a> <http://example.org/p> "two spaces and a dot  .", '
            '"then a newline  .\\nmore" .\n',
        )
        result = _cast(source, "-f", "nquads")
        assert result.exit_code == 0, result.output
        values = {str(o) for o in _default(_read(result.stdout, "nquads")).objects()}
        assert values == {"two spaces and a dot  .", "then a newline  .\nmore"}

    @pytest.mark.parametrize("with_output_dir", [True, False], ids=["-o", "pipe"])
    @pytest.mark.parametrize("flags", [(), ("--allow-flatten",)], ids=["no-flag", "allow-flatten"])
    @pytest.mark.parametrize(("source_format", "fmt"), [("nquads", "trig"), ("trig", "nquads")])
    def test_quad_to_quad_keeps_every_graph_whatever_the_flag(
        self,
        tmp_path: Path,
        source_format: str,
        fmt: str,
        flags: tuple[str, ...],
        with_output_dir: bool,
    ) -> None:
        source = _write(tmp_path, *QUAD_SOURCES[source_format])

        result, text = _cast_to(source, fmt, tmp_path, *flags, with_output_dir=with_output_dir)

        assert result.exit_code == 0, result.output
        _assert_quads_kept(_read(text, fmt))
        # Nothing was merged, so nothing is reported as flattened.
        assert "Flattened" not in result.stderr
        assert "urn:x-rdflib:default" not in text

    @pytest.mark.parametrize("fmt", QUAD_FORMATS)
    def test_jsonld_named_graphs_are_kept_in_quad_output(self, tmp_path: Path, fmt: str) -> None:
        source = _write(tmp_path, "d.jsonld", QUADS_JSONLD)
        result = _cast(source, "-f", fmt)
        assert result.exit_code == 0, result.output
        assert result.stderr == "Casting d.jsonld...\n"
        _assert_quads_kept(_read(result.stdout, fmt))

    def test_a_blank_node_graph_name_stays_a_blank_node(self, tmp_path: Path) -> None:
        source = _write(
            tmp_path,
            "bn.nq",
            '<http://example.org/d> <http://example.org/p> "default" .\n'
            '<http://example.org/a> <http://example.org/p> "named" _:g .\n',
        )
        result = _cast(source, "-f", "trig")
        assert result.exit_code == 0, result.output
        assert _shape(_read(result.stdout, "trig")) == (1, {"_:": 1})

    def test_a_quad_source_with_only_a_default_graph(self, tmp_path: Path) -> None:
        source = _write(
            tmp_path, "def.trig", '{ <http://example.org/d> <http://example.org/p> "default" . }\n'
        )
        result = _cast(source, "-f", "nquads")
        assert result.exit_code == 0, result.output
        assert result.stdout == '<http://example.org/d> <http://example.org/p> "default" .\n\n'

    def test_a_quad_source_with_only_named_graphs(self, tmp_path: Path) -> None:
        source = _write(
            tmp_path,
            "named.nq",
            '<http://example.org/a> <http://example.org/p> "one" <http://example.org/g1> .\n',
        )
        result = _cast(source, "-f", "trig")
        assert result.exit_code == 0, result.output
        assert _shape(_read(result.stdout, "trig")) == (0, {str(EX.g1): 1})

    def test_literal_forms_survive_quad_output(self, tmp_path: Path) -> None:
        source = _write(
            tmp_path,
            "forms.ttl",
            "<http://example.org/a> <http://example.org/p> "
            '"007"^^<http://www.w3.org/2001/XMLSchema#integer> .\n',
        )
        for fmt in QUAD_FORMATS:
            result = _cast(source, "-f", fmt)
            assert result.exit_code == 0, result.output
            assert [o.n3() for o in _default(_read(result.stdout, fmt)).objects()] == [
                '"007"^^<http://www.w3.org/2001/XMLSchema#integer>'
            ]


class TestCastFlatten:
    """``--allow-flatten`` merges the graphs for a single-graph target, and only for one."""

    @pytest.mark.parametrize("fmt", SINGLE_GRAPH_FORMATS)
    @pytest.mark.parametrize("source_format", ["nquads", "trig"])
    def test_quad_source_is_merged_for_a_single_graph_target(
        self, tmp_path: Path, source_format: str, fmt: str
    ) -> None:
        source = _write(tmp_path, *QUAD_SOURCES[source_format])

        result = _cast(source, "-f", fmt, "--allow-flatten")

        assert result.exit_code == 0, result.output
        assert result.stderr == (
            f"Casting {source.name}...\n"
            f"  ⚠ Flattened {source.name} for {fmt}: all named graphs merged into one graph.\n"
        )
        merged = _default(_read(result.stdout, fmt))
        assert len(merged) == QUADS_UNION_SIZE
        union = Graph()
        for s, p, o, _g in _read(QUADS_NQ, "nquads").quads((None, None, None, None)):
            union.add((s, p, o))
        assert isomorphic(merged, union)
        # The blank node the two graphs shared is one node, with both its statements.
        assert len(set(merged.subjects(EX.q, None))) == 1

    def test_a_mixed_request_merges_only_for_the_single_graph_target(self, tmp_path: Path) -> None:
        source = _write(tmp_path, "d.trig", QUADS_TRIG)
        out_dir = tmp_path / "out"

        result = _cast(source, "-f", "nquads", "-f", "turtle", "--allow-flatten", "-o", out_dir)

        assert result.exit_code == 0, result.output
        assert (
            "  ⚠ Flattened d.trig for turtle: all named graphs merged into one graph.\n"
            in result.stderr
        )
        assert sorted(p.name for p in out_dir.iterdir()) == ["d.nq", "d.ttl"]
        _assert_quads_kept(_read((out_dir / "d.nq").read_text(encoding="utf-8"), "nquads"))
        merged = Graph()
        merged.parse(out_dir / "d.ttl", format="turtle")
        assert len(merged) == QUADS_UNION_SIZE

    def test_a_mixed_request_without_the_flag_is_refused(self, tmp_path: Path) -> None:
        source = _write(tmp_path, "d.trig", QUADS_TRIG)
        out_dir = tmp_path / "out"
        result = _cast(source, "-f", "nquads", "-f", "turtle", "-o", out_dir)
        assert result.exit_code == 2, result.output
        assert not out_dir.exists()

    @pytest.mark.parametrize(("source_format", "other"), [("trig", "nquads"), ("nquads", "trig")])
    def test_the_guard_names_only_the_other_quad_format(
        self, tmp_path: Path, source_format: str, other: str
    ) -> None:
        """The source's own format would be refused as nothing to cast (#330)."""
        source = _write(tmp_path, *QUAD_SOURCES[source_format])
        result = _cast(source, "-f", "turtle")
        _assert_refused(
            result,
            f"Casting {source.name}...\n"
            f"✗ Source '{source.name}' uses a multi-graph format ({source_format}) but the "
            f"requested target format(s) are single-graph: turtle. Use --allow-flatten to merge "
            f"all named graphs into the default graph, or choose a quad output format ({other}).\n",
        )

    def test_help_says_quad_output_keeps_the_graphs(self) -> None:
        result = _cast("--help")
        assert result.exit_code == 0
        text = " ".join(result.output.split())
        assert "Lossy: graph names are discarded." in text
        assert "TriG and N-Quads output always keeps the graphs." in text
        assert "an N3 source with formulae or variables" in text


class TestCastJsonLdNamedGraphs:
    """A JSON-LD source that holds named graphs is a quad source, decided from its content."""

    GUARD = (
        "✗ Source '{name}' holds named graphs but the requested target format(s) are "
        "single-graph: {targets}. Use --allow-flatten to merge all named graphs into the default "
        "graph, or choose a quad output format (trig, nquads).\n"
    )

    @pytest.mark.parametrize("fmt", ["turtle", "xml", "nt", "n3"])
    def test_a_single_graph_target_is_refused(self, tmp_path: Path, fmt: str) -> None:
        source = _write(tmp_path, "d.jsonld", QUADS_JSONLD)
        result = _cast(source, "-f", fmt)
        _assert_refused(
            result, "Casting d.jsonld...\n" + self.GUARD.format(name="d.jsonld", targets=fmt)
        )

    def test_the_default_formats_are_refused_and_nothing_is_written(self, tmp_path: Path) -> None:
        source = _write(tmp_path, "d.jsonld", QUADS_JSONLD)
        out_dir = tmp_path / "out"
        result = _cast(source, "-o", out_dir)
        _assert_refused(
            result,
            "Casting d.jsonld...\n"
            "  Formats: turtle, xml\n"
            f"  Output:  {out_dir}/\n" + self.GUARD.format(name="d.jsonld", targets="turtle, xml"),
        )
        assert not out_dir.exists()

    @pytest.mark.parametrize("fmt", ["turtle", "xml", "nt", "n3"])
    def test_allow_flatten_merges_the_graphs(self, tmp_path: Path, fmt: str) -> None:
        source = _write(tmp_path, "d.jsonld", QUADS_JSONLD)
        result = _cast(source, "-f", fmt, "--allow-flatten")
        assert result.exit_code == 0, result.output
        assert result.stderr == (
            "Casting d.jsonld...\n"
            f"  ⚠ Flattened d.jsonld for {fmt}: all named graphs merged into one graph.\n"
        )
        merged = _default(_read(result.stdout, fmt))
        assert len(merged) == QUADS_UNION_SIZE
        assert len(set(merged.subjects(EX.q, None))) == 1

    def test_a_top_level_id_beside_graph_is_a_named_graph(self, tmp_path: Path) -> None:
        """It used to be cast to an empty file at exit 0: the plain graph held nothing."""
        source = _write(
            tmp_path,
            "g.jsonld",
            '{"@context": {"ex": "http://example.org/"}, "@id": "ex:g",'
            ' "@graph": [{"@id": "ex:a", "ex:p": "v"}]}\n',
        )
        _assert_refused(
            _cast(source, "-f", "turtle"),
            "Casting g.jsonld...\n" + self.GUARD.format(name="g.jsonld", targets="turtle"),
        )
        kept = _cast(source, "-f", "trig")
        assert kept.exit_code == 0, kept.output
        assert _shape(_read(kept.stdout, "trig")) == (0, {str(EX.g): 1})

    def test_a_top_level_graph_alone_is_the_default_graph(self, tmp_path: Path) -> None:
        source = _write(
            tmp_path,
            "plain.jsonld",
            '{"@context": {"ex": "http://example.org/"},'
            ' "@graph": [{"@id": "ex:a", "ex:p": "v"}]}\n',
        )
        result = _cast(source, "-f", "nt")
        assert result.exit_code == 0, result.output
        assert result.stdout == '<http://example.org/a> <http://example.org/p> "v" .\n'

    def test_its_own_format_beside_a_quad_format_is_a_skip_not_a_refusal(
        self, tmp_path: Path
    ) -> None:
        source = _write(tmp_path, "d.jsonld", QUADS_JSONLD)
        out_dir = tmp_path / "out"
        result = _cast(source, "-f", "json-ld", "-f", "trig", "-o", out_dir)
        assert result.exit_code == 1, result.output
        assert "Flattened" not in result.stderr
        assert sorted(p.name for p in out_dir.iterdir()) == ["d.trig"]
        _assert_quads_kept(_read((out_dir / "d.trig").read_text(encoding="utf-8"), "trig"))

    def test_a_parse_error_comes_before_the_guard(self, tmp_path: Path) -> None:
        source = _write(tmp_path, "bad.jsonld", '{"@graph": [')
        result = _cast(source, "-f", "turtle")
        assert result.exit_code == 2, result.output
        assert "Failed to parse 'bad.jsonld' as json-ld" in result.stderr
        assert "named graphs" not in result.stderr


class TestCastN3Constructs:
    """A source with N3 formulae or variables is refused: no other format can hold them (#542)."""

    @pytest.mark.parametrize("with_output_dir", [True, False], ids=["-o", "pipe"])
    @pytest.mark.parametrize("fmt", ["turtle", "xml", "json-ld", "nt", "trig", "nquads"])
    def test_a_formula_is_refused_for_every_target(
        self, tmp_path: Path, fmt: str, with_output_dir: bool
    ) -> None:
        source = _write(tmp_path, "f.n3", FORMULA_N3)
        out_dir = tmp_path / "out"
        refusal = N3_REFUSED.format(name="f.n3", counts="1 statement with a formula ({ … })")
        if with_output_dir:
            result = _cast(source, "-f", fmt, "-o", out_dir)
            header = f"Casting f.n3...\n  Formats: {fmt}\n  Output:  {out_dir}/\n"
        else:
            result = _cast(source, "-f", fmt)
            header = "Casting f.n3...\n"
        _assert_refused(result, header + refusal)
        assert not out_dir.exists()

    @pytest.mark.parametrize(
        ("n3", "counts"),
        [
            ("@forAll :x .\n:a :p :x .\n", "1 statement with a variable"),
            (":a :p ?x .\n:b :p ?y .\n", "2 statements with a variable"),
            (
                "{ { :a :b :c } :says :d } => { :e :f :g } .\n",
                "1 statement with a formula ({ … })",
            ),
            (
                "{ :a :b :c } => { :d :e :f } .\n{ :g :h :i } :says :j .\n:k :p ?x .\n",
                "2 statements with a formula ({ … }), 1 with a variable",
            ),
        ],
        ids=["forAll", "question-mark", "nested-formula", "formulae-and-variable"],
    )
    @pytest.mark.parametrize("fmt", ["turtle", "nquads"])
    def test_each_construct_is_counted_by_statement(
        self, tmp_path: Path, n3: str, counts: str, fmt: str
    ) -> None:
        source = _write(tmp_path, "c.n3", "@prefix : <http://ex/> .\n" + n3)
        _assert_refused(
            _cast(source, "-f", fmt),
            "Casting c.n3...\n" + N3_REFUSED.format(name="c.n3", counts=counts),
        )

    @pytest.mark.parametrize(
        "n3",
        ["@forSome :y .\n:a :p :y .\n", ":a!:b :p :c .\n", ":a^:b :p :c .\n", ":a => :b .\n"],
        ids=["forSome", "path-forward", "path-backward", "implies-without-formula"],
    )
    @pytest.mark.parametrize("fmt", ["turtle", "nt", "nquads"])
    def test_n3_that_is_plain_rdf_still_casts(self, tmp_path: Path, n3: str, fmt: str) -> None:
        source = _write(tmp_path, "plain.n3", "@prefix : <http://ex/> .\n" + n3)
        expected = Graph()
        expected.parse(source, format="n3")
        result = _cast(source, "-f", fmt)
        assert result.exit_code == 0, result.output
        assert isomorphic(_default(_read(result.stdout, fmt)), expected)

    def test_a_parse_error_comes_before_the_refusal(self, tmp_path: Path) -> None:
        source = _write(tmp_path, "bad.n3", "@prefix : <http://ex/> .\n{ :a :b :c } => { :d :e .\n")
        result = _cast(source, "-f", "turtle")
        assert result.exit_code == 2, result.output
        assert "Failed to parse 'bad.n3' as n3" in result.stderr
        assert "N3 constructs" not in result.stderr


class TestCastConverterDatasets:
    """The library path: ``CastConverter.convert`` holds the same rules as the CLI."""

    def test_pipe_mode_trig_holds_the_default_graph(self, ttl_file: Path) -> None:
        result = CastConverter().convert(
            source=ttl_file, formats=["trig"], output_dir=None, pipe_mode=True
        )
        assert result.success and result.stdout_content is not None
        assert _shape(_read(result.stdout_content, "trig")) == (5, {})

    def test_pipe_mode_nquads_is_normalised(self, ttl_file: Path) -> None:
        result = CastConverter().convert(
            source=ttl_file, formats=["nquads"], output_dir=None, pipe_mode=True
        )
        assert result.success and result.stdout_content is not None
        assert "  ." not in result.stdout_content
        assert _shape(_read(result.stdout_content, "nquads")) == (5, {})

    def test_file_mode_nquads_is_normalised(self, ttl_file: Path, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        result = CastConverter().convert(
            source=ttl_file, formats=["nquads"], output_dir=out_dir, pipe_mode=False
        )
        assert result.success and result.written_files == [out_dir / "ontology.nq"]
        text = (out_dir / "ontology.nq").read_text(encoding="utf-8")
        assert "  ." not in text
        assert _shape(_read(text, "nquads")) == (5, {})

    @pytest.mark.parametrize("allow_flatten", [False, True])
    def test_quad_to_quad_keeps_every_graph(self, tmp_path: Path, allow_flatten: bool) -> None:
        source = _write(tmp_path, "d.nq", QUADS_NQ)
        out_dir = tmp_path / "out"
        result = CastConverter().convert(
            source=source,
            formats=["trig"],
            output_dir=out_dir,
            pipe_mode=False,
            allow_flatten=allow_flatten,
        )
        assert result.success and result.warnings == []
        _assert_quads_kept(_read((out_dir / "d.trig").read_text(encoding="utf-8"), "trig"))

    def test_flatten_merges_every_graph_not_only_the_default_one(self, tmp_path: Path) -> None:
        """``Dataset.triples()`` reads the default graph alone: 2 of these 6 triples."""
        source = _write(tmp_path, "d.nq", QUADS_NQ)
        result = CastConverter().convert(
            source=source,
            formats=["nquads", "nt", "turtle"],
            output_dir=tmp_path / "out",
            pipe_mode=False,
            allow_flatten=True,
        )
        assert result.success
        assert result.skipped_formats == ["nquads"]
        assert result.warnings == [
            "Flattened d.nq for nt, turtle: all named graphs merged into one graph.",
            "Skipping 'nquads': source and target format are the same.",
        ]
        for name, fmt in (("d.nt", "nt"), ("d.ttl", "turtle")):
            merged = Graph()
            merged.parse(tmp_path / "out" / name, format=fmt)
            assert len(merged) == QUADS_UNION_SIZE, name

    def test_jsonld_named_graphs_are_refused_with_an_error(self, tmp_path: Path) -> None:
        source = _write(tmp_path, "d.jsonld", QUADS_JSONLD)
        out_dir = tmp_path / "out"
        result = CastConverter().convert(
            source=source, formats=["turtle", "xml"], output_dir=out_dir, pipe_mode=False
        )
        assert not result.success and not result.partial_failure
        assert result.error == (
            "Source 'd.jsonld' holds named graphs but the requested target format(s) are "
            "single-graph: turtle, xml. Use --allow-flatten to merge all named graphs into the "
            "default graph, or choose a quad output format (trig, nquads)."
        )
        assert result.written_files == [] and not out_dir.exists()

    def test_jsonld_without_named_graphs_needs_no_flag(self, tmp_path: Path) -> None:
        graph = Graph()
        graph.parse(data=SIMPLE_TTL, format="turtle")
        source = _write(tmp_path, "ontology.jsonld", graph.serialize(format="json-ld"))
        result = CastConverter().convert(
            source=source, formats=["turtle"], output_dir=None, pipe_mode=True
        )
        assert result.success and result.warnings == []

    def test_n3_formulae_are_refused_with_an_error(self, tmp_path: Path) -> None:
        source = _write(tmp_path, "f.n3", FORMULA_N3)
        out_dir = tmp_path / "out"
        result = CastConverter().convert(
            source=source, formats=["turtle", "nquads"], output_dir=out_dir, pipe_mode=False
        )
        assert not result.success and not result.partial_failure
        assert result.error == (
            "Source 'f.n3' holds N3 constructs that no other format can carry: 1 statement with "
            "a formula ({ … }). Only N3 can hold them, so there is nothing cast can write."
        )
        assert result.written_files == [] and not out_dir.exists()


class TestCastStatementsThatAreNotRdf:
    """N3 allows a literal subject and a predicate that is not an IRI; no other format does.

    Without the refusal they are written as N-Quads and N-Triples that do not parse, or dropped.
    """

    MISPLACED = "a literal subject or a predicate that is not an IRI"

    @pytest.mark.parametrize(
        ("n3", "counts"),
        [
            ('"lit" :p :b .\n', "1 statement with " + MISPLACED),
            ("7 :p :b .\n", "1 statement with " + MISPLACED),
            (":a _:p :b .\n", "1 statement with " + MISPLACED),
            ("@forSome :x .\n:a :x :b .\n", "1 statement with " + MISPLACED),
            (':a "p" :b .\n', "1 statement with " + MISPLACED),
            (":a :q!:r :b .\n", "1 statement with " + MISPLACED),
            ('"lit" :p :b .\n:a _:p :b .\n:x :y :z .\n', "2 statements with " + MISPLACED),
            (
                '{ :a :b :c } => { :d :e :f } .\n:k :p ?x .\n"lit" :p :b .\n',
                "1 statement with a formula ({ … }), 1 with a variable, 1 with " + MISPLACED,
            ),
        ],
        ids=[
            "literal-subject",
            "number-subject",
            "blank-node-predicate",
            "forSome-predicate",
            "literal-predicate",
            "path-predicate",
            "two-statements",
            "all-three-kinds",
        ],
    )
    @pytest.mark.parametrize("fmt", ["turtle", "nt", "nquads"])
    def test_it_is_refused(self, tmp_path: Path, n3: str, counts: str, fmt: str) -> None:
        source = _write(tmp_path, "g.n3", "@prefix : <http://ex/> .\n" + n3)
        _assert_refused(
            _cast(source, "-f", fmt),
            "Casting g.n3...\n" + N3_REFUSED.format(name="g.n3", counts=counts),
        )

    def test_a_turtle_source_rdflib_reads_one_from_is_refused_too(self, tmp_path: Path) -> None:
        """rdflib's Turtle parser lets a blank-node predicate through, so the check is on content."""
        source = _write(tmp_path, "bp.ttl", "<http://ex/a> _:p <http://ex/b> .\n")
        _assert_refused(
            _cast(source, "-f", "nt"),
            "Casting bp.ttl...\n"
            + N3_REFUSED.format(name="bp.ttl", counts="1 statement with " + self.MISPLACED),
        )

    def test_n3_output_can_hold_it_so_that_request_goes_ahead(self, tmp_path: Path) -> None:
        source = _write(tmp_path, "bp.ttl", "<http://ex/a> _:p <http://ex/b> .\n")
        result = _cast(source, "-f", "n3")
        assert result.exit_code == 0, result.output
        written = Graph()
        written.parse(data=result.stdout, format="n3")
        assert len(written) == 1

    def test_n3_beside_another_format_is_refused_whole(self, tmp_path: Path) -> None:
        source = _write(tmp_path, "bp.ttl", "<http://ex/a> _:p <http://ex/b> .\n")
        out_dir = tmp_path / "out"
        result = _cast(source, "-f", "n3", "-f", "nt", "-o", out_dir)
        assert result.exit_code == 2, result.output
        assert not out_dir.exists()


class TestCastReviewFindings:
    """Shapes the independent review of #544 found untested."""

    def test_the_default_graph_term_older_rdflib_writes_is_removed(self) -> None:
        """rdflib before 7.3 names the default graph in N-Quads by its internal IRI."""

        class OldRdflibDataset:
            def serialize(self, destination, format):  # type: ignore[no-untyped-def]  # noqa: A002
                destination.write(
                    b'<http://ex/a> <http://ex/p> "v" <urn:x-rdflib:default> .\n'
                    b'<http://ex/a> <http://ex/p> "w" <http://ex/g> .\n'
                    b'<http://ex/a> <http://ex/p> "x"  .\n\n'
                )

        content = CastConverter._serialise(OldRdflibDataset(), "nquads")  # type: ignore[arg-type]
        assert content == (
            b'<http://ex/a> <http://ex/p> "v" .\n'
            b'<http://ex/a> <http://ex/p> "w" <http://ex/g> .\n'
            b'<http://ex/a> <http://ex/p> "x" .\n\n'
        )

    def test_a_repeated_format_is_named_once_in_the_flatten_warning(self, tmp_path: Path) -> None:
        source = _write(tmp_path, "d.trig", QUADS_TRIG)
        result = _cast(
            source, "-f", "ttl", "-f", "ttl", "-f", "nq", "--allow-flatten", "-o", tmp_path / "out"
        )
        assert (
            "  ⚠ Flattened d.trig for turtle: all named graphs merged into one graph.\n"
            in result.stderr
        )

    def test_a_blank_node_graph_name_used_in_the_default_graph_is_still_the_name(
        self, tmp_path: Path
    ) -> None:
        source = _write(
            tmp_path,
            "bg.nq",
            "<http://ex/a> <http://ex/p> <http://ex/b> _:g .\n"
            "<http://ex/doc> <http://ex/hasGraph> _:g .\n",
        )
        result = _cast(source, "-f", "trig")
        assert result.exit_code == 0, result.output
        dataset = _read(result.stdout, "trig")
        names = {g for _s, _p, _o, g in dataset.quads((None, None, None, None)) if g != DEFAULT_ID}
        assert set(_default(dataset).objects()) == names and len(names) == 1

    def test_a_blank_node_graph_name_used_in_a_named_graph_is_still_the_name(
        self, tmp_path: Path
    ) -> None:
        source = _write(
            tmp_path,
            "bg.nq",
            "<http://ex/a> <http://ex/p> <http://ex/b> _:g .\n"
            "<http://ex/doc> <http://ex/hasGraph> _:g <http://ex/meta> .\n",
        )
        result = _cast(source, "-f", "trig")
        assert result.exit_code == 0, result.output
        dataset = _read(result.stdout, "trig")
        names = {g for _s, _p, _o, g in dataset.quads((None, None, None, None)) if g != DEFAULT_ID}
        objects = {
            o for _s, _p, o, _g in dataset.quads((None, URIRef("http://ex/hasGraph"), None, None))
        }
        assert objects < names

    def test_the_same_shape_survives_trig_to_nquads(self, tmp_path: Path) -> None:
        source = _write(
            tmp_path,
            "bg.trig",
            "<http://ex/meta> { <http://ex/doc> <http://ex/hasGraph> _:g . }\n"
            "_:g { <http://ex/a> <http://ex/p> <http://ex/b> . }\n",
        )
        result = _cast(source, "-f", "nquads")
        assert result.exit_code == 0, result.output
        dataset = _read(result.stdout, "nquads")
        names = {g for _s, _p, _o, g in dataset.quads((None, None, None, None)) if g != DEFAULT_ID}
        objects = {
            o for _s, _p, o, _g in dataset.quads((None, URIRef("http://ex/hasGraph"), None, None))
        }
        assert objects < names

    def test_an_empty_jsonld_named_graph_is_not_a_named_graph(self, tmp_path: Path) -> None:
        source = _write(
            tmp_path,
            "e.jsonld",
            '{"@context": {"ex": "http://example.org/"}, "@graph": ['
            '{"@id": "ex:a", "ex:p": "v"}, {"@id": "ex:g1", "@graph": []}]}\n',
        )
        result = _cast(source, "-f", "nt")
        assert result.exit_code == 0, result.output
        assert result.stdout == '<http://example.org/a> <http://example.org/p> "v" .\n'


# ---------------------------------------------------------------------------
# A graph named by a blank node, and used as an object (#545)
# ---------------------------------------------------------------------------

_A = "<http://ex/a> <http://ex/p> <http://ex/b>"
_DOC = "<http://ex/doc> <http://ex/hasGraph>"
_META = "<http://ex/meta>"
_FIRST, _REST, _NIL = f"<{RDF.first}>", f"<{RDF.rest}>", f"<{RDF.nil}>"

#: Each row is a dataset as N-Quads statements, and what :func:`_identity` says it holds. In
#: every one ``_:g`` names a graph and is used as an object. rdflib's own TriG serialiser
#: loses the link in all but ``default``, ``also a subject``, the two ``twice`` rows and
#: ``heads a list``.
GRAPH_NAME_ROWS: dict[str, tuple[list[str], tuple[int, int, int, int]]] = {
    "in its own graph": ([f"{_A} _:g", f"{_DOC} _:g _:g"], (2, 1, 1, 0)),
    "in an IRI-named graph": ([f"{_A} _:g", f"{_DOC} _:g {_META}"], (2, 1, 1, 0)),
    "in another blank-node graph": ([f"{_A} _:g", f"{_DOC} _:g _:h"], (2, 2, 1, 0)),
    "in the default graph": ([f"{_A} _:g", f"{_DOC} _:g"], (2, 1, 1, 0)),
    "also a subject": (
        [f"{_A} _:g", f"{_DOC} _:g {_META}", f"_:g <http://ex/created> <http://ex/x> {_META}"],
        (3, 1, 1, 1),
    ),
    "twice in one graph": (
        [f"{_A} _:g", f"{_DOC} _:g {_META}", f"<http://ex/doc2> <http://ex/hasGraph> _:g {_META}"],
        (3, 1, 2, 0),
    ),
    "twice in two graphs": (
        [f"{_A} _:g", f"{_DOC} _:g {_META}", f"{_DOC} _:g <http://ex/meta2>"],
        (3, 1, 2, 0),
    ),
    "a list member": (
        [
            f"{_A} _:g",
            f"<http://ex/doc> <http://ex/graphs> _:l {_META}",
            f"_:l {_FIRST} _:g {_META}",
            f"_:l {_REST} {_NIL} {_META}",
        ],
        (4, 2, 1, 0),
    ),
    "heads a list": (
        [f"_:g {_FIRST} <http://ex/x> _:g", f"_:g {_REST} {_NIL} _:g", f"{_DOC} _:g _:g"],
        (3, 1, 1, 2),
    ),
    "two graphs naming each other": (
        [f"{_DOC} _:h _:g", "<http://ex/doc2> <http://ex/hasGraph> _:g _:h"],
        (2, 2, 2, 0),
    ),
    "a member of a nested list": (
        [
            f"{_A} _:g",
            f"<http://ex/doc> <http://ex/graphs> _:l {_META}",
            f"_:l {_FIRST} _:m {_META}",
            f"_:l {_REST} {_NIL} {_META}",
            f"_:m {_FIRST} _:g {_META}",
            f"_:m {_REST} {_NIL} {_META}",
        ],
        (6, 3, 1, 0),
    ),
    "the only triple of its own graph": ([f"{_DOC} _:g _:g"], (1, 1, 1, 0)),
    "the object of a blank-node subject": (
        [
            f"{_A} _:g",
            f"<http://ex/doc> <http://ex/prov> _:x {_META}",
            f"_:x <http://ex/hasGraph> _:g {_META}",
        ],
        (3, 2, 1, 0),
    ),
}


def _terms(statement: str) -> tuple[str, str, str, str | None]:
    parts = statement.split(" ")
    return parts[0], parts[1], parts[2], parts[3] if len(parts) == 4 else None


def _as_nquads(statements: list[str]) -> str:
    return "".join(f"{statement} .\n" for statement in statements)


def _as_jsonld(statements: list[str]) -> str:
    def name(term: str) -> str:
        return term if term.startswith("_:") else term[1:-1]

    graphs: dict[str | None, list[dict[str, object]]] = {}
    for s, p, o, g in map(_terms, statements):
        graphs.setdefault(g, []).append({"@id": name(s), name(p): [{"@id": name(o)}]})
    document: list[dict[str, object]] = []
    for g, nodes in graphs.items():
        if g is None:
            document.extend(nodes)
        else:
            document.append({"@id": name(g), "@graph": nodes})
    return json.dumps(document)


#: The sources that can hold the rows. A TriG source cannot be cast to TriG (#330).
SOURCE_WRITERS = {"nquads": _as_nquads, "json-ld": _as_jsonld}


def _identity(dataset: Dataset) -> tuple[int, int, int, int]:
    """What a dataset holds, counted so that a blank node split in two shows.

    Returns:
        The statements, the distinct blank nodes (graph names included), the objects that
        are a graph's name, and the subjects that are a graph's name.
    """
    quads = list(dataset.quads((None, None, None, None)))
    names = {g for _s, _p, _o, g in quads if isinstance(g, BNode)}
    nodes = names | {term for s, _p, o, _g in quads for term in (s, o) if isinstance(term, BNode)}
    return (
        len(quads),
        len(nodes),
        sum(o in names for _s, _p, o, _g in quads),
        sum(s in names for s, _p, _o, _g in quads),
    )


def _trig_from(serialiser: type[TrigSerializer], dataset: Dataset) -> Dataset:
    buf = io.BytesIO()
    serialiser(dataset).serialize(buf)
    return _read(buf.getvalue().decode("utf-8"), "trig")


class _ListsTheDefaultGraphOnce(TrigSerializer):
    """rdflib's TriG serialiser, as it would be if it did not list the default graph twice."""

    def __init__(self, store: Dataset) -> None:
        super().__init__(store)
        self.contexts = list({context.identifier: context for context in self.contexts}.values())


class _KeepsNoReferenceCount(GUARDED_FORMATS["trig"]):  # type: ignore[misc]
    """Stands in for an rdflib whose TriG serialiser has no ``_references``.

    A simulation: nothing below it can serialise either, so it shows only what ``cast``
    does when the count is missing, not what such an rdflib would write.
    """

    def reset(self) -> None:
        super().reset()
        del self._references


class _CannotBeBuilt(GUARDED_FORMATS["trig"]):  # type: ignore[misc]
    """A TriG serialiser that fails as it is constructed, before anything is written."""

    def __init__(self, store: Dataset) -> None:
        raise ValueError("cannot be built")


NO_COUNT = (
    "this version of rdflib writes TriG in a way cast does not know, so a graph named by "
    "a blank node could lose its name. Use --format nquads, which keeps it"
)


class TestCastBlankNodeGraphNames:
    """In TriG, a blank node that names a graph is written with its label wherever it is used."""

    @pytest.mark.parametrize("with_output_dir", [False, True], ids=["pipe", "-o"])
    @pytest.mark.parametrize("source_format", SOURCE_WRITERS)
    @pytest.mark.parametrize("row", GRAPH_NAME_ROWS)
    def test_a_statement_that_points_at_the_graph_still_does(
        self, tmp_path: Path, row: str, source_format: str, with_output_dir: bool
    ) -> None:
        statements, held = GRAPH_NAME_ROWS[row]
        text = SOURCE_WRITERS[source_format](statements)
        # The fixture is what the row says it is, from this source format too.
        assert _identity(_read(text, source_format)) == held
        source = _write(tmp_path, f"bg{EXTENSION[source_format]}", text)
        result, written = _cast_to(source, "trig", tmp_path, with_output_dir=with_output_dir)
        assert result.exit_code == 0, result.output
        assert _identity(_read(written, "trig")) == held

    @pytest.mark.parametrize("with_output_dir", [False, True], ids=["pipe", "-o"])
    def test_a_blank_node_that_names_nothing_is_still_written_inline(
        self, tmp_path: Path, with_output_dir: bool
    ) -> None:
        source = _write(tmp_path, "z.nq", f"<http://ex/doc> <http://ex/p> _:z {_META} .\n")
        result, written = _cast_to(source, "trig", tmp_path, with_output_dir=with_output_dir)
        assert result.exit_code == 0, result.output
        assert "ns1:doc ns1:p [ ] ." in written

    def test_the_default_graph_row_does_not_rest_on_rdflib_listing_it_twice(self) -> None:
        """rdflib counts every default-graph triple twice, which is all that keeps this row.

        With the default graph listed once, as a fixed rdflib would, rdflib's serialiser
        loses the link there too, and the graph-name count keeps it.
        """
        statements, held = GRAPH_NAME_ROWS["in the default graph"]
        dataset = _read(_as_nquads(statements), "nquads")
        assert _identity(_trig_from(TrigSerializer, dataset)) == held
        assert _identity(_trig_from(_ListsTheDefaultGraphOnce, dataset)) != held
        counted = type("Counted", (GraphNameReferences, _ListsTheDefaultGraphOnce), {})
        assert _identity(_trig_from(counted, dataset)) == held

    @pytest.mark.parametrize("with_output_dir", [False, True], ids=["pipe", "-o"])
    def test_a_literal_beside_a_graph_name_keeps_its_form(
        self, tmp_path: Path, with_output_dir: bool
    ) -> None:
        """The serialiser is built over the CLI's own, which keeps literal forms (#377)."""
        statements, held = GRAPH_NAME_ROWS["in an IRI-named graph"]
        flag = f'<http://ex/a> <http://ex/flag> "1"^^<{XSD.boolean}> _:g .\n'
        source = _write(tmp_path, "bg.nq", _as_nquads(statements) + flag)
        result, written = _cast_to(source, "trig", tmp_path, with_output_dir=with_output_dir)
        assert result.exit_code == 0, result.output
        dataset = _read(written, "trig")
        assert _identity(dataset) == (held[0] + 1, *held[1:])
        (literal,) = (
            o for _s, _p, o, _g in dataset.quads((None, URIRef("http://ex/flag"), None, None))
        )
        assert (str(literal), literal.datatype) == ("1", XSD.boolean)

    @pytest.mark.parametrize("pipe_mode", [True, False], ids=["pipe", "file"])
    def test_the_library_path_keeps_the_name(self, tmp_path: Path, pipe_mode: bool) -> None:
        statements, held = GRAPH_NAME_ROWS["in an IRI-named graph"]
        source = _write(tmp_path, "bg.nq", _as_nquads(statements))
        result = CastConverter().convert(
            source=source, formats=["trig"], output_dir=tmp_path / "out", pipe_mode=pipe_mode
        )
        assert result.success, result.error
        if pipe_mode:
            assert result.stdout_content is not None
            written = result.stdout_content
        else:
            written = (tmp_path / "out" / "bg.trig").read_text(encoding="utf-8")
        assert _identity(_read(written, "trig")) == held

    def test_without_a_reference_count_the_name_is_refused_not_lost(self, tmp_path: Path) -> None:
        """If rdflib drops ``_references``, the cast fails and says where to go."""
        statements, _held = GRAPH_NAME_ROWS["in an IRI-named graph"]
        source = _write(tmp_path, "bg.nq", _as_nquads(statements))
        with patch.dict(GUARDED_FORMATS, {"trig": _KeepsNoReferenceCount}):
            piped = _cast(source, "-f", "trig")
            to_file, written = _cast_to(source, "trig", tmp_path, with_output_dir=True)
            beside = _cast(
                source, "-f", "trig", "-f", "ttl", "--allow-flatten", "-o", tmp_path / "b"
            )
        assert piped.exit_code == 2, piped.output
        assert piped.stdout == ""
        assert piped.stderr.endswith(f"✗ Failed to serialise to trig: {NO_COUNT}\n")
        assert to_file.exit_code == 2, to_file.output
        assert f"⚠ Failed to write bg.trig (trig): {NO_COUNT}\n" in to_file.stderr
        # The file is opened before the serialiser runs, as rdflib does it: what a failed
        # write leaves behind is #409's.
        assert written == ""
        assert beside.exit_code == 1, beside.output
        assert f"⚠ Failed to write bg.trig (trig): {NO_COUNT}\n" in beside.stderr
        assert (tmp_path / "b" / "bg.ttl").exists()

    def test_a_serialiser_that_cannot_be_built_leaves_no_file(self, tmp_path: Path) -> None:
        """The serialiser is built before the file is opened, as rdflib does it."""
        statements, _held = GRAPH_NAME_ROWS["in an IRI-named graph"]
        source = _write(tmp_path, "bg.nq", _as_nquads(statements))
        with patch.dict(GUARDED_FORMATS, {"trig": _CannotBeBuilt}):
            result = _cast(source, "-f", "trig", "-o", tmp_path / "out")
        assert result.exit_code == 2, result.output
        assert "⚠ Failed to write bg.trig (trig): cannot be built\n" in result.stderr
        assert not (tmp_path / "out" / "bg.trig").exists()

    def test_the_reference_count_is_needed_only_when_a_blank_node_names_a_graph(self) -> None:
        class NoCount:
            """A serialiser with nothing to count in: only ``store`` and ``preprocess``."""

            def __init__(self, store: Dataset) -> None:
                self.store = store
                self.preprocessed = False

            def preprocess(self) -> None:
                self.preprocessed = True

        counted = type("Counted", (GraphNameReferences, NoCount), {})
        iri_named = counted(_read(f"{_A} {_META} .\n", "nquads"))
        iri_named.preprocess()
        assert iri_named.preprocessed

        blank_named = counted(_read(f"{_A} _:g .\n", "nquads"))
        with pytest.raises(RuntimeError, match="Use --format nquads, which keeps it"):
            blank_named.preprocess()
        assert not blank_named.preprocessed
