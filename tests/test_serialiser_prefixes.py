"""Tests for prefix filtering in serialiser output.

Verifies that serialise_turtle() and build_section_graph() only emit
prefix declarations for namespaces actually used in the graph's triples,
filtering out rdflib's built-in well-known namespace defaults.

Relates to: #49
"""

import pytest
from pathlib import Path

from rdflib import Graph, URIRef, Literal, Namespace, RDF
from rdflib.namespace import RDFS, OWL, XSD, DCTERMS, SKOS

from rdf_construct.core.serialiser import (
    collect_used_namespaces,
    serialise_turtle,
    build_section_graph,
)


# -- Namespace constants used across tests --
# NOTE: Avoid attribute names that shadow str built-in methods (e.g.
# .count, .index, .format) — rdflib's Namespace extends str, so those
# resolve to the method rather than constructing a URIRef.

EX = Namespace("http://example.org/ont#")
DC = Namespace("http://purl.org/dc/elements/1.1/")


@pytest.fixture
def small_graph() -> Graph:
    """Graph with a handful of explicitly bound prefixes and triples."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    g.add((EX.Animal, RDF.type, OWL.Class))
    g.add((EX.Animal, RDFS.label, Literal("Animal", lang="en")))
    g.add((EX.Dog, RDF.type, OWL.Class))
    g.add((EX.Dog, RDFS.subClassOf, EX.Animal))

    return g


@pytest.fixture
def overlapping_ns_graph() -> Graph:
    """Graph using both dc: and dcterms: to test longest-match-first logic."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("dc", DC)
    g.bind("dcterms", DCTERMS)

    g.add((EX.MyOnt, RDF.type, OWL.Ontology))
    g.add((EX.MyOnt, DCTERMS.title, Literal("My Ontology")))
    g.add((EX.MyOnt, DC.creator, Literal("Test Author")))

    return g


# -- collect_used_namespaces tests --


class TestCollectUsedNamespaces:
    """Tests for the collect_used_namespaces helper."""

    def test_returns_only_used_namespaces(self, small_graph: Graph) -> None:
        """Only namespaces referenced in triples should be returned."""
        used = collect_used_namespaces(small_graph)

        assert str(EX) in used
        assert str(OWL) in used
        assert str(RDFS) in used
        assert str(RDF) in used  # rdf:type is used

    def test_excludes_unused_rdflib_defaults(self, small_graph: Graph) -> None:
        """rdflib's well-known defaults that aren't used should be excluded."""
        used = collect_used_namespaces(small_graph)

        # These are typical rdflib defaults that shouldn't appear
        unused_defaults = [
            "https://brickschema.org/schema/Brick#",
            "http://www.w3.org/ns/csvw#",
            "http://xmlns.com/foaf/0.1/",
            "http://www.w3.org/ns/org#",
            "https://schema.org/",
            "http://www.w3.org/ns/shacl#",
            "http://www.w3.org/ns/prov#",
        ]
        for ns in unused_defaults:
            assert ns not in used, f"Unused default namespace should be excluded: {ns}"

    def test_empty_graph_returns_empty_set(self) -> None:
        """An empty graph should yield no used namespaces."""
        g = Graph()
        assert collect_used_namespaces(g) == set()

    def test_overlapping_namespaces_longest_match(
        self, overlapping_ns_graph: Graph
    ) -> None:
        """dc: and dcterms: should both be detected independently."""
        used = collect_used_namespaces(overlapping_ns_graph)

        assert str(DC) in used
        assert str(DCTERMS) in used

    def test_datatype_namespace_included(self) -> None:
        """Namespace from a datatype URI should be included."""
        g = Graph()
        g.bind("ex", EX)
        g.bind("xsd", XSD)
        # Use explicit URIRef for the predicate to avoid shadowing str
        # built-in methods (e.g. Namespace("...").count -> str.count).
        g.add((EX.Thing, EX.itemCount, Literal(42, datatype=XSD.integer)))

        used = collect_used_namespaces(g)
        assert str(XSD) in used


# -- serialise_turtle prefix output tests --


class TestSerialiseTurtlePrefixes:
    """Tests for prefix filtering in serialise_turtle output."""

    def test_output_contains_only_used_prefixes(
        self, small_graph: Graph, tmp_path: Path
    ) -> None:
        """Output file should only declare prefixes for used namespaces."""
        out = tmp_path / "output.ttl"
        subjects = [EX.Animal, EX.Dog]

        serialise_turtle(small_graph, subjects, out)

        content = out.read_text(encoding="utf-8")
        prefix_lines = [
            line for line in content.splitlines() if line.startswith("PREFIX ")
        ]

        # Extract declared prefix names
        declared = {line.split(":")[0].replace("PREFIX ", "") for line in prefix_lines}

        # Should include prefixes we actually use
        assert "ex" in declared
        assert "owl" in declared
        assert "rdfs" in declared

        # Should NOT include rdflib defaults we don't use
        assert "brick" not in declared
        assert "foaf" not in declared
        assert "csvw" not in declared
        assert "schema" not in declared
        assert "sh" not in declared
        assert "prov" not in declared
        assert "sosa" not in declared

    def test_output_with_overlapping_namespaces(
        self, overlapping_ns_graph: Graph, tmp_path: Path
    ) -> None:
        """Both dc: and dcterms: should appear when both are used."""
        out = tmp_path / "output.ttl"
        subjects = [EX.MyOnt]

        serialise_turtle(overlapping_ns_graph, subjects, out)

        content = out.read_text(encoding="utf-8")
        prefix_lines = [
            line for line in content.splitlines() if line.startswith("PREFIX ")
        ]
        declared = {line.split(":")[0].replace("PREFIX ", "") for line in prefix_lines}

        assert "dc" in declared
        assert "dcterms" in declared


# -- build_section_graph tests --


class TestBuildSectionGraphPrefixes:
    """Tests for prefix filtering in build_section_graph."""

    def test_section_graph_has_only_used_prefixes(
        self, small_graph: Graph
    ) -> None:
        """Sub-graph should only carry namespace bindings for its own triples."""
        # Build a section with only EX.Animal
        sg = build_section_graph(small_graph, [EX.Animal])

        sg_prefixes = {pfx for pfx, _ in sg.namespace_manager.namespaces()}

        # Should have namespaces used by Animal's triples
        assert "ex" in sg_prefixes
        assert "owl" in sg_prefixes
        assert "rdfs" in sg_prefixes

        # Should NOT carry over unused rdflib defaults
        assert "brick" not in sg_prefixes
        assert "foaf" not in sg_prefixes
        assert "csvw" not in sg_prefixes
        assert "schema" not in sg_prefixes

    def test_section_graph_triples_preserved(self, small_graph: Graph) -> None:
        """All triples for the specified subjects should be present."""
        sg = build_section_graph(small_graph, [EX.Animal])

        triples = list(sg.triples((EX.Animal, None, None)))
        assert len(triples) == 2  # rdf:type + rdfs:label

    def test_section_graph_excludes_other_subjects(
        self, small_graph: Graph
    ) -> None:
        """Triples for subjects not in the list should be absent."""
        sg = build_section_graph(small_graph, [EX.Animal])

        dog_triples = list(sg.triples((EX.Dog, None, None)))
        assert len(dog_triples) == 0
