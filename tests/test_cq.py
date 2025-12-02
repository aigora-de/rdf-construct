"""Unit tests for the competency question testing module."""

import pytest
from pathlib import Path
from io import StringIO

from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal

from rdf_construct.cq.expectations import (
    BooleanExpectation,
    HasResultsExpectation,
    NoResultsExpectation,
    CountExpectation,
    ValuesExpectation,
    ContainsExpectation,
    parse_expectation,
)
from rdf_construct.cq.loader import (
    CQTest,
    CQTestSuite,
    load_test_suite,
    build_query_with_prefixes,
)
from rdf_construct.cq.runner import (
    CQTestRunner,
    CQStatus,
)
from rdf_construct.cq.formatters import format_text, format_json, format_junit


# Test fixtures
EX = Namespace("http://example.org/test#")


@pytest.fixture
def simple_graph():
    """Create a simple test graph."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)

    # Define classes
    g.add((EX.Animal, RDF.type, OWL.Class))
    g.add((EX.Dog, RDF.type, OWL.Class))
    g.add((EX.Dog, RDFS.subClassOf, EX.Animal))
    g.add((EX.Cat, RDF.type, OWL.Class))
    g.add((EX.Cat, RDFS.subClassOf, EX.Animal))

    # Add instances
    g.add((EX.Fido, RDF.type, EX.Dog))
    g.add((EX.Fido, RDFS.label, Literal("Fido")))
    g.add((EX.Rex, RDF.type, EX.Dog))
    g.add((EX.Rex, RDFS.label, Literal("Rex")))
    g.add((EX.Mittens, RDF.type, EX.Cat))

    return g


@pytest.fixture
def prefixes():
    """Standard prefixes for tests."""
    return {
        "ex": "http://example.org/test#",
        "owl": "http://www.w3.org/2002/07/owl#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    }


# ============================================
# Expectation Tests
# ============================================

class TestBooleanExpectation:
    """Tests for ASK query expectations."""

    def test_true_matches_true(self, simple_graph):
        """ASK query returning true should match expect: true."""
        result = simple_graph.query("ASK { ?x a <http://www.w3.org/2002/07/owl#Class> }")
        exp = BooleanExpectation(True)
        check = exp.check(result)
        assert check.passed

    def test_true_fails_false(self, simple_graph):
        """ASK query returning true should fail expect: false."""
        result = simple_graph.query("ASK { ?x a <http://www.w3.org/2002/07/owl#Class> }")
        exp = BooleanExpectation(False)
        check = exp.check(result)
        assert not check.passed

    def test_false_matches_false(self, simple_graph):
        """ASK query returning false should match expect: false."""
        result = simple_graph.query("ASK { ?x a <http://example.org/test#NonExistent> }")
        exp = BooleanExpectation(False)
        check = exp.check(result)
        assert check.passed


class TestHasResultsExpectation:
    """Tests for has_results expectation."""

    def test_has_results_passes(self, simple_graph):
        """Query with results should pass has_results."""
        result = simple_graph.query(
            "SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }"
        )
        exp = HasResultsExpectation()
        check = exp.check(result)
        assert check.passed
        assert "2" in check.actual  # Two dogs

    def test_has_results_fails_empty(self, simple_graph):
        """Query with no results should fail has_results."""
        result = simple_graph.query(
            "SELECT ?x WHERE { ?x a <http://example.org/test#NonExistent> }"
        )
        exp = HasResultsExpectation()
        check = exp.check(result)
        assert not check.passed


class TestNoResultsExpectation:
    """Tests for no_results expectation."""

    def test_no_results_passes(self, simple_graph):
        """Empty query should pass no_results."""
        result = simple_graph.query(
            "SELECT ?x WHERE { ?x a <http://example.org/test#NonExistent> }"
        )
        exp = NoResultsExpectation()
        check = exp.check(result)
        assert check.passed

    def test_no_results_fails(self, simple_graph):
        """Query with results should fail no_results."""
        result = simple_graph.query(
            "SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }"
        )
        exp = NoResultsExpectation()
        check = exp.check(result)
        assert not check.passed


class TestCountExpectation:
    """Tests for count expectations."""

    def test_exact_count_passes(self, simple_graph):
        """Exact count should pass when matched."""
        result = simple_graph.query(
            "SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }"
        )
        exp = CountExpectation(exact=2)
        check = exp.check(result)
        assert check.passed

    def test_exact_count_fails(self, simple_graph):
        """Exact count should fail when not matched."""
        result = simple_graph.query(
            "SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }"
        )
        exp = CountExpectation(exact=3)
        check = exp.check(result)
        assert not check.passed

    def test_min_count_passes(self, simple_graph):
        """Min count should pass when >= min."""
        result = simple_graph.query(
            "SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }"
        )
        exp = CountExpectation(min_count=1)
        check = exp.check(result)
        assert check.passed

    def test_min_count_fails(self, simple_graph):
        """Min count should fail when < min."""
        result = simple_graph.query(
            "SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }"
        )
        exp = CountExpectation(min_count=5)
        check = exp.check(result)
        assert not check.passed

    def test_max_count_passes(self, simple_graph):
        """Max count should pass when <= max."""
        result = simple_graph.query(
            "SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }"
        )
        exp = CountExpectation(max_count=5)
        check = exp.check(result)
        assert check.passed

    def test_range_count(self, simple_graph):
        """Range count should work with both min and max."""
        result = simple_graph.query(
            "SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }"
        )
        exp = CountExpectation(min_count=1, max_count=5)
        check = exp.check(result)
        assert check.passed


class TestContainsExpectation:
    """Tests for contains expectation (subset matching)."""

    def test_contains_single_binding(self, simple_graph):
        """Should find a single expected binding."""
        result = simple_graph.query(
            "SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }"
        )
        exp = ContainsExpectation(expected_bindings=[
            {"x": "http://example.org/test#Fido"}
        ])
        check = exp.check(result)
        assert check.passed

    def test_contains_missing_binding(self, simple_graph):
        """Should fail when expected binding is missing."""
        result = simple_graph.query(
            "SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }"
        )
        exp = ContainsExpectation(expected_bindings=[
            {"x": "http://example.org/test#NonExistent"}
        ])
        check = exp.check(result)
        assert not check.passed


class TestParseExpectation:
    """Tests for expectation parsing from YAML values."""

    def test_parse_boolean_true(self):
        """Should parse boolean True."""
        exp = parse_expectation(True)
        assert isinstance(exp, BooleanExpectation)
        assert exp.expected is True

    def test_parse_boolean_false(self):
        """Should parse boolean False."""
        exp = parse_expectation(False)
        assert isinstance(exp, BooleanExpectation)
        assert exp.expected is False

    def test_parse_has_results_string(self):
        """Should parse 'has_results' string."""
        exp = parse_expectation("has_results")
        assert isinstance(exp, HasResultsExpectation)

    def test_parse_no_results_string(self):
        """Should parse 'no_results' string."""
        exp = parse_expectation("no_results")
        assert isinstance(exp, NoResultsExpectation)

    def test_parse_count_dict(self):
        """Should parse count dict."""
        exp = parse_expectation({"count": 5})
        assert isinstance(exp, CountExpectation)
        assert exp.exact == 5

    def test_parse_min_results_dict(self):
        """Should parse min_results dict."""
        exp = parse_expectation({"min_results": 1})
        assert isinstance(exp, CountExpectation)
        assert exp.min_count == 1

    def test_parse_results_dict(self):
        """Should parse results dict."""
        exp = parse_expectation({"results": [{"x": "value"}]})
        assert isinstance(exp, ValuesExpectation)

    def test_parse_contains_dict(self):
        """Should parse contains dict."""
        exp = parse_expectation({"contains": [{"x": "value"}]})
        assert isinstance(exp, ContainsExpectation)

    def test_parse_unknown_raises(self):
        """Should raise for unknown format."""
        with pytest.raises(ValueError):
            parse_expectation("unknown_string")


# ============================================
# Loader Tests
# ============================================

class TestBuildQueryWithPrefixes:
    """Tests for prefix injection."""

    def test_adds_missing_prefixes(self):
        """Should add missing prefix declarations."""
        query = "SELECT ?x WHERE { ?x a ex:Dog }"
        prefixes = {"ex": "http://example.org/test#"}
        result = build_query_with_prefixes(query, prefixes)
        assert "PREFIX ex:" in result
        assert query in result

    def test_preserves_existing_prefixes(self):
        """Should not duplicate existing prefixes."""
        query = "PREFIX ex: <http://example.org/test#>\nSELECT ?x WHERE { ?x a ex:Dog }"
        prefixes = {"ex": "http://example.org/test#"}
        result = build_query_with_prefixes(query, prefixes)
        # Should only have one PREFIX ex: declaration
        assert result.count("PREFIX ex:") == 1


# ============================================
# Runner Tests
# ============================================

class TestCQTestRunner:
    """Tests for the test runner."""

    def test_run_passing_ask_test(self, simple_graph, prefixes):
        """Should correctly run a passing ASK test."""
        test = CQTest(
            id="test-001",
            name="Animal class exists",
            query="ASK { ex:Animal a owl:Class }",
            expectation=BooleanExpectation(True),
        )
        suite = CQTestSuite(prefixes=prefixes, questions=[test])

        runner = CQTestRunner()
        results = runner.run(simple_graph, suite)

        assert results.total_count == 1
        assert results.passed_count == 1
        assert results.all_passed

    def test_run_failing_test(self, simple_graph, prefixes):
        """Should correctly run a failing test."""
        test = CQTest(
            id="test-002",
            name="NonExistent class exists",
            query="ASK { ex:NonExistent a owl:Class }",
            expectation=BooleanExpectation(True),
        )
        suite = CQTestSuite(prefixes=prefixes, questions=[test])

        runner = CQTestRunner()
        results = runner.run(simple_graph, suite)

        assert results.total_count == 1
        assert results.failed_count == 1
        assert not results.all_passed

    def test_run_skipped_test(self, simple_graph, prefixes):
        """Should correctly handle skipped tests."""
        test = CQTest(
            id="test-003",
            name="Skipped test",
            query="ASK { ?x ?y ?z }",
            expectation=BooleanExpectation(True),
            skip=True,
            skip_reason="Test disabled",
        )
        suite = CQTestSuite(prefixes=prefixes, questions=[test])

        runner = CQTestRunner()
        results = runner.run(simple_graph, suite)

        assert results.total_count == 1
        assert results.skipped_count == 1
        assert results.all_passed  # Skips don't count as failures

    def test_run_with_syntax_error(self, simple_graph, prefixes):
        """Should handle SPARQL syntax errors gracefully."""
        test = CQTest(
            id="test-004",
            name="Invalid query",
            query="SELECT WHERE { broken syntax }",
            expectation=BooleanExpectation(True),
        )
        suite = CQTestSuite(prefixes=prefixes, questions=[test])

        runner = CQTestRunner()
        results = runner.run(simple_graph, suite)

        assert results.total_count == 1
        assert results.error_count == 1

    def test_fail_fast_stops_early(self, simple_graph, prefixes):
        """Should stop on first failure when fail_fast is True."""
        tests = [
            CQTest(
                id="test-001",
                name="Failing test",
                query="ASK { ex:NonExistent a owl:Class }",
                expectation=BooleanExpectation(True),
            ),
            CQTest(
                id="test-002",
                name="Would pass",
                query="ASK { ex:Animal a owl:Class }",
                expectation=BooleanExpectation(True),
            ),
        ]
        suite = CQTestSuite(prefixes=prefixes, questions=tests)

        runner = CQTestRunner(fail_fast=True)
        results = runner.run(simple_graph, suite)

        # Only first test should have run
        assert len(results.results) == 1


# ============================================
# Formatter Tests
# ============================================

class TestTextFormatter:
    """Tests for text output formatting."""

    def test_format_passing_results(self, simple_graph, prefixes):
        """Should format passing results correctly."""
        test = CQTest(
            id="test-001",
            name="Animal class exists",
            query="ASK { ex:Animal a owl:Class }",
            expectation=BooleanExpectation(True),
        )
        suite = CQTestSuite(prefixes=prefixes, questions=[test])

        runner = CQTestRunner()
        results = runner.run(simple_graph, suite)

        output = format_text(results, use_color=False)

        assert "PASS" in output
        assert "test-001" in output
        assert "1 passed" in output


class TestJsonFormatter:
    """Tests for JSON output formatting."""

    def test_format_json_structure(self, simple_graph, prefixes):
        """Should produce valid JSON with expected structure."""
        import json

        test = CQTest(
            id="test-001",
            name="Animal class exists",
            query="ASK { ex:Animal a owl:Class }",
            expectation=BooleanExpectation(True),
        )
        suite = CQTestSuite(prefixes=prefixes, questions=[test])

        runner = CQTestRunner()
        results = runner.run(simple_graph, suite)

        output = format_json(results)
        data = json.loads(output)

        assert "questions" in data
        assert "summary" in data
        assert data["summary"]["total"] == 1
        assert data["summary"]["passed"] == 1


class TestJunitFormatter:
    """Tests for JUnit XML output formatting."""

    def test_format_junit_structure(self, simple_graph, prefixes):
        """Should produce valid JUnit XML."""
        import xml.etree.ElementTree as ET

        test = CQTest(
            id="test-001",
            name="Animal class exists",
            query="ASK { ex:Animal a owl:Class }",
            expectation=BooleanExpectation(True),
        )
        suite = CQTestSuite(prefixes=prefixes, questions=[test])

        runner = CQTestRunner()
        results = runner.run(simple_graph, suite)

        output = format_junit(results)

        # Should be valid XML
        root = ET.fromstring(output)
        assert root.tag == "testsuite"
        assert root.get("tests") == "1"
        assert root.get("failures") == "0"


# ============================================
# Tag Filtering Tests
# ============================================

class TestTagFiltering:
    """Tests for tag-based test filtering."""

    def test_filter_include_tags(self, prefixes):
        """Should include only tests with specified tags."""
        tests = [
            CQTest(id="t1", name="Test 1", query="ASK {}",
                   expectation=BooleanExpectation(True), tags=["core"]),
            CQTest(id="t2", name="Test 2", query="ASK {}",
                   expectation=BooleanExpectation(True), tags=["extra"]),
        ]
        suite = CQTestSuite(prefixes=prefixes, questions=tests)

        filtered = suite.filter_by_tags(include_tags={"core"})

        assert len(filtered.questions) == 1
        assert filtered.questions[0].id == "t1"

    def test_filter_exclude_tags(self, prefixes):
        """Should exclude tests with specified tags."""
        tests = [
            CQTest(id="t1", name="Test 1", query="ASK {}",
                   expectation=BooleanExpectation(True), tags=["core"]),
            CQTest(id="t2", name="Test 2", query="ASK {}",
                   expectation=BooleanExpectation(True), tags=["slow"]),
        ]
        suite = CQTestSuite(prefixes=prefixes, questions=tests)

        filtered = suite.filter_by_tags(exclude_tags={"slow"})

        assert len(filtered.questions) == 1
        assert filtered.questions[0].id == "t1"
