"""Ordering and sorting logic for RDF subjects."""

import heapq
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional

from rdflib import Graph, URIRef, RDFS

from .utils import CurieError, extract_prefix_map, qname_sort_key, resolve_curie

#: Every ``sort:`` mode a profile section may name, in the order they are
#: documented. ``qname_alpha`` is the same as ``alpha``, and
#: ``topological_then_alpha`` the same as ``topological``: ties in a
#: topological sort are already broken alphabetically. Matched ignoring case.
SORT_MODES: tuple[str, ...] = ("alpha", "qname_alpha", "topological", "topological_then_alpha")

#: The modes of :data:`SORT_MODES` that sort by hierarchy, and so take ``roots``.
TOPOLOGICAL_MODES: tuple[str, ...] = ("topological", "topological_then_alpha")

#: The hierarchy predicates a topological section is sorted over, together. RDFS gives
#: ``rdfs:subClassOf`` a class at each end and ``rdfs:subPropertyOf`` a property at each end,
#: so each links only like with like, and a term that is both a class and a property (a pun)
#: keeps both hierarchies. Choosing one predicate per section by sniffing its members' types
#: ignored characteristic-only, ``other_props`` and annotation-property hierarchies, and one
#: punned class sent a whole class section alphabetical (#245).
HIERARCHY_PREDICATES: tuple[URIRef, ...] = (RDFS.subClassOf, RDFS.subPropertyOf)


class UnknownSortModeError(ValueError):
    """A sort mode that is not one of :data:`SORT_MODES`.

    Raised rather than falling back to alphabetical order, because
    alphabetical output looks exactly like a profile that worked: the
    hierarchy order the profile asked for is silently lost. See issue #242.
    """


class InvalidRootError(ValueError):
    """A ``roots:`` value that is not a list of CURIEs and IRIs.

    Raised for a value that is not a list (a single string would otherwise be read a
    character at a time), an entry that is not a string, and an entry that is neither a
    CURIE nor an IRI, such as ``Animal``. A root whose prefix the source does not declare
    is not this error: a configuration shared between ontologies meets that legitimately,
    so it is reported, not refused (#241).
    """


@dataclass(frozen=True)
class ResolvedRoot:
    """One ``roots:`` entry, resolved against a graph's prefixes.

    Attributes:
        text: The entry as written.
        iri: The IRI it names, or None if its prefix is not declared.
        error: Why it did not resolve, when ``iri`` is None.
    """

    text: str
    iri: URIRef | None
    error: CurieError | None = None


def check_roots(roots: object) -> list[str]:
    """Find what makes a ``roots:`` value unusable, without a graph.

    Whether an entry is a CURIE or an IRI at all does not depend on the source's prefixes,
    so this runs before anything is parsed or written. ``None`` and ``[]`` are fine.

    Args:
        roots: The value given for ``roots:``, from a profile section or a caller

    Returns:
        One message per problem; empty if there are none
    """
    if roots is None:
        return []
    if not isinstance(roots, list):
        return [f"roots: expected a list of CURIEs or IRIs, such as [ex:Animal]; got {roots!r}"]
    problems: list[str] = []
    for entry in roots:
        if not isinstance(entry, str):
            problems.append(f"root {entry!r} is not a CURIE or an IRI: expected a string")
            continue
        try:
            resolve_curie({}, entry)
        except CurieError as exc:
            if exc.prefix is None:
                problems.append(
                    f"root {entry!r} is not a CURIE or an IRI; write ex:Term, <http://…> "
                    "or http://…"
                )
    return problems


def resolve_roots(graph: Graph, roots: object) -> list[ResolvedRoot]:
    """Resolve ``roots:`` entries against the prefixes the graph declares.

    Each distinct entry once, in the order given. Resolution is ``resolve_curie``'s:
    a bracketed or full IRI, or a CURIE whose prefix the graph binds, never rdflib's own
    prefix table. Whether the IRI is in the graph is the caller's question.

    Args:
        graph: The graph whose prefixes the CURIEs use
        roots: The ``roots:`` value

    Returns:
        One entry per distinct root; an undeclared prefix gives ``iri=None`` and its error

    Raises:
        InvalidRootError: If :func:`check_roots` finds a problem
    """
    problems = check_roots(roots)
    if problems:
        raise InvalidRootError("; ".join(problems))
    if not isinstance(roots, list) or not roots:
        return []
    prefixes = extract_prefix_map(graph)
    resolved: list[ResolvedRoot] = []
    for text in dict.fromkeys(roots):
        try:
            resolved.append(ResolvedRoot(text, resolve_curie(prefixes, text)))
        except CurieError as exc:
            resolved.append(ResolvedRoot(text, None, exc))
    return resolved


def normalise_sort_mode(mode: object) -> str:
    """Return the canonical spelling of a sort mode, or refuse it.

    Args:
        mode: The value given for ``sort:``, from a profile or a caller

    Returns:
        The mode, lower-cased: one of :data:`SORT_MODES`

    Raises:
        UnknownSortModeError: If the value is not a string, is empty, or is not
            one of :data:`SORT_MODES` in any case
    """
    if isinstance(mode, str) and mode.lower() in SORT_MODES:
        return mode.lower()
    raise UnknownSortModeError(
        f"unknown sort mode {mode!r}. Accepted sort modes: {', '.join(SORT_MODES)}"
    )


def _edges(edge_predicate: URIRef | Sequence[URIRef]) -> tuple[URIRef, ...]:
    """One predicate or several, as a tuple. A ``URIRef`` is a ``str``: never iterate it."""
    if isinstance(edge_predicate, str):
        return (URIRef(edge_predicate),)
    return tuple(edge_predicate)


def build_adjacency(
    graph: Graph, nodes: set, edge_predicate: URIRef | Sequence[URIRef]
) -> tuple[dict[URIRef, set[URIRef]], dict[URIRef, int]]:
    """Build adjacency list and indegree map for topological sorting.

    Creates parent->children adjacency representation within the given node set.
    A self-loop (``C rdfs:subClassOf C``) is ignored: it is a tautology, not a cycle.

    Args:
        graph: RDF graph containing the relationships
        nodes: Set of nodes to build adjacency for
        edge_predicate: Predicate defining parent-child relationship
                       (typically rdfs:subClassOf or rdfs:subPropertyOf), or several,
                       such as :data:`HIERARCHY_PREDICATES`. A parent linked by more than
                       one of them is counted once.

    Returns:
        Tuple of (adjacency dict, indegree dict) where:
        - adjacency maps parent URIRef to set of child URIRefs
        - indegree maps each URIRef to its incoming edge count
    """
    adj: dict[URIRef, set[URIRef]] = {n: set() for n in nodes}
    indeg: dict[URIRef, int] = {n: 0 for n in nodes}

    for n in nodes:
        for predicate in _edges(edge_predicate):
            for parent in graph.objects(n, predicate):
                # RDFS entailment (rdfs10, rdfs6) materialises n ⊑ n for every term;
                # as an edge it would keep n and its subtree out of the sort (#339).
                # A pun can reach the same parent by both predicates: one edge (#245).
                if parent in nodes and parent != n:
                    children = adj[parent]
                    if n not in children:
                        children.add(n)  # parent before child
                        indeg[n] += 1

    return adj, indeg


def topo_sort_subset(graph: Graph, nodes: set, edge_predicate: URIRef | Sequence[URIRef]) -> list:
    """Topologically sort a subset of nodes using Kahn's algorithm.

    Sorts nodes so parents appear before children. Uses alphabetical
    tie-breaking for deterministic output. Handles cycles by appending
    remaining nodes alphabetically.

    Args:
        graph: RDF graph containing the relationships
        nodes: Set of nodes to sort
        edge_predicate: Predicate defining parent-child relationship, or several

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


def descendants_of(
    graph: Graph, root: URIRef, nodes: set[URIRef], edge_predicate: URIRef | Sequence[URIRef]
) -> set:
    """Find all descendants of a root node within a set of nodes.

    Traverses the graph following child edges (subClassOf/subPropertyOf)
    to find all nodes reachable from the root.

    Args:
        graph: RDF graph containing the relationships
        root: Root node to start traversal from
        nodes: Set of nodes to consider (search space)
        edge_predicate: Predicate defining parent-child relationship, or several

    Returns:
        Set of URIRefs reachable from root (including root itself if in nodes)
    """
    # Build parent->children map
    children: dict[URIRef, set[URIRef]] = {n: set() for n in nodes}
    for n in nodes:
        for predicate in _edges(edge_predicate):
            for parent in graph.objects(n, predicate):
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

    The hierarchy is :data:`HIERARCHY_PREDICATES`, ``rdfs:subClassOf`` and
    ``rdfs:subPropertyOf`` together, whatever the subjects are.

    Roots are resolved by :func:`resolve_roots`. A root whose prefix the graph does not
    declare, or that names no subject in ``subjects``, anchors nothing and is passed over;
    :func:`resolve_roots` tells a caller which, so it can say so.

    Args:
        graph: RDF graph containing the relationships
        subjects: Set of subjects to sort
        mode: Sorting mode (should be 'topological' or 'topological_then_alpha')
        roots_cfg: List of root CURIEs/IRIs defining branch order

    Returns:
        List of URIRefs in the specified order

    Raises:
        UnknownSortModeError: If ``mode`` is not one of :data:`SORT_MODES`
        InvalidRootError: If ``roots_cfg`` is not a list of CURIEs and IRIs
    """
    mode = normalise_sort_mode(mode)
    resolved = resolve_roots(graph, roots_cfg)

    edge = HIERARCHY_PREDICATES

    # Fall back to simple topological if no roots or mode doesn't support them
    if mode not in TOPOLOGICAL_MODES or not roots_cfg:
        if mode in TOPOLOGICAL_MODES:
            return topo_sort_subset(graph, subjects, edge)
        return sorted(subjects, key=lambda t: qname_sort_key(graph, t))

    root_iris = [root.iri for root in resolved if root.iri is not None]

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

    Raises:
        UnknownSortModeError: If ``sort_mode`` is not one of :data:`SORT_MODES`
        InvalidRootError: If ``roots_cfg`` is not a list of CURIEs and IRIs
    """
    mode = normalise_sort_mode(sort_mode)
    problems = check_roots(roots_cfg)
    if problems:
        raise InvalidRootError("; ".join(problems))

    if mode in TOPOLOGICAL_MODES:
        return sort_with_roots(graph, subjects, mode, roots_cfg)

    return sorted(subjects, key=lambda t: qname_sort_key(graph, t))
