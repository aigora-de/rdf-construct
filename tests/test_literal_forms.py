"""Typed literals keep the lexical form the source wrote (#377).

rdflib normalises a typed literal whenever one is constructed, and a parse constructs every
literal it reads, so every command used to write ``"007"^^xsd:integer`` as ``"7"`` and merge
``"1"^^xsd:boolean`` into ``"true"``. The CLI now runs every command inside
``preserve_literal_forms``, which switches that off and guards rdflib's Turtle, TriG and N3
serialisers, which would otherwise write ``"1"^^xsd:boolean`` bare as ``1``, an ``xsd:integer``.

Every output here is read back **without normalisation**. A test that reads it back normalised
agrees with whatever the command wrote, so it can see neither the merge nor the changed datatype.
The fixture, ``tests/fixtures/literals/lit.ttl``, states 16 triples; rdflib's default gives 14.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import rdflib
from click.testing import CliRunner, Result
from rdflib import BNode, Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, SH, XSD
from rdflib.plugin import get as get_plugin
from rdflib.plugins.serializers.n3 import N3Serializer
from rdflib.plugins.serializers.trig import TrigSerializer
from rdflib.plugins.serializers.turtle import TurtleSerializer
from rdflib.serializer import Serializer

from rdf_construct.cli import cli
from rdf_construct.core import preserve_literal_forms
from rdf_construct.core.literal_forms import GUARDED_FORMATS, bare_form_is_faithful
from rdf_construct.core.predicate_tiers import value_key
from rdf_construct.localise.entities import is_deprecated
from rdf_construct.merge.config import ConflictConfig, MergeConfig, SourceConfig
from rdf_construct.merge.merger import OntologyMerger
from tests.test_cli_smoke import assert_no_crash

FIXTURE = Path(__file__).parent / "fixtures" / "literals" / "lit.ttl"
EX = Namespace("http://example.org/lit#")

PREFIXES = """\
@prefix ex: <http://example.org/lit#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
"""


def read(path: Path, fmt: str | None = None) -> Graph:
    """Parse a file the way the CLI does: every literal as written."""
    with preserve_literal_forms():
        return Graph().parse(path, format=fmt)


def read_dataset(path: Path) -> Dataset:
    """Parse a TriG file the way the CLI does. A plain ``Graph`` reads TriG as 0 triples (#362)."""
    with preserve_literal_forms():
        dataset = Dataset()
        dataset.parse(path, format="trig")
        return dataset


def literals(graph: Graph | Dataset) -> set[str]:
    """Every literal object, as N3, so a test failure names the form and the datatype."""
    if isinstance(graph, Dataset):
        objects = [o for _, _, o, _ in graph.quads()]
    else:
        objects = list(graph.objects())
    return {o.n3() for o in objects if isinstance(o, Literal)}


def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *argv: object) -> Result:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, [str(a) for a in argv])
    assert_no_crash(result)
    assert result.exit_code in (0, 1), result.output
    return result


SOURCE = read(FIXTURE)


def test_the_fixture_shows_the_bug() -> None:
    """The fixture is only useful if rdflib's default visibly loses something from it."""
    assert len(SOURCE) == 16
    assert len(Graph().parse(FIXTURE)) == 14
    assert rdflib.NORMALIZE_LITERALS is True


# -- the guard --------------------------------------------------------------------------------


def _lit(lexical: str, datatype: URIRef) -> Literal:
    return Literal(lexical, datatype=datatype, normalize=False)


@pytest.mark.parametrize(
    ("literal", "bare", "faithful"),
    [
        (_lit("7", XSD.integer), "7", True),
        (_lit("007", XSD.integer), "007", False),
        (_lit("+5", XSD.integer), "+5", False),
        (_lit("true", XSD.boolean), "true", True),
        (_lit("1", XSD.boolean), "1", False),
        (_lit("0", XSD.boolean), "0", False),
        (_lit("1.50", XSD.decimal), "1.50", True),
        (_lit("1", XSD.decimal), "1.0", False),
        (_lit("20.0", XSD.double), "2e+01", False),
        (_lit("abc", XSD.integer), "abc", False),
    ],
    ids=lambda v: v.n3() if isinstance(v, Literal) else str(v),
)
def test_a_literal_is_bare_only_when_that_reads_back_unchanged(
    literal: Literal, bare: str, faithful: bool
) -> None:
    assert bare_form_is_faithful(literal, bare) is faithful


@pytest.mark.parametrize("fmt", ["turtle", "n3"])
def test_the_guarded_serialisers_write_every_form_as_given(fmt: str) -> None:
    with preserve_literal_forms():
        text = SOURCE.serialize(format=fmt)
        back = Graph().parse(data=text, format=fmt)
    assert len(back) == 16
    assert literals(back) == literals(SOURCE)


def test_the_guarded_trig_serialiser_writes_every_form_as_given() -> None:
    with preserve_literal_forms():
        dataset = Dataset()
        dataset.parse(data=SOURCE.serialize(format="trig"), format="trig")
    assert literals(dataset) == literals(SOURCE)


def test_unguarded_turtle_would_change_a_datatype() -> None:
    """Why the guard exists: rdflib's own serialiser writes "1"^^xsd:boolean bare, as 1."""
    rdflib.NORMALIZE_LITERALS = False
    try:
        back = Graph().parse(data=SOURCE.serialize(format="turtle"), format="turtle")
    finally:
        rdflib.NORMALIZE_LITERALS = True
    assert '"1"^^<http://www.w3.org/2001/XMLSchema#integer>' in literals(back)


# -- set and restored -------------------------------------------------------------------------


def _stock() -> None:
    assert rdflib.NORMALIZE_LITERALS is True
    assert get_plugin("turtle", Serializer) is TurtleSerializer
    assert get_plugin("trig", Serializer) is TrigSerializer
    assert get_plugin("n3", Serializer) is N3Serializer


def test_the_context_manager_restores_and_nests() -> None:
    with preserve_literal_forms():
        with preserve_literal_forms():
            assert rdflib.NORMALIZE_LITERALS is False
        assert rdflib.NORMALIZE_LITERALS is False
        for name, cls in GUARDED_FORMATS.items():
            assert get_plugin(name, Serializer) is cls
    _stock()


def test_the_context_manager_restores_on_an_exception() -> None:
    with pytest.raises(RuntimeError), preserve_literal_forms():
        raise RuntimeError("flatline")
    _stock()


@pytest.mark.parametrize(
    "argv",
    [["--help"], ["--version"], ["no-such-command"], ["cast", "--no-such-option"]],
    ids=["help", "version", "usage-error", "bad-option"],
)
def test_the_cli_leaves_rdflib_as_it_found_it(argv: list[str]) -> None:
    CliRunner().invoke(cli, argv)
    _stock()


def test_a_command_runs_without_normalisation_and_restores_it(tmp_path, monkeypatch) -> None:
    run(tmp_path, monkeypatch, "cast", FIXTURE, "-f", "nt", "-o", tmp_path / "out")
    _stock()


def test_a_crash_restores_it(tmp_path, monkeypatch) -> None:
    seen: list[bool] = []

    class Exploding:
        def __init__(self, *args: object, **kwargs: object) -> None:
            seen.append(rdflib.NORMALIZE_LITERALS)
            raise RuntimeError("flatline")

    # ``rdf_construct.cli`` is the Click group, so reach the module through ``sys.modules``.
    monkeypatch.setattr(sys.modules["rdf_construct.cli"], "CastConverter", Exploding)
    result = CliRunner().invoke(cli, ["cast", str(FIXTURE), "-f", "nt", "-o", str(tmp_path / "o")])
    assert result.exit_code == 2
    assert seen == [False]
    _stock()


# -- every command, end to end ----------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["nt", "xml", "n3"])
def test_cast_writes_every_form_as_given(fmt: str, tmp_path, monkeypatch) -> None:
    run(tmp_path, monkeypatch, "cast", FIXTURE, "-f", fmt, "-o", tmp_path / "out")
    [written] = (tmp_path / "out").iterdir()
    back = read(written, fmt)
    assert len(back) == 16
    assert literals(back) == literals(SOURCE)


def test_cast_to_turtle_writes_every_form_as_given(tmp_path, monkeypatch) -> None:
    """From N-Triples, because ``cast`` refuses Turtle to Turtle (#330)."""
    run(tmp_path, monkeypatch, "cast", FIXTURE, "-f", "nt", "-o", tmp_path / "nt")
    [ntriples] = (tmp_path / "nt").iterdir()
    run(tmp_path, monkeypatch, "cast", ntriples, "-f", "turtle", "-o", tmp_path / "out")
    [written] = (tmp_path / "out").iterdir()
    back = read(written, "turtle")
    assert len(back) == 16
    assert literals(back) == literals(SOURCE)


def test_cast_to_trig_writes_every_form_as_given(tmp_path, monkeypatch) -> None:
    run(tmp_path, monkeypatch, "cast", FIXTURE, "-f", "trig", "-o", tmp_path / "out")
    [written] = (tmp_path / "out").iterdir()
    assert literals(read_dataset(written)) == literals(SOURCE)


@pytest.mark.xfail(
    strict=True,
    reason="#462: rdflib's JSON-LD serialiser writes booleans and numbers from their value",
)
def test_cast_to_json_ld_writes_every_form_as_given(tmp_path, monkeypatch) -> None:
    run(tmp_path, monkeypatch, "cast", FIXTURE, "-f", "json-ld", "-o", tmp_path / "out")
    [written] = (tmp_path / "out").iterdir()
    back = read(written, "json-ld")
    assert len(back) == 16
    assert literals(back) == literals(SOURCE)


def test_merge_writes_every_form_as_given(tmp_path, monkeypatch) -> None:
    out = tmp_path / "merged.ttl"
    run(tmp_path, monkeypatch, "merge", FIXTURE, "-o", out)
    back = read(out)
    assert literals(back) == literals(SOURCE)


def test_order_writes_every_form_as_given(tmp_path, monkeypatch) -> None:
    config = tmp_path / "order.yml"
    config.write_text(
        "profiles:\n"
        "  all:\n"
        "    sections:\n"
        "      - classes: {select: classes, sort: alpha}\n"
        "      - object_properties: {select: obj_props, sort: alpha}\n"
        "      - individuals: {select: individuals, sort: alpha}\n",
        encoding="utf-8",
    )
    run(tmp_path, monkeypatch, "order", FIXTURE, config, "-o", tmp_path / "out")
    [written] = (tmp_path / "out").glob("*.ttl")
    assert literals(read(written)) == literals(SOURCE)


def test_split_writes_every_form_as_given(tmp_path, monkeypatch) -> None:
    out = tmp_path / "modules"
    run(tmp_path, monkeypatch, "split", FIXTURE, "--by-namespace", "-o", out)
    union = Graph()
    for module in out.glob("*.ttl"):
        union += read(module)
    assert literals(union) == literals(SOURCE)


def test_refactor_rename_writes_every_form_as_given(tmp_path, monkeypatch) -> None:
    out = tmp_path / "renamed.ttl"
    run(
        tmp_path,
        monkeypatch,
        "refactor",
        "rename",
        FIXTURE,
        "--from",
        EX.p,
        "--to",
        EX.q,
        "-o",
        out,
    )
    back = read(out)
    assert len(back) == 16
    assert literals(back) == literals(SOURCE)


def test_localise_round_trip_writes_every_form_as_given(tmp_path, monkeypatch) -> None:
    source = tmp_path / "ont.ttl"
    source.write_text(
        FIXTURE.read_text(encoding="utf-8") + 'ex:A rdfs:label "A"@en .\n', encoding="utf-8"
    )
    strings = tmp_path / "de.yml"
    merged = tmp_path / "merged.ttl"
    run(tmp_path, monkeypatch, "localise", "extract", source, "-l", "de", "-o", strings)
    run(tmp_path, monkeypatch, "localise", "merge", source, strings, "-o", merged)
    assert literals(read(merged)) == literals(read(source))


def test_shacl_gen_reads_a_cardinality_by_value(tmp_path, monkeypatch) -> None:
    out = tmp_path / "shapes.ttl"
    run(tmp_path, monkeypatch, "shacl-gen", FIXTURE, "-o", out)
    shapes = read(out)
    counts = {int(o) for p in (SH.minCount, SH.maxCount) for o in shapes.objects(None, p)}
    assert counts == {1}


def test_diff_reports_a_change_of_lexical_form(tmp_path) -> None:
    old = tmp_path / "old.ttl"
    new = tmp_path / "new.ttl"
    old.write_text(PREFIXES + 'ex:x a ex:C ; ex:v "01"^^xsd:integer .\n', encoding="utf-8")
    new.write_text(PREFIXES + 'ex:x a ex:C ; ex:v "1"^^xsd:integer .\n', encoding="utf-8")
    result = CliRunner().invoke(cli, ["diff", str(old), str(new)])
    assert_no_crash(result)
    assert result.exit_code == 1, result.output
    assert '- ex:v "01"^^xsd:integer' in result.output
    assert '+ ex:v "1"^^xsd:integer' in result.output


def test_a_bare_number_in_the_source_is_still_canonicalised(tmp_path, monkeypatch) -> None:
    """The migration row's qualifier: rdflib's parser canonicalises a bare 007 whatever the flag."""
    source = tmp_path / "bare.ttl"
    source.write_text(PREFIXES + "ex:x ex:v 007 .\n", encoding="utf-8")
    run(tmp_path, monkeypatch, "cast", source, "-f", "nt", "-o", tmp_path / "out")
    [written] = (tmp_path / "out").iterdir()
    assert literals(read(written, "nt")) == {'"7"^^<http://www.w3.org/2001/XMLSchema#integer>'}


# -- owl:deprecated ---------------------------------------------------------------------------


def test_refactor_deprecate_sees_a_boolean_one_as_already_deprecated(tmp_path, monkeypatch) -> None:
    """Before #377's fix the parse turned "1" into "true"; the reader must not depend on that."""
    source = tmp_path / "ont.ttl"
    source.write_text(
        PREFIXES + 'ex:Old a owl:Class ; owl:deprecated "1"^^xsd:boolean .\n', encoding="utf-8"
    )
    out = tmp_path / "out.ttl"
    run(tmp_path, monkeypatch, "refactor", "deprecate", source, "--entity", EX.Old, "-o", out)
    assert list(read(out).objects(EX.Old, OWL.deprecated)) == [_lit("1", XSD.boolean)]


@pytest.mark.parametrize(
    ("form", "deprecated"),
    [('"true"^^xsd:boolean', True), ('"1"^^xsd:boolean', True), ('"TRUE"^^xsd:boolean', False)],
)
def test_localise_reads_deprecated_by_its_lexical_form(form: str, deprecated: bool, tmp_path):
    """A migration line: "TRUE" is not a boolean's lexical form, and is no longer normalised."""
    source = tmp_path / "ont.ttl"
    source.write_text(
        PREFIXES + f"ex:Old a owl:Class ; owl:deprecated {form} .\n", encoding="utf-8"
    )
    assert is_deprecated(read(source), EX.Old) is deprecated


# -- merge: both forms kept, conflicts compare values -----------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        (_lit("1", XSD.integer), _lit("01", XSD.integer), True),
        (_lit("true", XSD.boolean), _lit("1", XSD.boolean), True),
        (
            _lit("2024-01-01T00:00:00Z", XSD.dateTime),
            _lit("2024-01-01T00:00:00+00:00", XSD.dateTime),
            True,
        ),
        (_lit("2", XSD.integer), _lit("3", XSD.integer), False),
        (_lit("1", XSD.integer), _lit("1", XSD.int), False),
        (_lit("abc", XSD.integer), _lit("abc", XSD.integer), True),
        (_lit("abc", XSD.integer), _lit(" abc", XSD.integer), False),
    ],
)
def test_value_key_folds_one_value_written_two_ways(a: Literal, b: Literal, same: bool) -> None:
    assert (value_key(a) == value_key(b)) is same


def test_value_key_leaves_an_ill_typed_literal_as_written() -> None:
    literal = _lit("abc", XSD.integer)
    assert value_key(literal).n3() == literal.n3()


def test_merge_keeps_both_forms_and_raises_no_conflict_between_them(tmp_path) -> None:
    a = tmp_path / "a.ttl"
    b = tmp_path / "b.ttl"
    a.write_text(PREFIXES + 'ex:x ex:v "1"^^xsd:integer ; ex:w "2"^^xsd:integer .\n', "utf-8")
    b.write_text(PREFIXES + 'ex:x ex:v "01"^^xsd:integer ; ex:w "3"^^xsd:integer .\n', "utf-8")
    tiers = {"load_bearing": [str(EX.v), str(EX.w)]}
    config = MergeConfig(
        sources=[SourceConfig(a, priority=2), SourceConfig(b, priority=1)],
        conflicts=ConflictConfig(predicate_tiers=tiers),
    )
    with preserve_literal_forms():
        result = OntologyMerger(config).merge()
    assert [c.predicate for c in result.conflicts] == [EX.w]
    assert set(result.merged_graph.objects(EX.x, EX.v)) == {
        _lit("1", XSD.integer),
        _lit("01", XSD.integer),
    }


def test_merge_keeps_two_restrictions_that_differ_only_in_lexical_form(
    tmp_path, monkeypatch
) -> None:
    """Faithful to RDF 1.1, and a migration line: they are two blank-node structures."""
    sources = []
    for name, form in (("a", "1"), ("b", "01")):
        path = tmp_path / f"{name}.ttl"
        path.write_text(
            PREFIXES
            + "ex:A a owl:Class ; rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:p ; "
            + f'owl:cardinality "{form}"^^xsd:nonNegativeInteger ] .\n',
            encoding="utf-8",
        )
        sources.append(path)
    out = tmp_path / "merged.ttl"
    run(tmp_path, monkeypatch, "merge", *sources, "-o", out)
    merged = read(out)
    restrictions = {s for s in merged.subjects(None, OWL.Restriction) if isinstance(s, BNode)}
    assert len(restrictions) == 2


# -- cq-test: a literal constant in a pattern matches by term ---------------------------------


def test_cq_test_matches_a_pattern_constant_by_term(tmp_path, monkeypatch) -> None:
    ontology = tmp_path / "ont.ttl"
    ontology.write_text(PREFIXES + 'ex:x ex:v "007"^^xsd:integer .\n', encoding="utf-8")
    questions = tmp_path / "cq.yml"
    questions.write_text(
        'version: "1.0"\n'
        "prefixes:\n"
        '  ex: "http://example.org/lit#"\n'
        "questions:\n"
        "  - id: by-term\n"
        '    name: "A pattern constant matches by term"\n'
        '    query: "ASK { ex:x ex:v 7 }"\n'
        "    expect: false\n"
        "  - id: by-value\n"
        '    name: "A FILTER compares values"\n'
        '    query: "ASK { ex:x ex:v ?v FILTER(?v = 7) }"\n'
        "    expect: true\n",
        encoding="utf-8",
    )
    result = run(tmp_path, monkeypatch, "cq-test", ontology, questions)
    assert result.exit_code == 0, result.output
