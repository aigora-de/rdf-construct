"""Tests for ordering functionality."""

import pytest
from rdflib import Graph, URIRef, RDFS
from rdflib.namespace import OWL

from rdf_construct.core.ordering import (
    build_adjacency,
    descendants_of,
    sort_subjects,
    topo_sort_subset,
)


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
