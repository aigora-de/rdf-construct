"""Basic count metrics for RDF ontologies.

Provides fundamental counts: triples, classes, properties, individuals.
"""

from dataclasses import dataclass, field

from rdflib import Graph, RDF, RDFS
from rdflib.namespace import OWL


@dataclass
class BasicStats:
    """Basic count statistics for an ontology.

    Attributes:
        triples: Total number of triples in the graph.
        classes: Number of owl:Class + rdfs:Class entities.
        object_properties: Number of owl:ObjectProperty entities.
        datatype_properties: Number of owl:DatatypeProperty entities.
        annotation_properties: Number of owl:AnnotationProperty entities.
        individuals: Number of named individuals (non-class, non-property).
    """

    triples: int = 0
    classes: int = 0
    object_properties: int = 0
    datatype_properties: int = 0
    annotation_properties: int = 0
    individuals: int = 0

    @property
    def total_properties(self) -> int:
        """Total count of all property types."""
        return self.object_properties + self.datatype_properties + self.annotation_properties


def get_all_classes(graph: Graph) -> set:
    """Get all classes from the graph (owl:Class + rdfs:Class).

    Args:
        graph: RDF graph to query.

    Returns:
        Set of class URIRefs.
    """
    classes = set(graph.subjects(RDF.type, OWL.Class))
    classes |= set(graph.subjects(RDF.type, RDFS.Class))
    return classes


def get_all_properties(graph: Graph) -> set:
    """Get all properties from the graph.

    Args:
        graph: RDF graph to query.

    Returns:
        Set of property URIRefs (object, datatype, annotation).
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


def get_individuals(graph: Graph) -> set:
    """Get all named individuals from the graph.

    Individuals are subjects that are typed but not classes or properties.

    Args:
        graph: RDF graph to query.

    Returns:
        Set of individual URIRefs.
    """
    classes = get_all_classes(graph)
    properties = get_all_properties(graph)

    # Get all typed subjects
    all_typed = set()
    for s in graph.subjects(RDF.type, None):
        # Skip blank nodes and literal subjects
        if hasattr(s, "n3"):
            all_typed.add(s)

    # Exclude classes, properties, and ontology declarations
    ontologies = set(graph.subjects(RDF.type, OWL.Ontology))
    individuals = all_typed - classes - properties - ontologies

    # Also exclude property types themselves and OWL constructs
    owl_constructs = {
        OWL.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        OWL.Restriction,
        OWL.Ontology,
        RDFS.Class,
        RDF.Property,
    }
    individuals = {i for i in individuals if i not in owl_constructs}

    return individuals


def collect_basic_stats(graph: Graph) -> BasicStats:
    """Collect basic count statistics from an RDF graph.

    Args:
        graph: RDF graph to analyse.

    Returns:
        BasicStats with all count metrics populated.
    """
    # Total triples
    triples = len(graph)

    # Classes (both owl:Class and rdfs:Class)
    classes = len(get_all_classes(graph))

    # Object properties
    obj_props = len(set(graph.subjects(RDF.type, OWL.ObjectProperty)))

    # Datatype properties
    data_props = len(set(graph.subjects(RDF.type, OWL.DatatypeProperty)))

    # Annotation properties
    ann_props = len(set(graph.subjects(RDF.type, OWL.AnnotationProperty)))

    # Individuals
    individuals = len(get_individuals(graph))

    return BasicStats(
        triples=triples,
        classes=classes,
        object_properties=obj_props,
        datatype_properties=data_props,
        annotation_properties=ann_props,
        individuals=individuals,
    )
