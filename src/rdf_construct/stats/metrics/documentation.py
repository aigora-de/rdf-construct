"""Documentation metrics for RDF ontologies.

Analyses documentation coverage: labels, comments, definitions.
"""

from dataclasses import dataclass

from rdflib import Graph, RDF, RDFS, Namespace
from rdflib.namespace import OWL, DCTERMS


# Common documentation namespaces
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


@dataclass
class DocumentationStats:
    """Documentation statistics for an ontology.

    Attributes:
        classes_labelled: Classes with rdfs:label or skos:prefLabel.
        classes_labelled_pct: Proportion of classes with labels (0.0 - 1.0).
        classes_documented: Classes with rdfs:comment or skos:definition.
        classes_documented_pct: Proportion of classes with documentation (0.0 - 1.0).
        properties_labelled: Properties with labels.
        properties_labelled_pct: Proportion of properties with labels (0.0 - 1.0).
    """

    classes_labelled: int = 0
    classes_labelled_pct: float = 0.0
    classes_documented: int = 0
    classes_documented_pct: float = 0.0
    properties_labelled: int = 0
    properties_labelled_pct: float = 0.0


# Predicates considered as labels
LABEL_PREDICATES = (
    RDFS.label,
    SKOS.prefLabel,
)

# Predicates considered as documentation
DOC_PREDICATES = (
    RDFS.comment,
    SKOS.definition,
    DCTERMS.description,
)


def _get_all_classes(graph: Graph) -> set:
    """Get all classes from the graph."""
    classes = set(graph.subjects(RDF.type, OWL.Class))
    classes |= set(graph.subjects(RDF.type, RDFS.Class))
    return classes


def _get_all_properties(graph: Graph) -> set:
    """Get all properties from the graph."""
    props = set()
    for prop_type in (
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        RDF.Property,
    ):
        props |= set(graph.subjects(RDF.type, prop_type))
    return props


def _has_any_predicate(graph: Graph, subject: object, predicates: tuple) -> bool:
    """Check if subject has any of the given predicates.

    Args:
        graph: RDF graph to query.
        subject: Subject to check.
        predicates: Tuple of predicates to look for.

    Returns:
        True if subject has at least one of the predicates.
    """
    for pred in predicates:
        if graph.value(subject, pred) is not None:
            return True
    return False


def collect_documentation_stats(graph: Graph) -> DocumentationStats:
    """Collect documentation statistics from an RDF graph.

    Args:
        graph: RDF graph to analyse.

    Returns:
        DocumentationStats with all documentation metrics populated.
    """
    classes = _get_all_classes(graph)
    properties = _get_all_properties(graph)

    total_classes = len(classes)
    total_props = len(properties)

    if total_classes == 0 and total_props == 0:
        return DocumentationStats()

    # Count classes with labels
    classes_with_label = sum(
        1 for c in classes if _has_any_predicate(graph, c, LABEL_PREDICATES)
    )

    # Count classes with documentation
    classes_with_doc = sum(
        1 for c in classes if _has_any_predicate(graph, c, DOC_PREDICATES)
    )

    # Count properties with labels
    props_with_label = sum(
        1 for p in properties if _has_any_predicate(graph, p, LABEL_PREDICATES)
    )

    return DocumentationStats(
        classes_labelled=classes_with_label,
        classes_labelled_pct=round(classes_with_label / total_classes, 3) if total_classes else 0.0,
        classes_documented=classes_with_doc,
        classes_documented_pct=round(classes_with_doc / total_classes, 3) if total_classes else 0.0,
        properties_labelled=props_with_label,
        properties_labelled_pct=round(props_with_label / total_props, 3) if total_props else 0.0,
    )
