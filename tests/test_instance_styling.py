"""Tests for instance-specific styling functionality.

Run with: pytest test_instance_styling.py -v
"""

import pytest
from rdflib import Graph, Namespace, URIRef, RDF, RDFS


@pytest.fixture
def sample_graph():
    """Create a sample RDF graph with IES-style hierarchy."""
    g = Graph()
    IES = Namespace("http://ies.data.gov.uk/ontology/ies4#")
    BUILDING = Namespace("http://example.org/building#")

    g.bind("ies", IES)
    g.bind("building", BUILDING)

    # Class hierarchy
    g.add((BUILDING.Building, RDFS.subClassOf, IES.Entity))
    g.add((BUILDING.Wall, RDFS.subClassOf, BUILDING.BuiltEntity))
    g.add((BUILDING.BuiltEntity, RDFS.subClassOf, IES.Entity))
    g.add((BUILDING.BuildingState, RDFS.subClassOf, IES.State))
    g.add((BUILDING.WallState, RDFS.subClassOf, BUILDING.BuiltEntityState))
    g.add((BUILDING.BuiltEntityState, RDFS.subClassOf, IES.State))

    # Instances
    g.add((BUILDING.Windsor_Castle, RDF.type, BUILDING.Building))
    g.add((BUILDING.Wall_23, RDF.type, BUILDING.Wall))
    g.add((BUILDING.Windsor_State_2025, RDF.type, BUILDING.BuildingState))
    g.add((BUILDING.WallState_001, RDF.type, BUILDING.WallState))

    return g


def test_graph_structure(sample_graph):
    """Verify test graph is constructed correctly."""
    BUILDING = Namespace("http://example.org/building#")
    IES = Namespace("http://ies.data.gov.uk/ontology/ies4#")

    # Check instance types
    types = list(sample_graph.objects(BUILDING.Windsor_Castle, RDF.type))
    assert len(types) > 0
    assert BUILDING.Building in types

    # Check class hierarchy
    parents = list(sample_graph.objects(BUILDING.Building, RDFS.subClassOf))
    assert IES.Entity in parents


def test_style_config_structure():
    """Test style configuration dictionary structure."""
    config = {
        "classes": {
            "by_type": {
                "ies:Entity": {"border": "#FEFE54", "fill": "#FEFE54"}
            }
        },
        "instances": {
            "by_type": {
                "ies:Entity": {"border": "#FEFE54", "fill": "#000000"}
            },
            "default": {"border": "#000000", "fill": "#000000"}
        }
    }

    assert "instances" in config
    assert "by_type" in config["instances"]
    assert "default" in config["instances"]


# More tests would require the actual StyleScheme implementation
# These are structural tests to verify the design

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
