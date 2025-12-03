"""Core merge logic for combining RDF ontologies.

This module provides the main OntologyMerger class that:
- Loads multiple source ontology files
- Detects and resolves conflicts
- Handles namespace remapping
- Manages owl:imports statements
- Writes merged output with conflict markers
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from rdflib import Graph, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, OWL

from rdf_construct.merge.config import (
    MergeConfig,
    SourceConfig,
    ConflictStrategy,
    ImportsStrategy,
)
from rdf_construct.merge.conflicts import (
    Conflict,
    ConflictDetector,
    SourceGraph,
    generate_conflict_marker,
    generate_conflict_end_marker,
)


@dataclass
class MergeResult:
    """Result of a merge operation.

    Attributes:
        merged_graph: The merged RDF graph
        conflicts: List of detected conflicts
        resolved_conflicts: Conflicts that were automatically resolved
        unresolved_conflicts: Conflicts requiring manual attention
        source_stats: Statistics per source file
        total_triples: Total triples in merged output
        success: Whether merge completed without errors
        error: Error message if success is False
    """

    merged_graph: Graph | None = None
    conflicts: list[Conflict] = field(default_factory=list)
    resolved_conflicts: list[Conflict] = field(default_factory=list)
    unresolved_conflicts: list[Conflict] = field(default_factory=list)
    source_stats: dict[str, int] = field(default_factory=dict)
    total_triples: int = 0
    success: bool = True
    error: str | None = None

    @property
    def has_conflicts(self) -> bool:
        """Check if any conflicts were detected."""
        return len(self.conflicts) > 0

    @property
    def has_unresolved(self) -> bool:
        """Check if there are unresolved conflicts."""
        return len(self.unresolved_conflicts) > 0


class OntologyMerger:
    """Merges multiple RDF ontology files with conflict detection.

    The merger:
    1. Loads all source files with priority metadata
    2. Builds a unified namespace map
    3. Detects conflicts (same subject+predicate, different values)
    4. Resolves conflicts according to the configured strategy
    5. Marks unresolved conflicts in the output
    6. Handles owl:imports according to configuration
    """

    def __init__(self, config: MergeConfig):
        """Initialize the merger.

        Args:
            config: Merge configuration
        """
        self.config = config
        self.detector = ConflictDetector(
            ignore_predicates=config.conflicts.ignore_predicates
        )

    def merge(self) -> MergeResult:
        """Execute the merge operation.

        Returns:
            MergeResult with merged graph and conflict information
        """
        result = MergeResult()

        # Load all source graphs
        sources: list[SourceGraph] = []
        for src_config in self.config.sources:
            try:
                source = self._load_source(src_config)
                sources.append(source)
                result.source_stats[src_config.path.name] = source.triple_count
            except Exception as e:
                result.success = False
                result.error = f"Failed to load {src_config.path}: {e}"
                return result

        if not sources:
            result.success = False
            result.error = "No source files to merge"
            return result

        # Detect conflicts
        result.conflicts = self.detector.detect_conflicts(sources)

        # Resolve conflicts
        self._resolve_conflicts(result.conflicts, result)

        # Create merged graph
        result.merged_graph = self._create_merged_graph(sources, result)
        result.total_triples = len(result.merged_graph)

        return result

    def _load_source(self, src_config: SourceConfig) -> SourceGraph:
        """Load a single source file.

        Args:
            src_config: Configuration for this source

        Returns:
            SourceGraph with loaded data

        Raises:
            FileNotFoundError: If source file doesn't exist
            ValueError: If source file can't be parsed
        """
        if not src_config.path.exists():
            raise FileNotFoundError(f"Source file not found: {src_config.path}")

        graph = Graph()

        # Determine format from extension
        ext = src_config.path.suffix.lower()
        format_map = {
            ".ttl": "turtle",
            ".turtle": "turtle",
            ".rdf": "xml",
            ".xml": "xml",
            ".owl": "xml",
            ".n3": "n3",
            ".nt": "nt",
            ".ntriples": "nt",
            ".jsonld": "json-ld",
            ".json": "json-ld",
        }
        rdf_format = format_map.get(ext, "turtle")

        try:
            graph.parse(src_config.path.as_posix(), format=rdf_format)
        except Exception as e:
            raise ValueError(f"Failed to parse {src_config.path}: {e}")

        # Apply namespace remapping if configured
        if src_config.namespace_remap:
            graph = self._remap_namespaces(graph, src_config.namespace_remap)

        return SourceGraph(
            graph=graph,
            path=str(src_config.path),
            priority=src_config.priority,
        )

    def _remap_namespaces(
        self, graph: Graph, remappings: dict[str, str]
    ) -> Graph:
        """Remap namespaces in a graph.

        Args:
            graph: Source graph to remap
            remappings: Mapping of old namespace -> new namespace

        Returns:
            New graph with remapped URIs
        """
        if not remappings:
            return graph

        new_graph = Graph()

        # Copy namespace bindings
        for prefix, ns in graph.namespace_manager.namespaces():
            ns_str = str(ns)
            if ns_str in remappings:
                new_graph.bind(prefix, Namespace(remappings[ns_str]))
            else:
                new_graph.bind(prefix, ns)

        # Remap triples
        for s, p, o in graph:
            new_s = self._remap_uri(s, remappings)
            new_p = self._remap_uri(p, remappings)
            new_o = self._remap_uri(o, remappings) if isinstance(o, URIRef) else o
            new_graph.add((new_s, new_p, new_o))

        return new_graph

    def _remap_uri(self, uri: URIRef, remappings: dict[str, str]) -> URIRef:
        """Remap a single URI according to namespace remappings.

        Args:
            uri: URI to remap
            remappings: Namespace remapping rules

        Returns:
            Remapped URI or original if no mapping applies
        """
        uri_str = str(uri)
        for old_ns, new_ns in remappings.items():
            if uri_str.startswith(old_ns):
                return URIRef(uri_str.replace(old_ns, new_ns, 1))
        return uri

    def _resolve_conflicts(
        self, conflicts: list[Conflict], result: MergeResult
    ) -> None:
        """Resolve conflicts according to configured strategy.

        Args:
            conflicts: Detected conflicts to resolve
            result: MergeResult to update with resolution info
        """
        strategy = self.config.conflicts.strategy

        for conflict in conflicts:
            if strategy == ConflictStrategy.PRIORITY:
                conflict.resolve_by_priority()
            elif strategy == ConflictStrategy.FIRST:
                conflict.resolve_by_first()
            elif strategy == ConflictStrategy.LAST:
                conflict.resolve_by_last()
            # MARK_ALL leaves conflicts unresolved

            if conflict.is_resolved:
                result.resolved_conflicts.append(conflict)
            else:
                result.unresolved_conflicts.append(conflict)

    def _create_merged_graph(
        self, sources: list[SourceGraph], result: MergeResult
    ) -> Graph:
        """Create the merged graph from sources.

        Args:
            sources: Source graphs to merge
            result: MergeResult with conflict information

        Returns:
            Merged RDF graph
        """
        merged = Graph()

        # Collect and merge namespace bindings
        for source in sources:
            for prefix, ns in source.graph.namespace_manager.namespaces():
                try:
                    merged.bind(prefix, ns, override=False)
                except Exception:
                    pass  # Skip conflicting bindings

        # Apply preferred prefixes from config
        for prefix, ns in self.config.namespaces.preferred_prefixes.items():
            merged.bind(prefix, Namespace(ns), override=True)

        # Add all triples from all sources
        for source in sources:
            for triple in source.graph:
                merged.add(triple)

        # Handle owl:imports
        merged = self._handle_imports(merged, sources)

        return merged

    def _handle_imports(
        self, merged: Graph, sources: list[SourceGraph]
    ) -> Graph:
        """Handle owl:imports statements according to strategy.

        Args:
            merged: The merged graph
            sources: Original source graphs

        Returns:
            Graph with imports handled
        """
        strategy = self.config.imports

        if strategy == ImportsStrategy.REMOVE:
            # Remove all owl:imports statements
            imports_to_remove = list(merged.triples((None, OWL.imports, None)))
            for triple in imports_to_remove:
                merged.remove(triple)

        elif strategy == ImportsStrategy.MERGE:
            # Deduplicate imports (already done by Graph.add())
            pass

        # PRESERVE and UPDATE are handled as-is for now
        # UPDATE would require knowing the output path to update references

        return merged

    def write_output(self, result: MergeResult, output_path: Path) -> None:
        """Write the merged graph to file with conflict markers.

        Args:
            result: MergeResult with merged graph and conflicts
            output_path: Path to write output file
        """
        if result.merged_graph is None:
            raise ValueError("No merged graph to write")

        # For now, serialize normally and then inject conflict markers
        # A more sophisticated approach would use a custom serializer
        turtle_output = result.merged_graph.serialize(format="turtle")

        # If there are unresolved conflicts, we need to add markers
        if result.unresolved_conflicts:
            turtle_output = self._inject_conflict_markers(
                turtle_output, result.unresolved_conflicts, result.merged_graph
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(turtle_output)

    def _inject_conflict_markers(
        self,
        turtle: str,
        conflicts: list[Conflict],
        graph: Graph,
    ) -> str:
        """Inject conflict markers into Turtle output.

        This is a simplified implementation that adds a conflict summary
        at the top of the file. A more sophisticated version would inline
        markers near the conflicting statements.

        Args:
            turtle: Original Turtle serialization
            conflicts: Unresolved conflicts to mark
            graph: Graph for namespace resolution

        Returns:
            Turtle string with conflict markers added
        """
        # Build conflict summary header
        header_lines = [
            "# ============================================================",
            "# MERGE CONFLICTS",
            f"# {len(conflicts)} unresolved conflict(s) require manual review",
            "# Search for '=== CONFLICT ===' to find each one",
            "# ============================================================",
            "",
        ]

        for conflict in conflicts:
            header_lines.append(generate_conflict_marker(conflict, graph))
            header_lines.append(generate_conflict_end_marker())
            header_lines.append("")

        header_lines.append("# ============================================================")
        header_lines.append("")

        return "\n".join(header_lines) + turtle


def merge_files(
    sources: list[Path],
    output: Path,
    priorities: list[int] | None = None,
    conflict_strategy: str = "priority",
    dry_run: bool = False,
) -> MergeResult:
    """Convenience function to merge files with minimal configuration.

    Args:
        sources: List of source file paths
        output: Output file path
        priorities: Optional list of priorities (same order as sources)
        conflict_strategy: Strategy name: priority, first, last, mark_all
        dry_run: If True, don't write output

    Returns:
        MergeResult with merge information
    """
    from .config import SourceConfig, OutputConfig, ConflictConfig, ConflictStrategy

    if priorities is None:
        priorities = list(range(1, len(sources) + 1))

    source_configs = [
        SourceConfig(path=p, priority=pri)
        for p, pri in zip(sources, priorities)
    ]

    strategy = ConflictStrategy[conflict_strategy.upper()]

    config = MergeConfig(
        sources=source_configs,
        output=OutputConfig(path=output),
        conflicts=ConflictConfig(strategy=strategy),
        dry_run=dry_run,
    )

    merger = OntologyMerger(config)
    result = merger.merge()

    if not dry_run and result.success and result.merged_graph:
        merger.write_output(result, output)

    return result
