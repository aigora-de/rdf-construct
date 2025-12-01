"""JSON formatter for diff output - designed for programmatic use and scripting."""

import json
from typing import Any

from rdflib import Graph, URIRef, Literal, BNode
from rdflib.term import Node

from rdf_construct.diff.change_types import (
    EntityChange,
    EntityType,
    GraphDiff,
    TripleChange,
)


def format_json(diff: GraphDiff, graph: Graph | None = None, indent: int = 2) -> str:
    """Format diff as JSON for programmatic use.

    Args:
        diff: The diff result to format.
        graph: Optional graph for CURIE formatting.
        indent: JSON indentation (default 2).

    Returns:
        JSON formatted diff.
    """
    result = _build_json_structure(diff, graph)
    return json.dumps(result, indent=indent, ensure_ascii=False)


def _build_json_structure(diff: GraphDiff, graph: Graph | None = None) -> dict[str, Any]:
    """Build the JSON structure for a diff."""
    return {
        "comparison": {
            "old": diff.old_path,
            "new": diff.new_path,
        },
        "identical": diff.is_identical,
        "added": _format_entity_group_json(diff.added, graph),
        "removed": _format_entity_group_json(diff.removed, graph),
        "modified": _format_modified_entities_json(diff.modified, graph),
        "summary": diff.summary,
        "warnings": _build_warnings(diff),
    }


def _format_entity_group_json(
    entities: list[EntityChange], graph: Graph | None = None
) -> dict[str, list[dict]]:
    """Format a group of entities by type for JSON output."""
    result: dict[str, list[dict]] = {
        "classes": [],
        "object_properties": [],
        "datatype_properties": [],
        "annotation_properties": [],
        "individuals": [],
        "other": [],
    }

    type_mapping = {
        EntityType.CLASS: "classes",
        EntityType.OBJECT_PROPERTY: "object_properties",
        EntityType.DATATYPE_PROPERTY: "datatype_properties",
        EntityType.ANNOTATION_PROPERTY: "annotation_properties",
        EntityType.INDIVIDUAL: "individuals",
        EntityType.ONTOLOGY: "other",
        EntityType.OTHER: "other",
    }

    for entity in entities:
        key = type_mapping.get(entity.entity_type, "other")
        result[key].append(_format_entity_json(entity, graph))

    # Remove empty categories
    return {k: v for k, v in result.items() if v}


def _format_entity_json(entity: EntityChange, graph: Graph | None = None) -> dict:
    """Format a single entity for JSON output."""
    result = {
        "uri": str(entity.uri),
        "label": entity.label,
        "type": entity.entity_type.value,
    }

    if entity.superclasses:
        result["superclasses"] = [str(sc) for sc in entity.superclasses]

    return result


def _format_modified_entities_json(
    entities: list[EntityChange], graph: Graph | None = None
) -> list[dict]:
    """Format modified entities with detailed changes."""
    result = []

    for entity in entities:
        entity_dict = {
            "uri": str(entity.uri),
            "label": entity.label,
            "type": entity.entity_type.value,
            "changes": [],
        }

        # Format added triples
        for change in entity.added_triples:
            entity_dict["changes"].append({
                "action": "added",
                "predicate": str(change.predicate),
                "predicate_curie": _format_uri(change.predicate, graph),
                "object": _format_object_json(change.object, graph),
                "category": change.category.value,
            })

        # Format removed triples
        for change in entity.removed_triples:
            entity_dict["changes"].append({
                "action": "removed",
                "predicate": str(change.predicate),
                "predicate_curie": _format_uri(change.predicate, graph),
                "object": _format_object_json(change.object, graph),
                "category": change.category.value,
            })

        result.append(entity_dict)

    return result


def _format_object_json(obj: Node, graph: Graph | None = None) -> dict:
    """Format an RDF object for JSON output."""
    if isinstance(obj, URIRef):
        return {
            "type": "uri",
            "value": str(obj),
            "curie": _format_uri(obj, graph),
        }
    elif isinstance(obj, BNode):
        return {
            "type": "bnode",
            "value": str(obj),
        }
    elif isinstance(obj, Literal):
        result = {
            "type": "literal",
            "value": str(obj),
        }
        if obj.language:
            result["language"] = obj.language
        if obj.datatype:
            result["datatype"] = str(obj.datatype)
        return result

    return {"type": "unknown", "value": str(obj)}


def _format_uri(uri: URIRef | BNode, graph: Graph | None = None) -> str:
    """Format a URI as a CURIE if possible."""
    if isinstance(uri, BNode):
        return f"_:{uri}"

    if graph is not None:
        try:
            curie = graph.namespace_manager.normalizeUri(uri)
            if curie and not curie.startswith("<"):
                return curie
        except Exception:
            pass

    uri_str = str(uri)
    if "#" in uri_str:
        return uri_str.split("#")[-1]
    elif "/" in uri_str:
        parts = uri_str.split("/")
        return parts[-1] if parts[-1] else parts[-2]

    return uri_str


def _build_warnings(diff: GraphDiff) -> list[str]:
    """Build list of warning messages."""
    warnings = []

    if diff.blank_node_warning:
        warnings.append(
            "Blank node changes were detected but not fully analysed. "
            "Consider skolemising blank nodes for detailed comparison."
        )

    return warnings
