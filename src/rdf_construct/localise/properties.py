"""How `localise` names a property: CURIEs resolved and IRIs shortened (#355).

There are two sources of prefixes, and every property name is read against exactly one of them:

- **An ontology's own prefixes**, for what is typed against it: ``--properties`` and the
  property names ``report`` prints. The graph is parsed with ``bind_namespaces="core"``, so these
  are the prefixes the file declares plus rdf, rdfs, owl, xsd and xml, never rdflib's extended
  table.
- **The file format's prefixes** (`FILE_PREFIXES`), for a translation file's ``property:`` and a
  configuration file's ``properties:``. A YAML file declares no prefixes and is merged into
  whichever ontology it is given, so its CURIEs cannot depend on that ontology. ``extract`` has
  always written these six, and they keep the meaning they were written with: ``dc:`` is Dublin
  Core elements. Any other property is written as a full IRI.

Resolution is `core.utils.resolve_curie`'s, so an unbound prefix is refused, never passed through
as a predicate that matches nothing.
"""

from collections.abc import Iterable, Mapping

from rdflib import Graph, URIRef

from rdf_construct.core.utils import resolve_curie

# The prefixes a translation or configuration file may use, in the order they are tried
FILE_PREFIXES: dict[str, str] = {
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}

# A local part holding one of these would not read back as a prefixed name
_LOCAL_DELIMITERS = ("/", "#", "?")


def source_prefixes(graph: Graph) -> dict[str, str]:
    """Return the prefixes bound in a graph, as prefix to namespace IRI.

    Args:
        graph: A graph parsed with ``bind_namespaces="core"``.

    Returns:
        Every bound prefix.
    """
    return {prefix: str(namespace) for prefix, namespace in graph.namespaces()}


def resolve_property(prefixes: Mapping[str, str], prop: str) -> URIRef:
    """Resolve a property named as a CURIE or an IRI.

    A `URIRef` is already an IRI and is returned as it is, so a property resolved once (by the
    CLI, or when a configuration file is read) is not read a second time against other prefixes.
    A bare ``urn:x`` would not survive that.

    Args:
        prefixes: Prefix to namespace IRI.
        prop: A CURIE, a bracketed IRI, a full IRI, or a `URIRef`.

    Returns:
        The property's IRI.

    Raises:
        CurieError: If `prop` is text whose prefix is not in `prefixes`, or names nothing.
    """
    if isinstance(prop, URIRef):
        return prop
    return resolve_curie(prefixes, prop)


def resolve_properties(prefixes: Mapping[str, str], props: Iterable[str]) -> list[URIRef]:
    """Resolve each property with `resolve_property`.

    Args:
        prefixes: Prefix to namespace IRI.
        props: CURIEs, IRIs or `URIRef`s.

    Returns:
        The IRIs, in the order given.

    Raises:
        CurieError: For the first property that cannot be resolved.
    """
    return [resolve_property(prefixes, prop) for prop in props]


def shorten_property(prefixes: Mapping[str, str], iri: str) -> str:
    """Write an IRI as a CURIE on one of `prefixes`, or as the IRI when none fits.

    The longest matching namespace wins, then the first prefix in alphabetical order. No prefix is
    ever invented, unlike rdflib's ``compute_qname``.

    Args:
        prefixes: Prefix to namespace IRI.
        iri: The IRI to shorten.

    Returns:
        A CURIE that `resolve_property` reads back as `iri`, or `iri` itself.
    """
    best: tuple[int, str] | None = None
    for prefix, namespace in prefixes.items():
        if not namespace or not iri.startswith(namespace):
            continue
        local = iri[len(namespace) :]
        if any(delimiter in local for delimiter in _LOCAL_DELIMITERS):
            continue
        candidate = (-len(namespace), prefix)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return str(iri)  # a URIRef would be written to YAML as a Python object
    prefix = best[1]
    return prefix + ":" + iri[len(prefixes[prefix]) :]
