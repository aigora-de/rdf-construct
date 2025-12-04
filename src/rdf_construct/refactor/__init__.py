"""Refactor module for URI renaming and deprecation.

This module provides tools for common ontology maintenance tasks:
- Renaming URIs (single entities or bulk namespace changes)
- Deprecating entities with proper OWL annotations
- Data migration for instance graphs

Example usage:
    from rdf_construct.refactor import OntologyRenamer, RenameConfig

    renamer = OntologyRenamer()
    config = RenameConfig(entities={
        "http://example.org/Buiding": "http://example.org/Building"
    })
    result = renamer.rename(graph, config)
"""

from rdf_construct.refactor.config import (
    RenameConfig,
    RenameMapping,
    DeprecationSpec,
    DeprecationConfig,
    RefactorConfig,
    DataMigrationSpec,
    load_refactor_config,
    create_default_rename_config,
    create_default_deprecation_config,
)
from rdf_construct.refactor.renamer import (
    OntologyRenamer,
    RenameResult,
    RenameStats,
    rename_file,
    rename_files,
)
from rdf_construct.refactor.deprecator import (
    OntologyDeprecator,
    DeprecationResult,
    DeprecationStats,
    EntityDeprecationInfo,
    deprecate_file,
    generate_deprecation_message,
)
from rdf_construct.refactor.formatters import TextFormatter

__all__ = [
    # Config
    "RenameConfig",
    "RenameMapping",
    "DeprecationSpec",
    "DeprecationConfig",
    "RefactorConfig",
    "DataMigrationSpec",
    "load_refactor_config",
    "create_default_rename_config",
    "create_default_deprecation_config",
    # Renamer
    "OntologyRenamer",
    "RenameResult",
    "RenameStats",
    "rename_file",
    "rename_files",
    # Deprecator
    "OntologyDeprecator",
    "DeprecationResult",
    "DeprecationStats",
    "EntityDeprecationInfo",
    "deprecate_file",
    "generate_deprecation_message",
    # Formatters
    "TextFormatter",
]
