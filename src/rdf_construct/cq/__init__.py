"""Competency Question (CQ) testing module.

Validates whether an ontology can answer competency questions expressed
as SPARQL queries with expected results.

Example usage:

    from rdf_construct.cq import run_tests

    results = run_tests(
        ontology_path=Path("ontology.ttl"),
        test_suite_path=Path("cq-tests.yml"),
    )

    print(f"Passed: {results.passed_count}/{results.total_count}")

Or with more control:

    from rdf_construct.cq import load_test_suite, CQTestRunner
    from rdflib import Graph

    ontology = Graph()
    ontology.parse("ontology.ttl", format="turtle")

    suite = load_test_suite(Path("cq-tests.yml"))
    suite = suite.filter_by_tags(include_tags={"core"})

    runner = CQTestRunner(fail_fast=True)
    results = runner.run(ontology, suite)
"""

from rdf_construct.cq.loader import CQTest, CQTestSuite, load_test_suite
from rdf_construct.cq.runner import (
    CQTestRunner,
    CQTestResult,
    CQTestResults,
    CQStatus,
    run_tests,
)
from rdf_construct.cq.expectations import (
    Expectation,
    BooleanExpectation,
    HasResultsExpectation,
    NoResultsExpectation,
    CountExpectation,
    ValuesExpectation,
    ContainsExpectation,
    parse_expectation,
)
from rdf_construct.cq.formatters import format_results, format_text, format_json, format_junit

__all__ = [
    # Loader
    "CQTest",
    "CQTestSuite",
    "load_test_suite",
    # Runner
    "CQTestRunner",
    "CQTestResult",
    "CQTestResults",
    "CQStatus",
    "run_tests",
    # Expectations
    "Expectation",
    "BooleanExpectation",
    "HasResultsExpectation",
    "NoResultsExpectation",
    "CountExpectation",
    "ValuesExpectation",
    "ContainsExpectation",
    "parse_expectation",
    # Formatters
    "format_results",
    "format_text",
    "format_json",
    "format_junit",
]
