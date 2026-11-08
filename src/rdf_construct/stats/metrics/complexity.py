"""Complexity metrics for RDF ontologies.

Analyses structural complexity: multiple inheritance, axioms, restrictions.
"""

from collections import defaultdict
from dataclasses import dataclass

from rdflib import Graph, RDF, RDFS
from rdflib.namespace import OWL

from rdf_construct.core.ownership import ownership
from rdf_construct.stats.metrics.basic import get_all_classes


@dataclass
class ComplexityStats:
    """Complexity statistics for an ontology.

    Attributes:
        avg_properties_per_class: Average properties referencing each class.
        avg_superclasses_per_class: Average number of superclasses per class.
        multiple_inheritance_count: Classes with 2+ direct superclasses.
        owl_restriction_count: Number of owl:Restriction nodes.
        owl_equivalent_count: Number of owl:equivalentClass statements.
    """

    avg_properties_per_class: float = 0.0
    avg_superclasses_per_class: float = 0.0
    multiple_inheritance_count: int = 0
    owl_restriction_count: int = 0
    owl_equivalent_count: int = 0


def _get_all_classes(graph: Graph) -> set:
    """Get all classes from the graph: the ontology's own, of any `CLASS_TYPES` type (#138)."""
    return get_all_classes(graph)


def _count_properties_per_class(graph: Graph, classes: set) -> dict:
    """Count how many properties reference each class (via domain/range).

    Args:
        graph: RDF graph to query.
        classes: Set of class URIRefs.

    Returns:
        Dictionary mapping class -> property count.
    """
    counts: dict = defaultdict(int)
    # A property that is not the ontology's own is in no count (#371)
    owned = ownership(graph)

    # Count domain references
    for s, p, o in graph.triples((None, RDFS.domain, None)):
        if o in classes and not owned.is_foreign(s):
            counts[o] += 1

    # Count range references
    for s, p, o in graph.triples((None, RDFS.range, None)):
        if o in classes and not owned.is_foreign(s):
            counts[o] += 1

    return dict(counts)


def _count_superclasses(graph: Graph, classes: set) -> dict:
    """Count direct superclasses for each class.

    Args:
        graph: RDF graph to query.
        classes: Set of class URIRefs.

    Returns:
        Dictionary mapping class -> superclass count.
    """
    counts: dict = {}

    for cls in classes:
        superclasses = set(graph.objects(cls, RDFS.subClassOf))
        # Only count named classes, not restrictions or other constructs
        named_supers = superclasses & classes
        counts[cls] = len(named_supers)

    return counts


def _count_multiple_inheritance(superclass_counts: dict) -> int:
    """Count classes with multiple inheritance (2+ superclasses).

    Args:
        superclass_counts: Dictionary mapping class -> superclass count.

    Returns:
        Number of classes with multiple inheritance.
    """
    return sum(1 for count in superclass_counts.values() if count >= 2)


def collect_complexity_stats(graph: Graph) -> ComplexityStats:
    """Collect complexity statistics from an RDF graph.

    Args:
        graph: RDF graph to analyse.

    Returns:
        ComplexityStats with all complexity metrics populated.
    """
    classes = _get_all_classes(graph)
    total_classes = len(classes)

    if total_classes == 0:
        return ComplexityStats()

    # Properties per class
    prop_counts = _count_properties_per_class(graph, classes)
    total_prop_refs = sum(prop_counts.values())
    avg_props = total_prop_refs / total_classes if total_classes else 0.0

    # Superclasses per class
    super_counts = _count_superclasses(graph, classes)
    total_supers = sum(super_counts.values())
    avg_supers = total_supers / total_classes if total_classes else 0.0

    # Multiple inheritance
    multi_inherit = _count_multiple_inheritance(super_counts)

    # OWL restrictions
    restrictions = len(set(graph.subjects(RDF.type, OWL.Restriction)))

    # Equivalent class statements
    equivalents = len(list(graph.triples((None, OWL.equivalentClass, None))))

    return ComplexityStats(
        avg_properties_per_class=round(avg_props, 2),
        avg_superclasses_per_class=round(avg_supers, 2),
        multiple_inheritance_count=multi_inherit,
        owl_restriction_count=restrictions,
        owl_equivalent_count=equivalents,
    )
