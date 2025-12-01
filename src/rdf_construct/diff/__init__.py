"""Semantic diff for RDF ontologies.

This module provides tools for comparing RDF graphs and identifying
semantic differences, filtering out cosmetic changes like statement
order, prefix bindings, and whitespace.

Usage:
    from rdf_construct.diff import compare_files, format_diff

    diff = compare_files(Path("old.ttl"), Path("new.ttl"))
    print(format_diff(diff, format_name="text"))

CLI:
    rdf-construct diff old.ttl new.ttl
    rdf-construct diff old.ttl new.ttl --format markdown -o changelog.md
"""

from rdf_construct.diff.change_types import (
    ChangeType,
    EntityChange,
    EntityType,
    GraphDiff,
    PredicateCategory,
    TripleChange,
)
from rdf_construct.diff.comparator import compare_graphs, compare_files
from rdf_construct.diff.filters import filter_diff, parse_filter_string
from rdf_construct.diff.formatters import (
    format_diff,
    format_text,
    format_markdown,
    format_json,
    get_formatter,
    FORMATTERS,
)


__all__ = [
    # Change types
    "ChangeType",
    "EntityChange",
    "EntityType",
    "GraphDiff",
    "PredicateCategory",
    "TripleChange",
    # Comparison
    "compare_graphs",
    "compare_files",
    # Filtering
    "filter_diff",
    "parse_filter_string",
    # Formatting
    "format_diff",
    "format_text",
    "format_markdown",
    "format_json",
    "get_formatter",
    "FORMATTERS",
]
