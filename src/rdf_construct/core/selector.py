"""Subject selection logic for RDF graphs."""

from rdflib import RDF, Graph
from rdflib.term import Node, URIRef

from .vocab import (
    ANNOTATION_PROPERTY_TYPES,
    CLASS_TYPES,
    DATATYPE_PROPERTY_TYPES,
    GENERIC_PROPERTY_TYPES,
    KIND_SPECIFIC_PROPERTY_TYPES,
    OBJECT_PROPERTY_TYPES,
)


def _subjects_of_types(graph: Graph, types: frozenset[URIRef]) -> set[Node]:
    """Collect every subject declared with any of the given rdf:type values.

    Args:
        graph: RDF graph to scan
        types: Type URIs to match

    Returns:
        Set of matching subjects
    """
    subjects: set[Node] = set()
    for type_uri in types:
        subjects |= set(graph.subjects(RDF.type, type_uri))
    return subjects


def select_subjects(graph: Graph, selector_key: str, selectors: dict[str, str]) -> set:
    """Select subjects from a graph based on selector criteria.

    Supports several selector shorthands:
    - classes: owl:Class, rdfs:Class and owl:DeprecatedClass entities
    - obj_props: owl:ObjectProperty entities, including terms declared only by an
      object-property characteristic (owl:TransitiveProperty, owl:SymmetricProperty,
      owl:AsymmetricProperty, owl:ReflexiveProperty, owl:IrreflexiveProperty,
      owl:InverseFunctionalProperty)
    - data_props: owl:DatatypeProperty entities
    - ann_props: owl:AnnotationProperty entities
    - other_props: properties whose kind is not implied by their declaration —
      rdf:Property, owl:FunctionalProperty, owl:DeprecatedProperty — and which no
      kind-specific selector claims
    - individuals: All subjects that aren't classes or kind-specific properties

    Terms matched by ``other_props`` remain visible to ``individuals`` so that a
    profile without an ``other_props`` section still emits them; the ``order``
    command de-duplicates by section order, so adding an ``other_props`` section
    before ``individuals`` moves them rather than duplicating them.

    Args:
        graph: RDF graph to select from
        selector_key: Key identifying the selection type
        selectors: Dictionary of selector definitions

    Returns:
        Set of URIRefs matching the selection criteria
    """
    sel = selectors.get(selector_key, "").strip()
    subjects: set = set()

    # Classes - check owl:Class, rdfs:Class and owl:DeprecatedClass
    if sel in ("owl:Class", "rdf:type owl:Class") or selector_key == "classes":
        subjects = _subjects_of_types(graph, CLASS_TYPES)

    # Object properties - including characteristic-only declarations
    elif sel in ("owl:ObjectProperty",) or selector_key == "obj_props":
        subjects = _subjects_of_types(graph, OBJECT_PROPERTY_TYPES)

    # Datatype properties
    elif sel in ("owl:DatatypeProperty",) or selector_key == "data_props":
        subjects = _subjects_of_types(graph, DATATYPE_PROPERTY_TYPES)

    # Annotation properties
    elif sel in ("owl:AnnotationProperty",) or selector_key == "ann_props":
        subjects = _subjects_of_types(graph, ANNOTATION_PROPERTY_TYPES)

    # Properties whose kind is not implied by their declaration
    elif sel in ("rdf:Property",) or selector_key == "other_props":
        subjects = _subjects_of_types(graph, GENERIC_PROPERTY_TYPES)
        subjects -= _subjects_of_types(graph, KIND_SPECIFIC_PROPERTY_TYPES)

    # Individuals - everything that's not a class or a kind-specific property.
    # Generic properties (rdf:Property, owl:FunctionalProperty,
    # owl:DeprecatedProperty) are deliberately NOT subtracted: no kind-specific
    # section claims them, so subtracting them here would drop them from the
    # output entirely.
    elif selector_key == "individuals" or sel.startswith("FILTER"):
        classes = _subjects_of_types(graph, CLASS_TYPES)
        properties = _subjects_of_types(graph, KIND_SPECIFIC_PROPERTY_TYPES)

        all_subjects = {s for (s, _, _) in graph}
        subjects = all_subjects - classes - properties

    return subjects
