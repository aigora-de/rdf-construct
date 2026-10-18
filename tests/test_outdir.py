"""Unit tests for the output-directory marker helper (#261).

``core.outdir`` decides what in a directory a command did not write, and marks a directory as a
command's own. The CLI's refusal is tested per command in ``test_output_dir_marker.py``.

Relates to: #261
"""

import os
import sys
from pathlib import Path

import pytest

from rdf_construct import __version__
from rdf_construct.core.outdir import (
    IGNORED_ENTRIES,
    OUTPUT_MARKER,
    ForeignOutputDirError,
    foreign_entries,
    mark_output_dir,
    read_marker,
)


class TestForeignEntries:
    """What makes a directory someone else's."""

    def test_missing_directory_is_not_foreign(self, tmp_path: Path) -> None:
        assert foreign_entries(tmp_path / "absent", "docs") == []

    def test_empty_directory_is_not_foreign(self, tmp_path: Path) -> None:
        assert foreign_entries(tmp_path, "docs") == []

    def test_a_file_in_the_way_is_left_to_the_caller(self, tmp_path: Path) -> None:
        path = tmp_path / "docs"
        path.write_text("not a directory")
        assert foreign_entries(path, "docs") == []

    @pytest.mark.parametrize("name", sorted(IGNORED_ENTRIES))
    def test_os_and_placeholder_files_are_ignored(self, tmp_path: Path, name: str) -> None:
        (tmp_path / name).write_text("")
        assert foreign_entries(tmp_path, "docs") == []

    def test_the_ignored_set_names_each_platform(self) -> None:
        """Finder looking at docs/ must not make it foreign, nor must Explorer or Dolphin."""
        assert {".DS_Store", "Thumbs.db", "desktop.ini", ".directory", ".gitkeep"} <= (
            IGNORED_ENTRIES
        )

    def test_any_other_dotfile_counts(self, tmp_path: Path) -> None:
        (tmp_path / ".nojekyll").write_text("")
        assert foreign_entries(tmp_path, "docs") == [tmp_path / ".nojekyll"]

    def test_appledouble_files_count(self, tmp_path: Path) -> None:
        """``._index.html`` shadows a real file; it is not ignored by pattern."""
        (tmp_path / "._index.html").write_text("")
        assert foreign_entries(tmp_path, "docs") == [tmp_path / "._index.html"]

    def test_entries_are_sorted_and_exclude_ignored(self, tmp_path: Path) -> None:
        for name in ("zeta.md", "alpha.md", ".DS_Store"):
            (tmp_path / name).write_text("")
        (tmp_path / "middle").mkdir()
        assert foreign_entries(tmp_path, "docs") == [
            tmp_path / "alpha.md",
            tmp_path / "middle",
            tmp_path / "zeta.md",
        ]

    def test_own_marker_makes_everything_its_own(self, tmp_path: Path) -> None:
        mark_output_dir(tmp_path, "docs")
        (tmp_path / "index.html").write_text("")
        assert foreign_entries(tmp_path, "docs") == []

    def test_another_commands_marker_is_foreign(self, tmp_path: Path) -> None:
        mark_output_dir(tmp_path, "order")
        (tmp_path / "index.html").write_text("")
        assert foreign_entries(tmp_path, "docs") == [
            tmp_path / OUTPUT_MARKER,
            tmp_path / "index.html",
        ]

    def test_another_commands_marker_alone_is_foreign(self, tmp_path: Path) -> None:
        mark_output_dir(tmp_path, "order")
        assert foreign_entries(tmp_path, "docs") == [tmp_path / OUTPUT_MARKER]

    def test_a_different_version_of_the_same_command_is_its_own(self, tmp_path: Path) -> None:
        (tmp_path / OUTPUT_MARKER).write_text("command: docs\nversion: 0.0.1\n")
        (tmp_path / "index.html").write_text("")
        assert foreign_entries(tmp_path, "docs") == []

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "docs\n",
            "command: docs\n",
            "version: 0.7.0\n",
            "command: docs\nversion: 0.7.0\nfiles: index.html\n",
            "command:\nversion: 0.7.0\n",
            "command: docs\nversion: 0.7.0\nstray line\n",
        ],
        ids=[
            "empty",
            "bare-name",
            "no-version",
            "no-command",
            "extra-key",
            "blank-command",
            "stray-line",
        ],
    )
    def test_a_malformed_marker_is_foreign(self, tmp_path: Path, text: str) -> None:
        (tmp_path / OUTPUT_MARKER).write_text(text)
        assert foreign_entries(tmp_path, "docs") == [tmp_path / OUTPUT_MARKER]

    def test_a_binary_marker_is_foreign(self, tmp_path: Path) -> None:
        (tmp_path / OUTPUT_MARKER).write_bytes(b"\xff\xfe\x00")
        assert foreign_entries(tmp_path, "docs") == [tmp_path / OUTPUT_MARKER]

    @pytest.mark.skipif(
        sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
        reason="permissions are not enforced here",
    )
    def test_an_unreadable_marker_is_foreign(self, tmp_path: Path) -> None:
        marker = mark_output_dir(tmp_path, "docs")
        marker.chmod(0)
        try:
            assert foreign_entries(tmp_path, "docs") == [marker]
        finally:
            marker.chmod(0o644)


class TestMarkOutputDir:
    """The marker names the command and the version, and nothing else."""

    def test_marker_contents(self, tmp_path: Path) -> None:
        marker = mark_output_dir(tmp_path, "uml")
        assert marker == tmp_path / OUTPUT_MARKER
        assert marker.read_text() == f"command: uml\nversion: {__version__}\n"

    def test_marker_reads_back(self, tmp_path: Path) -> None:
        mark_output_dir(tmp_path, "split")
        assert read_marker(tmp_path) == "split"

    def test_marking_again_is_harmless(self, tmp_path: Path) -> None:
        mark_output_dir(tmp_path, "order")
        first = (tmp_path / OUTPUT_MARKER).read_text()
        mark_output_dir(tmp_path, "order")
        assert (tmp_path / OUTPUT_MARKER).read_text() == first
        assert list(tmp_path.iterdir()) == [tmp_path / OUTPUT_MARKER]

    def test_marking_does_not_create_the_directory(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            mark_output_dir(tmp_path / "absent", "docs")

    def test_no_marker_reads_as_none(self, tmp_path: Path) -> None:
        assert read_marker(tmp_path) is None


def test_foreign_output_dir_error_carries_what_it_found(tmp_path: Path) -> None:
    entries = [tmp_path / "index.md"]
    error = ForeignOutputDirError(tmp_path, entries)
    assert error.path == tmp_path
    assert error.entries == entries
    assert str(tmp_path) in str(error)
