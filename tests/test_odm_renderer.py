#!/usr/bin/env python3
"""Test suite for ODM RDF Profile renderer.

Tests the ODM-compliant rendering mode for PlantUML diagrams.
"""

import pytest
from io import StringIO
from rdflib import Graph, URIRef, Namespace, RDF, RDFS, Literal
from rdflib.namespace import OWL

# Import the ODM renderer
from rdf_construct.uml.odm_renderer import (
    ODMRenderer,
    render_odm_plantuml,
    qname,
    local_name,
    plantuml_identifier,
    ODM_CLASS_STEREOTYPES,
    ODM_PROPERTY_STEREOTYPES,
    ODM_INDIVIDUAL_STEREOTYPE,
)

# Test namespaces
EX = Namespace("http://example.org/")
IES = Namespace("http://example.org/ies#")


@pytest.fixture
def simple_graph():
    """Create a simple test graph with classes and properties."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("ies", IES)

    # Add classes
    g.add((EX.Animal, RDF.type, OWL.Class))
    g.add((EX.Animal, RDFS.label, Literal("Animal")))

    g.add((EX.Dog, RDF.type, OWL.Class))
    g.add((EX.Dog, RDFS.subClassOf, EX.Animal))

    # Add object property
    g.add((EX.hasParent, RDF.type, OWL.ObjectProperty))
    g.add((EX.hasParent, RDFS.domain, EX.Animal))
    g.add((EX.hasParent, RDFS.range, EX.Animal))

    # Add datatype property
    g.add((EX.age, RDF.type, OWL.DatatypeProperty))
    g.add((EX.age, RDFS.domain, EX.Animal))

    # Add individual
    g.add((EX.Fido, RDF.type, EX.Dog))
    g.add((EX.Fido, RDFS.label, Literal("Fido")))

    return g


@pytest.fixture
def entities(simple_graph):
    """Create entity dictionary for rendering."""
    return {
        "classes": {EX.Animal, EX.Dog},
        "object_properties": {EX.hasParent},
        "datatype_properties": {EX.age},
        "annotation_properties": set(),
        "instances": {EX.Fido},
    }


class TestODMStereotypes:
    """Test ODM stereotype mappings."""

    def test_class_stereotypes_defined(self):
        """Verify ODM class stereotypes are defined."""
        assert str(OWL.Class) in ODM_CLASS_STEREOTYPES
        assert str(RDFS.Class) in ODM_CLASS_STEREOTYPES
        assert ODM_CLASS_STEREOTYPES[str(OWL.Class)] == "owlClass"
        assert ODM_CLASS_STEREOTYPES[str(RDFS.Class)] == "rdfsClass"

    def test_property_stereotypes_defined(self):
        """Verify ODM property stereotypes are defined."""
        assert str(OWL.ObjectProperty) in ODM_PROPERTY_STEREOTYPES
        assert str(OWL.DatatypeProperty) in ODM_PROPERTY_STEREOTYPES
        assert ODM_PROPERTY_STEREOTYPES[str(OWL.ObjectProperty)] == "objectProperty"
        assert ODM_PROPERTY_STEREOTYPES[str(OWL.DatatypeProperty)] == "datatypeProperty"

    def test_individual_stereotype_defined(self):
        """Verify ODM individual stereotype is defined."""
        assert ODM_INDIVIDUAL_STEREOTYPE == "individual"


class TestODMRenderer:
    """Test ODM renderer functionality."""

    def test_render_class_stereotype(self, simple_graph, entities):
        """Test that classes get correct ODM stereotypes."""
        renderer = ODMRenderer(simple_graph, entities)

        lines = renderer.render_class(EX.Animal)
        output = "\n".join(lines)

        assert "<<owlClass>>" in output
        assert "ex.Animal" in output or "Animal" in output

    def test_render_property_stereotype(self, simple_graph, entities):
        """Test that properties get correct ODM stereotypes."""
        renderer = ODMRenderer(simple_graph, entities)

        lines = renderer.render_property_as_class(EX.hasParent)
        output = "\n".join(lines)

        assert "<<objectProperty>>" in output

    def test_render_individual_stereotype(self, simple_graph, entities):
        """Test that individuals get correct ODM stereotypes."""
        renderer = ODMRenderer(simple_graph, entities)

        lines = renderer.render_individual(EX.Fido)
        output = "\n".join(lines)

        # Should have individual stereotype with type info
        assert "<<individual" in output
        assert "ex:Dog" in output or "Dog" in output

    def test_render_subclass_no_label(self, simple_graph, entities):
        """Test that subclass relationships don't have labels in ODM mode."""
        renderer = ODMRenderer(simple_graph, entities)

        lines = renderer.render_subclass_relationships()
        output = "\n".join(lines)

        # ODM mode: subclass relationships are plain generalisations
        assert "-|>" in output
        # Should NOT have <<rdfs:subClassOf>> label (that's default mode)
        assert "<<rdfs:subClassOf>>" not in output

    def test_render_domain_range_stereotypes(self, simple_graph, entities):
        """Test that domain/range use ODM stereotypes."""
        renderer = ODMRenderer(simple_graph, entities)

        lines = renderer.render_domain_range_relationships()
        output = "\n".join(lines)

        # Should use ODM stereotype names
        assert "<<rdfsDomain>>" in output
        assert "<<rdfsRange>>" in output

    def test_render_type_stereotype(self, simple_graph, entities):
        """Test that rdf:type uses ODM stereotype."""
        renderer = ODMRenderer(simple_graph, entities)

        lines = renderer.render_type_relationships()
        output = "\n".join(lines)

        # Should use ODM stereotype name
        assert "<<rdfType>>" in output

    def test_full_render_has_odm_comment(self, simple_graph, entities):
        """Test that full render includes ODM identification comment."""
        renderer = ODMRenderer(simple_graph, entities)

        output = renderer.render()

        assert "ODM RDF Profile" in output
        assert "@startuml" in output
        assert "@enduml" in output


class TestUtilityFunctions:
    """Test utility functions."""

    def test_qname(self, simple_graph):
        """Test QName generation."""
        result = qname(simple_graph, EX.Animal)
        assert "Animal" in result

    def test_local_name(self, simple_graph):
        """Test local name extraction."""
        result = local_name(simple_graph, EX.Animal)
        assert result == "Animal"

    def test_plantuml_identifier(self, simple_graph):
        """Test PlantUML identifier generation."""
        result = plantuml_identifier(simple_graph, EX.Animal)
        # Should use dot notation, not colon
        assert ":" not in result or "." in result


class TestRenderODMPlantuml:
    """Test the main render function."""

    def test_render_to_string(self, simple_graph, entities):
        """Test rendering to string without file output."""
        output = render_odm_plantuml(simple_graph, entities)

        assert isinstance(output, str)
        assert "@startuml" in output
        assert "@enduml" in output
        assert "<<owlClass>>" in output

    def test_render_with_style(self, simple_graph, entities):
        """Test that style parameter is accepted."""
        # Should not raise even without a real style object
        output = render_odm_plantuml(simple_graph, entities, style=None)
        assert "@startuml" in output


class TestIESColourPaletteIntegration:
    """Test integration with IES colour palette styling."""

    def test_style_get_class_style_called(self, simple_graph, entities):
        """Test that renderer calls style.get_class_style correctly."""

        class MockPalette:
            def to_plantuml(self):
                return "#back:FEFE54;line:968584"

        class MockStyle:
            def get_class_style(self, graph, cls, is_instance=False):
                return MockPalette()

            def get_property_style(self, graph, prop):
                return MockPalette()

        renderer = ODMRenderer(simple_graph, entities, style=MockStyle())
        output = renderer.render()

        # Should contain the mock colour specification
        assert "#back:FEFE54" in output or "FEFE54" in output

    def test_instance_styling_with_is_instance_true(self, simple_graph, entities):
        """Test that instances are styled with is_instance=True."""

        class MockPalette:
            def __init__(self, spec):
                self.spec = spec

            def to_plantuml(self):
                return self.spec

        class MockStyle:
            def get_class_style(self, graph, cls, is_instance=False):
                if is_instance:
                    # Instance styling: black fill, coloured text
                    return MockPalette("#back:000000;text:FEFE54")
                else:
                    # Class styling
                    return MockPalette("#back:FEFE54;line:968584")

            def get_property_style(self, graph, prop):
                return MockPalette("#CCCCCC")

        renderer = ODMRenderer(simple_graph, entities, style=MockStyle())
        output = renderer.render()

        # Should have both class and instance styling
        assert "FEFE54" in output  # Class colour
        assert "000000" in output  # Instance black fill

    def test_arrow_colours_from_style(self, simple_graph, entities):
        """Test that arrow colours are taken from style config."""

        class MockArrowColors:
            def get_color(self, relationship_type):
                if relationship_type == "type":
                    return "#FF0000"
                return "#000000"

        class MockStyle:
            arrow_colors = MockArrowColors()

            def get_class_style(self, graph, cls, is_instance=False):
                return None

            def get_property_style(self, graph, prop):
                return None

        renderer = ODMRenderer(simple_graph, entities, style=MockStyle())
        lines = renderer.render_type_relationships()
        output = "\n".join(lines)

        # Should use the colour from arrow_colors
        assert "#FF0000" in output or "FF0000" in output


class TestPropertyCharacteristics:
    """Test rendering of property characteristics."""

    def test_functional_property_stereotype(self):
        """Test that functional properties include characteristic in stereotype."""
        g = Graph()
        g.bind("ex", EX)

        # Create a functional object property
        g.add((EX.hasMother, RDF.type, OWL.ObjectProperty))
        g.add((EX.hasMother, RDF.type, OWL.FunctionalProperty))

        entities = {
            "classes": set(),
            "object_properties": {EX.hasMother},
            "datatype_properties": set(),
            "annotation_properties": set(),
            "instances": set(),
        }

        renderer = ODMRenderer(g, entities)
        lines = renderer.render_property_as_class(EX.hasMother)
        output = "\n".join(lines)

        # Should include both objectProperty and functional
        assert "objectProperty" in output
        assert "functional" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
