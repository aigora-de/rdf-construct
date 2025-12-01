"""Tests for the semantic diff module."""

import json
import pytest
from pathlib import Path

from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS
from rdflib.namespace import OWL, XSD

# For testing, we'll import from the local files
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from rdf_construct.diff import (
    compare_graphs,
    filter_diff,
    parse_filter_string,
    ChangeType,
    EntityChange,
    EntityType,
    GraphDiff,
    TripleChange,
    PredicateCategory,
)
from rdf_construct.diff.change_types import categorise_predicate
from rdf_construct.diff.comparator import _determine_entity_type
from rdf_construct.diff.formatters import format_text, format_markdown, format_json

# Test namespaces
EX = Namespace("http://example.org/")


class TestCompareGraphs:
    """Tests for core graph comparison."""

    def test_identical_graphs(self):
        """Same triples in different order should be identical."""
        # Graph 1
        g1 = Graph()
        g1.add((EX.ClassA, RDF.type, OWL.Class))
        g1.add((EX.ClassA, RDFS.label, Literal("Class A")))
        g1.add((EX.ClassB, RDF.type, OWL.Class))

        # Graph 2 - same content, different insertion order
        g2 = Graph()
        g2.add((EX.ClassB, RDF.type, OWL.Class))
        g2.add((EX.ClassA, RDFS.label, Literal("Class A")))
        g2.add((EX.ClassA, RDF.type, OWL.Class))

        diff = compare_graphs(g1, g2)

        assert diff.is_identical
        assert len(diff.added) == 0
        assert len(diff.removed) == 0
        assert len(diff.modified) == 0

    def test_added_class(self):
        """Detect a new class in the new graph."""
        g1 = Graph()
        g1.add((EX.ClassA, RDF.type, OWL.Class))

        g2 = Graph()
        g2.add((EX.ClassA, RDF.type, OWL.Class))
        g2.add((EX.ClassB, RDF.type, OWL.Class))  # New class

        diff = compare_graphs(g1, g2)

        assert not diff.is_identical
        assert len(diff.added) == 1
        assert len(diff.removed) == 0
        assert len(diff.modified) == 0

        added_entity = diff.added[0]
        assert added_entity.uri == EX.ClassB
        assert added_entity.entity_type == EntityType.CLASS
        assert added_entity.change_type == ChangeType.ADDED

    def test_removed_class(self):
        """Detect a removed class."""
        g1 = Graph()
        g1.add((EX.ClassA, RDF.type, OWL.Class))
        g1.add((EX.ClassB, RDF.type, OWL.Class))

        g2 = Graph()
        g2.add((EX.ClassA, RDF.type, OWL.Class))
        # ClassB is removed

        diff = compare_graphs(g1, g2)

        assert not diff.is_identical
        assert len(diff.added) == 0
        assert len(diff.removed) == 1
        assert len(diff.modified) == 0

        removed_entity = diff.removed[0]
        assert removed_entity.uri == EX.ClassB
        assert removed_entity.entity_type == EntityType.CLASS

    def test_modified_class_label(self):
        """Detect a modified label."""
        g1 = Graph()
        g1.add((EX.ClassA, RDF.type, OWL.Class))
        g1.add((EX.ClassA, RDFS.label, Literal("Class A")))

        g2 = Graph()
        g2.add((EX.ClassA, RDF.type, OWL.Class))
        g2.add((EX.ClassA, RDFS.label, Literal("Class Alpha")))  # Changed label

        diff = compare_graphs(g1, g2)

        assert not diff.is_identical
        assert len(diff.added) == 0
        assert len(diff.removed) == 0
        assert len(diff.modified) == 1

        modified = diff.modified[0]
        assert modified.uri == EX.ClassA
        assert len(modified.added_triples) == 1
        assert len(modified.removed_triples) == 1

    def test_hierarchy_change(self):
        """Detect a change in class hierarchy."""
        g1 = Graph()
        g1.add((EX.ClassA, RDF.type, OWL.Class))
        g1.add((EX.ClassA, RDFS.subClassOf, EX.Thing))

        g2 = Graph()
        g2.add((EX.ClassA, RDF.type, OWL.Class))
        g2.add((EX.ClassA, RDFS.subClassOf, EX.PhysicalEntity))  # New parent

        diff = compare_graphs(g1, g2)

        assert not diff.is_identical
        assert len(diff.modified) == 1

        modified = diff.modified[0]
        # Should have removed old subClassOf and added new one
        added_preds = [t.predicate for t in modified.added_triples]
        removed_preds = [t.predicate for t in modified.removed_triples]
        assert RDFS.subClassOf in added_preds
        assert RDFS.subClassOf in removed_preds

    def test_prefix_independence(self):
        """Different prefixes for same URIs should be identical."""
        g1 = Graph()
        g1.bind("ex", EX)
        g1.add((EX.ClassA, RDF.type, OWL.Class))

        g2 = Graph()
        g2.bind("example", EX)  # Different prefix
        g2.add((EX.ClassA, RDF.type, OWL.Class))

        diff = compare_graphs(g1, g2)
        assert diff.is_identical

    def test_ignore_predicates(self):
        """Ignored predicates should not appear in diff."""
        DCTERMS = Namespace("http://purl.org/dc/terms/")

        g1 = Graph()
        g1.add((EX.ClassA, RDF.type, OWL.Class))
        g1.add((EX.ClassA, DCTERMS.modified, Literal("2024-01-01")))

        g2 = Graph()
        g2.add((EX.ClassA, RDF.type, OWL.Class))
        g2.add((EX.ClassA, DCTERMS.modified, Literal("2024-06-15")))  # Different date

        # Without ignore, should show modification
        diff1 = compare_graphs(g1, g2)
        assert not diff1.is_identical

        # With ignore, should be identical
        diff2 = compare_graphs(g1, g2, ignore_predicates={DCTERMS.modified})
        assert diff2.is_identical

    def test_detect_object_property(self):
        """Correctly classify ObjectProperty entities."""
        g1 = Graph()

        g2 = Graph()
        g2.add((EX.hasPart, RDF.type, OWL.ObjectProperty))
        g2.add((EX.hasPart, RDFS.domain, EX.Thing))

        diff = compare_graphs(g1, g2)

        assert len(diff.added) == 1
        assert diff.added[0].entity_type == EntityType.OBJECT_PROPERTY

    def test_detect_datatype_property(self):
        """Correctly classify DatatypeProperty entities."""
        g1 = Graph()

        g2 = Graph()
        g2.add((EX.hasName, RDF.type, OWL.DatatypeProperty))
        g2.add((EX.hasName, RDFS.range, XSD.string))

        diff = compare_graphs(g1, g2)

        assert len(diff.added) == 1
        assert diff.added[0].entity_type == EntityType.DATATYPE_PROPERTY

    def test_detect_individual(self):
        """Correctly classify individual instances."""
        g1 = Graph()

        g2 = Graph()
        g2.add((EX.building1, RDF.type, EX.Building))
        g2.add((EX.building1, RDFS.label, Literal("Building One")))

        diff = compare_graphs(g1, g2)

        assert len(diff.added) == 1
        assert diff.added[0].entity_type == EntityType.INDIVIDUAL


class TestFilters:
    """Tests for diff filtering."""

    def test_filter_show_added_only(self):
        """Filter to show only added entities."""
        diff = GraphDiff(
            old_path="old.ttl",
            new_path="new.ttl",
            added=[
                EntityChange(
                    uri=EX.ClassA,
                    entity_type=EntityType.CLASS,
                    change_type=ChangeType.ADDED,
                )
            ],
            removed=[
                EntityChange(
                    uri=EX.ClassB,
                    entity_type=EntityType.CLASS,
                    change_type=ChangeType.REMOVED,
                )
            ],
            modified=[
                EntityChange(
                    uri=EX.ClassC,
                    entity_type=EntityType.CLASS,
                    change_type=ChangeType.MODIFIED,
                )
            ],
        )

        filtered = filter_diff(diff, show_types={"added"})

        assert len(filtered.added) == 1
        assert len(filtered.removed) == 0
        assert len(filtered.modified) == 0

    def test_filter_hide_modified(self):
        """Filter to hide modified entities."""
        diff = GraphDiff(
            old_path="old.ttl",
            new_path="new.ttl",
            added=[
                EntityChange(
                    uri=EX.ClassA,
                    entity_type=EntityType.CLASS,
                    change_type=ChangeType.ADDED,
                )
            ],
            removed=[
                EntityChange(
                    uri=EX.ClassB,
                    entity_type=EntityType.CLASS,
                    change_type=ChangeType.REMOVED,
                )
            ],
            modified=[
                EntityChange(
                    uri=EX.ClassC,
                    entity_type=EntityType.CLASS,
                    change_type=ChangeType.MODIFIED,
                )
            ],
        )

        filtered = filter_diff(diff, hide_types={"modified"})

        assert len(filtered.added) == 1
        assert len(filtered.removed) == 1
        assert len(filtered.modified) == 0

    def test_filter_by_entity_type(self):
        """Filter to show only classes."""
        diff = GraphDiff(
            old_path="old.ttl",
            new_path="new.ttl",
            added=[
                EntityChange(
                    uri=EX.ClassA,
                    entity_type=EntityType.CLASS,
                    change_type=ChangeType.ADDED,
                ),
                EntityChange(
                    uri=EX.prop1,
                    entity_type=EntityType.OBJECT_PROPERTY,
                    change_type=ChangeType.ADDED,
                ),
            ],
        )

        filtered = filter_diff(diff, entity_types={"classes"})

        assert len(filtered.added) == 1
        assert filtered.added[0].entity_type == EntityType.CLASS

    def test_parse_filter_string(self):
        """Parse comma-separated filter strings."""
        assert parse_filter_string("added,removed") == {"added", "removed"}
        assert parse_filter_string(" added , removed ") == {"added", "removed"}
        assert parse_filter_string("") == set()
        assert parse_filter_string("classes") == {"classes"}


class TestFormatters:
    """Tests for output formatters."""

    @pytest.fixture
    def sample_diff(self):
        """Create a sample diff for testing formatters."""
        return GraphDiff(
            old_path="v1.0.ttl",
            new_path="v1.1.ttl",
            added=[
                EntityChange(
                    uri=EX.SmartBuilding,
                    entity_type=EntityType.CLASS,
                    change_type=ChangeType.ADDED,
                    label="SmartBuilding",
                    superclasses=[EX.Building],
                )
            ],
            removed=[
                EntityChange(
                    uri=EX.DeprecatedClass,
                    entity_type=EntityType.CLASS,
                    change_type=ChangeType.REMOVED,
                    label="DeprecatedClass",
                )
            ],
            modified=[
                EntityChange(
                    uri=EX.Building,
                    entity_type=EntityType.CLASS,
                    change_type=ChangeType.MODIFIED,
                    label="Building",
                    added_triples=[
                        TripleChange(
                            predicate=RDFS.comment,
                            object=Literal("A constructed structure"),
                            is_addition=True,
                        )
                    ],
                )
            ],
        )

    def test_text_format(self, sample_diff):
        """Test plain text output."""
        output = format_text(sample_diff)

        assert "Comparing v1.0.ttl → v1.1.ttl" in output
        assert "ADDED (1 entities):" in output
        assert "SmartBuilding" in output
        assert "REMOVED (1 entities):" in output
        assert "DeprecatedClass" in output
        assert "MODIFIED (1 entities):" in output
        assert "Building" in output
        assert "Summary: 1 added, 1 removed, 1 modified" in output

    def test_markdown_format(self, sample_diff):
        """Test markdown output."""
        output = format_markdown(sample_diff)

        assert "# Ontology Changes:" in output
        assert "## Summary" in output
        assert "## Added" in output
        assert "## Removed" in output
        assert "## Modified" in output
        assert "**SmartBuilding**" in output

    def test_json_format(self, sample_diff):
        """Test JSON output."""
        output = format_json(sample_diff)
        data = json.loads(output)

        assert data["comparison"]["old"] == "v1.0.ttl"
        assert data["comparison"]["new"] == "v1.1.ttl"
        assert data["identical"] is False
        assert data["summary"]["added"] == 1
        assert data["summary"]["removed"] == 1
        assert data["summary"]["modified"] == 1
        assert "classes" in data["added"]

    def test_identical_diff_output(self):
        """Test output for identical graphs."""
        diff = GraphDiff(old_path="a.ttl", new_path="b.ttl")

        text_output = format_text(diff)
        assert "No semantic differences found" in text_output

        md_output = format_markdown(diff)
        assert "No semantic differences found" in md_output

        json_output = format_json(diff)
        data = json.loads(json_output)
        assert data["identical"] is True


class TestPredicateCategories:
    """Tests for predicate categorisation."""

    def test_categorise_type(self):
        """Correctly categorise rdf:type."""
        assert categorise_predicate(RDF.type) == PredicateCategory.TYPE

    def test_categorise_hierarchy(self):
        """Correctly categorise subClassOf."""
        assert categorise_predicate(RDFS.subClassOf) == PredicateCategory.HIERARCHY

    def test_categorise_label(self):
        """Correctly categorise rdfs:label."""
        assert categorise_predicate(RDFS.label) == PredicateCategory.LABEL

    def test_categorise_comment(self):
        """Correctly categorise rdfs:comment."""
        assert categorise_predicate(RDFS.comment) == PredicateCategory.DOCUMENTATION


class TestEntityTypeDetection:
    """Tests for entity type detection."""

    def test_detect_owl_class(self):
        """Detect owl:Class."""
        g = Graph()
        g.add((EX.Thing, RDF.type, OWL.Class))
        assert _determine_entity_type(g, EX.Thing) == EntityType.CLASS

    def test_detect_rdfs_class(self):
        """Detect rdfs:Class."""
        g = Graph()
        g.add((EX.Thing, RDF.type, RDFS.Class))
        assert _determine_entity_type(g, EX.Thing) == EntityType.CLASS

    def test_detect_ontology(self):
        """Detect owl:Ontology."""
        g = Graph()
        g.add((EX.myOntology, RDF.type, OWL.Ontology))
        assert _determine_entity_type(g, EX.myOntology) == EntityType.ONTOLOGY


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
