"""Tests for the post-write verification harness itself (#266).

The contracts are applied to real commands in ``test_post_write.py``. This module checks that each
checker passes what it should, fails what it should, and reports rather than raises.
"""

import pytest
from rdflib import BNode, Graph, Literal, Namespace
from rdflib.namespace import OWL, RDF, RDFS

from rdf_construct.core.verify import (
    CONTRACTS,
    SAMPLE_SIZE,
    Contract,
    check_contract,
    check_counts_agree,
    check_isomorphic,
    check_superset,
    check_triple_count,
    check_union_isomorphic,
    describe,
)
from tests.test_cli_smoke import EXPECTED_COMMANDS

EX = Namespace("http://example.org/ont#")

# One class with an anonymous restriction, so that blank nodes are in play.
SOURCE_TTL = """\
@prefix ex: <http://example.org/ont#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Building a owl:Class ;
    rdfs:label "Building"@en ;
    rdfs:subClassOf [ a owl:Restriction ;
        owl:onProperty ex:hasFloor ;
        owl:someValuesFrom ex:Floor ] .

ex:Floor a owl:Class .
ex:hasFloor a owl:ObjectProperty .
"""


def _source() -> Graph:
    return Graph().parse(data=SOURCE_TTL, format="turtle")


class TestIsomorphic:
    def test_two_parses_are_the_same_graph(self):
        """Blank-node labels differ across parses, and must not matter."""
        first, second = _source(), _source()
        assert {t for t in first if isinstance(t[0], BNode)} != {
            t for t in second if isinstance(t[0], BNode)
        }
        assert check_isomorphic(first, second) == []

    def test_a_lost_triple_is_reported_as_missing(self):
        actual = _source()
        actual.remove((EX.Building, RDFS.label, None))
        [found] = check_isomorphic(_source(), actual)
        assert found.contract is Contract.ISOMORPHIC
        assert found.missing == ((EX.Building, RDFS.label, Literal("Building", lang="en")),)
        assert (found.missing_count, found.extra_count) == (1, 0)

    def test_a_lost_blank_node_triple_is_reported(self):
        actual = _source()
        actual.remove((None, OWL.someValuesFrom, None))
        [found] = check_isomorphic(_source(), actual)
        assert found.missing_count > 0

    def test_an_invented_triple_is_reported_as_extra(self):
        actual = _source()
        actual.add((EX.Floor, RDFS.label, Literal("Floor")))
        [found] = check_isomorphic(_source(), actual)
        assert (found.missing_count, found.extra_count) == (0, 1)

    def test_samples_are_capped_and_counts_are_not(self):
        actual = Graph()
        expected = Graph()
        for i in range(SAMPLE_SIZE + 5):
            expected.add((EX[f"C{i}"], RDF.type, OWL.Class))
        [found] = check_isomorphic(expected, actual)
        assert len(found.missing) == SAMPLE_SIZE
        assert found.missing_count == SAMPLE_SIZE + 5


class TestTripleCount:
    def test_equal_counts_hold(self):
        assert check_triple_count(_source(), _source()) == []

    def test_a_merged_entity_is_reported(self):
        actual = _source()
        actual.remove((EX.Floor, RDF.type, OWL.Class))
        [found] = check_triple_count(_source(), actual)
        assert found.contract is Contract.TRIPLE_COUNT


class TestUnionIsomorphic:
    def test_a_clean_partition_holds(self):
        source = _source()
        first, second = Graph(), Graph()
        for t in source:
            (first if t[0] == EX.hasFloor else second).add(t)
        assert check_union_isomorphic(source, [first, second]) == []

    def test_a_duplicated_blank_node_closure_is_extra(self):
        """A closure copied into two parts is two closures once the parts are re-parsed."""
        parts = [_source(), _source()]
        [found] = check_union_isomorphic(_source(), parts)
        assert found.contract is Contract.UNION_ISOMORPHIC
        assert found.extra_count > 0

    def test_a_dropped_triple_is_missing(self):
        part = _source()
        part.remove((EX.hasFloor, None, None))
        [found] = check_union_isomorphic(_source(), [part])
        assert found.missing_count == 1


class TestSuperset:
    def test_the_union_of_two_sources_holds(self):
        other = Graph()
        other.add((EX.Room, RDF.type, OWL.Class))
        output = _source() + other
        assert check_superset([_source(), other], output) == []

    def test_extra_triples_in_the_output_are_allowed(self):
        output = _source()
        output.add((EX.Building, OWL.deprecated, Literal(True)))
        assert check_superset([_source()], output) == []

    def test_a_dropped_triple_is_missing(self):
        output = _source()
        output.remove((EX.Building, RDFS.label, None))
        [found] = check_superset([_source()], output)
        assert found.missing == ((EX.Building, RDFS.label, Literal("Building", lang="en")),)

    def test_an_excluded_triple_may_be_dropped(self):
        label = (EX.Building, RDFS.label, Literal("Building", lang="en"))
        output = _source()
        output.remove(label)
        assert check_superset([_source()], output, excluded=[label]) == []

    def test_an_excluded_triple_that_survives_is_reported(self):
        """A conflict reported as resolved, with both values still written (#169)."""
        label = (EX.Building, RDFS.label, Literal("Building", lang="en"))
        [found] = check_superset([_source()], _source(), excluded=[label])
        assert found.extra == (label,)
        assert (found.missing_count, found.extra_count) == (0, 1)

    def test_a_dropped_blank_node_interior_is_missing(self):
        output = _source()
        output.remove((None, OWL.onProperty, None))
        [found] = check_superset([_source()], output)
        assert found.missing_count > 0


class TestCountsAgree:
    def test_equal_counts_hold(self):
        assert check_counts_agree({"pages": 3, "index": 3, "search": 3}) == []

    def test_disagreeing_counts_are_named(self):
        [found] = check_counts_agree({"pages": 497, "index": 515})
        assert "pages = 497" in found.message
        assert "index = 515" in found.message


class TestCheckContract:
    @pytest.mark.parametrize(
        "contract",
        [Contract.ISOMORPHIC, Contract.TRIPLE_COUNT, Contract.UNION_ISOMORPHIC, Contract.SUPERSET],
    )
    def test_routes_every_graph_contract(self, contract: Contract):
        assert check_contract(contract, inputs=[_source()], outputs=[_source()]) == []

    def test_routes_counts(self):
        assert check_contract(Contract.COUNTS_AGREE, counts={"a": 1, "b": 2}) != []

    def test_a_failed_contract_is_returned_not_raised(self):
        found = check_contract(Contract.ISOMORPHIC, inputs=[_source()], outputs=[Graph()])
        assert len(found) == 1

    @pytest.mark.parametrize(
        ("contract", "inputs", "outputs"),
        [
            (Contract.ISOMORPHIC, 2, 1),
            (Contract.ISOMORPHIC, 1, 2),
            (Contract.TRIPLE_COUNT, 0, 1),
            (Contract.UNION_ISOMORPHIC, 2, 1),
            (Contract.SUPERSET, 0, 1),
            (Contract.SUPERSET, 1, 2),
        ],
    )
    def test_the_wrong_number_of_graphs_is_a_caller_error(
        self, contract: Contract, inputs: int, outputs: int
    ):
        with pytest.raises(ValueError):
            check_contract(
                contract,
                inputs=[_source()] * inputs,
                outputs=[_source()] * outputs,
            )

    def test_counts_agree_without_counts_is_a_caller_error(self):
        with pytest.raises(ValueError):
            check_contract(Contract.COUNTS_AGREE)

    def test_an_argument_the_contract_ignores_is_a_caller_error(self):
        """Excluded triples passed to ISOMORPHIC would otherwise be dropped in silence."""
        label = (EX.Building, RDFS.label, Literal("Building", lang="en"))
        with pytest.raises(ValueError):
            check_contract(
                Contract.ISOMORPHIC, inputs=[_source()], outputs=[_source()], excluded=[label]
            )
        with pytest.raises(ValueError):
            check_contract(
                Contract.ISOMORPHIC, inputs=[_source()], outputs=[_source()], counts={"a": 1}
            )
        with pytest.raises(ValueError):
            check_contract(Contract.COUNTS_AGREE, inputs=[_source()], counts={"a": 1})


class TestDescribe:
    def test_names_the_contract_and_each_sampled_triple(self):
        actual = _source()
        actual.remove((EX.Building, RDFS.label, None))
        text = describe(check_isomorphic(_source(), actual))
        assert text.startswith("isomorphic: ")
        assert (
            '  - <http://example.org/ont#Building> <http://www.w3.org/2000/01/rdf-schema#label> "Building"@en'
            in text
        )

    def test_says_how_many_were_not_sampled(self):
        expected = Graph()
        for i in range(SAMPLE_SIZE + 5):
            expected.add((EX[f"C{i}"], RDF.type, OWL.Class))
        assert "... and 5 more missing" in describe(check_isomorphic(expected, Graph()))

    def test_nothing_found_is_empty(self):
        assert describe([]) == ""


class TestContracts:
    def test_every_contract_names_a_real_command(self):
        assert set(CONTRACTS) <= EXPECTED_COMMANDS

    def test_the_table_is_read_only(self):
        with pytest.raises(TypeError):
            CONTRACTS["order"] = CONTRACTS["cast"]  # type: ignore[index]

    def test_keys_match_entries(self):
        assert all(name == entry.command for name, entry in CONTRACTS.items())

    def test_ambiguous_contracts_say_why(self):
        assert all(entry.note for entry in CONTRACTS.values() if entry.ambiguous)

    def test_the_verify_candidates_are_unambiguous(self):
        """#308 offers --verify only where the claim is settled."""
        assert not CONTRACTS["order"].ambiguous
        assert CONTRACTS["refactor deprecate"].ambiguous
