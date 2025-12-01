"""Configuration handling for SHACL shape generation."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from rdflib import URIRef


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


@dataclass
class ShaclConfig:
    """Configuration for SHACL shape generation.

    Controls which OWL patterns are converted and how shapes are structured.

    Attributes:
        level: Strictness level for conversion.
        default_severity: Default severity for generated constraints.
        closed: Generate closed shapes (no extra properties allowed).
        shape_namespace: Namespace suffix for generated shapes.
        target_classes: Optional list of classes to generate shapes for.
        exclude_classes: Classes to skip during generation.
        include_labels: Include rdfs:label as sh:name.
        include_descriptions: Include rdfs:comment as sh:description.
        inherit_constraints: Inherit property constraints from superclasses.
        generate_property_shapes: Generate top-level PropertyShapes.
        ignored_properties: Properties to ignore in closed shapes.
    """

    level: StrictnessLevel = StrictnessLevel.STANDARD
    default_severity: Severity = Severity.VIOLATION
    closed: bool = False
    shape_namespace: str = "shapes#"
    target_classes: list[str] = field(default_factory=list)
    exclude_classes: list[str] = field(default_factory=list)
    include_labels: bool = True
    include_descriptions: bool = True
    inherit_constraints: bool = True
    generate_property_shapes: bool = False
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
        """
        # Handle enum conversions
        level_str = data.get("level", "standard").lower()
        try:
            level = StrictnessLevel(level_str)
        except ValueError:
            valid = ", ".join(s.value for s in StrictnessLevel)
            raise ValueError(f"Invalid strictness level '{level_str}'. Valid: {valid}")

        severity_str = data.get("default_severity", "violation").lower()
        try:
            severity = Severity(severity_str)
        except ValueError:
            valid = ", ".join(s.value for s in Severity)
            raise ValueError(f"Invalid severity '{severity_str}'. Valid: {valid}")

        return cls(
            level=level,
            default_severity=severity,
            closed=data.get("closed", False),
            shape_namespace=data.get("shape_namespace", "shapes#"),
            target_classes=data.get("target_classes", []),
            exclude_classes=data.get("exclude_classes", []),
            include_labels=data.get("include_labels", True),
            include_descriptions=data.get("include_descriptions", True),
            inherit_constraints=data.get("inherit_constraints", True),
            generate_property_shapes=data.get("generate_property_shapes", False),
            ignored_properties=data.get("ignored_properties", []),
        )

    def should_generate_for(self, class_uri: URIRef, graph: "Graph") -> bool:
        """Check if a shape should be generated for this class.

        Args:
            class_uri: The class URI to check.
            graph: The source graph (for CURIE expansion).

        Returns:
            True if shape should be generated.
        """
        class_str = str(class_uri)

        # If explicit targets specified, only generate for those
        if self.target_classes:
            return any(class_str.endswith(t) or t in class_str for t in self.target_classes)

        # Check exclusions
        if self.exclude_classes:
            return not any(
                class_str.endswith(e) or e in class_str for e in self.exclude_classes
            )

        return True


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
