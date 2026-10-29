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


#: Selector keys ``select_subjects`` dispatches on, in the order they are
#: documented. A profile section's ``select:`` must name one of these, or a key
#: in the config's ``selectors:`` block whose value one of them recognises.
BUILTIN_SELECTOR_KEYS: tuple[str, ...] = (
    "classes",
    "obj_props",
    "data_props",
    "ann_props",
    "other_props",
    "individuals",
)

#: Values accepted in a ``selectors:`` block, mapped to the built-in key they
#: resolve to. Kept beside the dispatch below so the two cannot drift.
_SELECTOR_VALUES: dict[str, str] = {
    "owl:Class": "classes",
    "rdf:type owl:Class": "classes",
    "owl:ObjectProperty": "obj_props",
    "owl:DatatypeProperty": "data_props",
    "owl:AnnotationProperty": "ann_props",
    "rdf:Property": "other_props",
}


class UnknownSelectorError(ValueError):
    """A selector key that nothing knows how to resolve.

    Raised rather than returning an empty set, because an empty set is
    indistinguishable from "this ontology has none of those" and the
    section simply vanishes from the output. See issue #89.
    """


def is_known_selector(selector_key: str, selectors: dict[str, str]) -> bool:
    """Report whether ``select_subjects`` can resolve this selector key.

    For callers that legitimately probe keys they are not sure about —
    the unclaimed-subject hinting in the CLI walks every key in the
    config looking for one that would have claimed a subject.

    Args:
        selector_key: Key to test
        selectors: Selector definitions from the ordering config

    Returns:
        True if the key resolves to a selection, False otherwise
    """
    if selector_key in BUILTIN_SELECTOR_KEYS:
        return True
    raw = selectors.get(selector_key, "")
    value = raw.strip() if isinstance(raw, str) else ""
    return value in _SELECTOR_VALUES or value.startswith("FILTER")


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

    Raises:
        UnknownSelectorError: If the key names neither a built-in selector
            nor a config entry with a recognised value. Silently selecting
            nothing was #89.
    """
    # A selector value is a string in this grammar, but templates/ordering_starter.yml
    # — the file users are told to copy — writes lists, and `.strip()` on a list is an
    # AttributeError traceback rather than anything a user can act on. Non-strings are
    # treated as an unrecognised *value*: a built-in key still dispatches on its name,
    # so the shipped template works, and anything else reaches the error below.
    raw = selectors.get(selector_key, "")
    sel = raw.strip() if isinstance(raw, str) else ""
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

    else:
        # Nothing matched. Returning an empty set here is what #89 was: the
        # section renders empty, the output is silently short, and the
        # unclaimed-subjects warning then names a section the user believes
        # they already have.
        known = ", ".join(BUILTIN_SELECTOR_KEYS)
        defined = ", ".join(sorted(selectors)) or "none"
        if selector_key in selectors:
            raise UnknownSelectorError(
                f"selector {selector_key!r} is defined in the config as {sel!r}, "
                f"which is not a value this version understands. Accepted values: "
                f"{', '.join(sorted(_SELECTOR_VALUES))}, or a string starting 'FILTER'. "
                f"Built-in selector keys, usable without defining them: {known}"
            )
        raise UnknownSelectorError(
            f"unknown selector {selector_key!r}. Built-in selector keys: {known}. "
            f"Defined in this config: {defined}"
        )

    return subjects
