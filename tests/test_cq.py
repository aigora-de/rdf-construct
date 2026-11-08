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
    query_form_refusal,
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
            ({"contains": []}, "contains"),
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
