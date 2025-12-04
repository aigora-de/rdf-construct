"""Markdown formatter for coverage reports.

Generates markdown-formatted coverage reports suitable for documentation
or inclusion in PRs/issues.
"""

from datetime import datetime

from rdf_construct.localise.extractor import ExtractionResult
from rdf_construct.localise.merger import MergeResult
from rdf_construct.localise.reporter import CoverageReport


class MarkdownFormatter:
    """Formats localise results as Markdown."""

    def format_extraction_result(self, result: ExtractionResult) -> str:
        """Format extraction result as Markdown.

        Args:
            result: Extraction result.

        Returns:
            Markdown string.
        """
        lines: list[str] = []

        lines.append("# Extraction Result")
        lines.append("")

        if result.success:
            lines.append("**Status:** ✅ Success")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Entities | {result.total_entities} |")
            lines.append(f"| Strings | {result.total_strings} |")
            lines.append(f"| Skipped | {result.skipped_entities} |")

            if result.translation_file:
                tf = result.translation_file
                lines.append("")
                lines.append("## Metadata")
                lines.append("")
                lines.append(f"- **Source file:** `{tf.metadata.source_file}`")
                lines.append(f"- **Source language:** {tf.metadata.source_language}")
                lines.append(f"- **Target language:** {tf.metadata.target_language}")
        else:
            lines.append("**Status:** ❌ Failed")
            lines.append("")
            lines.append(f"**Error:** {result.error}")

        return "\n".join(lines)

    def format_merge_result(self, result: MergeResult) -> str:
        """Format merge result as Markdown.

        Args:
            result: Merge result.

        Returns:
            Markdown string.
        """
        lines: list[str] = []

        lines.append("# Merge Result")
        lines.append("")

        if result.success:
            lines.append("**Status:** ✅ Success")
            lines.append("")

            stats = result.stats
            lines.append("| Metric | Count |")
            lines.append("|--------|-------|")
            lines.append(f"| Added | {stats.added} |")
            lines.append(f"| Updated | {stats.updated} |")
            lines.append(f"| Skipped (status) | {stats.skipped_status} |")
            lines.append(f"| Skipped (existing) | {stats.skipped_existing} |")
            lines.append(f"| Errors | {stats.errors} |")

            if result.warnings:
                lines.append("")
                lines.append("## Warnings")
                lines.append("")
                for warning in result.warnings:
                    lines.append(f"- {warning}")
        else:
            lines.append("**Status:** ❌ Failed")
            lines.append("")
            lines.append(f"**Error:** {result.error}")

        return "\n".join(lines)

    def format_coverage_report(
        self,
        report: CoverageReport,
        verbose: bool = False,
    ) -> str:
        """Format coverage report as Markdown.

        Args:
            report: Coverage report.
            verbose: Include detailed missing entity list.

        Returns:
            Markdown string.
        """
        lines: list[str] = []

        # Header
        lines.append("# Translation Coverage Report")
        lines.append("")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Source file:** `{report.source_file}`")
        lines.append(f"- **Source language:** {report.source_language}")
        lines.append(f"- **Total entities:** {report.total_entities}")
        lines.append(f"- **Properties checked:** {', '.join(report.properties)}")
        lines.append("")

        # Coverage table
        lines.append("## Coverage by Language")
        lines.append("")

        # Build header
        header = ["Language"]
        header.extend(report.properties)
        header.append("Overall")
        header.append("Status")
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * len(header)) + " |")

        # Data rows
        for lang, coverage in report.languages.items():
            row = []

            # Language
            if coverage.is_source:
                row.append(f"**{lang}** (base)")
            else:
                row.append(lang)

            # Property coverages
            for prop in report.properties:
                prop_cov = coverage.by_property.get(prop)
                if prop_cov:
                    pct = f"{prop_cov.coverage:.0f}%"
                else:
                    pct = "-"
                row.append(pct)

            # Overall
            row.append(f"**{coverage.coverage:.0f}%**")

            # Status
            if coverage.coverage == 100:
                row.append("✅ Complete")
            elif coverage.coverage >= 75:
                row.append(f"⚠️ {coverage.pending} pending")
            elif coverage.coverage > 0:
                row.append(f"❌ {coverage.pending} pending")
            else:
                row.append("❌ Not started")

            lines.append("| " + " | ".join(row) + " |")

        # Missing translations section
        if verbose:
            has_missing = False
            for lang, coverage in report.languages.items():
                if coverage.missing_entities and not coverage.is_source:
                    if not has_missing:
                        lines.append("")
                        lines.append("## Missing Translations")
                        has_missing = True

                    lines.append("")
                    lines.append(f"### {lang.upper()}")
                    lines.append("")

                    # Group by entity type based on URI pattern
                    lines.append("<details>")
                    lines.append(f"<summary>{len(coverage.missing_entities)} entities missing translations</summary>")
                    lines.append("")
                    for uri in coverage.missing_entities:
                        short_uri = self._shorten_uri(uri)
                        lines.append(f"- `{short_uri}`")
                    lines.append("")
                    lines.append("</details>")

        # Footer
        lines.append("")
        lines.append("---")
        lines.append("*Generated by rdf-construct localise*")

        return "\n".join(lines)

    def _shorten_uri(self, uri: str) -> str:
        """Shorten a URI for display.

        Args:
            uri: Full URI.

        Returns:
            Shortened version.
        """
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
