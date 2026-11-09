"""Filtering logic for diff results.

Supports filtering by:
- Change type (added, removed, modified)
- Entity type (classes, properties, individuals, the ontology, untyped terms, and
  blank-node structures that belong to no entity)

A filter changes only what is shown. What it leaves out is counted on the filtered
``GraphDiff`` (``not_shown``), so ``is_identical`` still describes the graphs, and the
formatters can say what was hidden (#144). A name that matches nothing is refused, never
dropped: a typo used to filter everything out and report the graphs identical.
"""

import difflib
from collections.abc import Iterable
from dataclasses import replace

from rdf_construct.diff.change_types import (
    ChangeType,
    DiffFilter,
    EntityChange,
    EntityType,
    GraphDiff,
)


# Maps CLI filter strings to internal types
CHANGE_TYPE_MAP = {
    "added": ChangeType.ADDED,
    "removed": ChangeType.REMOVED,
    "modified": ChangeType.MODIFIED,
}

ENTITY_TYPE_MAP = {
    "classes": EntityType.CLASS,
    "class": EntityType.CLASS,
    "object_properties": EntityType.OBJECT_PROPERTY,
    "object-properties": EntityType.OBJECT_PROPERTY,
    "objprops": EntityType.OBJECT_PROPERTY,
    "datatype_properties": EntityType.DATATYPE_PROPERTY,
    "datatype-properties": EntityType.DATATYPE_PROPERTY,
    "dataprops": EntityType.DATATYPE_PROPERTY,
    "annotation_properties": EntityType.ANNOTATION_PROPERTY,
    "annotation-properties": EntityType.ANNOTATION_PROPERTY,
    "annprops": EntityType.ANNOTATION_PROPERTY,
    "other_properties": EntityType.OTHER_PROPERTY,
    "other-properties": EntityType.OTHER_PROPERTY,
    "otherprops": EntityType.OTHER_PROPERTY,
    "properties": None,  # Special: matches all property types
    "individuals": EntityType.INDIVIDUAL,
    "instances": EntityType.INDIVIDUAL,
    "ontology": EntityType.ONTOLOGY,
    #: A subject with no rdf:type in the file it is listed from (#144)
    "untyped": EntityType.OTHER,
}

# Property types for the "properties" filter
PROPERTY_TYPES = {
    EntityType.OBJECT_PROPERTY,
    EntityType.DATATYPE_PROPERTY,
    EntityType.ANNOTATION_PROPERTY,
    EntityType.OTHER_PROPERTY,
}

#: The ``--entities`` name for blank-node structures that belong to no named entity. Not an
#: :class:`EntityType`: such a structure is an axiom about the terms it mentions, and routing
#: it to one of their types would be a guess (#144).
STRUCTURES = "structures"

#: Every change type a filter may name, in canonical spelling and order.
CHANGE_TYPE_NAMES: tuple[str, ...] = ("added", "removed", "modified")

#: Every entity type a filter may name, in canonical spelling and order. Each of the other
#: spellings in :data:`ENTITY_TYPE_MAP` is accepted as the canonical name with its value.
ENTITY_TYPE_NAMES: tuple[str, ...] = (
    "classes",
    "properties",
    "object_properties",
    "datatype_properties",
    "annotation_properties",
    "other_properties",
    "individuals",
    "ontology",
    "untyped",
    STRUCTURES,
)

#: Keys of ``GraphDiff.not_shown``, in the order they are reported.
NOT_SHOWN_KEYS: tuple[str, ...] = ("added", "removed", "modified", "structures")

_CHANGE_SPELLINGS: dict[str, str] = {name: name for name in CHANGE_TYPE_NAMES}

_ENTITY_SPELLINGS: dict[str, str] = {
    spelling: next(n for n in ENTITY_TYPE_NAMES if ENTITY_TYPE_MAP.get(n, n) == value)
    for spelling, value in ENTITY_TYPE_MAP.items()
} | {STRUCTURES: STRUCTURES}

_DISPLAY_NAMES: dict[str, str] = {
    "ontology": "the ontology",
    "untyped": "untyped terms",
    STRUCTURES: "blank-node structures",
}


class UnknownFilterError(ValueError):
    """A filter that names nothing, names something unknown, or can show nothing.

    Raised rather than dropping the name, because a dropped name narrows the view without
    saying so: a typo in ``--show`` used to hide every change and report the graphs
    identical at exit 0. See issue #144.
    """


def _normalise(
    names: Iterable[str],
    spellings: dict[str, str],
    canonical: tuple[str, ...],
    kind: str,
    label: str,
) -> tuple[str, ...]:
    """Map filter names to canonical ones, or refuse them all at once.

    Args:
        names: The names given, in any case, possibly padded with whitespace
        spellings: Every accepted spelling, lower-cased, to its canonical name
        canonical: The canonical names, in the order they are listed and returned
        kind: What a name is, for the message: ``change type`` or ``entity type``
        label: What the names were given as, prefixed to the message; empty for none

    Returns:
        The canonical names, each once, in canonical order

    Raises:
        UnknownFilterError: If no name is given, or any name is not accepted
    """
    prefix = f"{label}: " if label else ""
    if isinstance(names, str):
        raise UnknownFilterError(
            f"{prefix}expected a collection of {kind}s, not the string {names!r}; "
            f"pass {{{names!r}}}"
        )
    # A set has no order of its own: sort it, so the message is the same on every run
    ordered = sorted(names) if isinstance(names, set | frozenset) else list(names)
    given = [name.strip() for name in ordered]
    given = [name for name in given if name]
    accepted = ", ".join(canonical)
    if not given:
        raise UnknownFilterError(f"{prefix}no {kind}s named. Accepted: {accepted}")
    # Each unknown name once, as first written, in the order given; case does not make it new
    first: dict[str, str] = {}
    for name in given:
        if name.lower() not in spellings:
            first.setdefault(name.lower(), name)
    unknown = list(first.values())
    if unknown:
        parts = []
        for name in unknown:
            nearest = difflib.get_close_matches(name.lower(), list(spellings), n=1)
            hint = f" (did you mean '{spellings[nearest[0]]}'?)" if nearest else ""
            parts.append(f"'{name}'{hint}")
        plural = "s" if len(unknown) > 1 else ""
        raise UnknownFilterError(
            f"{prefix}unknown {kind}{plural} {', '.join(parts)}. Accepted: {accepted}"
        )
    chosen = {spellings[name.lower()] for name in given}
    return tuple(name for name in canonical if name in chosen)


def normalise_change_types(names: Iterable[str], label: str = "") -> tuple[str, ...]:
    """Return the canonical change types for ``--show`` or ``--hide`` names, or refuse them.

    Args:
        names: The names given, in any case
        label: What they were given as, for the message (``show_types``); empty for none

    Returns:
        The canonical names, each once, in the order of :data:`CHANGE_TYPE_NAMES`

    Raises:
        UnknownFilterError: If no name is given, or any name is not a change type
    """
    return _normalise(names, _CHANGE_SPELLINGS, CHANGE_TYPE_NAMES, "change type", label)


def normalise_entity_types(names: Iterable[str], label: str = "") -> tuple[str, ...]:
    """Return the canonical entity types for ``--entities`` names, or refuse them.

    Args:
        names: The names given, in any case, in any spelling of :data:`ENTITY_TYPE_MAP`
            or ``structures``
        label: What they were given as, for the message (``entity_types``); empty for none

    Returns:
        The canonical names, each once, in the order of :data:`ENTITY_TYPE_NAMES`

    Raises:
        UnknownFilterError: If no name is given, or any name is not an entity type
    """
    return _normalise(names, _ENTITY_SPELLINGS, ENTITY_TYPE_NAMES, "entity type", label)


def build_filter(
    show_types: Iterable[str] | None = None,
    hide_types: Iterable[str] | None = None,
    entity_types: Iterable[str] | None = None,
    labels: tuple[str, str, str] = ("show_types", "hide_types", "entity_types"),
) -> DiffFilter:
    """Check a filter and return it in canonical names.

    Args:
        show_types: Change types to show, or None if not given
        hide_types: Change types to hide, or None if not given
        entity_types: Entity types to show, or None if not given
        labels: What the three were given as, for the messages

    Returns:
        The filter, with an empty tuple for each part not given

    Raises:
        UnknownFilterError: If a part names nothing or something unknown; if both
            ``show_types`` and ``hide_types`` are given, since ``show_types`` already hides
            every change type it does not name; or if ``hide_types`` hides every change type
    """
    show_label, hide_label, entity_label = labels
    show = () if show_types is None else normalise_change_types(show_types, show_label)
    hide = () if hide_types is None else normalise_change_types(hide_types, hide_label)
    entities = () if entity_types is None else normalise_entity_types(entity_types, entity_label)
    if show and hide:
        raise UnknownFilterError(
            f"{show_label} and {hide_label} cannot be used together: {show_label} already "
            "hides every change type it does not name"
        )
    if set(hide) == set(CHANGE_TYPE_NAMES):
        raise UnknownFilterError(
            f"{hide_label} hides every change type ({', '.join(hide)}), so nothing would be shown"
        )
    return DiffFilter(show=show, hide=hide, entities=entities)


def filter_diff(
    diff: GraphDiff,
    show_types: set[str] | None = None,
    hide_types: set[str] | None = None,
    entity_types: set[str] | None = None,
) -> GraphDiff:
    """Filter a GraphDiff by change types and entity types.

    The result lists what the filter selects and counts the rest in ``not_shown``, so its
    ``is_identical`` still describes the graphs (#144). Ownerless blank-node structures follow
    the change types by action, and ``entity_types`` keeps them only if it names
    ``structures``. A diff that is already filtered is refused: what it left out was left
    out by another filter, which a second could not report truthfully.

    Args:
        diff: The diff to filter.
        show_types: If provided, only include these change types.
        hide_types: If provided, exclude these change types.
        entity_types: If provided, only include these entity types.

    Returns:
        A new GraphDiff with filtered results.

    Raises:
        UnknownFilterError: As :func:`build_filter` does: a part that names nothing or
            something unknown, ``show_types`` with ``hide_types``, or hiding every change type.
            Also if ``diff`` is already filtered.
    """
    spec = build_filter(show_types, hide_types, entity_types)
    if spec != DiffFilter() and diff.filter is not None:
        raise UnknownFilterError(
            "this diff is already filtered; filter the diff compare_files or compare_graphs "
            "returned instead"
        )
    if spec == DiffFilter():
        return replace(
            diff,
            added=list(diff.added),
            removed=list(diff.removed),
            modified=list(diff.modified),
            added_structures=list(diff.added_structures),
            removed_structures=list(diff.removed_structures),
            uncompared=list(diff.uncompared),
            not_shown=dict(diff.not_shown),
        )

    shown = set(spec.show) if spec.show else set(CHANGE_TYPE_NAMES) - set(spec.hide)

    # Determine which entity types to include
    include_entity_types: set[EntityType] | None = None
    include_structures = True
    if spec.entities:
        include_entity_types = set()
        for name in spec.entities:
            if name == STRUCTURES:
                continue
            mapped = ENTITY_TYPE_MAP[name]
            if mapped is None:  # "properties" special case
                include_entity_types.update(PROPERTY_TYPES)
            else:
                include_entity_types.add(mapped)
        include_structures = STRUCTURES in spec.entities

    not_shown = dict.fromkeys(NOT_SHOWN_KEYS, 0)

    def keep(entities: list[EntityChange], change: str) -> list[EntityChange]:
        kept = [
            e
            for e in entities
            if change in shown
            and (include_entity_types is None or e.entity_type in include_entity_types)
        ]
        not_shown[change] += len(entities) - len(kept)
        return kept

    def keep_structures(structures: list[str], action: str) -> list[str]:
        kept = structures if action in shown and include_structures else []
        not_shown["structures"] += len(structures) - len(kept)
        return list(kept)

    return GraphDiff(
        old_path=diff.old_path,
        new_path=diff.new_path,
        added=keep(diff.added, "added"),
        removed=keep(diff.removed, "removed"),
        modified=keep(diff.modified, "modified"),
        added_structures=keep_structures(diff.added_structures, "added"),
        removed_structures=keep_structures(diff.removed_structures, "removed"),
        uncompared=diff.uncompared,
        filter=spec,
        not_shown=not_shown,
    )


def parse_filter_string(filter_str: str) -> set[str]:
    """Parse a comma-separated filter string into a set.

    Args:
        filter_str: Comma-separated list (e.g., "added,removed")

    Returns:
        Set of individual filter terms.
    """
    if not filter_str:
        return set()
    return {f.strip() for f in filter_str.split(",") if f.strip()}


def _either(items: list[str] | tuple[str, ...]) -> str:
    """Join alternatives: ``a``, ``a or b``, ``a, b or c``."""
    if len(items) <= 2:
        return " or ".join(items)
    return f"{', '.join(items[:-1])} or {items[-1]}"


def _breakdown(not_shown: dict[str, int]) -> tuple[int, str]:
    """Total what a filter left out, and break it down: ``2 modified, 1 blank-node structure``."""
    parts = []
    for key in NOT_SHOWN_KEYS:
        count = not_shown.get(key, 0)
        if not count:
            continue
        if key == "structures":
            parts.append(f"{count} blank-node structure{'s' if count != 1 else ''}")
        else:
            parts.append(f"{count} {key}")
    return sum(not_shown.values()), ", ".join(parts)


def _options(spec: DiffFilter | None) -> list[tuple[str, tuple[str, ...]]]:
    """The options a filter was given as, with their values, in the order of ``--help``."""
    if spec is None:
        return []
    named = [("--show", spec.show), ("--hide", spec.hide), ("--entities", spec.entities)]
    return [(option, values) for option, values in named if values]


def not_shown_sentence(diff: GraphDiff) -> str:
    """Say that a filtered view is empty and what it left out, never that nothing changed.

    For example: ``No added changes. 3 changes not shown (2 modified, 1 blank-node
    structure) — run without --show to see them.``

    Args:
        diff: A filtered diff

    Returns:
        The sentence
    """
    spec = diff.filter or DiffFilter()
    shown = spec.show or tuple(n for n in CHANGE_TYPE_NAMES if n not in spec.hide)
    kinds = f"{_either(shown)} " if len(shown) < len(CHANGE_TYPE_NAMES) else ""
    targets = [_DISPLAY_NAMES.get(n, n.replace("_", " ")) for n in spec.entities]
    to = f" to {_either(targets)}" if targets else ""
    total, breakdown = _breakdown(diff.not_shown)
    options = " and ".join(option for option, _ in _options(diff.filter)) or "the filter"
    return (
        f"No {kinds}changes{to}. {total} change{'s' if total != 1 else ''} not shown "
        f"({breakdown}) — run without {options} to see {'it' if total == 1 else 'them'}."
    )


def not_shown_line(diff: GraphDiff) -> str:
    """Say what a filtered view that shows something left out.

    For example: ``Not shown: 2 blank-node structures (--entities classes).``

    Args:
        diff: A filtered diff with something in ``not_shown``

    Returns:
        The line
    """
    _, breakdown = _breakdown(diff.not_shown)
    options = " ".join(f"{option} {','.join(values)}" for option, values in _options(diff.filter))
    return f"Not shown: {breakdown}" + (f" ({options})." if options else ".")
