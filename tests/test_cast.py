"""Tests for the cast command and core/formats module."""

from __future__ import annotations

import io
from pathlib import Path
from textwrap import dedent
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIMPLE_TTL = dedent("""\
    @prefix ex: <http://example.org/> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

    ex:Thing a owl:Class ;
        rdfs:label "Thing" .

    ex:hasPart a owl:ObjectProperty ;
        rdfs:domain ex:Thing ;
        rdfs:range ex:Thing .
""")

SIMPLE_TRIG = dedent("""\
    @prefix ex: <http://example.org/> .

    ex:graph1 {
        ex:Thing a <http://www.w3.org/2002/07/owl#Class> .
    }

    ex:graph2 {
        ex:OtherThing a <http://www.w3.org/2002/07/owl#Class> .
    }
""")


@pytest.fixture()
def ttl_file(tmp_path: Path) -> Path:
    """Write a simple Turtle file and return its path."""
    p = tmp_path / "ontology.ttl"
    p.write_text(SIMPLE_TTL, encoding="utf-8")
    return p


@pytest.fixture()
def trig_file(tmp_path: Path) -> Path:
    """Write a simple TriG file and return its path."""
    p = tmp_path / "multi.trig"
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

    def test_source_equals_target_format_skips_with_warning(
        self, ttl_file: Path, tmp_path: Path
    ) -> None:
        converter = CastConverter()
        result = converter.convert(
            source=ttl_file,
            formats=["turtle"],
            output_dir=tmp_path,
            pipe_mode=False,
        )
        # Should succeed overall but have a warning and no output file
        assert result.success
        assert result.written_files == []
        assert any("source" in w.lower() or "skip" in w.lower() for w in result.warnings)

    def test_quad_source_to_single_graph_raises(
        self, trig_file: Path, tmp_path: Path
    ) -> None:
        converter = CastConverter()
        result = converter.convert(
            source=trig_file,
            formats=["turtle"],
            output_dir=tmp_path,
            pipe_mode=False,
        )
        assert not result.success
        assert result.error is not None
        assert (
            "flatten" in result.error.lower()
            or "quad" in result.error.lower()
            or "named graph" in result.error.lower()
        )

    def test_quad_source_with_allow_flatten_succeeds(
        self, trig_file: Path, tmp_path: Path
    ) -> None:
        converter = CastConverter()
        result = converter.convert(
            source=trig_file,
            formats=["turtle"],
            output_dir=tmp_path,
            pipe_mode=False,
            allow_flatten=True,
        )
        assert result.success
        assert len(result.written_files) == 1
        # Flattening should produce a warning
        assert any("flatten" in w.lower() or "named graph" in w.lower() for w in result.warnings)

    def test_partial_failure_reports_failed_formats(
        self, ttl_file: Path, tmp_path: Path
    ) -> None:
        """When one format fails but another succeeds, result reflects partial failure."""
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
                output_dir=tmp_path,
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

        We test this at the converter level rather than through the CLI runner
        so that stdout/stderr mixing does not interfere with RDF parsing.
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
        """Omitting --format should write xml and json-ld (not ttl) to output-dir."""
        from click.testing import CliRunner
        from rdf_construct.cli import cli

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["cast", str(ttl_file), "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 0
        written = list(tmp_path.iterdir())
        # Should have .rdf and .jsonld, but NOT .ttl (source format excluded)
        extensions = {f.suffix for f in written}
        assert ".rdf" in extensions
        assert ".jsonld" in extensions
        assert ".ttl" not in extensions

    def test_cast_allow_flatten_flag(self, trig_file: Path, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from rdf_construct.cli import cli

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "cast",
                str(trig_file),
                "--format", "turtle",
                "--output-dir", str(tmp_path),
                "--allow-flatten",
            ],
        )
        assert result.exit_code == 0

    def test_cast_quad_without_flatten_exits_two(self, trig_file: Path, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from rdf_construct.cli import cli

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "cast",
                str(trig_file),
                "--format", "turtle",
                "--output-dir", str(tmp_path),
            ],
        )
        assert result.exit_code == 2
