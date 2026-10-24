"""`diff` compares blank nodes by structure, in both directions (#143).

Before #143, `diff` compared triples by rdflib's parse-time blank-node labels and then skipped
every blank-node subject. So a file containing a restriction differed from a copy of itself
(exit 1), and a change made only inside blank nodes was "semantically identical" (exit 0).

Now both graphs are relabelled by content (`core.blank_nodes.label_by_content`). A structure
that both state drops out of the set difference, and a changed one is attributed to the named
subject it belongs to and written as Turtle, never as a parser's label.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import BNode, Graph, URIRef
from rdflib.compare import isomorphic

import rdf_construct.core.blank_nodes as blank_nodes
import rdf_construct.diff.structures as structures
from rdf_construct.cli import cli
from rdf_construct.core.blank_nodes import blank_node_components, is_tree
from rdf_construct.diff import GraphDiff, compare_graphs, filter_diff, format_diff
from rdf_construct.diff.change_types import UncomparedStructure
from rdf_construct.diff.comparator import NON_TREE_LIMIT

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "examples"
IES = Path(__file__).parent / "fixtures" / "ies"
V1 = EXAMPLES / "diff" / "v1.ttl"
V2 = EXAMPLES / "diff" / "v2.ttl"
GUIDE = ROOT / "docs" / "user_guides" / "DIFF_GUIDE.md"

PREFIXES = """\
@prefix ex: <http://example.org/ont#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
"""

#: A blank-node label that is not one of the renderer's own `_:s1`, `_:s2`, … labels.
PARSER_LABEL = re.compile(r"_:(?!s\d+\b)\w+")

AXIOM = (
    PREFIXES
    + """
ex:Dog a owl:Class ; rdfs:subClassOf ex:Animal .
ex:Animal a owl:Class .

[] a owl:Axiom ;
   owl:annotatedSource ex:Dog ;
   owl:annotatedProperty rdfs:subClassOf ;
   owl:annotatedTarget ex:Animal ;
   rdfs:comment "Every dog is an animal." .
"""
)

RESTRICTION = (
    PREFIXES
    + """
ex:Dog a owl:Class ;
    rdfs:subClassOf [ a owl:Restriction ;
        owl:onProperty ex:hasName ;
        owl:cardinality 1 ] .
"""
)


def _graph(text: str) -> Graph:
    graph = Graph()
    graph.parse(data=text, format="turtle")
    return graph


def _diff(old: str, new: str) -> GraphDiff:
    return compare_graphs(_graph(PREFIXES + old), _graph(PREFIXES + new), "old.ttl", "new.ttl")


def _text(diff: GraphDiff, new: str) -> list[str]:
    """The text formatter's lines below the header."""
    return format_diff(diff, "text", _graph(PREFIXES + new)).splitlines()[2:]


def _run(tmp_path: Path, old: str, new: str, *options: str) -> Result:
    (tmp_path / "old.ttl").write_text(old, encoding="utf-8")
    (tmp_path / "new.ttl").write_text(new, encoding="utf-8")
    return CliRunner().invoke(
        cli, ["diff", str(tmp_path / "old.ttl"), str(tmp_path / "new.ttl"), *options]
    )


# -- #143's reproducers, through the CLI --


class TestReproducers:
    @pytest.mark.parametrize("output_format", ["text", "markdown", "json"])
    def test_a_change_inside_an_axiom_is_reported(self, tmp_path: Path, output_format: str) -> None:
        changed = AXIOM.replace("Every dog is an animal.", "COMPLETELY DIFFERENT TEXT.")
        result = _run(tmp_path, AXIOM, changed, "-f", output_format)

        assert result.exit_code == 1, result.output
        assert "No semantic differences found." not in result.stdout
        assert "semantically identical" not in result.output
        assert '"COMPLETELY DIFFERENT TEXT."' in result.stdout.replace('\\"', '"')
        assert '"Every dog is an animal."' in result.stdout.replace('\\"', '"')
        assert not PARSER_LABEL.search(result.stdout)
        if output_format == "json":
            data = json.loads(result.stdout)
            assert data["identical"] is False
            (dog,) = data["modified"]
            assert dog["uri"] == "http://example.org/ont#Dog"
            assert [s["action"] for s in dog["structures"]] == ["added", "removed"]

    def test_the_axiom_change_is_shown_under_the_subject_it_annotates(self, tmp_path: Path) -> None:
        changed = AXIOM.replace("Every dog is an animal.", "COMPLETELY DIFFERENT TEXT.")
        result = _run(tmp_path, AXIOM, changed)

        assert result.stdout.splitlines()[2:] == [
            "MODIFIED (1 entities):",
            "  ~ Class ex:Dog",
            "    + [ a owl:Axiom ; owl:annotatedProperty rdfs:subClassOf ; "
            "owl:annotatedSource ex:Dog ; owl:annotatedTarget ex:Animal ; "
            'rdfs:comment "COMPLETELY DIFFERENT TEXT." ]',
            "    - [ a owl:Axiom ; owl:annotatedProperty rdfs:subClassOf ; "
            "owl:annotatedSource ex:Dog ; owl:annotatedTarget ex:Animal ; "
            'rdfs:comment "Every dog is an animal." ]',
            "",
            "Summary: 0 added, 0 removed, 1 modified",
        ]

    @pytest.mark.parametrize("output_format", ["text", "markdown", "json"])
    def test_a_file_with_a_restriction_is_identical_to_a_copy_of_itself(
        self, tmp_path: Path, output_format: str
    ) -> None:
        result = _run(tmp_path, RESTRICTION, RESTRICTION, "-f", output_format)

        assert result.exit_code == 0, result.output
        assert "Graphs are semantically identical." in result.output
        if output_format == "json":
            data = json.loads(result.stdout)
            assert data["identical"] is True
            assert data["warnings"] == []
        else:
            assert "No semantic differences found." in result.stdout

    def test_a_changed_cardinality_is_shown_as_a_changed_restriction(self, tmp_path: Path) -> None:
        changed = RESTRICTION.replace("owl:cardinality 1", "owl:cardinality 99")
        result = _run(tmp_path, RESTRICTION, changed)

        assert result.exit_code == 1, result.output
        assert result.stdout.splitlines()[2:] == [
            "MODIFIED (1 entities):",
            "  ~ Class ex:Dog",
            '    + rdfs:subClassOf [ a owl:Restriction ; owl:cardinality "99"^^xsd:integer ; '
            "owl:onProperty ex:hasName ]",
            '    - rdfs:subClassOf [ a owl:Restriction ; owl:cardinality "1"^^xsd:integer ; '
            "owl:onProperty ex:hasName ]",
            "",
            "Summary: 0 added, 0 removed, 1 modified",
        ]


# -- Every shipped file with a blank node is identical to itself --


def _files_with_blank_nodes() -> list[Path]:
    files = []
    for path in sorted([*EXAMPLES.rglob("*.ttl"), *IES.glob("*.ttl")]):
        graph = Graph()
        graph.parse(path, format="turtle")
        if any(isinstance(s, BNode) or isinstance(o, BNode) for s, _, o in graph):
            files.append(path)
    return files


FILES_WITH_BLANK_NODES = _files_with_blank_nodes()


def test_the_corpus_has_blank_nodes_to_compare() -> None:
    """The self-diff below is only a guard while these files carry blank nodes."""
    names = {path.name for path in FILES_WITH_BLANK_NODES}
    assert {"ies-env-building.ttl", "ies-env-building-classification.ttl", "v1.ttl"} <= names


@pytest.mark.parametrize(
    "path",
    FILES_WITH_BLANK_NODES,
    ids=[p.relative_to(ROOT).as_posix() for p in FILES_WITH_BLANK_NODES],
)
def test_a_shipped_file_is_identical_to_itself(path: Path) -> None:
    result = CliRunner().invoke(cli, ["diff", str(path), str(path)])

    assert result.exit_code == 0, result.output
    assert "No semantic differences found." in result.stdout


# -- What each shape of structure is reported as --

R = "[ a owl:Restriction ; owl:onProperty ex:p ; owl:someValuesFrom ex:A ]"

SHAPES = {
    "shared": (
        'ex:A ex:p [ ex:q _:s ] . ex:B ex:p [ ex:q _:s ] . _:s rdfs:label "shared" .',
        'ex:A ex:p [ ex:q _:s ] . ex:B ex:p [ ex:q _:s ] . _:s rdfs:label "S" .',
        [
            "MODIFIED (2 entities):",
            "  ~ Entity ex:A",
            '    + ex:A ex:p [ ex:q _:s1 ] . ex:B ex:p [ ex:q _:s1 ] . _:s1 rdfs:label "S" .',
            '    - ex:A ex:p [ ex:q _:s1 ] . ex:B ex:p [ ex:q _:s1 ] . _:s1 rdfs:label "shared" .',
            "  ~ Entity ex:B",
            '    + ex:A ex:p [ ex:q _:s1 ] . ex:B ex:p [ ex:q _:s1 ] . _:s1 rdfs:label "S" .',
            '    - ex:A ex:p [ ex:q _:s1 ] . ex:B ex:p [ ex:q _:s1 ] . _:s1 rdfs:label "shared" .',
            "",
            "Summary: 0 added, 0 removed, 2 modified",
        ],
    ),
    "cycle": (
        'ex:A ex:links _:a . _:a ex:next _:b ; rdfs:label "a" . _:b ex:next _:a .',
        'ex:A ex:links _:a . _:a ex:next _:b ; rdfs:label "A" . _:b ex:next _:a .',
        [
            "MODIFIED (1 entities):",
            "  ~ Entity ex:A",
            '    + ex:A ex:links _:s1 . _:s1 ex:next [ ex:next _:s1 ] ; rdfs:label "A" .',
            '    - ex:A ex:links _:s1 . _:s1 ex:next [ ex:next _:s1 ] ; rdfs:label "a" .',
            "",
            "Summary: 0 added, 0 removed, 1 modified",
        ],
    ),
    "cycle that nothing refers to": (
        '_:a ex:next _:b . _:b ex:next _:a ; rdfs:label "b" .',
        '_:a ex:next _:b . _:b ex:next _:a ; rdfs:label "B" .',
        [
            "BLANK-NODE STRUCTURES (1 added, 1 removed):",
            '  + _:s1 ex:next [ ex:next _:s1 ; rdfs:label "B" ] .',
            '  - _:s1 ex:next [ ex:next _:s1 ; rdfs:label "b" ] .',
            "",
            "Summary: 0 added, 0 removed, 0 modified; blank-node structures: 1 added, 1 removed",
        ],
    ),
    "list": (
        "ex:Pet owl:equivalentClass [ a owl:Class ; owl:unionOf ( ex:Dog ex:Cat ) ] .",
        "ex:Pet owl:equivalentClass [ a owl:Class ; owl:unionOf ( ex:Dog ex:Cat ex:Fish ) ] .",
        [
            "MODIFIED (1 entities):",
            "  ~ Entity ex:Pet",
            "    + owl:equivalentClass [ a owl:Class ; owl:unionOf ( ex:Dog ex:Cat ex:Fish ) ]",
            "    - owl:equivalentClass [ a owl:Class ; owl:unionOf ( ex:Dog ex:Cat ) ]",
            "",
            "Summary: 0 added, 0 removed, 1 modified",
        ],
    ),
    "list that is not well formed": (
        "ex:U ex:p _:c0 . _:c0 rdf:first ex:A ; rdf:rest _:c1 . "
        "_:c1 rdf:first ex:B ; rdf:rest _:c2 ; a rdf:List . _:c2 rdf:first ex:C ; rdf:rest rdf:nil .",
        "ex:U ex:p ( ex:A ex:B ) .",
        [
            "MODIFIED (1 entities):",
            "  ~ Entity ex:U",
            "    + ex:p ( ex:A ex:B )",
            "    - ex:p [ rdf:first ex:A ; rdf:rest [ a rdf:List ; rdf:first ex:B ; "
            "rdf:rest ( ex:C ) ] ]",
            "",
            "Summary: 0 added, 0 removed, 1 modified",
        ],
    ),
    "all disjoint classes": (
        "[] a owl:AllDisjointClasses ; owl:members ( ex:A ex:B ) .",
        "[] a owl:AllDisjointClasses ; owl:members ( ex:A ex:B ex:C ) .",
        [
            "BLANK-NODE STRUCTURES (1 added, 1 removed):",
            "  + [ a owl:AllDisjointClasses ; owl:members ( ex:A ex:B ex:C ) ]",
            "  - [ a owl:AllDisjointClasses ; owl:members ( ex:A ex:B ) ]",
            "",
            "Summary: 0 added, 0 removed, 0 modified; blank-node structures: 1 added, 1 removed",
        ],
    ),
    "reified statement": (
        '[] a rdf:Statement ; rdf:subject ex:A ; rdf:predicate ex:p ; rdf:object ex:B ; rdfs:comment "x" .',
        '[] a rdf:Statement ; rdf:subject ex:A ; rdf:predicate ex:p ; rdf:object ex:B ; rdfs:comment "y" .',
        [
            "MODIFIED (1 entities):",
            "  ~ Entity ex:A",
            "    + [ a rdf:Statement ; rdf:object ex:B ; rdf:predicate ex:p ; rdf:subject ex:A ; "
            'rdfs:comment "y" ]',
            "    - [ a rdf:Statement ; rdf:object ex:B ; rdf:predicate ex:p ; rdf:subject ex:A ; "
            'rdfs:comment "x" ]',
            "",
            "Summary: 0 added, 0 removed, 1 modified",
        ],
    ),
    "negative property assertion": (
        "[] a owl:NegativePropertyAssertion ; owl:sourceIndividual ex:i ; "
        "owl:assertionProperty ex:p ; owl:targetIndividual ex:j .",
        "",
        [
            "MODIFIED (1 entities):",
            "  ~ Entity ex:i",
            "    - [ a owl:NegativePropertyAssertion ; owl:assertionProperty ex:p ; "
            "owl:sourceIndividual ex:i ; owl:targetIndividual ex:j ]",
            "",
            "Summary: 0 added, 0 removed, 1 modified",
        ],
    ),
    "blank node as an object only": (
        "ex:A ex:knows [] .",
        "ex:A ex:knows [] , [] .",
        [
            "MODIFIED (1 entities):",
            "  ~ Entity ex:A",
            "    + ex:knows []",
            "",
            "Summary: 0 added, 0 removed, 1 modified",
        ],
    ),
    "one of a duplicated pair removed": (
        f"ex:Dog rdfs:subClassOf {R} , {R} .",
        f"ex:Dog rdfs:subClassOf {R} .",
        [
            "MODIFIED (1 entities):",
            "  ~ Entity ex:Dog",
            "    - rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:p ; "
            "owl:someValuesFrom ex:A ]",
            "",
            "Summary: 0 added, 0 removed, 1 modified",
        ],
    ),
    "two objects for one predicate (#343's shape)": (
        "[] a owl:Axiom ; owl:annotatedSource ex:D ; owl:annotatedProperty rdfs:label ; "
        'owl:annotatedTarget "d" ; rdfs:comment "one" , "two" .',
        "",
        [
            "MODIFIED (1 entities):",
            "  ~ Entity ex:D",
            "    - [ a owl:Axiom ; owl:annotatedProperty rdfs:label ; owl:annotatedSource ex:D ; "
            'owl:annotatedTarget "d" ; rdfs:comment "one" , "two" ]',
            "",
            "Summary: 0 added, 0 removed, 1 modified",
        ],
    ),
    "blank node that is owl:sameAs itself": (
        "ex:Dog rdfs:subClassOf _:r . _:r a owl:Restriction ; owl:onProperty ex:p ; "
        "owl:someValuesFrom ex:A ; owl:sameAs _:r .",
        "ex:Dog rdfs:subClassOf _:r . _:r a owl:Restriction ; owl:onProperty ex:p ; "
        "owl:someValuesFrom ex:B ; owl:sameAs _:r .",
        [
            "MODIFIED (1 entities):",
            "  ~ Entity ex:Dog",
            "    + ex:Dog rdfs:subClassOf _:s1 . _:s1 a owl:Restriction ; owl:onProperty ex:p ; "
            "owl:sameAs _:s1 ; owl:someValuesFrom ex:B .",
            "    - ex:Dog rdfs:subClassOf _:s1 . _:s1 a owl:Restriction ; owl:onProperty ex:p ; "
            "owl:sameAs _:s1 ; owl:someValuesFrom ex:A .",
            "",
            "Summary: 0 added, 0 removed, 1 modified",
        ],
    ),
}


@pytest.mark.parametrize("name", SHAPES)
def test_a_shape_is_reported_as_turtle(name: str) -> None:
    old, new, expected = SHAPES[name]
    diff = _diff(old, new)

    assert not diff.is_identical
    assert _text(diff, new) == expected


@pytest.mark.parametrize("name", SHAPES)
def test_a_shape_is_identical_to_itself(name: str) -> None:
    old, new, _ = SHAPES[name]
    assert _diff(old, old).is_identical
    assert _diff(new, new).is_identical


def _rendered(diff: GraphDiff, added: bool) -> str:
    """Rebuild one side's changed blank-node structures as a Turtle document from the diff."""
    statements: set[str] = set()
    for entity in diff.added + diff.removed + diff.modified:
        changes = entity.added_triples if added else entity.removed_triples
        for change in changes:
            if change.turtle is not None:
                statements.add(f"<{entity.uri}> <{change.predicate}> {change.turtle} .")
        statements.update(entity.added_structures if added else entity.removed_structures)
    statements.update(diff.added_structures if added else diff.removed_structures)
    body = "\n".join(s if s.endswith(" .") else f"{s} ." for s in sorted(statements))
    return PREFIXES + "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n" + body


def _blank_part(graph: Graph) -> Graph:
    part = Graph()
    for s, p, o in graph:
        if isinstance(s, BNode) or isinstance(o, BNode):
            part.add((s, p, o))
    return part


#: Shapes where one structure is common to both sides, so a side's changes are not all of it.
COMMON_TO_BOTH = {"one of a duplicated pair removed", "blank node as an object only"}


@pytest.mark.parametrize("name", [n for n in SHAPES if n not in COMMON_TO_BOTH])
@pytest.mark.parametrize("side", ["old", "new"])
def test_what_is_written_is_the_structure_itself(name: str, side: str) -> None:
    """Read back, the Turtle a diff writes is isomorphic to the blank-node part of that side.

    In every shape here, no structure is common to both sides, so each side's changed structures
    are all of its blank-node triples. A renderer that drops a triple, merges two nodes or
    splits a shared one fails this.
    """
    old, new, _ = SHAPES[name]
    text = old if side == "old" else new
    diff = _diff(old, new)

    rebuilt = _graph(_rendered(diff, added=side == "new"))

    assert isomorphic(rebuilt, _blank_part(_graph(PREFIXES + text)))


# -- Too large to compare: the fallback --


def _closed_list(cells: int, extra: str = "") -> str:
    """A list as an OWL-RL closure leaves it: every cell owl:sameAs itself, so not a tree."""
    rows = [
        f"_:c{i} rdf:first ex:M{i} ; rdf:rest {f'_:c{i + 1}' if i < cells - 1 else 'rdf:nil'} ; "
        f"owl:sameAs _:c{i} ."
        for i in range(cells)
    ]
    return PREFIXES + "ex:U owl:unionOf _:c0 .\n" + extra + "\n".join(rows)


CLOSED = NON_TREE_LIMIT + 100


class TestTooLargeToCompare:
    def test_a_file_with_one_is_never_identical_to_itself(self, tmp_path: Path) -> None:
        text = _closed_list(CLOSED)
        result = _run(tmp_path, text, text)

        assert result.exit_code == 1, result.output
        assert "No semantic differences found." not in result.stdout
        assert "semantically identical" not in result.output
        assert result.stdout.splitlines()[2:] == [
            f"Note: A blank-node structure in old.ttl was not compared: it is not a tree, and it "
            f"has {CLOSED:,} blank nodes, over the limit of {NON_TREE_LIMIT:,}, under ex:U "
            "owl:unionOf. Its changes, if any, are not shown. Each of its blank nodes is "
            "owl:sameAs itself, which an OWL-RL closure adds; diff the asserted files instead.",
            f"Note: A blank-node structure in new.ttl was not compared: it is not a tree, and it "
            f"has {CLOSED:,} blank nodes, over the limit of {NON_TREE_LIMIT:,}, under ex:U "
            "owl:unionOf. Its changes, if any, are not shown. Each of its blank nodes is "
            "owl:sameAs itself, which an OWL-RL closure adds; diff the asserted files instead.",
            "",
            "Summary: 0 added, 0 removed, 0 modified",
        ]

    def test_the_rest_of_the_file_is_still_compared(self, tmp_path: Path) -> None:
        old = _closed_list(CLOSED, "ex:Dog ex:p [ ex:q 1 ] .\n")
        new = _closed_list(CLOSED, "ex:Dog ex:p [ ex:q 2 ] .\n")
        result = _run(tmp_path, old, new, "-f", "json")

        assert result.exit_code == 1, result.output
        data = json.loads(result.stdout)
        assert data["identical"] is False
        assert len(data["warnings"]) == 2
        assert all("was not compared" in warning for warning in data["warnings"])
        (dog,) = data["modified"]
        assert [c["object"]["turtle"] for c in dog["changes"]] == [
            '[ ex:q "2"^^xsd:integer ]',
            '[ ex:q "1"^^xsd:integer ]',
        ]

    def test_the_hint_is_given_only_for_owl_sameas_self_links(self, tmp_path: Path) -> None:
        """A large structure that is not a tree for another reason gets no OWL-RL hint."""
        rows = [f"_:c{i} rdf:first _:shared ; rdf:rest _:c{i + 1} ." for i in range(CLOSED)]
        text = (
            PREFIXES + "ex:U owl:unionOf _:c0 .\n" + "\n".join(rows) + f"\n_:c{CLOSED} a ex:End ."
        )
        result = _run(tmp_path, text, text)

        assert result.exit_code == 1, result.output
        assert "was not compared" in result.stdout
        assert "OWL-RL" not in result.stdout

    def test_a_large_tree_is_compared(self, tmp_path: Path) -> None:
        """The limit is for structures that are not trees; a tree of any size is hashed."""
        rows = [
            f"_:c{i} rdf:first ex:M{i} ; rdf:rest {f'_:c{i + 1}' if i < CLOSED - 1 else 'rdf:nil'} ."
            for i in range(CLOSED)
        ]
        text = PREFIXES + "ex:U owl:unionOf _:c0 .\n" + "\n".join(rows)
        result = _run(tmp_path, text, text)

        assert result.exit_code == 0, result.output
        assert "was not compared" not in result.stdout

    @pytest.mark.parametrize("output_format", ["text", "markdown"])
    def test_the_note_comes_before_any_verdict(
        self, monkeypatch: pytest.MonkeyPatch, output_format: str
    ) -> None:
        """Even a diff whose verdict claims identity says first what it could not compare."""
        diff = GraphDiff(
            old_path="old.ttl",
            new_path="new.ttl",
            uncompared=[UncomparedStructure("old.ttl", 600, NON_TREE_LIMIT, "ex:U owl:unionOf")],
            blank_node_warning=True,
        )
        monkeypatch.setattr(GraphDiff, "is_identical", property(lambda self: True))

        lines = format_diff(diff, output_format).splitlines()

        assert "was not compared" in lines[2]

    def test_a_warning_alone_is_never_identical(self) -> None:
        diff = GraphDiff(old_path="old.ttl", new_path="new.ttl", blank_node_warning=True)

        assert not diff.is_identical
        assert diff.notes == ["There are blank-node changes that could not be described."]
        assert "could not be described" in format_diff(diff, "text").splitlines()[2]


# -- The rest of the command keeps working with structures --


def test_an_ignored_predicate_inside_a_structure_is_ignored(tmp_path: Path) -> None:
    changed = AXIOM.replace("Every dog is an animal.", "COMPLETELY DIFFERENT TEXT.")
    result = _run(tmp_path, AXIOM, changed, "--ignore-predicates", "rdfs:comment")

    assert result.exit_code == 0, result.output
    assert "No semantic differences found." in result.stdout

    # Ignoring the comment does not hide a change elsewhere in the same structure
    retargeted = changed.replace("owl:annotatedTarget ex:Animal", "owl:annotatedTarget ex:Pet")
    result = _run(tmp_path, AXIOM, retargeted, "--ignore-predicates", "rdfs:comment")

    assert result.exit_code == 1, result.output
    assert "owl:annotatedTarget ex:Pet ]" in result.stdout
    assert "rdfs:comment" not in result.stdout


def test_a_filter_keeps_structures_that_belong_to_no_entity() -> None:
    """Filters select entities; a structure with no owner is not hidden as a side effect."""
    old, new, _ = SHAPES["all disjoint classes"]
    diff = filter_diff(_diff(old, new), show_types={"modified"})

    assert diff.added_structures and diff.removed_structures
    assert not diff.is_identical


def test_is_tree() -> None:
    def component(text: str) -> Graph:
        (only,) = blank_node_components(_graph(PREFIXES + text))
        return only

    assert is_tree(component(f"ex:Dog rdfs:subClassOf {R} ."))
    assert is_tree(component("ex:U owl:unionOf ( ex:A ex:B ) ."))
    assert not is_tree(component(SHAPES["shared"][0]))
    assert not is_tree(component(SHAPES["cycle"][0]))
    assert not is_tree(component(SHAPES["blank node that is owl:sameAs itself"][0]))


# -- The cost is linear, by count, not by the clock --


def _restrictions(n: int, value: int) -> Graph:
    return _graph(
        PREFIXES
        + "\n".join(
            f"ex:C{i} rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:p ; "
            f"owl:minCardinality {value} ] ."
            for i in range(n)
        )
    )


def _malformed_chain(n: int, member: str) -> Graph:
    """A chain of list cells that is not a well-formed list, because its last cell has a type.

    Only the end is wrong, so a renderer that does not remember why a chain failed re-walks it
    from every cell.
    """
    rows = [
        f"_:c{i} rdf:first ex:{member}{i} ; "
        f"rdf:rest {f'_:c{i + 1}' if i < n - 1 else 'rdf:nil ; a rdf:List'} ."
        for i in range(n)
    ]
    return _graph(PREFIXES + "ex:U ex:p _:c0 .\n" + "\n".join(rows))


def _counts(monkeypatch: pytest.MonkeyPatch, old: Graph, new: Graph) -> tuple[int, int, int]:
    """Count the hashing, rendering and canonicalising work a comparison does."""
    calls = {"sha": 0, "pairs": 0, "canonical": 0}

    def counted(name: str, function):  # type: ignore[no-untyped-def]
        def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
            calls[name] += 1
            return function(*args, **kwargs)

        return wrapper

    monkeypatch.setattr(blank_nodes, "_sha256", counted("sha", blank_nodes._sha256))
    monkeypatch.setattr(
        blank_nodes, "to_canonical_graph", counted("canonical", blank_nodes.to_canonical_graph)
    )
    monkeypatch.setattr(structures._Renderer, "pairs", counted("pairs", structures._Renderer.pairs))
    diff = compare_graphs(old, new)
    assert not diff.is_identical
    monkeypatch.undo()
    return calls["sha"], calls["pairs"], calls["canonical"]


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda n: (_restrictions(n, 1), _restrictions(n, 2)), id="restrictions"),
        pytest.param(
            lambda n: (_malformed_chain(n, "A"), _malformed_chain(n, "B")), id="malformed-chain"
        ),
    ],
)
def test_the_cost_grows_linearly(monkeypatch: pytest.MonkeyPatch, build) -> None:  # type: ignore[no-untyped-def]
    """Every structure changed: the work at 3n minus 2n equals the work at 2n minus n.

    A count, not a wall-clock time. A quadratic path, such as rendering a chain that is not a
    list by re-walking it from every cell, breaks the equality; so does canonicalising a tree.
    """
    # Above the limit at every size, so the scan for structures too large to compare runs at each
    n = NON_TREE_LIMIT + 1
    counts = [_counts(monkeypatch, *build(k * n)) for k in (1, 2, 3)]
    assert counts[0][0] > 0 and counts[0][1] > 0, "the counters must see the work they count"

    for column in range(2):
        first, second, third = (c[column] for c in counts)
        assert third - second == second - first, counts
    assert all(c[2] == 0 for c in counts), "a tree must never reach rdflib.compare"


# -- The examples and the guide --


def test_the_example_pair_differs_only_inside_blank_nodes() -> None:
    """examples/diff/ exists for this shape: every named triple is the same in both files."""

    def named(path: Path) -> set[tuple[URIRef, URIRef, object]]:
        graph = Graph()
        graph.parse(path)
        return {t for t in graph if not any(isinstance(term, BNode) for term in t)}

    assert named(V1) == named(V2)


class TestDiffGuideExamples:
    """`DIFF_GUIDE.md`'s blank-node section is a capture of these runs, and must stay one."""

    def test_the_guides_output_is_what_the_command_prints(self) -> None:
        argv = ["diff", "examples/diff/v1.ttl", "examples/diff/v2.ttl"]
        command = "rdf-construct " + " ".join(argv)
        guide = GUIDE.read_text(encoding="utf-8")
        assert f"```bash\n{command}\n```" in guide, f"the guide no longer shows `{command}`"

        result = CliRunner().invoke(
            cli, [str(ROOT / a) if a.startswith("examples/") else a for a in argv]
        )

        assert result.exit_code == 1, result.output
        block = f"```bash\n{command}\n```\n\n```text\n{result.stdout.rstrip()}\n```"
        assert block in guide, f"the guide's output for `{command}` is not what it prints"

    def test_the_guides_note_is_what_the_command_prints(self, tmp_path: Path) -> None:
        """The note the guide quotes, from a 5,000-cell list as an OWL-RL closure leaves it."""
        text = _closed_list(5000)
        result = _run(tmp_path, text, text)

        note = result.stdout.splitlines()[2]
        assert note.startswith("Note: A blank-node structure in old.ttl was not compared")
        assert f"```text\n{note}\n```" in GUIDE.read_text(encoding="utf-8")
