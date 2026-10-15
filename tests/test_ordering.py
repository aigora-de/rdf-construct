"""Tests for ordering functionality."""

import random
from pathlib import Path
from unittest import mock

import pytest
from rdflib import BNode, Graph, URIRef, RDF, RDFS
from rdflib.namespace import OWL

from rdf_construct.core import OrderingConfig
from rdf_construct.core.ordering import (
    build_adjacency,
    descendants_of,
    sort_subjects,
    topo_sort_subset,
)
from rdf_construct.core.selector import select_subjects
from rdf_construct.core.utils import qname_sort_key
from rdf_construct.core.vocab import ALL_PROPERTY_TYPES, CLASS_TYPES

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def simple_graph():
    """Create a simple test graph with class hierarchy."""
    g = Graph()

    # Bind prefixes
    ex = "http://example.org/test#"
    g.bind("ex", ex)

    # Create simple hierarchy: A <- B <- C
    A = URIRef(ex + "A")
    B = URIRef(ex + "B")
    C = URIRef(ex + "C")

    g.add((A, RDFS.subClassOf, OWL.Thing))
    g.add((B, RDFS.subClassOf, A))
    g.add((C, RDFS.subClassOf, B))

    return g, {A, B, C}


def test_build_adjacency(simple_graph):
    """Test adjacency list construction."""
    g, nodes = simple_graph
    adj, indeg = build_adjacency(g, nodes, RDFS.subClassOf)

    # Check structure: A should have B as child, B should have C
    A = URIRef("http://example.org/test#A")
    B = URIRef("http://example.org/test#B")
    C = URIRef("http://example.org/test#C")

    assert B in adj[A]
    assert C in adj[B]
    assert indeg[A] == 0  # A has no parents in the set
    assert indeg[B] == 1  # B has A as parent
    assert indeg[C] == 1  # C has B as parent


def test_topo_sort_subset(simple_graph):
    """Test topological sorting preserves hierarchy."""
    g, nodes = simple_graph
    sorted_nodes = topo_sort_subset(g, nodes, RDFS.subClassOf)

    A = URIRef("http://example.org/test#A")
    B = URIRef("http://example.org/test#B")
    C = URIRef("http://example.org/test#C")

    # Parents should come before children
    idx_a = sorted_nodes.index(A)
    idx_b = sorted_nodes.index(B)
    idx_c = sorted_nodes.index(C)

    assert idx_a < idx_b < idx_c


def test_descendants_of(simple_graph):
    """Test finding descendants of a root node."""
    g, nodes = simple_graph

    A = URIRef("http://example.org/test#A")
    B = URIRef("http://example.org/test#B")
    C = URIRef("http://example.org/test#C")

    # Descendants of A should include A, B, and C
    desc = descendants_of(g, A, nodes, RDFS.subClassOf)
    assert A in desc
    assert B in desc
    assert C in desc

    # Descendants of B should include B and C
    desc_b = descendants_of(g, B, nodes, RDFS.subClassOf)
    assert B in desc_b
    assert C in desc_b
    assert A not in desc_b


def test_sort_subjects_alpha(simple_graph):
    """Test alphabetical sorting mode."""
    g, nodes = simple_graph
    sorted_nodes = sort_subjects(g, nodes, "alpha")

    # Should be alphabetically ordered by QName
    qnames = [g.namespace_manager.normalizeUri(n) for n in sorted_nodes]
    assert qnames == sorted(qnames)


def test_sort_subjects_topological(simple_graph):
    """Test topological sorting mode."""
    g, nodes = simple_graph
    sorted_nodes = sort_subjects(g, nodes, "topological")

    A = URIRef("http://example.org/test#A")
    B = URIRef("http://example.org/test#B")
    C = URIRef("http://example.org/test#C")

    # Parents before children
    idx_a = sorted_nodes.index(A)
    idx_b = sorted_nodes.index(B)
    idx_c = sorted_nodes.index(C)

    assert idx_a < idx_b < idx_c


# ---------------------------------------------------------------------------
# #300: topo_sort_subset at O(n log n), with byte-identical output
# ---------------------------------------------------------------------------


def _reference_topo_sort(graph: Graph, nodes: set, edge_predicate: URIRef) -> list:
    """The quadratic implementation #300 replaced, kept verbatim as the oracle.

    The fix promises the same order, not just a valid one, so the tests compare
    against this rather than only checking parents precede children.
    """
    if not nodes:
        return []

    adj, indeg = build_adjacency(graph, nodes, edge_predicate)

    # Start with nodes that have no incoming edges
    zero = [n for n, d in indeg.items() if d == 0]
    zero.sort(key=lambda t: qname_sort_key(graph, t))

    out: list = []

    while zero:
        u = zero.pop(0)
        out.append(u)

        # Process children in alphabetical order
        for v in sorted(adj[u], key=lambda t: qname_sort_key(graph, t)):
            indeg[v] -= 1
            if indeg[v] == 0:
                zero.append(v)
                zero.sort(key=lambda t: qname_sort_key(graph, t))

    # Handle any remaining nodes (cycles or disconnected components)
    if len(out) < len(nodes):
        remaining = [n for n in nodes if n not in out]
        remaining.sort(key=lambda t: qname_sort_key(graph, t))
        out.extend(remaining)

    return out


def _assert_same_as_reference(
    graph: Graph, subjects: set, sort_mode: str, roots: list[str] | None = None
) -> None:
    """sort_subjects must give the same list with the new sort as with the old."""
    new = sort_subjects(graph, set(subjects), sort_mode, roots)
    with mock.patch("rdf_construct.core.ordering.topo_sort_subset", _reference_topo_sort):
        old = sort_subjects(graph, set(subjects), sort_mode, roots)
    assert new == old


def _generated_hierarchy(
    n: int, *, max_parents: int, cycles: int, components: int, seed: int, self_loops: int = 0
) -> tuple[Graph, set]:
    """A seeded random class hierarchy over n classes.

    Each class picks up to ``max_parents`` parents among earlier classes of its
    own component (some pick none, so there are several roots); ``cycles`` extra
    subClassOf edges are then added at random, which close cycles. ``self_loops``
    classes get ``C rdfs:subClassOf C``, as RDFS entailment (rdfs10) materialises.
    """
    rng = random.Random(seed)
    g = Graph()
    g.bind("ex", "http://example.org/gen#")
    classes = [URIRef(f"http://example.org/gen#C{rng.randrange(10**9)}_{i}") for i in range(n)]
    for i, c in enumerate(classes):
        g.add((c, RDF.type, OWL.Class))
        earlier = classes[i % components : i : components]
        if earlier and rng.random() > 0.05:
            for parent in rng.sample(earlier, min(len(earlier), rng.randint(1, max_parents))):
                g.add((c, RDFS.subClassOf, parent))
    for _ in range(cycles):
        a, b = rng.sample(classes, 2)
        g.add((a, RDFS.subClassOf, b))
    for c in rng.sample(classes, self_loops):
        g.add((c, RDFS.subClassOf, c))
    return g, set(classes)


@pytest.mark.parametrize(
    "max_parents,cycles,components,self_loops",
    [(1, 0, 1, 0), (3, 0, 1, 0), (3, 25, 1, 0), (1, 0, 4, 0), (3, 0, 1, 20), (3, 25, 4, 20)],
    ids=["single-parent", "multi-parent", "cycles", "components", "self-loops", "all"],
)
def test_topo_sort_matches_reference_on_generated_hierarchies(
    max_parents, cycles, components, self_loops
):
    """Two thousand classes: same order as the old implementation (#300)."""
    g, nodes = _generated_hierarchy(
        2000,
        max_parents=max_parents,
        cycles=cycles,
        components=components,
        seed=300,
        self_loops=self_loops,
    )
    assert topo_sort_subset(g, nodes, RDFS.subClassOf) == _reference_topo_sort(
        g, nodes, RDFS.subClassOf
    )


def test_topo_sort_matches_reference_with_roots():
    """sort_with_roots calls the sort once per root branch and once for the tail."""
    g, nodes = _generated_hierarchy(2000, max_parents=2, cycles=10, components=3, seed=301)
    roots = sorted(qname_sort_key(g, n) for n in nodes)[::250]
    _assert_same_as_reference(g, nodes, "topological_then_alpha", roots)


IES_FIXTURES = sorted((REPO / "tests" / "fixtures" / "ies").glob("*.ttl"))


@pytest.mark.parametrize("fixture", IES_FIXTURES, ids=lambda p: p.stem)
@pytest.mark.parametrize(
    "types,edge",
    [(CLASS_TYPES, RDFS.subClassOf), (ALL_PROPERTY_TYPES, RDFS.subPropertyOf)],
    ids=["classes", "properties"],
)
def test_topo_sort_matches_reference_on_ies(fixture, types, edge):
    """The pinned IES fixtures sort exactly as before (#300)."""
    g = Graph()
    g.parse(fixture, format="turtle")
    nodes = {s for t in types for s in g.subjects(RDF.type, t)}
    assert topo_sort_subset(g, nodes, edge) == _reference_topo_sort(g, nodes, edge)


IES_SOURCES = [str(p.relative_to(REPO)) for p in IES_FIXTURES]
EXAMPLE_PAIRS = [
    ("examples/order/ordering.yml", "examples/order/library.ttl"),
    ("examples/order/test_profile.yml", "examples/animal_ontology.ttl"),
    ("examples/order/test_profile.yml", "examples/organisation_ontology.ttl"),
    *[("examples/order/ies_profile.yml", src) for src in IES_SOURCES],
    *[("examples/order/sample_profile.yml", src) for src in IES_SOURCES],
]


@pytest.mark.parametrize("config,source", EXAMPLE_PAIRS)
def test_topo_sort_matches_reference_on_example_profiles(config, source):
    """Every topological section of every shipped order profile, roots included."""
    ordering_config = OrderingConfig(REPO / config)
    g = Graph()
    g.parse(REPO / source, format="turtle")
    checked = 0
    for prof_name in ordering_config.list_profiles():
        for sec in ordering_config.get_profile(prof_name).sections:
            if not isinstance(sec, dict) or not sec:
                continue
            sec_name, sec_cfg = next(iter(sec.items()))
            sec_cfg = sec_cfg or {}
            if sec_name == "header" or not str(sec_cfg.get("sort", "")).startswith("topological"):
                continue
            chosen = select_subjects(g, sec_cfg.get("select", sec_name), ordering_config.selectors)
            _assert_same_as_reference(g, chosen, sec_cfg["sort"], sec_cfg.get("roots"))
            checked += 1
    assert checked, f"{config} has no topological section"


def test_topo_sort_computes_each_key_once():
    """Exactly one qname_sort_key call per node: the cost bound behind #300."""
    g, nodes = _generated_hierarchy(1000, max_parents=3, cycles=10, components=2, seed=302)
    with mock.patch(
        "rdf_construct.core.ordering.qname_sort_key", side_effect=qname_sort_key
    ) as counted:
        topo_sort_subset(g, nodes, RDFS.subClassOf)
    assert counted.call_count == len(nodes)


def test_topo_sort_cycle_remainder_appended_in_key_order():
    """Nodes on a cycle never become ready; they follow the rest, in key order."""
    g = Graph()
    ex = "http://example.org/test#"
    g.bind("ex", ex)
    a, b, c, z = (URIRef(ex + n) for n in ("A", "B", "C", "Z"))
    # Z is acyclic; C <-> A is a cycle, and B hangs off it
    g.add((c, RDFS.subClassOf, a))
    g.add((a, RDFS.subClassOf, c))
    g.add((b, RDFS.subClassOf, a))

    assert topo_sort_subset(g, {a, b, c, z}, RDFS.subClassOf) == [z, a, b, c]


def test_topo_sort_equal_keys_break_ties_as_before():
    """A BNode and a relative IRI of the same lexical form share a key ('<a>').

    Among equal keys the old stable re-sort + pop(0) emitted whichever node
    became ready first; the heap's insertion counter must do the same, and must
    never compare a URIRef with a BNode. The two parents ('<0p1>', '<0p2>') sort
    before every tied key, so both members of each pair are ready together, and
    the one under the first parent was ready first. That is a URIRef for 'a' and a
    BNode for 'b', so no tie-break on the terms themselves can pass.
    """
    g = Graph()
    first, second = URIRef("0p1"), URIRef("0p2")
    g.add((URIRef("a"), RDFS.subClassOf, first))
    g.add((BNode("a"), RDFS.subClassOf, second))
    g.add((BNode("b"), RDFS.subClassOf, first))
    g.add((URIRef("b"), RDFS.subClassOf, second))
    nodes = {first, second, URIRef("a"), BNode("a"), URIRef("b"), BNode("b")}
    assert qname_sort_key(g, URIRef("a")) == qname_sort_key(g, BNode("a")) == "<a>"

    expected = [first, second, URIRef("a"), BNode("a"), BNode("b"), URIRef("b")]
    assert _reference_topo_sort(g, nodes, RDFS.subClassOf) == expected
    assert topo_sort_subset(g, nodes, RDFS.subClassOf) == expected
