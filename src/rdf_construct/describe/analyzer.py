"""Main analyzer for ontology description.

Orchestrates all analysis components and aggregates results into
a complete OntologyDescription.
"""

from datetime import datetime
from pathlib import Path

from rdflib import Graph

from rdf_construct.describe.models import OntologyDescription
from rdf_construct.describe.metadata import extract_metadata
from rdf_construct.describe.metrics import collect_metrics
from rdf_construct.describe.profiles import detect_profile
from rdf_construct.describe.namespaces import analyse_namespaces
from rdf_construct.describe.imports import analyse_imports
from rdf_construct.describe.hierarchy import analyse_hierarchy
from rdf_construct.describe.documentation import analyse_documentation


def describe_ontology(
    graph: Graph,
    source: str | Path,
    brief: bool = False,
    resolve_imports: bool = True,
    include_reasoning: bool = False,
) -> OntologyDescription:
    """Generate a complete description of an ontology.

    Runs all analysis components and aggregates results.

    Args:
        graph: Parsed RDF graph to analyse.
        source: Source file path or identifier.
        brief: If True, skip detailed analysis (imports, hierarchy, etc.).
        resolve_imports: Whether to check resolvability of imports.
        include_reasoning: Whether to include reasoning analysis.

    Returns:
        OntologyDescription with all analysis results.
    """
    # Always perform core analysis
    metadata = extract_metadata(graph)
    metrics = collect_metrics(graph)
    profile = detect_profile(graph)

    # Create base description
    description = OntologyDescription(
        source=source,
        timestamp=datetime.now(),
        metadata=metadata,
        metrics=metrics,
        profile=profile,
        brief=brief,
        include_reasoning=include_reasoning,
    )

    # Skip detailed analysis if brief mode
    if brief:
        return description

    # Full analysis
    description.namespaces = analyse_namespaces(graph)
    description.imports = analyse_imports(graph, resolve=resolve_imports)
    description.hierarchy = analyse_hierarchy(graph)
    description.documentation = analyse_documentation(graph)

    # Reasoning analysis is optional and off by default
    if include_reasoning:
        description.reasoning = _analyse_reasoning(graph, profile)

    return description


def describe_file(
    file_path: Path,
    brief: bool = False,
    resolve_imports: bool = True,
    include_reasoning: bool = False,
) -> OntologyDescription:
    """Generate a complete description of an ontology file.

    Convenience function that handles file loading and format detection.

    Args:
        file_path: Path to RDF file.
        brief: If True, skip detailed analysis.
        resolve_imports: Whether to check resolvability of imports.
        include_reasoning: Whether to include reasoning analysis.

    Returns:
        OntologyDescription with all analysis results.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file cannot be parsed.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Detect format from extension
    rdf_format = _infer_format(file_path)

    # Parse the file
    graph = Graph()
    try:
        graph.parse(str(file_path), format=rdf_format)
    except Exception as e:
        raise ValueError(f"Failed to parse {file_path}: {e}") from e

    return describe_ontology(
        graph=graph,
        source=file_path,
        brief=brief,
        resolve_imports=resolve_imports,
        include_reasoning=include_reasoning,
    )


def _infer_format(path: Path) -> str:
    """Infer RDF format from file extension.

    Args:
        path: Path to RDF file.

    Returns:
        Format string for rdflib.
    """
    suffix = path.suffix.lower()
    format_map = {
        ".ttl": "turtle",
        ".turtle": "turtle",
        ".rdf": "xml",
        ".xml": "xml",
        ".owl": "xml",
        ".nt": "nt",
        ".ntriples": "nt",
        ".n3": "n3",
        ".jsonld": "json-ld",
        ".json": "json-ld",
    }
    return format_map.get(suffix, "turtle")


def _analyse_reasoning(graph: Graph, profile) -> "ReasoningAnalysis":
    """Perform reasoning analysis (optional feature).

    This is a placeholder for future reasoning analysis functionality.

    Args:
        graph: RDF graph to analyse.
        profile: Detected profile.

    Returns:
        ReasoningAnalysis with reasoning implications.
    """
    from rdf_construct.describe.models import ReasoningAnalysis, OntologyProfile

    # Determine entailment regime based on profile
    regime_map = {
        OntologyProfile.RDF: "none",
        OntologyProfile.RDFS: "rdfs",
        OntologyProfile.OWL_DL_SIMPLE: "owl-dl",
        OntologyProfile.OWL_DL_EXPRESSIVE: "owl-dl",
        OntologyProfile.OWL_FULL: "owl-full",
    }

    regime = regime_map.get(profile.profile, "unknown")

    return ReasoningAnalysis(
        entailment_regime=regime,
        inferred_superclasses=[],
        inferred_types=[],
        consistency_notes=[],
    )
