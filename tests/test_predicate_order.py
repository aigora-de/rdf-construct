"""Tests for predicate ordering functionality."""

import pytest
from rdflib import Graph, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL

from rdf_construct.core.predicate_order import (
    PredicateOrderSpec,
    PredicateOrderConfig,
    classify_subject,
    expand_curie,
    order_predicates,
)

EX = Namespace("http://example.org/")
IES = Namespace("http://example.org/ies/")


class TestPredicateOrderSpec:
    """Tests for PredicateOrderSpec dataclass."""

    def test_from_dict_empty(self):
        """Empty dict creates empty spec."""
        spec = PredicateOrderSpec.from_dict({})
        assert spec.first == []
        assert spec.last == []

    def test_from_dict_none(self):
        """None creates empty spec."""
        spec = PredicateOrderSpec.from_dict(None)
        assert spec.first == []
        assert spec.last == []

    def test_from_dict_with_values(self):
        """Dict with values populates spec."""
        spec = PredicateOrderSpec.from_dict({
            "first": ["rdfs:label", "rdfs:comment"],
            "last": ["rdfs:subClassOf"],
        })
        assert spec.first == ["rdfs:label", "rdfs:comment"]
        assert spec.last == ["rdfs:subClassOf"]


class TestPredicateOrderConfig:
    """Tests for PredicateOrderConfig dataclass."""

    def test_from_dict_empty(self):
        """Empty dict creates config with empty specs."""
        config = PredicateOrderConfig.from_dict({})
        assert config.classes.first == []
        assert config.properties.first == []

    def test_from_dict_with_values(self):
        """Dict with values populates config."""
        config = PredicateOrderConfig.from_dict({
            "classes": {
                "first": ["rdfs:label"],
                "last": ["rdfs:subClassOf"],
            },
            "properties": {
                "first": ["rdfs:domain", "rdfs:range"],
            },
        })
        assert config.classes.first == ["rdfs:label"]
        assert config.classes.last == ["rdfs:subClassOf"]
        assert config.properties.first == ["rdfs:domain", "rdfs:range"]
        assert config.properties.last == []

    def test_get_spec_for_type_class(self):
        """get_spec_for_type returns class spec."""
        config = PredicateOrderConfig.from_dict({
            "classes": {"first": ["rdfs:label"]},
            "default": {"first": ["rdfs:comment"]},
        })
        spec = config.get_spec_for_type("class")
        assert spec.first == ["rdfs:label"]

    def test_get_spec_for_type_falls_back_to_default(self):
        """get_spec_for_type falls back to default when type spec empty."""
        config = PredicateOrderConfig.from_dict({
            "classes": {},
            "default": {"first": ["rdfs:comment"]},
        })
        spec = config.get_spec_for_type("class")
        assert spec.first == ["rdfs:comment"]


class TestClassifySubject:
    """Tests for subject classification."""

    def test_classify_class(self):
        """owl:Class is classified as 'class'."""
        g = Graph()
        g.bind("ex", EX)
        g.add((EX.MyClass, RDF.type, OWL.Class))

        assert classify_subject(g, EX.MyClass) == "class"

    def test_classify_rdfs_class(self):
        """rdfs:Class is classified as 'class'."""
        g = Graph()
        g.bind("ex", EX)
        g.add((EX.MyClass, RDF.type, RDFS.Class))

        assert classify_subject(g, EX.MyClass) == "class"

    def test_classify_object_property(self):
        """owl:ObjectProperty is classified as 'property'."""
        g = Graph()
        g.bind("ex", EX)
        g.add((EX.hasPart, RDF.type, OWL.ObjectProperty))

        assert classify_subject(g, EX.hasPart) == "property"

    def test_classify_datatype_property(self):
        """owl:DatatypeProperty is classified as 'property'."""
        g = Graph()
        g.bind("ex", EX)
        g.add((EX.hasName, RDF.type, OWL.DatatypeProperty))

        assert classify_subject(g, EX.hasName) == "property"

    def test_classify_individual(self):
        """Non-class, non-property is classified as 'individual'."""
        g = Graph()
        g.bind("ex", EX)
        g.add((EX.instance1, RDF.type, EX.MyClass))

        assert classify_subject(g, EX.instance1) == "individual"


class TestExpandCurie:
    """Tests for CURIE expansion."""

    def test_expand_known_prefix(self):
        """Known prefix expands correctly."""
        g = Graph()
        g.bind("rdfs", RDFS)

        uri = expand_curie(g, "rdfs:label")
        assert uri == RDFS.label

    def test_expand_unknown_prefix(self):
        """Unknown prefix returns None."""
        g = Graph()

        uri = expand_curie(g, "unknown:foo")
        assert uri is None

    def test_expand_no_colon(self):
        """String without colon returns None."""
        g = Graph()

        uri = expand_curie(g, "nocolon")
        assert uri is None


class TestOrderPredicates:
    """Tests for predicate ordering."""

    def setup_method(self):
        """Create graph with namespaces."""
        self.g = Graph()
        self.g.bind("rdfs", RDFS)
        self.g.bind("owl", OWL)
        self.g.bind("ex", EX)
        self.g.bind("ies", IES)

    def format_term(self, term):
        """Simple format function for testing."""
        try:
            return self.g.namespace_manager.normalizeUri(term)
        except Exception:
            return str(term)

    def test_first_predicates_come_first(self):
        """'first' predicates appear in order before others."""
        spec = PredicateOrderSpec(
            first=["rdfs:label", "rdfs:comment"],
            last=[],
        )
        predicates = [RDFS.comment, EX.foo, RDFS.label, IES.bar]

        ordered = order_predicates(self.g, predicates, spec, self.format_term)

        # First two should be label, comment (in that order)
        assert ordered[0] == RDFS.label
        assert ordered[1] == RDFS.comment

    def test_last_predicates_come_last(self):
        """'last' predicates appear at the end in order."""
        spec = PredicateOrderSpec(
            first=[],
            last=["rdfs:subClassOf"],
        )
        predicates = [RDFS.subClassOf, EX.foo, RDFS.label]

        ordered = order_predicates(self.g, predicates, spec, self.format_term)

        # subClassOf should be last
        assert ordered[-1] == RDFS.subClassOf

    def test_middle_sorted_alphabetically(self):
        """Middle predicates are sorted alphabetically by QName."""
        spec = PredicateOrderSpec(
            first=["rdfs:label"],
            last=["rdfs:subClassOf"],
        )
        # ex:foo should come before ies:bar alphabetically
        predicates = [IES.bar, RDFS.subClassOf, EX.foo, RDFS.label]

        ordered = order_predicates(self.g, predicates, spec, self.format_term)

        # Expected: label, foo, bar, subClassOf
        # (ex: before ies: alphabetically)
        assert ordered[0] == RDFS.label
        assert ordered[-1] == RDFS.subClassOf
        # Middle predicates should be alphabetically ordered
        middle = ordered[1:-1]
        assert middle == sorted(middle, key=self.format_term)

    def test_missing_first_predicate_skipped(self):
        """'first' predicates not in input are skipped."""
        spec = PredicateOrderSpec(
            first=["rdfs:label", "rdfs:comment"],
            last=[],
        )
        # Only label is present, not comment
        predicates = [EX.foo, RDFS.label]

        ordered = order_predicates(self.g, predicates, spec, self.format_term)

        assert ordered[0] == RDFS.label
        assert RDFS.comment not in ordered

    def test_full_ordering_example(self):
        """Full example matching the class serialisation use case."""
        spec = PredicateOrderSpec(
            first=["rdfs:label", "rdfs:comment"],
            last=["rdfs:subClassOf"],
        )
        predicates = [
            RDFS.subClassOf,
            IES.powertype,
            RDFS.comment,
            RDFS.label,
            EX.customProp,
        ]

        ordered = order_predicates(self.g, predicates, spec, self.format_term)

        # Expected order:
        # 1. rdfs:label (first)
        # 2. rdfs:comment (first)
        # 3. ex:customProp (middle, alphabetically)
        # 4. ies:powertype (middle, alphabetically)
        # 5. rdfs:subClassOf (last)
        assert ordered[0] == RDFS.label
        assert ordered[1] == RDFS.comment
        assert ordered[-1] == RDFS.subClassOf

        # Check middle is sorted
        middle = ordered[2:-1]
        assert EX.customProp in middle
        assert IES.powertype in middle


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
