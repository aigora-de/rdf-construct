"""Custom RDF serialisers that preserve semantic ordering.

RDFlib's built-in serialisers always sort subjects alphabetically,
which defeats semantic ordering. These custom serialisers respect
the exact subject order provided.
"""

from pathlib import Path

from rdflib import Graph, URIRef, Literal, RDF
from rdflib.namespace import RDFS, OWL, XSD

try:
    from .predicate_order import (
        PredicateOrderConfig,
        PredicateOrderSpec,
        classify_subject,
        order_predicates,
    )
except ImportError:
    from predicate_order import (
        PredicateOrderConfig,
        PredicateOrderSpec,
        classify_subject,
        order_predicates,
    )


def collect_used_namespaces(
    graph: Graph,
    namespace_source: Graph | None = None,
) -> set[str]:
    """Collect namespace URIs that are actually used in the graph's triples.

    Scans all subjects, predicates, and objects (including Literal datatype
    URIs) to find which registered namespace URIs are referenced. Uses
    longest-match-first ordering to correctly handle overlapping namespaces
    (e.g. ``dc:`` vs ``dcterms:``).

    Args:
        graph: RDF graph whose triples to scan.
        namespace_source: Optional graph whose namespace registry to match
            against. Defaults to *graph* itself. Use this when the graph
            being scanned has a stripped namespace manager (e.g. built
            with ``bind_namespaces="none"``).

    Returns:
        Set of namespace URI strings that appear in the graph's triples.
    """
    ns_graph = namespace_source if namespace_source is not None else graph

    used_ns: set[str] = set()
    # Sort namespaces longest-first so we match the most specific prefix
    ns_uris = sorted(
        [str(uri) for _, uri in ns_graph.namespace_manager.namespaces()],
        key=len,
        reverse=True,
    )

    def _match_uri(uri_str: str) -> None:
        """Add the best-matching namespace for *uri_str* to used_ns."""
        for ns_uri in ns_uris:
            if uri_str.startswith(ns_uri):
                used_ns.add(ns_uri)
                return

    for s, p, o in graph:
        for term in (s, p, o):
            if isinstance(term, URIRef):
                _match_uri(str(term))
            elif isinstance(term, Literal) and term.datatype is not None:
                _match_uri(str(term.datatype))

    return used_ns


def format_term(graph: Graph, term, use_prefixes: bool = True) -> str:
    """Format an RDF term as a Turtle string.

    Args:
        graph: RDF graph containing namespace bindings
        term: RDF term to format (URIRef, Literal, or other)
        use_prefixes: Whether to use prefix notation for URIs

    Returns:
        Turtle-formatted string representation of the term
    """
    if isinstance(term, URIRef):
        if use_prefixes:
            try:
                qname = graph.namespace_manager.normalizeUri(term)
                return qname
            except Exception:
                return f"<{term}>"
        return f"<{term}>"

    elif isinstance(term, Literal):
        value = str(term)
        # Escape special characters
        value = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )

        if term.datatype:
            dt = format_term(graph, term.datatype, use_prefixes=True)
            return f'"{value}"^^{dt}'
        elif term.language:
            return f'"{value}"@{term.language}'
        else:
            return f'"{value}"'

    else:
        return str(term)


def serialise_turtle(
    graph: Graph,
    subjects_ordered: list,
    output_path: Path | str,
    predicate_order: PredicateOrderConfig | None = None,
) -> None:
    """Serialise RDF graph to Turtle format with preserved subject ordering.

    This custom serialiser respects the exact order of subjects provided,
    unlike rdflib's built-in serialisers which always sort alphabetically.

    Only prefix declarations for namespaces actually used in the graph's
    triples are emitted, filtering out rdflib's built-in defaults.

    Formatting features:
    - Prefixes sorted alphabetically at top (used namespaces only)
    - Subjects in specified order
    - rdf:type predicate listed first for each subject
    - Predicates ordered according to predicate_order config (or alphabetically)
    - Objects sorted alphabetically within each predicate
    - Proper indentation and punctuation

    Args:
        graph: RDF graph to serialise
        subjects_ordered: List of subjects in desired output order
        output_path: Path to write Turtle file to
        predicate_order: Optional predicate ordering configuration
    """
    lines = []

    # Write prefixes — only those actually used in the graph
    used_ns = collect_used_namespaces(graph)
    prefixes = sorted(graph.namespace_manager.namespaces(), key=lambda x: x[0])
    for prefix, namespace in prefixes:
        if prefix and str(namespace) in used_ns:
            lines.append(f"PREFIX {prefix}: <{namespace}>")
    lines.append("")  # Blank line after prefixes

    # Write subjects in order
    for subject in subjects_ordered:
        preds = list(graph.predicate_objects(subject))
        if not preds:
            continue

        # Write subject
        subj_str = format_term(graph, subject)
        lines.append(f"{subj_str}")

        # Group predicates
        pred_dict: dict[URIRef, list] = {}
        for p, o in preds:
            if p not in pred_dict:
                pred_dict[p] = []
            pred_dict[p].append(o)

        # Order predicates
        sorted_preds = _order_subject_predicates(
            graph, subject, pred_dict, predicate_order
        )

        # Write predicate-object pairs
        for i, (pred, objects) in enumerate(sorted_preds):
            # Use 'a' shorthand for rdf:type
            pred_str = "a" if pred == RDF.type else format_term(graph, pred)
            objects_sorted = sorted(objects, key=lambda x: format_term(graph, x))

            if len(objects_sorted) == 1:
                obj_str = format_term(graph, objects_sorted[0])
                if i == len(sorted_preds) - 1:
                    lines.append(f"    {pred_str} {obj_str} .")
                else:
                    lines.append(f"    {pred_str} {obj_str} ;")
            else:
                # Multiple objects for same predicate
                lines.append(f"    {pred_str}")
                for j, obj in enumerate(objects_sorted):
                    obj_str = format_term(graph, obj)
                    if j == len(objects_sorted) - 1:
                        if i == len(sorted_preds) - 1:
                            lines.append(f"        {obj_str} .")
                        else:
                            lines.append(f"        {obj_str} ;")
                    else:
                        lines.append(f"        {obj_str} ,")

        lines.append("")  # Blank line after each subject

    # Write to file
    output_path = Path(output_path)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _order_subject_predicates(
    graph: Graph,
    subject: URIRef,
    pred_dict: dict[URIRef, list],
    predicate_order: PredicateOrderConfig | None,
) -> list[tuple[URIRef, list]]:
    """Order predicates for a subject according to configuration.

    Args:
        graph: RDF graph
        subject: The subject being serialised
        pred_dict: Dictionary of predicate -> objects
        predicate_order: Predicate ordering configuration

    Returns:
        List of (predicate, objects) tuples in desired order
    """
    sorted_preds = []

    # rdf:type always first
    if RDF.type in pred_dict:
        sorted_preds.append((RDF.type, pred_dict[RDF.type]))

    # Get remaining predicates (excluding rdf:type)
    remaining = [p for p in pred_dict.keys() if p != RDF.type]

    if predicate_order:
        # Use configured ordering
        subject_type = classify_subject(graph, subject)
        spec = predicate_order.get_spec_for_type(subject_type)

        ordered = order_predicates(
            graph,
            remaining,
            spec,
            lambda x: format_term(graph, x),
        )
    else:
        # Default: alphabetical ordering
        ordered = sorted(remaining, key=lambda x: format_term(graph, x))

    # Add ordered predicates
    for pred in ordered:
        sorted_preds.append((pred, pred_dict[pred]))

    return sorted_preds


def build_section_graph(base: Graph, subjects_ordered: list) -> Graph:
    """Build a new graph containing only the specified subjects and their triples.

    Creates a filtered view of the base graph that includes all triples
    where the subject is in the provided list. Only namespace bindings
    that are actually used by the included triples are carried over;
    rdflib's built-in well-known namespace defaults are suppressed.

    Args:
        base: Source RDF graph to filter
        subjects_ordered: List of subjects to include

    Returns:
        New graph containing only triples for the specified subjects
    """
    # Suppress rdflib's automatic well-known namespace bindings so the
    # sub-graph starts with a clean namespace manager.
    sg = Graph(bind_namespaces="none")

    # Copy triples for each subject
    for s in subjects_ordered:
        for p, o in base.predicate_objects(s):
            sg.add((s, p, o))

    # Match sub-graph triples against the *base* graph's namespace registry
    # (the sub-graph's own registry is intentionally empty at this point).
    used_ns = collect_used_namespaces(sg, namespace_source=base)
    for pfx, uri in base.namespace_manager.namespaces():
        if str(uri) in used_ns:
            sg.namespace_manager.bind(pfx, uri, override=True, replace=True)

    return sg
