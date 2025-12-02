"""Merge generated RDF with existing ontologies.

This module provides functionality to merge newly generated RDF
from PlantUML with existing ontology files, preserving manually
added content while updating what's defined in the diagram.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rdflib import Graph, Namespace, URIRef, RDF, RDFS
from rdflib.namespace import OWL


@dataclass
class MergeResult:
    """Result of merging two graphs.

    Attributes:
        graph: The merged graph
        added_count: Number of triples added from new graph
        updated_count: Number of triples updated (replaced)
        preserved_count: Number of triples preserved from existing
        conflicts: List of conflict descriptions
    """

    graph: Graph
    added_count: int = 0
    updated_count: int = 0
    preserved_count: int = 0
    conflicts: list[str] = None

    def __post_init__(self):
        if self.conflicts is None:
            self.conflicts = []


class OntologyMerger:
    """Merges generated RDF with existing ontology content.

    The merger follows these principles:
    1. Entities defined in PlantUML are authoritative - their
       rdfs:subClassOf, domain, range etc. are updated
    2. Additional annotations (comments, labels) in the existing
       file are preserved if not explicitly defined in PlantUML
    3. Entities only in the existing file are preserved
    4. Conflicts are reported but existing content wins by default

    Example:
        merger = OntologyMerger()
        result = merger.merge(new_graph, existing_path)
        result.graph.serialize("merged.ttl", format="turtle")
    """

    # Predicates that PlantUML defines authoritatively
    AUTHORITATIVE_PREDICATES = {
        RDF.type,
        RDFS.subClassOf,
        RDFS.domain,
        RDFS.range,
        RDFS.subPropertyOf,
    }

    # Predicates to merge (keep both if different)
    MERGEABLE_PREDICATES = {
        RDFS.label,
        RDFS.comment,
        RDFS.seeAlso,
    }

    def __init__(self, preserve_existing: bool = True) -> None:
        """Initialise the merger.

        Args:
            preserve_existing: If True, existing content wins on conflict
        """
        self.preserve_existing = preserve_existing

    def merge(
        self,
        new_graph: Graph,
        existing_path: Path,
        output_format: str = "turtle",
    ) -> MergeResult:
        """Merge new graph with existing ontology file.

        Args:
            new_graph: Newly generated RDF graph
            existing_path: Path to existing ontology file
            output_format: RDF format for parsing existing file

        Returns:
            MergeResult with merged graph and statistics
        """
        # Load existing graph
        existing = Graph()
        existing.parse(str(existing_path), format=output_format)

        return self.merge_graphs(new_graph, existing)

    def merge_graphs(
        self,
        new_graph: Graph,
        existing: Graph,
    ) -> MergeResult:
        """Merge two graphs.

        Args:
            new_graph: Newly generated RDF graph
            existing: Existing ontology graph

        Returns:
            MergeResult with merged graph and statistics
        """
        result = MergeResult(graph=Graph())
        conflicts = []

        # Copy all prefixes from both
        for prefix, ns in existing.namespace_manager.namespaces():
            result.graph.bind(prefix, ns, override=False)
        for prefix, ns in new_graph.namespace_manager.namespaces():
            result.graph.bind(prefix, ns, override=False)

        # Get all subjects defined in new graph
        new_subjects = set(new_graph.subjects())

        # Process existing triples
        for s, p, o in existing:
            if s in new_subjects:
                # Subject is also in new graph - check for conflicts
                if p in self.AUTHORITATIVE_PREDICATES:
                    # New graph is authoritative for these
                    new_values = set(new_graph.objects(s, p))
                    if new_values:
                        # Will be added from new graph
                        result.updated_count += 1
                        continue
                    else:
                        # Keep existing if not in new
                        result.graph.add((s, p, o))
                        result.preserved_count += 1
                elif p in self.MERGEABLE_PREDICATES:
                    # Keep existing and add new if different
                    result.graph.add((s, p, o))
                    result.preserved_count += 1
                else:
                    # Other predicates - preserve existing
                    result.graph.add((s, p, o))
                    result.preserved_count += 1
            else:
                # Subject only in existing - preserve
                result.graph.add((s, p, o))
                result.preserved_count += 1

        # Add triples from new graph
        for s, p, o in new_graph:
            if (s, p, o) not in result.graph:
                # Check for conflicting values on authoritative predicates
                if p in self.AUTHORITATIVE_PREDICATES:
                    existing_values = list(result.graph.objects(s, p))
                    for ev in existing_values:
                        if ev != o:
                            conflicts.append(
                                f"Conflict on {s} {p}: existing={ev}, new={o}"
                            )
                            if not self.preserve_existing:
                                result.graph.remove((s, p, ev))

                result.graph.add((s, p, o))
                result.added_count += 1

        result.conflicts = conflicts
        return result


def merge_with_existing(
    new_graph: Graph,
    existing_path: Path,
    output_path: Optional[Path] = None,
    output_format: str = "turtle",
) -> MergeResult:
    """Convenience function to merge and optionally save.

    Args:
        new_graph: Newly generated RDF graph
        existing_path: Path to existing ontology
        output_path: Path to write merged result (optional)
        output_format: RDF serialization format

    Returns:
        MergeResult with merged graph and statistics
    """
    merger = OntologyMerger()
    result = merger.merge(new_graph, existing_path, output_format)

    if output_path:
        result.graph.serialize(str(output_path), format=output_format)

    return result
