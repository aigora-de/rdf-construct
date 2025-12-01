"""Main orchestrator for documentation generation.

This module coordinates entity extraction, template rendering, and output
file creation for generating ontology documentation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rdflib import Graph

from rdf_construct.docs.config import DocsConfig, load_docs_config
from rdf_construct.docs.extractors import ExtractedEntities, extract_all
from rdf_construct.docs.search import generate_search_index, write_search_index
    
if TYPE_CHECKING:
    pass


class DocsGenerator:
    """Main documentation generator class.

    Coordinates extraction, rendering, and file output for generating
    comprehensive ontology documentation.
    """

    def __init__(self, config: DocsConfig | None = None) -> None:
        """Initialise the documentation generator.

        Args:
            config: Documentation configuration. Uses defaults if not provided.
        """
        self.config = config or DocsConfig()
        self._renderer: "BaseRenderer | None" = None

    @property
    def renderer(self) -> "BaseRenderer":
        """Get the appropriate renderer for the configured format.

        Returns:
            Renderer instance for the configured output format.
        """
        if self._renderer is None:
            self._renderer = self._create_renderer()
        return self._renderer

    def _create_renderer(self) -> "BaseRenderer":
        """Create the appropriate renderer based on configuration.

        Returns:
            Renderer instance.

        Raises:
            ValueError: If the output format is not supported.
        """
        from .renderers import HTMLRenderer, JSONRenderer, MarkdownRenderer

        format_lower = self.config.format.lower()

        if format_lower == "html":
            return HTMLRenderer(self.config)
        elif format_lower in ("markdown", "md"):
            return MarkdownRenderer(self.config)
        elif format_lower == "json":
            return JSONRenderer(self.config)
        else:
            raise ValueError(f"Unsupported output format: {self.config.format}")

    def generate(self, graph: Graph) -> GenerationResult:
        """Generate documentation from an RDF graph.

        Args:
            graph: RDF graph to generate documentation from.

        Returns:
            GenerationResult with details of generated files.
        """
        # Extract all entities
        entities = extract_all(graph)

        # Apply configuration overrides
        if self.config.title:
            entities.ontology.title = self.config.title
        if self.config.description:
            entities.ontology.description = self.config.description

        # Create output directory
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        result = GenerationResult(output_dir=self.config.output_dir)

        # Generate main pages
        if self.config.single_page:
            output_path = self.renderer.render_single_page(entities)
            result.files_created.append(output_path)
        else:
            # Index page
            index_path = self.renderer.render_index(entities)
            result.files_created.append(index_path)

            # Hierarchy page
            if self.config.include_hierarchy:
                hierarchy_path = self.renderer.render_hierarchy(entities)
                result.files_created.append(hierarchy_path)

            # Individual entity pages
            if self.config.include_classes:
                for class_info in entities.classes:
                    class_path = self.renderer.render_class(class_info, entities)
                    result.files_created.append(class_path)
                    result.classes_count += 1

            if self.config.include_object_properties:
                for prop_info in entities.object_properties:
                    prop_path = self.renderer.render_property(prop_info, entities)
                    result.files_created.append(prop_path)
                    result.properties_count += 1

            if self.config.include_datatype_properties:
                for prop_info in entities.datatype_properties:
                    prop_path = self.renderer.render_property(prop_info, entities)
                    result.files_created.append(prop_path)
                    result.properties_count += 1

            if self.config.include_annotation_properties:
                for prop_info in entities.annotation_properties:
                    prop_path = self.renderer.render_property(prop_info, entities)
                    result.files_created.append(prop_path)
                    result.properties_count += 1

            if self.config.include_instances:
                for instance_info in entities.instances:
                    instance_path = self.renderer.render_instance(instance_info, entities)
                    result.files_created.append(instance_path)
                    result.instances_count += 1

            # Namespace page
            namespace_path = self.renderer.render_namespaces(entities)
            result.files_created.append(namespace_path)

        # Generate search index
        if self.config.include_search and self.config.format == "html":
            search_entries = generate_search_index(entities, self.config)
            search_path = write_search_index(search_entries, self.config.output_dir)
            result.files_created.append(search_path)

        # Copy assets
        self.renderer.copy_assets()

        return result

    def generate_from_file(self, source: Path) -> GenerationResult:
        """Generate documentation from an RDF file.

        Args:
            source: Path to RDF source file.

        Returns:
            GenerationResult with details of generated files.

        Raises:
            FileNotFoundError: If the source file doesn't exist.
        """
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        graph = Graph()

        # Determine format from extension
        suffix = source.suffix.lower()
        format_map = {
            ".ttl": "turtle",
            ".turtle": "turtle",
            ".rdf": "xml",
            ".xml": "xml",
            ".owl": "xml",
            ".nt": "nt",
            ".ntriples": "nt",
            ".n3": "n3",
            ".jsonld": "json-ld",
            ".json": "json-ld",
        }
        rdf_format = format_map.get(suffix, "turtle")

        graph.parse(str(source), format=rdf_format)
        return self.generate(graph)


class GenerationResult:
    """Result of a documentation generation run."""

    def __init__(self, output_dir: Path) -> None:
        """Initialise the result.

        Args:
            output_dir: Output directory for generated files.
        """
        self.output_dir = output_dir
        self.files_created: list[Path] = []
        self.classes_count = 0
        self.properties_count = 0
        self.instances_count = 0

    @property
    def total_pages(self) -> int:
        """Get the total number of pages generated."""
        return len(self.files_created)

    def __str__(self) -> str:
        """Get a summary string."""
        return (
            f"Generated {self.total_pages} files to {self.output_dir}/\n"
            f"  Classes: {self.classes_count}\n"
            f"  Properties: {self.properties_count}\n"
            f"  Instances: {self.instances_count}"
        )


# Public interface from this module
class BaseRenderer:
    """Base class for documentation renderers.

    Subclasses implement format-specific rendering logic.
    """

    def __init__(self, config: DocsConfig) -> None:
        """Initialise the renderer.

        Args:
            config: Documentation configuration.
        """
        self.config = config

    def render_index(self, entities: ExtractedEntities) -> Path:
        """Render the main index page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        raise NotImplementedError

    def render_hierarchy(self, entities: ExtractedEntities) -> Path:
        """Render the class hierarchy page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        raise NotImplementedError

    def render_class(
        self,
        class_info: "ClassInfo",
        entities: ExtractedEntities,
    ) -> Path:
        """Render a class documentation page.

        Args:
            class_info: Class to render.
            entities: All extracted entities (for cross-references).

        Returns:
            Path to the rendered file.
        """
        raise NotImplementedError

    def render_property(
        self,
        prop_info: "PropertyInfo",
        entities: ExtractedEntities,
    ) -> Path:
        """Render a property documentation page.

        Args:
            prop_info: Property to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        raise NotImplementedError

    def render_instance(
        self,
        instance_info: "InstanceInfo",
        entities: ExtractedEntities,
    ) -> Path:
        """Render an instance documentation page.

        Args:
            instance_info: Instance to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        raise NotImplementedError

    def render_namespaces(self, entities: ExtractedEntities) -> Path:
        """Render the namespace reference page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        raise NotImplementedError

    def render_single_page(self, entities: ExtractedEntities) -> Path:
        """Render all documentation as a single page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        raise NotImplementedError

    def copy_assets(self) -> None:
        """Copy static assets (CSS, JS) to the output directory."""
        pass  # Default: no assets to copy


def generate_docs(
    source: Path,
    output_dir: Path | None = None,
    config_path: Path | None = None,
    output_format: str = "html",
) -> GenerationResult:
    """Generate documentation from an RDF file.

    Convenience function for simple documentation generation.

    Args:
        source: Path to RDF source file.
        output_dir: Output directory (overrides config).
        config_path: Path to configuration file.
        output_format: Output format (html, markdown, json).

    Returns:
        GenerationResult with details of generated files.
    """
    config = load_docs_config(config_path)

    if output_dir:
        config.output_dir = output_dir
    if output_format:
        config.format = output_format

    generator = DocsGenerator(config)
    return generator.generate_from_file(source)
