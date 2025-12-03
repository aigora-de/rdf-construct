"""Conflict detection and resolution for ontology merging.

This module handles:
- Detecting conflicting values for the same subject+predicate
- Resolving conflicts based on configured strategy
- Marking unresolved conflicts in output
- Generating conflict reports
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Iterator

from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL
from rdflib.term import Node


class ConflictType(Enum):
    """Classification of conflict types."""

    VALUE_DIFFERENCE = auto()  # Same predicate, different literal values
    TYPE_DIFFERENCE = auto()  # Different rdf:type declarations
    HIERARCHY_DIFFERENCE = auto()  # Different subClassOf/subPropertyOf
    SEMANTIC_CONTRADICTION = auto()  # Logically incompatible (e.g., disjoint + subclass)


@dataclass
class ConflictValue:
    """A single value in a conflict.

    Attributes:
        value: The RDF value (Literal, URIRef, or BNode)
        source_path: Path to the source file
        priority: Priority of the source
    """

    value: Node
    source_path: str
    priority: int

    def __str__(self) -> str:
        """Return string representation of the value."""
        if isinstance(self.value, Literal):
            lang = f"@{self.value.language}" if self.value.language else ""
            dtype = f"^^{self.value.datatype}" if self.value.datatype else ""
            return f'"{self.value}"{lang}{dtype}'
        return str(self.value)


@dataclass
class Conflict:
    """Represents a conflict between source files.

    Attributes:
        subject: The subject URI where conflict occurs
        predicate: The predicate where conflict occurs
        values: List of conflicting values from different sources
        conflict_type: Classification of the conflict
        resolution: The resolved value, if any
        is_resolved: Whether the conflict was automatically resolved
    """

    subject: URIRef | BNode
    predicate: URIRef
    values: list[ConflictValue]
    conflict_type: ConflictType = ConflictType.VALUE_DIFFERENCE
    resolution: ConflictValue | None = None
    is_resolved: bool = False

    @property
    def requires_attention(self) -> bool:
        """Check if this conflict requires manual attention."""
        return not self.is_resolved

    def resolve_by_priority(self) -> None:
        """Resolve conflict by choosing highest priority value."""
        if self.values:
            sorted_vals = sorted(self.values, key=lambda v: v.priority, reverse=True)
            self.resolution = sorted_vals[0]
            self.is_resolved = True

    def resolve_by_first(self) -> None:
        """Resolve conflict by choosing first value."""
        if self.values:
            self.resolution = self.values[0]
            self.is_resolved = True

    def resolve_by_last(self) -> None:
        """Resolve conflict by choosing last value."""
        if self.values:
            self.resolution = self.values[-1]
            self.is_resolved = True


@dataclass
class SourceGraph:
    """A loaded source graph with metadata.

    Attributes:
        graph: The RDF graph
        path: Path to the source file
        priority: Priority for conflict resolution
        triple_count: Number of triples in the graph
    """

    graph: Graph
    path: str
    priority: int
    triple_count: int = 0

    def __post_init__(self):
        """Calculate triple count."""
        self.triple_count = len(self.graph)


class ConflictDetector:
    """Detects conflicts between multiple source graphs.

    A conflict occurs when the same subject has different values for
    the same predicate across different sources. This is particularly
    important for functional properties or single-valued predicates.
    """

    # Predicates that typically should have single values
    SINGLE_VALUE_PREDICATES: set[URIRef] = {
        RDFS.label,
        RDFS.comment,
        RDFS.domain,
        RDFS.range,
        OWL.inverseOf,
    }

    def __init__(self, ignore_predicates: set[str] | None = None):
        """Initialize the conflict detector.

        Args:
            ignore_predicates: Predicates to ignore in conflict detection
        """
        self.ignore_predicates: set[URIRef] = set()
        if ignore_predicates:
            self.ignore_predicates = {URIRef(p) for p in ignore_predicates}

    def detect_conflicts(self, sources: list[SourceGraph]) -> list[Conflict]:
        """Detect conflicts across multiple source graphs.

        Args:
            sources: List of source graphs to compare

        Returns:
            List of detected conflicts
        """
        conflicts: list[Conflict] = []

        # Build index: subject -> predicate -> [(value, source, priority)]
        index: dict[Node, dict[URIRef, list[ConflictValue]]] = {}

        for source in sources:
            for s, p, o in source.graph:
                # Skip ignored predicates
                if p in self.ignore_predicates:
                    continue

                # Skip blank node subjects for now (complex to handle)
                if isinstance(s, BNode):
                    continue

                if s not in index:
                    index[s] = {}
                if p not in index[s]:
                    index[s][p] = []

                # Check if this exact value already exists
                existing_values = [cv.value for cv in index[s][p]]
                if o not in existing_values:
                    index[s][p].append(
                        ConflictValue(value=o, source_path=source.path, priority=source.priority)
                    )

        # Find predicates with multiple different values
        for subject, predicates in index.items():
            for predicate, values in predicates.items():
                if len(values) > 1:
                    conflict_type = self._classify_conflict(predicate)
                    conflicts.append(
                        Conflict(
                            subject=subject,
                            predicate=predicate,
                            values=values,
                            conflict_type=conflict_type,
                        )
                    )

        return conflicts

    def _classify_conflict(self, predicate: URIRef) -> ConflictType:
        """Classify the type of conflict based on the predicate.

        Args:
            predicate: The conflicting predicate

        Returns:
            ConflictType classification
        """
        pred_str = str(predicate)

        if predicate == RDF.type:
            return ConflictType.TYPE_DIFFERENCE

        if any(
            x in pred_str for x in ["subClassOf", "subPropertyOf", "equivalentClass"]
        ):
            return ConflictType.HIERARCHY_DIFFERENCE

        if "disjoint" in pred_str.lower():
            return ConflictType.SEMANTIC_CONTRADICTION

        return ConflictType.VALUE_DIFFERENCE


def generate_conflict_marker(conflict: Conflict, graph: Graph) -> str:
    """Generate a conflict marker comment for Turtle output.

    Args:
        conflict: The conflict to mark
        graph: Graph for namespace resolution

    Returns:
        Multi-line comment string marking the conflict
    """
    lines = []

    # Try to get a readable name for the subject
    try:
        subject_name = graph.namespace_manager.normalizeUri(conflict.subject)
    except Exception:
        subject_name = str(conflict.subject)

    try:
        pred_name = graph.namespace_manager.normalizeUri(conflict.predicate)
    except Exception:
        pred_name = str(conflict.predicate)

    lines.append(f"# === CONFLICT: {subject_name} {pred_name} ===")

    for cv in conflict.values:
        lines.append(f"# Source: {cv.source_path} (priority {cv.priority}): {cv}")

    if conflict.is_resolved and conflict.resolution:
        lines.append(f"# Resolution: Used {conflict.resolution} (highest priority)")
    else:
        lines.append("# Resolution: UNRESOLVED - values differ, manual review required")
        lines.append(
            "# To resolve: keep one value below, delete the other and this comment block"
        )

    return "\n".join(lines)


def generate_conflict_end_marker() -> str:
    """Generate the end marker for a conflict block.

    Returns:
        End marker comment string
    """
    return "# === END CONFLICT ==="


def filter_semantic_conflicts(conflicts: list[Conflict]) -> list[Conflict]:
    """Filter to only semantic contradictions that require attention.

    Semantic contradictions are logically incompatible assertions,
    such as declaring two classes both disjoint and related by subclass.

    Args:
        conflicts: All detected conflicts

    Returns:
        Only conflicts classified as semantic contradictions
    """
    return [c for c in conflicts if c.conflict_type == ConflictType.SEMANTIC_CONTRADICTION]
