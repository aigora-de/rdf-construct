"""Whether a run's output paths are the same file as each other, or as one of its inputs (#411).

A command that works out several output paths from its inputs (one per source, one per data file)
can land two of them on one file, so the second write replaces the first, or land one on an input,
so the write replaces the file it was made from. Both happen at exit 0 unless something checks the
whole set before the first byte is written.

This module knows what "the same file" means and reports every case. It never decides: whether a
case is refused, or allowed by a flag such as ``refactor rename --in-place``, belongs to the CLI,
which knows what each path is for. That keeps it free of Click, like the rest of ``core/``.

**Two outputs** usually do not exist yet, so they are compared by resolved path, ignoring case.
``Path.resolve()`` follows symbolic links and ``..`` but keeps case as written, and on a
case-insensitive filesystem (macOS and Windows by default) ``out/A.ttl`` and ``out/a.ttl`` are one
file. Comparing without case refuses that pair on a case-sensitive filesystem too, where it would
have been two files: such output is not portable, so the refusal is the safer answer.

**An output and an input** are compared with :func:`os.path.samefile`. An input exists, so an
output that is the same file exists too, and ``samefile`` catches every spelling: a symbolic link,
a hard link, ``..`` and a difference in case. An output that does not exist cannot be an input.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


@dataclass(frozen=True)
class PlannedOutput:
    """A file a run means to write, and the input it is made from.

    Attributes:
        path: Where the output will be written.
        made_from: The input this output is the result of, if it has exactly one.
    """

    path: Path
    made_from: Path | None = None


def _key(path: Path) -> str:
    """The resolved path, ignoring case."""
    return str(path.resolve()).casefold()


def colliding_outputs(outputs: Sequence[PlannedOutput]) -> list[list[PlannedOutput]]:
    """Group the outputs that would be written to the same file.

    Args:
        outputs: Every output the run plans, in the order it would write them.

    Returns:
        Each group of two or more outputs that are one file, in order of first appearance. Empty
        when every output is a different file.
    """
    groups: dict[str, list[PlannedOutput]] = {}
    for output in outputs:
        groups.setdefault(_key(output.path), []).append(output)
    return [group for group in groups.values() if len(group) > 1]


def is_same_file(output: Path, existing: Path) -> bool:
    """Whether writing ``output`` would replace the existing file ``existing``.

    Args:
        output: A path the run means to write.
        existing: A file the run reads.

    Returns:
        True when both exist and are the same file, however either is spelled.
    """
    try:
        return output.exists() and existing.exists() and os.path.samefile(output, existing)
    except OSError:
        return False


def outputs_over_inputs(
    outputs: Sequence[PlannedOutput], inputs: Sequence[Path]
) -> list[tuple[PlannedOutput, Path]]:
    """Find every output that would replace one of the run's inputs.

    Args:
        outputs: Every output the run plans.
        inputs: Every file the run reads.

    Returns:
        Each output with the input it would replace, in output order. An output that would
        replace the input it is made from is included: telling an in-place rewrite from an
        accident is the caller's decision, and :attr:`PlannedOutput.made_from` is there for it.
    """
    found: list[tuple[PlannedOutput, Path]] = []
    for output in outputs:
        for existing in inputs:
            if is_same_file(output.path, existing):
                found.append((output, existing))
                break
    return found
