"""Statistics and metrics module for RDF ontologies.

Computes comprehensive metrics about an ontology's structure, complexity,
and documentation coverage.
"""

from rdf_construct.stats.collector import (
    OntologyStats,
    collect_stats,
)
from rdf_construct.stats.comparator import (
    ComparisonResult,
    MetricChange,
    compare_stats,
)
from rdf_construct.stats.formatters import format_stats, format_comparison

__all__ = [
    # Main collection
    "OntologyStats",
    "collect_stats",
    # Comparison
    "ComparisonResult",
    "MetricChange",
    "compare_stats",
    # Formatting
    "format_stats",
    "format_comparison",
]
