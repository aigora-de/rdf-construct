"""Documentation generation module for rdf-construct.

This module provides functionality for generating comprehensive, navigable
documentation from RDF ontologies in HTML, Markdown, or JSON formats.

Example usage:
    from rdf_construct.docs import generate_docs

    result = generate_docs(
        source=Path("ontology.ttl"),
        output_dir=Path("docs/"),
        output_format="html",
    )
    print(f"Generated {result.total_pages} pages")

For more control, use the DocsGenerator class directly:
    from rdf_construct.docs import DocsGenerator, DocsConfig

    config = DocsConfig(
        output_dir=Path("docs/"),
        format="html",
        include_instances=True,
        include_search=True,
    )
    generator = DocsGenerator(config)
    result = generator.generate_from_file(Path("ontology.ttl"))
"""

from rdf_construct.docs.config import DocsConfig, load_docs_config
from rdf_construct.docs.extractors import (
    ClassInfo,
    ExtractedEntities,
    InstanceInfo,
    OntologyInfo,
    PropertyInfo,
    extract_all,
)
from rdf_construct.docs.generator import DocsGenerator, GenerationResult, generate_docs
from rdf_construct.docs.search import SearchEntry, generate_search_index

__all__ = [
    # Main interface
    "generate_docs",
    "DocsGenerator",
    "GenerationResult",
    # Configuration
    "DocsConfig",
    "load_docs_config",
    # Data classes
    "ClassInfo",
    "PropertyInfo",
    "InstanceInfo",
    "OntologyInfo",
    "ExtractedEntities",
    # Extraction
    "extract_all",
    # Search
    "SearchEntry",
    "generate_search_index",
]
