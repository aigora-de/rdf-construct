"""Profile and configuration management for RDF ordering."""

from pathlib import Path
from typing import Any

import yaml

from .predicate_order import PredicateOrderConfig

#: Policies for subjects that no section of a profile claims.
#:
#: - ``warn``   — emit only what the sections claimed, and report the loss (default)
#: - ``emit``   — append the unclaimed subjects in a trailing section, losing nothing
#: - ``ignore`` — emit only what the sections claimed, silently; for a profile that
#:   filters deliberately
UNCLAIMED_POLICIES = ("warn", "emit", "ignore")

DEFAULT_UNCLAIMED_POLICY = "warn"


class OrderingProfile:
    """Represents an ordering profile from a YAML configuration.

    A profile defines how to organize and order RDF subjects, typically
    with multiple sections (classes, properties, individuals) each having
    their own selection and sorting rules.

    Attributes:
        name: Profile identifier
        description: Human-readable description
        sections: List of section configurations
        predicate_order: Optional predicate ordering configuration
        unclaimed: Policy for subjects no section claims, or None to inherit
            the config-level default
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
        self.unclaimed = config.get("unclaimed")
        self.predicate_order = PredicateOrderConfig.from_dict(config.get("predicate_order"))

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
        predicate_order: Default predicate ordering (can be overridden per profile)
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

        # Load default predicate ordering (can be overridden per profile)
        self.predicate_order = PredicateOrderConfig.from_dict(self.config.get("predicate_order"))

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

    def get_predicate_order(self, profile_name: str) -> PredicateOrderConfig | None:
        """Get the effective predicate ordering for a profile.

        Profile-level predicate_order takes precedence over config-level.

        Args:
            profile_name: Profile identifier

        Returns:
            PredicateOrderConfig or None if no ordering configured
        """
        profile = self.get_profile(profile_name)

        # Profile-level overrides config-level
        if profile.predicate_order.classes.first or profile.predicate_order.classes.last:
            return profile.predicate_order
        if profile.predicate_order.properties.first or profile.predicate_order.properties.last:
            return profile.predicate_order
        if profile.predicate_order.individuals.first or profile.predicate_order.individuals.last:
            return profile.predicate_order
        if profile.predicate_order.default.first or profile.predicate_order.default.last:
            return profile.predicate_order

        # Fall back to config-level
        if self.predicate_order.classes.first or self.predicate_order.classes.last:
            return self.predicate_order
        if self.predicate_order.properties.first or self.predicate_order.properties.last:
            return self.predicate_order
        if self.predicate_order.individuals.first or self.predicate_order.individuals.last:
            return self.predicate_order
        if self.predicate_order.default.first or self.predicate_order.default.last:
            return self.predicate_order

        return None

    def get_unclaimed_policy(self, profile_name: str) -> str:
        """Get the effective policy for subjects no section of a profile claims.

        Profile-level ``unclaimed`` takes precedence over ``defaults.unclaimed``,
        which in turn takes precedence over the built-in default (``warn``).

        Args:
            profile_name: Profile identifier

        Returns:
            One of :data:`UNCLAIMED_POLICIES`

        Raises:
            KeyError: If profile name not found
            ValueError: If the configured policy is not a recognised value
        """
        profile = self.get_profile(profile_name)

        policy = profile.unclaimed
        if policy is None:
            policy = self.defaults.get("unclaimed", DEFAULT_UNCLAIMED_POLICY)

        if policy not in UNCLAIMED_POLICIES:
            raise ValueError(
                f"Unknown 'unclaimed' policy {policy!r} in profile '{profile_name}'. "
                f"Expected one of: {', '.join(UNCLAIMED_POLICIES)}"
            )

        return str(policy)

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
