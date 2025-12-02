"""Core comparison logic for semantic RDF graph diffing.

The algorithm:
1. Parse both graphs into rdflib Graph objects
2. Compute triple sets: added = new - old, removed = old - new
3. Group changes by subject
4. Classify entities as added/removed/modified
5. Determine entity types and extract metadata
"""

from collections import defaultdict
from pathlib import Path

from rdflib import Graph, RDF, RDFS, URIRef, BNode, Literal
from rdflib.namespace import OWL
from rdflib.term import Node

from rdf_construct.diff.change_types import (
    ChangeType,
    EntityChange,
    EntityType,
    GraphDiff,
    TripleChange,
)


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

    # Compute triple-level differences using set operations
    old_triples = set(old_graph)
    new_triples = set(new_graph)

    added_triples = new_triples - old_triples
    removed_triples = old_triples - new_triples

    # Filter out ignored predicates
    if ignore_predicates:
        added_triples = {
            (s, p, o) for s, p, o in added_triples if p not in ignore_predicates
        }
        removed_triples = {
            (s, p, o) for s, p, o in removed_triples if p not in ignore_predicates
        }

    # Group changes by subject
    changes_by_subject: dict[Node, dict[str, list[tuple]]] = defaultdict(
        lambda: {"added": [], "removed": []}
    )

    for s, p, o in added_triples:
        changes_by_subject[s]["added"].append((p, o))

    for s, p, o in removed_triples:
        changes_by_subject[s]["removed"].append((p, o))

    # Track if we encountered blank nodes
    has_blank_nodes = any(isinstance(s, BNode) for s in changes_by_subject)

    # All subjects in each graph (for determining new vs removed entities)
    old_subjects = {s for s, _, _ in old_graph}
    new_subjects = {s for s, _, _ in new_graph}

    # Classify each changed subject
    added_entities: list[EntityChange] = []
    removed_entities: list[EntityChange] = []
    modified_entities: list[EntityChange] = []

    for subject, changes in changes_by_subject.items():
        # Skip blank nodes for deep analysis (just flag them)
        if isinstance(subject, BNode):
            continue

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

        # Create triple changes
        added_triple_changes = [
            TripleChange(predicate=p, object=o, is_addition=True)
            for p, o in changes["added"]
        ]
        removed_triple_changes = [
            TripleChange(predicate=p, object=o, is_addition=False)
            for p, o in changes["removed"]
        ]

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
        blank_node_warning=has_blank_nodes,
    )


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

    superclasses = [
        sc for sc in graph.objects(subject, RDFS.subClassOf) if isinstance(sc, URIRef)
    ]

    return superclasses if superclasses else None
