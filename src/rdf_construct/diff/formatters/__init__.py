"""Diff output formatters.

Available formatters:
- text: Plain text for terminal output
- markdown: Markdown for release notes
- json: JSON for programmatic use
"""

from rdflib import Graph

from rdf_construct.diff.change_types import GraphDiff
from rdf_construct.diff.formatters.text import format_text
from rdf_construct.diff.formatters.markdown import format_markdown
from rdf_construct.diff.formatters.json import format_json


# Format name to formatter function mapping
FORMATTERS = {
    "text": format_text,
    "markdown": format_markdown,
    "md": format_markdown,
    "json": format_json,
}


def get_formatter(format_name: str):
    """Get a formatter function by name.

    Args:
        format_name: One of 'text', 'markdown', 'md', 'json'

    Returns:
        Formatter function.

    Raises:
        KeyError: If format_name is not recognized.
    """
    name = format_name.lower()
    if name not in FORMATTERS:
        available = ", ".join(FORMATTERS.keys())
        raise KeyError(f"Unknown format '{format_name}'. Available: {available}")
    return FORMATTERS[name]


def format_diff(
    diff: GraphDiff,
    format_name: str = "text",
    graph: Graph | None = None,
) -> str:
    """Format a diff result using the specified formatter.

    Args:
        diff: The diff result to format.
        format_name: Output format ('text', 'markdown', 'json').
        graph: Optional graph for CURIE formatting.

    Returns:
        Formatted string.
    """
    formatter = get_formatter(format_name)
    return formatter(diff, graph)


__all__ = [
    "format_text",
    "format_markdown",
    "format_json",
    "format_diff",
    "get_formatter",
    "FORMATTERS",
]
