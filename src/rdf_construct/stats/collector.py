"""Main statistics collector for RDF ontologies.

Orchestrates metric collection from multiple specialised collectors and
aggregates results into a single OntologyStats object.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rdflib import Graph

from rdf_construct.stats.metrics.basic import BasicStats, collect_basic_stats
from rdf_construct.stats.metrics.hierarchy import HierarchyStats, collect_hierarchy_stats
from rdf_construct.stats.metrics.properties import PropertyStats, collect_property_stats
from rdf_construct.stats.metrics.documentation import DocumentationStats, collect_documentation_stats
from rdf_construct.stats.metrics.complexity import ComplexityStats, collect_complexity_stats
from rdf_construct.stats.metrics.connectivity import ConnectivityStats, collect_connectivity_stats


@dataclass
class OntologyStats:
    """Complete statistics for an ontology.

    Aggregates metrics from all categories into a single structure.

    Attributes:
        source: Path to the source ontology file
        timestamp: When the stats were collected
        basic: Basic count metrics (triples, classes, properties)
        hierarchy: Hierarchy metrics (depth, branching, orphans)
        properties: Property metrics (domain/range coverage)
        documentation: Documentation coverage (labels, comments)
        complexity: Complexity indicators (multiple inheritance, axioms)
        connectivity: Connectivity metrics (most connected, isolated)
    """

    source: str
    timestamp: datetime
    basic: BasicStats
    hierarchy: HierarchyStats
    properties: PropertyStats
    documentation: DocumentationStats
    complexity: ComplexityStats
    connectivity: ConnectivityStats

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary for JSON serialisation.

        Returns:
            Dictionary representation of all statistics.
        """
        return {
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "basic": {
                "triples": self.basic.triples,
                "classes": self.basic.classes,
                "object_properties": self.basic.object_properties,
                "datatype_properties": self.basic.datatype_properties,
                "annotation_properties": self.basic.annotation_properties,
                "individuals": self.basic.individuals,
            },
            "hierarchy": {
                "root_classes": self.hierarchy.root_classes,
                "leaf_classes": self.hierarchy.leaf_classes,
                "max_depth": self.hierarchy.max_depth,
                "avg_depth": self.hierarchy.avg_depth,
                "avg_branching": self.hierarchy.avg_branching,
                "orphan_classes": self.hierarchy.orphan_classes,
                "orphan_rate": self.hierarchy.orphan_rate,
            },
            "properties": {
                "with_domain": self.properties.with_domain,
                "with_range": self.properties.with_range,
                "domain_coverage": self.properties.domain_coverage,
                "range_coverage": self.properties.range_coverage,
                "inverse_pairs": self.properties.inverse_pairs,
                "functional": self.properties.functional,
                "symmetric": self.properties.symmetric,
            },
            "documentation": {
                "classes_labelled": self.documentation.classes_labelled,
                "classes_labelled_pct": self.documentation.classes_labelled_pct,
                "classes_documented": self.documentation.classes_documented,
                "classes_documented_pct": self.documentation.classes_documented_pct,
                "properties_labelled": self.documentation.properties_labelled,
                "properties_labelled_pct": self.documentation.properties_labelled_pct,
            },
            "complexity": {
                "avg_properties_per_class": self.complexity.avg_properties_per_class,
                "avg_superclasses_per_class": self.complexity.avg_superclasses_per_class,
                "multiple_inheritance_count": self.complexity.multiple_inheritance_count,
                "owl_restriction_count": self.complexity.owl_restriction_count,
                "owl_equivalent_count": self.complexity.owl_equivalent_count,
            },
            "connectivity": {
                "most_connected_class": self.connectivity.most_connected_class,
                "most_connected_count": self.connectivity.most_connected_count,
                "isolated_classes": self.connectivity.isolated_classes,
            },
        }


# Category names for filtering
METRIC_CATEGORIES = frozenset({
    "basic",
    "hierarchy",
    "properties",
    "documentation",
    "complexity",
    "connectivity",
})


def collect_stats(
    graph: Graph,
    source: str | Path = "<graph>",
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> OntologyStats:
    """Collect comprehensive statistics for an ontology.

    Args:
        graph: The RDF graph to analyse.
        source: Source file path or identifier for reporting.
        include: Set of category names to include (default: all).
        exclude: Set of category names to exclude (default: none).

    Returns:
        OntologyStats containing all collected metrics.

    Raises:
        ValueError: If include/exclude contain unknown category names.
    """
    # Validate category names
    all_categories = METRIC_CATEGORIES
    if include:
        unknown = include - all_categories
        if unknown:
            raise ValueError(f"Unknown metric categories: {', '.join(sorted(unknown))}")
    if exclude:
        unknown = exclude - all_categories
        if unknown:
            raise ValueError(f"Unknown metric categories: {', '.join(sorted(unknown))}")

    # Determine which categories to collect
    categories = set(all_categories)
    if include:
        categories = include
    if exclude:
        categories = categories - exclude

    # Collect each category (use defaults for excluded ones)
    basic = collect_basic_stats(graph) if "basic" in categories else BasicStats()
    hierarchy = collect_hierarchy_stats(graph) if "hierarchy" in categories else HierarchyStats()
    properties = collect_property_stats(graph) if "properties" in categories else PropertyStats()
    documentation = (
        collect_documentation_stats(graph) if "documentation" in categories else DocumentationStats()
    )
    complexity = (
        collect_complexity_stats(graph) if "complexity" in categories else ComplexityStats()
    )
    connectivity = (
        collect_connectivity_stats(graph) if "connectivity" in categories else ConnectivityStats()
    )

    return OntologyStats(
        source=str(source),
        timestamp=datetime.now(),
        basic=basic,
        hierarchy=hierarchy,
        properties=properties,
        documentation=documentation,
        complexity=complexity,
        connectivity=connectivity,
    )
