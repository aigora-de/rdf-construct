"""JSON documentation renderer for structured data output."""

from __future__ import annotations

import json
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
            "kinds": [str(k) for k in class_info.kinds],
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
            "kinds": [str(k) for k in prop_info.kinds],
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
            "kinds": [str(k) for k in instance_info.kinds],
            "label": instance_info.label,
            "definition": instance_info.definition,
            "types": [str(uri) for uri in instance_info.types],
            "properties": properties,
            "annotations": instance_info.annotations,
        }

    def _property_shape_to_dict(
        self,
        ps: "PropertyShapeInfo",
    ) -> dict[str, Any]:
        """Convert a PropertyShapeInfo to a dictionary.

        Schema is stable for downstream consumers (#60). Naming choices:
        ``class`` (matches the SHACL spec key) instead of the dataclass
        field ``class_`` which was renamed for Python keyword reasons;
        ``in_values`` (more readable in JSON than ``in`` and avoids the
        keyword issue at the consumer end too).

        Args:
            ps: PropertyShape info.

        Returns:
            Dictionary representation.
        """
        return {
            "uri": str(ps.uri) if ps.uri is not None else None,
            "qname": ps.qname,
            "is_blank": ps.is_blank,
            "path": str(ps.path) if ps.path is not None else None,
            "name": ps.name,
            "description": ps.description,
            "datatype": str(ps.datatype) if ps.datatype is not None else None,
            "class": str(ps.class_) if ps.class_ is not None else None,
            "node_kind": str(ps.node_kind) if ps.node_kind is not None else None,
            "min_count": ps.min_count,
            "max_count": ps.max_count,
            "min_length": ps.min_length,
            "max_length": ps.max_length,
            "min_inclusive": ps.min_inclusive,
            "max_inclusive": ps.max_inclusive,
            "pattern": ps.pattern,
            "has_value": str(ps.has_value) if ps.has_value is not None else None,
            "in_values": [str(v) for v in ps.in_values],
            "other_constraints": {
                str(pred): [str(v) for v in vals] for pred, vals in ps.other_constraints.items()
            },
        }

    def _shape_to_dict(self, shape_info: "ShapeInfo") -> dict[str, Any]:
        """Convert a ShapeInfo to a dictionary.

        Args:
            shape_info: Shape to convert.

        Returns:
            Dictionary representation.
        """
        return {
            "uri": str(shape_info.uri),
            "qname": shape_info.qname,
            "kinds": [str(k) for k in shape_info.kinds],
            "label": shape_info.label,
            "definition": shape_info.definition,
            "target_classes": [str(uri) for uri in shape_info.target_classes],
            "target_nodes": [str(uri) for uri in shape_info.target_nodes],
            "target_subjects_of": [str(uri) for uri in shape_info.target_subjects_of],
            "target_objects_of": [str(uri) for uri in shape_info.target_objects_of],
            "closed": shape_info.closed,
            "ignored_properties": [str(uri) for uri in shape_info.ignored_properties],
            "properties": [self._property_shape_to_dict(ps) for ps in shape_info.properties],
            "property_shape": (
                self._property_shape_to_dict(shape_info.property_shape)
                if shape_info.property_shape is not None
                else None
            ),
            "annotations": shape_info.annotations,
            "other_constraints": {
                str(pred): [str(v) for v in vals]
                for pred, vals in shape_info.other_constraints.items()
            },
        }

    def _label_groups_to_list(self, labels: list["LabelGroup"]) -> list[dict[str, Any]]:
        """Convert SKOS label groups to a serialisable list.

        One entry per language tag; the untagged group carries an empty
        ``language`` string rather than being dropped.
        """
        return [
            {
                "language": group.language,
                "preferred": list(group.preferred),
                "alternative": list(group.alternative),
                "hidden": list(group.hidden),
            }
            for group in labels
        ]

    def _notes_to_dict(
        self,
        notes: dict[str, list["NoteValue"]],
    ) -> dict[str, list[dict[str, str]]]:
        """Convert SKOS notes to a serialisable mapping.

        Each value keeps its language tag, so a consumer can tell an
        English scope note from a French one.
        """
        return {
            name: [{"text": value.text, "language": value.language} for value in values]
            for name, values in notes.items()
        }

    def _concept_to_dict(self, concept_info: "ConceptInfo") -> dict[str, Any]:
        """Convert a ConceptInfo to a dictionary.

        ``broader`` and ``narrower`` carry both asserted and inverse-derived
        neighbours — SKOS declares the two properties to be inverses, so a
        consumer sees the same hierarchy whichever direction the source
        vocabulary asserted.

        Args:
            concept_info: Concept to convert.

        Returns:
            Dictionary representation.
        """
        properties: dict[str, list[str]] = {}
        for pred, values in concept_info.properties.items():
            properties[str(pred)] = [str(v) for v in values]

        return {
            "uri": str(concept_info.uri),
            "qname": concept_info.qname,
            "kinds": [str(k) for k in concept_info.kinds],
            "label": concept_info.label,
            "definition": concept_info.definition,
            "labels": self._label_groups_to_list(concept_info.labels),
            "notes": self._notes_to_dict(concept_info.notes),
            "broader": [str(uri) for uri in concept_info.broader],
            "narrower": [str(uri) for uri in concept_info.narrower],
            "related": [str(uri) for uri in concept_info.related],
            "in_schemes": [str(uri) for uri in concept_info.in_schemes],
            "top_concept_of": [str(uri) for uri in concept_info.top_concept_of],
            "types": [str(uri) for uri in concept_info.types],
            "properties": properties,
            "annotations": concept_info.annotations,
        }

    def _concept_scheme_to_dict(self, scheme_info: "ConceptSchemeInfo") -> dict[str, Any]:
        """Convert a ConceptSchemeInfo to a dictionary.

        Args:
            scheme_info: Concept scheme to convert.

        Returns:
            Dictionary representation.
        """
        properties: dict[str, list[str]] = {}
        for pred, values in scheme_info.properties.items():
            properties[str(pred)] = [str(v) for v in values]

        return {
            "uri": str(scheme_info.uri),
            "qname": scheme_info.qname,
            "kinds": [str(k) for k in scheme_info.kinds],
            "label": scheme_info.label,
            "definition": scheme_info.definition,
            "labels": self._label_groups_to_list(scheme_info.labels),
            "notes": self._notes_to_dict(scheme_info.notes),
            "top_concepts": [str(uri) for uri in scheme_info.top_concepts],
            "concepts": [str(uri) for uri in scheme_info.concepts],
            "types": [str(uri) for uri in scheme_info.types],
            "properties": properties,
            "annotations": scheme_info.annotations,
        }

    def _concept_tree_to_json(self, nodes: list["ConceptNode"]) -> list[dict[str, Any]]:
        """Convert a concept hierarchy tree to nested dictionaries."""
        return [
            {
                "uri": str(node.concept.uri),
                "qname": node.concept.qname,
                "label": node.concept.label,
                "children": self._concept_tree_to_json(node.children),
            }
            for node in nodes
        ]

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
                "shapes": len(entities.shapes),
                "concepts": len(entities.concepts),
                "concept_schemes": len(entities.concept_schemes),
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
            # Top-level shapes array (#60). Breaking change from v0.4.x:
            # shapes used to appear in the 'instances' array because the
            # extractor didn't filter them out; they're now their own
            # bucket. Each entry includes the multi-kind list so
            # consumers can distinguish NodeShape, PropertyShape, and
            # any further kinds added in later milestone stages.
            "shapes": [
                {
                    "uri": str(s.uri),
                    "qname": s.qname,
                    "kinds": [str(k) for k in s.kinds],
                    "label": s.label,
                }
                for s in entities.shapes
            ],
            # Top-level concepts / concept_schemes arrays (#63). Breaking
            # change from v0.5.x, in the same way the shapes array was in
            # v0.5.0: SKOS entities used to appear in 'instances' and now
            # have their own buckets.
            "concepts": [
                {
                    "uri": str(c.uri),
                    "qname": c.qname,
                    "kinds": [str(k) for k in c.kinds],
                    "label": c.label,
                }
                for c in entities.concepts
            ],
            "concept_schemes": [
                {
                    "uri": str(s.uri),
                    "qname": s.qname,
                    "kinds": [str(k) for k in s.kinds],
                    "label": s.label,
                }
                for s in entities.concept_schemes
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

    def render_shape(
        self,
        shape_info: "ShapeInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a SHACL shape as JSON.

        The full shape representation is documented in the docstring of
        :meth:`_shape_to_dict`. NodeShapes and named PropertyShapes are
        both rendered through this method; the ``kinds`` field carries
        the discriminator.

        Args:
            shape_info: Shape to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        data = self._shape_to_dict(shape_info)

        from ..config import entity_to_path

        rel_path = entity_to_path(shape_info.qname, "shape", self.config, extension=".json")
        return self._write_json(self.config.output_dir / rel_path, data)

    def render_concept(
        self,
        concept_info: "ConceptInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a SKOS concept as JSON.

        Args:
            concept_info: Concept to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        data = self._concept_to_dict(concept_info)

        from ..config import entity_to_path

        rel_path = entity_to_path(
            concept_info.qname, "skos_concept", self.config, extension=".json"
        )
        return self._write_json(self.config.output_dir / rel_path, data)

    def render_concept_scheme(
        self,
        scheme_info: "ConceptSchemeInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a SKOS concept scheme as JSON.

        The scheme's cycle-safe broader/narrower tree is included as
        ``hierarchy`` so a consumer does not have to rebuild it.

        Args:
            scheme_info: Concept scheme to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        from ..extractors import build_concept_tree

        data = self._concept_scheme_to_dict(scheme_info)
        data["hierarchy"] = self._concept_tree_to_json(
            build_concept_tree(entities.concepts, scheme_info.uri)
        )

        from ..config import entity_to_path

        rel_path = entity_to_path(
            scheme_info.qname, "skos_concept_scheme", self.config, extension=".json"
        )
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
            "object_properties": [self._property_to_dict(p) for p in entities.object_properties],
            "datatype_properties": [
                self._property_to_dict(p) for p in entities.datatype_properties
            ],
            "annotation_properties": [
                self._property_to_dict(p) for p in entities.annotation_properties
            ],
            "instances": [self._instance_to_dict(i) for i in entities.instances],
            # Full shape representations. Breaking change from v0.4.x:
            # shapes used to be lumped into 'instances' because the
            # extractor didn't filter them out. They now have their
            # own top-level array.
            "shapes": [self._shape_to_dict(s) for s in entities.shapes],
            # SKOS entities left 'instances' for their own arrays in #63.
            "concepts": [self._concept_to_dict(c) for c in entities.concepts],
            "concept_schemes": [self._concept_scheme_to_dict(s) for s in entities.concept_schemes],
        }

        return self._write_json(self._get_output_path("ontology.json"), data)

    def copy_assets(self) -> None:
        """Copy static assets. No assets needed for JSON."""
        pass
