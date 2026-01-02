"""Output formatters for ontology description."""

from typing import Optional

from rdf_construct.describe.models import OntologyDescription
from rdf_construct.describe.formatters.text import format_text
from rdf_construct.describe.formatters.markdown import format_markdown
from rdf_construct.describe.formatters.json import format_json


def format_description(
    description: OntologyDescription,
    format_name: str = "text",
    use_colour: bool = True,
) -> str:
    """Format ontology description for output.

    Args:
        description: The description to format.
        format_name: Output format ("text", "json", "markdown", "md").
        use_colour: Whether to use ANSI colour codes (text format only).

    Returns:
        Formatted string representation.

    Raises:
        ValueError: If format_name is not recognised.
    """
    format_name = format_name.lower()

    if format_name == "text":
        return format_text(description, use_colour=use_colour)
    elif format_name == "json":
        return format_json(description)
    elif format_name in ("markdown", "md"):
        return format_markdown(description)
    else:
        valid = "text, json, markdown, md"
        raise ValueError(f"Unknown format '{format_name}'. Valid formats: {valid}")


__all__ = [
    "format_description",
    "format_text",
    "format_markdown",
    "format_json",
]
