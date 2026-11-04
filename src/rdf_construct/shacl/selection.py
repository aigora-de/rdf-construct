"""Which classes get shapes, and which properties a closed shape ignores.

One resolver serves ``--classes``, ``target_classes``, ``exclude_classes`` and
``ignored_properties``. A CURIE or an IRI is resolved strictly through
`rdf_construct.core.utils.resolve_curie`, against the source graph's own prefix bindings,
and compared by equality. A bare local name, one with no ``:``, is looked up among the
classes the source declares (#226, #356).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rdflib import RDF, Graph, URIRef

from rdf_construct.core.utils import CurieError, extract_prefix_map, resolve_curie
from rdf_construct.core.vocab import CLASS_TYPES

from .config import StrictnessLevel

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .config import ShaclConfig


class ShaclSelectionError(ValueError):
    """A class selection or an ignored property that cannot be honoured.

    Every problem found is collected before this is raised, so one run names all of them.

    Attributes:
        problems: One line per problem, each naming the entry as given.
    """

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems = tuple(problems)
        super().__init__("\n".join(self.problems))


@dataclass(frozen=True)
class Selection:
    """The resolved selection for one source.

    Attributes:
        classes: The classes that get a shape.
        targets: The classes ``target_classes`` named, resolved; empty when none were given.
        ignored_properties: What a closed shape ignores: ``rdf:type`` first, no duplicates.
        notes: Things worth saying that do not stop the run.
    """

    classes: tuple[URIRef, ...]
    targets: tuple[URIRef, ...]
    ignored_properties: tuple[URIRef, ...]
    notes: tuple[str, ...]


def local_name(iri: str) -> str:
    """The part of an IRI after its namespace.

    After the last ``#`` if there is one, else after the last ``/``, else after the last
    ``:``, so ``urn:x:Cat`` gives ``Cat`` and ``http://ex.org/a/b:c`` gives ``b:c``.

    Args:
        iri: The IRI.

    Returns:
        The local name, possibly empty.
    """
    return iri[len(namespace_of(iri)) :]


def namespace_of(iri: str) -> str:
    """The namespace part of an IRI, up to and including its last delimiter.

    The counterpart of `local_name`.

    Args:
        iri: The IRI.

    Returns:
        The namespace, or the empty string if the IRI has no delimiter.
    """
    for delimiter in "#/:":
        cut = iri.rfind(delimiter)
        if cut != -1:
            return iri[: cut + 1]
    return ""


def display(iri: URIRef, prefixes: Mapping[str, str]) -> str:
    """An IRI as a CURIE where a bound prefix covers it, else in angle brackets.

    Never binds a prefix, unlike rdflib's namespace manager.

    Args:
        iri: The IRI.
        prefixes: Prefix to namespace IRI.

    Returns:
        ``pfx:local`` using the longest matching namespace, or ``<iri>``.
    """
    s = str(iri)
    best: tuple[str, str] | None = None
    for pfx, ns in prefixes.items():
        if ns and s.startswith(ns) and len(s) > len(ns):
            rest = s[len(ns) :]
            if "/" in rest or "#" in rest:
                continue
            if (
                best is None
                or len(ns) > len(prefixes[best[0]])
                or (len(ns) == len(prefixes[best[0]]) and pfx < best[0])
            ):
                best = (pfx, rest)
    if best is None:
        return f"<{s}>"
    return f"{best[0]}:{best[1]}"


def declared_classes(graph: Graph) -> set[URIRef]:
    """Every named class the graph declares with a type in `CLASS_TYPES`.

    Args:
        graph: The source graph.

    Returns:
        The declared classes.
    """
    found: set[URIRef] = set()
    for class_type in CLASS_TYPES:
        for subject in graph.subjects(RDF.type, class_type):
            if isinstance(subject, URIRef):
                found.add(subject)
    return found


def _patterns(iri: URIRef) -> tuple[tuple[URIRef | None, URIRef | None, URIRef | None], ...]:
    """Triple patterns that find an IRI in any position."""
    return ((iri, None, None), (None, iri, None), (None, None, iri))


def _rdflib_table() -> dict[str, str]:
    """rdflib's built-in prefix table, read through a graph so no private name is used."""
    return {p: str(ns) for p, ns in Graph(bind_namespaces="rdflib").namespaces()}


def _curie_problem(key: str, text: str, error: CurieError) -> str:
    """Explain a CurieError, with the IRI rdflib's table would give if it knows the prefix."""
    if error.prefix is None:
        return f"{key}: {text!r} is not a CURIE or an IRI"
    message = (
        f"{key}: {text!r}: prefix {error.prefix!r} is not bound in this source "
        f"(bound: {', '.join(p or '(default)' for p in error.bound) or 'none'})"
    )
    known = _rdflib_table().get(error.prefix)
    if known is not None:
        local = text.strip().split(":", 1)[1]
        message += f"; write <{known}{local}> if you mean {error.prefix}: as {known}"
    else:
        message += f"; to give an IRI, write it in angle brackets (<{text.strip()}>)"
    return message


def _check_list(key: str, value: object) -> str | None:
    """A problem if the value is not a list of strings, else None."""
    if not isinstance(value, list | tuple):
        return f"{key} must be a list, got {type(value).__name__} {value!r}"
    for item in value:
        if not isinstance(item, str):
            return f"{key} must be a list of strings, got {type(item).__name__} {item!r}"
    return None


class _ClassResolver:
    """Resolves class entries against one source."""

    def __init__(self, graph: Graph, shaped: set[URIRef], prefixes: Mapping[str, str]) -> None:
        self.graph = graph
        self.shaped = shaped
        self.prefixes = prefixes
        self.declared = declared_classes(graph) | shaped
        self.by_local: dict[str, list[URIRef]] = {}
        for cls in self.declared:
            self.by_local.setdefault(local_name(str(cls)), []).append(cls)
        for matches in self.by_local.values():
            matches.sort(key=str)

    def resolve(self, key: str, text: str) -> tuple[URIRef | None, str | None]:
        """Resolve one entry to a shaped class, or explain why it names none."""
        entry = text.strip()
        if not entry:
            return None, f"{key}: an empty entry (a stray comma?) names no class"
        if ":" not in entry:
            matches = self.by_local.get(entry, [])
            if not matches:
                hint = difflib.get_close_matches(entry, sorted(self.by_local), n=3)
                suggestion = f"; did you mean {', '.join(hint)}?" if hint else ""
                return None, f"{key}: {text!r} names no class in this source{suggestion}"
            if len(matches) > 1:
                names = ", ".join(display(m, self.prefixes) for m in matches)
                return None, (
                    f"{key}: {text!r} matches {len(matches)} classes ({names}); "
                    "name one as a CURIE or an IRI"
                )
            iri = matches[0]
        else:
            try:
                iri = resolve_curie(self.prefixes, entry)
            except CurieError as error:
                return None, _curie_problem(key, text, error)
        return self._classify(key, text, iri)

    def _classify(self, key: str, text: str, iri: URIRef) -> tuple[URIRef | None, str | None]:
        if iri in self.shaped:
            return iri, None
        shown = display(iri, self.prefixes)
        named = repr(text) if text.strip() == shown else f"{text!r} ({shown})"
        if iri in self.declared:
            types = sorted(
                display(t, self.prefixes)
                for t in self.graph.objects(iri, RDF.type)
                if isinstance(t, URIRef) and t in CLASS_TYPES
            )
            return None, (
                f"{key}: {named} is declared only as {', '.join(types)}, "
                "which shacl-gen does not shape yet (#228)"
            )
        if any(pattern in self.graph for pattern in _patterns(iri)):
            return (
                None,
                f"{key}: {named} is only referenced, not declared as a class in this source",
            )
        return None, f"{key}: {named} names no class in this source"


def resolve_selection(graph: Graph, config: ShaclConfig, shaped: Iterable[URIRef]) -> Selection:
    """Resolve a configuration's class selection and ignored properties against a source.

    CURIEs resolve against ``graph``'s own prefix bindings, whatever they are: a source
    parsed with ``Graph(bind_namespaces="core")`` has the file's prefixes plus rdf, rdfs, owl,
    xsd and xml, while a bare ``Graph()`` also has rdflib's built-in table.

    Args:
        graph: The source graph.
        config: The generation configuration.
        shaped: The classes the generator can shape, in the order shapes are made.

    Returns:
        The selection.

    Raises:
        ShaclSelectionError: Listing every target that names no shapeable class, every
            ignored property that cannot be resolved, every key that is not a list of
            strings, and a selection left empty.
    """
    problems: list[str] = []
    notes: list[str] = []
    shaped_order = list(shaped)
    shaped_set = set(shaped_order)
    prefixes = extract_prefix_map(graph)

    for key in ("target_classes", "exclude_classes", "ignored_properties"):
        problem = _check_list(key, getattr(config, key))
        if problem:
            problems.append(problem)
    if problems:
        raise ShaclSelectionError(problems)

    resolver = _ClassResolver(graph, shaped_set, prefixes)

    targets: list[URIRef] = []
    for text in config.target_classes:
        iri, problem = resolver.resolve("target_classes", text)
        if problem:
            problems.append(problem)
        elif iri is not None and iri not in targets:
            targets.append(iri)

    excluded: list[URIRef] = []
    for text in config.exclude_classes:
        iri, problem = resolver.resolve("exclude_classes", text)
        if problem:
            notes.append(f"{problem}; it excludes nothing")
        elif iri is not None and iri not in excluded:
            excluded.append(iri)

    ignored: list[URIRef] = [URIRef(RDF.type)]
    for text in config.ignored_properties:
        try:
            prop = resolve_curie(prefixes, text)
        except CurieError as error:
            problems.append(_curie_problem("ignored_properties", text, error))
            continue
        if prop not in ignored:
            ignored.append(prop)

    if problems:
        raise ShaclSelectionError(problems)

    for iri in excluded:
        if iri in targets:
            notes.append(
                f"exclude_classes: {display(iri, prefixes)} is also a target; it is excluded"
            )

    wanted = set(targets) if config.target_classes else shaped_set
    removed = set(excluded)
    classes = [c for c in shaped_order if c in wanted and c not in removed]

    if not classes and (config.target_classes or config.exclude_classes):
        raise ShaclSelectionError(
            ["the selection is empty: no class is left once exclude_classes is applied"]
        )

    if config.ignored_properties and not (config.closed and config.level is StrictnessLevel.STRICT):
        notes.append(
            "ignored_properties has no effect: shapes are closed only with --closed "
            "at --level strict"
        )

    return Selection(
        classes=tuple(classes),
        targets=tuple(targets),
        ignored_properties=tuple(ignored),
        notes=tuple(notes),
    )
