"""Basic metrics collection for ontology description.

Provides counts of classes, properties, individuals, and triples.
"""

from rdflib import Graph, RDF, RDFS
from rdflib.namespace import OWL

from rdf_construct.describe.models import BasicMetrics


def collect_metrics(graph: Graph) -> BasicMetrics:
    """Collect basic count metrics from an RDF graph.

    Args:
        graph: RDF graph to analyse.

    Returns:
        BasicMetrics with all count values populated.
    """
    # Total triples
    total_triples = len(graph)

    # Classes: both owl:Class and rdfs:Class (deduplicated)
    owl_classes = set(graph.subjects(RDF.type, OWL.Class))
    rdfs_classes = set(graph.subjects(RDF.type, RDFS.Class))
    all_classes = owl_classes | rdfs_classes
    classes = len(all_classes)

    # Object properties
    object_properties = len(set(graph.subjects(RDF.type, OWL.ObjectProperty)))

    # Datatype properties
    datatype_properties = len(set(graph.subjects(RDF.type, OWL.DatatypeProperty)))

    # Annotation properties
    annotation_properties = len(set(graph.subjects(RDF.type, OWL.AnnotationProperty)))

    # RDF properties (rdf:Property not typed as OWL property)
    all_rdf_props = set(graph.subjects(RDF.type, RDF.Property))
    owl_props = (
        set(graph.subjects(RDF.type, OWL.ObjectProperty))
        | set(graph.subjects(RDF.type, OWL.DatatypeProperty))
        | set(graph.subjects(RDF.type, OWL.AnnotationProperty))
    )
    rdf_properties = len(all_rdf_props - owl_props)

    # Individuals: typed subjects that aren't classes, properties, or ontology
    individuals = _count_individuals(graph, all_classes)

    return BasicMetrics(
        total_triples=total_triples,
        classes=classes,
        object_properties=object_properties,
        datatype_properties=datatype_properties,
        annotation_properties=annotation_properties,
        rdf_properties=rdf_properties,
        individuals=individuals,
    )


def _count_individuals(graph: Graph, classes: set) -> int:
    """Count named individuals in the graph.

    Individuals are typed subjects that are not classes, properties,
    or ontology declarations.

    Args:
        graph: RDF graph to analyse.
        classes: Set of class URIs already identified.

    Returns:
        Count of named individuals.
    """
    # Gather all property URIs
    properties = (
        set(graph.subjects(RDF.type, OWL.ObjectProperty))
        | set(graph.subjects(RDF.type, OWL.DatatypeProperty))
        | set(graph.subjects(RDF.type, OWL.AnnotationProperty))
        | set(graph.subjects(RDF.type, RDF.Property))
    )

    # Ontology declarations
    ontologies = set(graph.subjects(RDF.type, OWL.Ontology))

    # OWL constructs that shouldn't be counted as individuals
    owl_constructs = {
        OWL.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        OWL.Restriction,
        OWL.Ontology,
        OWL.AllDisjointClasses,
        OWL.AllDifferent,
        OWL.NamedIndividual,
        RDFS.Class,
        RDF.Property,
    }

    # Collect all typed subjects
    all_typed = set()
    for s in graph.subjects(RDF.type, None):
        # Skip blank nodes for counting
        if hasattr(s, "n3") and not str(s).startswith("_:"):
            all_typed.add(s)

    # Exclude non-individuals
    individuals = all_typed - classes - properties - ontologies - owl_constructs

    return len(individuals)


def get_all_classes(graph: Graph) -> set:
    """Get all classes from the graph.

    Args:
        graph: RDF graph to query.

    Returns:
        Set of class URIRefs (owl:Class and rdfs:Class).
    """
    owl_classes = set(graph.subjects(RDF.type, OWL.Class))
    rdfs_classes = set(graph.subjects(RDF.type, RDFS.Class))
    return owl_classes | rdfs_classes


def get_all_properties(graph: Graph) -> set:
    """Get all properties from the graph.

    Args:
        graph: RDF graph to query.

    Returns:
        Set of property URIRefs (all types).
    """
    props = set()
    for prop_type in (
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        RDF.Property,
    ):
        props |= set(graph.subjects(RDF.type, prop_type))
    return props
