"""Ordering and sorting logic for RDF subjects."""

import heapq
from typing import Optional

from rdflib import Graph, URIRef, RDF, RDFS
from rdflib.namespace import OWL

from .utils import expand_curie, qname_sort_key


def build_adjacency(
    graph: Graph, nodes: set, edge_predicate: URIRef
) -> tuple[dict[URIRef, set[URIRef]], dict[URIRef, int]]:
    """Build adjacency list and indegree map for topological sorting.

    Creates parent->children adjacency representation within the given node set.
    A self-loop (``C rdfs:subClassOf C``) is ignored: it is a tautology, not a cycle.

    Args:
        graph: RDF graph containing the relationships
        nodes: Set of nodes to build adjacency for
        edge_predicate: Predicate defining parent-child relationship
                       (typically rdfs:subClassOf or rdfs:subPropertyOf)

    Returns:
        Tuple of (adjacency dict, indegree dict) where:
        - adjacency maps parent URIRef to set of child URIRefs
        - indegree maps each URIRef to its incoming edge count
    """
    adj: dict[URIRef, set[URIRef]] = {n: set() for n in nodes}
    indeg: dict[URIRef, int] = {n: 0 for n in nodes}

    for n in nodes:
        for parent in graph.objects(n, edge_predicate):
            # RDFS entailment (rdfs10, rdfs6) materialises n ⊑ n for every term;
            # as an edge it would keep n and its subtree out of the sort (#339).
            if parent in nodes and parent != n:
                adj[parent].add(n)  # parent before child
                indeg[n] += 1

    return adj, indeg


def topo_sort_subset(graph: Graph, nodes: set, edge_predicate: URIRef) -> list:
    """Topologically sort a subset of nodes using Kahn's algorithm.

    Sorts nodes so parents appear before children. Uses alphabetical
    tie-breaking for deterministic output. Handles cycles by appending
    remaining nodes alphabetically.

    Args:
        graph: RDF graph containing the relationships
        nodes: Set of nodes to sort
        edge_predicate: Predicate defining parent-child relationship

    Returns:
        List of URIRefs in topological order
    """
    if not nodes:
        return []

    adj, indeg = build_adjacency(graph, nodes, edge_predicate)

    # Compute each sort key once: normalizeUri is uncached and dominated the
    # quadratic version of this sort (#300).
    key = {n: qname_sort_key(graph, n) for n in nodes}

    # The ready set is a heap of (key, seq, node). The insertion counter breaks
    # ties on key exactly as the previous stable re-sort + pop(0) did (earliest
    # ready first), and means two terms are never compared directly.
    ready: list[tuple[str, int, URIRef]] = []
    seq = 0

    # Start with nodes that have no incoming edges
    for n in sorted((n for n, d in indeg.items() if d == 0), key=key.__getitem__):
        ready.append((key[n], seq, n))
        seq += 1
    heapq.heapify(ready)

    out: list = []

    while ready:
        _, _, u = heapq.heappop(ready)
        out.append(u)

        # Process children in alphabetical order
        for v in sorted(adj[u], key=key.__getitem__):
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(ready, (key[v], seq, v))
                seq += 1

    # Handle any remaining nodes (cycles or disconnected components)
    if len(out) < len(nodes):
        emitted = set(out)
        remaining = [n for n in nodes if n not in emitted]
        remaining.sort(key=key.__getitem__)
        out.extend(remaining)

    return out


def descendants_of(graph: Graph, root: URIRef, nodes: set, edge_predicate: URIRef) -> set:
    """Find all descendants of a root node within a set of nodes.

    Traverses the graph following child edges (subClassOf/subPropertyOf)
    to find all nodes reachable from the root.

    Args:
        graph: RDF graph containing the relationships
        root: Root node to start traversal from
        nodes: Set of nodes to consider (search space)
        edge_predicate: Predicate defining parent-child relationship

    Returns:
        Set of URIRefs reachable from root (including root itself if in nodes)
    """
    # Build parent->children map
    children: dict[URIRef, set[URIRef]] = {n: set() for n in nodes}
    for n in nodes:
        for parent in graph.objects(n, edge_predicate):
            if parent in nodes:
                children[parent].add(n)

    reachable = set()
    stack = [root] if root in nodes else []

    while stack:
        u = stack.pop()
        for v in children.get(u, ()):
            if v not in reachable:
                reachable.add(v)
                stack.append(v)

    # Include root itself if it's in the node set
    if root in nodes:
        reachable.add(root)

    return reachable


def sort_with_roots(graph: Graph, subjects: set, mode: str, roots_cfg: Optional[list[str]]) -> list:
    """Sort subjects with explicit root ordering.

    When roots are provided, emits each root's branch contiguously
    (topologically within each branch), then emits remaining subjects
    topologically. This creates a deterministic ordering that respects
    both hierarchy and explicit sequencing preferences.

    Args:
        graph: RDF graph containing the relationships
        subjects: Set of subjects to sort
        mode: Sorting mode (should be 'topological' or 'topological_then_alpha')
        roots_cfg: List of root CURIEs/IRIs defining branch order

    Returns:
        List of URIRefs in the specified order
    """
    mode = (mode or "qname_alpha").lower()

    # Determine appropriate edge predicate based on subject types
    looks_like_props = any(
        (s, RDF.type, OWL.ObjectProperty) in graph or (s, RDF.type, OWL.DatatypeProperty) in graph
        for s in subjects
    )
    edge = RDFS.subPropertyOf if looks_like_props else RDFS.subClassOf

    # Fall back to simple topological if no roots or mode doesn't support them
    if mode not in ("topological", "topological_then_alpha") or not roots_cfg:
        if mode in ("topological", "topological_then_alpha"):
            return topo_sort_subset(graph, subjects, edge)
        return sorted(subjects, key=lambda t: qname_sort_key(graph, t))

    # Expand roots to IRIs
    root_iris: list[URIRef] = []
    for r in roots_cfg:
        iri = expand_curie(graph, r)
        if iri is not None:
            root_iris.append(iri)

    remaining: set = set(subjects)
    ordered: list = []

    # Emit branches in the order of roots list
    for root in root_iris:
        branch_nodes = descendants_of(graph, root, remaining, edge)
        if not branch_nodes:
            continue

        branch_order = topo_sort_subset(graph, branch_nodes, edge)
        for n in branch_order:
            if n in remaining:
                ordered.append(n)
                remaining.remove(n)

    # Emit whatever is left (disconnected components)
    tail_order = topo_sort_subset(graph, remaining, edge)
    ordered.extend(tail_order)

    return ordered


def sort_subjects(
    graph: Graph, subjects: set, sort_mode: str, roots_cfg: Optional[list[str]] = None
) -> list:
    """Sort subjects according to the specified mode.

    Supported modes:
    - 'alpha' or 'qname_alpha': Alphabetical by QName
    - 'topological' or 'topological_then_alpha': Topological with optional roots

    Args:
        graph: RDF graph containing the relationships
        subjects: Set of subjects to sort
        sort_mode: Sorting mode identifier
        roots_cfg: Optional list of root CURIEs for topological sorting

    Returns:
        List of URIRefs in the specified order
    """
    mode = (sort_mode or "qname_alpha").lower()

    if mode in ("alpha", "qname_alpha"):
        return sorted(subjects, key=lambda t: qname_sort_key(graph, t))

    if mode in ("topological", "topological_then_alpha"):
        return sort_with_roots(graph, subjects, mode, roots_cfg)

    # Fallback to alphabetical
    return sorted(subjects, key=lambda t: qname_sort_key(graph, t))
