"""Expectation types and matching logic for competency question tests.

Supports various expectation styles:
- Boolean: ASK queries returning true/false
- Existence: has_results, no_results
- Count: exact, min, max result counts
- Values: specific result bindings
- Contains: subset matching
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from rdflib import URIRef, Literal, BNode
from rdflib.query import Result


@dataclass
class CheckResult:
    """Result of an expectation check.

    Attributes:
        passed: Whether the expectation was met
        message: Human-readable explanation of the result
        expected: String representation of expected value
        actual: String representation of actual value
    """
    passed: bool
    message: str
    expected: str = ""
    actual: str = ""


class Expectation(ABC):
    """Abstract base class for all expectation types."""

    @abstractmethod
    def check(self, result: Result) -> CheckResult:
        """Check if the query result meets this expectation.

        Args:
            result: SPARQL query result from rdflib

        Returns:
            CheckResult with pass/fail status and explanation
        """
        ...

    @abstractmethod
    def describe(self) -> str:
        """Return a human-readable description of this expectation."""
        ...


class BooleanExpectation(Expectation):
    """Expectation for ASK queries returning true/false."""

    def __init__(self, expected: bool):
        self.expected = expected

    def check(self, result: Result) -> CheckResult:
        # ASK queries return a boolean result
        actual = bool(result)
        passed = actual == self.expected

        return CheckResult(
            passed=passed,
            message="ASK query matched" if passed else "ASK query did not match",
            expected=str(self.expected),
            actual=str(actual),
        )

    def describe(self) -> str:
        return f"ASK = {self.expected}"


class HasResultsExpectation(Expectation):
    """Expectation that a query returns at least one result."""

    def check(self, result: Result) -> CheckResult:
        # Convert to list to count (consumes the iterator)
        results_list = list(result)
        count = len(results_list)
        passed = count > 0

        return CheckResult(
            passed=passed,
            message=f"Found {count} result(s)" if passed else "No results found",
            expected="≥1 results",
            actual=f"{count} results",
        )

    def describe(self) -> str:
        return "has results"


class NoResultsExpectation(Expectation):
    """Expectation that a query returns zero results."""

    def check(self, result: Result) -> CheckResult:
        results_list = list(result)
        count = len(results_list)
        passed = count == 0

        return CheckResult(
            passed=passed,
            message="No results (as expected)" if passed else f"Expected no results, got {count}",
            expected="0 results",
            actual=f"{count} results",
        )

    def describe(self) -> str:
        return "no results"


@dataclass
class CountExpectation(Expectation):
    """Expectation for specific result counts.

    Attributes:
        exact: Exact count required (None if not specified)
        min_count: Minimum count (inclusive)
        max_count: Maximum count (inclusive)
    """
    exact: int | None = None
    min_count: int | None = None
    max_count: int | None = None

    def check(self, result: Result) -> CheckResult:
        results_list = list(result)
        actual = len(results_list)

        if self.exact is not None:
            passed = actual == self.exact
            expected_str = f"exactly {self.exact}"
        else:
            passed = True
            expected_parts = []

            if self.min_count is not None:
                if actual < self.min_count:
                    passed = False
                expected_parts.append(f"≥{self.min_count}")

            if self.max_count is not None:
                if actual > self.max_count:
                    passed = False
                expected_parts.append(f"≤{self.max_count}")

            expected_str = " and ".join(expected_parts) if expected_parts else "any count"

        if passed:
            message = f"Count {actual} matches expectation"
        else:
            message = f"Count mismatch: expected {expected_str}, got {actual}"

        return CheckResult(
            passed=passed,
            message=message,
            expected=expected_str,
            actual=str(actual),
        )

    def describe(self) -> str:
        if self.exact is not None:
            return f"count = {self.exact}"
        parts = []
        if self.min_count is not None:
            parts.append(f"≥{self.min_count}")
        if self.max_count is not None:
            parts.append(f"≤{self.max_count}")
        return "count " + " and ".join(parts) if parts else "any count"


@dataclass
class ValuesExpectation(Expectation):
    """Expectation for exact result values.

    Checks that results match a specific set of bindings exactly.
    """
    expected_results: list[dict[str, Any]] = field(default_factory=list)

    def check(self, result: Result) -> CheckResult:
        results_list = list(result)
        actual_bindings = [self._normalize_row(row) for row in results_list]
        expected_bindings = [self._normalize_dict(d) for d in self.expected_results]

        # Sort for comparison
        actual_sorted = sorted(actual_bindings, key=lambda x: str(sorted(x.items())))
        expected_sorted = sorted(expected_bindings, key=lambda x: str(sorted(x.items())))

        passed = actual_sorted == expected_sorted

        if passed:
            message = f"All {len(expected_bindings)} expected result(s) matched"
        else:
            message = "Result values do not match expected"

        return CheckResult(
            passed=passed,
            message=message,
            expected=str(expected_bindings),
            actual=str(actual_bindings),
        )

    def _normalize_row(self, row) -> dict[str, str]:
        """Normalize a result row for comparison."""
        # rdflib ResultRow has asdict() method
        if hasattr(row, 'asdict'):
            row_dict = row.asdict()
        else:
            row_dict = dict(row)
        return {str(k): self._term_to_string(v) for k, v in row_dict.items()}

    def _normalize_dict(self, d: dict) -> dict[str, str]:
        """Normalize an expected dict for comparison."""
        return {str(k): str(v) for k, v in d.items()}

    def _term_to_string(self, term: Any) -> str:
        """Convert an RDF term to a comparable string."""
        if isinstance(term, URIRef):
            return str(term)
        elif isinstance(term, Literal):
            return str(term.toPython()) if term.toPython() is not None else str(term)
        elif isinstance(term, BNode):
            return f"_:{term}"
        return str(term)

    def describe(self) -> str:
        return f"values = {len(self.expected_results)} row(s)"


@dataclass
class ContainsExpectation(Expectation):
    """Expectation that results contain certain bindings (subset match).

    Unlike ValuesExpectation, this doesn't require exact match -
    it only checks that the expected bindings are present.
    """
    expected_bindings: list[dict[str, Any]] = field(default_factory=list)

    def check(self, result: Result) -> CheckResult:
        results_list = list(result)
        actual_bindings = [self._normalize_row(row) for row in results_list]

        missing = []
        for expected in self.expected_bindings:
            normalized_expected = self._normalize_dict(expected)
            found = False
            for actual in actual_bindings:
                if self._matches(actual, normalized_expected):
                    found = True
                    break
            if not found:
                missing.append(normalized_expected)

        passed = len(missing) == 0

        if passed:
            message = f"All {len(self.expected_bindings)} expected binding(s) found"
        else:
            message = f"Missing {len(missing)} expected binding(s)"

        return CheckResult(
            passed=passed,
            message=message,
            expected=str(self.expected_bindings),
            actual=f"Missing: {missing}" if missing else "All present",
        )

    def _matches(self, actual: dict[str, str], expected: dict[str, str]) -> bool:
        """Check if actual contains all expected key-value pairs."""
        for key, value in expected.items():
            if key not in actual or actual[key] != value:
                return False
        return True

    def _normalize_row(self, row) -> dict[str, str]:
        """Normalize a result row for comparison."""
        # rdflib ResultRow has asdict() method
        if hasattr(row, 'asdict'):
            row_dict = row.asdict()
        else:
            row_dict = dict(row)
        return {str(k): self._term_to_string(v) for k, v in row_dict.items()}

    def _normalize_dict(self, d: dict) -> dict[str, str]:
        """Normalize an expected dict for comparison."""
        return {str(k): str(v) for k, v in d.items()}

    def _term_to_string(self, term: Any) -> str:
        """Convert an RDF term to a comparable string."""
        if isinstance(term, URIRef):
            return str(term)
        elif isinstance(term, Literal):
            return str(term.toPython()) if term.toPython() is not None else str(term)
        elif isinstance(term, BNode):
            return f"_:{term}"
        return str(term)

    def describe(self) -> str:
        return f"contains {len(self.expected_bindings)} binding(s)"


def parse_expectation(expect: Any) -> Expectation:
    """Parse an expectation from YAML configuration.

    Supports multiple formats:
    - Boolean: true/false for ASK queries
    - String: "has_results" or "no_results"
    - Dict with count: {"count": 5}, {"min_results": 1}, {"max_results": 10}
    - Dict with results: {"results": [{"var": "value"}]}
    - Dict with contains: {"contains": [{"var": "value"}]}

    Args:
        expect: Raw expectation value from YAML

    Returns:
        Appropriate Expectation subclass instance

    Raises:
        ValueError: If expectation format is unrecognised
    """
    # Boolean for ASK queries
    if isinstance(expect, bool):
        return BooleanExpectation(expect)

    # String shortcuts
    if isinstance(expect, str):
        if expect == "has_results":
            return HasResultsExpectation()
        elif expect == "no_results":
            return NoResultsExpectation()
        elif expect.lower() == "true":
            return BooleanExpectation(True)
        elif expect.lower() == "false":
            return BooleanExpectation(False)
        else:
            raise ValueError(f"Unknown expectation string: {expect}")

    # Dict with specific keys
    if isinstance(expect, dict):
        # Exact count
        if "count" in expect:
            return CountExpectation(exact=expect["count"])

        # Min/max count
        if "min_results" in expect or "max_results" in expect:
            return CountExpectation(
                min_count=expect.get("min_results"),
                max_count=expect.get("max_results"),
            )

        # Exact values
        if "results" in expect:
            return ValuesExpectation(expected_results=expect["results"])

        # Subset contains
        if "contains" in expect:
            return ContainsExpectation(expected_bindings=expect["contains"])

        raise ValueError(f"Unknown expectation dict keys: {expect.keys()}")

    raise ValueError(f"Unknown expectation format: {type(expect).__name__}")
