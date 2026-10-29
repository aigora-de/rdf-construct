"""PlantUML to RDF import module.

This module provides tools for converting PlantUML class diagrams
to RDF/OWL ontologies, enabling diagram-first ontology design.

Example:
    from rdf_construct.puml_import import PlantUMLParser, PumlToRdfConverter

    # Parse a PlantUML file
    parser = PlantUMLParser()
    result = parser.parse_file(Path("design.puml"))

    if result.success:
        # Convert to RDF
        converter = PumlToRdfConverter()
        rdf_result = converter.convert(result.model)

        # Save the ontology
        rdf_result.graph.serialize("ontology.ttl", format="turtle")
"""

from rdf_construct.puml2rdf.model import (
    PropertyKind,
    PumlAttribute,
    PumlClass,
    PumlModel,
    PumlNote,
    PumlPackage,
    PumlRelationship,
    RelationshipType,
)
from rdf_construct.puml2rdf.parser import (
    ParseError,
    ParseResult,
    PlantUMLParser,
)
from rdf_construct.puml2rdf.converter import (
    ConversionConfig,
    ConversionResult,
    PumlToRdfConverter,
    XSD_TYPE_MAP,
)
from rdf_construct.puml2rdf.config import (
    DatatypeMapping,
    NamespaceMapping,
    PumlImportConfig,
    create_default_config,
    load_import_config,
)
from rdf_construct.puml2rdf.merger import (
    MergeResult,
    OntologyMerger,
    merge_with_existing,
)
from rdf_construct.puml2rdf.validators import (
    PumlModelValidator,
    RdfValidator,
    Severity,
    ValidationIssue,
    ValidationResult,
    validate_puml,
    validate_rdf,
)


__all__ = [
    # Model classes
    "PropertyKind",
    "PumlAttribute",
    "PumlClass",
    "PumlModel",
    "PumlNote",
    "PumlPackage",
    "PumlRelationship",
    "RelationshipType",
    # Parser
    "ParseError",
    "ParseResult",
    "PlantUMLParser",
    # Converter
    "ConversionConfig",
    "ConversionResult",
    "PumlToRdfConverter",
    "XSD_TYPE_MAP",
    # Config
    "DatatypeMapping",
    "NamespaceMapping",
    "PumlImportConfig",
    "create_default_config",
    "load_import_config",
    # Merger
    "MergeResult",
    "OntologyMerger",
    "merge_with_existing",
    # Validators
    "PumlModelValidator",
    "RdfValidator",
    "Severity",
    "ValidationIssue",
    "ValidationResult",
    "validate_puml",
    "validate_rdf",
]
