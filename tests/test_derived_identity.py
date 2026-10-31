"""What a filtering ``order`` profile writes about itself (#90) and into itself (#280).

#90: a profile that drops anything writes an extract, and before this fix the extract kept its
source's header verbatim, ``owl:versionIRI`` included, so it claimed to be the release it was cut
from. Now any run that writes fewer source triples than it read keeps the ontology IRI,
``owl:versionInfo`` and ``owl:imports``, drops ``owl:versionIRI``, and gains
``prov:wasDerivedFrom`` naming the source. The trigger is what was written, not the profile's
``unclaimed`` policy. The header is also no longer a section's to lose: it leads the file whether
or not a ``header`` section exists, and a profile omits it only by saying ``header: false``.

#280: a ``classes`` section claimed the anonymous ``owl:unionOf`` behind a property's range, so a
profile that dropped the property wrote the union as a detached ``_:n…`` stub. A blank node
reachable from a named subject is now never selected; the closure brings it in with its owner.

The fixture family is ``tests/fixtures/provenance/``.
"""

from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner, Result
from rdflib import RDF, BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, PROV, RDFS

from rdf_construct.cli import cli

FIXTURES = Path(__file__).parent / "fixtures" / "provenance"
SOURCE = FIXTURES / "derived.ttl"
CONFIG = FIXTURES / "derived.yml"

ONTOLOGY = URIRef("http://example.org/derived")
VERSION = URIRef("http://example.org/derived/2.1.0")
UPSTREAM = URIRef("http://example.org/upstream")
EX = "http://example.org/derived#"
HAS_PART = URIRef(EX + "hasPart")
ROOM = URIRef(EX + "Room")

LOSSLESS = ["full", "no_header_section", "header_late"]


def _order(source: Path, config: Path, outdir: Path, *profiles: str) -> Result:
    """Run the order command through Click's test runner."""
    args = [arg for p in profiles for arg in ("-p", p)]
    return CliRunner().invoke(cli, ["order", str(source), str(config), "-o", str(outdir), *args])


def _written(outdir: Path, source: Path, profile: str) -> Path:
    return outdir / f"{source.stem}-{profile}.ttl"


def _parse(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def _subject_order(text: str) -> list[str]:
    """The top-level subjects of a file ``order`` wrote, in the order it wrote them."""
    return [line for line in text.splitlines() if line and not line[0].isspace() and line[0] != "@"]


@pytest.fixture
def written(tmp_path: Path) -> dict[str, Path]:
    """Every profile of the fixture config, written once."""
    result = _order(SOURCE, CONFIG, tmp_path)
    assert result.exit_code == 0, result.output
    return {p: _written(tmp_path, SOURCE, p) for p in ("classes_ignore", "classes_warn", *LOSSLESS)}


# -- #90: a filtering profile's header --


class TestFilteringExtract:
    """A profile that drops subjects keeps the IRI and loses the version IRI."""

    @pytest.mark.parametrize("profile", ["classes_ignore", "classes_warn"])
    def test_keeps_the_ontology_iri_version_info_and_imports(
        self, written: dict[str, Path], profile: str
    ) -> None:
        graph = _parse(written[profile])
        assert (ONTOLOGY, RDF.type, OWL.Ontology) in graph
        assert (ONTOLOGY, OWL.versionInfo, Literal("2.1.0")) in graph
        assert (ONTOLOGY, OWL.imports, UPSTREAM) in graph
        assert (ONTOLOGY, RDFS.label, Literal("Derived identity fixture", lang="en")) in graph

    @pytest.mark.parametrize("profile", ["classes_ignore", "classes_warn"])
    def test_drops_the_version_iri(self, written: dict[str, Path], profile: str) -> None:
        graph = _parse(written[profile])
        assert not list(graph.objects(None, OWL.versionIRI))

    @pytest.mark.parametrize("profile", ["classes_ignore", "classes_warn"])
    def test_names_the_source_version(self, written: dict[str, Path], profile: str) -> None:
        graph = _parse(written[profile])
        assert list(graph.objects(ONTOLOGY, PROV.wasDerivedFrom)) == [VERSION]

    def test_declares_the_stamp_as_an_annotation_property(self, written: dict[str, Path]) -> None:
        graph = _parse(written["classes_ignore"])
        assert (PROV.wasDerivedFrom, RDF.type, OWL.AnnotationProperty) in graph

    def test_declaration_follows_the_header(self, written: dict[str, Path]) -> None:
        subjects = _subject_order(written["classes_ignore"].read_text(encoding="utf-8"))
        assert subjects[:2] == ["<http://example.org/derived>", "prov:wasDerivedFrom"]

    def test_binds_the_prov_prefix(self, written: dict[str, Path]) -> None:
        text = written["classes_ignore"].read_text(encoding="utf-8")
        assert "@prefix prov: <http://www.w3.org/ns/prov#> ." in text
        assert "prov:wasDerivedFrom <http://example.org/derived/2.1.0>" in text

    def test_is_otherwise_a_subset_of_the_source(self, written: dict[str, Path]) -> None:
        """The stamp is the only thing the extract asserts that the source did not."""
        source = _parse(SOURCE)
        graph = _parse(written["classes_ignore"])
        stamp = {
            (ONTOLOGY, PROV.wasDerivedFrom, VERSION),
            (PROV.wasDerivedFrom, RDF.type, OWL.AnnotationProperty),
        }
        extra = {t for t in graph if t not in source and not any(isinstance(n, BNode) for n in t)}
        assert extra == stamp

    def test_dropping_only_a_blank_node_is_an_extract(self, tmp_path: Path) -> None:
        """The trigger counts triples, so a lost axiom with no name still counts."""
        source = tmp_path / "disjoint.ttl"
        source.write_text(
            dedent(
                """
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix ex: <http://example.org/d#> .

                <http://example.org/d> a owl:Ontology .
                ex:A a owl:Class .
                ex:B a owl:Class .
                [] a owl:AllDisjointClasses ; owl:members ( ex:A ex:B ) .
                """
            ),
            encoding="utf-8",
        )
        result = _order(source, CONFIG, tmp_path / "out", "classes_ignore")
        assert result.exit_code == 0
        graph = _parse(_written(tmp_path / "out", source, "classes_ignore"))
        assert (None, RDF.type, OWL.AllDisjointClasses) not in graph
        ontology = URIRef("http://example.org/d")
        assert list(graph.objects(ontology, PROV.wasDerivedFrom)) == [ontology]

    def test_the_run_says_what_it_did(self, tmp_path: Path) -> None:
        result = _order(SOURCE, CONFIG, tmp_path, "classes_ignore")
        assert result.exit_code == 0
        assert (
            "  ◇ extract: 14 of 29 source triples written. Stamped <http://example.org/derived>:\n"
            "      owl:versionIRI <http://example.org/derived/2.1.0> removed\n"
            "      prov:wasDerivedFrom <http://example.org/derived/2.1.0> added\n"
        ) in result.stdout

    def test_ignore_still_reports_the_stamp_but_not_the_loss(self, tmp_path: Path) -> None:
        result = _order(SOURCE, CONFIG, tmp_path, "classes_ignore")
        assert "claimed by no section" not in result.output
        assert "◇ extract" in result.stdout

    def test_warn_reports_both(self, tmp_path: Path) -> None:
        result = _order(SOURCE, CONFIG, tmp_path, "classes_warn")
        assert result.exit_code == 0
        assert "claimed by no section" in result.stderr
        assert "◇ extract" in result.stdout


class TestLosslessProfiles:
    """A profile that loses nothing is the source reordered: nothing is stamped."""

    @pytest.mark.parametrize("profile", LOSSLESS)
    def test_output_is_the_source(self, written: dict[str, Path], profile: str) -> None:
        assert _parse(written[profile]).isomorphic(_parse(SOURCE))

    @pytest.mark.parametrize("profile", LOSSLESS)
    def test_says_nothing_about_an_extract(self, tmp_path: Path, profile: str) -> None:
        result = _order(SOURCE, CONFIG, tmp_path, profile)
        assert result.exit_code == 0
        assert "◇" not in result.output
        assert "prov" not in _written(tmp_path, SOURCE, profile).read_text(encoding="utf-8")


class TestDerivationTarget:
    """What the stamp names when the source has no version IRI, or several headers."""

    def _source(self, tmp_path: Path, body: str) -> Path:
        path = tmp_path / "src.ttl"
        path.write_text(
            dedent(
                """
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix ex: <http://example.org/s#> .
                """
            )
            + dedent(body),
            encoding="utf-8",
        )
        return path

    def test_falls_back_to_the_ontology_iri(self, tmp_path: Path) -> None:
        source = self._source(
            tmp_path,
            """
            <http://example.org/s> a owl:Ontology ; owl:versionInfo "1" .
            ex:A a owl:Class .
            ex:p a owl:ObjectProperty .
            """,
        )
        result = _order(source, CONFIG, tmp_path / "out", "classes_ignore")
        assert result.exit_code == 0
        graph = _parse(_written(tmp_path / "out", source, "classes_ignore"))
        ontology = URIRef("http://example.org/s")
        assert list(graph.objects(ontology, PROV.wasDerivedFrom)) == [ontology]
        assert (
            "      prov:wasDerivedFrom <http://example.org/s> added: the source has no "
            "owl:versionIRI, so it names the ontology's own IRI\n"
        ) in result.stdout
        assert "removed" not in result.stdout

    def test_each_of_several_headers_names_its_own_version(self, tmp_path: Path) -> None:
        source = self._source(
            tmp_path,
            """
            <http://example.org/a> a owl:Ontology ; owl:versionIRI <http://example.org/a/1> .
            <http://example.org/b> a owl:Ontology ; owl:versionIRI <http://example.org/b/7> .
            ex:A a owl:Class .
            ex:p a owl:ObjectProperty .
            """,
        )
        result = _order(source, CONFIG, tmp_path / "out", "classes_ignore")
        assert result.exit_code == 0
        graph = _parse(_written(tmp_path / "out", source, "classes_ignore"))
        for name, version in (("a", "a/1"), ("b", "b/7")):
            ontology = URIRef(f"http://example.org/{name}")
            assert (ontology, RDF.type, OWL.Ontology) in graph
            assert list(graph.objects(ontology, PROV.wasDerivedFrom)) == [
                URIRef(f"http://example.org/{version}")
            ]
        assert not list(graph.objects(None, OWL.versionIRI))
        assert "Stamped 2 ontology headers:" in result.stdout

    def test_a_source_with_no_header_is_not_stamped(self, tmp_path: Path) -> None:
        source = self._source(
            tmp_path,
            """
            ex:A a owl:Class .
            ex:p a owl:ObjectProperty .
            """,
        )
        result = _order(source, CONFIG, tmp_path / "out", "classes_ignore")
        assert result.exit_code == 0
        graph = _parse(_written(tmp_path / "out", source, "classes_ignore"))
        assert not list(graph.objects(None, PROV.wasDerivedFrom))
        assert (PROV.wasDerivedFrom, None, None) not in graph
        assert (
            "  ◇ extract: 1 of 2 source triples written. "
            "No owl:Ontology in the source: nothing stamped.\n"
        ) in result.stdout

    def test_an_anonymous_header_with_no_version_names_nothing(self, tmp_path: Path) -> None:
        source = self._source(
            tmp_path,
            """
            [] a owl:Ontology ; owl:versionInfo "1" .
            ex:A a owl:Class .
            ex:p a owl:ObjectProperty .
            """,
        )
        result = _order(source, CONFIG, tmp_path / "out", "classes_ignore")
        assert result.exit_code == 0
        graph = _parse(_written(tmp_path / "out", source, "classes_ignore"))
        assert not list(graph.objects(None, PROV.wasDerivedFrom))
        assert "Stamped an anonymous ontology:" in result.stdout
        assert "nothing names the source: not stamped" in result.stdout


class TestTheStampsOwnProperty:
    """``prov:wasDerivedFrom``'s own description travels with the header (#367's panel)."""

    def test_a_rerun_through_the_same_profile_is_a_fixed_point(self, tmp_path: Path) -> None:
        """No section claims the stamp's declaration, so this re-stamped before."""
        assert _order(SOURCE, CONFIG, tmp_path / "once", "classes_ignore").exit_code == 0
        once = _written(tmp_path / "once", SOURCE, "classes_ignore")
        result = _order(once, CONFIG, tmp_path / "twice", "classes_ignore")
        assert result.exit_code == 0
        assert "◇" not in result.output
        twice = _written(tmp_path / "twice", once, "classes_ignore")
        assert twice.read_bytes() == once.read_bytes()

    def test_a_source_typing_it_otherwise_keeps_that_type(self, tmp_path: Path) -> None:
        """PROV-O declares it an object property: typing it both ways leaves OWL 2 DL."""
        path = tmp_path / "src.ttl"
        path.write_text(
            dedent(
                """
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix prov: <http://www.w3.org/ns/prov#> .
                @prefix ex: <http://example.org/s#> .
                <http://example.org/s> a owl:Ontology ; owl:versionIRI <http://example.org/s/1> .
                prov:wasDerivedFrom a owl:ObjectProperty .
                ex:A a owl:Class .
                ex:p a owl:ObjectProperty .
                """
            ),
            encoding="utf-8",
        )
        result = _order(path, CONFIG, tmp_path / "out", "classes_ignore")
        assert result.exit_code == 0
        written = _written(tmp_path / "out", path, "classes_ignore")
        graph = _parse(written)
        assert set(graph.objects(PROV.wasDerivedFrom, RDF.type)) == {OWL.ObjectProperty}
        assert list(graph.objects(URIRef("http://example.org/s"), PROV.wasDerivedFrom)) == [
            URIRef("http://example.org/s/1")
        ]
        subjects = _subject_order(written.read_text(encoding="utf-8"))
        assert subjects[:2] == ["<http://example.org/s>", "prov:wasDerivedFrom"]

    def test_a_target_already_named_is_not_reported_as_added(self, tmp_path: Path) -> None:
        path = tmp_path / "src.ttl"
        path.write_text(
            dedent(
                """
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix prov: <http://www.w3.org/ns/prov#> .
                @prefix ex: <http://example.org/s#> .
                <http://example.org/s> a owl:Ontology ;
                    prov:wasDerivedFrom <http://example.org/s> .
                ex:A a owl:Class .
                ex:p a owl:ObjectProperty .
                """
            ),
            encoding="utf-8",
        )
        result = _order(path, CONFIG, tmp_path / "out", "classes_ignore")
        assert result.exit_code == 0
        assert (
            "      prov:wasDerivedFrom <http://example.org/s> already present: the source has no "
            "owl:versionIRI, so it names the ontology's own IRI\n"
        ) in result.stdout
        assert " added" not in result.stdout


# -- #90: the header is not a section's to lose --


class TestHeaderWithoutASection:
    def test_leads_the_file_without_a_header_section(self, written: dict[str, Path]) -> None:
        subjects = _subject_order(written["no_header_section"].read_text(encoding="utf-8"))
        assert subjects[0] == "<http://example.org/derived>"

    def test_a_later_header_section_still_decides_its_place(self, written: dict[str, Path]) -> None:
        subjects = _subject_order(written["header_late"].read_text(encoding="utf-8"))
        assert subjects.index("<http://example.org/derived>") == 3
        assert subjects[:3] == ["ex:Building", "ex:Floor", "ex:Room"]

    def test_header_false_omits_it_and_says_so(self, tmp_path: Path) -> None:
        result = _order(SOURCE, CONFIG, tmp_path, "omit_header")
        assert result.exit_code == 0
        graph = _parse(_written(tmp_path, SOURCE, "omit_header"))
        assert (None, RDF.type, OWL.Ontology) not in graph
        assert (None, PROV.wasDerivedFrom, None) not in graph
        assert "claimed by no section" not in result.output
        assert (
            "  ◇ extract: 24 of 29 source triples written. "
            "The profile omits the header (header: false): nothing stamped.\n"
        ) in result.stdout

    def _config(self, tmp_path: Path, text: str) -> Path:
        path = tmp_path / "cfg.yml"
        path.write_text(dedent(text), encoding="utf-8")
        return path

    def test_header_false_inherits_from_defaults(self, tmp_path: Path) -> None:
        config = self._config(
            tmp_path,
            """
            defaults:
              header: false
            profiles:
              p:
                sections:
                  - classes: {}
            """,
        )
        result = _order(SOURCE, config, tmp_path / "out", "p")
        assert result.exit_code == 0
        assert (None, RDF.type, OWL.Ontology) not in _parse(_written(tmp_path / "out", SOURCE, "p"))

    def test_a_header_section_outranks_a_default_of_false(self, tmp_path: Path) -> None:
        config = self._config(
            tmp_path,
            """
            defaults:
              header: false
            profiles:
              p:
                sections:
                  - header: {}
                  - classes: {}
            """,
        )
        result = _order(SOURCE, config, tmp_path / "out", "p")
        assert result.exit_code == 0
        assert (ONTOLOGY, RDF.type, OWL.Ontology) in _parse(_written(tmp_path / "out", SOURCE, "p"))

    @pytest.mark.parametrize(
        ("profile", "message"),
        [
            (
                "header: false\n    sections:\n      - header: {}",
                "sets 'header: false' but also has a 'header' section",
            ),
            ("header: omit\n    sections:\n      - classes: {}", "Unknown 'header' setting 'omit'"),
        ],
        ids=["contradiction", "not-a-boolean"],
    )
    def test_refused_before_anything_is_written(
        self, tmp_path: Path, profile: str, message: str
    ) -> None:
        config = self._config(
            tmp_path,
            f"profiles:\n  good:\n    sections:\n      - classes: {{}}\n  bad:\n    {profile}\n",
        )
        result = _order(SOURCE, config, tmp_path / "out", "good", "bad")
        assert result.exit_code == 2
        assert message in result.output
        assert not (tmp_path / "out").exists()


# -- #280: anonymous class expressions are not claimed on their own --


class TestOwnedBlankNodes:
    @pytest.mark.parametrize("profile", ["classes_ignore", "classes_then_individuals"])
    def test_no_detached_stub(self, tmp_path: Path, profile: str) -> None:
        result = _order(SOURCE, CONFIG, tmp_path, profile)
        assert result.exit_code == 0
        text = _written(tmp_path, SOURCE, profile).read_text(encoding="utf-8")
        assert not re.search(r"^_:", text, re.MULTILINE), text
        assert "owl:unionOf" not in text
        graph = _parse(_written(tmp_path, SOURCE, profile))
        assert (None, OWL.unionOf, None) not in graph
        assert (None, RDF.first, None) not in graph

    def test_the_union_is_inlined_when_its_property_survives(
        self, written: dict[str, Path]
    ) -> None:
        graph = _parse(written["full"])
        [union] = graph.objects(HAS_PART, RDFS.range)
        assert isinstance(union, BNode)
        assert (union, RDF.type, OWL.Class) in graph
        assert not re.search(r"^_:", written["full"].read_text(encoding="utf-8"), re.MULTILINE)

    def test_the_restriction_still_survives_whole(self, written: dict[str, Path]) -> None:
        graph = _parse(written["classes_ignore"])
        [restriction] = graph.objects(URIRef(EX + "Building"), RDFS.subClassOf)
        assert (restriction, OWL.onProperty, HAS_PART) in graph
        assert (restriction, OWL.someValuesFrom, ROOM) in graph

    def test_warn_counts_the_dropped_expression_as_anonymous(self, tmp_path: Path) -> None:
        result = _order(SOURCE, CONFIG, tmp_path, "classes_warn")
        assert "+ 3 anonymous nodes reachable from nothing claimed" in result.stderr

    def test_a_root_blank_node_is_still_claimed(self, tmp_path: Path) -> None:
        """`owl:AllDisjointClasses` is an axiom nothing references: only a selector reaches it."""
        source = tmp_path / "disjoint.ttl"
        source.write_text(
            dedent(
                """
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix ex: <http://example.org/d#> .

                <http://example.org/d> a owl:Ontology .
                ex:A a owl:Class .
                ex:B a owl:Class .
                [] a owl:AllDisjointClasses ; owl:members ( ex:A ex:B ) .
                """
            ),
            encoding="utf-8",
        )
        result = _order(source, CONFIG, tmp_path / "out", "full")
        assert result.exit_code == 0
        assert "◇" not in result.output
        assert _parse(_written(tmp_path / "out", source, "full")).isomorphic(_parse(source))


# -- #280 through the other callers of select_subjects --


class TestOtherSelectorCallers:
    DEFAULT_ORDER = Path(__file__).parent / "fixtures" / "default_order" / "default_order.ttl"
    UML_CONTEXTS = Path(__file__).parent.parent / "examples" / "uml" / "uml_contexts.yml"

    def test_uml_draws_no_anonymous_class(self, tmp_path: Path) -> None:
        """`uml`'s `selector: classes` drew the union behind `ex:partOf` as a class box."""
        result = CliRunner().invoke(
            cli,
            [
                "uml",
                str(self.DEFAULT_ORDER),
                "-C",
                str(self.UML_CONTEXTS),
                "-c",
                "full",
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output
        puml = (tmp_path / "default_order-full.puml").read_text(encoding="utf-8")
        assert not re.search(r"^class <n[0-9a-f]+>", puml, re.MULTILINE), puml
        assert "class ex.Vehicle" in puml

    def test_a_lossless_profile_keeps_root_blank_nodes(self, tmp_path: Path) -> None:
        """`owl:AllDisjointClasses` and `owl:AllDifferent` reach the output only by a selector."""
        result = _order(
            self.DEFAULT_ORDER,
            Path(__file__).parent.parent / "examples" / "order" / "ordering.yml",
            tmp_path,
            "alpha",
        )
        assert result.exit_code == 0
        graph = _parse(_written(tmp_path, self.DEFAULT_ORDER, "alpha"))
        assert graph.isomorphic(_parse(self.DEFAULT_ORDER))
        assert (None, RDF.type, OWL.AllDisjointClasses) in graph
        assert (None, RDF.type, OWL.AllDifferent) in graph
