"""What a derived artefact may claim about its own identity (#90, #171, #178).

A command that writes something other than its source — an extract, a merge, a module — must not
let the output claim to *be* that source. The rule, decided in cluster 1 of the #126 decision
round, has three parts, and this module offers each one on its own so that every command applies
the same answer:

- **What names a source**: its ``owl:versionIRI`` where it has one, else its ontology IRI
  (:func:`derivation_targets`).
- **Strip the version IRI**: ``owl:versionIRI`` is the one header triple that is a claim about
  particular bytes, so a derived document never carries its source's (:func:`strip_version_iri`).
- **Record the derivation**: ``prov:wasDerivedFrom`` naming each source, an annotation, so it
  changes no entailment (:func:`stamp_derivation`).

``prov:wasDerivedFrom`` rather than ``dcterms:source``, because ``docs`` already reads
``dcterms:source`` as metadata an author wrote. The property is declared as an
``owl:AnnotationProperty`` wherever it is used: an undeclared annotation property is itself
outside OWL 2 DL.

**Who uses what.** ``order`` (#90) keeps the ontology IRI and calls :func:`stamp_extract`, which
composes the three for every header in an extract. ``split`` (#178) names each module by its own
ladder and calls :func:`stamp_derivation` on the module's IRI with the source's
:func:`derivation_targets`. ``merge`` (#171) names the merged ontology itself, demotes each source
header — :func:`strip_version_iri` plus removing that subject's ``a owl:Ontology``, and nothing
else, since an IRI may be punned — and calls :func:`stamp_derivation` with one target per source.
The ladders and the demotion are those commands' own; nothing here mints an IRI.

**It reports and never decides.** Nothing here prints, and whether a run is derived at all is the
caller's question: :func:`missing_triples` measures it on the graph the caller is about to write,
under the 4d principle that a summary is derived from what was written. Like the rest of
``core/``, this module imports no Click.

None of it touches SKOS: a ``skos:ConceptScheme`` is not an ontology header.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rdflib import RDF, Graph, URIRef
from rdflib.namespace import OWL, PROV

if TYPE_CHECKING:
    from rdflib.term import Node

ONTOLOGY: URIRef = OWL.Ontology
"""The type that makes a subject an ontology header."""

VERSION_IRI: URIRef = OWL.versionIRI
"""The header triple that identifies one version of an ontology: never copied into a derivative."""

WAS_DERIVED_FROM: URIRef = PROV.wasDerivedFrom
"""The stamp a derived artefact carries, naming what it was derived from."""

PROV_PREFIX = "prov"
"""The prefix the stamp is written under, unless the graph already binds PROV-O to another."""


@dataclass(frozen=True)
class Stamp:
    """What :func:`stamp_extract` did to one ontology header.

    Attributes:
        ontology: The header's subject. Its IRI is unchanged.
        removed: The ``owl:versionIRI`` values removed from it, sorted.
        derived_from: The ``prov:wasDerivedFrom`` targets added to it, sorted. Empty when nothing
            names the source: a blank-node header with no version IRI.
    """

    ontology: Node
    removed: tuple[Node, ...]
    derived_from: tuple[URIRef, ...]


def derivation_targets(source: Graph, ontology: Node) -> list[URIRef]:
    """Name a source ontology the way a derivation stamp names it.

    Args:
        source: The graph that declares the ontology.
        ontology: The ontology's subject in ``source``.

    Returns:
        Its ``owl:versionIRI`` values, sorted; else the ontology IRI itself; else an empty list,
        for a blank-node ontology with no version IRI, which nothing names.
    """
    versions = sorted(v for v in source.objects(ontology, VERSION_IRI) if isinstance(v, URIRef))
    if versions:
        return versions
    if isinstance(ontology, URIRef):
        return [ontology]
    return []


def strip_version_iri(graph: Graph, ontology: Node) -> list[Node]:
    """Remove every ``owl:versionIRI`` from one ontology header, and nothing else.

    Args:
        graph: The derived graph, changed in place.
        ontology: The header's subject.

    Returns:
        The values removed, sorted.
    """
    removed = sorted(graph.objects(ontology, VERSION_IRI), key=str)
    graph.remove((ontology, VERSION_IRI, None))
    return removed


def stamp_derivation(graph: Graph, subject: Node, targets: list[URIRef]) -> None:
    """Record that ``subject`` was derived from each of ``targets``.

    Adds one ``prov:wasDerivedFrom`` per target, declares ``prov:wasDerivedFrom`` an
    ``owl:AnnotationProperty``, and binds the ``prov:`` prefix. A graph that already binds the
    PROV-O namespace keeps its own prefix for it, and one that binds ``prov:`` to something else
    keeps that binding: rdflib then picks another prefix for PROV-O. Does nothing when
    ``targets`` is empty.

    Args:
        graph: The derived graph, changed in place.
        subject: The derived artefact's ontology subject.
        targets: What it was derived from, normally from :func:`derivation_targets`.
    """
    if not targets:
        return
    for target in targets:
        graph.add((subject, WAS_DERIVED_FROM, target))
    graph.add((WAS_DERIVED_FROM, RDF.type, OWL.AnnotationProperty))
    graph.namespace_manager.bind(PROV_PREFIX, PROV, override=False, replace=False)


def missing_triples(source: Graph, written: Graph) -> int:
    """Count the source triples that a graph about to be written does not hold.

    Non-zero means the output is derived from the source rather than a rewriting of it, however
    the command arrived there.

    Args:
        source: The graph that was read.
        written: The graph that will be written.

    Returns:
        The number of triples of ``source`` absent from ``written``.
    """
    return sum(1 for triple in source if triple not in written)


def stamp_extract(source: Graph, extract: Graph) -> list[Stamp]:
    """Give an extract of ``source`` an honest header, keeping each ontology's IRI.

    For every ontology header in ``extract``: remove its ``owl:versionIRI`` and add
    ``prov:wasDerivedFrom`` naming the source as :func:`derivation_targets` names it.
    ``owl:versionInfo``, ``owl:imports`` and every other annotation stay. Call it only on a
    graph that :func:`missing_triples` says is derived.

    Args:
        source: The graph the extract was taken from.
        extract: The extract, changed in place.

    Returns:
        One :class:`Stamp` per header, ordered by subject.
    """
    stamps: list[Stamp] = []
    for ontology in sorted(set(extract.subjects(RDF.type, ONTOLOGY)), key=str):
        targets = derivation_targets(source, ontology)
        removed = strip_version_iri(extract, ontology)
        stamp_derivation(extract, ontology, targets)
        stamps.append(Stamp(ontology, tuple(removed), tuple(targets)))
    return stamps
