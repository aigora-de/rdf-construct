"""`diff --show`, `--hide` and `--entities`: refused when they name nothing usable, and never
the verdict (#144).

A filter changes only what is shown. The exit code, the "identical" sentence and the JSON's
`identical` describe the whole comparison, and a filtered view says what it left out.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from rdf_construct.cli import cli
from rdf_construct.diff import compare_files, filter_diff
from rdf_construct.diff.comparator import NON_TREE_LIMIT
from rdf_construct.diff.filters import (
    CHANGE_TYPE_MAP,
    CHANGE_TYPE_NAMES,
    ENTITY_TYPE_MAP,
    ENTITY_TYPE_NAMES,
    STRUCTURES,
    UnknownFilterError,
)

ROOT = Path(__file__).resolve().parent.parent
V1 = ROOT / "examples" / "diff" / "v1.ttl"
V2 = ROOT / "examples" / "diff" / "v2.ttl"

PREFIXES = """\
@prefix ex: <http://example.org/ont#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
"""

# #144's reproducer: ex:Cat is removed, and nothing else changes
OLD = (
    PREFIXES
    + """\
ex:Animal a owl:Class .
ex:Dog a owl:Class ; rdfs:subClassOf ex:Animal .
ex:Cat a owl:Class ; rdfs:subClassOf ex:Animal .
"""
)
NEW = (
    PREFIXES
    + """\
ex:Animal a owl:Class .
ex:Dog a owl:Class ; rdfs:subClassOf ex:Animal .
"""
)

IDENTICAL = "Graphs are semantically identical"
NO_DIFFERENCES = "No semantic differences found."


def _run(tmp_path: Path, old: str, new: str, *options: str) -> Result:
    (tmp_path / "old.ttl").write_text(old, encoding="utf-8")
    (tmp_path / "new.ttl").write_text(new, encoding="utf-8")
    return CliRunner().invoke(
        cli, ["diff", str(tmp_path / "old.ttl"), str(tmp_path / "new.ttl"), *options]
    )


def _run_examples(*options: str) -> Result:
    return CliRunner().invoke(cli, ["diff", str(V1), str(V2), *options])


def _refused(result: Result, *fragments: str) -> None:
    assert result.exit_code == 2, result.output
    assert result.stdout == ""
    assert "Usage:" in result.stderr
    for fragment in fragments:
        assert fragment in result.stderr, result.stderr


# -- Every accepted spelling is accepted, whatever its case --


@pytest.mark.parametrize("name", sorted(CHANGE_TYPE_MAP))
@pytest.mark.parametrize("option", ["--show", "--hide"])
@pytest.mark.parametrize("case", [str.lower, str.upper])
def test_every_change_type_spelling_is_accepted(
    tmp_path: Path, name: str, option: str, case: type[str]
) -> None:
    result = _run(tmp_path, OLD, NEW, option, case(name))
    assert result.exit_code == 1, result.output


@pytest.mark.parametrize("name", sorted(set(ENTITY_TYPE_MAP) | {STRUCTURES}))
@pytest.mark.parametrize("case", [str.lower, str.upper])
def test_every_entity_type_spelling_is_accepted(tmp_path: Path, name: str, case: type[str]) -> None:
    result = _run(tmp_path, OLD, NEW, "--entities", case(name))
    assert result.exit_code == 1, result.output


def test_every_canonical_name_is_a_spelling() -> None:
    assert set(CHANGE_TYPE_NAMES) == set(CHANGE_TYPE_MAP)
    assert set(ENTITY_TYPE_NAMES) <= set(ENTITY_TYPE_MAP) | {STRUCTURES}


def test_whitespace_and_a_trailing_comma_are_accepted(tmp_path: Path) -> None:
    assert _run(tmp_path, OLD, NEW, "--show", " removed ").exit_code == 1
    result = _run(tmp_path, OLD, NEW, "--show", "removed,")
    assert result.exit_code == 1, result.output
    assert "- Class ex:Cat" in result.stdout


# -- What is refused, at 2, before anything is read or written --


@pytest.mark.parametrize(
    ("option", "value", "fragments"),
    [
        ("--show", "addedd", ["'--show'", "'addedd' (did you mean 'added'?)"]),
        ("--hide", "modified,typo", ["'--hide'", "'typo'", "Accepted: added, removed, modified"]),
        ("--entities", "bogus", ["'--entities'", "'bogus'", "Accepted: classes, properties"]),
        (
            "--entities",
            "clases,classes,propertys",
            ["'clases' (did you mean 'classes'?)", "'propertys' (did you mean 'properties'?)"],
        ),
        ("--entities", "objprop", ["did you mean 'object_properties'?"]),
    ],
)
def test_an_unknown_name_is_refused(
    tmp_path: Path, option: str, value: str, fragments: list[str]
) -> None:
    _refused(_run(tmp_path, OLD, NEW, option, value), *fragments)


def test_the_refusal_lists_every_canonical_entity_type(tmp_path: Path) -> None:
    result = _run(tmp_path, OLD, NEW, "--entities", "bogus")
    _refused(result, "Accepted: " + ", ".join(ENTITY_TYPE_NAMES))


@pytest.mark.parametrize("option", ["--show", "--hide", "--entities"])
@pytest.mark.parametrize("value", ["", ",", " ", " , "])
def test_an_empty_value_is_refused(tmp_path: Path, option: str, value: str) -> None:
    _refused(_run(tmp_path, OLD, NEW, option, value), f"'{option}'", "named")


@pytest.mark.parametrize(
    ("show", "hide"),
    [("added", "added"), ("added,removed", "removed"), ("added", "removed")],
)
def test_show_with_hide_is_refused(tmp_path: Path, show: str, hide: str) -> None:
    result = _run(tmp_path, OLD, NEW, "--show", show, "--hide", hide)
    _refused(result, "--show and --hide cannot be used together")


def test_hiding_every_change_type_is_refused(tmp_path: Path) -> None:
    result = _run(tmp_path, OLD, NEW, "--hide", "Modified,added,removed")
    _refused(result, "--hide hides every change type", "nothing would be shown")


def test_overlapping_entity_types_are_a_union(tmp_path: Path) -> None:
    result = _run(tmp_path, OLD, NEW, "--entities", "properties,object_properties")
    assert result.exit_code == 1, result.output


@pytest.mark.parametrize(
    "options",
    [("--show", "addedd"), ("--entities", ""), ("--show", "added", "--hide", "added")],
    ids=["unknown", "empty", "show-and-hide"],
)
def test_a_refused_filter_writes_nothing(tmp_path: Path, options: tuple[str, ...]) -> None:
    out = tmp_path / "out.txt"
    result = _run(tmp_path, OLD, NEW, "-o", str(out), *options)
    assert result.exit_code == 2, result.output
    assert not out.exists()


def test_a_refused_filter_is_refused_before_the_files_are_read(tmp_path: Path) -> None:
    result = _run(tmp_path, "this is not turtle", NEW, "--show", "addedd")
    _refused(result, "'addedd'")


# -- The verdict follows the graphs; the view says what it left out --


@pytest.mark.parametrize("output_format", ["text", "markdown"])
def test_a_filter_that_hides_every_change_says_so(tmp_path: Path, output_format: str) -> None:
    result = _run(tmp_path, OLD, NEW, "--show", "added", "-f", output_format)

    assert result.exit_code == 1, result.output
    assert (
        "No added changes. 1 change not shown (1 removed) — run without --show to see it."
        in result.stdout
    )
    assert NO_DIFFERENCES not in result.stdout
    assert IDENTICAL not in result.stderr


def test_a_valid_filter_matching_nothing_says_what_it_hid(tmp_path: Path) -> None:
    result = _run(tmp_path, OLD, NEW, "--entities", "properties")

    assert result.exit_code == 1, result.output
    assert "No changes to properties. 1 change not shown (1 removed)" in result.stdout
    assert "run without --entities to see it." in result.stdout
    assert IDENTICAL not in result.stderr


def test_both_options_are_named_in_the_hint(tmp_path: Path) -> None:
    result = _run(tmp_path, OLD, NEW, "--show", "added", "--entities", "classes,untyped")

    assert result.exit_code == 1, result.output
    assert (
        "No added changes to classes or untyped terms. 1 change not shown (1 removed) "
        "— run without --show and --entities to see it." in result.stdout
    )


def test_a_filter_on_identical_graphs_is_honestly_identical(tmp_path: Path) -> None:
    result = _run(tmp_path, OLD, OLD, "--show", "added", "--entities", "classes")

    assert result.exit_code == 0, result.output
    assert NO_DIFFERENCES in result.stdout
    assert "Graphs are semantically identical." in result.stderr


def test_a_partial_view_says_what_it_did_not_show() -> None:
    result = _run_examples("--entities", "classes")

    assert result.exit_code == 1, result.output
    assert "~ Class bld:Building" in result.stdout
    assert "BLANK-NODE STRUCTURES" not in result.stdout
    assert "Not shown: 2 blank-node structures (--entities classes)." in result.stdout


def test_a_partial_view_says_so_in_markdown() -> None:
    result = _run_examples("--entities", "classes", "-f", "markdown")

    assert result.exit_code == 1, result.output
    assert "- Not shown: 2 blank-node structures (--entities classes)." in result.stdout
    assert "## Blank-node structures" not in result.stdout


def test_the_view_goes_to_the_output_file(tmp_path: Path) -> None:
    out = tmp_path / "out.md"
    result = _run(tmp_path, OLD, NEW, "--show", "added", "-f", "markdown", "-o", str(out))

    assert result.exit_code == 1, result.output
    assert "No added changes. 1 change not shown (1 removed)" in out.read_text(encoding="utf-8")


# -- The JSON --


def test_the_json_identical_describes_the_graphs(tmp_path: Path) -> None:
    result = _run(tmp_path, OLD, NEW, "--show", "ADDED", "-f", "json")

    assert result.exit_code == 1, result.output
    data = json.loads(result.stdout)
    assert data["identical"] is False
    assert data["summary"] == {"added": 0, "removed": 0, "modified": 0, "structures": 0}
    assert data["filter"] == {
        "show": ["added"],
        "hide": [],
        "entities": [],
        "not_shown": {"added": 0, "removed": 1, "modified": 0, "structures": 0},
    }


def test_the_json_filter_names_are_canonical() -> None:
    result = _run_examples(
        "--hide", "modified", "--entities", "Instances,structures,CLASS", "-f", "json"
    )

    assert result.exit_code == 1, result.output
    data = json.loads(result.stdout)
    assert data["filter"]["hide"] == ["modified"]
    assert data["filter"]["entities"] == ["classes", "individuals", "structures"]
    assert data["filter"]["not_shown"] == {
        "added": 0,
        "removed": 0,
        "modified": 2,
        "structures": 0,
    }
    assert data["summary"]["structures"] == 2


def test_the_json_has_no_filter_key_without_a_filter(tmp_path: Path) -> None:
    result = _run(tmp_path, OLD, NEW, "-f", "json")
    assert "filter" not in json.loads(result.stdout)


# -- Ownerless blank-node structures --


@pytest.mark.parametrize(
    ("options", "added", "removed", "hidden"),
    [
        (("--show", "added"), True, False, 1),
        (("--show", "removed"), False, True, 1),
        (("--show", "modified"), False, False, 2),
        (("--hide", "added"), False, True, 1),
        (("--entities", "classes"), False, False, 2),
        (("--entities", "individuals"), False, False, 2),
        (("--entities", "classes,structures"), True, True, 0),
        (("--entities", "structures"), True, True, 0),
    ],
)
def test_structures_under_each_filter(
    options: tuple[str, ...], added: bool, removed: bool, hidden: int
) -> None:
    result = _run_examples(*options, "-f", "json")

    assert result.exit_code == 1, result.output
    data = json.loads(result.stdout)
    actions = [s["action"] for s in data["structures"]]
    assert ("added" in actions) is added
    assert ("removed" in actions) is removed
    assert data["filter"]["not_shown"]["structures"] == hidden
    assert data["identical"] is False


def test_a_filter_hiding_only_structures_still_differs(tmp_path: Path) -> None:
    old = PREFIXES + "ex:A a owl:Class . ex:B a owl:Class .\n"
    new = old + "[] a owl:AllDisjointClasses ; owl:members ( ex:A ex:B ) .\n"
    result = _run(tmp_path, old, new, "--entities", "classes")

    assert result.exit_code == 1, result.output
    assert "No changes to classes. 1 change not shown (1 blank-node structure)" in result.stdout
    assert IDENTICAL not in result.stderr


def _closed_list(cells: int) -> str:
    """A list as an OWL-RL closure leaves it: every cell owl:sameAs itself, so not a tree."""
    rows = [
        f"_:c{i} rdf:first ex:M{i} ; rdf:rest {f'_:c{i + 1}' if i < cells - 1 else 'rdf:nil'} ; "
        f"owl:sameAs _:c{i} ."
        for i in range(cells)
    ]
    return PREFIXES + "ex:U owl:unionOf _:c0 .\n" + "\n".join(rows)


def test_an_uncompared_structure_is_reported_under_a_filter(tmp_path: Path) -> None:
    text = _closed_list(NON_TREE_LIMIT + 100)
    result = _run(tmp_path, text, text, "--show", "added")

    assert result.exit_code == 1, result.output
    assert result.stdout.splitlines()[2].startswith("Note: A blank-node structure in old.ttl")
    assert NO_DIFFERENCES not in result.stdout
    assert IDENTICAL not in result.stderr


# -- The new entity types --


def test_ontology_and_untyped_select_their_entities(tmp_path: Path) -> None:
    old = PREFIXES + "ex:A a owl:Class .\n"
    new = old + "<http://example.org/ont> a owl:Ontology .\nex:loose rdfs:label 'loose' .\n"

    ontology = _run(tmp_path, old, new, "--entities", "ontology")
    assert ontology.exit_code == 1, ontology.output
    assert "+ Ontology " in ontology.stdout
    assert "ex:loose" not in ontology.stdout
    assert "Not shown: 1 added (--entities ontology)." in ontology.stdout

    untyped = _run(tmp_path, old, new, "--entities", "untyped")
    assert untyped.exit_code == 1, untyped.output
    assert "ex:loose" in untyped.stdout
    assert "Not shown: 1 added (--entities untyped)." in untyped.stdout


# -- --ignore-predicates: identical under the comparison asked for --


def test_identical_says_which_predicates_it_ignored(tmp_path: Path) -> None:
    old = PREFIXES + "ex:A a owl:Class ; rdfs:comment 'one' .\n"
    new = PREFIXES + "ex:A a owl:Class ; rdfs:comment 'two' .\n"
    result = _run(tmp_path, old, new, "--ignore-predicates", "rdfs:comment")

    assert result.exit_code == 0, result.output
    assert "Graphs are semantically identical, ignoring rdfs:comment." in result.stderr


def test_without_ignored_predicates_the_sentence_is_unqualified(tmp_path: Path) -> None:
    result = _run(tmp_path, OLD, OLD)
    assert result.exit_code == 0, result.output
    assert "Graphs are semantically identical.\n" in result.stderr


# -- The library refuses what the CLI refuses --


@pytest.mark.parametrize(
    ("kwargs", "fragment"),
    [
        ({"show_types": {"addedd"}}, "show_types: unknown change type 'addedd'"),
        ({"hide_types": {"typo"}}, "hide_types: unknown change type 'typo'"),
        ({"entity_types": {"bogus"}}, "entity_types: unknown entity type 'bogus'"),
        ({"show_types": set()}, "show_types: no change types named"),
        ({"entity_types": {" "}}, "entity_types: no entity types named"),
        ({"show_types": {"added"}, "hide_types": {"added"}}, "cannot be used together"),
        ({"hide_types": {"added", "removed", "modified"}}, "hides every change type"),
    ],
)
def test_filter_diff_refuses(tmp_path: Path, kwargs: dict[str, set[str]], fragment: str) -> None:
    (tmp_path / "old.ttl").write_text(OLD, encoding="utf-8")
    (tmp_path / "new.ttl").write_text(NEW, encoding="utf-8")
    diff = compare_files(tmp_path / "old.ttl", tmp_path / "new.ttl")

    with pytest.raises(UnknownFilterError, match=fragment):
        filter_diff(diff, **kwargs)


def test_filter_diff_keeps_the_verdict_and_accumulates() -> None:
    whole = compare_files(V1, V2)
    once = filter_diff(whole, show_types={"added"})
    twice = filter_diff(once, entity_types={"classes"})

    assert once.added_structures and not once.removed_structures
    assert not once.is_identical
    assert once.not_shown == {"added": 0, "removed": 0, "modified": 2, "structures": 1}
    assert twice.not_shown == {"added": 0, "removed": 0, "modified": 2, "structures": 2}
    assert not twice.is_identical


def test_filter_diff_without_a_filter_is_the_whole_diff() -> None:
    whole = compare_files(V1, V2)
    same = filter_diff(whole)

    assert same is not whole
    assert same == whole
    assert same.filter is None


def test_the_guides_refusal_is_what_the_command_prints(tmp_path: Path) -> None:
    """`DIFF_GUIDE.md` quotes the refusal of `--show addedd`; it must stay a capture."""
    result = _run(tmp_path, OLD, NEW, "--show", "addedd")
    line = result.stderr.rstrip().splitlines()[-1]

    guide = (ROOT / "docs" / "user_guides" / "DIFF_GUIDE.md").read_text(encoding="utf-8")
    assert f"```text\n{line}\n```" in guide
