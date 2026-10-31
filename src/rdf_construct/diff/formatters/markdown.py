"""Markdown formatter for diff output - designed for release notes and changelogs."""

from rdflib import Graph, URIRef, Literal, BNode
from rdflib.term import Node

from rdf_construct.diff.change_types import (
    EntityChange,
    EntityType,
    GraphDiff,
    TripleChange,
)


# Section headings for entity types
ENTITY_TYPE_HEADINGS = {
    EntityType.CLASS: "Classes",
    EntityType.OBJECT_PROPERTY: "Object Properties",
    EntityType.DATATYPE_PROPERTY: "Datatype Properties",
    EntityType.ANNOTATION_PROPERTY: "Annotation Properties",
    EntityType.INDIVIDUAL: "Instances",
    EntityType.ONTOLOGY: "Ontology Metadata",
    EntityType.OTHER: "Other",
}


def format_markdown(diff: GraphDiff, graph: Graph | None = None) -> str:
    """Format diff as Markdown for release notes.

    Args:
        diff: The diff result to format.
        graph: Optional graph for CURIE formatting.

    Returns:
        Markdown formatted diff.
    """
    lines: list[str] = []

    # Title
    lines.append(f"# Ontology Changes: {diff.old_path} → {diff.new_path}")
    lines.append("")

    # Changes that cannot be described come before any verdict, so nothing can hide them (#143)
    if diff.notes:
        for note in diff.notes:
            lines.append(f"> **Note:** {note}")
            lines.append("")

    if diff.is_identical:
        lines.append("No semantic differences found.")
        return "\n".join(lines)

    # Summary at top
    summary = diff.summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **{summary['added']}** entities added")
    lines.append(f"- **{summary['removed']}** entities removed")
    lines.append(f"- **{summary['modified']}** entities modified")
    if summary["structures"]:
        lines.append(
            f"- **{len(diff.added_structures)}** blank-node structures added, "
            f"**{len(diff.removed_structures)}** removed"
        )
    lines.append("")

    # Added entities
    if diff.added:
        lines.append("## Added")
        lines.append("")
        lines.extend(_format_entity_group(diff.added, graph))
        lines.append("")

    # Removed entities
    if diff.removed:
        lines.append("## Removed")
        lines.append("")
        lines.extend(_format_entity_group(diff.removed, graph))
        lines.append("")

    # Modified entities
    if diff.modified:
        lines.append("## Modified")
        lines.append("")
        for entity in diff.modified:
            lines.extend(_format_modified_entity_md(entity, graph))
        lines.append("")

    # Blank-node structures that belong to no named entity
    if diff.added_structures or diff.removed_structures:
        lines.append("## Blank-node structures")
        lines.append("")
        if diff.added_structures:
            lines.append("**Added:**")
            lines.append("")
            for text in diff.added_structures:
                lines.append(f"- `{text}`")
            lines.append("")
        if diff.removed_structures:
            lines.append("**Removed:**")
            lines.append("")
            for text in diff.removed_structures:
                lines.append(f"- ~~`{text}`~~")
            lines.append("")

    return "\n".join(lines)


def _format_entity_group(entities: list[EntityChange], graph: Graph | None = None) -> list[str]:
    """Format a group of entities by type."""
    lines: list[str] = []

    # Group by entity type
    by_type: dict[EntityType, list[EntityChange]] = {}
    for entity in entities:
        if entity.entity_type not in by_type:
            by_type[entity.entity_type] = []
        by_type[entity.entity_type].append(entity)

    # Output each type group
    for entity_type in EntityType:
        if entity_type not in by_type:
            continue

        heading = ENTITY_TYPE_HEADINGS.get(entity_type, "Other")
        lines.append(f"### {heading}")
        lines.append("")

        for entity in by_type[entity_type]:
            lines.append(_format_entity_bullet(entity, graph))

        lines.append("")

    return lines


def _format_entity_bullet(entity: EntityChange, graph: Graph | None = None) -> str:
    """Format a single entity as a markdown bullet."""
    uri_str = _format_uri(entity.uri, graph)
    label = entity.label or uri_str

    # Build the bullet
    bullet = f"- **{label}**"

    # Add superclass info for classes
    if entity.superclasses:
        superclass_strs = [_format_uri(sc, graph) for sc in entity.superclasses]
        bullet += f" — subclass of {', '.join(superclass_strs)}"

    return bullet


def _format_modified_entity_md(entity: EntityChange, graph: Graph | None = None) -> list[str]:
    """Format a modified entity with detailed changes."""
    lines: list[str] = []

    uri_str = _format_uri(entity.uri, graph)
    label = entity.label or uri_str

    lines.append(f"### {label}")
    lines.append("")

    # Additions
    if entity.added_triples or entity.added_structures:
        lines.append("**Added:**")
        lines.append("")
        for change in entity.added_triples:
            pred_str = _format_uri(change.predicate, graph)
            obj_str = (
                f"`{change.turtle}`" if change.turtle else _format_object(change.object, graph)
            )
            lines.append(f"- `{pred_str}` → {obj_str}")
        for text in entity.added_structures:
            lines.append(f"- `{text}`")
        lines.append("")

    # Removals
    if entity.removed_triples or entity.removed_structures:
        lines.append("**Removed:**")
        lines.append("")
        for change in entity.removed_triples:
            pred_str = _format_uri(change.predicate, graph)
            obj_str = (
                f"`{change.turtle}`" if change.turtle else _format_object(change.object, graph)
            )
            lines.append(f"- ~~`{pred_str}` → {obj_str}~~")
        for text in entity.removed_structures:
            lines.append(f"- ~~`{text}`~~")
        lines.append("")

    return lines


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


def _format_object(obj: Node, graph: Graph | None = None) -> str:
    """Format an RDF object (URI, BNode, or Literal)."""
    if isinstance(obj, URIRef):
        return f"`{_format_uri(obj, graph)}`"
    elif isinstance(obj, BNode):
        return f"`_:{obj}`"
    elif isinstance(obj, Literal):
        value = str(obj)
        if obj.language:
            return f'"{value}"@{obj.language}'
        return f'"{value}"'
    return str(obj)
