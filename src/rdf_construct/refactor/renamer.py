"""URI renaming logic for ontology refactoring.

This module handles renaming URIs in RDF graphs:
- Single entity renames (fixing typos, etc.)
- Bulk namespace changes (project/org renames)
- Predicate position handling (URIs as predicates are also renamed)

The renamer does NOT modify text inside literals - comments mentioning
renamed entities are left unchanged (this is intentional to avoid
corrupting documentation).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef, Literal, BNode

from rdf_construct.refactor.config import RenameConfig, RenameMapping


@dataclass
class RenameStats:
    """Statistics from a rename operation.

    Attributes:
        subjects_renamed: URIs renamed in subject position.
        predicates_renamed: URIs renamed in predicate position.
        objects_renamed: URIs renamed in object position.
        entities_by_source: Count of entities by mapping source.
        literal_mentions: Count of mentions in literals (NOT renamed).
    """

    subjects_renamed: int = 0
    predicates_renamed: int = 0
    objects_renamed: int = 0
    entities_by_source: dict[str, int] = field(default_factory=dict)
    literal_mentions: dict[str, int] = field(default_factory=dict)

    @property
    def total_renames(self) -> int:
        """Total number of URI substitutions made."""
        return self.subjects_renamed + self.predicates_renamed + self.objects_renamed

    @property
    def namespace_entities(self) -> int:
        """Number of entities renamed by namespace rules."""
        return self.entities_by_source.get("namespace", 0)

    @property
    def explicit_entities(self) -> int:
        """Number of entities renamed by explicit rules."""
        return self.entities_by_source.get("explicit", 0)


@dataclass
class RenameResult:
    """Result of a rename operation.

    Attributes:
        renamed_graph: The graph with URIs renamed.
        stats: Rename statistics.
        success: Whether the operation succeeded.
        error: Error message if success is False.
        mappings_applied: List of mappings that were actually applied.
        source_triples: Original triple count.
        result_triples: Final triple count.
    """

    renamed_graph: Graph | None = None
    stats: RenameStats = field(default_factory=RenameStats)
    success: bool = True
    error: str | None = None
    mappings_applied: list[RenameMapping] = field(default_factory=list)
    source_triples: int = 0
    result_triples: int = 0


class OntologyRenamer:
    """Renames URIs in RDF ontology graphs.

    Handles both single entity renames and bulk namespace changes.
    The renamer processes subjects, predicates, and objects, but
    intentionally leaves literal values unchanged.

    Example usage:
        renamer = OntologyRenamer()
        config = RenameConfig(entities={
            "http://example.org/Buiding": "http://example.org/Building"
        })
        result = renamer.rename(graph, config)
    """

    def rename(
        self,
        graph: Graph,
        config: RenameConfig,
    ) -> RenameResult:
        """Rename URIs in a graph according to configuration.

        Args:
            graph: Source RDF graph.
            config: Rename configuration with namespace and entity mappings.

        Returns:
            RenameResult with the modified graph and statistics.
        """
        result = RenameResult()
        result.source_triples = len(graph)

        # Build concrete mappings from config
        mappings = config.build_mappings(graph)
        if not mappings:
            # Nothing to rename
            result.renamed_graph = graph
            result.result_triples = len(graph)
            return result

        # Create URI lookup map for efficient substitution
        uri_map: dict[URIRef, tuple[URIRef, str]] = {
            m.from_uri: (m.to_uri, m.source) for m in mappings
        }

        # Track which mappings were actually applied
        applied_mappings: set[URIRef] = set()

        # Create new graph with renamed URIs
        renamed_graph = Graph()

        # Copy namespace bindings, updating if needed
        old_ns_to_new: dict[str, str] = {}
        if config.namespaces:
            old_ns_to_new = config.namespaces

        for prefix, ns in graph.namespace_manager.namespaces():
            ns_str = str(ns)
            new_ns_str = ns_str
            for old_ns, new_ns in old_ns_to_new.items():
                if ns_str.startswith(old_ns) or ns_str == old_ns:
                    new_ns_str = ns_str.replace(old_ns, new_ns, 1)
                    break
            renamed_graph.bind(prefix, new_ns_str, override=True)

        # Process each triple
        for s, p, o in graph:
            new_s, new_p, new_o = s, p, o

            # Check subject
            if isinstance(s, URIRef) and s in uri_map:
                new_s = uri_map[s][0]
                result.stats.subjects_renamed += 1
                applied_mappings.add(s)
                source = uri_map[s][1]
                result.stats.entities_by_source[source] = (
                    result.stats.entities_by_source.get(source, 0) + 1
                )

            # Check predicate
            if isinstance(p, URIRef) and p in uri_map:
                new_p = uri_map[p][0]
                result.stats.predicates_renamed += 1
                applied_mappings.add(p)
                # Don't double-count in entities_by_source

            # Check object (only URIRefs, not Literals)
            if isinstance(o, URIRef) and o in uri_map:
                new_o = uri_map[o][0]
                result.stats.objects_renamed += 1
                applied_mappings.add(o)
                # Don't double-count in entities_by_source

            renamed_graph.add((new_s, new_p, new_o))

        # Scan for literal mentions (informational only)
        for mapping in mappings:
            old_local = str(mapping.from_uri).split("#")[-1].split("/")[-1]
            for s, p, o in graph:
                if isinstance(o, Literal) and old_local in str(o):
                    key = str(mapping.from_uri)
                    result.stats.literal_mentions[key] = (
                        result.stats.literal_mentions.get(key, 0) + 1
                    )

        # Build list of applied mappings
        result.mappings_applied = [m for m in mappings if m.from_uri in applied_mappings]

        result.renamed_graph = renamed_graph
        result.result_triples = len(renamed_graph)
        result.success = True

        return result

    def rename_single(
        self,
        graph: Graph,
        from_uri: str,
        to_uri: str,
    ) -> RenameResult:
        """Convenience method for renaming a single URI.

        Args:
            graph: Source RDF graph.
            from_uri: URI to rename.
            to_uri: New URI.

        Returns:
            RenameResult with the modified graph.
        """
        config = RenameConfig(entities={from_uri: to_uri})
        return self.rename(graph, config)

    def rename_namespace(
        self,
        graph: Graph,
        from_namespace: str,
        to_namespace: str,
    ) -> RenameResult:
        """Convenience method for bulk namespace rename.

        Args:
            graph: Source RDF graph.
            from_namespace: Old namespace prefix.
            to_namespace: New namespace prefix.

        Returns:
            RenameResult with the modified graph.
        """
        config = RenameConfig(namespaces={from_namespace: to_namespace})
        return self.rename(graph, config)


def rename_file(
    source_path: Path,
    output_path: Path,
    config: RenameConfig,
) -> RenameResult:
    """Convenience function to rename URIs in a file.

    Args:
        source_path: Path to source RDF file.
        output_path: Path to write renamed output.
        config: Rename configuration.

    Returns:
        RenameResult with statistics.
    """
    # Load source graph
    graph = Graph()
    try:
        graph.parse(source_path.as_posix())
    except Exception as e:
        result = RenameResult()
        result.success = False
        result.error = f"Failed to parse {source_path}: {e}"
        return result

    # Perform rename
    renamer = OntologyRenamer()
    result = renamer.rename(graph, config)

    if not result.success:
        return result

    # Write output
    if result.renamed_graph:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.renamed_graph.serialize(destination=output_path.as_posix(), format="turtle")

    return result


def rename_files(
    source_paths: list[Path],
    output_dir: Path,
    config: RenameConfig,
) -> list[tuple[Path, RenameResult]]:
    """Rename URIs in multiple files.

    Args:
        source_paths: Paths to source RDF files.
        output_dir: Directory to write renamed outputs.
        config: Rename configuration.

    Returns:
        List of (output_path, result) tuples.
    """
    results: list[tuple[Path, RenameResult]] = []

    for source_path in source_paths:
        output_path = output_dir / source_path.name
        result = rename_file(source_path, output_path, config)
        results.append((output_path, result))

    return results
