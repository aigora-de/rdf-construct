"""An output that is an input, or another output of the same run, is refused before writing.

#412: ``stats``, ``describe``, ``diff``, ``cq-test``, ``localise report``, ``shacl-gen``,
``puml2rdf``, ``localise merge`` and ``merge`` wrote each output as given, so a report could
replace the ontology it describes, and ``merge``'s three outputs could replace each other or a
source, all at exit 0. Every case is now refused at exit 2 with nothing written, listing every
problem. There is no flag: none of these outputs is the input's own result.

Two inputs are left out on purpose: ``puml2rdf -o`` may name its ``--merge`` ontology, which is
the documented round trip, and ``localise merge -o`` equal to its source is #162's question.

The same-file checks are ``core.output_paths``'s, tested in ``test_refactor_outputs.py``.
"""

import os
import shutil
from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner, Result

REPO = Path(__file__).parent.parent
ANIMAL = REPO / "examples" / "animal_ontology.ttl"
CQ_TESTS = REPO / "examples" / "cq-test" / "cq_tests_animal.yml"
SHACL_CONFIG = REPO / "examples" / "shacl" / "shacl_config.yml"
DIAGRAM = REPO / "tests" / "fixtures" / "smoke" / "diagram.puml"
TRANSLATIONS = REPO / "tests" / "fixtures" / "smoke" / "translations_de.yml"

PREFIXES = dedent(
    """\
    @prefix ex: <http://example.org/x#> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    """
)

# Two labels for one class: merge writes its --report only when there is a conflict
LA = PREFIXES + 'ex:Thing a owl:Class ; rdfs:label "Thing A"@en .\n'
LB = PREFIXES + 'ex:Thing a owl:Class ; rdfs:label "Thing B"@en .\n'
DATA = "@prefix ex: <http://example.org/x#> .\nex:i1 a ex:Thing .\n"

ONTOLOGIES = {"la.ttl": LA, "lb.ttl": LB}
WITH_DATA = {"la.ttl": LA, "lb.ttl": LB, "dat.ttl": DATA}


def _write(tmp_path: Path, files: dict[str, str | Path]) -> None:
    """Create each file under ``tmp_path``: a string is its text, a ``Path`` is copied."""
    for rel, content in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, Path):
            shutil.copy(content, target)
        else:
            target.write_text(content)


def _run(argv: list[str], tmp_path: Path) -> tuple[Result, dict[str, str], dict[str, str]]:
    """Run the CLI from ``tmp_path`` and snapshot the disk around it."""
    from rdf_construct.cli import cli
    from tests.test_cli_smoke import assert_no_crash, snapshot

    before = snapshot(argv, tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = CliRunner().invoke(cli, argv)
    finally:
        os.chdir(cwd)
    assert_no_crash(result)
    return result, before, snapshot(argv, tmp_path)


def _case_blind(tmp_path: Path) -> bool:
    """Whether ``tmp_path``'s filesystem ignores case, as macOS and Windows do by default."""
    probe = tmp_path / "case-probe"
    probe.write_text("")
    try:
        return (tmp_path / "CASE-PROBE").exists()
    finally:
        probe.unlink()


# name: (files, argv, a line the refusal must contain)
REFUSED: dict[str, tuple[dict[str, str | Path], list[str], str]] = {
    "stats -o the ontology": (
        ONTOLOGIES,
        ["stats", "la.ttl", "-o", "la.ttl"],
        "-o la.ttl would replace the input la.ttl.",
    ),
    "stats -o the second of several inputs": (
        ONTOLOGIES,
        ["stats", "la.ttl", "lb.ttl", "-o", "lb.ttl"],
        "-o lb.ttl would replace the input lb.ttl.",
    ),
    "stats --compare -o the new file": (
        ONTOLOGIES,
        ["stats", "--compare", "la.ttl", "lb.ttl", "-o", "lb.ttl"],
        "-o lb.ttl would replace the input lb.ttl.",
    ),
    "describe -o the ontology": (
        ONTOLOGIES,
        ["describe", "la.ttl", "--no-resolve", "-o", "la.ttl"],
        "-o la.ttl would replace the input la.ttl.",
    ),
    "diff -o the old file": (
        ONTOLOGIES,
        ["diff", "la.ttl", "lb.ttl", "-o", "la.ttl"],
        "-o la.ttl would replace the input la.ttl.",
    ),
    "diff -o the new file": (
        ONTOLOGIES,
        ["diff", "la.ttl", "lb.ttl", "-o", "lb.ttl"],
        "-o lb.ttl would replace the input lb.ttl.",
    ),
    "diff -o one of two equivalent files": (
        {"la.ttl": LA, "la2.ttl": LA},
        ["diff", "la.ttl", "la2.ttl", "-o", "la.ttl"],
        "-o la.ttl would replace the input la.ttl.",
    ),
    "cq-test -o the ontology": (
        {"animal.ttl": ANIMAL, "cq.yml": CQ_TESTS},
        ["cq-test", "animal.ttl", "cq.yml", "-o", "animal.ttl"],
        "-o animal.ttl would replace the input animal.ttl.",
    ),
    "cq-test -o the test file": (
        {"animal.ttl": ANIMAL, "cq.yml": CQ_TESTS},
        ["cq-test", "animal.ttl", "cq.yml", "-o", "cq.yml"],
        "-o cq.yml would replace the input cq.yml.",
    ),
    "cq-test -o a --data file": (
        {"animal.ttl": ANIMAL, "cq.yml": CQ_TESTS, "dat.ttl": DATA},
        ["cq-test", "animal.ttl", "cq.yml", "--data", "dat.ttl", "-o", "dat.ttl"],
        "-o dat.ttl would replace the input dat.ttl.",
    ),
    "localise report -o the ontology": (
        {"animal.ttl": ANIMAL},
        ["localise", "report", "animal.ttl", "-l", "en,de", "-o", "animal.ttl"],
        "-o animal.ttl would replace the input animal.ttl.",
    ),
    "localise merge -o a translation file": (
        {"animal.ttl": ANIMAL, "de.yml": TRANSLATIONS},
        ["localise", "merge", "animal.ttl", "de.yml", "-o", "de.yml"],
        "-o de.yml would replace the input de.yml.",
    ),
    "shacl-gen -o the ontology": (
        {"animal.ttl": ANIMAL},
        ["shacl-gen", "animal.ttl", "-o", "animal.ttl"],
        "-o animal.ttl would replace the input animal.ttl.",
    ),
    "shacl-gen -o its config": (
        {"animal.ttl": ANIMAL, "shacl.yml": SHACL_CONFIG},
        ["shacl-gen", "animal.ttl", "-C", "shacl.yml", "-o", "shacl.yml"],
        "-o shacl.yml would replace the input shacl.yml.",
    ),
    "puml2rdf -o the diagram": (
        {"d.puml": DIAGRAM},
        ["puml2rdf", "d.puml", "-o", "d.puml"],
        "-o d.puml would replace the input d.puml.",
    ),
    "merge -o a source": (
        ONTOLOGIES,
        ["merge", "la.ttl", "lb.ttl", "-o", "la.ttl"],
        "-o la.ttl would replace the input la.ttl.",
    ),
    "merge -o the last source": (
        ONTOLOGIES,
        ["merge", "la.ttl", "lb.ttl", "-o", "lb.ttl"],
        "-o lb.ttl would replace the input lb.ttl.",
    ),
    "merge --report a source": (
        ONTOLOGIES,
        ["merge", "la.ttl", "lb.ttl", "-o", "m.ttl", "--report", "la.ttl"],
        "--report la.ttl would replace the input la.ttl.",
    ),
    "merge --report is -o": (
        ONTOLOGIES,
        ["merge", "la.ttl", "lb.ttl", "-o", "out.ttl", "--report", "out.ttl"],
        "-o and --report name one file, out.ttl.",
    ),
    # Without a conflict no report is written, so this was safe only by accident
    "merge --report is -o, without a conflict": (
        {"la.ttl": LA},
        ["merge", "la.ttl", "-o", "out.ttl", "--report", "out.ttl"],
        "-o and --report name one file, out.ttl.",
    ),
    "merge --report differs from -o only in case": (
        ONTOLOGIES,
        ["merge", "la.ttl", "lb.ttl", "-o", "out.ttl", "--report", "OUT.ttl"],
        "-o and --report name one file, out.ttl.",
    ),
    "merge --data-output a source": (
        WITH_DATA,
        ["merge", "la.ttl", "-o", "m.ttl", "--migrate-data", "dat.ttl", "--data-output", "la.ttl"],
        "--data-output la.ttl would replace the input la.ttl.",
    ),
    "merge --data-output is -o": (
        WITH_DATA,
        ["merge", "la.ttl", "-o", "m.ttl", "--migrate-data", "dat.ttl", "--data-output", "m.ttl"],
        "-o and --data-output name one file, m.ttl.",
    ),
    "merge --data-output is --report": (
        WITH_DATA,
        [
            "merge",
            "la.ttl",
            "lb.ttl",
            "-o",
            "m.ttl",
            "--report",
            "r.md",
            "--migrate-data",
            "dat.ttl",
            "--data-output",
            "r.md",
        ],
        "--report and --data-output name one file, r.md.",
    ),
    "merge --data-output the data file": (
        WITH_DATA,
        ["merge", "la.ttl", "-o", "m.ttl", "--migrate-data", "dat.ttl", "--data-output", "dat.ttl"],
        "--data-output dat.ttl would replace the input dat.ttl.",
    ),
    "merge -o the data file": (
        WITH_DATA,
        ["merge", "la.ttl", "-o", "dat.ttl", "--migrate-data", "dat.ttl", "--data-output", "d.ttl"],
        "-o dat.ttl would replace the input dat.ttl.",
    ),
    "merge --report the data file": (
        WITH_DATA,
        [
            "merge",
            "la.ttl",
            "lb.ttl",
            "-o",
            "m.ttl",
            "--report",
            "dat.ttl",
            "--migrate-data",
            "dat.ttl",
            "--data-output",
            "d.ttl",
        ],
        "--report dat.ttl would replace the input dat.ttl.",
    ),
    "merge -o its config": (
        {"la.ttl": LA, "m.yml": "sources:\n  - path: la.ttl\n"},
        ["merge", "-c", "m.yml", "-o", "m.yml"],
        "-o m.yml would replace the input m.yml.",
    ),
    "merge -o its --migration-rules file": (
        {"la.ttl": LA, "rules.yml": "rules: []\n"},
        ["merge", "la.ttl", "-o", "rules.yml", "--migration-rules", "rules.yml"],
        "-o rules.yml would replace the input rules.yml.",
    ),
    "merge -o a source named only in its config": (
        {"la.ttl": LA, "m.yml": "sources:\n  - path: la.ttl\n"},
        ["merge", "-c", "m.yml", "-o", "la.ttl"],
        "-o la.ttl would replace the input la.ttl.",
    ),
    "merge --dry-run refuses the same way": (
        ONTOLOGIES,
        ["merge", "la.ttl", "lb.ttl", "-o", "m.ttl", "--report", "lb.ttl", "--dry-run"],
        "--report lb.ttl would replace the input lb.ttl.",
    ),
    "stats -o the ontology through ..": (
        {**ONTOLOGIES, "sub/keep": ""},
        ["stats", "la.ttl", "-o", "sub/../la.ttl"],
        "-o sub/../la.ttl would replace the input la.ttl.",
    ),
    "merge -o a source through ..": (
        {**ONTOLOGIES, "sub/keep": ""},
        ["merge", "la.ttl", "lb.ttl", "-o", "sub/../la.ttl"],
        "-o sub/../la.ttl would replace the input la.ttl.",
    ),
}


@pytest.mark.parametrize("case", list(REFUSED))
def test_refused_with_nothing_written(case: str, tmp_path: Path) -> None:
    from tests.test_cli_smoke import assert_wrote_nothing

    files, argv, line = REFUSED[case]
    _write(tmp_path, files)

    result, before, after = _run(argv, tmp_path)

    assert result.exit_code == 2, result.output
    assert "Nothing was written:" in result.output
    assert line in result.output
    assert_wrote_nothing(before, after)


@pytest.mark.parametrize(
    "argv",
    [
        ["stats", "la.ttl", "-o", "link.ttl"],
        ["diff", "la.ttl", "lb.ttl", "-o", "link.ttl"],
        ["merge", "la.ttl", "lb.ttl", "-o", "link.ttl"],
        ["merge", "la.ttl", "lb.ttl", "-o", "m.ttl", "--report", "link.ttl"],
    ],
    ids=["stats", "diff", "merge -o", "merge --report"],
)
@pytest.mark.parametrize("link", ["symbolic", "hard"])
def test_refused_through_a_link(argv: list[str], link: str, tmp_path: Path) -> None:
    from tests.test_cli_smoke import assert_wrote_nothing

    _write(tmp_path, ONTOLOGIES)
    (os.symlink if link == "symbolic" else os.link)(tmp_path / "la.ttl", tmp_path / "link.ttl")

    result, before, after = _run(argv, tmp_path)

    assert result.exit_code == 2, result.output
    assert "link.ttl would replace the input la.ttl." in result.output
    assert_wrote_nothing(before, after)


@pytest.mark.parametrize(
    "argv",
    [
        ["stats", "la.ttl", "-o", "LA.TTL"],
        ["describe", "la.ttl", "--no-resolve", "-o", "LA.TTL"],
        ["diff", "la.ttl", "lb.ttl", "-o", "LA.TTL"],
        ["merge", "la.ttl", "lb.ttl", "-o", "LA.TTL"],
        ["merge", "la.ttl", "lb.ttl", "-o", "m.ttl", "--report", "LA.TTL"],
    ],
    ids=["stats", "describe", "diff", "merge -o", "merge --report"],
)
def test_refused_in_another_case(argv: list[str], tmp_path: Path) -> None:
    """On a case-blind filesystem ``LA.TTL`` is ``la.ttl``; elsewhere it is a new file."""
    from tests.test_cli_smoke import assert_wrote_nothing

    if not _case_blind(tmp_path):
        pytest.skip("LA.TTL and la.ttl are two files on a case-sensitive filesystem")
    _write(tmp_path, ONTOLOGIES)

    result, before, after = _run(argv, tmp_path)

    assert result.exit_code == 2, result.output
    assert "LA.TTL would replace the input la.ttl." in result.output
    assert_wrote_nothing(before, after)


def test_every_problem_is_listed(tmp_path: Path) -> None:
    _write(tmp_path, ONTOLOGIES)

    result, _, _ = _run(
        ["merge", "la.ttl", "lb.ttl", "-o", "la.ttl", "--report", "la.ttl"], tmp_path
    )

    assert result.exit_code == 2
    assert result.output.splitlines()[1:] == [
        "  -o and --report name one file, la.ttl. Choose different paths.",
        "  -o la.ttl would replace the input la.ttl. Choose another path.",
        "  --report la.ttl would replace the input la.ttl. Choose another path.",
    ]


# ---------------------------------------------------------------------------
# What still runs
# ---------------------------------------------------------------------------


class TestUnchanged:
    """Outputs that are no input, and the two inputs an output may still replace."""

    @pytest.mark.parametrize(
        ("argv", "code"),
        [
            (["stats", "la.ttl", "-o", "s.txt"], 0),
            (["describe", "la.ttl", "--no-resolve", "-o", "d.txt"], 0),
            (["diff", "la.ttl", "lb.ttl", "-o", "diff.txt"], 1),
            (["merge", "la.ttl", "lb.ttl", "-o", "m.ttl", "--report", "r.md"], 0),
        ],
        ids=["stats", "describe", "diff", "merge"],
    )
    def test_a_new_path_is_written(self, argv: list[str], code: int, tmp_path: Path) -> None:
        _write(tmp_path, ONTOLOGIES)

        result, _, _ = _run(argv, tmp_path)

        assert result.exit_code == code, result.output
        for path in argv[argv.index("-o") + 1 :: 2]:
            assert (tmp_path / path).stat().st_size > 0

    def test_an_earlier_report_is_replaced(self, tmp_path: Path) -> None:
        """An existing output that is not an input is written over, as before."""
        _write(tmp_path, {**ONTOLOGIES, "s.txt": "last run\n"})

        result, _, _ = _run(["stats", "la.ttl", "-o", "s.txt"], tmp_path)

        assert result.exit_code == 0, result.output
        assert (tmp_path / "s.txt").read_text().startswith("Ontology Statistics")

    def test_puml2rdf_may_update_its_merge_ontology(self, tmp_path: Path) -> None:
        """``--merge onto.ttl -o onto.ttl`` is the round trip the CLI reference documents."""
        _write(tmp_path, {"d.puml": DIAGRAM})
        first, _, _ = _run(["puml2rdf", "d.puml", "-o", "onto.ttl"], tmp_path)
        assert first.exit_code == 0, first.output

        result, _, _ = _run(
            ["puml2rdf", "d.puml", "--merge", "onto.ttl", "-o", "onto.ttl"], tmp_path
        )

        assert result.exit_code == 0, result.output
        assert "Preserved" in result.output
        assert "owl:Class" in (tmp_path / "onto.ttl").read_text()

    def test_localise_merge_may_write_over_its_source(self, tmp_path: Path) -> None:
        """``-o`` equal to SOURCE is #162's question, so #412 leaves it as it was."""
        _write(tmp_path, {"animal.ttl": ANIMAL, "de.yml": TRANSLATIONS})

        result, _, _ = _run(
            ["localise", "merge", "animal.ttl", "de.yml", "-o", "animal.ttl"], tmp_path
        )

        assert result.exit_code == 0, result.output
        assert "@de" in (tmp_path / "animal.ttl").read_text()


def test_guide_refusal_is_the_real_output(tmp_path: Path) -> None:
    """``MERGE_SPLIT_GUIDE.md``'s refusal runs verbatim and prints what it shows."""
    import re
    import shlex

    guide = (REPO / "docs" / "user_guides" / "MERGE_SPLIT_GUIDE.md").read_text()
    section = guide[guide.index("#### Where Output Goes") : guide.index("### Conflict Detection")]
    command, shown = re.findall(r"```(?:bash)?\n(.*?)```", section, re.S)
    argv = shlex.split(command.replace("\\\n", " "))
    assert argv[0] == "rdf-construct"
    shutil.copytree(REPO / "examples" / "merge", tmp_path / "examples" / "merge")

    result, before, after = _run(argv[1:], tmp_path)

    from tests.test_cli_smoke import assert_wrote_nothing

    assert result.exit_code == 2
    assert result.output == shown
    assert_wrote_nothing(before, after)
