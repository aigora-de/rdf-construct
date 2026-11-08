"""YAML test file loader for competency question tests.

Parses YAML files containing competency questions with SPARQL queries
and their expected results.
"""

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rdflib import Graph

from rdf_construct.cq.expectations import Expectation, parse_expectation

#: Keys a test file may carry at its top level (#148)
TOP_LEVEL_KEYS = ("version", "name", "description", "prefixes", "data", "questions")

#: Keys a question may carry (#148)
QUESTION_KEYS = ("id", "name", "description", "tags", "query", "expect", "skip", "skip_reason")

#: Keys a ``data:`` mapping may carry (#148)
DATA_KEYS = ("inline", "files")

#: Names spelling-distance misses but people write for an accepted key (#135's ``tests:``)
_SYNONYMS = {"tests": "questions", "cqs": "questions"}

_DATA_FORMS = (
    "'data:' takes a file path, a list of file paths, or a mapping such as\n"
    "  data:\n"
    "    files: [sample-data.ttl]\n"
    '    inline: "ex:thing1 a ex:Thing ."'
)


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

    def filter_by_tags(
        self, include_tags: set[str] | None = None, exclude_tags: set[str] | None = None
    ) -> "CQTestSuite":
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
        ValueError: If the YAML is malformed or invalid: not a mapping, an unknown key at
            any level, a ``data:`` of the wrong shape or a data source with no triples,
            or no ``questions:`` key (#148). An empty ``questions:`` list loads as an
            empty suite; refusing an empty selection is the caller's decision (#135).
    """
    if not path.exists():
        raise FileNotFoundError(f"Test suite file not found: {path}")

    if base_dir is None:
        base_dir = path.parent

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config is None:
        raise ValueError(f"Empty test suite file: {path}")

    # The file's shape is checked before anything is read from it, so a file keyed
    # 'tests:' is refused as an unknown key, not as an empty selection (#148 before #135)
    if not isinstance(config, dict):
        raise ValueError(
            f"{path.name} must be a mapping with a 'questions:' list, not {_kind(config)}"
        )
    _check_keys(config, TOP_LEVEL_KEYS, path.name)
    if "questions" not in config:
        found = ", ".join(str(k) for k in config) or "none"
        raise ValueError(
            f"no questions to run: {path.name} has no 'questions:' list "
            f"(top-level keys found: {found})"
        )

    # Parse metadata
    version = config.get("version")
    name = config.get("name")
    description = config.get("description")

    # Parse prefixes
    prefixes = config.get("prefixes", {})
    if not isinstance(prefixes, dict):
        raise ValueError("'prefixes' must be a dictionary")

    # Parse sample data
    data_graph = _load_data(config, prefixes, base_dir) if "data" in config else None

    # Parse questions; an empty 'questions:' is an empty list, refused by the CLI
    questions_raw = config["questions"]
    if questions_raw is None:
        questions_raw = []
    if not isinstance(questions_raw, list):
        raise ValueError(f"'questions' in {path.name} must be a list, not {_kind(questions_raw)}")

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


def _load_data(config: dict[str, Any], prefixes: dict[str, str], base_dir: Path) -> Graph:
    """Load the sample data a test file's ``data:`` key names.

    Supports:
    - Inline Turtle data
    - External file references
    - Both combined
    - A file path, or a list of file paths, as shorthand for ``files:``

    Each source is parsed on its own first, and refused if it holds no triples: a
    ``no_results`` or ``max_results`` question would otherwise pass on data that never
    loaded (#148). The sources are then combined.

    Args:
        config: The test file's top-level mapping, which carries a ``data`` key
        prefixes: Prefix definitions to apply to inline data
        base_dir: Base directory for resolving file paths

    Returns:
        Combined data graph

    Raises:
        ValueError: If ``data:`` has the wrong shape, or a source holds no triples
        FileNotFoundError: If a named data file does not exist
    """
    data_config = _data_mapping(config["data"])

    graph = Graph()

    # Bind prefixes
    for prefix, uri in prefixes.items():
        graph.bind(prefix, uri)

    # Load inline data
    if "inline" in data_config:
        inline = data_config["inline"]
        if not isinstance(inline, str):
            raise ValueError(f"'data: inline:' must be Turtle text, not {_kind(inline)}")
        # Build prefix declarations for parsing
        prefix_decls = "\n".join(f"@prefix {p}: <{u}> ." for p, u in prefixes.items())
        turtle_data = f"{prefix_decls}\n\n{inline}"
        source = Graph()
        source.parse(data=turtle_data, format="turtle")
        _refuse_empty(source, "data: inline:")
        graph += source

    # Load external files
    if "files" in data_config:
        files = data_config["files"]
        if isinstance(files, str):
            files = [files]
        if not isinstance(files, list) or not files:
            raise ValueError(f"'data: files:' must be a list of file paths, not {_kind(files)}")

        for file_path_str in files:
            if not isinstance(file_path_str, str):
                raise ValueError(f"'data: files:' must list file paths, not {_kind(file_path_str)}")
            file_path = base_dir / file_path_str
            if not file_path.exists():
                raise FileNotFoundError(f"Data file not found: {file_path}")

            # Infer format from extension
            fmt = _format_from_extension(file_path)
            source = Graph()
            source.parse(str(file_path), format=fmt)
            _refuse_empty(source, f"data: {file_path_str}")
            graph += source

    return graph


def _data_mapping(data: Any) -> dict[str, Any]:
    """Return ``data:`` as a mapping, reading a path or a list of paths as ``files:``.

    Raises:
        ValueError: For any other shape, or a mapping with an unknown key or neither key
    """
    if isinstance(data, str):
        return {"files": [data]}
    if isinstance(data, list) and data and all(isinstance(entry, str) for entry in data):
        return {"files": data}
    if isinstance(data, dict):
        _check_keys(data, DATA_KEYS, "'data:'")
        if not data:
            raise ValueError(f"'data:' is an empty mapping. {_DATA_FORMS}")
        return data
    raise ValueError(f"'data:' cannot be {_kind(data)}. {_DATA_FORMS}")


def _refuse_empty(source: Graph, label: str) -> None:
    """Refuse a data source that parsed to no triples (#148)."""
    if len(source) == 0:
        raise ValueError(
            f"{label} loaded no triples; a no_results or max_results question "
            "would pass on missing data"
        )


def _check_keys(mapping: dict[Any, Any], accepted: tuple[str, ...], where: str) -> None:
    """Refuse the first key of ``mapping`` that is not in ``accepted`` (#148).

    Args:
        mapping: The YAML mapping to check
        accepted: The keys it may carry
        where: Where the mapping is, for the message (a file name, ``'data:'``, a question)

    Raises:
        ValueError: Naming the key, the nearest accepted key if there is one, and the
            accepted set
    """
    for key in mapping:
        name = str(key)
        if name in accepted:
            continue
        nearest = [_SYNONYMS[name]] if _SYNONYMS.get(name) in accepted else []
        nearest = nearest or difflib.get_close_matches(name, accepted, n=1)
        hint = f" Did you mean '{nearest[0]}'?" if nearest else ""
        raise ValueError(
            f"unknown key '{name}' in {where}.{hint} Accepted keys: {', '.join(accepted)}"
        )


def _kind(value: Any) -> str:
    """Describe a YAML value for a message."""
    if value is None:
        return "empty"
    if isinstance(value, str):
        return f"the string '{value}'"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, int | float):
        return f"the number {value}"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "a mapping"
    return type(value).__name__


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


def _parse_question(raw: Any, prefixes: dict[str, str]) -> CQTest:
    """Parse a single question from YAML config.

    Args:
        raw: Question mapping from YAML
        prefixes: Prefix definitions for query injection

    Returns:
        Parsed CQTest

    Raises:
        ValueError: If required fields are missing or invalid, or a key is unknown
    """
    if not isinstance(raw, dict):
        raise ValueError(
            f"a question must be a mapping with 'id', 'query' and 'expect', not {_kind(raw)}"
        )
    q: dict[str, Any] = raw

    where = f"question '{q['id']}'" if "id" in q else "a question"
    _check_keys(q, QUESTION_KEYS, where)

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
    if not isinstance(skip, bool):
        # A quoted "false" is a non-empty string, which skipped the question (#148)
        raise ValueError(f"'skip' must be true or false, unquoted, not {_kind(skip)}")
    skip_reason = q.get("skip_reason")

    # Parse tags
    tags = q.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        raise ValueError(f"'tags' must be a tag or a list of tags, not {_kind(tags)}")
    for t in tags:
        if not isinstance(t, str):
            raise ValueError(f"'tags' must list tags as text, not {_kind(t)}")

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
