"""``split --by-namespace`` builds modules from the namespaces subjects use (#177).

Each source in ``tests/fixtures/split/namespaces/`` carries one case, and ``expected.yml`` lists by
hand the module files it must give and the subjects each holds, so a phantom module, a renamed
one or a misplaced subject is visible as a difference from it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

from rdf_construct.cli import cli
from rdf_construct.core.utils import in_namespace
from rdf_construct.merge.splitter import (
    ModuleDefinition,
    OntologySplitter,
    SplitConfig,
    _claiming_namespace,
    _fallback_name,
    select_classes,
    select_properties,
)
from tests.test_cli_smoke import assert_no_crash

FIXTURES = Path(__file__).parent / "fixtures" / "split" / "namespaces"
EXPECTED = yaml.safe_load((FIXTURES / "expected.yml").read_text())
IES = Path(__file__).parent / "fixtures" / "ies"


def _split(source: Path, out: Path) -> int:
    result = CliRunner().invoke(cli, ["split", str(source), "-o", str(out), "--by-namespace"])
    assert_no_crash(result)
    return result.exit_code


def _subjects(module: Path) -> set[str]:
    """The named subjects a module holds, less its own owl:Ontology header (#178's)."""
    graph = Graph().parse(module)
    headers = set(graph.subjects(RDF.type, OWL.Ontology))
    return {str(s) for s in graph.subjects() if isinstance(s, URIRef) and s not in headers}


def _prefixes(module: Path) -> set[str]:
    return set(re.findall(r"^@prefix (\S*): ", module.read_text(), flags=re.MULTILINE))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_modules_are_the_namespaces_subjects_use(name: str, tmp_path: Path) -> None:
    expected = EXPECTED[name]
    out = tmp_path / "modules"

    assert _split(FIXTURES / name, out) == 0

    written = {p.name: _subjects(p) for p in out.glob("*.ttl")}
    assert written == {f: set(subjects) for f, subjects in expected["modules"].items()}

    manifest = yaml.safe_load((out / "manifest.yml").read_text())
    assert [m["file"] for m in manifest["modules"]] == sorted(
        expected["modules"], key=lambda f: f.removesuffix(".ttl")
    )
    assert [m["name"] for m in manifest["modules"]] == [
        m["file"].removesuffix(".ttl") for m in manifest["modules"]
    ]
    assert manifest["summary"]["unmatched_entities"] == 0

    for module, prefixes in expected.get("prefixes", {}).items():
        assert _prefixes(out / module) == set(prefixes)


def test_ies_classification_terms_go_to_their_own_module(tmp_path: Path) -> None:
    """``env:`` is a prefix of ``blg-class:``; the first match used to take all 185 terms."""
    source = IES / "ies-env-building-classification.ttl"
    out = tmp_path / "modules"

    assert _split(source, out) == 0

    graph = Graph(bind_namespaces="none").parse(source)
    routed = {str(e) for e in select_classes(graph) | select_properties(graph)}
    assert len(routed) == 185  # the other four of its 189 subjects are #176's
    assert sorted(p.name for p in out.glob("*.ttl")) == ["blg-class.ttl"]
    assert _subjects(out / "blg-class.ttl") == routed


def test_ies_nested_namespaces_each_get_their_own_module(tmp_path: Path) -> None:
    source = IES / "ies-env-building.ttl"
    out = tmp_path / "modules"

    assert _split(source, out) == 0

    building = "http://informationexchangestandard.org/ont/ies/env/building/"
    written = {p.name: _subjects(p) for p in out.glob("*.ttl")}
    assert sorted(written) == ["building.ttl", "env.ttl"]
    assert all(written.values())
    assert all(in_namespace(s, building) for s in written["building.ttl"])
    assert not any(in_namespace(s, building) for s in written["env.ttl"])


def test_empty_file_writes_no_module(tmp_path: Path) -> None:
    out = tmp_path / "modules"

    assert _split(FIXTURES / "empty.ttl", out) == 0

    manifest = yaml.safe_load((out / "manifest.yml").read_text())
    assert manifest["modules"] == []
    assert manifest["summary"]["total_modules"] == 0


@pytest.mark.parametrize(
    ("iri", "namespaces", "expected"),
    [
        (
            "http://e.org/env/building/Door",
            {"http://e.org/env/", "http://e.org/env/building/"},
            "http://e.org/env/building/",
        ),
        (
            "http://e.org/env/x/Y",
            {"http://e.org/env/", "http://e.org/env/building/"},
            "http://e.org/env/",
        ),
        ("http://e.org/env/building-classification/X", {"http://e.org/env/building"}, None),
        ("http://e.org/ont", {"http://e.org/ont"}, "http://e.org/ont"),
        ("http://e.org/ont/extra#Three", {"http://e.org/ont", "http://e.org/"}, "http://e.org/ont"),
        ("http://e.org/ontology#Two", {"http://e.org/ont"}, None),
        ("urn:old:A", {"urn:old:", "urn:"}, "urn:old:"),
        ("urn:older:C", {"urn:old:"}, None),
    ],
)
def test_claiming_namespace_is_the_longest_in_namespace_match(
    iri: str, namespaces: set[str], expected: str | None
) -> None:
    containing = [ns for ns in namespaces if in_namespace(iri, ns)]
    assert _claiming_namespace(iri, namespaces) == expected
    assert expected == (max(containing, key=len) if containing else None)


@pytest.mark.parametrize(
    ("namespace", "expected"),
    [
        ("http://example.org/ontology#", "ontology"),
        ("http://informationexchangestandard.org/ont/ies/common/", "common"),
        ("http://example.org/", "example.org"),
        ("urn:example:codes:", "codes"),
        ("http://example.org/a%20b/", "a_20b"),
        ("http://example.org/thing/1#", "1"),
    ],
)
def test_fallback_name_is_the_last_segment(namespace: str, expected: str) -> None:
    assert _fallback_name(namespace) == expected


NESTED_SOURCE = """\
@prefix env: <http://example.org/env/> .
@prefix building: <http://example.org/env/building/> .
@prefix org: <http://example.org/org#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

env:Thing a owl:Class .
building:Door a owl:Class .
org:Team a owl:Class .
"""


@pytest.fixture
def nested_source(tmp_path: Path) -> Path:
    source = tmp_path / "nested.ttl"
    source.write_text(NESTED_SOURCE)
    return source


def _config(source: Path, tmp_path: Path, modules: list[ModuleDefinition]) -> SplitConfig:
    return SplitConfig(source=source, output_dir=tmp_path / "out", modules=modules, dry_run=True)


@pytest.mark.parametrize("reverse", [False, True], ids=["env-first", "building-first"])
def test_longest_namespace_claims_whatever_the_module_order(
    nested_source: Path, tmp_path: Path, reverse: bool
) -> None:
    modules = [
        ModuleDefinition(name="env", output="env.ttl", namespaces=["http://example.org/env/"]),
        ModuleDefinition(
            name="building", output="building.ttl", namespaces=["http://example.org/env/building/"]
        ),
    ]
    result = OntologySplitter(
        _config(nested_source, tmp_path, modules[::-1] if reverse else modules)
    ).split()

    assert result.entity_assignments["http://example.org/env/building/Door"] == "building"
    assert result.entity_assignments["http://example.org/env/Thing"] == "env"


def test_config_curie_means_the_files_own_prefix(nested_source: Path, tmp_path: Path) -> None:
    """``org:`` is the file's, not rdflib's W3C organisation vocabulary (#177, P10)."""
    modules = [ModuleDefinition(name="teams", output="teams.ttl", classes=["org:Team"])]
    result = OntologySplitter(_config(nested_source, tmp_path, modules)).split()

    assert result.success
    assert result.entity_assignments["http://example.org/org#Team"] == "teams"


def test_config_curie_with_an_unbound_prefix_is_refused(
    nested_source: Path, tmp_path: Path
) -> None:
    modules = [ModuleDefinition(name="zz", output="zz.ttl", classes=["zz:X"])]
    result = OntologySplitter(_config(nested_source, tmp_path, modules)).split()

    assert not result.success
    assert "prefix 'zz' is not bound" in (result.error or "")
