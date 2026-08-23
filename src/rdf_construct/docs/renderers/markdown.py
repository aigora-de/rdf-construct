"""Markdown documentation renderer."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..config import DocsConfig
    from ..extractors import (
        ClassInfo,
        ConceptInfo,
        ConceptNode,
        ConceptSchemeInfo,
        ExtractedEntities,
        InstanceInfo,
        LabelGroup,
        NoteValue,
        PropertyInfo,
        PropertyShapeInfo,
        ShapeInfo,
    )


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
        lines.append(
            self._frontmatter(
                title=entities.ontology.title or "Ontology Documentation",
                layout="default",
            )
        )

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
        if entities.shapes and self.config.include_shapes:
            lines.append(f"- **Shapes:** {len(entities.shapes)}")
        if entities.concepts and self.config.include_skos:
            lines.append(f"- **Concepts:** {len(entities.concepts)}")
        if entities.concept_schemes and self.config.include_skos:
            lines.append(f"- **Concept Schemes:** {len(entities.concept_schemes)}")
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

        # Shapes section (#60). Listed before instances would be (when
        # the existing renderer ever gets that section), reflecting the
        # priority that shapes carry more semantic weight than plain
        # individuals.
        if entities.shapes and self.config.include_shapes:
            lines.append("## Shapes")
            lines.append("")
            for s in entities.shapes:
                link = self._entity_link(s.qname, "shape", s.label or s.qname)
                kind_tags = " ".join(f"`{k}`" for k in s.kinds if k != "shape")
                if kind_tags:
                    lines.append(f"- {link} {kind_tags}")
                else:
                    lines.append(f"- {link}")
            lines.append("")

        # SKOS vocabulary section (#63). Schemes first — they are the
        # containers a reader navigates into.
        if (entities.concepts or entities.concept_schemes) and self.config.include_skos:
            lines.append("## SKOS Vocabulary")
            lines.append("")
            for scheme in entities.concept_schemes:
                link = self._entity_link(
                    scheme.qname, "skos_concept_scheme", scheme.label or scheme.qname
                )
                lines.append(f"- {link} `skos_concept_scheme`")
            for concept in entities.concepts:
                link = self._entity_link(
                    concept.qname, "skos_concept", concept.label or concept.qname
                )
                lines.append(f"- {link} `skos_concept`")
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
            has_internal_parent = any(str(parent) in internal_uris for parent in c.superclasses)
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

        lines.append(
            self._frontmatter(
                title=class_info.label or class_info.qname,
                type="class",
            )
        )

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

        Searches classes, properties, instances, and shapes (in that
        order — most specific match wins). Falls back to the URI's
        local name in code formatting when no entity matches.

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

        # Check if it's a known property
        for p in entities.properties:
            if str(p.uri) == uri_str:
                entity_type = f"{p.property_type}_property"
                return self._entity_link(p.qname, entity_type, p.label or p.qname)

        # Check if it's a known instance
        for i in entities.instances:
            if str(i.uri) == uri_str:
                return self._entity_link(i.qname, "instance", i.label or i.qname)

        # Check if it's a known shape
        for s in entities.shapes:
            if str(s.uri) == uri_str:
                return self._entity_link(s.qname, "shape", s.label or s.qname)

        # Check if it's a known SKOS concept or concept scheme (#63)
        for concept in entities.concepts:
            if str(concept.uri) == uri_str:
                return self._entity_link(
                    concept.qname, "skos_concept", concept.label or concept.qname
                )

        for scheme in entities.concept_schemes:
            if str(scheme.uri) == uri_str:
                return self._entity_link(
                    scheme.qname, "skos_concept_scheme", scheme.label or scheme.qname
                )

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
        lines.append(
            self._frontmatter(
                title=prop_info.label or prop_info.qname,
                type=prop_info.property_type,
            )
        )

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

        lines.append(
            self._frontmatter(
                title=instance_info.label or instance_info.qname,
                type="instance",
            )
        )

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
                pred_name = (
                    str(pred).split("#")[-1] if "#" in str(pred) else str(pred).split("/")[-1]
                )
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

    def _render_label_table(self, labels: list["LabelGroup"]) -> list[str]:
        """Render SKOS labels as a language-per-row Markdown table.

        Returns the table's lines, or an empty list when there are no
        labels (the caller adds surrounding blank lines).
        """
        if not labels:
            return []

        lines = [
            "| Language | Preferred | Alternative | Hidden |",
            "| --- | --- | --- | --- |",
        ]
        for group in labels:
            language = group.language or "—"
            lines.append(
                f"| `{language}` | {', '.join(group.preferred)} "
                f"| {', '.join(group.alternative)} | {', '.join(group.hidden)} |"
            )
        return lines

    def _render_notes_table(self, notes: dict[str, list["NoteValue"]]) -> list[str]:
        """Render the SKOS documentation properties as a Markdown table.

        Language tags are kept alongside the value rather than discarded —
        a French scope note and an English one are different content.
        """
        if not notes:
            return []

        lines = ["| Property | Value |", "| --- | --- |"]
        for name, values in notes.items():
            for value in values:
                text = value.text.replace("|", "\\|")
                tag = f" _({value.language})_" if value.language else ""
                lines.append(f"| `skos:{name}` | {text}{tag} |")
        return lines

    def render_concept(
        self,
        concept_info: "ConceptInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a SKOS concept documentation page.

        Args:
            concept_info: Concept to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        lines = []

        lines.append(
            self._frontmatter(
                title=concept_info.label or concept_info.qname,
                type="skos_concept",
            )
        )

        lines.append(f"# {concept_info.label or concept_info.qname}")
        lines.append("")
        kind_labels = " ".join(f"`{kind}`" for kind in concept_info.kinds)
        if kind_labels:
            lines.append(f"**Kinds:** {kind_labels}")
            lines.append("")
        lines.append(f"**URI:** `{concept_info.uri}`")
        lines.append("")

        if concept_info.definition:
            lines.append(concept_info.definition)
            lines.append("")

        label_table = self._render_label_table(concept_info.labels)
        if label_table:
            lines.append("## Labels")
            lines.append("")
            lines.extend(label_table)
            lines.append("")

        if concept_info.in_schemes or concept_info.top_concept_of:
            lines.append("## Schemes")
            lines.append("")
            if concept_info.in_schemes:
                joined = ", ".join(
                    self._uri_to_display(uri, entities, "skos_concept_scheme")
                    for uri in concept_info.in_schemes
                )
                lines.append(f"- **In scheme:** {joined}")
            if concept_info.top_concept_of:
                joined = ", ".join(
                    self._uri_to_display(uri, entities, "skos_concept_scheme")
                    for uri in concept_info.top_concept_of
                )
                lines.append(f"- **Top concept of:** {joined}")
            lines.append("")

        relations: list[tuple[str, list]] = []
        if concept_info.broader:
            relations.append(("Broader", concept_info.broader))
        if concept_info.narrower:
            relations.append(("Narrower", concept_info.narrower))
        if concept_info.related:
            relations.append(("Related", concept_info.related))
        if relations:
            lines.append("## Semantic Relations")
            lines.append("")
            for label, uris in relations:
                joined = ", ".join(
                    self._uri_to_display(uri, entities, "skos_concept") for uri in uris
                )
                lines.append(f"- **{label}:** {joined}")
            lines.append("")

        notes_table = self._render_notes_table(concept_info.notes)
        if notes_table:
            lines.append("## Notes")
            lines.append("")
            lines.extend(notes_table)
            lines.append("")

        if concept_info.types:
            lines.append("## Types")
            lines.append("")
            for uri in concept_info.types:
                lines.append(f"- {self._uri_to_display(uri, entities)}")
            lines.append("")

        # Mappings (skos:exactMatch and friends) and anything else asserted
        # about the concept — visible rather than dropped.
        if concept_info.properties:
            lines.append("## Other Properties")
            lines.append("")
            for pred, values in concept_info.properties.items():
                pred_name = (
                    str(pred).split("#")[-1] if "#" in str(pred) else str(pred).split("/")[-1]
                )
                for value in values:
                    if isinstance(value, str):
                        lines.append(f"- **{pred_name}:** {value}")
                    else:
                        lines.append(f"- **{pred_name}:** {self._uri_to_display(value, entities)}")
            lines.append("")

        if concept_info.annotations:
            lines.append("## Annotations")
            lines.append("")
            for name, values in concept_info.annotations.items():
                for value in values:
                    lines.append(f"- **{name}:** {value}")
            lines.append("")

        content = "\n".join(lines)
        from ..config import entity_to_path

        rel_path = entity_to_path(concept_info.qname, "skos_concept", self.config, extension=".md")
        return self._write_file(self.config.output_dir / rel_path, content)

    def render_concept_scheme(
        self,
        scheme_info: "ConceptSchemeInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a SKOS concept scheme documentation page.

        Args:
            scheme_info: Concept scheme to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        from ..extractors import build_concept_tree

        lines = []

        lines.append(
            self._frontmatter(
                title=scheme_info.label or scheme_info.qname,
                type="skos_concept_scheme",
            )
        )

        lines.append(f"# {scheme_info.label or scheme_info.qname}")
        lines.append("")
        kind_labels = " ".join(f"`{kind}`" for kind in scheme_info.kinds)
        if kind_labels:
            lines.append(f"**Kinds:** {kind_labels}")
            lines.append("")
        lines.append(f"**URI:** `{scheme_info.uri}`")
        lines.append("")

        if scheme_info.definition:
            lines.append(scheme_info.definition)
            lines.append("")

        label_table = self._render_label_table(scheme_info.labels)
        if label_table:
            lines.append("## Labels")
            lines.append("")
            lines.extend(label_table)
            lines.append("")

        if scheme_info.top_concepts:
            lines.append("## Top Concepts")
            lines.append("")
            for uri in scheme_info.top_concepts:
                lines.append(f"- {self._uri_to_display(uri, entities, 'skos_concept')}")
            lines.append("")

        tree = build_concept_tree(entities.concepts, scheme_info.uri)
        if tree:
            lines.append("## Concept Hierarchy")
            lines.append("")

            def render_tree(nodes: list["ConceptNode"], indent: int = 0) -> None:
                prefix = "  " * indent
                for node in nodes:
                    link = self._entity_link(
                        node.concept.qname,
                        "skos_concept",
                        node.concept.label or node.concept.qname,
                    )
                    lines.append(f"{prefix}- {link}")
                    if node.children:
                        render_tree(node.children, indent + 1)

            render_tree(tree)
            lines.append("")

        if scheme_info.concepts:
            lines.append("## Concepts in this Scheme")
            lines.append("")
            for uri in scheme_info.concepts:
                lines.append(f"- {self._uri_to_display(uri, entities, 'skos_concept')}")
            lines.append("")

        notes_table = self._render_notes_table(scheme_info.notes)
        if notes_table:
            lines.append("## Notes")
            lines.append("")
            lines.extend(notes_table)
            lines.append("")

        if scheme_info.properties:
            lines.append("## Other Properties")
            lines.append("")
            for pred, values in scheme_info.properties.items():
                pred_name = (
                    str(pred).split("#")[-1] if "#" in str(pred) else str(pred).split("/")[-1]
                )
                for value in values:
                    if isinstance(value, str):
                        lines.append(f"- **{pred_name}:** {value}")
                    else:
                        lines.append(f"- **{pred_name}:** {self._uri_to_display(value, entities)}")
            lines.append("")

        if scheme_info.annotations:
            lines.append("## Annotations")
            lines.append("")
            for name, values in scheme_info.annotations.items():
                for value in values:
                    lines.append(f"- **{name}:** {value}")
            lines.append("")

        content = "\n".join(lines)
        from ..config import entity_to_path

        rel_path = entity_to_path(
            scheme_info.qname,
            "skos_concept_scheme",
            self.config,
            extension=".md",
        )
        return self._write_file(self.config.output_dir / rel_path, content)

    def _render_property_shape_table(
        self,
        ps: "PropertyShapeInfo",
        entities: "ExtractedEntities",
    ) -> list[str]:
        """Render a PropertyShape's constraints as a Markdown table.

        Output is a GFM 2-column table (constraint -> value). Only
        populated first-class fields are included; long-tail SHACL
        predicates from ``other_constraints`` get a generic key-value
        row each so they remain visible without per-predicate template
        work.

        Returns the lines of the table (no trailing blank line — caller
        adds spacing).
        """
        rows: list[tuple[str, str]] = []

        if ps.path is not None:
            # Try to resolve to a known property for a clickable link.
            display = self._uri_to_display(ps.path, entities)
            rows.append(("Path", display))
        if ps.name:
            rows.append(("Name", ps.name))
        if ps.description:
            rows.append(("Description", ps.description))
        if ps.datatype is not None:
            rows.append(("Datatype", f"`{ps.datatype}`"))
        if ps.class_ is not None:
            rows.append(("Class", self._uri_to_display(ps.class_, entities)))
        if ps.node_kind is not None:
            rows.append(("Node Kind", f"`{ps.node_kind}`"))
        if ps.min_count is not None:
            rows.append(("Min Count", str(ps.min_count)))
        if ps.max_count is not None:
            rows.append(("Max Count", str(ps.max_count)))
        if ps.min_length is not None:
            rows.append(("Min Length", str(ps.min_length)))
        if ps.max_length is not None:
            rows.append(("Max Length", str(ps.max_length)))
        if ps.min_inclusive is not None:
            rows.append(("Min Inclusive", str(ps.min_inclusive)))
        if ps.max_inclusive is not None:
            rows.append(("Max Inclusive", str(ps.max_inclusive)))
        if ps.pattern is not None:
            rows.append(("Pattern", f"`{ps.pattern}`"))
        if ps.has_value is not None:
            rows.append(("Has Value", f"`{ps.has_value}`"))
        if ps.in_values:
            joined = ", ".join(f"`{v}`" for v in ps.in_values)
            rows.append(("In", joined))

        # Long-tail fallback
        for pred, vals in ps.other_constraints.items():
            joined = ", ".join(f"`{v}`" for v in vals)
            rows.append((f"`{pred}`", joined))

        if not rows:
            return []

        lines = ["| Constraint | Value |", "| --- | --- |"]
        for k, v in rows:
            # Pipe characters in cell values would break the table layout.
            v_safe = v.replace("|", "\\|")
            lines.append(f"| {k} | {v_safe} |")
        return lines

    def render_shape(
        self,
        shape_info: "ShapeInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a SHACL shape documentation page.

        Renders both NodeShapes and named PropertyShapes from the same
        method (the kind in the frontmatter and the section headings
        differ).

        Args:
            shape_info: Shape to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        lines = []

        # Frontmatter — pick the most-specific kind for the type field
        # so static-site generators can filter on it.
        primary = "shape"
        if "node_shape" in shape_info.kinds:
            primary = "node_shape"
        elif "property_shape" in shape_info.kinds:
            primary = "property_shape"
        lines.append(
            self._frontmatter(
                title=shape_info.label or shape_info.qname,
                type=primary,
            )
        )

        lines.append(f"# {shape_info.label or shape_info.qname}")
        lines.append("")
        # All kinds as a Markdown badge-style line, mirroring HTML output.
        kind_labels = " ".join(f"`{kind}`" for kind in shape_info.kinds if kind != "shape")
        if kind_labels:
            lines.append(f"**Kinds:** {kind_labels}")
            lines.append("")
        lines.append(f"**URI:** `{shape_info.uri}`")
        lines.append("")

        if shape_info.definition:
            lines.append(shape_info.definition)
            lines.append("")

        # Targets
        target_rows: list[tuple[str, list]] = []
        if shape_info.target_classes:
            target_rows.append(("Target class", shape_info.target_classes))
        if shape_info.target_nodes:
            target_rows.append(("Target node", shape_info.target_nodes))
        if shape_info.target_subjects_of:
            target_rows.append(("Target subjects of", shape_info.target_subjects_of))
        if shape_info.target_objects_of:
            target_rows.append(("Target objects of", shape_info.target_objects_of))
        if target_rows:
            lines.append("## Targets")
            lines.append("")
            for label, uris in target_rows:
                joined = ", ".join(self._uri_to_display(u, entities) for u in uris)
                lines.append(f"- **{label}:** {joined}")
            lines.append("")

        # NodeShape structural fields
        if "node_shape" in shape_info.kinds:
            structure_rows: list[str] = []
            if shape_info.closed:
                structure_rows.append("- **Closed:** true")
            if shape_info.ignored_properties:
                joined = ", ".join(f"`{u}`" for u in shape_info.ignored_properties)
                structure_rows.append(f"- **Ignored properties:** {joined}")
            if structure_rows:
                lines.append("## Structure")
                lines.append("")
                lines.extend(structure_rows)
                lines.append("")

            # Property arcs
            if shape_info.properties:
                lines.append("## Property Constraints")
                lines.append("")
                for ps in shape_info.properties:
                    if ps.is_blank:
                        # Heading: the property path if available, else a placeholder.
                        if ps.path is not None:
                            heading = self._uri_to_display(ps.path, entities)
                        else:
                            heading = "_(blank-node constraint)_"
                        lines.append(f"### {heading}")
                    else:
                        # Named PropertyShape — link to its standalone page.
                        link = self._entity_link(
                            ps.qname or "",
                            "shape",
                            ps.name or ps.qname or "",
                        )
                        lines.append(f"### {link} `property_shape`")
                    lines.append("")
                    table_lines = self._render_property_shape_table(ps, entities)
                    if table_lines:
                        lines.extend(table_lines)
                    lines.append("")

        # PropertyShape constraints (when the top-level shape is itself a PropertyShape)
        if "property_shape" in shape_info.kinds and shape_info.property_shape is not None:
            lines.append("## Constraints")
            lines.append("")
            table_lines = self._render_property_shape_table(shape_info.property_shape, entities)
            if table_lines:
                lines.extend(table_lines)
            lines.append("")

        # Long-tail SHACL predicates at the top level
        if shape_info.other_constraints:
            lines.append("## Other Constraints")
            lines.append("")
            lines.append("| Predicate | Value |")
            lines.append("| --- | --- |")
            for pred, vals in shape_info.other_constraints.items():
                joined = ", ".join(f"`{v}`" for v in vals)
                lines.append(f"| `{pred}` | {joined} |")
            lines.append("")

        # Annotations
        if shape_info.annotations:
            lines.append("## Annotations")
            lines.append("")
            for name, values in shape_info.annotations.items():
                for value in values:
                    lines.append(f"- **{name}:** {value}")
            lines.append("")

        content = "\n".join(lines)
        from ..config import entity_to_path

        rel_path = entity_to_path(shape_info.qname, "shape", self.config, extension=".md")
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

        lines.append(
            self._frontmatter(
                title=entities.ontology.title or "Ontology Documentation",
            )
        )

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
        if entities.shapes and self.config.include_shapes:
            lines.append("- [Shapes](#shapes)")
        if (entities.concepts or entities.concept_schemes) and self.config.include_skos:
            lines.append("- [SKOS Vocabulary](#skos-vocabulary)")
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

        # Shapes (#60)
        if entities.shapes and self.config.include_shapes:
            lines.append("## Shapes")
            lines.append("")
            for s in entities.shapes:
                lines.append(f"### {s.label or s.qname}")
                lines.append("")
                kind_tags = " ".join(f"`{k}`" for k in s.kinds if k != "shape")
                if kind_tags:
                    lines.append(f"**Kinds:** {kind_tags}")
                    lines.append("")
                lines.append(f"**URI:** `{s.uri}`")
                lines.append("")
                if s.definition:
                    lines.append(s.definition)
                    lines.append("")
                if s.target_classes:
                    joined = ", ".join(self._uri_to_display(u, entities) for u in s.target_classes)
                    lines.append(f"**Target classes:** {joined}")
                    lines.append("")
                if "node_shape" in s.kinds and s.properties:
                    lines.append(f"**Property constraints:** {len(s.properties)}")
                    lines.append("")

        # SKOS vocabulary (#63)
        if (entities.concepts or entities.concept_schemes) and self.config.include_skos:
            lines.append("## SKOS Vocabulary")
            lines.append("")
            for scheme in entities.concept_schemes:
                lines.append(f"### {scheme.label or scheme.qname}")
                lines.append("")
                lines.append("**Kinds:** `skos_concept_scheme`")
                lines.append("")
                lines.append(f"**URI:** `{scheme.uri}`")
                lines.append("")
                if scheme.definition:
                    lines.append(scheme.definition)
                    lines.append("")
                if scheme.concepts:
                    lines.append(f"**Concepts:** {len(scheme.concepts)}")
                    lines.append("")
            for concept in entities.concepts:
                lines.append(f"### {concept.label or concept.qname}")
                lines.append("")
                kind_tags = " ".join(f"`{kind}`" for kind in concept.kinds)
                lines.append(f"**Kinds:** {kind_tags}")
                lines.append("")
                lines.append(f"**URI:** `{concept.uri}`")
                lines.append("")
                if concept.definition:
                    lines.append(concept.definition)
                    lines.append("")
                if concept.broader:
                    joined = ", ".join(
                        self._uri_to_display(uri, entities, "skos_concept")
                        for uri in concept.broader
                    )
                    lines.append(f"**Broader:** {joined}")
                    lines.append("")
                if concept.narrower:
                    joined = ", ".join(
                        self._uri_to_display(uri, entities, "skos_concept")
                        for uri in concept.narrower
                    )
                    lines.append(f"**Narrower:** {joined}")
                    lines.append("")
                if concept.in_schemes:
                    joined = ", ".join(
                        self._uri_to_display(uri, entities, "skos_concept_scheme")
                        for uri in concept.in_schemes
                    )
                    lines.append(f"**In scheme:** {joined}")
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
