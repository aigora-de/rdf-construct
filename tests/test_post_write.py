"""Post-write contracts (#266): what each command wrote, checked against what it claims.

Every test runs the real command through ``CliRunner``, reads the output back from disk and
checks the command's contract from ``rdf_construct.core.verify.CONTRACTS``. The smoke test
(``test_cli_smoke.py``) asserts that a command ran and exited correctly. This module asserts
that what it wrote is right.

Inputs are ``examples/``, the smallest pinned IES file, and for ``docs`` the SKOS fixture, which
has concepts, schemes and individuals in under 150 lines. The larger IES files add tens of
seconds to the suite and catch nothing the smallest does not.

A contract that fails today is ``xfail(strict=True)`` against the issue that explains it. The fix
for that issue makes the test pass, and the strict marker then fails the suite until the fix
removes it.
"""

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SH

from rdf_construct.cli import cli
from rdf_construct.core.verify import CONTRACTS, Triple, check_contract, describe
from rdf_construct.core.vocab import CLASS_TYPES
from rdf_construct.docs import extract_all
from tests.test_cli_smoke import assert_no_crash

REPO = Path(__file__).parent.parent
EXAMPLES = REPO / "examples"
FIXTURES = REPO / "tests" / "fixtures"

ANIMAL = EXAMPLES / "animal_ontology.ttl"
LIBRARY = EXAMPLES / "order" / "library.ttl"
IES_SMALL = FIXTURES / "ies" / "ies-env-building-classification.ttl"
DOCS_SOURCE = FIXTURES / "docs" / "skos_vocabulary.ttl"

EXO = Namespace("http://example.org/")


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *argv: object) -> Result:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, [str(arg) for arg in argv])
    assert_no_crash(result)
    assert result.exit_code in (0, 1), result.output
    return result


def _parse(path: Path, fmt: str | None = None) -> Graph:
    return Graph().parse(path, format=fmt)


def _assert_holds(
    command: str,
    *,
    inputs: Sequence[Graph] = (),
    outputs: Sequence[Graph] = (),
    excluded: Iterable[Triple] = (),
    counts: Mapping[str, int] | None = None,
) -> None:
    """Assert ``command``'s declared contract holds, so a test never names the contract itself."""
    found = check_contract(
        CONTRACTS[command].contract,
        inputs=inputs,
        outputs=outputs,
        excluded=excluded,
        counts=counts,
    )
    assert not found, describe(found)


# ---------------------------------------------------------------------------
# cast: isomorphic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source", [ANIMAL, LIBRARY, IES_SMALL], ids=lambda p: p.stem)
@pytest.mark.parametrize("fmt", ["nt", "xml", "json-ld"])
def test_cast_is_isomorphic(source: Path, fmt: str, tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, "cast", source, "-f", fmt, "-o", tmp_path / "out")
    [written] = (tmp_path / "out").iterdir()
    _assert_holds("cast", inputs=[_parse(source)], outputs=[_parse(written, fmt)])


# ---------------------------------------------------------------------------
# order: isomorphic, for lossless profiles (filtering profiles are #90, P13)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "config", "profile"),
    [
        (LIBRARY, EXAMPLES / "order" / "ordering.yml", "alpha"),
        (LIBRARY, EXAMPLES / "order" / "ordering.yml", "hierarchy"),
        (LIBRARY, EXAMPLES / "order" / "ordering.yml", "anchored"),
        (IES_SMALL, EXAMPLES / "order" / "ies_profile.yml", "alpha"),
        (IES_SMALL, EXAMPLES / "order" / "ies_profile.yml", "logical_topo"),
        (IES_SMALL, EXAMPLES / "order" / "ies_profile.yml", "props_by_domain"),
        (IES_SMALL, EXAMPLES / "order" / "ies_profile.yml", "doc_order"),
    ],
    ids=lambda v: v.stem if isinstance(v, Path) else v,
)
def test_order_lossless_profile_is_isomorphic(source, config, profile, tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, "order", source, config, "-p", profile, "-o", tmp_path / "out")
    [written] = (tmp_path / "out").glob("*.ttl")
    _assert_holds("order", inputs=[_parse(source)], outputs=[_parse(written)])


# ---------------------------------------------------------------------------
# localise: an unedited extract merges back to the source
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source", [ANIMAL, IES_SMALL], ids=lambda p: p.stem)
def test_localise_round_trip_is_isomorphic(source: Path, tmp_path, monkeypatch):
    strings = tmp_path / "de.yml"
    merged = tmp_path / "merged.ttl"
    _run(tmp_path, monkeypatch, "localise", "extract", source, "-l", "de", "-o", strings)
    _run(tmp_path, monkeypatch, "localise", "merge", source, strings, "-o", merged)
    _assert_holds("localise merge", inputs=[_parse(source)], outputs=[_parse(merged)])


# ---------------------------------------------------------------------------
# refactor rename: the same triple count
# ---------------------------------------------------------------------------

RENAMES = [
    pytest.param(
        EXAMPLES / "refactor" / "typos.ttl",
        ("-c", EXAMPLES / "refactor" / "renames.yml"),
        id="typos-config",
    ),
    pytest.param(
        IES_SMALL,
        (
            "--from",
            "http://informationexchangestandard.org/ont/ies/env/building-classification/"
            "0mm_RoofingInsulation",
            "--to",
            "http://informationexchangestandard.org/ont/ies/env/building-classification/"
            "RoofingInsulationNone",
        ),
        id="ies-class",
    ),
    pytest.param(
        ANIMAL,
        ("--from", "http://example.org/animals#Animal", "--to", "http://example.org/animals#Bird"),
        id="onto-existing-iri",
        marks=pytest.mark.xfail(strict=True, reason="#185"),
    ),
]


@pytest.mark.parametrize(("source", "args"), RENAMES)
def test_refactor_rename_keeps_the_triple_count(source, args, tmp_path, monkeypatch):
    out = tmp_path / "renamed.ttl"
    _run(tmp_path, monkeypatch, "refactor", "rename", source, *args, "-o", out)
    _assert_holds("refactor rename", inputs=[_parse(source)], outputs=[_parse(out)])


def test_refactor_deprecate_keeps_every_input_triple(tmp_path, monkeypatch):
    """The declared contract is ambiguous (see ``CONTRACTS``). This checks only what is settled."""
    source = EXAMPLES / "refactor" / "legacy.ttl"
    out = tmp_path / "deprecated.ttl"
    config = EXAMPLES / "refactor" / "deprecations.yml"
    _run(tmp_path, monkeypatch, "refactor", "deprecate", source, "-c", config, "-o", out)
    _assert_holds("refactor deprecate", inputs=[_parse(source)], outputs=[_parse(out)])


# ---------------------------------------------------------------------------
# split: the union of the modules is the source
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        # Nothing is lost, but every module gains a fabricated header and file:// imports.
        pytest.param(
            EXAMPLES / "split" / "split_monolith.ttl",
            id="monolith",
            marks=pytest.mark.xfail(strict=True, reason="#178"),
        ),
        # Individuals, the header and blank-node interiors are lost (#176), and headers are
        # fabricated (#178).
        pytest.param(
            IES_SMALL,
            id="ies",
            marks=pytest.mark.xfail(strict=True, reason="#176, #178"),
        ),
    ],
)
def test_split_union_is_isomorphic(source: Path, tmp_path, monkeypatch):
    out = tmp_path / "modules"
    _run(tmp_path, monkeypatch, "split", source, "--by-namespace", "-o", out)
    modules = [_parse(path) for path in sorted(out.glob("*.ttl"))]
    _assert_holds("split", inputs=[_parse(source)], outputs=modules)


# ---------------------------------------------------------------------------
# merge: every source triple, minus the losers of resolved conflicts
# ---------------------------------------------------------------------------

# The losing values of the five conflicts `merge` reports as auto-resolved for core + conflicting
# under the default `priority` strategy, where merge_conflicting.ttl has the higher priority. They
# are named by hand so that the test does not depend on the merger's own conflict detection
# (#193).
MERGE_LOSERS: tuple[Triple, ...] = (
    (EXO.hasName, RDFS.domain, EXO.Building),
    (EXO.hasName, RDFS.label, Literal("has name", lang="en")),
    (EXO.Building, RDFS.label, Literal("Building", lang="en")),
    (EXO.Building, RDFS.comment, Literal("A constructed structure.", lang="en")),
    (EXO.hasLocation, RDFS.range, EXO.Place),
)


def _merge(tmp_path: Path, monkeypatch, sources: list[Path]) -> Graph:
    out = tmp_path / "merged.ttl"
    _run(tmp_path, monkeypatch, "merge", *sources, "-o", out)
    return _parse(out)


def test_merge_keeps_every_source_triple(tmp_path, monkeypatch):
    sources = [EXAMPLES / "merge" / "merge_core.ttl", EXAMPLES / "merge" / "merge_extension.ttl"]
    merged = _merge(tmp_path, monkeypatch, sources)
    _assert_holds("merge", inputs=[_parse(s) for s in sources], outputs=[merged])


@pytest.mark.xfail(strict=True, reason="#169")
def test_merge_drops_the_losers_of_resolved_conflicts(tmp_path, monkeypatch):
    sources = [EXAMPLES / "merge" / "merge_core.ttl", EXAMPLES / "merge" / "merge_conflicting.ttl"]
    merged = _merge(tmp_path, monkeypatch, sources)
    _assert_holds(
        "merge", inputs=[_parse(s) for s in sources], outputs=[merged], excluded=MERGE_LOSERS
    )


# ---------------------------------------------------------------------------
# docs: entities selected = pages written = index entries = search index entries
# ---------------------------------------------------------------------------

DOCS_PAGE_DIRS = ("classes", "properties", "instances", "shapes", "concepts")


def _selected_entities(source: Path, no_instances: bool) -> int:
    # The tool's own extractor, so this contract checks that the artefacts agree with each other.
    # An entity the extractor never sees is invisible here; the taxonomy tests own that.
    entities = extract_all(_parse(source))
    total = (
        len(entities.classes)
        + len(entities.properties)
        + len(entities.shapes)
        + len(entities.concepts)
        + len(entities.concept_schemes)
    )
    return total if no_instances else total + len(entities.instances)


def _pages(out: Path, suffix: str) -> int:
    return sum(
        1
        for name in DOCS_PAGE_DIRS
        for _ in (out / name).rglob(f"*{suffix}")
        if (out / name).is_dir()
    )


@pytest.mark.parametrize("no_instances", [False, True], ids=["all", "no-instances"])
def test_docs_html_counts_agree(no_instances: bool, tmp_path, monkeypatch):
    out = tmp_path / "docs"
    flags = ["--no-instances"] if no_instances else []
    _run(tmp_path, monkeypatch, "docs", DOCS_SOURCE, *flags, "-o", out)
    search = json.loads((out / "search.json").read_text())["entities"]
    counts = {
        "entities selected": _selected_entities(DOCS_SOURCE, no_instances),
        "pages written": _pages(out, ".html"),
        "search index entries": len(search),
    }
    _assert_holds("docs", counts=counts)


INDEX_LISTS = (
    "classes",
    "object_properties",
    "datatype_properties",
    "annotation_properties",
    "other_properties",
    "instances",
    "shapes",
    "concepts",
    "concept_schemes",
)


@pytest.mark.parametrize(
    "no_instances",
    [False, pytest.param(True, marks=pytest.mark.xfail(strict=True, reason="#253"))],
    ids=["all", "no-instances"],
)
def test_docs_json_counts_agree(no_instances: bool, tmp_path, monkeypatch):
    out = tmp_path / "docs"
    flags = ["--no-instances"] if no_instances else []
    _run(tmp_path, monkeypatch, "docs", DOCS_SOURCE, "-f", "json", *flags, "-o", out)
    index = json.loads((out / "index.json").read_text())
    counts = {
        "entities selected": _selected_entities(DOCS_SOURCE, no_instances),
        "pages written": _pages(out, ".json"),
        "index entries": sum(len(index[name]) for name in INDEX_LISTS),
        "index statistics": sum(index["statistics"][name] for name in INDEX_LISTS),
    }
    _assert_holds("docs", counts=counts)


# ---------------------------------------------------------------------------
# shacl-gen: one shape per selected class
# ---------------------------------------------------------------------------


def _classes(graph: Graph) -> set[URIRef]:
    return {
        subject
        for class_type in CLASS_TYPES
        for subject in graph.subjects(RDF.type, class_type)
        if isinstance(subject, URIRef)
    }


@pytest.mark.parametrize(
    ("source", "args", "selected"),
    [
        pytest.param(ANIMAL, (), None, id="animal"),
        pytest.param(IES_SMALL, (), None, id="ies"),
        pytest.param(
            ANIMAL,
            ("--classes", "ex:Dog"),
            {URIRef("http://example.org/animals#Dog")},
            id="classes-curie",
            marks=pytest.mark.xfail(strict=True, reason="#226"),
        ),
        pytest.param(
            FIXTURES / "docs" / "deprecated_terms.ttl",
            (),
            None,
            id="deprecated-class",
            marks=pytest.mark.xfail(strict=True, reason="#228"),
        ),
    ],
)
def test_shacl_gen_one_shape_per_selected_class(source, args, selected, tmp_path, monkeypatch):
    out = tmp_path / "shapes.ttl"
    _run(tmp_path, monkeypatch, "shacl-gen", source, *args, "-o", out)
    classes = selected if selected is not None else _classes(_parse(source))
    shapes = _parse(out)
    targeted = set(shapes.objects(None, SH.targetClass))
    counts = {
        "selected classes": len(classes),
        "node shapes": len(set(shapes.subjects(RDF.type, SH.NodeShape))),
        "selected classes targeted": len(classes & targeted),
    }
    _assert_holds("shacl-gen", counts=counts)
