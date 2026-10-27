"""``refactor rename`` plans every output before writing, and migrates from what it read.

#411: two outputs that are one file, or an output that is an input, are refused at exit 2 with
nothing written, unless ``--in-place`` lets a source or data file be rewritten with its own
result. A config's ``output:`` with several sources is refused, and a CLI ``-o`` overrides it.

#414: the data's rename map is built from the sources as read, so an in-place namespace rename
migrates the same data as one written elsewhere, and a data file that cannot be parsed refuses
the run before anything is written.

The same-file checks live in ``core.output_paths``, tested first.
"""

import os
from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner, Result

from rdf_construct.core.output_paths import (
    PlannedOutput,
    colliding_outputs,
    is_same_file,
    outputs_over_inputs,
)

NS_X = "http://example.org/x#"
OLD_NS = "http://old.example.org/ont#"
NEW_NS = "http://new.example.org/ont#"
REN_X = ["--from", f"{NS_X}Old", "--to", f"{NS_X}New"]
REN_NS = ["--from-namespace", OLD_NS, "--to-namespace", NEW_NS]


def _ontology(local: str) -> str:
    return dedent(
        f"""\
        @prefix ex: <{NS_X}> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .

        ex:{local} a owl:Class .
        ex:Old a owl:Class .
        """
    )


DATA = f"@prefix ex: <{NS_X}> .\n<http://example.org/d#i1> a ex:Old .\n"

NS_ONTOLOGY = dedent(
    f"""\
    @prefix o: <{OLD_NS}> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .

    o:Building a owl:Class .
    o:hasFloors a owl:DatatypeProperty .
    """
)

NS_DATA = f"@prefix o: <{OLD_NS}> .\n<http://example.org/d#b1> a o:Building ; o:hasFloors 3 .\n"

CONFIG = dedent(
    f"""\
    rename:
      entities:
        "{NS_X}Old": "{NS_X}New"
    output: renamed.ttl
    """
)


def _write(tmp_path: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)


def _run(argv: list[str], tmp_path: Path) -> tuple[Result, dict[str, str], dict[str, str]]:
    """Run the CLI from ``tmp_path`` and snapshot the disk around it."""
    from rdf_construct.cli import cli
    from tests.test_cli_smoke import assert_no_crash, snapshot

    resolved = [str(tmp_path / a[2:]) if a.startswith("@/") else a for a in argv]
    before = snapshot(resolved, tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = CliRunner().invoke(cli, resolved)
    finally:
        os.chdir(cwd)
    assert_no_crash(result)
    return result, before, snapshot(resolved, tmp_path)


# ---------------------------------------------------------------------------
# core.output_paths
# ---------------------------------------------------------------------------


class TestCollidingOutputs:
    """Two outputs are one file when their resolved paths match, ignoring case."""

    def test_distinct_outputs(self, tmp_path):
        outputs = [PlannedOutput(tmp_path / "a.ttl"), PlannedOutput(tmp_path / "b.ttl")]
        assert colliding_outputs(outputs) == []

    def test_same_path_twice(self, tmp_path):
        a, b = PlannedOutput(tmp_path / "out.ttl", tmp_path / "x"), PlannedOutput(
            tmp_path / "out.ttl", tmp_path / "y"
        )
        assert colliding_outputs([a, b]) == [[a, b]]

    def test_case_and_dot_dot_are_the_same_file(self, tmp_path):
        (tmp_path / "sub").mkdir()
        outputs = [
            PlannedOutput(tmp_path / "out" / "A.ttl"),
            PlannedOutput(tmp_path / "sub" / ".." / "out" / "a.ttl"),
            PlannedOutput(tmp_path / "out" / "b.ttl"),
        ]
        assert colliding_outputs(outputs) == [outputs[:2]]

    def test_through_a_symlinked_directory(self, tmp_path):
        (tmp_path / "real").mkdir()
        os.symlink(tmp_path / "real", tmp_path / "link")
        outputs = [PlannedOutput(tmp_path / "real/a.ttl"), PlannedOutput(tmp_path / "link/a.ttl")]
        assert colliding_outputs(outputs) == [outputs]


class TestOutputsOverInputs:
    """An output is an input when both exist and are the same file, however spelled."""

    def test_missing_output_is_never_an_input(self, tmp_path):
        source = tmp_path / "a.ttl"
        source.write_text("x")
        assert not is_same_file(tmp_path / "new.ttl", source)

    @pytest.mark.parametrize("spelling", ["same", "symlink", "hardlink", "dotdot"])
    def test_every_spelling_of_one_file(self, tmp_path, spelling):
        source = tmp_path / "a.ttl"
        source.write_text("x")
        (tmp_path / "sub").mkdir()
        output = {
            "same": source,
            "symlink": tmp_path / "sub" / "link.ttl",
            "hardlink": tmp_path / "sub" / "hard.ttl",
            "dotdot": tmp_path / "sub" / ".." / "a.ttl",
        }[spelling]
        if spelling == "symlink":
            os.symlink(source, output)
        if spelling == "hardlink":
            os.link(source, output)

        planned = PlannedOutput(output, made_from=source)
        assert outputs_over_inputs([planned], [source]) == [(planned, source)]

    def test_other_file_is_not_an_input(self, tmp_path):
        source, other = tmp_path / "a.ttl", tmp_path / "b.ttl"
        source.write_text("x")
        other.write_text("x")
        assert outputs_over_inputs([PlannedOutput(other)], [source]) == []


# ---------------------------------------------------------------------------
# refactor rename: refused, nothing written
# ---------------------------------------------------------------------------

REFUSED = {
    "same basename, two sources": (
        {"x/onto.ttl": _ontology("X"), "y/onto.ttl": _ontology("Y")},
        ["@/x/onto.ttl", "@/y/onto.ttl", *REN_X, "-o", "@/out"],
        "would be written 2 times",
    ),
    "basenames differ only in case": (
        {"p/A.ttl": _ontology("Upper"), "q/a.ttl": _ontology("Lower")},
        ["@/p/A.ttl", "@/q/a.ttl", *REN_X, "-o", "@/out"],
        "would be written 2 times",
    ),
    "-o is the sources' directory": (
        {"z/a.ttl": _ontology("A"), "z/b.ttl": _ontology("B")},
        ["@/z/a.ttl", "@/z/b.ttl", *REN_X, "-o", "@/z"],
        "Pass --in-place",
    ),
    "-o is the single source": (
        {"a.ttl": _ontology("A")},
        ["@/a.ttl", *REN_X, "-o", "@/a.ttl"],
        "is the input it is made from: writing it would replace that file",
    ),
    "-o is one of two sources": (
        {"a.ttl": _ontology("A"), "b.ttl": _ontology("B")},
        ["@/a.ttl", "@/b.ttl", *REN_X, "-o", "@/a.ttl"],
        "is a file, but with several inputs -o names a directory",
    ),
    "--dry-run refuses as the run would": (
        {"a.ttl": _ontology("A")},
        ["@/a.ttl", *REN_X, "-o", "@/a.ttl", "--dry-run"],
        "Pass --in-place",
    ),
    "config output: with two CLI sources": (
        {"a.ttl": _ontology("A"), "b.ttl": _ontology("B"), "cfg.yml": CONFIG},
        ["@/a.ttl", "@/b.ttl", "-c", "@/cfg.yml"],
        "The config's output: names one file, renamed.ttl, but there are 2 sources",
    ),
    "config output: with two config sources": (
        {
            "a.ttl": _ontology("A"),
            "b.ttl": _ontology("B"),
            "cfg.yml": CONFIG + "source_files:\n  - a.ttl\n  - b.ttl\n",
        },
        ["-c", "@/cfg.yml"],
        "but there are 2 sources",
    ),
    "two data files, same basename": (
        {"ont.ttl": _ontology("A"), "p/data.ttl": DATA, "q/data.ttl": DATA},
        [
            "@/ont.ttl",
            *REN_X,
            "-o",
            "@/new.ttl",
            "--migrate-data",
            "@/p/data.ttl",
            "--migrate-data",
            "@/q/data.ttl",
            "--data-output",
            "@/dd",
        ],
        "dd/data.ttl would be written 2 times",
    ),
    "data output is the ontology output": (
        {"ont.ttl": _ontology("A"), "data.ttl": DATA},
        [
            "@/ont.ttl",
            *REN_X,
            "-o",
            "@/new.ttl",
            "--migrate-data",
            "@/data.ttl",
            "--data-output",
            "@/new.ttl",
        ],
        "new.ttl would be written 2 times",
    ),
    "data output is the data file": (
        {"ont.ttl": _ontology("A"), "data.ttl": DATA},
        [
            "@/ont.ttl",
            *REN_X,
            "-o",
            "@/new.ttl",
            "--migrate-data",
            "@/data.ttl",
            "--data-output",
            "@/data.ttl",
        ],
        "Pass --in-place",
    ),
    "data output is the source, even with --in-place": (
        {"ont.ttl": _ontology("A"), "data.ttl": DATA},
        [
            "@/ont.ttl",
            *REN_X,
            "-o",
            "@/new.ttl",
            "--in-place",
            "--migrate-data",
            "@/data.ttl",
            "--data-output",
            "@/ont.ttl",
        ],
        "ont.ttl would replace an input, but it is the result of",
    ),
    "-o is the config file, even with --in-place": (
        {"a.ttl": _ontology("A"), "cfg.yml": CONFIG.replace("output: renamed.ttl\n", "")},
        ["@/a.ttl", "-c", "@/cfg.yml", "-o", "@/cfg.yml", "--in-place"],
        "cfg.yml would replace an input",
    ),
    "a data file that does not parse": (
        {"ont.ttl": _ontology("A"), "good.ttl": DATA, "bad.ttl": "this is not turtle .\n"},
        [
            "@/ont.ttl",
            *REN_X,
            "-o",
            "@/new.ttl",
            "--migrate-data",
            "@/good.ttl",
            "--migrate-data",
            "@/bad.ttl",
            "--data-output",
            "@/dd",
        ],
        "Could not parse data file",
    ),
}


@pytest.mark.parametrize("case", list(REFUSED))
def test_refused_with_nothing_written(case, tmp_path):
    from tests.test_cli_smoke import assert_wrote_nothing

    files, argv, message = REFUSED[case]
    _write(tmp_path, files)

    result, before, after = _run(["refactor", "rename", *argv], tmp_path)

    assert result.exit_code == 2, result.output
    assert message in result.output
    assert_wrote_nothing(before, after)


def test_refused_through_a_symlinked_directory(tmp_path):
    from tests.test_cli_smoke import assert_wrote_nothing

    _write(tmp_path, {"z/a.ttl": _ontology("A"), "z/b.ttl": _ontology("B")})
    os.symlink(tmp_path / "z", tmp_path / "link")

    result, before, after = _run(
        ["refactor", "rename", "@/z/a.ttl", "@/z/b.ttl", *REN_X, "-o", "@/link"], tmp_path
    )

    assert result.exit_code == 2, result.output
    assert "is the input it is made from" in result.output
    assert_wrote_nothing(before, after)


def test_every_problem_is_listed(tmp_path):
    _write(tmp_path, {"z/a.ttl": _ontology("A"), "z/b.ttl": _ontology("B")})

    result, _, _ = _run(
        ["refactor", "rename", "@/z/a.ttl", "@/z/b.ttl", *REN_X, "-o", "@/z"], tmp_path
    )

    assert result.exit_code == 2
    assert result.output.count("is the input it is made from") == 2


# ---------------------------------------------------------------------------
# refactor rename: what still runs
# ---------------------------------------------------------------------------


class TestInPlace:
    """``--in-place`` rewrites each input with its own result, and says so."""

    def test_sources_directory(self, tmp_path):
        _write(tmp_path, {"z/a.ttl": _ontology("A"), "z/b.ttl": _ontology("B")})

        result, _, _ = _run(
            ["refactor", "rename", "@/z/a.ttl", "@/z/b.ttl", *REN_X, "-o", "@/z", "--in-place"],
            tmp_path,
        )

        assert result.exit_code == 0, result.output
        for name in ("a.ttl", "b.ttl"):
            text = (tmp_path / "z" / name).read_text()
            assert "ex:New" in text and "ex:Old" not in text
            assert f"⚠ Replaced {tmp_path / 'z' / name}" in result.output

    def test_namespace_rename_migrates_as_it_would_elsewhere(self, tmp_path):
        """#414's reproducer: in place, the data is migrated as with ``-o new.ttl``."""
        outputs = {}
        for target in ("ont.ttl", "new.ttl"):
            work = tmp_path / target.removesuffix(".ttl")
            _write(work, {"ont.ttl": NS_ONTOLOGY, "data.ttl": NS_DATA})
            result, _, _ = _run(
                [
                    "refactor",
                    "rename",
                    "@/ont.ttl",
                    *REN_NS,
                    "-o",
                    f"@/{target}",
                    "--in-place",
                    "--migrate-data",
                    "@/data.ttl",
                    "--data-output",
                    "@/dout.ttl",
                ],
                work,
            )
            assert result.exit_code == 0, result.output
            assert "Migrated data.ttl: 2 changes" in result.output
            outputs[target] = (work / "dout.ttl").read_bytes()

        assert outputs["ont.ttl"] == outputs["new.ttl"]
        assert NEW_NS.encode() in outputs["ont.ttl"]
        assert OLD_NS.encode() not in outputs["ont.ttl"]

    def test_data_file_rewritten_with_its_own_migration(self, tmp_path):
        _write(tmp_path, {"ont.ttl": NS_ONTOLOGY, "data.ttl": NS_DATA})

        result, _, _ = _run(
            [
                "refactor",
                "rename",
                "@/ont.ttl",
                *REN_NS,
                "-o",
                "@/ont.ttl",
                "--in-place",
                "--migrate-data",
                "@/data.ttl",
                "--data-output",
                "@/data.ttl",
            ],
            tmp_path,
        )

        assert result.exit_code == 0, result.output
        assert NEW_NS in (tmp_path / "data.ttl").read_text()
        assert f"⚠ Replaced {tmp_path / 'data.ttl'}" in result.output

    def test_flag_without_an_input_to_replace_changes_nothing(self, tmp_path):
        _write(tmp_path, {"a.ttl": _ontology("A")})

        result, _, _ = _run(
            ["refactor", "rename", "@/a.ttl", *REN_X, "-o", "@/new.ttl", "--in-place"], tmp_path
        )

        assert result.exit_code == 0, result.output
        assert "Replaced" not in result.output
        assert "ex:Old" in (tmp_path / "a.ttl").read_text()


class TestUnchanged:
    """What #411 and #414 leave as it was on ``main``."""

    def test_single_source_without_o_writes_nothing(self, tmp_path):
        """#183's case is P37's to decide; it still writes nothing at exit 0."""
        _write(tmp_path, {"a.ttl": _ontology("A")})

        result, before, after = _run(["refactor", "rename", "@/a.ttl", *REN_X], tmp_path)

        assert result.exit_code == 0, result.output
        assert before == after

    def test_two_sources_into_a_fresh_directory(self, tmp_path):
        _write(tmp_path, {"x/a.ttl": _ontology("A"), "y/b.ttl": _ontology("B")})

        result, _, _ = _run(
            ["refactor", "rename", "@/x/a.ttl", "@/y/b.ttl", *REN_X, "-o", "@/out"], tmp_path
        )

        assert result.exit_code == 0, result.output
        assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["a.ttl", "b.ttl"]


class TestConfigOutput:
    """A CLI ``-o`` overrides a config's ``output:`` (#411)."""

    def test_directory_o_wins_over_config_output(self, tmp_path):
        _write(tmp_path, {"a.ttl": _ontology("A"), "b.ttl": _ontology("B"), "cfg.yml": CONFIG})

        result, _, _ = _run(
            ["refactor", "rename", "@/a.ttl", "@/b.ttl", "-c", "@/cfg.yml", "-o", "@/outdir"],
            tmp_path,
        )

        assert result.exit_code == 0, result.output
        assert sorted(p.name for p in (tmp_path / "outdir").iterdir()) == ["a.ttl", "b.ttl"]
        assert not (tmp_path / "renamed.ttl").exists()

    def test_config_output_with_one_source(self, tmp_path):
        _write(tmp_path, {"a.ttl": _ontology("A"), "cfg.yml": CONFIG})

        result, _, _ = _run(["refactor", "rename", "@/a.ttl", "-c", "@/cfg.yml"], tmp_path)

        assert result.exit_code == 0, result.output
        assert "ex:New" in (tmp_path / "renamed.ttl").read_text()


def test_guide_refusal_is_the_real_output(monkeypatch):
    """``REFACTOR_GUIDE.md``'s in-place refusal runs verbatim and prints what it shows."""
    import re
    import shlex

    from rdf_construct.cli import cli

    root = Path(__file__).parent.parent
    guide = (root / "docs" / "user_guides" / "REFACTOR_GUIDE.md").read_text()
    section = guide[guide.index("### Where Output Goes") : guide.index("### CURIEs")]
    command, shown = re.findall(r"```(?:bash)?\n(.*?)```", section, re.S)
    argv = shlex.split(command.replace("\\\n", " "))
    assert argv[0] == "rdf-construct"

    monkeypatch.chdir(root)
    before = (root / "examples" / "refactor" / "typos.ttl").read_bytes()
    result = CliRunner().invoke(cli, argv[1:])

    assert result.exit_code == 2
    assert result.output == shown
    assert (root / "examples" / "refactor" / "typos.ttl").read_bytes() == before
