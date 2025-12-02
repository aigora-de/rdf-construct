"""Test execution engine for competency question tests.

Runs SPARQL queries against RDF graphs and checks results against expectations.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from rdflib import Graph

from rdf_construct.cq.loader import CQTest, CQTestSuite, build_query_with_prefixes
from rdf_construct.cq.expectations import CheckResult


class CQStatus(Enum):
    """Status of a test execution."""
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"


@dataclass
class CQTestResult:
    """Result of running a single competency question test.

    Attributes:
        test: The test that was run
        status: Pass/fail/error/skip status
        duration_ms: Execution time in milliseconds
        result_count: Number of results returned (if applicable)
        check_result: Detailed check result from expectation
        error: Error message if status is ERROR
    """
    test: CQTest
    status: CQStatus
    duration_ms: float = 0.0
    result_count: int | None = None
    check_result: CheckResult | None = None
    error: str | None = None

    @property
    def passed(self) -> bool:
        """Return True if test passed."""
        return self.status == CQStatus.PASS

    @property
    def message(self) -> str:
        """Return a human-readable result message."""
        if self.error:
            return self.error
        if self.check_result:
            return self.check_result.message
        if self.status == CQStatus.SKIP:
            return self.test.skip_reason or "Skipped"
        return ""


@dataclass
class CQTestResults:
    """Results of running a full test suite.

    Attributes:
        suite: The test suite that was run
        results: Individual test results
        total_duration_ms: Total execution time in milliseconds
        ontology_file: Path to the ontology file tested
    """
    suite: CQTestSuite
    results: list[CQTestResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    ontology_file: Path | None = None

    @property
    def total_count(self) -> int:
        """Total number of tests."""
        return len(self.results)

    @property
    def passed_count(self) -> int:
        """Number of passed tests."""
        return sum(1 for r in self.results if r.status == CQStatus.PASS)

    @property
    def failed_count(self) -> int:
        """Number of failed tests."""
        return sum(1 for r in self.results if r.status == CQStatus.FAIL)

    @property
    def error_count(self) -> int:
        """Number of tests with errors."""
        return sum(1 for r in self.results if r.status == CQStatus.ERROR)

    @property
    def skipped_count(self) -> int:
        """Number of skipped tests."""
        return sum(1 for r in self.results if r.status == CQStatus.SKIP)

    @property
    def all_passed(self) -> bool:
        """Return True if all tests passed (excluding skips)."""
        return self.failed_count == 0 and self.error_count == 0

    @property
    def has_failures(self) -> bool:
        """Return True if any tests failed."""
        return self.failed_count > 0

    @property
    def has_errors(self) -> bool:
        """Return True if any tests had errors."""
        return self.error_count > 0


class CQTestRunner:
    """Runner for executing competency question tests.

    Handles:
    - Loading and combining graphs (ontology + sample data)
    - Injecting prefixes into queries
    - Executing SPARQL queries
    - Checking results against expectations
    - Timing and error handling

    Args:
        fail_fast: Stop on first failure if True
        verbose: Output verbose logging if True
    """

    def __init__(self, fail_fast: bool = False, verbose: bool = False):
        self.fail_fast = fail_fast
        self.verbose = verbose

    def run(self, ontology: Graph, suite: CQTestSuite,
            ontology_file: Path | None = None) -> CQTestResults:
        """Run all tests in a suite against an ontology.

        Args:
            ontology: RDF graph containing the ontology
            suite: Test suite to execute
            ontology_file: Optional path for reporting

        Returns:
            CQTestResults with all test results
        """
        start_time = time.perf_counter()

        # Combine ontology with test data if present
        if suite.data_graph:
            graph = ontology + suite.data_graph
        else:
            graph = ontology

        # Bind prefixes for query execution
        for prefix, uri in suite.prefixes.items():
            graph.bind(prefix, uri)

        results = []
        for test in suite.questions:
            result = self._run_test(graph, test, suite.prefixes)
            results.append(result)

            if self.fail_fast and result.status in (CQStatus.FAIL, CQStatus.ERROR):
                break

        total_duration = (time.perf_counter() - start_time) * 1000

        return CQTestResults(
            suite=suite,
            results=results,
            total_duration_ms=total_duration,
            ontology_file=ontology_file,
        )

    def _run_test(self, graph: Graph, test: CQTest,
                  prefixes: dict[str, str]) -> CQTestResult:
        """Run a single test.

        Args:
            graph: Combined ontology + data graph
            test: Test to run
            prefixes: Prefix definitions for query injection

        Returns:
            CQTestResult with status and details
        """
        # Handle skipped tests
        if test.skip:
            return CQTestResult(
                test=test,
                status=CQStatus.SKIP,
            )

        start_time = time.perf_counter()

        try:
            # Inject prefixes into query
            full_query = build_query_with_prefixes(test.query, prefixes)

            # Execute query
            result = graph.query(full_query)

            # Check if this is an ASK query (returns boolean) or SELECT (returns rows)
            # rdflib Result objects have a 'type' attribute
            is_ask_query = getattr(result, 'type', None) == 'ASK'

            if is_ask_query:
                # ASK query - result is boolean
                result_count = None
                check_input = result
            else:
                # SELECT query - need to materialise results for counting
                # But we also need them for expectation checking
                # So we convert to list first
                results_list = list(result)
                result_count = len(results_list)

                # Create a fake result object that can be iterated
                # This is a bit hacky but necessary since rdflib results
                # are single-use iterators
                class ResultWrapper:
                    def __init__(self, rows):
                        self.rows = rows
                    def __iter__(self):
                        return iter(self.rows)
                    def __bool__(self):
                        return len(self.rows) > 0
                    def __len__(self):
                        return len(self.rows)

                check_input = ResultWrapper(results_list)

            # Check expectation
            check_result = test.expectation.check(check_input)

            duration = (time.perf_counter() - start_time) * 1000

            return CQTestResult(
                test=test,
                status=CQStatus.PASS if check_result.passed else CQStatus.FAIL,
                duration_ms=duration,
                result_count=result_count,
                check_result=check_result,
            )

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000

            return CQTestResult(
                test=test,
                status=CQStatus.ERROR,
                duration_ms=duration,
                error=f"{type(e).__name__}: {e}",
            )


def run_tests(ontology_path: Path, test_suite_path: Path,
              additional_data: list[Path] | None = None,
              include_tags: set[str] | None = None,
              exclude_tags: set[str] | None = None,
              fail_fast: bool = False,
              verbose: bool = False) -> CQTestResults:
    """Convenience function to run tests from file paths.

    Args:
        ontology_path: Path to ontology file
        test_suite_path: Path to test suite YAML
        additional_data: Additional data files to load
        include_tags: Only run tests with these tags
        exclude_tags: Exclude tests with these tags
        fail_fast: Stop on first failure
        verbose: Verbose output

    Returns:
        CQTestResults

    Raises:
        FileNotFoundError: If files don't exist
        ValueError: If parsing fails
    """
    from .loader import load_test_suite

    # Load ontology
    ontology = Graph()
    ontology.parse(str(ontology_path), format=_format_from_path(ontology_path))

    # Load additional data
    if additional_data:
        for data_path in additional_data:
            ontology.parse(str(data_path), format=_format_from_path(data_path))

    # Load test suite
    suite = load_test_suite(test_suite_path)

    # Filter by tags
    if include_tags or exclude_tags:
        suite = suite.filter_by_tags(include_tags, exclude_tags)

    # Run tests
    runner = CQTestRunner(fail_fast=fail_fast, verbose=verbose)
    return runner.run(ontology, suite, ontology_file=ontology_path)


def _format_from_path(path: Path) -> str:
    """Infer RDF format from file extension."""
    suffix = path.suffix.lower()
    format_map = {
        ".ttl": "turtle",
        ".turtle": "turtle",
        ".rdf": "xml",
        ".xml": "xml",
        ".owl": "xml",
        ".nt": "nt",
        ".ntriples": "nt",
        ".n3": "n3",
        ".jsonld": "json-ld",
        ".json": "json-ld",
    }
    return format_map.get(suffix, "turtle")
