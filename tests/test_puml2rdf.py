"""Tests for PlantUML import module.

Tests cover parsing, conversion, validation, and merging functionality.
"""

import pytest
from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS, Literal
from rdflib.namespace import OWL, XSD

from rdf_construct.puml2rdf import (
    PlantUMLParser,
    PumlToRdfConverter,
    ConversionConfig,
    PumlModel,
    PumlClass,
    PumlAttribute,
    PumlRelationship,
    RelationshipType,
    validate_puml,
    validate_rdf,
    OntologyMerger,
)


# ==============================================================================
# Parser Tests
# ==============================================================================


class TestPlantUMLParser:
    """Tests for PlantUML parsing."""

    def test_parse_simple_class(self):
        """Test parsing a simple class declaration."""
        content = """
        @startuml
        class Building
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        assert len(result.model.classes) == 1
        assert result.model.classes[0].name == "Building"

    def test_parse_class_with_attributes(self):
        """Test parsing a class with attributes."""
        content = """
        @startuml
        class Building {
            floorArea : decimal
            constructionYear : gYear
            name : string
        }
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        assert len(result.model.classes) == 1
        cls = result.model.classes[0]
        assert cls.name == "Building"
        assert len(cls.attributes) == 3

        attr_names = {a.name for a in cls.attributes}
        assert attr_names == {"floorArea", "constructionYear", "name"}

        floor_area = next(a for a in cls.attributes if a.name == "floorArea")
        assert floor_area.datatype == "decimal"

    def test_parse_abstract_class(self):
        """Test parsing abstract class declaration."""
        content = """
        @startuml
        abstract class Entity
        class Building
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        entity = result.model.get_class("Entity")
        assert entity is not None
        assert entity.is_abstract is True

        building = result.model.get_class("Building")
        assert building is not None
        assert building.is_abstract is False

    def test_parse_inheritance(self):
        """Test parsing inheritance relationships."""
        content = """
        @startuml
        class Entity
        class Building
        Building --|> Entity
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        assert len(result.model.relationships) == 1

        rel = result.model.relationships[0]
        assert rel.rel_type == RelationshipType.INHERITANCE
        assert rel.source == "Building"  # Child
        assert rel.target == "Entity"  # Parent

    def test_parse_inheritance_reverse_arrow(self):
        """Test parsing inheritance with reversed arrow."""
        content = """
        @startuml
        class Entity
        class Building
        Entity <|-- Building
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        rel = result.model.relationships[0]
        assert rel.source == "Building"  # Child
        assert rel.target == "Entity"  # Parent

    def test_parse_association_with_label(self):
        """Test parsing labeled association."""
        content = """
        @startuml
        class Building
        class Floor
        Building --> Floor : hasFloor
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        # Find non-inheritance relationships
        assocs = result.model.property_relationships()
        assert len(assocs) >= 1

        rel = assocs[0]
        assert rel.source == "Building"
        assert rel.target == "Floor"
        assert rel.label == "hasFloor"

    def test_parse_package(self):
        """Test parsing package declaration."""
        content = """
        @startuml
        package "http://example.org/building#" as bld {
            class Building
        }
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        assert len(result.model.packages) == 1

        pkg = result.model.packages[0]
        assert pkg.name == "http://example.org/building#"

    def test_parse_class_in_package(self):
        """Test that classes track their containing package."""
        content = """
        @startuml
        package building {
            class Building
            class Floor
        }
        class ExternalClass
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success

        building = result.model.get_class("Building")
        assert building is not None
        assert building.package == "building"

        external = result.model.get_class("ExternalClass")
        assert external is not None
        assert external.package is None

    def test_parse_note_attached_to_class(self):
        """Test parsing notes attached to classes."""
        content = """
        @startuml
        class Building
        note right of Building : A physical structure
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        building = result.model.get_class("Building")
        assert building.note == "A physical structure"

    def test_parse_multiline_note(self):
        """Test parsing multi-line notes."""
        content = """
        @startuml
        class Building
        note right of Building
            A physical structure
            that can be occupied
        end note
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        building = result.model.get_class("Building")
        assert building.note is not None
        assert "physical structure" in building.note

    def test_parse_title(self):
        """Test parsing diagram title."""
        content = """
        @startuml
        title Building Ontology
        class Building
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        assert result.model.title == "Building Ontology"


# ==============================================================================
# Converter Tests
# ==============================================================================


class TestPumlToRdfConverter:
    """Tests for PlantUML to RDF conversion."""

    def test_convert_simple_class(self):
        """Test converting a simple class."""
        model = PumlModel(
            classes=[PumlClass(name="Building")]
        )

        config = ConversionConfig(
            default_namespace="http://example.org/ont#"
        )
        converter = PumlToRdfConverter(config)
        result = converter.convert(model)

        graph = result.graph
        ns = Namespace("http://example.org/ont#")

        # Check class exists and is typed
        assert (ns.Building, RDF.type, OWL.Class) in graph

    def test_convert_class_with_label(self):
        """Test that classes get labels."""
        model = PumlModel(
            classes=[PumlClass(name="FloorArea")]
        )

        config = ConversionConfig(
            default_namespace="http://example.org/ont#",
            generate_labels=True,
            camel_to_label=True,
        )
        converter = PumlToRdfConverter(config)
        result = converter.convert(model)

        ns = Namespace("http://example.org/ont#")
        labels = list(result.graph.objects(ns.FloorArea, RDFS.label))

        assert len(labels) == 1
        assert str(labels[0]) == "floor area"

    def test_convert_class_with_comment(self):
        """Test that notes become comments."""
        model = PumlModel(
            classes=[
                PumlClass(
                    name="Building",
                    note="A physical structure"
                )
            ]
        )

        converter = PumlToRdfConverter()
        result = converter.convert(model)

        ns = Namespace("http://example.org/ontology#")
        comments = list(result.graph.objects(ns.Building, RDFS.comment))

        assert len(comments) == 1
        assert "physical structure" in str(comments[0])

    def test_convert_attribute_to_datatype_property(self):
        """Test that attributes become datatype properties."""
        model = PumlModel(
            classes=[
                PumlClass(
                    name="Building",
                    attributes=[
                        PumlAttribute(name="floorArea", datatype="decimal")
                    ]
                )
            ]
        )

        config = ConversionConfig(
            default_namespace="http://example.org/ont#"
        )
        converter = PumlToRdfConverter(config)
        result = converter.convert(model)

        ns = Namespace("http://example.org/ont#")
        graph = result.graph

        # Check property type
        assert (ns.floorArea, RDF.type, OWL.DatatypeProperty) in graph

        # Check domain
        domains = list(graph.objects(ns.floorArea, RDFS.domain))
        assert ns.Building in domains

        # Check range
        ranges = list(graph.objects(ns.floorArea, RDFS.range))
        assert XSD.decimal in ranges

    def test_convert_inheritance(self):
        """Test that inheritance becomes subClassOf."""
        model = PumlModel(
            classes=[
                PumlClass(name="Entity"),
                PumlClass(name="Building"),
            ],
            relationships=[
                PumlRelationship(
                    source="Building",
                    target="Entity",
                    rel_type=RelationshipType.INHERITANCE,
                )
            ]
        )

        config = ConversionConfig(
            default_namespace="http://example.org/ont#"
        )
        converter = PumlToRdfConverter(config)
        result = converter.convert(model)

        ns = Namespace("http://example.org/ont#")
        assert (ns.Building, RDFS.subClassOf, ns.Entity) in result.graph

    def test_convert_association_to_object_property(self):
        """Test that associations become object properties."""
        model = PumlModel(
            classes=[
                PumlClass(name="Building"),
                PumlClass(name="Floor"),
            ],
            relationships=[
                PumlRelationship(
                    source="Building",
                    target="Floor",
                    rel_type=RelationshipType.ASSOCIATION,
                    label="has floor",
                )
            ]
        )

        config = ConversionConfig(
            default_namespace="http://example.org/ont#"
        )
        converter = PumlToRdfConverter(config)
        result = converter.convert(model)

        ns = Namespace("http://example.org/ont#")
        graph = result.graph

        # Check property exists
        assert (ns.hasFloor, RDF.type, OWL.ObjectProperty) in graph

        # Check domain and range
        assert (ns.hasFloor, RDFS.domain, ns.Building) in graph
        assert (ns.hasFloor, RDFS.range, ns.Floor) in graph

    def test_convert_generates_ontology_header(self):
        """Test that conversion creates ontology declaration."""
        model = PumlModel(
            title="Building Ontology",
            classes=[PumlClass(name="Building")]
        )

        config = ConversionConfig(
            default_namespace="http://example.org/building#"
        )
        converter = PumlToRdfConverter(config)
        result = converter.convert(model)

        ont_uri = Namespace("http://example.org/building")[""]
        # Check for ontology type (URI without trailing #)
        ont_types = list(result.graph.subjects(RDF.type, OWL.Ontology))
        assert len(ont_types) >= 1


# ==============================================================================
# Validator Tests
# ==============================================================================


class TestPumlValidation:
    """Tests for PlantUML model validation."""

    def test_validate_duplicate_classes(self):
        """Test detection of duplicate class names."""
        model = PumlModel(
            classes=[
                PumlClass(name="Building"),
                PumlClass(name="Building"),
            ]
        )

        result = validate_puml(model)
        assert result.has_errors
        assert any("DUPLICATE_CLASS" in str(i) for i in result.issues)

    def test_validate_unknown_relationship_class(self):
        """Test detection of relationships to unknown classes."""
        model = PumlModel(
            classes=[PumlClass(name="Building")],
            relationships=[
                PumlRelationship(
                    source="Building",
                    target="NonExistent",
                    rel_type=RelationshipType.ASSOCIATION,
                )
            ]
        )

        result = validate_puml(model)
        assert result.has_errors
        assert any("UNKNOWN_CLASS" in str(i) for i in result.issues)

    def test_validate_unknown_datatype(self):
        """Test warning for unknown datatypes."""
        model = PumlModel(
            classes=[
                PumlClass(
                    name="Building",
                    attributes=[
                        PumlAttribute(name="custom", datatype="UnknownType")
                    ]
                )
            ]
        )

        result = validate_puml(model)
        assert result.has_warnings
        assert any("UNKNOWN_DATATYPE" in str(i) for i in result.issues)

    def test_validate_inheritance_cycle(self):
        """Test detection of inheritance cycles."""
        model = PumlModel(
            classes=[
                PumlClass(name="A"),
                PumlClass(name="B"),
                PumlClass(name="C"),
            ],
            relationships=[
                PumlRelationship(source="A", target="B", rel_type=RelationshipType.INHERITANCE),
                PumlRelationship(source="B", target="C", rel_type=RelationshipType.INHERITANCE),
                PumlRelationship(source="C", target="A", rel_type=RelationshipType.INHERITANCE),
            ]
        )

        result = validate_puml(model)
        assert result.has_errors
        assert any("INHERITANCE_CYCLE" in str(i) for i in result.issues)


class TestRdfValidation:
    """Tests for RDF graph validation."""

    def test_validate_untyped_class(self):
        """Test warning for classes used without type declaration."""
        graph = Graph()
        ns = Namespace("http://example.org/ont#")

        # Add subClassOf without class type
        graph.add((ns.Building, RDFS.subClassOf, ns.Entity))

        result = validate_rdf(graph)
        assert any("UNTYPED_CLASS" in str(i) for i in result.issues)

    def test_validate_missing_domain(self):
        """Test info for properties without domain."""
        graph = Graph()
        ns = Namespace("http://example.org/ont#")

        graph.add((ns.hasFloor, RDF.type, OWL.ObjectProperty))
        # No domain added

        result = validate_rdf(graph)
        assert any("MISSING_DOMAIN" in str(i) for i in result.issues)


# ==============================================================================
# Merger Tests
# ==============================================================================


class TestOntologyMerger:
    """Tests for ontology merging."""

    def test_merge_adds_new_triples(self):
        """Test that new triples are added."""
        existing = Graph()
        ns = Namespace("http://example.org/ont#")
        existing.add((ns.Building, RDF.type, OWL.Class))

        new_graph = Graph()
        new_graph.add((ns.Floor, RDF.type, OWL.Class))

        merger = OntologyMerger()
        result = merger.merge_graphs(new_graph, existing)

        assert (ns.Building, RDF.type, OWL.Class) in result.graph
        assert (ns.Floor, RDF.type, OWL.Class) in result.graph

    def test_merge_preserves_existing_annotations(self):
        """Test that existing annotations are preserved."""
        existing = Graph()
        ns = Namespace("http://example.org/ont#")
        existing.add((ns.Building, RDF.type, OWL.Class))
        existing.add((ns.Building, RDFS.comment, Literal("Manually added comment")))

        new_graph = Graph()
        new_graph.add((ns.Building, RDF.type, OWL.Class))
        # No comment in new

        merger = OntologyMerger()
        result = merger.merge_graphs(new_graph, existing)

        comments = list(result.graph.objects(ns.Building, RDFS.comment))
        assert any("Manually added" in str(c) for c in comments)


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestRoundTrip:
    """Integration tests for full parse-convert workflow."""

    def test_full_conversion(self):
        """Test complete parse and convert workflow."""
        puml = """
        @startuml
        title Building Ontology

        class Building {
            floorArea : decimal
            constructionYear : gYear
        }

        class Floor {
            level : integer
        }

        Building --|> Entity
        Building --> Floor : hasFloor

        note right of Building
            A physical structure
            that can be occupied.
        end note

        @enduml
        """

        # Parse
        parser = PlantUMLParser()
        parse_result = parser.parse(puml)
        assert parse_result.success

        # Add Entity class (referenced but not defined)
        parse_result.model.classes.append(PumlClass(name="Entity"))

        # Convert
        config = ConversionConfig(
            default_namespace="http://example.org/building#",
            generate_labels=True,
        )
        converter = PumlToRdfConverter(config)
        result = converter.convert(parse_result.model)

        # Verify
        graph = result.graph
        ns = Namespace("http://example.org/building#")

        # Classes exist
        assert (ns.Building, RDF.type, OWL.Class) in graph
        assert (ns.Floor, RDF.type, OWL.Class) in graph

        # Inheritance
        assert (ns.Building, RDFS.subClassOf, ns.Entity) in graph

        # Properties
        assert (ns.floorArea, RDF.type, OWL.DatatypeProperty) in graph
        assert (ns.hasFloor, RDF.type, OWL.ObjectProperty) in graph

        # Comment from note
        comments = list(graph.objects(ns.Building, RDFS.comment))
        assert len(comments) >= 1
