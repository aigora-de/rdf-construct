"""JSON output formatter for competency question test results.

Produces structured JSON for programmatic consumption.
"""

import json
from typing import Any

from rdf_construct.cq.runner import CQTestResults, CQTestResult, CQStatus


def format_json(results: CQTestResults, verbose: bool = False,
                indent: int = 2) -> str:
    """Format test results as JSON.

    Args:
        results: Test results to format
        verbose: Include additional details
        indent: JSON indentation level (0 for compact)

    Returns:
        JSON string
    """
    data = _build_json_data(results, verbose)
    return json.dumps(data, indent=indent if indent > 0 else None, default=str)


def _build_json_data(results: CQTestResults, verbose: bool) -> dict[str, Any]:
    """Build the JSON data structure."""
    data: dict[str, Any] = {}

    # Metadata
    if results.ontology_file:
        data["ontology"] = str(results.ontology_file)

    if results.suite.name:
        data["suite_name"] = results.suite.name

    if results.suite.version:
        data["suite_version"] = results.suite.version

    # Test results
    data["questions"] = [
        _format_result(r, verbose) for r in results.results
    ]

    # Summary
    data["summary"] = {
        "total": results.total_count,
        "passed": results.passed_count,
        "failed": results.failed_count,
        "errors": results.error_count,
        "skipped": results.skipped_count,
    }

    if verbose:
        data["summary"]["duration_ms"] = round(results.total_duration_ms, 2)

    return data


def _format_result(result: CQTestResult, verbose: bool) -> dict[str, Any]:
    """Format a single test result as a dict."""
    data: dict[str, Any] = {
        "id": result.test.id,
        "name": result.test.name,
        "status": result.status.value,
    }

    # Add tags if present
    if result.test.tags:
        data["tags"] = result.test.tags

    # Add timing
    if result.duration_ms:
        data["duration_ms"] = round(result.duration_ms, 2)

    # Add result count for SELECT queries
    if result.result_count is not None:
        data["result_count"] = result.result_count

    # Add failure details
    if result.status == CQStatus.FAIL and result.check_result:
        data["expected"] = result.check_result.expected
        data["actual"] = result.check_result.actual
        data["message"] = result.check_result.message

    # Add error details
    if result.status == CQStatus.ERROR and result.error:
        data["error"] = result.error

    # Add skip reason
    if result.status == CQStatus.SKIP and result.test.skip_reason:
        data["skip_reason"] = result.test.skip_reason

    # Add verbose details
    if verbose:
        if result.test.description:
            data["description"] = result.test.description

        # Include the query in verbose mode
        data["query"] = result.test.query.strip()

    return data
