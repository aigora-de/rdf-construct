"""Lint engine for running rules against RDF graphs.

The engine coordinates rule execution, applies configuration overrides,
and collects results for reporting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from rdflib import Graph, URIRef

from rdf_construct.core.ownership import ownership
from rdf_construct.core.utils import (
    CurieError,
    extract_prefix_map,
    parse_failure_message,
    resolve_curie,
)
from rdf_construct.core.vocab import is_deprecated
from rdf_construct.lint.rules import (
    get_all_rules,
    get_rule,
    list_rules,
    LintIssue,
    RuleSpec,
    Severity,
)


def check_rule_ids(rule_ids: Iterable[str], where: str) -> None:
    """Refuse any rule name the registry does not know (#203).

    Args:
        rule_ids: Rule names to check.
        where: Where the names came from, for the message (e.g. ``--enable``).

    Raises:
        ValueError: If any name is not a registered rule.
    """
    known_rules = set(list_rules())
    for rule_id in rule_ids:
        if rule_id not in known_rules:
            raise ValueError(
                f"Unknown rule '{rule_id}' in {where}. "
                f"Available rules: {', '.join(sorted(known_rules))}"
            )


def find_line_number(file_path: Path, entity: URIRef) -> int | None:
    """Find approximate line number for an entity's definition in a Turtle file.

    Prioritises finding the entity as a subject (its definition) rather than
    as a predicate or object.
    """
    if not file_path.exists():
        return None

    uri_str = str(entity)

    # Extract local name
    if "#" in uri_str:
        local_name = uri_str.split("#")[-1]
    elif "/" in uri_str:
        local_name = uri_str.rsplit("/", 1)[-1]
    else:
        local_name = uri_str

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (IOError, UnicodeDecodeError):
        return None

    # First pass: look for entity as a SUBJECT (definition)
    # Pattern: entity at start of line (after optional whitespace), followed by 'a' or predicate
    subject_patterns = [
        # Full URI as subject
        rf"^\s*<{re.escape(uri_str)}>\s+",
        # Prefixed form as subject at start of line
        rf"^\s*\w+:{re.escape(local_name)}\s+",
    ]

    for pattern in subject_patterns:
        regex = re.compile(pattern)
        for i, line in enumerate(lines, start=1):
            if regex.match(line):
                return i

    # Second pass: find any occurrence (fallback)
    fallback_patterns = [
        re.escape(f"<{uri_str}>"),
        rf"\b\w+:{re.escape(local_name)}\b",
    ]

    for pattern in fallback_patterns:
        regex = re.compile(pattern)
        for i, line in enumerate(lines, start=1):
            if regex.search(line):
                return i

    return None


@dataclass
class LintConfig:
    """Configuration for a lint run.

    Attributes:
        level: Strictness level (strict/standard/relaxed).
        enabled_rules: Specific rules to enable (empty = all).
        disabled_rules: Specific rules to disable.
        severity_overrides: Override default severity for specific rules.
        external_namespaces: Namespaces whose terms are not the file's own, as written: full
            IRIs, ``<…>`` or CURIEs such as ``ies:``. A CURIE resolves against each linted
            file's own prefixes plus rdf, rdfs, owl, xsd and xml (#69).
    """

    level: str = "standard"
    enabled_rules: set[str] = field(default_factory=set)
    disabled_rules: set[str] = field(default_factory=set)
    severity_overrides: dict[str, Severity] = field(default_factory=dict)
    external_namespaces: list[str] = field(default_factory=list)

    def get_effective_rules(self) -> list[RuleSpec]:
        """Get the list of rules that should run based on config.

        The level never changes which rules run, only their severity (#208).

        Returns:
            List of RuleSpec objects to execute.

        Raises:
            ValueError: If a rule name is unknown, or if no rule is left to run (#293).
        """
        check_rule_ids(self.enabled_rules, "LintConfig.enabled_rules")
        check_rule_ids(self.disabled_rules, "LintConfig.disabled_rules")
        check_rule_ids(self.severity_overrides, "LintConfig.severity_overrides")

        all_rules = get_all_rules()

        # If specific rules enabled, use only those
        if self.enabled_rules:
            rules = [all_rules[r] for r in self.enabled_rules if r in all_rules]
        else:
            rules = list(all_rules.values())

        # Remove disabled rules
        rules = [r for r in rules if r.rule_id not in self.disabled_rules]

        # A run with no rules would report every file clean (#293)
        if not rules:
            enabled = ", ".join(sorted(self.enabled_rules)) or "all rules"
            disabled = ", ".join(sorted(self.disabled_rules)) or "none"
            raise ValueError(
                f"No lint rules left to run: enabled {enabled}; disabled {disabled}. "
                "A run with no rules would report every file clean."
            )

        return rules

    def get_effective_severity(self, rule_id: str) -> Severity:
        """Get the effective severity for a rule.

        Args:
            rule_id: The rule identifier.

        Returns:
            The severity to use for this rule.
        """
        # Check for explicit override
        if rule_id in self.severity_overrides:
            return self.severity_overrides[rule_id]

        rule = get_rule(rule_id)
        if rule is None:
            return Severity.ERROR

        # Apply level adjustments
        if self.level == "strict":
            # In strict mode, warnings become errors
            if rule.default_severity == Severity.WARNING:
                return Severity.ERROR
        elif self.level == "relaxed":
            # In relaxed mode, warnings become info
            if rule.default_severity == Severity.WARNING:
                return Severity.INFO

        return rule.default_severity


@dataclass
class LintResult:
    """Result of linting a single file.

    Attributes:
        file_path: Path to the linted file.
        graph: The parsed RDF graph (for namespace resolution).
        issues: List of issues found.
        error_count: Number of error-level issues.
        warning_count: Number of warning-level issues.
        info_count: Number of info-level issues.
        parse_error: Why the file could not be parsed, or None if it was. A file that could not
            be parsed has no issues: no rule ran on it, so it is not a finding (#322).
    """

    file_path: Path
    graph: Graph | None = None
    issues: list[LintIssue] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    parse_error: str | None = None

    def add_issue(self, issue: LintIssue) -> None:
        """Add an issue and update counts."""
        self.issues.append(issue)
        if issue.severity == Severity.ERROR:
            self.error_count += 1
        elif issue.severity == Severity.WARNING:
            self.warning_count += 1
        else:
            self.info_count += 1

    @property
    def total_issues(self) -> int:
        """Total number of issues found."""
        return len(self.issues)

    @property
    def has_errors(self) -> bool:
        """Whether any errors were found."""
        return self.error_count > 0

    @property
    def has_warnings(self) -> bool:
        """Whether any warnings were found."""
        return self.warning_count > 0


@dataclass
class LintSummary:
    """Summary of linting multiple files.

    Attributes:
        results: Individual file results.
        total_errors: Total errors across all files.
        total_warnings: Total warnings across all files.
        total_info: Total info messages across all files.
    """

    results: list[LintResult] = field(default_factory=list)
    total_errors: int = 0
    total_warnings: int = 0
    total_info: int = 0

    def add_result(self, result: LintResult) -> None:
        """Add a file result and update totals."""
        self.results.append(result)
        self.total_errors += result.error_count
        self.total_warnings += result.warning_count
        self.total_info += result.info_count

    @property
    def files_with_issues(self) -> int:
        """Number of files that had at least one issue."""
        return sum(1 for r in self.results if r.total_issues > 0)

    @property
    def unparsed(self) -> list[LintResult]:
        """The results for files that could not be parsed, in the order they were linted."""
        return [r for r in self.results if r.parse_error is not None]


def needs_prefixes(entry: str) -> bool:
    """Whether an ``external_namespaces`` entry is a CURIE, which needs a file's prefixes.

    Args:
        entry: The entry as written.

    Returns:
        False for ``<…>`` and for a full IRI (one containing ``://``), True otherwise.
    """
    s = entry.strip()
    return not (s.startswith("<") and s.endswith(">")) and "://" not in s


def resolve_external_namespaces(
    entries: Sequence[str], prefixes: dict[str, str], where: str
) -> list[str]:
    """Resolve ``external_namespaces`` entries to namespace IRIs for one file.

    Args:
        entries: The entries as written.
        prefixes: The file's own prefixes plus the core five.
        where: The file, for the message.

    Returns:
        The namespace IRIs, in the entries' order.

    Raises:
        ValueError: If a CURIE's prefix is not bound in the file.
    """
    resolved = []
    for entry in entries:
        try:
            resolved.append(str(resolve_curie(prefixes, entry)))
        except CurieError as e:
            raise ValueError(f"external_namespaces entry {entry!r} for {where}: {e}") from e
    return resolved


class LintEngine:
    """Engine for running lint rules against RDF graphs.

    The engine loads graphs, runs configured rules, and collects results.
    It supports linting single files or batches of files.
    """

    def __init__(self, config: LintConfig | None = None):
        """Initialise the lint engine.

        Args:
            config: Configuration for the lint run. Defaults to standard config.
        """
        self.config = config or LintConfig()

    def _severity(self, issue: LintIssue, graph: Graph) -> Severity:
        """The severity to report ``issue`` at.

        A finding on a deprecated term is info, whatever the level, unless the configuration
        overrides that rule's severity by name (#204, #233).

        Args:
            issue: The issue as the rule returned it.
            graph: The graph the rule ran on.

        Returns:
            The severity to report.
        """
        if (
            issue.entity is not None
            and issue.rule_id not in self.config.severity_overrides
            and is_deprecated(graph, issue.entity)
        ):
            return Severity.INFO
        return self.config.get_effective_severity(issue.rule_id)

    def _populate_line_numbers(self, result: LintResult, file_path: Path) -> None:
        """Add line numbers to issues by searching the source file."""
        for issue in result.issues:
            if issue.entity and issue.line is None:
                issue.line = find_line_number(file_path, issue.entity)

    def lint_file(self, file_path: Path) -> LintResult:
        """Lint a single RDF file.

        Args:
            file_path: Path to the RDF file.

        Returns:
            LintResult containing all issues found. If the file cannot be parsed, its
            ``parse_error`` says why and it has no issues (#322).

        Raises:
            ValueError: If the rule selection is refused, or an ``external_namespaces`` CURIE
                uses a prefix the file does not bind.
        """
        # Resolve rules before reading the file, so a refused selection never
        # depends on whether the file parses
        rules = self.config.get_effective_rules()

        result = LintResult(file_path=file_path)

        # Guess format from extension
        suffix = file_path.suffix.lower()
        if suffix in (".ttl", ".turtle"):
            fmt = "turtle"
        elif suffix in (".rdf", ".xml", ".owl"):
            fmt = "xml"
        elif suffix in (".nt", ".ntriples"):
            fmt = "nt"
        elif suffix in (".n3",):
            fmt = "n3"
        elif suffix in (".jsonld", ".json"):
            fmt = "json-ld"
        else:
            fmt = "turtle"  # Default

        # Load the graph
        graph = Graph()
        try:
            graph.parse(file_path.as_posix(), format=fmt)
            result.graph = graph  # Store for namespace resolution
        except Exception as e:
            # No rule runs on a file that cannot be parsed, so it is not a finding (#322)
            result.parse_error = parse_failure_message(file_path, fmt, e)
            return result

        # Which terms are the file's own (#69, #368): a CURIE entry resolves against the file's
        # own prefixes, which lint's own parse cannot tell apart from rdflib's defaults
        entries = self.config.external_namespaces
        prefixes: dict[str, str] = {}
        if any(needs_prefixes(e) for e in entries):
            declared = Graph(bind_namespaces="core")
            declared.parse(file_path.as_posix(), format=fmt)
            prefixes = extract_prefix_map(declared)
        owned = ownership(
            graph, resolve_external_namespaces(entries, prefixes, file_path.as_posix())
        )

        # Run rules
        for rule in rules:
            try:
                if rule.uses_ownership:
                    issues = rule.check_fn(graph, ownership=owned)
                else:
                    issues = rule.check_fn(graph)
                for issue in issues:
                    # Apply severity override
                    effective_severity = self._severity(issue, graph)
                    adjusted_issue = LintIssue(
                        rule_id=issue.rule_id,
                        severity=effective_severity,
                        entity=issue.entity,
                        message=issue.message,
                        line=issue.line,
                    )
                    result.add_issue(adjusted_issue)
            except Exception as e:
                # Rule execution error
                result.add_issue(
                    LintIssue(
                        rule_id=f"rule-error:{rule.rule_id}",
                        severity=Severity.ERROR,
                        entity=None,
                        message=f"Rule '{rule.rule_id}' failed: {e}",
                    )
                )

        # Populate line numbers
        self._populate_line_numbers(result, file_path)

        return result

    def lint_files(self, file_paths: Sequence[Path]) -> LintSummary:
        """Lint multiple RDF files.

        Args:
            file_paths: Paths to RDF files.

        Returns:
            LintSummary containing all results.
        """
        summary = LintSummary()

        for path in file_paths:
            result = self.lint_file(path)
            summary.add_result(result)

        return summary

    def lint_graph(self, graph: Graph, source_name: str = "<graph>") -> LintResult:
        """Lint an in-memory RDF graph.

        Args:
            graph: The RDF graph to lint.
            source_name: Name to use in result (for display).

        Returns:
            LintResult containing all issues found.

        An ``external_namespaces`` CURIE resolves against the prefixes `graph` binds. A graph
        built with rdflib's default ``Graph()`` binds rdflib's own table too, so ``prov:``
        resolves there whether or not the data declares it; build the graph with
        ``Graph(bind_namespaces="core")``, as `lint_file` does, to resolve against the data's own
        prefixes plus rdf, rdfs, owl, xsd and xml only.

        Raises:
            ValueError: If the rule selection is refused, or an ``external_namespaces`` CURIE
                uses a prefix the graph does not bind.
        """
        result = LintResult(file_path=Path(source_name), graph=graph)

        rules = self.config.get_effective_rules()
        owned = ownership(
            graph,
            resolve_external_namespaces(
                self.config.external_namespaces, extract_prefix_map(graph), source_name
            ),
        )

        for rule in rules:
            try:
                if rule.uses_ownership:
                    issues = rule.check_fn(graph, ownership=owned)
                else:
                    issues = rule.check_fn(graph)
                for issue in issues:
                    effective_severity = self._severity(issue, graph)
                    adjusted_issue = LintIssue(
                        rule_id=issue.rule_id,
                        severity=effective_severity,
                        entity=issue.entity,
                        message=issue.message,
                        line=issue.line,
                    )
                    result.add_issue(adjusted_issue)
            except Exception as e:
                result.add_issue(
                    LintIssue(
                        rule_id=f"rule-error:{rule.rule_id}",
                        severity=Severity.ERROR,
                        entity=None,
                        message=f"Rule '{rule.rule_id}' failed: {e}",
                    )
                )

        return result
