"""Tests for `rdf-construct --version` and the version strings behind it (#66)."""

from __future__ import annotations

import re
from pathlib import Path

from click.testing import CliRunner

import rdf_construct
from rdf_construct.cli import cli

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"
CLAUDE_MD = ROOT / "CLAUDE.md"
CHANGELOG = ROOT / "CHANGELOG.md"


class TestVersionOption:
    """`--version` must report the source version, not installed metadata."""

    def test_reports_source_version(self) -> None:
        """The reported version is `rdf_construct.__version__`.

        Regression test for #66: `@click.version_option()` with no argument
        resolves through `importlib.metadata`, so an editable install whose
        metadata predates a version bump reported the stale number.
        """
        result = CliRunner().invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert rdf_construct.__version__ in result.output

    def test_uses_the_tool_name_not_the_group_name(self) -> None:
        """Output names the tool, rather than the `cli` group function."""
        result = CliRunner().invoke(cli, ["--version"])

        assert result.output.startswith("rdf-construct, version ")

    def test_does_not_consult_installed_metadata(self) -> None:
        """A stale or absent distribution must not change what is reported.

        `importlib.metadata.version()` raising is the strongest evidence the
        option no longer depends on it, so patch it to blow up and confirm
        `--version` is unaffected.
        """
        import importlib.metadata

        def explode(_name: str) -> str:
            raise importlib.metadata.PackageNotFoundError("rdf-construct")

        original = importlib.metadata.version
        importlib.metadata.version = explode  # type: ignore[assignment]
        try:
            result = CliRunner().invoke(cli, ["--version"])
        finally:
            importlib.metadata.version = original  # type: ignore[assignment]

        assert result.exit_code == 0
        assert rdf_construct.__version__ in result.output


class TestVersionStringsAgree:
    """The two hand-maintained version strings must not drift apart."""

    def test_pyproject_matches_dunder_version(self) -> None:
        """`pyproject.toml` and `__init__.py` carry the same version.

        `scripts/ci-local.sh` gates on this too, but that gate is a shell
        script nobody runs from an IDE; the suite should catch it as well.

        Read with a regex rather than a TOML parser: `tomllib` is 3.11+ and
        this project supports 3.10, and pulling in `tomli` for one assertion
        is not worth a dependency. This matches the `sed` the gate uses.
        """
        match = re.search(r'^version = "(.*)"', PYPROJECT.read_text(encoding="utf-8"), re.MULTILINE)

        assert match is not None, "no version line found in pyproject.toml"
        assert match.group(1) == rdf_construct.__version__


class TestDocumentedVersionsAgree:
    """Prose that states the version must not drift from the code (#98).

    These are the strings that actually went stale: README claimed v0.4.1 for
    four releases, and CLAUDE.md carried a wrong version alongside a wrong
    command and subpackage count. `scripts/release.sh` checks all of this
    before a release, but a release is a rare event and the script is easy not
    to run — so the suite guards it on every commit too.
    """

    def test_readme_names_no_other_version(self) -> None:
        """Every `vX.Y.Z` in README.md is the current version."""
        found = set(re.findall(r"v(\d+\.\d+\.\d+)", README.read_text(encoding="utf-8")))

        assert found, "README.md names no version at all — it used to name two"
        assert found == {
            rdf_construct.__version__
        }, f"README.md names {sorted(found)}, expected only {rdf_construct.__version__}"

    def test_claude_md_names_the_current_version(self) -> None:
        """CLAUDE.md's stated version matches the code."""
        text = CLAUDE_MD.read_text(encoding="utf-8")

        assert (
            f"v{rdf_construct.__version__}" in text
        ), f"CLAUDE.md does not name v{rdf_construct.__version__}"

    def test_changelog_top_entry_is_the_current_version(self) -> None:
        """The newest dated CHANGELOG entry is this version, and it has a date."""
        match = re.search(
            r"^## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})$",
            CHANGELOG.read_text(encoding="utf-8"),
            re.MULTILINE,
        )

        assert match is not None, "no dated release heading found in CHANGELOG.md"
        assert match.group(1) == rdf_construct.__version__


class TestClaudeMdCounts:
    """CLAUDE.md states counts as fact; the size guard measures bytes, not truth."""

    def test_command_count_is_accurate(self) -> None:
        """The stated command count matches the CLI's actual top-level commands."""
        stated = re.search(r"^(\d+) commands across", CLAUDE_MD.read_text(encoding="utf-8"), re.M)

        assert stated is not None, "CLAUDE.md no longer states a command count"
        assert int(stated.group(1)) == len(cli.commands)

    def test_subpackage_count_is_accurate(self) -> None:
        """The stated subpackage count matches the directories on disk."""
        stated = re.search(
            r"commands across (\d+) subpackages", CLAUDE_MD.read_text(encoding="utf-8")
        )
        packages = [
            d
            for d in (ROOT / "src" / "rdf_construct").iterdir()
            if d.is_dir() and not d.name.startswith("__")
        ]

        assert stated is not None, "CLAUDE.md no longer states a subpackage count"
        assert int(stated.group(1)) == len(
            packages
        ), f"CLAUDE.md says {stated.group(1)}, found {sorted(p.name for p in packages)}"
