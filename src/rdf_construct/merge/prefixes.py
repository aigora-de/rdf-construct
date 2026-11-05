"""Prefix bindings for a graph built from several sources (#357, #358).

`merge` writes one file from many, and each source declares its own prefixes. This module decides
which prefix each namespace is written with:

1. ``namespaces.preferred_prefixes`` claim first, then rdf, rdfs, owl, xsd and xml, then each
   source's declarations in command-line order. A namespace keeps the first prefix it is given.
2. A declaration whose prefix another namespace already holds loses it. Once every declaration
   has been seen, each loser is named: a named prefix gets a number (``ex1:``), and the empty
   prefix ``:`` is named after its namespace's last path segment (``…/ont#`` gives ``ont:``),
   or ``default1:`` when that segment is not a valid prefix. A generated name never takes a
   prefix that any source declares.
3. rdflib's built-in table then names a namespace that nothing else names, under a prefix that is
   still free, so a source that cannot declare prefixes (N-Triples) keeps ``foaf:`` without that
   table ever displacing a prefix a source declared.

Every source declaration that is not written as declared yields one note for the user.
"""

from __future__ import annotations

import re
from functools import cache
from typing import TYPE_CHECKING

from rdflib import Graph, Namespace

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

# A prefix this module will generate: ASCII PN_PREFIX, which may not end with a dot.
_VALID_PREFIX = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*(?<!\.)$")
_SEGMENT_DELIMITERS = "#/:"


@cache
def core_bindings() -> tuple[tuple[str, str], ...]:
    """The bindings every ``bind_namespaces="core"`` graph starts with (rdf, rdfs, owl, xsd, xml)."""
    return tuple((p, str(ns)) for p, ns in Graph(bind_namespaces="core").namespaces())


@cache
def _rdflib_table() -> tuple[tuple[str, str], ...]:
    """rdflib's built-in prefix table, as a bare ``Graph()`` binds it."""
    return tuple((p, str(ns)) for p, ns in Graph(bind_namespaces="rdflib").namespaces())


def _shown(prefix: str) -> str:
    """A prefix as a reader sees it in Turtle: ``ex:``, or ``:`` for the empty prefix."""
    return f'"{prefix}:"'


def _segment_name(namespace: str) -> str | None:
    """The namespace's last path segment, if it is a valid prefix (``…/ont#`` gives ``ont``)."""
    segments = [s for s in re.split(r"[#/:]", namespace.rstrip(_SEGMENT_DELIMITERS)) if s]
    if segments and _VALID_PREFIX.match(segments[-1]):
        return segments[-1]
    return None


def combine_prefixes(
    sources: Sequence[tuple[str, Iterable[tuple[str, str]]]],
    preferred: Mapping[str, str] | None = None,
    advice: str = " Set namespaces.preferred_prefixes to choose.",
) -> tuple[dict[str, str], list[str]]:
    """Decide the prefix each namespace is written with, across several sources.

    Args:
        sources: Each source's name (used in notes) with its prefix bindings, in the order the
            sources were given.
        preferred: ``namespaces.preferred_prefixes``: prefix to namespace, claimed before any
            source.
        advice: Appended to the note for a renamed binding: how the user can choose instead.

    Returns:
        The prefix to namespace map to bind, and one note per source declaration that is not
        written as declared.
    """
    preferred = preferred or {}
    claimed: dict[str, str] = {}  # prefix -> namespace
    prefix_of: dict[str, str] = {}  # namespace -> prefix
    holder: dict[str, str | None] = {}  # prefix -> the source that claimed it (None: not a source)
    losers: list[tuple[str | None, str, str]] = []  # (source, prefix, namespace)
    notes: list[str] = []
    chosen: set[str] = set()  # the namespaces preferred_prefixes names

    source_bindings = [(name, [(p, str(ns)) for p, ns in b]) for name, b in sources]
    declared = {p for _, b in source_bindings for p, _ in b}

    def claim(prefix: str, namespace: str, owner: str | None) -> None:
        claimed[prefix] = namespace
        prefix_of[namespace] = prefix
        holder[prefix] = owner

    def note_written_as(prefix: str, namespace: str, owner: str | None) -> None:
        # A namespace preferred_prefixes names is not noted: the user chose its prefix
        if owner is not None and namespace not in chosen:
            notes.append(
                f"Note: {owner} declares {_shown(prefix)} for <{namespace}>, which is "
                f"written as {_shown(prefix_of[namespace])}."
            )

    def offer(prefix: str, namespace: str, owner: str | None) -> None:
        if prefix_of.get(namespace) == prefix:
            return
        if namespace in prefix_of:
            note_written_as(prefix, namespace, owner)
            return
        if prefix in claimed:
            losers.append((owner, prefix, namespace))
            return
        claim(prefix, namespace, owner)

    for prefix, namespace in preferred.items():
        offer(prefix, str(namespace), None)
    chosen.update(prefix_of)
    for prefix, namespace in core_bindings():
        offer(prefix, namespace, None)
    for name, bindings in source_bindings:
        for prefix, namespace in bindings:
            offer(prefix, namespace, name)

    # Name the losers only now, so a generated name never takes a prefix a later source declares
    taken = set(claimed) | declared | set(preferred)
    for owner, prefix, namespace in losers:
        if namespace in prefix_of:
            note_written_as(prefix, namespace, owner)
            continue
        new = _generated_prefix(prefix, namespace, taken)
        taken.add(new)
        held_ns = claimed[prefix]
        claim(new, namespace, owner)
        if owner is None:
            continue
        by = holder[prefix]
        if by is not None:
            whose = f"which {by} uses for <{held_ns}>"
        elif prefix in preferred:
            whose = f"which namespaces.preferred_prefixes gives to <{held_ns}>"
        else:
            whose = f"which is reserved for <{held_ns}>"
        notes.append(
            f"Note: {owner} declares {_shown(prefix)} for <{namespace}>, {whose}; written as "
            f"{_shown(new)}.{advice}"
        )

    return claimed, notes


def _generated_prefix(prefix: str, namespace: str, taken: set[str]) -> str:
    """A free prefix for a namespace that lost ``prefix`` to another namespace.

    A named prefix gets the smallest free number (``ex1``). The empty prefix is named after the
    namespace's last path segment, numbered from 1 if taken, or ``default1`` when the segment is not
    a valid prefix.
    """
    if prefix:
        stem = prefix
    else:
        segment = _segment_name(namespace)
        if segment is not None and segment not in taken:
            return segment
        stem = segment if segment is not None else "default"
    n = 1
    while f"{stem}{n}" in taken:
        n += 1
    return f"{stem}{n}"


def table_gaps(bound: Iterable[tuple[str, object]]) -> list[tuple[str, str]]:
    """rdflib's table entries whose prefix is free and whose namespace is unbound.

    Args:
        bound: The bindings already made, prefix to namespace.

    Returns:
        The entries to add, in rdflib's order.
    """
    pairs = [(p, str(ns)) for p, ns in bound]
    prefixes = {p for p, _ in pairs}
    namespaces = {ns for _, ns in pairs}
    return [(p, ns) for p, ns in _rdflib_table() if p not in prefixes and ns not in namespaces]


def fill_table_gaps(graph: Graph) -> None:
    """Bind rdflib's table where it names a namespace nothing else names, under a free prefix."""
    for prefix, namespace in table_gaps(graph.namespaces()):
        graph.bind(prefix, Namespace(namespace), override=False)


def bind_exactly(graph: Graph, prefixes: Mapping[str, str]) -> None:
    """Bind ``prefixes`` exactly, then fill the gaps from rdflib's table.

    Args:
        graph: A graph made with ``bind_namespaces="core"``.
        prefixes: Prefix to namespace, as `combine_prefixes` decided.
    """
    for prefix, namespace in prefixes.items():
        graph.bind(prefix, Namespace(namespace), override=True, replace=True)
    fill_table_gaps(graph)
