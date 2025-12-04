"""Formatters for localise command output.

Provides output formatting for:
- Console text output
- Markdown reports
"""

from rdf_construct.localise.formatters.text import TextFormatter
from rdf_construct.localise.formatters.markdown import MarkdownFormatter

__all__ = [
    "TextFormatter",
    "MarkdownFormatter",
    "get_formatter",
]


def get_formatter(format_name: str, use_colour: bool = True) -> TextFormatter | MarkdownFormatter:
    """Get a formatter by name.

    Args:
        format_name: Formatter name ("text" or "markdown").
        use_colour: Whether to use colour output (text only).

    Returns:
        Formatter instance.

    Raises:
        ValueError: If format name is unknown.
    """
    if format_name == "text":
        return TextFormatter(use_colour=use_colour)
    elif format_name in ("markdown", "md"):
        return MarkdownFormatter()
    else:
        raise ValueError(f"Unknown format: {format_name}")
