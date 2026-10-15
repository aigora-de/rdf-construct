"""Cross-process determinism (#200): the same input gives the same bytes, whatever the hash seed.

The smoke test (``test_cli_smoke.py``) asks whether a command ran, and the post-write harness
(``test_post_write.py``) whether what it wrote is right. This module asks a third question:
whether a command writes the same bytes every time. ``tests/test_determinism.py`` holds the cases.

**Why every run is a subprocess.** ``list(set(...))`` iterates in a stable order *within* one
interpreter, so two calls in one process agree however unsorted the collection is. That is how
#107 survived, and why ``CliRunner`` cannot test this. Each run here is a separate
``python -m rdf_construct`` process with its own ``PYTHONHASHSEED``, set in the child's
environment. The child inherits everything else except pytest-cov's subprocess hook,
``PYTHONPATH`` included, so a run from a ``git worktree`` with ``PYTHONPATH=<worktree>/src`` tests
the worktree's code.

**Two entry points**, because the ``determinism`` label covers two defects:

- ``distinct_outputs`` varies the **hash seed**. It runs one invocation under each of ``SEEDS``.
- ``distinct_outputs_by_statement_order`` varies the **input's statement order**. It writes the
  same triples in two orders to the same path and runs the invocation over each. #141 is this
  kind: the same graph, a different answer.

Both return the set of distinct ``Output``s. A deterministic command yields exactly one, and
``assert_one_output`` says so with a message that names what differed.

**What counts as the same output.** Byte identity of stdout and of every file the command wrote,
not graph isomorphism, which belongs to the post-write harness. Stderr is not compared, since it
holds diagnostics, not output. A blank-node label that changes between runs is a difference.

**The output directory is constant.** Every seed writes to the same absolute ``out_dir``, cleared
before each run, which is also the working directory. A per-seed directory leaks into output that
records its own path, such as ``split``'s ``manifest.yml``, and reports false non-determinism.

**A run that fails is never an output.** Any seed that exits with something other than
``expect_exit``, or ends in a crash (the ``CrashHandlingGroup`` banner, or a bare traceback), fails
the test with that seed's stderr. So does a run that wrote nothing at all, to stdout or to
``out_dir``. Without that, a command that crashes under every seed, or a ``python -m`` that runs
nothing (``__main__.py`` was empty until #200), would yield one "distinct output" and pass.

**Worked example: a fix PR.** ``split`` is pinned as a strict xfail against #181::

    @pytest.mark.xfail(strict=True, reason="#181")
    def test_split_by_namespace(tmp_path):
        out = tmp_path / "out"
        outputs = distinct_outputs(["split", MONOLITH, "--by-namespace", "-o", out], out)
        assert_one_output(outputs)

The fix for #181 sorts the manifest. The test then passes, so the strict marker fails the suite
until the fix deletes it, and the case becomes the fix's regression test. A fix for a defect with
no case yet (#94 lands with #95's routing) adds one in the same shape.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rdflib import Graph

if TYPE_CHECKING:
    from pathlib import Path

# Six seeds, as in #200 and every issue's own measurement. The seeds are fixed, so an outcome
# is reproducible: a command that is 2/6 today is 2/6 on every run, and a strict xfail never
# passes by luck. Each seed costs one interpreter start, about 0.2 s.
SEEDS: tuple[int, ...] = (0, 1, 7, 42, 1000, 31337)

# The key under which ``Output.files`` would hold stdout, as ``normalise`` sees it.
STDOUT = "<stdout>"

# Replaced in an argv by the path of the reordered input.
INPUT = "{input}"

# What a crash leaves in stderr: the #320 handler's banner, or a traceback it did not catch.
_CRASH_MARKERS = ("rdf-construct flatlined", "Traceback (most recent call last)")

Normaliser = Callable[[str, bytes], bytes]


@dataclass(frozen=True)
class Output:
    """Everything one run produced: stdout, and each file it wrote under ``out_dir``.

    Attributes:
        stdout: The bytes written to stdout.
        files: ``(path relative to out_dir, bytes)`` for every file, sorted by path.
    """

    stdout: bytes
    files: tuple[tuple[str, bytes], ...]


def distinct_outputs(
    argv: Sequence[str | Path],
    out_dir: Path,
    *,
    seeds: Sequence[int] = SEEDS,
    expect_exit: int = 0,
    normalise: Normaliser | None = None,
) -> set[Output]:
    """Run one invocation under several ``PYTHONHASHSEED`` values, each in its own process.

    Args:
        argv: The arguments after ``rdf-construct``. Paths should be absolute. Any output path
            should be ``out_dir`` or lie under it.
        out_dir: An absolute directory, the same for every seed. It is deleted and recreated
            before each run and is the run's working directory, so a file the command writes
            there by default is compared too.
        seeds: The hash seeds, one process each.
        expect_exit: The exit code every run must return: 0, or 1 for a command that reports
            findings (#286).
        normalise: Called as ``normalise(name, data)`` on stdout (name ``STDOUT``) and on each
            file (its relative path) before comparing. For masking a field that varies for a
            reason other than hash order, such as a wall-clock timestamp (#332). Leave it out
            unless an issue names the field.

    Returns:
        The distinct outputs. A deterministic command yields exactly one.

    Raises:
        AssertionError: If any run exits with something other than ``expect_exit``, or crashes.
    """
    outputs: set[Output] = set()
    for seed in seeds:
        outputs.add(_run(argv, out_dir, seed, expect_exit, normalise))
    return outputs


def distinct_outputs_by_statement_order(
    source: Path,
    argv: Sequence[str | Path],
    out_dir: Path,
    *,
    expect_exit: int = 0,
    normalise: Normaliser | None = None,
) -> set[Output]:
    """Run one invocation over the same triples in two statement orders.

    ``source`` is parsed and written as N-Triples twice, its lines sorted and then reversed,
    to one path beside ``out_dir`` (so a command that prints its input's path prints the same
    one). Each order runs once, under the first of ``SEEDS``, so only the order differs.

    Args:
        source: The RDF file whose triples are reordered.
        argv: The arguments after ``rdf-construct``, with ``INPUT`` where the input goes.
        out_dir: As for ``distinct_outputs``.
        expect_exit: As for ``distinct_outputs``.
        normalise: As for ``distinct_outputs``.

    Returns:
        The distinct outputs. A command that does not depend on statement order yields one.

    Raises:
        AssertionError: If ``argv`` has no ``INPUT``, or any run fails as in
            ``distinct_outputs``.
    """
    assert INPUT in argv, f"argv must contain {INPUT!r} where the reordered input goes"
    lines = sorted(
        line for line in Graph().parse(source).serialize(format="nt").splitlines() if line.strip()
    )
    reordered = out_dir.parent / f"reordered-{source.stem}.nt"
    run_argv = [reordered if arg == INPUT else arg for arg in argv]
    outputs: set[Output] = set()
    for order in (lines, lines[::-1]):
        reordered.write_text("\n".join(order) + "\n", encoding="utf-8")
        outputs.add(_run(run_argv, out_dir, SEEDS[0], expect_exit, normalise))
    return outputs


def assert_one_output(outputs: set[Output]) -> None:
    """Fail unless ``outputs`` holds exactly one ``Output``, naming what differed.

    Args:
        outputs: The result of ``distinct_outputs`` or ``distinct_outputs_by_statement_order``.
    """
    if len(outputs) == 1:
        return
    first, *rest = outputs
    base = dict(first.files)
    differing: set[str] = set()
    for other in rest:
        if other.stdout != first.stdout:
            differing.add(STDOUT)
        files = dict(other.files)
        differing.update(
            name for name in base.keys() | files.keys() if base.get(name) != files.get(name)
        )
    raise AssertionError(
        f"{len(outputs)} distinct outputs; differing: {', '.join(sorted(differing))}"
    )


def without_coverage(env: Mapping[str, str]) -> dict[str, str]:
    """Drop pytest-cov's subprocess hook from a child's environment.

    Under ``--cov``, pytest-cov starts coverage in every Python child it can see, and each child
    writes data that ``branch = true`` then refuses to combine, which fails the whole suite. The
    children here measure bytes, not coverage, and the ``CliRunner`` tests cover the same code.
    """
    return {
        key: value
        for key, value in env.items()
        if not key.startswith("COV_CORE_") and key != "COVERAGE_PROCESS_START"
    }


def _run(
    argv: Sequence[str | Path],
    out_dir: Path,
    seed: int,
    expect_exit: int,
    normalise: Normaliser | None,
) -> Output:
    """Run ``python -m rdf_construct`` once in a fresh ``out_dir`` and collect what it wrote."""
    assert out_dir.is_absolute(), f"out_dir must be absolute, not {out_dir}"
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    proc = subprocess.run(
        [sys.executable, "-m", "rdf_construct", *map(str, argv)],
        env={**without_coverage(os.environ), "PYTHONHASHSEED": str(seed)},
        cwd=out_dir,
        capture_output=True,
        check=False,
    )
    stderr = proc.stderr.decode(errors="replace")
    crashed = any(marker in stderr for marker in _CRASH_MARKERS)
    if crashed or proc.returncode != expect_exit:
        raise AssertionError(
            f"seed {seed}: {'crashed, ' if crashed else ''}exited {proc.returncode}, "
            f"expected {expect_exit}\n--- stderr ---\n{stderr}"
        )
    keep = normalise or (lambda _name, data: data)
    files = tuple(
        (str(path.relative_to(out_dir)), keep(str(path.relative_to(out_dir)), path.read_bytes()))
        for path in sorted(out_dir.rglob("*"))
        if path.is_file()
    )
    if not proc.stdout and not files:
        raise AssertionError(f"seed {seed}: wrote nothing, so there is nothing to compare")
    return Output(stdout=keep(STDOUT, proc.stdout), files=files)
