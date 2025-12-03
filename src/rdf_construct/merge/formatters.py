"""Output formatters for merge operations.

Provides text and Markdown formatters for:
- Merge progress and results
- Conflict reports
- Data migration summaries
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TextIO

from rdflib import Graph

from rdf_construct.merge.conflicts import Conflict, ConflictType
from rdf_construct.merge.merger import MergeResult
from rdf_construct.merge.migrator import MigrationResult


class BaseFormatter(ABC):
    """Abstract base class for merge output formatters."""

    @abstractmethod
    def format_merge_result(self, result: MergeResult, graph: Graph | None = None) -> str:
        """Format a merge result for output.

        Args:
            result: MergeResult to format
            graph: Optional graph for namespace resolution

        Returns:
            Formatted string
        """
        pass

    @abstractmethod
    def format_conflict_report(
        self, conflicts: list[Conflict], graph: Graph | None = None
    ) -> str:
        """Format a conflict report.

        Args:
            conflicts: List of conflicts to report
            graph: Optional graph for namespace resolution

        Returns:
            Formatted conflict report
        """
        pass

    @abstractmethod
    def format_migration_result(self, result: MigrationResult) -> str:
        """Format a migration result.

        Args:
            result: MigrationResult to format

        Returns:
            Formatted string
        """
        pass


class TextFormatter(BaseFormatter):
    """Plain text formatter for console output."""

    def __init__(self, use_colour: bool = True):
        """Initialize the formatter.

        Args:
            use_colour: Whether to use ANSI colour codes
        """
        self.use_colour = use_colour

    def _colour(self, text: str, colour: str) -> str:
        """Apply ANSI colour to text.

        Args:
            text: Text to colour
            colour: Colour name (green, yellow, red, cyan)

        Returns:
            Coloured text or plain text if colours disabled
        """
        if not self.use_colour:
            return text

        colours = {
            "green": "\033[92m",
            "yellow": "\033[93m",
            "red": "\033[91m",
            "cyan": "\033[96m",
            "bold": "\033[1m",
            "reset": "\033[0m",
        }
        return f"{colours.get(colour, '')}{text}{colours['reset']}"

    def format_merge_result(self, result: MergeResult, graph: Graph | None = None) -> str:
        """Format merge result as plain text."""
        lines = []

        if not result.success:
            lines.append(self._colour(f"✗ Merge failed: {result.error}", "red"))
            return "\n".join(lines)

        lines.append(self._colour("Merge Results", "bold"))
        lines.append("")

        # Source statistics
        lines.append("Sources:")
        for source, count in result.source_stats.items():
            lines.append(f"  {self._colour('✓', 'green')} {source}: {count} triples")

        lines.append("")
        lines.append(f"Total merged: {result.total_triples} triples")

        # Conflict summary
        if result.conflicts:
            lines.append("")
            lines.append(self._colour("Conflicts:", "yellow"))
            lines.append(f"  Detected: {len(result.conflicts)}")
            lines.append(
                f"  Auto-resolved: {len(result.resolved_conflicts)}"
            )
            if result.unresolved_conflicts:
                lines.append(
                    f"  {self._colour(f'Unresolved: {len(result.unresolved_conflicts)}', 'red')}"
                )
                lines.append(
                    "  → Search for '=== CONFLICT ===' in output"
                )
        else:
            lines.append("")
            lines.append(self._colour("✓ No conflicts detected", "green"))

        return "\n".join(lines)

    def format_conflict_report(
        self, conflicts: list[Conflict], graph: Graph | None = None
    ) -> str:
        """Format conflicts as plain text."""
        lines = []

        resolved = [c for c in conflicts if c.is_resolved]
        unresolved = [c for c in conflicts if not c.is_resolved]

        lines.append(self._colour("Conflict Report", "bold"))
        lines.append(f"Total: {len(conflicts)}")
        lines.append(f"Resolved: {len(resolved)}")
        lines.append(f"Unresolved: {len(unresolved)}")
        lines.append("")

        if unresolved:
            lines.append(self._colour("Unresolved Conflicts:", "red"))
            for i, conflict in enumerate(unresolved, 1):
                subj = self._format_term(conflict.subject, graph)
                pred = self._format_term(conflict.predicate, graph)
                lines.append(f"  {i}. {subj} {pred}")
                for cv in conflict.values:
                    lines.append(f"      - {cv} (from {cv.source_path})")
            lines.append("")

        if resolved:
            lines.append(self._colour("Auto-Resolved:", "green"))
            for conflict in resolved:
                subj = self._format_term(conflict.subject, graph)
                pred = self._format_term(conflict.predicate, graph)
                lines.append(f"  {subj} {pred}")
                if conflict.resolution:
                    lines.append(
                        f"    → Used: {conflict.resolution}"
                    )

        return "\n".join(lines)

    def format_migration_result(self, result: MigrationResult) -> str:
        """Format migration result as plain text."""
        lines = []

        if not result.success:
            lines.append(self._colour(f"✗ Migration failed: {result.error}", "red"))
            return "\n".join(lines)

        lines.append(self._colour("Migration Results", "bold"))
        lines.append("")
        lines.append(f"Source triples: {result.source_triples}")
        lines.append(f"Result triples: {result.result_triples}")
        lines.append("")

        lines.append("Changes:")
        lines.append(f"  Subjects updated: {result.stats.subjects_updated}")
        lines.append(f"  Objects updated: {result.stats.objects_updated}")
        lines.append(f"  Triples added: {result.stats.triples_added}")
        lines.append(f"  Triples removed: {result.stats.triples_removed}")

        if result.stats.rules_applied:
            lines.append("")
            lines.append("Rules applied:")
            for rule, count in result.stats.rules_applied.items():
                lines.append(f"  {rule}: {count} instances")

        return "\n".join(lines)

    def _format_term(self, term, graph: Graph | None) -> str:
        """Format an RDF term for display."""
        if graph:
            try:
                return graph.namespace_manager.normalizeUri(term)
            except Exception:
                pass
        return str(term)


class MarkdownFormatter(BaseFormatter):
    """Markdown formatter for conflict reports."""

    def format_merge_result(self, result: MergeResult, graph: Graph | None = None) -> str:
        """Format merge result as Markdown."""
        lines = []

        lines.append("# Merge Report")
        lines.append("")
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")

        if not result.success:
            lines.append(f"**Error**: {result.error}")
            return "\n".join(lines)

        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Source files | {len(result.source_stats)} |")
        lines.append(f"| Total triples | {result.total_triples} |")
        lines.append(f"| Conflicts detected | {len(result.conflicts)} |")
        lines.append(f"| Auto-resolved | {len(result.resolved_conflicts)} |")
        lines.append(f"| **Unresolved** | **{len(result.unresolved_conflicts)}** |")
        lines.append("")

        if result.source_stats:
            lines.append("## Sources")
            lines.append("")
            lines.append("| File | Triples |")
            lines.append("|------|---------|")
            for source, count in result.source_stats.items():
                lines.append(f"| {source} | {count} |")
            lines.append("")

        return "\n".join(lines)

    def format_conflict_report(
        self, conflicts: list[Conflict], graph: Graph | None = None
    ) -> str:
        """Format conflicts as Markdown."""
        lines = []

        resolved = [c for c in conflicts if c.is_resolved]
        unresolved = [c for c in conflicts if not c.is_resolved]

        lines.append("# Merge Conflict Report")
        lines.append("")
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Count |")
        lines.append("|--------|-------|")
        lines.append(f"| Total conflicts | {len(conflicts)} |")
        lines.append(f"| Auto-resolved | {len(resolved)} |")
        lines.append(f"| **Unresolved** | **{len(unresolved)}** |")
        lines.append("")

        if unresolved:
            lines.append("## Unresolved Conflicts")
            lines.append("")
            lines.append(
                "These require manual review. "
                "Search for `# === CONFLICT ===` in the output file."
            )
            lines.append("")

            for i, conflict in enumerate(unresolved, 1):
                subj = self._format_term(conflict.subject, graph)
                pred = self._format_term(conflict.predicate, graph)

                lines.append(f"### {i}. {subj} {pred}")
                lines.append("")
                lines.append("| Source | Priority | Value |")
                lines.append("|--------|----------|-------|")
                for cv in conflict.values:
                    lines.append(f"| {cv.source_path} | {cv.priority} | {cv} |")
                lines.append("")
                lines.append(
                    f"**Reason**: {self._conflict_reason(conflict)}"
                )
                lines.append("")

        if resolved:
            lines.append("## Auto-Resolved Conflicts")
            lines.append("")
            lines.append(
                "These were resolved automatically based on priority."
            )
            lines.append("")

            for conflict in resolved:
                subj = self._format_term(conflict.subject, graph)
                pred = self._format_term(conflict.predicate, graph)

                lines.append(f"### {subj} {pred}")
                lines.append("")
                if conflict.resolution:
                    lines.append(
                        f"- **Kept** ({conflict.resolution.source_path}, "
                        f"priority {conflict.resolution.priority}): {conflict.resolution}"
                    )
                    for cv in conflict.values:
                        if cv != conflict.resolution:
                            lines.append(
                                f"- *Discarded* ({cv.source_path}, "
                                f"priority {cv.priority}): {cv}"
                            )
                lines.append("")

        lines.append("## Recommendations")
        lines.append("")
        lines.append("1. Review unresolved conflicts in output file")
        lines.append(
            "2. Consider whether similar values should be merged or aliased"
        )
        lines.append(
            "3. Run `rdf-construct lint` on merged output to check for issues"
        )
        lines.append("")

        return "\n".join(lines)

    def format_migration_result(self, result: MigrationResult) -> str:
        """Format migration result as Markdown."""
        lines = []

        lines.append("# Data Migration Report")
        lines.append("")
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")

        if not result.success:
            lines.append(f"**Error**: {result.error}")
            return "\n".join(lines)

        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Source triples | {result.source_triples} |")
        lines.append(f"| Result triples | {result.result_triples} |")
        lines.append(f"| Subjects updated | {result.stats.subjects_updated} |")
        lines.append(f"| Objects updated | {result.stats.objects_updated} |")
        lines.append(f"| Triples added | {result.stats.triples_added} |")
        lines.append(f"| Triples removed | {result.stats.triples_removed} |")
        lines.append("")

        if result.stats.rules_applied:
            lines.append("## Rules Applied")
            lines.append("")
            lines.append("| Rule | Instances |")
            lines.append("|------|-----------|")
            for rule, count in result.stats.rules_applied.items():
                lines.append(f"| {rule} | {count} |")
            lines.append("")

        return "\n".join(lines)

    def _format_term(self, term, graph: Graph | None) -> str:
        """Format an RDF term for display."""
        if graph:
            try:
                return f"`{graph.namespace_manager.normalizeUri(term)}`"
            except Exception:
                pass
        return f"`{term}`"

    def _conflict_reason(self, conflict: Conflict) -> str:
        """Get a human-readable reason for the conflict."""
        type_reasons = {
            ConflictType.VALUE_DIFFERENCE: "Different values for the same predicate",
            ConflictType.TYPE_DIFFERENCE: "Different type declarations",
            ConflictType.HIERARCHY_DIFFERENCE: "Different hierarchy positions",
            ConflictType.SEMANTIC_CONTRADICTION: "Semantically incompatible assertions",
        }
        return type_reasons.get(
            conflict.conflict_type, "Values differ between sources"
        )


# Formatter registry
FORMATTERS = {
    "text": TextFormatter,
    "markdown": MarkdownFormatter,
    "md": MarkdownFormatter,
}


def get_formatter(format_name: str, **kwargs) -> BaseFormatter:
    """Get a formatter by name.

    Args:
        format_name: Format name (text, markdown, md)
        **kwargs: Additional arguments for formatter

    Returns:
        Formatter instance

    Raises:
        ValueError: If format name is unknown
    """
    formatter_class = FORMATTERS.get(format_name.lower())
    if not formatter_class:
        raise ValueError(
            f"Unknown format: {format_name}. "
            f"Available: {', '.join(FORMATTERS.keys())}"
        )
    return formatter_class(**kwargs)
