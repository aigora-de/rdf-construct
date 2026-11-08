"""The ``cq-test`` docs run as written (#148, #135, #137).

Every YAML block in ``CQ_TEST_GUIDE.md`` and in ``CLI_REFERENCE.md``'s ``cq-test`` section
that is a test file, or a piece of one, must load under the test file's schema. Every
``rdf-construct cq-test`` command in either runs verbatim, and exits as a clean suite does.

A block that is neither is named here by the heading it sits under, so a new kind of block
fails until someone decides what it is.
"""

from __future__ import annotations

import re
import shlex
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from rdf_construct.cli import cli
from rdf_construct.cq import load_test_suite

REPO = Path(__file__).resolve().parent.parent
GUIDE = REPO / "docs" / "user_guides" / "CQ_TEST_GUIDE.md"
REFERENCE = REPO / "docs" / "user_guides" / "CLI_REFERENCE.md"
EXAMPLES = REPO / "examples"

#: YAML blocks that are not test files, by the heading they sit under
NOT_TEST_FILES = {"GitHub Actions", "GitLab CI"}

#: Prefixes a fragment is loaded with: the guide's own, so a query is not the point here
FRAGMENT_PREFIXES = {
    "ex": "http://example.org/ontology#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}


def _reference_section() -> str:
    text = REFERENCE.read_text()
    start = text.index("### cq-test - Run Competency Question Tests")
    end = text.index("\n---\n", start)
    return text[start:end]


def _blocks(text: str) -> list[tuple[str, str, str]]:
    """Every fenced block as (language, heading above it, body)."""
    found = []
    for match in re.finditer(r"^```(\w*)\n(.*?)^```", text, re.DOTALL | re.MULTILINE):
        headings = re.findall(r"^#+ (.+)$", text[: match.start()], re.MULTILINE)
        found.append((match.group(1), headings[-1] if headings else "", match.group(2)))
    return found


def _sources() -> list[tuple[str, str]]:
    return [("CQ_TEST_GUIDE.md", GUIDE.read_text()), ("CLI_REFERENCE.md", _reference_section())]


def _yaml_blocks() -> list[Any]:
    params = []
    for name, text in _sources():
        for language, heading, body in _blocks(text):
            if language == "yaml":
                params.append(pytest.param(heading, body, id=f"{name}:{heading}"))
    return params


def _as_test_file(heading: str, block: Any, elided: bool = False) -> dict[str, Any] | None:
    """The block as a whole test file, wrapping a fragment; None if it is not one."""
    if heading in NOT_TEST_FILES:
        return None
    question = {"id": "fragment", "query": "ASK { ?s ?p ?o }", "expect": True}
    if isinstance(block, list):
        # A list of questions. One whose body is elided ("# ...") gets the required fields it
        # leaves out, but every key it does show is still checked
        questions = [{**question, **q} if isinstance(q, dict) else q for q in block]
        return {"prefixes": FRAGMENT_PREFIXES, "questions": questions if elided else block}
    assert isinstance(block, dict), f"a YAML block under {heading!r} is neither"
    if "questions" in block:
        return block
    if set(block) <= {"query", "expect"}:
        # An expectation, with or without its query
        return {"prefixes": FRAGMENT_PREFIXES, "questions": [{**question, **block}]}
    if set(block) <= {"prefixes", "data"}:
        return {"prefixes": FRAGMENT_PREFIXES, **block, "questions": [question]}
    pytest.fail(f"a YAML block under {heading!r} is not a recognised kind of block: add it")


@pytest.mark.parametrize(("heading", "body"), _yaml_blocks())
def test_every_test_file_block_loads(tmp_path: Path, heading: str, body: str) -> None:
    block = yaml.safe_load(body)
    test_file = _as_test_file(heading, block, elided="# ..." in body)
    if test_file is None:
        assert "questions" not in (block if isinstance(block, dict) else {})
        return
    (tmp_path / "sample-data.ttl").write_text(
        "@prefix ex: <http://example.org/ontology#> .\nex:Thing2 a ex:MyClass .\n"
    )
    path = tmp_path / "t.yml"
    path.write_text(yaml.safe_dump(test_file))
    suite = load_test_suite(path)
    assert suite.questions


def test_the_ci_blocks_are_the_only_ones_skipped() -> None:
    headings = {
        heading for _, text in _sources() for lang, heading, _ in _blocks(text) if lang == "yaml"
    }
    assert headings >= NOT_TEST_FILES, "a block named in NOT_TEST_FILES is gone: update the set"


def _commands() -> list[Any]:
    params = []
    for name, text in _sources():
        for _, _heading, body in _blocks(text):
            joined = body.replace("\\\n", " ")
            for line in joined.splitlines():
                command = re.sub(r"^\s*(?:- |run: )?", "", line)
                if not command.startswith("rdf-construct cq-test"):
                    continue
                if "[OPTIONS]" in command:
                    continue  # a usage line, not a command
                params.append(pytest.param(command, id=f"{name}:{command[22:]}"))
    return params


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The files the docs' commands name: the animal ontology and its example suite."""
    shutil.copy(EXAMPLES / "animal_ontology.ttl", tmp_path / "ontology.ttl")
    suite = EXAMPLES / "cq-test" / "cq_tests_animal.yml"
    (tmp_path / "tests").mkdir()
    for target in ("tests.yml", "cq-tests.yml", "tests/cq-tests.yml"):
        shutil.copy(suite, tmp_path / target)
    shutil.copy(EXAMPLES / "split" / "split_instances.ttl", tmp_path / "split_instances.ttl")
    (tmp_path / "test-data.ttl").write_text(
        "@prefix ex: <http://example.org/animals#> .\nex:Spot a ex:Dog .\n"
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize("command", _commands())
def test_every_command_runs_as_written(workdir: Path, command: str) -> None:
    argv = shlex.split(command)[1:]
    result = CliRunner().invoke(cli, argv)
    assert result.exit_code == 0, f"{command}\n{result.output}"


def test_the_commands_are_found() -> None:
    commands = [p.values[0] for p in _commands()]
    assert len(commands) >= 15
    assert any("--fail-fast" in c for c in commands)
    assert any("tests/cq-tests.yml" in c for c in commands), "the CI blocks' commands"
