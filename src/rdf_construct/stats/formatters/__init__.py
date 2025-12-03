"""Output formatters for ontology statistics."""

from typing import Optional

from rdflib import Graph

from rdf_construct.stats.collector import OntologyStats
from rdf_construct.stats.comparator import ComparisonResult
from rdf_construct.stats.formatters.text import format_text_stats, format_text_comparison
from rdf_construct.stats.formatters.json import format_json_stats, format_json_comparison
from rdf_construct.stats.formatters.markdown import format_markdown_stats, format_markdown_comparison


def format_stats(
    stats: OntologyStats,
    format_name: str = "text",
    graph: Optional[Graph] = None,
) -> str:
    """Format ontology statistics for output.

    Args:
        stats: The statistics to format.
        format_name: Output format ("text", "json", "markdown", "md").
        graph: Optional graph for CURIE formatting.

    Returns:
        Formatted string representation.

    Raises:
        ValueError: If format_name is not recognised.
    """
    formatters = {
        "text": format_text_stats,
        "json": format_json_stats,
        "markdown": format_markdown_stats,
        "md": format_markdown_stats,
    }

    formatter = formatters.get(format_name.lower())
    if not formatter:
        valid = ", ".join(sorted(formatters.keys()))
        raise ValueError(f"Unknown format '{format_name}'. Valid formats: {valid}")

    return formatter(stats, graph)


def format_comparison(
    comparison: ComparisonResult,
    format_name: str = "text",
    graph: Optional[Graph] = None,
) -> str:
    """Format comparison results for output.

    Args:
        comparison: The comparison result to format.
        format_name: Output format ("text", "json", "markdown", "md").
        graph: Optional graph for CURIE formatting.

    Returns:
        Formatted string representation.

    Raises:
        ValueError: If format_name is not recognised.
    """
    formatters = {
        "text": format_text_comparison,
        "json": format_json_comparison,
        "markdown": format_markdown_comparison,
        "md": format_markdown_comparison,
    }

    formatter = formatters.get(format_name.lower())
    if not formatter:
        valid = ", ".join(sorted(formatters.keys()))
        raise ValueError(f"Unknown format '{format_name}'. Valid formats: {valid}")

    return formatter(comparison, graph)


__all__ = [
    "format_stats",
    "format_comparison",
]
