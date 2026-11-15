"""Output directories the tool has marked as its own (#261).

``docs``, ``uml``, ``split`` and ``order`` each write into a directory of their own by default
(``docs/``, ``diagrams/``, ``modules/``, ``ordered/``). Before #261 they wrote over whatever was
already there, in silence. Now every run that writes leaves a small marker file in its output
directory, naming the command and the version that wrote it, and a run into a **default**
directory that holds anything else refuses.

This module knows what a collision is and how a directory is marked. It reports and never
decides: whether the default was used, and whether to refuse, belong to the CLI, which knows
where each value came from. That keeps this module free of Click, like the rest of ``core/``.

**What counts as "something else".** Every entry in the directory counts, dotfiles included,
except the files an operating system or a file manager drops into any directory a person
looks at, and the empty placeholders that keep a directory in version control. They are listed
by exact name in :data:`IGNORED_ENTRIES`. macOS's AppleDouble ``._*`` files are deliberately not
ignored: each one shadows a real file, and that file counts anyway.

**A marker from another command is foreign.** ``docs``'s marker in ``ordered/`` says that
``docs`` wrote there, not ``order``. A marker that cannot be read, or does not have the shape
:func:`mark_output_dir` writes, is foreign too: nothing can say which command wrote it. A
different version of the same command is not foreign.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

OUTPUT_MARKER = ".rdf-construct"
"""The marker's file name, the same for every command."""

IGNORED_ENTRIES: frozenset[str] = frozenset(
    {
        # macOS: Finder's view settings, and a localised folder name.
        ".DS_Store",
        ".localized",
        # Windows: Explorer's thumbnail caches and folder settings.
        "Thumbs.db",
        "ehthumbs.db",
        "desktop.ini",
        # Linux: KDE Dolphin's folder settings.
        ".directory",
        # Placeholders that keep an otherwise empty directory in version control.
        ".gitkeep",
        ".keep",
    }
)
"""Entries that never make a directory count as non-empty, matched by exact name."""


def read_marker(path: Path) -> str | None:
    """Return the command named by the marker in ``path``.

    Args:
        path: The output directory.

    Returns:
        The command name, or ``None`` when there is no marker, it cannot be read, or it does
        not have the shape :func:`mark_output_dir` writes.
    """
    try:
        text = (path / OUTPUT_MARKER).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            return None
        fields[key.strip()] = value.strip()

    command = fields.get("command")
    if not command or not fields.get("version") or set(fields) != {"command", "version"}:
        return None
    return command


def foreign_entries(path: Path, command: str) -> list[Path]:
    """Return what in ``path`` the given command did not write.

    This is the existence check: the one place that knows what a collision is.

    Args:
        path: The output directory.
        command: The command about to write there, such as ``"docs"``.

    Returns:
        The entries, sorted, that make ``path`` someone else's. A foreign or malformed marker is
        one of them. Empty when ``path`` does not exist, is not a directory, holds only
        :data:`IGNORED_ENTRIES`, or carries ``command``'s own marker.
    """
    if not path.is_dir():
        return []
    if read_marker(path) == command:
        return []
    return sorted(entry for entry in path.iterdir() if entry.name not in IGNORED_ENTRIES)


def mark_output_dir(path: Path, command: str) -> Path:
    """Mark ``path`` as written by ``command``, at this version.

    Call it after every check that could refuse the run and immediately before the first output
    file is written. A directory marked and then left with nothing in it would look like the
    tool's own on the next run. Writing it again is harmless.

    Args:
        path: The output directory, which must already exist.
        command: The command writing there, such as ``"docs"``.

    Returns:
        The marker's path.
    """
    from rdf_construct import __version__

    marker = path / OUTPUT_MARKER
    marker.write_text(f"command: {command}\nversion: {__version__}\n", encoding="utf-8")
    return marker
