"""Configuration handling for PlantUML import.

This module provides YAML-based configuration for controlling
how PlantUML diagrams are converted to RDF ontologies.
"""

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from rdf_construct import __version__
from rdf_construct.puml2rdf.converter import ConversionConfig
from rdf_construct.puml2rdf.datatypes import DatatypeMap, parse_datatype_value
from rdf_construct.puml2rdf.model import NamespaceMapping
from rdf_construct.puml2rdf.parser import URI_SCHEME_PATTERN

# Every key a puml2rdf config may hold; anything else is refused (#152, as #268 decides)
ACCEPTED_KEYS: tuple[str, ...] = (
    "default_namespace",
    "language",
    "generate_labels",
    "camel_to_label",
    "namespace_mappings",
    "datatype_mappings",
)

# Keys earlier releases accepted and nothing ever read, with why each is gone (#152)
REMOVED_KEYS: dict[str, str] = {
    "prefix_order": (
        "puml2rdf does not order its prefixes yet; the key can return when its Turtle goes "
        "through the semantic serialiser (#162). The `order` command honours prefix_order"
    ),
    "ontology_imports": "nothing ever read it, so no owl:imports was ever written",
    "annotation_properties": "nothing ever read it",
    "generate_inverse_properties": "nothing ever read it, and no inverse was ever generated",
}

_MAPPING_KEYS = ("package", "namespace_uri", "prefix")
_DATATYPE_ITEM_KEYS = ("puml_type", "rdf_type")


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
        namespace_mappings: Package to namespace mappings, which the parser applies
        datatype_mappings: Custom datatype conversions, merged into the one datatype map
        notes: What the config chose that is worth saying, such as a built-in type name it
            maps differently; never fatal
    """

    default_namespace: str = "http://example.org/ontology#"
    language: str = "en"
    generate_labels: bool = True
    camel_to_label: bool = True
    namespace_mappings: list[NamespaceMapping] = field(default_factory=list)
    datatype_mappings: list[DatatypeMapping] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def datatype_map(self) -> DatatypeMap:
        """Build the datatype map: the built-in type names, with these mappings over them.

        Raises:
            ValueError: If a mapping names no datatype, or two type names fold together.
        """
        return DatatypeMap({m.puml_type: m.rdf_type for m in self.datatype_mappings})

    def to_conversion_config(self) -> ConversionConfig:
        """Convert to the simpler ConversionConfig used by converter."""
        return ConversionConfig(
            default_namespace=self.default_namespace,
            language=self.language,
            generate_labels=self.generate_labels,
            camel_to_label=self.camel_to_label,
            datatypes=self.datatype_map(),
        )


def load_import_config(path: Path) -> PumlImportConfig:
    """Load PlantUML import configuration from a YAML file.

    Args:
        path: Path to the YAML configuration file

    Returns:
        Parsed configuration object

    Raises:
        FileNotFoundError: If the config file doesn't exist
        ValueError: If the config holds a key puml2rdf does not accept, a value of the
            wrong type, or a datatype mapping that names no datatype
    """
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Configuration must be a YAML dictionary")

    return _parse_config(data)


def _check_keys(data: dict[str, Any]) -> None:
    """Refuse a key puml2rdf does not accept, naming what it does (#152, #268).

    Raises:
        ValueError: For the first key that is removed or unknown.
    """
    for key in data:
        name = str(key)
        if name in ACCEPTED_KEYS:
            continue
        if name in REMOVED_KEYS:
            raise ValueError(
                f"'{name}' was removed in rdf-construct 0.7.0: {REMOVED_KEYS[name]}. "
                "Delete it from the config"
            )
        nearest = difflib.get_close_matches(name, ACCEPTED_KEYS, n=1)
        hint = f" Did you mean '{nearest[0]}'?" if nearest else ""
        raise ValueError(
            f"unknown key '{name}' (rdf-construct {__version__}).{hint} "
            f"Accepted keys: {', '.join(ACCEPTED_KEYS)}"
        )


def _string(data: dict[str, Any], key: str) -> str:
    """Return ``data[key]`` if it is a string, or refuse it."""
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"'{key}' must be a string, not {_kind(value)}")
    return value


def _boolean(data: dict[str, Any], key: str) -> bool:
    """Return ``data[key]`` if it is a YAML boolean, or refuse it: ``"false"`` is a string."""
    value = data[key]
    if not isinstance(value, bool):
        raise ValueError(f"'{key}' must be true or false, unquoted, not {_kind(value)}")
    return value


def _kind(value: Any) -> str:
    """Describe a YAML value for a message."""
    if value is None:
        return "empty"
    if isinstance(value, str):
        return f"the string '{value}'"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, int | float):
        return f"the number {value}"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "a mapping"
    return type(value).__name__


def _sub_keys(item: dict[str, Any], accepted: tuple[str, ...], where: str) -> None:
    """Refuse a key in a list entry that the entry does not accept."""
    for key in item:
        if key not in accepted:
            raise ValueError(
                f"{where} has an unknown key '{key}'. Accepted keys: {', '.join(accepted)}"
            )


def _parse_namespace_mappings(raw: Any) -> list[NamespaceMapping]:
    """Read ``namespace_mappings``: a list of ``{package, namespace_uri, prefix}`` entries."""
    if not isinstance(raw, list):
        raise ValueError(f"'namespace_mappings' must be a list, not {_kind(raw)}")
    mappings: list[NamespaceMapping] = []
    seen: set[str] = set()
    for number, item in enumerate(raw, start=1):
        where = f"namespace_mappings entry {number}"
        if not isinstance(item, dict):
            raise ValueError(f"{where} must be a mapping, not {_kind(item)}")
        _sub_keys(item, _MAPPING_KEYS, where)
        for required in ("package", "namespace_uri"):
            if not isinstance(item.get(required), str) or not item[required].strip():
                raise ValueError(f"{where} needs '{required}', as a string")
        package = item["package"].strip()
        uri = item["namespace_uri"].strip()
        prefix = item.get("prefix")
        if prefix is not None and not isinstance(prefix, str):
            raise ValueError(f"{where}: 'prefix' must be a string, not {_kind(prefix)}")
        if prefix is not None and not prefix.strip():
            raise ValueError(f"{where}: 'prefix' is empty; leave it out to use the package's name")
        if not URI_SCHEME_PATTERN.match(uri):
            raise ValueError(
                f"{where}: namespace_uri '{uri}' is not an IRI: it has no scheme, such as http:"
            )
        if package in seen:
            raise ValueError(f"{where} maps package '{package}' a second time")
        seen.add(package)
        mappings.append(NamespaceMapping(package=package, namespace_uri=uri, prefix=prefix))
    return mappings


def _parse_datatype_mappings(raw: Any) -> list[DatatypeMapping]:
    """Read ``datatype_mappings``: a mapping of type name to datatype, or a list of entries."""
    pairs: list[tuple[str, Any]] = []
    if isinstance(raw, dict):
        pairs = [(str(name), value) for name, value in raw.items()]
    elif isinstance(raw, list):
        for number, item in enumerate(raw, start=1):
            where = f"datatype_mappings entry {number}"
            if not isinstance(item, dict):
                raise ValueError(f"{where} must be a mapping, not {_kind(item)}")
            _sub_keys(item, _DATATYPE_ITEM_KEYS, where)
            if not isinstance(item.get("puml_type"), str):
                raise ValueError(f"{where} needs 'puml_type', as a string")
            pairs.append((item["puml_type"], item.get("rdf_type")))
    else:
        raise ValueError(
            f"'datatype_mappings' must be a mapping of type name to datatype, not {_kind(raw)}"
        )
    mappings: list[DatatypeMapping] = []
    for name, value in pairs:
        if not isinstance(value, str):
            raise ValueError(f"datatype_mappings '{name}' must be a datatype, not {_kind(value)}")
        try:
            parse_datatype_value(value)
        except ValueError as error:
            raise ValueError(f"datatype_mappings '{name}': {error}") from error
        mappings.append(DatatypeMapping(puml_type=name, rdf_type=value))
    return mappings


def _parse_config(data: dict[str, Any]) -> PumlImportConfig:
    """Parse configuration dictionary into PumlImportConfig.

    Args:
        data: Raw YAML data dictionary

    Returns:
        Parsed configuration object

    Raises:
        ValueError: If a key is removed or unknown, or a value has the wrong type
    """
    _check_keys(data)
    config = PumlImportConfig()

    if "default_namespace" in data:
        config.default_namespace = _string(data, "default_namespace")
    if "language" in data:
        config.language = _string(data, "language")
    if "generate_labels" in data:
        config.generate_labels = _boolean(data, "generate_labels")
    if "camel_to_label" in data:
        config.camel_to_label = _boolean(data, "camel_to_label")
    if "namespace_mappings" in data:
        config.namespace_mappings = _parse_namespace_mappings(data["namespace_mappings"])
    if "datatype_mappings" in data:
        config.datatype_mappings = _parse_datatype_mappings(data["datatype_mappings"])

    # Fold collisions are refused here, where the file is named, rather than at conversion
    for name in config.datatype_map().overrides:
        config.notes.append(f"datatype_mappings '{name}' replaces the built-in type of that name")

    return config


def create_default_config() -> str:
    """Generate a default configuration YAML string.

    Returns:
        YAML string with default configuration and comments
    """
    return """# PlantUML Import Configuration
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

# Map PlantUML packages to RDF namespaces. `package` is the package's name as the
# diagram gives it (`outer.inner` for a nested one); `prefix` is optional
namespace_mappings:
  - package: "building"
    namespace_uri: "http://example.org/building#"
    prefix: "bld"
  # - package: "core"
  #   namespace_uri: "http://example.org/core#"

# Custom datatype mappings (PlantUML type -> datatype). Type names match without
# regard to case; a value is an xsd: CURIE or a full IRI
datatype_mappings:
  Money: "xsd:decimal"
  Percentage: "xsd:decimal"
  Identifier: "xsd:string"
  # Add custom types as needed
"""
