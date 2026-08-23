"""Entity extraction from RDF graphs for documentation generation.

Extracts comprehensive information about classes, properties, and instances
from RDF ontologies for use in generating navigable documentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from rdflib import BNode, RDF, RDFS, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, SH, SKOS

from rdf_construct.core.vocab import ALL_PROPERTY_TYPES, CLASS_TYPES

if TYPE_CHECKING:
    from rdflib import Graph


class EntityKind(str, Enum):
    """Discrete entity kinds for the docs taxonomy.

    Subclassing ``str`` is the pre-3.11 idiom for what 3.11's ``StrEnum``
    does natively: members compare equal to their string values
    (``EntityKind.SHAPE == "shape"`` is ``True``), serialise to JSON as
    plain strings, and work as dict keys interchangeably with strings.

    The ``__str__`` override below restores the 3.10-era behaviour of
    returning the value (``"shape"``) rather than ``"EntityKind.SHAPE"``
    — Python 3.11 changed the default for ``str`` mixin enums in a way
    that breaks f-string and template rendering. Without the override,
    a Jinja template ``{{ kind }}`` would emit ``"EntityKind.SHAPE"``.

    This is the central registry of kind values across the docs module.
    Adding a new kind (e.g. for SKOS support in stage 2 of the v0.5.0
    milestone) should land here first; everything else flows through.
    See issue #60 panel review for the rationale on the multi-kind
    data model.
    """

    # Existing taxonomy
    CLASS = "class"
    PROPERTY = "property"
    OBJECT_PROPERTY = "object_property"
    DATATYPE_PROPERTY = "datatype_property"
    ANNOTATION_PROPERTY = "annotation_property"
    RDF_PROPERTY = "rdf_property"
    INSTANCE = "instance"

    # SHACL shapes (#60)
    SHAPE = "shape"
    NODE_SHAPE = "node_shape"
    PROPERTY_SHAPE = "property_shape"

    # SKOS vocabulary entities (#63)
    SKOS_CONCEPT = "skos_concept"
    SKOS_CONCEPT_SCHEME = "skos_concept_scheme"

    def __str__(self) -> str:
        # Return the string value so f-strings and Jinja render
        # "shape" rather than "EntityKind.SHAPE". See class docstring.
        return self.value


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

# Standard annotation predicates extracted for every entity, paired with the
# name they are grouped under. Module-level so consumers that need to know
# which predicates are already captured (see ``_other_properties``) can ask
# rather than reproduce the list.
ANNOTATION_PREDICATES = [
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

# SKOS documentation properties, in the order they render on a concept or
# scheme page (#63). The SKOS spec defines seven; issue #63 lists six,
# omitting ``skos:changeNote`` — which is rendered here too, since dropping
# it would lose a value that ``get_annotations`` was already surfacing.
SKOS_NOTE_PREDICATES: list[tuple[URIRef, str]] = [
    (SKOS.definition, "definition"),
    (SKOS.scopeNote, "scopeNote"),
    (SKOS.example, "example"),
    (SKOS.note, "note"),
    (SKOS.historyNote, "historyNote"),
    (SKOS.editorialNote, "editorialNote"),
    (SKOS.changeNote, "changeNote"),
]

# SKOS labelling properties. Values are grouped by language tag rather than
# by property, so a reader can see one language at a time.
SKOS_LABEL_PREDICATES: list[tuple[URIRef, str]] = [
    (SKOS.prefLabel, "preferred"),
    (SKOS.altLabel, "alternative"),
    (SKOS.hiddenLabel, "hidden"),
]

# SKOS predicates rendered structurally on a concept or scheme page. They are
# excluded from the generic key-value fallback so nothing renders twice.
SKOS_STRUCTURAL_PREDICATES: frozenset[URIRef] = frozenset(
    {
        SKOS.broader,
        SKOS.narrower,
        SKOS.related,
        SKOS.inScheme,
        SKOS.topConceptOf,
        SKOS.hasTopConcept,
    }
    | {pred for pred, _ in SKOS_NOTE_PREDICATES}
    | {pred for pred, _ in SKOS_LABEL_PREDICATES}
)


@dataclass
class PropertyInfo:
    """Information about an RDF property for documentation."""

    uri: URIRef
    qname: str
    kinds: list[EntityKind] = field(default_factory=list)
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
    kinds: list[EntityKind] = field(default_factory=list)
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
    kinds: list[EntityKind] = field(default_factory=list)
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


# First-class SHACL constraints rendered explicitly by the renderers.
# Anything not in this list falls back to the generic key-value display
# in PropertyShapeInfo.other_constraints / ShapeInfo.other_constraints.
# See issue #60 panel review for the rationale on what's included.
FIRST_CLASS_SHACL_CONSTRAINTS = frozenset(
    [
        SH.path,
        SH.minCount,
        SH.maxCount,
        SH.datatype,
        SH["class"],  # 'class' is a Python keyword
        SH.nodeKind,
        SH["in"],  # 'in' is a Python keyword
        SH.hasValue,
        SH.pattern,
        SH.minLength,
        SH.maxLength,
        SH.minInclusive,
        SH.maxInclusive,
        SH.targetClass,
        SH.targetNode,
        SH.targetSubjectsOf,
        SH.targetObjectsOf,
        SH.closed,
        SH.ignoredProperties,
        SH.name,
        SH.description,
    ]
)


@dataclass
class PropertyShapeInfo:
    """Information about a SHACL PropertyShape (named or blank-node).

    PropertyShapes attached to a NodeShape via ``sh:property`` are usually
    blank nodes — they represent constraints on a single property and have
    no stable identity outside their parent shape. Named PropertyShapes
    (with their own URI) can be referenced from multiple NodeShapes and
    are also rendered as standalone pages — see :class:`ShapeInfo`.

    Constraint values are stored as raw RDF terms (URIRef or Literal) so
    renderers can format them per-output-format. The 20 first-class
    constraints (see ``FIRST_CLASS_SHACL_CONSTRAINTS``) are stored in
    named fields; everything else lands in ``other_constraints`` keyed by
    the predicate URI for visible-but-plain rendering.
    """

    # Identity. URI is None for blank-node PropertyShapes.
    uri: URIRef | None = None
    qname: str | None = None
    is_blank: bool = True

    # First-class constraints. Most are at-most-one; sh:in is a list.
    path: URIRef | None = None
    name: str | None = None
    description: str | None = None
    datatype: URIRef | None = None
    class_: URIRef | None = None  # sh:class
    node_kind: URIRef | None = None
    min_count: int | None = None
    max_count: int | None = None
    min_length: int | None = None
    max_length: int | None = None
    min_inclusive: str | None = None
    max_inclusive: str | None = None
    pattern: str | None = None
    has_value: URIRef | str | None = None
    in_values: list[URIRef | str] = field(default_factory=list)

    # Anything not first-class: predicate URI -> list of raw object terms.
    other_constraints: dict[URIRef, list[URIRef | str]] = field(default_factory=dict)


@dataclass
class ShapeInfo:
    """Information about a SHACL shape (NodeShape or named PropertyShape).

    Captures top-level shape metadata, target declarations, and any
    PropertyShape arcs (``sh:property``). PropertyShape arcs are
    extracted as :class:`PropertyShapeInfo` instances so renderers can
    show them inline on the parent NodeShape's page.
    """

    uri: URIRef
    qname: str
    kinds: list[EntityKind] = field(default_factory=list)  # e.g. [SHAPE, NODE_SHAPE]
    label: str | None = None
    definition: str | None = None

    # Target declarations
    target_classes: list[URIRef] = field(default_factory=list)
    target_nodes: list[URIRef] = field(default_factory=list)
    target_subjects_of: list[URIRef] = field(default_factory=list)
    target_objects_of: list[URIRef] = field(default_factory=list)

    # NodeShape-only structural fields
    closed: bool = False
    ignored_properties: list[URIRef] = field(default_factory=list)
    properties: list[PropertyShapeInfo] = field(default_factory=list)

    # When this is itself a PropertyShape, its own constraints
    property_shape: PropertyShapeInfo | None = None

    # Generic annotations and any unknown SHACL predicates on the shape
    annotations: dict[str, list[str]] = field(default_factory=dict)
    other_constraints: dict[URIRef, list[URIRef | str]] = field(default_factory=dict)


@dataclass
class NoteValue:
    """A single SKOS documentation-property value and its language tag.

    ``language`` is the empty string for a plain (untagged) literal or for
    a value that was a resource rather than a literal.
    """

    text: str
    language: str = ""


@dataclass
class LabelGroup:
    """SKOS labels for one language.

    Groups ``skos:prefLabel``, ``skos:altLabel`` and ``skos:hiddenLabel``
    by language tag rather than by property, so a reader can ask "what does
    this concept look like in French" and get one row. ``language`` is the
    empty string for untagged literals.
    """

    language: str
    preferred: list[str] = field(default_factory=list)
    alternative: list[str] = field(default_factory=list)
    hidden: list[str] = field(default_factory=list)


@dataclass
class ConceptInfo:
    """Information about a ``skos:Concept`` for documentation.

    ``broader`` and ``narrower`` carry both directions: SKOS declares
    ``skos:narrower`` to be the inverse of ``skos:broader``, so a
    vocabulary that asserts only one direction still documents both. See
    :func:`_related_concepts`.

    ``in_schemes`` likewise includes schemes reached via
    ``skos:topConceptOf`` (a sub-property of ``skos:inScheme``) and via a
    scheme's own ``skos:hasTopConcept``.
    """

    uri: URIRef
    qname: str
    kinds: list[EntityKind] = field(default_factory=list)
    label: str | None = None
    definition: str | None = None

    # Labels grouped by language, and the seven SKOS note properties.
    labels: list[LabelGroup] = field(default_factory=list)
    notes: dict[str, list[NoteValue]] = field(default_factory=dict)

    # Semantic relations and scheme membership
    broader: list[URIRef] = field(default_factory=list)
    narrower: list[URIRef] = field(default_factory=list)
    related: list[URIRef] = field(default_factory=list)
    in_schemes: list[URIRef] = field(default_factory=list)
    top_concept_of: list[URIRef] = field(default_factory=list)

    # Everything else asserted about the concept
    types: list[URIRef] = field(default_factory=list)
    properties: dict[URIRef, list[str | URIRef]] = field(default_factory=dict)
    annotations: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ConceptSchemeInfo:
    """Information about a ``skos:ConceptScheme`` for documentation.

    ``top_concepts`` merges the scheme's ``skos:hasTopConcept`` arcs with
    concepts asserting ``skos:topConceptOf`` back at it; ``concepts`` is
    every member reachable through ``skos:inScheme`` or through being a top
    concept.
    """

    uri: URIRef
    qname: str
    kinds: list[EntityKind] = field(default_factory=list)
    label: str | None = None
    definition: str | None = None

    labels: list[LabelGroup] = field(default_factory=list)
    notes: dict[str, list[NoteValue]] = field(default_factory=dict)

    top_concepts: list[URIRef] = field(default_factory=list)
    concepts: list[URIRef] = field(default_factory=list)

    types: list[URIRef] = field(default_factory=list)
    properties: dict[URIRef, list[str | URIRef]] = field(default_factory=dict)
    annotations: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ConceptNode:
    """One node of a ``skos:broader`` / ``skos:narrower`` hierarchy tree."""

    concept: ConceptInfo
    children: list["ConceptNode"] = field(default_factory=list)


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

    for pred, name in ANNOTATION_PREDICATES:
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
        kinds=[EntityKind.CLASS],
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

    # Kinds: [PROPERTY, <type>_PROPERTY] — base PROPERTY plus the
    # specific subtype, so renderers can match on either. The string
    # value of property_type ("object", "datatype", ...) maps to the
    # corresponding EntityKind member.
    _PROPERTY_TYPE_TO_KIND = {
        "object": EntityKind.OBJECT_PROPERTY,
        "datatype": EntityKind.DATATYPE_PROPERTY,
        "annotation": EntityKind.ANNOTATION_PROPERTY,
        "rdf": EntityKind.RDF_PROPERTY,
    }
    info.kinds = [EntityKind.PROPERTY]
    specific = _PROPERTY_TYPE_TO_KIND.get(info.property_type)
    if specific is not None:
        info.kinds.append(specific)

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
        kinds=[EntityKind.INSTANCE],
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
        if pred in [
            p
            for p, _ in [
                (RDFS.label, None),
                (RDFS.comment, None),
                (SKOS.prefLabel, None),
                (SKOS.definition, None),
            ]
        ]:
            continue

        if pred not in info.properties:
            info.properties[pred] = []

        if isinstance(obj, Literal):
            info.properties[pred].append(str(obj))
        elif isinstance(obj, URIRef):
            info.properties[pred].append(obj)

    return info


def _walk_rdf_list(graph: Graph, head: URIRef | BNode | None) -> list[URIRef | str]:
    """Walk an ``rdf:List`` and return its members as a Python list.

    SHACL uses ``rdf:List`` for ``sh:in``, ``sh:ignoredProperties``, and
    similar collection constraints. Returns raw terms (URIRefs preserved
    as URIRef, Literals as ``str``); non-list inputs return empty.

    rdflib represents the list cells as blank nodes by default, so the
    walker accepts both ``URIRef`` and ``BNode`` as valid list-pointers
    — earlier versions that only accepted ``URIRef`` silently truncated
    lists at the first cell because the ``rdf:rest`` pointer is a
    blank node, not a URI.

    Args:
        graph: RDF graph to query.
        head: Head of the rdf:List (or None).

    Returns:
        List of members. Empty if ``head`` is None or rdf:nil.
    """
    members: list[URIRef | str] = []
    current: URIRef | BNode | None = head
    seen: set[URIRef | BNode] = set()
    while current is not None and current != RDF.nil:
        # Cycle protection — malformed lists shouldn't loop forever.
        if current in seen:
            break
        seen.add(current)
        first = next(iter(graph.objects(current, RDF.first)), None)
        if first is not None:
            if isinstance(first, Literal):
                members.append(str(first))
            elif isinstance(first, URIRef):
                members.append(first)
        rest = next(iter(graph.objects(current, RDF.rest)), None)
        current = rest if isinstance(rest, (URIRef, BNode)) else None
    return members


def _coerce_int(value: object) -> int | None:
    """Coerce a Literal-or-string SHACL constraint value to an int.

    SHACL count constraints are typed ``xsd:integer`` but rdflib hands
    them to us as Literals. We convert through ``str`` -> ``int`` and
    swallow conversion failures rather than crash on malformed shapes.
    """
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def extract_property_shape_info(
    graph: Graph,
    node: URIRef | None,
) -> PropertyShapeInfo:
    """Extract constraint information from a PropertyShape node.

    Works for both named PropertyShapes (when ``node`` is a URIRef and
    has its own URI) and blank-node PropertyShapes (when ``node`` is a
    blank node — represented in rdflib as a ``BNode``). The ``is_blank``
    field on the result reflects the input shape.

    First-class constraints (see ``FIRST_CLASS_SHACL_CONSTRAINTS``) are
    stored in named fields; everything else lands in
    ``other_constraints`` keyed by the predicate URI for visible-but-
    plain rendering.

    Args:
        graph: RDF graph to query.
        node: The PropertyShape node (URIRef or blank node).

    Returns:
        PropertyShapeInfo with extracted constraints.
    """
    info = PropertyShapeInfo()

    if isinstance(node, URIRef):
        info.uri = node
        info.qname = get_qname(graph, node)
        info.is_blank = False
    else:
        info.is_blank = True

    if node is None:
        return info

    for pred, obj in graph.predicate_objects(node):
        if not isinstance(pred, URIRef):
            continue
        # Skip rdf:type — handled at the shape level
        if pred == RDF.type:
            continue

        # First-class: dispatch by predicate URI.
        if pred == SH.path:
            if isinstance(obj, URIRef):
                info.path = obj
        elif pred == SH.name:
            if isinstance(obj, Literal):
                info.name = str(obj)
        elif pred == SH.description:
            if isinstance(obj, Literal):
                info.description = str(obj)
        elif pred == SH.datatype:
            if isinstance(obj, URIRef):
                info.datatype = obj
        elif pred == SH["class"]:
            if isinstance(obj, URIRef):
                info.class_ = obj
        elif pred == SH.nodeKind:
            if isinstance(obj, URIRef):
                info.node_kind = obj
        elif pred == SH.minCount:
            info.min_count = _coerce_int(obj)
        elif pred == SH.maxCount:
            info.max_count = _coerce_int(obj)
        elif pred == SH.minLength:
            info.min_length = _coerce_int(obj)
        elif pred == SH.maxLength:
            info.max_length = _coerce_int(obj)
        elif pred == SH.minInclusive:
            info.min_inclusive = str(obj)
        elif pred == SH.maxInclusive:
            info.max_inclusive = str(obj)
        elif pred == SH.pattern:
            if isinstance(obj, Literal):
                info.pattern = str(obj)
        elif pred == SH.hasValue:
            if isinstance(obj, Literal):
                info.has_value = str(obj)
            elif isinstance(obj, URIRef):
                info.has_value = obj
        elif pred == SH["in"]:
            if isinstance(obj, (URIRef, BNode)):
                info.in_values = _walk_rdf_list(graph, obj)
        else:
            # Generic fallback for anything not first-class.
            if pred not in info.other_constraints:
                info.other_constraints[pred] = []
            if isinstance(obj, Literal):
                info.other_constraints[pred].append(str(obj))
            elif isinstance(obj, URIRef):
                info.other_constraints[pred].append(obj)

    return info


def extract_shape_info(graph: Graph, uri: URIRef) -> ShapeInfo:
    """Extract comprehensive information about a SHACL shape.

    Handles both NodeShapes and named PropertyShapes (distinguished
    via the ``kinds`` field). For NodeShapes, ``sh:property`` arcs
    are recursively extracted as :class:`PropertyShapeInfo` entries
    so renderers can inline them on the shape's page.

    Args:
        graph: RDF graph to query.
        uri: Shape URI to extract info for.

    Returns:
        ShapeInfo with all available metadata.
    """
    info = ShapeInfo(
        uri=uri,
        qname=get_qname(graph, uri),
        label=get_label(graph, uri),
        definition=get_definition(graph, uri),
        annotations=get_annotations(graph, uri),
    )

    is_node_shape = (uri, RDF.type, SH.NodeShape) in graph
    is_property_shape = (uri, RDF.type, SH.PropertyShape) in graph

    info.kinds = [EntityKind.SHAPE]
    if is_node_shape:
        info.kinds.append(EntityKind.NODE_SHAPE)
    if is_property_shape:
        info.kinds.append(EntityKind.PROPERTY_SHAPE)
    # If neither (shouldn't happen since the caller only passes shape URIs)
    # we still mark it as a shape so renderers don't crash on missing kind.

    # Top-level (NodeShape and PropertyShape both can have these)
    for obj in graph.objects(uri, SH.targetClass):
        if isinstance(obj, URIRef):
            info.target_classes.append(obj)
    for obj in graph.objects(uri, SH.targetNode):
        if isinstance(obj, URIRef):
            info.target_nodes.append(obj)
    for obj in graph.objects(uri, SH.targetSubjectsOf):
        if isinstance(obj, URIRef):
            info.target_subjects_of.append(obj)
    for obj in graph.objects(uri, SH.targetObjectsOf):
        if isinstance(obj, URIRef):
            info.target_objects_of.append(obj)

    # NodeShape structural fields
    if is_node_shape:
        for obj in graph.objects(uri, SH.closed):
            if isinstance(obj, Literal):
                info.closed = bool(obj)
                break
        ignored_head = next(iter(graph.objects(uri, SH.ignoredProperties)), None)
        if ignored_head is not None:
            members = _walk_rdf_list(graph, ignored_head)
            info.ignored_properties = [m for m in members if isinstance(m, URIRef)]

        # Property shape arcs — extract each as a PropertyShapeInfo
        for prop_node in graph.objects(uri, SH.property):
            # prop_node is typically a blank node; extract_property_shape_info
            # handles both blank and named cases.
            info.properties.append(extract_property_shape_info(graph, prop_node))

    # If this shape is itself a PropertyShape, capture its own constraints.
    if is_property_shape:
        info.property_shape = extract_property_shape_info(graph, uri)

    # Generic fallback for any non-first-class SHACL predicate at the
    # top level — same approach as PropertyShapeInfo.other_constraints.
    handled_at_top_level = {
        SH.targetClass,
        SH.targetNode,
        SH.targetSubjectsOf,
        SH.targetObjectsOf,
        SH.closed,
        SH.ignoredProperties,
        SH.property,
        # Also skip things already captured via get_label/get_definition/etc.
        RDFS.label,
        RDFS.comment,
        RDF.type,
    }
    for pred, obj in graph.predicate_objects(uri):
        if not isinstance(pred, URIRef):
            continue
        if pred in handled_at_top_level:
            continue
        # Only collect predicates in the SHACL namespace as "other constraints";
        # arbitrary annotations are already captured via get_annotations().
        if not str(pred).startswith(str(SH)):
            continue
        # Skip predicates we capture per-PropertyShape (they shouldn't
        # appear at the top level of a NodeShape, but PropertyShape-as-shape
        # captures them via info.property_shape above).
        if is_property_shape and pred in FIRST_CLASS_SHACL_CONSTRAINTS:
            continue
        if pred not in info.other_constraints:
            info.other_constraints[pred] = []
        if isinstance(obj, Literal):
            info.other_constraints[pred].append(str(obj))
        elif isinstance(obj, URIRef):
            info.other_constraints[pred].append(obj)

    return info


def extract_all_shapes(graph: Graph) -> list[ShapeInfo]:
    """Extract information for all SHACL shapes in the graph.

    Returns NodeShapes and *named* PropertyShapes. Blank-node
    PropertyShapes attached to NodeShapes via ``sh:property`` are
    extracted as part of their parent shape (see
    :func:`extract_shape_info`) and do not appear as standalone entries.

    Args:
        graph: RDF graph to query.

    Returns:
        List of ShapeInfo objects, sorted by qname.
    """
    shapes = []
    seen: set[URIRef] = set()

    # NodeShapes (named only — blank-node NodeShapes are unusual but
    # would be unreachable in our docs anyway, so we ignore them).
    for uri in graph.subjects(RDF.type, SH.NodeShape):
        if isinstance(uri, URIRef) and uri not in seen:
            seen.add(uri)
            shapes.append(extract_shape_info(graph, uri))

    # Named PropertyShapes
    for uri in graph.subjects(RDF.type, SH.PropertyShape):
        if isinstance(uri, URIRef) and uri not in seen:
            seen.add(uri)
            shapes.append(extract_shape_info(graph, uri))

    shapes.sort(key=lambda s: s.qname)
    return shapes


def _skos_label_groups(graph: Graph, uri: URIRef) -> list[LabelGroup]:
    """Group an entity's SKOS labels by language tag.

    Args:
        graph: RDF graph to query.
        uri: Concept or scheme URI.

    Returns:
        One :class:`LabelGroup` per language tag, ordered by tag with
        untagged literals last.
    """
    collected: dict[str, dict[str, list[str]]] = {}

    for pred, slot in SKOS_LABEL_PREDICATES:
        for obj in graph.objects(uri, pred):
            if not isinstance(obj, Literal):
                continue
            language = obj.language or ""
            by_slot = collected.setdefault(language, {})
            by_slot.setdefault(slot, []).append(str(obj))

    # Untagged literals sort last; everything else alphabetically by tag.
    languages = sorted(collected, key=lambda lang: (lang == "", lang))
    return [
        LabelGroup(
            language=language,
            preferred=sorted(collected[language].get("preferred", [])),
            alternative=sorted(collected[language].get("alternative", [])),
            hidden=sorted(collected[language].get("hidden", [])),
        )
        for language in languages
    ]


def _skos_notes(graph: Graph, uri: URIRef) -> dict[str, list[NoteValue]]:
    """Extract the SKOS documentation properties for an entity.

    Args:
        graph: RDF graph to query.
        uri: Concept or scheme URI.

    Returns:
        Note values keyed by the property's local name, in the order
        given by ``SKOS_NOTE_PREDICATES``. Resource-valued notes are kept
        as their URI string rather than dropped.
    """
    notes: dict[str, list[NoteValue]] = {}

    for pred, name in SKOS_NOTE_PREDICATES:
        values: list[NoteValue] = []
        for obj in graph.objects(uri, pred):
            if isinstance(obj, Literal):
                values.append(NoteValue(text=str(obj), language=obj.language or ""))
            elif isinstance(obj, URIRef):
                values.append(NoteValue(text=str(obj)))
        if values:
            notes[name] = sorted(values, key=lambda value: (value.language, value.text))

    return notes


def _other_properties(
    graph: Graph,
    uri: URIRef,
    handled: frozenset[URIRef],
) -> dict[URIRef, list[str | URIRef]]:
    """Collect predicates not already rendered by a first-class field.

    Anything a concept or scheme asserts that is neither structural SKOS,
    nor a label, nor one of the standard annotations lands here so it stays
    visible rather than being silently dropped — the same posture the SHACL
    renderer takes with long-tail constraints.

    Args:
        graph: RDF graph to query.
        uri: Entity URI.
        handled: Predicates already rendered elsewhere on the page.

    Returns:
        Raw object terms keyed by predicate URI.
    """
    captured = (
        handled
        | {pred for pred, _ in ANNOTATION_PREDICATES}
        | {RDF.type, RDFS.label, RDFS.comment, DCTERMS.title, DCTERMS.description}
    )

    properties: dict[URIRef, list[str | URIRef]] = {}
    for pred, obj in graph.predicate_objects(uri):
        if not isinstance(pred, URIRef) or pred in captured:
            continue
        if isinstance(obj, Literal):
            properties.setdefault(pred, []).append(str(obj))
        elif isinstance(obj, URIRef):
            properties.setdefault(pred, []).append(obj)

    return properties


def _related_concepts(
    graph: Graph,
    uri: URIRef,
    forward: URIRef,
    inverse: URIRef,
) -> list[URIRef]:
    """Collect concepts related to ``uri``, in both assertion directions.

    SKOS declares ``skos:broader`` and ``skos:narrower`` to be inverses of
    one another, so a vocabulary that only ever writes ``skos:narrower``
    still has to produce a broader link on the child's page. Materialising
    the inverse here means the hierarchy is complete whichever direction
    the author chose.

    Args:
        graph: RDF graph to query.
        uri: Concept URI.
        forward: Predicate asserted on this concept.
        inverse: Predicate asserted on the other concept, pointing back.

    Returns:
        Sorted, de-duplicated concept URIs.
    """
    found: set[URIRef] = {obj for obj in graph.objects(uri, forward) if isinstance(obj, URIRef)}
    found |= {subj for subj in graph.subjects(inverse, uri) if isinstance(subj, URIRef)}
    return sorted(found)


def extract_concept_info(graph: Graph, uri: URIRef) -> ConceptInfo:
    """Extract comprehensive information about a SKOS concept.

    Args:
        graph: RDF graph to query.
        uri: Concept URI to extract info for.

    Returns:
        ConceptInfo with all available metadata.
    """
    info = ConceptInfo(
        uri=uri,
        qname=get_qname(graph, uri),
        kinds=[EntityKind.SKOS_CONCEPT],
        label=get_label(graph, uri),
        definition=get_definition(graph, uri),
        labels=_skos_label_groups(graph, uri),
        notes=_skos_notes(graph, uri),
        annotations=get_annotations(graph, uri),
    )

    # The SKOS notes are rendered from `notes`, with their language tags.
    # Drop the copies get_annotations() collected so they render once.
    for _, name in SKOS_NOTE_PREDICATES:
        info.annotations.pop(name, None)

    info.broader = _related_concepts(graph, uri, SKOS.broader, SKOS.narrower)
    info.narrower = _related_concepts(graph, uri, SKOS.narrower, SKOS.broader)
    # skos:related is symmetric, so both directions count.
    info.related = _related_concepts(graph, uri, SKOS.related, SKOS.related)
    info.top_concept_of = _related_concepts(graph, uri, SKOS.topConceptOf, SKOS.hasTopConcept)

    # skos:topConceptOf is a sub-property of skos:inScheme, so a top concept
    # belongs to its scheme even without an explicit inScheme triple.
    schemes: set[URIRef] = {
        obj for obj in graph.objects(uri, SKOS.inScheme) if isinstance(obj, URIRef)
    }
    schemes |= set(info.top_concept_of)
    info.in_schemes = sorted(schemes)

    for obj in graph.objects(uri, RDF.type):
        if isinstance(obj, URIRef):
            info.types.append(obj)

    info.properties = _other_properties(graph, uri, SKOS_STRUCTURAL_PREDICATES)

    return info


def extract_concept_scheme_info(graph: Graph, uri: URIRef) -> ConceptSchemeInfo:
    """Extract comprehensive information about a SKOS concept scheme.

    Args:
        graph: RDF graph to query.
        uri: Concept scheme URI to extract info for.

    Returns:
        ConceptSchemeInfo with all available metadata.
    """
    info = ConceptSchemeInfo(
        uri=uri,
        qname=get_qname(graph, uri),
        kinds=[EntityKind.SKOS_CONCEPT_SCHEME],
        label=get_label(graph, uri),
        definition=get_definition(graph, uri),
        labels=_skos_label_groups(graph, uri),
        notes=_skos_notes(graph, uri),
        annotations=get_annotations(graph, uri),
    )

    for _, name in SKOS_NOTE_PREDICATES:
        info.annotations.pop(name, None)

    info.top_concepts = _related_concepts(graph, uri, SKOS.hasTopConcept, SKOS.topConceptOf)

    members: set[URIRef] = {
        subj for subj in graph.subjects(SKOS.inScheme, uri) if isinstance(subj, URIRef)
    }
    members |= set(info.top_concepts)
    info.concepts = sorted(members)

    for obj in graph.objects(uri, RDF.type):
        if isinstance(obj, URIRef):
            info.types.append(obj)

    info.properties = _other_properties(graph, uri, SKOS_STRUCTURAL_PREDICATES)

    return info


def _claimed_by_other_buckets(graph: Graph) -> set[URIRef]:
    """Collect subjects that classes, properties or shapes already document.

    SKOS entities sit between shapes and plain instances in the routing
    order, so a subject that is also a class, a property or a SHACL shape
    keeps the page it already had rather than gaining a second one. The
    type sets come from :mod:`rdf_construct.core.vocab` — a term declared
    only by an OWL characteristic is still a property.

    Args:
        graph: RDF graph to query.

    Returns:
        Set of URIs owned by a higher-priority bucket.
    """
    claimed: set[URIRef] = set()
    higher_priority_types = (
        set(CLASS_TYPES) | set(ALL_PROPERTY_TYPES) | {SH.NodeShape, SH.PropertyShape}
    )
    for type_uri in higher_priority_types:
        for subj in graph.subjects(RDF.type, type_uri):
            if isinstance(subj, URIRef):
                claimed.add(subj)
    return claimed


def extract_all_concepts(graph: Graph) -> list[ConceptInfo]:
    """Extract information for all SKOS concepts in the graph.

    Subjects already documented as a class, property or SHACL shape are
    skipped — SKOS/OWL punning is legal, and documenting the same subject
    twice serves nobody. See :func:`_claimed_by_other_buckets`.

    Args:
        graph: RDF graph to query.

    Returns:
        List of ConceptInfo objects, sorted by qname.
    """
    claimed = _claimed_by_other_buckets(graph)

    concepts = []
    seen: set[URIRef] = set()
    for uri in graph.subjects(RDF.type, SKOS.Concept):
        if isinstance(uri, URIRef) and uri not in seen and uri not in claimed:
            seen.add(uri)
            concepts.append(extract_concept_info(graph, uri))

    concepts.sort(key=lambda c: c.qname)
    return concepts


def extract_all_concept_schemes(graph: Graph) -> list[ConceptSchemeInfo]:
    """Extract information for all SKOS concept schemes in the graph.

    Args:
        graph: RDF graph to query.

    Returns:
        List of ConceptSchemeInfo objects, sorted by qname.
    """
    claimed = _claimed_by_other_buckets(graph)

    schemes = []
    seen: set[URIRef] = set()
    for uri in graph.subjects(RDF.type, SKOS.ConceptScheme):
        if isinstance(uri, URIRef) and uri not in seen and uri not in claimed:
            seen.add(uri)
            schemes.append(extract_concept_scheme_info(graph, uri))

    schemes.sort(key=lambda s: s.qname)
    return schemes


def build_concept_tree(
    concepts: list[ConceptInfo],
    scheme: URIRef | None = None,
) -> list[ConceptNode]:
    """Build a ``skos:broader`` / ``skos:narrower`` tree.

    SKOS does not promise an acyclic hierarchy, and a cycle would leave no
    concept without an internal parent — so the walker (a) refuses to
    revisit a concept already on the current path, and (b) promotes any
    concept the roots could not reach to a root of its own. A cyclic
    vocabulary therefore renders in full rather than either looping
    forever or silently losing concepts.

    Args:
        concepts: Concepts to build the tree from.
        scheme: Restrict to members of this scheme. ``None`` uses every
            concept given.

    Returns:
        Root nodes, sorted by qname.
    """
    if scheme is not None:
        members = [c for c in concepts if scheme in c.in_schemes]
    else:
        members = list(concepts)

    by_uri = {str(c.uri): c for c in members}
    visited: set[str] = set()

    def build(concept: ConceptInfo, ancestors: frozenset[str]) -> ConceptNode:
        visited.add(str(concept.uri))
        path = ancestors | {str(concept.uri)}
        children = [
            build(by_uri[key], path)
            for key in (str(uri) for uri in concept.narrower)
            if key in by_uri and key not in path
        ]
        children.sort(key=lambda node: node.concept.qname)
        return ConceptNode(concept=concept, children=children)

    # Declared top concepts anchor the tree; without any, everything with no
    # parent inside the scheme becomes a root.
    roots = [c for c in members if scheme is not None and scheme in c.top_concept_of]
    if not roots:
        roots = [c for c in members if not any(str(uri) in by_uri for uri in c.broader)]

    nodes = [build(c, frozenset()) for c in sorted(roots, key=lambda c: c.qname)]

    # Anything unreachable from a root — a cycle, or a concept whose only
    # parents sit in another scheme — still gets rendered.
    for concept in sorted(members, key=lambda c: c.qname):
        if str(concept.uri) not in visited:
            nodes.append(build(concept, frozenset()))

    return nodes


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
    classes, properties, or SHACL shapes.

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
    for prop_type in [
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        RDF.Property,
    ]:
        for uri in graph.subjects(RDF.type, prop_type):
            if isinstance(uri, URIRef):
                property_uris.add(uri)

    # Also exclude the ontology itself
    for uri in graph.subjects(RDF.type, OWL.Ontology):
        if isinstance(uri, URIRef):
            class_uris.add(uri)

    # Exclude SHACL shapes (#60) — they have their own bucket via
    # extract_all_shapes(). Without this filter shapes would render as
    # generic instances. Only excludes URIs (named shapes); blank-node
    # PropertyShapes never had URIs to begin with so they don't reach
    # the instance loop.
    shape_uris: set[URIRef] = set()
    for shape_type in [SH.NodeShape, SH.PropertyShape]:
        for uri in graph.subjects(RDF.type, shape_type):
            if isinstance(uri, URIRef):
                shape_uris.add(uri)

    # Exclude SKOS concepts and concept schemes (#63) — they have their own
    # buckets via extract_all_concepts() / extract_all_concept_schemes().
    # A concept that is also a class, property or shape is not excluded here
    # because it was never routed to SKOS in the first place: those buckets
    # outrank SKOS, and the class/property/shape filters above already claim it.
    skos_uris: set[URIRef] = set()
    for skos_type in [SKOS.Concept, SKOS.ConceptScheme]:
        for uri in graph.subjects(RDF.type, skos_type):
            if isinstance(uri, URIRef):
                skos_uris.add(uri)

    # Find all subjects with rdf:type that aren't classes, properties, shapes
    # or SKOS entities
    for subj, _, obj in graph.triples((None, RDF.type, None)):
        if isinstance(subj, URIRef) and subj not in seen:
            if (
                subj not in class_uris
                and subj not in property_uris
                and subj not in shape_uris
                and subj not in skos_uris
            ):
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
    shapes: list[ShapeInfo] = field(default_factory=list)
    concepts: list[ConceptInfo] = field(default_factory=list)
    concept_schemes: list[ConceptSchemeInfo] = field(default_factory=list)

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

    @property
    def node_shapes(self) -> list[ShapeInfo]:
        """Get only NodeShapes (named only — blank-node NodeShapes are not extracted)."""
        return [s for s in self.shapes if EntityKind.NODE_SHAPE in s.kinds]

    @property
    def property_shapes(self) -> list[ShapeInfo]:
        """Get only named PropertyShapes.

        Blank-node PropertyShapes attached via ``sh:property`` are
        captured inline on their parent NodeShape and do not appear here.
        """
        return [s for s in self.shapes if EntityKind.PROPERTY_SHAPE in s.kinds]


def extract_all(graph: Graph) -> ExtractedEntities:
    """Extract all entities from an ontology graph.

    Args:
        graph: RDF graph to extract from.

    Returns:
        ExtractedEntities containing all classes, properties, instances,
        SHACL shapes, SKOS concepts and SKOS concept schemes.
    """
    return ExtractedEntities(
        ontology=extract_ontology_info(graph),
        classes=extract_all_classes(graph),
        properties=extract_all_properties(graph),
        instances=extract_all_instances(graph),
        shapes=extract_all_shapes(graph),
        concepts=extract_all_concepts(graph),
        concept_schemes=extract_all_concept_schemes(graph),
    )
