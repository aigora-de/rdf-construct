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

from rdf_construct.core.language_tags import LanguageTagError, check_tag

# A translation file names this many unreadable values before summarising the rest
MAX_PROBLEMS_SHOWN = 10


class TranslationFileError(ValueError):
    """A translation file is valid YAML that holds a value of the wrong type or shape (#408).

    YAML reads ordinary text as other things: an unquoted ``Yes`` is a boolean, ``0123`` is the
    number 83 and an empty field is ``null``. Nothing in such a file is merged, so the message
    names every value that cannot be read, not only the first.

    Args:
        problems: One message per value that cannot be read, each naming where it is.
    """

    def __init__(self, problems: str | list[str]) -> None:
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__(self._format())

    def _format(self) -> str:
        if len(self.problems) == 1:
            return self.problems[0]
        shown = self.problems[:MAX_PROBLEMS_SHOWN]
        lines = [f"{len(self.problems)} values cannot be read:"]
        lines.extend(f"  - {problem}" for problem in shown)
        if len(self.problems) > len(shown):
            lines.append(f"  - and {len(self.problems) - len(shown)} more")
        return "\n".join(lines)


class LocaliseConfigError(ValueError):
    """A localise configuration file holds a value of the wrong type or shape (#408)."""


def _reads_as(value: object, example: str = "Yes") -> str:
    """Say what YAML read a value as, for a message about a value that should be text."""
    if isinstance(value, bool):
        return (
            f"reads as {str(value).lower()}, not text: YAML reads an unquoted yes, no, on, off, "
            f'true or false that way. Quote the text, e.g. "{example}"'
        )
    if isinstance(value, int | float):
        return (
            f"reads as the number {value!r}, not text: YAML reads an unquoted number that way "
            '(0123 as 83, 1.50 as 1.5). Quote the text as written, e.g. "0123"'
        )
    if isinstance(value, datetime):
        return 'reads as a date and time, not text. Quote it, e.g. "2025-01-15T10:30"'
    if isinstance(value, dict):
        return "is a mapping, not text"
    if isinstance(value, list):
        return "is a list, not text"
    if value is None:
        return "is blank"
    return f"reads as a {type(value).__name__}, not text. Quote it"


def _required_text(data: dict[str, Any], key: str) -> str:
    """Return ``data[key]`` as non-blank text, or raise ``TranslationFileError`` naming the key."""
    value = data.get(key)
    if value is None:
        raise TranslationFileError(f"{key} {'is blank' if key in data else 'is missing'}")
    if not isinstance(value, str):
        raise TranslationFileError(f"{key} {_reads_as(value)}")
    if not value.strip():
        raise TranslationFileError(f"{key} is blank")
    return value


def _optional_text(data: dict[str, Any], key: str, default: str) -> str:
    """Return an informational key's text, or ``default`` when it is missing or not text.

    These keys (``source_file``, ``tool``, ``type``) are written for people and never reach the
    ontology, so a wrong type is treated as absent rather than refused.
    """
    value = data.get(key)
    return value if isinstance(value, str) else default


def _list_of_mappings(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Return ``data[key]`` as a list of mappings; a missing or blank key is an empty list."""
    value = data.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise TranslationFileError(f"{key} must be a list, not {_kind(value)}")
    for i, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise TranslationFileError(f"{key} item {i} must be a mapping, not {_kind(item)}")
    return value


def _kind(value: object) -> str:
    """Name a YAML value's kind for a message: "a list", "the number 3", "true"."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int | float):
        return f"the number {value!r}"
    if isinstance(value, str):
        return f"the text {value!r}"
    if isinstance(value, dict):
        return "a mapping"
    if isinstance(value, list):
        return "a list"
    if value is None:
        return "blank"
    return f"a {type(value).__name__}"


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
        """Create from dictionary.

        A blank ``translation`` or ``status`` is read as missing: untranslated, and ``pending``.

        Raises:
            TranslationFileError: If ``property`` or ``source`` is missing or not text, if
                ``translation`` is not text (YAML reads an unquoted ``Yes`` or ``123`` as a
                boolean or a number, and the text typed cannot be recovered from it), or if
                ``status`` is not one of the four statuses (#408).
        """
        prop = _required_text(data, "property")
        source = data.get("source")
        if source is None or not isinstance(source, str):
            detail = "is missing" if "source" not in data else _reads_as(source)
            raise TranslationFileError(f"source {detail}")
        translation = data.get("translation")
        if translation is None:
            translation = ""
        elif not isinstance(translation, str):
            raise TranslationFileError(f"translation {_reads_as(translation)}")

        status_value = data.get("status")
        if status_value is None:
            status = TranslationStatus.PENDING
        elif isinstance(status_value, str) and status_value in {s.value for s in TranslationStatus}:
            status = TranslationStatus(status_value)
        else:
            accepted = ", ".join(s.value for s in TranslationStatus)
            raise TranslationFileError(
                f"status is {_kind(status_value)}; it must be one of {accepted}"
            )

        notes = data.get("notes")
        return cls(
            property=prop,
            source_text=source,
            translation=translation,
            status=status,
            notes=notes if isinstance(notes, str) else None,
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
        """Create from dictionary.

        Raises:
            TranslationFileError: If ``uri`` is missing or not text, if ``labels`` is not a list
                of mappings, or if any label cannot be read. Every unreadable label is named,
                by its position and property (#408).
        """
        uri = _required_text(data, "uri")
        labels: list[TranslationEntry] = []
        problems: list[str] = []
        for i, entry in enumerate(_list_of_mappings(data, "labels"), start=1):
            try:
                labels.append(TranslationEntry.from_dict(entry))
            except TranslationFileError as e:
                prop = entry.get("property")
                where = f"label {i} ({prop})" if isinstance(prop, str) else f"label {i}"
                problems.extend(f"{where}: {problem}" for problem in e.problems)
        if problems:
            raise TranslationFileError(problems)
        return cls(
            uri=uri,
            entity_type=_optional_text(data, "type", "unknown"),
            labels=labels,
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
        """Create from dictionary.

        Raises:
            LanguageTagError: If ``target_language`` is missing, blank, not a string or not a
                well-formed language tag, if ``source_language`` is given and malformed, or if
                the two are the same tag. A file without a usable target would merge its
                translations as untagged literals, which ``localise`` reads as the source
                language (#159).
        """
        # A key written with no value reads as None in YAML: that is a blank tag, not a missing one
        target_value = data.get("target_language")
        if target_value is None and "target_language" in data:
            target_value = ""
        target_language = check_tag(target_value, "target_language")
        source_language = check_tag(data.get("source_language", "en"), "source_language")
        if target_language.lower() == source_language.lower():
            raise LanguageTagError(
                f"target_language {target_language} is the source language; merging it would "
                "replace the source text rather than add a translation",
                target_language,
            )

        # Informational: a value that is not a timestamp is treated as absent (#408)
        generated = data.get("generated")
        if isinstance(generated, str):
            try:
                generated = datetime.fromisoformat(generated)
            except ValueError:
                generated = None
        if not isinstance(generated, datetime):
            generated = datetime.now()

        properties = data.get("properties")
        if not (isinstance(properties, list) and all(isinstance(p, str) for p in properties)):
            properties = []

        return cls(
            source_file=_optional_text(data, "source_file", ""),
            source_language=source_language,
            target_language=target_language,
            generated=generated,
            properties=properties,
            tool_version=_optional_text(data, "tool", "rdf-construct"),
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

        return header + yaml.dump(
            data, default_flow_style=False, allow_unicode=True, sort_keys=False
        )

    @classmethod
    def from_yaml(cls, path: Path) -> "TranslationFile":
        """Load from YAML file.

        Args:
            path: Path to YAML file.

        Returns:
            TranslationFile instance.

        Raises:
            FileNotFoundError: If file doesn't exist.
            TranslationFileError: If the file is empty, is not a mapping, or holds a value of
                the wrong type or shape. Every unreadable entry is named, by its position and
                IRI, so one run finds them all (#408). It is a ``ValueError``.
            LanguageTagError: If ``target_language`` or ``source_language`` cannot be used
                (#159).
        """
        if not path.exists():
            raise FileNotFoundError(f"Translation file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise TranslationFileError(
                "the file holds no YAML, only comments or blank lines, if anything; "
                "it is not a translation file"
            )
        if not isinstance(data, dict):
            raise TranslationFileError(
                f"the file holds {_kind(data)}, not a mapping; it is not a translation file"
            )

        metadata_data = data.get("metadata")
        if metadata_data is None:
            metadata_data = {}
        elif not isinstance(metadata_data, dict):
            raise TranslationFileError(f"metadata must be a mapping, not {_kind(metadata_data)}")
        metadata = TranslationFileMetadata.from_dict(metadata_data)

        entities: list[EntityTranslations] = []
        problems: list[str] = []
        for i, entity in enumerate(_list_of_mappings(data, "entities"), start=1):
            try:
                entities.append(EntityTranslations.from_dict(entity))
            except TranslationFileError as e:
                uri = entity.get("uri")
                where = f"entity {i} ({uri})" if isinstance(uri, str) else f"entity {i}"
                problems.extend(f"{where}, {problem}" for problem in e.problems)
        if problems:
            raise TranslationFileError(problems)

        # Informational, and recalculated on every save: a summary that is not a mapping is absent
        summary = None
        if isinstance(data.get("summary"), dict):
            summary = TranslationSummary.from_dict(data["summary"])

        return cls(metadata=metadata, entities=entities, summary=summary)

    def finished_entries(self) -> dict[str, int]:
        """Count the entries that hold a translator's work, by status (#404).

        An entry is finished when its status is not ``pending``, or when its translation is
        not blank: text typed with the status left at ``pending`` is still work, counted as
        ``pending with text``.

        Returns:
            A count per status, in the order statuses are declared, with ``pending with text``
            last. Statuses with no finished entry are left out; an empty map means none.
        """
        counts: dict[str, int] = {}
        for status in TranslationStatus:
            if status is not TranslationStatus.PENDING:
                counts[status.value] = 0
        counts["pending with text"] = 0
        for entity in self.entities:
            for label in entity.labels:
                if label.status is not TranslationStatus.PENDING:
                    counts[label.status.value] += 1
                elif label.translation.strip():
                    counts["pending with text"] += 1
        return {status: n for status, n in counts.items() if n}

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

        Raises:
            FileNotFoundError: If the file doesn't exist.
            LocaliseConfigError: If the file is empty, is not a mapping, or holds a value of the
                wrong type (#408).
        """
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise LocaliseConfigError("the file is empty")
        if not isinstance(data, dict):
            raise LocaliseConfigError(f"the file holds {_kind(data)}, not a mapping")
        section = data.get("localise", data)
        if not isinstance(section, dict):
            raise LocaliseConfigError(f"localise must be a mapping, not {_kind(section)}")
        return cls.from_dict(section)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocaliseConfig":
        """Create from dictionary.

        A key written with no value is read as missing, and takes its default.

        Args:
            data: Configuration dictionary.

        Returns:
            LocaliseConfig instance.

        Raises:
            LocaliseConfigError: If a value has the wrong type (#408). YAML reads an unquoted
                ``no`` as a boolean and ``'false'`` as text, so a language must be text, a
                switch must be ``true`` or ``false``, and ``properties`` must be a list: a single
                value is refused rather than read as a list of one, since ``rdfs:label,
                skos:prefLabel`` would become one property that matches nothing.
        """
        # Parse languages section
        languages = _config_section(data, "languages")
        source_language = _config_text(
            languages,
            "source",
            "languages.source",
            _config_text(data, "source_language", "source_language", "en"),
        )
        target_languages = _config_text_list(
            languages,
            "targets",
            "languages.targets",
            _config_text_list(data, "target_languages", "target_languages", []),
        )
        properties = _config_text_list(data, "properties", "properties", None)

        # Parse extract settings
        extract_data = _config_section(data, "extract")
        extract = ExtractConfig(
            source_language=source_language,
            target_language=_config_text(
                extract_data, "target_language", "extract.target_language", ""
            ),
            properties=properties if properties is not None else ExtractConfig().properties,
            include_deprecated=_config_bool(extract_data, "include_deprecated", "extract"),
            include_unlabelled=_config_bool(extract_data, "include_unlabelled", "extract"),
            missing_only=_config_bool(extract_data, "missing_only", "extract"),
        )

        # Parse merge settings
        merge_data = _config_section(data, "merge")
        merge = MergeConfig(
            min_status=TranslationStatus(
                _config_choice(merge_data, "min_status", "merge", TranslationStatus, "translated")
            ),
            existing=ExistingStrategy(
                _config_choice(merge_data, "existing", "merge", ExistingStrategy, "preserve")
            ),
        )

        # Parse output settings
        output_data = _config_section(data, "output")
        output_dir = Path(
            _config_text(output_data, "directory", "output.directory", "translations")
        )
        output_naming = _config_text(output_data, "naming", "output.naming", "{language}.yml")

        return cls(
            properties=properties if properties is not None else cls().properties,
            source_language=source_language,
            target_languages=target_languages or [],
            extract=extract,
            merge=merge,
            output_dir=output_dir,
            output_naming=output_naming,
        )


def _config_section(data: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a config section; a missing or blank one is empty."""
    value = data.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise LocaliseConfigError(f"{key} must be a mapping, not {_kind(value)}")
    return value


def _config_text(data: dict[str, Any], key: str, name: str, default: str) -> str:
    """Return a config value that must be text, or ``default`` when it is missing or blank."""
    value = data.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise LocaliseConfigError(f"{name} {_reads_as(value, example='no')}")
    return value


def _config_text_list(
    data: dict[str, Any], key: str, name: str, default: list[str] | None
) -> list[str] | None:
    """Return a config value that must be a list of text, or ``default`` when it is missing."""
    value = data.get(key)
    if value is None:
        return default
    if isinstance(value, str):
        raise LocaliseConfigError(
            f"{name} must be a list, not the single value {value!r}; "
            f"write it as a list: {key}: [{value}]"
        )
    if not isinstance(value, list):
        raise LocaliseConfigError(f"{name} must be a list, not {_kind(value)}")
    for i, item in enumerate(value, start=1):
        if not isinstance(item, str):
            raise LocaliseConfigError(f"{name} item {i} {_reads_as(item, example='no')}")
        if not item.strip():
            raise LocaliseConfigError(f"{name} item {i} is blank")
    return value


def _config_bool(data: dict[str, Any], key: str, section: str) -> bool:
    """Return a config switch, which must be ``true`` or ``false``; missing or blank is false."""
    value = data.get(key)
    if value is None:
        return False
    if not isinstance(value, bool):
        hint = "; write it unquoted" if isinstance(value, str) else ""
        raise LocaliseConfigError(
            f"{section}.{key} must be true or false, not {_kind(value)}{hint}"
        )
    return value


def _config_choice(
    data: dict[str, Any], key: str, section: str, choices: type[Enum], default: str
) -> str:
    """Return a config value that must be one of an enum's values, or ``default``."""
    value = data.get(key)
    if value is None:
        return default
    accepted = [choice.value for choice in choices]
    if not isinstance(value, str) or value not in accepted:
        raise LocaliseConfigError(
            f"{section}.{key} is {_kind(value)}; it must be one of {', '.join(accepted)}"
        )
    return value


def create_default_config() -> str:
    """Generate default localise configuration as YAML string.

    Returns:
        YAML configuration template.
    """
    return """# rdf-construct localise configuration
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
"""


def load_localise_config(path: Path) -> LocaliseConfig:
    """Load localise configuration from a YAML file.

    Args:
        path: Path to configuration file.

    Returns:
        LocaliseConfig instance.
    """
    return LocaliseConfig.from_yaml(path)
