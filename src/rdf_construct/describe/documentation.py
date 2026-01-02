"""Documentation coverage analysis for ontology description.

Analyses the presence of labels and definitions for classes and properties.
"""

from rdflib import Graph, URIRef, RDF, RDFS
from rdflib.namespace import OWL

from rdf_construct.describe.models import DocumentationCoverage


# Predicates considered as providing a label
LABEL_PREDICATES = {
    RDFS.label,
    URIRef("http://www.w3.org/2004/02/skos/core#prefLabel"),
    URIRef("http://www.w3.org/2004/02/skos/core#altLabel"),
    URIRef("http://purl.org/dc/elements/1.1/title"),
    URIRef("http://purl.org/dc/terms/title"),
}

# Predicates considered as providing a definition/description
DEFINITION_PREDICATES = {
    RDFS.comment,
    URIRef("http://www.w3.org/2004/02/skos/core#definition"),
    URIRef("http://purl.org/dc/elements/1.1/description"),
    URIRef("http://purl.org/dc/terms/description"),
}


def analyse_documentation(graph: Graph) -> DocumentationCoverage:
    """Analyse documentation coverage for classes and properties.

    Args:
        graph: RDF graph to analyse.

    Returns:
        DocumentationCoverage with coverage metrics.
    """
    # Get all classes
    classes = _get_all_classes(graph)
    classes_total = len(classes)

    # Get all properties
    properties = _get_all_properties(graph)
    properties_total = len(properties)

    # Count classes with labels
    classes_with_label = sum(1 for cls in classes if _has_label(graph, cls))

    # Count classes with definitions
    classes_with_definition = sum(1 for cls in classes if _has_definition(graph, cls))

    # Count properties with labels
    properties_with_label = sum(1 for prop in properties if _has_label(graph, prop))

    # Count properties with definitions
    properties_with_definition = sum(
        1 for prop in properties if _has_definition(graph, prop)
    )

    return DocumentationCoverage(
        classes_with_label=classes_with_label,
        classes_total=classes_total,
        classes_with_definition=classes_with_definition,
        properties_with_label=properties_with_label,
        properties_total=properties_total,
        properties_with_definition=properties_with_definition,
    )


def _get_all_classes(graph: Graph) -> set[URIRef]:
    """Get all classes from the graph.

    Args:
        graph: RDF graph to query.

    Returns:
        Set of class URIRefs.
    """
    classes: set[URIRef] = set()

    for cls in graph.subjects(RDF.type, OWL.Class):
        if isinstance(cls, URIRef):
            classes.add(cls)

    for cls in graph.subjects(RDF.type, RDFS.Class):
        if isinstance(cls, URIRef):
            classes.add(cls)

    return classes


def _get_all_properties(graph: Graph) -> set[URIRef]:
    """Get all properties from the graph.

    Args:
        graph: RDF graph to query.

    Returns:
        Set of property URIRefs.
    """
    properties: set[URIRef] = set()

    for prop_type in (
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        RDF.Property,
    ):
        for prop in graph.subjects(RDF.type, prop_type):
            if isinstance(prop, URIRef):
                properties.add(prop)

    return properties


def _has_label(graph: Graph, subject: URIRef) -> bool:
    """Check if a subject has any label predicate.

    Args:
        graph: RDF graph to query.
        subject: Subject to check.

    Returns:
        True if subject has at least one label.
    """
    for pred in LABEL_PREDICATES:
        if any(graph.objects(subject, pred)):
            return True
    return False


def _has_definition(graph: Graph, subject: URIRef) -> bool:
    """Check if a subject has any definition/description predicate.

    Args:
        graph: RDF graph to query.
        subject: Subject to check.

    Returns:
        True if subject has at least one definition.
    """
    for pred in DEFINITION_PREDICATES:
        if any(graph.objects(subject, pred)):
            return True
    return False
