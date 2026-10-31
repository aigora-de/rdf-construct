"""Utilities for handling prefixes, CURIEs, and namespace operations."""

from collections.abc import Container, Iterable, Mapping
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


def _authority_span(iri: str) -> tuple[int, int] | None:
    """Where an IRI's authority starts and ends, or None if it has none.

    A hierarchical IRI (``scheme://…``) has an authority from after the ``//`` up to the first
    ``/``, ``?`` or ``#``. The authority names one server and is not divided: a ``:`` inside it
    starts a port or ends user information, or belongs to an IPv6 literal (``http://[::1]/``),
    so no namespace boundary falls within it (#423). A non-hierarchical IRI such as ``urn:`` or
    ``tag:`` has no authority, and every ``:`` in it is a boundary.

    Args:
        iri: The IRI.

    Returns:
        The start and end offsets of the authority, or None.
    """
    colon = iri.find(":")
    if colon <= 0 or not iri.startswith("//", colon + 1):
        return None
    start = colon + 3
    ends = [j for j in (iri.find(ch, start) for ch in "/?#") if j != -1]
    return start, min(ends, default=len(iri))


def _contains_at(iri: str, k: int, authority: tuple[int, int] | None) -> bool:
    """Whether the namespace ``iri[:k]`` contains `iri`: the boundary rule, in one place.

    Args:
        iri: The IRI.
        k: The length of the namespace, a prefix of `iri`.
        authority: The IRI's authority span, from `_authority_span`.

    Returns:
        True if the namespace of length `k` contains `iri`.
    """
    if k <= 0 or k > len(iri):
        return False
    if k == len(iri):
        return True
    if authority is not None and authority[0] < k < authority[1]:
        return False
    return not iri[k - 1].isalnum() or iri[k] in "#/:"


def in_namespace(iri: str, namespace: str) -> bool:
    """Whether an IRI falls within a namespace, matched at a boundary.

    A namespace that ends in anything but a letter or a digit names its own boundary, so it
    matches as a plain prefix: ``http://example.org/`` takes the whole subtree, ``urn:old:``
    takes ``urn:old:A`` but not ``urn:older:C``, and a stem such as OBO's
    ``http://purl.obolibrary.org/obo/GO_`` or ``…/items?id=`` takes the terms that continue it
    (#422). A namespace that ends in a letter or a digit matches only where the IRI ends, or at a
    following ``#``, ``/`` or ``:``. So ``http://example.org/ont`` takes ``…/ont`` itself
    (typically the ontology IRI), ``…/ont#One`` and ``…/ont/extra#Three``, but not
    ``…/ontology#Two``. To name one namespace exactly, give it with its delimiter (``…/ont#``).

    An IRI's authority is not divided: a namespace that ends within it takes only the IRI equal
    to it. So ``http://example.org`` does not take ``http://example.org:8080/…``, which is
    another server, and neither does ``http://example.org:`` (#423).

    Args:
        iri: The IRI to test.
        namespace: The namespace to test against.

    Returns:
        True if `iri` is within `namespace`.
    """
    if not namespace or not iri.startswith(namespace):
        return False
    return _contains_at(iri, len(namespace), _authority_span(iri))


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


def claiming_namespace(iri: str, namespaces: Container[str]) -> str | None:
    """The longest of `namespaces` that contains `iri`, matched as `in_namespace` does.

    A namespace can only contain `iri` if it is `iri` itself, or ends just before or just after
    one of its characters that is not a letter or a digit, so only those prefixes are looked up.
    The cost follows the length of the IRI rather than the number of namespaces, and the answer
    is independent of the order they were declared in (#177, #424).

    Args:
        iri: The IRI to place.
        namespaces: The candidate namespaces.

    Returns:
        The longest namespace containing `iri`, or None if none does.
    """
    if iri in namespaces:
        return iri
    authority = _authority_span(iri)
    best: str | None = None
    for i, ch in enumerate(iri):
        if ch.isalnum():
            continue
        for k in (i, i + 1):
            candidate = iri[:k]
            if candidate in namespaces and _contains_at(iri, k, authority):
                best = candidate
    return best


def rebase_by_rules(iri: str, rules: Mapping[str, str]) -> str | None:
    """Move an IRI by the longest namespace rule that contains it.

    Every command that moves IRIs by namespace (`merge`'s remap, data migration and
    `refactor rename`) goes through this, so the order of the rules never matters (#424). It is
    one pass: an IRI moves at most once, and is never moved again by the rule its new IRI falls
    within.

    Args:
        iri: The IRI to move.
        rules: Old namespace to new namespace.

    Returns:
        The rebased IRI, or None if no rule's namespace contains `iri`.
    """
    old_namespace = claiming_namespace(iri, rules)
    if old_namespace is None:
        return None
    return rules[old_namespace] + iri[len(old_namespace) :]


def nested_rules(rules: Iterable[str]) -> list[tuple[str, str]]:
    """The pairs of rule namespaces where one lies within the other.

    Where rules nest, the longer one wins for the IRIs within it (`rebase_by_rules`); a command
    names each pair so that the precedence is visible (#424).

    Args:
        rules: The rules' old namespaces.

    Returns:
        ``(inner, outer)`` pairs, sorted.
    """
    namespaces = sorted(set(rules))
    return sorted(
        (inner, outer)
        for inner in namespaces
        for outer in namespaces
        if inner != outer and in_namespace(inner, outer)
    )


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
