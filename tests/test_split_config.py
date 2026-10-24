"""``split -c`` runs (#175), and a config value stands unless the command line names it (#291).

Each test writes its own config into ``tmp_path``, so that nothing a config names (``output_dir``,
``split_data``) can resolve inside the repository.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner, Result

from rdf_construct.cli import cli
from tests.test_cli_smoke import assert_no_crash, assert_wrote_nothing, snapshot

EXAMPLES = Path(__file__).parent.parent / "examples" / "split"

#: One module for the org namespace: everything else in the monolith is unmatched
ORG_ONLY: dict[str, Any] = {
    "modules": [
        {"name": "organisation", "namespaces": ["http://example.org/ontology/org#"]},
    ],
}


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "monolith.ttl"
    shutil.copy(EXAMPLES / "split_monolith.ttl", path)
    return path


def _config(tmp_path: Path, split: dict[str, Any]) -> Path:
    path = tmp_path / "split.yml"
    path.write_text(yaml.safe_dump({"split": split}))
    return path


def _run(source: Path, config: Path, *args: str) -> Result:
    result = CliRunner().invoke(cli, ["split", str(source), "-c", str(config), *args])
    assert_no_crash(result)
    return result


def test_example_config_runs(source: Path, tmp_path: Path) -> None:
    config = tmp_path / "split_config.yml"
    shutil.copy(EXAMPLES / "split_config.yml", config)

    result = _run(source, config, "-o", str(tmp_path / "out"))

    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in (tmp_path / "out").glob("*.ttl")) == [
        "building.ttl",
        "core.ttl",
        "organisation.ttl",
    ]


# ---------------------------------------------------------------------------
# #291: the command line overrides the config, and the config overrides a default
# ---------------------------------------------------------------------------


def test_config_unmatched_error_is_honoured(source: Path, tmp_path: Path) -> None:
    config = _config(tmp_path, {**ORG_ONLY, "unmatched": {"strategy": "error"}})
    before = snapshot([], tmp_path)

    result = _run(source, config, "-o", str(tmp_path / "out"))

    assert result.exit_code == 2
    assert "Unmatched entities" in result.output
    assert_wrote_nothing(before, snapshot([], tmp_path))


def test_unmatched_on_the_command_line_overrides_the_config(source: Path, tmp_path: Path) -> None:
    config = _config(tmp_path, {**ORG_ONLY, "unmatched": {"strategy": "error"}})

    result = _run(source, config, "-o", str(tmp_path / "out"), "--unmatched", "common")

    assert result.exit_code == 1
    assert (tmp_path / "out" / "unmatched.ttl").exists()


def test_config_unmatched_module_name_is_honoured(source: Path, tmp_path: Path) -> None:
    config = _config(
        tmp_path, {**ORG_ONLY, "unmatched": {"module": "shared", "output": "shared.ttl"}}
    )

    _run(source, config, "-o", str(tmp_path / "a"))
    _run(source, config, "-o", str(tmp_path / "b"), "--common-name", "rest")

    assert (tmp_path / "a" / "shared.ttl").exists()
    assert (tmp_path / "b" / "rest.ttl").exists()
    assert not (tmp_path / "b" / "shared.ttl").exists()


def test_config_output_dir_is_honoured_and_counts_as_named(source: Path, tmp_path: Path) -> None:
    # A directory the config names is one the user named, so a foreign file in it is no refusal
    (tmp_path / "configured").mkdir()
    (tmp_path / "configured" / "notes.txt").write_text("mine")
    config = _config(tmp_path, {**ORG_ONLY, "output_dir": "configured"})

    result = CliRunner().invoke(cli, ["split", str(source), "-c", str(config)])

    assert_no_crash(result)
    assert result.exit_code == 1, result.output
    assert (tmp_path / "configured" / "organisation.ttl").exists()


def test_output_dir_on_the_command_line_overrides_the_config(source: Path, tmp_path: Path) -> None:
    config = _config(tmp_path, {**ORG_ONLY, "output_dir": "configured"})

    _run(source, config, "-o", str(tmp_path / "given"))

    assert (tmp_path / "given" / "organisation.ttl").exists()
    assert not (tmp_path / "configured").exists()


def test_config_dry_run_and_manifest_are_honoured(source: Path, tmp_path: Path) -> None:
    dry = _config(tmp_path, {**ORG_ONLY, "dry_run": True})
    _run(source, dry, "-o", str(tmp_path / "dry"))
    assert not (tmp_path / "dry").exists()

    quiet = _config(tmp_path, {**ORG_ONLY, "generate_manifest": False})
    _run(source, quiet, "-o", str(tmp_path / "quiet"))
    assert (tmp_path / "quiet" / "organisation.ttl").exists()
    assert not (tmp_path / "quiet" / "manifest.yml").exists()


# ---------------------------------------------------------------------------
# #175: the config path runs end to end
# ---------------------------------------------------------------------------


def test_migrate_data_keeps_the_data_files_own_prefixes(source: Path, tmp_path: Path) -> None:
    data = tmp_path / "data.ttl"
    data.write_text(
        "@prefix org: <http://example.org/ontology/org#> .\n"
        "@prefix data: <http://example.org/data#> .\n"
        "data:acme a org:Company .\n"
    )
    config = _config(tmp_path, ORG_ONLY)

    result = _run(
        source,
        config,
        "-o",
        str(tmp_path / "out"),
        "--migrate-data",
        str(data),
        "--data-output",
        str(tmp_path / "data"),
    )

    assert result.exit_code == 1, result.output
    written = (tmp_path / "data" / "data_organisation.ttl").read_text()
    assert "@prefix org: <http://example.org/ontology/org#>" in written
    assert "org1:" not in written


def test_an_unbound_prefix_in_the_config_is_refused(source: Path, tmp_path: Path) -> None:
    config = _config(tmp_path, {"modules": [{"name": "m", "include": {"classes": ["zz:X"]}}]})
    before = snapshot([], tmp_path)

    result = _run(source, config, "-o", str(tmp_path / "out"))

    assert result.exit_code == 2
    assert "prefix 'zz' is not bound" in result.output
    assert_wrote_nothing(before, snapshot([], tmp_path))


def test_imports_given_as_a_file_name_are_refused(source: Path, tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        {"modules": [{**ORG_ONLY["modules"][0], "imports": ["core.ttl"]}]},
    )

    result = _run(source, config, "-o", str(tmp_path / "out"))

    assert result.exit_code == 2
    assert "cannot resolve 'core.ttl'" in result.output
