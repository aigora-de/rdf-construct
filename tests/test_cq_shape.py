"""``cq-test`` checks its test file's shape, and refuses an empty selection (#148, #135).

#148: a test file of the wrong shape is refused at exit 2, naming the key and what is
accepted, where it used to load and test something other than what its author wrote:
``data: file.ttl`` was silently dropped, a top-level list crashed, and an unknown key
anywhere was ignored. #135: a run with no questions to check exits 2, not 0, and says why.

The shape check runs before the empty-selection refusal, so a file keyed ``tests:`` is
refused as an unknown key, not as "no questions" (#148 before #135, #283).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from rdf_construct.cli import cli
from rdf_construct.cq import load_test_suite, run_tests

REPO = Path(__file__).resolve().parent.parent
ANIMAL = REPO / "examples" / "animal_ontology.ttl"
ANIMAL_CQ = REPO / "examples" / "cq-test" / "cq_tests_animal.yml"

BASE = """\
@prefix ex: <http://example.org/ont#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:Animal a owl:Class .
ex:Dog a owl:Class .
"""

PREFIXES = 'prefixes:\n  ex: "http://example.org/ont#"\n  owl: "http://www.w3.org/2002/07/owl#"\n'

HAS = (
    "questions:\n"
    "  - id: t1\n"
    '    query: "SELECT ?s WHERE { ?s a ex:Animal }"\n'
    "    expect: has_results\n"
)
NONE = HAS.replace("has_results", "no_results")
ASK = 'questions:\n  - id: t1\n    query: "ASK { ex:Animal a owl:Class }"\n    expect: true\n'


@pytest.fixture
def files(tmp_path: Path) -> Path:
    """A directory holding the ontology and two one-triple data files."""
    (tmp_path / "base.ttl").write_text(BASE)
    (tmp_path / "data.ttl").write_text(
        "@prefix ex: <http://example.org/ont#> .\nex:rex a ex:Animal .\n"
    )
    (tmp_path / "data2.ttl").write_text(
        "@prefix ex: <http://example.org/ont#> .\nex:fido a ex:Animal .\n"
    )
    (tmp_path / "empty.ttl").write_text("# no triples\n")
    return tmp_path


def _run(d: Path, yml: str, *args: str, name: str = "t.yml") -> Result:
    path = d / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yml)
    return CliRunner().invoke(cli, ["cq-test", str(d / "base.ttl"), str(path), *args])


def _refused(result: Result, *fragments: str) -> None:
    """Exit 2 through ``Refusal`` or the loader, with every fragment in the message."""
    assert result.exit_code == 2, result.output
    assert "Traceback" not in result.output
    assert "Refusal:" not in result.output, "a Refusal was swallowed by the generic handler"
    for fragment in fragments:
        assert fragment in result.output, result.output


class TestTopLevel:
    """The file is a mapping of known keys (#148)."""

    def test_a_top_level_list_is_refused_by_name(self, files: Path) -> None:
        result = _run(files, '- id: t1\n  query: "ASK {}"\n  expect: true\n')
        _refused(result, "t.yml must be a mapping with a 'questions:' list, not a list")
        assert "AttributeError" not in result.output

    def test_a_scalar_is_refused(self, files: Path) -> None:
        _refused(_run(files, "just a string\n"), "not the string 'just a string'")

    def test_an_empty_file_keeps_its_message(self, files: Path) -> None:
        _refused(_run(files, ""), "Empty test suite file")

    def test_tests_is_refused_as_an_unknown_key_not_as_no_questions(self, files: Path) -> None:
        result = _run(files, PREFIXES + ASK.replace("questions:", "tests:"))
        _refused(result, "unknown key 'tests' in t.yml", "Did you mean 'questions'?")
        assert "no questions to run" not in result.output

    def test_a_misspelt_key_gets_a_did_you_mean(self, files: Path) -> None:
        yml = 'prefixs:\n  ex: "http://example.org/ont#"\n' + ASK
        _refused(
            _run(files, yml),
            "unknown key 'prefixs'",
            "Did you mean 'prefixes'?",
            "Accepted keys: version, name, description, prefixes, data, questions",
        )

    def test_an_anchor_parked_under_a_spare_key_is_refused(self, files: Path) -> None:
        yml = PREFIXES + (
            "defaults: &d\n  expect: true\n"
            'questions:\n  - id: t1\n    query: "ASK { ex:Animal a owl:Class }"\n    <<: *d\n'
        )
        _refused(_run(files, yml), "unknown key 'defaults'")

    def test_an_anchor_at_its_first_use_loads(self, files: Path) -> None:
        yml = PREFIXES + (
            "questions:\n"
            '  - id: t1\n    query: "ASK { ex:Animal a owl:Class }"\n    expect: &yes true\n'
            '  - id: t2\n    query: "ASK { ex:Dog a owl:Class }"\n    expect: *yes\n'
        )
        result = _run(files, yml)
        assert result.exit_code == 0, result.output
        assert "2 passed" in result.output


class TestQuestions:
    """A question is a mapping of known keys, with a boolean ``skip`` (#148)."""

    @pytest.mark.parametrize(
        ("key", "nearest"),
        [("expectt", "expect"), ("expected", "expect"), ("tag", "tags"), ("skipp", "skip")],
    )
    def test_an_unknown_key_is_refused(self, files: Path, key: str, nearest: str) -> None:
        yml = PREFIXES + ASK + f"    {key}: x\n"
        _refused(
            _run(files, yml),
            f"unknown key '{key}' in question 't1'",
            f"Did you mean '{nearest}'?",
        )

    def test_a_quoted_false_skip_is_refused(self, files: Path) -> None:
        # It used to be a non-empty string, so the failing question was skipped at exit 0
        yml = PREFIXES + ASK.replace("ex:Animal", "ex:Unicorn") + '    skip: "false"\n'
        _refused(_run(files, yml), "'skip' must be true or false, unquoted")

    def test_tags_must_be_text(self, files: Path) -> None:
        _refused(_run(files, PREFIXES + ASK + "    tags: [1]\n"), "'tags' must list tags as text")

    def test_a_question_that_is_not_a_mapping_is_refused(self, files: Path) -> None:
        _refused(
            _run(files, PREFIXES + 'questions:\n  - "ASK {}"\n'), "a question must be a mapping"
        )

    def test_a_missing_expect_is_still_refused(self, files: Path) -> None:
        _refused(
            _run(files, PREFIXES + 'questions:\n  - id: t1\n    query: "ASK {}"\n'),
            "missing required 'expect' field",
        )


class TestExpectMapping:
    """An ``expect:`` mapping takes one form, of known keys (#148)."""

    def _yml(self, expect: str) -> str:
        return PREFIXES + (
            "questions:\n"
            '  - id: t1\n    query: "SELECT ?s WHERE { ?s a owl:Class }"\n'
            f"    expect: {expect}\n"
        )

    def test_an_unknown_key_is_refused(self, files: Path) -> None:
        _refused(
            _run(files, self._yml("{count: 2, max_resultz: 1}")),
            "unknown key 'max_resultz' in 'expect:'",
            "Did you mean 'max_results'?",
        )

    def test_mixed_forms_are_refused(self, files: Path) -> None:
        # max_results was ignored, in silence, beside count
        _refused(
            _run(files, self._yml("{count: 2, max_results: 1}")),
            "'expect:' combines count, max_results",
        )

    def test_min_and_max_combine(self, files: Path) -> None:
        result = _run(files, self._yml("{min_results: 1, max_results: 3}"))
        assert result.exit_code == 0, result.output


class TestData:
    """``data:`` takes a path, a list of paths or a mapping, and every source must load (#148)."""

    def test_a_path_is_shorthand_for_files(self, files: Path) -> None:
        result = _run(files, PREFIXES + f"data: {files / 'data.ttl'}\n" + HAS)
        assert result.exit_code == 0, result.output

    def test_the_shorthand_turns_a_passing_no_results_into_a_failure(self, files: Path) -> None:
        # The data used to be dropped, so no_results passed on nothing
        result = _run(files, PREFIXES + f"data: {files / 'data.ttl'}\n" + NONE)
        assert result.exit_code == 1, result.output

    def test_a_list_of_paths_is_shorthand_for_files(self, files: Path) -> None:
        yml = PREFIXES + "data: [data.ttl, data2.ttl]\n" + HAS.replace("has_results", "{count: 2}")
        result = _run(files, yml)
        assert result.exit_code == 0, result.output

    def test_a_relative_shorthand_resolves_against_the_test_files_directory(
        self, files: Path
    ) -> None:
        (files / "sub").mkdir()
        (files / "sub" / "rel.ttl").write_text((files / "data.ttl").read_text())
        result = _run(files, PREFIXES + "data: rel.ttl\n" + HAS, name="sub/t.yml")
        assert result.exit_code == 0, result.output

    def test_inline_and_files_both_load(self, files: Path) -> None:
        yml = (
            PREFIXES
            + ('data:\n  inline: "ex:fido a ex:Animal ."\n  files: [data.ttl]\n')
            + HAS.replace("has_results", "{count: 2}")
        )
        assert _run(files, yml).exit_code == 0

    def test_data_and_dash_d_are_a_union(self, files: Path) -> None:
        yml = PREFIXES + "data: data.ttl\n" + HAS.replace("has_results", "{count: 2}")
        result = _run(files, yml, "-d", str(files / "data2.ttl"))
        assert result.exit_code == 0, result.output

    @pytest.mark.parametrize(
        ("value", "kind"),
        [("42", "the number 42"), ("true", "a boolean"), ("", "empty")],
    )
    def test_any_other_shape_is_refused_showing_the_long_form(
        self, files: Path, value: str, kind: str
    ) -> None:
        _refused(
            _run(files, PREFIXES + f"data: {value}\n" + HAS),
            f"'data:' cannot be {kind}",
            "files: [sample-data.ttl]",
        )

    def test_an_unknown_data_key_is_refused(self, files: Path) -> None:
        _refused(
            _run(files, PREFIXES + "data:\n  file: [data.ttl]\n" + HAS),
            "unknown key 'file' in 'data:'",
            "Did you mean 'files'?",
        )

    def test_inline_must_be_text(self, files: Path) -> None:
        yml = PREFIXES + 'data:\n  inline: ["ex:rex a ex:Animal ."]\n' + NONE
        _refused(_run(files, yml), "'data: inline:' must be Turtle text, not a list")

    def test_an_empty_file_is_refused(self, files: Path) -> None:
        _refused(
            _run(files, PREFIXES + "data:\n  files: [empty.ttl]\n" + NONE),
            "data: empty.ttl loaded no triples",
        )

    def test_empty_inline_is_refused(self, files: Path) -> None:
        _refused(
            _run(files, PREFIXES + 'data:\n  inline: ""\n' + NONE),
            "data: inline: loaded no triples",
        )

    def test_one_good_file_does_not_hide_an_empty_one(self, files: Path) -> None:
        yml = PREFIXES + "data: [data.ttl, empty.ttl]\n" + HAS
        _refused(_run(files, yml), "data: empty.ttl loaded no triples")


class TestEmptySelection:
    """A selection with nothing to check is refused at 2, saying why (#135)."""

    def test_no_questions_key(self, files: Path) -> None:
        _refused(
            _run(files, PREFIXES),
            "no questions to run: t.yml has no 'questions:' list",
            "(top-level keys found: prefixes)",
        )

    @pytest.mark.parametrize("value", ["[]", ""])
    def test_an_empty_questions_list(self, files: Path, value: str) -> None:
        _refused(
            _run(files, PREFIXES + f"questions: {value}\n"),
            "no questions to run: 'questions:' in t.yml is an empty list",
        )

    def test_a_tag_that_matches_nothing_names_the_defined_tags(self) -> None:
        result = CliRunner().invoke(
            cli, ["cq-test", str(ANIMAL), str(ANIMAL_CQ), "--tag", "scheme"]
        )
        _refused(
            result,
            "no questions to run: --tag scheme matches no question in cq_tests_animal.yml",
            "Tags defined: abilities, aggregation, core, data, dogs, future, hierarchy",
        )

    def _tagged(self) -> str:
        return PREFIXES + (
            "questions:\n"
            '  - id: t1\n    query: "ASK { ex:Animal a owl:Class }"\n    expect: true\n'
            "    tags: [core]\n"
            '  - id: t2\n    query: "ASK { ex:Dog a owl:Class }"\n    expect: true\n'
            "    tags: [wip]\n    skip: true\n"
        )

    def test_tag_and_exclude_tag_that_cancel_out(self, files: Path) -> None:
        _refused(
            _run(files, self._tagged(), "--tag", "core", "--exclude-tag", "core"),
            "--exclude-tag core removes every question --tag core selected",
            "Tags defined: core, wip",
        )

    def test_exclusions_alone(self, files: Path) -> None:
        _refused(
            _run(files, self._tagged(), "-x", "core", "-x", "wip"),
            "--exclude-tag core --exclude-tag wip removes every question in t.yml",
        )

    def test_a_suite_with_no_tags_says_none(self, files: Path) -> None:
        _refused(_run(files, PREFIXES + ASK, "--tag", "core"), "Tags defined: (none)")

    def test_a_filter_that_leaves_only_skipped_questions(self, files: Path) -> None:
        _refused(
            _run(files, self._tagged(), "--tag", "wip"),
            "no questions to run: every selected question has skip: true",
        )

    def test_a_file_where_every_question_is_skipped(self, files: Path) -> None:
        yml = PREFIXES + ASK + "    skip: true\n"
        _refused(_run(files, yml), "every selected question has skip: true")

    def test_the_examples_future_tag_selects_only_a_skipped_question(self) -> None:
        result = CliRunner().invoke(
            cli, ["cq-test", str(ANIMAL), str(ANIMAL_CQ), "--tag", "future"]
        )
        _refused(result, "every selected question has skip: true")

    def test_one_runnable_question_beside_skips_runs(self, files: Path) -> None:
        result = _run(files, self._tagged())
        assert result.exit_code == 0, result.output
        assert "1 passed, 1 skipped" in result.output


class TestLibrary:
    """``load_test_suite`` raises ``ValueError`` for the shape; the CLI owns the empty selection."""

    @pytest.mark.parametrize(
        ("yml", "fragment"),
        [
            ("- id: t1\n", "must be a mapping"),
            (PREFIXES + ASK.replace("questions:", "tests:"), "unknown key 'tests'"),
            (PREFIXES, "has no 'questions:' list"),
            (PREFIXES + "data: 42\n" + ASK, "'data:' cannot be the number 42"),
            (PREFIXES + "data: empty.ttl\n" + ASK, "loaded no triples"),
            (PREFIXES + ASK + "    skip: 'no'\n", "'skip' must be true or false"),
        ],
    )
    def test_load_test_suite_raises(self, files: Path, yml: str, fragment: str) -> None:
        path = files / "t.yml"
        path.write_text(yml)
        with pytest.raises(ValueError, match=fragment.replace("(", r"\(").replace(")", r"\)")):
            load_test_suite(path)

    def test_an_empty_list_loads_as_an_empty_suite(self, files: Path) -> None:
        path = files / "t.yml"
        path.write_text(PREFIXES + "questions: []\n")
        assert load_test_suite(path).questions == []
        assert run_tests(files / "base.ttl", path).total_count == 0

    def test_the_shorthand_loads_its_data(self, files: Path) -> None:
        path = files / "t.yml"
        path.write_text(PREFIXES + "data: data.ttl\n" + HAS)
        suite = load_test_suite(path)
        assert suite.data_graph is not None and len(suite.data_graph) == 1


class TestReviewFindings:
    """Shapes the independent review of #525 found with unclear messages."""

    def test_an_empty_data_list_says_so(self, files: Path) -> None:
        _refused(_run(files, PREFIXES + "data: []\n" + HAS), "'data:' is an empty list")

    def test_a_non_path_in_a_data_list_is_named(self, files: Path) -> None:
        _refused(
            _run(files, PREFIXES + "data: [data.ttl, 3]\n" + HAS),
            "'data:' must list file paths, not the number 3",
        )

    def test_an_empty_files_list_says_so(self, files: Path) -> None:
        _refused(
            _run(files, PREFIXES + "data:\n  files: []\n" + HAS), "'data: files:' is an empty list"
        )

    def test_an_empty_expect_mapping_names_the_forms(self, files: Path) -> None:
        _refused(
            _run(files, PREFIXES + ASK.replace("expect: true", "expect: {}")),
            "'expect:' is an empty mapping; use one of count",
        )

    def test_an_unmatched_tag_beside_an_excluded_one_names_both_causes(self, files: Path) -> None:
        yml = PREFIXES + ASK + "    tags: [core]\n"
        _refused(
            _run(files, yml, "--tag", "nope", "--tag", "core", "--exclude-tag", "core"),
            "--tag nope matches no question in t.yml; "
            "--exclude-tag core removes every question --tag core selected",
        )
