"""Configuration loading and defaults for documentation generation."""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable


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
        include_shapes: Whether to include SHACL shapes (NodeShapes and
            named PropertyShapes) as a first-class entity type. Default
            True. When False, shapes are excluded entirely from output
            and from the search index.
        include_skos: Whether to include SKOS concepts and concept schemes
            as a first-class entity type. Default True. When False, both
            are excluded entirely from output and from the search index —
            they do not fall back to the Instances section.
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
    include_shapes: bool = True
    include_skos: bool = True
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
    include_other_properties: bool = True

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
        if "include_shapes" in data:
            config.include_shapes = data["include_shapes"]
        if "include_skos" in data:
            config.include_skos = data["include_skos"]
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
        if "include_other_properties" in data:
            config.include_other_properties = data["include_other_properties"]

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


# Entity type filtering (#252)

#: Every entity type ``--include`` and ``--exclude`` may name, in canonical spelling and order.
ENTITY_TYPE_NAMES: tuple[str, ...] = (
    "classes",
    "properties",
    "object_properties",
    "datatype_properties",
    "annotation_properties",
    "other_properties",
    "instances",
    "shapes",
    "concepts",
)

#: Other accepted spellings, each meaning its canonical name. Concepts and concept schemes
#: are one toggle, so ``concept_schemes`` and ``skos`` select (or exclude) both.
ENTITY_TYPE_ALIASES: dict[str, str] = {
    "concept_schemes": "concepts",
    "skos": "concepts",
}

#: The :class:`DocsConfig` fields each canonical name sets.
ENTITY_TYPE_TOGGLES: dict[str, tuple[str, ...]] = {
    "classes": ("include_classes",),
    "properties": (
        "include_object_properties",
        "include_datatype_properties",
        "include_annotation_properties",
        "include_other_properties",
    ),
    "object_properties": ("include_object_properties",),
    "datatype_properties": ("include_datatype_properties",),
    "annotation_properties": ("include_annotation_properties",),
    "other_properties": ("include_other_properties",),
    "instances": ("include_instances",),
    "shapes": ("include_shapes",),
    "concepts": ("include_skos",),
}

#: Every entity toggle, in the order of :data:`ENTITY_TYPE_NAMES`.
_ENTITY_TOGGLE_FIELDS: tuple[str, ...] = (
    "include_classes",
    "include_object_properties",
    "include_datatype_properties",
    "include_annotation_properties",
    "include_other_properties",
    "include_instances",
    "include_shapes",
    "include_skos",
)

_SPELLINGS: dict[str, str] = {name: name for name in ENTITY_TYPE_NAMES} | ENTITY_TYPE_ALIASES


class EntityFilterError(ValueError):
    """An entity filter that names nothing, names something unknown, or selects nothing.

    Raised rather than dropping the name, because a dropped name used to switch every entity
    type off: a typo in ``--include`` wrote a site with no entities at exit 0. See #252.
    """


def normalise_entity_types(names: Iterable[str], label: str = "") -> tuple[str, ...]:
    """Map entity type names to canonical ones, or refuse them all at once.

    Args:
        names: The names given, in any case, possibly padded with whitespace; empty
            elements are skipped
        label: What the names were given as, prefixed to the message; empty for none

    Returns:
        The canonical names, each once, in the order of :data:`ENTITY_TYPE_NAMES`

    Raises:
        EntityFilterError: If no name is given, or any name is not an entity type
    """
    prefix = f"{label}: " if label else ""
    if isinstance(names, str):
        raise EntityFilterError(
            f"{prefix}expected a collection of entity types, not the string {names!r}; "
            f"pass [{names!r}]"
        )
    given = [name.strip() for name in names]
    given = [name for name in given if name]
    accepted = ", ".join(ENTITY_TYPE_NAMES)
    if not given:
        raise EntityFilterError(f"{prefix}no entity types named. Accepted: {accepted}")
    # Each unknown name once, as first written, in the order given; case does not make it new
    first: dict[str, str] = {}
    for name in given:
        if name.lower() not in _SPELLINGS:
            first.setdefault(name.lower(), name)
    unknown = list(first.values())
    if unknown:
        parts = []
        for name in unknown:
            nearest = difflib.get_close_matches(name.lower(), list(_SPELLINGS), n=1)
            hint = f" (did you mean '{_SPELLINGS[nearest[0]]}'?)" if nearest else ""
            parts.append(f"'{name}'{hint}")
        plural = "s" if len(unknown) > 1 else ""
        raise EntityFilterError(
            f"{prefix}unknown entity type{plural} {', '.join(parts)}. Accepted: {accepted}"
        )
    chosen = {_SPELLINGS[name.lower()] for name in given}
    return tuple(name for name in ENTITY_TYPE_NAMES if name in chosen)


def apply_entity_filter(
    config: DocsConfig,
    include: Iterable[str] | None = None,
    exclude: Iterable[str] | None = None,
) -> DocsConfig:
    """Apply ``--include`` and ``--exclude`` to a configuration's entity toggles.

    ``include`` sets every entity toggle to whether it names that type; ``exclude`` then
    switches off each type it names. Whatever the toggles were set by, the configuration
    included, a selection that leaves no entity type switched on is refused: it would
    write a site with no entities (#252).

    Args:
        config: The configuration, changed in place
        include: Entity types to document, or None for no ``--include``
        exclude: Entity types to leave out, or None for no ``--exclude``

    Returns:
        The same configuration

    Raises:
        EntityFilterError: If either list names nothing or an unknown type, or if no
            entity type is left switched on
    """
    included = None if include is None else normalise_entity_types(include, "include")
    excluded = None if exclude is None else normalise_entity_types(exclude, "exclude")
    if included is not None:
        selected = {toggle for name in included for toggle in ENTITY_TYPE_TOGGLES[name]}
        for toggle in _ENTITY_TOGGLE_FIELDS:
            setattr(config, toggle, toggle in selected)
    if excluded is not None:
        for name in excluded:
            for toggle in ENTITY_TYPE_TOGGLES[name]:
                setattr(config, toggle, False)
    if not any(getattr(config, toggle) for toggle in _ENTITY_TOGGLE_FIELDS):
        raise EntityFilterError(
            "no entity type is left switched on, so nothing would be documented"
        )
    return config


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
        entity_type: Type of entity. Accepts ``"class"``,
            ``"object_property"``, ``"datatype_property"``,
            ``"annotation_property"``, ``"rdf_property"``, ``"instance"``,
            ``"shape"``, ``"skos_concept"`` or ``"skos_concept_scheme"``.
            ``EntityKind`` members are also accepted directly (they
            compare equal to their string values).
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

    # Organise by entity type. NodeShapes and named PropertyShapes share
    # the shapes/ directory — the kind badge on the page distinguishes
    # them. See issue #60. SKOS concepts and concept schemes share
    # concepts/ on the same principle (#63): a scheme is the container for
    # a vocabulary, but readers reach it from the index rather than by
    # browsing a directory of its own.
    type_dirs = {
        "class": "classes",
        "object_property": "properties/object",
        "datatype_property": "properties/datatype",
        "annotation_property": "properties/annotation",
        "instance": "instances",
        "shape": "shapes",
        "skos_concept": "concepts",
        "skos_concept_scheme": "concepts",
        # Properties whose kind is not implied by their declaration (#76):
        # rdf:Property, owl:FunctionalProperty, owl:DeprecatedProperty. The
        # bare "property" key catches a term reachable only through
        # rdfs:domain / rdfs:range that carries no rdf:type at all, so it
        # lands with its siblings rather than in a junk directory.
        "rdf_property": "properties/other",
        "property": "properties/other",
    }

    subdir = type_dirs.get(entity_type, "other")
    return Path(subdir) / filename


def entity_type_included(entity_type: str, config: DocsConfig) -> bool:
    """Report whether pages of this entity type are being generated.

    Filtering decides what is *generated*; it has to decide what is
    *linked to* as well, or the output fills with links to pages that
    were never written (#115). Unknown types default to True so a new
    entity kind is linked rather than silently unlinked before its flag
    exists.

    Args:
        entity_type: Entity type string, as used by ``entity_to_path``.
        config: Documentation configuration.

    Returns:
        True if that type's pages are part of this run.
    """
    return {
        "class": config.include_classes,
        "object_property": config.include_object_properties,
        "datatype_property": config.include_datatype_properties,
        "annotation_property": config.include_annotation_properties,
        "rdf_property": config.include_other_properties,
        "property": config.include_other_properties,
        "instance": config.include_instances,
        "shape": config.include_shapes,
        "skos_concept": config.include_skos,
        "skos_concept_scheme": config.include_skos,
    }.get(entity_type, True)


def relative_url_prefix(page_path: Path | str) -> str:
    """Compute the relative URL prefix from a page back to the docs root.

    Used so that generated HTML works regardless of where the docs are served
    from (file://, sub-paths, GitHub Pages project sites) when no absolute
    ``base_url`` is configured.

    Args:
        page_path: Path of the page relative to the docs output directory
            (e.g. ``"index.html"``, ``"classes/Foo.html"``,
            ``"properties/object/bar.html"``).

    Returns:
        ``"."`` for a top-level page, ``".."`` for one level deep,
        ``"../.."`` for two levels deep, etc.
    """
    page = Path(page_path)
    # Number of directory components above the page (i.e. excluding the file).
    depth = len(page.parts) - 1
    if depth <= 0:
        return "."
    return "/".join([".."] * depth)


def entity_to_url(
    qname: str,
    entity_type: str,
    config: DocsConfig,
    from_path: Path | str | None = None,
    extension: str | None = None,
) -> str:
    """Generate the URL for an entity's documentation page.

    Args:
        qname: Entity qualified name.
        entity_type: Type of entity.
        config: Documentation configuration.
        from_path: Optional path of the page the link is being rendered on
            (relative to the docs output directory). When ``config.base_url``
            is empty and ``from_path`` is provided, the returned URL is made
            relative to that page so links work regardless of the page's
            depth in the output tree. When ``config.base_url`` is set, that
            value takes precedence and ``from_path`` is ignored, preserving
            the previous behaviour.
        extension: File extension, passed through to
            :func:`entity_to_path`. Defaults to one derived from
            ``config.format`` — which knows ``"markdown"`` but not the
            ``"md"`` alias that :class:`DocsGenerator` accepts, so a caller
            that may see either should state it.

    Returns:
        URL path for linking to the entity.
    """
    path = entity_to_path(qname, entity_type, config, extension=extension)
    url = str(path).replace("\\", "/")  # Ensure forward slashes

    if config.base_url:
        return f"{config.base_url}/{url}"
    if from_path is not None:
        prefix = relative_url_prefix(from_path)
        if prefix == ".":
            return url
        return f"{prefix}/{url}"
    return url
