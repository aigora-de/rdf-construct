"""Configuration handling for PlantUML import.

This module provides YAML-based configuration for controlling
how PlantUML diagrams are converted to RDF ontologies.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from rdf_construct.puml2rdf.converter import ConversionConfig


@dataclass
class NamespaceMapping:
    """Maps a PlantUML package to an RDF namespace.

    Attributes:
        package: PlantUML package name or pattern
        namespace_uri: Target namespace URI
        prefix: Preferred prefix for this namespace
    """

    package: str
    namespace_uri: str
    prefix: Optional[str] = None


@dataclass
class DatatypeMapping:
    """Custom datatype mapping.

    Attributes:
        puml_type: PlantUML/UML type name
        rdf_type: Full RDF type URI or CURIE
    """

    puml_type: str
    rdf_type: str


@dataclass
class PumlImportConfig:
    """Complete configuration for PlantUML to RDF import.

    Attributes:
        default_namespace: Default namespace for entities without explicit package
        language: Language tag for labels/comments
        generate_labels: Whether to auto-generate rdfs:label
        camel_to_label: Convert camelCase to readable labels
        generate_inverse_properties: Create inverse for each object property
        namespace_mappings: Package to namespace mappings
        datatype_mappings: Custom datatype conversions
        prefix_order: Preferred prefix ordering for output
        ontology_imports: URIs to add as owl:imports
        annotation_properties: Additional properties to preserve
    """

    default_namespace: str = "http://example.org/ontology#"
    language: str = "en"
    generate_labels: bool = True
    camel_to_label: bool = True
    generate_inverse_properties: bool = False
    namespace_mappings: list[NamespaceMapping] = field(default_factory=list)
    datatype_mappings: list[DatatypeMapping] = field(default_factory=list)
    prefix_order: list[str] = field(default_factory=list)
    ontology_imports: list[str] = field(default_factory=list)
    annotation_properties: list[str] = field(default_factory=list)

    def to_conversion_config(self) -> ConversionConfig:
        """Convert to the simpler ConversionConfig used by converter."""
        return ConversionConfig(
            default_namespace=self.default_namespace,
            language=self.language,
            generate_labels=self.generate_labels,
            camel_to_label=self.camel_to_label,
            generate_inverse_properties=self.generate_inverse_properties,
        )


def load_import_config(path: Path) -> PumlImportConfig:
    """Load PlantUML import configuration from a YAML file.

    Args:
        path: Path to the YAML configuration file

    Returns:
        Parsed configuration object

    Raises:
        FileNotFoundError: If the config file doesn't exist
        ValueError: If the config format is invalid
    """
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Configuration must be a YAML dictionary")

    return _parse_config(data)


def _parse_config(data: dict[str, Any]) -> PumlImportConfig:
    """Parse configuration dictionary into PumlImportConfig.

    Args:
        data: Raw YAML data dictionary

    Returns:
        Parsed configuration object
    """
    config = PumlImportConfig()

    # Simple string/bool fields
    if "default_namespace" in data:
        config.default_namespace = str(data["default_namespace"])
    if "language" in data:
        config.language = str(data["language"])
    if "generate_labels" in data:
        config.generate_labels = bool(data["generate_labels"])
    if "camel_to_label" in data:
        config.camel_to_label = bool(data["camel_to_label"])
    if "generate_inverse_properties" in data:
        config.generate_inverse_properties = bool(data["generate_inverse_properties"])

    # Parse namespace mappings
    if "namespace_mappings" in data:
        mappings = data["namespace_mappings"]
        if isinstance(mappings, list):
            for item in mappings:
                if isinstance(item, dict):
                    config.namespace_mappings.append(
                        NamespaceMapping(
                            package=item.get("package", ""),
                            namespace_uri=item.get("namespace_uri", ""),
                            prefix=item.get("prefix"),
                        )
                    )

    # Parse datatype mappings
    if "datatype_mappings" in data:
        mappings = data["datatype_mappings"]
        if isinstance(mappings, dict):
            for puml_type, rdf_type in mappings.items():
                config.datatype_mappings.append(
                    DatatypeMapping(puml_type=puml_type, rdf_type=str(rdf_type))
                )
        elif isinstance(mappings, list):
            for item in mappings:
                if isinstance(item, dict):
                    config.datatype_mappings.append(
                        DatatypeMapping(
                            puml_type=item.get("puml_type", ""),
                            rdf_type=item.get("rdf_type", ""),
                        )
                    )

    # Parse simple lists
    if "prefix_order" in data:
        config.prefix_order = list(data["prefix_order"])
    if "ontology_imports" in data:
        config.ontology_imports = list(data["ontology_imports"])
    if "annotation_properties" in data:
        config.annotation_properties = list(data["annotation_properties"])

    return config


def create_default_config() -> str:
    """Generate a default configuration YAML string.

    Returns:
        YAML string with default configuration and comments
    """
    return '''# PlantUML Import Configuration
# ================================

# Default namespace for entities without explicit package
default_namespace: "http://example.org/ontology#"

# Language tag for labels and comments
language: "en"

# Automatically generate rdfs:label from entity names
generate_labels: true

# Convert camelCase names to readable labels
# e.g., 'floorArea' -> 'floor area'
camel_to_label: true

# Generate inverse properties for object properties
generate_inverse_properties: false

# Map PlantUML packages to RDF namespaces
namespace_mappings:
  - package: "building"
    namespace_uri: "http://example.org/building#"
    prefix: "bld"
  # - package: "core"
  #   namespace_uri: "http://example.org/core#"
  #   prefix: "core"

# Custom datatype mappings (PlantUML type -> XSD type)
datatype_mappings:
  Money: "xsd:decimal"
  Percentage: "xsd:decimal"
  Identifier: "xsd:string"
  # Add custom types as needed

# Preferred prefix ordering in output
prefix_order:
  - ""      # Default namespace first
  - "owl"
  - "rdfs"
  - "xsd"

# URIs to include as owl:imports
ontology_imports: []
  # - "http://example.org/core"

# Annotation properties to preserve from notes
annotation_properties: []
  # - "dcterms:description"
  # - "skos:definition"
'''
