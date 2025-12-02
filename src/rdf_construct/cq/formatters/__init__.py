"""Output formatters for competency question test results.

Supports:
- text: Human-readable console output
- json: Structured JSON for programmatic use
- junit: JUnit XML for CI integration
"""

from rdf_construct.cq.formatters.text import format_text
from rdf_construct.cq.formatters.json import format_json
from rdf_construct.cq.formatters.junit import format_junit

__all__ = [
    "format_text",
    "format_json",
    "format_junit",
]


def format_results(results, format_name: str = "text",
                   verbose: bool = False) -> str:
    """Format test results using the specified formatter.

    Args:
        results: CQTestResults to format
        format_name: One of "text", "json", "junit"
        verbose: Include verbose details

    Returns:
        Formatted string

    Raises:
        ValueError: If format_name is unknown
    """
    formatters = {
        "text": lambda r, v: format_text(r, verbose=v),
        "json": lambda r, v: format_json(r, verbose=v),
        "junit": lambda r, v: format_junit(r, verbose=v),
    }

    if format_name not in formatters:
        valid = ", ".join(formatters.keys())
        raise ValueError(f"Unknown format '{format_name}'. Valid formats: {valid}")

    return formatters[format_name](results, verbose)
