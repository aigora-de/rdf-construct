"""A default output directory the tool has not marked is refused (#261).

``docs``, ``uml``, ``split`` and ``order`` write into ``docs/``, ``diagrams/``, ``modules/`` and
``ordered/`` by default, and used to overwrite whatever was there at exit 0. The decision on #261:

- a run into the **default** directory refuses at exit 2, writing nothing, when the directory is
  non-empty and holds no marker from this command;
- every run that writes marks its directory, so a re-run proceeds;
- an explicit ``-o`` never refuses, and ``--overwrite`` writes and marks.

Each command gets the decision's five cases. The working directory is ``tmp_path``, so the
default directory lands there. The collision file in each case is one the command really writes,
the same file the reproducer on #261 lost.

Relates to: #261
"""

from dataclasses import dataclass
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from rdf_construct.cli import cli
from rdf_construct.core.outdir import OUTPUT_MARKER, mark_output_dir, read_marker
from tests.test_cli_smoke import assert_no_crash, assert_wrote_nothing, snapshot

REPO = Path(__file__).parent.parent
EXAMPLES = REPO / "examples"
ANIMAL = EXAMPLES / "animal_ontology.ttl"
UML_CONFIG = REPO / "tests" / "fixtures" / "smoke" / "uml_all_classes.yml"
ORDER_CONFIG = EXAMPLES / "order" / "sample_profile.yml"

HAND_WRITTEN = "hand-written, not generated\n"


@dataclass(frozen=True)
class Case:
    """One command's default run, and a file that run writes."""

    command: str
    argv: tuple[str, ...]
    default_dir: str
    collision: str

    def args(self, *extra: str) -> list[str]:
        return [self.command, *self.argv, *extra]


CASES = [
    Case("docs", (str(ANIMAL),), "docs", "index.html"),
    Case(
        "uml", (str(ANIMAL), "-C", str(UML_CONFIG)), "diagrams", "animal_ontology-all_classes.puml"
    ),
    Case("split", (str(ANIMAL), "--by-namespace"), "modules", "ex.ttl"),
    Case("order", (str(ANIMAL), str(ORDER_CONFIG)), "ordered", "animal_ontology-alpha.ttl"),
]


@pytest.fixture(autouse=True)
def in_tmp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


def run(args: list[str], **kwargs: object) -> Result:
    return CliRunner().invoke(cli, args, **kwargs)  # type: ignore[arg-type]


def assert_wrote(result: Result) -> None:
    """A run that writes exits 0, or 1 when ``split`` reports unmatched entities."""
    assert_no_crash(result)
    assert result.exit_code in (0, 1), result.output


def foreign_dir(case: Case, tmp_path: Path) -> Path:
    """The default directory, holding someone else's copy of a file the command writes."""
    path = tmp_path / case.default_dir
    path.mkdir()
    (path / case.collision).write_text(HAND_WRITTEN)
    (path / "notes.md").write_text("mine\n")
    return path


def assert_refused(case: Case, args: list[str], tmp_path: Path) -> Result:
    before = snapshot(args, tmp_path)
    result = run(args)
    assert_no_crash(result)
    assert result.exit_code == 2, result.output
    assert_wrote_nothing(before, snapshot(args, tmp_path))
    return result


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.command)
class TestTheDecisionsFiveCases:
    """The five cases the decision on #261 names, for each command."""

    def test_fresh_directory_is_written_and_marked(self, case: Case, tmp_path: Path) -> None:
        result = run(case.args())
        assert_wrote(result)
        out = tmp_path / case.default_dir
        assert (out / case.collision).is_file()
        assert read_marker(out) == case.command

    def test_rerun_into_marked_directory_writes(self, case: Case, tmp_path: Path) -> None:
        assert_wrote(run(case.args()))
        out = tmp_path / case.default_dir
        (out / case.collision).write_text(HAND_WRITTEN)

        assert_wrote(run(case.args()))
        assert (out / case.collision).read_text() != HAND_WRITTEN

    def test_foreign_default_directory_refuses_and_writes_nothing(
        self, case: Case, tmp_path: Path
    ) -> None:
        out = foreign_dir(case, tmp_path)
        result = assert_refused(case, case.args(), tmp_path)

        assert (out / case.collision).read_text() == HAND_WRITTEN
        assert not (out / OUTPUT_MARKER).exists()
        # The message shows what it found and the two ways on.
        assert case.collision in result.output
        assert "notes.md" in result.output
        assert "-o <dir>" in result.output
        assert "--overwrite" in result.output

    def test_explicit_output_into_foreign_directory_writes(
        self, case: Case, tmp_path: Path
    ) -> None:
        out = foreign_dir(case, tmp_path)
        assert_wrote(run(case.args("-o", str(out))))

        assert (out / case.collision).read_text() != HAND_WRITTEN
        assert read_marker(out) == case.command

    def test_overwrite_writes_and_marks(self, case: Case, tmp_path: Path) -> None:
        out = foreign_dir(case, tmp_path)
        assert_wrote(run(case.args("--overwrite")))

        assert (out / case.collision).read_text() != HAND_WRITTEN
        assert (out / "notes.md").read_text() == "mine\n", "--overwrite deletes nothing"
        assert read_marker(out) == case.command

        # Needed once: the next default run proceeds.
        assert_wrote(run(case.args()))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.command)
class TestWhatCountsAsForeign:
    """The refusal's edges, through each command."""

    def test_only_os_files_do_not_refuse(self, case: Case, tmp_path: Path) -> None:
        out = tmp_path / case.default_dir
        out.mkdir()
        (out / ".DS_Store").write_bytes(b"\x00")
        assert_wrote(run(case.args()))
        assert read_marker(out) == case.command

    def test_another_commands_marker_refuses(self, case: Case, tmp_path: Path) -> None:
        out = tmp_path / case.default_dir
        out.mkdir()
        other = "order" if case.command != "order" else "docs"
        mark_output_dir(out, other)
        (out / "something.txt").write_text("")

        assert_refused(case, case.args(), tmp_path)
        assert read_marker(out) == other

    def test_overwrite_with_explicit_output_is_accepted(self, case: Case, tmp_path: Path) -> None:
        out = foreign_dir(case, tmp_path)
        result = run(case.args("-o", str(out), "--overwrite"))
        assert_wrote(result)
        assert "--overwrite" not in result.output

    def test_default_map_counts_as_named(self, case: Case, tmp_path: Path) -> None:
        """Only ``ParameterSource.DEFAULT`` is unnamed; a ``default_map`` value is a choice."""
        out = foreign_dir(case, tmp_path)
        param = {"docs": "output", "uml": "outdir", "split": "output_dir", "order": "outdir"}
        default_map = {case.command: {param[case.command]: case.default_dir}}

        assert_wrote(run(case.args(), default_map=default_map))
        assert read_marker(out) == case.command


class TestDocsConfig:
    """A config file's ``output_dir`` names the directory as surely as ``-o`` does."""

    def test_config_naming_the_default_writes(self, tmp_path: Path) -> None:
        out = foreign_dir(CASES[0], tmp_path)
        config = tmp_path / "docs_config.yml"
        config.write_text("output_dir: docs\n")

        assert_wrote(run(["docs", str(ANIMAL), "-C", str(config)]))
        assert read_marker(out) == "docs"

    def test_config_without_output_dir_still_refuses(self, tmp_path: Path) -> None:
        foreign_dir(CASES[0], tmp_path)
        config = tmp_path / "docs_config.yml"
        config.write_text("title: Animals\n")

        assert_refused(CASES[0], ["docs", str(ANIMAL), "-C", str(config)], tmp_path)


class TestSplitDryRun:
    """``--dry-run`` reports the same refusal, and never marks."""

    def test_dry_run_refuses_the_same_way(self, tmp_path: Path) -> None:
        foreign_dir(CASES[2], tmp_path)
        assert_refused(CASES[2], CASES[2].args("--dry-run"), tmp_path)

    def test_dry_run_with_overwrite_writes_nothing(self, tmp_path: Path) -> None:
        foreign_dir(CASES[2], tmp_path)
        args = CASES[2].args("--dry-run", "--overwrite")
        before = snapshot(args, tmp_path)
        assert_wrote(run(args))
        assert_wrote_nothing(before, snapshot(args, tmp_path))

    def test_dry_run_into_fresh_directory_writes_no_marker(self, tmp_path: Path) -> None:
        assert_wrote(run(CASES[2].args("--dry-run")))
        assert not (tmp_path / "modules").exists()


class TestRefusalUnderExplicitOutputLeavesNoMarker:
    """A run that refuses after the check must not mark a directory it then left alone.

    Under an explicit ``-o`` the check passes, so these pin where the marker is written:
    after every refusal and immediately before the first output file. A marker written earlier
    would make the user's own directory look like the tool's on the next run.
    """

    def test_docs_with_a_malformed_source(self, tmp_path: Path) -> None:
        out = foreign_dir(CASES[0], tmp_path)
        bad = tmp_path / "bad.ttl"
        bad.write_text("@prefix ex: <http://example.org/> .\nex:a ex:b .\n")

        assert_refused(CASES[0], ["docs", str(bad), "-o", str(out)], tmp_path)
        assert not (out / OUTPUT_MARKER).exists()

    def test_split_with_a_malformed_source(self, tmp_path: Path) -> None:
        """``split`` has no clean failure to build this from yet.

        A malformed source crashes ``--by-namespace`` (#180) and every ``-c`` run crashes
        (#175). The crash still exits 2, so this asserts only the file tree: the splitter, not
        the CLI, writes the marker, so nothing is marked before the parse.
        """
        out = foreign_dir(CASES[2], tmp_path)
        bad = tmp_path / "bad.ttl"
        bad.write_text("@prefix ex: <http://example.org/> .\nex:a ex:b .\n")
        args = ["split", str(bad), "--by-namespace", "-o", str(out)]

        before = snapshot(args, tmp_path)
        result = run(args)
        assert result.exit_code == 2, result.output
        assert_wrote_nothing(before, snapshot(args, tmp_path))
        assert not (out / OUTPUT_MARKER).exists()

    def test_order_with_an_unknown_selector(self, tmp_path: Path) -> None:
        """``order`` refuses a typo'd selector inside its per-profile loop."""
        out = foreign_dir(CASES[3], tmp_path)
        config = tmp_path / "typo.yml"
        config.write_text(
            "selectors:\n"
            '  classes: "rdf:type owl:Class"\n'
            "profiles:\n"
            "  typo:\n"
            "    sections:\n"
            "      - classes: {select: clases, sort: alpha}\n"
        )
        args = ["order", str(ANIMAL), str(config), "-o", str(out)]

        assert_refused(CASES[3], args, tmp_path)
        assert not (out / OUTPUT_MARKER).exists()


def test_the_check_runs_before_the_parse(tmp_path: Path) -> None:
    """A malformed source into a foreign default directory is refused for the directory.

    Alex's point on #261's panel: a long parse followed by "no" wastes the wait.
    """
    foreign_dir(CASES[0], tmp_path)
    bad = tmp_path / "bad.ttl"
    bad.write_text("not turtle at all")

    result = assert_refused(CASES[0], ["docs", str(bad)], tmp_path)
    assert "--overwrite" in result.output
    assert "Could not parse" not in result.output


def test_long_listings_are_cut_short(tmp_path: Path) -> None:
    out = tmp_path / "docs"
    out.mkdir()
    for n in range(8):
        (out / f"page{n}.md").write_text("")

    result = assert_refused(CASES[0], CASES[0].args(), tmp_path)
    assert "page4.md" in result.output
    assert "page5.md" not in result.output
    assert "and 3 more" in result.output
