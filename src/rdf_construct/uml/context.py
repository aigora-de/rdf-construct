"""UML context configuration for selecting RDF subsets to diagram.

A context defines what classes, properties, and individuals to include
in a PlantUML diagram, along with filtering and inclusion rules.
"""

from pathlib import Path
from typing import Any, Optional

import yaml


class UMLContext:
    """Represents a UML diagramming context from YAML configuration.

    A context specifies which RDF entities to include in a PlantUML diagram,
    how to traverse hierarchies, and which relationships to show.

    Attributes:
        name: Context identifier
        description: Human-readable description
        root_classes: List of root class CURIEs to start from
        focus_classes: Explicit list of classes to include (alternative to roots)
        include_descendants: Whether to include subclasses
        max_depth: Maximum depth when traversing hierarchies (None = unlimited)
        properties: Property inclusion configuration
        include_instances: Whether to include individuals
        selector: Selector key for bulk selection (alternative to roots/focus)
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize a UML context from configuration.

        Args:
            name: Context identifier
            config: Context configuration dictionary from YAML
        """
        self.name = name
        self.description = config.get("description", "")

        # Class selection strategies
        self.root_classes = config.get("root_classes", [])
        self.focus_classes = config.get("focus_classes", [])
        self.selector = config.get("selector")  # e.g., "classes"

        # Traversal settings
        self.include_descendants = config.get("include_descendants", False)
        self.max_depth = config.get("max_depth")

        # Property configuration
        prop_config = config.get("properties", {})
        if isinstance(prop_config, dict):
            self.property_mode = prop_config.get("mode", "domain_based")
            self.property_include = prop_config.get("include", [])
            self.property_exclude = prop_config.get("exclude", [])
        else:
            # Simple boolean for backward compatibility
            self.property_mode = "all" if prop_config else "none"
            self.property_include = []
            self.property_exclude = []

        # Instances
        self.include_instances = config.get("include_instances", False)

        # Style reference (will be used later)
        self.style = config.get("style", "default")

    def has_class_selection(self) -> bool:
        """Check if context has any class selection criteria."""
        return bool(
            self.root_classes or self.focus_classes or self.selector
        )

    def __repr__(self) -> str:
        return (
            f"UMLContext(name={self.name!r}, "
            f"roots={len(self.root_classes)}, "
            f"focus={len(self.focus_classes)})"
        )


class UMLConfig:
    """Configuration for UML diagram generation.

    Loads and manages YAML-based UML context specifications with support
    for multiple contexts, default settings, and shared configuration via
    YAML anchors.

    Attributes:
        defaults: Default settings applied across contexts
        contexts: Dictionary of available UML contexts
    """

    def __init__(self, yaml_path: Path | str):
        """Load UML configuration from a YAML file.

        Args:
            yaml_path: Path to YAML configuration file
        """
        yaml_path = Path(yaml_path)
        self.config = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        self.defaults = self.config.get("defaults", {}) or {}

        # Load contexts
        self.contexts = {}
        for ctx_name, ctx_config in (self.config.get("contexts", {}) or {}).items():
            self.contexts[ctx_name] = UMLContext(ctx_name, ctx_config)

    def get_context(self, name: str) -> UMLContext:
        """Get a context by name.

        Args:
            name: Context identifier

        Returns:
            UMLContext instance

        Raises:
            KeyError: If context name not found
        """
        if name not in self.contexts:
            raise KeyError(
                f"Context '{name}' not found. Available contexts: "
                f"{', '.join(self.contexts.keys())}"
            )
        return self.contexts[name]

    def list_contexts(self) -> list[str]:
        """Get list of available context names.

        Returns:
            List of context identifier strings
        """
        return list(self.contexts.keys())

    def __repr__(self) -> str:
        return f"UMLConfig(contexts={list(self.contexts.keys())})"


def load_uml_config(path: Path | str) -> UMLConfig:
    """Load UML configuration from a YAML file.

    Args:
        path: Path to YAML configuration file

    Returns:
        UMLConfig instance
    """
    return UMLConfig(path)
