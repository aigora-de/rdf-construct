"""Text output formatter for competency question test results.

Produces human-readable console output with colors using Click.
"""

from rdf_construct.cq.runner import CQTestResults, CQTestResult, CQStatus


def format_text(results: CQTestResults, verbose: bool = False,
                use_color: bool = True) -> str:
    """Format test results as human-readable text.

    Args:
        results: Test results to format
        verbose: Include detailed information
        use_color: Include ANSI color codes (for terminal output)

    Returns:
        Formatted text string
    """
    lines = []

    # Header
    if results.ontology_file:
        header = f"Competency Question Tests: {results.ontology_file.name}"
    else:
        header = "Competency Question Tests"

    lines.append(header)
    lines.append("=" * len(header))
    lines.append("")

    # Individual test results
    for result in results.results:
        line = _format_result_line(result, verbose, use_color)
        lines.append(line)

        # Add failure details
        if result.status == CQStatus.FAIL and result.check_result:
            lines.append(_indent(f"Expected: {result.check_result.expected}"))
            lines.append(_indent(f"Actual:   {result.check_result.actual}"))

        # Add error details
        if result.status == CQStatus.ERROR and result.error:
            lines.append(_indent(f"Error: {result.error}"))

        # Add verbose details
        if verbose and result.result_count is not None:
            lines.append(_indent(f"Results: {result.result_count}"))
        if verbose and result.duration_ms:
            lines.append(_indent(f"Duration: {result.duration_ms:.1f}ms"))

    lines.append("")

    # Summary
    summary = _format_summary(results, use_color)
    lines.append(summary)

    # Total duration
    if verbose:
        lines.append(f"Total duration: {results.total_duration_ms:.1f}ms")

    return "\n".join(lines)


def _format_result_line(result: CQTestResult, verbose: bool,
                        use_color: bool) -> str:
    """Format a single test result line."""
    status_map = {
        CQStatus.PASS: ("PASS", "green"),
        CQStatus.FAIL: ("FAIL", "red"),
        CQStatus.ERROR: ("ERROR", "red"),
        CQStatus.SKIP: ("SKIP", "yellow"),
    }

    status_text, color = status_map[result.status]

    if use_color:
        status = _colorise(f"[{status_text}]", color)
    else:
        status = f"[{status_text}]"

    # Build result info
    info_parts = []
    if result.result_count is not None and result.status == CQStatus.PASS:
        info_parts.append(f"{result.result_count} result(s)")

    if result.status == CQStatus.SKIP and result.test.skip_reason:
        info_parts.append(result.test.skip_reason)

    info_str = f" ({', '.join(info_parts)})" if info_parts else ""

    return f"{status} {result.test.id}: {result.test.name}{info_str}"


def _format_summary(results: CQTestResults, use_color: bool) -> str:
    """Format the summary line."""
    parts = []

    passed = results.passed_count
    failed = results.failed_count
    errors = results.error_count
    skipped = results.skipped_count

    if passed > 0:
        text = f"{passed} passed"
        parts.append(_colorise(text, "green") if use_color else text)

    if failed > 0:
        text = f"{failed} failed"
        parts.append(_colorise(text, "red") if use_color else text)

    if errors > 0:
        text = f"{errors} error(s)"
        parts.append(_colorise(text, "red") if use_color else text)

    if skipped > 0:
        text = f"{skipped} skipped"
        parts.append(_colorise(text, "yellow") if use_color else text)

    return f"Results: {', '.join(parts)}"


def _indent(text: str, spaces: int = 7) -> str:
    """Indent text for nested display."""
    return " " * spaces + text


def _colorise(text: str, color: str) -> str:
    """Add ANSI color codes to text.

    Supported colors: green, red, yellow, cyan, bold
    """
    color_codes = {
        "green": "\033[32m",
        "red": "\033[31m",
        "yellow": "\033[33m",
        "cyan": "\033[36m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }

    code = color_codes.get(color, "")
    reset = color_codes["reset"]

    return f"{code}{text}{reset}"
