"""Configuration dataclasses for the refactor command.

Defines configuration structures for:
- URI renaming (single and bulk namespace)
- Deprecation specifications
- Data migration settings
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Literal

import yaml
from rdflib import Graph, URIRef


@dataclass
class RenameMapping:
    """A single URI rename mapping.

    Attributes:
        from_uri: Source URI to rename.
        to_uri: Target URI to rename to.
        source: How this mapping was determined.
    """

    from_uri: URIRef
    to_uri: URIRef
    source: Literal["explicit", "namespace"]


@dataclass
class RenameConfig:
    """Configuration for URI renaming operations.

    Supports both explicit entity renames and bulk namespace remapping.
    Namespace rules are applied first, then explicit entity renames,
    allowing fine-grained overrides after namespace changes.

    Attributes:
        namespaces: Old namespace -> new namespace mappings.
        entities: Explicit old URI -> new URI mappings.
    """

    namespaces: dict[str, str] = field(default_factory=dict)
    entities: dict[str, str] = field(default_factory=dict)

    def build_mappings(self, graph: Graph) -> list[RenameMapping]:
        """Expand namespace rules to concrete URI mappings.

        Scans the graph for all URIs and creates RenameMapping entries
        for those matching namespace patterns. Explicit entity mappings
        override any namespace-derived mappings.

        Args:
            graph: RDF graph to scan for URIs.

        Returns:
            List of RenameMapping objects.
        """
        mappings: dict[URIRef, RenameMapping] = {}

        # Phase 1: Apply namespace mappings
        if self.namespaces:
            # Collect all URIs from the graph
            all_uris: set[URIRef] = set()
            for s, p, o in graph:
                if isinstance(s, URIRef):
                    all_uris.add(s)
                if isinstance(p, URIRef):
                    all_uris.add(p)
                if isinstance(o, URIRef):
                    all_uris.add(o)

            # Apply namespace mappings
            for uri in all_uris:
                uri_str = str(uri)
                for old_ns, new_ns in self.namespaces.items():
                    if uri_str.startswith(old_ns):
                        new_uri_str = uri_str.replace(old_ns, new_ns, 1)
                        mappings[uri] = RenameMapping(
                            from_uri=uri,
                            to_uri=URIRef(new_uri_str),
                            source="namespace",
                        )
                        break

        # Phase 2: Apply explicit entity mappings (override namespace)
        for old_uri_str, new_uri_str in self.entities.items():
            old_uri = URIRef(old_uri_str)
            mappings[old_uri] = RenameMapping(
                from_uri=old_uri,
                to_uri=URIRef(new_uri_str),
                source="explicit",
            )

        return list(mappings.values())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RenameConfig":
        """Create from dictionary.

        Args:
            data: Dictionary with rename configuration.

        Returns:
            RenameConfig instance.
        """
        return cls(
            namespaces=data.get("namespaces", {}),
            entities=data.get("entities", {}),
        )


@dataclass
class DeprecationSpec:
    """Specification for deprecating a single entity.

    Attributes:
        entity: URI of entity to deprecate.
        replaced_by: Optional URI of replacement entity.
        message: Deprecation message for rdfs:comment.
        version: Optional version when deprecated.
    """

    entity: str
    replaced_by: str | None = None
    message: str | None = None
    version: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeprecationSpec":
        """Create from dictionary.

        Args:
            data: Dictionary with deprecation specification.

        Returns:
            DeprecationSpec instance.
        """
        return cls(
            entity=data["entity"],
            replaced_by=data.get("replaced_by"),
            message=data.get("message"),
            version=data.get("version"),
        )


@dataclass
class DeprecationConfig:
    """Configuration for bulk deprecation operations.

    Attributes:
        deprecations: List of deprecation specifications.
    """

    deprecations: list[DeprecationSpec] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeprecationConfig":
        """Create from dictionary.

        Args:
            data: Dictionary with deprecation configuration.

        Returns:
            DeprecationConfig instance.
        """
        specs = [DeprecationSpec.from_dict(d) for d in data.get("deprecations", [])]
        return cls(deprecations=specs)


@dataclass
class DataMigrationSpec:
    """Specification for data graph migration.

    Attributes:
        sources: Paths to data files to migrate.
        output_dir: Directory for migrated outputs.
        output: Single output file (for merging all data).
    """

    sources: list[str] = field(default_factory=list)
    output_dir: str | None = None
    output: str | None = None


@dataclass
class RefactorConfig:
    """Complete configuration for a refactor operation.

    Can contain either rename or deprecation (or both) configurations.

    Attributes:
        rename: Rename configuration (namespaces and entities).
        deprecations: List of deprecation specifications.
        migrate_data: Optional data migration configuration.
        source_files: Source ontology files to process.
        output: Output file path (for single file).
        output_dir: Output directory (for multiple files).
        dry_run: If True, report what would happen without writing.
    """

    rename: RenameConfig | None = None
    deprecations: list[DeprecationSpec] = field(default_factory=list)
    migrate_data: DataMigrationSpec | None = None
    source_files: list[Path] = field(default_factory=list)
    output: Path | None = None
    output_dir: Path | None = None
    dry_run: bool = False

    @classmethod
    def from_yaml(cls, path: Path) -> "RefactorConfig":
        """Load configuration from a YAML file.

        Args:
            path: Path to YAML configuration file.

        Returns:
            RefactorConfig instance.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            ValueError: If config is invalid.
        """
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RefactorConfig":
        """Create from dictionary.

        Args:
            data: Dictionary with configuration.

        Returns:
            RefactorConfig instance.
        """
        # Parse rename config
        rename = None
        if "rename" in data:
            rename = RenameConfig.from_dict(data["rename"])

        # Parse deprecations
        deprecations = []
        if "deprecations" in data:
            deprecations = [DeprecationSpec.from_dict(d) for d in data["deprecations"]]

        # Parse data migration
        migrate_data = None
        if "migrate_data" in data:
            mig = data["migrate_data"]
            migrate_data = DataMigrationSpec(
                sources=mig.get("sources", []),
                output_dir=mig.get("output_dir"),
                output=mig.get("output"),
            )

        # Parse source files
        sources = [Path(p) for p in data.get("source_files", [])]

        # Parse output
        output = Path(data["output"]) if data.get("output") else None
        output_dir = Path(data["output_dir"]) if data.get("output_dir") else None

        return cls(
            rename=rename,
            deprecations=deprecations,
            migrate_data=migrate_data,
            source_files=sources,
            output=output,
            output_dir=output_dir,
            dry_run=data.get("dry_run", False),
        )


def load_refactor_config(path: Path) -> RefactorConfig:
    """Load refactor configuration from a YAML file.

    Args:
        path: Path to configuration file.

    Returns:
        RefactorConfig instance.
    """
    return RefactorConfig.from_yaml(path)


def create_default_rename_config() -> str:
    """Generate default rename configuration as YAML string.

    Returns:
        YAML configuration template.
    """
    return '''# rdf-construct refactor rename configuration
# See REFACTOR_GUIDE.md for full documentation

# Source files to process
source_files:
  - ontology.ttl

# Output file
output: renamed.ttl

# Rename configuration
rename:
  # Namespace mappings (applied first)
  namespaces:
    "http://old.example.org/v1#": "http://example.org/v2#"
    # "http://temp.local/": "http://example.org/v2#"

  # Individual entity renames (applied after namespace)
  entities:
    # Fix typos
    # "http://example.org/v2#Buiding": "http://example.org/v2#Building"
    # "http://example.org/v2#hasAddres": "http://example.org/v2#hasAddress"

# Optional data migration
# migrate_data:
#   sources:
#     - data/*.ttl
#   output_dir: data/migrated/
'''


def create_default_deprecation_config() -> str:
    """Generate default deprecation configuration as YAML string.

    Returns:
        YAML configuration template.
    """
    return '''# rdf-construct refactor deprecation configuration
# See REFACTOR_GUIDE.md for full documentation

# Source files to process
source_files:
  - ontology.ttl

# Output file
output: deprecated.ttl

# Deprecation specifications
deprecations:
  - entity: "http://example.org/ont#LegacyPerson"
    replaced_by: "http://example.org/ont#Agent"
    message: "Deprecated in v2.0. Use Agent for both people and organisations."
    version: "2.0.0"

  - entity: "http://example.org/ont#hasAddress"
    replaced_by: "http://example.org/ont#locatedAt"
    message: "Renamed for consistency with location vocabulary."

  - entity: "http://example.org/ont#TemporaryClass"
    # No replacement - just deprecated
    message: "Experimental class removed. No replacement available."
'''
