"""Data migration substitutes predicates as well as subjects and objects (#415).

A renamed property has to move in the instance data that uses it, or every triple is left on a
property the renamed ontology no longer declares. Both of the migrator's substitution sites are
covered (``DataMigrator.migrate``'s map and the rename rules applied through
``_apply_uri_substitution``), the summed statistics of ``migrate_data_files``, and the two commands
that reach them: ``refactor rename --migrate-data`` and ``merge``'s data migration.
"""

from pathlib import Path
from textwrap import dedent

from click.testing import CliRunner, Result
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF

from rdf_construct.merge import DataMigrator, MarkdownFormatter, TextFormatter, migrate_data_files
from rdf_construct.merge.config import MigrationRule
from rdf_construct.merge.migrator import MigrationResult, MigrationStats
from rdf_construct.refactor import OntologyRenamer, RenameConfig

EXAMPLES_DIR = Path(__file__).parent.parent / "examples" / "refactor"

EX = "http://example.org/o#"
OLD_NS = "http://old.example.org/ont#"
NEW_NS = "http://new.example.org/ont#"

ONTOLOGY = dedent(
    f"""\
    @prefix ex: <{EX}> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

    ex:Building a owl:Class .
    ex:hasFloors a owl:DatatypeProperty ; rdfs:domain ex:Building .
    """
)

DATA = dedent(
    f"""\
    @prefix ex: <{EX}> .
    @prefix d: <http://example.org/d#> .

    d:b1 a ex:Building ; ex:hasFloors 3 .
    """
)

NS_ONTOLOGY = dedent(
    f"""\
    @prefix o: <{OLD_NS}> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

    o:Building a owl:Class .
    o:hasFloors a owl:DatatypeProperty ; rdfs:domain o:Building .
    """
)

NS_DATA = dedent(
    f"""\
    @prefix o: <{OLD_NS}> .
    @prefix d: <http://example.org/d#> .

    d:b1 a o:Building ; o:hasFloors 3 .
    """
)

B1 = URIRef("http://example.org/d#b1")
HAS_FLOORS = URIRef(f"{EX}hasFloors")
FLOOR_COUNT = URIRef(f"{EX}floorCount")


def _data() -> Graph:
    return Graph().parse(data=DATA, format="turtle")


def _uses(graph: Graph, iri: URIRef) -> int:
    """Triples in which an IRI appears in any position."""
    return sum(1 for t in graph if iri in t)


def _run(argv: list[str]) -> Result:
    from rdf_construct.cli import cli
    from tests.test_cli_smoke import assert_no_crash

    result = CliRunner().invoke(cli, argv)
    assert_no_crash(result)
    return result


class TestMigratorSubstitutesPredicates:
    """Both substitution sites move a predicate, and count it."""

    def test_uri_map_moves_predicate(self):
        result = DataMigrator().migrate(_data(), uri_map={HAS_FLOORS: FLOOR_COUNT})

        assert (B1, FLOOR_COUNT, Literal(3)) in result.migrated_graph
        assert _uses(result.migrated_graph, HAS_FLOORS) == 0
        assert result.stats.predicates_updated == 1
        assert result.stats.subjects_updated == 0
        assert result.stats.objects_updated == 0
        assert result.stats.total_changes == 1

    def test_rename_rule_moves_predicate(self):
        rule = MigrationRule(type="rename", from_uri=str(HAS_FLOORS), to_uri=str(FLOOR_COUNT))

        result = DataMigrator().migrate(_data(), rules=[rule])

        assert (B1, FLOOR_COUNT, Literal(3)) in result.migrated_graph
        assert _uses(result.migrated_graph, HAS_FLOORS) == 0
        assert result.stats.predicates_updated == 1
        assert result.stats.total_changes == 1

    def test_unmapped_predicates_are_kept(self):
        result = DataMigrator().migrate(_data(), uri_map={HAS_FLOORS: FLOOR_COUNT})

        assert (B1, RDF.type, URIRef(f"{EX}Building")) in result.migrated_graph
        assert len(result.migrated_graph) == 2

    def test_punned_term_moves_in_every_position_as_the_renamer_does(self):
        """A term used as subject, predicate and object moves everywhere, counted per position.

        The ontology renamer already substitutes all three positions; the migrated data and the
        renamed ontology must agree on the same graph.
        """
        data = Graph()
        data.add((B1, HAS_FLOORS, Literal(3)))
        data.add((HAS_FLOORS, RDF.type, OWL.DatatypeProperty))
        data.add((B1, URIRef(f"{EX}mentions"), HAS_FLOORS))
        data.add((HAS_FLOORS, HAS_FLOORS, HAS_FLOORS))

        migrated = DataMigrator().migrate(data, uri_map={HAS_FLOORS: FLOOR_COUNT})
        renamed = OntologyRenamer().rename(
            data, RenameConfig(entities={str(HAS_FLOORS): str(FLOOR_COUNT)})
        )

        assert set(migrated.migrated_graph) == set(renamed.renamed_graph)
        stats = migrated.stats
        assert (stats.subjects_updated, stats.predicates_updated, stats.objects_updated) == (
            renamed.stats.subjects_renamed,
            renamed.stats.predicates_renamed,
            renamed.stats.objects_renamed,
        )
        assert stats.predicates_updated == 2

    def test_migrate_data_files_sums_predicates(self, tmp_path):
        paths = []
        for name, subject in (("a.ttl", "b1"), ("b.ttl", "b2")):
            path = tmp_path / name
            path.write_text(DATA.replace("d:b1", f"d:{subject}"))
            paths.append(path)

        result = migrate_data_files(paths, uri_map={HAS_FLOORS: FLOOR_COUNT})

        assert result.success
        assert result.stats.predicates_updated == 2
        assert result.stats.total_changes == 2
        assert _uses(result.migrated_graph, HAS_FLOORS) == 0

    def test_positional_stats_keep_their_meaning(self):
        """``MigrationStats`` is public: the new field is last, so old positional calls still hold."""
        stats = MigrationStats(1, 2, 3, 4)

        assert (stats.subjects_updated, stats.objects_updated) == (1, 2)
        assert (stats.triples_added, stats.triples_removed) == (3, 4)
        assert stats.predicates_updated == 0


class TestFormattersShowPredicates:
    """The migration summaries report predicates between subjects and objects."""

    def _result(self) -> MigrationResult:
        stats = MigrationStats(subjects_updated=1, predicates_updated=2, objects_updated=3)
        return MigrationResult(stats=stats, source_triples=4, result_triples=4)

    def test_text(self):
        lines = TextFormatter(use_colour=False).format_migration_result(self._result())
        assert "  Subjects updated: 1\n  Predicates updated: 2\n  Objects updated: 3\n" in lines

    def test_markdown(self):
        lines = MarkdownFormatter().format_migration_result(self._result())
        assert (
            "| Subjects updated | 1 |\n| Predicates updated | 2 |\n| Objects updated | 3 |\n"
            in lines
        )


class TestRefactorMigratesPredicates:
    """``refactor rename --migrate-data`` moves the instance triples of a renamed property."""

    def test_property_rename(self, tmp_path):
        """The reproducer from #415: it reported 0 changes and kept ex:hasFloors."""
        ontology, data = tmp_path / "ont.ttl", tmp_path / "data.ttl"
        ontology.write_text(ONTOLOGY)
        data.write_text(DATA)
        out, data_out = tmp_path / "new.ttl", tmp_path / "dout.ttl"

        result = _run(
            [
                "refactor",
                "rename",
                str(ontology),
                "--from",
                str(HAS_FLOORS),
                "--to",
                str(FLOOR_COUNT),
                "-o",
                str(out),
                "--migrate-data",
                str(data),
                "--data-output",
                str(data_out),
            ]
        )

        assert result.exit_code == 0, result.output
        assert "Migrated data.ttl: 1 changes" in result.output
        migrated = Graph().parse(data_out)
        assert (B1, FLOOR_COUNT, Literal(3)) in migrated
        assert _uses(migrated, HAS_FLOORS) == 0
        assert _uses(Graph().parse(out), FLOOR_COUNT) > 0

    def test_namespace_rename_moves_properties_too(self, tmp_path):
        """Every property in a renamed namespace moves, not only the classes."""
        ontology, data = tmp_path / "ont.ttl", tmp_path / "data.ttl"
        ontology.write_text(NS_ONTOLOGY)
        data.write_text(NS_DATA)
        data_out = tmp_path / "dout.ttl"

        result = _run(
            [
                "refactor",
                "rename",
                str(ontology),
                "--from-namespace",
                OLD_NS,
                "--to-namespace",
                NEW_NS,
                "-o",
                str(tmp_path / "new.ttl"),
                "--migrate-data",
                str(data),
                "--data-output",
                str(data_out),
            ]
        )

        assert result.exit_code == 0, result.output
        assert "Migrated data.ttl: 2 changes" in result.output
        migrated = Graph().parse(data_out)
        assert (B1, URIRef(f"{NEW_NS}hasFloors"), Literal(3)) in migrated
        assert (B1, RDF.type, URIRef(f"{NEW_NS}Building")) in migrated
        assert not any(OLD_NS in str(term) for triple in migrated for term in triple)

    def test_shipped_example_renames_its_property_in_the_data(self, tmp_path, monkeypatch):
        """``renames.yml`` fixes ``hasAddres``; the shipped instances use it as a predicate."""
        monkeypatch.chdir(EXAMPLES_DIR)
        data_out = tmp_path / "migrated.ttl"

        result = _run(
            [
                "refactor",
                "rename",
                "-c",
                "renames.yml",
                "-o",
                str(tmp_path / "fixed.ttl"),
                "--migrate-data",
                "instances.ttl",
                "--data-output",
                str(data_out),
            ]
        )

        assert result.exit_code == 0, result.output
        assert "Migrated instances.ttl: 7 changes" in result.output
        migrated = Graph().parse(data_out)
        assert _uses(migrated, URIRef("http://example.org/ont#hasAddres")) == 0
        assert _uses(migrated, URIRef("http://example.org/ont#hasAddress")) == 2


class TestMergeMigratesPredicates:
    """``merge``'s data migration applies a rename rule to predicates, and says so."""

    def test_rename_rule_for_a_property(self, tmp_path):
        (tmp_path / "ont.ttl").write_text(ONTOLOGY)
        (tmp_path / "data.ttl").write_text(DATA)
        data_out = tmp_path / "mdata.ttl"
        config = tmp_path / "merge.yml"
        config.write_text(
            dedent(
                f"""\
                sources:
                  - path: {tmp_path / "ont.ttl"}
                migrate_data:
                  sources:
                    - {tmp_path / "data.ttl"}
                  output: {data_out}
                  rules:
                    - type: rename
                      from: "{HAS_FLOORS}"
                      to: "{FLOOR_COUNT}"
                """
            )
        )

        result = _run(["merge", "-c", str(config), "-o", str(tmp_path / "merged.ttl")])

        assert result.exit_code == 0, result.output
        assert "  Predicates updated: 1\n" in result.output
        migrated = Graph().parse(data_out)
        assert (B1, FLOOR_COUNT, Literal(3)) in migrated
        assert _uses(migrated, HAS_FLOORS) == 0
