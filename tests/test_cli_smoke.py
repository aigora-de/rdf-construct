"""CLI smoke test (#195): every command runs, and exits within the #286 convention.

This is a **liveness** check, not a correctness one. A command that passes it has run without
crashing and returned an exit code that fits the state it was put in. That is no evidence that it
did what it says. Correctness belongs to the post-write harness (#266), and determinism to #200.

Four tables:

- **The inventory:** the command tree that ``cli`` actually registers, so that adding a command
  fails this module until someone gives it rows here.
- **Three states per command:** clean (0), findings (1) and refused (2). Each of the three is the
  usage-level case: a ``Refusal`` path or a Click usage error.
- **Malformed input:** unparseable Turtle, YAML and PlantUML, each of which should be refused
  (2). Most of the crashes live here, and each is marked ``xfail(strict=True)`` against its
  issue.

Every refused row, in either table, also asserts that the refusal **wrote nothing** (#286, #266):
see ``assert_wrote_nothing``.
- **The realistic tier:** every command over each pinned IES ontology in ``tests/fixtures/ies/``
  (#317). Nothing in a well-formed file should be refused, so the code must be 0 or 1.

Known crashes are ``xfail(strict=True, reason="#N")``. The fix that makes one pass then has to
remove its marker, so the list cannot go quietly stale.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import click
import pytest
from click.testing import CliRunner, Result

from rdf_construct.cli import cli

if TYPE_CHECKING:
    # pytest.param() returns this, and pytest exports it only from its private package.
    from _pytest.mark import ParameterSet

REPO = Path(__file__).parent.parent
EXAMPLES = REPO / "examples"
SMOKE = REPO / "tests" / "fixtures" / "smoke"
IES = REPO / "tests" / "fixtures" / "ies"

ANIMAL = str(EXAMPLES / "animal_ontology.ttl")
SIMPLE = str(EXAMPLES / "simple_ontology.ttl")
CLEAN_LINT = str(EXAMPLES / "split" / "split_instances.ttl")
LIBRARY = str(EXAMPLES / "order" / "library.ttl")
ORDERING = str(EXAMPLES / "order" / "ordering.yml")
UML_CONTEXTS = str(EXAMPLES / "uml" / "uml_contexts.yml")
MONOLITH = str(EXAMPLES / "split" / "split_monolith.ttl")
TRANSLATIONS = str(SMOKE / "translations_de.yml")
MALFORMED_TTL = str(SMOKE / "malformed.ttl")
MALFORMED_YAML = str(SMOKE / "malformed.yml")

# The exit-code convention decided on #286.
STATE_CODE = {"clean": 0, "findings": 1, "refused": 2}

# Every command path ``cli`` should register. Derived from the code by ``_command_paths``, and
# asserted against this list, so that the inventory is a check and not an assumption.
EXPECTED_COMMANDS = {
    "cast",
    "contexts",
    "cq-test",
    "describe",
    "diff",
    "docs",
    "lint",
    "localise",
    "localise config",
    "localise extract",
    "localise init",
    "localise merge",
    "localise report",
    "merge",
    "order",
    "profiles",
    "puml2rdf",
    "refactor",
    "refactor deprecate",
    "refactor rename",
    "shacl-gen",
    "split",
    "stats",
    "uml",
}

# A leading "@tmp/" makes an argument a path under the test's tmp_path.
TMP = "@tmp/"


def assert_no_crash(result: Result) -> None:
    """Fail if the command ended in an exception that no code path handled.

    Call this **before** any assertion on the exit code. Under #286, a crash exits 2, which is
    also what a refusal exits. So "exit 2" alone never says whether the command refused its
    input or broke.

    **A crash** is an exception that no code path handled. Since #320 (P3a), the ``cli`` group's
    top-level handler turns one into ``SystemExit(2)``, the same type and code as a refusal, and
    keeps it distinguishable in two ways: the ``SystemExit`` is raised ``from`` the original
    exception, and the traceback goes to stderr. This helper reads the ``__cause__``. A
    ``Refusal`` (a ``click.ClickException``), usage errors and every deliberate exit reach
    ``CliRunner`` as a ``SystemExit`` with no cause. An exception that is not ``SystemExit`` at
    all means the handler was bypassed, and it is a crash too.

    This helper is the one place that decides what counts as a crash. Nothing else in this
    module may.

    **A known limit (#325).** ``diff``, ``shacl-gen``, ``cq-test``, ``stats`` and ``describe``
    wrap most of their body in ``except Exception`` and exit 2. A crash inside one of them
    reaches this helper as a deliberate ``SystemExit(2)``, and it cannot be seen as a crash.
    Their clean and IES rows still fail on the exit code, because 2 is not 0 or 1, but a
    refused row passes. ``assert_wrote_nothing`` does not close that gap: a crash that is
    swallowed before anything was written passes it too. The fix is to narrow those handlers,
    not to match exception names in stderr.

    Args:
        result: The ``CliRunner`` result to check.
    """
    exc = result.exception
    if isinstance(exc, SystemExit):
        exc = exc.__cause__
    if exc is not None:
        raise AssertionError(
            f"crashed with {type(exc).__name__}: {exc}\n\n--- output ---\n{result.output}"
        )


def snapshot(argv: list[str], tmp_path: Path) -> dict[str, str]:
    """Record every file and directory a command could write to, with a hash of each file.

    That is everything under ``tmp_path``, which is also the working directory, and every entry
    directly in the directory of each existing absolute path argument. Relative arguments are
    skipped, because a command name such as ``docs`` would otherwise match a directory. The second catches a command that
    writes beside its input, as ``cast``, ``shacl-gen`` and ``refactor deprecate`` do by default.

    Args:
        argv: The resolved arguments.
        tmp_path: The test's temporary directory.

    Returns:
        A map from each path to the SHA-256 of its contents, or ``"dir"`` for a directory.
    """
    roots = [path for path in map(Path, argv) if path.is_absolute() and path.exists()]
    entries = list(tmp_path.rglob("*"))
    for directory in {path.parent for path in roots if tmp_path not in path.parents}:
        entries.extend(directory.iterdir())
    return {
        str(entry): hashlib.sha256(entry.read_bytes()).hexdigest() if entry.is_file() else "dir"
        for entry in entries
    }


def assert_wrote_nothing(before: dict[str, str], after: dict[str, str]) -> None:
    """Fail if a refused command created, changed or deleted anything (#286, #266).

    The #286 convention says that 2 means "the command did not do it". A refusal that leaves a
    partial file behind did part of it. Call this after ``assert_no_crash``.

    Args:
        before: ``snapshot`` taken before the command ran.
        after: ``snapshot`` taken after it ran.
    """
    changed = sorted(set(before.items()) ^ set(after.items()))
    assert not changed, f"a refusal wrote to disk: {sorted({path for path, _ in changed})}"


def _command_paths(group: click.Group, prefix: str = "") -> set[str]:
    """Return every command path registered under ``group``, groups included."""
    paths: set[str] = set()
    for name, command in group.commands.items():
        path = f"{prefix}{name}"
        paths.add(path)
        if isinstance(command, click.Group):
            paths |= _command_paths(command, f"{path} ")
    return paths


def _leaf_commands() -> set[str]:
    """Return the command paths that do work, i.e. every path that is not a group."""
    groups = {name for name, command in cli.commands.items() if isinstance(command, click.Group)}
    return EXPECTED_COMMANDS - groups


def _resolve(argv: tuple[str, ...], tmp_path: Path) -> list[str]:
    return [str(tmp_path / arg[len(TMP) :]) if arg.startswith(TMP) else arg for arg in argv]


def _invoke(argv: tuple[str, ...], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Result:
    # Some commands write to the working directory (`localise config --init`, `lint --init`).
    monkeypatch.chdir(tmp_path)
    return CliRunner().invoke(cli, _resolve(argv, tmp_path))


@dataclass(frozen=True)
class Row:
    """One invocation and the state it puts the command in.

    Attributes:
        command: The command path the row exercises, as in ``EXPECTED_COMMANDS``.
        state: ``clean``, ``findings`` or ``refused``.
        argv: The arguments, with output paths written as ``@tmp/<name>``.
        existing: Files to create in the working directory first.
    """

    command: str
    state: str
    argv: tuple[str, ...]
    existing: tuple[str, ...] = ()


def _row(row: Row, *, xfail: str | None = None, label: str = "") -> "ParameterSet":
    marks = [pytest.mark.xfail(strict=True, reason=xfail)] if xfail else []
    test_id = f"{row.command}::{row.state}" + (f"-{label}" if label else "")
    return pytest.param(row, marks=marks, id=test_id)


# ---------------------------------------------------------------------------
# The inventory, and --help for every command
# ---------------------------------------------------------------------------


def test_command_inventory():
    """The registered commands are exactly the expected ones (#195).

    If this fails because you added a command, add it to ``EXPECTED_COMMANDS`` and give it rows
    in ``THREE_STATES`` and, if it reads an ontology, ``IES_INVOCATIONS``.
    """
    assert _command_paths(cli) == EXPECTED_COMMANDS


@pytest.mark.parametrize("command", sorted(EXPECTED_COMMANDS))
def test_help_exits_cleanly(command: str):
    result = CliRunner().invoke(cli, [*command.split(), "--help"])
    assert_no_crash(result)
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Three states per command
# ---------------------------------------------------------------------------

THREE_STATES = [
    _row(Row("cast", "clean", ("cast", ANIMAL, "-f", "nt", "-o", "@tmp/cast"))),
    _row(Row("cast", "refused", ("cast", ANIMAL, "-f", "nope"))),
    _row(Row("order", "clean", ("order", LIBRARY, ORDERING, "-o", "@tmp/order"))),
    _row(Row("order", "refused", ("order", LIBRARY, ORDERING, "-p", "nope", "-o", "@tmp/order"))),
    _row(Row("profiles", "clean", ("profiles", ORDERING))),
    _row(Row("profiles", "refused", ("profiles", "@tmp/missing.yml"))),
    _row(Row("uml", "clean", ("uml", ANIMAL, "-C", UML_CONTEXTS, "-o", "@tmp/uml"))),
    _row(
        Row("uml", "refused", ("uml", ANIMAL, "-C", UML_CONTEXTS, "-c", "nope", "-o", "@tmp/uml"))
    ),
    _row(Row("contexts", "clean", ("contexts", UML_CONTEXTS))),
    _row(Row("contexts", "refused", ("contexts", "@tmp/missing.yml"))),
    _row(Row("lint", "clean", ("lint", CLEAN_LINT))),
    _row(
        Row("lint", "findings", ("lint", str(EXAMPLES / "lint" / "example_lint_problematic.ttl")))
    ),
    _row(Row("lint", "refused", ("lint", "-c", MALFORMED_YAML, ANIMAL))),
    _row(
        Row("lint", "clean", ("lint", "--format", "json", CLEAN_LINT)), xfail="#201", label="json"
    ),
    _row(Row("lint", "clean", ("lint", "--list-rules")), xfail="#202", label="list-rules"),
    _row(Row("lint", "clean", ("lint", "--init")), xfail="#202", label="init"),
    _row(Row("diff", "clean", ("diff", ANIMAL, ANIMAL))),
    _row(Row("diff", "findings", ("diff", ANIMAL, SIMPLE))),
    _row(Row("diff", "refused", ("diff", ANIMAL, "@tmp/missing.ttl"))),
    _row(Row("docs", "clean", ("docs", ANIMAL, "-o", "@tmp/docs"))),
    _row(Row("docs", "refused", ("docs", ANIMAL, "--format", "nope", "-o", "@tmp/docs"))),
    _row(Row("shacl-gen", "clean", ("shacl-gen", ANIMAL, "-o", "@tmp/shapes.ttl"))),
    _row(
        Row("shacl-gen", "refused", ("shacl-gen", ANIMAL, "-C", MALFORMED_YAML, "-o", "@tmp/s.ttl"))
    ),
    _row(Row("puml2rdf", "clean", ("puml2rdf", str(SMOKE / "diagram.puml"), "-o", "@tmp/d.ttl"))),
    _row(Row("puml2rdf", "refused", ("puml2rdf", "@tmp/missing.puml"))),
    _row(
        Row(
            "cq-test",
            "clean",
            ("cq-test", ANIMAL, str(EXAMPLES / "cq-test" / "cq_tests_animal.yml")),
        )
    ),
    _row(Row("cq-test", "findings", ("cq-test", ANIMAL, str(SMOKE / "cq_failing.yml")))),
    _row(Row("cq-test", "refused", ("cq-test", ANIMAL, MALFORMED_YAML))),
    _row(Row("stats", "clean", ("stats", ANIMAL))),
    _row(Row("stats", "refused", ("stats", "--compare", ANIMAL))),
    _row(Row("describe", "clean", ("describe", ANIMAL))),
    _row(Row("describe", "refused", ("describe", ANIMAL, "--format", "nope"))),
    _row(
        Row(
            "merge",
            "clean",
            (
                "merge",
                str(EXAMPLES / "merge" / "merge_core.ttl"),
                str(EXAMPLES / "merge" / "merge_extension.ttl"),
                "-o",
                "@tmp/merged.ttl",
            ),
        )
    ),
    _row(
        Row(
            "merge",
            "findings",
            (
                "merge",
                str(EXAMPLES / "merge" / "merge_core.ttl"),
                str(EXAMPLES / "merge" / "merge_conflicting.ttl"),
                "--strategy",
                "mark_all",
                "-o",
                "@tmp/merged.ttl",
            ),
        )
    ),
    _row(Row("merge", "refused", ("merge", "-c", MALFORMED_YAML, "-o", "@tmp/merged.ttl"))),
    _row(Row("split", "clean", ("split", MONOLITH, "--by-namespace", "-o", "@tmp/split"))),
    _row(Row("split", "refused", ("split", MONOLITH, "-o", "@tmp/split"))),
    _row(
        Row(
            "split",
            "clean",
            ("split", MONOLITH, "-c", str(EXAMPLES / "split" / "split_config.yml"), "-o", "@tmp/s"),
        ),
        xfail="#175",
        label="config",
    ),
    _row(
        Row(
            "refactor rename",
            "clean",
            (
                "refactor",
                "rename",
                str(EXAMPLES / "refactor" / "typos.ttl"),
                "-c",
                str(EXAMPLES / "refactor" / "renames.yml"),
                "-o",
                "@tmp/renamed.ttl",
            ),
        )
    ),
    _row(
        Row(
            "refactor rename",
            "refused",
            ("refactor", "rename", str(EXAMPLES / "refactor" / "typos.ttl"), "-o", "@tmp/r.ttl"),
        )
    ),
    _row(
        Row(
            "refactor deprecate",
            "clean",
            (
                "refactor",
                "deprecate",
                str(EXAMPLES / "refactor" / "legacy.ttl"),
                "-c",
                str(EXAMPLES / "refactor" / "deprecations.yml"),
                "-o",
                "@tmp/deprecated.ttl",
            ),
        )
    ),
    _row(
        Row(
            "refactor deprecate",
            "findings",
            (
                "refactor",
                "deprecate",
                str(EXAMPLES / "refactor" / "legacy.ttl"),
                "--entity",
                "http://example.org/nope#X",
                "-o",
                "@tmp/deprecated.ttl",
            ),
        )
    ),
    _row(
        Row(
            "refactor deprecate",
            "refused",
            (
                "refactor",
                "deprecate",
                str(EXAMPLES / "refactor" / "legacy.ttl"),
                "-o",
                "@tmp/d.ttl",
            ),
        )
    ),
    _row(
        Row(
            "localise extract",
            "clean",
            ("localise", "extract", ANIMAL, "-l", "de", "-o", "@tmp/de.yml"),
        )
    ),
    _row(Row("localise extract", "refused", ("localise", "extract"))),
    _row(
        Row(
            "localise merge",
            "clean",
            ("localise", "merge", ANIMAL, TRANSLATIONS, "-o", "@tmp/l.ttl"),
        )
    ),
    _row(
        Row(
            "localise merge",
            "refused",
            ("localise", "merge", ANIMAL, "@tmp/missing.yml", "-o", "@tmp/l.ttl"),
        )
    ),
    _row(Row("localise report", "clean", ("localise", "report", ANIMAL, "-l", "en,de"))),
    _row(Row("localise report", "refused", ("localise", "report"))),
    _row(
        Row("localise init", "clean", ("localise", "init", ANIMAL, "-l", "ja", "-o", "@tmp/ja.yml"))
    ),
    _row(Row("localise init", "refused", ("localise", "init"))),
    _row(Row("localise config", "clean", ("localise", "config", "--init"))),
    _row(
        Row(
            "localise config",
            "refused",
            ("localise", "config", "--init"),
            existing=("localise.yml",),
        )
    ),
]


def test_every_command_has_a_three_state_row():
    """Every command that does work appears in ``THREE_STATES`` at least once."""
    covered = {param.values[0].command for param in THREE_STATES}
    assert covered == _leaf_commands()


@pytest.mark.parametrize("row", THREE_STATES)
def test_three_states(row: Row, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for name in row.existing:
        (tmp_path / name).write_text("")
    before = snapshot(_resolve(row.argv, tmp_path), tmp_path)
    result = _invoke(row.argv, tmp_path, monkeypatch)
    assert_no_crash(result)
    assert result.exit_code == STATE_CODE[row.state], result.output
    if row.state == "refused":
        assert_wrote_nothing(before, snapshot(_resolve(row.argv, tmp_path), tmp_path))


# ---------------------------------------------------------------------------
# Malformed input: every row should be refused at 2
# ---------------------------------------------------------------------------

MALFORMED = [
    _row(Row("cast", "refused", ("cast", MALFORMED_TTL, "-o", "@tmp/cast")), label="ttl"),
    _row(
        Row("order", "refused", ("order", MALFORMED_TTL, ORDERING, "-o", "@tmp/order")),
        xfail="#249",
        label="ttl",
    ),
    _row(
        Row("order", "refused", ("order", ANIMAL, MALFORMED_YAML, "-o", "@tmp/order")),
        xfail="#318",
        label="yaml",
    ),
    _row(Row("profiles", "refused", ("profiles", MALFORMED_YAML)), xfail="#318", label="yaml"),
    _row(
        Row("uml", "refused", ("uml", MALFORMED_TTL, "-C", UML_CONTEXTS, "-o", "@tmp/uml")),
        xfail="#321",
        label="ttl",
    ),
    _row(
        Row("uml", "refused", ("uml", ANIMAL, "-C", MALFORMED_YAML, "-o", "@tmp/uml")),
        xfail="#318",
        label="yaml",
    ),
    _row(Row("contexts", "refused", ("contexts", MALFORMED_YAML)), xfail="#318", label="yaml"),
    _row(Row("lint", "refused", ("lint", MALFORMED_TTL)), xfail="#322", label="ttl"),
    _row(Row("diff", "refused", ("diff", MALFORMED_TTL, ANIMAL)), label="ttl"),
    _row(
        Row("docs", "refused", ("docs", MALFORMED_TTL, "-o", "@tmp/docs")),
        xfail="#301",
        label="ttl",
    ),
    _row(
        Row("shacl-gen", "refused", ("shacl-gen", MALFORMED_TTL, "-o", "@tmp/shapes.ttl")),
        label="ttl",
    ),
    _row(
        Row("puml2rdf", "refused", ("puml2rdf", str(SMOKE / "malformed.puml"), "-o", "@tmp/p.ttl")),
        xfail="#151",
        label="puml",
    ),
    _row(
        Row("cq-test", "refused", ("cq-test", MALFORMED_TTL, str(SMOKE / "cq_failing.yml"))),
        label="ttl",
    ),
    _row(Row("stats", "refused", ("stats", MALFORMED_TTL)), label="ttl"),
    _row(Row("describe", "refused", ("describe", MALFORMED_TTL)), label="ttl"),
    _row(
        Row("merge", "refused", ("merge", MALFORMED_TTL, ANIMAL, "-o", "@tmp/merged.ttl")),
        label="ttl",
    ),
    _row(
        Row("split", "refused", ("split", MALFORMED_TTL, "--by-namespace", "-o", "@tmp/split")),
        xfail="#180",
        label="ttl",
    ),
    _row(
        Row(
            "refactor rename",
            "refused",
            (
                "refactor",
                "rename",
                MALFORMED_TTL,
                "--from",
                "http://example.org/A",
                "--to",
                "http://example.org/B",
                "-o",
                "@tmp/r.ttl",
            ),
        ),
        label="ttl",
    ),
    _row(
        Row(
            "refactor deprecate",
            "refused",
            (
                "refactor",
                "deprecate",
                MALFORMED_TTL,
                "--entity",
                "http://example.org/A",
                "-o",
                "@tmp/d.ttl",
            ),
        ),
        label="ttl",
    ),
    _row(
        Row(
            "localise extract",
            "refused",
            ("localise", "extract", MALFORMED_TTL, "-l", "de", "-o", "@tmp/de.yml"),
        ),
        xfail="#321",
        label="ttl",
    ),
    _row(
        Row(
            "localise extract",
            "refused",
            ("localise", "extract", ANIMAL, "-l", "de", "-c", MALFORMED_YAML, "-o", "@tmp/de.yml"),
        ),
        xfail="#318",
        label="yaml",
    ),
    _row(
        Row(
            "localise merge",
            "refused",
            ("localise", "merge", MALFORMED_TTL, TRANSLATIONS, "-o", "@tmp/l.ttl"),
        ),
        xfail="#321",
        label="ttl",
    ),
    _row(
        Row(
            "localise merge",
            "refused",
            ("localise", "merge", ANIMAL, MALFORMED_YAML, "-o", "@tmp/l.ttl"),
        ),
        xfail="#318",
        label="yaml",
    ),
    _row(
        Row("localise report", "refused", ("localise", "report", MALFORMED_TTL, "-l", "en,de")),
        xfail="#321",
        label="ttl",
    ),
    _row(
        Row(
            "localise init",
            "refused",
            ("localise", "init", MALFORMED_TTL, "-l", "ja", "-o", "@tmp/ja.yml"),
        ),
        xfail="#321",
        label="ttl",
    ),
]


@pytest.mark.parametrize("row", MALFORMED)
def test_malformed_input_is_refused(row: Row, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    before = snapshot(_resolve(row.argv, tmp_path), tmp_path)
    result = _invoke(row.argv, tmp_path, monkeypatch)
    assert_no_crash(result)
    assert result.exit_code == STATE_CODE["refused"], result.output
    assert_wrote_nothing(before, snapshot(_resolve(row.argv, tmp_path), tmp_path))


# ---------------------------------------------------------------------------
# The realistic tier: every command over each pinned IES ontology
# ---------------------------------------------------------------------------
#
# `profiles`, `contexts` and `localise config` read only a config file, and `puml2rdf` reads
# PlantUML, so none of them take an ontology and none of them appear here. The `refactor` rows
# name a class each file declares. The files are pinned by `test_ies_fixtures.py`, so the IRIs
# cannot drift.

IES_CLASS = {
    "ies-common": "http://informationexchangestandard.org/ont/ies/common/Entity",
    "ies-env-building": "http://informationexchangestandard.org/ont/ies/env/building/Building",
    "ies-env-building-classification": (
        "http://informationexchangestandard.org/ont/ies/env/building-classification/"
        "0mm_RoofingInsulation"
    ),
}


def _ies_invocations(name: str) -> dict[str, tuple[str, ...]]:
    src = str(IES / f"{name}.ttl")
    cls = IES_CLASS[name]
    return {
        "cast": ("cast", src, "-f", "nt", "-o", "@tmp/cast"),
        "order": ("order", src, str(EXAMPLES / "order" / "ies_profile.yml"), "-o", "@tmp/order"),
        "uml": ("uml", src, "-C", str(SMOKE / "uml_all_classes.yml"), "-o", "@tmp/uml"),
        "lint": ("lint", src),
        "diff": ("diff", src, src),
        "docs": ("docs", src, "-o", "@tmp/docs"),
        "shacl-gen": ("shacl-gen", src, "-o", "@tmp/shapes.ttl"),
        "cq-test": ("cq-test", src, str(SMOKE / "cq_ies.yml")),
        "stats": ("stats", src),
        "describe": ("describe", src),
        "merge": ("merge", src, str(IES / "ies-common.ttl"), "-o", "@tmp/merged.ttl"),
        "split": ("split", src, "--by-namespace", "-o", "@tmp/split"),
        "refactor rename": (
            "refactor",
            "rename",
            src,
            "--from",
            cls,
            "--to",
            f"{cls}Renamed",
            "-o",
            "@tmp/renamed.ttl",
        ),
        "refactor deprecate": (
            "refactor",
            "deprecate",
            src,
            "--entity",
            cls,
            "-o",
            "@tmp/deprecated.ttl",
        ),
        "localise extract": ("localise", "extract", src, "-l", "de", "-o", "@tmp/de.yml"),
        "localise merge": ("localise", "merge", src, TRANSLATIONS, "-o", "@tmp/localised.ttl"),
        "localise report": ("localise", "report", src, "-l", "en,de"),
        "localise init": ("localise", "init", src, "-l", "ja", "-o", "@tmp/ja.yml"),
    }


IES_INVOCATIONS = [
    pytest.param(argv, id=f"{name}::{command}")
    for name in IES_CLASS
    for command, argv in _ies_invocations(name).items()
]


@pytest.mark.parametrize("argv", IES_INVOCATIONS)
def test_ies_tier_completes(argv: tuple[str, ...], tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    result = _invoke(argv, tmp_path, monkeypatch)
    assert_no_crash(result)
    assert result.exit_code in (STATE_CODE["clean"], STATE_CODE["findings"]), result.output
