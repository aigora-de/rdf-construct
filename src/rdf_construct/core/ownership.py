"""Whose term is this: the one answer to "this ontology's own terms" (#69, #368, #371).

A file declares terms it does not own. OWL 2 DL asks it to declare every annotation property it
uses, so ``dcterms:creator a owl:AnnotationProperty`` and the derivation stamp's
``prov:wasDerivedFrom a owl:AnnotationProperty`` sit beside the ontology's own classes. A command
that reports on "the ontology's terms" must not treat those as the author's: ``lint`` would ask for
a label the author cannot write, ``docs`` would document someone else's term, ``stats`` would count
it. This module is the answer all of them use, so that none ships its own.

**Foreign** (:meth:`Ownership.is_foreign`) means either of:

- **borrowed**: the file names an ontology, and none of its ontologies owns the term's
  namespace (:func:`is_borrowed`). An ontology owns its own host; on a host many publishers share
  (:data:`SHARED_HOSTS`) it owns only the space under its own IRI. This is the rule ``split``
  decided for #383, moved here unchanged. A file that names no ontology gives nothing to judge by,
  so it borrows nothing;
- **external**: within a namespace the caller names as external, matched at a boundary
  (:func:`~rdf_construct.core.utils.in_namespace`). ``lint`` reads these from
  ``external_namespaces:`` in ``.rdf-lint.yml``; resolving a CURIE to an IRI is the caller's job.

No namespace is cut here: the rule compares hosts and matches IRIs, and never derives a namespace
from a term (#384). ``lint``'s ``dangling-reference`` adds its own threshold, two or more
definitions in a namespace before it checks references there (#69); that is evidence for checking
references, not a claim about who owns the namespace, so it stays in ``lint``.

:func:`ontology_references` names the IRIs a file uses to point at ontologies, not at terms: the
objects of the predicates only an ontology takes, of ``owl:versionIRI``, and of the derivation
stamp on a header.

``describe``'s local namespaces (#295) adopt :meth:`Ownership.is_foreign` when they land. Like the
rest of ``core/``, this module reports and never decides, and imports no Click.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

from .provenance import ONTOLOGY, ONTOLOGY_ONLY, VERSION_IRI, WAS_DERIVED_FROM
from .utils import in_namespace

if TYPE_CHECKING:
    from collections.abc import Iterable

    from rdflib.term import Node

ONTOLOGY_REFERENCES: tuple[URIRef, ...] = (*ONTOLOGY_ONLY, VERSION_IRI)
"""Predicates whose objects name an ontology or one of its versions, never a term."""


def source_ontologies(graph: Graph) -> list[URIRef]:
    """The ontology IRIs a source declares: its named ``owl:Ontology`` subjects, sorted.

    Args:
        graph: The source graph.

    Returns:
        The IRIs, sorted. A blank-node header has no IRI and is left out.
    """
    return sorted(s for s in graph.subjects(RDF.type, OWL.Ontology) if isinstance(s, URIRef))


def _host(iri: str) -> str:
    """The authority part of an IRI, lower-cased: ``www.w3.org`` for W3C's vocabularies."""
    return urlsplit(iri).netloc.lower()


#: Hosts where many publishers each own a part of the space: a persistent-identifier service, or
#: W3C's, whose vocabularies are separate ontologies with separate owners. On these, sharing the
#: host says nothing about who owns a namespace (#385's panel). ``purl.obolibrary.org`` is not
#: here: OBO terms all share ``…/obo/``, so no test by namespace can tell one ontology's from
#: another's.
SHARED_HOSTS: frozenset[str] = frozenset({"purl.org", "w3id.org", "www.w3.org"})


def _owns(ontology: URIRef, namespace: str) -> bool:
    """Whether an ontology owns a namespace: on its own host, or within its own IRI.

    On an ordinary host, the whole host is the ontology's. On one of :data:`SHARED_HOSTS`, only
    the space under the ontology's own IRI is: ``http://purl.org/myont`` owns
    ``http://purl.org/myont#`` but not ``http://purl.org/dc/terms/``.
    """
    host = _host(str(ontology))
    if host != _host(namespace):
        return False
    if host in SHARED_HOSTS:
        return in_namespace(
            _lower_authority(namespace), _lower_authority(str(ontology)).rstrip("#/")
        )
    return True


def _lower_authority(iri: str) -> str:
    """The IRI with its scheme and host lower-cased, which RFC 3986 compares without case."""
    parts = urlsplit(iri)
    authority = f"{parts.scheme}://{parts.netloc}"
    if not iri.startswith(authority):
        return iri
    return authority.lower() + iri[len(authority) :]


def is_borrowed(namespace: str, ontologies: list[URIRef]) -> bool:
    """Whether a namespace belongs to someone other than the source (#383, #178).

    A namespace is borrowed when no ontology the source declares owns it (:func:`_owns`):
    ``dcterms:`` or GeoSPARQL's in a file whose ontology lives elsewhere, or ``dcterms:`` in one
    that lives elsewhere on ``purl.org``. A source that declares no ontology gives nothing to
    judge by, so nothing is borrowed.

    Args:
        namespace: The namespace IRI.
        ontologies: The source's ontology IRIs, from :func:`source_ontologies`.

    Returns:
        True if the namespace is borrowed.
    """
    return bool(ontologies) and not any(_owns(o, namespace) for o in ontologies)


def ontology_references(graph: Graph) -> set[Node]:
    """The objects in a graph that name an ontology or a version of one, not a term.

    These are the objects of :data:`ONTOLOGY_REFERENCES` wherever they occur, and of
    ``prov:wasDerivedFrom`` on an ``owl:Ontology`` subject: the derivation stamp names the
    ontologies or versions a document was derived from (#90, #171, #178).

    Args:
        graph: The graph.

    Returns:
        The objects, of any kind.
    """
    refs: set[Node] = set()
    for predicate in ONTOLOGY_REFERENCES:
        refs.update(graph.objects(None, predicate))
    for header in graph.subjects(RDF.type, ONTOLOGY):
        refs.update(graph.objects(header, WAS_DERIVED_FROM))
    return refs


@dataclass(frozen=True)
class Ownership:
    """Which terms a file may call its own.

    Attributes:
        ontologies: The file's ontology IRIs, from :func:`source_ontologies`.
        external: Namespaces the caller names as external, as IRIs.
    """

    ontologies: tuple[URIRef, ...] = ()
    external: tuple[str, ...] = ()

    def is_foreign(self, iri: Node) -> bool:
        """Whether a term belongs to someone other than this file.

        Args:
            iri: The term. A blank node or a literal is never foreign.

        Returns:
            True if the term lies within an external namespace, or is borrowed.
        """
        if not isinstance(iri, URIRef):
            return False
        text = str(iri)
        if any(in_namespace(text, namespace) for namespace in self.external):
            return True
        return is_borrowed(text, list(self.ontologies))


def ownership(graph: Graph, external: Iterable[str] = ()) -> Ownership:
    """The ownership answer for one graph.

    Args:
        graph: The file's graph.
        external: Namespaces to treat as external, already resolved to IRIs.

    Returns:
        The graph's :class:`Ownership`.
    """
    return Ownership(
        ontologies=tuple(source_ontologies(graph)),
        external=tuple(dict.fromkeys(str(n) for n in external)),
    )
