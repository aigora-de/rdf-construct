"""Configuration file handling for rdf-construct lint.

Supports loading .rdf-lint.yml files with rule settings and severity overrides.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rdf_construct.lint.engine import LintConfig
from rdf_construct.lint.rules import Severity, list_rules


def load_lint_config(config_path: Path) -> LintConfig:
    """Load lint configuration from a YAML file.

    The configuration file format:

    ```yaml
    # Global settings
    level: standard  # strict | standard | relaxed

    # Rules to enable (empty means all)
    enable:
      - orphan-class
      - missing-label

    # Rules to disable
    disable:
      - inconsistent-naming

    # Override severity for specific rules
    severity:
      missing-comment: info
      orphan-class: warning
    ```

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        LintConfig with settings from the file.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config file is invalid.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")

    if data is None:
        data = {}

    return _parse_config(data, config_path)


def _parse_config(data: dict[str, Any], source: Path) -> LintConfig:
    """Parse configuration dictionary into LintConfig.

    Args:
        data: Configuration dictionary from YAML.
        source: Source file path (for error messages).

    Returns:
        Parsed LintConfig.

    Raises:
        ValueError: If configuration is invalid.
    """
    config = LintConfig()
    known_rules = set(list_rules())

    # Parse level
    if "level" in data:
        level = data["level"]
        if level not in ("strict", "standard", "relaxed"):
            raise ValueError(
                f"Invalid level '{level}' in {source}. "
                "Must be 'strict', 'standard', or 'relaxed'."
            )
        config.level = level

    # Parse enabled rules
    if "enable" in data:
        enabled = data["enable"]
        if not isinstance(enabled, list):
            raise ValueError(f"'enable' must be a list in {source}")

        for rule_id in enabled:
            if rule_id not in known_rules:
                raise ValueError(
                    f"Unknown rule '{rule_id}' in 'enable' section of {source}. "
                    f"Available rules: {', '.join(sorted(known_rules))}"
                )
            config.enabled_rules.add(rule_id)

    # Parse disabled rules
    if "disable" in data:
        disabled = data["disable"]
        if not isinstance(disabled, list):
            raise ValueError(f"'disable' must be a list in {source}")

        for rule_id in disabled:
            if rule_id not in known_rules:
                raise ValueError(
                    f"Unknown rule '{rule_id}' in 'disable' section of {source}. "
                    f"Available rules: {', '.join(sorted(known_rules))}"
                )
            config.disabled_rules.add(rule_id)

    # Parse severity overrides
    if "severity" in data:
        severities = data["severity"]
        if not isinstance(severities, dict):
            raise ValueError(f"'severity' must be a mapping in {source}")

        for rule_id, sev_str in severities.items():
            if rule_id not in known_rules:
                raise ValueError(
                    f"Unknown rule '{rule_id}' in 'severity' section of {source}. "
                    f"Available rules: {', '.join(sorted(known_rules))}"
                )

            try:
                severity = Severity(sev_str)
            except ValueError:
                raise ValueError(
                    f"Invalid severity '{sev_str}' for rule '{rule_id}' in {source}. "
                    "Must be 'error', 'warning', or 'info'."
                )

            config.severity_overrides[rule_id] = severity

    return config


def find_config_file(start_dir: Path | None = None) -> Path | None:
    """Find a lint config file by searching up the directory tree.

    Looks for files named '.rdf-lint.yml' or '.rdf-lint.yaml' starting
    from start_dir and moving up to the filesystem root.

    Args:
        start_dir: Directory to start searching from. Defaults to cwd.

    Returns:
        Path to config file if found, None otherwise.
    """
    if start_dir is None:
        start_dir = Path.cwd()

    config_names = [".rdf-lint.yml", ".rdf-lint.yaml", "rdf-lint.yml", "rdf-lint.yaml"]

    current = start_dir.resolve()

    while True:
        for name in config_names:
            config_path = current / name
            if config_path.exists():
                return config_path

        parent = current.parent
        if parent == current:
            # Reached filesystem root
            break
        current = parent

    return None


def create_default_config() -> str:
    """Generate a default configuration file as a string.

    Returns:
        YAML string with commented default configuration.
    """
    known_rules = sorted(list_rules())

    return f"""\
# rdf-construct lint configuration
# Place this file as .rdf-lint.yml in your project root

# Strictness level: strict | standard | relaxed
# - strict: warnings become errors
# - standard: default severities
# - relaxed: warnings become info
level: standard

# Enable only specific rules (empty = all rules)
# enable:
#   - orphan-class
#   - missing-label

# Disable specific rules
# disable:
#   - inconsistent-naming

# Override severity for specific rules
# severity:
#   missing-comment: info
#   orphan-class: warning

# Available rules:
# {chr(10).join(f'#   - {r}' for r in known_rules)}
"""
