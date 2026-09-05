"""Tests for `order`'s default output directory.

`-o/--outdir` defaulted to ``src/ontology``, so a bare ``order`` run silently
created a two-level tree wherever the user happened to be standing — a Python
packaging convention that says nothing about ordered RDF, and the reason this
repo carries a gitignored ``src/ontology/`` at all. The default is now
``ordered``, matching ``uml`` → ``diagrams``, ``docs`` → ``docs`` and
``split`` → ``modules``.

Nothing asserted the default before, which is how it survived this long.

Relates to: #128
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from rdf_construct.cli import cli
from rdf_construct.core import OrderingConfig

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"

SOURCE = EXAMPLES / "animal_ontology.ttl"
CONFIG = EXAMPLES / "order" / "sample_profile.yml"


class TestDefaultOutdir:
    """A bare `order` run writes to `ordered/`, relative to the caller."""

    def test_bare_run_writes_to_ordered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(cli, ["order", str(SOURCE), str(CONFIG)])
        assert result.exit_code == 0, result.output

        outdir = tmp_path / "ordered"
        assert outdir.is_dir()

        for prof_name in OrderingConfig(CONFIG).list_profiles():
            assert (outdir / f"{SOURCE.stem}-{prof_name}.ttl").is_file()

    def test_bare_run_creates_no_src_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The old default built `src/ontology/` two levels deep, unasked."""
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(cli, ["order", str(SOURCE), str(CONFIG)])
        assert result.exit_code == 0, result.output

        assert not (tmp_path / "src").exists()

    def test_explicit_outdir_still_wins_and_nests(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicit `-o` is the user's word, including a path yet to exist.

        `PROJECT_SETUP.md` documents `-o output/ordered`, which only works
        because the command creates parents.
        """
        monkeypatch.chdir(tmp_path)
        outdir = tmp_path / "output" / "ordered"
        result = CliRunner().invoke(cli, ["order", str(SOURCE), str(CONFIG), "-o", str(outdir)])
        assert result.exit_code == 0, result.output

        assert list(outdir.glob("*.ttl"))
        assert not (tmp_path / "ordered").exists()


class TestHelpStatesTheDefault:
    """Whatever the default is, `--help` has to say so."""

    def test_help_names_ordered(self) -> None:
        result = CliRunner().invoke(cli, ["order", "--help"])
        assert result.exit_code == 0
        assert "default: ordered" in result.output
        assert "src/ontology" not in result.output
