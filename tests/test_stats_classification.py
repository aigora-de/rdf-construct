"""`stats` and `diff` classify through `core.vocab` (#138); `stats` reports a union (#140).

Every test drives the CLI or the public library functions and reads what they report: the JSON
fields, the text and markdown lines, `diff`'s labels and JSON keys, and the exit code. The
per-type fixtures are parametrised over `core.vocab`'s sets themselves, so a type added there is
tested here without a change.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import BNode, Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from rdf_construct.cli import _union_inputs, cli
from rdf_construct.core.vocab import (
    ANNOTATION_PROPERTY_TYPES,
    CLASS_TYPES,
    DATATYPE_PROPERTY_TYPES,
    GENERIC_PROPERTY_TYPES,
    OBJECT_PROPERTY_TYPES,
)
from rdf_construct.diff import EntityType, compare_files, filter_diff
from rdf_construct.stats import collect_stats, compare_stats

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "examples" / "stats"
GUIDE = ROOT / "docs" / "user_guides" / "STATS_GUIDE.md"

PREFIXES = """\
@prefix ex: <http://example.org/ont#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
"""

HEADER = "ex: a owl:Ontology .\n"

#: #138's reproducer, verbatim: three classes, nine properties, one individual.
VOCAB = (
    PREFIXES
    + HEADER
    + """
ex:Animal  a owl:Class .
ex:Legacy  a rdfs:Class .
ex:Retired a owl:DeprecatedClass .

ex:hasAncestor a owl:TransitiveProperty .
ex:marriedTo   a owl:SymmetricProperty .
ex:hasSSN      a owl:InverseFunctionalProperty .
ex:hasMother   a owl:FunctionalProperty .
ex:oldProp     a owl:DeprecatedProperty .
ex:plainProp   a rdf:Property .

ex:realObj  a owl:ObjectProperty .
ex:realData a owl:DatatypeProperty .
ex:realAnn  a owl:AnnotationProperty .

ex:rex a ex:Animal .
"""
)

BASIC_KEYS = (
    "classes",
    "object_properties",
    "datatype_properties",
    "annotation_properties",
    "other_properties",
    "individuals",
)

#: Each `core.vocab` type, the `stats` count it lands in, and `diff`'s JSON key and text label.
VOCAB_CASES = [
    *((t, "classes", "classes", "Class") for t in sorted(CLASS_TYPES)),
    *(
        (t, "object_properties", "object_properties", "ObjectProperty")
        for t in sorted(OBJECT_PROPERTY_TYPES)
    ),
    *(
        (t, "datatype_properties", "datatype_properties", "DataProperty")
        for t in sorted(DATATYPE_PROPERTY_TYPES)
    ),
    *(
        (t, "annotation_properties", "annotation_properties", "AnnotationProperty")
        for t in sorted(ANNOTATION_PROPERTY_TYPES)
    ),
    *(
        (t, "other_properties", "other_properties", "Property")
        for t in sorted(GENERIC_PROPERTY_TYPES)
    ),
]


def _write(path: Path, body: str, *, header: bool = True) -> Path:
    path.write_text(PREFIXES + (HEADER if header else "") + body)
    return path


def _invoke(*argv: str | Path) -> Result:
    return CliRunner().invoke(cli, [str(a) for a in argv])


def _stats_json(*files: Path, extra: tuple[str, ...] = ()) -> dict:
    result = _invoke("stats", *files, "-f", "json", *extra)
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def _basic(data: dict) -> dict[str, int]:
    return {k: data["basic"][k] for k in BASIC_KEYS}


def _diff_added(tmp_path: Path, body: str) -> dict[str, list[dict]]:
    old = tmp_path / "old.ttl"
    old.write_text(PREFIXES)
    new = _write(tmp_path / "new.ttl", body)
    result = _invoke("diff", old, new, "--format", "json")
    assert result.exit_code == 1, result.output
    added: dict[str, list[dict]] = json.loads(result.stdout)["added"]
    return added


def _keys_of(added: dict[str, list[dict]], local: str) -> list[str]:
    uri = f"http://example.org/ont#{local}"
    return [key for key, entries in added.items() for e in entries if e["uri"] == uri]


# --- each core.vocab type alone --------------------------------------------------------------


@pytest.mark.parametrize(
    ("rdf_type", "count", "json_key", "label"),
    VOCAB_CASES,
    ids=[str(c[0]).rsplit("#", 1)[-1] for c in VOCAB_CASES],
)
class TestEachVocabType:
    """A term declared with one `core.vocab` type alone lands in exactly one place."""

    def test_stats_counts_it_once(
        self, tmp_path: Path, rdf_type: URIRef, count: str, json_key: str, label: str
    ) -> None:
        data = _stats_json(_write(tmp_path / "t.ttl", f"ex:t a <{rdf_type}> .\n"))
        expected = {k: 0 for k in BASIC_KEYS}
        expected[count] = 1
        assert _basic(data) == expected

    def test_diff_lists_it_under_its_kind(
        self, tmp_path: Path, rdf_type: URIRef, count: str, json_key: str, label: str
    ) -> None:
        added = _diff_added(tmp_path, f"ex:t a <{rdf_type}> .\n")
        assert _keys_of(added, "t") == [json_key]

        result = _invoke("diff", tmp_path / "old.ttl", tmp_path / "new.ttl")
        assert f"+ {label} ex:t" in result.stdout


# --- #138's reproducer -----------------------------------------------------------------------


class TestReproducer:
    def test_stats(self, tmp_path: Path) -> None:
        data = _stats_json(_write(tmp_path / "vocab.ttl", VOCAB, header=False))
        assert _basic(data) == {
            "classes": 3,
            "object_properties": 4,
            "datatype_properties": 1,
            "annotation_properties": 1,
            "other_properties": 3,
            "individuals": 1,
        }
        assert data["properties"]["functional"] == 1
        assert data["properties"]["symmetric"] == 1
        # ex:Retired is a class, so it is in the hierarchy figures
        assert data["hierarchy"]["root_classes"] == 3

    def test_stats_text_and_markdown_rows(self, tmp_path: Path) -> None:
        path = _write(tmp_path / "vocab.ttl", VOCAB, header=False)
        text = _invoke("stats", path)
        assert text.exit_code == 0
        assert re.search(r"^  Other Properties:\s+3$", text.stdout, re.M)
        assert re.search(r"^  Individuals:\s+1$", text.stdout, re.M)
        markdown = _invoke("stats", path, "-f", "markdown")
        assert "| Other Properties | 3 |" in markdown.stdout

    def test_diff(self, tmp_path: Path) -> None:
        old = tmp_path / "empty.ttl"
        old.write_text(PREFIXES)
        new = tmp_path / "vocab.ttl"
        new.write_text(VOCAB)
        result = _invoke("diff", old, new)
        assert result.exit_code == 1
        for line in (
            "+ Class ex:Retired",
            "+ ObjectProperty ex:hasAncestor",
            "+ ObjectProperty ex:marriedTo",
            "+ ObjectProperty ex:hasSSN",
            "+ Property ex:hasMother",
            "+ Property ex:oldProp",
            "+ Property ex:plainProp",
            "+ Instance ex:rex",
        ):
            assert line in result.stdout
        assert "ObjectProperty ex:plainProp" not in result.stdout

        data = json.loads(_invoke("diff", old, new, "--format", "json").stdout)
        other = {e["uri"].rsplit("#", 1)[1]: e["type"] for e in data["added"]["other_properties"]}
        assert other == {
            "hasMother": "other_property",
            "oldProp": "other_property",
            "plainProp": "other_property",
        }
        assert [e["uri"] for e in data["added"]["individuals"]] == ["http://example.org/ont#rex"]

        markdown = _invoke("diff", old, new, "--format", "markdown").stdout
        assert "### Other Properties" in markdown


# --- precedence and multi-kind terms ---------------------------------------------------------


class TestKinds:
    def test_a_kind_specific_type_wins_over_a_generic_one(self, tmp_path: Path) -> None:
        body = "ex:q a owl:ObjectProperty , owl:FunctionalProperty .\n"
        data = _stats_json(_write(tmp_path / "q.ttl", body))
        assert data["basic"]["object_properties"] == 1
        assert data["basic"]["other_properties"] == 0
        assert data["properties"]["functional"] == 1
        assert _keys_of(_diff_added(tmp_path, body), "q") == ["object_properties"]

    def test_a_characteristic_beside_rdf_property_is_an_object_property(
        self, tmp_path: Path
    ) -> None:
        body = "ex:r a rdf:Property , owl:TransitiveProperty .\n"
        data = _stats_json(_write(tmp_path / "r.ttl", body))
        assert (data["basic"]["object_properties"], data["basic"]["other_properties"]) == (1, 0)
        assert _keys_of(_diff_added(tmp_path, body), "r") == ["object_properties"]

    def test_two_kinds_count_in_each_and_list_under_one(self, tmp_path: Path) -> None:
        body = "ex:p a owl:ObjectProperty , owl:DatatypeProperty .\n"
        data = _stats_json(_write(tmp_path / "p.ttl", body))
        assert (data["basic"]["object_properties"], data["basic"]["datatype_properties"]) == (1, 1)
        # One distinct property, so coverage divides by one
        assert data["documentation"]["properties_labelled_pct"] == 0.0
        assert _keys_of(_diff_added(tmp_path, body), "p") == ["object_properties"]

    def test_a_punned_class_and_property(self, tmp_path: Path) -> None:
        body = "ex:A2 a owl:Class , owl:ObjectProperty .\n"
        data = _stats_json(_write(tmp_path / "a2.ttl", body))
        assert (data["basic"]["classes"], data["basic"]["object_properties"]) == (1, 1)
        assert data["basic"]["individuals"] == 0
        assert _keys_of(_diff_added(tmp_path, body), "A2") == ["classes"]

    @pytest.mark.parametrize("kind", ["owl:Class", "owl:ObjectProperty"])
    def test_an_own_named_individual_punned_counts_as_an_individual(
        self, tmp_path: Path, kind: str
    ) -> None:
        body = f"ex:S a {kind} , owl:NamedIndividual .\n"
        data = _stats_json(_write(tmp_path / "s.ttl", body))
        assert data["basic"]["individuals"] == 1
        bucket = "classes" if kind == "owl:Class" else "object_properties"
        assert data["basic"][bucket] == 1

    def test_a_named_individual_alone_and_with_a_class(self, tmp_path: Path) -> None:
        body = "ex:A a owl:Class .\nex:i a owl:NamedIndividual .\nex:j a owl:NamedIndividual , ex:A .\n"
        data = _stats_json(_write(tmp_path / "i.ttl", body))
        assert (data["basic"]["classes"], data["basic"]["individuals"]) == (1, 2)

    def test_a_deprecated_class_is_in_the_hierarchy_and_diff_reports_its_superclass(
        self, tmp_path: Path
    ) -> None:
        body = "ex:A a owl:Class .\nex:Old a owl:DeprecatedClass ; rdfs:subClassOf ex:A .\n"
        data = _stats_json(_write(tmp_path / "d.ttl", body))
        assert data["basic"]["classes"] == 2
        assert data["hierarchy"]["max_depth"] == 1
        added = _diff_added(tmp_path, body)
        old = next(e for e in added["classes"] if e["uri"].endswith("#Old"))
        assert old["superclasses"] == ["http://example.org/ont#A"]

    def test_a_deprecated_class_is_in_the_connectivity_figures(self, tmp_path: Path) -> None:
        body = (
            "ex:A a owl:Class .\n"
            "ex:Old a owl:DeprecatedClass .\n"
            "ex:Lone a owl:DeprecatedClass .\n"
            "ex:p a owl:ObjectProperty ; rdfs:domain ex:Old ; rdfs:range ex:Old .\n"
            "ex:q a owl:ObjectProperty ; rdfs:domain ex:A .\n"
        )
        data = _stats_json(_write(tmp_path / "c.ttl", body))
        assert data["connectivity"]["most_connected_class"] == "http://example.org/ont#Old"
        assert data["connectivity"]["most_connected_count"] == 2
        assert data["connectivity"]["isolated_classes"] == 1  # ex:Lone


# --- ownership (#371's guard) ----------------------------------------------------------------


class TestOwnership:
    def test_a_borrowed_characteristic_only_term_is_in_no_count(self, tmp_path: Path) -> None:
        body = (
            "ex:A a owl:Class .\n"
            "foaf:knows a owl:SymmetricProperty .\n"
            "foaf:age a owl:FunctionalProperty .\n"
            "foaf:Old a owl:DeprecatedClass .\n"
            "foaf:Person a owl:Class , owl:NamedIndividual .\n"
        )
        data = _stats_json(_write(tmp_path / "b.ttl", body))
        assert _basic(data) == {
            "classes": 1,
            "object_properties": 0,
            "datatype_properties": 0,
            "annotation_properties": 0,
            "other_properties": 0,
            "individuals": 0,
        }

    def test_borrowed_characteristics_are_not_counted(self, tmp_path: Path) -> None:
        body = (
            "ex:A a owl:Class .\n"
            "ex:r a owl:ObjectProperty .\n"
            "foaf:knows a owl:ObjectProperty , owl:SymmetricProperty ; owl:inverseOf foaf:knows .\n"
            "foaf:mbox a owl:FunctionalProperty , owl:DatatypeProperty .\n"
        )
        data = _stats_json(_write(tmp_path / "b.ttl", body))
        assert data["properties"]["functional"] == 0
        assert data["properties"]["symmetric"] == 0
        assert data["properties"]["inverse_pairs"] == 0
        assert data["basic"]["object_properties"] == 1

    def test_own_characteristics_are_counted(self, tmp_path: Path) -> None:
        body = (
            "ex:r a owl:SymmetricProperty ; owl:inverseOf ex:r .\n"
            "ex:m a owl:FunctionalProperty .\n"
        )
        data = _stats_json(_write(tmp_path / "o.ttl", body))
        props = data["properties"]
        assert (props["functional"], props["symmetric"], props["inverse_pairs"]) == (1, 1, 1)
        # Both properties, of two kinds, are the coverage's denominator
        assert data["properties"]["domain_coverage"] == 0.0
        assert data["basic"]["other_properties"] == 1


# --- #140: the union -------------------------------------------------------------------------


A = "@prefix ex: <http://example.org/#> .\n@prefix owl: <http://www.w3.org/2002/07/owl#> .\nex:A a owl:Class . ex:B a owl:Class . ex:C a owl:Class .\n"
B = "@prefix ex: <http://example.org/#> .\n@prefix owl: <http://www.w3.org/2002/07/owl#> .\nex:D a owl:Class .\n"
C = "@prefix ex: <http://example.org/#> .\n@prefix owl: <http://www.w3.org/2002/07/owl#> .\nex:E a owl:Class . ex:A a owl:Class .\n"
BNODES = (
    "@prefix ex: <http://example.org/#> .\n@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
    "ex:A a owl:Class ; rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:p ;"
    " owl:someValuesFrom ex:A ] .\n"
)


@pytest.fixture
def files(tmp_path: Path) -> dict[str, Path]:
    out = {}
    for name, text in {"a": A, "b": B, "c": C, "bn": BNODES}.items():
        out[name] = tmp_path / f"{name}.ttl"
        out[name].write_text(text)
    return out


class TestUnion:
    def test_two_files(self, files: dict[str, Path]) -> None:
        data = _stats_json(files["a"], files["b"])
        assert data["sources"] == [str(files["a"]), str(files["b"])]
        assert (data["basic"]["triples"], data["basic"]["classes"]) == (4, 4)

    def test_three_files_that_overlap(self, files: dict[str, Path]) -> None:
        result = _invoke("stats", files["a"], files["b"], files["c"])
        assert result.exit_code == 0, result.output
        # ex:A is in a.ttl and c.ttl: one triple, one class
        assert re.search(r"^  Triples:\s+5$", result.stdout, re.M)
        assert re.search(r"^  Classes:\s+5$", result.stdout, re.M)
        assert "Union of 3 files: 5 triples" in result.stderr
        assert "  Loaded 2 triples" in result.stderr  # c.ttl's own count, not what it added

    def test_the_text_and_markdown_headers_name_the_union(self, files: dict[str, Path]) -> None:
        text = _invoke("stats", files["a"], files["b"]).stdout.splitlines()
        assert text[:3] == [
            "Ontology Statistics: 2 files (union)",
            f"  {files['a']}",
            f"  {files['b']}",
        ]
        markdown = _invoke("stats", files["a"], files["b"], "-f", "markdown").stdout
        assert f"**Sources (union of 2 files):**\n\n- `{files['a']}`\n- `{files['b']}`" in markdown

    def test_one_file_keeps_its_header_and_has_a_list_of_sources(
        self, files: dict[str, Path]
    ) -> None:
        assert _stats_json(files["a"])["sources"] == [str(files["a"])]
        assert _invoke("stats", files["a"]).stdout.startswith(
            f"Ontology Statistics: {files['a']}\n"
        )
        markdown = _invoke("stats", files["a"], "-f", "markdown").stdout
        assert f"**Source:** `{files['a']}`" in markdown
        assert "Union of" not in _invoke("stats", files["a"]).stderr

    def test_a_hierarchy_across_files(self) -> None:
        core, care = EXAMPLES / "zoo_core.ttl", EXAMPLES / "zoo_care.ttl"
        alone = _stats_json(care)
        both = _stats_json(core, care)
        # care:Patient is a root on its own; over both it sits under zoo:Mammal
        assert alone["hierarchy"]["max_depth"] == 0
        assert both["hierarchy"]["max_depth"] == 2
        assert both["basic"]["classes"] == 9

    @pytest.mark.parametrize("how", ["twice", "symlink", "another spelling"])
    def test_a_file_named_twice_is_read_once(
        self, files: dict[str, Path], tmp_path: Path, how: str
    ) -> None:
        bn = files["bn"]
        if how == "twice":
            again = bn
        elif how == "symlink":
            again = tmp_path / "link.ttl"
            again.symlink_to(bn)
        else:
            (tmp_path / "sub").mkdir()
            again = tmp_path / "sub" / ".." / "bn.ttl"
        once = _stats_json(bn)
        result = _invoke("stats", bn, files["b"], again, "-f", "json")
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        expected = "is named twice" if again == bn else f"is {bn}"
        assert f"Note: {again} {expected}, read once" in result.stderr
        assert data["sources"] == [str(bn), str(files["b"])]
        assert (
            data["complexity"]["owl_restriction_count"]
            == once["complexity"]["owl_restriction_count"]
        )
        assert data["basic"]["triples"] == once["basic"]["triples"] + 1

    def test_an_empty_file_adds_nothing(self, files: dict[str, Path], tmp_path: Path) -> None:
        empty = tmp_path / "empty.ttl"
        empty.write_text("")
        data = _stats_json(files["a"], empty)
        assert data["basic"]["triples"] == 3
        assert data["sources"] == [str(files["a"]), str(empty)]

    def test_a_file_that_cannot_be_parsed_is_named(
        self, files: dict[str, Path], tmp_path: Path
    ) -> None:
        graph = Graph()
        graph.add((URIRef("http://example.org/#X"), RDF.type, OWL.Class))
        rdfxml = tmp_path / "x.rdf"
        rdfxml.write_text(graph.serialize(format="xml"))
        result = _invoke("stats", files["a"], rdfxml)
        assert result.exit_code == 2
        assert f"Failed to parse {rdfxml}" in result.stderr

    def test_compare_is_unchanged(self, files: dict[str, Path]) -> None:
        result = _invoke("stats", files["a"], files["b"], "--compare", "-f", "json")
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert (data["old_source"], data["new_source"]) == (str(files["a"]), str(files["b"]))
        assert "Union of" not in result.stderr
        assert _invoke("stats", files["a"], "--compare").exit_code == 2
        assert _invoke("stats", files["a"], files["b"], files["c"], "--compare").exit_code == 2

    def test_prefixes_first_file_wins(self, tmp_path: Path) -> None:
        one = tmp_path / "one.ttl"
        one.write_text(B)
        other = tmp_path / "other.ttl"
        other.write_text(
            "@prefix ex: <http://other.example/#> .\n@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            "ex:Z a owl:Class . ex:p a owl:ObjectProperty ; rdfs:domain ex:Z .\n"
        )
        text = _invoke("stats", one, other).stdout
        assert re.search(r"^  Most Connected:\s+ex1:Z \(1 refs\)$", text, re.M)


def test_union_inputs_keeps_the_first_spelling(tmp_path: Path) -> None:
    a = tmp_path / "a.ttl"
    a.write_text("")
    b = tmp_path / "b.ttl"
    b.write_text("")
    link = tmp_path / "l.ttl"
    link.symlink_to(a)
    kept, notes = _union_inputs([a, b, link, a])
    assert kept == [a, b]
    assert notes == [f"Note: {link} is {a}, read once", f"Note: {a} is named twice, read once"]


# --- the library ------------------------------------------------------------------------------


class TestLibrary:
    def test_collect_stats_takes_sources(self, tmp_path: Path) -> None:
        graph = Graph().parse(data=VOCAB, format="turtle")
        stats = collect_stats(graph, sources=["a.ttl", Path("b.ttl")])
        assert stats.sources == ["a.ttl", "b.ttl"]
        assert stats.basic.other_properties == 3
        assert stats.basic.total_properties == 9
        assert collect_stats(graph).sources == ["<graph>"]
        assert stats.to_dict()["sources"] == ["a.ttl", "b.ttl"]
        assert "source" not in stats.to_dict()

    def test_compare_stats_compares_other_properties(self) -> None:
        old = collect_stats(Graph().parse(data=PREFIXES + HEADER, format="turtle"), sources=["v1"])
        new = collect_stats(Graph().parse(data=VOCAB, format="turtle"), sources=["v2"])
        result = compare_stats(old, new)
        change = next(c for c in result.changes if c.metric == "other_properties")
        assert (change.old_value, change.new_value, change.improved) == (0, 3, None)
        assert (result.old_source, result.new_source) == ("v1", "v2")

    def test_filter_diff_selects_other_properties(self, tmp_path: Path) -> None:
        old = tmp_path / "old.ttl"
        old.write_text(PREFIXES)
        new = tmp_path / "new.ttl"
        new.write_text(VOCAB)
        diff = compare_files(old, new)
        types = {e.entity_type for e in diff.added}
        assert EntityType.OTHER_PROPERTY in types

        for name in ("other_properties", "other-properties", "otherprops"):
            only = filter_diff(diff, entity_types={name})
            assert {str(e.uri).rsplit("#", 1)[1] for e in only.added} == {
                "hasMother",
                "oldProp",
                "plainProp",
            }
        everything = filter_diff(diff, entity_types={"properties"})
        assert {e.entity_type for e in everything.added} == {
            EntityType.OBJECT_PROPERTY,
            EntityType.DATATYPE_PROPERTY,
            EntityType.ANNOTATION_PROPERTY,
            EntityType.OTHER_PROPERTY,
        }
        assert len(everything.added) == 9

    def test_entities_on_the_command_line(self, tmp_path: Path) -> None:
        old = tmp_path / "old.ttl"
        old.write_text(PREFIXES)
        new = tmp_path / "new.ttl"
        new.write_text(VOCAB)
        result = _invoke("diff", old, new, "--entities", "other_properties")
        lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip().startswith("+")]
        assert sorted(lines) == [
            "+ Property ex:hasMother",
            "+ Property ex:oldProp",
            "+ Property ex:plainProp",
        ]
        props = _invoke("diff", old, new, "--entities", "properties").stdout
        assert "+ Property ex:plainProp" in props and "+ ObjectProperty ex:realObj" in props


# --- STATS_GUIDE.md's captures ----------------------------------------------------------------


TIMESTAMP = re.compile(r'"timestamp": "[^"]+"')


@pytest.mark.parametrize(
    ("fmt", "fence"), [("text", "text"), ("json", "json"), ("markdown", "markdown")]
)
def test_the_guides_samples_are_what_the_command_prints(fmt: str, fence: str) -> None:
    """`STATS_GUIDE.md`'s Output Formats samples are captures of this run, and must stay ones."""
    argv = ["stats", "examples/stats/zoo_core.ttl", "examples/stats/zoo_care.ttl"]
    guide = GUIDE.read_text(encoding="utf-8")
    assert f"```bash\nrdf-construct {' '.join(argv)}\n```" in guide

    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        result = CliRunner().invoke(cli, [*argv, "-f", fmt])
    finally:
        os.chdir(cwd)
    assert result.exit_code == 0, result.output

    printed = TIMESTAMP.sub('"timestamp": "…"', result.stdout.rstrip("\n"))
    shown = TIMESTAMP.sub('"timestamp": "…"', guide)
    assert f"```{fence}\n{printed}\n```" in shown


def test_the_examples_figures(tmp_path: Path) -> None:
    """The pinned figures, each checked by hand against `core.vocab` (see the files' comments)."""
    data = _stats_json(EXAMPLES / "zoo_core.ttl", EXAMPLES / "zoo_care.ttl")
    assert _basic(data) == {
        "classes": 9,
        "object_properties": 5,
        "datatype_properties": 1,
        "annotation_properties": 1,
        "other_properties": 4,
        "individuals": 3,
    }
    assert (data["properties"]["functional"], data["properties"]["symmetric"]) == (2, 1)
    assert (data["properties"]["with_domain"], data["properties"]["with_range"]) == (7, 6)
    assert data["documentation"]["properties_labelled"] == 7
    # Neither file has a blank node or an rdfs:Datatype (#529, #530)
    for name in ("zoo_core.ttl", "zoo_care.ttl"):
        graph = Graph().parse(EXAMPLES / name, format="turtle")
        assert not any(isinstance(node, BNode) for node in graph.all_nodes())
        assert (None, RDF.type, RDFS.Datatype) not in graph
