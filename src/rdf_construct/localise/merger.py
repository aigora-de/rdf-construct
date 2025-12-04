"""Merge translations back into RDF ontologies.

Takes completed translation files and adds translated literals to the
ontology, creating new language-tagged triples.
"""

from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph, Literal, URIRef

from rdf_construct.localise.config import (
    ExistingStrategy,
    MergeConfig,
    TranslationFile,
    TranslationStatus,
)


@dataclass
class MergeStats:
    """Statistics for a merge operation.

    Attributes:
        added: Number of translations added.
        updated: Number of translations updated.
        skipped_status: Translations skipped due to status.
        skipped_existing: Translations skipped (already exist, preserve mode).
        errors: Number of errors encountered.
    """

    added: int = 0
    updated: int = 0
    skipped_status: int = 0
    skipped_existing: int = 0
    errors: int = 0

    @property
    def total_processed(self) -> int:
        """Total translations processed."""
        return self.added + self.updated + self.skipped_status + self.skipped_existing


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
            merged = Graph()
            for prefix, namespace in graph.namespaces():
                merged.bind(prefix, namespace)
            for triple in graph:
                merged.add(triple)

            stats = MergeStats()
            warnings: list[str] = []
            target_lang = translation_file.metadata.target_language

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
                    # Check status threshold
                    if not self._meets_status(entry.status):
                        stats.skipped_status += 1
                        continue

                    # Skip empty translations
                    if not entry.translation.strip():
                        stats.skipped_status += 1
                        continue

                    # Expand property
                    prop_uri = URIRef(self._expand_property(entry.property))

                    # Check for existing translation
                    existing = self._get_existing_translation(
                        merged, entity_uri, prop_uri, target_lang
                    )

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
        merged = Graph()
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
            combined_stats.errors += result.stats.errors
            all_warnings.extend(result.warnings)

        return MergeResult(
            success=True,
            merged_graph=merged,
            stats=combined_stats,
            warnings=all_warnings,
        )

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
            List of matching triples.
        """
        existing = []

        for obj in graph.objects(subject, predicate):
            if isinstance(obj, Literal) and obj.language == language:
                existing.append((subject, predicate, obj))

        return existing

    def _expand_property(self, prop: str) -> str:
        """Expand a CURIE to full URI.

        Args:
            prop: Property string (CURIE or full URI).

        Returns:
            Full URI string.
        """
        prefixes = {
            "rdfs:": "http://www.w3.org/2000/01/rdf-schema#",
            "skos:": "http://www.w3.org/2004/02/skos/core#",
            "owl:": "http://www.w3.org/2002/07/owl#",
            "rdf:": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "dc:": "http://purl.org/dc/elements/1.1/",
            "dcterms:": "http://purl.org/dc/terms/",
        }

        for prefix, namespace in prefixes.items():
            if prop.startswith(prefix):
                return namespace + prop[len(prefix) :]

        return prop


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
    # Load graph
    graph = Graph()
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
