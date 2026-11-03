"""Tests for localise's entity set, language tags and coverage arithmetic (#157, #159, #158).

- #157 / #406: an entity is any IRI subject carrying a requested property as a literal, so a term
  typed only by an OWL characteristic, a SKOS concept, the ontology header, an individual typed by
  a class declared elsewhere and an untyped subject are all extracted and counted.
- #407: one rule for "deprecated", shared by extract and report, which recognises a plain-string
  ``owl:deprecated "true"``.
- #159: tags compared without regard to case but exactly; a zero-match warning that exits 1;
  malformed, missing and blank tags refused at exit 2 with nothing written; canonical case on merge.
- #158: coverage counted in entities over the entities carrying the property in any language,
  printed as counts beside the percentage.
- #405: ``preserve`` keeps every translation of a repeatable property (P23); ``overwrite`` replaces
  its set only when nothing is lost by it, and ``--missing-only`` offers a group with several
  source values whole (P81).
"""

import re
from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner, Result
from rdflib import Graph, Literal, URIRef

from rdf_construct.cli import cli
from rdf_construct.localise.reporter import format_fraction
from tests.test_cli_smoke import assert_no_crash, assert_wrote_nothing, snapshot

REPO = Path(__file__).resolve().parent.parent
GUIDE = REPO / "docs" / "user_guides" / "LOCALISE_GUIDE.md"
COVERAGE = REPO / "tests" / "fixtures" / "localise" / "coverage.ttl"
EX = "http://example.org/ont#"

PREFIXES = """\
@prefix ex:   <http://example.org/ont#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
"""


def ttl(tmp_path: Path, body: str, name: str = "ont.ttl") -> Path:
    path = tmp_path / name
    path.write_text(PREFIXES + dedent(body), encoding="utf-8")
    return path


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


def extracted(path: Path) -> dict[str, list[str]]:
    """Return each extracted entity's URI with its source strings, from a translation file."""
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {e["uri"]: [label["source"] for label in e["labels"]] for e in data["entities"]}


def merge_file(tmp_path: Path, target: str | None, entries: str, name: str = "t.yml") -> Path:
    """Write a translation file; `target` None leaves the key out, "" writes it with no value."""
    line = "" if target is None else f"  target_language: {target}\n"
    path = tmp_path / name
    path.write_text(
        "metadata:\n  source_file: ont.ttl\n  source_language: en\n" + line + dedent(entries),
        encoding="utf-8",
    )
    return path


BUILDING_DE = """\
entities:
- uri: http://example.org/ont#Building
  type: owl:Class
  labels:
  - {property: rdfs:label, source: Building, translation: UEBERSETZT, status: translated}
"""


# --- #157 and #406: which subjects are entities --------------------------------------------


class TestEntities:
    def test_characteristic_only_property_is_extracted_and_counted(self, tmp_path: Path) -> None:
        src = ttl(
            tmp_path,
            """
            ex:Building     a owl:Class              ; rdfs:label "Building"@en .
            ex:partOf       a owl:TransitiveProperty ; rdfs:label "part of"@en .
            ex:AncientThing a owl:DeprecatedClass    ; rdfs:label "Ancient Thing"@en .
            """,
        )
        out = tmp_path / "de.yml"
        result = run("localise", "extract", src, "-l", "de", "-o", out)
        assert result.exit_code == 0, result.output
        assert set(extracted(out)) == {EX + "Building", EX + "partOf"}
        assert "Skipped:         1" in result.output
        assert "type: owl:ObjectProperty" in out.read_text()

        report = run("localise", "report", src, "-l", "en,de", "--no-colour")
        assert "Entities: 2" in report.output
        assert "Deprecated: 1" in report.output

    def test_deprecated_class_only_is_extracted_with_include_deprecated(
        self, tmp_path: Path
    ) -> None:
        src = ttl(tmp_path, 'ex:AncientThing a owl:DeprecatedClass ; rdfs:label "Ancient"@en .')
        out = tmp_path / "de.yml"
        run("localise", "extract", src, "-l", "de", "--include-deprecated", "-o", out)
        assert extracted(out) == {EX + "AncientThing": ["Ancient"]}
        assert "type: owl:DeprecatedClass" in out.read_text()

    def test_rdfs_class_is_recorded_as_rdfs_class(self, tmp_path: Path) -> None:
        src = ttl(tmp_path, 'ex:A a rdfs:Class ; rdfs:label "A"@en .')
        out = tmp_path / "de.yml"
        run("localise", "extract", src, "-l", "de", "-o", out)
        assert "type: rdfs:Class" in out.read_text()

    def test_skos_header_and_individuals_are_entities(self, tmp_path: Path) -> None:
        # #406's reproducer, plus an untyped subject and a blank node
        src = ttl(
            tmp_path,
            """
            ex:scheme a skos:ConceptScheme ; skos:prefLabel "Colours"@en .
            ex:red a skos:Concept ; skos:inScheme ex:scheme ; skos:prefLabel "red"@en .
            ex:Dog a owl:Class ; rdfs:label "Dog"@en .
            ex:fido a ex:Dog ; rdfs:label "Fido"@en .
            <http://example.org/ont> a owl:Ontology ; rdfs:label "Vocabulary"@en .
            ex:stray rdfs:label "Stray"@en .
            [] rdfs:label "Nobody"@en .
            """,
        )
        out = tmp_path / "de.yml"
        run("localise", "extract", src, "-l", "de", "-p", "skos:prefLabel,rdfs:label", "-o", out)
        assert set(extracted(out)) == {
            EX + "scheme",
            EX + "red",
            EX + "Dog",
            EX + "fido",
            "http://example.org/ont",
            EX + "stray",
        }
        text = out.read_text()
        assert "type: skos:Concept" in text and "type: untyped" in text

        report = run(
            "localise", "report", src, "-l", "en,de", "-p", "skos:prefLabel,rdfs:label",
            "--no-colour",
        )  # fmt: skip
        assert "Entities: 6" in report.output

    def test_a_class_typed_both_ways_is_recorded_as_owl_class(self, tmp_path: Path) -> None:
        src = ttl(tmp_path, 'ex:A a owl:Class, rdfs:Class ; rdfs:label "A"@en .')
        out = tmp_path / "de.yml"
        run("localise", "extract", src, "-l", "de", "-o", out)
        assert "type: owl:Class" in out.read_text()


# --- #407: one rule for "deprecated" ------------------------------------------------------


class TestDeprecated:
    DEP = """
        ex:A a owl:Class ; rdfs:label "A"@en, "A"@de .
        ex:B a owl:Class ; rdfs:label "B"@en ; owl:deprecated "true"^^xsd:boolean .
        ex:C a owl:Class ; rdfs:label "C"@en ; owl:deprecated "true" .
        ex:D a owl:Class ; rdfs:label "D"@en ; owl:deprecated "TRUE" .
        """

    def test_report_leaves_out_what_extract_skips(self, tmp_path: Path) -> None:
        src = ttl(tmp_path, self.DEP)
        out = tmp_path / "de.yml"
        run("localise", "extract", src, "-l", "de", "-o", out)
        # A plain "TRUE" is not a boolean's lexical form, so ex:D is not deprecated (rdflib
        # rewrites "TRUE"^^xsd:boolean to "true" at parse, which is #377's ground)
        assert set(extracted(out)) == {EX + "A", EX + "D"}

        report = run("localise", "report", src, "-l", "en,de", "--no-colour")
        assert re.search(r"^de\s+1/2 \(50%\)", report.output, re.M), report.output
        assert "Deprecated: 2 (not counted; --include-deprecated counts them)" in report.output

    def test_include_deprecated_counts_them(self, tmp_path: Path) -> None:
        src = ttl(tmp_path, self.DEP)
        report = run(
            "localise", "report", src, "-l", "en,de", "--include-deprecated", "--no-colour"
        )
        assert re.search(r"^de\s+1/4 \(25%\)", report.output, re.M), report.output
        assert "Deprecated:" not in report.output


# --- #159: language tags -------------------------------------------------------------------


GB = """
    ex:House a owl:Class ;
        rdfs:label   "House"@en-GB ;
        rdfs:comment "A dwelling."@EN-gb .
    """


class TestTags:
    def test_zero_match_warns_names_the_tag_and_exits_1(self, tmp_path: Path) -> None:
        src = ttl(tmp_path, GB)
        out = tmp_path / "de.yml"
        result = run("localise", "extract", src, "-l", "de", "-o", out)
        assert result.exit_code == 1, result.output
        assert (
            "Found 2 literals tagged en-GB; --source-language en does not match them. "
            "Did you mean --source-language en-GB?"
        ) in result.output
        assert out.exists() and extracted(out) == {}

        report = run("localise", "report", src, "-l", "en,de", "--no-colour")
        assert report.exit_code == 1
        assert "Found 2 literals tagged en-GB" in report.output

    @pytest.mark.parametrize("given", ["en-gb", "EN-GB", "en-GB"])
    def test_case_is_folded_on_both_sides(self, tmp_path: Path, given: str) -> None:
        src = ttl(tmp_path, GB)
        out = tmp_path / "de.yml"
        result = run("localise", "extract", src, "-l", "de", "--source-language", given, "-o", out)
        assert result.exit_code == 0, result.output
        assert extracted(out) == {EX + "House": ["House", "A dwelling."]}

    def test_a_tag_is_not_a_range(self, tmp_path: Path) -> None:
        # en does not select en-GB, and en-GB does not select en
        src = ttl(tmp_path, 'ex:A a owl:Class ; rdfs:label "A"@en .')
        out = tmp_path / "de.yml"
        result = run(
            "localise", "extract", src, "-l", "de", "--source-language", "en-GB", "-o", out
        )
        assert extracted(out) == {}
        assert "Found 1 literal tagged en; --source-language en-GB" in result.output

    @pytest.mark.parametrize(("source", "tag"), [("x-foo", "x-bar"), ("i-klingon", "i-enochian")])
    def test_a_private_use_tag_is_related_to_nothing(
        self, tmp_path: Path, source: str, tag: str
    ) -> None:
        # x- and i- start with a singleton, which names no language (#425)
        src = ttl(tmp_path, f'ex:A rdfs:label "A"@{tag} .')
        out = tmp_path / "de.yml"
        result = run("localise", "extract", src, "-l", "de", "--source-language", source, "-o", out)
        assert result.exit_code == 0, result.output
        assert "Found" not in result.output

    def test_one_literal_reads_it_not_them(self, tmp_path: Path) -> None:
        src = ttl(tmp_path, 'ex:A rdfs:label "A"@en-GB .')
        result = run("localise", "extract", src, "-l", "de", "-o", tmp_path / "de.yml")
        assert (
            "Found 1 literal tagged en-GB; --source-language en does not match it." in result.output
        )

    def test_non_ascii_target_language_is_refused(self, tmp_path: Path) -> None:
        # A Kelvin-sign K would merge as @ko on main (#425)
        src = ttl(tmp_path, 'ex:Building a owl:Class ; rdfs:label "Building"@en .')
        trans = merge_file(tmp_path, "\u212ao", BUILDING_DE)
        result = refused(tmp_path, "localise", "merge", src, trans, "-o", tmp_path / "out.ttl")
        assert "not a well-formed" in result.output

    def test_no_warning_when_the_tag_matches_something(self, tmp_path: Path) -> None:
        src = ttl(
            tmp_path,
            """
            ex:A a owl:Class ; rdfs:label "A"@en .
            ex:B a owl:Class ; rdfs:label "B"@en-GB .
            """,
        )
        report = run("localise", "report", src, "-l", "en,de", "--no-colour")
        assert report.exit_code == 0, report.output
        assert "Found" not in report.output
        assert re.search(r"^en \(base\)\s+1/2 \(50%\)", report.output, re.M), report.output

    def test_untagged_counts_as_source_and_und_matches_nothing(self, tmp_path: Path) -> None:
        src = ttl(
            tmp_path,
            """
            ex:A a owl:Class ; rdfs:label "A" .
            ex:B a owl:Class ; rdfs:label "B"@und .
            """,
        )
        report = run("localise", "report", src, "-l", "en,de", "--no-colour")
        assert re.search(r"^en \(base\)\s+1/2 \(50%\)", report.output, re.M), report.output
        out = tmp_path / "de.yml"
        run("localise", "extract", src, "-l", "de", "-o", out)
        assert extracted(out) == {EX + "A": ["A"]}

    def test_preserve_finds_an_existing_label_whatever_its_case(self, tmp_path: Path) -> None:
        # #159's reproducer 2: target_language DE over an existing @de label
        src = ttl(tmp_path, 'ex:Building a owl:Class ; rdfs:label "Building"@en, "Gebaeude"@de .')
        out = tmp_path / "out.ttl"
        result = run("localise", "merge", src, merge_file(tmp_path, "DE", BUILDING_DE), "-o", out)
        assert result.exit_code == 0, result.output
        assert "Skipped (exists): 1" in result.output
        labels = set(Graph().parse(out).objects(URIRef(EX + "Building"), None))
        assert Literal("UEBERSETZT", lang="de") not in labels
        assert "@DE" not in out.read_text()

    def test_merge_writes_canonical_case(self, tmp_path: Path) -> None:
        src = ttl(tmp_path, 'ex:Building a owl:Class ; rdfs:label "Building"@en .')
        out = tmp_path / "out.ttl"
        run("localise", "merge", src, merge_file(tmp_path, "PT-br", BUILDING_DE), "-o", out)
        assert '"UEBERSETZT"@pt-BR' in out.read_text()

    def test_overwrite_replaces_a_label_whose_tag_differs_only_in_case(
        self, tmp_path: Path
    ) -> None:
        src = ttl(tmp_path, 'ex:Building a owl:Class ; rdfs:label "Building"@en, "Alt"@DE .')
        out = tmp_path / "out.ttl"
        trans = merge_file(tmp_path, "de", BUILDING_DE)
        run("localise", "merge", src, trans, "-o", out, "--existing", "overwrite")
        text = out.read_text()
        assert '"UEBERSETZT"@de' in text and "Alt" not in text

    @pytest.mark.parametrize(
        "args",
        [
            ("extract", "-l", "not a tag!"),
            ("extract", "-l", "de", "--source-language", "en_GB"),
            ("extract", "-l", "EN"),
            ("init", "-l", " "),
            ("report", "-l", "en,,de"),
            ("report", "-l", "en,de_DE"),
            ("extract", "-l", "\u212ao"),
            ("report", "-l", "en,d\u0131"),
        ],
    )
    def test_malformed_or_source_tag_on_the_command_line_is_refused(
        self, tmp_path: Path, args: tuple[str, ...]
    ) -> None:
        src = ttl(tmp_path, 'ex:A a owl:Class ; rdfs:label "A"@en .')
        out = ("-o", tmp_path / "x.yml") if args[0] != "report" else ()
        refused(tmp_path, "localise", args[0], src, *args[1:], *out)

    @pytest.mark.parametrize(
        ("target", "says"),
        [
            (None, "target_language is missing"),
            ("", "target_language is blank"),
            ("no", "quote it"),
            ("en_GB", "not a well-formed"),
            ("EN", "is the source language"),
        ],
    )
    def test_unusable_target_language_is_refused(
        self, tmp_path: Path, target: str | None, says: str
    ) -> None:
        src = ttl(tmp_path, 'ex:Building a owl:Class ; rdfs:label "Building"@en .')
        trans = merge_file(tmp_path, target, BUILDING_DE)
        result = refused(tmp_path, "localise", "merge", src, trans, "-o", tmp_path / "out.ttl")
        assert says in result.output

    def test_quoted_norwegian_is_accepted(self, tmp_path: Path) -> None:
        src = ttl(tmp_path, 'ex:Building a owl:Class ; rdfs:label "Building"@en .')
        out = tmp_path / "out.ttl"
        result = run("localise", "merge", src, merge_file(tmp_path, "'no'", BUILDING_DE), "-o", out)
        assert result.exit_code == 0, result.output
        assert '"UEBERSETZT"@no' in out.read_text()

    def test_blank_target_under_overwrite_keeps_the_untagged_source(self, tmp_path: Path) -> None:
        # The #159 comment's second reproducer: this deleted "Building" on main
        src = ttl(tmp_path, 'ex:Building a owl:Class ; rdfs:label "Building" .')
        trans = merge_file(tmp_path, "", BUILDING_DE)
        refused(
            tmp_path, "localise", "merge", src, trans, "-o", tmp_path / "u2.ttl",
            "--existing", "overwrite",
        )  # fmt: skip
        assert '"Building"' in src.read_text()


# --- #158: coverage arithmetic ---------------------------------------------------------------


class TestCoverage:
    def test_base_row_is_measured(self, tmp_path: Path) -> None:
        # #158's reproducer 1: one class of five labelled, labelled in English
        src = ttl(
            tmp_path,
            """
            ex:A a owl:Class ; rdfs:label "A"@en .
            ex:B a owl:Class .
            ex:C a owl:Class .
            """,
        )
        report = run("localise", "report", src, "-l", "en,de", "--no-colour")
        assert re.search(
            r"^en \(base\)\s+1/1 \(100%\)\s+0/0 \(—\)\s+1/1 \(100%\)", report.output, re.M
        )

    def test_base_row_counts_a_term_labelled_only_in_a_target(self, tmp_path: Path) -> None:
        src = ttl(
            tmp_path,
            """
            ex:A a owl:Class ; rdfs:label "A"@en .
            ex:B a owl:Class ; rdfs:label "B"@de .
            """,
        )
        report = run("localise", "report", src, "-l", "en,de", "--no-colour")
        assert re.search(r"^en \(base\)\s+1/2 \(50%\)", report.output, re.M), report.output
        assert "1 pending" in report.output

    def test_unit_is_entities_and_a_second_label_is_a_warning(self, tmp_path: Path) -> None:
        # #158's reproducer 2: three German labels on one class read 300% and -2 pending on main
        src = ttl(
            tmp_path,
            """
            ex:Twin a owl:Class ;
                rdfs:label "Twin"@en, "Zwilling"@de, "Doppelgaenger"@de, "Zwillingsbruder"@de .
            """,
        )
        report = run("localise", "report", src, "-l", "en,de", "--no-colour")
        assert report.exit_code == 0
        assert re.search(r"^de\s+1/1 \(100%\)", report.output, re.M), report.output
        assert "-" + "2 pending" not in report.output
        assert "1 entity has more than one de value" in report.output
        assert "Twin rdfs:label" in report.output

    def test_duplicate_warning_follows_predicate_tiers(self, tmp_path: Path) -> None:
        src = ttl(
            tmp_path,
            """
            ex:A skos:altLabel "One"@de, "Two"@de ; skos:prefLabel "Eins"@de, "Uno"@de .
            """,
        )
        report = run(
            "localise", "report", src, "-l", "en,de", "-p", "skos:altLabel,skos:prefLabel",
            "--no-colour",
        )  # fmt: skip
        assert "A skos:prefLabel" in report.output
        assert "skos:altLabel\n" not in report.output.split("value for a property")[-1]

    def test_status_agrees_with_the_printed_percentage(self, tmp_path: Path) -> None:
        # 149/200 is printed as 75%, so the status is the 75%-and-over one
        german = ', "K"@de'
        body = "".join(
            f'ex:C{i} a owl:Class ; rdfs:label "C"@en{german if i < 149 else ""} .\n'
            for i in range(200)
        )
        report = run("localise", "report", ttl(tmp_path, body), "-l", "en,de", "--no-colour")
        assert re.search(r"^de\s+149/200 \(75%\).*⚠ 51 pending", report.output, re.M)

    def test_verbose_lists_what_the_base_row_is_missing(self, tmp_path: Path) -> None:
        src = ttl(tmp_path, 'ex:A rdfs:label "A"@en .\nex:Turm rdfs:label "Turm"@de .')
        report = run("localise", "report", src, "-l", "en,de", "--no-colour", "-v")
        assert "Missing en source labels:\n  - Turm" in report.output

    def test_markdown_prints_counts(self, tmp_path: Path) -> None:
        src = ttl(
            tmp_path, 'ex:A a owl:Class ; rdfs:label "A"@en, "A"@de .\nex:B rdfs:label "B"@en .'
        )
        report = run("localise", "report", src, "-l", "en,de", "-f", "markdown")
        assert "| de | 1/2 (50%) | 0/0 (—) | **1/2 (50%)** |" in report.output

    @pytest.mark.parametrize(
        ("covered", "total", "shown"),
        [
            (42, 57, "42/57 (74%)"),
            (5, 8, "5/8 (63%)"),
            (0, 0, "0/0 (—)"),
            (1433, 1434, "1433/1434 (99%)"),
            (1, 1000, "1/1000 (1%)"),
            (0, 3, "0/3 (0%)"),
            (3, 3, "3/3 (100%)"),
        ],
    )
    def test_format_fraction(self, covered: int, total: int, shown: str) -> None:
        assert format_fraction(covered, total) == shown

    def test_guide_example_is_the_real_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # LOCALISE_GUIDE.md's report example is generated from tests/fixtures/localise/
        monkeypatch.chdir(REPO)
        result = run(
            "localise", "report", COVERAGE.relative_to(REPO), "-l", "en,de,fr", "--no-colour"
        )
        guide = GUIDE.read_text(encoding="utf-8")
        block = guide.split("#### Example Output", 1)[1].split("```\n", 2)[1].split("```", 1)[0]
        assert block.strip() in result.output, result.output


# --- #405, the half that lands here --------------------------------------------------------


def test_preserve_keeps_every_translation_of_a_repeatable_property(tmp_path: Path) -> None:
    src = ttl(
        tmp_path,
        """
        ex:Building a owl:Class ;
            rdfs:label "Building"@en ;
            skos:altLabel "Edifice"@en, "Structure"@en, "Bauwerk"@de .
        """,
    )
    trans = merge_file(
        tmp_path,
        "de",
        """\
        entities:
        - uri: http://example.org/ont#Building
          type: owl:Class
          labels:
          - {property: skos:altLabel, source: Edifice, translation: Bauwerk, status: translated}
          - {property: skos:altLabel, source: Structure, translation: Struktur, status: translated}
        """,
    )
    out = tmp_path / "out.ttl"
    result = run("localise", "merge", src, trans, "-o", out)
    assert "Added:           1" in result.output and "Skipped (exists): 1" in result.output
    values = set(Graph().parse(out).objects(URIRef(EX + "Building"), None))
    assert {Literal("Bauwerk", lang="de"), Literal("Struktur", lang="de")} <= values


# --- #405, the open half (P81): overwrite and --missing-only on a repeatable property --------

REPEATABLE = REPO / "tests" / "fixtures" / "localise" / "repeatable"
BRIDGE = URIRef(EX + "Bridge")
BUILDING = URIRef(EX + "Building")
ALT = URIRef("http://www.w3.org/2004/02/skos/core#altLabel")
COMMENT = URIRef("http://www.w3.org/2000/01/rdf-schema#comment")


def fill(
    path: Path, out: Path, translate: dict[str, str] | None = None, suffix: str = "-de"
) -> Path:
    """Finish an extracted file: each source `s` becomes `translate[s]`, or `s + suffix`.

    A source mapped to "" is left pending.
    """
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for entity in data["entities"]:
        for label in entity["labels"]:
            text = (translate or {}).get(label["source"], label["source"] + suffix)
            label["translation"] = text
            label["status"] = "translated" if text else "pending"
    out.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return out


def german(path: Path, subject: URIRef, prop: URIRef) -> set[str]:
    return {
        str(o)
        for o in Graph().parse(path).objects(subject, prop)
        if isinstance(o, Literal) and o.language == "de"
    }


class TestRepeatable:
    """Overwrite replaces a repeatable property's set, only when nothing is lost by it."""

    PROPS = "rdfs:label,rdfs:comment,skos:altLabel"

    def extract(self, tmp_path: Path, src: Path, *args: str) -> Path:
        out = tmp_path / "de.yml"
        result = run("localise", "extract", src, "-l", "de", *args, "-o", out)
        assert result.exit_code == 0, result.output
        return out

    def preserved(self, tmp_path: Path) -> Path:
        """The fixture with every value translated once, by a preserve merge."""
        src = REPEATABLE / "ontology.ttl"
        done = fill(self.extract(tmp_path, src, "-p", self.PROPS), tmp_path / "first.yml")
        out = tmp_path / "preserved.ttl"
        result = run("localise", "merge", src, done, "-o", out)
        assert result.exit_code == 0 and "Added:           10" in result.output, result.output
        return out

    def test_overwrite_onto_no_translation_adds_every_value(self, tmp_path: Path) -> None:
        src = REPEATABLE / "ontology.ttl"
        done = fill(self.extract(tmp_path, src, "-p", self.PROPS), tmp_path / "done.yml")
        out = tmp_path / "out.ttl"
        result = run("localise", "merge", src, done, "--existing", "overwrite", "-o", out)
        assert result.exit_code == 0, result.output
        assert "Added:           10" in result.output and "Updated:         0" in result.output
        assert german(out, BRIDGE, ALT) == {"Span-de", "Crossing-de", "Viaduct-de"}
        assert german(out, BUILDING, ALT) == {"Structure-de", "Edifice-de"}

    def test_overwrite_onto_translations_replaces_the_set(self, tmp_path: Path) -> None:
        src = self.preserved(tmp_path)
        done = fill(
            self.extract(tmp_path, REPEATABLE / "ontology.ttl", "-p", self.PROPS),
            tmp_path / "second.yml",
            suffix="-neu",
        )
        out = tmp_path / "out.ttl"
        result = run("localise", "merge", src, done, "--existing", "overwrite", "-o", out)
        assert result.exit_code == 0, result.output
        assert "Added:           0" in result.output and "Updated:         10" in result.output
        assert german(out, BRIDGE, ALT) == {"Span-neu", "Crossing-neu", "Viaduct-neu"}
        assert german(out, BRIDGE, COMMENT) == {"One.-neu", "Two.-neu"}
        assert german(out, BUILDING, ALT) == {"Structure-neu", "Edifice-neu"}

    def test_a_pending_sibling_leaves_the_group_unchanged_at_exit_1(self, tmp_path: Path) -> None:
        src = self.preserved(tmp_path)
        extract = self.extract(tmp_path, REPEATABLE / "ontology.ttl", "-p", "skos:altLabel")
        done = fill(extract, tmp_path / "one.yml", {"Crossing": "", "Viaduct": ""}, "-neu")
        out = tmp_path / "out.ttl"
        result = run("localise", "merge", src, done, "--existing", "overwrite", "-o", out)
        assert result.exit_code == 1, result.output
        assert "Skipped (group): 3" in result.output
        assert f"Left unchanged: {BRIDGE} skos:altLabel @de: 2 of 3 entries" in result.output
        # The guide's example is this run's warning
        warning = next(line for line in result.output.splitlines() if "Left unchanged" in line)
        assert warning.strip() in GUIDE.read_text(encoding="utf-8")
        assert german(out, BRIDGE, ALT) == {"Span-de", "Crossing-de", "Viaduct-de"}
        # Building's group was whole and current, so it was replaced
        assert german(out, BUILDING, ALT) == {"Structure-neu", "Edifice-neu"}

    def test_a_stale_source_leaves_the_group_unchanged_at_exit_1(self, tmp_path: Path) -> None:
        src = self.preserved(tmp_path)
        extract = self.extract(tmp_path, REPEATABLE / "ontology.ttl", "-p", "skos:altLabel")
        extract.write_text(extract.read_text().replace("source: Span", "source: Old span"))
        done = fill(extract, tmp_path / "stale.yml", suffix="-neu")
        out = tmp_path / "out.ttl"
        result = run("localise", "merge", src, done, "--existing", "overwrite", "-o", out)
        assert result.exit_code == 1, result.output
        assert 'not in the ontology: "Old span"; not in the file: "Span"' in result.output
        assert "Skipped (group): 3" in result.output
        assert german(out, BRIDGE, ALT) == {"Span-de", "Crossing-de", "Viaduct-de"}

    def test_the_guard_applies_only_when_values_would_be_removed(self, tmp_path: Path) -> None:
        src = REPEATABLE / "ontology.ttl"
        extract = self.extract(tmp_path, src, "-p", "skos:altLabel")
        extract.write_text(extract.read_text().replace("source: Span", "source: Old span"))
        done = fill(extract, tmp_path / "stale.yml", {"Crossing": ""})
        out = tmp_path / "out.ttl"
        result = run("localise", "merge", src, done, "--existing", "overwrite", "-o", out)
        assert result.exit_code == 0, result.output
        assert "Added:           4" in result.output and "Skipped (status): 1" in result.output
        assert german(out, BRIDGE, ALT) == {"Old span-de", "Viaduct-de"}

    def test_a_group_split_across_blocks_and_spellings_is_one_group(self, tmp_path: Path) -> None:
        src = self.preserved(tmp_path)
        trans = merge_file(
            tmp_path,
            "de",
            """\
            entities:
            - uri: http://example.org/ont#Bridge
              labels:
              - {property: skos:altLabel, source: Span, translation: S, status: translated}
            - uri: http://example.org/ont#Bridge
              labels:
              - property: http://www.w3.org/2004/02/skos/core#altLabel
                source: Crossing
                translation: C
                status: translated
              - {property: skos:altLabel, source: Viaduct, translation: V, status: translated}
            """,
        )
        out = tmp_path / "out.ttl"
        result = run("localise", "merge", src, trans, "--existing", "overwrite", "-o", out)
        assert result.exit_code == 0, result.output
        assert "Updated:         3" in result.output
        assert german(out, BRIDGE, ALT) == {"S", "C", "V"}

    def test_default_properties_keep_both_comments(self, tmp_path: Path) -> None:
        src = REPEATABLE / "ontology.ttl"
        done = fill(self.extract(tmp_path, src), tmp_path / "done.yml")
        out = tmp_path / "out.ttl"
        result = run("localise", "merge", src, done, "--existing", "overwrite", "-o", out)
        assert result.exit_code == 0, result.output
        assert german(out, BRIDGE, COMMENT) == {"One.-de", "Two.-de"}

    def test_missing_only_offers_a_group_with_several_sources(self, tmp_path: Path) -> None:
        import yaml

        src = ttl(
            tmp_path,
            """
            ex:Bridge a owl:Class ;
                rdfs:comment "A crossing."@en, "Eine Querung."@de ;
                skos:altLabel "Span"@en, "Crossing"@en, "Viaduct"@en, "Bruecke"@de, "Steg"@de .
            """,
        )
        out = self.extract(tmp_path, src, "-p", "rdfs:comment,skos:altLabel", "--missing-only")
        data = yaml.safe_load(out.read_text(encoding="utf-8"))
        labels = data["entities"][0]["labels"]
        # The comment has one source value and a German one, so it is done, as before
        assert {label["source"] for label in labels} == {"Span", "Crossing", "Viaduct"}
        assert {label["property"] for label in labels} == {"skos:altLabel"}
        assert {label["notes"] for label in labels} == {'Already in de: "Bruecke", "Steg"'}
        # The guide's example is this file's entry
        assert 'notes: \'Already in de: "Bruecke", "Steg"\'' in out.read_text(encoding="utf-8")
        assert 'notes: \'Already in de: "Bruecke", "Steg"\'' in GUIDE.read_text(encoding="utf-8")

    def test_missing_only_still_skips_a_per_language_property(self, tmp_path: Path) -> None:
        src = ttl(tmp_path, 'ex:A a owl:Class ; rdfs:label "A"@en, "B"@en, "Ah"@de .')
        out = tmp_path / "de.yml"
        result = run(
            "localise", "extract", src, "-l", "de", "-p", "rdfs:label", "--missing-only",
            "-o", out,
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        assert "Strings:         0" in result.output

    def test_preserve_puts_a_reworded_translation_beside_the_old_one(self, tmp_path: Path) -> None:
        # Not P81's to change: P23's identical-text rule, so a reworded re-translation is added
        src = ttl(tmp_path, 'ex:A a owl:Class ; skos:altLabel "One"@en, "Two"@en, "Eins"@de .')
        extract = self.extract(tmp_path, src, "-p", "skos:altLabel")
        done = fill(extract, tmp_path / "done.yml", {"One": "Ein", "Two": "Zwei"})
        out = tmp_path / "out.ttl"
        result = run("localise", "merge", src, done, "-o", out)
        assert result.exit_code == 0 and "Added:           2" in result.output, result.output
        assert german(out, URIRef(EX + "A"), ALT) == {"Ein", "Eins", "Zwei"}

    @pytest.mark.parametrize("existing", ["preserve", "overwrite"])
    def test_a_per_language_property_merges_byte_for_byte_as_before(
        self, tmp_path: Path, existing: str
    ) -> None:
        out = tmp_path / "out.ttl"
        result = run(
            "localise", "merge", REPEATABLE / "per_language.ttl",
            REPEATABLE / "per_language_de.yml", "--existing", existing, "-o", out,
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        expected = REPEATABLE / f"per_language.{existing}.expected.ttl"
        assert out.read_bytes() == expected.read_bytes()

    def test_the_api_counts_and_notes(self, tmp_path: Path) -> None:
        from rdf_construct.localise import (
            ExistingStrategy,
            ExtractConfig,
            MergeConfig,
            StringExtractor,
            TranslationFile,
            TranslationMerger,
        )
        from rdf_construct.localise.formatters.markdown import MarkdownFormatter

        src = self.preserved(tmp_path)
        graph = Graph().parse(src)
        extract = self.extract(tmp_path, REPEATABLE / "ontology.ttl", "-p", "skos:altLabel")
        done = fill(extract, tmp_path / "one.yml", {"Span": ""}, "-neu")
        merger = TranslationMerger(MergeConfig(existing=ExistingStrategy.OVERWRITE))
        result = merger.merge(graph, TranslationFile.from_yaml(done))
        assert result.success
        assert (result.stats.updated, result.stats.skipped_group) == (2, 3)
        assert result.stats.total_processed == 5
        assert "| Skipped (group) | 3 |" in MarkdownFormatter().format_merge_result(result)

        config = ExtractConfig(
            target_language="de", properties=["skos:altLabel"], missing_only=True
        )
        file = StringExtractor(config).extract(graph, "x.ttl").translation_file
        assert file is not None
        notes = {label.notes for entity in file.entities for label in entity.labels}
        assert notes == {
            'Already in de: "Crossing-de", "Span-de", "Viaduct-de"',
            'Already in de: "Edifice-de", "Structure-de"',
        }
