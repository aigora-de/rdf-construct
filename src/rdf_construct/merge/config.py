"""Configuration dataclasses for the merge command.

Defines configuration structures for:
- Source files with priority ordering
- Namespace remapping rules
- Conflict resolution strategies
- Data migration settings
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

import yaml
from rdflib import URIRef

from rdf_construct.core.predicate_tiers import PredicateTier, build_tiers
from rdf_construct.core.utils import CurieError, resolve_curie


class ConflictStrategy(Enum):
    """Strategy for resolving conflicting values."""

    PRIORITY = auto()  # Higher priority source wins
    FIRST = auto()  # First source encountered wins
    LAST = auto()  # Last source encountered wins
    MARK_ALL = auto()  # Mark all conflicts for manual resolution


class ImportsStrategy(Enum):
    """Strategy for handling owl:imports statements."""

    PRESERVE = auto()  # Keep all imports from all sources
    REMOVE = auto()  # Remove all imports
    UPDATE = auto()  # Update imports to point to merged output
    MERGE = auto()  # Merge and deduplicate imports


@dataclass
class SourceConfig:
    """Configuration for a single source file.

    Attributes:
        path: Path to the source RDF file.
        priority: Priority for conflict resolution (higher wins).
        namespace_remap: Optional namespace remapping rules.
    """

    path: Path
    priority: int = 1
    namespace_remap: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> "SourceConfig":
        """Create from dictionary or simple path string.

        Args:
            data: Either a path string or dict with path, priority, remap

        Returns:
            SourceConfig instance
        """
        if isinstance(data, str):
            return cls(path=Path(data))

        return cls(
            path=Path(data["path"]),
            priority=data.get("priority", 1),
            namespace_remap=data.get("namespace_remap", {}),
        )


@dataclass
class NamespaceConfig:
    """Configuration for namespace handling.

    Attributes:
        base: Base namespace for the merged output.
        remappings: Global namespace remapping rules.
        preferred_prefixes: Preferred prefix bindings for output.
    """

    base: str | None = None
    remappings: dict[str, str] = field(default_factory=dict)
    preferred_prefixes: dict[str, str] = field(default_factory=dict)


@dataclass
class ConflictConfig:
    """Configuration for conflict handling.

    Attributes:
        strategy: How to resolve conflicts.
        report_path: Optional path to write conflict report.
        ignore_predicates: Predicates to ignore in conflict detection.
        predicate_tiers: Tier name (repeatable, per_language, load_bearing) to the predicates
            placed in it, over the defaults in `rdf_construct.core.predicate_tiers`.
    """

    strategy: ConflictStrategy = ConflictStrategy.PRIORITY
    report_path: Path | None = None
    ignore_predicates: set[str] = field(default_factory=set)
    predicate_tiers: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class MigrationRule:
    """A single data migration rule.

    Supports two types:
    - rename: Simple URI substitution
    - transform: SPARQL CONSTRUCT-style transformation

    Attributes:
        type: Either "rename" or "transform"
        description: Human-readable description of the rule
        from_uri: For rename: source URI to match
        to_uri: For rename: target URI to replace with
        match: For transform: SPARQL pattern to match
        construct: For transform: list of patterns to construct
        delete_matched: Whether to delete matched triples
    """

    type: str  # "rename" or "transform"
    description: str = ""
    # For rename type
    from_uri: str | None = None
    to_uri: str | None = None
    # For transform type
    match: str | None = None
    construct: list[dict[str, str]] = field(default_factory=list)
    delete_matched: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MigrationRule":
        """Create from dictionary.

        Args:
            data: Dictionary with rule configuration

        Returns:
            MigrationRule instance
        """
        return cls(
            type=data.get("type", "rename"),
            description=data.get("description", ""),
            from_uri=data.get("from"),
            to_uri=data.get("to"),
            match=data.get("match"),
            construct=data.get("construct", []),
            delete_matched=data.get("delete_matched", True),
        )


@dataclass
class DataMigrationConfig:
    """Configuration for data graph migration.

    Attributes:
        data_sources: Paths to data files to migrate.
        output_path: Path for migrated data output.
        rules: List of migration rules to apply.
        rules_file: Optional path to YAML file with rules.
    """

    data_sources: list[Path] = field(default_factory=list)
    output_path: Path | None = None
    rules: list[MigrationRule] = field(default_factory=list)
    rules_file: Path | None = None


@dataclass
class OutputConfig:
    """Configuration for output generation.

    Attributes:
        path: Output file path.
        format: RDF serialization format.
        preserve_prefixes: Whether to preserve source prefix bindings.
    """

    path: Path
    format: str = "turtle"
    preserve_prefixes: bool = True


@dataclass
class MergeConfig:
    """Complete configuration for a merge operation.

    Attributes:
        sources: List of source file configurations.
        output: Output configuration.
        namespaces: Namespace handling configuration.
        conflicts: Conflict resolution configuration.
        imports: owl:imports handling strategy.
        migrate_data: Optional data migration configuration.
        dry_run: If True, report what would happen without writing.
    """

    sources: list[SourceConfig] = field(default_factory=list)
    output: OutputConfig | None = None
    namespaces: NamespaceConfig = field(default_factory=NamespaceConfig)
    conflicts: ConflictConfig = field(default_factory=ConflictConfig)
    imports: ImportsStrategy = ImportsStrategy.PRESERVE
    migrate_data: DataMigrationConfig | None = None
    dry_run: bool = False

    @classmethod
    def from_yaml(cls, path: Path) -> "MergeConfig":
        """Load configuration from a YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            MergeConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MergeConfig":
        """Create from dictionary.

        Args:
            data: Dictionary with configuration

        Returns:
            MergeConfig instance
        """
        # Parse sources
        sources = []
        for src in data.get("sources", []):
            sources.append(SourceConfig.from_dict(src))

        # Parse output
        output = None
        if "output" in data:
            out_data = data["output"]
            if isinstance(out_data, str):
                output = OutputConfig(path=Path(out_data))
            else:
                output = OutputConfig(
                    path=Path(out_data["path"]),
                    format=out_data.get("format", "turtle"),
                    preserve_prefixes=out_data.get("preserve_prefixes", True),
                )

        # Parse namespaces
        ns_data = data.get("namespaces", {})
        namespaces = NamespaceConfig(
            base=ns_data.get("base"),
            remappings=ns_data.get("remappings", {}),
            preferred_prefixes=ns_data.get("preferred_prefixes", {}),
        )

        # Parse conflicts
        conf_data = data.get("conflicts", {})
        strategy_str = conf_data.get("strategy", "priority").upper()
        ignore_predicates, predicate_tiers = _parse_predicate_tiers(conf_data)
        conflicts = ConflictConfig(
            strategy=ConflictStrategy[strategy_str],
            report_path=Path(conf_data["report"]) if conf_data.get("report") else None,
            ignore_predicates=ignore_predicates,
            predicate_tiers=predicate_tiers,
        )

        # Parse imports strategy
        imports_str = data.get("imports", "preserve").upper()
        imports = ImportsStrategy[imports_str]

        # Parse data migration
        migrate_data = None
        if "migrate_data" in data:
            mig_data = data["migrate_data"]
            rules = [MigrationRule.from_dict(r) for r in mig_data.get("rules", [])]
            migrate_data = DataMigrationConfig(
                data_sources=[Path(p) for p in mig_data.get("sources", [])],
                output_path=Path(mig_data["output"]) if mig_data.get("output") else None,
                rules=rules,
                rules_file=Path(mig_data["rules_file"]) if mig_data.get("rules_file") else None,
            )

        return cls(
            sources=sources,
            output=output,
            namespaces=namespaces,
            conflicts=conflicts,
            imports=imports,
            migrate_data=migrate_data,
            dry_run=data.get("dry_run", False),
        )


def _predicate_iri(text: Any, key: str) -> str:
    """Resolve one predicate in the conflicts config to an IRI.

    Only IRIs are accepted for now: `merge` does not yet parse its sources with the project's
    binding rule (#357), so there is no prefix table a CURIE could honestly be resolved against.
    """
    try:
        return str(resolve_curie({}, str(text)))
    except CurieError as e:
        raise ValueError(
            f"conflicts.{key}: {text!r} is not an IRI. Give the full IRI, as "
            f"'http://www.w3.org/2000/01/rdf-schema#label' or "
            f"'<http://www.w3.org/2000/01/rdf-schema#label>'; prefixed names are not "
            f"resolved here yet"
        ) from e


def _parse_predicate_tiers(conf_data: dict[str, Any]) -> tuple[set[str], dict[str, list[str]]]:
    """Read and check `ignore_predicates` and `predicate_tiers` from the conflicts section.

    Raises:
        ValueError: If a tier name is unknown, a predicate is not an IRI, or one predicate is
            placed in two tiers.
    """
    ignore = {
        _predicate_iri(p, "ignore_predicates") for p in conf_data.get("ignore_predicates") or []
    }

    raw = conf_data.get("predicate_tiers") or {}
    if not isinstance(raw, dict):
        raise ValueError("conflicts.predicate_tiers must map tier names to lists of predicates")
    names = [t.value for t in PredicateTier]
    tiers: dict[str, list[str]] = {}
    for name, predicates in raw.items():
        if name not in names:
            raise ValueError(
                f"conflicts.predicate_tiers: unknown tier {name!r}. Tiers: {', '.join(names)}"
            )
        if not isinstance(predicates, list):
            raise ValueError(f"conflicts.predicate_tiers.{name} must be a list of predicates")
        tiers[name] = [_predicate_iri(p, f"predicate_tiers.{name}") for p in predicates]

    overrides: dict[PredicateTier, list[URIRef]] = {
        PredicateTier.REPEATABLE: [URIRef(p) for p in sorted(ignore)]
    }
    for name, predicates in tiers.items():
        overrides.setdefault(PredicateTier(name), []).extend(URIRef(p) for p in predicates)
    try:
        build_tiers(overrides)
    except ValueError as e:
        raise ValueError(f"conflicts: {e}; ignore_predicates counts as repeatable") from e
    return ignore, tiers


def load_merge_config(path: Path) -> MergeConfig:
    """Load merge configuration from a YAML file.

    Args:
        path: Path to configuration file

    Returns:
        MergeConfig instance
    """
    return MergeConfig.from_yaml(path)


def create_default_config() -> str:
    """Generate default merge configuration as YAML string.

    Returns:
        YAML configuration template
    """
    return """# rdf-construct merge configuration
# See MERGE_GUIDE.md for full documentation

# Source files to merge (in order of priority, lowest to highest)
sources:
  - path: core.ttl
    priority: 1
  - path: extension.ttl
    priority: 2

# Output configuration
output:
  path: merged.ttl
  format: turtle

# Namespace handling
namespaces:
  # base: "http://example.org/merged#"
  remappings: {}
  preferred_prefixes: {}

# Conflict resolution
conflicts:
  strategy: priority  # priority, first, last, or mark_all
  # report: conflicts.md  # Optional conflict report
  # Move a predicate into a tier, by full IRI. Unlisted predicates are repeatable.
  # predicate_tiers:
  #   repeatable: ["http://www.w3.org/2000/01/rdf-schema#label"]
  #   per_language: ["http://purl.org/dc/terms/title"]
  #   load_bearing: ["http://example.org/maxOccupancy"]

# owl:imports handling
imports: preserve  # preserve, remove, update, or merge

# Optional data migration
# migrate_data:
#   sources:
#     - split_instances.ttl
#   output: migrated.ttl
#   rules:
#     - type: rename
#       from: "http://old.example.org/ont#OldClass"
#       to: "http://example.org/ont#NewClass"
"""
