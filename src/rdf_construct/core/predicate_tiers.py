"""Predicate tiers: whether a second value for a predicate changes what an ontology says.

Under the open-world assumption two values for one subject and predicate are two assertions, both
true, so most predicates take any number of values. A few do not, and they fail in two ways:

- **per language tag** — ``rdfs:label`` and ``skos:prefLabel`` name a term once in each language.
  Two English labels are a conflict; an English and a French one are not. A second
  ``skos:prefLabel`` in one tag breaks a SKOS integrity condition (S14), so it is *malformed*; a
  second ``rdfs:label`` is legal RDF and only *ambiguous*.
- **load-bearing** — two ``rdfs:domain`` or ``rdfs:range`` values mean their intersection, which
  is rarely what either author meant. A tool may report such a conflict, but has no basis for
  choosing between the values.

Everything else is **repeatable**, including any predicate not listed here: the map is the only
source of conflicts. ``rdf:type`` is repeatable on purpose, because multiple types and punning are
normal.

This is the one list of these predicates (#193, #169); `merge` and the merged ontology's header
(#171) share it, and a configuration may move a predicate into any tier.
"""

from collections.abc import Iterable, Mapping
from enum import Enum
from types import MappingProxyType

from rdflib.namespace import RDFS, SKOS
from rdflib.term import Literal, Node, URIRef


class PredicateTier(Enum):
    """What a second value for a predicate means."""

    REPEATABLE = "repeatable"  # another assertion, never a conflict
    PER_LANGUAGE = "per_language"  # a conflict only within one language tag
    LOAD_BEARING = "load_bearing"  # changes what the ontology says; mark, never pick


#: The decided tiers (#169). A predicate not in this map is repeatable.
DEFAULT_PREDICATE_TIERS: Mapping[URIRef, PredicateTier] = MappingProxyType(
    {
        RDFS.comment: PredicateTier.REPEATABLE,
        SKOS.altLabel: PredicateTier.REPEATABLE,
        SKOS.note: PredicateTier.REPEATABLE,
        RDFS.seeAlso: PredicateTier.REPEATABLE,
        RDFS.label: PredicateTier.PER_LANGUAGE,
        SKOS.prefLabel: PredicateTier.PER_LANGUAGE,
        RDFS.domain: PredicateTier.LOAD_BEARING,
        RDFS.range: PredicateTier.LOAD_BEARING,
    }
)

#: Per-language predicates whose specification allows one value per tag, so a second one is
#: malformed rather than merely ambiguous (SKOS integrity condition S14).
MALFORMED_WHEN_REPEATED: frozenset[URIRef] = frozenset({SKOS.prefLabel})


def build_tiers(
    overrides: Mapping[PredicateTier, Iterable[URIRef]] | None = None,
) -> dict[URIRef, PredicateTier]:
    """Return the default tier map with `overrides` applied.

    Args:
        overrides: Predicates to place in each tier. They win over the defaults.

    Returns:
        A map from predicate to tier. A predicate not in it is repeatable.

    Raises:
        ValueError: If one predicate is placed in two different tiers.
    """
    placed: dict[URIRef, PredicateTier] = {}
    for tier, predicates in (overrides or {}).items():
        for predicate in predicates:
            earlier = placed.setdefault(predicate, tier)
            if earlier is not tier:
                raise ValueError(
                    f"<{predicate}> is placed in two tiers, {earlier.value} and {tier.value}"
                )
    return {**DEFAULT_PREDICATE_TIERS, **placed}


def tier_of(predicate: URIRef, tiers: Mapping[URIRef, PredicateTier]) -> PredicateTier:
    """Return a predicate's tier: its entry in `tiers`, else repeatable."""
    return tiers.get(predicate, PredicateTier.REPEATABLE)


def language_bucket(value: Node) -> str | None:
    """Return the language tag a per-language comparison files `value` under.

    BCP 47 tags are case-insensitive and RDF 1.1 gives them a lower-case value space, but rdflib
    keeps a parsed tag verbatim, so the tag is folded here. Subtags are not matched: ``en`` and
    ``en-gb`` are different buckets (#159). An untagged literal, or any other term, is filed under
    ``None``.

    Args:
        value: The object of a triple.

    Returns:
        The lower-cased language tag, or None.
    """
    if isinstance(value, Literal) and value.language:
        return value.language.lower()
    return None


def value_key(value: Node) -> Node:
    """Return the term `value` is compared as: itself, with any language tag folded to lower case.

    Args:
        value: The object of a triple.

    Returns:
        A term equal for two values that differ only in the case of their language tag.
    """
    if isinstance(value, Literal) and value.language:
        return Literal(str(value), lang=value.language.lower())
    return value
