"""Tests for the prefixes ``order`` writes (issue #239).

``order`` parsed its source into a bare ``Graph()``, whose default
``bind_namespaces="rdflib"`` pre-binds about thirty well-known prefixes. A
source declaring its own ``org:``, ``dc:``, ``foaf:`` or ``skos:`` came back as
``org1:`` and so on: the graph was isomorphic, but every CURIE a reader sees had
changed. The source is now parsed with ``bind_namespaces="core"``: its own
prefixes plus rdf, rdfs, owl, xsd and xml.
"""

import re
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import Graph
from rdflib.compare import isomorphic

from rdf_construct.cli import cli

EXAMPLES = Path(__file__).parent.parent / "examples"

#: One profile that writes everything, one that filters (and so is stamped, #90).
CONFIG = """\
profiles:
  full:
    unclaimed: emit
    sections:
      - header: {}
      - classes: {select: classes}
  classes:
    unclaimed: ignore
    sections:
      - header: {}
      - classes: {select: classes}
"""


def _run(tmp_path: Path, ontology: str, config: str = CONFIG) -> tuple[Result, Path]:
    """Write the ontology and the config, then run ``order`` on them."""
    model = tmp_path / "model.ttl"
    model.write_text(ontology, encoding="utf-8")
    cfg = tmp_path / "order.yml"
    cfg.write_text(config, encoding="utf-8")
    out = tmp_path / "out"
    result = CliRunner().invoke(cli, ["order", str(model), str(cfg), "-o", str(out)])
    return result, out


def _prefixes(text: str) -> dict[str, str]:
    """The ``@prefix`` declarations of a Turtle document, prefix to namespace."""
    return dict(re.findall(r"^@prefix ([^:]*): <([^>]*)> \.$", text, re.M))


def _written(out: Path, profile: str = "full") -> str:
    return (out / f"model-{profile}.ttl").read_text(encoding="utf-8")


def _assert_same_graph(source: str, written: str) -> None:
    expected, actual = Graph(), Graph()
    expected.parse(data=source, format="turtle")
    actual.parse(data=written, format="turtle")
    assert isomorphic(expected, actual)


def test_organisation_example_keeps_org(tmp_path: Path):
    """#239's reproducer: the organisation example through ``sample_profile.yml -p alpha``."""
    out = tmp_path / "out"
    result = CliRunner().invoke(
        cli,
        [
            "order",
            str(EXAMPLES / "organisation_ontology.ttl"),
            str(EXAMPLES / "order" / "sample_profile.yml"),
            "-p",
            "alpha",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    text = (out / "organisation_ontology-alpha.ttl").read_text(encoding="utf-8")
    assert _prefixes(text)["org"] == "http://example.org/organisation#"
    assert "org1" not in text


#: Prefixes rdflib's extended table binds to a vocabulary of its own.
COLLIDING = ["org", "dc", "foaf", "skos", "time", "geo", "prov", "dcat", "schema", "vann"]


@pytest.mark.parametrize("prefix", COLLIDING)
def test_a_source_prefix_rdflib_also_binds_is_kept(tmp_path: Path, prefix: str):
    namespace = f"http://example.org/{prefix}#"
    ontology = (
        f"@prefix {prefix}: <{namespace}> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        f"{prefix}:Thing a owl:Class .\n"
    )
    result, out = _run(tmp_path, ontology)
    assert result.exit_code == 0, result.output
    text = _written(out)
    assert _prefixes(text)[prefix] == namespace
    assert f"{prefix}:Thing" in text
    assert f"{prefix}1" not in text
    _assert_same_graph(ontology, text)


def test_dc_bound_to_dc_terms_stays_dc(tmp_path: Path):
    """What many real ontologies write: ``dc:`` for DC Terms, not rdflib's DC Elements."""
    ontology = (
        "@prefix dc: <http://purl.org/dc/terms/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix ex: <http://example.org/ex#> .\n"
        '<http://example.org/ex> a owl:Ontology ; dc:title "Example" .\n'
        'ex:A a owl:Class ; dc:description "an A" .\n'
    )
    result, out = _run(tmp_path, ontology)
    assert result.exit_code == 0, result.output
    text = _written(out)
    assert _prefixes(text)["dc"] == "http://purl.org/dc/terms/"
    assert 'dc:title "Example"' in text
    assert "dc1" not in text


def test_an_undeclared_core_namespace_is_written_with_its_core_prefix(tmp_path: Path):
    ontology = (
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix ex: <http://example.org/ex#> .\n"
        'ex:A a owl:Class ; <http://www.w3.org/2000/01/rdf-schema#label> "A" .\n'
    )
    result, out = _run(tmp_path, ontology)
    assert result.exit_code == 0, result.output
    text = _written(out)
    assert _prefixes(text)["rdfs"] == "http://www.w3.org/2000/01/rdf-schema#"
    assert 'rdfs:label "A"' in text


def test_an_undeclared_namespace_outside_the_core_is_written_in_full(tmp_path: Path):
    """rdflib's table no longer supplies a prefix the source never declared."""
    ontology = (
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix ex: <http://example.org/ex#> .\n"
        'ex:A a owl:Class ; <http://www.w3.org/2004/02/skos/core#definition> "an A" .\n'
    )
    result, out = _run(tmp_path, ontology)
    assert result.exit_code == 0, result.output
    text = _written(out)
    assert "skos" not in _prefixes(text)
    assert '<http://www.w3.org/2004/02/skos/core#definition> "an A"' in text


def test_a_source_redefining_a_core_prefix_gets_a_numbered_one(tmp_path: Path):
    """Pinned edge: the core prefixes are bound before the parse, so a source's own ``owl:``
    for another namespace is renamed, and OWL keeps ``owl:``."""
    ontology = (
        "@prefix owl: <http://example.org/not-owl#> .\n"
        "@prefix ex: <http://example.org/ex#> .\n"
        'ex:A a <http://www.w3.org/2002/07/owl#Class> ; owl:note "x" .\n'
    )
    result, out = _run(tmp_path, ontology)
    assert result.exit_code == 0, result.output
    text = _written(out)
    prefixes = _prefixes(text)
    assert prefixes["owl"] == "http://www.w3.org/2002/07/owl#"
    assert prefixes["owl1"] == "http://example.org/not-owl#"
    assert 'owl1:note "x"' in text


def test_two_prefixes_for_one_namespace_keep_only_one(tmp_path: Path):
    """Pinned as unchanged: rdflib keeps one prefix per namespace, here the later ``dcterms:``."""
    ontology = (
        "@prefix dct: <http://purl.org/dc/terms/> .\n"
        "@prefix dcterms: <http://purl.org/dc/terms/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix ex: <http://example.org/ex#> .\n"
        'ex:A a owl:Class ; dct:title "A" .\n'
    )
    result, out = _run(tmp_path, ontology)
    assert result.exit_code == 0, result.output
    prefixes = _prefixes(_written(out))
    assert prefixes["dcterms"] == "http://purl.org/dc/terms/"
    assert "dct" not in prefixes


STAMPED = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix ex: <http://example.org/ex#> .
<http://example.org/ex> a owl:Ontology ; owl:versionInfo "1.0" .
ex:A a owl:Class .
ex:i a ex:A .
"""


def test_a_source_prov_for_another_namespace_keeps_prov(tmp_path: Path):
    """The stamp (#90) binds ``prov:`` without overriding, so PROV-O takes ``prov1:``."""
    ontology = "@prefix prov: <http://example.org/my-prov#> .\n" + STAMPED.replace(
        '"1.0" .', '"1.0" ; prov:note "mine" .'
    )
    result, out = _run(tmp_path, ontology)
    assert result.exit_code == 0, result.output
    text = _written(out, "classes")
    prefixes = _prefixes(text)
    assert prefixes["prov"] == "http://example.org/my-prov#"
    assert prefixes["prov1"] == "http://www.w3.org/ns/prov#"
    assert "prov1:wasDerivedFrom <http://example.org/ex>" in text
    assert 'prov:note "mine"' in text


def test_prov_o_bound_as_another_prefix_and_unused_in_the_extract(tmp_path: Path):
    """Pinned as unchanged: only the bindings an extract uses are copied, so a ``pv:`` the
    extract no longer uses is not there for the stamp, which writes ``prov:``. A run that
    keeps everything keeps ``pv:``."""
    ontology = "@prefix pv: <http://www.w3.org/ns/prov#> .\n" + STAMPED.replace(
        "ex:i a ex:A .", "ex:i a ex:A ; pv:wasAttributedTo ex:someone ."
    )
    result, out = _run(tmp_path, ontology)
    assert result.exit_code == 0, result.output
    extract = _written(out, "classes")
    assert _prefixes(extract)["prov"] == "http://www.w3.org/ns/prov#"
    assert "prov:wasDerivedFrom <http://example.org/ex>" in extract
    whole = _written(out)
    assert _prefixes(whole)["pv"] == "http://www.w3.org/ns/prov#"
    assert "pv:wasAttributedTo ex:someone" in whole


def test_a_roots_curie_resolves_against_the_source_prefix(tmp_path: Path):
    """``roots: org:Zone`` names the source's own term, not one in W3C's ``org:``."""
    ontology = (
        "@prefix org: <http://example.org/org#> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "org:Alpha a owl:Class .\n"
        "org:Zone a owl:Class .\n"
        "org:Bee a owl:Class ; rdfs:subClassOf org:Zone .\n"
    )
    config = (
        "profiles:\n  full:\n    unclaimed: emit\n    sections:\n"
        "      - classes: {select: classes, sort: topological, roots: [org:Zone]}\n"
    )
    result, out = _run(tmp_path, ontology, config)
    assert result.exit_code == 0, result.output
    classes = [line for line in _written(out).splitlines() if line.startswith("org:")]
    # The root's branch first, then the rest. Unresolved, the root would be skipped and
    # `org:Alpha` would lead.
    assert classes == ["org:Zone", "org:Bee", "org:Alpha"]
