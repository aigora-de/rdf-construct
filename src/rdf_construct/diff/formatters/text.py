"""Text formatter for diff output - designed for terminal display."""

from typing import Protocol

from rdflib import Graph, URIRef, Literal, BNode
from rdflib.term import Node

from rdf_construct.diff.change_types import (
    EntityChange,
    EntityType,
    GraphDiff,
    PredicateCategory,
    TripleChange,
)


class DiffFormatter(Protocol):
    """Protocol for diff formatters."""

    def format(self, diff: GraphDiff, graph: Graph | None = None) -> str:
        """Format a diff result as a string.

        Args:
            diff: The diff result to format.
            graph: Optional graph for CURIE formatting.

        Returns:
            Formatted string representation.
        """
        ...


# Human-readable names for entity types
ENTITY_TYPE_NAMES = {
    EntityType.CLASS: "Class",
    EntityType.OBJECT_PROPERTY: "ObjectProperty",
    EntityType.DATATYPE_PROPERTY: "DataProperty",
    EntityType.ANNOTATION_PROPERTY: "AnnotationProperty",
    EntityType.INDIVIDUAL: "Instance",
    EntityType.ONTOLOGY: "Ontology",
    EntityType.OTHER: "Entity",
}


def format_text(diff: GraphDiff, graph: Graph | None = None) -> str:
    """Format diff as plain text for terminal output.

    Args:
        diff: The diff result to format.
        graph: Optional graph for CURIE formatting.

    Returns:
        Plain text diff representation.
    """
    lines: list[str] = []

    # Header
    lines.append(f"Comparing {diff.old_path} → {diff.new_path}")
    lines.append("")

    if diff.is_identical:
        lines.append("No semantic differences found.")
        return "\n".join(lines)

    # Added entities
    if diff.added:
        lines.append(f"ADDED ({len(diff.added)} entities):")
        for entity in diff.added:
            lines.append(_format_added_entity(entity, graph))
        lines.append("")

    # Removed entities
    if diff.removed:
        lines.append(f"REMOVED ({len(diff.removed)} entities):")
        for entity in diff.removed:
            lines.append(_format_removed_entity(entity, graph))
        lines.append("")

    # Modified entities
    if diff.modified:
        lines.append(f"MODIFIED ({len(diff.modified)} entities):")
        for entity in diff.modified:
            lines.extend(_format_modified_entity(entity, graph))
        lines.append("")

    # Summary
    summary = diff.summary
    lines.append(
        f"Summary: {summary['added']} added, "
        f"{summary['removed']} removed, "
        f"{summary['modified']} modified"
    )

    # Blank node warning
    if diff.blank_node_warning:
        lines.append("")
        lines.append(
            "Note: Blank node changes detected but not fully analysed. "
            "Consider skolemising blank nodes for detailed comparison."
        )

    return "\n".join(lines)


def _format_uri(uri: URIRef | BNode, graph: Graph | None = None) -> str:
    """Format a URI as a CURIE if possible, or full URI otherwise."""
    if isinstance(uri, BNode):
        return f"_:{uri}"

    if graph is not None:
        try:
            curie = graph.namespace_manager.normalizeUri(uri)
            if curie and not curie.startswith("<"):
                return curie
        except Exception:
            pass

    # Fallback: extract local name
    uri_str = str(uri)
    if "#" in uri_str:
        return uri_str.split("#")[-1]
    elif "/" in uri_str:
        parts = uri_str.split("/")
        return parts[-1] if parts[-1] else parts[-2]

    return uri_str


def _format_object(obj: Node, graph: Graph | None = None) -> str:
    """Format an RDF object (URI, BNode, or Literal)."""
    if isinstance(obj, URIRef):
        return _format_uri(obj, graph)
    elif isinstance(obj, BNode):
        return f"_:{obj}"
    elif isinstance(obj, Literal):
        value = str(obj)
        if obj.language:
            return f'"{value}"@{obj.language}'
        elif obj.datatype:
            dtype = _format_uri(obj.datatype, graph)
            # Skip xsd:string as it's the default
            if "string" in dtype.lower():
                return f'"{value}"'
            return f'"{value}"^^{dtype}'
        return f'"{value}"'
    return str(obj)


def _format_added_entity(entity: EntityChange, graph: Graph | None = None) -> str:
    """Format a single added entity."""
    type_name = ENTITY_TYPE_NAMES.get(entity.entity_type, "Entity")
    uri_str = _format_uri(entity.uri, graph)

    # Build description
    desc = f"  + {type_name} {uri_str}"

    # Add superclass info for classes
    if entity.superclasses:
        superclass_strs = [_format_uri(sc, graph) for sc in entity.superclasses]
        desc += f" (subclass of {', '.join(superclass_strs)})"

    return desc


def _format_removed_entity(entity: EntityChange, graph: Graph | None = None) -> str:
    """Format a single removed entity."""
    type_name = ENTITY_TYPE_NAMES.get(entity.entity_type, "Entity")
    uri_str = _format_uri(entity.uri, graph)

    return f"  - {type_name} {uri_str}"


def _format_modified_entity(
    entity: EntityChange, graph: Graph | None = None
) -> list[str]:
    """Format a modified entity with its changes."""
    lines: list[str] = []

    type_name = ENTITY_TYPE_NAMES.get(entity.entity_type, "Entity")
    uri_str = _format_uri(entity.uri, graph)

    lines.append(f"  ~ {type_name} {uri_str}")

    # Group and format changes
    for change in entity.added_triples:
        pred_str = _format_uri(change.predicate, graph)
        obj_str = _format_object(change.object, graph)
        lines.append(f"    + {pred_str} {obj_str}")

    for change in entity.removed_triples:
        pred_str = _format_uri(change.predicate, graph)
        obj_str = _format_object(change.object, graph)
        lines.append(f"    - {pred_str} {obj_str}")

    return lines
