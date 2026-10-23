"""``merge`` compares sources (#193) and applies the resolution it reports (#169).

The tiers are ``rdf_construct.core.predicate_tiers``. The fixtures in
``tests/fixtures/merge/conflicts/`` carry one case each, and every ``*.expected.ttl`` is written by
hand, so an output that keeps a loser, drops a winner or picks a load-bearing value is visible as a
difference from it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner, Result
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import RDFS, SKOS

from rdf_construct.cli import cli
from rdf_construct.core.predicate_tiers import (
    DEFAULT_PREDICATE_TIERS,
    PredicateTier,
    build_tiers,
    language_bucket,
    tier_of,
)
from rdf_construct.core.verify import check_isomorphic, describe
from rdf_construct.merge import ConflictDetector, SourceGraph
from tests.test_cli_smoke import assert_no_crash

FIXTURES = Path(__file__).parent / "fixtures" / "merge" / "conflicts"
EX = Namespace("http://example.org/")
DCTERMS_TITLE = "http://purl.org/dc/terms/title"
STRATEGIES = ["priority", "first", "last", "mark_all"]


def _f(name: str) -> Path:
    return FIXTURES / name


def _merge(tmp_path: Path, *argv: object) -> tuple[Result, Graph, str]:
    out = tmp_path / "merged.ttl"
    result = CliRunner().invoke(cli, ["merge", *[str(a) for a in argv], "-o", str(out)])
    assert_no_crash(result)
    text = out.read_text() if out.exists() else ""
    return result, (Graph().parse(data=text, format="turtle") if text else Graph()), text


def _config(tmp_path: Path, sources: list[tuple[Path, int | None]], **conflicts: object) -> Path:
    data = {
        "sources": [
            {"path": str(path)} if priority is None else {"path": str(path), "priority": priority}
            for path, priority in sources
        ],
        "conflicts": conflicts,
    }
    path = tmp_path / "merge.yml"
    path.write_text(yaml.safe_dump(data))
    return path


def _assert_is(expected: str, merged: Graph) -> None:
    found = check_isomorphic(Graph().parse(_f(expected)), merged)
    assert not found, describe(found)


def _detected(result: Result) -> int:
    for line in result.output.splitlines():
        if line.strip().startswith("Detected:"):
            return int(line.split(":")[1])
    assert "No conflicts detected" in result.output, result.output
    return 0


class TestDetectionComparesSources:
    """#193: a conflict needs values from more than one source."""

    def test_a_multilingual_file_alone_has_no_conflict(self, tmp_path):
        result, merged, _ = _merge(tmp_path, _f("multilang.ttl"), "--strategy", "mark_all")
        assert result.exit_code == 0, result.output
        assert _detected(result) == 0
        assert isomorphic(merged, Graph().parse(_f("multilang.ttl")))

    def test_a_multilingual_file_with_itself_has_no_conflict(self, tmp_path):
        source = _f("multilang.ttl")
        result, merged, _ = _merge(tmp_path, source, source, "--strategy", "mark_all")
        assert result.exit_code == 0, result.output
        assert _detected(result) == 0
        assert isomorphic(merged, Graph().parse(source))

    def test_two_values_from_one_source_never_conflict(self):
        graph = Graph().parse(_f("subset_b.ttl"))
        detector = ConflictDetector()
        assert detector.detect_conflicts([SourceGraph(graph, "subset_b.ttl", 1)]) == []

    def test_a_subset_of_another_source_is_not_a_conflict(self, tmp_path):
        a, b = _f("subset_a.ttl"), _f("subset_b.ttl")
        result, merged, _ = _merge(tmp_path, a, b, "-p", "2", "-p", "1")
        assert result.exit_code == 0, result.output
        assert _detected(result) == 0
        assert isomorphic(merged, Graph().parse(a) + Graph().parse(b))

    def test_an_unlisted_predicate_is_repeatable(self, tmp_path):
        a, b = _f("unlisted_a.ttl"), _f("unlisted_b.ttl")
        result, merged, _ = _merge(tmp_path, a, b, "--strategy", "mark_all")
        assert result.exit_code == 0, result.output
        assert _detected(result) == 0
        assert isomorphic(merged, Graph().parse(a) + Graph().parse(b))

    def test_the_ontology_header_is_left_for_171(self, tmp_path):
        a, b = _f("header_a.ttl"), _f("header_b.ttl")
        result, merged, _ = _merge(tmp_path, a, b)
        assert result.exit_code == 0, result.output
        assert _detected(result) == 0
        assert isomorphic(merged, Graph().parse(a) + Graph().parse(b))


class TestTheMiddleTier:
    """#169: ``--strategy`` picks per language tag, and the losing triple is removed."""

    @pytest.mark.parametrize("strategy", ["priority", "first", "last"])
    def test_each_strategy_keeps_its_own_winner(self, strategy: str, tmp_path):
        result, merged, text = _merge(
            tmp_path,
            *(_f(f"labels_{x}.ttl") for x in "abc"),
            "-p", "1", "-p", "3", "-p", "2",
            "--strategy", strategy,
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        assert _detected(result) == 1
        assert "CONFLICT" not in text
        _assert_is(f"labels.{strategy}.expected.ttl", merged)

    def test_mark_all_keeps_every_value_and_says_why(self, tmp_path):
        result, merged, text = _merge(
            tmp_path, *(_f(f"labels_{x}.ttl") for x in "abc"), "--strategy", "mark_all"
        )
        assert result.exit_code == 1, result.output
        _assert_is("labels.mark_all.expected.ttl", merged)
        assert "# Ambiguous: two rdfs:label values tagged @en are legal RDF" in text
        assert "# Not picked: --strategy mark_all marks every conflict." in text

    def test_the_four_strategies_write_four_different_graphs(self, tmp_path):
        graphs = []
        for strategy in STRATEGIES:
            out = tmp_path / strategy
            out.mkdir()
            _, merged, _ = _merge(
                out,
                *(_f(f"labels_{x}.ttl") for x in "abc"),
                "-p", "1", "-p", "3", "-p", "2",
                "--strategy", strategy,
            )  # fmt: skip
            graphs.append(frozenset(merged))
        assert len(set(graphs)) == 4

    def test_tags_are_compared_without_case_and_untagged_is_a_bucket(self, tmp_path):
        result, merged, _ = _merge(tmp_path, _f("tags_a.ttl"), _f("tags_b.ttl"))
        assert result.exit_code == 0, result.output
        assert _detected(result) == 2
        _assert_is("tags.expected.ttl", merged)

    def test_a_second_preflabel_is_called_malformed(self, tmp_path):
        a, b = _f("preflabel_a.ttl"), _f("preflabel_b.ttl")
        result, merged, text = _merge(tmp_path, a, b, "--strategy", "mark_all")
        assert result.exit_code == 1, result.output
        assert "# Malformed: SKOS allows one skos:prefLabel per language tag (S14)" in text
        assert "demote the others to skos:altLabel" in text
        assert isomorphic(merged, Graph().parse(a) + Graph().parse(b))

    def test_a_picked_preflabel_keeps_both_altlabels(self, tmp_path):
        result, merged, _ = _merge(tmp_path, _f("preflabel_a.ttl"), _f("preflabel_b.ttl"))
        assert result.exit_code == 0, result.output
        assert set(merged.objects(EX.car, SKOS.prefLabel)) == {Literal("Automobile", lang="en")}
        assert len(set(merged.objects(EX.car, SKOS.altLabel))) == 2

    def test_tied_priorities_that_disagree_are_marked(self, tmp_path):
        a, b = _f("labels_a.ttl"), _f("labels_b.ttl")
        config = _config(tmp_path, [(a, None), (b, None)], strategy="priority")
        result, merged, text = _merge(tmp_path, "-c", config)
        assert result.exit_code == 1, result.output
        assert "# Not picked: sources tied at priority 1;" in text
        assert isomorphic(merged, Graph().parse(a) + Graph().parse(b))

    def test_tied_priorities_that_agree_are_picked(self, tmp_path):
        a, b = _f("labels_a.ttl"), _f("labels_b.ttl")
        copy = tmp_path / "labels_a_copy.ttl"
        copy.write_text(a.read_text())
        config = _config(tmp_path, [(b, 1), (a, 2), (copy, 2)], strategy="priority")
        result, merged, _ = _merge(tmp_path, "-c", config)
        assert result.exit_code == 0, result.output
        labels = set(merged.objects(EX.Thing, RDFS.label))
        assert Literal("Alpha", lang="en") in labels
        assert Literal("Beta", lang="en") not in labels

    def test_a_value_that_is_not_a_literal_is_never_removed(self, tmp_path):
        a, b = tmp_path / "a.ttl", tmp_path / "b.ttl"
        a.write_text("@prefix ex: <http://example.org/> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\nex:W rdfs:label ex:NameNode .\n")  # fmt: skip
        b.write_text("@prefix ex: <http://example.org/> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\nex:W rdfs:label \"Name\" .\n")  # fmt: skip
        result, merged, text = _merge(tmp_path, a, b)
        assert result.exit_code == 1, result.output
        assert "only literals are ever removed" in text
        assert len(merged) == 2


class TestTheLoadBearingTier:
    """#169: ``rdfs:domain`` and ``rdfs:range`` are marked, never picked, and both values stay."""

    @pytest.mark.parametrize("strategy", STRATEGIES)
    def test_marked_and_kept_under_every_strategy(self, strategy: str, tmp_path):
        a, b = _f("domain_range_a.ttl"), _f("domain_range_b.ttl")
        result, merged, text = _merge(tmp_path, a, b, "-p", "1", "-p", "2", "--strategy", strategy)
        assert result.exit_code == 1, result.output
        _assert_is("domain_range.expected.ttl", merged)
        assert text.count("=== CONFLICT:") == 2
        assert "# Changes meaning: two rdfs:domain values mean their intersection" in text
        assert "# Not picked under any --strategy." in text
        assert "keep one value below" not in text

    def test_a_declared_functional_property_is_load_bearing(self, tmp_path):
        a, b = _f("functional_a.ttl"), _f("functional_b.ttl")
        result, merged, text = _merge(tmp_path, a, b)
        assert result.exit_code == 1, result.output
        assert "ex:maxOccupancy is declared owl:FunctionalProperty" in text
        assert isomorphic(merged, Graph().parse(a) + Graph().parse(b))


class TestTheOverride:
    """The tier map is overridable in config, by full IRI."""

    def test_a_predicate_can_be_made_per_language(self, tmp_path):
        a, b = _f("unlisted_a.ttl"), _f("unlisted_b.ttl")
        config = _config(
            tmp_path, [(a, 1), (b, 2)], predicate_tiers={"per_language": [DCTERMS_TITLE]}
        )
        result, merged, _ = _merge(tmp_path, "-c", config)
        assert result.exit_code == 0, result.output
        assert _detected(result) == 1
        titles = set(merged.objects(EX.Hall, URIRef(DCTERMS_TITLE)))
        assert titles == {Literal("Venue hall", lang="en")}

    def test_a_predicate_can_be_made_repeatable(self, tmp_path):
        a, b = _f("labels_a.ttl"), _f("labels_b.ttl")
        config = _config(
            tmp_path, [(a, 1), (b, 2)], predicate_tiers={"repeatable": [str(RDFS.label)]}
        )
        result, merged, _ = _merge(tmp_path, "-c", config)
        assert result.exit_code == 0, result.output
        assert _detected(result) == 0
        assert isomorphic(merged, Graph().parse(a) + Graph().parse(b))

    def test_the_configuration_wins_over_a_functional_declaration(self, tmp_path):
        a, b = _f("functional_a.ttl"), _f("functional_b.ttl")
        config = _config(
            tmp_path,
            [(a, 1), (b, 2)],
            predicate_tiers={"repeatable": [f"<{EX.maxOccupancy}>"]},
        )
        result, _, _ = _merge(tmp_path, "-c", config)
        assert result.exit_code == 0, result.output
        assert _detected(result) == 0

    def test_ignore_predicates_still_takes_an_iri(self, tmp_path):
        a, b = _f("labels_a.ttl"), _f("labels_b.ttl")
        config = _config(tmp_path, [(a, 1), (b, 2)], ignore_predicates=[str(RDFS.label)])
        result, _, _ = _merge(tmp_path, "-c", config)
        assert result.exit_code == 0, result.output
        assert _detected(result) == 0

    @pytest.mark.parametrize(
        ("conflicts", "message"),
        [
            ({"ignore_predicates": ["rdfs:label"]}, "'rdfs:label' is not an IRI"),
            ({"predicate_tiers": {"load_bearing": ["rdfs:label"]}}, "'rdfs:label' is not an IRI"),
            ({"predicate_tiers": {"single": [DCTERMS_TITLE]}}, "unknown tier 'single'"),
            (
                {
                    "predicate_tiers": {
                        "per_language": [DCTERMS_TITLE],
                        "load_bearing": [DCTERMS_TITLE],
                    }
                },
                "is placed in two tiers",
            ),
            (
                {
                    "ignore_predicates": [DCTERMS_TITLE],
                    "predicate_tiers": {"load_bearing": [DCTERMS_TITLE]},
                },
                "is placed in two tiers",
            ),
        ],
        ids=["curie-ignored", "curie-tier", "unknown-tier", "two-tiers", "ignored-and-tiered"],
    )
    def test_a_predicate_it_cannot_place_is_refused(self, conflicts, message, tmp_path):
        config = _config(tmp_path, [(_f("labels_a.ttl"), 1)], **conflicts)
        result, _, _ = _merge(tmp_path, "-c", config)
        assert result.exit_code == 2, result.output
        assert message in result.output
        assert not (tmp_path / "merged.ttl").exists()


class TestTheTierMap:
    def test_the_decided_tiers(self):
        assert tier_of(RDFS.comment, DEFAULT_PREDICATE_TIERS) is PredicateTier.REPEATABLE
        assert tier_of(RDFS.label, DEFAULT_PREDICATE_TIERS) is PredicateTier.PER_LANGUAGE
        assert tier_of(RDFS.range, DEFAULT_PREDICATE_TIERS) is PredicateTier.LOAD_BEARING
        assert tier_of(RDFS.subClassOf, DEFAULT_PREDICATE_TIERS) is PredicateTier.REPEATABLE

    def test_an_override_wins_and_a_double_placement_is_refused(self):
        tiers = build_tiers({PredicateTier.REPEATABLE: [RDFS.domain]})
        assert tiers[RDFS.domain] is PredicateTier.REPEATABLE
        with pytest.raises(ValueError, match="two tiers"):
            build_tiers(
                {PredicateTier.REPEATABLE: [RDFS.domain], PredicateTier.LOAD_BEARING: [RDFS.domain]}
            )

    def test_the_bucket_folds_case_and_keeps_subtags(self):
        assert language_bucket(Literal("x", lang="EN-gb")) == language_bucket(
            Graph()
            .parse(data='<urn:a> <urn:b> "x"@EN-gb .', format="nt")
            .value(URIRef("urn:a"), URIRef("urn:b"))
        )
        assert language_bucket(Literal("x", lang="en")) != language_bucket(
            Literal("x", lang="en-gb")
        )
        assert language_bucket(Literal("x")) is None


class TestCost:
    def test_twenty_thousand_values_on_one_key(self, tmp_path):
        """Sam's worst case: the old index compared each value with every other (118.6 s)."""
        values = ", ".join(f'"label {i}"@en' for i in range(20000))
        a, b = tmp_path / "a.ttl", tmp_path / "b.ttl"
        a.write_text(f"<http://example.org/Hub> <{RDFS.label}> {values} .\n")
        b.write_text(a.read_text().replace('"label 0"@en', '"other"@en'))
        result, merged, text = _merge(tmp_path, a, b, "--strategy", "mark_all")
        assert result.exit_code == 1, result.output
        assert len(merged) == 20001
        assert text.count("# Source:") == 2
