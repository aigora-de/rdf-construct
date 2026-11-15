"""Tests for lint's standalone flags (#202).

``--list-rules`` and ``--init`` run without a source. A source given alongside
either is ignored, the two cannot be combined, and a bare ``lint`` refuses with
our own message rather than Click's usage error.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from rdf_construct.cli import cli
from rdf_construct.lint import get_all_rules

REPO = Path(__file__).parent.parent
ANIMAL = REPO / "examples" / "animal_ontology.ttl"
CONFIG = ".rdf-lint.yml"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run in a scratch directory, so ``--init`` never writes into the repo."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestListRules:
    def test_runs_without_a_source(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["lint", "--list-rules"])
        assert result.exit_code == 0, result.output
        for rule_id in get_all_rules():
            assert rule_id in result.output

    def test_a_source_given_alongside_is_ignored(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["lint", str(ANIMAL), "--list-rules"])
        assert result.exit_code == 0, result.output
        assert "Available lint rules:" in result.output
        assert "Scanning" not in result.output


class TestInit:
    def test_runs_without_a_source(self, runner: CliRunner, cwd: Path) -> None:
        result = runner.invoke(cli, ["lint", "--init"])
        assert result.exit_code == 0, result.output
        assert (cwd / CONFIG).is_file()
        assert (cwd / CONFIG).read_text()

    def test_second_run_refuses_and_leaves_the_file(self, runner: CliRunner, cwd: Path) -> None:
        assert runner.invoke(cli, ["lint", "--init"]).exit_code == 0
        before = (cwd / CONFIG).read_bytes()

        result = runner.invoke(cli, ["lint", "--init"])
        assert result.exit_code == 2
        assert "Config file already exists" in result.stderr
        assert (cwd / CONFIG).read_bytes() == before


class TestCombined:
    @pytest.mark.parametrize(
        "argv",
        [
            ["lint", "--init", "--list-rules"],
            ["lint", "--list-rules", "--init", str(ANIMAL)],
        ],
        ids=["no-source", "with-source"],
    )
    def test_init_and_list_rules_refuse(
        self, runner: CliRunner, cwd: Path, argv: list[str]
    ) -> None:
        result = runner.invoke(cli, argv)
        assert result.exit_code == 2
        assert "--init" in result.stderr
        assert "--list-rules" in result.stderr
        assert not (cwd / CONFIG).exists()
        assert "Available lint rules:" not in result.output


class TestBareLint:
    def test_refuses_with_our_message(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["lint"])
        assert result.exit_code == 2
        assert "No source files specified." in result.stderr
        assert "Missing argument" not in result.stderr
