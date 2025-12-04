"""String extraction from RDF ontologies.

Extracts translatable strings (labels, comments, definitions) from ontology
files and generates translation files in YAML format.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from rdf_construct.localise.config import (
    EntityTranslations,
    ExtractConfig,
    TranslationEntry,
    TranslationFile,
    TranslationFileMetadata,
    TranslationStatus,
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
    """

    success: bool
    translation_file: TranslationFile | None = None
    total_entities: int = 0
    total_strings: int = 0
    skipped_entities: int = 0
    error: str | None = None


class StringExtractor:
    """Extracts translatable strings from RDF ontologies.

    The extractor identifies entities (classes, properties, individuals) and
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
            # Get all entities from the graph
            entities = self._collect_entities(graph)

            # Extract translations for each entity
            entity_translations: list[EntityTranslations] = []
            total_strings = 0
            skipped = 0

            for entity_uri, entity_type in entities:
                # Check for deprecation
                if not self.config.include_deprecated and self._is_deprecated(
                    graph, entity_uri
                ):
                    skipped += 1
                    continue

                # Extract labels for this entity
                labels = self._extract_entity_labels(
                    graph,
                    entity_uri,
                    target_lang,
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
                            entity_type=entity_type,
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
                properties=[self._shorten_property(p) for p in self.config.properties],
            )

            translation_file = TranslationFile(
                metadata=metadata,
                entities=entity_translations,
            )

            return ExtractionResult(
                success=True,
                translation_file=translation_file,
                total_entities=len(entity_translations),
                total_strings=total_strings,
                skipped_entities=skipped,
            )

        except Exception as e:
            return ExtractionResult(
                success=False,
                error=str(e),
            )

    def _collect_entities(self, graph: Graph) -> list[tuple[URIRef, str]]:
        """Collect all entities from the graph with their types.

        Args:
            graph: RDF graph.

        Returns:
            List of (URI, type_string) tuples.
        """
        entities: list[tuple[URIRef, str]] = []
        seen: set[URIRef] = set()

        # Classes
        for cls_type in [OWL.Class, RDFS.Class]:
            for s in graph.subjects(RDF.type, cls_type):
                if isinstance(s, URIRef) and s not in seen:
                    seen.add(s)
                    entities.append((s, "owl:Class"))

        # Object Properties
        for s in graph.subjects(RDF.type, OWL.ObjectProperty):
            if isinstance(s, URIRef) and s not in seen:
                seen.add(s)
                entities.append((s, "owl:ObjectProperty"))

        # Datatype Properties
        for s in graph.subjects(RDF.type, OWL.DatatypeProperty):
            if isinstance(s, URIRef) and s not in seen:
                seen.add(s)
                entities.append((s, "owl:DatatypeProperty"))

        # Annotation Properties
        for s in graph.subjects(RDF.type, OWL.AnnotationProperty):
            if isinstance(s, URIRef) and s not in seen:
                seen.add(s)
                entities.append((s, "owl:AnnotationProperty"))

        # RDF Properties
        for s in graph.subjects(RDF.type, RDF.Property):
            if isinstance(s, URIRef) and s not in seen:
                seen.add(s)
                entities.append((s, "rdf:Property"))

        # Named Individuals
        for s in graph.subjects(RDF.type, OWL.NamedIndividual):
            if isinstance(s, URIRef) and s not in seen:
                seen.add(s)
                entities.append((s, "owl:NamedIndividual"))

        # Sort by URI for consistent output
        entities.sort(key=lambda x: str(x[0]))

        return entities

    def _extract_entity_labels(
        self,
        graph: Graph,
        entity: URIRef,
        target_lang: str,
    ) -> list[TranslationEntry]:
        """Extract label properties for a single entity.

        Args:
            graph: RDF graph.
            entity: Entity URI.
            target_lang: Target language code.

        Returns:
            List of TranslationEntry objects.
        """
        labels: list[TranslationEntry] = []
        source_lang = self.config.source_language

        for prop_uri_str in self.config.properties:
            prop_uri = URIRef(self._expand_property(prop_uri_str))

            # Find source language literals
            source_literals = self._get_language_literals(
                graph, entity, prop_uri, source_lang
            )

            if not source_literals:
                continue

            # Check for existing translation if missing_only mode
            if self.config.missing_only:
                existing = self._get_language_literals(
                    graph, entity, prop_uri, target_lang
                )
                if existing:
                    continue

            for source_text in source_literals:
                labels.append(
                    TranslationEntry(
                        property=self._shorten_property(str(prop_uri)),
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
        results: list[str] = []

        for obj in graph.objects(subject, predicate):
            if isinstance(obj, Literal):
                # Match language exactly or match untagged literals for source
                obj_lang = obj.language
                if obj_lang == language:
                    results.append(str(obj))
                elif obj_lang is None and language == self.config.source_language:
                    # Treat untagged literals as source language
                    results.append(str(obj))

        return results

    def _is_deprecated(self, graph: Graph, entity: URIRef) -> bool:
        """Check if an entity is deprecated.

        Args:
            graph: RDF graph.
            entity: Entity URI.

        Returns:
            True if entity is deprecated.
        """
        # Check owl:deprecated
        for obj in graph.objects(entity, OWL.deprecated):
            if isinstance(obj, Literal) and obj.toPython() is True:
                return True

        # Check owl:DeprecatedClass / owl:DeprecatedProperty
        deprecated_types = [OWL.DeprecatedClass, OWL.DeprecatedProperty]
        for dtype in deprecated_types:
            if (entity, RDF.type, dtype) in graph:
                return True

        return False

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

    def _shorten_property(self, prop: str) -> str:
        """Shorten a full URI to CURIE if possible.

        Args:
            prop: Full property URI.

        Returns:
            CURIE or original URI.
        """
        namespaces = {
            "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
            "http://www.w3.org/2004/02/skos/core#": "skos:",
            "http://www.w3.org/2002/07/owl#": "owl:",
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
            "http://purl.org/dc/elements/1.1/": "dc:",
            "http://purl.org/dc/terms/": "dcterms:",
        }

        for namespace, prefix in namespaces.items():
            if prop.startswith(namespace):
                return prefix + prop[len(namespace) :]

        return prop


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
        properties: Properties to extract. Uses defaults if not provided.
        include_deprecated: Include deprecated entities.
        missing_only: Only extract missing translations.

    Returns:
        ExtractionResult with translation file.
    """
    # Load graph
    graph = Graph()
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
