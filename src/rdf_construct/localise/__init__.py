"""Localise module for multi-language translation management.

This module provides tools for managing translations in RDF ontologies:
- Extract translatable strings to YAML files for translators
- Merge completed translations back into ontologies
- Report on translation coverage across languages

Example usage:
    from rdf_construct.localise import (
        StringExtractor,
        TranslationMerger,
        CoverageReporter,
        extract_strings,
        merge_translations,
        generate_coverage_report,
    )

    # Extract strings for German translation
    result = extract_strings(
        source=Path("ontology.ttl"),
        target_language="de",
        output=Path("translations/de.yml"),
    )

    # Merge completed translations
    result = merge_translations(
        source=Path("ontology.ttl"),
        translation_files=[Path("translations/de.yml")],
        output=Path("localised.ttl"),
    )

    # Generate coverage report
    report = generate_coverage_report(
        source=Path("ontology.ttl"),
        languages=["en", "de", "fr"],
    )
"""

from rdf_construct.localise.config import (
    TranslationStatus,
    TranslationEntry,
    EntityTranslations,
    TranslationFile,
    TranslationFileMetadata,
    TranslationSummary,
    ExtractConfig,
    MergeConfig,
    ExistingStrategy,
    LocaliseConfig,
    create_default_config,
    load_localise_config,
)

from rdf_construct.localise.extractor import (
    StringExtractor,
    ExtractionResult,
    extract_strings,
)

from rdf_construct.localise.merger import (
    TranslationMerger,
    MergeResult,
    MergeStats,
    merge_translations,
)

from rdf_construct.localise.reporter import (
    CoverageReporter,
    CoverageReport,
    LanguageCoverage,
    PropertyCoverage,
    generate_coverage_report,
)

from rdf_construct.localise.formatters import (
    TextFormatter,
    MarkdownFormatter,
    get_formatter,
)

__all__ = [
    # Config
    "TranslationStatus",
    "TranslationEntry",
    "EntityTranslations",
    "TranslationFile",
    "TranslationFileMetadata",
    "TranslationSummary",
    "ExtractConfig",
    "MergeConfig",
    "ExistingStrategy",
    "LocaliseConfig",
    "create_default_config",
    "load_localise_config",
    # Extractor
    "StringExtractor",
    "ExtractionResult",
    "extract_strings",
    # Merger
    "TranslationMerger",
    "MergeResult",
    "MergeStats",
    "merge_translations",
    # Reporter
    "CoverageReporter",
    "CoverageReport",
    "LanguageCoverage",
    "PropertyCoverage",
    "generate_coverage_report",
    # Formatters
    "TextFormatter",
    "MarkdownFormatter",
    "get_formatter",
]
