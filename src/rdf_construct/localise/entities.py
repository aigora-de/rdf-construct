"""Which subjects ``localise`` translates, and which literals are in which language.

``extract`` and ``report`` share these rules, so the strings a translator is handed and the
strings coverage is measured over are the same strings.

- **An entity is any IRI subject that carries one of the requested properties as a literal**
  (#406). No list of types decides it, so no kind of term can be missed: SKOS concepts, the
  ontology header, an individual typed by a class declared elsewhere, and an untyped subject
  are all entities when they carry a label. Blank nodes are not, since a translation file names
  its subjects by IRI.
- **A deprecated entity** is one with ``owl:deprecated`` true, written as an ``xsd:boolean`` or
  as the plain string ``"true"`` or ``"1"``, or one typed ``owl:DeprecatedClass`` or
  ``owl:DeprecatedProperty`` (#407, #157).
- **A literal is in a language** when its tag equals the language tag, compared without regard
  to case (#159). Tags are matched exactly, not as ranges: ``en`` does not match ``en-GB``. An
  untagged literal counts as the source language; ``@und`` matches no language.
"""

from collections import Counter
from collections.abc import Iterable

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, XSD

from rdf_construct.core.language_tags import canonical_case, primary_subtag
from rdf_construct.core.vocab import (
    ANNOTATION_PROPERTY_TYPES,
    CLASS_TYPES,
    DATATYPE_PROPERTY_TYPES,
    GENERIC_PROPERTY_TYPES,
    OBJECT_PROPERTY_TYPES,
)

_CURIES = {
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/2004/02/skos/core#": "skos:",
    "http://www.w3.org/2002/07/owl#": "owl:",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://purl.org/dc/elements/1.1/": "dc:",
    "http://purl.org/dc/terms/": "dcterms:",
}


def _shorten(iri: str) -> str:
    for namespace, prefix in _CURIES.items():
        if iri.startswith(namespace):
            return prefix + iri[len(namespace) :]
    return iri


def collect_entities(graph: Graph, properties: Iterable[URIRef]) -> list[URIRef]:
    """Return every IRI subject carrying one of `properties` as a literal, sorted by IRI.

    Args:
        graph: The ontology.
        properties: The properties being translated or measured.

    Returns:
        The entities, sorted by IRI.
    """
    entities: set[URIRef] = set()
    for prop in properties:
        for subject, value in graph.subject_objects(prop):
            if isinstance(subject, URIRef) and isinstance(value, Literal):
                entities.add(subject)
    return sorted(entities, key=str)


def entity_type(graph: Graph, entity: URIRef) -> str:
    """Return the type a translation file records for `entity`.

    Classes come first (the first class type by IRI), then the property kinds, then
    ``owl:NamedIndividual``, using the ``core.vocab`` sets; a property whose kind is not
    inferable is ``rdf:Property``. Otherwise
    the entity's first type by IRI is given, and ``untyped`` when it has none.

    Args:
        graph: The ontology.
        entity: An entity.

    Returns:
        A CURIE, an IRI, or ``untyped``.
    """
    types = set(graph.objects(entity, RDF.type))
    declared_classes = sorted(str(t) for t in types & CLASS_TYPES)
    if declared_classes:
        return _shorten(declared_classes[0])
    if types & OBJECT_PROPERTY_TYPES:
        return "owl:ObjectProperty"
    if types & DATATYPE_PROPERTY_TYPES:
        return "owl:DatatypeProperty"
    if types & ANNOTATION_PROPERTY_TYPES:
        return "owl:AnnotationProperty"
    if types & GENERIC_PROPERTY_TYPES:
        return "rdf:Property"
    if OWL.NamedIndividual in types:
        return "owl:NamedIndividual"
    named = sorted(str(t) for t in types if isinstance(t, URIRef))
    return _shorten(named[0]) if named else "untyped"


def is_deprecated(graph: Graph, entity: URIRef) -> bool:
    """Return whether `entity` is deprecated.

    Args:
        graph: The ontology.
        entity: An entity.

    Returns:
        True for ``owl:deprecated`` true (an ``xsd:boolean``, or the plain string ``"true"`` or
        ``"1"``), or a type of ``owl:DeprecatedClass`` or ``owl:DeprecatedProperty``.
    """
    for value in graph.objects(entity, OWL.deprecated):
        if (
            isinstance(value, Literal)
            and value.datatype in (None, XSD.boolean, XSD.string)
            and value.language is None
            and str(value).strip().lower() in ("true", "1")
        ):
            return True
    return any(
        (entity, RDF.type, t) in graph for t in (OWL.DeprecatedClass, OWL.DeprecatedProperty)
    )


def in_language(value: Literal, language: str, source_language: str) -> bool:
    """Return whether `value` is in `language`.

    Args:
        value: A literal.
        language: The language tag asked for, in any case.
        source_language: The source language tag, which untagged literals count as.

    Returns:
        True if the tags are equal without regard to case, or if `value` is untagged and
        `language` is the source language.
    """
    if value.language is None:
        return language.lower() == source_language.lower()
    return value.language.lower() == language.lower()


def literals(graph: Graph, entity: URIRef, prop: URIRef) -> list[Literal]:
    """Return the literal values of `prop` on `entity`."""
    return [value for value in graph.objects(entity, prop) if isinstance(value, Literal)]


def related_tags(
    graph: Graph,
    entities: Iterable[URIRef],
    properties: Iterable[URIRef],
    language: str,
) -> Counter[str]:
    """Count literals tagged with a tag related to `language`, but not `language` itself.

    Two tags are related when they share a primary subtag: ``en``, ``en-GB`` and ``en-US`` are
    related to one another. This finds the material an exact match leaves out, for the warning
    given when `language` matches nothing (#159).

    Args:
        graph: The ontology.
        entities: The entities being read.
        properties: The properties being read.
        language: The language tag asked for.

    Returns:
        A count of literals per related tag, each tag in canonical case.
    """
    primary = primary_subtag(language)
    found: Counter[str] = Counter()
    props = list(properties)
    for entity in entities:
        for prop in props:
            for value in literals(graph, entity, prop):
                tag = value.language
                if tag and tag.lower() != language.lower() and primary_subtag(tag) == primary:
                    found[canonical_case(tag)] += 1
    return found


def zero_match_warnings(found: Counter[str], language: str, flag: str) -> list[str]:
    """Return the warnings for a language that matched no literal while related tags did.

    Args:
        found: The related tags and their literal counts, from :func:`related_tags`.
        language: The language tag asked for, as given.
        flag: The option it was given with, e.g. ``"--source-language"`` or ``"-l"``.

    Returns:
        One warning per related tag, most literals first.
    """
    return [
        f"Found {count} literal{'s' if count != 1 else ''} tagged {tag}; {flag} {language} "
        f"does not match them. Did you mean {flag} {tag}?"
        for tag, count in sorted(found.items(), key=lambda item: (-item[1], item[0]))
    ]


__all__ = [
    "collect_entities",
    "entity_type",
    "in_language",
    "is_deprecated",
    "literals",
    "related_tags",
    "zero_match_warnings",
]
