"""JUnit XML output formatter for competency question test results.

Produces JUnit XML format for CI integration (GitHub Actions, GitLab CI, Jenkins).
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom

from rdf_construct.cq.runner import CQTestResults, CQTestResult, CQStatus


def format_junit(results: CQTestResults, verbose: bool = False) -> str:
    """Format test results as JUnit XML.

    Args:
        results: Test results to format
        verbose: Include additional details in output

    Returns:
        JUnit XML string
    """
    # Build testsuite element
    testsuite = ET.Element("testsuite")

    # Set testsuite attributes
    if results.suite.name:
        testsuite.set("name", results.suite.name)
    else:
        testsuite.set("name", "Competency Questions")

    testsuite.set("tests", str(results.total_count))
    testsuite.set("failures", str(results.failed_count))
    testsuite.set("errors", str(results.error_count))
    testsuite.set("skipped", str(results.skipped_count))
    testsuite.set("time", f"{results.total_duration_ms / 1000:.3f}")

    if results.ontology_file:
        testsuite.set("file", str(results.ontology_file))

    # Add testcase elements
    for result in results.results:
        testcase = _format_testcase(result, verbose)
        testsuite.append(testcase)

    # Convert to string with pretty printing
    rough_string = ET.tostring(testsuite, encoding="unicode")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding=None)


def _format_testcase(result: CQTestResult, verbose: bool) -> ET.Element:
    """Format a single test result as a testcase element."""
    testcase = ET.Element("testcase")

    # Required attributes
    testcase.set("name", f"{result.test.id}: {result.test.name}")
    testcase.set("classname", "CompetencyQuestions")
    testcase.set("time", f"{result.duration_ms / 1000:.3f}")

    # Status-specific content
    if result.status == CQStatus.FAIL:
        failure = ET.SubElement(testcase, "failure")
        if result.check_result:
            failure.set("message", result.check_result.message)
            failure.text = (
                f"Expected: {result.check_result.expected}\n"
                f"Actual: {result.check_result.actual}"
            )
        else:
            failure.set("message", "Test failed")

    elif result.status == CQStatus.ERROR:
        error = ET.SubElement(testcase, "error")
        if result.error:
            error.set("message", result.error)
            error.set("type", "QueryError")
            error.text = result.error
        else:
            error.set("message", "Unknown error")

    elif result.status == CQStatus.SKIP:
        skipped = ET.SubElement(testcase, "skipped")
        if result.test.skip_reason:
            skipped.set("message", result.test.skip_reason)

    # Add system-out for verbose mode
    if verbose:
        system_out = ET.SubElement(testcase, "system-out")
        output_lines = []

        if result.test.description:
            output_lines.append(f"Description: {result.test.description}")

        if result.test.tags:
            output_lines.append(f"Tags: {', '.join(result.test.tags)}")

        if result.result_count is not None:
            output_lines.append(f"Result count: {result.result_count}")

        output_lines.append(f"Query:\n{result.test.query}")

        system_out.text = "\n".join(output_lines)

    return testcase
