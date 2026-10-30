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


# ---------------------------------------------------------------------------
# #413: every output is checked before the source is parsed
# ---------------------------------------------------------------------------

ORG = "http://example.org/ontology/org#"
BUILDING = "http://example.org/ontology/building#"


def _modules(*outputs: str) -> dict[str, Any]:
    """Modules named m0, m1, … with the given ``output:`` values, one namespace each."""
    namespaces = [ORG, BUILDING, "http://example.org/ontology#"]
    return {
        "modules": [
            {"name": f"m{i}", "output": output, "namespaces": [namespaces[i]]}
            for i, output in enumerate(outputs)
        ]
    }


def _refused(source: Path, config: Path, tmp_path: Path, *args: str) -> str:
    """Run a split that must be refused with nothing written, and return its output."""
    before = snapshot([], tmp_path)
    result = _run(source, config, "-o", str(tmp_path / "out"), *args)
    assert result.exit_code == 2, result.output
    assert "Nothing was written:" in result.output
    assert_wrote_nothing(before, snapshot([], tmp_path))
    return result.output


def test_two_modules_with_one_output_are_refused(source: Path, tmp_path: Path) -> None:
    output = _refused(source, _config(tmp_path, _modules("same.ttl", "same.ttl")), tmp_path)

    assert "module 'm0' (output: same.ttl) and module 'm1' (output: same.ttl) name one file" in (
        output
    )


def test_outputs_differing_only_in_case_are_refused(source: Path, tmp_path: Path) -> None:
    output = _refused(source, _config(tmp_path, _modules("A.ttl", "a.ttl")), tmp_path)

    assert "name one file" in output


def test_an_output_outside_the_directory_is_refused(source: Path, tmp_path: Path) -> None:
    outside = tmp_path / "escaped.ttl"
    outside.write_text("KEEP ME\n")

    output = _refused(source, _config(tmp_path, _modules("../escaped.ttl")), tmp_path)

    assert "(output: ../escaped.ttl) is outside output_dir" in output
    assert outside.read_text() == "KEEP ME\n"


def test_an_absolute_output_is_refused(source: Path, tmp_path: Path) -> None:
    absolute = str(tmp_path / "out" / "inside.ttl")

    output = _refused(source, _config(tmp_path, _modules(absolute)), tmp_path)

    assert "is an absolute path" in output


def test_an_output_through_a_symbolic_link_out_is_refused(source: Path, tmp_path: Path) -> None:
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "out").mkdir()
    try:
        (tmp_path / "out" / "link").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are not available")

    output = _refused(source, _config(tmp_path, _modules("link/x.ttl")), tmp_path)

    assert "(output: link/x.ttl) is outside output_dir" in output


@pytest.mark.parametrize("name", ["manifest.yml", ".rdf-construct"])
def test_an_output_named_like_the_manifest_or_the_marker_is_refused(
    source: Path, tmp_path: Path, name: str
) -> None:
    output = _refused(source, _config(tmp_path, _modules(name)), tmp_path)

    assert f"(output: {name}) and " in output


def test_an_output_named_manifest_is_allowed_without_a_manifest(
    source: Path, tmp_path: Path
) -> None:
    result = _run(
        source,
        _config(tmp_path, _modules("manifest.yml")),
        "-o",
        str(tmp_path / "out"),
        "--no-manifest",
    )

    assert result.exit_code == 1, result.output
    assert "@prefix" in (tmp_path / "out" / "manifest.yml").read_text()


def test_an_output_naming_a_directory_is_refused(source: Path, tmp_path: Path) -> None:
    (tmp_path / "out" / "org").mkdir(parents=True)

    output = _refused(source, _config(tmp_path, _modules("org")), tmp_path)

    assert "(output: org) names a directory" in output


def test_an_output_over_the_source_is_refused(source: Path, tmp_path: Path) -> None:
    original = source.read_bytes()
    config = _config(tmp_path, _modules(source.name))

    before = snapshot([], tmp_path)
    result = _run(source, config, "-o", str(tmp_path))

    assert result.exit_code == 2, result.output
    assert f"would replace the input {source}" in result.output
    assert_wrote_nothing(before, snapshot([], tmp_path))
    assert source.read_bytes() == original


def test_modules_sharing_a_name_are_refused(source: Path, tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        {
            "modules": [
                {"name": "same", "output": "a.ttl", "namespaces": [ORG]},
                {"name": "Same", "output": "b.ttl", "namespaces": [BUILDING]},
            ]
        },
    )

    output = _refused(source, config, tmp_path)

    assert "Modules 'same' and 'Same' share a name" in output


def test_every_problem_is_listed_in_one_refusal(source: Path, tmp_path: Path) -> None:
    config = _config(tmp_path, _modules("same.ttl", "same.ttl", "../escaped.ttl"))

    output = _refused(source, config, tmp_path)

    assert "name one file" in output
    assert "is outside output_dir" in output


def test_a_dry_run_is_refused_the_same_way(source: Path, tmp_path: Path) -> None:
    config = _config(tmp_path, _modules("same.ttl", "same.ttl"))

    output = _refused(source, config, tmp_path, "--dry-run")

    assert "name one file" in output


def test_overwrite_does_not_permit_an_output_outside_the_directory(
    source: Path, tmp_path: Path
) -> None:
    output = _refused(
        source, _config(tmp_path, _modules("../escaped.ttl")), tmp_path, "--overwrite"
    )

    assert "is outside output_dir" in output


def test_a_clash_with_the_unmatched_module_is_refused_with_nothing_unmatched(
    source: Path, tmp_path: Path
) -> None:
    split = yaml.safe_load((EXAMPLES / "split_config.yml").read_text())["split"]
    split["unmatched"] = {"strategy": "common", "module": "core", "output": "core.ttl"}
    config = _config(tmp_path, split)

    output = _refused(source, config, tmp_path)

    assert "The unmatched module 'core' (core.ttl) would overwrite module 'core'" in output


def test_outputs_in_a_subdirectory_are_written(source: Path, tmp_path: Path) -> None:
    result = _run(
        source,
        _config(tmp_path, _modules("org/org.ttl", "sub/../building.ttl")),
        "-o",
        str(tmp_path / "out"),
    )

    assert result.exit_code == 1, result.output
    assert (tmp_path / "out" / "org" / "org.ttl").is_file()
    assert (tmp_path / "out" / "building.ttl").is_file()
    assert not (tmp_path / "out" / "sub").exists()


def test_a_data_file_named_like_a_module_output_is_refused(source: Path, tmp_path: Path) -> None:
    data = tmp_path / "data.ttl"
    data.write_text("")

    output = _refused(
        source,
        _config(tmp_path, _modules("data_m1.ttl", "m1.ttl")),
        tmp_path,
        "--migrate-data",
        str(data),
    )

    assert "and the data file for module 'm1' (data_m1.ttl: prefix + name) name one file" in output


def test_migrated_data_goes_to_the_config_output_dir(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --data-output, data goes where the modules go, not to the -o default."""
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data.ttl"
    data.write_text(
        "@prefix org: <http://example.org/ontology/org#> .\n"
        "@prefix data: <http://example.org/data#> .\n"
        "data:acme a org:Company .\n"
    )
    config = _config(tmp_path, {**ORG_ONLY, "output_dir": "named"})

    result = _run(source, config, "--migrate-data", str(data))

    assert result.exit_code == 1, result.output
    assert (tmp_path / "named" / "data_organisation.ttl").is_file()
    assert not (tmp_path / "modules").exists()


def test_migrated_data_keeps_the_config_data_directory_and_prefix(
    source: Path, tmp_path: Path
) -> None:
    data = tmp_path / "data.ttl"
    data.write_text(
        "@prefix org: <http://example.org/ontology/org#> .\n"
        "@prefix data: <http://example.org/data#> .\n"
        "data:acme a org:Company .\n"
    )
    config = _config(
        tmp_path,
        {**ORG_ONLY, "split_data": {"sources": [], "output_dir": "instances", "prefix": "i_"}},
    )

    result = _run(source, config, "-o", str(tmp_path / "out"), "--migrate-data", str(data))

    assert result.exit_code == 1, result.output
    assert (tmp_path / "instances" / "i_organisation.ttl").is_file()
