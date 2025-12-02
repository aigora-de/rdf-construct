"""Markdown documentation renderer."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..config import DocsConfig
    from ..extractors import ClassInfo, ExtractedEntities, InstanceInfo, PropertyInfo


class MarkdownRenderer:
    """Renders ontology documentation as Markdown files.

    Generates GitHub/GitLab-compatible Markdown with optional
    Jekyll/Hugo frontmatter.
    """

    def __init__(self, config: "DocsConfig") -> None:
        """Initialise the Markdown renderer.

        Args:
            config: Documentation configuration.
        """
        self.config = config

    def _get_output_path(self, filename: str, subdir: str | None = None) -> Path:
        """Get the full output path for a file.

        Args:
            filename: Name of the file.
            subdir: Optional subdirectory.

        Returns:
            Full output path.
        """
        if subdir:
            path = self.config.output_dir / subdir / filename
        else:
            path = self.config.output_dir / filename

        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _write_file(self, path: Path, content: str) -> Path:
        """Write content to a file.

        Args:
            path: Output path.
            content: Content to write.

        Returns:
            Path to the written file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _entity_link(self, qname: str, entity_type: str, label: str | None = None) -> str:
        """Generate a markdown link to an entity.

        Args:
            qname: Entity qualified name.
            entity_type: Type of entity.
            label: Optional display label.

        Returns:
            Markdown link string.
        """
        from ..config import entity_to_path

        display = label or qname
        path = entity_to_path(qname, entity_type, self.config, extension=".md")
        # Make path relative from root
        return f"[{display}]({path})"

    def _frontmatter(self, **kwargs: Any) -> str:
        """Generate YAML frontmatter.

        Args:
            **kwargs: Frontmatter fields.

        Returns:
            Frontmatter string.
        """
        lines = ["---"]
        for key, value in kwargs.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    def render_index(self, entities: "ExtractedEntities") -> Path:
        """Render the main index page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        lines = []

        # Frontmatter
        lines.append(self._frontmatter(
            title=entities.ontology.title or "Ontology Documentation",
            layout="default",
        ))

        # Header
        lines.append(f"# {entities.ontology.title or 'Ontology Documentation'}")
        lines.append("")

        if entities.ontology.description:
            lines.append(entities.ontology.description)
            lines.append("")

        # Statistics
        lines.append("## Overview")
        lines.append("")
        lines.append(f"- **Classes:** {len(entities.classes)}")
        lines.append(f"- **Object Properties:** {len(entities.object_properties)}")
        lines.append(f"- **Datatype Properties:** {len(entities.datatype_properties)}")
        lines.append(f"- **Annotation Properties:** {len(entities.annotation_properties)}")
        if entities.instances:
            lines.append(f"- **Instances:** {len(entities.instances)}")
        lines.append("")

        # Navigation
        lines.append("## Quick Links")
        lines.append("")
        lines.append("- [Class Hierarchy](hierarchy.md)")
        lines.append("- [Namespaces](namespaces.md)")
        lines.append("")

        # Classes section
        if entities.classes:
            lines.append("## Classes")
            lines.append("")
            for c in entities.classes:
                link = self._entity_link(c.qname, "class", c.label or c.qname)
                if c.definition:
                    # Truncate long definitions
                    desc = c.definition[:100] + "..." if len(c.definition) > 100 else c.definition
                    lines.append(f"- {link} — {desc}")
                else:
                    lines.append(f"- {link}")
            lines.append("")

        # Properties section
        if entities.object_properties:
            lines.append("## Object Properties")
            lines.append("")
            for p in entities.object_properties:
                link = self._entity_link(p.qname, "object_property", p.label or p.qname)
                lines.append(f"- {link}")
            lines.append("")

        if entities.datatype_properties:
            lines.append("## Datatype Properties")
            lines.append("")
            for p in entities.datatype_properties:
                link = self._entity_link(p.qname, "datatype_property", p.label or p.qname)
                lines.append(f"- {link}")
            lines.append("")

        content = "\n".join(lines)
        return self._write_file(self._get_output_path("index.md"), content)

    def render_hierarchy(self, entities: "ExtractedEntities") -> Path:
        """Render the class hierarchy page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        lines = []

        lines.append(self._frontmatter(title="Class Hierarchy"))
        lines.append("# Class Hierarchy")
        lines.append("")

        # Build and render tree
        hierarchy = self._build_hierarchy_tree(entities.classes)

        def render_tree(nodes: list[dict[str, Any]], indent: int = 0) -> None:
            prefix = "  " * indent
            for node in nodes:
                c = node["class"]
                link = self._entity_link(c.qname, "class", c.label or c.qname)
                lines.append(f"{prefix}- {link}")
                if node["children"]:
                    render_tree(node["children"], indent + 1)

        render_tree(hierarchy)
        lines.append("")

        content = "\n".join(lines)
        return self._write_file(self._get_output_path("hierarchy.md"), content)

    def _build_hierarchy_tree(
        self,
        classes: list["ClassInfo"],
    ) -> list[dict[str, Any]]:
        """Build a tree structure for the class hierarchy.

        Args:
            classes: List of all classes.

        Returns:
            Nested list structure representing the hierarchy.
        """
        class_by_uri = {str(c.uri): c for c in classes}
        internal_uris = set(class_by_uri.keys())
        root_classes = []

        for c in classes:
            has_internal_parent = any(
                str(parent) in internal_uris for parent in c.superclasses
            )
            if not has_internal_parent:
                root_classes.append(c)

        def build_node(class_info: "ClassInfo") -> dict[str, Any]:
            children = []
            for child_uri in class_info.subclasses:
                child_key = str(child_uri)
                if child_key in class_by_uri:
                    children.append(build_node(class_by_uri[child_key]))

            return {
                "class": class_info,
                "children": sorted(children, key=lambda n: n["class"].qname),
            }

        return sorted(
            [build_node(c) for c in root_classes],
            key=lambda n: n["class"].qname,
        )

    def render_class(
        self,
        class_info: "ClassInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a class documentation page.

        Args:
            class_info: Class to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        lines = []

        lines.append(self._frontmatter(
            title=class_info.label or class_info.qname,
            type="class",
        ))

        lines.append(f"# {class_info.label or class_info.qname}")
        lines.append("")
        lines.append(f"**URI:** `{class_info.uri}`")
        lines.append("")

        if class_info.definition:
            lines.append(class_info.definition)
            lines.append("")

        # Superclasses
        if class_info.superclasses:
            lines.append("## Superclasses")
            lines.append("")
            for uri in class_info.superclasses:
                # Try to make a link if we have this class
                qname = self._uri_to_display(uri, entities)
                lines.append(f"- {qname}")
            lines.append("")

        # Subclasses
        if class_info.subclasses:
            lines.append("## Subclasses")
            lines.append("")
            for uri in class_info.subclasses:
                qname = self._uri_to_display(uri, entities)
                lines.append(f"- {qname}")
            lines.append("")

        # Domain of (properties where this is domain)
        if class_info.domain_of:
            lines.append("## Properties")
            lines.append("")
            for p in class_info.domain_of:
                link = self._entity_link(p.qname, f"{p.property_type}_property")
                lines.append(f"- {link}")
            lines.append("")

        # Range of (properties where this is range)
        if class_info.range_of:
            lines.append("## Used as Range")
            lines.append("")
            for p in class_info.range_of:
                link = self._entity_link(p.qname, f"{p.property_type}_property")
                lines.append(f"- {link}")
            lines.append("")

        # Instances
        if class_info.instances:
            lines.append("## Instances")
            lines.append("")
            for uri in class_info.instances:
                qname = self._uri_to_display(uri, entities, "instance")
                lines.append(f"- {qname}")
            lines.append("")

        # Annotations
        if class_info.annotations:
            lines.append("## Annotations")
            lines.append("")
            for name, values in class_info.annotations.items():
                for value in values:
                    lines.append(f"- **{name}:** {value}")
            lines.append("")

        content = "\n".join(lines)
        from ..config import entity_to_path
        rel_path = entity_to_path(class_info.qname, "class", self.config, extension=".md")
        return self._write_file(self.config.output_dir / rel_path, content)

    def _uri_to_display(
        self,
        uri: Any,
        entities: "ExtractedEntities",
        default_type: str = "class",
    ) -> str:
        """Convert a URI to a display string, linking if possible.

        Args:
            uri: URI to convert.
            entities: All entities for lookups.
            default_type: Entity type if not found.

        Returns:
            Display string with link if available.
        """
        uri_str = str(uri)

        # Check if it's a known class
        for c in entities.classes:
            if str(c.uri) == uri_str:
                return self._entity_link(c.qname, "class", c.label or c.qname)

        # Check if it's a known instance
        for i in entities.instances:
            if str(i.uri) == uri_str:
                return self._entity_link(i.qname, "instance", i.label or i.qname)

        # Fall back to extracting local name
        if "#" in uri_str:
            return f"`{uri_str.split('#')[-1]}`"
        elif "/" in uri_str:
            return f"`{uri_str.split('/')[-1]}`"
        return f"`{uri_str}`"

    def render_property(
        self,
        prop_info: "PropertyInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a property documentation page.

        Args:
            prop_info: Property to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        lines = []

        type_label = prop_info.property_type.replace("_", " ").title()
        lines.append(self._frontmatter(
            title=prop_info.label or prop_info.qname,
            type=prop_info.property_type,
        ))

        lines.append(f"# {prop_info.label or prop_info.qname}")
        lines.append("")
        lines.append(f"**Type:** {type_label} Property")
        lines.append("")
        lines.append(f"**URI:** `{prop_info.uri}`")
        lines.append("")

        if prop_info.definition:
            lines.append(prop_info.definition)
            lines.append("")

        # Domain
        if prop_info.domain:
            lines.append("## Domain")
            lines.append("")
            for uri in prop_info.domain:
                display = self._uri_to_display(uri, entities)
                lines.append(f"- {display}")
            lines.append("")

        # Range
        if prop_info.range:
            lines.append("## Range")
            lines.append("")
            for uri in prop_info.range:
                display = self._uri_to_display(uri, entities)
                lines.append(f"- {display}")
            lines.append("")

        # Characteristics
        characteristics = []
        if prop_info.is_functional:
            characteristics.append("Functional")
        if prop_info.is_inverse_functional:
            characteristics.append("Inverse Functional")
        if prop_info.inverse_of:
            inv_display = self._uri_to_display(prop_info.inverse_of, entities)
            characteristics.append(f"Inverse of {inv_display}")

        if characteristics:
            lines.append("## Characteristics")
            lines.append("")
            for char in characteristics:
                lines.append(f"- {char}")
            lines.append("")

        # Super/subproperties
        if prop_info.superproperties:
            lines.append("## Superproperties")
            lines.append("")
            for uri in prop_info.superproperties:
                lines.append(f"- `{uri}`")
            lines.append("")

        if prop_info.subproperties:
            lines.append("## Subproperties")
            lines.append("")
            for uri in prop_info.subproperties:
                lines.append(f"- `{uri}`")
            lines.append("")

        content = "\n".join(lines)
        entity_type = f"{prop_info.property_type}_property"
        from ..config import entity_to_path
        rel_path = entity_to_path(prop_info.qname, entity_type, self.config, extension=".md")
        return self._write_file(self.config.output_dir / rel_path, content)

    def render_instance(
        self,
        instance_info: "InstanceInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render an instance documentation page.

        Args:
            instance_info: Instance to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        lines = []

        lines.append(self._frontmatter(
            title=instance_info.label or instance_info.qname,
            type="instance",
        ))

        lines.append(f"# {instance_info.label or instance_info.qname}")
        lines.append("")
        lines.append(f"**URI:** `{instance_info.uri}`")
        lines.append("")

        if instance_info.definition:
            lines.append(instance_info.definition)
            lines.append("")

        # Types
        if instance_info.types:
            lines.append("## Types")
            lines.append("")
            for uri in instance_info.types:
                display = self._uri_to_display(uri, entities)
                lines.append(f"- {display}")
            lines.append("")

        # Properties
        if instance_info.properties:
            lines.append("## Properties")
            lines.append("")
            for pred, values in instance_info.properties.items():
                pred_name = str(pred).split("#")[-1] if "#" in str(pred) else str(pred).split("/")[-1]
                for value in values:
                    if isinstance(value, str):
                        lines.append(f"- **{pred_name}:** {value}")
                    else:
                        display = self._uri_to_display(value, entities)
                        lines.append(f"- **{pred_name}:** {display}")
            lines.append("")

        content = "\n".join(lines)
        from ..config import entity_to_path
        rel_path = entity_to_path(instance_info.qname, "instance", self.config, extension=".md")
        return self._write_file(self.config.output_dir / rel_path, content)

    def render_namespaces(self, entities: "ExtractedEntities") -> Path:
        """Render the namespace reference page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        lines = []

        lines.append(self._frontmatter(title="Namespaces"))
        lines.append("# Namespaces")
        lines.append("")

        if entities.ontology.namespaces:
            lines.append("| Prefix | Namespace |")
            lines.append("|--------|-----------|")
            for prefix, namespace in sorted(entities.ontology.namespaces.items()):
                lines.append(f"| `{prefix}` | `{namespace}` |")
            lines.append("")

        content = "\n".join(lines)
        return self._write_file(self._get_output_path("namespaces.md"), content)

    def render_single_page(self, entities: "ExtractedEntities") -> Path:
        """Render all documentation as a single page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        lines = []

        lines.append(self._frontmatter(
            title=entities.ontology.title or "Ontology Documentation",
        ))

        # Header
        lines.append(f"# {entities.ontology.title or 'Ontology Documentation'}")
        lines.append("")

        if entities.ontology.description:
            lines.append(entities.ontology.description)
            lines.append("")

        # TOC
        lines.append("## Table of Contents")
        lines.append("")
        lines.append("- [Classes](#classes)")
        lines.append("- [Object Properties](#object-properties)")
        lines.append("- [Datatype Properties](#datatype-properties)")
        lines.append("- [Namespaces](#namespaces)")
        lines.append("")

        # Classes
        lines.append("## Classes")
        lines.append("")
        for c in entities.classes:
            lines.append(f"### {c.label or c.qname}")
            lines.append("")
            lines.append(f"**URI:** `{c.uri}`")
            lines.append("")
            if c.definition:
                lines.append(c.definition)
                lines.append("")

        # Properties
        lines.append("## Object Properties")
        lines.append("")
        for p in entities.object_properties:
            lines.append(f"### {p.label or p.qname}")
            lines.append("")
            lines.append(f"**URI:** `{p.uri}`")
            lines.append("")
            if p.definition:
                lines.append(p.definition)
                lines.append("")

        lines.append("## Datatype Properties")
        lines.append("")
        for p in entities.datatype_properties:
            lines.append(f"### {p.label or p.qname}")
            lines.append("")
            lines.append(f"**URI:** `{p.uri}`")
            lines.append("")
            if p.definition:
                lines.append(p.definition)
                lines.append("")

        # Namespaces
        lines.append("## Namespaces")
        lines.append("")
        if entities.ontology.namespaces:
            lines.append("| Prefix | Namespace |")
            lines.append("|--------|-----------|")
            for prefix, namespace in sorted(entities.ontology.namespaces.items()):
                lines.append(f"| `{prefix}` | `{namespace}` |")
            lines.append("")

        content = "\n".join(lines)
        return self._write_file(self._get_output_path("index.md"), content)

    def copy_assets(self) -> None:
        """Copy static assets. No assets needed for Markdown."""
        pass
