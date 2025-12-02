"""YAML test file loader for competency question tests.

Parses YAML files containing competency questions with SPARQL queries
and their expected results.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rdflib import Graph

from rdf_construct.cq.expectations import Expectation, parse_expectation


@dataclass
class CQTest:
    """A single competency question test.

    Attributes:
        id: Unique identifier for the test (e.g., "cq-001")
        name: Human-readable name
        description: Optional longer description
        tags: Tags for filtering tests (e.g., ["core", "schema"])
        query: SPARQL query string
        expectation: What result is expected
        skip: Whether to skip this test
        skip_reason: Reason for skipping (if skip is True)
    """
    id: str
    name: str
    query: str
    expectation: Expectation
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    skip: bool = False
    skip_reason: str | None = None


@dataclass
class CQTestSuite:
    """A suite of competency question tests.

    Attributes:
        prefixes: Namespace prefix definitions shared across all tests
        data_graph: Optional sample data graph merged with ontology
        questions: List of competency question tests
        version: Optional format version string
        name: Optional suite name
        description: Optional suite description
    """
    prefixes: dict[str, str]
    questions: list[CQTest]
    data_graph: Graph | None = None
    version: str | None = None
    name: str | None = None
    description: str | None = None

    def filter_by_tags(self, include_tags: set[str] | None = None,
                       exclude_tags: set[str] | None = None) -> "CQTestSuite":
        """Return a new suite with only tests matching tag criteria.

        Args:
            include_tags: If set, only include tests with at least one of these tags
            exclude_tags: If set, exclude tests with any of these tags

        Returns:
            New CQTestSuite with filtered questions
        """
        filtered = []
        for q in self.questions:
            question_tags = set(q.tags)

            # Check exclusions first
            if exclude_tags and question_tags & exclude_tags:
                continue

            # Check inclusions
            if include_tags and not (question_tags & include_tags):
                continue

            filtered.append(q)

        return CQTestSuite(
            prefixes=self.prefixes,
            questions=filtered,
            data_graph=self.data_graph,
            version=self.version,
            name=self.name,
            description=self.description,
        )


def load_test_suite(path: Path, base_dir: Path | None = None) -> CQTestSuite:
    """Load a competency question test suite from a YAML file.

    Args:
        path: Path to the YAML file
        base_dir: Base directory for resolving relative file paths
                  (defaults to parent directory of the YAML file)

    Returns:
        Parsed CQTestSuite

    Raises:
        FileNotFoundError: If the YAML file doesn't exist
        ValueError: If the YAML is malformed or invalid
    """
    if not path.exists():
        raise FileNotFoundError(f"Test suite file not found: {path}")

    if base_dir is None:
        base_dir = path.parent

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config is None:
        raise ValueError(f"Empty test suite file: {path}")

    # Parse metadata
    version = config.get("version")
    name = config.get("name")
    description = config.get("description")

    # Parse prefixes
    prefixes = config.get("prefixes", {})
    if not isinstance(prefixes, dict):
        raise ValueError("'prefixes' must be a dictionary")

    # Parse sample data
    data_graph = _load_data(config.get("data", {}), prefixes, base_dir)

    # Parse questions
    questions_raw = config.get("questions", [])
    if not isinstance(questions_raw, list):
        raise ValueError("'questions' must be a list")

    questions = []
    for i, q in enumerate(questions_raw):
        try:
            question = _parse_question(q, prefixes)
            questions.append(question)
        except Exception as e:
            q_id = q.get("id", f"question[{i}]") if isinstance(q, dict) else f"question[{i}]"
            raise ValueError(f"Error parsing {q_id}: {e}") from e

    return CQTestSuite(
        prefixes=prefixes,
        questions=questions,
        data_graph=data_graph,
        version=version,
        name=name,
        description=description,
    )


def _load_data(data_config: dict | None, prefixes: dict[str, str],
               base_dir: Path) -> Graph | None:
    """Load sample data from configuration.

    Supports:
    - Inline Turtle data
    - External file references
    - Both combined

    Args:
        data_config: Data configuration dict from YAML
        prefixes: Prefix definitions to apply to inline data
        base_dir: Base directory for resolving file paths

    Returns:
        Combined data graph, or None if no data specified
    """
    if not data_config:
        return None

    graph = Graph()

    # Bind prefixes
    for prefix, uri in prefixes.items():
        graph.bind(prefix, uri)

    # Load inline data
    if "inline" in data_config:
        inline = data_config["inline"]
        if isinstance(inline, str):
            # Build prefix declarations for parsing
            prefix_decls = "\n".join(
                f"@prefix {p}: <{u}> ." for p, u in prefixes.items()
            )
            turtle_data = f"{prefix_decls}\n\n{inline}"
            graph.parse(data=turtle_data, format="turtle")

    # Load external files
    if "files" in data_config:
        files = data_config["files"]
        if isinstance(files, str):
            files = [files]

        for file_path_str in files:
            file_path = base_dir / file_path_str
            if not file_path.exists():
                raise FileNotFoundError(f"Data file not found: {file_path}")

            # Infer format from extension
            fmt = _format_from_extension(file_path)
            graph.parse(str(file_path), format=fmt)

    return graph if len(graph) > 0 else None


def _format_from_extension(path: Path) -> str:
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


def _parse_question(q: dict[str, Any], prefixes: dict[str, str]) -> CQTest:
    """Parse a single question from YAML config.

    Args:
        q: Question dict from YAML
        prefixes: Prefix definitions for query injection

    Returns:
        Parsed CQTest

    Raises:
        ValueError: If required fields are missing or invalid
    """
    # Required fields
    if "id" not in q:
        raise ValueError("Question missing required 'id' field")
    if "query" not in q:
        raise ValueError(f"Question '{q['id']}' missing required 'query' field")
    if "expect" not in q:
        raise ValueError(f"Question '{q['id']}' missing required 'expect' field")

    # Parse expectation
    expectation = parse_expectation(q["expect"])

    # Handle skip
    skip = q.get("skip", False)
    skip_reason = q.get("skip_reason")

    # Parse tags
    tags = q.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    return CQTest(
        id=q["id"],
        name=q.get("name", q["id"]),
        description=q.get("description"),
        tags=tags,
        query=q["query"],
        expectation=expectation,
        skip=skip,
        skip_reason=skip_reason,
    )


def build_query_with_prefixes(query: str, prefixes: dict[str, str]) -> str:
    """Inject prefix declarations into a SPARQL query if not present.

    Args:
        query: SPARQL query string
        prefixes: Prefix definitions to inject

    Returns:
        Query with prefix declarations prepended
    """
    # Check if query already has PREFIX declarations
    query_upper = query.upper().strip()

    # Build prefix declarations
    prefix_lines = []
    for prefix, uri in prefixes.items():
        prefix_decl = f"PREFIX {prefix}: <{uri}>"
        # Only add if not already declared
        if prefix_decl.upper() not in query_upper:
            prefix_lines.append(prefix_decl)

    if prefix_lines:
        return "\n".join(prefix_lines) + "\n\n" + query
    return query
