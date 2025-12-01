"""SHACL shape generation from OWL ontologies.

This module provides tools for generating SHACL validation shapes from
OWL ontology definitions, converting domain/range, cardinality restrictions,
and other OWL patterns to equivalent SHACL constraints.

Basic usage:

    from rdf_construct.shacl import generate_shapes, ShaclConfig, StrictnessLevel

    # Generate shapes with default settings
    graph, turtle = generate_shapes(Path("ontology.ttl"))

    # Generate with strict level
    config = ShaclConfig(level=StrictnessLevel.STRICT, closed=True)
    graph, turtle = generate_shapes(Path("ontology.ttl"), config)

    # Generate and write to file
    from rdf_construct.shacl import generate_shapes_to_file
    generate_shapes_to_file(
        Path("ontology.ttl"),
        Path("shapes.ttl"),
        config,
    )
"""

from rdf_construct.shacl.config import (
    ShaclConfig,
    Severity,
    StrictnessLevel,
    load_shacl_config,
)
from rdf_construct.shacl.converters import PropertyConstraint
from rdf_construct.shacl.generator import (
    ShapeGenerator,
    generate_shapes,
    generate_shapes_to_file,
)
from rdf_construct.shacl.namespaces import SH, SHACL_PREFIXES

__all__ = [
    # Configuration
    "ShaclConfig",
    "StrictnessLevel",
    "Severity",
    "load_shacl_config",
    # Generator
    "ShapeGenerator",
    "generate_shapes",
    "generate_shapes_to_file",
    # Converters
    "PropertyConstraint",
    # Namespaces
    "SH",
    "SHACL_PREFIXES",
]
