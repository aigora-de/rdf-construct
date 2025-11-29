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

    Formatting features:
    - Prefixes sorted alphabetically at top
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

    # Write prefixes
    prefixes = sorted(graph.namespace_manager.namespaces(), key=lambda x: x[0])
    for prefix, namespace in prefixes:
        if prefix:  # Skip the default namespace
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
    where the subject is in the provided list. Preserves all namespace
    bindings from the base graph.

    Args:
        base: Source RDF graph to filter
        subjects_ordered: List of subjects to include

    Returns:
        New graph containing only triples for the specified subjects
    """
    sg = Graph()

    # Copy namespace bindings
    for pfx, uri in base.namespace_manager.namespaces():
        sg.namespace_manager.bind(pfx, uri, override=True, replace=True)

    # Copy triples for each subject
    for s in subjects_ordered:
        for p, o in base.predicate_objects(s):
            sg.add((s, p, o))

    return sg
