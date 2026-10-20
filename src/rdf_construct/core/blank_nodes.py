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
labelled on its own and its labels carry the component's digest.

**Trees are hashed structurally.** Almost every component an ontology has is a tree: each blank
node has at most one blank-node parent and there is no cycle. Restrictions, ``rdf:List`` chains,
nested class expressions and reifications all are. A tree is hashed bottom-up, each node from its
own triples and its children's hashes, in time close to linear. Only a component that is not a tree
(a node with two blank-node parents, or a cycle) is canonicalised with ``rdflib.compare``, whose
cost grows steeply with size: a 1,000-cell list took 11 s that way (#170's panel). The two methods
digest under different tags, so they can never collide.

**Copies within one file are kept.** The k-th copy of a component in a graph gets its own labels, so
relabelling a graph never changes it, and the union of relabelled graphs holds each component as
many times as the graph with the most copies. Redundancy that is not an identical copy (one file
states a restriction, another states it with an extra annotation) is kept too: removing it is
graph leaning, which is NP-hard and changes what a file says it states.

**The verifier uses this module too.** ``core.verify``'s ``SUPERSET`` check compares components by
:func:`component_digest`, so a fault in the digest would pass both ``merge`` and its contract. The
exact expectation of a merge is therefore pinned against a hand-written file with ``ISOMORPHIC``,
which uses ``rdflib.compare`` and nothing here.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

from rdflib import Graph
from rdflib.compare import to_canonical_graph
from rdflib.term import BNode, Node

#: Hex digits of a component's SHA-256 digest kept in its labels: 128 bits.
DIGEST_LENGTH = 32

#: Hex digits of the path hash that tells the nodes of one tree component apart.
PATH_LENGTH = 16


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


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


#: A component's digest, the place of each of its blank nodes keyed by label, and the triples
#: those labels name.
Labelled = tuple[str, dict[str, str], list[tuple[Node, Node, Node]]]


def _tree_labels(component: Graph) -> Labelled | None:
    """Digest and label a component that is a tree, or return None if it is not one.

    A node's hash covers its outgoing triples, with each blank-node object replaced by that
    child's hash, and its incoming triples from ground subjects. Siblings with the same predicate
    and hash are identical subtrees, so the order in which they are numbered does not change the
    graph that the labels describe.
    """
    children: dict[Node, list[tuple[Node, Node]]] = defaultdict(list)
    ground_out: dict[Node, list[str]] = defaultdict(list)
    ground_in: dict[Node, list[str]] = defaultdict(list)
    parents: dict[Node, int] = defaultdict(int)
    nodes: set[Node] = set()
    for s, p, o in component:
        if isinstance(s, BNode):
            nodes.add(s)
            if isinstance(o, BNode):
                nodes.add(o)
                children[s].append((p, o))
                parents[o] += 1
            else:
                ground_out[s].append(f"{p.n3()} {o.n3()}")
        else:
            nodes.add(o)
            ground_in[o].append(f"^ {s.n3()} {p.n3()}")

    roots = [node for node in nodes if parents[node] == 0]
    if len(roots) != 1 or any(count > 1 for count in parents.values()):
        return None
    root = roots[0]

    order = [root]
    for node in order:
        order.extend(child for _, child in children[node])
    if len(order) != len(nodes):
        return None

    hashes: dict[Node, str] = {}
    for node in reversed(order):
        items = ground_out[node] + ground_in[node]
        items += [f"{p.n3()} #{hashes[child]}" for p, child in children[node]]
        hashes[node] = _sha256("\n".join(sorted(items)))
    digest = _sha256(f"tree\n{hashes[root]}")

    paths: dict[str, str] = {str(root): "r"}
    for node in order:
        seen: dict[tuple[str, str], int] = defaultdict(int)
        for p, child in sorted(children[node], key=lambda pc: (pc[0].n3(), hashes[pc[1]])):
            key = (p.n3(), hashes[child])
            index = seen[key]
            seen[key] += 1
            place = _sha256(f"{paths[str(node)]}\n{key[0]}\n{key[1]}\n{index}")
            paths[str(child)] = place[:PATH_LENGTH]
    return digest, paths, list(component)


def _graph_labels(component: Graph) -> Labelled:
    """Digest and label any component with ``rdflib.compare``: used for those that are not trees.

    The places it returns name the nodes of the canonical copy, so its triples are that copy's.
    """
    triples = list(to_canonical_graph(component))
    lines = sorted(" ".join(term.n3() for term in triple) for triple in triples)
    digest = _sha256("graph\n" + "\n".join(lines))
    canonical = sorted({str(term) for t in triples for term in t if isinstance(term, BNode)})
    places = {node: str(position) for position, node in enumerate(canonical)}
    return digest, places, triples


def _labelled(component: Graph) -> Labelled:
    return _tree_labels(component) or _graph_labels(component)


def component_digest(component: Graph) -> str:
    """Return a digest of a component that depends only on its content.

    Args:
        component: One blank-node component, as :func:`blank_node_components` returns it.

    Returns:
        A SHA-256 hex digest. Two components have the same digest exactly when they are
        isomorphic.
    """
    return _labelled(component)[0]


def label_by_content(graph: Graph) -> Graph:
    """Return a copy of ``graph`` whose blank nodes are labelled by their component's content.

    The copy is isomorphic to ``graph``. Two graphs that share a component give it the same labels,
    so their union holds it once. Labels are ``b<digest>_<k>_<node>``: the component's digest,
    which copy of it this is within ``graph``, and the node's place within the component.

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
        digest, places, triples = _labelled(component)
        prefix = f"b{digest[:DIGEST_LENGTH]}_{copies[digest]}_"
        copies[digest] += 1
        labels = {node: BNode(prefix + place) for node, place in places.items()}
        for s, p, o in triples:
            relabelled.add(
                (
                    labels[str(s)] if isinstance(s, BNode) else s,
                    p,
                    labels[str(o)] if isinstance(o, BNode) else o,
                )
            )
    return relabelled
