"""Filtering logic for diff results.

Supports filtering by:
- Change type (added, removed, modified)
- Entity type (classes, properties, instances)
"""

from rdf_construct.diff.change_types import ChangeType, EntityChange, EntityType, GraphDiff


# Maps CLI filter strings to internal types
CHANGE_TYPE_MAP = {
    "added": ChangeType.ADDED,
    "removed": ChangeType.REMOVED,
    "modified": ChangeType.MODIFIED,
}

ENTITY_TYPE_MAP = {
    "classes": EntityType.CLASS,
    "class": EntityType.CLASS,
    "object_properties": EntityType.OBJECT_PROPERTY,
    "object-properties": EntityType.OBJECT_PROPERTY,
    "objprops": EntityType.OBJECT_PROPERTY,
    "datatype_properties": EntityType.DATATYPE_PROPERTY,
    "datatype-properties": EntityType.DATATYPE_PROPERTY,
    "dataprops": EntityType.DATATYPE_PROPERTY,
    "annotation_properties": EntityType.ANNOTATION_PROPERTY,
    "annotation-properties": EntityType.ANNOTATION_PROPERTY,
    "annprops": EntityType.ANNOTATION_PROPERTY,
    "properties": None,  # Special: matches all property types
    "individuals": EntityType.INDIVIDUAL,
    "instances": EntityType.INDIVIDUAL,
}

# Property types for the "properties" filter
PROPERTY_TYPES = {
    EntityType.OBJECT_PROPERTY,
    EntityType.DATATYPE_PROPERTY,
    EntityType.ANNOTATION_PROPERTY,
}


def filter_diff(
    diff: GraphDiff,
    show_types: set[str] | None = None,
    hide_types: set[str] | None = None,
    entity_types: set[str] | None = None,
) -> GraphDiff:
    """Filter a GraphDiff by change types and entity types.

    Args:
        diff: The diff to filter.
        show_types: If provided, only include these change types.
        hide_types: If provided, exclude these change types.
        entity_types: If provided, only include these entity types.

    Returns:
        A new GraphDiff with filtered results.

    Note:
        show_types and hide_types are mutually exclusive in practice,
        but if both are provided, show_types is applied first.
    """
    # Determine which change types to include
    include_change_types = set(ChangeType)

    if show_types:
        include_change_types = {
            CHANGE_TYPE_MAP[t.lower()]
            for t in show_types
            if t.lower() in CHANGE_TYPE_MAP
        }

    if hide_types:
        for t in hide_types:
            if t.lower() in CHANGE_TYPE_MAP:
                include_change_types.discard(CHANGE_TYPE_MAP[t.lower()])

    # Determine which entity types to include
    include_entity_types: set[EntityType] | None = None
    if entity_types:
        include_entity_types = set()
        for et in entity_types:
            et_lower = et.lower()
            if et_lower in ENTITY_TYPE_MAP:
                mapped = ENTITY_TYPE_MAP[et_lower]
                if mapped is None:  # "properties" special case
                    include_entity_types.update(PROPERTY_TYPES)
                else:
                    include_entity_types.add(mapped)

    # Filter the entities
    def should_include(entity: EntityChange) -> bool:
        if include_entity_types is not None:
            if entity.entity_type not in include_entity_types:
                return False
        return True

    filtered_added = []
    filtered_removed = []
    filtered_modified = []

    if ChangeType.ADDED in include_change_types:
        filtered_added = [e for e in diff.added if should_include(e)]

    if ChangeType.REMOVED in include_change_types:
        filtered_removed = [e for e in diff.removed if should_include(e)]

    if ChangeType.MODIFIED in include_change_types:
        filtered_modified = [e for e in diff.modified if should_include(e)]

    return GraphDiff(
        old_path=diff.old_path,
        new_path=diff.new_path,
        added=filtered_added,
        removed=filtered_removed,
        modified=filtered_modified,
        blank_node_warning=diff.blank_node_warning,
    )


def parse_filter_string(filter_str: str) -> set[str]:
    """Parse a comma-separated filter string into a set.

    Args:
        filter_str: Comma-separated list (e.g., "added,removed")

    Returns:
        Set of individual filter terms.
    """
    if not filter_str:
        return set()
    return {f.strip() for f in filter_str.split(",") if f.strip()}
