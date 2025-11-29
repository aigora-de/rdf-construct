"""Predicate ordering configuration and logic for RDF serialisation.

Controls the order in which predicates (properties) appear when serialising
RDF subjects. Supports different orderings for different subject types
(classes, properties, individuals).
"""

from dataclasses import dataclass, field
from typing import Any

from rdflib import Graph, RDF, RDFS, URIRef
from rdflib.namespace import OWL


@dataclass
class PredicateOrderSpec:
    """Ordering specification for predicates of a particular subject type.

    Attributes:
        first: Predicates to appear first, in order (after rdf:type)
        last: Predicates to appear last, in order
    """

    first: list[str] = field(default_factory=list)
    last: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PredicateOrderSpec":
        """Create from dictionary configuration.

        Args:
            data: Dictionary with 'first' and/or 'last' keys

        Returns:
            PredicateOrderSpec instance
        """
        if not data:
            return cls()
        return cls(
            first=data.get("first", []) or [],
            last=data.get("last", []) or [],
        )


@dataclass
class PredicateOrderConfig:
    """Configuration for predicate ordering across subject types.

    Defines how predicates should be ordered for different types of
    RDF subjects (classes, properties, individuals).

    Attributes:
        classes: Ordering for owl:Class and rdfs:Class subjects
        properties: Ordering for property subjects (ObjectProperty, etc.)
        individuals: Ordering for individual/instance subjects
        default: Fallback ordering for unmatched subject types
    """

    classes: PredicateOrderSpec = field(default_factory=PredicateOrderSpec)
    properties: PredicateOrderSpec = field(default_factory=PredicateOrderSpec)
    individuals: PredicateOrderSpec = field(default_factory=PredicateOrderSpec)
    default: PredicateOrderSpec = field(default_factory=PredicateOrderSpec)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PredicateOrderConfig":
        """Create from dictionary configuration.

        Args:
            data: Dictionary with subject type keys (classes, properties, etc.)

        Returns:
            PredicateOrderConfig instance
        """
        if not data:
            return cls()
        return cls(
            classes=PredicateOrderSpec.from_dict(data.get("classes")),
            properties=PredicateOrderSpec.from_dict(data.get("properties")),
            individuals=PredicateOrderSpec.from_dict(data.get("individuals")),
            default=PredicateOrderSpec.from_dict(data.get("default")),
        )

    def get_spec_for_type(self, subject_type: str) -> PredicateOrderSpec:
        """Get the predicate ordering spec for a subject type.

        Args:
            subject_type: One of 'class', 'property', 'individual', or other

        Returns:
            Appropriate PredicateOrderSpec for the subject type
        """
        if subject_type == "class":
            return self.classes if self.classes.first or self.classes.last else self.default
        elif subject_type == "property":
            return self.properties if self.properties.first or self.properties.last else self.default
        elif subject_type == "individual":
            return self.individuals if self.individuals.first or self.individuals.last else self.default
        else:
            return self.default


def classify_subject(graph: Graph, subject: URIRef) -> str:
    """Determine the type category of an RDF subject.

    Classifies subjects into one of: 'class', 'property', 'individual'.

    Args:
        graph: RDF graph containing the subject
        subject: The subject URI to classify

    Returns:
        Subject type: 'class', 'property', or 'individual'
    """
    types = set(graph.objects(subject, RDF.type))

    # Check if it's a class
    if OWL.Class in types or RDFS.Class in types:
        return "class"

    # Check if it's a property
    property_types = {
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        RDF.Property,
    }
    if types & property_types:
        return "property"

    # Default to individual
    return "individual"


def expand_curie(graph: Graph, curie: str) -> URIRef | None:
    """Expand a CURIE (prefix:local) to a full URI.

    Args:
        graph: RDF graph with namespace bindings
        curie: CURIE string like 'rdfs:label'

    Returns:
        Expanded URIRef, or None if prefix not found
    """
    if ":" not in curie:
        return None

    prefix, local = curie.split(":", 1)
    for bound_prefix, namespace in graph.namespace_manager.namespaces():
        if bound_prefix == prefix:
            return URIRef(str(namespace) + local)
    return None


def order_predicates(
    graph: Graph,
    predicates: list[URIRef],
    spec: PredicateOrderSpec,
    format_fn: callable,
) -> list[URIRef]:
    """Order predicates according to a specification.

    Ordering logic:
    1. rdf:type always first (handled by caller)
    2. 'first' predicates in specified order
    3. Remaining predicates sorted alphabetically by QName
    4. 'last' predicates in specified order

    Args:
        graph: RDF graph with namespace bindings
        predicates: List of predicate URIs to order
        spec: Predicate ordering specification
        format_fn: Function to format URIRef as string (for sorting)

    Returns:
        Ordered list of predicates
    """
    # Expand CURIEs to URIs
    first_uris = [expand_curie(graph, c) for c in spec.first]
    first_uris = [u for u in first_uris if u is not None]

    last_uris = [expand_curie(graph, c) for c in spec.last]
    last_uris = [u for u in last_uris if u is not None]

    # Build sets for quick lookup
    first_set = set(first_uris)
    last_set = set(last_uris)
    special_set = first_set | last_set | {RDF.type}

    # Partition predicates
    first_found = []
    middle = []
    last_found = []

    # Collect 'first' predicates in specified order
    for uri in first_uris:
        if uri in predicates:
            first_found.append(uri)

    # Collect 'last' predicates in specified order
    for uri in last_uris:
        if uri in predicates:
            last_found.append(uri)

    # Collect middle predicates (everything else except rdf:type)
    for pred in predicates:
        if pred not in special_set:
            middle.append(pred)

    # Sort middle predicates alphabetically by QName
    middle.sort(key=lambda x: format_fn(x))

    return first_found + middle + last_found
