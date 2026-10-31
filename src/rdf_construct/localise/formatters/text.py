"""Text formatter for console output.

Provides formatted text output for extraction results, merge results,
and coverage reports.
"""

from rdf_construct.localise.extractor import ExtractionResult
from rdf_construct.localise.merger import MergeResult
from rdf_construct.localise.reporter import CoverageReport, format_fraction, percent


class TextFormatter:
    """Formats localise results for console output."""

    def __init__(self, use_colour: bool = True):
        """Initialise formatter.

        Args:
            use_colour: Whether to use ANSI colour codes.
        """
        self.use_colour = use_colour

    def format_extraction_result(self, result: ExtractionResult) -> str:
        """Format extraction result for display.

        Args:
            result: Extraction result.

        Returns:
            Formatted string.
        """
        lines: list[str] = []

        if result.success:
            lines.append(self._success("✓ Extraction complete"))
            lines.append("")
            lines.append(f"  Entities:        {result.total_entities}")
            lines.append(f"  Strings:         {result.total_strings}")
            if result.skipped_entities > 0:
                lines.append(f"  Skipped:         {result.skipped_entities}")

            if result.translation_file:
                tf = result.translation_file
                lines.append("")
                lines.append(f"  Source language: {tf.metadata.source_language}")
                lines.append(f"  Target language: {tf.metadata.target_language}")
        else:
            lines.append(self._error(f"✗ Extraction failed: {result.error}"))

        return "\n".join(lines)

    def format_merge_result(self, result: MergeResult) -> str:
        """Format merge result for display.

        Args:
            result: Merge result.

        Returns:
            Formatted string.
        """
        lines: list[str] = []

        if result.success:
            lines.append(self._success("✓ Merge complete"))
            lines.append("")

            stats = result.stats
            lines.append(f"  Added:           {stats.added}")
            lines.append(f"  Updated:         {stats.updated}")

            if stats.skipped_status > 0:
                lines.append(f"  Skipped (status): {stats.skipped_status}")
            if stats.skipped_existing > 0:
                lines.append(f"  Skipped (exists): {stats.skipped_existing}")
            if stats.errors > 0:
                lines.append(self._warning(f"  Errors:          {stats.errors}"))

            if result.warnings:
                lines.append("")
                lines.append(self._warning("Warnings:"))
                for warning in result.warnings[:10]:  # Limit to 10
                    lines.append(f"  - {warning}")
                if len(result.warnings) > 10:
                    lines.append(f"  ... and {len(result.warnings) - 10} more")
        else:
            lines.append(self._error(f"✗ Merge failed: {result.error}"))

        return "\n".join(lines)

    def format_coverage_report(
        self,
        report: CoverageReport,
        verbose: bool = False,
    ) -> str:
        """Format coverage report for display.

        Args:
            report: Coverage report.
            verbose: Include detailed missing entity list.

        Returns:
            Formatted string.
        """
        lines: list[str] = []

        # Header
        lines.append("Translation Coverage Report")
        lines.append("=" * 40)
        lines.append("")
        lines.append(f"Source: {report.source_file}")
        lines.append(f"Entities: {report.total_entities}")
        if report.deprecated_entities:
            lines.append(
                f"Deprecated: {report.deprecated_entities} (not counted; "
                "--include-deprecated counts them)"
            )
        lines.append(f"Properties: {', '.join(report.properties)}")
        lines.append("")

        # Build every cell first, so each column is as wide as its widest cell
        header = ["Language", *report.properties, "Overall", "Status"]
        rows: list[list[str]] = []
        statuses: list[str] = []
        for lang, coverage in report.languages.items():
            row = [f"{lang} (base)" if coverage.is_source else lang]

            # Property coverages: entities in this language, of those carrying the property
            for prop in report.properties:
                prop_cov = coverage.by_property.get(prop)
                row.append(
                    format_fraction(prop_cov.translated, prop_cov.total) if prop_cov else "-"
                )

            # Overall coverage, over every entity and property pair
            row.append(format_fraction(coverage.translated, coverage.total_pairs))
            rows.append(row)

            # Status indicator
            if coverage.total_pairs == 0:
                statuses.append("— Nothing to measure")
            elif coverage.translated == coverage.total_pairs:
                statuses.append(self._success("✓ Complete"))
            elif percent(coverage.translated, coverage.total_pairs) >= 75:
                statuses.append(self._warning(f"⚠ {coverage.pending} pending"))
            elif coverage.translated > 0:
                statuses.append(f"✗ {coverage.pending} pending")
            else:
                statuses.append("✗ Not started")

        widths = [max(len(cells[i]) for cells in [header, *rows]) for i in range(len(header) - 1)]
        lines.append(
            "  ".join([*(h.ljust(w) for h, w in zip(header, widths, strict=False)), header[-1]])
        )
        lines.append("-" * (sum(widths) + 2 * len(widths) + len(header[-1])))
        for row, status in zip(rows, statuses, strict=True):
            lines.append(
                "  ".join([*(c.ljust(w) for c, w in zip(row, widths, strict=False)), status])
            )

        # A language that matched nothing while a related tag did (#159)
        if report.warnings:
            lines.append("")
            for warning in report.warnings:
                lines.append(self._warning(f"⚠ {warning}"))

        # A second literal in one language, for a property that takes one per language (#158)
        for lang, coverage in report.languages.items():
            if coverage.duplicates:
                lines.append("")
                lines.append(
                    self._warning(
                        f"⚠ {len(coverage.duplicates)} entit"
                        f"{'y has' if len(coverage.duplicates) == 1 else 'ies have'} "
                        f"more than one {lang} value for a property that takes one per language:"
                    )
                )
                for uri, prop in coverage.duplicates[:20]:
                    lines.append(f"  - {self._shorten_uri(uri)} {prop}")
                if len(coverage.duplicates) > 20:
                    lines.append(f"  ... and {len(coverage.duplicates) - 20} more")

        # Missing entities section
        if verbose:
            for lang, coverage in report.languages.items():
                if coverage.missing_entities:
                    lines.append("")
                    # The base row can be incomplete too: terms labelled only in other languages
                    what = "source labels" if coverage.is_source else "translations"
                    lines.append(f"Missing {lang} {what}:")
                    for uri in coverage.missing_entities[:20]:
                        # Shorten URI for display
                        short_uri = self._shorten_uri(uri)
                        lines.append(f"  - {short_uri}")
                    if len(coverage.missing_entities) > 20:
                        lines.append(f"  ... and {len(coverage.missing_entities) - 20} more")

        return "\n".join(lines)

    def _success(self, text: str) -> str:
        """Format as success (green)."""
        if self.use_colour:
            return f"\033[32m{text}\033[0m"
        return text

    def _warning(self, text: str) -> str:
        """Format as warning (yellow)."""
        if self.use_colour:
            return f"\033[33m{text}\033[0m"
        return text

    def _error(self, text: str) -> str:
        """Format as error (red)."""
        if self.use_colour:
            return f"\033[31m{text}\033[0m"
        return text

    def _shorten_uri(self, uri: str) -> str:
        """Shorten a URI for display.

        Args:
            uri: Full URI.

        Returns:
            Shortened version.
        """
        # Common namespace prefixes
        prefixes = {
            "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
            "http://www.w3.org/2004/02/skos/core#": "skos:",
            "http://www.w3.org/2002/07/owl#": "owl:",
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
        }

        for namespace, prefix in prefixes.items():
            if uri.startswith(namespace):
                return prefix + uri[len(namespace) :]

        # If no known prefix, just show local name
        if "#" in uri:
            return uri.split("#")[-1]
        elif "/" in uri:
            return uri.split("/")[-1]

        return uri
