"""Configuration loading and defaults for documentation generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DocsConfig:
    """Configuration for documentation generation.

    Attributes:
        output_dir: Directory to write generated documentation.
        format: Output format (html, markdown, json).
        title: Override title for the documentation.
        description: Override description for the documentation.
        template_dir: Custom template directory (overrides defaults).
        single_page: Generate single-page documentation.
        include_instances: Whether to include instances in output.
        include_imports: List of namespaces to treat as "internal".
        exclude_namespaces: List of namespaces to exclude from output.
        language: Preferred language for labels/definitions.
        base_url: Base URL for generated links (for deployment).
        logo_path: Path to logo image to include.
        css_path: Path to custom CSS to include.
        include_search: Generate search index for HTML output.
        include_hierarchy: Generate hierarchy visualisation.
        include_statistics: Include ontology statistics.
    """

    output_dir: Path = field(default_factory=lambda: Path("docs"))
    format: str = "html"
    title: str | None = None
    description: str | None = None
    template_dir: Path | None = None
    single_page: bool = False
    include_instances: bool = True
    include_imports: list[str] = field(default_factory=list)
    exclude_namespaces: list[str] = field(default_factory=list)
    language: str = "en"
    base_url: str = ""
    logo_path: Path | None = None
    css_path: Path | None = None
    include_search: bool = True
    include_hierarchy: bool = True
    include_statistics: bool = True

    # Entity type filtering
    include_classes: bool = True
    include_object_properties: bool = True
    include_datatype_properties: bool = True
    include_annotation_properties: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocsConfig:
        """Create configuration from a dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            DocsConfig instance.
        """
        config = cls()

        if "output_dir" in data:
            config.output_dir = Path(data["output_dir"])
        if "format" in data:
            config.format = data["format"]
        if "title" in data:
            config.title = data["title"]
        if "description" in data:
            config.description = data["description"]
        if "template_dir" in data:
            config.template_dir = Path(data["template_dir"])
        if "single_page" in data:
            config.single_page = data["single_page"]
        if "include_instances" in data:
            config.include_instances = data["include_instances"]
        if "include_imports" in data:
            config.include_imports = data["include_imports"]
        if "exclude_namespaces" in data:
            config.exclude_namespaces = data["exclude_namespaces"]
        if "language" in data:
            config.language = data["language"]
        if "base_url" in data:
            config.base_url = data["base_url"].rstrip("/")
        if "logo_path" in data:
            config.logo_path = Path(data["logo_path"])
        if "css_path" in data:
            config.css_path = Path(data["css_path"])
        if "include_search" in data:
            config.include_search = data["include_search"]
        if "include_hierarchy" in data:
            config.include_hierarchy = data["include_hierarchy"]
        if "include_statistics" in data:
            config.include_statistics = data["include_statistics"]

        # Entity filtering
        if "include_classes" in data:
            config.include_classes = data["include_classes"]
        if "include_object_properties" in data:
            config.include_object_properties = data["include_object_properties"]
        if "include_datatype_properties" in data:
            config.include_datatype_properties = data["include_datatype_properties"]
        if "include_annotation_properties" in data:
            config.include_annotation_properties = data["include_annotation_properties"]

        return config

    @classmethod
    def from_file(cls, path: Path) -> DocsConfig:
        """Load configuration from a YAML file.

        Args:
            path: Path to YAML configuration file.

        Returns:
            DocsConfig instance.

        Raises:
            FileNotFoundError: If the configuration file doesn't exist.
            ValueError: If the configuration file is invalid.
        """
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid configuration file: {path}")

        return cls.from_dict(data)


def load_docs_config(path: Path | None = None) -> DocsConfig:
    """Load documentation configuration.

    If no path is provided, returns default configuration.

    Args:
        path: Optional path to configuration file.

    Returns:
        DocsConfig instance.
    """
    if path is None:
        return DocsConfig()
    return DocsConfig.from_file(path)


# Utility functions for path generation

def entity_to_filename(qname: str) -> str:
    """Convert an entity QName to a safe filename.

    Args:
        qname: Qualified name like 'ex:Building'.

    Returns:
        Filesystem-safe filename like 'Building'.
    """
    # Strip prefix if present
    if ":" in qname:
        local_name = qname.split(":", 1)[1]
    else:
        local_name = qname

    # Replace any remaining problematic characters
    safe_name = local_name.replace("/", "_").replace("\\", "_").replace("#", "_")
    return safe_name


def entity_to_path(
    qname: str,
    entity_type: str,
    config: DocsConfig,
    extension: str | None = None,
) -> Path:
    """Generate the output path for an entity's documentation page.

    Args:
        qname: Entity qualified name.
        entity_type: Type of entity (class, object_property, datatype_property, instance).
        config: Documentation configuration.
        extension: File extension (defaults based on format).

    Returns:
        Relative path for the entity's documentation file.
    """
    if extension is None:
        extension = {
            "html": ".html",
            "markdown": ".md",
            "json": ".json",
        }.get(config.format, ".html")

    filename = entity_to_filename(qname) + extension

    # Organise by entity type
    type_dirs = {
        "class": "classes",
        "object_property": "properties/object",
        "datatype_property": "properties/datatype",
        "annotation_property": "properties/annotation",
        "instance": "instances",
    }

    subdir = type_dirs.get(entity_type, "other")
    return Path(subdir) / filename


def entity_to_url(
    qname: str,
    entity_type: str,
    config: DocsConfig,
) -> str:
    """Generate the URL for an entity's documentation page.

    Args:
        qname: Entity qualified name.
        entity_type: Type of entity.
        config: Documentation configuration.

    Returns:
        URL path for linking to the entity.
    """
    path = entity_to_path(qname, entity_type, config)
    url = str(path).replace("\\", "/")  # Ensure forward slashes

    if config.base_url:
        return f"{config.base_url}/{url}"
    return url
