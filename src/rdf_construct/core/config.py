#!/usr/bin/env python3
"""Configuration and YAML handling for rdf-construct.

This module handles loading ordering profiles from YAML files and managing
RDF namespace prefixes and CURIE expansion.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from rdflib import Graph, Namespace, URIRef


@dataclass
class SectionConfig:
    """Configuration for a single section in an ordering profile."""

    name: str
    select: str
    sort: str = "qname_alpha"
    roots: Optional[List[str]] = None
    cluster: Optional[str] = None
    within_level: Optional[str] = None
    group_by: Optional[str] = None
    group_order: Optional[str] = None
    explicit_group_sequence: Optional[List[str]] = None
    within_group_tie: Optional[str] = None
    anchors: Optional[List[str]] = None
    after_anchors: Optional[str] = None


@dataclass
class ProfileConfig:
    """Configuration for an ordering profile."""

    name: str
    description: str = ""
    sections: List[SectionConfig] = field(default_factory=list)


@dataclass
class OrderingSpec:
    """Complete ordering specification from YAML."""

    defaults: Dict = field(default_factory=dict)
    selectors: Dict[str, str] = field(default_factory=dict)
    prefix_order: List[str] = field(default_factory=list)
    profiles: Dict[str, ProfileConfig] = field(default_factory=dict)


def load_yaml(path: Path) -> dict:
    """Load and parse a YAML file.

    Args:
        path: Path to the YAML file

    Returns:
        Parsed YAML content as dictionary

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the file is not valid YAML
    """
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_ordering_spec(path: Path) -> OrderingSpec:
    """Load and validate an ordering specification from YAML.

    Args:
        path: Path to the YAML ordering specification

    Returns:
        Validated OrderingSpec object
    """
    data = load_yaml(path)

    # Parse profiles
    profiles = {}
    for prof_name, prof_data in data.get("profiles", {}).items():
        sections = []
        for sec in prof_data.get("sections", []):
            if not isinstance(sec, dict) or not sec:
                continue
            sec_name, sec_cfg = next(iter(sec.items()))
            sec_cfg = sec_cfg or {}

            sections.append(
                SectionConfig(
                    name=sec_name,
                    select=sec_cfg.get("select", sec_name),
                    sort=sec_cfg.get("sort", "qname_alpha"),
                    roots=sec_cfg.get("roots"),
                    cluster=sec_cfg.get("cluster"),
                    within_level=sec_cfg.get("within_level"),
                    group_by=sec_cfg.get("group_by"),
                    group_order=sec_cfg.get("group_order"),
                    explicit_group_sequence=sec_cfg.get("explicit_group_sequence"),
                    within_group_tie=sec_cfg.get("within_group_tie"),
                    anchors=sec_cfg.get("anchors"),
                    after_anchors=sec_cfg.get("after_anchors"),
                )
            )

        profiles[prof_name] = ProfileConfig(
            name=prof_name, description=prof_data.get("description", ""), sections=sections
        )

    return OrderingSpec(
        defaults=data.get("defaults", {}),
        selectors=data.get("selectors", {}),
        prefix_order=data.get("prefix_order", []),
        profiles=profiles,
    )
