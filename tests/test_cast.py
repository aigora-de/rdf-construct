"""Tests for the cast command and core/formats module."""

from __future__ import annotations

import io
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from rdf_construct.core.formats import (
    FORMAT_ALIASES,
    FormatInfo,
    default_cast_formats,
    extension_for_format,
    infer_format,
    is_quad_format,
    normalise_format,
)
from rdf_construct.cast.converter import CastConverter, ConversionResult

if TYPE_CHECKING:
    from click.testing import Result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
        assert result.error is not None
        assert (
            "flatten" in result.error.lower()
            or "quad" in result.error.lower()
            or "named graph" in result.error.lower()
        )

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
        assert len(result.written_files) == 1
        # Flattening should produce a warning
        assert any("flatten" in w.lower() or "named graph" in w.lower() for w in result.warnings)

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


# ---------------------------------------------------------------------------
# Every requested format the source's own (#330)
# ---------------------------------------------------------------------------

SIMPLE_NT = "<http://example.org/a> <http://example.org/p> <http://example.org/b> .\n"
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

    def test_a_skip_beside_a_partial_failure_exits_one(
        self, ttl_file: Path, tmp_path: Path
    ) -> None:
        """A skip, a failure (nquads, #189) and a written file: finished, with findings."""
        out_dir = tmp_path / "out"
        result = self._invoke(
            str(ttl_file), "-f", "turtle", "-f", "nt", "-f", "nquads", "-o", str(out_dir)
        )
        assert result.exit_code == 1, result.output
        assert "  \u26a0 Skipping 'turtle': source and target format are the same.\n" in (
            result.stderr
        )
        assert "\u2717 Partial failure: nquads could not be converted.\n" in result.stderr
        assert sorted(p.name for p in out_dir.iterdir()) == ["ontology.nt"]

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

    def test_a_skip_and_a_failure_with_nothing_written_exits_two(
        self, trig_file: Path, tmp_path: Path
    ) -> None:
        """Nothing asked for was done, so 2 (#330, ruling 5); the nquads failure is #189."""
        out_dir = tmp_path / "out"
        result = self._invoke(str(trig_file), "-f", "trig", "-f", "nquads", "-o", str(out_dir))
        assert result.exit_code == 2, result.output
        assert "\u2717 All target format conversions failed: nquads\n" in result.stderr
        assert "Cast " not in result.stderr

    def test_help_defines_a_skip_as_exit_one(self) -> None:
        result = self._invoke("--help")
        assert result.exit_code == 0
        assert "a format was skipped (the" in result.output
        assert "source's own) or failed, and at least one was written" in result.output
