"""Tests for ``core.provenance``: the derived-identity helper shared by #90, #171 and #178.

``order`` (#90) uses :func:`stamp_extract`. ``split`` (#178) and ``merge`` (#171) will compose
the smaller functions under identities of their own, so each is tested here for the shape those
commands need, not only for ``order``'s.
"""

from __future__ import annotations

from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, PROV, RDFS

from rdf_construct.core import (
    WAS_DERIVED_FROM,
    Stamp,
    derivation_targets,
    missing_triples,
    stamp_derivation,
    stamp_extract,
    strip_version_iri,
)

A = URIRef("http://example.org/a")
A_V1 = URIRef("http://example.org/a/1.0")
A_V2 = URIRef("http://example.org/a/2.0")
B = URIRef("http://example.org/b")
EX = Namespace("http://example.org/a#")


def _header(graph: Graph, ontology: URIRef, *versions: URIRef) -> Graph:
    graph.add((ontology, RDF.type, OWL.Ontology))
    graph.add((ontology, OWL.versionInfo, Literal("1.0")))
    graph.add((ontology, OWL.imports, URIRef("http://example.org/upstream")))
    for version in versions:
        graph.add((ontology, OWL.versionIRI, version))
    return graph


class TestDerivationTargets:
    def test_names_the_version_iri(self) -> None:
        assert derivation_targets(_header(Graph(), A, A_V1), A) == [A_V1]

    def test_falls_back_to_the_ontology_iri(self) -> None:
        assert derivation_targets(_header(Graph(), A), A) == [A]

    def test_several_version_iris_are_each_named_in_order(self) -> None:
        assert derivation_targets(_header(Graph(), A, A_V2, A_V1), A) == [A_V1, A_V2]

    def test_a_literal_version_iri_names_nothing_and_falls_back(self) -> None:
        graph = _header(Graph(), A)
        graph.add((A, OWL.versionIRI, Literal("1.0")))
        assert derivation_targets(graph, A) == [A]

    def test_an_anonymous_ontology_with_no_version_has_no_name(self) -> None:
        node = BNode()
        graph = Graph()
        graph.add((node, RDF.type, OWL.Ontology))
        assert derivation_targets(graph, node) == []

    def test_an_anonymous_ontology_is_named_by_its_version(self) -> None:
        node = BNode()
        graph = Graph()
        graph.add((node, RDF.type, OWL.Ontology))
        graph.add((node, OWL.versionIRI, A_V1))
        assert derivation_targets(graph, node) == [A_V1]


class TestStripVersionIri:
    def test_removes_only_the_version_iri(self) -> None:
        """#171's demotion is this plus the type triple, so nothing else may go."""
        graph = _header(Graph(), A, A_V1)
        graph.add((A, RDF.type, OWL.Class))  # punned: an ontology and a class
        before = set(graph)
        assert strip_version_iri(graph, A) == [A_V1]
        assert set(graph) == before - {(A, OWL.versionIRI, A_V1)}

    def test_touches_no_other_header(self) -> None:
        graph = _header(_header(Graph(), A, A_V1), B, URIRef("http://example.org/b/3"))
        strip_version_iri(graph, A)
        assert list(graph.objects(B, OWL.versionIRI)) == [URIRef("http://example.org/b/3")]

    def test_nothing_to_remove(self) -> None:
        graph = _header(Graph(), A)
        assert strip_version_iri(graph, A) == []


class TestStampDerivation:
    def test_one_derivation_per_source(self) -> None:
        """#171: a merged header names each source it was built from."""
        merged = Graph()
        merged.add((B, RDF.type, OWL.Ontology))
        stamp_derivation(merged, B, [A_V1, URIRef("http://example.org/c")])
        assert set(merged.objects(B, WAS_DERIVED_FROM)) == {A_V1, URIRef("http://example.org/c")}

    def test_on_a_subject_other_than_the_source(self) -> None:
        """#178: a module's own IRI is stamped with its source's name."""
        module = Graph()
        module_iri = URIRef("http://example.org/a/core")
        module.add((module_iri, RDF.type, OWL.Ontology))
        stamp_derivation(module, module_iri, derivation_targets(_header(Graph(), A, A_V1), A))
        assert list(module.objects(module_iri, PROV.wasDerivedFrom)) == [A_V1]

    def test_declares_the_property(self) -> None:
        graph = Graph()
        stamp_derivation(graph, A, [A_V1])
        assert (PROV.wasDerivedFrom, RDF.type, OWL.AnnotationProperty) in graph

    def test_a_generic_property_type_does_not_suppress_the_declaration(self) -> None:
        """#426: ``rdf:Property`` says the IRI is a property, not which kind."""
        graph = Graph()
        graph.add((PROV.wasDerivedFrom, RDF.type, RDF.Property))
        stamp_derivation(graph, A, [A_V1])
        assert (PROV.wasDerivedFrom, RDF.type, OWL.AnnotationProperty) in graph

    def test_a_lone_functional_property_still_gets_the_declaration(self) -> None:
        graph = Graph()
        graph.add((PROV.wasDerivedFrom, RDF.type, OWL.FunctionalProperty))
        stamp_derivation(graph, A, [A_V1])
        assert (PROV.wasDerivedFrom, RDF.type, OWL.AnnotationProperty) in graph

    def test_an_existing_annotation_declaration_is_kept(self) -> None:
        graph = Graph()
        graph.add((PROV.wasDerivedFrom, RDF.type, OWL.AnnotationProperty))
        stamp_derivation(graph, A, [A_V1])
        assert set(graph.objects(PROV.wasDerivedFrom, RDF.type)) == {OWL.AnnotationProperty}

    def test_binds_prov(self) -> None:
        graph = Graph(bind_namespaces="none")
        stamp_derivation(graph, A, [A_V1])
        assert ("prov", URIRef(str(PROV))) in set(graph.namespace_manager.namespaces())

    def test_keeps_a_prefix_the_graph_already_has_for_prov(self) -> None:
        graph = Graph(bind_namespaces="none")
        graph.namespace_manager.bind("pv", PROV)
        stamp_derivation(graph, A, [A_V1])
        bound = dict(graph.namespace_manager.namespaces())
        assert bound["pv"] == URIRef(str(PROV))
        assert "prov" not in bound

    def test_never_rebinds_a_prov_prefix_meaning_something_else(self) -> None:
        other = URIRef("http://example.org/provenance#")
        graph = Graph(bind_namespaces="none")
        graph.namespace_manager.bind("prov", other)
        stamp_derivation(graph, A, [A_V1])
        assert dict(graph.namespace_manager.namespaces())["prov"] == other

    def test_keeps_a_property_type_the_graph_already_has(self) -> None:
        """PROV-O's own type for it: declaring it an annotation too would leave OWL 2 DL."""
        graph = Graph()
        graph.add((PROV.wasDerivedFrom, RDF.type, OWL.ObjectProperty))
        stamp_derivation(graph, A, [A_V1])
        assert set(graph.objects(PROV.wasDerivedFrom, RDF.type)) == {OWL.ObjectProperty}

    def test_returns_only_what_it_added(self) -> None:
        graph = Graph()
        graph.add((A, PROV.wasDerivedFrom, A_V1))
        assert stamp_derivation(graph, A, [A_V1, A_V2]) == [A_V2]
        assert set(graph.objects(A, PROV.wasDerivedFrom)) == {A_V1, A_V2}

    def test_no_targets_changes_nothing(self) -> None:
        graph = _header(Graph(bind_namespaces="none"), A)
        before = set(graph)
        stamp_derivation(graph, A, [])
        assert set(graph) == before
        assert "prov" not in dict(graph.namespace_manager.namespaces())


class TestMissingTriples:
    def test_zero_for_the_source_itself(self) -> None:
        graph = _header(Graph(), A, A_V1)
        assert missing_triples(graph, graph) == 0

    def test_counts_what_was_dropped(self) -> None:
        source = _header(Graph(), A, A_V1)
        source.add((EX.C, RDF.type, OWL.Class))
        written = _header(Graph(), A, A_V1)
        assert missing_triples(source, written) == 1

    def test_additions_do_not_hide_a_loss(self) -> None:
        source = _header(Graph(), A, A_V1)
        written = _header(Graph(), A)
        written.add((EX.D, RDF.type, OWL.Class))
        assert missing_triples(source, written) == 1

    def test_counts_dropped_blank_node_triples(self) -> None:
        """A count of named subjects would miss these."""
        source = Graph()
        node = BNode()
        source.add((EX.C, RDF.type, OWL.Class))
        source.add((node, RDF.type, OWL.AllDisjointClasses))
        written = Graph()
        written.add((EX.C, RDF.type, OWL.Class))
        assert missing_triples(source, written) == 1


class TestStampExtract:
    def test_keeps_the_iri_and_every_other_annotation(self) -> None:
        source = _header(Graph(), A, A_V1)
        source.add((A, RDFS.label, Literal("A")))
        extract = Graph()
        for triple in source:
            extract.add(triple)
        stamps = stamp_extract(source, extract)
        assert stamps == [Stamp(A, (A_V1,), (A_V1,), (A_V1,))]
        assert set(extract) == (set(source) - {(A, OWL.versionIRI, A_V1)}) | {
            (A, PROV.wasDerivedFrom, A_V1),
            (PROV.wasDerivedFrom, RDF.type, OWL.AnnotationProperty),
        }

    def test_each_header_is_stamped_for_itself(self) -> None:
        source = _header(_header(Graph(), A, A_V1), B)
        extract = Graph()
        for triple in source:
            extract.add(triple)
        stamps = stamp_extract(source, extract)
        assert stamps == [Stamp(A, (A_V1,), (A_V1,), (A_V1,)), Stamp(B, (), (B,), (B,))]

    def test_an_extract_with_no_header_gets_no_stamp(self) -> None:
        source = Graph()
        source.add((EX.C, RDF.type, OWL.Class))
        extract = Graph()
        assert stamp_extract(source, extract) == []
        assert len(extract) == 0
