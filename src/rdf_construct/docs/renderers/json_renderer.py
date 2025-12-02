"""JSON documentation renderer for structured data output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..config import DocsConfig
    from ..extractors import ClassInfo, ExtractedEntities, InstanceInfo, PropertyInfo


class JSONRenderer:
    """Renders ontology documentation as structured JSON files.

    Produces machine-readable JSON that can be consumed by custom
    renderers, APIs, or documentation systems.
    """

    def __init__(self, config: "DocsConfig") -> None:
        """Initialise the JSON renderer.

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

    def _write_json(self, path: Path, data: Any) -> Path:
        """Write JSON data to a file.

        Args:
            path: Output path.
            data: Data to serialise.

        Returns:
            Path to the written file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return path

    def _class_to_dict(self, class_info: "ClassInfo") -> dict[str, Any]:
        """Convert a ClassInfo to a dictionary.

        Args:
            class_info: Class to convert.

        Returns:
            Dictionary representation.
        """
        return {
            "uri": str(class_info.uri),
            "qname": class_info.qname,
            "label": class_info.label,
            "definition": class_info.definition,
            "superclasses": [str(uri) for uri in class_info.superclasses],
            "subclasses": [str(uri) for uri in class_info.subclasses],
            "domain_of": [self._property_to_dict(p) for p in class_info.domain_of],
            "range_of": [self._property_to_dict(p) for p in class_info.range_of],
            "instances": [str(uri) for uri in class_info.instances],
            "disjoint_with": [str(uri) for uri in class_info.disjoint_with],
            "equivalent_to": [str(uri) for uri in class_info.equivalent_to],
            "annotations": class_info.annotations,
        }

    def _property_to_dict(self, prop_info: "PropertyInfo") -> dict[str, Any]:
        """Convert a PropertyInfo to a dictionary.

        Args:
            prop_info: Property to convert.

        Returns:
            Dictionary representation.
        """
        return {
            "uri": str(prop_info.uri),
            "qname": prop_info.qname,
            "label": prop_info.label,
            "definition": prop_info.definition,
            "property_type": prop_info.property_type,
            "domain": [str(uri) for uri in prop_info.domain],
            "range": [str(uri) for uri in prop_info.range],
            "superproperties": [str(uri) for uri in prop_info.superproperties],
            "subproperties": [str(uri) for uri in prop_info.subproperties],
            "is_functional": prop_info.is_functional,
            "is_inverse_functional": prop_info.is_inverse_functional,
            "inverse_of": str(prop_info.inverse_of) if prop_info.inverse_of else None,
            "annotations": prop_info.annotations,
        }

    def _instance_to_dict(self, instance_info: "InstanceInfo") -> dict[str, Any]:
        """Convert an InstanceInfo to a dictionary.

        Args:
            instance_info: Instance to convert.

        Returns:
            Dictionary representation.
        """
        # Convert properties to serialisable format
        properties: dict[str, list[str]] = {}
        for pred, values in instance_info.properties.items():
            pred_str = str(pred)
            properties[pred_str] = [str(v) for v in values]

        return {
            "uri": str(instance_info.uri),
            "qname": instance_info.qname,
            "label": instance_info.label,
            "definition": instance_info.definition,
            "types": [str(uri) for uri in instance_info.types],
            "properties": properties,
            "annotations": instance_info.annotations,
        }

    def _ontology_to_dict(self, entities: "ExtractedEntities") -> dict[str, Any]:
        """Convert ontology info to a dictionary.

        Args:
            entities: All extracted entities.

        Returns:
            Dictionary representation.
        """
        onto = entities.ontology
        return {
            "uri": str(onto.uri) if onto.uri else None,
            "title": onto.title,
            "description": onto.description,
            "version": onto.version,
            "creators": onto.creators,
            "contributors": onto.contributors,
            "imports": [str(uri) for uri in onto.imports],
            "namespaces": onto.namespaces,
            "annotations": onto.annotations,
        }

    def render_index(self, entities: "ExtractedEntities") -> Path:
        """Render the main index as JSON.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        data = {
            "ontology": self._ontology_to_dict(entities),
            "statistics": {
                "classes": len(entities.classes),
                "object_properties": len(entities.object_properties),
                "datatype_properties": len(entities.datatype_properties),
                "annotation_properties": len(entities.annotation_properties),
                "instances": len(entities.instances),
            },
            "classes": [
                {
                    "uri": str(c.uri),
                    "qname": c.qname,
                    "label": c.label,
                }
                for c in entities.classes
            ],
            "object_properties": [
                {
                    "uri": str(p.uri),
                    "qname": p.qname,
                    "label": p.label,
                }
                for p in entities.object_properties
            ],
            "datatype_properties": [
                {
                    "uri": str(p.uri),
                    "qname": p.qname,
                    "label": p.label,
                }
                for p in entities.datatype_properties
            ],
            "annotation_properties": [
                {
                    "uri": str(p.uri),
                    "qname": p.qname,
                    "label": p.label,
                }
                for p in entities.annotation_properties
            ],
            "instances": [
                {
                    "uri": str(i.uri),
                    "qname": i.qname,
                    "label": i.label,
                }
                for i in entities.instances
            ],
        }

        return self._write_json(self._get_output_path("index.json"), data)

    def render_hierarchy(self, entities: "ExtractedEntities") -> Path:
        """Render the class hierarchy as JSON.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        hierarchy = self._build_hierarchy_tree(entities.classes)

        def tree_to_json(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                {
                    "uri": str(node["class"].uri),
                    "qname": node["class"].qname,
                    "label": node["class"].label,
                    "children": tree_to_json(node["children"]),
                }
                for node in nodes
            ]

        data = {"hierarchy": tree_to_json(hierarchy)}
        return self._write_json(self._get_output_path("hierarchy.json"), data)

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
        """Render a class as JSON.

        Args:
            class_info: Class to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        data = self._class_to_dict(class_info)

        from ..config import entity_to_path
        rel_path = entity_to_path(class_info.qname, "class", self.config, extension=".json")
        return self._write_json(self.config.output_dir / rel_path, data)

    def render_property(
        self,
        prop_info: "PropertyInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a property as JSON.

        Args:
            prop_info: Property to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        data = self._property_to_dict(prop_info)

        entity_type = f"{prop_info.property_type}_property"
        from ..config import entity_to_path
        rel_path = entity_to_path(prop_info.qname, entity_type, self.config, extension=".json")
        return self._write_json(self.config.output_dir / rel_path, data)

    def render_instance(
        self,
        instance_info: "InstanceInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render an instance as JSON.

        Args:
            instance_info: Instance to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        data = self._instance_to_dict(instance_info)

        from ..config import entity_to_path
        rel_path = entity_to_path(instance_info.qname, "instance", self.config, extension=".json")
        return self._write_json(self.config.output_dir / rel_path, data)

    def render_namespaces(self, entities: "ExtractedEntities") -> Path:
        """Render namespaces as JSON.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        data = {
            "namespaces": entities.ontology.namespaces,
        }
        return self._write_json(self._get_output_path("namespaces.json"), data)

    def render_single_page(self, entities: "ExtractedEntities") -> Path:
        """Render all documentation as a single JSON file.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        data = {
            "ontology": self._ontology_to_dict(entities),
            "classes": [self._class_to_dict(c) for c in entities.classes],
            "object_properties": [
                self._property_to_dict(p) for p in entities.object_properties
            ],
            "datatype_properties": [
                self._property_to_dict(p) for p in entities.datatype_properties
            ],
            "annotation_properties": [
                self._property_to_dict(p) for p in entities.annotation_properties
            ],
            "instances": [
                self._instance_to_dict(i) for i in entities.instances
            ],
        }

        return self._write_json(self._get_output_path("ontology.json"), data)

    def copy_assets(self) -> None:
        """Copy static assets. No assets needed for JSON."""
        pass
