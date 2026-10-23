"""``split`` places every subject (#176) and names every module honestly (#178, #382, #383).

The fixtures in ``tests/fixtures/split/residue/`` are written so that a wrong answer is visible:
in ``routing.ttl`` every routed subject's ``rdfs:comment`` starts with the module file it belongs
in, so a misplaced subject disagrees with its own comment.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner, Result
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, PROV, RDF, RDFS, XSD

from rdf_construct.cli import cli
from rdf_construct.core.provenance import derivation_targets
from rdf_construct.core.verify import CONTRACTS, check_contract, describe
from rdf_construct.merge.splitter import (
    REASON_BNODE_SPLIT,
    REASON_BORROWED,
    REASON_CONCEPT_NO_MODULE,
    REASON_FOREIGN_TYPE,
    REASON_SCHEMES_SPLIT,
    REASON_TYPE_UNMATCHED,
    REASON_TYPES_SPLIT,
    REASON_UNTYPED,
    RUNG_CONFIG,
    RUNG_NAMESPACE,
    RUNG_NAMESPACE_UNCHECKED,
    RUNG_NONE,
    RUNG_SOURCE,
    ModuleDefinition,
    OntologySplitter,
    SplitConfig,
    UnmatchedStrategy,
    select_classes,
    select_properties,
)
from tests.test_cli_smoke import assert_no_crash, assert_wrote_nothing, snapshot

FIXTURES = Path(__file__).parent / "fixtures" / "split" / "residue"
IES = Path(__file__).parent / "fixtures" / "ies"
MONOLITH = Path(__file__).parent.parent / "examples" / "split" / "split_monolith.ttl"

A = "http://example.org/a#"
EX = "http://example.org/ont#"


def _split(source: Path, out: Path, *args: str) -> Result:
    result = CliRunner().invoke(
        cli, ["split", str(source), "-o", str(out), "--by-namespace", *args]
    )
    assert_no_crash(result)
    return result


def _modules(out: Path) -> dict[str, Graph]:
    return {p.name: Graph().parse(p) for p in sorted(out.glob("*.ttl"))}


def _header(graph: Graph) -> URIRef:
    (header,) = graph.subjects(RDF.type, OWL.Ontology)
    assert isinstance(header, URIRef)
    return header


# ---------------------------------------------------------------------------
# #176: what is placed
# ---------------------------------------------------------------------------


def test_selectors_use_the_vocab_sets() -> None:
    graph = Graph().parse(FIXTURES / "routing.ttl")

    assert URIRef(A + "Old") in select_classes(graph)
    assert {URIRef(A + "chain"), URIRef(A + "fun")} <= select_properties(graph)


def test_reproducer_loses_nothing_and_invents_only_a_header(tmp_path: Path) -> None:
    source = FIXTURES / "reproducer.ttl"
    out = tmp_path / "modules"

    assert _split(source, out).exit_code == 0

    modules = _modules(out)
    assert sorted(modules) == ["ex.ttl"]
    found = check_contract(
        CONTRACTS["split"].contract, inputs=[Graph().parse(source)], outputs=list(modules.values())
    )
    assert not found, describe(found)

    ex = modules["ex.ttl"]
    # The restriction is there, not `rdfs:subClassOf [ ]`
    (restriction,) = ex.objects(URIRef(EX + "Building"), RDFS.subClassOf)
    assert isinstance(restriction, BNode)
    assert (restriction, OWL.minCardinality, Literal("1", datatype=XSD.nonNegativeInteger)) in ex
    for subject in ("theBuilding", "Topic", "hasPart"):
        assert (URIRef(EX + subject), None, None) in ex


@pytest.fixture(scope="module")
def routed(tmp_path_factory: pytest.TempPathFactory) -> tuple[Result, dict[str, Graph]]:
    out = tmp_path_factory.mktemp("routing") / "modules"
    result = _split(FIXTURES / "routing.ttl", out)
    return result, _modules(out)


def test_every_subject_is_in_the_module_its_comment_names(
    routed: tuple[Result, dict[str, Graph]],
) -> None:
    _, modules = routed
    source = Graph().parse(FIXTURES / "routing.ttl")

    expected = {
        s: str(c).split(":", 1)[0] for s, c in source.subject_objects(RDFS.comment) if ".ttl:" in c
    }
    assert len(expected) == 16
    found = {
        s: name for name, graph in modules.items() for s in expected if (s, None, None) in graph
    }
    assert found == expected


def test_root_blank_nodes_go_where_their_terms_are(routed: tuple[Result, dict[str, Graph]]) -> None:
    _, modules = routed

    def disjoint_members(graph: Graph) -> list[set[str]]:
        return [
            {str(m) for m in graph.items(members)}
            for axiom in graph.subjects(RDF.type, OWL.AllDisjointClasses)
            for members in graph.objects(axiom, OWL.members)
        ]

    assert disjoint_members(modules["a.ttl"]) == [{A + "A", A + "A2"}]
    assert disjoint_members(modules["unmatched.ttl"]) == [{A + "A", "http://example.org/b#B"}]
    assert list(modules["unmatched.ttl"].subjects(RDFS.subClassOf, URIRef(A + "A")))


def test_a_shared_blank_node_is_copied_into_each_module_and_counted(
    routed: tuple[Result, dict[str, Graph]],
) -> None:
    result, modules = routed

    for name, owner in (("a.ttl", A + "A"), ("b.ttl", "http://example.org/b#B")):
        (shared,) = modules[name].objects(URIRef(owner), RDFS.seeAlso)
        assert (shared, RDFS.label, Literal("shared")) in modules[name]
    assert "Blank nodes copied into more than one module: 1" in result.output


def test_the_summary_counts_what_went_to_the_unmatched_module_and_why(
    routed: tuple[Result, dict[str, Graph]],
) -> None:
    result, modules = routed

    assert result.exit_code == 1
    assert "Unmatched subjects: 10" in result.output
    for count, reason in (
        (2, REASON_BNODE_SPLIT),
        (1, REASON_BORROWED),
        (1, REASON_SCHEMES_SPLIT),
        (1, REASON_CONCEPT_NO_MODULE),
        (1, REASON_UNTYPED),
        (1, REASON_TYPE_UNMATCHED),
        (1, REASON_TYPES_SPLIT),
        (2, REASON_FOREIGN_TYPE),
    ):
        assert f"    {count} {reason}\n" in result.output
    # Derived from what was written: every named subject it lists is in the unmatched module
    listed = [line.split("- ", 1)[1] for line in result.output.splitlines() if "- http" in line]
    assert len(listed) == 8
    assert all((URIRef(iri), None, None) in modules["unmatched.ttl"] for iri in listed)


def test_unmatched_error_on_by_namespace_refuses_and_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "modules"
    before = snapshot([], tmp_path)

    result = _split(FIXTURES / "routing.ttl", out, "--unmatched", "error")

    assert result.exit_code == 2
    assert "Unmatched entities (10)" in result.output
    assert_wrote_nothing(before, snapshot([], tmp_path))


def test_a_file_with_nothing_unmatched_still_exits_0_under_unmatched_error(tmp_path: Path) -> None:
    assert _split(MONOLITH, tmp_path / "modules", "--unmatched", "error").exit_code == 0


# ---------------------------------------------------------------------------
# #382: the unmatched module's name
# ---------------------------------------------------------------------------


def test_unmatched_module_defaults_to_unmatched_and_common_name_renames_it(tmp_path: Path) -> None:
    source = FIXTURES / "routing.ttl"

    _split(source, tmp_path / "default")
    _split(source, tmp_path / "named", "--common-name", "leftovers")

    assert (tmp_path / "default" / "unmatched.ttl").exists()
    assert (tmp_path / "named" / "leftovers.ttl").exists()
    assert not (tmp_path / "named" / "unmatched.ttl").exists()


def test_a_clash_with_the_unmatched_module_is_refused(tmp_path: Path) -> None:
    out = tmp_path / "modules"
    before = snapshot([], tmp_path)

    result = _split(FIXTURES / "unmatched_prefix.ttl", out)

    assert result.exit_code == 2
    assert "would overwrite module 'unmatched'" in result.output
    assert_wrote_nothing(before, snapshot([], tmp_path))

    renamed = _split(FIXTURES / "unmatched_prefix.ttl", out, "--common-name", "rest")
    assert renamed.exit_code == 1
    assert sorted(_modules(out)) == ["ex.ttl", "rest.ttl", "unmatched.ttl"]


def test_a_clash_is_compared_without_case(tmp_path: Path) -> None:
    config = SplitConfig(
        source=FIXTURES / "unmatched_prefix.ttl",
        output_dir=tmp_path,
        modules=[ModuleDefinition(name="Common", output="Common.ttl", namespaces=[EX])],
        unmatched=UnmatchedStrategy(common_module="common", common_output="common.ttl"),
    )
    result = OntologySplitter(config).split()

    assert not result.success
    assert "would overwrite module 'Common'" in (result.error or "")


# ---------------------------------------------------------------------------
# #383: borrowed vocabularies
# ---------------------------------------------------------------------------


def test_borrowed_declarations_go_to_the_unmatched_module(tmp_path: Path) -> None:
    out = tmp_path / "modules"

    result = _split(FIXTURES / "borrowed.ttl", out)

    assert result.exit_code == 1
    modules = _modules(out)
    assert sorted(modules) == ["ex.ttl", "unmatched.ttl"]
    borrowed = {
        "http://www.w3.org/2000/01/rdf-schema#label",
        "http://purl.org/dc/terms/title",
        "http://www.w3.org/2004/02/skos/core#prefLabel",
        "http://www.w3.org/2002/07/owl#Thing",
    }
    assert {str(s) for s in modules["unmatched.ttl"].subjects(RDF.type)} - {
        str(_header(modules["unmatched.ttl"])),
        str(PROV.wasDerivedFrom),
    } == borrowed
    assert f"    4 {REASON_BORROWED}\n" in result.output


def test_without_a_header_nothing_is_borrowed(tmp_path: Path) -> None:
    source = tmp_path / "headerless.ttl"
    source.write_text(
        (FIXTURES / "borrowed.ttl")
        .read_text()
        .replace('<http://example.org/ex> a owl:Ontology ; dcterms:title "Ex" .', "")
    )

    assert _split(source, tmp_path / "modules").exit_code == 0
    assert sorted(_modules(tmp_path / "modules")) == [
        "dcterms.ttl",
        "ex.ttl",
        "owl.ttl",
        "rdfs.ttl",
        "skos.ttl",
    ]


# ---------------------------------------------------------------------------
# #178: each module's identity
# ---------------------------------------------------------------------------


def _iris(source: Path, modules: list[ModuleDefinition], tmp_path: Path) -> dict[str, tuple]:
    config = SplitConfig(source=source, output_dir=tmp_path, modules=modules)
    result = OntologySplitter(config).split()
    assert result.success, result.error
    return result.module_iris


@pytest.mark.parametrize(
    ("source", "module", "expected"),
    [
        # Rung 1: the config names it, as a CURIE of the source's own prefixes
        (
            MONOLITH,
            ModuleDefinition(name="core", output="core.ttl", ontology_iri="ex:core"),
            ("http://example.org/ontology#core", RUNG_CONFIG),
        ),
        # Rung 2, checked: the namespace is on the source ontology's host
        (
            FIXTURES / "routing.ttl",
            ModuleDefinition(name="a", output="a.ttl", namespaces=[A]),
            ("http://example.org/a", RUNG_NAMESPACE),
        ),
        # Rung 2, unchecked: the source declares no ontology to check it against
        (
            MONOLITH,
            ModuleDefinition(
                name="org", output="org.ttl", namespaces=["http://example.org/ontology/org#"]
            ),
            ("http://example.org/ontology/org", RUNG_NAMESPACE_UNCHECKED),
        ),
        # The guard: rung 2 would be the source's own ontology IRI
        (
            FIXTURES / "reproducer.ttl",
            ModuleDefinition(name="ex", output="ex.ttl", namespaces=[EX]),
            ("http://example.org/ont/ex", RUNG_SOURCE),
        ),
        # The guard: …/ies/common/ against the source's …/ies/common/, a trailing / apart
        (
            IES / "ies-common.ttl",
            ModuleDefinition(
                name="ies",
                output="ies.ttl",
                namespaces=["http://informationexchangestandard.org/ont/ies/common/"],
            ),
            ("http://informationexchangestandard.org/ont/ies/common/ies", RUNG_SOURCE),
        ),
        # The guard: GeoSPARQL's namespace would claim OGC's ontology IRI
        (
            IES / "ies-common.ttl",
            ModuleDefinition(
                name="geo", output="geo.ttl", namespaces=["http://www.opengis.net/ont/geosparql#"]
            ),
            ("http://informationexchangestandard.org/ont/ies/common/geo", RUNG_SOURCE),
        ),
        # Rung 3 with two headers: the one whose IRI holds the module's namespace, the longest
        (
            IES / "ies-env-building.ttl",
            ModuleDefinition(
                name="building",
                output="building.ttl",
                namespaces=["http://informationexchangestandard.org/ont/ies/env/building/"],
            ),
            ("http://informationexchangestandard.org/ont/ies/env/building/building", RUNG_SOURCE),
        ),
        # Rung 4: no namespace, two headers, and no config
        (
            IES / "ies-env-building.ttl",
            ModuleDefinition(name="picked", output="picked.ttl", classes=["building:Building"]),
            (None, RUNG_NONE),
        ),
    ],
    ids=[
        "config",
        "namespace",
        "namespace-unchecked",
        "not-the-source",
        "not-the-source-slash",
        "not-borrowed",
        "two-headers",
        "none",
    ],
)
def test_the_ladder(
    source: Path, module: ModuleDefinition, expected: tuple, tmp_path: Path
) -> None:
    assert _iris(source, [module], tmp_path)[module.name] == expected


def test_a_module_with_no_iri_gets_no_header_and_cannot_be_imported(tmp_path: Path) -> None:
    out = tmp_path / "modules"

    result = _split(IES / "ies-env-building.ttl", out)

    assert result.exit_code == 1
    modules = _modules(out)
    assert not list(modules["unmatched.ttl"].subjects(RDF.type, OWL.Ontology))
    assert "unmatched: no ontology IRI to give it" in result.output
    assert "building depends on unmatched, which has no ontology IRI" in result.output


@pytest.mark.parametrize(
    "source",
    [
        MONOLITH,
        FIXTURES / "reproducer.ttl",
        FIXTURES / "routing.ttl",
        IES / "ies-common.ttl",
        IES / "ies-env-building.ttl",
        IES / "ies-env-building-classification.ttl",
    ],
    ids=lambda p: p.stem,
)
def test_module_headers_hold_only_their_own_identity(source: Path, tmp_path: Path) -> None:
    out = tmp_path / "modules"
    _split(source, out)
    original = Graph().parse(source)
    targets = sorted(
        {
            t
            for o in original.subjects(RDF.type, OWL.Ontology)
            for t in derivation_targets(original, o)
        }
    )

    modules = _modules(out)
    iris = {
        name: _header(graph)
        for name, graph in modules.items()
        if (None, RDF.type, OWL.Ontology) in graph
    }
    assert iris
    sources = set(original.subjects(RDF.type, OWL.Ontology))
    for name, iri in iris.items():
        graph = modules[name]
        assert iri not in sources
        assert set(graph.predicates(iri)) <= {RDF.type, OWL.imports, PROV.wasDerivedFrom}
        assert sorted(graph.objects(iri, PROV.wasDerivedFrom)) == targets
        assert set(graph.objects(iri, OWL.imports)) <= set(iris.values()) - {iri}
    written = "".join(p.read_text() for p in out.glob("*.ttl"))
    assert "file:" not in written
    if source.parent == IES:
        assert "example.org" not in written
    assert all(
        str(i) in {str(v) for v in iris.values()}
        for m in yaml.safe_load((out / "manifest.yml").read_text())["modules"]
        for i in m["imports"]
    )


def test_imports_name_the_ontology_iris_of_dependencies(tmp_path: Path) -> None:
    out = tmp_path / "modules"
    _split(MONOLITH, out)

    building = _modules(out)["building.ttl"]

    assert set(building.objects(None, OWL.imports)) == {
        URIRef("http://example.org/ontology"),
        URIRef("http://example.org/ontology/org"),
    }


def test_a_source_that_types_the_stamp_keeps_its_type_in_every_module(tmp_path: Path) -> None:
    out = tmp_path / "modules"
    _split(FIXTURES / "prov_typed.ttl", out)

    modules = _modules(out)
    assert modules
    for name, graph in modules.items():
        assert (_header(graph), PROV.wasDerivedFrom, URIRef("http://example.org/ex")) in graph
        assert set(graph.objects(PROV.wasDerivedFrom, RDF.type)) == {OWL.ObjectProperty}, name
