"""Text output formatter for ontology statistics."""

from typing import Optional

from rdflib import Graph

from rdf_construct.stats.collector import OntologyStats
from rdf_construct.stats.comparator import ComparisonResult


def _format_pct(value: float) -> str:
    """Format a percentage value for display."""
    return f"{value * 100:.1f}%"


def _shorten_uri(uri: str, graph: Optional[Graph] = None) -> str:
    """Shorten a URI to CURIE if possible."""
    if graph:
        try:
            qname = graph.namespace_manager.qname(uri)
            return qname
        except Exception:
            pass
    # Fallback: extract local name
    if "#" in uri:
        return uri.split("#")[-1]
    if "/" in uri:
        return uri.rsplit("/", 1)[-1]
    return uri


def format_text_stats(stats: OntologyStats, graph: Optional[Graph] = None) -> str:
    """Format ontology statistics as aligned text.

    Args:
        stats: The statistics to format.
        graph: Optional graph for CURIE formatting.

    Returns:
        Formatted text string.
    """
    lines = []

    # Header
    lines.append(f"Ontology Statistics: {stats.source}")
    lines.append("=" * 50)
    lines.append("")

    # Basic counts
    lines.append("BASIC COUNTS")
    lines.append(f"  Triples:                  {stats.basic.triples:,}")
    lines.append(f"  Classes:                  {stats.basic.classes:,}")
    lines.append(f"  Object Properties:        {stats.basic.object_properties:,}")
    lines.append(f"  Datatype Properties:      {stats.basic.datatype_properties:,}")
    lines.append(f"  Annotation Properties:    {stats.basic.annotation_properties:,}")
    lines.append(f"  Individuals:              {stats.basic.individuals:,}")
    lines.append("")

    # Hierarchy
    lines.append("HIERARCHY")
    lines.append(f"  Root Classes:             {stats.hierarchy.root_classes:,}")
    lines.append(f"  Leaf Classes:             {stats.hierarchy.leaf_classes:,}")
    lines.append(f"  Max Depth:                {stats.hierarchy.max_depth}")
    lines.append(f"  Avg Depth:                {stats.hierarchy.avg_depth:.1f}")
    lines.append(f"  Avg Branching:            {stats.hierarchy.avg_branching:.1f}")
    orphan_pct = _format_pct(stats.hierarchy.orphan_rate)
    lines.append(f"  Orphan Classes:           {stats.hierarchy.orphan_classes} ({orphan_pct})")
    lines.append("")

    # Properties
    lines.append("PROPERTIES")
    dom_pct = _format_pct(stats.properties.domain_coverage)
    range_pct = _format_pct(stats.properties.range_coverage)
    lines.append(f"  With Domain:              {stats.properties.with_domain} ({dom_pct})")
    lines.append(f"  With Range:               {stats.properties.with_range} ({range_pct})")
    lines.append(f"  Inverse Pairs:            {stats.properties.inverse_pairs}")
    lines.append(f"  Functional:               {stats.properties.functional}")
    lines.append(f"  Symmetric:                {stats.properties.symmetric}")
    lines.append("")

    # Documentation
    lines.append("DOCUMENTATION")
    cls_label_pct = _format_pct(stats.documentation.classes_labelled_pct)
    cls_doc_pct = _format_pct(stats.documentation.classes_documented_pct)
    prop_label_pct = _format_pct(stats.documentation.properties_labelled_pct)
    lines.append(f"  Classes Labelled:         {stats.documentation.classes_labelled} ({cls_label_pct})")
    lines.append(f"  Classes Documented:       {stats.documentation.classes_documented} ({cls_doc_pct})")
    lines.append(f"  Properties Labelled:      {stats.documentation.properties_labelled} ({prop_label_pct})")
    lines.append("")

    # Complexity
    lines.append("COMPLEXITY")
    lines.append(f"  Avg Props/Class:          {stats.complexity.avg_properties_per_class:.1f}")
    lines.append(f"  Avg Superclasses:         {stats.complexity.avg_superclasses_per_class:.1f}")
    lines.append(f"  Multiple Inheritance:     {stats.complexity.multiple_inheritance_count}")
    lines.append(f"  OWL Restrictions:         {stats.complexity.owl_restriction_count}")
    lines.append(f"  Equivalent Classes:       {stats.complexity.owl_equivalent_count}")
    lines.append("")

    # Connectivity
    lines.append("CONNECTIVITY")
    if stats.connectivity.most_connected_class:
        most_connected = _shorten_uri(stats.connectivity.most_connected_class, graph)
        lines.append(f"  Most Connected:           {most_connected} ({stats.connectivity.most_connected_count} refs)")
    else:
        lines.append(f"  Most Connected:           (none)")
    lines.append(f"  Isolated Classes:         {stats.connectivity.isolated_classes}")

    return "\n".join(lines)


def format_text_comparison(
        comparison: ComparisonResult,
        graph: Optional[Graph] = None,
) -> str:
    """Format comparison results as aligned text.

    Args:
        comparison: The comparison result to format.
        graph: Optional graph for CURIE formatting.

    Returns:
        Formatted text string.
    """
    lines = []

    # Header
    lines.append(f"Comparing: {comparison.old_source} → {comparison.new_source}")
    lines.append("=" * 60)
    lines.append("")

    if not comparison.changes:
        lines.append("No changes detected.")
        return "\n".join(lines)

    # Table header
    lines.append(f"{'Metric':<30} {'Old':>10} {'New':>10} {'Change':>15}")
    lines.append("-" * 65)

    # Group changes by category
    current_category = None
    for change in comparison.changes:
        if change.category != current_category:
            current_category = change.category
            lines.append(f"\n{current_category.upper()}")

        # Format the change
        old_str = _format_value(change.old_value)
        new_str = _format_value(change.new_value)

        # Format delta with sign
        if change.delta is not None:
            if change.pct_change is not None:
                delta_str = f"{change.delta:+g} ({change.pct_change:+.1f}%)"
            else:
                delta_str = f"{change.delta:+g}"
        else:
            delta_str = "-"

        # Add indicator
        if change.improved is True:
            delta_str += " ✓"
        elif change.improved is False:
            delta_str += " ⚠"

        metric_name = change.metric.replace("_", " ").title()
        lines.append(f"  {metric_name:<28} {old_str:>10} {new_str:>10} {delta_str:>15}")

    lines.append("")
    lines.append(f"Summary: {comparison.summary}")

    return "\n".join(lines)


def _format_value(value: float | int | str | None) -> str:
    """Format a metric value for display."""
    if value is None:
        return "-"
    if isinstance(value, float):
        if value < 1:
            # Probably a percentage/rate
            return f"{value * 100:.1f}%"
        return f"{value:.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)
