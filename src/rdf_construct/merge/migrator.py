"""Data graph migration for ontology changes.

This module handles migrating instance data when ontologies change:
- Simple URI substitution (renames, namespace changes)
- Complex CONSTRUCT-style transformations (property splits, type migrations)

The migrator is reusable by merge, split, and refactor commands.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import RDF

from rdf_construct.core.utils import extract_prefix_map, rebase_by_rules
from rdf_construct.merge.config import MigrationRule, DataMigrationConfig
from rdf_construct.merge.prefixes import bind_exactly, combine_prefixes
from rdf_construct.merge.rules import ResolvedRule, RuleEngine, resolve_rules


@dataclass
class MigrationStats:
    """Statistics from a migration operation.

    Attributes:
        subjects_updated: Number of subject URIs substituted
        objects_updated: Number of object URIs substituted
        triples_added: Number of triples added by transformations
        triples_removed: Number of triples removed by transformations
        rules_applied: For each rule, the matches (transform) or positions substituted (rename)
        predicates_updated: Number of predicate URIs substituted
        rules_kept: For each transform rule, the matches left unchanged because a construct
            built no value (#492)
    """

    subjects_updated: int = 0
    objects_updated: int = 0
    triples_added: int = 0
    triples_removed: int = 0
    rules_applied: dict[str, int] = field(default_factory=dict)
    # Last, so that positional construction from before #415 keeps its meaning.
    predicates_updated: int = 0
    rules_kept: dict[str, int] = field(default_factory=dict)

    @property
    def total_changes(self) -> int:
        """Total number of changes made."""
        return (
            self.subjects_updated
            + self.predicates_updated
            + self.objects_updated
            + self.triples_added
            + self.triples_removed
        )


@dataclass
class MigrationResult:
    """Result of a data migration operation.

    Attributes:
        migrated_graph: The migrated RDF graph
        stats: Migration statistics
        success: Whether migration completed without errors
        error: Error message if success is False
        source_triples: Original triple count
        result_triples: Final triple count
        prefix_notes: One line per data-file prefix not written as declared (#358)
        unmatched_rules: The rules that matched nothing (transform) or substituted nothing
            (rename) in any data file, by the name the summary gives them (#492)
    """

    migrated_graph: Graph | None = None
    stats: MigrationStats = field(default_factory=MigrationStats)
    success: bool = True
    error: str | None = None
    source_triples: int = 0
    result_triples: int = 0
    prefix_notes: list[str] = field(default_factory=list)
    unmatched_rules: list[str] = field(default_factory=list)


class DataMigrator:
    """Migrates instance data graphs when ontology structure changes.

    Supports two types of migration:

    1. **Simple URI substitution**: Replaces URIs throughout the graph.
       Used for renames, namespace changes, and class/property moves.

    2. **Complex transformations**: SPARQL CONSTRUCT-style rules that can:
       - Split properties (fullName → givenName + familyName)
       - Merge properties
       - Change types (Company → Organisation)
       - Transform values (Fahrenheit → Celsius)

    Example usage:
        migrator = DataMigrator()
        uri_map = {
            URIRef("http://old.org/Class"): URIRef("http://new.org/Class")
        }
        result = migrator.migrate(data_graph, uri_map=uri_map)
    """

    def __init__(self) -> None:
        """Initialize the data migrator."""
        self.rule_engine = RuleEngine()

    def migrate(
        self,
        data: Graph,
        uri_map: dict[URIRef, URIRef] | None = None,
        rules: list[MigrationRule] | None = None,
        namespace_rules: Mapping[str, str] | None = None,
    ) -> MigrationResult:
        """Migrate a data graph.

        The migrated graph carries the data's own prefix bindings and no others, so a caller that
        combines several can tell a declaration from rdflib's table (#358).

        Args:
            data: Source data graph to migrate
            uri_map: Simple URI substitution map (old -> new)
            rules: Complex migration rules to apply
            namespace_rules: Old namespace -> new namespace; a prefix binding moves with its
                namespace, as `refactor rename` moves the ontology's (#358)

        Returns:
            MigrationResult with migrated graph and statistics

        Raises:
            RuleError: If a rule cannot be read against the data's own prefixes, before the
                data is touched (#492)
        """
        resolved = resolve_rules(rules, [(Path("data"), extract_prefix_map(data))]) if rules else []
        result, _ = self._migrate(data, uri_map, resolved, namespace_rules)
        return result

    def _migrate(
        self,
        data: Graph,
        uri_map: dict[URIRef, URIRef] | None,
        rules: Sequence[ResolvedRule],
        namespace_rules: Mapping[str, str] | None = None,
    ) -> tuple[MigrationResult, list[int]]:
        """Migrate a data graph with rules already resolved.

        Returns:
            The result, and for each rule the matches or positions substituted, so a caller
            combining several graphs can tell a rule that did nothing in any of them (#492)
        """
        result = MigrationResult()
        counts: list[int] = []
        result.source_triples = len(data)

        # Create a new graph for the migrated data. "core", so the data's own org: is not
        # pushed aside to org1: by rdflib's table (#358)
        migrated = Graph(bind_namespaces="core")

        # Copy namespace bindings, moving each one with its namespace
        for prefix, ns in data.namespace_manager.namespaces():
            moved = rebase_by_rules(str(ns), namespace_rules) if namespace_rules else None
            migrated.bind(prefix, ns if moved is None else moved)

        # Phase 1: Apply simple URI substitutions
        if uri_map:
            for s, p, o in data:
                new_s = self._substitute_uri(s, uri_map, result.stats, is_subject=True)
                new_p = self._substitute_predicate(p, uri_map, result.stats)
                new_o = self._substitute_uri(o, uri_map, result.stats, is_subject=False)
                migrated.add((new_s, new_p, new_o))
        else:
            # No substitutions, just copy
            for triple in data:
                migrated.add(triple)

        # Phase 2: Apply complex transformation rules, each one already resolved and checked
        stats = result.stats
        for rule in rules:
            label = rule.label
            if rule.from_iri is not None and rule.to_iri is not None:
                # Handle rename rules that weren't in uri_map
                before = stats.subjects_updated + stats.predicates_updated + stats.objects_updated
                migrated = self._apply_uri_substitution(
                    migrated, {rule.from_iri: rule.to_iri}, stats
                )
                count = (
                    stats.subjects_updated + stats.predicates_updated + stats.objects_updated
                ) - before
            else:
                changes = self.rule_engine.apply_rule(migrated, rule)
                stats.triples_added += changes["added"]
                stats.triples_removed += changes["removed"]
                count = changes["instances"]
                if changes["kept"]:
                    stats.rules_kept[label] = stats.rules_kept.get(label, 0) + changes["kept"]
            stats.rules_applied[label] = stats.rules_applied.get(label, 0) + count
            counts.append(count)

        result.migrated_graph = migrated
        result.result_triples = len(migrated)
        result.success = True
        result.unmatched_rules = [
            rule.label for rule, n in zip(rules, counts, strict=True) if n == 0
        ]

        return result, counts

    def _substitute_uri(
        self,
        term: Any,
        uri_map: dict[URIRef, URIRef],
        stats: MigrationStats,
        is_subject: bool,
    ) -> Any:
        """Substitute a URI if it's in the mapping.

        Args:
            term: RDF term to potentially substitute
            uri_map: URI substitution map
            stats: Statistics to update
            is_subject: Whether this is a subject position

        Returns:
            Substituted term or original
        """
        if isinstance(term, URIRef) and term in uri_map:
            if is_subject:
                stats.subjects_updated += 1
            else:
                stats.objects_updated += 1
            return uri_map[term]
        return term

    def _substitute_predicate(
        self,
        term: Any,
        uri_map: dict[URIRef, URIRef],
        stats: MigrationStats,
    ) -> Any:
        """Substitute a predicate URI if it's in the mapping.

        A renamed property must move in the data that uses it, or every instance triple is
        left on a property the ontology no longer declares (#415).

        Args:
            term: Predicate to potentially substitute
            uri_map: URI substitution map
            stats: Statistics to update

        Returns:
            Substituted term or original
        """
        if isinstance(term, URIRef) and term in uri_map:
            stats.predicates_updated += 1
            return uri_map[term]
        return term

    def _apply_uri_substitution(
        self,
        graph: Graph,
        uri_map: dict[URIRef, URIRef],
        stats: MigrationStats,
    ) -> Graph:
        """Apply URI substitution to an entire graph.

        Args:
            graph: Graph to transform
            uri_map: URI substitution map
            stats: Statistics to update

        Returns:
            New graph with substitutions applied
        """
        new_graph = Graph(bind_namespaces="core")

        # Copy namespace bindings, updating if needed
        for prefix, ns in graph.namespace_manager.namespaces():
            new_graph.bind(prefix, ns)

        for s, p, o in graph:
            new_s = self._substitute_uri(s, uri_map, stats, is_subject=True)
            new_p = self._substitute_predicate(p, uri_map, stats)
            new_o = self._substitute_uri(o, uri_map, stats, is_subject=False)
            new_graph.add((new_s, new_p, new_o))

        return new_graph

    def build_uri_map_from_namespaces(
        self,
        graph: Graph,
        namespace_remaps: dict[str, str],
    ) -> dict[URIRef, URIRef]:
        """Build a URI map from namespace remappings.

        Scans the graph for all URIs and creates substitution entries
        for those that fall within remapped namespaces.

        Args:
            graph: Graph to scan for URIs
            namespace_remaps: Old namespace -> new namespace mapping

        Returns:
            URI substitution map
        """
        uri_map: dict[URIRef, URIRef] = {}

        # Collect all URIs from the graph
        all_uris: set[URIRef] = set()
        for s, p, o in graph:
            if isinstance(s, URIRef):
                all_uris.add(s)
            if isinstance(p, URIRef):
                all_uris.add(p)
            if isinstance(o, URIRef):
                all_uris.add(o)

        # Build substitution map
        for uri in all_uris:
            new_uri_str = rebase_by_rules(str(uri), namespace_remaps)
            if new_uri_str is not None:
                uri_map[uri] = URIRef(new_uri_str)

        return uri_map


def migrate_data_files(
    data_paths: list[Path],
    uri_map: dict[URIRef, URIRef] | None = None,
    rules: list[MigrationRule] | None = None,
    output_path: Path | None = None,
) -> MigrationResult:
    """Convenience function to migrate multiple data files.

    Reads every file first, then migrates them with ``migrate_data_graphs``. A caller that must
    refuse a bad file before writing anything else (the ``merge`` command, #437) reads the files
    itself and calls ``migrate_data_graphs`` directly.

    Args:
        data_paths: Paths to data files to migrate
        uri_map: URI substitution map
        rules: Migration rules to apply
        output_path: Path to write combined migrated output

    Returns:
        MigrationResult with combined statistics, or with ``success`` False and ``error`` set
        when a file is missing or cannot be parsed, in which case nothing is written
    """
    graphs: list[tuple[Path, Graph]] = []
    for data_path in data_paths:
        if not data_path.exists():
            return MigrationResult(success=False, error=f"Data file not found: {data_path}")

        # Load the data file
        data = Graph(bind_namespaces="core")
        try:
            data.parse(data_path.as_posix())
        except Exception as e:
            return MigrationResult(success=False, error=f"Failed to parse {data_path}: {e}")
        graphs.append((data_path, data))

    return migrate_data_graphs(graphs, uri_map=uri_map, rules=rules, output_path=output_path)


def migrate_data_graphs(
    graphs: Sequence[tuple[Path, Graph]],
    uri_map: dict[URIRef, URIRef] | None = None,
    rules: list[MigrationRule] | None = None,
    output_path: Path | None = None,
    prefixes: Sequence[tuple[Path, Mapping[str, str]]] = (),
) -> MigrationResult:
    """Migrate data graphs that have already been read, and combine them into one.

    Args:
        graphs: Each data file's path, which names it in the prefix notes, with its parsed
            graph. Parse with ``Graph(bind_namespaces="core")``, so a file's own ``org:`` is
            not pushed aside to ``org1:`` by rdflib's table (#358).
        uri_map: URI substitution map
        rules: Migration rules to apply. A CURIE in one resolves once across every data file's
            prefixes and ``prefixes``; one no source binds, or two bind differently, is refused
            (#492).
        output_path: Path to write combined migrated output
        prefixes: More prefixes for the rules, each with the file that gives them: a merge
            config's ``namespaces.preferred_prefixes``, named by the config file

    Returns:
        MigrationResult with combined statistics

    Raises:
        RuleError: If a rule cannot be read, before any graph is migrated (#492)
    """
    resolved = (
        resolve_rules(
            rules,
            [*prefixes, *((path, extract_prefix_map(graph)) for path, graph in graphs)],
        )
        if rules
        else []
    )
    totals = [0] * len(resolved)
    migrator = DataMigrator()
    combined_result = MigrationResult()
    combined_graph = Graph(bind_namespaces="core")
    bindings: list[tuple[str, list[tuple[str, str]]]] = []
    combined_stats = MigrationStats()

    for data_path, data in graphs:
        # Migrate this file
        result, counts = migrator._migrate(data, uri_map, resolved)
        totals = [total + n for total, n in zip(totals, counts, strict=True)]

        if not result.success:
            return result

        # Combine results
        combined_result.source_triples += result.source_triples
        if result.migrated_graph:
            for triple in result.migrated_graph:
                combined_graph.add(triple)

            bindings.append(
                (data_path.name, [(p, str(ns)) for p, ns in result.migrated_graph.namespaces()])
            )

        # Combine stats
        combined_stats.subjects_updated += result.stats.subjects_updated
        combined_stats.predicates_updated += result.stats.predicates_updated
        combined_stats.objects_updated += result.stats.objects_updated
        combined_stats.triples_added += result.stats.triples_added
        combined_stats.triples_removed += result.stats.triples_removed
        for rule_name, count in result.stats.rules_applied.items():
            combined_stats.rules_applied[rule_name] = (
                combined_stats.rules_applied.get(rule_name, 0) + count
            )
        for rule_name, count in result.stats.rules_kept.items():
            combined_stats.rules_kept[rule_name] = (
                combined_stats.rules_kept.get(rule_name, 0) + count
            )

    # One prefix per namespace across every data file, decided as merge decides it (#358)
    # preferred_prefixes applies to the ontology only, so the notes offer no advice
    combined, combined_result.prefix_notes = combine_prefixes(bindings, advice="")
    bind_exactly(combined_graph, combined)

    combined_result.migrated_graph = combined_graph
    combined_result.stats = combined_stats
    combined_result.result_triples = len(combined_graph)
    combined_result.success = True
    combined_result.unmatched_rules = [
        rule.label for rule, total in zip(resolved, totals, strict=True) if total == 0
    ]

    # Write output if path provided
    if output_path and combined_result.migrated_graph:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined_result.migrated_graph.serialize(
            destination=output_path.as_posix(), format="turtle"
        )

    return combined_result
