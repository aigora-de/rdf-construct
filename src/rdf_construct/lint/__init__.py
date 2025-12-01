"""RDF ontology linting module.

Provides static analysis for RDF ontologies to detect quality issues,
structural problems, and best practice violations.

Example usage:

    from rdf_construct.lint import LintEngine, LintConfig

    # Basic usage
    engine = LintEngine()
    result = engine.lint_file(Path("ontology.ttl"))

    for issue in result.issues:
        print(issue)

    # With configuration
    config = LintConfig(level="strict")
    engine = LintEngine(config)

    # Multiple files
    summary = engine.lint_files([Path("a.ttl"), Path("b.ttl")])
    print(f"Exit code: {summary.exit_code}")
"""

from .rules import (
    LintIssue,
    RuleSpec,
    Severity,
    get_all_rules,
    get_rule,
    list_rules,
)
from .engine import (
    LintConfig,
    LintEngine,
    LintResult,
    LintSummary,
)
from .config import (
    load_lint_config,
    find_config_file,
    create_default_config,
)
from .formatters import (
    Formatter,
    TextFormatter,
    JsonFormatter,
    get_formatter,
)


__all__ = [
    # Rules
    "LintIssue",
    "RuleSpec",
    "Severity",
    "get_all_rules",
    "get_rule",
    "list_rules",
    # Engine
    "LintConfig",
    "LintEngine",
    "LintResult",
    "LintSummary",
    # Config
    "load_lint_config",
    "find_config_file",
    "create_default_config",
    # Formatters
    "Formatter",
    "TextFormatter",
    "JsonFormatter",
    "get_formatter",
]
