"""Tests for `rdf-construct --version` and the version strings behind it (#66)."""

from __future__ import annotations

import re
from pathlib import Path

from click.testing import CliRunner

import rdf_construct
from rdf_construct.cli import cli

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


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
