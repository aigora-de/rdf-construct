"""Tests for how localise names a property (#355), and the renamed coverage count (#421).

- #355: ``--properties`` resolves a CURIE against the prefixes the ontology declares, plus rdf,
  rdfs, owl, xsd and xml; an unbound prefix is refused at exit 2 with nothing written. A
  translation file's ``property:`` and a configuration file's ``properties:`` are read against
  the file format's six prefixes, whatever ontology they meet: ``dc:`` there is Dublin Core
  elements. The reporter API resolves CURIEs as the CLI does.
- #421: ``LanguageCoverage.total_pairs`` counts entity and property pairs; ``total_strings`` is
  gone from it, and stays in a translation file's ``summary:``.

Every predicate in the fixtures carries a different literal, so a property resolved to the wrong
IRI extracts or merges the wrong text, or none, rather than passing by accident.
"""

import re
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner, Result
from rdflib import Graph, Literal, URIRef

from rdf_construct.cli import cli
from rdf_construct.core.utils import CurieError
from rdf_construct.localise import (
    LanguageCoverage,
    TranslationFile,
    extract_strings,
    generate_coverage_report,
)
from rdf_construct.localise.config import TranslationFileError
from rdf_construct.localise.properties import FILE_PREFIXES, shorten_property
from tests.test_cli_smoke import assert_no_crash, assert_wrote_nothing, snapshot

EX = "http://example.org/ont#"
DC_ELEMENTS = "http://purl.org/dc/elements/1.1/"
DC_TERMS = "http://purl.org/dc/terms/"
SKOS = "http://www.w3.org/2004/02/skos/core#"

# ex:note and <urn:x> each carry their own text; rdfs:label is never declared, being core
ONTOLOGY = """\
@prefix ex: <http://example.org/ont#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:A a owl:Class ;
    <http://www.w3.org/2000/01/rdf-schema#label> "Alpha"@en ;
    ex:note "hello"@en ;
    <urn:x> "urnval"@en .
"""

# dc: bound three ways; each file carries elements and terms titles with different text
DC_AS_ELEMENTS = f"""\
@prefix ex: <{EX}> .
@prefix dc: <{DC_ELEMENTS}> .
ex:A dc:title "elemtitle"@en ; <{DC_TERMS}title> "termtitle"@en .
"""
DC_AS_TERMS = f"""\
@prefix ex: <{EX}> .
@prefix dc: <{DC_TERMS}> .
ex:A dc:title "termtitle"@en ; <{DC_ELEMENTS}title> "elemtitle"@en .
"""
DC_UNBOUND = f"""\
@prefix ex: <{EX}> .
ex:A <{DC_ELEMENTS}title> "elemtitle"@en ; <{DC_TERMS}title> "termtitle"@en .
"""

# rdflib's own table binds org: to W3C ORG; the file's org: must win (#355, P10)
ORG = """\
@prefix org: <http://example.org/organisation#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
org:Team a owl:Class ; org:note "orgnote"@en .
"""

# SKOS written as full IRIs, with no skos: prefix
SKOS_UNBOUND = f"""\
@prefix ex: <{EX}> .
ex:A <{SKOS}prefLabel> "pref"@en ; <{SKOS}definition> "defn"@en .
"""


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


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def extracted(tmp_path: Path, source: Path, *args: str) -> list[tuple[str, str]]:
    """Run extract and return each entry's (property, source text)."""
    out = tmp_path / "de.yml"
    result = run("localise", "extract", source, "-l", "de", *args, "-o", out)
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    return [
        (label["property"], label["source"])
        for entity in data["entities"] or []
        for label in entity["labels"]
    ]


def translation_file(tmp_path: Path, *properties: str, name: str = "t.yml") -> Path:
    """A finished translation of ex:A, one entry per property, each translated "Übersetzt"."""
    data = {
        "metadata": {"source_language": "en", "target_language": "de"},
        "entities": [
            {
                "uri": f"{EX}A",
                "labels": [
                    {
                        "property": p,
                        "source": "s",
                        "translation": "Übersetzt",
                        "status": "translated",
                    }
                    for p in properties
                ],
            }
        ],
    }
    return write(tmp_path, name, yaml.safe_dump(data, allow_unicode=True))


def merged_predicates(path: Path) -> set[URIRef]:
    """The predicates that carry the merged German text."""
    graph = Graph()
    graph.parse(path)
    return {
        p
        for p, o in graph.predicate_objects(URIRef(f"{EX}A"))
        if isinstance(o, Literal) and o.language == "de"
    }


# ---------------------------------------------------------------------------
# #355: --properties reads the ontology's own prefixes
# ---------------------------------------------------------------------------


class TestPropertiesFlag:
    @pytest.mark.parametrize("config", [False, True], ids=["plain", "config"])
    @pytest.mark.parametrize(
        ("prop", "expected"),
        [
            ("ex:note", (f"{EX}note", "hello")),
            (f"<{EX}note>", (f"{EX}note", "hello")),
            (f"{EX}note", (f"{EX}note", "hello")),
            ("<urn:x>", ("urn:x", "urnval")),
            ("rdfs:label", ("rdfs:label", "Alpha")),
        ],
        ids=["declared", "bracketed", "full-iri", "bracketed-urn", "core"],
    )
    def test_extract_resolves(self, tmp_path, prop, expected, config):
        source = write(tmp_path, "o.ttl", ONTOLOGY)
        args = ["-p", prop]
        if config:
            args += ["-c", str(write(tmp_path, "c.yml", "localise:\n  properties: [rdfs:label]\n"))]
        assert extracted(tmp_path, source, *args) == [expected]

    @pytest.mark.parametrize("config", [False, True], ids=["plain", "config"])
    @pytest.mark.parametrize("prop", ["zz:note", "urn:x", "note", "rdfs:label,"])
    def test_extract_refuses_unbound(self, tmp_path, prop, config):
        source = write(tmp_path, "o.ttl", ONTOLOGY)
        args = ["-p", prop]
        if config:
            args += ["-c", str(write(tmp_path, "c.yml", "localise:\n  properties: [rdfs:label]\n"))]
        result = refused(tmp_path, "localise", "extract", source, "-l", "de", *args, "-o", "de.yml")
        assert "--properties: cannot resolve" in result.output
        assert "Prefixes bound: ex, owl, rdf, rdfs, xml, xsd." in result.output

    def test_refusal_leaves_a_finished_file_alone(self, tmp_path):
        # --overwrite would replace it; the refusal comes first, so nothing is replaced
        source = write(tmp_path, "o.ttl", ONTOLOGY)
        out = translation_file(tmp_path, "rdfs:label", name="de.yml")
        refused(
            tmp_path,
            "localise",
            "extract",
            source,
            "-l",
            "de",
            "-p",
            "zz:x",
            "-o",
            out,
            "--overwrite",
        )
        assert "Übersetzt" in out.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        ("ontology", "expected"),
        [
            (DC_AS_ELEMENTS, [("dc:title", "elemtitle")]),
            (DC_AS_TERMS, [("dcterms:title", "termtitle")]),
        ],
        ids=["elements", "terms"],
    )
    def test_dc_means_what_the_ontology_binds(self, tmp_path, ontology, expected):
        source = write(tmp_path, "o.ttl", ontology)
        assert extracted(tmp_path, source, "-p", "dc:title") == expected

    def test_dc_unbound_is_refused(self, tmp_path):
        source = write(tmp_path, "o.ttl", DC_UNBOUND)
        result = refused(tmp_path, "localise", "extract", source, "-l", "de", "-p", "dc:title")
        assert "prefix 'dc' is not bound" in result.output

    def test_the_files_prefix_beats_rdflibs_table(self, tmp_path):
        source = write(tmp_path, "o.ttl", ORG)
        assert extracted(tmp_path, source, "-p", "org:note") == [
            ("http://example.org/organisation#note", "orgnote")
        ]

    def test_report_resolves_and_names_with_the_ontologys_prefixes(self, tmp_path):
        # Only the terms title is in English, so reading dc: as elements leaves the base at 0/1
        source = write(
            tmp_path,
            "o.ttl",
            f"@prefix ex: <{EX}> .\n@prefix dc: <{DC_TERMS}> .\n"
            f'ex:A dc:title "termtitle"@en ; <{DC_ELEMENTS}title> "Elementtitel"@de .\n',
        )
        result = run("localise", "report", source, "-l", "de", "-p", "dc:title,ex:missing")
        assert result.exit_code == 0, result.output
        assert "Properties: dc:title, ex:missing" in result.output
        assert "Language   dc:title    ex:missing" in result.output
        # dc:title is the terms title, which the base language carries; no entity has ex:missing
        assert re.search(r"en \(base\)\s+1/1 \(100%\)\s+0/0 \(—\)", result.output), result.output

    def test_report_refuses_unbound(self, tmp_path):
        source = write(tmp_path, "o.ttl", ONTOLOGY)
        result = refused(tmp_path, "localise", "report", source, "-l", "de", "-p", "dc:title")
        assert "prefix 'dc' is not bound" in result.output


class TestApi:
    def test_report_resolves_curies(self, tmp_path):
        source = write(tmp_path, "o.ttl", ONTOLOGY)
        for props in (["rdfs:label"], ["ex:note"], [f"{EX}note"]):
            report = generate_coverage_report(source, ["de"], properties=props)
            assert report.total_entities == 1, props
            assert report.languages["en"].translated == 1, props

    def test_report_refuses_unbound(self, tmp_path):
        source = write(tmp_path, "o.ttl", ONTOLOGY)
        with pytest.raises(CurieError):
            generate_coverage_report(source, ["de"], properties=["zz:note"])

    def test_extract_resolves_against_the_file(self, tmp_path):
        source = write(tmp_path, "o.ttl", ORG)
        result = extract_strings(source, "de", properties=["org:note"])
        assert result.success and result.total_strings == 1

    def test_extract_fails_on_unbound(self, tmp_path):
        source = write(tmp_path, "o.ttl", ONTOLOGY)
        result = extract_strings(source, "de", properties=["zz:note"])
        assert not result.success
        assert "prefix 'zz' is not bound" in (result.error or "")


# ---------------------------------------------------------------------------
# #355: a YAML file's CURIEs are the file format's, never the ontology's
# ---------------------------------------------------------------------------


class TestTranslationFileProperties:
    @pytest.mark.parametrize(
        ("prop", "predicate"),
        [
            ("rdfs:label", "http://www.w3.org/2000/01/rdf-schema#label"),
            (f"{EX}note", f"{EX}note"),
            (f"<{EX}note>", f"{EX}note"),
            ("<urn:x>", "urn:x"),
            # dc: in a translation file is elements, even in an ontology that binds it to terms
            ("dc:title", f"{DC_ELEMENTS}title"),
            ("dcterms:title", f"{DC_TERMS}title"),
        ],
    )
    def test_merge_reads(self, tmp_path, prop, predicate):
        source = write(tmp_path, "o.ttl", DC_AS_TERMS)
        out = tmp_path / "out.ttl"
        result = run("localise", "merge", source, translation_file(tmp_path, prop), "-o", out)
        assert result.exit_code == 0, result.output
        assert merged_predicates(out) == {URIRef(predicate)}

    def test_merge_refuses_every_unresolvable_entry(self, tmp_path):
        # ex: is bound in the ontology; a translation file cannot borrow it
        source = write(tmp_path, "o.ttl", ONTOLOGY)
        trans = translation_file(tmp_path, "ex:note", "rdfs:label", "urn:x")
        result = refused(tmp_path, "localise", "merge", source, trans, "-o", "out.ttl")
        assert "2 values cannot be read" in result.output
        assert "property 'ex:note' is not an IRI or a CURIE" in result.output
        assert "property 'urn:x' is not an IRI or a CURIE" in result.output
        assert "(dc, dcterms, owl, rdf, rdfs, skos)" in result.output

    def test_from_yaml_refuses(self, tmp_path):
        with pytest.raises(TranslationFileError, match="'zz:note'"):
            TranslationFile.from_yaml(translation_file(tmp_path, "zz:note"))

    def test_round_trip_of_a_declared_prefix(self, tmp_path):
        source = write(tmp_path, "o.ttl", ORG)
        strings = tmp_path / "de.yml"
        result = run("localise", "extract", source, "-l", "de", "-p", "org:note", "-o", strings)
        assert result.exit_code == 0, result.output
        data = yaml.safe_load(strings.read_text(encoding="utf-8"))
        assert data["metadata"]["properties"] == ["http://example.org/organisation#note"]
        assert data["summary"]["total_strings"] == 1  # file format, not #421's field
        for entity in data["entities"]:
            for label in entity["labels"]:
                label["translation"], label["status"] = "Notiz", "translated"
        strings.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        out = tmp_path / "out.ttl"
        result = run("localise", "merge", source, strings, "-o", out)
        assert result.exit_code == 0, result.output
        text = out.read_text(encoding="utf-8")
        assert '"Notiz"@de' in text
        # The destination graph binds only the core prefixes, so the file's org: survives
        assert "@prefix org: <http://example.org/organisation#>" in text
        assert "org1:" not in text


class TestConfigProperties:
    def test_six_prefixes_whatever_the_ontology_declares(self, tmp_path):
        source = write(tmp_path, "o.ttl", SKOS_UNBOUND)
        config = write(
            tmp_path, "c.yml", "localise:\n  properties: [skos:prefLabel, skos:definition]\n"
        )
        assert extracted(tmp_path, source, "-c", str(config)) == [
            ("skos:prefLabel", "pref"),
            ("skos:definition", "defn"),
        ]

    def test_full_iri(self, tmp_path):
        source = write(tmp_path, "o.ttl", ONTOLOGY)
        config = write(tmp_path, "c.yml", f"localise:\n  properties: ['{EX}note', '<urn:x>']\n")
        assert extracted(tmp_path, source, "-c", str(config)) == [
            (f"{EX}note", "hello"),
            ("urn:x", "urnval"),
        ]

    def test_refuses_any_other_curie(self, tmp_path):
        source = write(tmp_path, "o.ttl", ONTOLOGY)
        config = write(tmp_path, "c.yml", "localise:\n  properties: [rdfs:label, ex:note]\n")
        result = refused(
            tmp_path, "localise", "extract", source, "-l", "de", "-c", config, "-o", "de.yml"
        )
        assert "properties item 2 'ex:note' is not an IRI or a CURIE" in result.output


class TestShorten:
    def test_longest_namespace_wins(self):
        prefixes = {"base": "http://example.org/", "ex": EX}
        assert shorten_property(prefixes, f"{EX}note") == "ex:note"

    def test_never_invents_a_prefix(self):
        assert shorten_property({"ex": EX}, "http://other.org/x") == "http://other.org/x"

    def test_returns_text_for_a_uriref(self):
        name = shorten_property({}, URIRef("urn:x"))
        assert isinstance(name, str) and not isinstance(name, URIRef)

    def test_local_part_with_a_delimiter_stays_an_iri(self):
        assert shorten_property({"base": "http://example.org/"}, f"{EX}note") == f"{EX}note"

    def test_file_prefixes_are_the_six(self):
        assert FILE_PREFIXES["dc"] == DC_ELEMENTS
        assert sorted(FILE_PREFIXES) == ["dc", "dcterms", "owl", "rdf", "rdfs", "skos"]


# ---------------------------------------------------------------------------
# #421: the coverage count is named for what it counts
# ---------------------------------------------------------------------------


class TestTotalPairs:
    def test_counts_pairs(self, tmp_path):
        source = write(tmp_path, "o.ttl", ONTOLOGY)
        report = generate_coverage_report(source, ["de"], properties=["rdfs:label", "ex:note"])
        coverage = report.languages["en"]
        assert coverage.total_pairs == 2
        assert coverage.pending == 0 and coverage.coverage == 100.0
        assert report.languages["de"].pending == 2

    def test_old_name_is_gone(self):
        assert not hasattr(LanguageCoverage(language="de"), "total_strings")
