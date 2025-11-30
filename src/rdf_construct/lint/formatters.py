"""Output formatters for lint results.

Provides text and JSON formatting for lint results, suitable for
terminal output and CI integration respectively.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from rdflib import Graph, URIRef

from rdf_construct.lint.engine import LintResult, LintSummary
from rdf_construct.lint.rules import LintIssue, Severity


def format_entity_name(entity: URIRef, graph: Graph | None = None) -> str:
    """Format an entity URI for display.

    Tries to use a prefixed form (e.g., ies:Building) if possible,
    otherwise falls back to the local name.

    Args:
        entity: The entity URI.
        graph: Optional graph to get namespace bindings from.

    Returns:
        Formatted entity name string.
    """
    uri_str = str(entity)

    # Try to get QName from graph's namespace bindings
    if graph is not None:
        try:
            qname = graph.qname(entity)
            if qname and ":" in qname:
                return qname
        except Exception:
            pass

    # Fall back to extracting local name
    if "#" in uri_str:
        return uri_str.split("#")[-1]
    elif "/" in uri_str:
        return uri_str.rsplit("/", 1)[-1]

    return uri_str


class Formatter(ABC):
    """Base class for output formatters."""

    @abstractmethod
    def format_result(self, result: LintResult) -> str:
        """Format a single file's lint result.

        Args:
            result: The lint result to format.

        Returns:
            Formatted string output.
        """
        pass

    @abstractmethod
    def format_summary(self, summary: LintSummary) -> str:
        """Format a summary of multiple file results.

        Args:
            summary: The lint summary to format.

        Returns:
            Formatted string output.
        """
        pass


class TextFormatter(Formatter):
    """Plain text formatter for terminal output.

    Produces output like:
        file.ttl:12: error[orphan-class]: ies:Building - Class has no superclass
        file.ttl:18: warning[missing-label]: ies:hasFloor - Property lacks rdfs:label

        Found 1 error, 1 warning, 0 info messages
    """

    # ANSI colour codes
    COLOURS = {
        Severity.ERROR: "\033[91m",  # Red
        Severity.WARNING: "\033[93m",  # Yellow
        Severity.INFO: "\033[94m",  # Blue
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
    }

    def __init__(self, use_colour: bool = True, verbose: bool = False):
        """Initialise the text formatter.

        Args:
            use_colour: Whether to use ANSI colour codes.
            verbose: Whether to include additional details.
        """
        self.use_colour = use_colour
        self.verbose = verbose

    def _colour(self, text: str, *codes: str) -> str:
        """Apply colour codes to text if enabled."""
        if not self.use_colour:
            return text
        prefix = "".join(codes)
        return f"{prefix}{text}{self.COLOURS['reset']}"

    def _severity_colour(self, severity: Severity) -> str:
        """Get colour code for a severity level."""
        return self.COLOURS.get(severity, "")

    def format_issue(self, issue: LintIssue, file_path: Path, graph: Graph | None = None) -> str:
        """Format a single issue.

        Args:
            issue: The issue to format.
            file_path: Path to the file containing the issue.
            graph: Optional graph for namespace resolution.

        Returns:
            Formatted issue line.
        """
        parts = []

        # File location with line number
        location = str(file_path)
        if issue.line:
            location = f"{location}:{issue.line}"
        parts.append(self._colour(location, self.COLOURS["dim"]))

        # Severity and rule
        severity_str = issue.severity.value
        rule_part = f"{severity_str}[{issue.rule_id}]"
        parts.append(
            self._colour(rule_part, self.COLOURS["bold"], self._severity_colour(issue.severity))
        )

        # Entity (if present) - use formatted name with namespace
        if issue.entity:
            entity_name = format_entity_name(issue.entity, graph)
            parts.append(f"{entity_name}:")

        # Message
        parts.append(issue.message)

        return " ".join(parts)

    def format_result(self, result: LintResult) -> str:
        """Format a single file's lint result."""
        if not result.issues:
            return ""

        lines = []
        # Sort by line number (issues without lines go last)
        sorted_issues = sorted(
            result.issues,
            key=lambda i: (i.line or float('inf'), i.severity)
        )
        for issue in sorted_issues:
            lines.append(self.format_issue(issue, result.file_path, result.graph))

        return "\n".join(lines)

    def format_summary(self, summary: LintSummary) -> str:
        """Format a summary of multiple file results."""
        lines = []

        # Individual file results
        for result in summary.results:
            result_text = self.format_result(result)
            if result_text:
                lines.append(result_text)
                lines.append("")  # Blank line between files

        # Summary line
        summary_parts = []

        if summary.total_errors > 0:
            err_text = f"{summary.total_errors} error{'s' if summary.total_errors != 1 else ''}"
            summary_parts.append(self._colour(err_text, self._severity_colour(Severity.ERROR)))
        else:
            summary_parts.append("0 errors")

        if summary.total_warnings > 0:
            warn_text = f"{summary.total_warnings} warning{'s' if summary.total_warnings != 1 else ''}"
            summary_parts.append(self._colour(warn_text, self._severity_colour(Severity.WARNING)))
        else:
            summary_parts.append("0 warnings")

        if summary.total_info > 0:
            info_text = f"{summary.total_info} info"
            summary_parts.append(self._colour(info_text, self._severity_colour(Severity.INFO)))
        else:
            summary_parts.append("0 info")

        files_str = f"{len(summary.results)} file{'s' if len(summary.results) != 1 else ''}"

        summary_line = f"Found {', '.join(summary_parts)} in {files_str}"
        lines.append(summary_line)

        return "\n".join(lines)


class JsonFormatter(Formatter):
    """JSON formatter for machine-readable output.

    Produces output like:
    {
        "files": [
            {
                "path": "file.ttl",
                "issues": [
                    {
                        "rule": "orphan-class",
                        "severity": "error",
                        "entity": "http://example.org/Building",
                        "entity_name": "ies:Building",
                        "message": "Class has no superclass",
                        "line": 12
                    }
                ],
                "summary": {"errors": 1, "warnings": 0, "info": 0}
            }
        ],
        "summary": {"errors": 1, "warnings": 0, "info": 0, "files": 1}
    }
    """

    def __init__(self, pretty: bool = True):
        """Initialise the JSON formatter.

        Args:
            pretty: Whether to pretty-print the JSON.
        """
        self.pretty = pretty

    def _issue_to_dict(self, issue: LintIssue, graph: Graph | None = None) -> dict:
        """Convert an issue to a dictionary."""
        result = {
            "rule": issue.rule_id,
            "severity": issue.severity.value,
            "entity": str(issue.entity) if issue.entity else None,
            "message": issue.message,
            "line": issue.line,
        }

        # Add formatted entity name if available
        if issue.entity:
            result["entity_name"] = format_entity_name(issue.entity, graph)

        return result

    def format_result(self, result: LintResult) -> str:
        """Format a single file's lint result as JSON."""
        data = {
            "path": str(result.file_path),
            "issues": [self._issue_to_dict(i, result.graph) for i in result.issues],
            "summary": {
                "errors": result.error_count,
                "warnings": result.warning_count,
                "info": result.info_count,
            },
        }

        if self.pretty:
            return json.dumps(data, indent=2)
        return json.dumps(data)

    def format_summary(self, summary: LintSummary) -> str:
        """Format a summary of multiple file results as JSON."""
        data = {
            "files": [
                {
                    "path": str(r.file_path),
                    "issues": [self._issue_to_dict(i, r.graph) for i in r.issues],
                    "summary": {
                        "errors": r.error_count,
                        "warnings": r.warning_count,
                        "info": r.info_count,
                    },
                }
                for r in summary.results
            ],
            "summary": {
                "errors": summary.total_errors,
                "warnings": summary.total_warnings,
                "info": summary.total_info,
                "files": len(summary.results),
            },
        }

        if self.pretty:
            return json.dumps(data, indent=2)
        return json.dumps(data)


def get_formatter(format_name: str, **kwargs) -> Formatter:
    """Get a formatter by name.

    Args:
        format_name: 'text' or 'json'.
        **kwargs: Additional arguments passed to the formatter.

    Returns:
        Formatter instance.

    Raises:
        ValueError: If format name is unknown.
    """
    formatters = {
        "text": TextFormatter,
        "json": JsonFormatter,
    }

    if format_name not in formatters:
        raise ValueError(f"Unknown format '{format_name}'. Available: {', '.join(formatters.keys())}")

    return formatters[format_name](**kwargs)
