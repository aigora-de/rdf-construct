"""Unit tests for the ontology statistics module."""

import json
from datetime import datetime

import pytest
from rdflib import Graph, Namespace, RDF, RDFS, Literal
from rdflib.namespace import OWL, DCTERMS

from rdf_construct.stats import (
    OntologyStats,
    collect_stats,
    compare_stats,
    format_stats,
    format_comparison,
)
from rdf_construct.stats.metrics.basic import BasicStats, collect_basic_stats, get_all_classes
from rdf_construct.stats.metrics.hierarchy import HierarchyStats, collect_hierarchy_stats
from rdf_construct.stats.metrics.properties import PropertyStats, collect_property_stats
from rdf_construct.stats.metrics.documentation import DocumentationStats, collect_documentation_stats
from rdf_construct.stats.metrics.complexity import ComplexityStats, collect_complexity_stats
from rdf_construct.stats.metrics.connectivity import ConnectivityStats, collect_connectivity_stats


# Test namespaces
EX = Namespace("http://example.org/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


# --- Fixtures ---

@pytest.fixture
def empty_graph() -> Graph:
    """An empty RDF graph."""
    return Graph()


@pytest.fixture
def simple_graph() -> Graph:
    """A simple graph with a few classes and properties."""
    g = Graph()
    g.bind("ex", EX)

    # Classes
    g.add((EX.Animal, RDF.type, OWL.Class))
    g.add((EX.Animal, RDFS.label, Literal("Animal")))
    g.add((EX.Animal, RDFS.comment, Literal("A living creature")))

    g.add((EX.Dog, RDF.type, OWL.Class))
    g.add((EX.Dog, RDFS.subClassOf, EX.Animal))
    g.add((EX.Dog, RDFS.label, Literal("Dog")))

    g.add((EX.Cat, RDF.type, OWL.Class))
    g.add((EX.Cat, RDFS.subClassOf, EX.Animal))
    g.add((EX.Cat, RDFS.label, Literal("Cat")))

    # Object property
    g.add((EX.hasOwner, RDF.type, OWL.ObjectProperty))
    g.add((EX.hasOwner, RDFS.domain, EX.Animal))
    g.add((EX.hasOwner, RDFS.range, EX.Person))
    g.add((EX.hasOwner, RDFS.label, Literal("has owner")))

    # Datatype property
    g.add((EX.age, RDF.type, OWL.DatatypeProperty))
    g.add((EX.age, RDFS.domain, EX.Animal))
    g.add((EX.age, RDFS.label, Literal("age")))

    return g


@pytest.fixture
def complex_graph() -> Graph:
    """A more complex graph with hierarchy, multiple inheritance, etc."""
    g = Graph()
    g.bind("ex", EX)

    # Hierarchy: Entity -> Thing -> [Animal, Person]
    #                  Animal -> [Mammal, Bird]
    #                         Mammal -> Dog
    g.add((EX.Entity, RDF.type, OWL.Class))
    g.add((EX.Thing, RDF.type, OWL.Class))
    g.add((EX.Thing, RDFS.subClassOf, EX.Entity))
    g.add((EX.Animal, RDF.type, OWL.Class))
    g.add((EX.Animal, RDFS.subClassOf, EX.Thing))
    g.add((EX.Person, RDF.type, OWL.Class))
    g.add((EX.Person, RDFS.subClassOf, EX.Thing))
    g.add((EX.Mammal, RDF.type, OWL.Class))
    g.add((EX.Mammal, RDFS.subClassOf, EX.Animal))
    g.add((EX.Bird, RDF.type, OWL.Class))
    g.add((EX.Bird, RDFS.subClassOf, EX.Animal))
    g.add((EX.Dog, RDF.type, OWL.Class))
    g.add((EX.Dog, RDFS.subClassOf, EX.Mammal))

    # Multiple inheritance
    g.add((EX.Platypus, RDF.type, OWL.Class))
    g.add((EX.Platypus, RDFS.subClassOf, EX.Mammal))
    g.add((EX.Platypus, RDFS.subClassOf, EX.Bird))  # Multiple parents!

    # Orphan class
    g.add((EX.Orphan, RDF.type, OWL.Class))

    # Properties
    g.add((EX.hasChild, RDF.type, OWL.ObjectProperty))
    g.add((EX.hasParent, RDF.type, OWL.ObjectProperty))
    g.add((EX.hasChild, OWL.inverseOf, EX.hasParent))
    g.add((EX.hasChild, RDFS.domain, EX.Person))
    g.add((EX.hasChild, RDFS.range, EX.Person))

    g.add((EX.isSingleton, RDF.type, OWL.FunctionalProperty))
    g.add((EX.isSingleton, RDF.type, OWL.ObjectProperty))

    # Labels
    for cls in [EX.Entity, EX.Thing, EX.Animal, EX.Person]:
        g.add((cls, RDFS.label, Literal(str(cls).split("/")[-1])))

    return g


# --- Basic Stats Tests ---

class TestBasicStats:
    """Tests for basic count metrics."""

    def test_empty_graph(self, empty_graph: Graph):
        """Empty graph returns zeros."""
        stats = collect_basic_stats(empty_graph)
        assert stats.triples == 0
        assert stats.classes == 0
        assert stats.object_properties == 0

    def test_simple_counts(self, simple_graph: Graph):
        """Counts classes and properties correctly."""
        stats = collect_basic_stats(simple_graph)
        assert stats.classes == 3  # Animal, Dog, Cat
        assert stats.object_properties == 1  # hasOwner
        assert stats.datatype_properties == 1  # age
        assert stats.triples > 0

    def test_total_properties(self, simple_graph: Graph):
        """Total properties sums all property types."""
        stats = collect_basic_stats(simple_graph)
        assert stats.total_properties == stats.object_properties + stats.datatype_properties


# --- Hierarchy Stats Tests ---

class TestHierarchyStats:
    """Tests for hierarchy metrics."""

    def test_empty_graph(self, empty_graph: Graph):
        """Empty graph returns zeros."""
        stats = collect_hierarchy_stats(empty_graph)
        assert stats.root_classes == 0
        assert stats.max_depth == 0

    def test_simple_hierarchy(self, simple_graph: Graph):
        """Correctly identifies roots and leaves."""
        stats = collect_hierarchy_stats(simple_graph)
        assert stats.root_classes == 1  # Animal
        assert stats.leaf_classes == 2  # Dog, Cat
        assert stats.max_depth == 1  # Animal -> Dog/Cat

    def test_complex_hierarchy(self, complex_graph: Graph):
        """Handles deeper hierarchies."""
        stats = collect_hierarchy_stats(complex_graph)
        # Entity -> Thing -> Animal -> Mammal -> Dog
        assert stats.max_depth == 4
        assert stats.orphan_classes == 1  # Orphan class

    def test_orphan_rate(self, complex_graph: Graph):
        """Orphan rate is calculated correctly."""
        stats = collect_hierarchy_stats(complex_graph)
        total_classes = len(get_all_classes(complex_graph))
        assert stats.orphan_rate == pytest.approx(1 / total_classes, rel=0.01)


# --- Property Stats Tests ---

class TestPropertyStats:
    """Tests for property metrics."""

    def test_domain_range_coverage(self, simple_graph: Graph):
        """Counts domain and range declarations."""
        stats = collect_property_stats(simple_graph)
        assert stats.with_domain == 2  # hasOwner, age have domains
        assert stats.with_range == 1  # hasOwner has range

    def test_inverse_pairs(self, complex_graph: Graph):
        """Counts inverse property pairs."""
        stats = collect_property_stats(complex_graph)
        assert stats.inverse_pairs == 1  # hasChild/hasParent

    def test_functional_properties(self, complex_graph: Graph):
        """Counts functional properties."""
        stats = collect_property_stats(complex_graph)
        assert stats.functional == 1  # isSingleton


# --- Documentation Stats Tests ---

class TestDocumentationStats:
    """Tests for documentation coverage metrics."""

    def test_label_coverage(self, simple_graph: Graph):
        """Counts labelled classes."""
        stats = collect_documentation_stats(simple_graph)
        assert stats.classes_labelled == 3  # All three classes have labels
        assert stats.classes_labelled_pct == 1.0

    def test_documentation_coverage(self, simple_graph: Graph):
        """Counts documented classes (with comments)."""
        stats = collect_documentation_stats(simple_graph)
        assert stats.classes_documented == 1  # Only Animal has comment
        assert stats.classes_documented_pct == pytest.approx(1/3, rel=0.01)


# --- Complexity Stats Tests ---

class TestComplexityStats:
    """Tests for complexity metrics."""

    def test_multiple_inheritance(self, complex_graph: Graph):
        """Detects classes with multiple parents."""
        stats = collect_complexity_stats(complex_graph)
        assert stats.multiple_inheritance_count == 1  # Platypus


# --- Connectivity Stats Tests ---

class TestConnectivityStats:
    """Tests for connectivity metrics."""

    def test_most_connected(self, simple_graph: Graph):
        """Identifies the most connected class."""
        stats = collect_connectivity_stats(simple_graph)
        assert stats.most_connected_class is not None
        assert stats.most_connected_count > 0


# --- Collector Tests ---

class TestCollector:
    """Tests for the main stats collector."""

    def test_collect_all_categories(self, simple_graph: Graph):
        """Collects all metric categories."""
        stats = collect_stats(simple_graph, source="test.ttl")
        assert stats.source == "test.ttl"
        assert isinstance(stats.timestamp, datetime)
        assert isinstance(stats.basic, BasicStats)
        assert isinstance(stats.hierarchy, HierarchyStats)

    def test_include_filter(self, simple_graph: Graph):
        """Include filter limits categories."""
        stats = collect_stats(simple_graph, include={"basic"})
        assert stats.basic.classes > 0
        # Other categories should be defaults (zeros)
        assert stats.hierarchy.max_depth == 0

    def test_exclude_filter(self, simple_graph: Graph):
        """Exclude filter skips categories."""
        stats = collect_stats(simple_graph, exclude={"hierarchy"})
        assert stats.basic.classes > 0
        assert stats.hierarchy.max_depth == 0  # Excluded = default

    def test_invalid_category_raises(self, simple_graph: Graph):
        """Invalid category name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown metric categories"):
            collect_stats(simple_graph, include={"invalid_category"})

    def test_to_dict(self, simple_graph: Graph):
        """Stats can be converted to dictionary."""
        stats = collect_stats(simple_graph)
        d = stats.to_dict()
        assert "basic" in d
        assert "hierarchy" in d
        assert d["basic"]["classes"] == 3


# --- Comparator Tests ---

class TestComparator:
    """Tests for stats comparison."""

    def test_identical_stats(self, simple_graph: Graph):
        """Comparing identical graphs shows no changes."""
        stats1 = collect_stats(simple_graph, source="v1.ttl")
        stats2 = collect_stats(simple_graph, source="v2.ttl")
        comparison = compare_stats(stats1, stats2)
        assert len(comparison.changes) == 0

    def test_detect_changes(self, simple_graph: Graph, complex_graph: Graph):
        """Detects differences between graphs."""
        stats1 = collect_stats(simple_graph, source="simple.ttl")
        stats2 = collect_stats(complex_graph, source="complex.ttl")
        comparison = compare_stats(stats1, stats2)
        assert len(comparison.changes) > 0
        assert comparison.summary != ""

    def test_change_direction(self, simple_graph: Graph, complex_graph: Graph):
        """Change delta is calculated correctly."""
        stats1 = collect_stats(simple_graph, source="v1")
        stats2 = collect_stats(complex_graph, source="v2")
        comparison = compare_stats(stats1, stats2)

        # Complex has more classes
        class_change = next((c for c in comparison.changes if c.metric == "classes"), None)
        assert class_change is not None
        assert class_change.delta > 0  # More classes in complex


# --- Formatter Tests ---

class TestFormatters:
    """Tests for output formatters."""

    def test_text_format(self, simple_graph: Graph):
        """Text format produces readable output."""
        stats = collect_stats(simple_graph, source="test.ttl")
        output = format_stats(stats, format_name="text")
        assert "Ontology Statistics" in output
        assert "BASIC COUNTS" in output
        assert "Classes:" in output

    def test_json_format(self, simple_graph: Graph):
        """JSON format is valid JSON."""
        stats = collect_stats(simple_graph, source="test.ttl")
        output = format_stats(stats, format_name="json")
        parsed = json.loads(output)
        assert parsed["basic"]["classes"] == 3

    def test_markdown_format(self, simple_graph: Graph):
        """Markdown format has tables."""
        stats = collect_stats(simple_graph, source="test.ttl")
        output = format_stats(stats, format_name="markdown")
        assert "## Ontology Statistics" in output
        assert "| Metric | Value |" in output

    def test_invalid_format_raises(self, simple_graph: Graph):
        """Invalid format name raises ValueError."""
        stats = collect_stats(simple_graph)
        with pytest.raises(ValueError, match="Unknown format"):
            format_stats(stats, format_name="invalid")

    def test_comparison_text_format(self, simple_graph: Graph, complex_graph: Graph):
        """Comparison text format is readable."""
        stats1 = collect_stats(simple_graph, source="v1.ttl")
        stats2 = collect_stats(complex_graph, source="v2.ttl")
        comparison = compare_stats(stats1, stats2)
        output = format_comparison(comparison, format_name="text")
        assert "Comparing:" in output
        assert "Summary:" in output

    def test_comparison_json_format(self, simple_graph: Graph, complex_graph: Graph):
        """Comparison JSON format is valid."""
        stats1 = collect_stats(simple_graph, source="v1.ttl")
        stats2 = collect_stats(complex_graph, source="v2.ttl")
        comparison = compare_stats(stats1, stats2)
        output = format_comparison(comparison, format_name="json")
        parsed = json.loads(output)
        assert "changes" in parsed
        assert "summary" in parsed
