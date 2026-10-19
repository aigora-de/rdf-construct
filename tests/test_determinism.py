"""Cross-process determinism (#200): each command writes the same bytes under every hash seed.

The fixture and the reasoning behind it are in ``tests/determinism.py``. Every case runs six
subprocesses, so this module measures before it adds: a command gets a case when an issue wants
one, or when it is a regression guard (``docs`` for #107, ``stats`` for #284).

A case that fails today is ``xfail(strict=True)`` against the issue that explains it, and the fix
for that issue removes the marker. ``order``'s case is a filtering profile that wrote a detached
``_:n…`` stub, with a fresh label every run, until #280 was fixed, so it pins the corrected behaviour
(#264).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import rdf_construct
from tests.determinism import (
    INPUT,
    STDOUT,
    Normaliser,
    Output,
    assert_one_output,
    distinct_outputs,
    distinct_outputs_by_statement_order,
    without_coverage,
)
from tests.test_cli_smoke import (
    ANIMAL,
    EXAMPLES,
    MONOLITH,
    SIMPLE,
    TRANSLATIONS,
    UML_CONTEXTS,
)

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet

FIXTURES = Path(__file__).parent / "fixtures" / "determinism"
MERGE = EXAMPLES / "merge"
IES_SMALL = Path(__file__).parent / "fixtures" / "ies" / "ies-env-building-classification.ttl"
OWL_FULL = str(EXAMPLES / "describe" / "owl_full_example.ttl")
PROVENANCE = Path(__file__).parent / "fixtures" / "provenance"

# A leading "@out" makes an argument a path under the case's constant output directory.
OUT = "@out"

_TIMESTAMP = re.compile(rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?")


def mask_timestamps(_name: str, data: bytes) -> bytes:
    """Mask every ISO 8601 timestamp: ``stats``, ``describe`` and ``localise`` embed one (#332).

    The fix for #332 deletes this, and the ``normalise=`` on each case that uses it.
    """
    return _TIMESTAMP.sub(b"<timestamp>", data)


def _case(
    *argv: str,
    expect_exit: int = 0,
    normalise: Normaliser | None = None,
    xfail: str | None = None,
    label: str,
) -> ParameterSet:
    marks = [pytest.mark.xfail(strict=True, reason=xfail)] if xfail else []
    return pytest.param(argv, expect_exit, normalise, id=label, marks=marks)


def _resolve(argv: tuple[str, ...], out: Path) -> list[str]:
    return [str(out) + arg[len(OUT) :] if arg.startswith(OUT) else arg for arg in argv]


CASES = [
    # Pinned as passing.
    _case("stats", ANIMAL, label="stats"),
    _case("stats", ANIMAL, "-f", "json", normalise=mask_timestamps, label="stats-json"),
    _case("docs", ANIMAL, "-o", OUT, label="docs-html"),
    _case("docs", ANIMAL, "-f", "json", "-o", OUT, label="docs-json"),
    _case("describe", ANIMAL, "--no-colour", label="describe"),
    _case("diff", ANIMAL, SIMPLE, expect_exit=1, label="diff"),
    _case(
        "merge",
        str(MERGE / "merge_core.ttl"),
        str(MERGE / "merge_extension.ttl"),
        "-o",
        f"{OUT}/merged.ttl",
        label="merge",
    ),
    _case(
        "lint", str(EXAMPLES / "lint" / "example_lint_problematic.ttl"), expect_exit=1, label="lint"
    ),
    _case("cq-test", ANIMAL, str(EXAMPLES / "cq-test" / "cq_tests_animal.yml"), label="cq-test"),
    _case(
        "refactor",
        "rename",
        str(EXAMPLES / "refactor" / "typos.ttl"),
        "-c",
        str(EXAMPLES / "refactor" / "renames.yml"),
        "-o",
        f"{OUT}/renamed.ttl",
        label="refactor-rename",
    ),
    _case("localise", "merge", ANIMAL, TRANSLATIONS, "-o", f"{OUT}/l.ttl", label="localise-merge"),
    _case(
        "order",
        str(PROVENANCE / "derived.ttl"),
        str(PROVENANCE / "derived.yml"),
        "-p",
        "classes_ignore",
        "-o",
        OUT,
        label="order-filtering",
    ),
    # Failing today, each against its issue.
    _case("cast", ANIMAL, "-f", "nt", xfail="#190", label="cast-nt"),
    _case(
        "diff",
        str(FIXTURES / "diff_old.ttl"),
        str(FIXTURES / "diff_new.ttl"),
        expect_exit=1,
        xfail="#145",
        label="diff-annotations",
    ),
    _case(
        "merge",
        str(MERGE / "merge_core.ttl"),
        str(MERGE / "merge_conflicting.ttl"),
        "--strategy",
        "mark_all",
        "-o",
        f"{OUT}/merged.ttl",
        expect_exit=1,
        xfail="#173",
        label="merge-mark-all",
    ),
    _case("split", MONOLITH, "--by-namespace", "-o", OUT, xfail="#181", label="split"),
    _case("shacl-gen", ANIMAL, "-o", f"{OUT}/shapes.ttl", xfail="#94", label="shacl-gen"),
    _case(
        "describe",
        OWL_FULL,
        "-f",
        "json",
        normalise=mask_timestamps,
        xfail="#214",
        label="describe-json",
    ),
    _case("uml", ANIMAL, "-C", UML_CONTEXTS, "-o", OUT, xfail="#331", label="uml"),
]


@pytest.mark.parametrize(("argv", "expect_exit", "normalise"), CASES)
def test_same_output_under_every_hash_seed(
    argv: tuple[str, ...], expect_exit: int, normalise: Normaliser | None, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    outputs = distinct_outputs(
        _resolve(argv, out), out, expect_exit=expect_exit, normalise=normalise
    )
    assert_one_output(outputs)


@pytest.mark.xfail(strict=True, reason="#141")
def test_stats_most_connected_ignores_statement_order(tmp_path: Path) -> None:
    """Four classes tie on references, and ``Most Connected`` names whichever was read first."""
    out = tmp_path / "out"
    outputs = distinct_outputs_by_statement_order(FIXTURES / "stats_tie.ttl", ["stats", INPUT], out)
    assert_one_output(outputs)


@pytest.mark.xfail(strict=True, reason="#335")
def test_docs_relation_lists_ignore_statement_order(tmp_path: Path) -> None:
    """Each class's subclasses, superclasses and so on are listed in the order the input gave."""
    out = tmp_path / "out"
    outputs = distinct_outputs_by_statement_order(
        IES_SMALL, ["docs", INPUT, "-f", "json", "-o", out], out
    )
    assert_one_output(outputs)


# ---------------------------------------------------------------------------
# The fixture itself
# ---------------------------------------------------------------------------


def test_python_m_runs_the_cli() -> None:
    """``python -m rdf_construct`` runs ``cli``, so the fixture's subprocesses run real code.

    ``__main__.py`` was empty until #200, and every seed then produced the same empty output.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "rdf_construct", "--version"],
        env=without_coverage(os.environ),
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.decode() == f"rdf-construct, version {rdf_construct.__version__}\n"


def test_a_failing_seed_is_not_an_output(tmp_path: Path) -> None:
    """A run that exits wrongly fails the test, instead of counting as one more output."""
    with pytest.raises(AssertionError, match="seed 0: exited 2, expected 0"):
        distinct_outputs(["stats", str(tmp_path / "missing.ttl")], tmp_path / "out", seeds=(0,))


def test_a_seed_that_wrote_nothing_is_not_an_output(tmp_path: Path) -> None:
    """Empty output under every seed is one "distinct output", and proves nothing."""
    with pytest.raises(AssertionError, match="seed 0: wrote nothing"):
        distinct_outputs(["stats", ANIMAL, "-o", "/dev/null"], tmp_path / "out", seeds=(0,))


def test_assert_one_output_names_what_differed() -> None:
    first = Output(stdout=b"a", files=(("x.ttl", b"1"), ("y.ttl", b"1")))
    second = Output(stdout=b"b", files=(("x.ttl", b"2"), ("y.ttl", b"1")))
    with pytest.raises(AssertionError, match=f"2 distinct outputs; differing: {STDOUT}, x.ttl"):
        assert_one_output({first, second})
