"""Tests for the built-in default subject ordering and its completeness guard (#303).

The fixture names every hierarchy so that alphabetical order puts a child before its parent, so
each expected order below is structural: it follows from the hierarchy, not from hash order.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import RDFS, BNode, Graph, Namespace, URIRef
from rdflib.compare import isomorphic

from rdf_construct.core import (
    IncompleteSubjectOrderError,
    check_subject_order_complete,
    default_subject_order,
    serialise_turtle,
    serialise_turtle_str,
)
from tests.determinism import SEEDS, without_coverage

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "default_order" / "default_order.ttl"
EX = Namespace("http://example.org/order#")

#: The named subjects of the fixture, in the order the default sections place them.
EXPECTED_NAMED = [
    # header
    URIRef("http://example.org/order"),
    # classes: roots alphabetically, then each child once its parent is out, then the cycle
    EX.Part,
    EX.Species,
    EX.Vehicle,
    EX.Car,
    EX.Antique,
    EX.Loop1,
    EX.Loop2,
    # object, datatype, annotation and other properties, each parent first
    EX.relatedTo,
    EX.partOf,
    EX.size,
    EX.length,
    EX.note,
    EX.editorialNote,
    EX.identifier,
    EX.code,
    # individuals, then the unclaimed named subject
    EX.herbie,
    EX.myCar,
    EX.untyped,
]

#: Members of the subClassOf cycle, where no order can put every parent first.
CYCLE = {EX.Loop1, EX.Loop2}


@pytest.fixture
def graph() -> Graph:
    return Graph().parse(FIXTURE)


@pytest.fixture
def order(graph: Graph) -> list:
    return default_subject_order(graph)


class TestSections:
    """Which section each subject lands in, and the order inside it."""

    def test_named_subjects_in_section_order(self, order: list) -> None:
        assert [s for s in order if isinstance(s, URIRef)] == EXPECTED_NAMED

    def test_named_subjects_come_before_blank_nodes(self, order: list) -> None:
        kinds = [isinstance(s, BNode) for s in order]
        assert kinds == sorted(kinds)

    def test_every_subject_exactly_once(self, graph: Graph, order: list) -> None:
        assert len(order) == len(set(order))
        assert set(order) == set(graph.subjects())

    def test_puns_are_placed_in_classes(self, order: list) -> None:
        """owl:NamedIndividual and owl:ObjectProperty puns: the first section to claim wins."""
        classes = order[1:8]
        assert EX.Species in classes
        assert EX.Part in classes

    def test_property_of_no_inferable_kind_is_in_other_properties(self, order: list) -> None:
        assert order.index(EX.identifier) < order.index(EX.code) < order.index(EX.herbie)
        assert order.index(EX.editorialNote) < order.index(EX.identifier)

    def test_unclaimed_named_subject_is_emitted_after_individuals(self, order: list) -> None:
        assert order.index(EX.myCar) < order.index(EX.untyped)

    def test_anonymous_class_expression_is_not_claimed_by_classes(
        self, graph: Graph, order: list
    ) -> None:
        """#280: the owl:unionOf wrapper is typed owl:Class but is a blank node."""
        (union,) = graph.subjects(URIRef("http://www.w3.org/2002/07/owl#unionOf"), None)
        assert order.index(union) > order.index(EX.untyped)

    def test_root_blank_nodes_sorted_by_content(self, graph: Graph, order: list) -> None:
        owl = Namespace("http://www.w3.org/2002/07/owl#")
        (different,) = graph.subjects(None, owl.AllDifferent)
        (disjoint,) = graph.subjects(None, owl.AllDisjointClasses)
        assert order.index(different) < order.index(disjoint)


class TestHierarchyPrinciple:
    """#95: superclasses before subclasses, superproperties before subproperties."""

    @pytest.mark.parametrize("edge", [RDFS.subClassOf, RDFS.subPropertyOf])
    def test_every_parent_before_its_children(self, graph: Graph, order: list, edge) -> None:
        position = {s: i for i, s in enumerate(order)}
        pairs = [
            (child, parent)
            for child, parent in graph.subject_objects(edge)
            if isinstance(parent, URIRef) and child != parent and not {child, parent} <= CYCLE
        ]
        assert pairs, "the fixture carries no hierarchy over this edge"
        late = [(c, p) for c, p in pairs if position[p] > position[c]]
        assert late == []

    def test_annotation_hierarchy_is_sorted_over_subproperty_of(self, order: list) -> None:
        """#245: a characteristic-only edge choice sorts this section over rdfs:subClassOf."""
        assert order.index(EX.note) < order.index(EX.editorialNote)

    def test_object_property_pun_keeps_classes_on_subclass_of(self, order: list) -> None:
        """#245, the other way: ex:Part is also an owl:ObjectProperty."""
        assert order.index(EX.Vehicle) < order.index(EX.Car) < order.index(EX.Antique)


class TestGuard:
    """``check_subject_order_complete``: loud on a list that would lose triples."""

    def test_default_order_passes(self, graph: Graph, order: list) -> None:
        check_subject_order_complete(graph, order)

    def test_short_list_fails(self, graph: Graph, order: list) -> None:
        short = [s for s in order if s != EX.untyped]
        with pytest.raises(IncompleteSubjectOrderError, match=r"1 subject.*ex:untyped"):
            check_subject_order_complete(graph, short)

    def test_missing_root_blank_node_fails(self, graph: Graph, order: list) -> None:
        owl = Namespace("http://www.w3.org/2002/07/owl#")
        (root,) = graph.subjects(None, owl.AllDifferent)
        with pytest.raises(IncompleteSubjectOrderError, match="would not be written"):
            check_subject_order_complete(graph, [s for s in order if s != root])

    def test_inline_blank_node_needs_its_referrer(self, graph: Graph, order: list) -> None:
        """A listed inline blank node is skipped at the top level, so it cannot stand alone."""
        with pytest.raises(IncompleteSubjectOrderError, match="ex:Car"):
            check_subject_order_complete(graph, [s for s in order if s != EX.Car])

    def test_duplicate_fails(self, graph: Graph, order: list) -> None:
        with pytest.raises(IncompleteSubjectOrderError, match="more than once"):
            check_subject_order_complete(graph, [*order, EX.Car])

    def test_blank_node_cycle_unreachable_fails_loudly(self) -> None:
        """Two blank nodes referencing only each other are both inline, so neither is written.

        The serialiser drops them silently (#341); the default ordering refuses instead.
        """
        g = Graph()
        a, b = BNode(), BNode()
        g.add((a, EX.next, b))
        g.add((b, EX.next, a))
        with pytest.raises(IncompleteSubjectOrderError):
            default_subject_order(g)


class TestStringForm:
    """``serialise_turtle_str``: the text ``serialise_turtle`` writes."""

    def test_string_and_path_forms_give_the_same_bytes(
        self, graph: Graph, order: list, tmp_path: Path
    ) -> None:
        out = tmp_path / "out.ttl"
        serialise_turtle(graph, order, out)
        assert out.read_bytes() == serialise_turtle_str(graph, order).encode("utf-8")

    @pytest.mark.parametrize(
        "source",
        [FIXTURE, *sorted((REPO / "tests" / "fixtures" / "ies").glob("*.ttl"))],
        ids=lambda p: p.stem,
    )
    def test_round_trip_is_isomorphic(self, source: Path) -> None:
        g = Graph().parse(source)
        text = serialise_turtle_str(g, default_subject_order(g))
        assert isomorphic(Graph().parse(data=text, format="turtle"), g)


def test_same_order_under_every_hash_seed() -> None:
    """One process per seed: set iteration is stable within a process, so only this sees it.

    Blank-node labels are drawn afresh on every parse, so they are masked; what is compared is
    the order and everything written.
    """
    script = (
        "import sys\n"
        "from rdflib import Graph\n"
        "from rdf_construct.core import default_subject_order, serialise_turtle_str\n"
        "g = Graph().parse(sys.argv[1])\n"
        "sys.stdout.write(serialise_turtle_str(g, default_subject_order(g)))\n"
    )
    outputs = set()
    for seed in SEEDS:
        proc = subprocess.run(
            [sys.executable, "-c", script, str(FIXTURE)],
            env={**without_coverage(os.environ), "PYTHONHASHSEED": str(seed)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"seed {seed}:\n{proc.stderr}"
        outputs.add(re.sub(r"_:\w+", "_:b", proc.stdout))
    assert len(outputs) == 1
