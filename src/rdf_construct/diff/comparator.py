"""Core comparison logic for semantic RDF graph diffing.

The algorithm:
1. Parse both graphs into rdflib Graph objects
2. Label every blank node by its structure's content, so that a structure both graphs state is
   the same in each (#143)
3. Compute triple sets: added = new - old, removed = old - new
4. Group changes by subject, attributing each changed blank-node structure to the named subject
   it belongs to
5. Classify entities as added/removed/modified
6. Determine entity types and extract metadata
"""

from collections import defaultdict
from pathlib import Path

from rdflib import Graph, RDF, RDFS, URIRef, BNode, Literal
from rdflib.namespace import OWL
from rdflib.term import Node

from rdf_construct.core.blank_nodes import blank_node_components, is_tree, label_by_content
from rdf_construct.core.serialiser import format_term
from rdf_construct.diff.change_types import (
    ChangeType,
    EntityChange,
    EntityType,
    GraphDiff,
    TripleChange,
    UncomparedStructure,
)
from rdf_construct.diff.structures import describe_structures

#: The most blank nodes a structure that is not a tree is compared with. ``rdflib.compare``
#: canonicalises such a structure in time that grows steeply with its size: an 800-cell list whose
#: cells are each ``owl:sameAs`` themselves took 6.4 s, and 5,000 cells take minutes.
NON_TREE_LIMIT = 500


def compare_graphs(
    old_graph: Graph,
    new_graph: Graph,
    old_path: str = "old",
    new_path: str = "new",
    ignore_predicates: set[URIRef] | None = None,
) -> GraphDiff:
    """Compare two RDF graphs and return semantic differences.

    Uses set operations on triples to find changes, then groups by subject
    and classifies each entity as added, removed, or modified.

    Args:
        old_graph: The baseline/original graph.
        new_graph: The new/updated graph.
        old_path: Display name for the old graph.
        new_path: Display name for the new graph.
        ignore_predicates: Set of predicates to ignore in comparison.

    Returns:
        GraphDiff containing all semantic changes.
    """
    ignore_predicates = ignore_predicates or set()

    # Ignored predicates leave before blank nodes are labelled, so that a structure differing only
    # in an ignored predicate is the same structure in both graphs
    old_kept, old_uncompared = _set_aside(_without(old_graph, ignore_predicates), old_path)
    new_kept, new_uncompared = _set_aside(_without(new_graph, ignore_predicates), new_path)

    # Blank nodes are labelled by their structure's content, so a structure both graphs state has
    # the same labels in each, and a changed one leaves whole, with the triple referring to it
    old_labelled = label_by_content(old_kept)
    new_labelled = label_by_content(new_kept)

    # Compute triple-level differences using set operations
    old_triples = set(old_labelled)
    new_triples = set(new_labelled)

    added_triples = new_triples - old_triples
    removed_triples = old_triples - new_triples

    # Group changes by subject
    changes_by_subject: dict[Node, dict[str, list]] = defaultdict(
        lambda: {"added": [], "removed": [], "added_structures": [], "removed_structures": []}
    )
    ownerless: dict[str, list[str]] = {"added": [], "removed": []}

    for key, triples, labelled in (
        ("added", added_triples, new_labelled),
        ("removed", removed_triples, old_labelled),
    ):
        is_addition = key == "added"
        blank: list[tuple[Node, Node, Node]] = []
        for s, p, o in triples:
            if isinstance(s, BNode) or isinstance(o, BNode):
                blank.append((s, p, o))
            else:
                changes_by_subject[s][key].append(
                    TripleChange(predicate=p, object=o, is_addition=is_addition)
                )

        structures = describe_structures(blank, labelled)
        for pointer in structures.pointers:
            changes_by_subject[pointer.subject][key].append(
                TripleChange(
                    predicate=pointer.predicate,
                    object=pointer.node,
                    is_addition=is_addition,
                    turtle=pointer.turtle,
                )
            )
        for owner, text in structures.attached:
            changes_by_subject[owner][f"{key}_structures"].append(text)
        ownerless[key].extend(structures.ownerless)

    # All subjects in each graph (for determining new vs removed entities)
    old_subjects = {s for s, _, _ in old_graph}
    new_subjects = {s for s, _, _ in new_graph}

    # Classify each changed subject
    added_entities: list[EntityChange] = []
    removed_entities: list[EntityChange] = []
    modified_entities: list[EntityChange] = []

    for subject, changes in changes_by_subject.items():
        subject_in_old = subject in old_subjects
        subject_in_new = subject in new_subjects

        # Determine entity type from the appropriate graph
        if subject_in_new:
            entity_type = _determine_entity_type(new_graph, subject)
            label = _get_label(new_graph, subject)
            superclasses = _get_superclasses(new_graph, subject)
        else:
            entity_type = _determine_entity_type(old_graph, subject)
            label = _get_label(old_graph, subject)
            superclasses = _get_superclasses(old_graph, subject)

        added_triple_changes = changes["added"]
        removed_triple_changes = changes["removed"]
        added_structures = sorted(changes["added_structures"])
        removed_structures = sorted(changes["removed_structures"])

        # Classify the entity change
        if not subject_in_old and subject_in_new:
            # New entity (all its triples are in added)
            entity = EntityChange(
                uri=subject,
                entity_type=entity_type,
                change_type=ChangeType.ADDED,
                label=label,
                added_triples=added_triple_changes,
                removed_triples=[],
                superclasses=superclasses,
                added_structures=added_structures,
            )
            added_entities.append(entity)

        elif subject_in_old and not subject_in_new:
            # Removed entity (all its triples are in removed)
            entity = EntityChange(
                uri=subject,
                entity_type=entity_type,
                change_type=ChangeType.REMOVED,
                label=label,
                added_triples=[],
                removed_triples=removed_triple_changes,
                superclasses=superclasses,
                removed_structures=removed_structures,
            )
            removed_entities.append(entity)

        else:
            # Modified entity (exists in both, but has changes)
            entity = EntityChange(
                uri=subject,
                entity_type=entity_type,
                change_type=ChangeType.MODIFIED,
                label=label,
                added_triples=added_triple_changes,
                removed_triples=removed_triple_changes,
                superclasses=superclasses,
                added_structures=added_structures,
                removed_structures=removed_structures,
            )
            modified_entities.append(entity)

    # Sort entities by label/URI for consistent output
    added_entities.sort(key=lambda e: e.label or str(e.uri))
    removed_entities.sort(key=lambda e: e.label or str(e.uri))
    modified_entities.sort(key=lambda e: e.label or str(e.uri))

    return GraphDiff(
        old_path=old_path,
        new_path=new_path,
        added=added_entities,
        removed=removed_entities,
        modified=modified_entities,
        added_structures=sorted(ownerless["added"]),
        removed_structures=sorted(ownerless["removed"]),
        uncompared=old_uncompared + new_uncompared,
        blank_node_warning=bool(old_uncompared or new_uncompared),
    )


def _without(graph: Graph, predicates: set[URIRef]) -> Graph:
    """Return ``graph`` without the triples whose predicate is one of ``predicates``."""
    if not predicates:
        return graph
    kept = Graph(bind_namespaces="none")
    for prefix, namespace in graph.namespace_manager.namespaces():
        kept.bind(prefix, namespace, override=True, replace=True)
    for triple in graph:
        if triple[1] not in predicates:
            kept.add(triple)
    return kept


def _set_aside(graph: Graph, source: str) -> tuple[Graph, list[UncomparedStructure]]:
    """Set aside each blank-node structure too large to compare.

    Only a structure that is not a tree and has more than :data:`NON_TREE_LIMIT` blank nodes is
    set aside. Every other structure is compared, cycles and shared nodes included.

    Args:
        graph: The graph to compare.
        source: The file's display name, for the description.

    Returns:
        The graph without those structures, and a description of each.
    """
    blank_nodes = {t for triple in graph for t in (triple[0], triple[2]) if isinstance(t, BNode)}
    if len(blank_nodes) <= NON_TREE_LIMIT:
        return graph, []

    aside: list[Graph] = []
    uncompared: list[UncomparedStructure] = []
    for component in blank_node_components(graph):
        nodes = {t for triple in component for t in (triple[0], triple[2]) if isinstance(t, BNode)}
        if len(nodes) <= NON_TREE_LIMIT or is_tree(component):
            continue
        aside.append(component)
        refs = sorted(
            f"{format_term(graph, s)} {format_term(graph, p)}"
            for s, p, _ in component
            if not isinstance(s, BNode)
        )
        under = None
        if refs:
            under = refs[0] if len(refs) == 1 else f"{refs[0]} and {len(refs) - 1} more"
        uncompared.append(
            UncomparedStructure(
                source=source,
                blank_nodes=len(nodes),
                limit=NON_TREE_LIMIT,
                under=under,
                self_same_as=any(p == OWL.sameAs and s == o for s, p, o in component),
            )
        )

    if not aside:
        return graph, []

    excluded = {triple for component in aside for triple in component}
    kept = Graph(bind_namespaces="none")
    for prefix, namespace in graph.namespace_manager.namespaces():
        kept.bind(prefix, namespace, override=True, replace=True)
    for triple in graph:
        if triple not in excluded:
            kept.add(triple)
    uncompared.sort(key=lambda u: (u.under or "", u.blank_nodes))
    return kept, uncompared


def compare_files(
    old_path: Path,
    new_path: Path,
    ignore_predicates: set[URIRef] | None = None,
) -> GraphDiff:
    """Compare two RDF files and return semantic differences.

    Convenience wrapper that handles file loading.

    Args:
        old_path: Path to the baseline/original file.
        new_path: Path to the new/updated file.
        ignore_predicates: Set of predicates to ignore in comparison.

    Returns:
        GraphDiff containing all semantic changes.

    Raises:
        FileNotFoundError: If either file doesn't exist.
        ValueError: If files can't be parsed as RDF.
    """
    old_graph = _load_graph(old_path)
    new_graph = _load_graph(new_path)

    return compare_graphs(
        old_graph,
        new_graph,
        old_path=old_path.name,
        new_path=new_path.name,
        ignore_predicates=ignore_predicates,
    )


def _load_graph(path: Path) -> Graph:
    """Load an RDF file into a graph, guessing format from extension.

    Args:
        path: Path to the RDF file.

    Returns:
        Loaded rdflib Graph.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If file can't be parsed.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    graph = Graph()

    # Guess format from extension
    suffix = path.suffix.lower()
    format_map = {
        ".ttl": "turtle",
        ".turtle": "turtle",
        ".rdf": "xml",
        ".xml": "xml",
        ".owl": "xml",
        ".nt": "nt",
        ".ntriples": "nt",
        ".n3": "n3",
        ".jsonld": "json-ld",
        ".json": "json-ld",
    }
    fmt = format_map.get(suffix, "turtle")

    try:
        graph.parse(str(path), format=fmt)
    except Exception as e:
        raise ValueError(f"Failed to parse {path}: {e}")

    return graph


def _determine_entity_type(graph: Graph, subject: URIRef) -> EntityType:
    """Determine the semantic type of an entity.

    Args:
        graph: The RDF graph containing the entity.
        subject: The entity URI.

    Returns:
        The EntityType classification.
    """
    types = set(graph.objects(subject, RDF.type))

    # Check for ontology
    if OWL.Ontology in types:
        return EntityType.ONTOLOGY

    # Check for classes
    if OWL.Class in types or RDFS.Class in types:
        return EntityType.CLASS

    # Check for property types
    if OWL.ObjectProperty in types:
        return EntityType.OBJECT_PROPERTY
    if OWL.DatatypeProperty in types:
        return EntityType.DATATYPE_PROPERTY
    if OWL.AnnotationProperty in types:
        return EntityType.ANNOTATION_PROPERTY
    if RDF.Property in types:
        return EntityType.OBJECT_PROPERTY  # Default property type

    # If it has any type assertions (but not class/property), it's an individual
    if types:
        return EntityType.INDIVIDUAL

    return EntityType.OTHER


def _get_label(graph: Graph, subject: URIRef) -> str | None:
    """Get a human-readable label for an entity.

    Tries rdfs:label first, then skos:prefLabel, then falls back to
    the local name from the URI.

    Args:
        graph: The RDF graph containing the entity.
        subject: The entity URI.

    Returns:
        Label string or None.
    """
    # Try rdfs:label
    for label in graph.objects(subject, RDFS.label):
        if isinstance(label, Literal):
            return str(label)

    # Try skos:prefLabel
    SKOS = URIRef("http://www.w3.org/2004/02/skos/core#")
    for label in graph.objects(subject, SKOS + "prefLabel"):
        if isinstance(label, Literal):
            return str(label)

    # Fall back to local name from URI
    if isinstance(subject, URIRef):
        uri_str = str(subject)
        if "#" in uri_str:
            return uri_str.split("#")[-1]
        elif "/" in uri_str:
            return uri_str.split("/")[-1]

    return None


def _get_superclasses(graph: Graph, subject: URIRef) -> list[URIRef] | None:
    """Get direct superclasses of a class.

    Args:
        graph: The RDF graph containing the entity.
        subject: The entity URI.

    Returns:
        List of superclass URIs, or None if not a class.
    """
    types = set(graph.objects(subject, RDF.type))
    if OWL.Class not in types and RDFS.Class not in types:
        return None

    superclasses = [sc for sc in graph.objects(subject, RDFS.subClassOf) if isinstance(sc, URIRef)]

    return superclasses if superclasses else None
