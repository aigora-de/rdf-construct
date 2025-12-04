"""Data graph migration for ontology changes.

This module handles migrating instance data when ontologies change:
- Simple URI substitution (renames, namespace changes)
- Complex CONSTRUCT-style transformations (property splits, type migrations)

The migrator is reusable by merge, split, and refactor commands.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import RDF

from rdf_construct.merge.config import MigrationRule, DataMigrationConfig
from rdf_construct.merge.rules import RuleEngine


@dataclass
class MigrationStats:
    """Statistics from a migration operation.

    Attributes:
        subjects_updated: Number of subject URIs substituted
        objects_updated: Number of object URIs substituted
        triples_added: Number of triples added by transformations
        triples_removed: Number of triples removed by transformations
        rules_applied: Count of each rule applied
    """

    subjects_updated: int = 0
    objects_updated: int = 0
    triples_added: int = 0
    triples_removed: int = 0
    rules_applied: dict[str, int] = field(default_factory=dict)

    @property
    def total_changes(self) -> int:
        """Total number of changes made."""
        return (
            self.subjects_updated
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
    """

    migrated_graph: Graph | None = None
    stats: MigrationStats = field(default_factory=MigrationStats)
    success: bool = True
    error: str | None = None
    source_triples: int = 0
    result_triples: int = 0


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

    def __init__(self):
        """Initialize the data migrator."""
        self.rule_engine = RuleEngine()

    def migrate(
        self,
        data: Graph,
        uri_map: dict[URIRef, URIRef] | None = None,
        rules: list[MigrationRule] | None = None,
    ) -> MigrationResult:
        """Migrate a data graph.

        Args:
            data: Source data graph to migrate
            uri_map: Simple URI substitution map (old -> new)
            rules: Complex migration rules to apply

        Returns:
            MigrationResult with migrated graph and statistics
        """
        result = MigrationResult()
        result.source_triples = len(data)

        # Create a new graph for the migrated data
        migrated = Graph()

        # Copy namespace bindings
        for prefix, ns in data.namespace_manager.namespaces():
            migrated.bind(prefix, ns)

        # Phase 1: Apply simple URI substitutions
        if uri_map:
            for s, p, o in data:
                new_s = self._substitute_uri(s, uri_map, result.stats, is_subject=True)
                new_o = self._substitute_uri(o, uri_map, result.stats, is_subject=False)
                migrated.add((new_s, p, new_o))
        else:
            # No substitutions, just copy
            for triple in data:
                migrated.add(triple)

        # Phase 2: Apply complex transformation rules
        if rules:
            for rule in rules:
                if rule.type == "rename":
                    # Handle rename rules that weren't in uri_map
                    if rule.from_uri and rule.to_uri:
                        single_map = {
                            URIRef(rule.from_uri): URIRef(rule.to_uri)
                        }
                        migrated = self._apply_uri_substitution(
                            migrated, single_map, result.stats
                        )
                        result.stats.rules_applied[rule.description or "rename"] = (
                            result.stats.rules_applied.get(rule.description or "rename", 0) + 1
                        )

                elif rule.type == "transform":
                    changes = self.rule_engine.apply_rule(migrated, rule)
                    result.stats.triples_added += changes.get("added", 0)
                    result.stats.triples_removed += changes.get("removed", 0)
                    result.stats.rules_applied[rule.description or "transform"] = (
                        result.stats.rules_applied.get(rule.description or "transform", 0)
                        + changes.get("instances", 0)
                    )

        result.migrated_graph = migrated
        result.result_triples = len(migrated)
        result.success = True

        return result

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
        new_graph = Graph()

        # Copy namespace bindings, updating if needed
        for prefix, ns in graph.namespace_manager.namespaces():
            new_graph.bind(prefix, ns)

        for s, p, o in graph:
            new_s = self._substitute_uri(s, uri_map, stats, is_subject=True)
            new_o = self._substitute_uri(o, uri_map, stats, is_subject=False)
            new_graph.add((new_s, p, new_o))

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
            uri_str = str(uri)
            for old_ns, new_ns in namespace_remaps.items():
                if uri_str.startswith(old_ns):
                    new_uri_str = uri_str.replace(old_ns, new_ns, 1)
                    uri_map[uri] = URIRef(new_uri_str)
                    break

        return uri_map


def migrate_data_files(
    data_paths: list[Path],
    uri_map: dict[URIRef, URIRef] | None = None,
    rules: list[MigrationRule] | None = None,
    output_path: Path | None = None,
) -> MigrationResult:
    """Convenience function to migrate multiple data files.

    Args:
        data_paths: Paths to data files to migrate
        uri_map: URI substitution map
        rules: Migration rules to apply
        output_path: Path to write combined migrated output

    Returns:
        MigrationResult with combined statistics
    """
    migrator = DataMigrator()
    combined_result = MigrationResult()
    combined_graph = Graph()
    combined_stats = MigrationStats()

    for data_path in data_paths:
        if not data_path.exists():
            combined_result.success = False
            combined_result.error = f"Data file not found: {data_path}"
            return combined_result

        # Load the data file
        data = Graph()
        try:
            data.parse(data_path.as_posix())
        except Exception as e:
            combined_result.success = False
            combined_result.error = f"Failed to parse {data_path}: {e}"
            return combined_result

        # Migrate this file
        result = migrator.migrate(data, uri_map=uri_map, rules=rules)

        if not result.success:
            return result

        # Combine results
        combined_result.source_triples += result.source_triples
        if result.migrated_graph:
            for triple in result.migrated_graph:
                combined_graph.add(triple)

            # Copy namespace bindings
            for prefix, ns in result.migrated_graph.namespace_manager.namespaces():
                try:
                    combined_graph.bind(prefix, ns, override=False)
                except Exception:
                    pass

        # Combine stats
        combined_stats.subjects_updated += result.stats.subjects_updated
        combined_stats.objects_updated += result.stats.objects_updated
        combined_stats.triples_added += result.stats.triples_added
        combined_stats.triples_removed += result.stats.triples_removed
        for rule_name, count in result.stats.rules_applied.items():
            combined_stats.rules_applied[rule_name] = (
                combined_stats.rules_applied.get(rule_name, 0) + count
            )

    combined_result.migrated_graph = combined_graph
    combined_result.stats = combined_stats
    combined_result.result_triples = len(combined_graph)
    combined_result.success = True

    # Write output if path provided
    if output_path and combined_result.migrated_graph:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined_result.migrated_graph.serialize(
            destination=output_path.as_posix(), format="turtle"
        )

    return combined_result
