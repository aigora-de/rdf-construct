"""Conflict detection and resolution for ontology merging.

This module handles:
- Detecting where sources disagree on a predicate whose second value is a real conflict
- Resolving conflicts based on configured strategy
- Marking unresolved conflicts in output
- Generating conflict reports

Which predicates can conflict at all, and how, is `rdf_construct.core.predicate_tiers`.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum, auto

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS
from rdflib.term import Node

from rdf_construct.core.predicate_tiers import (
    MALFORMED_WHEN_REPEATED,
    PredicateTier,
    build_tiers,
    language_bucket,
    value_key,
)


class ConflictType(Enum):
    """Classification of conflict types, by what a second value means."""

    AMBIGUOUS = auto()  # Legal, but two names in one language tag (rdfs:label)
    MALFORMED = auto()  # Breaks the predicate's specification (skos:prefLabel, SKOS S14)
    CHANGES_MEANING = auto()  # Load-bearing: both values together say something new


@dataclass
class ConflictValue:
    """A single value in a conflict.

    Attributes:
        value: The RDF value (Literal, URIRef, or BNode)
        source_path: Path to the source file
        priority: Priority of the source
        source_index: Position of the source in the merge, which tells apart two sources with
            the same path
    """

    value: Node
    source_path: str
    priority: int
    source_index: int = 0

    def __str__(self) -> str:
        """Return string representation of the value."""
        if isinstance(self.value, Literal):
            lang = f"@{self.value.language}" if self.value.language else ""
            dtype = f"^^{self.value.datatype}" if self.value.datatype else ""
            return f'"{self.value}"{lang}{dtype}'
        return str(self.value)


@dataclass(frozen=True)
class ConflictSource:
    """A source that asserts the conflicting subject and predicate.

    Attributes:
        path: Path to the source file
        priority: Priority of the source
        index: Position of the source in the merge
    """

    path: str
    priority: int
    index: int = 0


def _source_of(cv: ConflictValue) -> ConflictSource:
    return ConflictSource(cv.source_path, cv.priority, cv.source_index)


@dataclass
class Conflict:
    """Sources that disagree on one subject and predicate (and language tag, where it counts).

    The sources disagree when merging them would assert a combination of values that no one of
    them asserts. A source that asserts a subset of another's values agrees with it.

    Attributes:
        subject: The subject URI where conflict occurs
        predicate: The predicate where conflict occurs
        values: The values not every asserting source shares, one entry per source asserting it
        conflict_type: Classification of the conflict
        tier: The predicate's tier
        language: The (lower-cased) language tag of a per-language conflict, or None
        sources: Every source asserting the subject and predicate, in merge order
        functional: Whether a source declares the predicate an owl:FunctionalProperty
        winner: The source whose values were kept, if the conflict was resolved
        is_resolved: Whether the conflict was automatically resolved
        unpicked: Why no source was picked, if none was
    """

    subject: URIRef | BNode
    predicate: URIRef
    values: list[ConflictValue]
    conflict_type: ConflictType = ConflictType.AMBIGUOUS
    tier: PredicateTier = PredicateTier.PER_LANGUAGE
    language: str | None = None
    sources: list[ConflictSource] = field(default_factory=list)
    functional: bool = False
    winner: ConflictSource | None = None
    is_resolved: bool = False
    unpicked: str | None = None

    @property
    def requires_attention(self) -> bool:
        """Check if this conflict requires manual attention."""
        return not self.is_resolved

    @property
    def kept(self) -> list[ConflictValue]:
        """The listed values the winning source asserts."""
        if self.winner is None:
            return []
        return [cv for cv in self.values if _source_of(cv) == self.winner]

    @property
    def discarded(self) -> list[ConflictValue]:
        """The listed values only losing sources assert: these are removed from the output."""
        if self.winner is None:
            return []
        kept = {value_key(cv.value) for cv in self.kept}
        return [
            cv
            for cv in self.values
            if _source_of(cv) != self.winner and value_key(cv.value) not in kept
        ]

    def _asserting(self) -> list[ConflictSource]:
        if self.sources:
            return self.sources
        return list(dict.fromkeys(_source_of(cv) for cv in self.values))

    def _listed(self, source: ConflictSource) -> frozenset[Node]:
        return frozenset(value_key(cv.value) for cv in self.values if _source_of(cv) == source)

    def _pickable(self) -> bool:
        # A load-bearing conflict is always marked; a strategy has no basis to choose (#169)
        if self.tier is PredicateTier.LOAD_BEARING:
            return False
        # Only literals are ever removed, so no blank-node structure loses its referrer
        if not all(isinstance(cv.value, Literal) for cv in self.values):
            self.unpicked = "a value is not a literal, and only literals are ever removed"
            return False
        return True

    def _pick(self, source: ConflictSource) -> None:
        self.winner = source
        self.is_resolved = True
        self.unpicked = None

    def resolve_by_priority(self) -> None:
        """Resolve conflict by keeping the highest-priority source's values.

        Sources tied at the highest priority that disagree with each other are not picked between.
        """
        sources = self._asserting()
        if not sources or not self._pickable():
            return
        top = max(s.priority for s in sources)
        tied = [s for s in sources if s.priority == top]
        if len({self._listed(s) for s in tied}) > 1:
            self.unpicked = (
                f"sources tied at priority {top}; give them different priorities, "
                "or use --strategy first or last"
            )
            return
        self._pick(tied[0])

    def resolve_by_first(self) -> None:
        """Resolve conflict by keeping the first asserting source's values."""
        sources = self._asserting()
        if sources and self._pickable():
            self._pick(sources[0])

    def resolve_by_last(self) -> None:
        """Resolve conflict by keeping the last asserting source's values."""
        sources = self._asserting()
        if sources and self._pickable():
            self._pick(sources[-1])


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

    A conflict occurs when sources assert different values for one subject and a predicate whose
    tier makes a second value a conflict, and merging them would assert a combination no one
    source asserts. Two values from one source never conflict, so a file merged alone or with
    itself has none. A source declaring a predicate owl:FunctionalProperty makes it load-bearing,
    unless the configuration places it.
    """

    def __init__(
        self,
        ignore_predicates: set[str] | None = None,
        predicate_tiers: Mapping[str, Iterable[str]] | None = None,
    ):
        """Initialize the conflict detector.

        Args:
            ignore_predicates: Predicates that are never a conflict (repeatable)
            predicate_tiers: Tier name (repeatable, per_language, load_bearing) to predicates

        Raises:
            ValueError: If a tier name is unknown, or a predicate is placed in two tiers
        """
        self.ignore_predicates: set[URIRef] = set()
        if ignore_predicates:
            self.ignore_predicates = {URIRef(p) for p in ignore_predicates}

        overrides: dict[PredicateTier, list[URIRef]] = {
            PredicateTier.REPEATABLE: sorted(self.ignore_predicates)
        }
        for name, predicates in (predicate_tiers or {}).items():
            overrides.setdefault(PredicateTier(name), []).extend(URIRef(p) for p in predicates)
        self.configured: set[URIRef] = {p for ps in overrides.values() for p in ps}
        self.tiers: dict[URIRef, PredicateTier] = build_tiers(overrides)

    def detect_conflicts(self, sources: list[SourceGraph]) -> list[Conflict]:
        """Detect conflicts across multiple source graphs.

        Args:
            sources: List of source graphs to compare

        Returns:
            List of detected conflicts
        """
        tiers = dict(self.tiers)
        functional: set[URIRef] = set()
        headers: set[Node] = set()
        for source in sources:
            for s in source.graph.subjects(RDF.type, OWL.FunctionalProperty):
                if isinstance(s, URIRef) and s not in self.configured:
                    functional.add(s)
            headers.update(source.graph.subjects(RDF.type, OWL.Ontology))
        for predicate in functional:
            tiers[predicate] = PredicateTier.LOAD_BEARING
        checked = [p for p, tier in tiers.items() if tier is not PredicateTier.REPEATABLE]

        # (subject, predicate, language) -> source index -> compared value -> values as written
        index: dict[tuple[URIRef, URIRef, str | None], dict[int, dict[Node, list[Node]]]] = {}
        for i, source in enumerate(sources):
            for predicate in checked:
                per_language = tiers[predicate] is PredicateTier.PER_LANGUAGE
                for s, o in source.graph.subject_objects(predicate):
                    # A blank node is labelled by its content, every triple on it included
                    # (#170), so two sources share one only where they agree on all of it
                    if not isinstance(s, URIRef):
                        continue
                    # The ontology header is #171's to merge; until then both pass through
                    if s in headers:
                        continue
                    bucket = language_bucket(o) if per_language else None
                    by_source = index.setdefault((s, predicate, bucket), {})
                    by_source.setdefault(i, {}).setdefault(value_key(o), []).append(o)

        conflicts: list[Conflict] = []
        for (subject, predicate, bucket), by_source in index.items():
            if len(by_source) < 2:
                continue
            sets = [frozenset(by_key) for by_key in by_source.values()]
            union = frozenset().union(*sets)
            if union in sets:
                continue
            common = frozenset.intersection(*sets)
            values = [
                ConflictValue(o, sources[i].path, sources[i].priority, i)
                for i, by_key in by_source.items()
                for key, written in by_key.items()
                if key not in common
                for o in written
            ]
            tier = tiers[predicate]
            conflicts.append(
                Conflict(
                    subject=subject,
                    predicate=predicate,
                    values=values,
                    conflict_type=self._classify_conflict(predicate, tier),
                    tier=tier,
                    language=bucket,
                    sources=[
                        ConflictSource(sources[i].path, sources[i].priority, i) for i in by_source
                    ],
                    functional=predicate in functional,
                )
            )

        return conflicts

    def _classify_conflict(self, predicate: URIRef, tier: PredicateTier) -> ConflictType:
        """Classify the type of conflict based on the predicate and its tier.

        Args:
            predicate: The conflicting predicate
            tier: The predicate's tier

        Returns:
            ConflictType classification
        """
        if tier is PredicateTier.LOAD_BEARING:
            return ConflictType.CHANGES_MEANING
        if predicate in MALFORMED_WHEN_REPEATED:
            return ConflictType.MALFORMED
        return ConflictType.AMBIGUOUS


def _name(graph: Graph, term: URIRef | BNode) -> str:
    try:
        return graph.namespace_manager.normalizeUri(term)
    except Exception:
        return str(term)


def _tagged(conflict: Conflict) -> str:
    return f"tagged @{conflict.language}" if conflict.language else "with no language tag"


def conflict_explanation(conflict: Conflict, graph: Graph) -> list[str]:
    """Say what a conflict means and how to settle it, one sentence per line.

    Args:
        conflict: The conflict to explain
        graph: Graph for namespace resolution

    Returns:
        Lines of explanation, without comment markers
    """
    pred = _name(graph, conflict.predicate)
    if conflict.conflict_type is ConflictType.CHANGES_MEANING:
        if conflict.functional:
            why = (
                f"{pred} is declared owl:FunctionalProperty, so two values make the ontology "
                "inconsistent (literals) or make the values one individual (IRIs)."
            )
        elif conflict.predicate in (RDFS.domain, RDFS.range):
            why = (
                f"two {pred} values mean their intersection, which no source said; "
                "both are kept."
            )
        else:
            why = f"{pred} is load-bearing in this merge's configuration; both values are kept."
        settle = (
            "delete the value you do not mean, then this block."
            if conflict.functional
            else "if every value is meant, delete this block; "
            "otherwise delete the value you do not mean, then this block."
        )
        return [
            f"Changes meaning: {why}",
            "Not picked under any --strategy.",
            f"To resolve: {settle}",
        ]

    if conflict.conflict_type is ConflictType.MALFORMED:
        lines = [
            f"Malformed: SKOS allows one {pred} per language tag (S14), and the merged "
            f"values {_tagged(conflict)} are more than one; both are kept."
        ]
        settle = "keep one, or demote the others to skos:altLabel, then delete this block."
    else:
        lines = [
            f"Ambiguous: two {pred} values {_tagged(conflict)} are legal RDF, but a reader "
            "cannot tell which is the name; both are kept."
        ]
        settle = "delete the value you do not mean, then this block."
    if conflict.unpicked:
        lines.append(f"Not picked: {conflict.unpicked}.")
    lines.append(f"To resolve: {settle}")
    return lines


def generate_conflict_marker(conflict: Conflict, graph: Graph) -> str:
    """Generate a conflict marker comment for Turtle output.

    Args:
        conflict: The conflict to mark
        graph: Graph for namespace resolution

    Returns:
        Multi-line comment string marking the conflict
    """
    lines = []

    subject_name = _name(graph, conflict.subject)
    pred_name = _name(graph, conflict.predicate)

    lines.append(f"# === CONFLICT: {subject_name} {pred_name} ===")

    for cv in conflict.values:
        lines.append(f"# Source: {cv.source_path} (priority {cv.priority}): {cv}")

    if conflict.is_resolved and conflict.winner:
        removed = len(conflict.discarded)
        lines.append(
            f"# Resolution: kept {conflict.winner.path} (priority {conflict.winner.priority}); "
            f"removed {removed} value(s)"
        )
    else:
        lines.extend(f"# {line}" for line in conflict_explanation(conflict, graph))

    return "\n".join(lines)


def generate_conflict_end_marker() -> str:
    """Generate the end marker for a conflict block.

    Returns:
        End marker comment string
    """
    return "# === END CONFLICT ==="
