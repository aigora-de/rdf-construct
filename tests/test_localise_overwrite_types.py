"""Tests for localise's overwrite refusal (#404) and its typed YAML reading (#408).

- #404: ``extract`` and ``init`` refuse, at exit 2 and before reading the ontology, to replace a
  destination holding a translator's work: an entry whose status is not ``pending``, or whose
  translation is not blank. A file that is not a translation file, a directory and a dangling
  link are refused too. ``--overwrite`` replaces it and says what it discarded. The default file
  is named in canonical case, so ``-l DE`` and ``-l de`` share ``de.yml`` on every filesystem.
- #408: every value read from a translation file or a config file is checked for its type. A
  value YAML read as a boolean, a number or the wrong shape is refused at exit 2, naming the
  file, the entity and the key, with nothing written; a blank translation is untranslated.

The translation-file cases each make **one** edit to ``coverage_de_finished.yml``, to its
``Listing`` entry, which is the one entry ``merge`` adds: a wrong answer shows as a missing or
wrong ``"Eintrag"@de``.
"""

import os
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import Graph, Literal, URIRef

from rdf_construct.cli import cli
from rdf_construct.localise.config import TranslationFile, TranslationFileError
from tests.test_cli_smoke import assert_no_crash, assert_wrote_nothing, snapshot

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures" / "localise"
COVERAGE = FIXTURES / "coverage.ttl"
FINISHED = FIXTURES / "coverage_de_finished.yml"
MALFORMED_TTL = REPO / "tests" / "fixtures" / "smoke" / "malformed.ttl"
LISTING = URIRef("http://example.org/heritage#Listing")
RDFS_LABEL = URIRef("http://www.w3.org/2000/01/rdf-schema#label")

# What the refusal must say about FINISHED: 7 of its 8 entries are work
FINISHED_COUNT = (
    "7 finished translations (translated 4, needs_review 1, approved 1, pending with text 1)"
)


def run(*args: str | Path) -> Result:
    result = CliRunner().invoke(cli, [str(a) for a in args])
    assert_no_crash(result)
    return result


def refused(tmp_path: Path, *args: str | Path) -> Result:
    """Run a command that must refuse at exit 2 and write nothing."""
    argv = [str(a) for a in args]
    before = snapshot(argv, tmp_path)
    result = run(*argv)
    assert result.exit_code == 2, result.output
    assert_wrote_nothing(before, snapshot(argv, tmp_path))
    return result


def edited(tmp_path: Path, old: str, new: str, name: str = "t.yml") -> Path:
    """Write FINISHED with exactly one edit, so the file differs from a good one in one place."""
    text = FINISHED.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    path = tmp_path / name
    path.write_text(text.replace(old, new), encoding="utf-8")
    return path


def listing_labels(path: Path) -> set[Literal]:
    graph = Graph()
    graph.parse(path)
    return {o for o in graph.objects(LISTING, RDFS_LABEL) if isinstance(o, Literal)}


# ---------------------------------------------------------------------------
# #404: extract and init never replace a translator's work in silence
# ---------------------------------------------------------------------------


class TestOverwrite:
    @pytest.mark.parametrize("command", ["extract", "init"])
    def test_finished_file_is_refused_with_o(self, tmp_path: Path, command: str) -> None:
        dest = tmp_path / "de.yml"
        shutil.copy(FINISHED, dest)
        result = refused(tmp_path, "localise", command, COVERAGE, "-l", "de", "-o", dest)
        assert FINISHED_COUNT in result.output
        assert "--overwrite" in result.output
        assert dest.read_bytes() == FINISHED.read_bytes()

    @pytest.mark.parametrize("command", ["extract", "init"])
    def test_finished_file_is_refused_at_the_default_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
    ) -> None:
        # The guide's first command, re-run: no -o, so the file is <language>.yml here
        monkeypatch.chdir(tmp_path)
        shutil.copy(FINISHED, tmp_path / "de.yml")
        result = refused(tmp_path, "localise", command, COVERAGE, "-l", "de")
        assert f"de.yml already holds {FINISHED_COUNT}" in result.output

    def test_default_name_is_the_tag_in_canonical_case(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = run("localise", "init", COVERAGE, "-l", "DE")
        assert result.exit_code == 0, result.output
        # listdir reports the name as created, on a case-insensitive filesystem too
        assert os.listdir(tmp_path) == ["de.yml"]

    def test_another_spelling_of_the_tag_is_refused_on_every_filesystem(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # -l DE names de.yml itself, so this does not rely on the filesystem folding case (#404)
        monkeypatch.chdir(tmp_path)
        shutil.copy(FINISHED, tmp_path / "de.yml")
        result = refused(tmp_path, "localise", "extract", COVERAGE, "-l", "DE")
        assert FINISHED_COUNT in result.output

    def test_text_left_at_pending_is_finished(self, tmp_path: Path) -> None:
        # One entry, pending, with text typed: a status-only rule would replace it in silence
        dest = tmp_path / "de.yml"
        shutil.copy(FIXTURES / "coverage_de_finished.yml", dest)
        tf = TranslationFile.from_yaml(dest)
        for entity in tf.entities:
            for label in entity.labels:
                if label.translation != "Häuschen":
                    label.translation = ""
                    label.status = label.status.PENDING
        tf.save(dest)
        before = dest.read_bytes()
        result = refused(tmp_path, "localise", "extract", COVERAGE, "-l", "de", "-o", dest)
        assert "1 finished translation (pending with text 1)" in result.output
        assert dest.read_bytes() == before

    def test_check_comes_before_the_ontology_is_read(self, tmp_path: Path) -> None:
        dest = tmp_path / "de.yml"
        shutil.copy(FINISHED, dest)
        result = refused(tmp_path, "localise", "extract", MALFORMED_TTL, "-l", "de", "-o", dest)
        assert "already holds" in result.output
        assert "Loading" not in result.output

    def test_a_file_with_no_work_in_it_is_replaced_without_a_word(self, tmp_path: Path) -> None:
        dest = tmp_path / "de.yml"
        assert run("localise", "extract", COVERAGE, "-l", "de", "-o", dest).exit_code == 0
        result = run("localise", "extract", COVERAGE, "-l", "de", "-o", dest)
        assert result.exit_code == 0, result.output
        assert "Replaced" not in result.output

    @pytest.mark.parametrize("command", ["extract", "init"])
    def test_overwrite_replaces_and_says_what_it_discarded(
        self, tmp_path: Path, command: str
    ) -> None:
        dest = tmp_path / "de.yml"
        shutil.copy(FINISHED, dest)
        result = run("localise", command, COVERAGE, "-l", "de", "-o", dest, "--overwrite")
        assert result.exit_code == 0, result.output
        assert "7 finished translations discarded" in result.stderr
        assert TranslationFile.from_yaml(dest).finished_entries() == {}

    def test_a_file_that_is_not_a_translation_file_is_refused(self, tmp_path: Path) -> None:
        dest = tmp_path / "other.ttl"
        shutil.copy(COVERAGE, dest)
        result = refused(tmp_path, "localise", "extract", COVERAGE, "-l", "de", "-o", dest)
        assert "is not a translation file: it is not valid YAML" in result.output

    @pytest.mark.parametrize(
        "content, reason",
        [
            ("not: [valid\n", "it is not valid YAML"),
            ("", "the file is empty"),
            ("just: a mapping\n", "target_language is missing"),
            ("metadata: [1]\n", "metadata must be a mapping"),
        ],
        ids=["broken-yaml", "empty", "other-mapping", "wrong-shape"],
    )
    def test_an_unreadable_destination_is_refused(
        self, tmp_path: Path, content: str, reason: str
    ) -> None:
        dest = tmp_path / "de.yml"
        dest.write_text(content, encoding="utf-8")
        result = refused(tmp_path, "localise", "init", COVERAGE, "-l", "de", "-o", dest)
        assert f"de.yml exists and is not a translation file: {reason}" in result.output

    def test_overwrite_replaces_a_file_that_is_not_a_translation_file(self, tmp_path: Path) -> None:
        dest = tmp_path / "other.ttl"
        shutil.copy(COVERAGE, dest)
        result = run("localise", "extract", COVERAGE, "-l", "de", "-o", dest, "--overwrite")
        assert result.exit_code == 0, result.output
        assert "which was not a translation file" in result.stderr

    def test_a_directory_is_refused_even_with_overwrite(self, tmp_path: Path) -> None:
        dest = tmp_path / "out"
        dest.mkdir()
        for extra in ((), ("--overwrite",)):
            result = refused(
                tmp_path, "localise", "extract", COVERAGE, "-l", "de", "-o", dest, *extra
            )
            assert "is a directory" in result.output

    def test_a_link_is_judged_by_its_target(self, tmp_path: Path) -> None:
        target = tmp_path / "real.yml"
        shutil.copy(FINISHED, target)
        link = tmp_path / "link.yml"
        link.symlink_to(target)
        result = refused(tmp_path, "localise", "extract", COVERAGE, "-l", "de", "-o", link)
        assert FINISHED_COUNT in result.output
        assert target.read_bytes() == FINISHED.read_bytes()

    def test_a_dangling_link_is_refused(self, tmp_path: Path) -> None:
        link = tmp_path / "link.yml"
        link.symlink_to(tmp_path / "nowhere.yml")
        result = refused(tmp_path, "localise", "extract", COVERAGE, "-l", "de", "-o", link)
        assert "a link to a file that does not exist" in result.output
        assert not (tmp_path / "nowhere.yml").exists()


# ---------------------------------------------------------------------------
# #408: a translation file's values are read as the type they must be
# ---------------------------------------------------------------------------

LISTING_ENTRY = "    source: Listing\n    translation: Eintrag\n    status: translated\n"
ENTITY_5 = "t.yml: entity 5 (http://example.org/heritage#Listing)"


class TestTranslationFileTypes:
    def test_the_unedited_file_merges_listing(self, tmp_path: Path) -> None:
        out = tmp_path / "l.ttl"
        result = run("localise", "merge", COVERAGE, FINISHED, "-o", out)
        assert result.exit_code == 0, result.output
        assert Literal("Eintrag", lang="de") in listing_labels(out)

    @pytest.mark.parametrize(
        "typed, reads_as",
        [
            ("Yes", "reads as true"),
            ("No", "reads as false"),
            ("On", "reads as true"),
            ("123", "reads as the number 123"),
            ("0123", "reads as the number 83"),
            ("1.50", "reads as the number 1.5"),
        ],
    )
    def test_a_translation_yaml_reads_as_a_value_is_refused(
        self, tmp_path: Path, typed: str, reads_as: str
    ) -> None:
        path = edited(tmp_path, "translation: Eintrag", f"translation: {typed}")
        result = refused(tmp_path, "localise", "merge", COVERAGE, path, "-o", tmp_path / "l.ttl")
        assert f"{ENTITY_5}, label 1 (rdfs:label): translation {reads_as}" in result.output
        assert "Quote the text" in result.output

    def test_a_quoted_translation_merges_as_typed(self, tmp_path: Path) -> None:
        path = edited(tmp_path, "translation: Eintrag", 'translation: "0123"')
        out = tmp_path / "l.ttl"
        assert run("localise", "merge", COVERAGE, path, "-o", out).exit_code == 0
        assert Literal("0123", lang="de") in listing_labels(out)

    def test_a_blank_translation_is_untranslated(self, tmp_path: Path) -> None:
        path = edited(tmp_path, "translation: Eintrag", "translation:")
        out = tmp_path / "l.ttl"
        result = run("localise", "merge", COVERAGE, path, "-o", out)
        assert result.exit_code == 0, result.output
        assert "Skipped (status): 4" in result.output
        assert not any(label.language == "de" for label in listing_labels(out))

    @pytest.mark.parametrize(
        "old, new, message",
        [
            (
                "status: translated\n- uri: http://example.org/heritage#partOf",
                "status: done\n- uri: http://example.org/heritage#partOf",
                f"{ENTITY_5}, label 1 (rdfs:label): status is the text 'done'; it must be one of "
                "pending, translated, needs_review, approved",
            ),
            (
                "- uri: http://example.org/heritage#Listing\n  type",
                "- type",
                "t.yml: entity 5, uri is missing",
            ),
            (
                "- uri: http://example.org/heritage#Listing",
                "- uri: 42",
                "t.yml: entity 5, uri reads as the number 42",
            ),
            (
                "  - property: rdfs:label\n    source: Listing",
                "  - source: Listing",
                f"{ENTITY_5}, label 1: property is missing",
            ),
            ("    source: Listing\n", "", f"{ENTITY_5}, label 1 (rdfs:label): source is missing"),
            (
                "  labels:\n  - property: rdfs:label\n" + LISTING_ENTRY,
                "  labels: Eintrag\n",
                f"{ENTITY_5}, labels must be a list, not the text 'Eintrag'",
            ),
            (
                "metadata:\n",
                "metadata: [1]\nunused:\n",
                "t.yml: metadata must be a mapping, not a list",
            ),
        ],
        ids=[
            "status",
            "no-uri",
            "uri-number",
            "no-property",
            "no-source",
            "labels-scalar",
            "metadata-list",
        ],
    )
    def test_a_wrong_shape_is_refused_naming_where(
        self, tmp_path: Path, old: str, new: str, message: str
    ) -> None:
        path = edited(tmp_path, old, new)
        result = refused(tmp_path, "localise", "merge", COVERAGE, path, "-o", tmp_path / "l.ttl")
        assert message in result.output

    @pytest.mark.parametrize(
        "content, message",
        [
            ("", "t.yml: the file is empty; it is not a translation file"),
            ("- 1\n", "t.yml: the file holds a list, not a mapping"),
            (
                "metadata:\n  target_language: de\nentities: none\n",
                "t.yml: entities must be a list, not the text 'none'",
            ),
        ],
        ids=["empty", "list", "entities-scalar"],
    )
    def test_a_file_of_the_wrong_shape_is_refused(
        self, tmp_path: Path, content: str, message: str
    ) -> None:
        path = tmp_path / "t.yml"
        path.write_text(content, encoding="utf-8")
        result = refused(tmp_path, "localise", "merge", COVERAGE, path, "-o", tmp_path / "l.ttl")
        assert message in result.output

    def test_one_bad_entry_refuses_the_file_and_every_bad_value_is_named(
        self, tmp_path: Path
    ) -> None:
        path = edited(tmp_path, "translation: Eintrag", "translation: Yes")
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("translation: Haus\n", "translation: 7\n"), encoding="utf-8")
        result = refused(tmp_path, "localise", "merge", COVERAGE, path, "-o", tmp_path / "l.ttl")
        assert "2 values cannot be read" in result.output
        assert "entity 4 (http://example.org/heritage#House), label 1" in result.output
        assert "entity 5 (http://example.org/heritage#Listing), label 1" in result.output

    @pytest.mark.parametrize(
        "old, new",
        [
            ("generated: '2026-10-25T12:00:00'", "generated: 'not a date'"),
            ("tool: rdf-construct", "tool: [1]"),
            (
                "  type: owl:Class\n  labels:\n  - property: rdfs:label\n    source: Listing",
                "  type: 3\n  labels:\n  - property: rdfs:label\n    source: Listing",
            ),
            (
                "    status: translated\n- uri: http://example.org/heritage#partOf",
                "    status: translated\n    notes: 5\n- uri: http://example.org/heritage#partOf",
            ),
            ("entities:\n", "summary: [1]\nentities:\n"),
        ],
        ids=["generated", "tool", "type", "notes", "summary"],
    )
    def test_an_informational_value_of_the_wrong_type_is_ignored(
        self, tmp_path: Path, old: str, new: str
    ) -> None:
        path = edited(tmp_path, old, new)
        out = tmp_path / "l.ttl"
        result = run("localise", "merge", COVERAGE, path, "-o", out)
        assert result.exit_code == 0, result.output
        assert Literal("Eintrag", lang="de") in listing_labels(out)

    def test_the_error_is_a_value_error(self) -> None:
        assert issubclass(TranslationFileError, ValueError)


# ---------------------------------------------------------------------------
# #408: a config file's values are read as the type they must be
# ---------------------------------------------------------------------------


class TestConfigTypes:
    def test_a_scalar_properties_is_refused(self, tmp_path: Path) -> None:
        config = FIXTURES / "localise_properties_scalar.yml"
        out = tmp_path / "de.yml"
        result = refused(
            tmp_path, "localise", "extract", COVERAGE, "-l", "de", "-c", config, "-o", out
        )
        assert (
            "localise_properties_scalar.yml: properties must be a list, not the single value "
            "'rdfs:label'; write it as a list: properties: [rdfs:label]"
        ) in result.output

    def test_a_switch_written_as_text_is_refused(self, tmp_path: Path) -> None:
        config = FIXTURES / "localise_missing_only_string.yml"
        result = refused(
            tmp_path,
            "localise",
            "extract",
            COVERAGE,
            "-l",
            "de",
            "-c",
            config,
            "-o",
            tmp_path / "de.yml",
        )
        assert "extract.missing_only must be true or false, not the text 'false'" in result.output

    @pytest.mark.parametrize(
        "content, message",
        [
            ("", "c.yml: the file is empty"),
            ("- 1\n", "c.yml: the file holds a list, not a mapping"),
            ("localise: 3\n", "c.yml: localise must be a mapping, not the number 3"),
            ("extract: yes\n", "c.yml: extract must be a mapping, not true"),
            ("languages: [en]\n", "c.yml: languages must be a mapping, not a list"),
            ("languages:\n  source: no\n", "c.yml: languages.source reads as false, not text"),
            ("languages:\n  targets: de\n", "c.yml: languages.targets must be a list"),
            ("properties:\n- 1\n", "c.yml: properties item 1 reads as the number 1"),
            (
                "extract:\n  include_deprecated: 'no'\n",
                "c.yml: extract.include_deprecated must be true or false, not the text 'no'",
            ),
            (
                "merge:\n  existing: keep\n",
                "c.yml: merge.existing is the text 'keep'; it must be one of preserve, overwrite",
            ),
            ("merge:\n  min_status: done\n", "c.yml: merge.min_status is the text 'done'"),
            ("output:\n  directory: 1\n", "c.yml: output.directory reads as the number 1"),
        ],
        ids=[
            "empty",
            "list",
            "localise-scalar",
            "extract-scalar",
            "languages-list",
            "source-no",
            "targets-scalar",
            "property-number",
            "deprecated-text",
            "existing",
            "min-status",
            "directory-number",
        ],
    )
    def test_a_wrong_type_is_refused_naming_the_key(
        self, tmp_path: Path, content: str, message: str
    ) -> None:
        config = tmp_path / "c.yml"
        config.write_text(content, encoding="utf-8")
        result = refused(
            tmp_path,
            "localise",
            "extract",
            COVERAGE,
            "-l",
            "de",
            "-c",
            config,
            "-o",
            tmp_path / "de.yml",
        )
        assert message in result.output

    def test_a_blank_key_takes_its_default(self, tmp_path: Path) -> None:
        config = tmp_path / "c.yml"
        config.write_text("properties:\n- rdfs:label\nextract:\nmerge:\n", encoding="utf-8")
        result = run(
            "localise", "extract", COVERAGE, "-l", "de", "-c", config, "-o", tmp_path / "de.yml"
        )
        assert result.exit_code == 0, result.output
        assert "Strings:         6" in result.output
