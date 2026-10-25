"""String extraction from RDF ontologies.

Extracts translatable strings (labels, comments, definitions) from ontology
files and generates translation files in YAML format.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rdflib import Graph, URIRef

from rdf_construct.localise.config import (
    EntityTranslations,
    ExtractConfig,
    TranslationEntry,
    TranslationFile,
    TranslationFileMetadata,
    TranslationStatus,
)
from rdf_construct.localise.entities import (
    collect_entities,
    entity_type,
    in_language,
    is_deprecated,
    literals,
    related_tags,
    zero_match_warnings,
)
from rdf_construct.localise.properties import (
    FILE_PREFIXES,
    resolve_properties,
    shorten_property,
    source_prefixes,
)


# Standard property URIs
LABEL_PROPERTIES = [
    "http://www.w3.org/2000/01/rdf-schema#label",
    "http://www.w3.org/2004/02/skos/core#prefLabel",
    "http://www.w3.org/2004/02/skos/core#altLabel",
]

COMMENT_PROPERTIES = [
    "http://www.w3.org/2000/01/rdf-schema#comment",
    "http://www.w3.org/2004/02/skos/core#definition",
    "http://www.w3.org/2004/02/skos/core#example",
    "http://www.w3.org/2004/02/skos/core#note",
    "http://www.w3.org/2004/02/skos/core#scopeNote",
]

DEFAULT_PROPERTIES = LABEL_PROPERTIES[:2] + COMMENT_PROPERTIES[:2]


@dataclass
class ExtractionResult:
    """Result of a string extraction operation.

    Attributes:
        success: Whether extraction succeeded.
        translation_file: Generated translation file.
        total_entities: Number of entities processed.
        total_strings: Number of strings extracted.
        skipped_entities: Number of entities skipped.
        error: Error message if failed.
        warnings: Findings that did not stop the extraction, such as a source language that
            matched no literal while a related tag did.
    """

    success: bool
    translation_file: TranslationFile | None = None
    total_entities: int = 0
    total_strings: int = 0
    skipped_entities: int = 0
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


class StringExtractor:
    """Extracts translatable strings from RDF ontologies.

    The extractor identifies entities (every IRI subject carrying one of the
    configured properties, see :mod:`rdf_construct.localise.entities`) and
    extracts text values for configured properties (rdfs:label, rdfs:comment, etc.)
    in the source language. The output is a translation file with empty
    translation fields ready for translators.
    """

    def __init__(self, config: ExtractConfig | None = None):
        """Initialise the extractor.

        Args:
            config: Extraction configuration. Uses defaults if not provided.
        """
        self.config = config or ExtractConfig()

    def extract(
        self,
        graph: Graph,
        source_file: Path | str,
        target_language: str | None = None,
    ) -> ExtractionResult:
        """Extract translatable strings from an RDF graph.

        Args:
            graph: RDF graph to extract from.
            source_file: Path to source file (for metadata).
            target_language: Override target language from config.

        Returns:
            ExtractionResult with translation file.
        """
        target_lang = target_language or self.config.target_language
        if not target_lang:
            return ExtractionResult(
                success=False,
                error="No target language specified",
            )

        try:
            # Get all entities from the graph. A CURIE means what the ontology's prefixes say (#355)
            properties = resolve_properties(source_prefixes(graph), self.config.properties)
            entities = collect_entities(graph, properties)

            # Extract translations for each entity
            entity_translations: list[EntityTranslations] = []
            read: list[URIRef] = []
            total_strings = 0
            skipped = 0

            for entity_uri in entities:
                # Check for deprecation
                if not self.config.include_deprecated and is_deprecated(graph, entity_uri):
                    skipped += 1
                    continue
                read.append(entity_uri)

                # Extract labels for this entity
                labels = self._extract_entity_labels(
                    graph,
                    entity_uri,
                    target_lang,
                    properties,
                )

                if not labels:
                    if self.config.include_unlabelled:
                        # Include entity with empty labels
                        pass
                    else:
                        skipped += 1
                        continue

                if labels:
                    entity_translations.append(
                        EntityTranslations(
                            uri=str(entity_uri),
                            entity_type=entity_type(graph, entity_uri),
                            labels=labels,
                        )
                    )
                    total_strings += len(labels)

            # Build translation file
            metadata = TranslationFileMetadata(
                source_file=str(source_file),
                source_language=self.config.source_language,
                target_language=target_lang,
                generated=datetime.now(),
                properties=[shorten_property(FILE_PREFIXES, p) for p in properties],
            )

            translation_file = TranslationFile(
                metadata=metadata,
                entities=entity_translations,
            )

            # A source language that matched nothing, beside a related tag that did (#159)
            source_lang = self.config.source_language
            warnings: list[str] = []
            if not any(
                in_language(value, source_lang, source_lang)
                for entity in read
                for prop in properties
                for value in literals(graph, entity, prop)
            ):
                warnings = zero_match_warnings(
                    related_tags(graph, read, properties, source_lang),
                    source_lang,
                    "--source-language",
                )

            return ExtractionResult(
                success=True,
                translation_file=translation_file,
                total_entities=len(entity_translations),
                total_strings=total_strings,
                skipped_entities=skipped,
                warnings=warnings,
            )

        except Exception as e:
            return ExtractionResult(
                success=False,
                error=str(e),
            )

    def _extract_entity_labels(
        self,
        graph: Graph,
        entity: URIRef,
        target_lang: str,
        properties: list[URIRef],
    ) -> list[TranslationEntry]:
        """Extract label properties for a single entity.

        Args:
            graph: RDF graph.
            entity: Entity URI.
            target_lang: Target language code.
            properties: The properties to extract, resolved.

        Returns:
            List of TranslationEntry objects.
        """
        labels: list[TranslationEntry] = []
        source_lang = self.config.source_language

        for prop_uri in properties:
            # Find source language literals
            source_literals = self._get_language_literals(graph, entity, prop_uri, source_lang)

            if not source_literals:
                continue

            # Check for existing translation if missing_only mode
            if self.config.missing_only:
                existing = self._get_language_literals(graph, entity, prop_uri, target_lang)
                if existing:
                    continue

            for source_text in source_literals:
                labels.append(
                    TranslationEntry(
                        property=shorten_property(FILE_PREFIXES, prop_uri),
                        source_text=source_text,
                        translation="",
                        status=TranslationStatus.PENDING,
                    )
                )

        return labels

    def _get_language_literals(
        self,
        graph: Graph,
        subject: URIRef,
        predicate: URIRef,
        language: str,
    ) -> list[str]:
        """Get literal values for a specific language.

        Args:
            graph: RDF graph.
            subject: Subject URI.
            predicate: Predicate URI.
            language: Language code.

        Returns:
            List of literal string values.
        """
        return [
            str(value)
            for value in literals(graph, subject, predicate)
            if in_language(value, language, self.config.source_language)
        ]


def extract_strings(
    source: Path,
    target_language: str,
    output: Path | None = None,
    source_language: str = "en",
    properties: list[str] | None = None,
    include_deprecated: bool = False,
    missing_only: bool = False,
) -> ExtractionResult:
    """Extract translatable strings from an ontology file.

    Convenience function for simple extraction.

    Args:
        source: Source ontology file.
        target_language: Target language code.
        output: Output file path. Auto-generated if not provided.
        source_language: Source language code.
        properties: Properties to extract, as CURIEs on the source file's own prefixes or as
            IRIs. Uses defaults if not provided.
        include_deprecated: Include deprecated entities.
        missing_only: Only extract missing translations.

    Returns:
        ExtractionResult with translation file. A CURIE whose prefix the source file does not
        bind fails the extraction, naming the bound prefixes.
    """
    # Load graph: the source's own prefixes, plus rdf, rdfs, owl, xsd and xml (#355)
    graph = Graph(bind_namespaces="core")
    graph.parse(source)

    # Build config
    config = ExtractConfig(
        source_language=source_language,
        target_language=target_language,
        properties=properties or list(DEFAULT_PROPERTIES),
        include_deprecated=include_deprecated,
        missing_only=missing_only,
    )

    # Extract
    extractor = StringExtractor(config)
    result = extractor.extract(graph, source, target_language)

    # Save if requested
    if result.success and output and result.translation_file:
        result.translation_file.save(output)

    return result
