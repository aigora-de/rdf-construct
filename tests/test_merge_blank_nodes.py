"""``merge`` writes a blank-node structure its sources share once, and keeps every other (#170).

The rule and why it is the safe one are in ``rdf_construct.core.blank_nodes``. The fixtures in
``tests/fixtures/merge/blank_nodes/`` carry one structure per case, and ``merged.expected.ttl`` is
written by hand, so an output that fuses two structures or keeps a duplicate is visible as a
difference from it.
"""

from __future__ import annotations

import os
import random
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import BNode, Graph, Namespace
from rdflib.compare import isomorphic
from rdflib.namespace import OWL, RDF

from rdf_construct.cli import cli
from rdf_construct.core.blank_nodes import (
    blank_node_components,
    component_digest,
    label_by_content,
)
from rdf_construct.core.verify import check_isomorphic, describe
from rdf_construct.merge import MergeConfig, OntologyMerger, SourceConfig
from tests.test_cli_smoke import assert_no_crash

FIXTURES = Path(__file__).parent / "fixtures" / "merge" / "blank_nodes"
CORE = FIXTURES / "core.ttl"
MODULE = FIXTURES / "module.ttl"
EXPECTED = FIXTURES / "merged.expected.ttl"
REPRODUCER = FIXTURES / "reproducer.ttl"

EX = Namespace("http://example.org/")

PREFIXES = """\
@prefix ex: <http://example.org/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
"""
RESTRICTION = "[ a owl:Restriction ; owl:onProperty ex:pA ; owl:someValuesFrom ex:B ]"


def _graph(body: str) -> Graph:
    return Graph().parse(data=PREFIXES + body, format="turtle")


def _merge(tmp_path: Path, *argv: object) -> tuple[Result, Graph]:
    out = tmp_path / "merged.ttl"
    result = CliRunner().invoke(cli, ["merge", *[str(a) for a in argv], "-o", str(out)])
    assert_no_crash(result)
    return result, Graph().parse(out)


def _union(*graphs: Graph) -> Graph:
    union = Graph()
    for graph in graphs:
        union += label_by_content(graph)
    return union


def _bnodes(graph: Graph) -> set[BNode]:
    return {term for triple in graph for term in triple if isinstance(term, BNode)}


class TestMergeCommand:
    def test_the_merge_is_the_hand_written_expectation(self, tmp_path):
        result, merged = _merge(tmp_path, CORE, MODULE)
        assert result.exit_code == 0, result.output
        assert not check_isomorphic(Graph().parse(EXPECTED), merged), describe(
            check_isomorphic(Graph().parse(EXPECTED), merged)
        )

    @pytest.mark.parametrize("source", [REPRODUCER, CORE, MODULE], ids=lambda p: p.name)
    def test_merging_a_file_with_itself_is_the_identity(self, source: Path, tmp_path):
        """core.ttl states one restriction twice, and both copies survive."""
        _, merged = _merge(tmp_path, source, source)
        assert isomorphic(merged, Graph().parse(source))

    @pytest.mark.parametrize("source", [REPRODUCER, CORE], ids=lambda p: p.name)
    def test_merging_one_file_is_the_identity(self, source: Path, tmp_path):
        _, merged = _merge(tmp_path, source)
        assert isomorphic(merged, Graph().parse(source))

    def test_the_reproducer_reports_what_it_wrote_and_no_conflict(self, tmp_path):
        result, merged = _merge(tmp_path, REPRODUCER, REPRODUCER)
        assert result.exit_code == 0, result.output
        assert len(merged) == 7
        assert "Total merged: 7 triples" in result.output
        assert "No conflicts detected" in result.output

    def test_mark_all_finds_nothing_to_mark_in_a_self_merge(self, tmp_path):
        """Before #170 the duplicate restriction was an unresolved conflict, at exit 1."""
        result, _ = _merge(tmp_path, REPRODUCER, REPRODUCER, "--strategy", "mark_all")
        assert result.exit_code == 0, result.output
        assert "CONFLICT" not in (tmp_path / "merged.ttl").read_text()


class TestNamespaceRemapping:
    def test_a_remapped_source_shares_its_structure_with_the_other(self, tmp_path):
        """Blank nodes are labelled after the remap, so a moved restriction meets its twin."""
        old = tmp_path / "old.ttl"
        old.write_text(
            REPRODUCER.read_text().replace("http://example.org/", "http://example.org/old/")
        )
        config = MergeConfig(
            sources=[
                SourceConfig(path=REPRODUCER, priority=1),
                SourceConfig(
                    path=old,
                    priority=2,
                    namespace_remap={"http://example.org/old/": "http://example.org/"},
                ),
            ]
        )
        result = OntologyMerger(config).merge()
        assert result.merged_graph is not None
        assert isomorphic(result.merged_graph, Graph().parse(REPRODUCER))
        assert result.conflicts == []


class TestTheRule:
    """Each case of stop 1 on #312's P15, on the union of two relabelled graphs."""

    @pytest.mark.parametrize(
        ("first", "second", "triples", "bnodes"),
        [
            pytest.param(
                f"ex:A rdfs:subClassOf {RESTRICTION} .",
                f"ex:A rdfs:subClassOf {RESTRICTION} .",
                4,
                1,
                id="same-subject-and-predicate",
            ),
            pytest.param(
                f"ex:A rdfs:subClassOf {RESTRICTION} .",
                f"ex:C rdfs:subClassOf {RESTRICTION} .",
                8,
                2,
                id="different-subjects",
            ),
            pytest.param(
                f"ex:A rdfs:subClassOf {RESTRICTION} .",
                f"ex:A owl:equivalentClass {RESTRICTION} .",
                8,
                2,
                id="different-predicates",
            ),
            pytest.param(
                f"ex:A rdfs:subClassOf {RESTRICTION}, {RESTRICTION} .",
                f"ex:A rdfs:subClassOf {RESTRICTION} .",
                8,
                2,
                id="two-copies-and-one",
            ),
            pytest.param(
                'ex:a foaf:knows [ foaf:name "Bob" ] .',
                'ex:c foaf:knows [ foaf:name "Bob" ] .',
                4,
                2,
                id="bob-from-two-subjects",
            ),
            pytest.param(
                'ex:a foaf:knows _:x . ex:c foaf:knows _:x . _:x foaf:name "Bob" .',
                'ex:a foaf:knows [ foaf:name "Bob" ] . ex:c foaf:knows [ foaf:name "Bob" ] .',
                7,
                3,
                id="one-shared-node-and-two",
            ),
            pytest.param(
                "[] a owl:AllDisjointClasses ; owl:members ( ex:B ex:C ) .",
                "[] a owl:AllDisjointClasses ; owl:members ( ex:B ex:C ) .",
                6,
                3,
                id="root-blank-node",
            ),
            pytest.param(
                f"ex:A rdfs:subClassOf {RESTRICTION} .",
                f"ex:A rdfs:subClassOf {RESTRICTION} . "
                "ex:Z rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:pZ ; "
                "owl:allValuesFrom ex:B ] .",
                8,
                2,
                id="an-unrelated-structure-beside-it",
            ),
        ],
    )
    def test_union(self, first: str, second: str, triples: int, bnodes: int):
        union = _union(_graph(first), _graph(second))
        assert (len(union), len(_bnodes(union))) == (triples, bnodes)

    def test_a_single_blank_node_is_never_fused_with_another_files(self):
        """``rdflib.compare`` calls every lone blank node ``_:cb0``; that must not leak out."""
        first = _graph(f"ex:A rdfs:subClassOf {RESTRICTION} .")
        second = _graph(
            "ex:Z rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:pZ ; "
            "owl:allValuesFrom ex:B ] ."
        )
        union = _union(first, second)
        assert len(set(union.objects(None, OWL.onProperty))) == 2
        assert len(set(union.subjects(OWL.onProperty, None))) == 2


class TestHelpers:
    def test_components_are_joined_through_blank_nodes_only(self):
        graph = _graph(
            f"ex:A rdfs:subClassOf {RESTRICTION}, {RESTRICTION} . "
            "ex:U owl:unionOf ( ex:B ex:C ) ."
        )
        sizes = sorted(len(component) for component in blank_node_components(graph))
        assert sizes == [4, 4, 5]

    def test_a_ground_triple_is_in_no_component(self):
        graph = _graph(f"ex:A a owl:Class ; rdfs:subClassOf {RESTRICTION} .")
        [component] = blank_node_components(graph)
        assert (EX.A, RDF.type, OWL.Class) not in component
        assert len(component) == 4

    def test_identical_subtrees_under_one_node_are_both_kept(self):
        """Two copies of one subtree inside a single tree need two sets of labels."""
        body = (
            "ex:A rdfs:subClassOf [ owl:intersectionOf ex:L ; "
            "ex:part [ ex:q ex:B ; ex:r [ ex:s ex:C ] ], [ ex:q ex:B ; ex:r [ ex:s ex:C ] ] ] ."
        )
        source = _graph(body)
        assert isomorphic(label_by_content(source), source)
        assert isomorphic(_union(source, _graph(body)), source)

    def test_the_digest_sees_the_referring_subject(self):
        [first] = blank_node_components(_graph(f"ex:A rdfs:subClassOf {RESTRICTION} ."))
        [second] = blank_node_components(_graph(f"ex:C rdfs:subClassOf {RESTRICTION} ."))
        assert component_digest(first) != component_digest(second)

    def test_relabelling_keeps_the_graph_and_its_prefixes(self):
        graph = Graph().parse(CORE)
        relabelled = label_by_content(graph)
        assert isomorphic(relabelled, graph)
        assert dict(relabelled.namespaces()) == dict(graph.namespaces())

    def test_labels_are_the_same_under_every_hash_seed(self):
        """A second process with another seed, since one process iterates sets stably."""
        script = (
            "import sys; from rdflib import Graph, BNode; "
            "from rdf_construct.core.blank_nodes import label_by_content; "
            "g = label_by_content(Graph().parse(sys.argv[1])); "
            "print(sorted({str(t) for x in g for t in x if isinstance(t, BNode)}))"
        )
        outputs = {
            subprocess.run(
                [sys.executable, "-c", script, str(CORE)],
                env={**os.environ, "PYTHONHASHSEED": seed},
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            for seed in ("0", "1", "42")
        }
        assert len(outputs) == 1


class TestNotATree:
    """Components that are not trees fall back to ``rdflib.compare``, and keep the same rule."""

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param("_:a ex:p _:x . _:b ex:q _:x . _:x ex:r ex:B .", id="two-blank-parents"),
            pytest.param("ex:A ex:p _:a . _:a ex:p _:b . _:b ex:p _:a .", id="cycle"),
            pytest.param(
                "_:b owl:sameAs _:b ; a owl:AllDisjointClasses ; owl:members ( ex:B ex:C ) .",
                id="self-reference",
            ),
        ],
    )
    def test_merged_with_itself_it_is_written_once(self, body: str):
        source = _graph(body)
        union = _union(source, _graph(body))
        assert isomorphic(union, source)

    def test_a_cycle_under_another_subject_is_kept_apart(self):
        union = _union(
            _graph("ex:A ex:p _:a . _:a ex:p _:b . _:b ex:p _:a ."),
            _graph("ex:C ex:p _:a . _:a ex:p _:b . _:b ex:p _:a ."),
        )
        assert len(_bnodes(union)) == 4

    def test_a_tree_never_reaches_rdflib_compare(self, monkeypatch):
        """Canonicalising a long list with ``rdflib.compare`` took 11 s at 1,000 cells."""

        def refuse(_graph: Graph) -> Graph:
            raise AssertionError("a tree component was canonicalised with rdflib.compare")

        monkeypatch.setattr("rdf_construct.core.blank_nodes.to_canonical_graph", refuse)
        label_by_content(Graph().parse(CORE))
        label_by_content(_long_list(50))


def _long_list(cells: int) -> Graph:
    graph = Graph()
    head: BNode = BNode()
    graph.add((EX.U, OWL.unionOf, head))
    for i in range(cells):
        rest = BNode() if i < cells - 1 else RDF.nil
        graph.add((head, RDF.first, EX[f"C{i}"]))
        graph.add((head, RDF.rest, rest))
        head = rest  # type: ignore[assignment]
    return graph


class TestCost:
    def test_a_five_thousand_member_list_merges(self, tmp_path):
        """#170's panel: through ``rdflib.compare`` this did not finish in ten minutes."""
        source = tmp_path / "list.ttl"
        _long_list(5000).serialize(source, format="nt", encoding="utf-8")
        result, merged = _merge(tmp_path, source, source)
        assert result.exit_code == 0, result.output
        assert len(merged) == 10001


def _random_tree(rng: random.Random) -> Graph:
    graph = Graph()
    nodes: list[BNode] = [BNode()]
    graph.add((rng.choice([EX.A, EX.C]), rng.choice([EX.p, EX.q]), nodes[0]))
    for _ in range(rng.randint(0, 3)):
        child = BNode()
        graph.add((rng.choice(nodes), rng.choice([EX.p, EX.q]), child))
        nodes.append(child)
    for node in nodes:
        for _ in range(rng.randint(0, 2)):
            graph.add((node, rng.choice([EX.p, EX.q]), rng.choice([EX.A, EX.B])))
    return graph


class TestTheTreeHashAgreesWithRdflib:
    def test_equal_digests_exactly_when_isomorphic(self):
        """Every pair from a pool of small random trees, judged by ``rdflib.compare``."""
        rng = random.Random(170)
        pool = [_random_tree(rng) for _ in range(80)]
        digests = [component_digest(tree) for tree in pool]
        for i, first in enumerate(pool):
            for j in range(i + 1, len(pool)):
                assert (digests[i] == digests[j]) == isomorphic(first, pool[j]), (i, j)
        assert len(set(digests)) < len(pool), "the pool should hold some isomorphic pairs"
