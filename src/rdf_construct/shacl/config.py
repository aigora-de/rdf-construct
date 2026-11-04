"""Configuration handling for SHACL shape generation."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class StrictnessLevel(Enum):
    """Strictness levels for SHACL generation.

    Controls how many OWL patterns are converted to SHACL constraints.

    Attributes:
        MINIMAL: Only basic type constraints (sh:class, sh:datatype).
        STANDARD: Adds cardinality, functional properties, and common patterns.
        STRICT: Maximum constraints including sh:closed, all cardinalities.
    """

    MINIMAL = "minimal"
    STANDARD = "standard"
    STRICT = "strict"


class Severity(Enum):
    """SHACL constraint severity levels.

    Maps to sh:Violation, sh:Warning, sh:Info.
    """

    VIOLATION = "violation"
    WARNING = "warning"
    INFO = "info"


# Keys earlier releases accepted and nothing ever read, with why each is gone (#223)
REMOVED_KEYS: dict[str, str] = {
    "generate_property_shapes": (
        "nothing ever read it, and no top-level sh:PropertyShape was ever generated; "
        "the design is #94's"
    ),
}


@dataclass
class ShaclConfig:
    """Configuration for SHACL shape generation.

    Controls which OWL patterns are converted and how shapes are structured.

    Attributes:
        level: Strictness level for conversion.
        default_severity: ``sh:severity`` for every node and property shape; None (the
            default) emits none, which SHACL reads as ``sh:Violation``.
        closed: Generate closed shapes (no extra properties allowed), at any level.
        shape_namespace: The full namespace IRI for generated shapes, ending in ``#``, ``/``
            or ``:``; None (the default) derives it from the ontology IRI, or from the
            namespace holding the most declared classes.
        target_classes: Optional list of classes to generate shapes for.
        exclude_classes: Classes to skip during generation.
        include_labels: Include rdfs:label as sh:name.
        include_descriptions: Include rdfs:comment as sh:description.
        inherit_constraints: Inherit property constraints from superclasses.
        ignored_properties: Properties to ignore in closed shapes.
    """

    level: StrictnessLevel = StrictnessLevel.STANDARD
    default_severity: Severity | None = None
    closed: bool = False
    shape_namespace: str | None = None
    target_classes: list[str] = field(default_factory=list)
    exclude_classes: list[str] = field(default_factory=list)
    include_labels: bool = True
    include_descriptions: bool = True
    inherit_constraints: bool = True
    ignored_properties: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> "ShaclConfig":
        """Load configuration from YAML file.

        Args:
            path: Path to YAML configuration file.

        Returns:
            Populated ShaclConfig instance.

        Raises:
            FileNotFoundError: If configuration file doesn't exist.
            ValueError: If configuration is invalid.
        """
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ShaclConfig":
        """Create configuration from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            Populated ShaclConfig instance.

        Raises:
            ValueError: If a value is invalid or a key has been removed.
        """
        for key in data:
            if str(key) in REMOVED_KEYS:
                raise ValueError(
                    f"'{key}' was removed in rdf-construct 0.7.0: {REMOVED_KEYS[str(key)]}. "
                    "Delete it from the config"
                )

        # Handle enum conversions
        level_str = data.get("level", "standard").lower()
        try:
            level = StrictnessLevel(level_str)
        except ValueError:
            valid = ", ".join(s.value for s in StrictnessLevel)
            raise ValueError(f"Invalid strictness level '{level_str}'. Valid: {valid}")

        # Absent or null: no sh:severity is written (#223)
        severity: Severity | None = None
        if data.get("default_severity") is not None:
            severity_str = str(data["default_severity"]).lower()
            try:
                severity = Severity(severity_str)
            except ValueError:
                valid = ", ".join(s.value for s in Severity)
                raise ValueError(f"Invalid severity '{severity_str}'. Valid: {valid}")

        return cls(
            level=level,
            default_severity=severity,
            closed=data.get("closed", False),
            shape_namespace=data.get("shape_namespace"),
            target_classes=data.get("target_classes", []),
            exclude_classes=data.get("exclude_classes", []),
            include_labels=data.get("include_labels", True),
            include_descriptions=data.get("include_descriptions", True),
            inherit_constraints=data.get("inherit_constraints", True),
            ignored_properties=data.get("ignored_properties", []),
        )


def load_shacl_config(path: Path | None) -> ShaclConfig:
    """Load SHACL configuration from file or return defaults.

    Args:
        path: Optional path to configuration file.

    Returns:
        ShaclConfig instance (defaults if no path provided).
    """
    if path is None:
        return ShaclConfig()

    return ShaclConfig.from_yaml(path)
