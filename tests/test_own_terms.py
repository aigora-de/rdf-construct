"""One answer to "this ontology's own terms", for lint, docs and stats (#69, #368, #371, #209).

`core.ownership` decides which terms a file may call its own: a borrowed vocabulary's term (one in
a namespace none of the file's ontologies owns) or one in an allow-listed namespace is foreign.
`lint` skips foreign terms in `dangling-reference`, `missing-label` and `missing-comment`, and
`dangling-reference` keeps #69's threshold of two or more definitions in a namespace, or a term
within the file's own ontology IRI. `docs` gives a foreign class or property no page, and shows
the derivation stamp as "Derived from". `stats` leaves foreign terms out of every count.

Findings are asserted by rule and term IRI. `lint --format json` crashes (#201), so the IRIs come
from `LintEngine` run with the same config, and the CLI is asserted for exit codes and refusals.
Every fixture is written into `tmp_path`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import Graph, URIRef
from rdflib.namespace import PROV

from rdf_construct.cli import cli
from rdf_construct.core import preserve_literal_forms
from rdf_construct.core.ownership import Ownership, ontology_references, ownership
from rdf_construct.lint import LintEngine
from rdf_construct.lint.config import create_default_config, load_lint_config
from rdf_construct.lint.engine import LintConfig
from tests.test_cli_smoke import assert_no_crash

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "examples"
IES = ROOT / "tests" / "fixtures" / "ies"

IES_COMMON = "http://informationexchangestandard.org/ont/ies/common/"
IES_ENV = "http://informationexchangestandard.org/ont/ies/env/"
STAMP = str(PROV.wasDerivedFrom)

PREFIXES = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
"""


def _write(tmp_path: Path, name: str, body: str, prefixes: str = PREFIXES) -> Path:
    path = tmp_path / name
    path.write_text(prefixes + body)
    return path


def _run(*argv: object) -> Result:
    result = CliRunner().invoke(cli, [str(a) for a in argv])
    assert_no_crash(result)
    return result


def _findings(path: Path, config: Path | None = None) -> set[tuple[str, str]]:
    """Every finding as (rule, term IRI), with the config the CLI would use."""
    lint_config = load_lint_config(config) if config else LintConfig()
    result = LintEngine(lint_config).lint_file(path)
    return {(i.rule_id, str(i.entity)) for i in result.issues if i.entity is not None}


def _on(findings: set[tuple[str, str]], term: str) -> set[str]:
    """The rules that fired on one term."""
    return {rule for rule, entity in findings if entity == term}


def _dangling(findings: set[tuple[str, str]]) -> set[str]:
    return {entity for rule, entity in findings if rule == "dangling-reference"}


def _stats_json(path: Path) -> dict:
    result = _run("stats", path, "--format", "json")
    assert result.exit_code == 0, result.output
    return json.loads(result.output[result.output.index("{") :])


# ---------------------------------------------------------------------------
# core.ownership
# ---------------------------------------------------------------------------


class TestOwnership:
    def test_a_vocabulary_on_another_host_is_foreign(self) -> None:
        owned = Ownership(ontologies=(URIRef("http://example.org/lib"),))
        assert owned.is_foreign(PROV.wasDerivedFrom)
        assert owned.is_foreign(URIRef("http://purl.org/dc/terms/creator"))
        assert not owned.is_foreign(URIRef("http://example.org/lib#Book"))
        assert not owned.is_foreign(URIRef("http://example.org/other#Thing"))  # same host

    def test_on_a_shared_host_only_the_ontology_iris_own_space_is_owned(self) -> None:
        owned = Ownership(ontologies=(URIRef("http://purl.org/myont"),))
        assert not owned.is_foreign(URIRef("http://purl.org/myont#A"))
        assert owned.is_foreign(URIRef("http://purl.org/dc/terms/title"))
        assert owned.is_foreign(URIRef("http://purl.org/myontology#A"))  # the boundary

    def test_a_file_with_no_named_header_borrows_nothing(self) -> None:
        assert not Ownership().is_foreign(PROV.wasDerivedFrom)

    def test_an_external_namespace_is_matched_at_a_boundary(self) -> None:
        owned = Ownership(external=("http://example.org/ont",))
        assert owned.is_foreign(URIRef("http://example.org/ont#X"))
        assert owned.is_foreign(URIRef("http://example.org/ont/sub#Y"))
        assert not owned.is_foreign(URIRef("http://example.org/ontology#X"))

    def test_ontology_references_name_ontologies_not_terms(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "refs.ttl",
            """\
<http://e.org/o> a owl:Ontology ;
    owl:versionIRI <http://e.org/o/2.0> ; owl:priorVersion <http://e.org/o/1.0> ;
    owl:imports <http://e.org/base> ; prov:wasDerivedFrom <http://e.org/src> .
<http://e.org/o#x> prov:wasDerivedFrom <http://e.org/o#y> .
""",
        )
        graph = Graph().parse(path)
        refs = {str(r) for r in ontology_references(graph)}
        assert refs == {
            "http://e.org/o/2.0",
            "http://e.org/o/1.0",
            "http://e.org/base",
            "http://e.org/src",
            "http://www.w3.org/2002/07/owl#Ontology",  # the header's type, a built-in
        }
        assert ownership(graph).ontologies == (URIRef("http://e.org/o"),)

    def test_a_namespace_the_file_describes_is_its_own_whatever_the_host(
        self, tmp_path: Path
    ) -> None:
        # Review finding 1: terms off the header's IRI on a shared host, PROV-O's own pattern
        path = _write(
            tmp_path,
            "w3id.ttl",
            """\
@prefix ex: <https://w3id.org/myont/> .
<https://w3id.org/myont/ontology> a owl:Ontology ; rdfs:label "My ontology" .
ex:A a owl:Class ; rdfs:label "A" .
ex:B a owl:Class ; rdfs:subClassOf ex:A, ex:Typo .
""",
        )
        owned = ownership(Graph().parse(path))
        assert not owned.is_foreign(URIRef("https://w3id.org/myont/A"))
        findings = _findings(path)
        assert "https://w3id.org/myont/Typo" in _dangling(findings)
        assert "missing-comment" in _on(findings, "https://w3id.org/myont/A")
        assert _stats_json(path)["basic"]["classes"] == 2

    def test_declarations_alone_describe_nothing(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "decl.ttl",
            """\
<http://example.org/x> a owl:Ontology ; dcterms:creator "D" ; dcterms:title "X" .
dcterms:creator a owl:AnnotationProperty .
dcterms:title a owl:AnnotationProperty .
""",
        )
        owned = ownership(Graph().parse(path))
        assert owned.is_foreign(URIRef("http://purl.org/dc/terms/creator"))

    def test_describing_two_terms_of_a_vocabulary_claims_it(self, tmp_path: Path) -> None:
        # The ruled trade-off: a file that describes two PROV terms owns prov:, stamp included
        path = _write(
            tmp_path,
            "prov.ttl",
            """\
<http://example.org/x> a owl:Ontology ; rdfs:label "X" .
prov:Entity a owl:Class ; rdfs:label "Entity" .
prov:used a owl:ObjectProperty ; rdfs:label "used" .
prov:wasDerivedFrom a owl:AnnotationProperty .
""",
        )
        owned = ownership(Graph().parse(path))
        assert not owned.is_foreign(PROV.wasDerivedFrom)

    def test_split_still_imports_is_borrowed(self) -> None:
        from rdf_construct.core.ownership import is_borrowed as moved
        from rdf_construct.merge.splitter import is_borrowed

        assert is_borrowed is moved


# ---------------------------------------------------------------------------
# lint: dangling-reference (#69, #209)
# ---------------------------------------------------------------------------

B = "@prefix b: <https://example.org/> .\n"


class TestDanglingReference:
    def test_issue_69_clean_is_clean(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path, "clean.ttl", "<https://example.org/instance/a> a b:SomeClass .\n", B
        )
        result = _run("lint", path)
        assert result.exit_code == 0
        assert _findings(path) == set()

    def test_issue_69_one_bare_base_node_claims_nothing(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "triggered.ttl",
            "<https://example.org/instance/a> a b:SomeClass .\n"
            "<https://example.org/registry> a b:SomeClass .\n",
            B,
        )
        result = _run("lint", path)
        assert result.exit_code == 0, result.output
        assert "dangling-reference" not in result.output
        assert _findings(path) == set()

    def test_two_definitions_claim_the_namespace(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "owned.ttl",
            """\
<https://example.org/registry> a b:SomeClass .
<https://example.org/Other> a owl:Class ; rdfs:label "O" ; rdfs:comment "O." .
<https://example.org/Child> a owl:Class ; rdfs:label "C" ; rdfs:comment "C." ;
    rdfs:subClassOf <https://example.org/Typo> .
""",
            B + PREFIXES,
        )
        result = _run("lint", path)
        assert result.exit_code == 1
        assert _dangling(_findings(path)) == {
            "https://example.org/SomeClass",
            "https://example.org/Typo",
        }

    def test_the_headers_own_space_is_checked_whatever_the_count(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "oneclass.ttl",
            """\
<http://example.org/o> a owl:Ontology ; rdfs:label "O" ; owl:versionIRI <http://example.org/o/1.0> .
<http://example.org/o#A> a owl:Class ; rdfs:subClassOf <http://example.org/o#Typo> .
""",
        )
        assert _dangling(_findings(path)) == {"http://example.org/o#Typo"}

    def test_imports_targets_are_not_term_references(self, tmp_path: Path) -> None:
        # #209's domain.ttl: the import target was reported as an undefined entity
        path = _write(
            tmp_path,
            "domain.ttl",
            """\
<https://example.org/domain> a owl:Ontology ; rdfs:label "D" ;
    owl:imports <https://example.org/foundation> .
<https://example.org/instance/a> a b:SomeClass .
<https://example.org/registry> a b:SomeClass .
""",
            B + PREFIXES,
        )
        dangling = _dangling(_findings(path))
        assert "https://example.org/foundation" not in dangling
        # The two definitions still claim the namespace: the imported class is still reported,
        # because lint does not resolve imports (#309)
        assert dangling == {"https://example.org/SomeClass"}

    def test_header_metadata_links_are_not_term_references(self, tmp_path: Path) -> None:
        # Review finding 2: clean on the base, and must stay clean
        path = _write(
            tmp_path,
            "seealso.ttl",
            """\
@prefix v: <http://example.org/vocab#> .
<http://example.org/ont> a owl:Ontology ; rdfs:label "O" ;
    rdfs:seeAlso <http://example.org/ont/spec.html> ;
    dcterms:hasVersion <http://example.org/ont/2.0> .
v:A a owl:Class ; rdfs:label "A" ; rdfs:comment "a" .
v:B a owl:Class ; rdfs:label "B" ; rdfs:comment "b" ; rdfs:subClassOf v:A .
""",
        )
        assert _dangling(_findings(path)) == set()
        assert _run("lint", path).exit_code == 0

    def test_a_borrowed_namespace_is_never_checked(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "borrowed.ttl",
            """\
<http://example.org/x> a owl:Ontology ; rdfs:label "X" ;
    dcterms:creator "Dave" ; dcterms:title "X" ; dcterms:modified "2026" .
dcterms:creator a owl:AnnotationProperty .
dcterms:title a owl:AnnotationProperty .
""",
        )
        assert _findings(path) == set()


class TestIesFixture:
    """#69's realistic test case, as corrected at Stop 1 (#69 decision of 2026-11-06)."""

    SOURCE = IES / "ies-env-building.ttl"

    def test_without_config_only_the_version_iri_clears(self, tmp_path: Path) -> None:
        dangling = _dangling(_findings(self.SOURCE))
        assert f"{IES_ENV}0.1.0-rc1" not in dangling
        assert len(dangling) == 55
        assert {f"{IES_ENV}AssetState", f"{IES_ENV}ClassOfAssetState"} <= dangling
        assert f"{IES_COMMON}Flow" in dangling

    def test_an_ies_allow_list_keeps_exactly_the_undefined_env_terms(self, tmp_path: Path) -> None:
        config = tmp_path / ".rdf-lint.yml"
        config.write_text("external_namespaces:\n  - ies:\n")
        assert _dangling(_findings(self.SOURCE, config)) == {
            f"{IES_ENV}AssetState",
            f"{IES_ENV}ClassOfAssetState",
        }
        result = _run("lint", self.SOURCE, "-c", config)
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# lint: missing-label / missing-comment (#368)
# ---------------------------------------------------------------------------


class TestDocumentationRules:
    def test_declared_vocabulary_terms_are_not_this_files_to_document(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "dc.ttl",
            """\
<http://example.org/x> a owl:Ontology ; rdfs:label "X" ; dcterms:creator "Dave" ; dcterms:title "X" .
dcterms:creator a owl:AnnotationProperty .
dcterms:title a owl:AnnotationProperty .
<http://example.org/x#A> a owl:Class ; rdfs:label "A"@en ; rdfs:comment "An A."@en ;
    rdfs:subClassOf owl:Thing .
""",
        )
        findings = _findings(path)
        assert _on(findings, "http://purl.org/dc/terms/creator") == set()
        assert _on(findings, "http://purl.org/dc/terms/title") == set()
        result = _run("lint", path, "--level", "strict")
        assert result.exit_code == 0, result.output

    def test_the_files_own_undocumented_terms_still_warn(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "bare.ttl",
            """\
<http://example.org/bare> a owl:Ontology ; rdfs:label "Bare" .
<http://example.org/bare#A> a owl:Class .
<http://example.org/elsewhere#B> a owl:Class .
""",
        )
        findings = _findings(path)
        assert _on(findings, "http://example.org/bare#A") >= {"missing-label", "missing-comment"}
        # Another namespace on the ontology's own host is still its own
        assert _on(findings, "http://example.org/elsewhere#B") >= {
            "missing-label",
            "missing-comment",
        }

    def test_a_urn_ontology_owns_its_urn_terms(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "urn.ttl",
            """\
<urn:example:zoo> a owl:Ontology ; rdfs:label "Zoo" .
<urn:example:Cat> a owl:Class .
""",
        )
        assert _on(_findings(path), "urn:example:Cat") >= {"missing-label", "missing-comment"}

    def test_an_external_namespace_applies_to_the_documentation_rules(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "ext.ttl",
            """\
<http://example.org/thing#A> a owl:Class .
<http://example.org/thing#B> a owl:Class .
""",
        )
        config = tmp_path / ".rdf-lint.yml"
        config.write_text("external_namespaces:\n  - http://example.org/thing#\n")
        assert {rule for rule, _ in _findings(path, config)} <= {"orphan-class"}
        assert {rule for rule, _ in _findings(path)} >= {"missing-label", "missing-comment"}


# ---------------------------------------------------------------------------
# lint: the allow-list
# ---------------------------------------------------------------------------


class TestAllowList:
    SOURCE = """\
@prefix ex: <http://example.org/ont#> .
<http://example.org/ont> a owl:Ontology ; rdfs:label "O" .
ex:A a owl:Class ; rdfs:label "A" ; rdfs:comment "A." ; rdfs:subClassOf ex:Missing .
<http://example.org/ontology#C> a owl:Class ; rdfs:label "C" ; rdfs:comment "C." ;
    rdfs:subClassOf <http://example.org/ontology#Gone> .
<http://example.org/ontology#D> a owl:Class ; rdfs:label "D" ; rdfs:comment "D." .
"""

    def _source(self, tmp_path: Path) -> Path:
        return _write(tmp_path, "ont.ttl", self.SOURCE)

    def test_a_curie_resolves_against_the_files_prefixes(self, tmp_path: Path) -> None:
        config = tmp_path / ".rdf-lint.yml"
        config.write_text("external_namespaces:\n  - ex:\n")
        dangling = _dangling(_findings(self._source(tmp_path), config))
        assert dangling == {"http://example.org/ontology#Gone"}

    def test_an_entry_is_matched_at_a_boundary(self, tmp_path: Path) -> None:
        # `…/ont` takes `…/ont#Missing` but not `…/ontology#Gone`
        config = tmp_path / ".rdf-lint.yml"
        config.write_text("external_namespaces:\n  - <http://example.org/ont>\n")
        dangling = _dangling(_findings(self._source(tmp_path), config))
        assert dangling == {"http://example.org/ontology#Gone"}

    def test_without_an_entry_both_are_reported(self, tmp_path: Path) -> None:
        assert _dangling(_findings(self._source(tmp_path))) == {
            "http://example.org/ont#Missing",
            "http://example.org/ontology#Gone",
        }

    def test_an_unbound_prefix_is_refused_naming_the_file(self, tmp_path: Path) -> None:
        source = self._source(tmp_path)
        config = tmp_path / ".rdf-lint.yml"
        config.write_text("external_namespaces:\n  - nope:\n")
        result = _run("lint", source, "-c", config)
        assert result.exit_code == 2
        assert "nope" in result.output and str(source) in result.output
        assert "dangling-reference" not in result.output

    def test_a_prefix_one_file_binds_and_another_does_not_is_refused(self, tmp_path: Path) -> None:
        first = self._source(tmp_path)
        second = _write(tmp_path, "other.ttl", "<http://example.org/z> a owl:Class .\n")
        config = tmp_path / ".rdf-lint.yml"
        config.write_text("external_namespaces:\n  - ex:\n")
        result = _run("lint", first, second, "-c", config)
        assert result.exit_code == 2
        assert str(second) in result.output
        assert "dangling-reference" not in result.output

    @pytest.mark.parametrize(
        ("value", "message"),
        [
            ('"ies:"', "must be a list"),
            ("[3]", "must be a non-empty string"),
            ('[""]', "must be a non-empty string"),
            ('["  "]', "must be a non-empty string"),
            ('["not a curie"]', "is not a namespace IRI"),
            ("[ies]", "is not a namespace IRI"),
        ],
    )
    def test_a_malformed_entry_is_refused_before_any_file_is_read(
        self, tmp_path: Path, value: str, message: str
    ) -> None:
        config = tmp_path / ".rdf-lint.yml"
        config.write_text(f"external_namespaces: {value}\n")
        source = _write(tmp_path, "unread.ttl", "this is not Turtle\n", "")
        result = _run("lint", source, "-c", config)
        assert result.exit_code == 2
        assert "external_namespaces" in result.output
        assert message in result.output
        assert "could not be parsed" not in result.output  # refused before the file was read

    def test_the_init_template_shows_the_key(self) -> None:
        assert "# external_namespaces:" in create_default_config()


# ---------------------------------------------------------------------------
# The stamp's producers, through lint, docs and stats (#368, #371)
# ---------------------------------------------------------------------------

SPLIT_SOURCE = """\
@prefix a: <http://example.org/ont/a#> .
@prefix b: <http://example.org/ont/b#> .
<http://example.org/ont> a owl:Ontology ; rdfs:label "Ont" ; owl:versionIRI <http://example.org/ont/1.0.0> .
a:A a owl:Class ; rdfs:label "A" ; rdfs:comment "An A." .
a:A2 a owl:Class ; rdfs:label "A2" ; rdfs:comment "An A2." ; rdfs:subClassOf a:A .
b:B a owl:Class ; rdfs:label "B" ; rdfs:comment "A B." ; rdfs:subClassOf a:A .
b:B2 a owl:Class ; rdfs:label "B2" ; rdfs:comment "A B2." ; rdfs:subClassOf b:B .
"""


def _order_extract(tmp_path: Path) -> Path:
    out = tmp_path / "order"
    result = _run(
        "order",
        EXAMPLES / "order" / "library.ttl",
        EXAMPLES / "order" / "ordering.yml",
        "-p",
        "classes-only",
        "-o",
        out,
    )
    assert result.exit_code == 0, result.output
    return out / "library-classes-only.ttl"


def _split_module(tmp_path: Path) -> Path:
    source = _write(tmp_path, "monolith.ttl", SPLIT_SOURCE)
    out = tmp_path / "split"
    result = _run("split", source, "--by-namespace", "-o", out)
    assert result.exit_code == 0, result.output
    return out / "b.ttl"


def _named_merge(tmp_path: Path) -> Path:
    out = tmp_path / "merged.ttl"
    result = _run(
        "merge",
        EXAMPLES / "merge" / "merge_core.ttl",
        EXAMPLES / "merge" / "merge_extension.ttl",
        "--ontology-iri",
        "http://example.org/merged",
        "-o",
        out,
    )
    assert result.exit_code == 0, result.output
    return out


PRODUCERS = {"order": _order_extract, "split": _split_module, "merge": _named_merge}


@pytest.mark.parametrize("producer", sorted(PRODUCERS))
class TestStampProducers:
    def _derived(self, tmp_path: Path, producer: str) -> Path:
        path = PRODUCERS[producer](tmp_path)
        with preserve_literal_forms():
            graph = Graph().parse(path)
        assert (PROV.wasDerivedFrom, None, None) in graph  # the stamp is there
        return path

    def test_lint_does_not_ask_to_document_the_stamp(self, tmp_path: Path, producer: str) -> None:
        path = self._derived(tmp_path, producer)
        findings = _findings(path)
        assert _on(findings, STAMP) == set()
        with preserve_literal_forms():
            graph = Graph().parse(path)
        targets = {str(o) for o in graph.objects(None, PROV.wasDerivedFrom)}
        assert not targets & _dangling(findings)  # the stamp's targets are not term references

    def test_docs_gives_the_stamp_no_page_and_shows_the_derivation(
        self, tmp_path: Path, producer: str
    ) -> None:
        path = self._derived(tmp_path, producer)
        site = tmp_path / "site"
        result = _run("docs", path, "-o", site)
        assert result.exit_code == 0, result.output
        assert not (site / "properties" / "annotation" / "wasDerivedFrom.html").exists()
        index = (site / "index.html").read_text()
        assert "Derived from:" in index
        assert "wasDerivedFrom" not in index
        search = (site / "search.json").read_text() if (site / "search.json").exists() else ""
        assert "wasDerivedFrom" not in search

    def test_docs_json_carries_derived_from(self, tmp_path: Path, producer: str) -> None:
        path = self._derived(tmp_path, producer)
        site = tmp_path / "site"
        assert _run("docs", path, "-o", site, "--format", "json").exit_code == 0
        data = json.loads((site / "index.json").read_text())
        with preserve_literal_forms():
            graph = Graph().parse(path)
        header_targets = sorted({str(o) for o in graph.objects(None, PROV.wasDerivedFrom)})
        assert data["ontology"]["derived_from"] == header_targets
        assert data["statistics"]["annotation_properties"] == 0
        assert data["annotation_properties"] == []

    def test_docs_markdown_shows_the_derivation(self, tmp_path: Path, producer: str) -> None:
        path = self._derived(tmp_path, producer)
        site = tmp_path / "site"
        assert _run("docs", path, "-o", site, "--format", "markdown").exit_code == 0
        assert "**Derived from:**" in (site / "index.md").read_text()
        assert not list(site.rglob("wasDerivedFrom*"))

    def test_stats_does_not_count_the_stamp(self, tmp_path: Path, producer: str) -> None:
        path = self._derived(tmp_path, producer)
        text = _run("stats", path).output
        assert "Annotation Properties:    0" in text
        data = _stats_json(path)
        assert data["basic"]["annotation_properties"] == 0


class TestMustStay:
    def test_classes_only_still_reports_lib_publishes(self, tmp_path: Path) -> None:
        # A true finding: the extract dropped a property its classes still reference
        path = _order_extract(tmp_path)
        assert "http://example.org/library#publishes" in _dangling(_findings(path))
        assert _run("lint", path).exit_code == 1


# ---------------------------------------------------------------------------
# docs (#371)
# ---------------------------------------------------------------------------


class TestDocs:
    SOURCE = """\
@prefix ex: <http://example.org/lib#> .
<http://example.org/lib> a owl:Ontology ; rdfs:label "Lib" ; prov:wasDerivedFrom <http://example.org/up> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
prov:wasDerivedFrom a owl:AnnotationProperty ; rdfs:label "was derived from" .
foaf:maker a owl:ObjectProperty ; rdfs:domain ex:Book .
ex:Book a owl:Class ; rdfs:label "Book" ; rdfs:comment "A book." .
ex:title a owl:DatatypeProperty ; rdfs:label "title" ; rdfs:domain ex:Book .
"""

    def test_a_labelled_foreign_term_still_gets_no_page(self, tmp_path: Path) -> None:
        # A source that labels prov:wasDerivedFrom itself is treated as its extract is
        path = _write(tmp_path, "lib.ttl", self.SOURCE)
        site = tmp_path / "site"
        assert _run("docs", path, "-o", site).exit_code == 0
        pages = {p.relative_to(site).as_posix() for p in site.rglob("*.html")}
        assert "classes/Book.html" in pages
        assert "properties/datatype/title.html" in pages
        assert not [p for p in pages if "wasDerivedFrom" in p or "maker" in p]

    def test_a_class_page_does_not_link_a_foreign_property(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "lib.ttl", self.SOURCE)
        site = tmp_path / "site"
        assert _run("docs", path, "-o", site).exit_code == 0
        book = (site / "classes" / "Book.html").read_text()
        assert "title" in book
        assert "maker" not in book

    def test_a_foreign_class_gets_no_page(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "geo.ttl",
            """\
@prefix geo: <http://www.opengis.net/ont/geosparql#> .
<http://example.org/lib> a owl:Ontology ; rdfs:label "Lib" .
geo:Geometry a rdfs:Class ; rdfs:label "Geometry" .
<http://example.org/lib#Shape> a owl:Class ; rdfs:label "Shape" ; rdfs:subClassOf geo:Geometry .
""",
        )
        site = tmp_path / "site"
        assert _run("docs", path, "-o", site).exit_code == 0
        pages = {p.relative_to(site).as_posix() for p in site.rglob("*.html")}
        assert "classes/Shape.html" in pages
        assert "classes/Geometry.html" not in pages

    def test_html_derived_from_names_the_target(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "lib.ttl", self.SOURCE)
        site = tmp_path / "site"
        assert _run("docs", path, "-o", site).exit_code == 0
        index = (site / "index.html").read_text()
        assert "<code>http://example.org/up</code>" in index


# ---------------------------------------------------------------------------
# stats (#371)
# ---------------------------------------------------------------------------


class TestStats:
    def test_foreign_terms_are_in_no_count(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "lib.ttl", TestDocs.SOURCE)
        data = _stats_json(path)
        assert data["basic"]["classes"] == 1
        assert data["basic"]["object_properties"] == 0
        assert data["basic"]["datatype_properties"] == 1
        assert data["basic"]["annotation_properties"] == 0
        # A foreign property is not moved into another bucket
        assert data["basic"]["individuals"] == 0
        assert data["documentation"]["properties_labelled"] == 1
        assert data["documentation"]["properties_labelled_pct"] == 1.0

    def test_a_foreign_property_connects_nothing(self, tmp_path: Path) -> None:
        # Review finding 3: connectivity and complexity counted it through its domain and range
        path = _write(
            tmp_path,
            "conn.ttl",
            """\
<http://example.org/ont> a owl:Ontology ; rdfs:label "O" .
<http://example.org/ont#A> a owl:Class .
prov:used a owl:ObjectProperty ; rdfs:domain <http://example.org/ont#A> ;
    rdfs:range <http://example.org/ont#A> .
""",
        )
        data = _stats_json(path)
        assert data["complexity"]["avg_properties_per_class"] == 0
        assert data["connectivity"]["most_connected_class"] is None
        assert data["connectivity"]["isolated_classes"] == 1

    def test_a_foreign_class_is_not_an_individual(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "geo.ttl",
            """\
@prefix geo: <http://www.opengis.net/ont/geosparql#> .
<http://example.org/lib> a owl:Ontology ; rdfs:label "Lib" .
geo:Geometry a rdfs:Class .
<http://example.org/lib#Shape> a owl:Class ; rdfs:subClassOf geo:Geometry .
""",
        )
        data = _stats_json(path)
        assert data["basic"]["classes"] == 1
        assert data["basic"]["individuals"] == 0


# ---------------------------------------------------------------------------
# LINT_GUIDE.md's worked example runs as written
# ---------------------------------------------------------------------------

GUIDE = ROOT / "docs" / "user_guides" / "LINT_GUIDE.md"


def _blocks(text: str, language: str) -> list[str]:
    """The bodies of a section's fenced blocks in one language, in order."""
    fence = f"```{language}\n"
    bodies = []
    rest = text
    while fence in rest:
        rest = rest[rest.index(fence) + len(fence) :]
        bodies.append(rest[: rest.index("```")])
        rest = rest[rest.index("```") + 3 :]
    return bodies


class TestGuideWorkedExample:
    def test_every_command_prints_what_the_guide_shows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        guide = GUIDE.read_text(encoding="utf-8")
        section = guide[guide.index("### A worked example") : guide.index("### Known limitations")]
        (turtle,) = _blocks(section, "turtle")
        (yaml_text,) = _blocks(section, "yaml")
        commands = _blocks(section, "bash")
        outputs = _blocks(section, "text")
        assert len(commands) == len(outputs) == 2

        (tmp_path / "domain.ttl").write_text(turtle)
        (tmp_path / "external.yml").write_text(yaml_text)
        monkeypatch.chdir(tmp_path)
        for command, shown in zip(commands, outputs, strict=True):
            argv = command.strip().split()
            assert argv[0] == "rdf-construct"
            result = _run(*argv[1:])
            assert result.exit_code == 1
            assert result.output.strip() == shown.strip(), command
