"""`merge`'s data-migration rules match only what their patterns say (#492).

A `transform` rule matched every triple in the data, so `delete_matched` emptied the data file at
exit 0. Each test's data carries triples the rule must not touch, and asserts that they survive.
Fixtures are written into ``tmp_path``, so they stay out of the corpus-wide prefix test.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner, Result
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, XSD

from rdf_construct.cli import cli
from rdf_construct.merge import (
    DataMigrator,
    MigrationRule,
    RuleError,
    migrate_data_files,
    migrate_data_graphs,
)
from tests.test_cli_smoke import assert_no_crash, assert_wrote_nothing, snapshot

REPO = Path(__file__).resolve().parent.parent
EX = "http://example.org/ont#"
OLD = "http://old.example.org/ont#"
D = "http://example.org/d#"
OTHER = "http://other.example.org/ont#"
FOAF = "http://xmlns.com/foaf/0.1/"

ONTOLOGY = f"""@prefix ex: <{EX}> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:Person a owl:Class .
"""

# ex:Person is punned; the blank node, d:leg and d:zed are there to be left alone, or moved only
# by the rule that names them
DATA = f"""@prefix ex: <{EX}> .
@prefix old: <{OLD}> .
@prefix d: <{D}> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:Person a owl:Class, owl:NamedIndividual .
d:ann a ex:Person ; ex:fullName "Ann Lee"@en ; ex:age 40 ; ex:note "hi"@en, "is a test" .
d:bob a ex:Company ; ex:fullName "Bob Ray" .
[] a ex:Company ; ex:label "Anon Co" .
d:leg a old:LegacyClass .
d:zed ex:note "untouched" .
"""

SPLIT = {
    "type": "transform",
    "description": "split",
    "match": "?s ex:fullName ?name",
    "construct": [
        {"pattern": "?s ex:givenName ?given", "bind": "STRBEFORE(?name, ' ') AS ?given"},
        {"pattern": "?s ex:familyName ?family", "bind": "STRAFTER(?name, ' ') AS ?family"},
    ],
}
COMPANY = {
    "type": "transform",
    "description": "company",
    "match": "?s a ex:Company",
    "construct": [{"pattern": "?s a ex:Organisation"}],
}


def ex(local: str) -> URIRef:
    return URIRef(EX + local)


def d(local: str) -> URIRef:
    return URIRef(D + local)


def _run(*argv: object) -> Result:
    result = CliRunner().invoke(cli, [str(a) for a in argv])
    assert_no_crash(result)
    return result


def _setup(
    tmp_path: Path,
    rules: list[dict[str, Any]],
    data: str = DATA,
    more_data: dict[str, str] | None = None,
    namespaces: dict[str, Any] | None = None,
) -> tuple[Path, Path, Path]:
    """Write an ontology, data files and a merge config; return config, -o and data output."""
    ont = tmp_path / "ont.ttl"
    ont.write_text(ONTOLOGY)
    paths = []
    for name, text in {"data.ttl": data, **(more_data or {})}.items():
        path = tmp_path / name
        path.write_text(text)
        paths.append(str(path))
    dout = tmp_path / "dout.ttl"
    body: dict[str, Any] = {
        "sources": [str(ont)],
        "migrate_data": {"sources": paths, "output": str(dout), "rules": rules},
    }
    if namespaces:
        body["namespaces"] = namespaces
    config = tmp_path / "merge.yml"
    config.write_text(yaml.safe_dump(body, sort_keys=False))
    return config, tmp_path / "merged.ttl", dout


def _migrate(
    tmp_path: Path, rules: list[dict[str, Any]], *extra: str, **kw: Any
) -> tuple[Result, Graph]:
    config, merged, dout = _setup(tmp_path, rules, **kw)
    result = _run("merge", "-c", config, "-o", merged, *extra)
    assert dout.exists(), result.output
    return result, Graph().parse(dout)


def _untouched(g: Graph) -> None:
    """The triples in DATA that no test's rule names."""
    assert (ex("Person"), RDF.type, OWL.Class) in g
    assert (ex("Person"), RDF.type, OWL.NamedIndividual) in g
    assert (d("ann"), ex("age"), Literal("40", datatype=XSD.integer)) in g
    assert (d("ann"), ex("note"), Literal("hi", lang="en")) in g
    assert (d("ann"), ex("note"), Literal("is a test")) in g
    assert (d("zed"), ex("note"), Literal("untouched")) in g


class TestTheGuidesRules:
    """`MERGE_SPLIT_GUIDE.md`'s and the example config's rules, run as they are written."""

    @staticmethod
    def _guide_config() -> dict[str, Any]:
        guide = (REPO / "docs/user_guides/MERGE_SPLIT_GUIDE.md").read_text()
        section = guide.split("#### Complex Migration (Transformation Rules)", 1)[1]
        block = re.search(r"```yaml\n(.*?)```", section, re.DOTALL)
        assert block, "the guide's Complex Migration section has no YAML block"
        config: dict[str, Any] = yaml.safe_load(block.group(1))
        return config

    @staticmethod
    def _example_rules() -> list[dict[str, Any]]:
        lines = (REPO / "examples/merge/merge_config.yml").read_text().splitlines()
        start = lines.index("# migrate_data:")
        block = []
        for line in lines[start:]:
            if not line.startswith("#"):
                break
            line = re.sub(r"^# ?", "", line)
            # Uncomment the commented-out rules: a "# - type:" line and what continues it
            line = re.sub(r"^(\s*)# (- type:|  )", r"\1\2", line)
            block.append(line)
        config: dict[str, Any] = yaml.safe_load("\n".join(block))
        migrate = config["migrate_data"]
        assert (REPO / migrate["sources"][0]).exists(), "the example's data path is wrong"
        rules: list[dict[str, Any]] = migrate["rules"]
        return rules

    def _check(self, result: Result, g: Graph) -> None:
        assert result.exit_code == 0, result.output
        # Rename: the legacy class moved, nothing else did
        assert (d("leg"), RDF.type, ex("ModernClass")) in g
        assert not any(URIRef(OLD + "LegacyClass") in t for t in g)
        # Split: only the fullName triples, keeping the language tag (N2)
        assert not list(g.triples((None, ex("fullName"), None)))
        assert (d("ann"), ex("givenName"), Literal("Ann", lang="en")) in g
        assert (d("ann"), ex("familyName"), Literal("Lee", lang="en")) in g
        assert (d("bob"), ex("givenName"), Literal("Bob")) in g
        assert (d("bob"), ex("familyName"), Literal("Ray")) in g
        # Company → Organisation: d:bob and the blank node, nothing else
        assert not list(g.triples((None, RDF.type, ex("Company"))))
        orgs = set(g.subjects(RDF.type, ex("Organisation")))
        assert d("bob") in orgs and len(orgs) == 2
        (blank,) = orgs - {d("bob")}
        assert isinstance(blank, BNode)
        assert (blank, ex("label"), Literal("Anon Co")) in g
        assert (d("ann"), RDF.type, ex("Person")) in g
        _untouched(g)

    def test_the_guides_config_runs_as_written(self, tmp_path):
        config = self._guide_config()
        rules = config["migrate_data"]["rules"]
        assert "migration_rules" not in config and "rules_file" not in config["migrate_data"]
        self._check(*_migrate(tmp_path, rules))

    def test_the_example_configs_rules_run_as_written(self, tmp_path):
        rules = self._example_rules()
        assert [r["type"] for r in rules] == ["rename", "transform", "transform"]
        self._check(*_migrate(tmp_path, rules))

    def test_the_summary_counts_matches(self, tmp_path):
        result, _ = _migrate(tmp_path, self._guide_config()["migrate_data"]["rules"])
        assert "Rename legacy class: 1 instances" in result.output
        assert "Split fullName into givenName and familyName: 2 instances" in result.output
        assert "Migrate Company to Organisation: 2 instances" in result.output


class TestMatching:
    def test_a_literal_in_each_form_matches_only_itself(self, tmp_path):
        rules = [
            {"type": "transform", "description": "age", "match": "?s ex:age 40"},
            {"type": "transform", "description": "hi", "match": '?s ex:note "hi"@en'},
            {"type": "transform", "description": "test", "match": '?s ex:note "is a test"'},
        ]
        result, g = _migrate(tmp_path, rules)
        assert result.exit_code == 0, result.output
        assert not list(g.triples((d("ann"), ex("age"), None)))
        assert set(g.objects(d("ann"), ex("note"))) == set()
        assert (d("zed"), ex("note"), Literal("untouched")) in g
        assert (d("ann"), RDF.type, ex("Person")) in g

    def test_a_typed_literal_matches(self, tmp_path):
        rules = [{"type": "transform", "description": "t", "match": '?s ex:age "40"^^xsd:integer'}]
        result, g = _migrate(tmp_path, rules)
        assert result.exit_code == 0, result.output
        assert not list(g.triples((d("ann"), ex("age"), None)))
        assert (d("ann"), ex("fullName"), Literal("Ann Lee", lang="en")) in g

    def test_a_type_match_leaves_a_punned_terms_own_types(self, tmp_path):
        rules = [{"type": "transform", "description": "p", "match": "?s a ex:Person"}]
        result, g = _migrate(tmp_path, rules)
        assert result.exit_code == 0, result.output
        assert (d("ann"), RDF.type, ex("Person")) not in g
        _untouched(g)

    def test_a_deliberate_match_everything_is_allowed(self, tmp_path):
        rules = [{"type": "transform", "description": "all", "match": "?s ?p ?o"}]
        config, merged, _ = _setup(tmp_path, rules)
        result = _run("merge", "-c", config, "-o", merged)
        assert result.exit_code == 0, result.output
        assert "Result triples: 0" in result.output
        assert "all: 13 instances" in result.output

    def test_a_repeated_variable_binds_one_value(self, tmp_path):
        data = DATA + f"d:ann <{EX}knows> d:ann, d:bob .\n"
        rules = [{"type": "transform", "description": "self", "match": "?s ex:knows ?s"}]
        result, g = _migrate(tmp_path, rules, data=data)
        assert result.exit_code == 0, result.output
        assert (d("ann"), ex("knows"), d("ann")) not in g
        assert (d("ann"), ex("knows"), d("bob")) in g

    def test_rules_run_in_order_on_one_graph(self, tmp_path):
        tag = {
            "type": "transform",
            "description": "tag",
            "match": "?s a ex:Organisation",
            "construct": [{"pattern": "?s ex:migrated true"}],
            "delete_matched": False,
        }
        result, g = _migrate(tmp_path, [COMPANY, tag])
        assert result.exit_code == 0, result.output
        flagged = set(g.subjects(ex("migrated"), Literal("true", datatype=XSD.boolean)))
        assert flagged == set(g.subjects(RDF.type, ex("Organisation")))
        assert len(flagged) == 2

    def test_a_blank_node_in_a_construct_is_fresh_for_each_match(self, tmp_path):
        rules = [
            {
                "type": "transform",
                "description": "addr",
                "match": "?s ex:fullName ?n",
                "construct": [
                    {"pattern": "?s ex:address _:a"},
                    {"pattern": "_:a ex:line ?n"},
                ],
                "delete_matched": False,
            }
        ]
        result, g = _migrate(tmp_path, rules)
        assert result.exit_code == 0, result.output
        ann, bob = g.value(d("ann"), ex("address")), g.value(d("bob"), ex("address"))
        assert isinstance(ann, BNode) and isinstance(bob, BNode) and ann != bob
        assert (ann, ex("line"), Literal("Ann Lee", lang="en")) in g
        assert (bob, ex("line"), Literal("Bob Ray")) in g

    def test_a_curie_rename_rule_renames(self, tmp_path):
        rules = [{"type": "rename", "description": "rn", "from": "ex:Person", "to": "ex:Human"}]
        result, g = _migrate(tmp_path, rules)
        assert result.exit_code == 0, result.output
        assert (d("ann"), RDF.type, ex("Human")) in g
        assert (ex("Human"), RDF.type, OWL.Class) in g
        assert not any(ex("Person") in t for t in g)
        # A subject twice and an object once
        assert "rn: 3 instances" in result.output


class TestBinds:
    def test_a_match_whose_construct_builds_nothing_is_left_unchanged(self, tmp_path):
        data = DATA + 'd:cher <http://example.org/ont#fullName> "Cher" .\n'
        result, g = _migrate(tmp_path, [SPLIT], data=data)
        assert result.exit_code == 1, result.output
        assert (
            "Left 1 match(es) unchanged, as a construct built no value: migration rule 1 ('split')"
            in result.stderr
        )
        assert (d("cher"), ex("fullName"), Literal("Cher")) in g
        assert not list(g.triples((d("cher"), ex("givenName"), None)))
        assert (d("ann"), ex("givenName"), Literal("Ann", lang="en")) in g

    def test_arithmetic_is_decimal_in_plain_notation(self, tmp_path):
        data = DATA + "d:x <http://example.org/ont#f> 212, 1e20, 98.6 .\n"
        rules = [
            {
                "type": "transform",
                "description": "c",
                "match": "?s ex:f ?f",
                "construct": [{"pattern": "?s ex:c ?c", "bind": "((?f - 32) * 5/9) AS ?c"}],
            }
        ]
        config, merged, dout = _setup(tmp_path, rules, data=data)
        result = _run("merge", "-c", config, "-o", merged)
        assert result.exit_code == 0, result.output
        assert "e+" not in dout.read_text().lower()
        values = {str(o) for o in Graph().parse(dout).objects(d("x"), ex("c"))}
        # A quotient that does not terminate keeps its integer part and 28 more digits
        assert values == {"100", "37.0", "55555555555555555537.7777777777777777777777777778"}
        assert all(o.datatype == XSD.decimal for o in Graph().parse(dout).objects(d("x"), ex("c")))

    def test_arithmetic_rounds_no_operand(self, tmp_path):
        big = "12345678901234567890123456789012"
        data = DATA + f"d:x <http://example.org/ont#n> {big} .\n"
        rules = [
            {
                "type": "transform",
                "description": "n",
                "match": "?s ex:n ?n",
                "construct": [{"pattern": "?s ex:m ?m", "bind": "((?n - 2) * 1/1) AS ?m"}],
            }
        ]
        result, g = _migrate(tmp_path, rules, data=data)
        assert result.exit_code == 0, result.output
        assert [str(o) for o in g.objects(d("x"), ex("m"))] == [big[:-1] + "0"]

    def test_arithmetic_on_a_value_that_is_not_numeric_leaves_its_match_unchanged(self, tmp_path):
        data = DATA + (
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
            'd:p <http://example.org/ont#n> "40" .\n'
            'd:q <http://example.org/ont#n> "40"@en .\n'
            'd:r <http://example.org/ont#n> "4e1"^^xsd:string .\n'
            'd:s <http://example.org/ont#n> "4e1"^^xsd:double .\n'
            'd:t <http://example.org/ont#n> "NaN"^^xsd:double .\n'
        )
        rules = [
            {
                "type": "transform",
                "description": "double",
                "match": "?s ex:n ?n",
                "construct": [{"pattern": "?s ex:m ?m", "bind": "((?n - 0) * 2/1) AS ?m"}],
            }
        ]
        result, g = _migrate(tmp_path, rules, data=data)
        assert result.exit_code == 1, result.output
        assert "Left 4 match(es) unchanged" in result.stderr
        assert [str(o) for o in g.objects(d("s"), ex("m"))] == ["80"]
        for local in "pqrt":
            assert not list(g.objects(d(local), ex("m")))
            assert len(list(g.objects(d(local), ex("n")))) == 1


class TestNothingMatched:
    @pytest.mark.parametrize("dry_run", [False, True])
    def test_a_rule_that_matches_nothing_exits_1(self, tmp_path, dry_run):
        rules = [
            SPLIT,
            {"type": "transform", "description": "typo", "match": "?s ex:fulName ?n"},
            {"type": "rename", "description": "gone", "from": "ex:Nobody", "to": "ex:Somebody"},
        ]
        config, merged, dout = _setup(tmp_path, rules)
        result = _run("merge", "-c", config, "-o", merged, *(["--dry-run"] if dry_run else []))
        assert result.exit_code == 1, result.output
        assert "Matched nothing in any data file: migration rule 2 ('typo')" in result.stderr
        assert "Matched nothing in any data file: migration rule 3 ('gone')" in result.stderr
        assert "split" not in result.stderr
        assert dout.exists() is not dry_run

    def test_rules_without_a_description_are_told_apart(self, tmp_path):
        rules = [
            {"type": "transform", "match": "?s ex:fulName ?n"},
            {"type": "transform", "match": "?s ex:nam ?n"},
            {"type": "transform", "match": "?s ex:fullName ?n",
             "construct": [{"pattern": "?s ex:g ?g", "bind": "STRBEFORE(?n, '#') AS ?g"}]},
            {"type": "transform", "match": "?s ex:label ?n",
             "construct": [{"pattern": "?s ex:g ?g", "bind": "STRBEFORE(?n, '#') AS ?g"}]},
        ]  # fmt: skip
        result, _ = _migrate(tmp_path, rules)
        assert result.exit_code == 1, result.output
        assert "Matched nothing in any data file: migration rule 1 ('transform')" in result.stderr
        assert "Matched nothing in any data file: migration rule 2 ('transform')" in result.stderr
        assert "Left 2 match(es) unchanged, as a construct built no value: migration rule 3" in (
            result.stderr
        )
        assert "Left 1 match(es) unchanged, as a construct built no value: migration rule 4" in (
            result.stderr
        )

    def test_a_rule_that_matches_in_one_data_file_of_two_is_not_listed(self, tmp_path):
        other = f'@prefix ex: <{EX}> .\n<{D}cy> ex:note "x" .\n'
        result, g = _migrate(tmp_path, [SPLIT], more_data={"data2.ttl": other})
        assert result.exit_code == 0, result.output
        assert "matched nothing" not in result.stderr


REFUSALS = [
    ({"type": "transform", "match": "?s foaf:name ?n"}, "prefix 'foaf' is not bound"),
    ({"type": "transform", "match": '?s ex:v "1"^^foo:t'}, "prefix 'foo' is not bound"),
    ({"type": "transform", "match": "?s ex:fullName"}, "is not three terms"),
    ({"type": "transfrom", "match": "?s ?p ?o"}, "type 'transfrom' is not"),
    ({"type": "rename", "from": "ex:Person"}, "has no to:"),
    ({"type": "transform"}, "a transform rule needs match:"),
    (
        {"type": "transform", "match": "?s ex:fullName ?n",
         "construct": [{"pattern": "?s ex:up ?y", "bind": "UCASE(?n) AS ?y"}]},
        "is not a form rules support",
    ),
    (
        {"type": "transform", "match": "?s ex:fullName ?n",
         "construct": [{"pattern": "?s ex:copy ?m"}]},
        "uses ?m, which the match does not bind",
    ),
    (
        {"type": "transform", "match": "?s ex:fullName ?n",
         "construct": [{"pattern": "?s ex:g ?x", "bind": "STRBEFORE(?n, ' ') AS ?y"}]},
        "is not the object of",
    ),
    ({"type": "transform", "match": "_:b ex:fullName ?n"}, "has a blank node"),
    (
        {"type": "transform", "match": "?s ex:age ?a",
         "construct": [{"pattern": "?s ex:x ?r", "bind": "((?a - 1) * 2/0) AS ?r"}]},
        "divides by 0",
    ),
    ({"type": "transform", "match": "?s ex:fullName"}, "migration rule 2 ('bad')"),
]  # fmt: skip


class TestRefusals:
    @pytest.mark.parametrize("dry_run", [False, True])
    @pytest.mark.parametrize(("bad", "message"), REFUSALS)
    def test_a_rule_that_cannot_be_read_is_refused(self, tmp_path, bad, message, dry_run):
        config, merged, _ = _setup(tmp_path, [SPLIT, {"description": "bad", **bad}])
        argv = ["merge", "-c", str(config), "-o", str(merged), *(["--dry-run"] if dry_run else [])]
        before = snapshot(argv, tmp_path)
        result = _run(*argv)
        assert result.exit_code == 2, result.output
        assert message in result.output
        assert_wrote_nothing(before, snapshot(argv, tmp_path))

    def test_a_prefix_two_data_files_bind_differently_is_refused(self, tmp_path):
        other = f'@prefix ex: <{OTHER}> .\n<{D}cy> ex:fullName "Cy Twombly" .\n'
        config, merged, _ = _setup(tmp_path, [SPLIT], more_data={"data2.ttl": other})
        argv = ["merge", "-c", str(config), "-o", str(merged)]
        before = snapshot(argv, tmp_path)
        result = _run(*argv)
        assert result.exit_code == 2, result.output
        assert "'ex:fullName' means different IRIs in different sources" in result.output
        assert "data2.ttl" in result.output
        assert_wrote_nothing(before, snapshot(argv, tmp_path))

    def test_preferred_prefixes_disagreeing_with_a_data_file_is_refused(self, tmp_path):
        config, merged, _ = _setup(
            tmp_path, [SPLIT], namespaces={"preferred_prefixes": {"ex": OTHER}}
        )
        argv = ["merge", "-c", str(config), "-o", str(merged)]
        before = snapshot(argv, tmp_path)
        result = _run(*argv)
        assert result.exit_code == 2, result.output
        assert "means different IRIs" in result.output and "merge.yml" in result.output
        assert_wrote_nothing(before, snapshot(argv, tmp_path))

    def test_a_prefix_only_preferred_prefixes_binds_resolves(self, tmp_path):
        rules = [
            {
                "type": "transform",
                "description": "foaf",
                "match": "?s ex:fullName ?n",
                "construct": [{"pattern": "?s foaf:name ?n"}],
            }
        ]
        result, g = _migrate(tmp_path, rules, namespaces={"preferred_prefixes": {"foaf": FOAF}})
        assert result.exit_code == 0, result.output
        assert (d("bob"), URIRef(FOAF + "name"), Literal("Bob Ray")) in g


class TestPrefixes:
    """A rule may use any prefix a data file declares, and the core five (#492)."""

    def test_xsd_resolves_when_the_data_declares_xs_for_its_namespace(self, tmp_path):
        data = DATA.replace(
            "@prefix ex:", "@prefix xs: <http://www.w3.org/2001/XMLSchema#> .\n@prefix ex:"
        )
        rules = [
            {"type": "transform", "description": "typed", "match": '?s ex:age "40"^^xsd:integer',
             "construct": [{"pattern": "?s ex:forty true"}], "delete_matched": False},
        ]  # fmt: skip
        result, g = _migrate(tmp_path, rules, data=data)
        assert result.exit_code == 0, result.output
        assert (d("ann"), ex("forty"), Literal(True)) in g

    def test_both_prefixes_a_file_declares_for_one_namespace_resolve(self, tmp_path):
        # rdflib keeps the last prefix declared for a namespace, so the graph has ont: and no ex:
        data = DATA + f"@prefix ont: <{EX}> .\n"
        result, g = _migrate(tmp_path, [SPLIT], data=data)
        assert result.exit_code == 0, result.output
        assert (d("bob"), ex("givenName"), Literal("Bob")) in g

    def test_a_data_file_binding_a_core_prefix_differently_is_refused(self, tmp_path):
        data = DATA.replace("@prefix ex:", f"@prefix xsd: <{OTHER}> .\n@prefix ex:")
        rules = [{"type": "transform", "match": '?s ex:age "40"^^xsd:integer'}]
        config, merged, _ = _setup(tmp_path, rules, data=data)
        argv = ["merge", "-c", str(config), "-o", str(merged)]
        before = snapshot(argv, tmp_path)
        result = _run(*argv)
        assert result.exit_code == 2, result.output
        assert "means different IRIs" in result.output and "the core prefixes" in result.output
        assert_wrote_nothing(before, snapshot(argv, tmp_path))

    def test_migrate_data_files_reads_each_files_declarations(self, tmp_path):
        path = tmp_path / "data.ttl"
        path.write_text(DATA + f"@prefix ont: <{EX}> .\n")
        result = migrate_data_files([path], rules=[MigrationRule.from_dict(SPLIT)])
        assert result.success and result.migrated_graph is not None
        assert (d("bob"), ex("givenName"), Literal("Bob")) in result.migrated_graph


class TestLibrary:
    def _graph(self) -> Graph:
        return Graph(bind_namespaces="core").parse(data=DATA, format="turtle")

    def test_migrate_raises_before_touching_the_data(self):
        data = self._graph()
        before = set(data)
        with pytest.raises(RuleError, match="prefix 'foaf' is not bound"):
            DataMigrator().migrate(
                data, rules=[MigrationRule(type="transform", match="?s foaf:name ?n")]
            )
        assert set(data) == before

    def test_migrate_data_graphs_raises_before_any_graph_is_migrated(self, tmp_path):
        first, second = self._graph(), self._graph()
        rules = [MigrationRule.from_dict(SPLIT), MigrationRule(type="transfrom")]
        with pytest.raises(RuleError) as caught:
            migrate_data_graphs(
                [(tmp_path / "a.ttl", first), (tmp_path / "b.ttl", second)],
                rules=rules,
                output_path=tmp_path / "out.ttl",
            )
        assert caught.value.index == 1
        assert not (tmp_path / "out.ttl").exists()
        assert len(first) == len(second) == len(self._graph())

    def test_migrate_data_graphs_takes_more_prefixes(self, tmp_path):
        rules = [
            MigrationRule(
                type="transform",
                match="?s ex:fullName ?n",
                construct=[{"pattern": "?s foaf:name ?n"}],
                delete_matched=False,
            )
        ]
        result = migrate_data_graphs(
            [(tmp_path / "a.ttl", self._graph())],
            rules=rules,
            prefixes=[(tmp_path / "merge.yml", {"foaf": FOAF})],
        )
        assert result.migrated_graph is not None
        assert (d("bob"), URIRef(FOAF + "name"), Literal("Bob Ray")) in result.migrated_graph
        assert result.unmatched_rules == []
