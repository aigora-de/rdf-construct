"""``merge`` writes what it was asked to, and nothing on a dry run or a refusal (#436, #437, #496).

- #496: source arguments given with ``-c`` replace the config's ``sources:``; they were dropped
  without a word. A replaced source's ``namespace_remap`` is never dropped in silence: the run is
  refused instead.
- #436: ``--dry-run`` wrote the conflict report. It now writes nothing and says what a real run
  would have written.
- #437: a data file that could not be read was reported after the ontology was written, at
  exit 0. Every data file is now read before anything is written, and a bad one refuses the run.

Flag-versus-config precedence for ``merge -c`` (#351) is in ``test_flag_precedence.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner, Result
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from rdf_construct.cli import cli
from rdf_construct.merge import MigrationResult, migrate_data_files, migrate_data_graphs
from tests.test_cli_smoke import assert_no_crash, assert_wrote_nothing, snapshot

LABELS = Path(__file__).parent / "fixtures" / "merge" / "conflicts"
LABELS_A = LABELS / "labels_a.ttl"
LABELS_B = LABELS / "labels_b.ttl"
THING = URIRef("http://example.org/Thing")
OTHER = URIRef("http://example.org/Other")
RECORD = URIRef("http://example.org/d#rec")


def write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def other_source(tmp_path: Path) -> Path:
    path = tmp_path / "other.ttl"
    path.write_text(
        "@prefix ex: <http://example.org/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "ex:Other a owl:Class .\n",
        encoding="utf-8",
    )
    return path


def data_file(tmp_path: Path, name: str = "data.ttl") -> Path:
    path = tmp_path / name
    path.write_text("@prefix d: <http://example.org/d#> .\nd:rec a d:Record .\n", encoding="utf-8")
    return path


def bad_file(tmp_path: Path) -> Path:
    path = tmp_path / "bad.ttl"
    path.write_text("this is not turtle\n", encoding="utf-8")
    return path


def invoke(runner: CliRunner, argv: list[str], tmp_path: Path) -> tuple[Result, dict, dict]:
    """Run ``argv`` and snapshot the disk around it."""
    before = snapshot(argv, tmp_path)
    result = runner.invoke(cli, argv)
    assert_no_crash(result)
    return result, before, snapshot(argv, tmp_path)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestSourcesWithConfig:
    """#496: source arguments replace the config's ``sources:``."""

    def test_source_arguments_replace_the_config_sources(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        config = write_yaml(tmp_path / "m.yml", {"sources": [str(LABELS_A), str(LABELS_B)]})
        out = tmp_path / "merged.ttl"
        argv = ["merge", "-c", str(config), str(other_source(tmp_path)), "-o", str(out)]
        result = runner.invoke(cli, argv)
        assert_no_crash(result)
        assert result.exit_code == 0, result.output
        merged = Graph().parse(out)
        assert (OTHER, RDF.type, OWL.Class) in merged
        assert (THING, RDF.type, OWL.Class) not in merged
        assert (
            "Note: 1 source(s) from the command line replace the config's 2; their priorities "
            "come from -p, or their order."
        ) in result.stderr

    def test_priorities_apply_to_the_source_arguments(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """The config lists b at 9; its arguments a, b with -p 5 make a win."""
        config = write_yaml(
            tmp_path / "m.yml", {"sources": [{"path": str(LABELS_B), "priority": 9}]}
        )
        out = tmp_path / "merged.ttl"
        argv = ["merge", "-c", str(config), str(LABELS_A), str(LABELS_B), "-o", str(out)]
        result = runner.invoke(cli, [*argv, "-p", "5"])
        assert result.exit_code == 0, result.output
        labels = {
            str(o) for o in Graph().parse(out).objects(THING, RDFS.label) if o.language == "en"
        }
        assert "Alpha" in labels and "Beta" not in labels

    def test_a_config_without_sources_takes_them_without_a_note(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        config = write_yaml(tmp_path / "m.yml", {"conflicts": {"strategy": "first"}})
        out = tmp_path / "merged.ttl"
        argv = ["merge", "-c", str(config), str(other_source(tmp_path)), "-o", str(out)]
        result = runner.invoke(cli, argv)
        assert result.exit_code == 0, result.output
        assert "Note:" not in result.stderr
        assert (OTHER, RDF.type, OWL.Class) in Graph().parse(out)

    def test_a_replaced_namespace_remap_is_refused(self, runner: CliRunner, tmp_path: Path) -> None:
        remap = {"http://example.org/": "http://example.net/"}
        config = write_yaml(
            tmp_path / "m.yml",
            {"sources": [{"path": str(LABELS_A), "namespace_remap": remap}, str(LABELS_B)]},
        )
        argv = ["merge", "-c", str(config), str(other_source(tmp_path))]
        argv += ["-o", str(tmp_path / "merged.ttl")]
        result, before, after = invoke(runner, argv, tmp_path)
        assert result.exit_code == 2, result.output
        assert f"{LABELS_A} there has a namespace_remap that would be dropped" in result.output
        assert_wrote_nothing(before, after)


class TestDryRun:
    """#436: a dry run writes nothing, and says what it would have written."""

    def test_a_dry_run_writes_no_report(self, runner: CliRunner, tmp_path: Path) -> None:
        out, report = tmp_path / "merged.ttl", tmp_path / "conflicts.md"
        argv = ["merge", str(LABELS_A), str(LABELS_B), "-o", str(out), "--report", str(report)]
        argv += ["--strategy", "mark_all", "--dry-run"]
        result, before, after = invoke(runner, argv, tmp_path)
        assert result.exit_code == 1, result.output
        assert_wrote_nothing(before, after)
        assert f"Dry run: would write -o {out}" in result.output
        assert f"Dry run: would write --report {report} (1 conflict(s))" in result.output
        assert "Dry run: nothing was written." in result.output
        assert "Conflict report:" not in result.output

    def test_a_report_without_conflicts_is_not_promised(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out, report = tmp_path / "merged.ttl", tmp_path / "conflicts.md"
        argv = ["merge", str(LABELS_A), "-o", str(out), "--report", str(report), "--dry-run"]
        result, before, after = invoke(runner, argv, tmp_path)
        assert result.exit_code == 0, result.output
        assert_wrote_nothing(before, after)
        assert "--report" not in result.output

    def test_a_dry_run_names_the_data_output(self, runner: CliRunner, tmp_path: Path) -> None:
        out, data_out = tmp_path / "merged.ttl", tmp_path / "migrated.ttl"
        argv = ["merge", str(LABELS_A), "-o", str(out), "--migrate-data"]
        argv += [str(data_file(tmp_path)), "--data-output", str(data_out), "--dry-run"]
        result, before, after = invoke(runner, argv, tmp_path)
        assert result.exit_code == 0, result.output
        assert_wrote_nothing(before, after)
        assert f"Dry run: would write --data-output {data_out}" in result.output


class TestDataReadFirst:
    """#437: every data file is read before anything is written."""

    @pytest.mark.parametrize("dry_run", [False, True], ids=["run", "dry-run"])
    def test_an_unparsable_data_file_is_refused(
        self, runner: CliRunner, tmp_path: Path, dry_run: bool
    ) -> None:
        bad = bad_file(tmp_path)
        argv = ["merge", str(LABELS_A), "-o", str(tmp_path / "merged.ttl"), "--migrate-data"]
        argv += [str(bad), "--data-output", str(tmp_path / "migrated.ttl")]
        argv += ["--dry-run"] if dry_run else []
        result, before, after = invoke(runner, argv, tmp_path)
        assert result.exit_code == 2, result.output
        assert f"Could not parse data file {bad}" in result.output
        assert "Merging ontologies" not in result.output
        assert_wrote_nothing(before, after)

    def test_an_unparsable_config_data_file_is_refused(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        bad = bad_file(tmp_path)
        good = data_file(tmp_path)
        migrate = {"sources": [str(good), str(bad)], "output": str(tmp_path / "migrated.ttl")}
        config = write_yaml(
            tmp_path / "m.yml", {"sources": [str(LABELS_A)], "migrate_data": migrate}
        )
        argv = ["merge", "-c", str(config), "-o", str(tmp_path / "merged.ttl")]
        result, before, after = invoke(runner, argv, tmp_path)
        assert result.exit_code == 2, result.output
        assert f"Could not parse data file {bad}" in result.output
        assert_wrote_nothing(before, after)

    def test_a_missing_config_data_file_is_refused(self, runner: CliRunner, tmp_path: Path) -> None:
        missing = tmp_path / "missing.ttl"
        migrate = {"sources": [str(missing)], "output": str(tmp_path / "migrated.ttl")}
        config = write_yaml(
            tmp_path / "m.yml", {"sources": [str(LABELS_A)], "migrate_data": migrate}
        )
        argv = ["merge", "-c", str(config), "-o", str(tmp_path / "merged.ttl")]
        result, before, after = invoke(runner, argv, tmp_path)
        assert result.exit_code == 2, result.output
        assert f"Data file not found: {missing}" in result.output
        assert_wrote_nothing(before, after)

    def test_a_migration_that_reports_failure_exits_2(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failure reported after the ontology is written still exits 2, never 0 (#286)."""

        def failed(*args: Any, **kwargs: Any) -> MigrationResult:
            return MigrationResult(success=False, error="disk on fire")

        monkeypatch.setattr(sys.modules["rdf_construct.cli"], "migrate_data_graphs", failed)
        argv = ["merge", str(LABELS_A), "-o", str(tmp_path / "merged.ttl"), "--migrate-data"]
        argv += [str(data_file(tmp_path)), "--data-output", str(tmp_path / "migrated.ttl")]
        result = runner.invoke(cli, argv)
        assert result.exit_code == 2, result.output
        assert "Data migration failed: disk on fire" in result.stderr

    def test_good_data_is_migrated(self, runner: CliRunner, tmp_path: Path) -> None:
        data_out = tmp_path / "migrated.ttl"
        argv = ["merge", str(LABELS_A), "-o", str(tmp_path / "merged.ttl"), "--migrate-data"]
        argv += [str(data_file(tmp_path)), "--data-output", str(data_out)]
        result = runner.invoke(cli, argv)
        assert result.exit_code == 0, result.output
        assert (RECORD, RDF.type, URIRef("http://example.org/d#Record")) in Graph().parse(data_out)


class TestLibrary:
    """``migrate_data_files`` keeps its contract; ``migrate_data_graphs`` takes parsed graphs."""

    def test_a_bad_file_is_reported_and_nothing_written(self, tmp_path: Path) -> None:
        out = tmp_path / "migrated.ttl"
        result = migrate_data_files([data_file(tmp_path), bad_file(tmp_path)], output_path=out)
        assert not result.success
        assert result.error is not None and result.error.startswith("Failed to parse")
        assert not out.exists()

    def test_files_and_graphs_migrate_alike(self, tmp_path: Path) -> None:
        path = data_file(tmp_path)
        graph = Graph(bind_namespaces="core").parse(path)
        from_files = migrate_data_files([path], output_path=tmp_path / "a.ttl")
        from_graphs = migrate_data_graphs([(path, graph)], output_path=tmp_path / "b.ttl")
        assert from_files.success and from_graphs.success
        assert (tmp_path / "a.ttl").read_bytes() == (tmp_path / "b.ttl").read_bytes()


class TestMigrationOutputRequired:
    @pytest.mark.parametrize("configured", [False, True])
    @pytest.mark.parametrize("dry_run", [False, True])
    def test_data_without_output_is_refused(
        self, runner: CliRunner, tmp_path: Path, configured: bool, dry_run: bool
    ) -> None:
        data = data_file(tmp_path)
        out = tmp_path / "merged.ttl"
        if configured:
            config = write_yaml(
                tmp_path / "m.yml",
                {"sources": [str(LABELS_A)], "migrate_data": {"sources": [str(data)]}},
            )
            argv = ["merge", "-c", str(config), "-o", str(out)]
        else:
            argv = ["merge", str(LABELS_A), "-o", str(out), "--migrate-data", str(data)]
        argv += ["--dry-run"] if dry_run else []
        result, before, after = invoke(runner, argv, tmp_path)
        assert result.exit_code == 2, result.output
        assert "--data-output" in result.output
        assert "migrate_data.output" in result.output
        assert_wrote_nothing(before, after)

    @pytest.mark.parametrize("configured", [False, True])
    def test_output_without_data_is_refused(
        self, runner: CliRunner, tmp_path: Path, configured: bool
    ) -> None:
        if configured:
            config = write_yaml(tmp_path / "m.yml", {"sources": [str(LABELS_A)]})
            argv = ["merge", "-c", str(config)]
        else:
            argv = ["merge", str(LABELS_A)]
        argv += ["-o", str(tmp_path / "merged.ttl"), "--data-output", str(tmp_path / "data.ttl")]
        result, before, after = invoke(runner, argv, tmp_path)
        assert result.exit_code == 2, result.output
        assert "--migrate-data" in result.output
        assert_wrote_nothing(before, after)

    def test_config_output_without_sources_is_refused(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        config = write_yaml(
            tmp_path / "m.yml",
            {
                "sources": [str(LABELS_A)],
                "migrate_data": {"output": str(tmp_path / "data.ttl")},
            },
        )
        argv = ["merge", "-c", str(config), "-o", str(tmp_path / "merged.ttl")]
        result, before, after = invoke(runner, argv, tmp_path)
        assert result.exit_code == 2, result.output
        assert "migrate_data.sources" in result.output
        assert_wrote_nothing(before, after)
