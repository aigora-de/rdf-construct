"""Class hierarchy analysis for ontology description.

Analyses class hierarchy structure including roots, depth, orphans, and cycles.
"""

from collections import defaultdict

from rdflib import Graph, URIRef, RDF, RDFS
from rdflib.namespace import OWL

from rdf_construct.describe.models import HierarchyAnalysis


# Classes that should not count as "real" superclasses for root detection
TOP_CLASSES = {
    OWL.Thing,
    RDFS.Resource,
    # Some ontologies use owl:Class as a type marker
    OWL.Class,
    RDFS.Class,
}


def analyse_hierarchy(graph: Graph, max_roots_display: int = 10) -> HierarchyAnalysis:
    """Analyse the class hierarchy structure.

    Args:
        graph: RDF graph to analyse.
        max_roots_display: Maximum number of root classes to list.

    Returns:
        HierarchyAnalysis with hierarchy metrics.
    """
    # Get all classes
    all_classes = _get_all_classes(graph)

    if not all_classes:
        return HierarchyAnalysis()

    # Build parent-child relationships
    parents: dict[URIRef, set[URIRef]] = defaultdict(set)
    children: dict[URIRef, set[URIRef]] = defaultdict(set)

    for cls in all_classes:
        for superclass in graph.objects(cls, RDFS.subClassOf):
            if isinstance(superclass, URIRef) and superclass in all_classes:
                parents[cls].add(superclass)
                children[superclass].add(cls)

    # Find root classes (no parent except top classes)
    root_classes: list[str] = []
    for cls in all_classes:
        real_parents = parents[cls] - TOP_CLASSES
        if not real_parents:
            root_classes.append(_curie(graph, cls))

    # Sort and limit for display
    root_classes.sort()
    display_roots = root_classes[:max_roots_display]
    if len(root_classes) > max_roots_display:
        display_roots.append(f"...and {len(root_classes) - max_roots_display} more")

    # Find orphan classes (neither parent nor child of anything)
    orphan_classes: list[str] = []
    for cls in all_classes:
        has_parent = bool(parents[cls] - TOP_CLASSES)
        has_child = bool(children[cls])
        if not has_parent and not has_child:
            orphan_classes.append(_curie(graph, cls))

    orphan_classes.sort()

    # Calculate maximum depth
    max_depth = _calculate_max_depth(all_classes, parents)

    # Detect cycles
    has_cycles, cycle_members = _detect_cycles(all_classes, parents)

    return HierarchyAnalysis(
        root_classes=display_roots,
        max_depth=max_depth,
        orphan_classes=orphan_classes,
        has_cycles=has_cycles,
        cycle_members=[_curie(graph, uri) for uri in cycle_members],
    )


def _get_all_classes(graph: Graph) -> set[URIRef]:
    """Get all classes from the graph.

    Args:
        graph: RDF graph to query.

    Returns:
        Set of class URIRefs.
    """
    classes: set[URIRef] = set()

    # owl:Class
    for cls in graph.subjects(RDF.type, OWL.Class):
        if isinstance(cls, URIRef):
            classes.add(cls)

    # rdfs:Class
    for cls in graph.subjects(RDF.type, RDFS.Class):
        if isinstance(cls, URIRef):
            classes.add(cls)

    return classes


def _calculate_max_depth(
    classes: set[URIRef],
    parents: dict[URIRef, set[URIRef]],
) -> int:
    """Calculate the maximum depth of the class hierarchy.

    Uses iterative deepening to handle potentially cyclic graphs.

    Args:
        classes: Set of all classes.
        parents: Parent relationships.

    Returns:
        Maximum hierarchy depth (0 if no hierarchy).
    """
    if not classes:
        return 0

    # Calculate depth for each class using BFS from roots
    depths: dict[URIRef, int] = {}

    # Find roots
    roots = {
        cls for cls in classes
        if not (parents[cls] - TOP_CLASSES)
    }

    # BFS to assign depths
    current_level = roots
    depth = 0

    while current_level:
        for cls in current_level:
            if cls not in depths:
                depths[cls] = depth

        # Find children at next level
        next_level: set[URIRef] = set()
        for cls in current_level:
            for child_cls in classes:
                if cls in parents[child_cls] and child_cls not in depths:
                    next_level.add(child_cls)

        current_level = next_level
        depth += 1

        # Safety limit to prevent infinite loops
        if depth > 1000:
            break

    return max(depths.values()) if depths else 0


def _detect_cycles(
    classes: set[URIRef],
    parents: dict[URIRef, set[URIRef]],
) -> tuple[bool, list[URIRef]]:
    """Detect cycles in the class hierarchy.

    Uses DFS-based cycle detection.

    Args:
        classes: Set of all classes.
        parents: Parent relationships.

    Returns:
        Tuple of (has_cycles, list of cycle member URIs).
    """
    # Build reverse mapping for traversal
    # Note: We traverse "up" via parents to detect cycles

    visited: set[URIRef] = set()
    rec_stack: set[URIRef] = set()
    cycle_members: set[URIRef] = set()

    def dfs(cls: URIRef) -> bool:
        visited.add(cls)
        rec_stack.add(cls)

        for parent in parents[cls]:
            if parent not in visited:
                if dfs(parent):
                    cycle_members.add(cls)
                    return True
            elif parent in rec_stack:
                # Found a cycle
                cycle_members.add(cls)
                cycle_members.add(parent)
                return True

        rec_stack.remove(cls)
        return False

    for cls in classes:
        if cls not in visited:
            if dfs(cls):
                # Continue to find all cycle members
                pass

    return bool(cycle_members), list(cycle_members)


def _curie(graph: Graph, uri: URIRef) -> str:
    """Convert URI to CURIE or short form for display.

    Args:
        graph: Graph with namespace bindings.
        uri: URI to convert.

    Returns:
        CURIE or shortened URI string.
    """
    try:
        return graph.namespace_manager.normalizeUri(uri)
    except Exception:
        s = str(uri)
        if "#" in s:
            return s.split("#")[-1]
        elif "/" in s:
            return s.split("/")[-1]
        return s
