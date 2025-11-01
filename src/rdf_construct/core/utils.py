"""Utilities for handling prefixes, CURIEs, and namespace operations."""

from typing import Optional

from rdflib import Graph, Namespace, URIRef


def extract_prefix_map(graph: Graph) -> dict[str, str]:
    """Extract all namespace prefixes from a graph.

    Args:
        graph: RDF graph to extract prefixes from

    Returns:
        Dictionary mapping prefix strings to namespace URIs
    """
    return {pfx: str(uri) for pfx, uri in graph.namespace_manager.namespaces()}


def expand_curie(graph: Graph, curie_or_iri: str) -> Optional[URIRef]:
    """Expand a CURIE to a full URIRef using the graph's namespace bindings.

    Handles multiple input formats:
    - CURIE format: 'ies:Element' -> http://example.org/ies#Element
    - Angle brackets: '<http://...>' -> http://...
    - Full IRI: 'http://...' -> http://...

    Args:
        graph: RDF graph containing namespace bindings
        curie_or_iri: CURIE, bracketed IRI, or full IRI string

    Returns:
        Expanded URIRef or None if expansion fails
    """
    s = curie_or_iri.strip()
    if not s:
        return None

    # Handle angle-bracketed IRIs
    if s.startswith("<") and s.endswith(">"):
        return URIRef(s[1:-1])

    # Handle full IRIs
    if "://" in s:
        return URIRef(s)

    # Handle CURIEs
    if ":" in s:
        pfx, local = s.split(":", 1)
        for p, uri in graph.namespace_manager.namespaces():
            if p == pfx:
                return URIRef(str(uri) + local)

    return None


def rebind_prefixes(
        graph: Graph, ordered_prefixes: list[str], prefix_map: dict[str, str]
) -> None:
    """Rebind prefixes in a graph according to a specified order.

    This ensures deterministic prefix ordering in serialized output.

    Args:
        graph: RDF graph to rebind prefixes in
        ordered_prefixes: List of prefix strings in desired order
        prefix_map: Dictionary mapping prefixes to namespace URIs
    """
    nm = graph.namespace_manager
    for pfx in ordered_prefixes:
        uri = prefix_map.get(pfx)
        if uri:
            nm.bind(pfx, URIRef(uri), override=True, replace=True)


def qname_sort_key(graph: Graph, term) -> str:
    """Generate a sortable string key for an RDF term using its QName.

    Args:
        graph: RDF graph containing namespace bindings
        term: RDF term to generate key for

    Returns:
        Normalized URI string suitable for alphabetical sorting
    """
    try:
        return graph.namespace_manager.normalizeUri(term)
    except Exception:
        return str(term)
