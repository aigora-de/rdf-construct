"""Connectivity metrics for RDF ontologies.

Analyses how classes are connected through properties.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from rdflib import Graph, RDF, RDFS, URIRef
from rdflib.namespace import OWL


@dataclass
class ConnectivityStats:
    """Connectivity statistics for an ontology.

    Attributes:
        most_connected_class: URI of the class referenced by most properties.
        most_connected_count: Number of properties referencing the most connected class.
        isolated_classes: Classes not referenced by any property domain/range.
    """

    most_connected_class: Optional[str] = None
    most_connected_count: int = 0
    isolated_classes: int = 0


def _get_all_classes(graph: Graph) -> set:
    """Get all classes from the graph."""
    classes = set(graph.subjects(RDF.type, OWL.Class))
    classes |= set(graph.subjects(RDF.type, RDFS.Class))
    return classes


def _count_property_references(graph: Graph, classes: set) -> dict:
    """Count property references to each class (via domain/range).

    A class is "connected" if a property references it in its domain or range.

    Args:
        graph: RDF graph to query.
        classes: Set of class URIRefs.

    Returns:
        Dictionary mapping class -> reference count.
    """
    counts: dict = defaultdict(int)

    # Count domain references
    for s, p, o in graph.triples((None, RDFS.domain, None)):
        if o in classes:
            counts[o] += 1

    # Count range references
    for s, p, o in graph.triples((None, RDFS.range, None)):
        if o in classes:
            counts[o] += 1

    return dict(counts)


def _find_most_connected(ref_counts: dict) -> tuple[Optional[str], int]:
    """Find the class with the most property references.

    Args:
        ref_counts: Dictionary mapping class -> reference count.

    Returns:
        Tuple of (class URI string, reference count).
    """
    if not ref_counts:
        return None, 0

    most_connected = max(ref_counts.items(), key=lambda x: x[1])
    uri = str(most_connected[0]) if most_connected[0] else None
    return uri, most_connected[1]


def _count_isolated(classes: set, ref_counts: dict, graph: Graph) -> int:
    """Count classes not connected to any property.

    A class is isolated if:
    - No property has it as domain or range
    - AND it has no subclasses or superclasses (not part of hierarchy)

    Args:
        classes: Set of class URIRefs.
        ref_counts: Dictionary mapping class -> reference count.
        graph: RDF graph to query for hierarchy.

    Returns:
        Number of isolated classes.
    """
    isolated = 0
    for cls in classes:
        # Not referenced by properties
        if ref_counts.get(cls, 0) == 0:
            # Also check if it's disconnected from hierarchy
            has_super = any(graph.objects(cls, RDFS.subClassOf))
            has_sub = any(graph.subjects(RDFS.subClassOf, cls))
            if not has_super and not has_sub:
                isolated += 1
    return isolated


def collect_connectivity_stats(graph: Graph) -> ConnectivityStats:
    """Collect connectivity statistics from an RDF graph.

    Args:
        graph: RDF graph to analyse.

    Returns:
        ConnectivityStats with all connectivity metrics populated.
    """
    classes = _get_all_classes(graph)

    if not classes:
        return ConnectivityStats()

    ref_counts = _count_property_references(graph, classes)

    most_uri, most_count = _find_most_connected(ref_counts)
    isolated = _count_isolated(classes, ref_counts, graph)

    return ConnectivityStats(
        most_connected_class=most_uri,
        most_connected_count=most_count,
        isolated_classes=isolated,
    )
