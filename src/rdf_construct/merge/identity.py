"""The merged document's ontology identity: at most one header (#171).

A merge writes one document, and an OWL 2 ontology document holds one ontology. So the merged
graph carries at most one ``owl:Ontology``:

- **Kept.** When every source declares exactly one header, all at one IRI with one set of version
  IRIs, the sources are parts of one identity (a single source, a file merged with itself, modules
  split under a shared ``ontology_iri:``), and the header is left as it is.
- **Named.** Given an IRI (``--ontology-iri``, or ``namespaces.base`` in a config), the merged
  graph gets one header at it, no ``owl:versionIRI``, and one ``prov:wasDerivedFrom`` per source
  naming that source's version IRI, or its ontology IRI where it has none.
- **Unnamed.** Otherwise, no header at all. The caller warns and shows the command that names it.

Either of the last two **demotes** every source header: it removes the ``owl:Ontology`` type, the
``owl:versionIRI``, and the four predicates whose ``rdfs:domain`` is ``owl:Ontology``
(``owl:imports``, ``owl:priorVersion``, ``owl:backwardCompatibleWith``, ``owl:incompatibleWith``),
any of which would make the subject an ontology again under RDFS entailment. Nothing else goes:
the IRI may be punned, and its title, licence and ``owl:versionInfo`` describe that source truly.
A named merge carries the demoted headers' imports onto its own header, except those of an
ontology the merge contains (a self-import).

Like ``core/``, nothing here prints or imports Click: it reports what it did in
:class:`MergeIdentity`, and the command says it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rdflib import RDF, BNode, Graph, URIRef
from rdflib.namespace import OWL, PROV
from rdflib.term import Node

from rdf_construct.core.provenance import derivation_targets, stamp_derivation, strip_version_iri

ONTOLOGY_ONLY: tuple[URIRef, ...] = (
    OWL.imports,
    OWL.priorVersion,
    OWL.backwardCompatibleWith,
    OWL.incompatibleWith,
)
"""Predicates whose ``rdfs:domain`` is ``owl:Ontology``: a demoted header loses them too."""

CORE_PREFIXES: dict[str, str] = {
    "rdf": str(RDF),
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": str(OWL),
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "xml": "http://www.w3.org/XML/1998/namespace",
}
"""The prefixes every merge binds, against which a CURIE-looking IRI is checked too."""

_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:.")
_FORBIDDEN = set('<>"{}|\\^`')

Triple = tuple[Node, Node, Node]


@dataclass(frozen=True)
class SourceHeaders:
    """One source's ontology headers, read before any namespace remapping.

    Attributes:
        name: The source file's name.
        headers: Its ``owl:Ontology`` subjects as read.
        targets: What a derivation stamp names it by: each header's version IRIs, else its IRI.
    """

    name: str
    headers: tuple[Node, ...]
    targets: tuple[URIRef, ...]


@dataclass
class MergeIdentity:
    """What the merge did to ontology headers.

    Attributes:
        ontology: The merged ontology's IRI: the one given, or the sources' shared one when
            ``kept``. ``None`` when the output has no header, or keeps a blank-node one.
        kept: True when the sources' one shared header was left as it is.
        demoted: Each demoted header and the source that declared it, in source order.
        moved_imports: Imports carried onto the named header.
        dropped_imports: Imports of a demoted header that an unnamed merge could not carry. Naming
            the merge carries them.
        self_imports: Imports dropped because the merge contains what they import.
        stamped: Per source, its name and the ``prov:wasDerivedFrom`` targets the named header
            gives it.
        unstamped: Sources a named merge could not name, each with the reason.
        notes: Lines the caller should show, about an IRI the user chose.
        removed: Source triples the demotion removed, which the output no longer holds. A
            blank-node header's are under the label the merge gave its node (#170).
    """

    ontology: URIRef | None = None
    kept: bool = False
    demoted: list[tuple[Node, str]] = field(default_factory=list)
    moved_imports: list[URIRef] = field(default_factory=list)
    dropped_imports: list[URIRef] = field(default_factory=list)
    self_imports: list[URIRef] = field(default_factory=list)
    stamped: list[tuple[str, list[URIRef]]] = field(default_factory=list)
    unstamped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    removed: list[Triple] = field(default_factory=list)

    @property
    def unnamed(self) -> bool:
        """True when source headers were demoted and nothing names the result."""
        return bool(self.demoted) and self.ontology is None


def read_headers(graph: Graph, name: str) -> SourceHeaders:
    """Read one source's headers and derivation targets, as the source states them.

    Args:
        graph: The source graph, before any namespace remapping.
        name: The source file's name.

    Returns:
        The headers in a stable order and the targets a stamp would name.
    """
    headers = tuple(sorted(set(graph.subjects(RDF.type, OWL.Ontology)), key=str))
    targets: list[URIRef] = []
    for header in headers:
        for target in derivation_targets(graph, header):
            if target not in targets:
                targets.append(target)
    return SourceHeaders(name=name, headers=headers, targets=tuple(targets))


def check_ontology_iri(value: object) -> URIRef:
    """Check that an ontology IRI the user gave is an absolute IRI.

    Args:
        value: The value given.

    Returns:
        It, as an IRI.

    Raises:
        ValueError: Naming what is wrong with it.
    """
    if not isinstance(value, str):
        raise ValueError(f"{value!r} is not an IRI")
    if not value.strip():
        raise ValueError("it is empty")
    bad = sorted({c for c in value if c in _FORBIDDEN or c.isspace() or not c.isprintable()})
    if bad:
        shown = ", ".join(repr(c) for c in bad)
        raise ValueError(f"{value!r} contains {shown}, which an IRI cannot")
    if not _SCHEME.match(value):
        raise ValueError(f"{value!r} is not an absolute IRI: it has no scheme, such as http:")
    return URIRef(value)


def curie_clash(value: str, declared: list[tuple[str, dict[str, str]]]) -> str | None:
    """Say whether an IRI the user gave reads as a CURIE in one of the sources' prefixes.

    ``ex:Merged`` is a well-formed IRI with the scheme ``ex``, so it passes
    :func:`check_ontology_iri`. When a source binds ``ex:``, it was almost certainly meant as a
    prefixed name, which the header would not expand.

    Args:
        value: The IRI given.
        declared: Each source's name and its prefix bindings.

    Returns:
        The reason to refuse it, naming the expansion, or ``None``.
    """
    prefix, _, local = value.partition(":")
    if local.startswith("//"):
        return None
    for name, prefixes in [*declared, ("the prefixes every merge binds", CORE_PREFIXES)]:
        if prefix in prefixes:
            expansion = prefixes[prefix] + local
            return (
                f"{value!r} reads as a prefixed name: {prefix}: is bound to <{prefixes[prefix]}> "
                f"in {name}. Give the full IRI: {expansion}"
            )
    return None


def _same_identity(sources: list[tuple[SourceHeaders, Graph]]) -> bool:
    """Whether every source declares exactly one header, all one subject with one set of versions.

    A blank-node header counts: copies of one file share it once blank nodes are labelled by
    content (#170), so a file with an anonymous ontology, alone or with itself, is kept.
    """
    seen: set[tuple[Node, frozenset[Node]]] = set()
    for _, graph in sources:
        headers = set(graph.subjects(RDF.type, OWL.Ontology))
        if len(headers) != 1:
            return False
        [header] = headers
        seen.add((header, frozenset(graph.objects(header, OWL.versionIRI))))
    return len(seen) == 1


def apply_identity(
    merged: Graph,
    sources: list[tuple[SourceHeaders, Graph]],
    ontology: URIRef | None,
    carry_imports: bool,
) -> MergeIdentity:
    """Give the merged graph at most one ontology header, demoting the sources' own.

    Args:
        merged: The merged graph, changed in place.
        sources: Per source, its headers as read and its graph as merged (after remapping).
        ontology: The IRI to name the merged ontology, or ``None``.
        carry_imports: Whether a named header takes the demoted headers' imports. False under
            ``--imports remove``.

    Returns:
        What was done.
    """
    identity = MergeIdentity()
    declared = [
        (header, read.name)
        for read, graph in sources
        for header in sorted(set(graph.subjects(RDF.type, OWL.Ontology)), key=str)
    ]
    if ontology is None and not declared:
        return identity
    if ontology is None and _same_identity(sources):
        identity.kept = True
        [header] = {h for h, _ in declared}
        identity.ontology = header if isinstance(header, URIRef) else None
        return identity

    own: set[Node] = set()
    for header, _ in declared:
        own.add(header)
        own.update(merged.objects(header, OWL.versionIRI))
    for read, _ in sources:
        own.update(read.targets)
        own.update(read.headers)
    if ontology is not None:
        own.add(ontology)
        named_as = sorted({name for header, name in declared if header == ontology})
        if named_as:
            identity.notes.append(
                f"Note: {ontology} is the ontology IRI of {', '.join(named_as)}; the merged "
                "ontology takes that identity, and every other source's content joins it."
            )
        elif any(
            pattern in merged
            for pattern in ((ontology, None, None), (None, ontology, None), (None, None, ontology))
        ):
            identity.notes.append(
                f"Note: {ontology} is already a term in the sources; the merged header "
                "shares its IRI."
            )

    imports: list[URIRef] = []
    seen: set[Node] = set()
    for header, name in declared:
        if header in seen:
            continue
        seen.add(header)
        identity.demoted.append((header, name))
        before = set(merged.triples((header, None, None)))
        merged.remove((header, RDF.type, OWL.Ontology))
        strip_version_iri(merged, header)
        for predicate in ONTOLOGY_ONLY:
            if predicate == OWL.imports:
                for target in merged.objects(header, OWL.imports):
                    if isinstance(target, URIRef) and target not in imports:
                        imports.append(target)
            merged.remove((header, predicate, None))
        identity.removed.extend(sorted(before - set(merged.triples((header, None, None)))))
    # A header declared in two sources was demoted under the first; name each source anyway
    for header, name in declared:
        if (header, name) not in identity.demoted:
            identity.demoted.append((header, name))

    for target in imports:
        if target in own:
            identity.self_imports.append(target)
        elif ontology is None:
            identity.dropped_imports.append(target)
        elif carry_imports:
            identity.moved_imports.append(target)

    if ontology is None:
        return identity

    identity.ontology = ontology
    prov_bound = any(str(ns) == str(PROV) for _, ns in merged.namespaces())
    merged.add((ontology, RDF.type, OWL.Ontology))
    for target in identity.moved_imports:
        merged.add((ontology, OWL.imports, target))
    for read, _ in sources:
        targets = [t for t in read.targets if t != ontology]
        if targets:
            stamp_derivation(merged, ontology, targets)
            identity.stamped.append((read.name, targets))
        elif read.targets:
            identity.unstamped.append(f"{read.name} (its ontology IRI is the merged one)")
        elif read.headers:
            identity.unstamped.append(f"{read.name} (a blank-node header, which nothing names)")
        else:
            identity.unstamped.append(f"{read.name} (no ontology header)")
    # A source that holds prov: for another namespace keeps it, and the stamp's is renamed (#357)
    written_as = {str(ns): prefix for prefix, ns in merged.namespaces()}.get(str(PROV))
    if identity.stamped and not prov_bound and written_as not in (None, "prov"):
        held = {prefix: str(ns) for prefix, ns in merged.namespaces()}.get("prov")
        identity.notes.append(
            f'Note: the derivation stamp declares "prov:" for <{PROV}>, which the sources use '
            f'for <{held}>; written as "{written_as}:". Set namespaces.preferred_prefixes to '
            "choose."
        )
    # The merged header re-adds what it shares with a demoted one of the same IRI
    identity.removed = [t for t in identity.removed if t not in merged]
    return identity


def describe(header: Node, name: str) -> str:
    """Name a demoted header for the user.

    Args:
        header: The header's subject.
        name: The source that declared it.

    Returns:
        ``<IRI> (name)``, or ``a blank-node header in name``.
    """
    if isinstance(header, BNode):
        return f"a blank-node header in {name}"
    return f"<{header}> ({name})"
