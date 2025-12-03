"""JSON output formatter for ontology statistics."""

import json
from typing import Optional

from rdflib import Graph

from rdf_construct.stats.collector import OntologyStats
from rdf_construct.stats.comparator import ComparisonResult


def format_json_stats(stats: OntologyStats, graph: Optional[Graph] = None) -> str:
    """Format ontology statistics as JSON.

    Args:
        stats: The statistics to format.
        graph: Optional graph (not used for JSON format).

    Returns:
        JSON string representation.
    """
    return json.dumps(stats.to_dict(), indent=2)


def format_json_comparison(
    comparison: ComparisonResult,
    graph: Optional[Graph] = None,
) -> str:
    """Format comparison results as JSON.

    Args:
        comparison: The comparison result to format.
        graph: Optional graph (not used for JSON format).

    Returns:
        JSON string representation.
    """
    return json.dumps(comparison.to_dict(), indent=2)
