"""Ontology statistics comparison.

Compares statistics between two ontology versions and generates change summaries.
"""

from dataclasses import dataclass, field
from typing import Any

from rdf_construct.stats.collector import OntologyStats


@dataclass
class MetricChange:
    """A change in a single metric between two versions.

    Attributes:
        category: The metric category (e.g., "basic", "hierarchy").
        metric: The metric name (e.g., "classes", "max_depth").
        old_value: Value in the old/baseline version.
        new_value: Value in the new version.
        delta: Numeric difference (new - old).
        pct_change: Percentage change (may be None for non-numeric).
        improved: Whether the change is an improvement (context-dependent).
    """

    category: str
    metric: str
    old_value: Any
    new_value: Any
    delta: float | int | None = None
    pct_change: float | None = None
    improved: bool | None = None


@dataclass
class ComparisonResult:
    """Result of comparing two ontology versions.

    Attributes:
        old_source: Path/identifier of the old version.
        new_source: Path/identifier of the new version.
        changes: List of metric changes.
        summary: Human-readable summary of the comparison.
    """

    old_source: str
    new_source: str
    changes: list[MetricChange] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert comparison to dictionary for JSON serialisation."""
        return {
            "old_source": self.old_source,
            "new_source": self.new_source,
            "changes": [
                {
                    "category": c.category,
                    "metric": c.metric,
                    "old_value": c.old_value,
                    "new_value": c.new_value,
                    "delta": c.delta,
                    "pct_change": c.pct_change,
                    "improved": c.improved,
                }
                for c in self.changes
            ],
            "summary": self.summary,
        }


def _pct_change(old: float | int, new: float | int) -> float | None:
    """Calculate percentage change between two values.

    Args:
        old: Original value.
        new: New value.

    Returns:
        Percentage change, or None if old is zero.
    """
    if old == 0:
        return None
    return round(((new - old) / old) * 100, 1)


def _is_improvement(category: str, metric: str, delta: float | int) -> bool | None:
    """Determine if a metric change is an improvement.

    Some metrics are better when higher (e.g., documentation coverage),
    others are better when lower (e.g., orphan rate).

    Args:
        category: The metric category.
        metric: The metric name.
        delta: The change in value.

    Returns:
        True if improved, False if degraded, None if neutral.
    """
    # Metrics where higher is better
    higher_is_better = {
        ("basic", "classes"),
        ("basic", "object_properties"),
        ("basic", "datatype_properties"),
        ("documentation", "classes_labelled"),
        ("documentation", "classes_labelled_pct"),
        ("documentation", "classes_documented"),
        ("documentation", "classes_documented_pct"),
        ("documentation", "properties_labelled"),
        ("documentation", "properties_labelled_pct"),
        ("properties", "with_domain"),
        ("properties", "with_range"),
        ("properties", "domain_coverage"),
        ("properties", "range_coverage"),
    }

    # Metrics where lower is better
    lower_is_better = {
        ("hierarchy", "orphan_classes"),
        ("hierarchy", "orphan_rate"),
        ("connectivity", "isolated_classes"),
    }

    key = (category, metric)
    if key in higher_is_better:
        return delta > 0
    if key in lower_is_better:
        return delta < 0

    # Neutral - neither better nor worse
    return None


def _extract_numeric_metrics(stats: OntologyStats) -> dict[tuple[str, str], float | int]:
    """Extract all numeric metrics from an OntologyStats object.

    Args:
        stats: The statistics object.

    Returns:
        Dictionary mapping (category, metric) -> value.
    """
    metrics: dict[tuple[str, str], float | int] = {}

    # Basic
    metrics[("basic", "triples")] = stats.basic.triples
    metrics[("basic", "classes")] = stats.basic.classes
    metrics[("basic", "object_properties")] = stats.basic.object_properties
    metrics[("basic", "datatype_properties")] = stats.basic.datatype_properties
    metrics[("basic", "annotation_properties")] = stats.basic.annotation_properties
    metrics[("basic", "individuals")] = stats.basic.individuals

    # Hierarchy
    metrics[("hierarchy", "root_classes")] = stats.hierarchy.root_classes
    metrics[("hierarchy", "leaf_classes")] = stats.hierarchy.leaf_classes
    metrics[("hierarchy", "max_depth")] = stats.hierarchy.max_depth
    metrics[("hierarchy", "avg_depth")] = stats.hierarchy.avg_depth
    metrics[("hierarchy", "avg_branching")] = stats.hierarchy.avg_branching
    metrics[("hierarchy", "orphan_classes")] = stats.hierarchy.orphan_classes
    metrics[("hierarchy", "orphan_rate")] = stats.hierarchy.orphan_rate

    # Properties
    metrics[("properties", "with_domain")] = stats.properties.with_domain
    metrics[("properties", "with_range")] = stats.properties.with_range
    metrics[("properties", "domain_coverage")] = stats.properties.domain_coverage
    metrics[("properties", "range_coverage")] = stats.properties.range_coverage
    metrics[("properties", "inverse_pairs")] = stats.properties.inverse_pairs
    metrics[("properties", "functional")] = stats.properties.functional
    metrics[("properties", "symmetric")] = stats.properties.symmetric

    # Documentation
    metrics[("documentation", "classes_labelled")] = stats.documentation.classes_labelled
    metrics[("documentation", "classes_labelled_pct")] = stats.documentation.classes_labelled_pct
    metrics[("documentation", "classes_documented")] = stats.documentation.classes_documented
    metrics[("documentation", "classes_documented_pct")] = stats.documentation.classes_documented_pct
    metrics[("documentation", "properties_labelled")] = stats.documentation.properties_labelled
    metrics[("documentation", "properties_labelled_pct")] = stats.documentation.properties_labelled_pct

    # Complexity
    metrics[("complexity", "avg_properties_per_class")] = stats.complexity.avg_properties_per_class
    metrics[("complexity", "avg_superclasses_per_class")] = stats.complexity.avg_superclasses_per_class
    metrics[("complexity", "multiple_inheritance_count")] = stats.complexity.multiple_inheritance_count
    metrics[("complexity", "owl_restriction_count")] = stats.complexity.owl_restriction_count
    metrics[("complexity", "owl_equivalent_count")] = stats.complexity.owl_equivalent_count

    # Connectivity
    metrics[("connectivity", "most_connected_count")] = stats.connectivity.most_connected_count
    metrics[("connectivity", "isolated_classes")] = stats.connectivity.isolated_classes

    return metrics


def _generate_summary(changes: list[MetricChange]) -> str:
    """Generate a human-readable summary of changes.

    Args:
        changes: List of metric changes.

    Returns:
        Summary string.
    """
    if not changes:
        return "No significant changes detected."

    # Count improvements and degradations
    improvements = sum(1 for c in changes if c.improved is True)
    degradations = sum(1 for c in changes if c.improved is False)

    # Find notable changes
    class_change = next((c for c in changes if c.metric == "classes"), None)
    doc_change = next((c for c in changes if c.metric == "classes_documented_pct"), None)
    orphan_change = next((c for c in changes if c.metric == "orphan_classes"), None)

    parts = []

    # Ontology growth/shrinkage
    if class_change and class_change.delta:
        if class_change.delta > 0:
            parts.append(f"Ontology grew (+{class_change.delta} classes)")
        else:
            parts.append(f"Ontology shrank ({class_change.delta} classes)")

    # Documentation improvements
    if doc_change and doc_change.delta and doc_change.delta > 0:
        parts.append("improved documentation coverage")

    # Orphan changes
    if orphan_change and orphan_change.delta:
        if orphan_change.delta < 0:
            parts.append("fewer orphan classes")
        elif orphan_change.delta > 0:
            parts.append("more orphan classes (review needed)")

    if not parts:
        if improvements > degradations:
            return "Overall improvement in ontology quality."
        elif degradations > improvements:
            return "Some quality metrics have degraded."
        else:
            return "Minor changes with mixed impact."

    return ", ".join(parts).capitalize() + "."


def compare_stats(
    old_stats: OntologyStats,
    new_stats: OntologyStats,
) -> ComparisonResult:
    """Compare statistics between two ontology versions.

    Args:
        old_stats: Statistics from the baseline/old version.
        new_stats: Statistics from the new version.

    Returns:
        ComparisonResult with all metric changes.
    """
    old_metrics = _extract_numeric_metrics(old_stats)
    new_metrics = _extract_numeric_metrics(new_stats)

    changes: list[MetricChange] = []

    for key, old_val in old_metrics.items():
        category, metric = key
        new_val = new_metrics.get(key, 0)

        # Skip if no change
        if old_val == new_val:
            continue

        delta = new_val - old_val
        pct = _pct_change(old_val, new_val)
        improved = _is_improvement(category, metric, delta)

        changes.append(
            MetricChange(
                category=category,
                metric=metric,
                old_value=old_val,
                new_value=new_val,
                delta=delta,
                pct_change=pct,
                improved=improved,
            )
        )

    # Sort by category then metric
    changes.sort(key=lambda c: (c.category, c.metric))

    summary = _generate_summary(changes)

    return ComparisonResult(
        old_source=old_stats.source,
        new_source=new_stats.source,
        changes=changes,
        summary=summary,
    )
