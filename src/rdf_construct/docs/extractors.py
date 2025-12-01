"""Entity extraction from RDF graphs for documentation generation.

Extracts comprehensive information about classes, properties, and instances
from RDF ontologies for use in generating navigable documentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rdflib import RDF, RDFS, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, SKOS

if TYPE_CHECKING:
    from rdflib import Graph


# Common annotation predicates for extracting labels and definitions
LABEL_PREDICATES = [
    RDFS.label,
    SKOS.prefLabel,
    DCTERMS.title,
]

DEFINITION_PREDICATES = [
    RDFS.comment,
    SKOS.definition,
    DCTERMS.description,
]


@dataclass
class PropertyInfo:
    """Information about an RDF property for documentation."""

    uri: URIRef
    qname: str
    label: str | None = None
    definition: str | None = None
    property_type: str = "property"  # object, datatype, annotation, rdf
    domain: list[URIRef] = field(default_factory=list)
    range: list[URIRef] = field(default_factory=list)
    superproperties: list[URIRef] = field(default_factory=list)
    subproperties: list[URIRef] = field(default_factory=list)
    annotations: dict[str, list[str]] = field(default_factory=dict)
    is_functional: bool = False
    is_inverse_functional: bool = False
    inverse_of: URIRef | None = None


@dataclass
class ClassInfo:
    """Information about an RDF class for documentation."""

    uri: URIRef
    qname: str
    label: str | None = None
    definition: str | None = None
    superclasses: list[URIRef] = field(default_factory=list)
    subclasses: list[URIRef] = field(default_factory=list)
    domain_of: list[PropertyInfo] = field(default_factory=list)
    range_of: list[PropertyInfo] = field(default_factory=list)
    inherited_properties: list[PropertyInfo] = field(default_factory=list)
    annotations: dict[str, list[str]] = field(default_factory=dict)
    instances: list[URIRef] = field(default_factory=list)
    disjoint_with: list[URIRef] = field(default_factory=list)
    equivalent_to: list[URIRef] = field(default_factory=list)


@dataclass
class InstanceInfo:
    """Information about an RDF instance for documentation."""

    uri: URIRef
    qname: str
    label: str | None = None
    definition: str | None = None
    types: list[URIRef] = field(default_factory=list)
    properties: dict[URIRef, list[str | URIRef]] = field(default_factory=dict)
    annotations: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class OntologyInfo:
    """Information about the ontology itself for documentation."""

    uri: URIRef | None = None
    title: str | None = None
    description: str | None = None
    version: str | None = None
    creators: list[str] = field(default_factory=list)
    contributors: list[str] = field(default_factory=list)
    imports: list[URIRef] = field(default_factory=list)
    namespaces: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, list[str]] = field(default_factory=dict)


def get_qname(graph: Graph, uri: URIRef) -> str:
    """Get a qualified name (CURIE) for a URI.

    Args:
        graph: RDF graph with namespace bindings.
        uri: URI to convert to QName.

    Returns:
        QName string like 'ex:Building' or the full URI if no prefix matches.
    """
    try:
        qname = graph.namespace_manager.qname(uri)
        return str(qname)
    except (ValueError, KeyError):
        return str(uri)


def get_label(graph: Graph, uri: URIRef, lang: str | None = "en") -> str | None:
    """Extract the best label for an entity.

    Tries multiple predicates in order of preference, optionally
    filtering by language tag.

    Args:
        graph: RDF graph to query.
        uri: Entity URI to find label for.
        lang: Preferred language tag (None for any).

    Returns:
        Label string or None if not found.
    """
    for pred in LABEL_PREDICATES:
        for obj in graph.objects(uri, pred):
            if isinstance(obj, Literal):
                if lang is None or obj.language == lang or obj.language is None:
                    return str(obj)
    # Fallback: try any language
    if lang is not None:
        return get_label(graph, uri, lang=None)
    return None


def get_definition(graph: Graph, uri: URIRef, lang: str | None = "en") -> str | None:
    """Extract the best definition/comment for an entity.

    Args:
        graph: RDF graph to query.
        uri: Entity URI to find definition for.
        lang: Preferred language tag (None for any).

    Returns:
        Definition string or None if not found.
    """
    for pred in DEFINITION_PREDICATES:
        for obj in graph.objects(uri, pred):
            if isinstance(obj, Literal):
                if lang is None or obj.language == lang or obj.language is None:
                    return str(obj)
    # Fallback: try any language
    if lang is not None:
        return get_definition(graph, uri, lang=None)
    return None


def get_annotations(graph: Graph, uri: URIRef) -> dict[str, list[str]]:
    """Extract all annotation values for an entity.

    Collects values from common annotation predicates, grouped by
    the predicate's local name.

    Args:
        graph: RDF graph to query.
        uri: Entity URI to extract annotations from.

    Returns:
        Dictionary mapping annotation names to lists of values.
    """
    annotations: dict[str, list[str]] = {}

    # Standard annotation predicates to extract
    annotation_preds = [
        (RDFS.seeAlso, "seeAlso"),
        (RDFS.isDefinedBy, "isDefinedBy"),
        (OWL.versionInfo, "versionInfo"),
        (OWL.deprecated, "deprecated"),
        (SKOS.example, "example"),
        (SKOS.note, "note"),
        (SKOS.historyNote, "historyNote"),
        (SKOS.editorialNote, "editorialNote"),
        (SKOS.changeNote, "changeNote"),
        (SKOS.scopeNote, "scopeNote"),
        (DCTERMS.creator, "creator"),
        (DCTERMS.created, "created"),
        (DCTERMS.modified, "modified"),
        (DCTERMS.source, "source"),
    ]

    for pred, name in annotation_preds:
        values = []
        for obj in graph.objects(uri, pred):
            if isinstance(obj, Literal):
                values.append(str(obj))
            elif isinstance(obj, URIRef):
                values.append(str(obj))
        if values:
            annotations[name] = values

    return annotations


def extract_ontology_info(graph: Graph) -> OntologyInfo:
    """Extract metadata about the ontology itself.

    Args:
        graph: RDF graph to extract ontology info from.

    Returns:
        OntologyInfo with ontology-level metadata.
    """
    info = OntologyInfo()

    # Find ontology URI
    for s in graph.subjects(RDF.type, OWL.Ontology):
        if isinstance(s, URIRef):
            info.uri = s
            break

    if info.uri:
        # Title
        info.title = get_label(graph, info.uri)
        if not info.title:
            # Try dcterms:title
            for obj in graph.objects(info.uri, DCTERMS.title):
                if isinstance(obj, Literal):
                    info.title = str(obj)
                    break

        # Description
        info.description = get_definition(graph, info.uri)

        # Version
        for obj in graph.objects(info.uri, OWL.versionInfo):
            if isinstance(obj, Literal):
                info.version = str(obj)
                break

        # Creators
        for obj in graph.objects(info.uri, DCTERMS.creator):
            if isinstance(obj, Literal):
                info.creators.append(str(obj))
            elif isinstance(obj, URIRef):
                info.creators.append(str(obj))

        # Contributors
        for obj in graph.objects(info.uri, DCTERMS.contributor):
            if isinstance(obj, Literal):
                info.contributors.append(str(obj))
            elif isinstance(obj, URIRef):
                info.contributors.append(str(obj))

        # Imports
        for obj in graph.objects(info.uri, OWL.imports):
            if isinstance(obj, URIRef):
                info.imports.append(obj)

        # Annotations
        info.annotations = get_annotations(graph, info.uri)

    # Namespaces - only include those actually used in triples
    used_uris: set[str] = set()
    for s, p, o in graph:
        if isinstance(s, URIRef):
            used_uris.add(str(s))
        if isinstance(p, URIRef):
            used_uris.add(str(p))
        if isinstance(o, URIRef):
            used_uris.add(str(o))

    # Only include namespaces that match at least one used URI
    for prefix, namespace in graph.namespaces():
        ns_str = str(namespace)
        if any(uri.startswith(ns_str) for uri in used_uris):
            info.namespaces[prefix] = ns_str

    return info


def extract_class_info(graph: Graph, uri: URIRef) -> ClassInfo:
    """Extract comprehensive information about a class.

    Args:
        graph: RDF graph to query.
        uri: Class URI to extract info for.

    Returns:
        ClassInfo with all available metadata.
    """
    info = ClassInfo(
        uri=uri,
        qname=get_qname(graph, uri),
        label=get_label(graph, uri),
        definition=get_definition(graph, uri),
        annotations=get_annotations(graph, uri),
    )

    # Superclasses (direct)
    for obj in graph.objects(uri, RDFS.subClassOf):
        if isinstance(obj, URIRef):
            info.superclasses.append(obj)

    # Subclasses (direct)
    for subj in graph.subjects(RDFS.subClassOf, uri):
        if isinstance(subj, URIRef):
            info.subclasses.append(subj)

    # Properties with this class as domain
    for prop in graph.subjects(RDFS.domain, uri):
        if isinstance(prop, URIRef):
            prop_info = extract_property_info(graph, prop)
            info.domain_of.append(prop_info)

    # Properties with this class as range
    for prop in graph.subjects(RDFS.range, uri):
        if isinstance(prop, URIRef):
            prop_info = extract_property_info(graph, prop)
            info.range_of.append(prop_info)

    # Instances of this class
    for inst in graph.subjects(RDF.type, uri):
        if isinstance(inst, URIRef):
            # Skip if it's a class itself
            if (inst, RDF.type, OWL.Class) in graph:
                continue
            if (inst, RDF.type, RDFS.Class) in graph:
                continue
            info.instances.append(inst)

    # Disjoint classes
    for obj in graph.objects(uri, OWL.disjointWith):
        if isinstance(obj, URIRef):
            info.disjoint_with.append(obj)

    # Equivalent classes
    for obj in graph.objects(uri, OWL.equivalentClass):
        if isinstance(obj, URIRef):
            info.equivalent_to.append(obj)

    return info


def extract_property_info(graph: Graph, uri: URIRef) -> PropertyInfo:
    """Extract comprehensive information about a property.

    Args:
        graph: RDF graph to query.
        uri: Property URI to extract info for.

    Returns:
        PropertyInfo with all available metadata.
    """
    info = PropertyInfo(
        uri=uri,
        qname=get_qname(graph, uri),
        label=get_label(graph, uri),
        definition=get_definition(graph, uri),
        annotations=get_annotations(graph, uri),
    )

    # Determine property type
    if (uri, RDF.type, OWL.ObjectProperty) in graph:
        info.property_type = "object"
    elif (uri, RDF.type, OWL.DatatypeProperty) in graph:
        info.property_type = "datatype"
    elif (uri, RDF.type, OWL.AnnotationProperty) in graph:
        info.property_type = "annotation"
    elif (uri, RDF.type, RDF.Property) in graph:
        info.property_type = "rdf"

    # Domain
    for obj in graph.objects(uri, RDFS.domain):
        if isinstance(obj, URIRef):
            info.domain.append(obj)

    # Range
    for obj in graph.objects(uri, RDFS.range):
        if isinstance(obj, URIRef):
            info.range.append(obj)

    # Superproperties
    for obj in graph.objects(uri, RDFS.subPropertyOf):
        if isinstance(obj, URIRef):
            info.superproperties.append(obj)

    # Subproperties
    for subj in graph.subjects(RDFS.subPropertyOf, uri):
        if isinstance(subj, URIRef):
            info.subproperties.append(subj)

    # Functional property
    info.is_functional = (uri, RDF.type, OWL.FunctionalProperty) in graph

    # Inverse functional property
    info.is_inverse_functional = (uri, RDF.type, OWL.InverseFunctionalProperty) in graph

    # Inverse of
    for obj in graph.objects(uri, OWL.inverseOf):
        if isinstance(obj, URIRef):
            info.inverse_of = obj
            break

    return info


def extract_instance_info(graph: Graph, uri: URIRef) -> InstanceInfo:
    """Extract information about an instance/individual.

    Args:
        graph: RDF graph to query.
        uri: Instance URI to extract info for.

    Returns:
        InstanceInfo with all available metadata.
    """
    info = InstanceInfo(
        uri=uri,
        qname=get_qname(graph, uri),
        label=get_label(graph, uri),
        definition=get_definition(graph, uri),
        annotations=get_annotations(graph, uri),
    )

    # Types
    for obj in graph.objects(uri, RDF.type):
        if isinstance(obj, URIRef):
            info.types.append(obj)

    # All other properties
    for pred, obj in graph.predicate_objects(uri):
        if pred == RDF.type:
            continue
        # Skip standard annotation predicates (already captured)
        if pred in [p for p, _ in [
            (RDFS.label, None), (RDFS.comment, None),
            (SKOS.prefLabel, None), (SKOS.definition, None),
        ]]:
            continue

        if pred not in info.properties:
            info.properties[pred] = []

        if isinstance(obj, Literal):
            info.properties[pred].append(str(obj))
        elif isinstance(obj, URIRef):
            info.properties[pred].append(obj)

    return info


def extract_all_classes(graph: Graph) -> list[ClassInfo]:
    """Extract information for all classes in the graph.

    Args:
        graph: RDF graph to query.

    Returns:
        List of ClassInfo objects for all classes.
    """
    classes = []
    seen: set[URIRef] = set()

    # OWL classes
    for uri in graph.subjects(RDF.type, OWL.Class):
        if isinstance(uri, URIRef) and uri not in seen:
            seen.add(uri)
            classes.append(extract_class_info(graph, uri))

    # RDFS classes
    for uri in graph.subjects(RDF.type, RDFS.Class):
        if isinstance(uri, URIRef) and uri not in seen:
            seen.add(uri)
            classes.append(extract_class_info(graph, uri))

    # Sort by qname for consistent ordering
    classes.sort(key=lambda c: c.qname)
    return classes


def extract_all_properties(graph: Graph) -> list[PropertyInfo]:
    """Extract information for all properties in the graph.

    Args:
        graph: RDF graph to query.

    Returns:
        List of PropertyInfo objects for all properties.
    """
    properties = []
    seen: set[URIRef] = set()

    property_types = [
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        RDF.Property,
    ]

    for prop_type in property_types:
        for uri in graph.subjects(RDF.type, prop_type):
            if isinstance(uri, URIRef) and uri not in seen:
                seen.add(uri)
                properties.append(extract_property_info(graph, uri))

    # Sort by qname for consistent ordering
    properties.sort(key=lambda p: p.qname)
    return properties


def extract_all_instances(graph: Graph) -> list[InstanceInfo]:
    """Extract information for all instances in the graph.

    Instances are entities that have rdf:type but are not themselves
    classes or properties.

    Args:
        graph: RDF graph to query.

    Returns:
        List of InstanceInfo objects for all instances.
    """
    instances = []
    seen: set[URIRef] = set()

    # Get all class URIs to exclude
    class_uris: set[URIRef] = set()
    for uri in graph.subjects(RDF.type, OWL.Class):
        if isinstance(uri, URIRef):
            class_uris.add(uri)
    for uri in graph.subjects(RDF.type, RDFS.Class):
        if isinstance(uri, URIRef):
            class_uris.add(uri)

    # Get all property URIs to exclude
    property_uris: set[URIRef] = set()
    for prop_type in [OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty, RDF.Property]:
        for uri in graph.subjects(RDF.type, prop_type):
            if isinstance(uri, URIRef):
                property_uris.add(uri)

    # Also exclude the ontology itself
    for uri in graph.subjects(RDF.type, OWL.Ontology):
        if isinstance(uri, URIRef):
            class_uris.add(uri)

    # Find all subjects with rdf:type that aren't classes or properties
    for subj, _, obj in graph.triples((None, RDF.type, None)):
        if isinstance(subj, URIRef) and subj not in seen:
            if subj not in class_uris and subj not in property_uris:
                seen.add(subj)
                instances.append(extract_instance_info(graph, subj))

    # Sort by qname for consistent ordering
    instances.sort(key=lambda i: i.qname)
    return instances


@dataclass
class ExtractedEntities:
    """Container for all extracted entities from an ontology."""

    ontology: OntologyInfo
    classes: list[ClassInfo]
    properties: list[PropertyInfo]
    instances: list[InstanceInfo]

    @property
    def object_properties(self) -> list[PropertyInfo]:
        """Get only object properties."""
        return [p for p in self.properties if p.property_type == "object"]

    @property
    def datatype_properties(self) -> list[PropertyInfo]:
        """Get only datatype properties."""
        return [p for p in self.properties if p.property_type == "datatype"]

    @property
    def annotation_properties(self) -> list[PropertyInfo]:
        """Get only annotation properties."""
        return [p for p in self.properties if p.property_type == "annotation"]


def extract_all(graph: Graph) -> ExtractedEntities:
    """Extract all entities from an ontology graph.

    Args:
        graph: RDF graph to extract from.

    Returns:
        ExtractedEntities containing all classes, properties, and instances.
    """
    return ExtractedEntities(
        ontology=extract_ontology_info(graph),
        classes=extract_all_classes(graph),
        properties=extract_all_properties(graph),
        instances=extract_all_instances(graph),
    )
