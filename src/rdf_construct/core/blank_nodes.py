"""Blank-node components: what makes two blank-node structures from different files the same (#170).

A blank node has no identity outside the file it was parsed from. rdflib mints fresh ``BNode``s
on every parse, so a restriction that two files both state is two different nodes to a graph's set
semantics, and a union of the two writes it twice.

**The unit of sameness is the component.** A blank-node component is a maximal set of blank nodes
joined by triples that have a blank node at both ends, together with every triple that touches one
of them, including the triple that refers to it (``ex:A rdfs:subClassOf _:r``). Two components are
the same when they are isomorphic, ground neighbours included. Writing one of two such components
is simple-entailment equivalent to writing both, so identifying them never adds or loses
information. Anything weaker is not safe:

- the same restriction under two different classes is two components, and stays two;
- ``_:x foaf:name "Bob"`` reached from two different subjects is two people, not one.

**Labels are derived from content, and only from content.** ``rdflib.compare`` labels relative to
the whole graph it is given: a graph with one blank node always calls it ``_:cb0``, so canonicalising
two files separately and taking the union fuses unrelated structures. Here each component is
canonicalised on its own and its labels carry the component's digest.

**Copies within one file are kept.** The k-th copy of a component in a graph gets its own labels, so
relabelling a graph never changes it, and the union of relabelled graphs holds each component as
many times as the graph with the most copies. Redundancy that is not an identical copy (one file
states a restriction, another states it with an extra annotation) is kept too: removing it is
graph leaning, which is NP-hard and changes what a file says it states.

**Cost.** Each component is canonicalised separately, which is cheap for the restrictions, lists and
reifications ontologies are made of. A single very large and highly symmetric component is the
worst case for ``rdflib.compare``.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

from rdflib import Graph
from rdflib.compare import to_canonical_graph
from rdflib.term import BNode, Node

#: Hex digits of a component's SHA-256 digest kept in its labels: 128 bits.
DIGEST_LENGTH = 32


def blank_node_components(graph: Graph) -> list[Graph]:
    """Divide the triples of ``graph`` that have a blank node into blank-node components.

    Args:
        graph: The graph to divide.

    Returns:
        One graph per component, holding every triple that touches one of its blank nodes. A
        triple with no blank node is in none of them.
    """
    parent: dict[Node, Node] = {}

    def find(node: Node) -> Node:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for s, _, o in graph:
        ends = [term for term in (s, o) if isinstance(term, BNode)]
        for end in ends:
            parent.setdefault(end, end)
        if len(ends) == 2:
            root_s, root_o = find(ends[0]), find(ends[1])
            if root_s != root_o:
                parent[root_s] = root_o

    components: dict[Node, Graph] = defaultdict(Graph)
    for triple in graph:
        s, _, o = triple
        anchor = s if isinstance(s, BNode) else o if isinstance(o, BNode) else None
        if anchor is not None:
            components[find(anchor)].add(triple)
    return list(components.values())


def _canonical(component: Graph) -> tuple[str, list[tuple[Node, Node, Node]]]:
    triples = list(to_canonical_graph(component))
    lines = sorted(" ".join(term.n3() for term in triple) for triple in triples)
    digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    return digest, triples


def component_digest(component: Graph) -> str:
    """Return a digest of a component that depends only on its content.

    Args:
        component: One blank-node component, as :func:`blank_node_components` returns it.

    Returns:
        The SHA-256 hex digest of the component's canonical N-Triples. Two components have the
        same digest exactly when they are isomorphic.
    """
    return _canonical(component)[0]


def label_by_content(graph: Graph) -> Graph:
    """Return a copy of ``graph`` whose blank nodes are labelled by their component's content.

    The copy is isomorphic to ``graph``. Two graphs that share a component give it the same labels,
    so their union holds it once. Labels are ``b<digest>_<k>_<i>``: the component's digest, which
    copy of it this is within ``graph``, and the node's position within the component.

    Args:
        graph: The graph to relabel. It is not changed.

    Returns:
        A new graph with the same triples, up to blank-node labels, and the same prefix bindings.
    """
    relabelled = Graph(bind_namespaces="none")
    for prefix, namespace in graph.namespace_manager.namespaces():
        relabelled.bind(prefix, namespace, override=True, replace=True)

    for triple in graph:
        if not isinstance(triple[0], BNode) and not isinstance(triple[2], BNode):
            relabelled.add(triple)

    copies: dict[str, int] = defaultdict(int)
    for component in blank_node_components(graph):
        digest, triples = _canonical(component)
        copy = copies[digest]
        copies[digest] += 1
        nodes = sorted({str(term) for t in triples for term in t if isinstance(term, BNode)})
        labels = {
            node: BNode(f"b{digest[:DIGEST_LENGTH]}_{copy}_{index}")
            for index, node in enumerate(nodes)
        }
        for s, p, o in triples:
            relabelled.add(
                (
                    labels[str(s)] if isinstance(s, BNode) else s,
                    p,
                    labels[str(o)] if isinstance(o, BNode) else o,
                )
            )
    return relabelled
