"""Tests for the exit-code convention (#286) and orphan-class's default severity (#302).

The convention: 0 the command did what you asked; 1 it finished and has something
to report; 2 it did not do it (input refused, run failed, or a usage error).
"""

import ast
import io
from pathlib import Path
from textwrap import dedent
from unittest import mock

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
# lint: a rule selection it cannot honour is refused (#203, #293, #208)
# ---------------------------------------------------------------------------

PROBLEMATIC = EXAMPLES / "lint" / "example_lint_problematic.ttl"
INFO_RULES = [
    "redundant-subclass",
    "property-no-domain",
    "property-no-range",
    "inconsistent-naming",
]


class TestLintRuleSelection:
    @pytest.fixture(autouse=True)
    def _no_found_config(self, tmp_path, monkeypatch):
        # Keep a stray .rdf-lint.yml above the cwd out of the run
        monkeypatch.chdir(tmp_path)

    def _refused(self, result) -> str:
        assert result.exit_code == 2
        assert "Scanning" not in result.output
        assert "Found" not in result.output
        return result.stderr

    def test_enable_typo_refused(self, runner):
        result = runner.invoke(cli, ["lint", "--enable", "orpahn-class", str(PROBLEMATIC)])
        stderr = self._refused(result)
        assert "Unknown rule 'orpahn-class' in --enable." in stderr
        assert "Available rules:" in stderr and "orphan-class" in stderr

    def test_disable_typo_refused(self, runner):
        result = runner.invoke(cli, ["lint", "--disable", "orpahn-class", str(PROBLEMATIC)])
        stderr = self._refused(result)
        assert "Unknown rule 'orpahn-class' in --disable." in stderr

    def test_enable_and_disable_same_rule_refused(self, runner):
        result = runner.invoke(
            cli,
            ["lint", "--enable", "orphan-class", "--disable", "orphan-class", str(PROBLEMATIC)],
        )
        stderr = self._refused(result)
        assert "No lint rules left to run" in stderr
        assert "enabled orphan-class; disabled orphan-class" in stderr
        assert "--enable replaces" not in stderr  # no config, no hint

    def test_disable_every_rule_refused(self, runner):
        args = ["lint", str(PROBLEMATIC)]
        for rule_id in get_all_rules():
            args += ["--disable", rule_id]
        stderr = self._refused(runner.invoke(cli, args))
        assert "No lint rules left to run: enabled all rules;" in stderr

    def test_config_disable_with_cli_enable_refused(self, runner, tmp_path):
        config = tmp_path / "lint.yml"
        config.write_text("disable:\n  - orphan-class\n  - missing-comment\n")
        result = runner.invoke(
            cli, ["lint", "-c", str(config), "--enable", "orphan-class", str(PROBLEMATIC)]
        )
        stderr = self._refused(result)
        assert "enabled orphan-class; disabled missing-comment, orphan-class" in stderr
        assert f"--enable replaces the enable: list in {config}" in stderr
        assert "--disable adds to its disable: list" in stderr

    def test_found_config_hint_names_it(self, runner, tmp_path):
        (tmp_path / ".rdf-lint.yml").write_text("disable:\n  - orphan-class\n")
        result = runner.invoke(cli, ["lint", "--enable", "orphan-class", str(PROBLEMATIC)])
        stderr = self._refused(result)
        assert "--enable replaces the enable: list in" in stderr
        assert ".rdf-lint.yml" in stderr

    def test_no_hint_when_config_selects_nothing(self, runner, tmp_path):
        config = tmp_path / "lint.yml"
        config.write_text("level: strict\n")
        result = runner.invoke(
            cli,
            [
                "lint",
                "-c",
                str(config),
                "--enable",
                "orphan-class",
                "--disable",
                "orphan-class",
                str(PROBLEMATIC),
            ],
        )
        stderr = self._refused(result)
        assert "No lint rules left to run" in stderr
        assert "--enable replaces" not in stderr

    def test_config_severity_typo_refused(self, runner, tmp_path):
        config = tmp_path / "lint.yml"
        config.write_text("severity:\n  orpahn-class: warning\n")
        result = runner.invoke(cli, ["lint", "-c", str(config), str(PROBLEMATIC)])
        assert result.exit_code == 2
        assert "Unknown rule 'orpahn-class' in 'severity' section" in result.stderr

    def test_refusal_does_not_depend_on_the_source(self, runner, tmp_path):
        broken = tmp_path / "broken.ttl"
        broken.write_text("this is not turtle .\n")
        result = runner.invoke(
            cli, ["lint", "--enable", "orphan-class", "--disable", "orphan-class", str(broken)]
        )
        assert "No lint rules left to run" in self._refused(result)

    def test_list_rules_ignores_selection(self, runner):
        result = runner.invoke(cli, ["lint", "--list-rules", "--enable", "orpahn-class"])
        assert result.exit_code == 0
        assert "orphan-class" in result.output

    def test_relaxed_runs_an_enabled_info_rule(self, runner):
        args = ["lint", "--level", "relaxed", "--enable", "property-no-domain", str(PROBLEMATIC)]
        result = runner.invoke(cli, args)
        assert "info[property-no-domain]" in result.output
        assert result.exit_code == 0
        assert runner.invoke(cli, args + ["--fail-on", "info"]).exit_code == 1

    @pytest.mark.parametrize("via_config", [False, True])
    def test_relaxed_runs_every_info_rule(self, runner, tmp_path, via_config):
        if via_config:
            config = tmp_path / "lint.yml"
            config.write_text("level: relaxed\n")
            args = ["lint", "-c", str(config), str(PROBLEMATIC)]
        else:
            args = ["lint", "--level", "relaxed", str(PROBLEMATIC)]
        result = runner.invoke(cli, args)
        for rule_id in INFO_RULES:
            assert f"info[{rule_id}]" in result.output
        assert "warning[" not in result.output
        assert "Found 5 errors, 0 warnings, 14 info in 1 file" in result.output
        assert result.exit_code == 1

    def test_guide_recipe_restores_previous_relaxed(self, runner, tmp_path):
        # LINT_GUIDE's "Many False Positives" recipe gives pre-v0.7.0 relaxed's counts
        config = tmp_path / "lint.yml"
        config.write_text(f"level: relaxed\ndisable: [{', '.join(INFO_RULES)}]\n")
        result = runner.invoke(cli, ["lint", "-c", str(config), str(PROBLEMATIC)])
        assert "Found 5 errors, 0 warnings, 9 info in 1 file" in result.output
        assert result.exit_code == 1


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


# ---------------------------------------------------------------------------
# #320: a crash exits 2, with its traceback
# ---------------------------------------------------------------------------


def _profiles_raising(runner: CliRunner, effect: BaseException):
    """Invoke ``profiles`` with its body replaced by one that raises ``effect``."""
    with mock.patch.object(cli.commands["profiles"], "callback", side_effect=effect):
        return runner.invoke(cli, ["profiles", str(ANIMAL)])


class TestCrashHandler:
    def test_crash_exits_two_with_traceback(self, runner):
        result = _profiles_raising(runner, RuntimeError("boom"))
        assert result.exit_code == 2
        assert isinstance(result.exception, SystemExit)
        assert isinstance(result.exception.__cause__, RuntimeError)
        assert "Traceback (most recent call last)" in result.stderr
        assert "RuntimeError: boom" in result.stderr
        assert "rdf-construct flatlined" in result.stderr

    def test_crash_writes_nothing_to_stdout(self, runner):
        result = _profiles_raising(runner, RuntimeError("boom"))
        assert result.stdout == ""

    def test_refusal_exits_two_without_traceback(self, runner):
        result = _profiles_raising(runner, Refusal("no"))
        assert result.exit_code == 2
        assert result.exception.__cause__ is None
        assert "Traceback" not in result.stderr
        assert result.stderr == "Error: no\n"

    def test_keyboard_interrupt_is_not_caught(self, runner):
        # Click's own main turns it into Abort: "Aborted!" at 1, no traceback.
        result = _profiles_raising(runner, KeyboardInterrupt())
        assert result.exit_code == 1
        assert "Aborted!" in result.stderr
        assert "Traceback" not in result.stderr

    def test_broken_pipe_is_not_caught(self, runner):
        # Click's own main handles EPIPE (``stats ... | head``) and exits 1, silently.
        result = _profiles_raising(runner, BrokenPipeError(32, "Broken pipe"))
        assert result.exit_code == 1
        assert result.stderr == ""

    @pytest.mark.parametrize(
        ("args", "expected"), [(["--help"], 0), (["--version"], 0), (["no-such-command"], 2)]
    )
    def test_click_exits_keep_their_codes(self, runner, args, expected):
        result = runner.invoke(cli, args)
        assert result.exit_code == expected
        assert "Traceback" not in result.stderr

    def test_outside_standalone_mode_the_exception_propagates(self):
        boom = RuntimeError("boom")
        with (
            mock.patch.object(cli.commands["profiles"], "callback", side_effect=boom),
            pytest.raises(RuntimeError, match="boom"),
        ):
            cli.main(["profiles", str(ANIMAL)], standalone_mode=False)
