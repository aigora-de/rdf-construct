"""Text formatter for console output.

Provides formatted text output for extraction results, merge results,
and coverage reports.
"""

from rdf_construct.localise.extractor import ExtractionResult
from rdf_construct.localise.merger import MergeResult
from rdf_construct.localise.reporter import CoverageReport


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
        lines.append(f"Properties: {', '.join(report.properties)}")
        lines.append("")

        # Table header
        # Calculate column widths
        lang_width = max(8, max(len(lang) for lang in report.languages.keys()))
        prop_width = max(10, max(len(p) for p in report.properties))

        # Build header row
        header_parts = ["Language".ljust(lang_width)]
        for prop in report.properties:
            header_parts.append(prop.ljust(prop_width))
        header_parts.append("Overall")
        header_parts.append("Status")

        lines.append("  ".join(header_parts))
        lines.append("-" * (len("  ".join(header_parts))))

        # Data rows
        for lang, coverage in report.languages.items():
            row_parts = []

            # Language name
            lang_display = f"{lang} (base)" if coverage.is_source else lang
            row_parts.append(lang_display.ljust(lang_width))

            # Property coverages
            for prop in report.properties:
                prop_cov = coverage.by_property.get(prop)
                if prop_cov:
                    pct = f"{prop_cov.coverage:.0f}%"
                else:
                    pct = "-"
                row_parts.append(pct.ljust(prop_width))

            # Overall coverage
            overall_pct = f"{coverage.coverage:.0f}%"
            row_parts.append(overall_pct.ljust(7))

            # Status indicator
            if coverage.coverage == 100:
                status = self._success("✓ Complete")
            elif coverage.coverage >= 75:
                status = self._warning(f"⚠ {coverage.pending} pending")
            elif coverage.coverage > 0:
                status = f"✗ {coverage.pending} pending"
            else:
                status = "✗ Not started"
            row_parts.append(status)

            lines.append("  ".join(row_parts))

        # Missing entities section
        if verbose:
            for lang, coverage in report.languages.items():
                if coverage.missing_entities and not coverage.is_source:
                    lines.append("")
                    lines.append(f"Missing {lang} translations:")
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
