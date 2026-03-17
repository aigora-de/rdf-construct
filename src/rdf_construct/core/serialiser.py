"""Custom RDF serialisers that preserve semantic ordering.

RDFlib's built-in serialisers always sort subjects alphabetically,
which defeats semantic ordering. These custom serialisers respect
the exact subject order provided.
"""

from pathlib import Path

from rdflib import BNode, Graph, URIRef, Literal, RDF
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


def collect_inline_bnodes(graph: Graph) -> set[BNode]:
    """Identify blank nodes eligible for inline ``[ \u2026 ]`` serialisation.

    A blank node is eligible if both conditions hold:

    1. It appears as the object of **exactly one** triple in the graph
       (a single incoming arc).
    2. It is **not** the subject of an ``rdf:type rdf:Statement`` triple
       (reification stubs must remain as top-level blocks).

    Args:
        graph: RDF graph to inspect.

    Returns:
        Set of :class:`~rdflib.BNode` instances that should be rendered
        inline rather than as top-level subjects.
    """
    # Count incoming arcs for every blank-node object.
    incoming: dict[BNode, int] = {}
    for _s, _p, o in graph:
        if isinstance(o, BNode):
            incoming[o] = incoming.get(o, 0) + 1

    # Keep only bnodes with exactly one incoming arc.
    candidates = {bn for bn, count in incoming.items() if count == 1}

    # Exclude reification stubs: any bnode that is the subject of
    # rdf:type rdf:Statement must stay as a top-level block.
    reification_subjects = {
        s
        for s, p, o in graph
        if isinstance(s, BNode) and p == RDF.type and o == RDF.Statement
    }
    candidates -= reification_subjects

    return candidates


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

    elif isinstance(term, BNode):
        # Emit the Turtle blank-node label syntax required by the grammar.
        # rdflib's str(BNode) gives the raw identifier without the prefix.
        return f"_:{term}"

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


def _format_inline_bnode(
    graph: Graph,
    bnode: BNode,
    inline_bnodes: set[BNode],
    predicate_order: PredicateOrderConfig | None,
    indent: int,
) -> str:
    """Render a blank node as a Turtle ``[ \u2026 ]`` inline block.

    Recursively renders any nested blank nodes that are themselves eligible
    for inline serialisation.  Predicate ordering within the block follows
    the same rules as for named subjects: ``rdf:type`` first, then
    according to *predicate_order* (or alphabetically if ``None``).

    Args:
        graph: RDF graph containing the blank node's triples.
        bnode: The blank node to render inline.
        inline_bnodes: Set of all blank nodes eligible for inlining,
            used to detect nested inline candidates.
        predicate_order: Optional predicate ordering configuration.
        indent: Current indentation depth (in 4-space units).  The
            opening ``[`` appears on the caller's line; each
            predicate-object line inside uses ``(indent + 1) * 4``
            spaces; the closing ``]`` uses ``indent * 4`` spaces.

    Returns:
        A multi-line string for the ``[ \u2026 ]`` block, starting with
        ``[\\n`` and ending with the indented ``]`` (no trailing
        punctuation \u2014 the caller appends ``;`` or ``.`` as needed).
    """
    inner_pad = " " * ((indent + 1) * 4)
    close_pad = " " * (indent * 4)

    # Collect predicate-object pairs for this bnode.
    pred_dict: dict[URIRef, list] = {}
    for p, o in graph.predicate_objects(bnode):
        if p not in pred_dict:
            pred_dict[p] = []
        pred_dict[p].append(o)

    sorted_preds = _order_subject_predicates(graph, bnode, pred_dict, predicate_order)

    block_lines = ["["]
    for i, (pred, objects) in enumerate(sorted_preds):
        pred_str = "a" if pred == RDF.type else format_term(graph, pred)
        objects_sorted = sorted(objects, key=lambda x: format_term(graph, x))
        is_last_pred = i == len(sorted_preds) - 1

        if len(objects_sorted) == 1:
            obj = objects_sorted[0]
            if isinstance(obj, BNode) and obj in inline_bnodes:
                obj_str = _format_inline_bnode(
                    graph, obj, inline_bnodes, predicate_order, indent + 1
                )
            else:
                obj_str = format_term(graph, obj)
            terminator = "" if is_last_pred else " ;"
            block_lines.append(f"{inner_pad}{pred_str} {obj_str}{terminator}")
        else:
            # Multiple objects for the same predicate.
            for j, obj in enumerate(objects_sorted):
                if isinstance(obj, BNode) and obj in inline_bnodes:
                    obj_str = _format_inline_bnode(
                        graph, obj, inline_bnodes, predicate_order, indent + 1
                    )
                else:
                    obj_str = format_term(graph, obj)
                is_last_obj = j == len(objects_sorted) - 1
                if not is_last_obj:
                    block_lines.append(f"{inner_pad}{pred_str} {obj_str} ,")
                else:
                    terminator = "" if is_last_pred else " ;"
                    block_lines.append(f"{inner_pad}{pred_str} {obj_str}{terminator}")

    block_lines.append(f"{close_pad}]")
    return "\n".join(block_lines)


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

    Blank nodes that are the object of exactly one triple are serialised
    using Turtle's anonymous ``[ \u2026 ]`` inline syntax, preserving authorial
    intent and improving readability.  Blank nodes referenced by more than
    one triple, or that are reification stubs, remain as top-level subjects.

    Formatting features:
    - Prefixes sorted alphabetically at top (used namespaces only)
    - Subjects in specified order
    - Single-arc blank nodes rendered inline (not as top-level stubs)
    - rdf:type predicate listed first for each subject and inline block
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

    # Pre-pass: identify blank nodes to be rendered inline.
    inline_bnodes = collect_inline_bnodes(graph)

    # Write prefixes \u2014 only those actually used in the graph
    used_ns = collect_used_namespaces(graph)
    prefixes = sorted(graph.namespace_manager.namespaces(), key=lambda x: x[0])
    for prefix, namespace in prefixes:
        if prefix and str(namespace) in used_ns:
            lines.append(f"PREFIX {prefix}: <{namespace}>")
    lines.append("")  # Blank line after prefixes

    # Write subjects in order
    for subject in subjects_ordered:
        # Skip blank nodes that will be rendered inline at their point of use.
        if isinstance(subject, BNode) and subject in inline_bnodes:
            continue

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
            is_last_pred = i == len(sorted_preds) - 1

            if len(objects_sorted) == 1:
                obj = objects_sorted[0]
                if isinstance(obj, BNode) and obj in inline_bnodes:
                    obj_str = _format_inline_bnode(
                        graph, obj, inline_bnodes, predicate_order, indent=1
                    )
                else:
                    obj_str = format_term(graph, obj)
                if is_last_pred:
                    lines.append(f"    {pred_str} {obj_str} .")
                else:
                    lines.append(f"    {pred_str} {obj_str} ;")
            else:
                # Multiple objects for same predicate
                lines.append(f"    {pred_str}")
                for j, obj in enumerate(objects_sorted):
                    if isinstance(obj, BNode) and obj in inline_bnodes:
                        obj_str = _format_inline_bnode(
                            graph, obj, inline_bnodes, predicate_order, indent=2
                        )
                    else:
                        obj_str = format_term(graph, obj)
                    is_last_obj = j == len(objects_sorted) - 1
                    if not is_last_obj:
                        lines.append(f"        {obj_str} ,")
                    else:
                        if is_last_pred:
                            lines.append(f"        {obj_str} .")
                        else:
                            lines.append(f"        {obj_str} ;")

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
