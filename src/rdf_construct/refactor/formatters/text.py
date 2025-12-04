"""Text formatter for refactor command output.

Provides formatted output for dry-run previews and results.
"""

from typing import Any

from rdf_construct.refactor.config import RenameConfig, RenameMapping, DeprecationSpec
from rdf_construct.refactor.renamer import RenameResult, RenameStats
from rdf_construct.refactor.deprecator import DeprecationResult, EntityDeprecationInfo


class TextFormatter:
    """Text formatter for refactor results and previews.

    Attributes:
        use_colour: Whether to use ANSI colour codes.
    """

    def __init__(self, use_colour: bool = True):
        """Initialize formatter.

        Args:
            use_colour: Whether to use ANSI colour codes.
        """
        self.use_colour = use_colour

    def _colour(self, text: str, colour: str) -> str:
        """Apply ANSI colour code if enabled.

        Args:
            text: Text to colour.
            colour: Colour name (green, red, yellow, cyan, bold).

        Returns:
            Coloured text (or original if colour disabled).
        """
        if not self.use_colour:
            return text

        codes = {
            "green": "\033[32m",
            "red": "\033[31m",
            "yellow": "\033[33m",
            "cyan": "\033[36m",
            "bold": "\033[1m",
            "dim": "\033[2m",
            "reset": "\033[0m",
        }
        return f"{codes.get(colour, '')}{text}{codes['reset']}"

    def format_rename_preview(
        self,
        mappings: list[RenameMapping],
        source_file: str,
        source_triples: int,
        literal_mentions: dict[str, int] | None = None,
    ) -> str:
        """Format a dry-run preview for rename operation.

        Args:
            mappings: List of rename mappings to apply.
            source_file: Name of source file.
            source_triples: Number of triples in source.
            literal_mentions: Count of mentions in literals (won't be changed).

        Returns:
            Formatted preview string.
        """
        lines = [
            self._colour("Refactoring Preview: Rename", "bold"),
            "=" * 27,
            "",
            f"Source: {source_file} ({source_triples:,} triples)",
            "",
        ]

        # Group by source type
        namespace_mappings = [m for m in mappings if m.source == "namespace"]
        explicit_mappings = [m for m in mappings if m.source == "explicit"]

        if namespace_mappings:
            # Group by namespace
            namespaces: dict[str, list[RenameMapping]] = {}
            for m in namespace_mappings:
                # Extract namespace prefix
                from_str = str(m.from_uri)
                to_str = str(m.to_uri)
                # Find common prefix
                ns_from = from_str.rsplit("#", 1)[0] + "#" if "#" in from_str else from_str.rsplit("/", 1)[0] + "/"
                ns_to = to_str.rsplit("#", 1)[0] + "#" if "#" in to_str else to_str.rsplit("/", 1)[0] + "/"
                key = f"{ns_from} → {ns_to}"
                if key not in namespaces:
                    namespaces[key] = []
                namespaces[key].append(m)

            lines.append(self._colour("Namespace renames:", "cyan"))
            for ns_change, ns_mappings in namespaces.items():
                lines.append(f"  {ns_change}")
                lines.append(f"    - {len(ns_mappings)} entities affected")
            lines.append("")

        if explicit_mappings:
            lines.append(self._colour("Entity renames:", "cyan"))
            for m in explicit_mappings:
                from_local = str(m.from_uri).split("#")[-1].split("/")[-1]
                to_local = str(m.to_uri).split("#")[-1].split("/")[-1]
                lines.append(f"  {from_local} → {to_local}")

                # Check for literal mentions
                if literal_mentions and str(m.from_uri) in literal_mentions:
                    count = literal_mentions[str(m.from_uri)]
                    lines.append(
                        f"    └─ {count} literal mention(s) "
                        f"{self._colour('(NOT changed)', 'yellow')}"
                    )
            lines.append("")

        # Summary
        lines.append(self._colour("Totals:", "bold"))
        lines.append(f"  - {len(mappings)} entities to rename")
        if namespace_mappings:
            lines.append(f"  - {len(namespace_mappings)} from namespace rules")
        if explicit_mappings:
            lines.append(f"  - {len(explicit_mappings)} from explicit rules")
        lines.append("")
        lines.append(self._colour("Run without --dry-run to apply changes.", "dim"))

        return "\n".join(lines)

    def format_rename_result(self, result: RenameResult) -> str:
        """Format the result of a rename operation.

        Args:
            result: Result from rename operation.

        Returns:
            Formatted result string.
        """
        if not result.success:
            return self._colour(f"✗ Rename failed: {result.error}", "red")

        lines = [
            self._colour("Rename Complete", "green"),
            "",
            f"  Source triples: {result.source_triples:,}",
            f"  Result triples: {result.result_triples:,}",
            "",
            self._colour("Changes:", "cyan"),
            f"  - Subjects renamed: {result.stats.subjects_renamed:,}",
            f"  - Predicates renamed: {result.stats.predicates_renamed:,}",
            f"  - Objects renamed: {result.stats.objects_renamed:,}",
            f"  - Total URI substitutions: {result.stats.total_renames:,}",
        ]

        if result.stats.namespace_entities > 0:
            lines.append(f"  - Via namespace rules: {result.stats.namespace_entities:,}")
        if result.stats.explicit_entities > 0:
            lines.append(f"  - Via explicit rules: {result.stats.explicit_entities:,}")

        if result.stats.literal_mentions:
            lines.append("")
            lines.append(
                self._colour(
                    f"  ⚠ {len(result.stats.literal_mentions)} entities mentioned in literals "
                    "(not modified)",
                    "yellow",
                )
            )

        return "\n".join(lines)

    def format_deprecation_preview(
        self,
        specs: list[DeprecationSpec],
        entity_info: list[EntityDeprecationInfo] | None = None,
        source_file: str = "",
        source_triples: int = 0,
    ) -> str:
        """Format a dry-run preview for deprecation operation.

        Args:
            specs: List of deprecation specifications.
            entity_info: Optional entity information from dry run.
            source_file: Name of source file.
            source_triples: Number of triples in source.

        Returns:
            Formatted preview string.
        """
        lines = [
            self._colour("Refactoring Preview: Deprecate", "bold"),
            "=" * 30,
            "",
            f"Source: {source_file} ({source_triples:,} triples)" if source_file else "",
            "",
            self._colour("Entities to deprecate:", "cyan"),
            "",
        ]

        for i, spec in enumerate(specs):
            # Extract local name
            local_name = spec.entity.split("#")[-1].split("/")[-1]
            lines.append(f"  {self._colour(local_name, 'bold')}")

            # Show current state if available
            if entity_info and i < len(entity_info):
                info = entity_info[i]
                if not info.found:
                    lines.append(f"    {self._colour('⚠ Entity not found in graph', 'yellow')}")
                else:
                    if info.was_already_deprecated:
                        lines.append(f"    {self._colour('Already deprecated', 'yellow')}")
                    if info.current_labels:
                        lines.append(f"    rdfs:label: \"{info.current_labels[0]}\"")
                    if info.reference_count > 0:
                        lines.append(
                            f"    {self._colour(f'Referenced {info.reference_count} times', 'dim')}"
                        )

            # Show what will be added
            lines.append("    Will add:")
            lines.append(f"      owl:deprecated {self._colour('true', 'green')}")

            if spec.replaced_by:
                repl_local = spec.replaced_by.split("#")[-1].split("/")[-1]
                lines.append(f"      dcterms:isReplacedBy {self._colour(repl_local, 'cyan')}")

            if spec.message:
                msg_preview = spec.message[:50] + "..." if len(spec.message) > 50 else spec.message
                lines.append(f"      rdfs:comment \"DEPRECATED: {msg_preview}\"")

            lines.append("")

        # Summary
        lines.append(self._colour("Summary:", "bold"))
        lines.append(f"  - {len(specs)} entities will be marked deprecated")
        with_replacement = len([s for s in specs if s.replaced_by])
        lines.append(f"  - {with_replacement} with replacement")
        lines.append(f"  - {len(specs) - with_replacement} without replacement")
        lines.append("")
        lines.append(
            self._colour(
                "Note: Deprecation marks entities but does not rename or migrate.",
                "dim",
            )
        )
        lines.append(
            self._colour(
                "      Use 'refactor rename' to actually migrate references.",
                "dim",
            )
        )
        lines.append("")
        lines.append(self._colour("Run without --dry-run to apply changes.", "dim"))

        return "\n".join(lines)

    def format_deprecation_result(self, result: DeprecationResult) -> str:
        """Format the result of a deprecation operation.

        Args:
            result: Result from deprecation operation.

        Returns:
            Formatted result string.
        """
        if not result.success:
            return self._colour(f"✗ Deprecation failed: {result.error}", "red")

        lines = [
            self._colour("Deprecation Complete", "green"),
            "",
            f"  Source triples: {result.source_triples:,}",
            f"  Result triples: {result.result_triples:,}",
            "",
            self._colour("Changes:", "cyan"),
            f"  - Entities deprecated: {result.stats.entities_deprecated}",
            f"  - Triples added: {result.stats.triples_added}",
        ]

        if result.stats.entities_not_found > 0:
            lines.append(
                self._colour(
                    f"  ⚠ Entities not found: {result.stats.entities_not_found}",
                    "yellow",
                )
            )

        if result.stats.entities_already_deprecated > 0:
            lines.append(
                f"  - Already deprecated: {result.stats.entities_already_deprecated}"
            )

        # Show details of deprecated entities
        if result.entity_info:
            lines.append("")
            lines.append("Details:")
            for info in result.entity_info:
                local_name = info.uri.split("#")[-1].split("/")[-1]
                if not info.found:
                    lines.append(f"  {self._colour('⚠', 'yellow')} {local_name} - not found")
                elif info.was_already_deprecated and info.triples_added == 0:
                    lines.append(f"  ○ {local_name} - already deprecated, no changes")
                else:
                    lines.append(f"  {self._colour('✓', 'green')} {local_name}")
                    if info.replaced_by:
                        repl_local = info.replaced_by.split("#")[-1].split("/")[-1]
                        lines.append(f"      → replaced by {repl_local}")

        return "\n".join(lines)
