"""Tests for the exit-code convention (#286) and orphan-class's default severity (#302).

The convention: 0 the command did what you asked; 1 it finished and has something
to report; 2 it did not do it (input refused, run failed, or a usage error).
"""

import ast
import io
from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner

from rdf_construct.cli import Refusal, _lint_exit_code, cli
from rdf_construct.lint import LintSummary, get_all_rules
from rdf_construct.lint.rules import Severity

REPO = Path(__file__).parent.parent
SRC = REPO / "src" / "rdf_construct"
EXAMPLES = REPO / "examples"
ANIMAL = EXAMPLES / "animal_ontology.ttl"

PREFIXES = """\
@prefix ex: <http://example.org/t#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
"""


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def malformed_yaml(tmp_path: Path) -> Path:
    path = tmp_path / "bad.yml"
    path.write_text("not: [valid\n")
    return path


def _ttl(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(PREFIXES + dedent(body))
    return path


# ---------------------------------------------------------------------------
# Refusal itself
# ---------------------------------------------------------------------------


class TestRefusal:
    def test_exit_code_is_two(self):
        assert Refusal("x").exit_code == 2

    def test_show_names_message_and_accepted(self, capsys):
        Refusal("Profile 'nope' not found in order.yml.", accepted=["a", "b"]).show()
        err = capsys.readouterr().err
        assert "Error: Profile 'nope' not found in order.yml." in err
        assert "Accepted: a, b" in err

    def test_show_without_accepted_has_no_accepted_line(self, capsys):
        Refusal("No source files specified.").show()
        assert "Accepted" not in capsys.readouterr().err

    def test_show_honours_file(self):
        buffer = io.StringIO()
        Refusal("x", accepted=["a"]).show(file=buffer)
        assert buffer.getvalue() == "Error: x\nAccepted: a\n"

    def test_config_refusal_names_the_file(self, runner, tmp_path, malformed_yaml):
        result = runner.invoke(
            cli, ["merge", "-c", str(malformed_yaml), "-o", str(tmp_path / "m.ttl")]
        )
        assert f"Could not load config {malformed_yaml}" in result.stderr


# ---------------------------------------------------------------------------
# Refusals exit 2, one per command group that used click.Abort
# ---------------------------------------------------------------------------


class TestRefusalsExitTwo:
    def test_order_unknown_profile(self, runner, tmp_path):
        result = runner.invoke(
            cli,
            [
                "order",
                str(EXAMPLES / "order" / "library.ttl"),
                str(EXAMPLES / "order" / "ordering.yml"),
                "-p",
                "nope",
                "-o",
                str(tmp_path / "out"),
            ],
        )
        assert result.exit_code == 2
        assert "Profile 'nope' not found" in result.stderr
        assert "Accepted:" in result.stderr
        assert not (tmp_path / "out").exists()

    def test_uml_unknown_context(self, runner, tmp_path):
        result = runner.invoke(
            cli,
            [
                "uml",
                str(ANIMAL),
                "-C",
                str(EXAMPLES / "uml" / "uml_contexts.yml"),
                "-c",
                "nope",
                "-o",
                str(tmp_path / "out"),
            ],
        )
        assert result.exit_code == 2
        assert "Context 'nope' not found" in result.stderr

    def test_uml_unknown_style(self, runner, tmp_path):
        result = runner.invoke(
            cli,
            [
                "uml",
                str(ANIMAL),
                "-C",
                str(EXAMPLES / "uml" / "uml_contexts.yml"),
                "--style-config",
                str(EXAMPLES / "uml" / "uml_styles.yml"),
                "-s",
                "nope",
                "-o",
                str(tmp_path / "out"),
            ],
        )
        assert result.exit_code == 2
        assert "Style scheme 'nope' not found" in result.stderr
        assert "Accepted:" in result.stderr

    def test_lint_malformed_config(self, runner, malformed_yaml):
        result = runner.invoke(cli, ["lint", "-c", str(malformed_yaml), str(ANIMAL)])
        assert result.exit_code == 2

    def test_lint_init_over_existing(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".rdf-lint.yml").write_text("# mine\n")
        result = runner.invoke(cli, ["lint", "--init", str(ANIMAL)])
        assert result.exit_code == 2
        assert "Config file already exists" in result.stderr
        assert (tmp_path / ".rdf-lint.yml").read_text() == "# mine\n"

    def test_merge_malformed_config(self, runner, tmp_path, malformed_yaml):
        out = tmp_path / "merged.ttl"
        result = runner.invoke(cli, ["merge", "-c", str(malformed_yaml), "-o", str(out)])
        assert result.exit_code == 2
        assert "Could not load config" in result.stderr
        assert not out.exists()

    def test_split_needs_a_mode(self, runner, tmp_path):
        result = runner.invoke(
            cli,
            ["split", str(EXAMPLES / "split" / "split_monolith.ttl"), "-o", str(tmp_path / "o")],
        )
        assert result.exit_code == 2
        assert "--by-namespace or --config" in result.stderr

    def test_split_malformed_config(self, runner, tmp_path, malformed_yaml):
        result = runner.invoke(
            cli,
            [
                "split",
                str(EXAMPLES / "split" / "split_monolith.ttl"),
                "-c",
                str(malformed_yaml),
                "-o",
                str(tmp_path / "o"),
            ],
        )
        assert result.exit_code == 2
        assert "Could not load config" in result.stderr

    def test_refactor_rename_from_without_to(self, runner, tmp_path):
        result = runner.invoke(
            cli,
            [
                "refactor",
                "rename",
                str(EXAMPLES / "refactor" / "typos.ttl"),
                "--from",
                "ex:A",
                "-o",
                str(tmp_path / "r.ttl"),
            ],
        )
        assert result.exit_code == 2
        assert "--from requires --to" in result.stderr

    def test_refactor_rename_malformed_config(self, runner, malformed_yaml):
        result = runner.invoke(cli, ["refactor", "rename", "-c", str(malformed_yaml)])
        assert result.exit_code == 2

    def test_refactor_deprecate_needs_entity(self, runner, tmp_path):
        result = runner.invoke(
            cli,
            [
                "refactor",
                "deprecate",
                str(EXAMPLES / "refactor" / "legacy.ttl"),
                "-o",
                str(tmp_path / "d.ttl"),
            ],
        )
        assert result.exit_code == 2
        assert "--entity is required" in result.stderr

    def test_localise_config_init_over_existing(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "localise.yml").write_text("# mine\n")
        result = runner.invoke(cli, ["localise", "config", "--init"])
        assert result.exit_code == 2
        assert (tmp_path / "localise.yml").read_text() == "# mine\n"

    def test_stats_compare_needs_two_files(self, runner):
        result = runner.invoke(cli, ["stats", "--compare", str(ANIMAL)])
        assert result.exit_code == 2

    def test_shacl_gen_malformed_config(self, runner, tmp_path, malformed_yaml):
        result = runner.invoke(
            cli,
            ["shacl-gen", str(ANIMAL), "-C", str(malformed_yaml), "-o", str(tmp_path / "s.ttl")],
        )
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# lint: findings exit 1, gated by --fail-on
# ---------------------------------------------------------------------------


def _summary(errors: int = 0, warnings: int = 0, info: int = 0) -> LintSummary:
    return LintSummary(total_errors=errors, total_warnings=warnings, total_info=info)


class TestLintExitCode:
    @pytest.mark.parametrize(
        ("summary", "fail_on", "expected"),
        [
            (_summary(), "error", 0),
            (_summary(), "info", 0),
            (_summary(errors=1), "error", 1),
            (_summary(errors=1), "warning", 1),
            (_summary(errors=1), "info", 1),
            (_summary(errors=1), "never", 0),
            (_summary(warnings=1), "error", 0),
            (_summary(warnings=1), "warning", 1),
            (_summary(warnings=1), "info", 1),
            (_summary(warnings=1), "never", 0),
            (_summary(info=1), "error", 0),
            (_summary(info=1), "warning", 0),
            (_summary(info=1), "info", 1),
            (_summary(info=1), "never", 0),
        ],
    )
    def test_threshold(self, summary, fail_on, expected):
        assert _lint_exit_code(summary, fail_on) == expected

    def test_engine_reports_no_exit_code(self):
        assert not hasattr(LintSummary(), "exit_code")

    def test_error_findings_exit_one_by_default(self, runner, tmp_path):
        path = _ttl(
            tmp_path,
            "dangling.ttl",
            """\
            ex:Child a owl:Class ; rdfs:label "Child" ; rdfs:comment "C." ;
                rdfs:subClassOf ex:Missing .
            """,
        )
        result = runner.invoke(cli, ["lint", str(path)])
        assert "error[dangling-reference]" in result.output
        assert result.exit_code == 1

    def test_warnings_only_exit_zero_by_default(self, runner, tmp_path):
        path = _ttl(tmp_path, "warn.ttl", "ex:Thing a owl:Class .\n")
        result = runner.invoke(cli, ["lint", str(path)])
        assert "warning[" in result.output
        assert result.exit_code == 0

    def test_warnings_exit_one_with_fail_on_warning(self, runner, tmp_path):
        path = _ttl(tmp_path, "warn.ttl", "ex:Thing a owl:Class .\n")
        result = runner.invoke(cli, ["lint", "--fail-on", "warning", str(path)])
        assert result.exit_code == 1

    def test_fail_on_rejects_unknown_value(self, runner):
        result = runner.invoke(cli, ["lint", "--fail-on", "sometimes", str(ANIMAL)])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# #302: orphan-class defaults to warning
# ---------------------------------------------------------------------------


class TestOrphanClassDefault:
    def test_default_severity_is_warning(self):
        assert get_all_rules()["orphan-class"].default_severity == Severity.WARNING

    def test_root_class_only_exits_zero(self, runner):
        # The shipped example's only error was orphan-class on its root class.
        result = runner.invoke(cli, ["lint", str(ANIMAL)])
        assert "warning[orphan-class]" in result.output
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Only the CLI layer exits (#286 panel)
# ---------------------------------------------------------------------------


def _exit_sites(path: Path) -> list[str]:
    """Return each sys.exit / SystemExit / click.Abort reference in a module."""
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Attribute) and node.attr in {"exit", "Abort"}:
            if isinstance(node.value, ast.Name) and node.value.id in {"sys", "click"}:
                found.append(f"{path.relative_to(SRC)}:{node.lineno} {node.value.id}.{node.attr}")
        elif isinstance(node, ast.Name) and node.id == "SystemExit":
            found.append(f"{path.relative_to(SRC)}:{node.lineno} SystemExit")
    return found


class TestExitPaths:
    def test_no_click_abort_in_cli(self):
        assert [s for s in _exit_sites(SRC / "cli.py") if "Abort" in s] == []

    def test_library_has_no_exit_path(self):
        sites = [
            site
            for path in sorted(SRC.rglob("*.py"))
            if path != SRC / "cli.py"
            for site in _exit_sites(path)
        ]
        assert sites == []
