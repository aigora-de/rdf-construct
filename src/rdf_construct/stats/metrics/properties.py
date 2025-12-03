"""Property metrics for RDF ontologies.

Analyses property definitions: domain/range coverage, special characteristics.
"""

from dataclasses import dataclass

from rdflib import Graph, RDF, RDFS
from rdflib.namespace import OWL


@dataclass
class PropertyStats:
    """Property statistics for an ontology.

    Attributes:
        with_domain: Properties that have rdfs:domain defined.
        with_range: Properties that have rdfs:range defined.
        domain_coverage: Proportion of properties with domain (0.0 - 1.0).
        range_coverage: Proportion of properties with range (0.0 - 1.0).
        inverse_pairs: Number of owl:inverseOf pairs.
        functional: Number of owl:FunctionalProperty properties.
        symmetric: Number of owl:SymmetricProperty properties.
    """

    with_domain: int = 0
    with_range: int = 0
    domain_coverage: float = 0.0
    range_coverage: float = 0.0
    inverse_pairs: int = 0
    functional: int = 0
    symmetric: int = 0


def _get_all_properties(graph: Graph) -> set:
    """Get all properties from the graph (object + datatype + annotation)."""
    props = set()
    for prop_type in (
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        RDF.Property,
    ):
        props |= set(graph.subjects(RDF.type, prop_type))
    return props


def collect_property_stats(graph: Graph) -> PropertyStats:
    """Collect property statistics from an RDF graph.

    Args:
        graph: RDF graph to analyse.

    Returns:
        PropertyStats with all property metrics populated.
    """
    properties = _get_all_properties(graph)
    total = len(properties)

    if total == 0:
        return PropertyStats()

    # Count properties with domain
    with_domain = sum(1 for p in properties if graph.value(p, RDFS.domain) is not None)

    # Count properties with range
    with_range = sum(1 for p in properties if graph.value(p, RDFS.range) is not None)

    # Count inverse pairs (each owl:inverseOf creates a pair)
    # Count unique pairs (A inverseOf B = B inverseOf A)
    inverse_subjects = set(graph.subjects(OWL.inverseOf, None))
    inverse_pairs = len(inverse_subjects)  # Each subject represents one pair relationship

    # Count functional properties
    functional = len(set(graph.subjects(RDF.type, OWL.FunctionalProperty)))

    # Count symmetric properties
    symmetric = len(set(graph.subjects(RDF.type, OWL.SymmetricProperty)))

    return PropertyStats(
        with_domain=with_domain,
        with_range=with_range,
        domain_coverage=round(with_domain / total, 3) if total else 0.0,
        range_coverage=round(with_range / total, 3) if total else 0.0,
        inverse_pairs=inverse_pairs,
        functional=functional,
        symmetric=symmetric,
    )
