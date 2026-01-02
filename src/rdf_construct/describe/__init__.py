"""Describe command for RDF ontology analysis.

Provides quick orientation and understanding of ontology files,
answering: "What is this?", "How big is it?", "What does it depend on?",
and "Can I work with it?"

Usage:
    from rdf_construct.describe import describe_file, format_description

    description = describe_file(Path("ontology.ttl"))
    print(format_description(description))

    # Brief mode (metadata + metrics + profile only)
    description = describe_file(Path("ontology.ttl"), brief=True)

    # Skip import resolution (faster)
    description = describe_file(Path("ontology.ttl"), resolve_imports=False)

    # JSON output
    print(format_description(description, format_name="json"))
"""

from rdf_construct.describe.models import (
    OntologyDescription,
    OntologyMetadata,
    BasicMetrics,
    ProfileDetection,
    OntologyProfile,
    NamespaceAnalysis,
    NamespaceInfo,
    NamespaceCategory,
    ImportAnalysis,
    ImportInfo,
    ImportStatus,
    HierarchyAnalysis,
    DocumentationCoverage,
    ReasoningAnalysis,
)

from rdf_construct.describe.analyzer import (
    describe_ontology,
    describe_file,
)

from rdf_construct.describe.formatters import (
    format_description,
    format_text,
    format_markdown,
    format_json,
)

from rdf_construct.describe.profiles import detect_profile
from rdf_construct.describe.metrics import collect_metrics
from rdf_construct.describe.imports import analyse_imports
from rdf_construct.describe.namespaces import analyse_namespaces
from rdf_construct.describe.hierarchy import analyse_hierarchy
from rdf_construct.describe.documentation import analyse_documentation
from rdf_construct.describe.metadata import extract_metadata


__all__ = [
    # Main functions
    "describe_file",
    "describe_ontology",
    "format_description",
    # Formatters
    "format_text",
    "format_markdown",
    "format_json",
    # Analysis functions (for direct use)
    "detect_profile",
    "collect_metrics",
    "analyse_imports",
    "analyse_namespaces",
    "analyse_hierarchy",
    "analyse_documentation",
    "extract_metadata",
    # Data models
    "OntologyDescription",
    "OntologyMetadata",
    "BasicMetrics",
    "ProfileDetection",
    "OntologyProfile",
    "NamespaceAnalysis",
    "NamespaceInfo",
    "NamespaceCategory",
    "ImportAnalysis",
    "ImportInfo",
    "ImportStatus",
    "HierarchyAnalysis",
    "DocumentationCoverage",
    "ReasoningAnalysis",
]
