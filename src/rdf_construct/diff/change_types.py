"""Data classes for representing semantic changes between RDF graphs.

This module defines the type hierarchy for diff results:
- EntityChange: Changes to a single entity (added/removed/modified)
- TripleChange: Individual triple-level changes
- GraphDiff: Complete diff result containing all changes
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from rdflib import URIRef, BNode, Literal
from rdflib.term import Node


class ChangeType(Enum):
    """Classification of change types for filtering and display."""

    ADDED = auto()
    REMOVED = auto()
    MODIFIED = auto()


class EntityType(Enum):
    """Classification of RDF entity types."""

    CLASS = "class"
    OBJECT_PROPERTY = "object_property"
    DATATYPE_PROPERTY = "datatype_property"
    ANNOTATION_PROPERTY = "annotation_property"
    INDIVIDUAL = "individual"
    ONTOLOGY = "ontology"
    OTHER = "other"


class PredicateCategory(Enum):
    """Semantic categories for predicates (for human-readable output)."""

    TYPE = "type"
    HIERARCHY = "hierarchy"
    DOMAIN_RANGE = "domain_range"
    LABEL = "label"
    DOCUMENTATION = "documentation"
    OWL_AXIOM = "owl_axiom"
    OTHER = "other"


@dataclass
class TripleChange:
    """Represents a single triple that was added or removed.

    Attributes:
        predicate: The predicate of the changed triple.
        object: The object of the changed triple.
        is_addition: True if added, False if removed.
        category: Semantic category of the predicate.
    """

    predicate: URIRef
    object: Node
    is_addition: bool
    category: PredicateCategory = PredicateCategory.OTHER

    def __post_init__(self):
        """Categorise the predicate if not already done."""
        if self.category == PredicateCategory.OTHER:
            self.category = categorise_predicate(self.predicate)


@dataclass
class EntityChange:
    """Represents all changes to a single entity.

    Attributes:
        uri: The URI of the changed entity.
        entity_type: The type of entity (class, property, individual, etc.).
        change_type: Whether entity was added, removed, or modified.
        label: Human-readable label if available.
        added_triples: List of triples added to this entity.
        removed_triples: List of triples removed from this entity.
        superclasses: Superclasses (for classes) or None.
    """

    uri: URIRef | BNode
    entity_type: EntityType
    change_type: ChangeType
    label: str | None = None
    added_triples: list[TripleChange] = field(default_factory=list)
    removed_triples: list[TripleChange] = field(default_factory=list)
    superclasses: list[URIRef] | None = None

    @property
    def is_blank_node(self) -> bool:
        """Check if this entity is a blank node."""
        return isinstance(self.uri, BNode)

    @property
    def all_changes(self) -> list[TripleChange]:
        """Get all triple changes (both additions and removals)."""
        return self.added_triples + self.removed_triples


@dataclass
class GraphDiff:
    """Complete result of comparing two RDF graphs.

    Attributes:
        old_path: Path/name of the old graph.
        new_path: Path/name of the new graph.
        added: Entities that exist only in the new graph.
        removed: Entities that exist only in the old graph.
        modified: Entities that exist in both but have changes.
        blank_node_warning: True if blank nodes were encountered.
    """

    old_path: str
    new_path: str
    added: list[EntityChange] = field(default_factory=list)
    removed: list[EntityChange] = field(default_factory=list)
    modified: list[EntityChange] = field(default_factory=list)
    blank_node_warning: bool = False

    @property
    def is_identical(self) -> bool:
        """Check if graphs are semantically identical."""
        return not self.added and not self.removed and not self.modified

    @property
    def summary(self) -> dict[str, int]:
        """Get summary counts."""
        return {
            "added": len(self.added),
            "removed": len(self.removed),
            "modified": len(self.modified),
        }

    def entities_by_type(
        self, change_type: ChangeType
    ) -> dict[EntityType, list[EntityChange]]:
        """Group entities by their type for a given change type.

        Args:
            change_type: ADDED, REMOVED, or MODIFIED

        Returns:
            Dictionary mapping EntityType to list of EntityChange
        """
        if change_type == ChangeType.ADDED:
            entities = self.added
        elif change_type == ChangeType.REMOVED:
            entities = self.removed
        else:
            entities = self.modified

        result: dict[EntityType, list[EntityChange]] = {}
        for entity in entities:
            if entity.entity_type not in result:
                result[entity.entity_type] = []
            result[entity.entity_type].append(entity)

        return result


def categorise_predicate(predicate: URIRef) -> PredicateCategory:
    """Categorise a predicate for human-readable output.

    Args:
        predicate: The predicate URI to categorise

    Returns:
        The semantic category of the predicate
    """
    pred_str = str(predicate)

    # Type predicates
    if pred_str.endswith("type") or "rdf-syntax-ns#type" in pred_str:
        return PredicateCategory.TYPE

    # Hierarchy predicates
    if any(
        x in pred_str
        for x in ["subClassOf", "subPropertyOf", "equivalentClass", "equivalentProperty"]
    ):
        return PredicateCategory.HIERARCHY

    # Domain/range
    if any(x in pred_str for x in ["domain", "range"]):
        return PredicateCategory.DOMAIN_RANGE

    # Labels
    if "label" in pred_str.lower() or "prefLabel" in pred_str:
        return PredicateCategory.LABEL

    # Documentation
    if any(x in pred_str.lower() for x in ["comment", "description", "definition", "note"]):
        return PredicateCategory.DOCUMENTATION

    # OWL axioms
    if "owl" in pred_str.lower() and any(
        x in pred_str
        for x in [
            "disjoint",
            "inverse",
            "functional",
            "cardinality",
            "restriction",
            "union",
            "intersection",
        ]
    ):
        return PredicateCategory.OWL_AXIOM

    return PredicateCategory.OTHER
