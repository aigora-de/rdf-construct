"""Tests for subjects that no section of an ordering profile claims.

`order` built its output graph from the subjects the profile's sections
selected, so anything no section claimed was discarded with no warning and
exit code 0 — reachable through the shipped example configs. Two distinct
failures live here:

- Blank nodes lost their triples while the reference to them survived, so an
  ``owl:Restriction`` collapsed to an empty ``[ ]`` — not a partial ontology
  but a different one. That is repaired unconditionally.
- Named subjects are governed by the ``unclaimed`` policy: ``warn`` (default),
  ``emit`` or ``ignore``.

Relates to: #84
"""

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner
from rdflib import RDF, BNode, Graph, Literal, Namespace
from rdflib.namespace import OWL, RDFS

from rdf_construct.cli import cli
from rdf_construct.core import OrderingConfig, bnode_closure

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"

EX = Namespace("http://example.org/")


# -- Fixtures --


@pytest.fixture
def restriction_ontology(tmp_path: Path) -> Path:
    """Ontology whose classes carry blank-node axioms.

    Covers both bnode shapes that matter: a single ``owl:Restriction`` hanging
    off ``rdfs:subClassOf``, and an ``owl:unionOf`` collection, which rdflib
    represents as a chain of blank nodes and so exercises transitivity.
    """
    content = dedent(
        """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        <http://example.org/> a owl:Ontology .

        ex:Dog a owl:Class ;
            rdfs:label "Dog" ;
            rdfs:subClassOf ex:Animal ,
                [ a owl:Restriction ;
                  owl:onProperty ex:hasOwner ;
                  owl:someValuesFrom ex:Person ] .

        ex:Animal a owl:Class .
        ex:Person a owl:Class .

        ex:Union a owl:Class ;
            owl:unionOf ( ex:Dog ex:Person ) .

        ex:hasOwner a owl:ObjectProperty .

        ex:note a owl:AnnotationProperty ;
            rdfs:label "note" .
        """
    ).strip()

    path = tmp_path / "restrictions.ttl"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def classes_only_config(tmp_path: Path) -> Path:
    """Config whose single profile claims classes and nothing else."""
    content = dedent(
        """
        selectors:
          classes: "rdf:type owl:Class"
        profiles:
          classes_only:
            description: "Classes and nothing else"
            sections:
              - header: {}
              - classes:
                  select: classes
                  sort: alpha
        """
    ).strip()

    path = tmp_path / "classes_only.yml"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def policy_config(tmp_path: Path) -> Path:
    """Config exercising each ``unclaimed`` policy and its inheritance."""
    content = dedent(
        """
        defaults:
          unclaimed: emit
        selectors:
          classes: "rdf:type owl:Class"
        profiles:
          inherits_emit:
            sections:
              - header: {}
              - classes: {select: classes, sort: alpha}
          overrides_ignore:
            unclaimed: ignore
            sections:
              - header: {}
              - classes: {select: classes, sort: alpha}
          overrides_warn:
            unclaimed: warn
            sections:
              - header: {}
              - classes: {select: classes, sort: alpha}
        """
    ).strip()

    path = tmp_path / "policies.yml"
    path.write_text(content, encoding="utf-8")
    return path


def _order(source: Path, config: Path, outdir: Path, *args: str):
    """Run the order command through Click's test runner."""
    runner = CliRunner()
    return runner.invoke(cli, ["order", str(source), str(config), "-o", str(outdir), *args])


# -- The shipped examples must not demonstrate the bug --


class TestShippedExamplesRoundTrip:
    """The bug was reachable by copying a shipped config; it must not be.

    A new user is invited to copy `examples/order/sample_profile.yml`, and its
    `doc_order` and `props_by_domain` profiles had no `annotation_properties`
    section — so `animals:scientificName` and its three triples vanished.
    """

    @pytest.mark.parametrize("config_name", ["sample_profile.yml", "ies_profile.yml"])
    @pytest.mark.parametrize("source_name", ["animal_ontology.ttl", "organisation_ontology.ttl"])
    def test_every_profile_preserves_every_triple(
        self, tmp_path: Path, config_name: str, source_name: str
    ) -> None:
        source = EXAMPLES / source_name
        config = EXAMPLES / "order" / config_name
        assert source.exists() and config.exists()

        result = _order(source, config, tmp_path)
        assert result.exit_code == 0

        base = Graph()
        base.parse(source)

        profiles = OrderingConfig(config).list_profiles()
        assert profiles

        for profile in profiles:
            out = tmp_path / f"{source.stem}-{profile}.ttl"
            ordered = Graph()
            ordered.parse(out)
            assert ordered.isomorphic(base), (
                f"{config_name} profile '{profile}' lost "
                f"{len(base) - len(ordered)} triple(s) of {source_name}"
            )

    def test_shipped_configs_emit_no_warning(self, tmp_path: Path) -> None:
        """A config that warns on its own example ontology is documentation of a bug."""
        result = _order(
            EXAMPLES / "animal_ontology.ttl",
            EXAMPLES / "order" / "sample_profile.yml",
            tmp_path,
        )
        assert result.exit_code == 0
        assert "claimed by no section" not in result.output

    def test_compact_filters_deliberately_and_silently(self, tmp_path: Path) -> None:
        """`compact` is header-and-classes by design and declares `unclaimed: ignore`."""
        source = EXAMPLES / "animal_ontology.ttl"
        result = _order(source, EXAMPLES / "order" / "test_profile.yml", tmp_path, "-p", "compact")
        assert result.exit_code == 0
        assert "claimed by no section" not in result.output

        base = Graph()
        base.parse(source)
        ordered = Graph()
        ordered.parse(tmp_path / f"{source.stem}-compact.ttl")
        assert len(ordered) < len(base)


# -- Blank-node closure --


class TestBnodeClosure:
    """Tests for the bnode_closure helper."""

    def test_finds_directly_referenced_bnode(self) -> None:
        g = Graph()
        node = BNode()
        g.add((EX.Dog, RDFS.subClassOf, node))
        g.add((node, RDF.type, OWL.Restriction))

        assert bnode_closure(g, [EX.Dog]) == [node]

    def test_walks_nested_bnodes_transitively(self) -> None:
        g = Graph()
        outer, inner = BNode(), BNode()
        g.add((EX.Thing, EX.hasQuantity, outer))
        g.add((outer, EX.hasValue, inner))
        g.add((inner, RDF.value, Literal(3)))

        assert set(bnode_closure(g, [EX.Thing])) == {outer, inner}

    def test_ignores_bnodes_already_present(self) -> None:
        g = Graph()
        node = BNode()
        g.add((EX.Dog, RDFS.subClassOf, node))
        g.add((node, RDF.type, OWL.Restriction))

        assert bnode_closure(g, [EX.Dog, node]) == []

    def test_ignores_unreachable_bnodes(self) -> None:
        g = Graph()
        orphan = BNode()
        g.add((EX.Dog, RDF.type, OWL.Class))
        g.add((orphan, RDF.type, OWL.Restriction))

        assert bnode_closure(g, [EX.Dog]) == []

    def test_terminates_on_a_bnode_cycle(self) -> None:
        g = Graph()
        first, second = BNode(), BNode()
        g.add((EX.Thing, EX.points, first))
        g.add((first, EX.points, second))
        g.add((second, EX.points, first))

        assert set(bnode_closure(g, [EX.Thing])) == {first, second}

    def test_does_not_follow_named_subjects(self) -> None:
        """Closure repairs anonymous descriptions; it does not pull in whole graphs."""
        g = Graph()
        node = BNode()
        g.add((EX.Dog, RDFS.subClassOf, EX.Animal))
        g.add((EX.Animal, RDFS.subClassOf, node))
        g.add((node, RDF.type, OWL.Restriction))

        assert bnode_closure(g, [EX.Dog]) == []


class TestBnodesSurviveUnclaimed:
    """A blank node no section claimed must not collapse to an empty `[ ]`."""

    def test_restriction_is_emitted_in_full(
        self, restriction_ontology: Path, classes_only_config: Path, tmp_path: Path
    ) -> None:
        outdir = tmp_path / "out"
        result = _order(restriction_ontology, classes_only_config, outdir)
        assert result.exit_code == 0

        ordered = Graph()
        ordered.parse(outdir / "restrictions-classes_only.ttl")

        restrictions = list(ordered.subjects(RDF.type, OWL.Restriction))
        assert len(restrictions) == 1
        assert (restrictions[0], OWL.onProperty, EX.hasOwner) in ordered
        assert (restrictions[0], OWL.someValuesFrom, EX.Person) in ordered

    def test_collection_members_survive(
        self, restriction_ontology: Path, classes_only_config: Path, tmp_path: Path
    ) -> None:
        outdir = tmp_path / "out"
        assert _order(restriction_ontology, classes_only_config, outdir).exit_code == 0

        ordered = Graph()
        ordered.parse(outdir / "restrictions-classes_only.ttl")

        union = next(ordered.objects(EX.Union, OWL.unionOf))
        members = list(ordered.items(union))
        assert members == [EX.Dog, EX.Person]

    def test_no_empty_brackets_in_output(
        self, restriction_ontology: Path, classes_only_config: Path, tmp_path: Path
    ) -> None:
        """The visible symptom: `rdfs:subClassOf [ ]` and `owl:unionOf [ ]`."""
        outdir = tmp_path / "out"
        assert _order(restriction_ontology, classes_only_config, outdir).exit_code == 0

        text = (outdir / "restrictions-classes_only.ttl").read_text(encoding="utf-8")
        assert "[\n        ]" not in text
        assert "[\n    ]" not in text

    def test_bnodes_are_not_reported_as_unclaimed(
        self, restriction_ontology: Path, classes_only_config: Path, tmp_path: Path
    ) -> None:
        """Only named subjects are counted: a bnode identifier tells the user nothing."""
        result = _order(restriction_ontology, classes_only_config, tmp_path / "out")
        assert result.exit_code == 0
        # ex:hasOwner and ex:note are unclaimed; the three blank nodes are not.
        assert "2 subjects claimed by no section" in result.output


# -- The unclaimed policy --


class TestUnclaimedPolicyResolution:
    """Tests for OrderingConfig.get_unclaimed_policy."""

    def test_defaults_to_warn(self, classes_only_config: Path) -> None:
        config = OrderingConfig(classes_only_config)
        assert config.get_unclaimed_policy("classes_only") == "warn"

    def test_inherits_config_level_default(self, policy_config: Path) -> None:
        config = OrderingConfig(policy_config)
        assert config.get_unclaimed_policy("inherits_emit") == "emit"

    def test_profile_overrides_config_level(self, policy_config: Path) -> None:
        config = OrderingConfig(policy_config)
        assert config.get_unclaimed_policy("overrides_ignore") == "ignore"
        assert config.get_unclaimed_policy("overrides_warn") == "warn"

    def test_rejects_an_unknown_policy(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yml"
        path.write_text(
            dedent(
                """
                profiles:
                  bogus:
                    unclaimed: yes-please
                    sections:
                      - header: {}
                """
            ).strip(),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="warn, emit, ignore"):
            OrderingConfig(path).get_unclaimed_policy("bogus")


class TestUnclaimedPolicyBehaviour:
    """End-to-end behaviour of each policy through the CLI."""

    def test_warn_names_the_term_and_the_missing_section(
        self, restriction_ontology: Path, classes_only_config: Path, tmp_path: Path
    ) -> None:
        """A bare count tells the user something is wrong but not what to do."""
        result = _order(restriction_ontology, classes_only_config, tmp_path / "out")

        assert result.exit_code == 0
        assert "profile 'classes_only'" in result.output
        assert "3 triples dropped" in result.output
        assert "ex:note" in result.output
        assert "owl:AnnotationProperty" in result.output
        assert "`select: ann_props`" in result.output
        assert "`select: obj_props`" in result.output

    def test_warn_does_not_change_the_output(
        self, restriction_ontology: Path, classes_only_config: Path, tmp_path: Path
    ) -> None:
        outdir = tmp_path / "out"
        assert _order(restriction_ontology, classes_only_config, outdir).exit_code == 0

        ordered = Graph()
        ordered.parse(outdir / "restrictions-classes_only.ttl")
        assert (EX.note, RDF.type, OWL.AnnotationProperty) not in ordered

    def test_emit_loses_nothing(
        self, restriction_ontology: Path, policy_config: Path, tmp_path: Path
    ) -> None:
        outdir = tmp_path / "out"
        result = _order(restriction_ontology, policy_config, outdir, "-p", "inherits_emit")
        assert result.exit_code == 0

        base = Graph()
        base.parse(restriction_ontology)
        ordered = Graph()
        ordered.parse(outdir / "restrictions-inherits_emit.ttl")
        assert ordered.isomorphic(base)

    def test_ignore_is_silent(
        self, restriction_ontology: Path, policy_config: Path, tmp_path: Path
    ) -> None:
        result = _order(
            restriction_ontology, policy_config, tmp_path / "out", "-p", "overrides_ignore"
        )
        assert result.exit_code == 0
        assert "claimed by no section" not in result.output

    def test_warn_exits_zero(
        self, restriction_ontology: Path, policy_config: Path, tmp_path: Path
    ) -> None:
        """Warnings that change the exit code break the scripts that call this."""
        result = _order(
            restriction_ontology, policy_config, tmp_path / "out", "-p", "overrides_warn"
        )
        assert result.exit_code == 0
        assert "claimed by no section" in result.output

    def test_unknown_policy_aborts_before_writing_anything(
        self, restriction_ontology: Path, tmp_path: Path
    ) -> None:
        """A typo in the last profile must not surface after the first is written."""
        config = tmp_path / "mixed.yml"
        config.write_text(
            dedent(
                """
                selectors:
                  classes: "rdf:type owl:Class"
                profiles:
                  good:
                    sections:
                      - header: {}
                      - classes: {select: classes, sort: alpha}
                  bad:
                    unclaimed: sure
                    sections:
                      - header: {}
                """
            ).strip(),
            encoding="utf-8",
        )

        outdir = tmp_path / "out"
        result = _order(restriction_ontology, config, outdir)

        assert result.exit_code != 0
        assert "Unknown 'unclaimed' policy" in result.output
        assert list(outdir.glob("*.ttl")) == []


class TestUnclaimedReporting:
    """The message has to be actionable, and it has to scale."""

    def test_lists_at_most_three_then_summarises(self, tmp_path: Path) -> None:
        lines = [
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
            "@prefix ex: <http://example.org/> .",
            "",
            "ex:Kept a owl:Class .",
        ]
        lines += [f"ex:prop{i} a owl:AnnotationProperty ." for i in range(5)]
        source = tmp_path / "many.ttl"
        source.write_text("\n".join(lines), encoding="utf-8")

        config = tmp_path / "classes.yml"
        config.write_text(
            dedent(
                """
                selectors:
                  classes: "rdf:type owl:Class"
                profiles:
                  classes_only:
                    sections:
                      - classes: {select: classes, sort: alpha}
                """
            ).strip(),
            encoding="utf-8",
        )

        result = _order(source, config, tmp_path / "out")

        assert result.exit_code == 0
        assert "5 subjects claimed by no section" in result.output
        assert "… and 2 more" in result.output

    def test_uses_singular_wording_for_one_subject(self, tmp_path: Path) -> None:
        source = tmp_path / "one.ttl"
        source.write_text(
            dedent(
                """
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix ex: <http://example.org/> .

                ex:Kept a owl:Class .
                ex:lost a owl:AnnotationProperty .
                """
            ).strip(),
            encoding="utf-8",
        )

        config = tmp_path / "classes.yml"
        config.write_text(
            dedent(
                """
                selectors:
                  classes: "rdf:type owl:Class"
                profiles:
                  classes_only:
                    sections:
                      - classes: {select: classes, sort: alpha}
                """
            ).strip(),
            encoding="utf-8",
        )

        result = _order(source, config, tmp_path / "out")

        assert result.exit_code == 0
        assert "1 subject claimed by no section" in result.output
        assert "1 triple dropped" in result.output

    def test_reports_a_term_with_no_matching_selector(self, tmp_path: Path) -> None:
        """An unclaimed term nothing can claim still gets the policy advice."""
        source = tmp_path / "odd.ttl"
        source.write_text(
            dedent(
                """
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix ex: <http://example.org/> .

                ex:Kept a owl:Class .
                ex:thing a ex:Widget .
                """
            ).strip(),
            encoding="utf-8",
        )

        config = tmp_path / "no_individuals.yml"
        config.write_text(
            dedent(
                """
                selectors:
                  classes: "rdf:type owl:Class"
                profiles:
                  classes_only:
                    sections:
                      - classes: {select: classes, sort: alpha}
                """
            ).strip(),
            encoding="utf-8",
        )

        result = _order(source, config, tmp_path / "out")

        assert result.exit_code == 0
        assert "ex:thing" in result.output
        assert "`unclaimed: ignore`" in result.output

    def test_unprefixed_uri_is_reported_in_full(self, tmp_path: Path) -> None:
        """No prefix is invented for the report — that would alter the output file."""
        source = tmp_path / "nopfx.ttl"
        source.write_text(
            dedent(
                """
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix ex: <http://example.org/> .

                ex:Kept a owl:Class .
                <http://elsewhere.invalid/lost> a owl:AnnotationProperty .
                """
            ).strip(),
            encoding="utf-8",
        )

        config = tmp_path / "classes.yml"
        config.write_text(
            dedent(
                """
                selectors:
                  classes: "rdf:type owl:Class"
                profiles:
                  classes_only:
                    sections:
                      - classes: {select: classes, sort: alpha}
                """
            ).strip(),
            encoding="utf-8",
        )

        result = _order(source, config, tmp_path / "out")

        assert result.exit_code == 0
        assert "<http://elsewhere.invalid/lost>" in result.output
