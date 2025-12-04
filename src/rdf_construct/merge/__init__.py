"""Ontology merge and modularisation tools.

This module provides tools for combining and splitting RDF ontology files
with intelligent conflict detection, namespace management, and optional
data migration support.

Usage:
    # Merge multiple ontologies
    from rdf_construct.merge import merge_files, OntologyMerger

    result = merge_files(
        sources=[Path("core.ttl"), Path("ext.ttl")],
        output=Path("merged.ttl"),
    )

    # With configuration
    from rdf_construct.merge import MergeConfig, load_merge_config

    config = load_merge_config(Path("merge.yml"))
    merger = OntologyMerger(config)
    result = merger.merge()

    # Split a monolithic ontology
    from rdf_construct.merge import OntologySplitter, SplitConfig

    config = SplitConfig.from_yaml(Path("split.yml"))
    splitter = OntologySplitter(config)
    result = splitter.split()
    splitter.write_modules(result)

    # Split by namespace (auto-detect)
    from rdf_construct.merge import split_by_namespace

    result = split_by_namespace(Path("large.ttl"), Path("modules/"))

CLI:
    # Basic merge
    rdf-construct merge core.ttl ext.ttl -o merged.ttl

    # With conflict report
    rdf-construct merge core.ttl ext.ttl -o merged.ttl --report conflicts.md

    # Split by namespace
    rdf-construct split large.ttl -o modules/ --by-namespace

    # Split with config
    rdf-construct split large.ttl -o modules/ -c split.yml
"""

from rdf_construct.merge.config import (
    MergeConfig,
    SourceConfig,
    NamespaceConfig,
    ConflictConfig,
    OutputConfig,
    DataMigrationConfig,
    MigrationRule,
    ConflictStrategy,
    ImportsStrategy,
    load_merge_config,
    create_default_config,
)

from rdf_construct.merge.conflicts import (
    Conflict,
    ConflictType,
    ConflictValue,
    ConflictDetector,
    SourceGraph,
    generate_conflict_marker,
    generate_conflict_end_marker,
    filter_semantic_conflicts,
)

from rdf_construct.merge.merger import (
    OntologyMerger,
    MergeResult,
    merge_files,
)

from rdf_construct.merge.migrator import (
    DataMigrator,
    MigrationResult,
    MigrationStats,
    migrate_data_files,
)

from rdf_construct.merge.rules import (
    RuleEngine,
    PatternParser,
    Match,
    Binding,
)

from rdf_construct.merge.formatters import (
    TextFormatter,
    MarkdownFormatter,
    get_formatter,
    FORMATTERS,
)

from rdf_construct.merge.splitter import (
    OntologySplitter,
    SplitConfig,
    SplitResult,
    ModuleDefinition,
    UnmatchedStrategy,
    SplitDataConfig,
    ModuleStats,
    split_by_namespace,
    create_default_split_config,
)

__all__ = [
    # Configuration
    "MergeConfig",
    "SourceConfig",
    "NamespaceConfig",
    "ConflictConfig",
    "OutputConfig",
    "DataMigrationConfig",
    "MigrationRule",
    "ConflictStrategy",
    "ImportsStrategy",
    "load_merge_config",
    "create_default_config",
    # Conflicts
    "Conflict",
    "ConflictType",
    "ConflictValue",
    "ConflictDetector",
    "SourceGraph",
    "generate_conflict_marker",
    "generate_conflict_end_marker",
    "filter_semantic_conflicts",
    # Merger
    "OntologyMerger",
    "MergeResult",
    "merge_files",
    # Migrator
    "DataMigrator",
    "MigrationResult",
    "MigrationStats",
    "migrate_data_files",
    # Rules
    "RuleEngine",
    "PatternParser",
    "Match",
    "Binding",
    # Formatters
    "TextFormatter",
    "MarkdownFormatter",
    "get_formatter",
    "FORMATTERS",
    # Splitter
    "OntologySplitter",
    "SplitConfig",
    "SplitResult",
    "ModuleDefinition",
    "UnmatchedStrategy",
    "SplitDataConfig",
    "ModuleStats",
    "split_by_namespace",
    "create_default_split_config",
]
