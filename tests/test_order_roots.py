"""`roots:` entries that anchor nothing are reported, and malformed ones refused (#241).

Before, a root that did not expand, or named nothing the section sorted, was skipped at exit
0 without a word. Each fixture puts its root's branch alphabetically last, so a root that
works is visible as that branch moving to the front.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import Graph, URIRef

from rdf_construct.cli import cli
from rdf_construct.core import InvalidRootError, check_roots, resolve_roots
from rdf_construct.core.ordering import sort_subjects, sort_with_roots
from rdf_construct.core.utils import CurieError

SOURCE = """\
@prefix ex: <http://example.org/roots#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix imp: <http://example.org/imported#> .

ex:Alpha a owl:Class .
ex:Beta a owl:Class ; rdfs:subClassOf ex:Alpha .
ex:Zed a owl:Class .
ex:Yak a owl:Class ; rdfs:subClassOf ex:Zed .
ex:Under a owl:Class ; rdfs:subClassOf imp:Parent .
ex:Part a owl:Class, owl:ObjectProperty .
ex:aProp a owl:ObjectProperty ; rdfs:subPropertyOf ex:Part .
ex:Alpha ex:usedOnly ex:Zed .
"""

EX = "http://example.org/roots#"


def _run(tmp_path: Path, config: str, *args: str) -> tuple[Result, Path]:
    source = tmp_path / "src.ttl"
    source.write_text(SOURCE)
    cfg = tmp_path / "order.yml"
    cfg.write_text(config)
    out = tmp_path / "out"
    result = CliRunner().invoke(cli, ["order", str(source), str(cfg), "-o", str(out), *args])
    return result, out


def _profile(roots: str, *, sort: str = "topological", extra: str = "") -> str:
    return (
        "profiles:\n"
        "  p:\n"
        "    unclaimed: ignore\n"
        "    sections:\n"
        f"      - classes: {{select: classes, sort: {sort}, roots: {roots}}}\n"
        f"{extra}"
    )


def _subjects(out: Path, profile: str = "p") -> list[str]:
    text = (out / f"src-{profile}.ttl").read_text()
    return [line for line in text.splitlines() if line.startswith("ex:")]


# -- Roots that anchor nothing: reported, written, exit 0 --


def test_a_working_root_leads_and_says_nothing(tmp_path: Path) -> None:
    result, out = _run(tmp_path, _profile("[ex:Zed]"))
    assert result.exit_code == 0, result.output
    assert "ignored" not in result.output
    assert _subjects(out)[:2] == ["ex:Zed", "ex:Yak"]


def test_an_undeclared_prefix_is_reported_with_the_declared_ones(tmp_path: Path) -> None:
    result, out = _run(tmp_path, _profile("[org:Person]"))
    assert result.exit_code == 0, result.output
    assert "⚠ profile 'p', section 'classes': 1 root ignored" in result.output
    assert (
        "org:Person — prefix 'org:' is not declared by this source "
        "(declared: ex:, imp:, owl:, rdf:, rdfs:, xml:, xsd:)"
    ) in result.output
    assert (out / "src-p.ttl").exists()


def test_a_root_not_in_the_ontology_prints_its_iri(tmp_path: Path) -> None:
    result, out = _run(tmp_path, _profile("[ex:Nothing]"))
    assert result.exit_code == 0, result.output
    assert f"ex:Nothing → {EX}Nothing — not in this ontology" in result.output
    assert (out / "src-p.ttl").exists()


def test_a_root_the_section_does_not_select_is_reported(tmp_path: Path) -> None:
    """An imported parent is in the graph, but no class section selects it."""
    result, out = _run(tmp_path, _profile("[imp:Parent]"))
    assert result.exit_code == 0, result.output
    assert (
        "imp:Parent → http://example.org/imported#Parent — in this ontology, "
        "but not selected by this section"
    ) in result.output


def test_a_root_an_earlier_section_placed_names_that_section(tmp_path: Path) -> None:
    """A class punned as a property is placed by `classes`; rooting `obj_props` on it misses."""
    config = (
        "profiles:\n"
        "  p:\n"
        "    unclaimed: ignore\n"
        "    sections:\n"
        "      - classes: {select: classes, sort: topological}\n"
        "      - obj_props: {select: obj_props, sort: topological, roots: [ex:Part]}\n"
    )
    result, _ = _run(tmp_path, config)
    assert result.exit_code == 0, result.output
    assert "⚠ profile 'p', section 'obj_props': 1 root ignored" in result.output
    assert f"ex:Part → {EX}Part — already placed by section 'classes'" in result.output


def test_roots_sharing_an_undeclared_prefix_share_a_line(tmp_path: Path) -> None:
    """A shared config run on the wrong ontology: one line per prefix, not per root."""
    result, _ = _run(tmp_path, _profile("[org:A, org:B, nope:C]"))
    assert result.exit_code == 0, result.output
    assert "⚠ profile 'p', section 'classes': 3 roots ignored" in result.output
    assert "org:A, org:B — prefix 'org:' is not declared" in result.output
    assert "nope:C — prefix 'nope:' is not declared" in result.output
    assert result.output.count("(declared:") == 2


def test_a_term_used_only_as_a_predicate_is_in_the_ontology(tmp_path: Path) -> None:
    """An undeclared property is still in the graph: not selected, not absent."""
    result, _ = _run(tmp_path, _profile("[ex:usedOnly]"))
    assert result.exit_code == 0, result.output
    assert "in this ontology, but not selected by this section" in result.output
    assert "not in this ontology" not in result.output


def test_roots_on_an_alphabetical_sort_are_reported(tmp_path: Path) -> None:
    result, out = _run(tmp_path, _profile("[ex:Zed]", sort="alpha"))
    assert result.exit_code == 0, result.output
    assert (
        "⚠ profile 'p', section 'classes': roots ignored — sort is 'alpha'; only a "
        "topological sort has branches to lead with."
    ) in result.output
    assert _subjects(out)[0] == "ex:Alpha"


def test_several_misses_are_one_block(tmp_path: Path) -> None:
    result, out = _run(tmp_path, _profile("[ex:Nothing, ex:Zed, org:Person]"))
    assert result.exit_code == 0, result.output
    assert "⚠ profile 'p', section 'classes': 2 roots ignored" in result.output
    assert _subjects(out)[:2] == ["ex:Zed", "ex:Yak"]


@pytest.mark.parametrize(
    "roots",
    ["[ex:Alpha, ex:Beta]", "[ex:Zed, ex:Zed]", "[]", "null"],
    ids=["overlapping", "duplicate", "empty", "null"],
)
def test_harmless_roots_are_silent(tmp_path: Path, roots: str) -> None:
    """`ex:Beta` is under `ex:Alpha`, whose branch takes it: it is placed, not missing."""
    result, _ = _run(tmp_path, _profile(roots))
    assert result.exit_code == 0, result.output
    assert "ignored" not in result.output


# -- Roots that are not roots at all: refused before anything is written --


@pytest.mark.parametrize(
    "roots,message",
    [
        (
            "ex:Zed",
            "roots: expected a list of CURIEs or IRIs, such as [ex:Animal]; got 'ex:Zed'",
        ),
        ("[42]", "root 42 is not a CURIE or an IRI: expected a string"),
        (
            "[Animal]",
            "root 'Animal' is not a CURIE or an IRI; write ex:Term, <http://…> or http://…",
        ),
    ],
    ids=["scalar", "number", "no-prefix"],
)
def test_a_malformed_roots_value_is_refused(tmp_path: Path, roots: str, message: str) -> None:
    result, out = _run(tmp_path, _profile(roots))
    assert result.exit_code == 2, result.output
    assert "Nothing was written:" in result.output
    assert f"profile 'p', section 'classes': {message}" in result.output
    assert not out.exists()


def test_a_refusal_in_a_later_profile_writes_no_earlier_one(tmp_path: Path) -> None:
    config = (
        "profiles:\n"
        "  first:\n"
        "    sections:\n"
        "      - classes: {sort: topological, roots: [ex:Zed]}\n"
        "  second:\n"
        "    sections:\n"
        "      - classes: {sort: topological, roots: ex:Zed}\n"
    )
    result, out = _run(tmp_path, config)
    assert result.exit_code == 2, result.output
    assert "profile 'second', section 'classes'" in result.output
    assert not out.exists()


# -- The library --


def _graph() -> Graph:
    g = Graph(bind_namespaces="core")
    g.parse(data=SOURCE, format="turtle")
    return g


def test_resolve_roots_reports_each_distinct_root_in_order() -> None:
    resolved = resolve_roots(_graph(), ["ex:Zed", "org:Person", "<urn:x>", "ex:Zed"])
    assert [r.text for r in resolved] == ["ex:Zed", "org:Person", "<urn:x>"]
    assert resolved[0].iri == URIRef(EX + "Zed")
    assert resolved[1].iri is None
    assert isinstance(resolved[1].error, CurieError)
    assert resolved[1].error.prefix == "org"
    assert resolved[2].iri == URIRef("urn:x")


def test_resolve_roots_never_uses_rdflibs_prefix_table() -> None:
    """`foaf:` is in rdflib's own table, not in this source."""
    assert resolve_roots(_graph(), ["foaf:Person"])[0].iri is None


@pytest.mark.parametrize("roots", [None, []])
def test_no_roots_resolve_to_nothing(roots: object) -> None:
    assert resolve_roots(_graph(), roots) == []
    assert check_roots(roots) == []


@pytest.mark.parametrize("roots", ["ex:Zed", [42], ["Animal"], [""], ["<>"], {"a": 1}])
def test_malformed_roots_raise(roots: object) -> None:
    g = _graph()
    assert check_roots(roots)
    with pytest.raises(InvalidRootError):
        resolve_roots(g, roots)
    with pytest.raises(InvalidRootError):
        sort_with_roots(g, {URIRef(EX + "Zed")}, "topological", roots)  # type: ignore[arg-type]
    with pytest.raises(InvalidRootError):
        sort_subjects(g, {URIRef(EX + "Zed")}, "alpha", roots)  # type: ignore[arg-type]


def test_invalid_root_error_is_a_value_error() -> None:
    assert issubclass(InvalidRootError, ValueError)


def test_an_undeclared_root_is_passed_over_by_the_sort() -> None:
    g = _graph()
    subjects = {URIRef(EX + n) for n in ("Alpha", "Beta", "Zed", "Yak")}
    assert sort_with_roots(g, subjects, "topological", ["org:X", "ex:Zed"])[:2] == [
        URIRef(EX + "Zed"),
        URIRef(EX + "Yak"),
    ]
