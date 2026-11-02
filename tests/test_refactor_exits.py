"""What `refactor rename` and `refactor deprecate` write, and how they exit (#183, #186, #352).

- #183: a rename that would write nothing is refused at 2; a rename that matches nothing in
  any file of the run exits 1, naming it.
- #186: `deprecate` plans every output before writing, as `rename` does: several sources take
  a directory, an output over a source needs `--in-place`, and an entity is missing only when
  no source describes it.
- #352: `-c` with an operation flag is refused at 2 before anything is read.

The two sources differ, so a run that writes one over the other shows it.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL

from rdf_construct.cli import cli
from tests.test_cli_smoke import assert_no_crash, assert_wrote_nothing, snapshot

REPO = Path(__file__).resolve().parent.parent
REFACTOR = REPO / "examples" / "refactor"

A_NS = "http://example.org/a#"
B_NS = "http://example.org/b#"

A_TTL = f"""@prefix ex: <{A_NS}> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:A a owl:Class .
ex:Old a owl:Class .
"""

B_TTL = f"""@prefix ex: <{B_NS}> .
@prefix a: <{A_NS}> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:B a owl:Class ; rdfs:subClassOf a:Old .
ex:OnlyB a owl:Class .
"""

DATA_TTL = f"<http://example.org/d#i1> a <{A_NS}Old> .\n"

RENAME_OLD = ["--from", f"{A_NS}Old", "--to", f"{A_NS}New"]
DEPRECATE_OLD = ["--entity", f"{A_NS}Old"]


def _files(tmp_path: Path, **files: str) -> None:
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)


def _cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *args: str
) -> tuple[Result, dict[str, str], dict[str, str]]:
    """Run `refactor …` in ``tmp_path``; return the result and the snapshots around it."""
    monkeypatch.chdir(tmp_path)
    argv = ["refactor", *args]
    before = snapshot(argv, tmp_path)
    result = CliRunner().invoke(cli, argv)
    assert_no_crash(result)
    return result, before, snapshot(argv, tmp_path)


def _refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> str:
    """Run a command that must be refused: exit 2, nothing written. Returns its stderr."""
    result, before, after = _cli(tmp_path, monkeypatch, *args)
    assert result.exit_code == 2, result.output
    assert_wrote_nothing(before, after)
    return result.stderr


def _parse(path: Path) -> Graph:
    return Graph().parse(path, format="turtle")


def _deprecated(graph: Graph, local: str, ns: str = A_NS) -> bool:
    return (URIRef(ns + local), OWL.deprecated, Literal(True)) in graph


# --- #183: a rename that would write nothing -------------------------------------------------


class TestRenameWritesNothing:
    def test_no_output_is_refused(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        stderr = _refused(tmp_path, monkeypatch, "rename", "a.ttl", *RENAME_OLD)
        assert "Nothing was written:\n  no output was named" in stderr
        assert "Pass -o FILE (-o DIR/ for several sources)" in stderr

    def test_several_sources_without_output_are_refused(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL, "b.ttl": B_TTL})
        stderr = _refused(tmp_path, monkeypatch, "rename", "a.ttl", "b.ttl", *RENAME_OLD)
        assert "no output was named" in stderr

    def test_a_config_without_output_is_refused(self, tmp_path, monkeypatch):
        _files(
            tmp_path,
            **{
                "a.ttl": A_TTL,
                "r.yml": f"source_files: [a.ttl]\nrename:\n  entities:\n"
                f"    '{A_NS}Old': '{A_NS}New'\n",
            },
        )
        stderr = _refused(tmp_path, monkeypatch, "rename", "-c", "r.yml")
        assert "set output: or output_dir: in the config" in stderr

    def test_in_place_alone_names_no_output(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        stderr = _refused(tmp_path, monkeypatch, "rename", "a.ttl", *RENAME_OLD, "--in-place")
        assert "--in-place lets -o replace a source; it does not name one." in stderr

    def test_a_dry_run_without_output_still_runs(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        result, before, after = _cli(
            tmp_path, monkeypatch, "rename", "a.ttl", *RENAME_OLD, "--dry-run"
        )
        assert result.exit_code == 0, result.output
        assert before == after

    def test_data_only_run_writes_the_data_and_says_so(self, tmp_path, monkeypatch):
        """The guide's typo workflow, step 3, has no -o: the data is still migrated."""
        _files(tmp_path, **{"a.ttl": A_TTL, "data.ttl": DATA_TTL})
        result, _, _ = _cli(
            tmp_path,
            monkeypatch,
            "rename",
            "a.ttl",
            *RENAME_OLD,
            "--migrate-data",
            "data.ttl",
            "--data-output",
            "new_data.ttl",
        )
        assert result.exit_code == 0, result.output
        assert "Note: no -o, so the renamed ontology is not written" in result.stderr
        assert (None, None, URIRef(f"{A_NS}New")) in _parse(tmp_path / "new_data.ttl")
        assert sorted(p.name for p in tmp_path.iterdir()) == ["a.ttl", "data.ttl", "new_data.ttl"]

    def test_a_namespace_matching_nothing_has_no_data_to_migrate(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL, "data.ttl": DATA_TTL})
        stderr = _refused(
            tmp_path,
            monkeypatch,
            "rename",
            "a.ttl",
            "--from-namespace",
            "http://nowhere.example/",
            "--to-namespace",
            "http://new.example/",
            "--migrate-data",
            "data.ttl",
        )
        assert "the rename matches nothing in the sources, so there is no data to migrate" in stderr


# --- #183: a rename that matches nothing ----------------------------------------------------


class TestRenameMatchesNothing:
    def test_an_absent_entity_exits_1_and_is_named(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        result, _, _ = _cli(
            tmp_path,
            monkeypatch,
            "rename",
            "a.ttl",
            "--from",
            f"{A_NS}Nope",
            "--to",
            f"{A_NS}Gone",
            "-o",
            "out.ttl",
        )
        assert result.exit_code == 1, result.output
        assert "1 rename matched nothing in any file of the run:" in result.stderr
        assert f"<{A_NS}Nope> occurs in no file of the run." in result.stderr
        assert (tmp_path / "out.ttl").exists()

    def test_a_namespace_that_moves_nothing_exits_1(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        result, _, _ = _cli(
            tmp_path,
            monkeypatch,
            "rename",
            "a.ttl",
            "--from-namespace",
            "http://nowhere.example/",
            "--to-namespace",
            "http://new.example/",
            "-o",
            "out.ttl",
        )
        assert result.exit_code == 1, result.output
        assert "namespace <http://nowhere.example/>" in result.stderr

    def test_a_dry_run_exits_as_the_run_would(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        result, before, after = _cli(
            tmp_path,
            monkeypatch,
            "rename",
            "a.ttl",
            "--from",
            f"{A_NS}Nope",
            "--to",
            f"{A_NS}Gone",
            "--dry-run",
        )
        assert result.exit_code == 1, result.output
        assert "matched nothing" in result.stderr
        assert before == after

    def test_a_term_in_one_module_only_is_not_inert(self, tmp_path, monkeypatch):
        """Judged over the union: `ex:OnlyB` is in b.ttl only, and that is enough."""
        _files(tmp_path, **{"a.ttl": A_TTL, "b.ttl": B_TTL})
        result, _, _ = _cli(
            tmp_path,
            monkeypatch,
            "rename",
            "a.ttl",
            "b.ttl",
            "--from",
            f"{B_NS}OnlyB",
            "--to",
            f"{B_NS}Renamed",
            "-o",
            "out",
        )
        assert result.exit_code == 0, result.output
        assert "matched nothing" not in result.stderr

    def test_a_mapping_live_only_in_the_data_is_not_inert(self, tmp_path, monkeypatch):
        """The guide's step 3: the ontology is already fixed, the data is not."""
        _files(tmp_path, **{"b.ttl": B_TTL.replace("a:Old", "ex:B"), "data.ttl": DATA_TTL})
        result, _, _ = _cli(
            tmp_path,
            monkeypatch,
            "rename",
            "b.ttl",
            *RENAME_OLD,
            "-o",
            "out.ttl",
            "--migrate-data",
            "data.ttl",
            "--data-output",
            "new_data.ttl",
        )
        assert result.exit_code == 0, result.output
        assert (None, None, URIRef(f"{A_NS}New")) in _parse(tmp_path / "new_data.ttl")

    def test_a_collision_still_refuses_first(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        rules = (
            f"source_files: [a.ttl]\noutput: out.ttl\nrename:\n  entities:\n"
            f"    '{A_NS}Old': '{A_NS}A'\n    '{A_NS}Nope': '{A_NS}Gone'\n"
        )
        _files(tmp_path, **{"r.yml": rules})
        stderr = _refused(tmp_path, monkeypatch, "rename", "-c", "r.yml")
        assert "would merge two entities" in stderr


class TestRenameOutputResolution:
    def test_o_is_read_against_the_command_line_sources(self, tmp_path, monkeypatch):
        """One CLI source over a two-source config: -o is that source's file, not a directory."""
        _files(
            tmp_path,
            **{
                "a.ttl": A_TTL,
                "b.ttl": B_TTL,
                "r.yml": f"source_files: [a.ttl, b.ttl]\nrename:\n  entities:\n"
                f"    '{A_NS}Old': '{A_NS}New'\n",
            },
        )
        result, _, _ = _cli(
            tmp_path, monkeypatch, "rename", "a.ttl", "-c", "r.yml", "-o", "out.ttl"
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "out.ttl").is_file()

    @pytest.mark.parametrize("command", ["rename", "deprecate"])
    def test_one_source_and_an_existing_directory(self, tmp_path, monkeypatch, command):
        _files(tmp_path, **{"a.ttl": A_TTL})
        (tmp_path / "out").mkdir()
        operation = RENAME_OLD if command == "rename" else DEPRECATE_OLD
        stderr = _refused(tmp_path, monkeypatch, command, "a.ttl", *operation, "-o", "out")
        assert "out is a directory, but with one input -o names the output file." in stderr
        assert "Name a file, such as out/a.ttl." in stderr


# --- #352: -c with an operation flag ---------------------------------------------------------


RENAME_FLAGS = {
    "--from": f"{A_NS}Old",
    "--to": f"{A_NS}New",
    "--from-namespace": A_NS,
    "--to-namespace": B_NS,
}
DEPRECATE_FLAGS = {
    "--entity": f"{A_NS}Old",
    "--replaced-by": f"{A_NS}A",
    "--message": "",
    "--version": "2.0",
}


class TestConfigWithOperation:
    @pytest.mark.parametrize("flag", list(RENAME_FLAGS))
    def test_rename_refuses_each_operation_flag(self, tmp_path, monkeypatch, flag):
        """Refused before the config is read: the config here could not even be loaded."""
        _files(tmp_path, **{"r.yml": ": not yaml ["})
        stderr = _refused(
            tmp_path, monkeypatch, "rename", "-c", "r.yml", flag, RENAME_FLAGS[flag], "-o", "o.ttl"
        )
        assert f"-c/--config cannot be combined with {flag}." in stderr
        assert "config's rename: section" in stderr

    @pytest.mark.parametrize("flag", list(DEPRECATE_FLAGS))
    def test_deprecate_refuses_each_operation_flag(self, tmp_path, monkeypatch, flag):
        """`--message ""` counts: the flag is detected as given, not by its value."""
        _files(tmp_path, **{"d.yml": ": not yaml ["})
        stderr = _refused(
            tmp_path,
            monkeypatch,
            "deprecate",
            "-c",
            "d.yml",
            flag,
            DEPRECATE_FLAGS[flag],
            "-o",
            "o.ttl",
        )
        assert f"-c/--config cannot be combined with {flag}." in stderr
        assert "config's deprecations: section" in stderr

    def test_every_given_flag_is_named(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"r.yml": "rename: {}\n"})
        stderr = _refused(
            tmp_path, monkeypatch, "rename", "-c", "r.yml", "--from", "ex:A", "--to", "ex:B"
        )
        assert "cannot be combined with --from, --to." in stderr

    def test_from_alone_names_the_combination(self, tmp_path, monkeypatch):
        """Not "--from requires --to": the combination is the problem."""
        _files(tmp_path, **{"r.yml": "rename: {}\n"})
        stderr = _refused(tmp_path, monkeypatch, "rename", "-c", "r.yml", "--from", "ex:A")
        assert "cannot be combined with --from." in stderr
        assert "requires" not in stderr

    @pytest.mark.parametrize(
        "settings",
        [
            ["--dry-run"],
            ["--no-colour"],
            ["--merge-entities"],
            ["--migrate-data", "instances.ttl", "--data-output", "d.ttl"],
        ],
        ids=["dry-run", "no-colour", "merge-entities", "migrate-data"],
    )
    def test_rename_settings_still_combine(self, tmp_path, monkeypatch, settings):
        for name in ("typos.ttl", "instances.ttl", "renames.yml"):
            (tmp_path / name).write_bytes((REFACTOR / name).read_bytes())
        result, _, _ = _cli(
            tmp_path, monkeypatch, "rename", "-c", "renames.yml", "-o", "o.ttl", *settings
        )
        assert result.exit_code == 0, result.output

    def test_deprecate_settings_still_combine(self, tmp_path, monkeypatch):
        for name in ("legacy.ttl", "deprecations.yml"):
            (tmp_path / name).write_bytes((REFACTOR / name).read_bytes())
        result, _, _ = _cli(
            tmp_path,
            monkeypatch,
            "deprecate",
            "-c",
            "deprecations.yml",
            "-o",
            "legacy.ttl",
            "--in-place",
            "--no-colour",
        )
        assert result.exit_code == 0, result.output
        assert _deprecated(
            _parse(tmp_path / "legacy.ttl"), "LegacyPerson", "http://example.org/ont#"
        )


# --- #186: deprecate's outputs ---------------------------------------------------------------


class TestDeprecateOutputs:
    def test_several_sources_into_a_directory(self, tmp_path, monkeypatch):
        """Each result keeps its source's name; neither replaces the other."""
        _files(tmp_path, **{"a.ttl": A_TTL, "b.ttl": B_TTL})
        result, _, _ = _cli(
            tmp_path, monkeypatch, "deprecate", "a.ttl", "b.ttl", *DEPRECATE_OLD, "-o", "out"
        )
        assert result.exit_code == 0, result.output
        a, b = _parse(tmp_path / "out" / "a.ttl"), _parse(tmp_path / "out" / "b.ttl")
        assert _deprecated(a, "Old")
        assert (URIRef(f"{B_NS}OnlyB"), None, None) in b
        assert (URIRef(f"{B_NS}OnlyB"), None, None) not in a

    def test_several_sources_and_an_existing_file(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL, "b.ttl": B_TTL, "both.ttl": "# mine\n"})
        stderr = _refused(
            tmp_path, monkeypatch, "deprecate", "a.ttl", "b.ttl", *DEPRECATE_OLD, "-o", "both.ttl"
        )
        assert "both.ttl is a file, but with several inputs -o names a directory." in stderr

    def test_o_naming_the_first_of_two_sources(self, tmp_path, monkeypatch):
        """It used to replace a.ttl with b.ttl's triples."""
        _files(tmp_path, **{"a.ttl": A_TTL, "b.ttl": B_TTL})
        _refused(
            tmp_path, monkeypatch, "deprecate", "a.ttl", "b.ttl", *DEPRECATE_OLD, "-o", "a.ttl"
        )
        assert (tmp_path / "a.ttl").read_text() == A_TTL

    def test_o_naming_its_only_source_needs_in_place(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        stderr = _refused(
            tmp_path, monkeypatch, "deprecate", "a.ttl", *DEPRECATE_OLD, "-o", "a.ttl"
        )
        assert "a.ttl is the input it is made from" in stderr
        assert "Pass --in-place to rewrite it" in stderr

    def test_in_place_rewrites_its_own_source(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        result, _, _ = _cli(
            tmp_path, monkeypatch, "deprecate", "a.ttl", *DEPRECATE_OLD, "-o", "a.ttl", "--in-place"
        )
        assert result.exit_code == 0, result.output
        assert "⚠ Replaced a.ttl" in result.stderr
        assert _deprecated(_parse(tmp_path / "a.ttl"), "Old")

    def test_a_dry_run_is_checked_too(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        _refused(
            tmp_path, monkeypatch, "deprecate", "a.ttl", *DEPRECATE_OLD, "-o", "a.ttl", "--dry-run"
        )

    def test_in_place_without_o_says_what_it_writes(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        result, _, _ = _cli(
            tmp_path, monkeypatch, "deprecate", "a.ttl", *DEPRECATE_OLD, "--in-place"
        )
        assert result.exit_code == 0, result.output
        assert "Note: --in-place lets -o replace its own source" in result.stderr
        assert (tmp_path / "a_deprecated.ttl").exists()
        assert (tmp_path / "a.ttl").read_text() == A_TTL

    def test_a_default_output_over_another_source(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"x.ttl": A_TTL, "x_deprecated.ttl": B_TTL})
        stderr = _refused(
            tmp_path, monkeypatch, "deprecate", "x.ttl", "x_deprecated.ttl", *DEPRECATE_OLD
        )
        assert "x_deprecated.ttl would replace an input, but it is the result of x.ttl." in stderr
        assert "Pass -o to write the results elsewhere." in stderr

    def test_the_config_output_dir_is_honoured(self, tmp_path, monkeypatch):
        _files(
            tmp_path,
            **{
                "a.ttl": A_TTL,
                "d.yml": f"source_files: [a.ttl]\noutput_dir: od\ndeprecations:\n"
                f"  - entity: '{A_NS}Old'\n",
            },
        )
        result, _, _ = _cli(tmp_path, monkeypatch, "deprecate", "-c", "d.yml")
        assert result.exit_code == 0, result.output
        assert _deprecated(_parse(tmp_path / "od" / "a.ttl"), "Old")
        assert not (tmp_path / "a_deprecated.ttl").exists()

    def test_a_config_output_file_for_several_sources(self, tmp_path, monkeypatch):
        _files(
            tmp_path,
            **{
                "a.ttl": A_TTL,
                "b.ttl": B_TTL,
                "d.yml": f"source_files: [a.ttl, b.ttl]\noutput: one.ttl\ndeprecations:\n"
                f"  - entity: '{A_NS}Old'\n",
            },
        )
        stderr = _refused(tmp_path, monkeypatch, "deprecate", "-c", "d.yml")
        assert "The config's output: names one file, one.ttl, but there are 2 sources" in stderr

    def test_one_source_given_twice(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        result, _, _ = _cli(tmp_path, monkeypatch, "deprecate", "a.ttl", "a.ttl", *DEPRECATE_OLD)
        assert result.exit_code == 0, result.output
        assert _deprecated(_parse(tmp_path / "a_deprecated.ttl"), "Old")
        assert (tmp_path / "a.ttl").read_text() == A_TTL


class TestDeprecateNotFound:
    def test_an_entity_in_the_second_source_only(self, tmp_path, monkeypatch):
        """It used to exit 1 after a.ttl and never process b.ttl."""
        _files(tmp_path, **{"a.ttl": A_TTL, "b.ttl": B_TTL})
        result, _, _ = _cli(
            tmp_path, monkeypatch, "deprecate", "a.ttl", "b.ttl", "--entity", f"{B_NS}OnlyB"
        )
        assert result.exit_code == 0, result.output
        assert _deprecated(_parse(tmp_path / "b_deprecated.ttl"), "OnlyB", B_NS)
        assert (tmp_path / "a_deprecated.ttl").exists()

    def test_declared_in_one_module_and_referenced_in_another(self, tmp_path, monkeypatch):
        """b.ttl refers to `a:Old` without describing it: that is not "not found"."""
        _files(tmp_path, **{"a.ttl": A_TTL, "b.ttl": B_TTL})
        result, _, _ = _cli(tmp_path, monkeypatch, "deprecate", "a.ttl", "b.ttl", *DEPRECATE_OLD)
        assert result.exit_code == 0, result.output
        assert "subject in no source" not in result.stderr

    def test_an_entity_in_no_source_exits_1_once(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL, "b.ttl": B_TTL})
        result, _, _ = _cli(
            tmp_path, monkeypatch, "deprecate", "a.ttl", "b.ttl", "--entity", f"{A_NS}Nope"
        )
        assert result.exit_code == 1, result.output
        assert result.stderr.count("1 entity is a subject in no source, so not deprecated:") == 1
        assert f"<{A_NS}Nope>" in result.stderr
        assert (tmp_path / "b_deprecated.ttl").exists()

    def test_a_dry_run_exits_as_the_run_would(self, tmp_path, monkeypatch):
        _files(tmp_path, **{"a.ttl": A_TTL})
        result, before, after = _cli(
            tmp_path, monkeypatch, "deprecate", "a.ttl", "--entity", f"{A_NS}Nope", "--dry-run"
        )
        assert result.exit_code == 1, result.output
        assert before == after


# --- The library: `inert_renames` ------------------------------------------------------------


class TestInertRenames:
    SOURCES = """@prefix a: <http://e.org/a/> .
@prefix b: <http://e.org/a/b/> .
a:X a a:C .
b:Y a a:C .
"""

    def _inert(self, **rename: dict[str, str]) -> list[tuple[str, str]]:
        from rdf_construct.refactor import RenameConfig, inert_renames

        sources = Graph().parse(data=self.SOURCES, format="turtle")
        return [(i.old, i.reason) for i in inert_renames(RenameConfig(**rename), sources)]

    def test_a_rule_onto_itself(self):
        assert self._inert(namespaces={"http://e.org/a/": "http://e.org/a/"}) == [
            ("http://e.org/a/", "self")
        ]

    def test_a_rule_shadowed_by_a_longer_one(self):
        """`b:Y` moves by the longer rule; the shorter still moves `a:X` and `a:C`."""
        rules = {"http://e.org/a/": "http://n/a/", "http://e.org/a/b/": "http://n/b/"}
        assert self._inert(namespaces=rules) == []
        only_b = {"http://e.org/a/b": "http://n/x/", "http://e.org/a/b/": "http://n/b/"}
        assert self._inert(namespaces=only_b) == [("http://e.org/a/b", "absent")]

    def test_a_rule_whose_terms_all_move_by_entity_mappings(self):
        assert self._inert(
            namespaces={"http://e.org/a/b/": "http://n/b/"},
            entities={"http://e.org/a/b/Y": "http://k/Y"},
        ) == [("http://e.org/a/b/", "absent")]
