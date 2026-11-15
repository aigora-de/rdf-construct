"""Merge translations back into RDF ontologies.

Takes completed translation files and adds translated literals to the
ontology, creating new language-tagged triples.
"""

from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph, Literal, URIRef

from rdf_construct.core.language_tags import canonical_case
from rdf_construct.core.predicate_tiers import (
    DEFAULT_PREDICATE_TIERS,
    PredicateTier,
    tier_of,
)
from rdf_construct.localise.config import (
    ExistingStrategy,
    MergeConfig,
    TranslationEntry,
    TranslationFile,
    TranslationStatus,
)
from rdf_construct.localise.entities import in_language, literals
from rdf_construct.localise.properties import FILE_PREFIXES, resolve_property


@dataclass
class MergeStats:
    """Statistics for a merge operation.

    Attributes:
        added: Number of translations added.
        updated: Number of translations updated.
        skipped_status: Translations skipped due to status.
        skipped_existing: Translations skipped (already exist, preserve mode).
        skipped_group: Translations of a repeatable property left unmerged under ``overwrite``,
            because their group was incomplete or its sources no longer match the ontology's
            (#405). Each such group is named in a warning.
        errors: Number of errors encountered.
    """

    added: int = 0
    updated: int = 0
    skipped_status: int = 0
    skipped_existing: int = 0
    skipped_group: int = 0
    errors: int = 0

    @property
    def total_processed(self) -> int:
        """Total translations processed."""
        return (
            self.added
            + self.updated
            + self.skipped_status
            + self.skipped_existing
            + self.skipped_group
        )


@dataclass
class MergeResult:
    """Result of a translation merge operation.

    Attributes:
        success: Whether merge succeeded.
        merged_graph: Graph with merged translations.
        stats: Merge statistics.
        error: Error message if failed.
        warnings: List of warning messages.
    """

    success: bool
    merged_graph: Graph | None = None
    stats: MergeStats = field(default_factory=MergeStats)
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


class TranslationMerger:
    """Merges translation files back into RDF ontologies.

    The merger takes completed translation YAML files and adds the
    translations as new language-tagged literals to the ontology.

    Language tags are compared without regard to case, so an existing ``@de`` label is found
    for a file whose ``target_language`` is ``DE``, and every literal written carries the tag in
    canonical case (``en-GB``) (#159). For a property that takes any number of values, such as
    ``skos:altLabel``, ``preserve`` skips a translation only when that same text already exists
    in the language, rather than whenever any value does.

    Under ``overwrite`` such a property's translations replace that language's values as one set,
    per entity and property, and only when nothing is lost by it (#405): when the language has no
    value yet, every finished translation is added; otherwise the set is replaced only if every
    entry for it is finished and their source texts are exactly the ontology's current source
    values. A group that fails either test is left as it is, counted in ``skipped_group`` and
    named in a warning. Nothing in RDF pairs one ``skos:altLabel`` with its translation, so the
    group, not the entry, is what is matched.
    """

    def __init__(self, config: MergeConfig | None = None):
        """Initialise the merger.

        Args:
            config: Merge configuration. Uses defaults if not provided.
        """
        self.config = config or MergeConfig()

    def merge(
        self,
        graph: Graph,
        translation_file: TranslationFile,
    ) -> MergeResult:
        """Merge translations into an RDF graph.

        Args:
            graph: RDF graph to merge into.
            translation_file: Completed translation file.

        Returns:
            MergeResult with merged graph.
        """
        try:
            # Create a copy of the graph to work with
            merged = Graph(bind_namespaces="core")
            for prefix, namespace in graph.namespaces():
                merged.bind(prefix, namespace)
            for triple in graph:
                merged.add(triple)

            stats = MergeStats()
            warnings: list[str] = []
            target_lang = canonical_case(translation_file.metadata.target_language)
            source_lang = translation_file.metadata.source_language

            # A repeatable property is overwritten as a set: gather each group's entries first,
            # across the whole file, keyed on the resolved property (#405)
            groups: dict[tuple[URIRef, URIRef], list[TranslationEntry]] = {}
            if self.config.existing == ExistingStrategy.OVERWRITE:
                for entity in translation_file.entities:
                    for entry in entity.labels:
                        prop_uri = resolve_property(FILE_PREFIXES, entry.property)
                        if tier_of(prop_uri, DEFAULT_PREDICATE_TIERS) is PredicateTier.REPEATABLE:
                            groups.setdefault((URIRef(entity.uri), prop_uri), []).append(entry)
            merged_groups: set[tuple[URIRef, URIRef]] = set()

            # Process each entity
            for entity in translation_file.entities:
                entity_uri = URIRef(entity.uri)

                # Check entity exists in graph
                if not self._entity_exists(merged, entity_uri):
                    warnings.append(f"Entity not found in graph: {entity.uri}")
                    stats.errors += 1
                    continue

                # Process each label
                for entry in entity.labels:
                    key = (entity_uri, resolve_property(FILE_PREFIXES, entry.property))
                    if key in groups:
                        if key not in merged_groups:
                            merged_groups.add(key)
                            self._merge_repeatable_group(
                                merged, key, groups[key], target_lang, source_lang, stats, warnings
                            )
                        continue

                    # Check status threshold
                    if not self._meets_status(entry.status):
                        stats.skipped_status += 1
                        continue

                    # Skip empty translations
                    if not entry.translation.strip():
                        stats.skipped_status += 1
                        continue

                    # A translation file's CURIEs are the file format's, not the ontology's (#355)
                    prop_uri = resolve_property(FILE_PREFIXES, entry.property)

                    # Check for existing translation
                    existing = self._get_existing_translation(
                        merged, entity_uri, prop_uri, target_lang
                    )

                    if (
                        existing
                        and self.config.existing == ExistingStrategy.PRESERVE
                        and tier_of(prop_uri, DEFAULT_PREDICATE_TIERS) is PredicateTier.REPEATABLE
                    ):
                        # Another value is another assertion: keep it only if it is this text
                        existing = [t for t in existing if str(t[2]) == entry.translation]

                    if existing:
                        if self.config.existing == ExistingStrategy.PRESERVE:
                            stats.skipped_existing += 1
                            continue
                        else:
                            # Remove existing before adding new
                            for triple in existing:
                                merged.remove(triple)
                            stats.updated += 1
                    else:
                        stats.added += 1

                    # Add translation
                    translation_literal = Literal(entry.translation, lang=target_lang)
                    merged.add((entity_uri, prop_uri, translation_literal))

            return MergeResult(
                success=True,
                merged_graph=merged,
                stats=stats,
                warnings=warnings,
            )

        except Exception as e:
            return MergeResult(
                success=False,
                error=str(e),
            )

    def merge_multiple(
        self,
        graph: Graph,
        translation_files: list[TranslationFile],
    ) -> MergeResult:
        """Merge multiple translation files into a graph.

        Args:
            graph: RDF graph to merge into.
            translation_files: List of translation files.

        Returns:
            Combined MergeResult.
        """
        # Start with a copy
        merged = Graph(bind_namespaces="core")
        for prefix, namespace in graph.namespaces():
            merged.bind(prefix, namespace)
        for triple in graph:
            merged.add(triple)

        combined_stats = MergeStats()
        all_warnings: list[str] = []

        for trans_file in translation_files:
            result = self.merge(merged, trans_file)

            if not result.success:
                return MergeResult(
                    success=False,
                    error=f"Failed merging {trans_file.metadata.target_language}: {result.error}",
                )

            # Use the merged graph for next iteration
            merged = result.merged_graph

            # Combine stats
            combined_stats.added += result.stats.added
            combined_stats.updated += result.stats.updated
            combined_stats.skipped_status += result.stats.skipped_status
            combined_stats.skipped_existing += result.stats.skipped_existing
            combined_stats.skipped_group += result.stats.skipped_group
            combined_stats.errors += result.stats.errors
            all_warnings.extend(result.warnings)

        return MergeResult(
            success=True,
            merged_graph=merged,
            stats=combined_stats,
            warnings=all_warnings,
        )

    def _merge_repeatable_group(
        self,
        graph: Graph,
        key: tuple[URIRef, URIRef],
        entries: list[TranslationEntry],
        target_lang: str,
        source_lang: str,
        stats: MergeStats,
        warnings: list[str],
    ) -> None:
        """Overwrite one entity's values of a repeatable property in the target language.

        Args:
            graph: The graph being merged into, changed in place.
            key: The entity and the resolved property.
            entries: Every entry in the file for that entity and property.
            target_lang: The target language tag, in canonical case.
            source_lang: The file's source language tag.
            stats: Counts to update.
            warnings: Warnings to extend.
        """
        subject, prop_uri = key
        finished = [
            entry
            for entry in entries
            if self._meets_status(entry.status) and entry.translation.strip()
        ]
        if not finished:
            stats.skipped_status += len(entries)
            return

        existing = self._get_existing_translation(graph, subject, prop_uri, target_lang)
        if existing:
            # Replacing the set must not lose a translation that nothing in the file replaces
            sources = {
                str(value)
                for value in literals(graph, subject, prop_uri)
                if in_language(value, source_lang, source_lang)
            }
            in_file = {entry.source_text for entry in entries}
            reason = ""
            if len(finished) < len(entries):
                reason = (
                    f"{len(entries) - len(finished)} of {len(entries)} entries not translated; "
                    "finish every entry, copying in any existing translation that still stands"
                )
            elif in_file != sources:
                reason = (
                    "the file's sources differ from the ontology's (not in the ontology: "
                    f"{_quoted(in_file - sources)}; not in the file: {_quoted(sources - in_file)}); "
                    "re-extract"
                )
            if reason:
                stats.skipped_group += len(entries)
                warnings.append(
                    f"Left unchanged: {subject} {entries[0].property} @{target_lang}: {reason}"
                )
                return
            for triple in existing:
                graph.remove(triple)

        stats.skipped_status += len(entries) - len(finished)
        for entry in finished:
            graph.add((subject, prop_uri, Literal(entry.translation, lang=target_lang)))
            if existing:
                stats.updated += 1
            else:
                stats.added += 1

    def _meets_status(self, status: TranslationStatus) -> bool:
        """Check if status meets minimum threshold.

        Args:
            status: Translation status to check.

        Returns:
            True if status meets threshold.
        """
        status_order = [
            TranslationStatus.PENDING,
            TranslationStatus.NEEDS_REVIEW,
            TranslationStatus.TRANSLATED,
            TranslationStatus.APPROVED,
        ]

        try:
            status_level = status_order.index(status)
            min_level = status_order.index(self.config.min_status)
            return status_level >= min_level
        except ValueError:
            return False

    def _entity_exists(self, graph: Graph, entity: URIRef) -> bool:
        """Check if an entity exists in the graph.

        Args:
            graph: RDF graph.
            entity: Entity URI.

        Returns:
            True if entity has any triples.
        """
        # Check if entity appears as subject
        for _ in graph.triples((entity, None, None)):
            return True

        return False

    def _get_existing_translation(
        self,
        graph: Graph,
        subject: URIRef,
        predicate: URIRef,
        language: str,
    ) -> list[tuple]:
        """Get existing translations for a specific language.

        Args:
            graph: RDF graph.
            subject: Subject URI.
            predicate: Predicate URI.
            language: Language code.

        Returns:
            List of matching triples, whatever the case of their tags.
        """
        existing = []

        for obj in graph.objects(subject, predicate):
            if (
                isinstance(obj, Literal)
                and obj.language
                and obj.language.lower() == language.lower()
            ):
                existing.append((subject, predicate, obj))

        return existing


def _quoted(values: set[str]) -> str:
    """Return `values` sorted and quoted, or "none"."""
    return ", ".join(f'"{value}"' for value in sorted(values)) or "none"


def merge_translations(
    source: Path,
    translation_files: list[Path],
    output: Path | None = None,
    min_status: str = "translated",
    existing: str = "preserve",
) -> MergeResult:
    """Merge translation files into an ontology.

    Convenience function for simple merge operations.

    Args:
        source: Source ontology file.
        translation_files: List of translation YAML files.
        output: Output file path. Writes to source if not provided.
        min_status: Minimum status to include.
        existing: How to handle existing translations.

    Returns:
        MergeResult with merged graph.
    """
    # Load graph: the source's own prefixes, plus rdf, rdfs, owl, xsd and xml (#355)
    graph = Graph(bind_namespaces="core")
    graph.parse(source)

    # Load translation files
    trans_files = [TranslationFile.from_yaml(p) for p in translation_files]

    # Build config
    config = MergeConfig(
        min_status=TranslationStatus(min_status),
        existing=ExistingStrategy(existing),
    )

    # Merge
    merger = TranslationMerger(config)
    result = merger.merge_multiple(graph, trans_files)

    # Save if requested
    if result.success and output and result.merged_graph:
        result.merged_graph.serialize(destination=output, format="turtle")

    return result
