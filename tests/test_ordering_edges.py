"""A topological section follows both hierarchies, whatever its members are (#245).

``sort_with_roots`` used to pick ``rdfs:subPropertyOf`` if any subject was typed
``owl:ObjectProperty`` or ``owl:DatatypeProperty``, and ``rdfs:subClassOf`` otherwise. Every
fixture here names its child so that it sorts alphabetically before its parent: a sort over
the wrong predicate, or none, shows as a reversed pair.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import RDFS, Graph, Namespace, URIRef

from rdf_construct.cli import cli
from rdf_construct.core import HIERARCHY_PREDICATES
from rdf_construct.core.ordering import build_adjacency, sort_subjects, topo_sort_subset
from rdf_construct.core.selector import select_subjects

EX = Namespace("http://example.org/edges#")

PREFIXES = """
@prefix ex: <http://example.org/edges#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
"""


def _graph(body: str) -> Graph:
    g = Graph(bind_namespaces="core")
    g.parse(data=PREFIXES + body, format="turtle")
    return g


def _sorted_section(body: str, selector: str, selectors: dict[str, str] | None = None) -> list:
    g = _graph(body)
    chosen = select_subjects(g, selector, selectors or {})
    return sort_subjects(g, set(chosen), "topological")


# The issue's reproducer: the same shape, declared two ways.
EDGE = """
ex:aChild  a owl:ObjectProperty ; rdfs:subPropertyOf ex:zParent .
ex:zParent a owl:ObjectProperty .
"""
EDGE_CHAR = """
ex:aChild  a owl:TransitiveProperty ; rdfs:subPropertyOf ex:zParent .
ex:zParent a owl:TransitiveProperty .
"""


@pytest.mark.parametrize("body", [EDGE, EDGE_CHAR], ids=["declared", "characteristic-only"])
def test_object_property_hierarchy_however_declared(body: str) -> None:
    assert _sorted_section(body, "obj_props") == [EX.zParent, EX.aChild]


def test_a_punned_class_does_not_send_its_section_alphabetical() -> None:
    """The 2026-10-15 comment on #245: one OWL Full pun flipped the whole class section."""
    body = """
    ex:Zeta  a owl:Class, owl:ObjectProperty .
    ex:Alpha a owl:Class ; rdfs:subClassOf ex:Zeta .
    ex:Mu    a owl:Class ; rdfs:subClassOf ex:Zeta .
    """
    assert _sorted_section(body, "classes") == [EX.Zeta, EX.Alpha, EX.Mu]


def test_other_props_sorts_topologically() -> None:
    """No `other_props` member is an owl:ObjectProperty, so the sniff could never pick it."""
    body = """
    ex:aChild  a owl:FunctionalProperty ; rdfs:subPropertyOf ex:zParent .
    ex:zParent a rdf:Property .
    """
    assert _sorted_section(body, "other_props") == [EX.zParent, EX.aChild]


def test_annotation_property_hierarchy() -> None:
    body = """
    ex:aChild  a owl:AnnotationProperty ; rdfs:subPropertyOf ex:zParent .
    ex:zParent a owl:AnnotationProperty .
    """
    assert _sorted_section(body, "ann_props") == [EX.zParent, EX.aChild]


def test_individuals_section_keeps_a_generic_property_hierarchy() -> None:
    """`individuals` sees generic properties; no per-selector edge table would cover it."""
    body = """
    ex:aChild  a owl:FunctionalProperty ; rdfs:subPropertyOf ex:zParent .
    ex:zParent a owl:FunctionalProperty .
    """
    assert _sorted_section(body, "individuals") == [EX.zParent, EX.aChild]


def test_a_pun_linked_to_one_parent_by_both_predicates_counts_one_edge() -> None:
    """Counted twice, the child's indegree would never reach zero: it would sort last."""
    body = """
    ex:zParent a owl:Class, owl:ObjectProperty .
    ex:aChild  a owl:Class, owl:ObjectProperty ;
        rdfs:subClassOf ex:zParent ; rdfs:subPropertyOf ex:zParent .
    ex:bGrandchild a owl:Class ; rdfs:subClassOf ex:aChild .
    """
    g = _graph(body)
    nodes = {EX.zParent, EX.aChild, EX.bGrandchild}
    _, indegree = build_adjacency(g, nodes, HIERARCHY_PREDICATES)
    assert indegree[EX.aChild] == 1
    assert _sorted_section(body, "classes") == [EX.zParent, EX.aChild, EX.bGrandchild]


def test_a_cycle_across_the_two_predicates_is_written_alphabetically() -> None:
    """Pinned: A ⊑ B by one predicate and B ⊑ A by the other is a cycle in the union.

    Its members go to the remainder, alphabetically, after everything that sorted, as any
    other cycle does; what hangs off it follows.
    """
    body = """
    ex:A a owl:Class, owl:ObjectProperty ; rdfs:subClassOf ex:B .
    ex:B a owl:Class, owl:ObjectProperty ; rdfs:subPropertyOf ex:A .
    ex:C a owl:Class ; rdfs:subClassOf ex:A .
    ex:D a owl:Class .
    """
    assert _sorted_section(body, "classes") == [EX.D, EX.A, EX.B, EX.C]


def test_a_single_predicate_is_still_accepted() -> None:
    """`topo_sort_subset` and friends take one predicate, as `default_order` passes it."""
    g = _graph(EDGE)
    nodes = {EX.aChild, EX.zParent}
    assert topo_sort_subset(g, nodes, RDFS.subPropertyOf) == [EX.zParent, EX.aChild]
    assert topo_sort_subset(g, nodes, RDFS.subClassOf) == [EX.aChild, EX.zParent]
    assert topo_sort_subset(g, nodes, URIRef(str(RDFS.subPropertyOf))) == [EX.zParent, EX.aChild]


def test_a_custom_selector_sorts_through_the_cli(tmp_path: Path) -> None:
    """A `selectors:` entry has no built-in key; its section still follows the hierarchy."""
    source = tmp_path / "pun.ttl"
    source.write_text(
        PREFIXES
        + """
        ex:Zeta  a owl:Class, owl:ObjectProperty .
        ex:Alpha a owl:Class ; rdfs:subClassOf ex:Zeta .
        """
    )
    config = tmp_path / "order.yml"
    config.write_text(
        "selectors:\n"
        '  mine: "rdf:type owl:Class"\n'
        "profiles:\n"
        "  p:\n"
        "    unclaimed: ignore\n"
        "    sections:\n"
        "      - things: {select: mine, sort: topological}\n"
    )
    out = tmp_path / "out"

    result = CliRunner().invoke(cli, ["order", str(source), str(config), "-o", str(out)])

    assert result.exit_code == 0, result.output
    text = (out / "pun-p.ttl").read_text()
    assert text.index("ex:Zeta\n") < text.index("ex:Alpha\n"), text
