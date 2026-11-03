"""Lint shared vocabulary types and distinguish an unparsed source from findings."""

from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import RDF, RDFS, BNode, Graph, Namespace, URIRef
from rdflib.namespace import OWL

from rdf_construct.cli import _lint_exit_code, cli
from rdf_construct.lint import LintEngine, LintIssue, LintResult, LintSummary, Severity
from rdf_construct.lint.rules import get_classes, get_object_properties, get_properties

EX = Namespace("http://example.org/o#")
PROPERTY_TYPES = [
    RDF.Property,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    OWL.AnnotationProperty,
    OWL.TransitiveProperty,
    OWL.SymmetricProperty,
    OWL.AsymmetricProperty,
    OWL.ReflexiveProperty,
    OWL.IrreflexiveProperty,
    OWL.InverseFunctionalProperty,
    OWL.FunctionalProperty,
    OWL.DeprecatedProperty,
]


@pytest.mark.parametrize("property_type", PROPERTY_TYPES, ids=lambda uri: uri.split("#")[-1])
def test_property_types_are_linted_and_not_reported_as_untyped(property_type: URIRef) -> None:
    graph = Graph()
    graph.add((EX.hasValue, RDF.type, property_type))
    graph.add((EX.hasValue, RDFS.domain, OWL.Thing))
    graph.add((EX.hasValue, RDFS.range, RDFS.Resource))

    result = LintEngine().lint_graph(graph)
    rules = {issue.rule_id for issue in result.issues if issue.entity == EX.hasValue}

    assert get_properties(graph) == {EX.hasValue}
    assert {"missing-label", "missing-comment"} <= rules
    assert "property-no-type" not in rules


@pytest.mark.parametrize("class_type", [OWL.Class, RDFS.Class, OWL.DeprecatedClass])
def test_class_types_are_linted_including_deprecated_classes(class_type: URIRef) -> None:
    graph = Graph()
    graph.add((EX.OldThing, RDF.type, class_type))

    result = LintEngine().lint_graph(graph)
    rules = {issue.rule_id for issue in result.issues if issue.entity == EX.OldThing}

    assert get_classes(graph) == {EX.OldThing}
    assert {"missing-label", "missing-comment", "orphan-class"} <= rules


def test_named_entity_sets_deduplicate_types_and_ignore_blank_nodes() -> None:
    graph = Graph()
    for entity in (EX.Punned, BNode()):
        for entity_type in (OWL.Class, OWL.DeprecatedClass, OWL.FunctionalProperty):
            graph.add((entity, RDF.type, entity_type))

    assert get_classes(graph) == {EX.Punned}
    assert get_properties(graph) == {EX.Punned}


@pytest.mark.parametrize("property_type", [OWL.FunctionalProperty, OWL.DeprecatedProperty])
def test_a_generic_property_type_does_not_imply_an_object_property(property_type: URIRef) -> None:
    graph = Graph()
    graph.add((EX.hasValue, RDF.type, property_type))

    assert get_properties(graph) == {EX.hasValue}
    assert get_object_properties(graph) == set()


def test_cli_lints_characteristic_and_deprecated_terms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "terms.ttl"
    source.write_text(
        "@prefix ex: <http://example.org/o#> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "ex:ancestorOf a owl:TransitiveProperty .\n"
        "ex:OldThing a owl:DeprecatedClass .\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["lint", str(source), "--level", "strict"])

    assert result.exit_code == 1, result.output
    assert "ancestorOf" in result.stdout and "OldThing" in result.stdout
    assert "missing-label" in result.stdout and "missing-comment" in result.stdout
    assert "Traceback" not in result.stderr


MALFORMED = {
    "ttl": "@prefix ex: <http://example.org/> .\nex:A a\n",
    "rdf": '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><',
    "nt": "not an N-Triples statement\n",
    "jsonld": '{"@id":',
}


@pytest.mark.parametrize("suffix", MALFORMED)
@pytest.mark.parametrize("fail_on", ["error", "warning", "info", "never"])
@pytest.mark.parametrize("order", ["only-bad", "bad-first", "bad-last"])
def test_an_unparseable_source_wins_over_findings_policy_and_file_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
    fail_on: str,
    order: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    bad = tmp_path / f"bad.{suffix}"
    bad.write_text(MALFORMED[suffix], encoding="utf-8")
    good = tmp_path / "good.ttl"
    good.write_text(
        "@prefix ex: <http://example.org/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "ex:hasValue a owl:DatatypeProperty .\n",
        encoding="utf-8",
    )
    sources = {"only-bad": [bad], "bad-first": [bad, good], "bad-last": [good, bad]}[order]

    result = CliRunner().invoke(cli, ["lint", *map(str, sources), "--fail-on", fail_on])

    assert result.exit_code == 2, result.output
    assert "parse-error" in result.stdout and bad.name in result.stdout
    assert "Traceback" not in result.stderr
    if order != "only-bad":
        assert "missing-comment" in result.stdout and good.name in result.stdout


def test_parse_status_is_retained_in_a_mixed_file_summary(tmp_path: Path) -> None:
    bad = tmp_path / "bad.ttl"
    bad.write_text(MALFORMED["ttl"], encoding="utf-8")
    good = tmp_path / "good.ttl"
    good.write_text(
        "<http://example.org/a> <http://example.org/p> <http://example.org/b> .\n", encoding="utf-8"
    )

    summary = LintEngine().lint_files([bad, good])

    assert [result.parse_failed for result in summary.results] == [True, False]
    assert summary.results[0].issues[0].rule_id == "parse-error"
    assert summary.results[0].error_count == 1
    assert summary.results[1].graph is not None
    assert _lint_exit_code(summary, "never") == 2


def test_an_ordinary_finding_does_not_mark_a_source_as_unparsed() -> None:
    result = LintResult(file_path=Path("invented.ttl"))
    result.add_issue(LintIssue("parse-error", Severity.ERROR, None, "An ordinary custom finding"))
    summary = LintSummary()
    summary.add_result(result)

    assert not result.parse_failed
    assert _lint_exit_code(summary, "never") == 0
    assert _lint_exit_code(summary, "error") == 1
