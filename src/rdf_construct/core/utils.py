"""Utilities for handling prefixes, CURIEs, and namespace operations."""

from collections.abc import Iterable, Mapping
from typing import Optional

from rdflib import Graph, Namespace, URIRef


def extract_prefix_map(graph: Graph) -> dict[str, str]:
    """Extract all namespace prefixes from a graph.

    Args:
        graph: RDF graph to extract prefixes from

    Returns:
        Dictionary mapping prefix strings to namespace URIs
    """
    return {pfx: str(uri) for pfx, uri in graph.namespace_manager.namespaces()}


def expand_curie(graph: Graph, curie_or_iri: str) -> Optional[URIRef]:
    """Expand a CURIE to a full URIRef using the graph's namespace bindings.

    Handles multiple input formats:
    - CURIE format: 'ies:Element' -> http://example.org/ies#Element
    - Angle brackets: '<http://...>' -> http://...
    - Full IRI: 'http://...' -> http://...

    Args:
        graph: RDF graph containing namespace bindings
        curie_or_iri: CURIE, bracketed IRI, or full IRI string

    Returns:
        Expanded URIRef or None if expansion fails
    """
    s = curie_or_iri.strip()
    if not s:
        return None

    # Handle angle-bracketed IRIs
    if s.startswith("<") and s.endswith(">"):
        return URIRef(s[1:-1])

    # Handle full IRIs
    if "://" in s:
        return URIRef(s)

    # Handle CURIEs
    if ":" in s:
        pfx, local = s.split(":", 1)
        for p, uri in graph.namespace_manager.namespaces():
            if p == pfx:
                return URIRef(str(uri) + local)

    return None


class CurieError(ValueError):
    """A string that names neither an IRI nor a CURIE with a bound prefix.

    Attributes:
        text: The string as given.
        prefix: The prefix that was not bound, or None for an empty string.
        bound: The prefixes that were available, sorted.
    """

    def __init__(self, text: str, prefix: str | None, bound: Iterable[str]) -> None:
        self.text = text
        self.prefix = prefix
        self.bound = tuple(sorted(bound))
        available = ", ".join(self.bound) or "none"
        if prefix is None:
            message = f"cannot resolve {text!r}: not a CURIE or an IRI"
        else:
            message = f"cannot resolve {text!r}: prefix {prefix!r} is not bound"
        super().__init__(
            f"{message}. Prefixes bound: {available}. "
            f"To give an IRI, write it in full or in angle brackets (<urn:…>)."
        )


def resolve_curie(prefixes: Mapping[str, str], text: str) -> URIRef:
    """Resolve a CURIE or an IRI to a URIRef, strictly.

    Unlike `expand_curie`, this never returns its input verbatim and never consults rdflib's
    built-in prefix table: `prefixes` is the whole of what a prefix can mean. Callers build it
    from a graph parsed with ``bind_namespaces="core"``, which holds the source file's own
    prefixes plus rdf, rdfs, owl, xsd and xml.

    The forms are tried in order:

    - ``<…>`` is the IRI inside the brackets.
    - ``pfx:local`` with ``pfx`` bound is a CURIE. A bound prefix wins even when it looks like
      a URI scheme, as in a Turtle prefixed name.
    - Anything containing ``://`` is an IRI.

    Anything else is refused. That includes a bare ``urn:isbn:…`` when ``urn`` is not bound,
    because it cannot be told apart from a CURIE whose prefix is missing; write ``<urn:isbn:…>``.

    Args:
        prefixes: Prefix to namespace IRI.
        text: A CURIE, a bracketed IRI or a full IRI.

    Returns:
        The resolved IRI.

    Raises:
        CurieError: If the string is empty, or its prefix is not in `prefixes`.
    """
    s = text.strip()
    if s.startswith("<") and s.endswith(">") and len(s) > 2:
        return URIRef(s[1:-1])
    if ":" in s:
        pfx, local = s.split(":", 1)
        if pfx in prefixes:
            return URIRef(prefixes[pfx] + local)
        if "://" in s:
            return URIRef(s)
        raise CurieError(text, pfx, prefixes)
    raise CurieError(text, None, prefixes)


_NAMESPACE_DELIMITERS = ("#", "/", ":")


def in_namespace(iri: str, namespace: str) -> bool:
    """Whether an IRI falls within a namespace, matched at a boundary.

    The delimiters are ``#``, ``/`` and ``:``, the last for URN- and ``tag:``-style
    namespaces. A namespace ending in a delimiter already names its boundary, so it matches as a
    plain prefix: ``http://example.org/`` takes the whole subtree, and ``urn:old:`` takes
    ``urn:old:A`` but not ``urn:older:C``. Otherwise the match must end where the namespace does,
    or at a following delimiter. So ``http://example.org/ont`` takes ``…/ont`` itself
    (typically the ontology IRI), ``…/ont#One`` and ``…/ont/extra#Three``, but not
    ``…/ontology#Two``. To name one namespace exactly, give it with its delimiter (``…/ont#``).

    Args:
        iri: The IRI to test.
        namespace: The namespace to test against.

    Returns:
        True if `iri` is within `namespace`.
    """
    if not namespace or not iri.startswith(namespace):
        return False
    if namespace.endswith(_NAMESPACE_DELIMITERS):
        return True
    rest = iri[len(namespace) :]
    return rest == "" or rest.startswith(_NAMESPACE_DELIMITERS)


def rebase_iri(iri: str, old_namespace: str, new_namespace: str) -> str | None:
    """Move an IRI from one namespace to another, matched at a boundary.

    Args:
        iri: The IRI to move.
        old_namespace: The namespace to move it out of, matched as `in_namespace` does.
        new_namespace: The namespace to move it into.

    Returns:
        The rebased IRI, or None if `iri` is not within `old_namespace`.
    """
    if not in_namespace(iri, old_namespace):
        return None
    return new_namespace + iri[len(old_namespace) :]


def rebind_prefixes(graph: Graph, ordered_prefixes: list[str], prefix_map: dict[str, str]) -> None:
    """Rebind prefixes in a graph according to a specified order.

    This ensures deterministic prefix ordering in serialized output.

    Args:
        graph: RDF graph to rebind prefixes in
        ordered_prefixes: List of prefix strings in desired order
        prefix_map: Dictionary mapping prefixes to namespace URIs
    """
    nm = graph.namespace_manager
    for pfx in ordered_prefixes:
        uri = prefix_map.get(pfx)
        if uri:
            nm.bind(pfx, URIRef(uri), override=True, replace=True)


def qname_sort_key(graph: Graph, term) -> str:
    """Generate a sortable string key for an RDF term using its QName.

    Args:
        graph: RDF graph containing namespace bindings
        term: RDF term to generate key for

    Returns:
        Normalized URI string suitable for alphabetical sorting
    """
    try:
        return graph.namespace_manager.normalizeUri(term)
    except Exception:
        return str(term)
