"""Configuration file handling for rdf-construct lint.

Supports loading .rdf-lint.yml files with rule settings and severity overrides.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from rdf_construct.lint.engine import LintConfig, check_rule_ids
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

    # Namespaces whose terms are not this ontology's own
    external_namespaces:
      - ies:
      - http://purl.org/dc/terms/
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

        check_rule_ids(enabled, f"'enable' section of {source}")
        config.enabled_rules.update(enabled)

    # Parse disabled rules
    if "disable" in data:
        disabled = data["disable"]
        if not isinstance(disabled, list):
            raise ValueError(f"'disable' must be a list in {source}")

        check_rule_ids(disabled, f"'disable' section of {source}")
        config.disabled_rules.update(disabled)

    # Parse severity overrides
    if "severity" in data:
        severities = data["severity"]
        if not isinstance(severities, dict):
            raise ValueError(f"'severity' must be a mapping in {source}")

        check_rule_ids(severities, f"'severity' section of {source}")

        for rule_id, sev_str in severities.items():
            try:
                severity = Severity(sev_str)
            except ValueError:
                raise ValueError(
                    f"Invalid severity '{sev_str}' for rule '{rule_id}' in {source}. "
                    "Must be 'error', 'warning', or 'info'."
                )

            config.severity_overrides[rule_id] = severity

    # Parse external namespaces (#69)
    if "external_namespaces" in data:
        config.external_namespaces = _parse_external_namespaces(data["external_namespaces"], source)

    return config


#: A CURIE as an ``external_namespaces`` entry: a prefix name (or none, for ``:``), a colon,
#: and no whitespace
_CURIE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_.-]*)?:\S*")


def _parse_external_namespaces(value: Any, source: Path) -> list[str]:
    """Check the ``external_namespaces`` list's shape, before any file is read.

    Each entry is a full IRI (``http://…``), an IRI in angle brackets (``<urn:x:>``) or a CURIE
    (``ies:``, ``dcterms:``). A CURIE is resolved later, against each linted file's prefixes.
    YAML reads an unquoted ``- ies:`` as a one-key mapping with no value; that is read as the
    CURIE ``ies:``, so it need not be quoted.

    Args:
        value: The key's value.
        source: The config file, for messages.

    Returns:
        The entries, stripped.

    Raises:
        ValueError: If the value is not a list, or an entry is not a non-empty string naming an
            IRI or a CURIE.
    """
    if not isinstance(value, list):
        raise ValueError(
            f"'external_namespaces' must be a list of namespace IRIs or CURIEs in {source}"
        )
    entries = []
    for item in value:
        # YAML reads an unquoted `- ies:` as the mapping {"ies": None}: that is the CURIE `ies:`
        if isinstance(item, dict) and len(item) == 1:
            ((key, val),) = item.items()
            if isinstance(key, str) and val is None:
                item = f"{key}:"
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"'external_namespaces' entry {item!r} in {source} must be a non-empty string: "
                "a namespace IRI, an IRI in angle brackets, or a CURIE such as 'ies:'."
            )
        entry = item.strip()
        bracketed = entry.startswith("<") and entry.endswith(">") and len(entry) > 2
        iri = "://" in entry and not any(ch.isspace() for ch in entry)
        if not (bracketed or iri or _CURIE.fullmatch(entry)):
            raise ValueError(
                f"'external_namespaces' entry {entry!r} in {source} is not a namespace IRI, an "
                "IRI in angle brackets, or a CURIE such as 'ies:'."
            )
        entries.append(entry)
    return entries


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

# Namespaces whose terms are not this ontology's own: a reference into one is never
# dangling, and its terms need no label or comment here. IRIs, <IRIs> or CURIEs, which
# resolve against each linted file's own prefixes.
# external_namespaces:
#   - ies:
#   - http://purl.org/dc/terms/

# Available rules:
{chr(10).join(f'#   - {r}' for r in known_rules)}
"""
