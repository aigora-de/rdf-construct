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
        turtle: The object written inline as Turtle, when it is a blank-node structure.
    """

    predicate: URIRef
    object: Node
    is_addition: bool
    category: PredicateCategory = PredicateCategory.OTHER
    turtle: str | None = None

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
        added_structures: Blank-node structures about this entity that were added, written as
            Turtle: an axiom annotation, a reified statement, or a structure shared or cyclic.
        removed_structures: The same, removed.
    """

    uri: URIRef | BNode
    entity_type: EntityType
    change_type: ChangeType
    label: str | None = None
    added_triples: list[TripleChange] = field(default_factory=list)
    removed_triples: list[TripleChange] = field(default_factory=list)
    superclasses: list[URIRef] | None = None
    added_structures: list[str] = field(default_factory=list)
    removed_structures: list[str] = field(default_factory=list)

    @property
    def is_blank_node(self) -> bool:
        """Check if this entity is a blank node."""
        return isinstance(self.uri, BNode)

    @property
    def all_changes(self) -> list[TripleChange]:
        """Get all triple changes (both additions and removals)."""
        return self.added_triples + self.removed_triples


@dataclass
class UncomparedStructure:
    """A blank-node structure too large to compare, so its changes, if any, are not known.

    A structure that is not a tree is compared with ``rdflib.compare``, whose cost grows steeply
    with the structure's size, so one above the limit is set aside instead (#143).

    Attributes:
        source: The file the structure is in.
        blank_nodes: How many blank nodes it has.
        limit: The most blank nodes a structure that is not a tree is compared with.
        under: Where it hangs, as ``subject predicate``, or None if nothing refers to it.
        self_same_as: True if any of its blank nodes is ``owl:sameAs`` itself.
    """

    source: str
    blank_nodes: int
    limit: int
    under: str | None = None
    self_same_as: bool = False

    def describe(self) -> str:
        """Say what was not compared and what to do about it."""
        where = f", under {self.under}" if self.under else ""
        text = (
            f"A blank-node structure in {self.source} was not compared: it is not a tree, and it "
            f"has {self.blank_nodes:,} blank nodes, over the limit of {self.limit:,}{where}. "
            "Its changes, if any, are not shown."
        )
        if self.self_same_as:
            text += (
                " Each of its blank nodes is owl:sameAs itself, which an OWL-RL closure adds;"
                " diff the asserted files instead."
            )
        return text


@dataclass
class GraphDiff:
    """Complete result of comparing two RDF graphs.

    Attributes:
        old_path: Path/name of the old graph.
        new_path: Path/name of the new graph.
        added: Entities that exist only in the new graph.
        removed: Entities that exist only in the old graph.
        modified: Entities that exist in both but have changes.
        added_structures: Blank-node structures that belong to no named entity, added, written
            as Turtle.
        removed_structures: The same, removed.
        uncompared: Blank-node structures too large to compare.
    """

    old_path: str
    new_path: str
    added: list[EntityChange] = field(default_factory=list)
    removed: list[EntityChange] = field(default_factory=list)
    modified: list[EntityChange] = field(default_factory=list)
    added_structures: list[str] = field(default_factory=list)
    removed_structures: list[str] = field(default_factory=list)
    uncompared: list[UncomparedStructure] = field(default_factory=list)

    @property
    def blank_node_warning(self) -> bool:
        """True if a blank-node structure was not compared, so its changes are not known.

        Derived from :attr:`uncompared`, which holds what the notes say, so the two cannot
        disagree.
        """
        return bool(self.uncompared)

    @property
    def is_identical(self) -> bool:
        """Check if graphs are semantically identical.

        Never while a blank-node structure changed or could not be compared (#143).
        """
        return (
            not self.added
            and not self.removed
            and not self.modified
            and not self.added_structures
            and not self.removed_structures
            and not self.uncompared
        )

    @property
    def notes(self) -> list[str]:
        """What a reader must be told before any verdict: the changes that cannot be described."""
        # A file compared with itself would say the same thing twice
        return list(dict.fromkeys(structure.describe() for structure in self.uncompared))

    @property
    def summary(self) -> dict[str, int]:
        """Get summary counts."""
        return {
            "added": len(self.added),
            "removed": len(self.removed),
            "modified": len(self.modified),
            "structures": len(self.added_structures) + len(self.removed_structures),
        }

    def entities_by_type(self, change_type: ChangeType) -> dict[EntityType, list[EntityChange]]:
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
