"""Basic count metrics for RDF ontologies.

Provides fundamental counts: triples, classes, properties, individuals.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from rdflib import Graph, RDF
from rdflib.namespace import OWL
from rdflib.term import Node

from rdf_construct.core.ownership import ownership
from rdf_construct.core.vocab import (
    ALL_PROPERTY_TYPES,
    ANNOTATION_PROPERTY_TYPES,
    CLASS_TYPES,
    DATATYPE_PROPERTY_TYPES,
    GENERIC_PROPERTY_TYPES,
    KIND_SPECIFIC_PROPERTY_TYPES,
    OBJECT_PROPERTY_TYPES,
)


@dataclass
class BasicStats:
    """Basic count statistics for an ontology.

    Every count is of the ontology's own terms, classified by `rdf_construct.core.vocab` (#138).
    A term declared with two kinds (an object and a datatype property, or a class punned as a
    property) is counted under each.

    Attributes:
        triples: Total number of triples in the graph.
        classes: Number of terms typed with a `CLASS_TYPES` type (``owl:Class``,
            ``rdfs:Class``, ``owl:DeprecatedClass``).
        object_properties: Number of terms typed with an `OBJECT_PROPERTY_TYPES` type, the OWL
            characteristics that imply an object property included.
        datatype_properties: Number of owl:DatatypeProperty entities.
        annotation_properties: Number of owl:AnnotationProperty entities.
        other_properties: Number of properties whose kind the source does not declare: typed
            ``rdf:Property``, ``owl:FunctionalProperty`` or ``owl:DeprecatedProperty`` and no
            kind-specific type.
        individuals: Number of individuals: typed subjects that are neither classes nor
            properties, and terms explicitly typed ``owl:NamedIndividual``.
    """

    triples: int = 0
    classes: int = 0
    object_properties: int = 0
    datatype_properties: int = 0
    annotation_properties: int = 0
    individuals: int = 0
    other_properties: int = 0

    @property
    def total_properties(self) -> int:
        """Sum of the four property counts; a term of two kinds counts in both."""
        return (
            self.object_properties
            + self.datatype_properties
            + self.annotation_properties
            + self.other_properties
        )


def _declared(graph: Graph, types: Iterable[Node]) -> set[Node]:
    """Every subject typed with one of ``types``, the ontology's own or not."""
    subjects: set[Node] = set()
    for rdf_type in types:
        subjects |= set(graph.subjects(RDF.type, rdf_type))
    return subjects


def _declared_classes(graph: Graph) -> set[Node]:
    """Every subject typed as a class (`CLASS_TYPES`), the ontology's own or not."""
    return _declared(graph, CLASS_TYPES)


def _declared_properties(graph: Graph) -> set[Node]:
    """Every subject typed as a property (`ALL_PROPERTY_TYPES`), the ontology's own or not."""
    return _declared(graph, ALL_PROPERTY_TYPES)


def _own(graph: Graph, terms: set[Node]) -> set[Node]:
    """The terms that are the ontology's own: not a borrowed vocabulary's it declares (#371)."""
    owned = ownership(graph)
    return {t for t in terms if not owned.is_foreign(t)}


def get_all_classes(graph: Graph) -> set:
    """Get all classes from the graph: subjects of any `CLASS_TYPES` type.

    Args:
        graph: RDF graph to query.

    Returns:
        Set of class URIRefs, except those that are not the ontology's own
        (`rdf_construct.core.ownership`).
    """
    return _own(graph, _declared_classes(graph))


def get_all_properties(graph: Graph) -> set:
    """Get all properties from the graph: subjects of any `ALL_PROPERTY_TYPES` type.

    Args:
        graph: RDF graph to query.

    Returns:
        Set of property URIRefs, of all four kinds (object, datatype, annotation and other),
        except those that are not the ontology's own (`rdf_construct.core.ownership`).
    """
    return _own(graph, _declared_properties(graph))


def get_other_properties(graph: Graph) -> set[Node]:
    """Get the properties whose kind the source does not declare.

    A subject of a `GENERIC_PROPERTY_TYPES` type (``rdf:Property``, ``owl:FunctionalProperty``,
    ``owl:DeprecatedProperty``) and of no kind-specific one, as ``order``'s ``other_props``
    selector has it.

    Args:
        graph: RDF graph to query.

    Returns:
        Set of property URIRefs, except those that are not the ontology's own.
    """
    generic = _declared(graph, GENERIC_PROPERTY_TYPES)
    return _own(graph, generic - _declared(graph, KIND_SPECIFIC_PROPERTY_TYPES))


def get_individuals(graph: Graph) -> set:
    """Get all individuals from the graph.

    Individuals are subjects that are typed but not classes or properties, and the ontology's
    own terms explicitly typed ``owl:NamedIndividual``, which a class or property may also be
    (OWL 2 punning).

    Args:
        graph: RDF graph to query.

    Returns:
        Set of individual URIRefs.
    """
    # Every declared class and property is excluded, the ontology's own or not: a borrowed
    # vocabulary's term is left out of the counts, never moved into this one (#371)
    classes = _declared_classes(graph)
    properties = _declared_properties(graph)

    # Get all typed subjects. Blank nodes are kept: an anonymous individual is one, and so,
    # wrongly, is an OWL restriction or axiom (#529)
    all_typed = set()
    for s in graph.subjects(RDF.type, None):
        if hasattr(s, "n3"):
            all_typed.add(s)

    # Exclude classes, properties, and ontology declarations
    ontologies = set(graph.subjects(RDF.type, OWL.Ontology))
    individuals = all_typed - classes - properties - ontologies

    # Also exclude property types themselves and OWL constructs
    owl_constructs = CLASS_TYPES | ALL_PROPERTY_TYPES | {OWL.Restriction, OWL.Ontology}
    individuals = {i for i in individuals if i not in owl_constructs}

    # A class or property the source also declares an individual is one (punning)
    named = set(graph.subjects(RDF.type, OWL.NamedIndividual)) & (classes | properties)
    individuals |= _own(graph, named)

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

    # Classes (every CLASS_TYPES type)
    classes = len(get_all_classes(graph))

    # Object properties, the characteristics that imply one included
    obj_props = len(_own(graph, _declared(graph, OBJECT_PROPERTY_TYPES)))

    # Datatype properties
    data_props = len(_own(graph, _declared(graph, DATATYPE_PROPERTY_TYPES)))

    # Annotation properties
    ann_props = len(_own(graph, _declared(graph, ANNOTATION_PROPERTY_TYPES)))

    # Properties whose kind is not declared
    other_props = len(get_other_properties(graph))

    # Individuals
    individuals = len(get_individuals(graph))

    return BasicStats(
        triples=triples,
        classes=classes,
        object_properties=obj_props,
        datatype_properties=data_props,
        annotation_properties=ann_props,
        individuals=individuals,
        other_properties=other_props,
    )
