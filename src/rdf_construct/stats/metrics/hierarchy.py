"""Hierarchy metrics for RDF ontologies.

Analyses class hierarchy structure: depth, branching factor, orphan classes.
"""

from collections import defaultdict
from dataclasses import dataclass

from rdflib import Graph, RDF, RDFS
from rdflib.namespace import OWL


@dataclass
class HierarchyStats:
    """Hierarchy statistics for an ontology.

    Attributes:
        root_classes: Classes with no superclass (except owl:Thing).
        leaf_classes: Classes with no subclasses.
        max_depth: Maximum depth of the class hierarchy.
        avg_depth: Average depth across all classes.
        avg_branching: Average number of direct subclasses per class.
        orphan_classes: Classes not connected to the main hierarchy.
        orphan_rate: Proportion of orphan classes (0.0 - 1.0).
    """

    root_classes: int = 0
    leaf_classes: int = 0
    max_depth: int = 0
    avg_depth: float = 0.0
    avg_branching: float = 0.0
    orphan_classes: int = 0
    orphan_rate: float = 0.0


def _get_all_classes(graph: Graph) -> set:
    """Get all classes from the graph."""
    classes = set(graph.subjects(RDF.type, OWL.Class))
    classes |= set(graph.subjects(RDF.type, RDFS.Class))
    return classes


def _build_hierarchy(graph: Graph, classes: set) -> tuple[dict, dict]:
    """Build parent/child adjacency lists from the class hierarchy.

    Args:
        graph: RDF graph to query.
        classes: Set of class URIRefs.

    Returns:
        Tuple of (parents_of, children_of) dictionaries.
    """
    parents_of: dict = defaultdict(set)  # child -> {parents}
    children_of: dict = defaultdict(set)  # parent -> {children}

    for cls in classes:
        for parent in graph.objects(cls, RDFS.subClassOf):
            # Only consider class-class relationships
            if parent in classes:
                parents_of[cls].add(parent)
                children_of[parent].add(cls)

    return dict(parents_of), dict(children_of)


def _compute_depths(classes: set, parents_of: dict) -> dict:
    """Compute depth of each class in the hierarchy.

    Depth is the length of the longest path from a root class.
    Root classes (no parents) have depth 0.

    Args:
        classes: Set of all class URIRefs.
        parents_of: Dictionary mapping class -> set of parent classes.

    Returns:
        Dictionary mapping class -> depth.
    """
    depths: dict = {}

    def compute_depth(cls: object, visited: set) -> int:
        """Recursively compute depth, handling cycles."""
        if cls in depths:
            return depths[cls]
        if cls in visited:
            # Cycle detected
            return 0

        visited.add(cls)
        parents = parents_of.get(cls, set())

        if not parents:
            # Root class
            depth = 0
        else:
            # Depth is max parent depth + 1
            depth = max(compute_depth(p, visited) for p in parents) + 1

        depths[cls] = depth
        return depth

    for cls in classes:
        if cls not in depths:
            compute_depth(cls, set())

    return depths


def _find_roots(classes: set, parents_of: dict) -> set:
    """Find root classes (those with no parent in the class set).

    Args:
        classes: Set of all class URIRefs.
        parents_of: Dictionary mapping class -> set of parent classes.

    Returns:
        Set of root class URIRefs.
    """
    return {cls for cls in classes if not parents_of.get(cls)}


def _find_leaves(classes: set, children_of: dict) -> set:
    """Find leaf classes (those with no children).

    Args:
        classes: Set of all class URIRefs.
        children_of: Dictionary mapping class -> set of child classes.

    Returns:
        Set of leaf class URIRefs.
    """
    return {cls for cls in classes if not children_of.get(cls)}


def _find_orphans(classes: set, parents_of: dict, children_of: dict) -> set:
    """Find orphan classes (not connected to any other class).

    An orphan class has no parents and no children in the hierarchy.

    Args:
        classes: Set of all class URIRefs.
        parents_of: Dictionary mapping class -> set of parent classes.
        children_of: Dictionary mapping class -> set of child classes.

    Returns:
        Set of orphan class URIRefs.
    """
    return {
        cls for cls in classes
        if not parents_of.get(cls) and not children_of.get(cls)
    }


def _compute_avg_branching(classes: set, children_of: dict) -> float:
    """Compute average branching factor (subclasses per class).

    Only considers classes that have at least one subclass.

    Args:
        classes: Set of all class URIRefs.
        children_of: Dictionary mapping class -> set of child classes.

    Returns:
        Average number of subclasses per parent class.
    """
    parent_counts = [len(children) for cls, children in children_of.items() if children]
    if not parent_counts:
        return 0.0
    return sum(parent_counts) / len(parent_counts)


def collect_hierarchy_stats(graph: Graph) -> HierarchyStats:
    """Collect hierarchy statistics from an RDF graph.

    Args:
        graph: RDF graph to analyse.

    Returns:
        HierarchyStats with all hierarchy metrics populated.
    """
    classes = _get_all_classes(graph)

    if not classes:
        return HierarchyStats()

    parents_of, children_of = _build_hierarchy(graph, classes)
    depths = _compute_depths(classes, parents_of)

    roots = _find_roots(classes, parents_of)
    leaves = _find_leaves(classes, children_of)
    orphans = _find_orphans(classes, parents_of, children_of)

    max_depth = max(depths.values()) if depths else 0
    avg_depth = sum(depths.values()) / len(depths) if depths else 0.0
    avg_branching = _compute_avg_branching(classes, children_of)

    orphan_rate = len(orphans) / len(classes) if classes else 0.0

    return HierarchyStats(
        root_classes=len(roots),
        leaf_classes=len(leaves),
        max_depth=max_depth,
        avg_depth=round(avg_depth, 2),
        avg_branching=round(avg_branching, 2),
        orphan_classes=len(orphans),
        orphan_rate=round(orphan_rate, 3),
    )
