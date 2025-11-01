"""Profile and configuration management for RDF ordering."""

from pathlib import Path
from typing import Any

import yaml


class OrderingProfile:
    """Represents an ordering profile from a YAML configuration.

    A profile defines how to organize and order RDF subjects, typically
    with multiple sections (classes, properties, individuals) each having
    their own selection and sorting rules.

    Attributes:
        name: Profile identifier
        description: Human-readable description
        sections: List of section configurations
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize a profile from configuration.

        Args:
            name: Profile identifier
            config: Profile configuration dictionary from YAML
        """
        self.name = name
        self.description = config.get("description", "")
        self.sections = config.get("sections", [])

    def __repr__(self) -> str:
        return f"OrderingProfile(name={self.name!r}, sections={len(self.sections)})"


class OrderingConfig:
    """Configuration for RDF ordering operations.

    Loads and manages YAML-based ordering specifications with support
    for multiple profiles, default settings, selectors, and shared
    configuration via YAML anchors.

    Attributes:
        defaults: Default settings applied across profiles
        selectors: Named selector definitions
        prefix_order: Preferred order for namespace prefixes
        profiles: Dictionary of available ordering profiles
    """

    def __init__(self, yaml_path: Path | str):
        """Load ordering configuration from a YAML file.

        Args:
            yaml_path: Path to YAML configuration file
        """
        yaml_path = Path(yaml_path)
        self.config = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        self.defaults = self.config.get("defaults", {}) or {}
        self.selectors = self.config.get("selectors", {}) or {}
        self.prefix_order = self.config.get("prefix_order", []) or []

        # Load profiles
        self.profiles = {}
        for prof_name, prof_config in (self.config.get("profiles", {}) or {}).items():
            self.profiles[prof_name] = OrderingProfile(prof_name, prof_config)

    def get_profile(self, name: str) -> OrderingProfile:
        """Get a profile by name.

        Args:
            name: Profile identifier

        Returns:
            OrderingProfile instance

        Raises:
            KeyError: If profile name not found
        """
        if name not in self.profiles:
            raise KeyError(
                f"Profile '{name}' not found. Available profiles: "
                f"{', '.join(self.profiles.keys())}"
            )
        return self.profiles[name]

    def list_profiles(self) -> list[str]:
        """Get list of available profile names.

        Returns:
            List of profile identifier strings
        """
        return list(self.profiles.keys())

    def __repr__(self) -> str:
        return f"OrderingConfig(profiles={list(self.profiles.keys())})"


def load_yaml(path: Path | str) -> dict[str, Any]:
    """Load YAML file with UTF-8 encoding.

    Args:
        path: Path to YAML file

    Returns:
        Parsed YAML content as dictionary
    """
    path = Path(path)
    return yaml.safe_load(path.read_text(encoding="utf-8"))
