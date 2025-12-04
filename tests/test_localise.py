"""Tests for the localise command.

Tests cover:
- Extract to YAML
- Extract with custom properties
- Extract --missing-only
- Merge translations
- Merge with status filtering
- Coverage report (text)
- Coverage report (Markdown)
- Init new language
- Round-trip: extract → fill → merge
- Multiple language files
"""

from datetime import datetime
from pathlib import Path
from textwrap import dedent

import pytest
from rdflib import Graph, Literal, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, OWL

from rdf_construct.localise import (
    # Config
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
    # Extractor
    StringExtractor,
    ExtractionResult,
    extract_strings,
    # Merger
    TranslationMerger,
    MergeResult,
    MergeStats,
    merge_translations,
    # Reporter
    CoverageReporter,
    CoverageReport,
    generate_coverage_report,
    # Formatters
    TextFormatter,
    MarkdownFormatter,
    get_formatter,
)


# Test namespaces
EX = Namespace("http://example.org/ontology#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def simple_ontology() -> Graph:
    """Create a simple ontology with English labels."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("rdfs", RDFS)
    g.bind("owl", OWL)

    # Define a class with English label and comment
    g.add((EX.Building, RDF.type, OWL.Class))
    g.add((EX.Building, RDFS.label, Literal("Building", lang="en")))
    g.add((EX.Building, RDFS.comment, Literal("A permanent structure", lang="en")))

    # Another class
    g.add((EX.Person, RDF.type, OWL.Class))
    g.add((EX.Person, RDFS.label, Literal("Person", lang="en")))

    # A property
    g.add((EX.hasLocation, RDF.type, OWL.ObjectProperty))
    g.add((EX.hasLocation, RDFS.label, Literal("has location", lang="en")))

    return g


@pytest.fixture
def multilingual_ontology() -> Graph:
    """Create an ontology with multiple language labels."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("rdfs", RDFS)
    g.bind("owl", OWL)

    # Class with English and German
    g.add((EX.Building, RDF.type, OWL.Class))
    g.add((EX.Building, RDFS.label, Literal("Building", lang="en")))
    g.add((EX.Building, RDFS.label, Literal("Gebäude", lang="de")))
    g.add((EX.Building, RDFS.comment, Literal("A permanent structure", lang="en")))
    # Note: German comment missing

    # Class with English only
    g.add((EX.Person, RDF.type, OWL.Class))
    g.add((EX.Person, RDFS.label, Literal("Person", lang="en")))

    return g


@pytest.fixture
def deprecated_ontology() -> Graph:
    """Create an ontology with deprecated entities."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("rdfs", RDFS)
    g.bind("owl", OWL)

    # Active class
    g.add((EX.Building, RDF.type, OWL.Class))
    g.add((EX.Building, RDFS.label, Literal("Building", lang="en")))

    # Deprecated class
    g.add((EX.OldBuilding, RDF.type, OWL.Class))
    g.add((EX.OldBuilding, RDFS.label, Literal("Old Building", lang="en")))
    g.add((EX.OldBuilding, OWL.deprecated, Literal(True)))

    return g


@pytest.fixture
def simple_ontology_file(temp_dir: Path, simple_ontology: Graph) -> Path:
    """Save simple ontology to file."""
    path = temp_dir / "ontology.ttl"
    simple_ontology.serialize(destination=path, format="turtle")
    return path


@pytest.fixture
def multilingual_ontology_file(temp_dir: Path, multilingual_ontology: Graph) -> Path:
    """Save multilingual ontology to file."""
    path = temp_dir / "multilingual.ttl"
    multilingual_ontology.serialize(destination=path, format="turtle")
    return path


class TestTranslationEntry:
    """Tests for TranslationEntry dataclass."""

    def test_create_entry(self):
        """Test creating a translation entry."""
        entry = TranslationEntry(
            property="rdfs:label",
            source_text="Building",
            translation="Gebäude",
            status=TranslationStatus.TRANSLATED,
        )
        assert entry.property == "rdfs:label"
        assert entry.source_text == "Building"
        assert entry.translation == "Gebäude"
        assert entry.status == TranslationStatus.TRANSLATED

    def test_to_dict(self):
        """Test serialisation to dict."""
        entry = TranslationEntry(
            property="rdfs:label",
            source_text="Building",
            translation="Gebäude",
            status=TranslationStatus.TRANSLATED,
            notes="Confirmed by native speaker",
        )
        d = entry.to_dict()
        assert d["property"] == "rdfs:label"
        assert d["source"] == "Building"
        assert d["translation"] == "Gebäude"
        assert d["status"] == "translated"
        assert d["notes"] == "Confirmed by native speaker"

    def test_from_dict(self):
        """Test creation from dict."""
        d = {
            "property": "rdfs:comment",
            "source": "A structure",
            "translation": "Ein Bauwerk",
            "status": "needs_review",
        }
        entry = TranslationEntry.from_dict(d)
        assert entry.property == "rdfs:comment"
        assert entry.source_text == "A structure"
        assert entry.translation == "Ein Bauwerk"
        assert entry.status == TranslationStatus.NEEDS_REVIEW


class TestTranslationFile:
    """Tests for TranslationFile serialisation."""

    def test_to_yaml(self):
        """Test YAML serialisation."""
        metadata = TranslationFileMetadata(
            source_file="test.ttl",
            source_language="en",
            target_language="de",
            generated=datetime(2025, 1, 15, 10, 30),
            properties=["rdfs:label"],
        )
        entities = [
            EntityTranslations(
                uri="http://example.org/Building",
                entity_type="owl:Class",
                labels=[
                    TranslationEntry(
                        property="rdfs:label",
                        source_text="Building",
                        translation="Gebäude",
                        status=TranslationStatus.TRANSLATED,
                    )
                ],
            )
        ]
        tf = TranslationFile(metadata=metadata, entities=entities)

        yaml_str = tf.to_yaml()
        assert "target_language: de" in yaml_str
        assert "Building" in yaml_str
        assert "Gebäude" in yaml_str

    def test_from_yaml(self, temp_dir: Path):
        """Test loading from YAML file."""
        yaml_content = dedent('''
            metadata:
              source_file: test.ttl
              source_language: en
              target_language: de
              generated: 2025-01-15T10:30:00
              properties:
                - rdfs:label
            entities:
              - uri: "http://example.org/Building"
                type: owl:Class
                labels:
                  - property: rdfs:label
                    source: Building
                    translation: Gebäude
                    status: translated
            summary:
              total_entities: 1
              total_strings: 1
              by_status:
                translated: 1
              coverage: "100%"
        ''')

        path = temp_dir / "translations.yml"
        path.write_text(yaml_content)

        tf = TranslationFile.from_yaml(path)
        assert tf.metadata.target_language == "de"
        assert len(tf.entities) == 1
        assert tf.entities[0].labels[0].translation == "Gebäude"


class TestStringExtractor:
    """Tests for string extraction."""

    def test_extract_basic(self, simple_ontology: Graph, temp_dir: Path):
        """Test basic extraction."""
        config = ExtractConfig(
            source_language="en",
            target_language="de",
            properties=[
                "http://www.w3.org/2000/01/rdf-schema#label",
                "http://www.w3.org/2000/01/rdf-schema#comment",
            ],
        )
        extractor = StringExtractor(config)
        result = extractor.extract(simple_ontology, "test.ttl", "de")

        assert result.success
        assert result.total_entities == 3  # Building, Person, hasLocation
        assert result.total_strings == 4  # 2 labels + 1 comment + 1 label

    def test_extract_with_custom_properties(self, temp_dir: Path):
        """Test extraction with custom properties."""
        g = Graph()
        g.bind("ex", EX)
        g.bind("skos", SKOS)
        g.add((EX.Concept, RDF.type, OWL.Class))
        g.add((EX.Concept, SKOS.prefLabel, Literal("Concept", lang="en")))
        g.add((EX.Concept, SKOS.definition, Literal("A general notion", lang="en")))

        config = ExtractConfig(
            source_language="en",
            target_language="de",
            properties=[
                "http://www.w3.org/2004/02/skos/core#prefLabel",
                "http://www.w3.org/2004/02/skos/core#definition",
            ],
        )
        extractor = StringExtractor(config)
        result = extractor.extract(g, "test.ttl", "de")

        assert result.success
        assert result.total_strings == 2

    def test_extract_missing_only(self, multilingual_ontology: Graph):
        """Test extraction of missing translations only."""
        config = ExtractConfig(
            source_language="en",
            target_language="de",
            missing_only=True,
        )
        extractor = StringExtractor(config)
        result = extractor.extract(multilingual_ontology, "test.ttl", "de")

        assert result.success
        # Building label exists in German, so only comment + Person label
        assert result.total_strings == 2  # Building comment + Person label

    def test_extract_excludes_deprecated(self, deprecated_ontology: Graph):
        """Test that deprecated entities are excluded by default."""
        config = ExtractConfig(
            source_language="en",
            target_language="de",
            include_deprecated=False,
        )
        extractor = StringExtractor(config)
        result = extractor.extract(deprecated_ontology, "test.ttl", "de")

        assert result.success
        assert result.total_entities == 1  # Only Building
        assert result.skipped_entities == 1  # OldBuilding skipped

    def test_extract_includes_deprecated(self, deprecated_ontology: Graph):
        """Test including deprecated entities."""
        config = ExtractConfig(
            source_language="en",
            target_language="de",
            include_deprecated=True,
        )
        extractor = StringExtractor(config)
        result = extractor.extract(deprecated_ontology, "test.ttl", "de")

        assert result.success
        assert result.total_entities == 2  # Both classes


class TestTranslationMerger:
    """Tests for translation merging."""

    def test_merge_basic(self, simple_ontology: Graph):
        """Test basic merge."""
        # Create translation file
        metadata = TranslationFileMetadata(
            source_file="test.ttl",
            source_language="en",
            target_language="de",
            generated=datetime.now(),
            properties=["rdfs:label"],
        )
        entities = [
            EntityTranslations(
                uri=str(EX.Building),
                entity_type="owl:Class",
                labels=[
                    TranslationEntry(
                        property="rdfs:label",
                        source_text="Building",
                        translation="Gebäude",
                        status=TranslationStatus.TRANSLATED,
                    )
                ],
            )
        ]
        tf = TranslationFile(metadata=metadata, entities=entities)

        # Merge
        merger = TranslationMerger()
        result = merger.merge(simple_ontology, tf)

        assert result.success
        assert result.stats.added == 1

        # Check translation was added
        german_labels = list(result.merged_graph.objects(EX.Building, RDFS.label))
        german = [l for l in german_labels if l.language == "de"]
        assert len(german) == 1
        assert str(german[0]) == "Gebäude"

    def test_merge_with_status_filtering(self, simple_ontology: Graph):
        """Test merge respects status threshold."""
        metadata = TranslationFileMetadata(
            source_file="test.ttl",
            source_language="en",
            target_language="de",
            generated=datetime.now(),
            properties=["rdfs:label"],
        )
        entities = [
            EntityTranslations(
                uri=str(EX.Building),
                entity_type="owl:Class",
                labels=[
                    TranslationEntry(
                        property="rdfs:label",
                        source_text="Building",
                        translation="Gebäude",
                        status=TranslationStatus.PENDING,  # Below threshold
                    )
                ],
            )
        ]
        tf = TranslationFile(metadata=metadata, entities=entities)

        config = MergeConfig(min_status=TranslationStatus.TRANSLATED)
        merger = TranslationMerger(config)
        result = merger.merge(simple_ontology, tf)

        assert result.success
        assert result.stats.skipped_status == 1
        assert result.stats.added == 0

    def test_merge_preserve_existing(self, multilingual_ontology: Graph):
        """Test preserve mode doesn't overwrite existing."""
        metadata = TranslationFileMetadata(
            source_file="test.ttl",
            source_language="en",
            target_language="de",
            generated=datetime.now(),
            properties=["rdfs:label"],
        )
        entities = [
            EntityTranslations(
                uri=str(EX.Building),
                entity_type="owl:Class",
                labels=[
                    TranslationEntry(
                        property="rdfs:label",
                        source_text="Building",
                        translation="NEUES Gebäude",  # Different from existing
                        status=TranslationStatus.TRANSLATED,
                    )
                ],
            )
        ]
        tf = TranslationFile(metadata=metadata, entities=entities)

        config = MergeConfig(existing=ExistingStrategy.PRESERVE)
        merger = TranslationMerger(config)
        result = merger.merge(multilingual_ontology, tf)

        assert result.success
        assert result.stats.skipped_existing == 1

        # Check original was preserved
        german_labels = [
            l for l in result.merged_graph.objects(EX.Building, RDFS.label)
            if l.language == "de"
        ]
        assert len(german_labels) == 1
        assert str(german_labels[0]) == "Gebäude"  # Original, not new

    def test_merge_overwrite_existing(self, multilingual_ontology: Graph):
        """Test overwrite mode replaces existing."""
        metadata = TranslationFileMetadata(
            source_file="test.ttl",
            source_language="en",
            target_language="de",
            generated=datetime.now(),
            properties=["rdfs:label"],
        )
        entities = [
            EntityTranslations(
                uri=str(EX.Building),
                entity_type="owl:Class",
                labels=[
                    TranslationEntry(
                        property="rdfs:label",
                        source_text="Building",
                        translation="Bauwerk",  # Different
                        status=TranslationStatus.TRANSLATED,
                    )
                ],
            )
        ]
        tf = TranslationFile(metadata=metadata, entities=entities)

        config = MergeConfig(existing=ExistingStrategy.OVERWRITE)
        merger = TranslationMerger(config)
        result = merger.merge(multilingual_ontology, tf)

        assert result.success
        assert result.stats.updated == 1

        # Check translation was updated
        german_labels = [
            l for l in result.merged_graph.objects(EX.Building, RDFS.label)
            if l.language == "de"
        ]
        assert len(german_labels) == 1
        assert str(german_labels[0]) == "Bauwerk"


class TestCoverageReporter:
    """Tests for coverage reporting."""

    def test_report_basic(self, multilingual_ontology: Graph):
        """Test basic coverage report."""
        reporter = CoverageReporter(source_language="en")
        report = reporter.report(multilingual_ontology, ["en", "de"], "test.ttl")

        assert report.total_entities == 2  # Building, Person
        assert "en" in report.languages
        assert "de" in report.languages

        en_coverage = report.languages["en"]
        assert en_coverage.is_source
        assert en_coverage.coverage == 100.0

        de_coverage = report.languages["de"]
        assert not de_coverage.is_source
        # Building label translated, Person label missing, comment missing
        assert de_coverage.coverage < 100.0

    def test_report_missing_entities(self, multilingual_ontology: Graph):
        """Test missing entity tracking."""
        reporter = CoverageReporter(source_language="en")
        report = reporter.report(multilingual_ontology, ["en", "de"], "test.ttl")

        de_coverage = report.languages["de"]
        # Person should be in missing list
        assert len(de_coverage.missing_entities) > 0


class TestFormatters:
    """Tests for output formatters."""

    def test_text_formatter_extraction(self, simple_ontology: Graph):
        """Test text formatter for extraction result."""
        config = ExtractConfig(source_language="en", target_language="de")
        extractor = StringExtractor(config)
        result = extractor.extract(simple_ontology, "test.ttl", "de")

        formatter = TextFormatter(use_colour=False)
        output = formatter.format_extraction_result(result)

        assert "Extraction complete" in output
        assert "Entities:" in output
        assert "Strings:" in output

    def test_text_formatter_coverage(self, multilingual_ontology: Graph):
        """Test text formatter for coverage report."""
        reporter = CoverageReporter(source_language="en")
        report = reporter.report(multilingual_ontology, ["en", "de"], "test.ttl")

        formatter = TextFormatter(use_colour=False)
        output = formatter.format_coverage_report(report)

        assert "Translation Coverage Report" in output
        assert "en (base)" in output
        assert "de" in output

    def test_markdown_formatter_coverage(self, multilingual_ontology: Graph):
        """Test markdown formatter for coverage report."""
        reporter = CoverageReporter(source_language="en")
        report = reporter.report(multilingual_ontology, ["en", "de"], "test.ttl")

        formatter = MarkdownFormatter()
        output = formatter.format_coverage_report(report)

        assert "# Translation Coverage Report" in output
        assert "| Language |" in output
        assert "**en**" in output


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_extract_strings(self, simple_ontology_file: Path, temp_dir: Path):
        """Test extract_strings function."""
        output = temp_dir / "de.yml"
        result = extract_strings(
            source=simple_ontology_file,
            target_language="de",
            output=output,
        )

        assert result.success
        assert output.exists()

        # Load and verify
        tf = TranslationFile.from_yaml(output)
        assert tf.metadata.target_language == "de"

    def test_merge_translations(self, simple_ontology_file: Path, temp_dir: Path):
        """Test merge_translations function."""
        # First extract
        trans_file = temp_dir / "de.yml"
        extract_result = extract_strings(
            source=simple_ontology_file,
            target_language="de",
            output=trans_file,
        )
        assert extract_result.success

        # Fill in a translation
        tf = TranslationFile.from_yaml(trans_file)
        for entity in tf.entities:
            for label in entity.labels:
                if label.source_text == "Building":
                    label.translation = "Gebäude"
                    label.status = TranslationStatus.TRANSLATED
        tf.save(trans_file)

        # Merge
        output = temp_dir / "merged.ttl"
        merge_result = merge_translations(
            source=simple_ontology_file,
            translation_files=[trans_file],
            output=output,
        )

        assert merge_result.success
        assert merge_result.stats.added >= 1
        assert output.exists()

    def test_generate_coverage_report(self, multilingual_ontology_file: Path):
        """Test generate_coverage_report function."""
        report = generate_coverage_report(
            source=multilingual_ontology_file,
            languages=["en", "de", "fr"],
        )

        assert report.total_entities == 2
        assert "en" in report.languages
        assert "de" in report.languages
        assert "fr" in report.languages


class TestRoundTrip:
    """Test extract → translate → merge roundtrip."""

    def test_roundtrip(self, simple_ontology_file: Path, temp_dir: Path):
        """Test complete roundtrip workflow."""
        # 1. Extract
        trans_file = temp_dir / "de.yml"
        extract_result = extract_strings(
            source=simple_ontology_file,
            target_language="de",
            output=trans_file,
        )
        assert extract_result.success

        # 2. Simulate translation
        tf = TranslationFile.from_yaml(trans_file)
        translations = {
            "Building": "Gebäude",
            "Person": "Person",  # Same in German
            "has location": "hat Standort",
            "A permanent structure": "Eine dauerhafte Struktur",
        }
        for entity in tf.entities:
            for label in entity.labels:
                if label.source_text in translations:
                    label.translation = translations[label.source_text]
                    label.status = TranslationStatus.TRANSLATED
        tf.save(trans_file)

        # 3. Merge back
        output = temp_dir / "localised.ttl"
        merge_result = merge_translations(
            source=simple_ontology_file,
            translation_files=[trans_file],
            output=output,
        )
        assert merge_result.success

        # 4. Verify result
        g = Graph()
        g.parse(output)

        # Check German labels exist
        building_labels = list(g.objects(EX.Building, RDFS.label))
        german_labels = [l for l in building_labels if l.language == "de"]
        assert len(german_labels) == 1
        assert str(german_labels[0]) == "Gebäude"


class TestConfigYAML:
    """Tests for configuration file handling."""

    def test_create_default_config(self):
        """Test default config generation."""
        config_str = create_default_config()
        assert "localise:" in config_str
        assert "properties:" in config_str
        assert "languages:" in config_str

    def test_load_config(self, temp_dir: Path):
        """Test loading config from YAML."""
        config_content = dedent('''
            localise:
              properties:
                - rdfs:label
                - skos:prefLabel
              languages:
                source: en
                targets:
                  - de
                  - fr
              output:
                directory: translations/
                naming: "{language}.yml"
              extract:
                include_deprecated: false
              merge:
                existing: preserve
                min_status: translated
        ''')

        config_path = temp_dir / "localise.yml"
        config_path.write_text(config_content)

        config = load_localise_config(config_path)
        assert config.source_language == "en"
        assert "de" in config.target_languages
        assert config.merge.existing == ExistingStrategy.PRESERVE


class TestMultipleLanguages:
    """Tests for handling multiple languages."""

    def test_extract_multiple_languages(
        self, simple_ontology_file: Path, temp_dir: Path
    ):
        """Test extracting for multiple languages."""
        languages = ["de", "fr", "es"]
        files: list[Path] = []

        for lang in languages:
            output = temp_dir / f"{lang}.yml"
            result = extract_strings(
                source=simple_ontology_file,
                target_language=lang,
                output=output,
            )
            assert result.success
            files.append(output)

        # Verify all files created
        for f in files:
            assert f.exists()
            tf = TranslationFile.from_yaml(f)
            assert tf.metadata.target_language in languages

    def test_merge_multiple_files(self, simple_ontology_file: Path, temp_dir: Path):
        """Test merging multiple translation files."""
        # Create German and French translations
        languages_data = [
            ("de", {"Building": "Gebäude", "Person": "Person"}),
            ("fr", {"Building": "Bâtiment", "Person": "Personne"}),
        ]

        trans_files: list[Path] = []
        for lang, translations in languages_data:
            # Extract
            trans_file = temp_dir / f"{lang}.yml"
            extract_strings(
                source=simple_ontology_file,
                target_language=lang,
                output=trans_file,
            )

            # Fill translations
            tf = TranslationFile.from_yaml(trans_file)
            for entity in tf.entities:
                for label in entity.labels:
                    if label.source_text in translations:
                        label.translation = translations[label.source_text]
                        label.status = TranslationStatus.TRANSLATED
            tf.save(trans_file)
            trans_files.append(trans_file)

        # Merge all
        output = temp_dir / "multilingual.ttl"
        result = merge_translations(
            source=simple_ontology_file,
            translation_files=trans_files,
            output=output,
        )

        assert result.success

        # Verify both languages present
        g = Graph()
        g.parse(output)

        building_labels = list(g.objects(EX.Building, RDFS.label))
        languages_found = {l.language for l in building_labels if hasattr(l, "language")}
        assert "de" in languages_found
        assert "fr" in languages_found
