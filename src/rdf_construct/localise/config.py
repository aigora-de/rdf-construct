"""Configuration dataclasses for the localise command.

Defines configuration structures for:
- Translation entries and files
- Extraction settings
- Merge settings
- Coverage reporting
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml
from rdflib import URIRef


class TranslationStatus(str, Enum):
    """Status of a translation entry."""

    PENDING = "pending"
    TRANSLATED = "translated"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"

    def __str__(self) -> str:
        return self.value


@dataclass
class TranslationEntry:
    """A single translation entry for a property.

    Attributes:
        property: URI of the property (e.g., rdfs:label).
        source_text: Original text in source language.
        translation: Translated text (empty if pending).
        status: Translation status.
        notes: Optional notes for translators.
    """

    property: str
    source_text: str
    translation: str = ""
    status: TranslationStatus = TranslationStatus.PENDING
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialisation."""
        result: dict[str, Any] = {
            "property": self.property,
            "source": self.source_text,
            "translation": self.translation,
            "status": str(self.status),
        }
        if self.notes:
            result["notes"] = self.notes
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranslationEntry":
        """Create from dictionary."""
        return cls(
            property=data["property"],
            source_text=data["source"],
            translation=data.get("translation", ""),
            status=TranslationStatus(data.get("status", "pending")),
            notes=data.get("notes"),
        )


@dataclass
class EntityTranslations:
    """Translation entries for a single entity.

    Attributes:
        uri: URI of the entity.
        entity_type: Type of entity (owl:Class, owl:ObjectProperty, etc.).
        labels: List of translation entries for this entity.
    """

    uri: str
    entity_type: str
    labels: list[TranslationEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialisation."""
        return {
            "uri": self.uri,
            "type": self.entity_type,
            "labels": [entry.to_dict() for entry in self.labels],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityTranslations":
        """Create from dictionary."""
        return cls(
            uri=data["uri"],
            entity_type=data.get("type", "unknown"),
            labels=[TranslationEntry.from_dict(entry) for entry in data.get("labels", [])],
        )


@dataclass
class TranslationFileMetadata:
    """Metadata for a translation file.

    Attributes:
        source_file: Original ontology file path.
        source_language: Source language code (e.g., "en").
        target_language: Target language code (e.g., "de").
        generated: Timestamp when file was generated.
        properties: List of properties extracted.
        tool_version: Version of rdf-construct that generated this file.
    """

    source_file: str
    source_language: str
    target_language: str
    generated: datetime
    properties: list[str] = field(default_factory=list)
    tool_version: str = "rdf-construct"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialisation."""
        return {
            "source_file": self.source_file,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "generated": self.generated.isoformat(),
            "tool": self.tool_version,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranslationFileMetadata":
        """Create from dictionary."""
        generated = data.get("generated")
        if isinstance(generated, str):
            generated = datetime.fromisoformat(generated)
        elif generated is None:
            generated = datetime.now()

        return cls(
            source_file=data.get("source_file", ""),
            source_language=data.get("source_language", "en"),
            target_language=data.get("target_language", ""),
            generated=generated,
            properties=data.get("properties", []),
            tool_version=data.get("tool", "rdf-construct"),
        )


@dataclass
class TranslationSummary:
    """Summary statistics for a translation file.

    Attributes:
        total_entities: Total number of entities.
        total_strings: Total number of translatable strings.
        by_status: Count of strings by status.
    """

    total_entities: int = 0
    total_strings: int = 0
    by_status: dict[str, int] = field(default_factory=dict)

    @property
    def translated(self) -> int:
        """Number of translated strings."""
        return self.by_status.get("translated", 0) + self.by_status.get("approved", 0)

    @property
    def coverage(self) -> float:
        """Translation coverage as percentage."""
        if self.total_strings == 0:
            return 0.0
        return (self.translated / self.total_strings) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialisation."""
        return {
            "total_entities": self.total_entities,
            "total_strings": self.total_strings,
            "by_status": self.by_status,
            "coverage": f"{self.coverage:.1f}%",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranslationSummary":
        """Create from dictionary."""
        return cls(
            total_entities=data.get("total_entities", 0),
            total_strings=data.get("total_strings", 0),
            by_status=data.get("by_status", {}),
        )


@dataclass
class TranslationFile:
    """A complete translation file.

    Contains metadata, entity translations, and summary statistics.

    Attributes:
        metadata: File metadata.
        entities: List of entity translations.
        summary: Summary statistics.
    """

    metadata: TranslationFileMetadata
    entities: list[EntityTranslations] = field(default_factory=list)
    summary: TranslationSummary | None = None

    def calculate_summary(self) -> TranslationSummary:
        """Calculate summary statistics from entities."""
        total_strings = 0
        by_status: dict[str, int] = {}

        for entity in self.entities:
            for label in entity.labels:
                total_strings += 1
                status = str(label.status)
                by_status[status] = by_status.get(status, 0) + 1

        return TranslationSummary(
            total_entities=len(self.entities),
            total_strings=total_strings,
            by_status=by_status,
        )

    def to_yaml(self) -> str:
        """Serialise to YAML string."""
        # Calculate summary before serialisation
        self.summary = self.calculate_summary()

        header = f"""# =============================================================================
# Translation File
# =============================================================================
# Source: {self.metadata.source_file}
# Source language: {self.metadata.source_language}
# Target language: {self.metadata.target_language}
# Generated: {self.metadata.generated.isoformat()}
#
# Instructions:
# 1. Fill in the 'translation' field for each entry
# 2. Set 'status' to 'translated' when complete
# 3. Use 'needs_review' if uncertain about translation
# 4. Leave 'status' as 'pending' for incomplete entries
# =============================================================================

"""

        data = {
            "metadata": self.metadata.to_dict(),
            "entities": [entity.to_dict() for entity in self.entities],
            "summary": self.summary.to_dict(),
        }

        return header + yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, path: Path) -> "TranslationFile":
        """Load from YAML file.

        Args:
            path: Path to YAML file.

        Returns:
            TranslationFile instance.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If file format is invalid.
        """
        if not path.exists():
            raise FileNotFoundError(f"Translation file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid translation file format: {path}")

        metadata = TranslationFileMetadata.from_dict(data.get("metadata", {}))
        entities = [
            EntityTranslations.from_dict(entity) for entity in data.get("entities", [])
        ]
        summary = None
        if "summary" in data:
            summary = TranslationSummary.from_dict(data["summary"])

        return cls(metadata=metadata, entities=entities, summary=summary)

    def save(self, path: Path) -> None:
        """Save to YAML file.

        Args:
            path: Output file path.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_yaml(), encoding="utf-8")


class ExistingStrategy(str, Enum):
    """How to handle existing translations in ontology."""

    PRESERVE = "preserve"
    OVERWRITE = "overwrite"


@dataclass
class ExtractConfig:
    """Configuration for extraction operation.

    Attributes:
        source_language: Source language code (default: "en").
        target_language: Target language code.
        properties: List of properties to extract.
        include_deprecated: Whether to include deprecated entities.
        include_unlabelled: Whether to include entities without source labels.
        missing_only: Only extract strings missing in target language.
    """

    source_language: str = "en"
    target_language: str = ""
    properties: list[str] = field(
        default_factory=lambda: [
            "http://www.w3.org/2000/01/rdf-schema#label",
            "http://www.w3.org/2000/01/rdf-schema#comment",
        ]
    )
    include_deprecated: bool = False
    include_unlabelled: bool = False
    missing_only: bool = False


@dataclass
class MergeConfig:
    """Configuration for merge operation.

    Attributes:
        min_status: Minimum status required to include translation.
        existing: How to handle existing translations.
    """

    min_status: TranslationStatus = TranslationStatus.TRANSLATED
    existing: ExistingStrategy = ExistingStrategy.PRESERVE


@dataclass
class LocaliseConfig:
    """Complete configuration for localise operations.

    Attributes:
        properties: Properties to extract/check.
        source_language: Base language for translations.
        target_languages: List of target language codes.
        extract: Extraction settings.
        merge: Merge settings.
        output_dir: Output directory for translation files.
        output_naming: Naming pattern for output files.
    """

    properties: list[str] = field(
        default_factory=lambda: [
            "http://www.w3.org/2000/01/rdf-schema#label",
            "http://www.w3.org/2000/01/rdf-schema#comment",
            "http://www.w3.org/2004/02/skos/core#prefLabel",
            "http://www.w3.org/2004/02/skos/core#definition",
        ]
    )
    source_language: str = "en"
    target_languages: list[str] = field(default_factory=list)
    extract: ExtractConfig = field(default_factory=ExtractConfig)
    merge: MergeConfig = field(default_factory=MergeConfig)
    output_dir: Path = field(default_factory=lambda: Path("translations"))
    output_naming: str = "{language}.yml"

    @classmethod
    def from_yaml(cls, path: Path) -> "LocaliseConfig":
        """Load from YAML configuration file.

        Args:
            path: Path to configuration file.

        Returns:
            LocaliseConfig instance.
        """
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data.get("localise", data))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocaliseConfig":
        """Create from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            LocaliseConfig instance.
        """
        # Parse languages section
        languages = data.get("languages", {})
        source_language = languages.get("source", data.get("source_language", "en"))
        target_languages = languages.get("targets", data.get("target_languages", []))

        # Parse extract settings
        extract_data = data.get("extract", {})
        extract = ExtractConfig(
            source_language=source_language,
            target_language=extract_data.get("target_language", ""),
            properties=data.get("properties", ExtractConfig().properties),
            include_deprecated=extract_data.get("include_deprecated", False),
            include_unlabelled=extract_data.get("include_unlabelled", False),
            missing_only=extract_data.get("missing_only", False),
        )

        # Parse merge settings
        merge_data = data.get("merge", {})
        min_status_str = merge_data.get("min_status", "translated")
        existing_str = merge_data.get("existing", "preserve")
        merge = MergeConfig(
            min_status=TranslationStatus(min_status_str),
            existing=ExistingStrategy(existing_str),
        )

        # Parse output settings
        output_data = data.get("output", {})
        output_dir = Path(output_data.get("directory", "translations"))
        output_naming = output_data.get("naming", "{language}.yml")

        return cls(
            properties=data.get("properties", cls().properties),
            source_language=source_language,
            target_languages=target_languages,
            extract=extract,
            merge=merge,
            output_dir=output_dir,
            output_naming=output_naming,
        )


def create_default_config() -> str:
    """Generate default localise configuration as YAML string.

    Returns:
        YAML configuration template.
    """
    return '''# rdf-construct localise configuration
# See LOCALISE_GUIDE.md for full documentation

localise:
  # Properties to extract/check (in display order)
  properties:
    - rdfs:label
    - skos:prefLabel
    - rdfs:comment
    - skos:definition
    - skos:altLabel
    - skos:example

  # Language configuration
  languages:
    source: en  # Base language for translations
    targets:
      - de
      - fr
      - es

  # Output settings
  output:
    directory: translations/
    naming: "{language}.yml"  # e.g., de.yml, fr.yml

  # Extraction options
  extract:
    # Include entities without source language labels?
    include_unlabelled: false
    # Include deprecated entities?
    include_deprecated: false

  # Merge options
  merge:
    # What to do with existing translations?
    existing: preserve  # preserve | overwrite
    # Minimum status to include in merge
    min_status: translated  # pending | translated | needs_review | approved
'''


def load_localise_config(path: Path) -> LocaliseConfig:
    """Load localise configuration from a YAML file.

    Args:
        path: Path to configuration file.

    Returns:
        LocaliseConfig instance.
    """
    return LocaliseConfig.from_yaml(path)
