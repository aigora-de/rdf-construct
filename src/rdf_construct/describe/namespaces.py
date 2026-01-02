"""Namespace analysis for ontology description.

Categorises namespaces as local, imported, or external (unimported).
"""

from collections import Counter

from rdflib import Graph, URIRef, BNode
from rdflib.namespace import OWL, RDF, RDFS, XSD

from rdf_construct.describe.models import (
    NamespaceAnalysis,
    NamespaceInfo,
    NamespaceCategory,
)
from rdf_construct.describe.imports import get_imported_namespaces


# Well-known vocabulary namespaces (always considered external but expected)
WELL_KNOWN_NAMESPACES = {
    str(RDF): "rdf",
    str(RDFS): "rdfs",
    str(OWL): "owl",
    str(XSD): "xsd",
    "http://www.w3.org/2004/02/skos/core#": "skos",
    "http://purl.org/dc/elements/1.1/": "dc",
    "http://purl.org/dc/terms/": "dcterms",
    "http://xmlns.com/foaf/0.1/": "foaf",
    "http://www.w3.org/ns/prov#": "prov",
    "http://www.w3.org/ns/shacl#": "sh",
}


def analyse_namespaces(graph: Graph) -> NamespaceAnalysis:
    """Analyse namespace usage in the ontology.

    Categorises each namespace as:
    - LOCAL: Defined in this ontology (contains defined classes/properties)
    - IMPORTED: Declared via owl:imports
    - EXTERNAL: Referenced but not imported (may indicate missing import)

    Args:
        graph: RDF graph to analyse.

    Returns:
        NamespaceAnalysis with categorised namespaces.
    """
    # Get ontology IRI to identify local namespace
    local_namespace = _get_local_namespace(graph)

    # Get imported namespaces
    imported_ns = get_imported_namespaces(graph)

    # Count namespace usage across all triples
    ns_usage = _count_namespace_usage(graph)

    # Get prefix bindings
    prefix_map = {str(uri): prefix for prefix, uri in graph.namespace_manager.namespaces()}

    # Build namespace info list
    namespaces: list[NamespaceInfo] = []
    unimported_external: list[str] = []

    for ns_uri, count in sorted(ns_usage.items(), key=lambda x: -x[1]):
        # Determine category
        if local_namespace and ns_uri == local_namespace:
            category = NamespaceCategory.LOCAL
        elif ns_uri in imported_ns:
            category = NamespaceCategory.IMPORTED
        elif ns_uri in WELL_KNOWN_NAMESPACES:
            # Well-known vocabularies are external but expected
            category = NamespaceCategory.EXTERNAL
        else:
            # Unknown external namespace - might be missing import
            category = NamespaceCategory.EXTERNAL
            if ns_uri not in WELL_KNOWN_NAMESPACES:
                unimported_external.append(ns_uri)

        # Get prefix (from bindings or well-known)
        prefix = prefix_map.get(ns_uri) or WELL_KNOWN_NAMESPACES.get(ns_uri)

        namespaces.append(NamespaceInfo(
            uri=ns_uri,
            prefix=prefix,
            category=category,
            usage_count=count,
        ))

    return NamespaceAnalysis(
        local_namespace=local_namespace,
        namespaces=namespaces,
        unimported_external=unimported_external,
    )


def _get_local_namespace(graph: Graph) -> str | None:
    """Determine the local/primary namespace for the ontology.

    Uses the ontology IRI if declared, otherwise infers from
    most commonly used namespace for defined entities.

    Args:
        graph: RDF graph to analyse.

    Returns:
        Local namespace URI or None if not determinable.
    """
    # First, try to get from owl:Ontology declaration
    for ontology in graph.subjects(RDF.type, OWL.Ontology):
        if isinstance(ontology, URIRef):
            return _extract_namespace(str(ontology))

    # Fall back to most common namespace for defined classes
    class_ns = Counter[str]()
    for cls in graph.subjects(RDF.type, OWL.Class):
        if isinstance(cls, URIRef):
            ns = _extract_namespace(str(cls))
            if ns not in WELL_KNOWN_NAMESPACES:
                class_ns[ns] += 1

    for cls in graph.subjects(RDF.type, RDFS.Class):
        if isinstance(cls, URIRef):
            ns = _extract_namespace(str(cls))
            if ns not in WELL_KNOWN_NAMESPACES:
                class_ns[ns] += 1

    if class_ns:
        return class_ns.most_common(1)[0][0]

    return None


def _count_namespace_usage(graph: Graph) -> dict[str, int]:
    """Count how many times each namespace is used in the graph.

    Args:
        graph: RDF graph to analyse.

    Returns:
        Dictionary mapping namespace URI to usage count.
    """
    ns_count: Counter[str] = Counter()

    for s, p, o in graph:
        # Count subject namespace (skip blank nodes)
        if isinstance(s, URIRef):
            ns_count[_extract_namespace(str(s))] += 1

        # Count predicate namespace
        if isinstance(p, URIRef):
            ns_count[_extract_namespace(str(p))] += 1

        # Count object namespace (if URI)
        if isinstance(o, URIRef):
            ns_count[_extract_namespace(str(o))] += 1

    return dict(ns_count)


def _extract_namespace(uri: str) -> str:
    """Extract namespace from a URI.

    Handles both # and / as namespace separators.

    Args:
        uri: Full URI string.

    Returns:
        Namespace portion of the URI.
    """
    # Split on # first (OWL-style namespaces)
    if "#" in uri:
        return uri.rsplit("#", 1)[0] + "#"

    # Otherwise split on last /
    if "/" in uri:
        return uri.rsplit("/", 1)[0] + "/"

    # No separator found, return as-is
    return uri
