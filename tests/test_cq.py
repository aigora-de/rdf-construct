"""Unit tests for the competency question testing module."""

import re

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
    query_form_refusal,
)
from rdf_construct.cq.loader import (
    CQTest,
    CQTestSuite,
    load_test_suite,
    build_query_with_prefixes,
)
from rdf_construct.cq.runner import (
    CQTestResult,
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
        result = simple_graph.query("SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }")
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
        result = simple_graph.query("SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }")
        exp = NoResultsExpectation()
        check = exp.check(result)
        assert not check.passed


class TestCountExpectation:
    """Tests for count expectations."""

    def test_exact_count_passes(self, simple_graph):
        """Exact count should pass when matched."""
        result = simple_graph.query("SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }")
        exp = CountExpectation(exact=2)
        check = exp.check(result)
        assert check.passed

    def test_exact_count_fails(self, simple_graph):
        """Exact count should fail when not matched."""
        result = simple_graph.query("SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }")
        exp = CountExpectation(exact=3)
        check = exp.check(result)
        assert not check.passed

    def test_min_count_passes(self, simple_graph):
        """Min count should pass when >= min."""
        result = simple_graph.query("SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }")
        exp = CountExpectation(min_count=1)
        check = exp.check(result)
        assert check.passed

    def test_min_count_fails(self, simple_graph):
        """Min count should fail when < min."""
        result = simple_graph.query("SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }")
        exp = CountExpectation(min_count=5)
        check = exp.check(result)
        assert not check.passed

    def test_max_count_passes(self, simple_graph):
        """Max count should pass when <= max."""
        result = simple_graph.query("SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }")
        exp = CountExpectation(max_count=5)
        check = exp.check(result)
        assert check.passed

    def test_range_count(self, simple_graph):
        """Range count should work with both min and max."""
        result = simple_graph.query("SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }")
        exp = CountExpectation(min_count=1, max_count=5)
        check = exp.check(result)
        assert check.passed


class TestContainsExpectation:
    """Tests for contains expectation (subset matching)."""

    def test_contains_single_binding(self, simple_graph):
        """Should find a single expected binding."""
        result = simple_graph.query("SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }")
        exp = ContainsExpectation(expected_bindings=[{"x": "http://example.org/test#Fido"}])
        check = exp.check(result)
        assert check.passed

    def test_contains_missing_binding(self, simple_graph):
        """Should fail when expected binding is missing."""
        result = simple_graph.query("SELECT ?x WHERE { ?x a <http://example.org/test#Dog> }")
        exp = ContainsExpectation(expected_bindings=[{"x": "http://example.org/test#NonExistent"}])
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

        # Only the first test ran; the second is recorded as not run, so the total is the
        # selected suite (#137, changed deliberately from len(results.results) == 1)
        assert len(results.results) == 2
        assert results.results[0].status == CQStatus.FAIL
        assert results.results[1].status == CQStatus.NOT_RUN
        assert results.total_count == 2
        assert results.not_run_count == 1
        assert results.stopped_after == "test-001"


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
            CQTest(
                id="t1",
                name="Test 1",
                query="ASK {}",
                expectation=BooleanExpectation(True),
                tags=["core"],
            ),
            CQTest(
                id="t2",
                name="Test 2",
                query="ASK {}",
                expectation=BooleanExpectation(True),
                tags=["extra"],
            ),
        ]
        suite = CQTestSuite(prefixes=prefixes, questions=tests)

        filtered = suite.filter_by_tags(include_tags={"core"})

        assert len(filtered.questions) == 1
        assert filtered.questions[0].id == "t1"

    def test_filter_exclude_tags(self, prefixes):
        """Should exclude tests with specified tags."""
        tests = [
            CQTest(
                id="t1",
                name="Test 1",
                query="ASK {}",
                expectation=BooleanExpectation(True),
                tags=["core"],
            ),
            CQTest(
                id="t2",
                name="Test 2",
                query="ASK {}",
                expectation=BooleanExpectation(True),
                tags=["slow"],
            ),
        ]
        suite = CQTestSuite(prefixes=prefixes, questions=tests)

        filtered = suite.filter_by_tags(exclude_tags={"slow"})

        assert len(filtered.questions) == 1
        assert filtered.questions[0].id == "t1"


# ============================================
# Query-form refusal (#134)
# ============================================


def _ask_refusal(question_id: str, key: str) -> str:
    """The refusal message for an ASK question checked with a non-boolean expectation."""
    return (
        f"{question_id}: an ASK query answers true or false, so it cannot be checked with "
        f"'{key}'; an ASK takes expect: true or expect: false"
    )


class TestQueryFormRefusal:
    """An ASK paired with a count-based expectation is that question's ERROR (#134)."""

    TRUE_ASK = "ASK { ex:Animal a owl:Class }"
    FALSE_ASK = "ASK { ex:Unicorn a owl:Class }"

    def _run(self, graph, prefixes, questions):
        suite = CQTestSuite(prefixes=prefixes, questions=questions)
        return CQTestRunner().run(graph, suite)

    def test_issue_reproducer_is_all_errors(self, simple_graph, prefixes):
        """A1-A5 of #134's reproducer are each refused, whatever the ASK answers."""
        cases = [
            ("A1", self.TRUE_ASK, "has_results", "has_results"),
            ("A2", self.FALSE_ASK, "has_results", "has_results"),
            ("A3", self.FALSE_ASK, "no_results", "no_results"),
            ("A4", self.TRUE_ASK, {"count": 1}, "count"),
            ("A5", self.FALSE_ASK, {"count": 1}, "count"),
        ]
        questions = [
            CQTest(id=qid, name=qid, query=query, expectation=parse_expectation(expect))
            for qid, query, expect, _ in cases
        ]
        results = self._run(simple_graph, prefixes, questions)

        assert results.total_count == 5
        assert [r.status for r in results.results] == [CQStatus.ERROR] * 5
        assert [r.error for r in results.results] == [
            _ask_refusal(qid, key) for qid, _, _, key in cases
        ]
        assert all(r.error_type == "InvalidExpectation" for r in results.results)
        assert results.has_errors

    @pytest.mark.parametrize(
        "expect, key",
        [
            ({"min_results": 1}, "min_results"),
            ({"max_results": 0}, "max_results"),
            ({"min_results": 1, "max_results": 2}, "min_results and max_results"),
            ({"results": []}, "results"),
            ({"results": [{"x": "y"}]}, "results"),
            ({"contains": [{"x": "y"}]}, "contains"),
        ],
    )
    @pytest.mark.parametrize("query", [TRUE_ASK, FALSE_ASK])
    def test_every_non_boolean_expectation_is_refused(
        self, simple_graph, prefixes, query, expect, key
    ):
        """min/max counts, values and contains are refused the same way on an ASK."""
        test = CQTest(id="Q", name="Q", query=query, expectation=parse_expectation(expect))
        (result,) = self._run(simple_graph, prefixes, [test]).results

        assert result.status == CQStatus.ERROR
        assert result.error == _ask_refusal("Q", key)
        assert result.error_type == "InvalidExpectation"

    def test_mixed_suite_reports_every_question(self, simple_graph, prefixes):
        """One bad ASK question is the only ERROR; the questions after it still run."""
        questions = [
            CQTest(
                id="ok-ask",
                name="ok",
                query=self.TRUE_ASK,
                expectation=BooleanExpectation(True),
            ),
            CQTest(
                id="bad-ask",
                name="bad",
                query=self.FALSE_ASK,
                expectation=HasResultsExpectation(),
            ),
            CQTest(
                id="ok-select",
                name="ok",
                query="SELECT ?c WHERE { ?c rdfs:subClassOf ex:Animal }",
                expectation=CountExpectation(exact=2),
            ),
            CQTest(
                id="failing-select",
                name="fails",
                query="SELECT ?c WHERE { ?c a ex:Nope }",
                expectation=HasResultsExpectation(),
            ),
        ]
        results = self._run(simple_graph, prefixes, questions)

        assert [(r.test.id, r.status) for r in results.results] == [
            ("ok-ask", CQStatus.PASS),
            ("bad-ask", CQStatus.ERROR),
            ("ok-select", CQStatus.PASS),
            ("failing-select", CQStatus.FAIL),
        ]

    @pytest.mark.parametrize(
        "query, expected, status",
        [
            (TRUE_ASK, True, CQStatus.PASS),
            (TRUE_ASK, False, CQStatus.FAIL),
            (FALSE_ASK, True, CQStatus.FAIL),
            (FALSE_ASK, False, CQStatus.PASS),
        ],
    )
    def test_boolean_on_ask_unchanged(self, simple_graph, prefixes, query, expected, status):
        """expect: true/false on an ASK is still decided by the ASK's answer."""
        test = CQTest(id="B", name="B", query=query, expectation=BooleanExpectation(expected))
        (result,) = self._run(simple_graph, prefixes, [test]).results

        assert result.status == status
        assert result.error is None

    def test_query_error_keeps_its_type(self, simple_graph, prefixes):
        """A query that cannot be run is still a QueryError, not a refused expectation."""
        test = CQTest(
            id="broken",
            name="broken",
            query="SELECT WHERE {",
            expectation=HasResultsExpectation(),
        )
        (result,) = self._run(simple_graph, prefixes, [test]).results

        assert result.status == CQStatus.ERROR
        assert result.error_type == "QueryError"

    def test_junit_error_element(self, simple_graph, prefixes):
        """The refused question is a JUnit <error> typed InvalidExpectation."""
        import xml.etree.ElementTree as ET

        test = CQTest(id="A2", name="A2", query=self.FALSE_ASK, expectation=HasResultsExpectation())
        results = self._run(simple_graph, prefixes, [test])
        root = ET.fromstring(format_junit(results))

        assert root.get("errors") == "1"
        assert root.get("failures") == "0"
        (error,) = root.iter("error")
        assert error.get("type") == "InvalidExpectation"
        assert error.get("message") == _ask_refusal("A2", "has_results")

    def test_refusal_accepts_declared_forms(self):
        """The refusal is None for every form an expectation declares."""
        for form in ("SELECT", "CONSTRUCT", "DESCRIBE"):
            assert query_form_refusal("Q", HasResultsExpectation(), form) is None
        for form in ("ASK", "SELECT", "CONSTRUCT", "DESCRIBE"):
            assert query_form_refusal("Q", BooleanExpectation(True), form) is None
        assert query_form_refusal("Q", ValuesExpectation(), "SELECT") is None
        assert query_form_refusal("Q", ContainsExpectation(), "SELECT") is None

    @pytest.mark.parametrize(
        "query, form",
        [
            ("CONSTRUCT { ?c a owl:Class } WHERE { ?c a owl:Class }", "CONSTRUCT"),
            ("DESCRIBE ex:Animal", "DESCRIBE"),
        ],
    )
    @pytest.mark.parametrize(
        "expect, key",
        [
            ({"results": []}, "results"),
            ({"contains": [{"c": "http://example.org/test#Animal"}]}, "contains"),
        ],
    )
    def test_bindings_refused_on_graph_forms(
        self, simple_graph, prefixes, query, form, expect, key
    ):
        """results/contains on a CONSTRUCT or DESCRIBE are refused, not a ValueError."""
        test = CQTest(id="G", name="G", query=query, expectation=parse_expectation(expect))
        (result,) = self._run(simple_graph, prefixes, [test]).results

        assert result.status == CQStatus.ERROR
        assert result.error == (
            f"G: a {form} query returns triples, not variable bindings, so it cannot be "
            f"checked with '{key}'"
        )
        assert result.error_type == "InvalidExpectation"

    @pytest.mark.parametrize(
        "query",
        ["CONSTRUCT { ?c a owl:Class } WHERE { ?c a owl:Class }", "DESCRIBE ex:Animal"],
    )
    def test_counts_still_run_on_graph_forms(self, simple_graph, prefixes, query):
        """CONSTRUCT and DESCRIBE still count triples."""
        test = CQTest(id="G", name="G", query=query, expectation=HasResultsExpectation())
        (result,) = self._run(simple_graph, prefixes, [test]).results

        assert result.status == CQStatus.PASS

    def test_cli_reports_every_question_and_exits_2(self):
        """At the CLI, the refused question is reported beside the others and the run exits 2."""
        from click.testing import CliRunner

        from rdf_construct.cli import cli

        repo = Path(__file__).parent.parent
        result = CliRunner().invoke(
            cli,
            [
                "cq-test",
                str(repo / "examples" / "animal_ontology.ttl"),
                str(repo / "tests" / "fixtures" / "smoke" / "cq_ask_count.yml"),
            ],
        )

        assert result.exit_code == 2
        assert "[PASS] cq-ask-ok:" in result.output
        assert "[ERROR] cq-ask-count:" in result.output
        assert _ask_refusal("cq-ask-count", "has_results") in result.output
        assert "[PASS] cq-select-ok:" in result.output


class TestBooleanExpectationMessage:
    """BooleanExpectation's message does not claim every query is an ASK (#134)."""

    def test_select_message_names_no_query_form(self, simple_graph, prefixes):
        """On a SELECT, true means at least one row, and the message says what was answered."""
        test = CQTest(
            id="S",
            name="S",
            query="SELECT ?c WHERE { ?c a ex:Nope }",
            expectation=BooleanExpectation(True),
        )
        suite = CQTestSuite(prefixes=prefixes, questions=[test])
        (result,) = CQTestRunner().run(simple_graph, suite).results

        assert result.status == CQStatus.FAIL
        assert result.check_result.message == "Query answered False, expected True"

    def test_passing_message(self, simple_graph):
        """A met boolean expectation says what the query answered."""
        result = simple_graph.query("ASK { ?x a <http://www.w3.org/2002/07/owl#Class> }")
        check = BooleanExpectation(True).check(result)

        assert check.message == "Query answered True, as expected"


# ============================================
# --fail-fast reports the selected suite (#137)
# ============================================

FF_YML = """\
prefixes:
  ex: "http://example.org/ont#"
  owl: "http://www.w3.org/2002/07/owl#"
questions:
  - id: t1
    query: "ASK { ex:Animal a owl:Class }"
    expect: true
  - id: t2-fails
    query: "ASK { ex:Unicorn a owl:Class }"
    expect: true
  - id: t3
    query: "ASK { ex:Dog a owl:Class }"
    expect: true
    tags: [later]
  - id: t4
    query: "ASK { ex:Dog a owl:Class }"
    expect: true
"""

FF_BASE = """\
@prefix ex: <http://example.org/ont#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:Animal a owl:Class .
ex:Dog a owl:Class .
"""


class TestFailFastReportsTheSelectedSuite:
    """The total is the selected suite; what --fail-fast didn't reach is NOT_RUN (#137)."""

    @pytest.fixture
    def ff(self, tmp_path):
        (tmp_path / "base.ttl").write_text(FF_BASE)
        (tmp_path / "ff.yml").write_text(FF_YML)
        return tmp_path

    def _cli(self, d, yml="ff.yml", *args):
        from click.testing import CliRunner

        from rdf_construct.cli import cli

        return CliRunner().invoke(
            cli, ["cq-test", str(d / "base.ttl"), str(d / yml), "--fail-fast", *args]
        )

    def test_json_counts_every_selected_question(self, ff):
        import json

        result = self._cli(ff, "ff.yml", "--format", "json")
        assert result.exit_code == 1, result.output
        data = json.loads(result.stdout)
        assert data["summary"] == {
            "total": 4,
            "passed": 1,
            "failed": 1,
            "errors": 0,
            "skipped": 0,
            "not_run": 2,
        }
        assert [q["status"] for q in data["questions"]] == ["pass", "fail", "not_run", "not_run"]
        assert data["questions"][2] == {
            "id": "t3",
            "name": "t3",
            "status": "not_run",
            "tags": ["later"],
        }

    def test_junit_emits_each_not_run_question_as_a_skipped_testcase(self, ff):
        import xml.etree.ElementTree as ET

        result = self._cli(ff, "ff.yml", "--format", "junit")
        assert result.exit_code == 1, result.output
        suite = ET.fromstring(result.stdout)
        assert (suite.get("tests"), suite.get("failures"), suite.get("errors")) == ("4", "1", "0")
        assert suite.get("skipped") == "2"
        cases = suite.findall("testcase")
        assert len(cases) == 4
        skipped = [c.find("skipped") for c in cases[2:]]
        assert [s.get("message") for s in skipped] == [
            "not run: --fail-fast stopped after t2-fails"
        ] * 2
        # A consumer deriving passes from the attributes gets the real count
        t, f, e, s = (int(suite.get(k)) for k in ("tests", "failures", "errors", "skipped"))
        assert t - f - e - s == 1

    def test_text_says_how_many_ran_and_where_it_stopped(self, ff):
        result = self._cli(ff)
        assert result.exit_code == 1, result.output
        assert "[NOT RUN] t3: t3" in result.stdout
        assert "[NOT RUN] t4: t4" in result.stdout
        assert "2 of 4 run — stopped by --fail-fast after 't2-fails'" in result.stdout

    def test_a_stop_on_the_last_question_leaves_nothing_not_run(self, ff):
        import json

        yml = FF_YML.replace("ex:Unicorn", "ex:Dog").replace(
            '  - id: t4\n    query: "ASK { ex:Dog a owl:Class }"',
            '  - id: t4\n    query: "ASK { ex:Unicorn a owl:Class }"',
        )
        (ff / "last.yml").write_text(yml)
        text = self._cli(ff, "last.yml")
        assert text.exit_code == 1, text.output
        assert "stopped by --fail-fast" not in text.stdout
        assert "NOT RUN" not in text.stdout
        data = json.loads(self._cli(ff, "last.yml", "-f", "json").stdout)
        assert data["summary"]["total"] == 4 and data["summary"]["not_run"] == 0

    def test_a_refused_question_counts_as_run(self, ff):
        """P19: a refused question is an ERROR; it is run, and stops --fail-fast (#137)."""
        import xml.etree.ElementTree as ET

        yml = FF_YML.replace(
            '  - id: t2-fails\n    query: "ASK { ex:Unicorn a owl:Class }"\n    expect: true',
            '  - id: t2-refused\n    query: "ASK { ex:Dog a owl:Class }"\n    expect: has_results',
        )
        (ff / "ref.yml").write_text(yml)
        result = self._cli(ff, "ref.yml", "-f", "junit")
        assert result.exit_code == 2, result.output
        suite = ET.fromstring(result.stdout)
        assert (suite.get("tests"), suite.get("errors"), suite.get("skipped")) == ("4", "1", "2")
        assert suite.findall("testcase")[1].find("error").get("type") == "InvalidExpectation"
        text = self._cli(ff, "ref.yml")
        assert "2 of 4 run — stopped by --fail-fast after 't2-refused'" in text.stdout

    def test_without_fail_fast_every_question_runs(self, ff):
        from click.testing import CliRunner

        from rdf_construct.cli import cli

        result = CliRunner().invoke(cli, ["cq-test", str(ff / "base.ttl"), str(ff / "ff.yml")])
        assert result.exit_code == 1
        assert "NOT RUN" not in result.stdout
        assert "Results: 3 passed, 1 failed" in result.stdout

    def test_an_author_skip_is_not_a_not_run(self, ff):
        """SKIP is the author's choice and NOT_RUN is --fail-fast's; JUnit counts both."""
        import json
        import xml.etree.ElementTree as ET

        # t1 skipped by its author, t2-fails stops the run, t3 and t4 not run
        yml = FF_YML.replace(
            '    query: "ASK { ex:Animal a owl:Class }"\n    expect: true\n',
            '    query: "ASK { ex:Animal a owl:Class }"\n    expect: true\n'
            '    skip: true\n    skip_reason: "pending"\n',
        )
        (ff / "skip.yml").write_text(yml)
        data = json.loads(self._cli(ff, "skip.yml", "-f", "json").stdout)
        assert [q["status"] for q in data["questions"]] == ["skip", "fail", "not_run", "not_run"]
        assert (data["summary"]["skipped"], data["summary"]["not_run"]) == (1, 2)

        suite = ET.fromstring(self._cli(ff, "skip.yml", "-f", "junit").stdout)
        assert suite.get("skipped") == "3"
        elements = [c.find("skipped") for c in suite.findall("testcase")]
        messages = [s.get("message") for s in elements if s is not None]
        assert messages[0] == "pending"
        assert all(m.startswith("not run: ") for m in messages[1:])

        text = self._cli(ff, "skip.yml").stdout
        assert "[SKIP] t1: t1 (pending)" in text
        assert "Results: 1 failed, 1 skipped" in text
        # "run" counts what --fail-fast reached: the author's skip was reached, not stopped
        assert "2 of 4 run — stopped by --fail-fast after 't2-fails'" in text

    def test_the_help_says_it_stops_on_an_error_too(self):
        from click.testing import CliRunner

        from rdf_construct.cli import cli

        result = CliRunner().invoke(cli, ["cq-test", "--help"])
        help_text = " ".join(result.output.split())
        assert "Stop after the first question that fails or errors" in help_text
        assert "Stop on first failure" not in help_text

    def test_run_tests_records_not_run(self, ff):
        from rdf_construct.cq import run_tests

        results = run_tests(ff / "base.ttl", ff / "ff.yml", fail_fast=True)
        assert results.total_count == 4
        assert results.not_run_count == 2
        assert results.stopped_after == "t2-fails"
        assert results.results[2].message == "not run: --fail-fast stopped after t2-fails"
        assert results.results[2].status == CQStatus.NOT_RUN
        assert results.results[2].status != CQStatus.SKIP
        assert results.all_passed is False and results.has_failures and not results.has_errors

    def test_no_stop_means_no_stopped_after(self, ff):
        from rdf_construct.cq import run_tests

        results = run_tests(ff / "base.ttl", ff / "ff.yml")
        assert results.stopped_after is None and results.not_run_count == 0


class TestFailFastKeepsAuthorSkips:
    """A ``skip: true`` question after the stop keeps its SKIP (ruled on #525's review)."""

    YML = FF_YML.replace(
        '  - id: t3\n    query: "ASK { ex:Dog a owl:Class }"\n    expect: true\n    tags: [later]\n',
        '  - id: t3\n    query: "ASK { ex:Dog a owl:Class }"\n    expect: true\n    tags: [later]\n'
        '    skip: true\n    skip_reason: "pending"\n',
    )

    @pytest.fixture
    def d(self, tmp_path):
        (tmp_path / "base.ttl").write_text(FF_BASE)
        (tmp_path / "s.yml").write_text(self.YML)
        return tmp_path

    def _cli(self, d, *args):
        from click.testing import CliRunner

        from rdf_construct.cli import cli

        return CliRunner().invoke(
            cli, ["cq-test", str(d / "base.ttl"), str(d / "s.yml"), "--fail-fast", *args]
        )

    def test_json_keeps_the_skip_and_counts_only_t4_as_not_run(self, d):
        import json

        data = json.loads(self._cli(d, "-f", "json").stdout)
        assert [q["status"] for q in data["questions"]] == ["pass", "fail", "skip", "not_run"]
        assert data["questions"][2]["skip_reason"] == "pending"
        assert (data["summary"]["skipped"], data["summary"]["not_run"]) == (1, 1)

    def test_junit_keeps_the_skip_reason(self, d):
        import xml.etree.ElementTree as ET

        suite = ET.fromstring(self._cli(d, "-f", "junit").stdout)
        skipped = [c.find("skipped").get("message") for c in suite.findall("testcase")[2:]]
        assert skipped == ["pending", "not run: --fail-fast stopped after t2-fails"]
        assert suite.get("skipped") == "2"

    def test_text_counts_up_to_the_stop(self, d):
        text = self._cli(d).stdout
        assert "[SKIP] t3: t3 (pending)" in text
        assert "2 of 4 run — stopped by --fail-fast after 't2-fails'" in text

    def test_only_skips_after_the_stop_means_no_not_run_line(self, tmp_path):
        from rdf_construct.cq import run_tests

        yml = FF_YML.replace("    tags: [later]\n", "    tags: [later]\n    skip: true\n").replace(
            '  - id: t4\n    query: "ASK { ex:Dog a owl:Class }"\n    expect: true\n',
            '  - id: t4\n    query: "ASK { ex:Dog a owl:Class }"\n    expect: true\n    skip: true\n',
        )
        (tmp_path / "base.ttl").write_text(FF_BASE)
        (tmp_path / "s.yml").write_text(yml)
        results = run_tests(tmp_path / "base.ttl", tmp_path / "s.yml", fail_fast=True)
        assert results.not_run_count == 0 and results.skipped_count == 2
        assert results.stopped_after is None and results.ran_count == 4
        assert "stopped by --fail-fast" not in self._cli(tmp_path).stdout


# ---------------------------------------------------------------------------
# #386: every SELECT solution is a row, one with every projected variable unbound included
# ---------------------------------------------------------------------------

UNBOUND_BASE = """\
@prefix ex: <http://example.org/ont#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:Animal a owl:Class .
ex:Plant a owl:Class ; rdfs:label "Plant" .
"""

UNBOUND_PREFIXES = {
    "ex": "http://example.org/ont#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}

#: Matches, with no variables: one solution, the empty mapping
VARLESS = "SELECT * WHERE { ex:Animal a owl:Class }"
#: Two classes, one labelled: two solutions, one of them with ?label unbound
OPTIONAL_ONLY = "SELECT ?label WHERE { ?c a owl:Class OPTIONAL { ?c rdfs:label ?label } }"
#: The same with ?c projected: no solution is empty, the unlabelled one omits ?label
MIXED = "SELECT ?c ?label WHERE { ?c a owl:Class OPTIONAL { ?c rdfs:label ?label } }"
ANIMAL_IRI = "http://example.org/ont#Animal"
PLANT_IRI = "http://example.org/ont#Plant"


@pytest.fixture
def unbound_graph() -> Graph:
    return Graph().parse(data=UNBOUND_BASE, format="turtle")


def _one(graph: Graph, query: str, expect) -> CQTestResult:
    """Run one question against ``graph`` and return its result."""
    suite = CQTestSuite(
        prefixes=UNBOUND_PREFIXES,
        questions=[CQTest(id="q", name="q", query=query, expectation=parse_expectation(expect))],
    )
    return CQTestRunner().run(graph, suite).results[0]


class TestEverySolutionIsARow:
    """The rows a SELECT has are SPARQL 1.1's solutions, as a bag (#386)."""

    @pytest.mark.parametrize(
        ("query", "rows"),
        [
            (VARLESS, 1),
            (OPTIONAL_ONLY, 2),
            ("SELECT ?x WHERE { ?c a owl:Class }", 2),  # two empty solutions: a bag
            ("SELECT DISTINCT ?x WHERE { ?c a owl:Class }", 1),
            ("SELECT ?x WHERE { ?c a owl:Class } OFFSET 1", 1),
            ("SELECT ?x WHERE { ?c a owl:Class } LIMIT 1", 1),
            ("SELECT ?x WHERE { ?c a owl:Class } LIMIT 0", 0),
            ("SELECT * WHERE {}", 1),
            ("SELECT * WHERE { ex:Nope a owl:Class }", 0),
            ("SELECT ?x WHERE { VALUES ?x { UNDEF ex:a UNDEF } }", 3),
            ("SELECT * WHERE { ex:Animal a owl:Class MINUS { ex:Animal a owl:Class } }", 1),
            ("SELECT * WHERE { OPTIONAL { ex:Nope a owl:Class } }", 1),
            ("SELECT ?x WHERE { { SELECT ?c WHERE { ?c a owl:Class } } }", 2),
            (MIXED, 2),
            ("SELECT (COUNT(*) AS ?n) WHERE { ?c a ex:Nothing }", 1),
        ],
        ids=[
            "variable-less",
            "optional-only",
            "bag of empties",
            "distinct empties",
            "offset",
            "limit 1",
            "limit 0",
            "empty pattern",
            "no match",
            "values undef",
            "minus with no shared variable",
            "lone optional",
            "sub-select",
            "mixed bound and unbound",
            "aggregate with no group",
        ],
    )
    def test_count(self, unbound_graph: Graph, query: str, rows: int) -> None:
        result = _one(unbound_graph, query, {"count": rows})

        assert result.status == CQStatus.PASS, result.message
        assert result.result_count == rows

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT ?c (COUNT(*) AS ?n) WHERE { ?c a ex:Nothing } GROUP BY ?c",
            "SELECT (COUNT(*) AS ?n) WHERE { ?c a ex:Nothing } GROUP BY ?c "
            "ORDER BY DESC(?n) OFFSET 0 LIMIT 3",
            "SELECT DISTINCT ?c WHERE { ?c a ex:Nothing } GROUP BY ?c",
            "SELECT ?c WHERE { ?c a ex:Nothing } GROUP BY ?c HAVING (COUNT(*) = 0)",
            "SELECT * WHERE { { SELECT ?c WHERE { ?c a ex:Nothing } GROUP BY ?c } }",
            "SELECT ?c ?n WHERE { { SELECT ?c (COUNT(*) AS ?n) WHERE { ?c a ex:Nothing } "
            "GROUP BY ?c } }",
        ],
        ids=[
            "group by",
            "with order and slice",
            "distinct",
            "having",
            "the only sub-select",
            "a sub-select, its variables projected",
        ],
    )
    def test_a_group_by_that_forms_no_groups_has_no_rows(
        self, unbound_graph: Graph, query: str
    ) -> None:
        """SPARQL has no solution here; rdflib yields one empty binding (RDFLib/rdflib#3382)."""
        result = _one(unbound_graph, query, "no_results")

        assert result.status == CQStatus.PASS, result.message
        assert result.result_count == 0

    @pytest.mark.parametrize(
        ("query", "rows"),
        [
            (
                "SELECT ?label WHERE { ?c a owl:Class OPTIONAL { ?c rdfs:label ?label } "
                "FILTER(?c = ex:Animal) } GROUP BY ?label",
                1,
            ),
            (OPTIONAL_ONLY + " GROUP BY ?label", 2),
            ("SELECT ?c WHERE { ?c a owl:Class } GROUP BY ?c", 2),
            # The outer projection drops the groups' keys: two solutions, both empty
            ("SELECT ?x WHERE { { SELECT ?c WHERE { ?c a owl:Class } GROUP BY ?c } }", 2),
        ],
        ids=[
            "one group, its key unbound",
            "two groups, one key unbound",
            "two groups",
            "two groups seen through a sub-select",
        ],
    )
    def test_a_group_with_an_unbound_key_is_a_row(
        self, unbound_graph: Graph, query: str, rows: int
    ) -> None:
        result = _one(unbound_graph, query, {"count": rows})

        assert result.status == CQStatus.PASS, result.message

    def test_rdflib_still_yields_an_empty_binding_for_no_groups(self, unbound_graph: Graph) -> None:
        """The artefact runner._solutions drops (RDFLib/rdflib#3382).

        When this fails, rdflib has fixed it (#3498): the GROUP BY guard in
        ``runner._solutions`` is then dead and can go.
        """
        result = unbound_graph.query(
            build_query_with_prefixes(
                "SELECT ?c WHERE { ?c a ex:Nothing } GROUP BY ?c", UNBOUND_PREFIXES
            )
        )

        assert [dict(b) for b in result.bindings] == [{}]

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT ?x WHERE { { SELECT ?c WHERE { ?c a ex:Nothing } GROUP BY ?c } }",
            "SELECT ?c WHERE { ?c a ex:Nothing } GROUP BY ?c VALUES ?x { 1 }",
            "SELECT * WHERE { { SELECT ?c WHERE { ?c a ex:Nothing } GROUP BY ?c } "
            "ex:Animal a owl:Class }",
            "SELECT * WHERE { { SELECT ?c WHERE { ?c a ex:Nothing } GROUP BY ?c } "
            "UNION { ex:Nope a owl:Class } }",
        ],
        ids=["projection sharing no variable", "trailing values", "joined", "union"],
    )
    def test_the_known_limitation_still_counts_one(self, unbound_graph: Graph, query: str) -> None:
        """The guide's known limitation (RDFLib/rdflib#3382): the guard cannot tell these."""
        assert _one(unbound_graph, query, {"count": 1}).status == CQStatus.PASS

    def test_rdflib_iteration_still_drops_an_empty_binding(self, unbound_graph: Graph) -> None:
        """Why runner._solutions reads ``bindings``: iterating drops the empty solution."""
        query = build_query_with_prefixes(VARLESS, UNBOUND_PREFIXES)

        assert list(unbound_graph.query(query)) == []
        assert len(unbound_graph.query(query).bindings) == 1

    @pytest.mark.parametrize(
        ("query", "grouped"),
        [
            ("SELECT ?c WHERE { ?c a ex:C } GROUP BY ?c", True),
            ("SELECT DISTINCT ?c WHERE { ?c a ex:C } GROUP BY ?c ORDER BY ?c LIMIT 2", True),
            ("SELECT ?c WHERE { ?c a ex:C } GROUP BY ?c HAVING (COUNT(*) > 1)", True),
            ("SELECT (COUNT(*) AS ?n) WHERE { ?c a ex:C }", False),
            ("SELECT ?c WHERE { ?c a ex:C }", False),
            ("SELECT * WHERE { { SELECT ?c WHERE { ?c a ex:C } GROUP BY ?c } ?c a ex:D }", False),
            ("SELECT ?x WHERE { { SELECT ?c WHERE { ?c a ex:C } GROUP BY ?c } }", False),
            ("SELECT * WHERE { { SELECT ?c WHERE { ?c a ex:C } GROUP BY ?c } }", True),
            ("SELECT ?c WHERE { ?c a ex:C } GROUP BY ?c VALUES ?x { 1 }", False),
            ("ASK { ?c a ex:C }", False),
        ],
    )
    def test_explicitly_grouped(self, query: str, grouped: bool) -> None:
        from rdflib.plugins.sparql import prepareQuery

        from rdf_construct.cq.runner import _explicitly_grouped

        prepared = prepareQuery(build_query_with_prefixes(query, {"ex": "http://example.org/x#"}))

        assert _explicitly_grouped(prepared.algebra) is grouped

    @pytest.mark.parametrize(
        "pattern",
        [
            "ex:Animal a owl:Class",
            "ex:Nope a owl:Class",
            "",
            "OPTIONAL { ex:Nope a owl:Class }",
            "ex:Animal a owl:Class MINUS { ex:Animal a owl:Class }",
            "ex:Animal a owl:Class FILTER NOT EXISTS { ex:Animal a owl:Class }",
            "ex:Animal a owl:Class . ex:Nope a owl:Class",
        ],
    )
    def test_a_variable_less_select_has_a_row_exactly_when_its_ask_is_true(
        self, unbound_graph: Graph, pattern: str
    ) -> None:
        ask = _one(unbound_graph, f"ASK {{ {pattern} }}", True)
        select = _one(unbound_graph, f"SELECT * WHERE {{ {pattern} }}", "has_results")

        assert (ask.status == CQStatus.PASS) is (select.status == CQStatus.PASS)

    @pytest.mark.parametrize(
        ("query", "triples"),
        [
            ("CONSTRUCT { ?c a owl:Class } WHERE { ?c a owl:Class }", 2),
            # No triple for the unlabelled class's solution: a template with an unbound term
            (
                "CONSTRUCT { ?c rdfs:label ?label } "
                "WHERE { ?c a owl:Class OPTIONAL { ?c rdfs:label ?label } }",
                1,
            ),
            ("DESCRIBE ex:Plant", 2),
        ],
        ids=["construct", "construct with an optional template", "describe"],
    )
    def test_construct_and_describe_count_triples(
        self, unbound_graph: Graph, query: str, triples: int
    ) -> None:
        result = _one(unbound_graph, query, {"count": triples})

        assert result.status == CQStatus.PASS, result.message
        assert result.result_count == triples

    def test_a_prefix_only_the_rdf_declares_still_resolves(self, tmp_path: Path) -> None:
        """A prefix from the ontology or a -d file works in a query, as before #386's fix."""
        from click.testing import CliRunner

        from rdf_construct.cli import cli

        (tmp_path / "o.ttl").write_text("@prefix my: <http://my.org/> .\nmy:a a my:Thing .\n")
        (tmp_path / "d.ttl").write_text("@prefix zz: <http://zz.org/> .\nzz:b a zz:Other .\n")
        (tmp_path / "q.yml").write_text(
            "questions:\n"
            '  - {id: onto, query: "SELECT ?s WHERE { ?s a my:Thing }", expect: {count: 1}}\n'
            '  - {id: data, query: "SELECT ?s WHERE { ?s a zz:Other }", expect: {count: 1}}\n'
        )

        result = CliRunner().invoke(
            cli,
            ["cq-test", str(tmp_path / "o.ttl"), str(tmp_path / "q.yml")]
            + ["-d", str(tmp_path / "d.ttl")],
        )

        assert result.exit_code == 0, result.output

    def test_an_ask_with_a_count_is_still_refused(self, unbound_graph: Graph) -> None:
        result = _one(unbound_graph, "ASK { ex:Animal a owl:Class }", {"count": 1})

        assert result.status == CQStatus.ERROR
        assert result.error_type == "InvalidExpectation"


class TestEveryExpectationSeesTheEmptySolution:
    """Each expectation checks the same solutions the count does (#386)."""

    @pytest.mark.parametrize(
        ("query", "expect", "status"),
        [
            (VARLESS, "has_results", CQStatus.PASS),
            (VARLESS, {"count": 1}, CQStatus.PASS),
            (VARLESS, "no_results", CQStatus.FAIL),
            (VARLESS, True, CQStatus.PASS),
            (VARLESS, False, CQStatus.FAIL),
            (VARLESS, {"min_results": 1}, CQStatus.PASS),
            (VARLESS, {"results": [{}]}, CQStatus.PASS),
            (OPTIONAL_ONLY, {"count": 2}, CQStatus.PASS),
            (OPTIONAL_ONLY, {"max_results": 1}, CQStatus.FAIL),
            (OPTIONAL_ONLY, {"results": [{"label": "Plant"}]}, CQStatus.FAIL),
            (OPTIONAL_ONLY, {"results": [{}, {"label": "Plant"}]}, CQStatus.PASS),
            (OPTIONAL_ONLY, {"results": [{"label": None}, {"label": "Plant"}]}, CQStatus.PASS),
            (OPTIONAL_ONLY, {"contains": [{"label": "Plant"}]}, CQStatus.PASS),
            (OPTIONAL_ONLY, {"contains": [{"label": None}]}, CQStatus.PASS),
            ("SELECT ?x WHERE { ?c a owl:Class }", {"results": [{}]}, CQStatus.FAIL),
            ("SELECT ?x WHERE { ?c a owl:Class }", {"results": [{}, {}]}, CQStatus.PASS),
        ],
    )
    def test_verdict(self, unbound_graph: Graph, query: str, expect, status: CQStatus) -> None:
        assert _one(unbound_graph, query, expect).status == status

    def test_a_partly_unbound_row_leaves_out_the_unbound_variable(
        self, unbound_graph: Graph
    ) -> None:
        both = [{"c": ANIMAL_IRI}, {"c": PLANT_IRI, "label": "Plant"}]
        spelled = [{"c": ANIMAL_IRI, "label": None}, {"c": PLANT_IRI, "label": "Plant"}]

        assert _one(unbound_graph, MIXED, {"results": both}).status == CQStatus.PASS
        assert _one(unbound_graph, MIXED, {"results": spelled}).status == CQStatus.PASS

    def test_contains_null_requires_the_variable_unbound(self, unbound_graph: Graph) -> None:
        animal = {"contains": [{"c": ANIMAL_IRI, "label": None}]}
        plant = {"contains": [{"c": PLANT_IRI, "label": None}]}

        assert _one(unbound_graph, MIXED, animal).status == CQStatus.PASS
        assert _one(unbound_graph, MIXED, plant).status == CQStatus.FAIL

    def test_contains_an_absent_variable_is_unconstrained(self, unbound_graph: Graph) -> None:
        result = _one(unbound_graph, MIXED, {"contains": [{"c": PLANT_IRI}]})

        assert result.status == CQStatus.PASS

    def test_contains_refuses_an_empty_binding(self) -> None:
        with pytest.raises(ValueError, match=r"empty binding \{\}.*use expect: has_results"):
            parse_expectation({"contains": [{"label": "Plant"}, {}]})

    @pytest.mark.parametrize(
        ("expect", "message"),
        [
            ({"contains": {}}, "'contains:' must be a list of bindings"),
            ({"contains": {"label": "x"}}, "'contains:' must be a list of bindings"),
            ({"contains": "foo"}, "'contains:' must be a list of bindings"),
            ({"contains": [None]}, "'contains:' must be a list of bindings"),
            ({"contains": []}, "'contains:' is an empty list, which checks nothing"),
            ({"results": [None]}, "'results:' must be a list of rows"),
            ({"results": {"label": "x"}}, "'results:' must be a list of rows"),
            ({"results": "foo"}, "'results:' must be a list of rows"),
        ],
    )
    def test_a_misshapen_binding_list_is_refused(self, expect, message: str) -> None:
        with pytest.raises(ValueError, match=re.escape(message)):
            parse_expectation(expect)

    def test_results_may_be_an_empty_list(self, unbound_graph: Graph) -> None:
        """``results: []`` checks that there are no rows."""
        query = "SELECT * WHERE { ex:Nope a owl:Class }"

        assert _one(unbound_graph, query, {"results": []}).status == CQStatus.PASS
        assert _one(unbound_graph, VARLESS, {"results": []}).status == CQStatus.FAIL

    def test_results_failure_shows_the_empty_solution(self, unbound_graph: Graph) -> None:
        result = _one(unbound_graph, OPTIONAL_ONLY, {"results": [{"label": "Plant"}]})

        assert result.check_result is not None
        assert result.check_result.expected == "[{'label': 'Plant'}]"
        assert result.check_result.actual == "[{}, {'label': 'Plant'}]"

    @pytest.mark.parametrize(
        "expectation",
        [
            HasResultsExpectation(),
            CountExpectation(exact=1),
            BooleanExpectation(True),
            ValuesExpectation(expected_results=[{}]),
            ContainsExpectation(expected_bindings=[{"label": None}]),
        ],
        ids=lambda e: type(e).__name__,
    )
    def test_check_on_rows_built_from_bindings(self, expectation) -> None:
        """A row from an empty binding with no projected variables is an empty, falsy tuple."""
        from rdflib.query import ResultRow

        row = ResultRow({}, [])
        assert not row

        assert expectation.check([row]).passed


UNBOUND_YML = """\
prefixes:
  ex: "http://example.org/ont#"
  owl: "http://www.w3.org/2002/07/owl#"
  rdfs: "http://www.w3.org/2000/01/rdf-schema#"
questions:
  - {id: S1, query: "SELECT * WHERE { ex:Animal a owl:Class }", expect: has_results}
  - {id: S2, query: "SELECT * WHERE { ex:Animal a owl:Class }", expect: {count: 1}}
  - id: S3
    query: "SELECT ?label WHERE { ?c a owl:Class OPTIONAL { ?c rdfs:label ?label } }"
    expect: {count: 2}
  - {id: S4, query: "ASK { ex:Animal a owl:Class }", expect: true}
  - {id: S5, query: "SELECT * WHERE { ex:Animal a owl:Class }", expect: no_results}
  - {id: S6, query: "SELECT * WHERE { ex:Animal a owl:Class }", expect: true}
  - id: S7
    query: "SELECT ?label WHERE { ?c a owl:Class OPTIONAL { ?c rdfs:label ?label } }"
    expect: {max_results: 1}
  - id: S8
    query: "SELECT ?label WHERE { ?c a owl:Class OPTIONAL { ?c rdfs:label ?label } }"
    expect: {results: [{label: "Plant"}]}
  - id: S9
    query: "SELECT ?label WHERE { ?c a owl:Class OPTIONAL { ?c rdfs:label ?label } }"
    expect: {contains: [{label: "Plant"}]}
"""

#: #386's rows S1-S9 as ruled: (status, result_count)
UNBOUND_VERDICTS = {
    "S1": ("pass", 1),
    "S2": ("pass", 1),
    "S3": ("pass", 2),
    "S4": ("pass", None),
    "S5": ("fail", 1),
    "S6": ("pass", 1),
    "S7": ("fail", 2),
    "S8": ("fail", 2),
    "S9": ("pass", 2),
}


class TestUnboundSolutionsAtTheCli:
    """#386's rows through the command, in each format."""

    @pytest.fixture
    def files(self, tmp_path: Path) -> tuple[Path, Path]:
        (tmp_path / "base.ttl").write_text(UNBOUND_BASE)
        (tmp_path / "select.yml").write_text(UNBOUND_YML)
        return tmp_path / "base.ttl", tmp_path / "select.yml"

    def _invoke(self, *argv: str):
        from click.testing import CliRunner

        from rdf_construct.cli import cli

        return CliRunner().invoke(cli, ["cq-test", *argv])

    def test_json(self, files: tuple[Path, Path]) -> None:
        import json

        result = self._invoke(str(files[0]), str(files[1]), "-f", "json")

        assert result.exit_code == 1, result.output
        report = json.loads(result.stdout)
        got = {q["id"]: (q["status"], q.get("result_count")) for q in report["questions"]}
        assert got == UNBOUND_VERDICTS

    def test_text(self, files: tuple[Path, Path]) -> None:
        result = self._invoke(str(files[0]), str(files[1]))

        assert result.exit_code == 1, result.output
        assert "[PASS] S1: S1 (1 result(s))" in result.stdout
        assert "[PASS] S3: S3 (2 result(s))" in result.stdout
        assert "Actual:   [{}, {'label': 'Plant'}]" in result.stdout

    def test_junit(self, files: tuple[Path, Path]) -> None:
        import xml.etree.ElementTree as ET

        result = self._invoke(str(files[0]), str(files[1]), "-f", "junit", "--verbose")

        assert result.exit_code == 1, result.output
        root = ET.fromstring(result.stdout[result.stdout.index("<") :])
        cases = {case.get("name").split(":")[0]: case for case in root.iter("testcase")}
        failed = {n for n, case in cases.items() if case.find("failure") is not None}
        assert failed == {"S5", "S7", "S8"}
        out = cases["S3"].find("system-out")
        assert out is not None and "Result count: 2" in out.text

    def test_contains_an_empty_binding_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / "base.ttl").write_text(UNBOUND_BASE)
        (tmp_path / "c.yml").write_text(
            'questions:\n  - {id: q, query: "SELECT * {}", expect: {contains: [{}]}}\n'
        )

        result = self._invoke(str(tmp_path / "base.ttl"), str(tmp_path / "c.yml"))

        assert result.exit_code == 2
        assert "'contains:' has an empty binding {}" in result.output

    def test_run_tests(self, files: tuple[Path, Path]) -> None:
        from rdf_construct.cq import run_tests

        results = run_tests(files[0], files[1])

        got = {r.test.id: (r.status.value, r.result_count) for r in results.results}
        assert got == UNBOUND_VERDICTS


class TestSuiteRecordsItsDataFiles:
    """``CQTestSuite.data_files`` is what ``data:`` loaded, resolved (#439)."""

    @pytest.mark.parametrize(
        "data",
        ["data: d1.ttl", "data: [d1.ttl, sub/d2.ttl]", "data:\n  files: [d1.ttl, sub/d2.ttl]"],
        ids=["shorthand", "list", "files"],
    )
    def test_data_files(self, tmp_path: Path, data: str) -> None:
        (tmp_path / "sub").mkdir()
        for name in ("d1.ttl", "sub/d2.ttl"):
            (tmp_path / name).write_text("<http://x/a> a <http://x/C> .\n")
        (tmp_path / "t.yml").write_text(f"{data}\nquestions: []\n")

        suite = load_test_suite(tmp_path / "t.yml")

        expected = [tmp_path / "d1.ttl", tmp_path / "sub" / "d2.ttl"][: data.count(".ttl")]
        assert suite.data_files == expected
        assert suite.filter_by_tags({"none"}).data_files == expected

    def test_inline_data_names_no_file(self, tmp_path: Path) -> None:
        (tmp_path / "t.yml").write_text(
            'data:\n  inline: "<http://x/a> a <http://x/C> ."\nquestions: []\n'
        )

        assert load_test_suite(tmp_path / "t.yml").data_files == []
