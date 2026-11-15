"""Tests for ``puml2rdf --merge``: the diagram replaces only what it can express (#417).

A diagram can say that a term is an ``owl:Class``, an ``owl:ObjectProperty`` or an
``owl:DatatypeProperty``, give a class named superclasses, and give a property a named domain and
range. Every case here is a target that says something more, or something else, about the terms
the base diagram draws. Each is run through ``OntologyMerger.merge_graphs`` and through the
documented round trip, ``puml2rdf design.puml --merge X -o X``, and the result is compared with a
hand-written expectation by isomorphism, never by "contains".
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner
from rdflib import BNode, Graph, URIRef
from rdflib.compare import graph_diff, isomorphic, to_isomorphic

from rdf_construct.cli import cli
from rdf_construct.core.blank_nodes import blank_node_components
from rdf_construct.puml2rdf import (
    MergeConflict,
    OntologyMerger,
    PlantUMLParser,
    PumlToRdfConverter,
    merge_with_existing,
)

ROOT = Path(__file__).parent.parent
GUIDE = ROOT / "docs" / "user_guides" / "PUML2RDF_GUIDE.md"

PREFIXES = dedent(
    """\
    @prefix ex: <http://example.org/ontology/ex#> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
    """
)

DIAGRAM = dedent(
    """\
    @startuml
    package "http://example.org/ontology/ex#" as ex {
      class Thing
      class Building {
        builtOn : date
      }
      class Wall
    }
    ex.Thing <|-- ex.Building
    ex.Building --> ex.Wall : hasPart
    @enduml
    """
)

# What the converter writes for DIAGRAM, one statement per term, so a case can swap one out
HEADER = "<http://example.org/ontology> a owl:Ontology ."
THING = 'ex:Thing a owl:Class ; rdfs:label "thing"@en .'
WALL = 'ex:Wall a owl:Class ; rdfs:label "wall"@en .'
BUILDING = 'ex:Building a owl:Class ; rdfs:label "building"@en ; rdfs:subClassOf ex:Thing .'
BUILT_ON = (
    'ex:builtOn a owl:DatatypeProperty ; rdfs:label "built on"@en ;'
    " rdfs:domain ex:Building ; rdfs:range xsd:date ."
)
HAS_PART = (
    'ex:hasPart a owl:ObjectProperty ; rdfs:label "hasPart"@en ;'
    " rdfs:domain ex:Building ; rdfs:range ex:Wall ."
)
DIAGRAM_STATEMENTS = [HEADER, THING, WALL, BUILDING, BUILT_ON, HAS_PART]


def turtle(*statements: str) -> str:
    return PREFIXES + "\n" + "\n".join(statements) + "\n"


def graph(text: str) -> Graph:
    g = Graph(bind_namespaces="core")
    g.parse(data=text, format="turtle")
    return g


def convert(diagram: str = DIAGRAM) -> Graph:
    result = PlantUMLParser().parse(diagram)
    assert result.success, result.errors
    return PumlToRdfConverter().convert(result.model).graph


def assert_same(actual: Graph, expected: Graph) -> None:
    if isomorphic(actual, expected):
        return
    _, only_actual, only_expected = graph_diff(to_isomorphic(actual), to_isomorphic(expected))
    raise AssertionError(
        "graphs differ\n--- only in the merge ---\n"
        + only_actual.serialize(format="nt")
        + "--- only in the expectation ---\n"
        + only_expected.serialize(format="nt")
    )


def unreferenced(g: Graph) -> int:
    """Blank-node components no named subject refers to: an orphaned restriction is one."""
    return sum(
        not any(not isinstance(s, BNode) and isinstance(o, BNode) for s, _, o in component)
        for component in blank_node_components(g)
    )


RESTRICTION = "[ a owl:Restriction ; owl:onProperty ex:hasPart ; owl:someValuesFrom ex:Wall ]"

CHARACTERISTICS = [
    "owl:FunctionalProperty",
    "owl:InverseFunctionalProperty",
    "owl:SymmetricProperty",
    "owl:AsymmetricProperty",
    "owl:TransitiveProperty",
    "owl:ReflexiveProperty",
    "owl:IrreflexiveProperty",
    "owl:DeprecatedProperty",
]


def case(
    target: list[str],
    expected: list[str],
    conflicts: tuple[str, ...] = (),
    diagram: str = DIAGRAM,
) -> tuple[str, str, tuple[str, ...], str]:
    return turtle(*target), turtle(*expected), conflicts, diagram


EDIT_SUPERCLASS = DIAGRAM.replace("  class Wall\n", "  class Wall\n  class Structure\n").replace(
    "ex.Thing <|-- ex.Building", "ex.Thing <|-- ex.Structure\nex.Structure <|-- ex.Building"
)
EDIT_REMOVED = DIAGRAM.replace("  class Wall\n", "").replace(
    "ex.Building --> ex.Wall : hasPart\n", ""
)
STRUCTURE = 'ex:Structure a owl:Class ; rdfs:label "structure"@en ; rdfs:subClassOf ex:Thing .'

# name -> (target, expected merge, conflict codes, diagram)
CASES = {
    # The reproducer from #417, with the rdfs prefix its snippet leaves out
    "r417": case(
        [
            "ex:hasPart a owl:ObjectProperty, owl:TransitiveProperty .",
            f"ex:Building a owl:Class ; rdfs:subClassOf {RESTRICTION} .",
        ],
        [
            HEADER,
            THING,
            WALL,
            BUILT_ON,
            HAS_PART,
            "ex:hasPart a owl:TransitiveProperty .",
            BUILDING,
            f"ex:Building rdfs:subClassOf {RESTRICTION} .",
        ],
    ),
    **{
        f"characteristic-{c.split(':')[1]}": case(
            [f"ex:hasPart a owl:ObjectProperty, {c} ."],
            [*DIAGRAM_STATEMENTS, f"ex:hasPart a {c} ."],
        )
        for c in CHARACTERISTICS
    },
    "characteristic-only": case(
        ["ex:hasPart a owl:TransitiveProperty ."],
        [*DIAGRAM_STATEMENTS, "ex:hasPart a owl:TransitiveProperty ."],
    ),
    "functional-datatype-property": case(
        ["ex:builtOn a owl:DatatypeProperty, owl:FunctionalProperty ."],
        [*DIAGRAM_STATEMENTS, "ex:builtOn a owl:FunctionalProperty ."],
    ),
    "punned-individual": case(
        ["ex:Building a owl:Class, owl:NamedIndividual ."],
        [*DIAGRAM_STATEMENTS, "ex:Building a owl:NamedIndividual ."],
    ),
    "rdfs-class": case(
        ["ex:Building a rdfs:Class ."],
        [*DIAGRAM_STATEMENTS, "ex:Building a rdfs:Class ."],
    ),
    "deprecated-class": case(
        ["ex:Building a owl:Class, owl:DeprecatedClass ."],
        [*DIAGRAM_STATEMENTS, "ex:Building a owl:DeprecatedClass ."],
    ),
    # A real contradiction: the target's kind is kept and the diagram's is reported
    "annotation-property": case(
        ["ex:hasPart a owl:AnnotationProperty ."],
        [
            HEADER,
            THING,
            WALL,
            BUILDING,
            BUILT_ON,
            'ex:hasPart a owl:AnnotationProperty ; rdfs:label "hasPart"@en ;'
            " rdfs:domain ex:Building ; rdfs:range ex:Wall .",
        ],
        ("kind-clash",),
    ),
    "datatype-property": case(
        ["ex:hasPart a owl:DatatypeProperty ."],
        [
            HEADER,
            THING,
            WALL,
            BUILDING,
            BUILT_ON,
            'ex:hasPart a owl:DatatypeProperty ; rdfs:label "hasPart"@en ;'
            " rdfs:domain ex:Building ; rdfs:range ex:Wall .",
        ],
        ("kind-clash",),
    ),
    "restriction": case(
        [f"ex:Building a owl:Class ; rdfs:subClassOf {RESTRICTION} ."],
        [*DIAGRAM_STATEMENTS, f"ex:Building rdfs:subClassOf {RESTRICTION} ."],
    ),
    "nested-restriction": case(
        [
            "ex:Building rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:hasPart ;"
            " owl:someValuesFrom [ a owl:Restriction ; owl:onProperty ex:hasPart ;"
            " owl:allValuesFrom ex:Wall ] ] ."
        ],
        [
            *DIAGRAM_STATEMENTS,
            "ex:Building rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:hasPart ;"
            " owl:someValuesFrom [ a owl:Restriction ; owl:onProperty ex:hasPart ;"
            " owl:allValuesFrom ex:Wall ] ] .",
        ],
    ),
    "union-superclass": case(
        ["ex:Building rdfs:subClassOf [ a owl:Class ; owl:unionOf ( ex:Thing ex:Wall ) ] ."],
        [
            *DIAGRAM_STATEMENTS,
            "ex:Building rdfs:subClassOf [ a owl:Class ; owl:unionOf ( ex:Thing ex:Wall ) ] .",
        ],
    ),
    "intersection-superclass": case(
        ["ex:Building rdfs:subClassOf [ a owl:Class ; owl:intersectionOf ( ex:Thing ex:Wall ) ] ."],
        [
            *DIAGRAM_STATEMENTS,
            "ex:Building rdfs:subClassOf"
            " [ a owl:Class ; owl:intersectionOf ( ex:Thing ex:Wall ) ] .",
        ],
    ),
    # The diagram does not draw ex:Structure, so its silence is not a deletion
    "named-superclass-not-drawn": case(
        ["ex:Building rdfs:subClassOf ex:Structure .", "ex:Structure a owl:Class ."],
        [
            *DIAGRAM_STATEMENTS,
            "ex:Building rdfs:subClassOf ex:Structure .",
            "ex:Structure a owl:Class .",
        ],
    ),
    "shared-restriction": case(
        [
            "_:r a owl:Restriction ; owl:onProperty ex:hasPart ; owl:someValuesFrom ex:Wall .",
            "ex:Building rdfs:subClassOf _:r .",
            "ex:Room rdfs:subClassOf _:r .",
        ],
        [
            *DIAGRAM_STATEMENTS,
            "_:r a owl:Restriction ; owl:onProperty ex:hasPart ; owl:someValuesFrom ex:Wall .",
            "ex:Building rdfs:subClassOf _:r .",
            "ex:Room rdfs:subClassOf _:r .",
        ],
    ),
    # An attribute's type is a datatype the diagram draws, so it replaces like with like
    "datatype-range": case(
        ["ex:builtOn a owl:DatatypeProperty ; rdfs:range xsd:dateTime ."],
        DIAGRAM_STATEMENTS,
        ("replaced",),
    ),
    "union-range": case(
        [
            "ex:hasPart a owl:ObjectProperty ;"
            " rdfs:range [ a owl:Class ; owl:unionOf ( ex:Wall ex:Floor ) ] ."
        ],
        [
            *DIAGRAM_STATEMENTS,
            "ex:hasPart rdfs:range [ a owl:Class ; owl:unionOf ( ex:Wall ex:Floor ) ] .",
        ],
    ),
    "two-domains": case(
        ["ex:hasPart a owl:ObjectProperty ; rdfs:domain ex:Building, ex:Room ."],
        [*DIAGRAM_STATEMENTS, "ex:hasPart rdfs:domain ex:Room ."],
    ),
    "superproperty": case(
        ["ex:hasPart rdfs:subPropertyOf ex:relatedTo ."],
        [*DIAGRAM_STATEMENTS, "ex:hasPart rdfs:subPropertyOf ex:relatedTo ."],
    ),
    "inverse-superproperty": case(
        ["ex:hasPart rdfs:subPropertyOf [ owl:inverseOf ex:partOf ] ."],
        [*DIAGRAM_STATEMENTS, "ex:hasPart rdfs:subPropertyOf [ owl:inverseOf ex:partOf ] ."],
    ),
    # The target is its own ontology: the diagram's derived header is not added
    "own-ontology-header": case(
        [
            "<http://example.org/onto/building> a owl:Ontology ;"
            " owl:versionIRI <http://example.org/onto/building/1.0> ;"
            " owl:imports <http://example.org/onto/core> .",
        ],
        [
            "<http://example.org/onto/building> a owl:Ontology ;"
            " owl:versionIRI <http://example.org/onto/building/1.0> ;"
            " owl:imports <http://example.org/onto/core> .",
            THING,
            WALL,
            BUILDING,
            BUILT_ON,
            HAS_PART,
        ],
    ),
    # The diagram moved Building from Thing, which it draws, to Structure
    "superclass-edited": case(
        ["ex:Building a owl:Class ; rdfs:subClassOf ex:Thing ."],
        [
            HEADER,
            THING,
            WALL,
            STRUCTURE,
            BUILT_ON,
            HAS_PART,
            'ex:Building a owl:Class ; rdfs:label "building"@en ; rdfs:subClassOf ex:Structure .',
        ],
        ("replaced",),
        EDIT_SUPERCLASS,
    ),
    # A term deleted from the diagram stays in the ontology
    "term-removed": case(
        [
            "ex:Wall a owl:Class .",
            "ex:hasPart a owl:ObjectProperty ; rdfs:domain ex:Building ; rdfs:range ex:Wall .",
        ],
        [
            HEADER,
            THING,
            BUILDING,
            BUILT_ON,
            "ex:Wall a owl:Class .",
            "ex:hasPart a owl:ObjectProperty ; rdfs:domain ex:Building ; rdfs:range ex:Wall .",
        ],
        diagram=EDIT_REMOVED,
    ),
}


class TestMergeGraphs:
    """The library: ``OntologyMerger.merge_graphs`` on each case."""

    @pytest.mark.parametrize("name", CASES)
    def test_case(self, name: str) -> None:
        target, expected, codes, diagram = CASES[name]
        existing = graph(target)

        result = OntologyMerger().merge_graphs(convert(diagram), existing)

        assert_same(result.graph, graph(expected))
        assert [c.code for c in result.conflicts] == list(codes)
        assert unreferenced(result.graph) == unreferenced(existing) == 0

    @pytest.mark.parametrize("name", CASES)
    def test_counts_are_what_is_written(self, name: str) -> None:
        target, _, _, diagram = CASES[name]
        existing = graph(target)

        result = OntologyMerger().merge_graphs(convert(diagram), existing)

        merged, before = set(result.graph), set(existing)
        assert result.added_count == len(merged - before)
        assert result.preserved_count == len(merged & before)
        assert result.updated_count == len(before - merged)

    def test_conflicts_name_both_values(self) -> None:
        target, _, _, diagram = CASES["superclass-edited"]

        (conflict,) = OntologyMerger().merge_graphs(convert(diagram), graph(target)).conflicts

        ex = "http://example.org/ontology/ex#"
        assert isinstance(conflict, MergeConflict)
        assert conflict.subject == URIRef(ex + "Building")
        assert conflict.existing == (URIRef(ex + "Thing"),)
        assert conflict.new == (URIRef(ex + "Structure"),)
        assert str(conflict) == (
            "ex:Building rdfs:subClassOf ex:Thing was replaced by the diagram's ex:Structure."
        )

    def test_kind_clash_message(self) -> None:
        target, _, _, _ = CASES["datatype-property"]

        (conflict,) = OntologyMerger().merge_graphs(convert(), graph(target)).conflicts

        assert str(conflict) == (
            "ex:hasPart is owl:DatatypeProperty here; the diagram's owl:ObjectProperty was not "
            "written."
        )

    def test_diagram_wins_a_kind_clash_when_asked(self) -> None:
        target, _, _, _ = CASES["datatype-property"]

        result = OntologyMerger(preserve_existing=False).merge_graphs(convert(), graph(target))

        assert_same(result.graph, graph(turtle(*DIAGRAM_STATEMENTS)))
        assert [c.code for c in result.conflicts] == ["kind-clash"]
        assert str(result.conflicts[0]) == (
            "ex:hasPart was owl:DatatypeProperty; the diagram's owl:ObjectProperty replaced it."
        )

    def test_diagrams_own_superclasses_are_not_a_conflict(self) -> None:
        """Multiple inheritance in the diagram, stated in the target too, reports nothing.

        Before #417 every IES class with two superclasses was reported as a conflict between
        the diagram's own two values.
        """
        diagram = DIAGRAM.replace(
            "ex.Thing <|-- ex.Building", "ex.Thing <|-- ex.Building\nex.Wall <|-- ex.Building"
        )
        target = turtle("ex:Building rdfs:subClassOf ex:Thing, ex:Wall .")

        result = OntologyMerger().merge_graphs(convert(diagram), graph(target))

        assert result.conflicts == []
        assert result.updated_count == 0

    @pytest.mark.parametrize(
        ("suffix", "rdf_format"), [(".rdf", "xml"), (".jsonld", "json-ld"), (".nt", "nt")]
    )
    def test_merge_reads_the_target_in_its_own_format(
        self, tmp_path: Path, suffix: str, rdf_format: str
    ) -> None:
        target, expected, _, _ = CASES["r417"]
        path = tmp_path / f"target{suffix}"
        graph(target).serialize(path, format=rdf_format)

        result = merge_with_existing(convert(), path)

        assert_same(result.graph, graph(expected))

    def test_prefixes_are_the_targets_own(self) -> None:
        """A prefix rdflib's own table also knows is written as the target binds it (#354)."""
        target = (
            PREFIXES
            + "@prefix sdo: <https://schema.org/> .\nex:Building rdfs:seeAlso sdo:Place .\n"
        )

        result = OntologyMerger().merge_graphs(convert(), graph(target))

        bound = dict(result.graph.namespace_manager.namespaces())
        assert str(bound["sdo"]) == "https://schema.org/"
        assert "schema" not in bound
        assert "@prefix sdo: <https://schema.org/> ." in result.graph.serialize(format="turtle")


def run(tmp_path: Path, args: list[str]) -> tuple[int, str]:
    result = CliRunner().invoke(cli, args)
    assert result.exception is None or isinstance(result.exception, SystemExit), result.output
    return result.exit_code, result.output


class TestRoundTrip:
    """The CLI: ``puml2rdf design.puml --merge X -o X``, the round trip the docs show."""

    @pytest.mark.parametrize("name", CASES)
    def test_case(self, tmp_path: Path, name: str) -> None:
        target, expected, codes, diagram = CASES[name]
        puml = tmp_path / "design.puml"
        puml.write_text(diagram)
        ontology = tmp_path / "ontology.ttl"
        ontology.write_text(target)

        code, output = run(
            tmp_path, ["puml2rdf", str(puml), "--merge", str(ontology), "-o", str(ontology)]
        )

        assert code == (1 if codes else 0), output
        merged = Graph(bind_namespaces="core").parse(ontology)
        assert_same(merged, graph(expected))
        assert output.count("⚠ ") == len(codes)

    def test_twice_keeps_everything_the_diagram_cannot_express(self, tmp_path: Path) -> None:
        """Every characteristic and blank-node axiom survives two round trips, unchanged."""
        statements = [
            f"ex:hasPart a owl:ObjectProperty, {', '.join(CHARACTERISTICS)} ;"
            " rdfs:subPropertyOf [ owl:inverseOf ex:partOf ] ;"
            " rdfs:range [ a owl:Class ; owl:unionOf ( ex:Wall ex:Floor ) ] .",
            "ex:Building a owl:Class, owl:NamedIndividual ; rdfs:subClassOf ex:Structure,"
            f" {RESTRICTION}, [ a owl:Class ; owl:intersectionOf ( ex:Thing ex:Wall ) ] .",
            "ex:Thing a rdfs:Class .",
            "ex:builtOn a owl:FunctionalProperty .",
        ]
        puml = tmp_path / "design.puml"
        puml.write_text(DIAGRAM)
        ontology = tmp_path / "ontology.ttl"
        ontology.write_text(turtle(*statements))
        argv = ["puml2rdf", str(puml), "--merge", str(ontology), "-o", str(ontology)]
        expected = graph(turtle(*DIAGRAM_STATEMENTS, *statements))

        first, _ = run(tmp_path, argv)
        after_first = Graph(bind_namespaces="core").parse(ontology)
        second, output = run(tmp_path, argv)
        after_second = Graph(bind_namespaces="core").parse(ontology)

        assert (first, second) == (0, 0)
        assert_same(after_first, expected)
        assert_same(after_second, expected)
        assert "Added: 0, Preserved: " in output
        assert "Replaced: 0" in output

    def test_every_conflict_is_printed(self, tmp_path: Path) -> None:
        names = [f"C{i}" for i in range(7)]
        diagram = "@startuml\n" + "".join(f"class {n}\n" for n in names) + "@enduml\n"
        puml = tmp_path / "design.puml"
        puml.write_text(diagram)
        ontology = tmp_path / "ontology.ttl"
        ontology.write_text(
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
            "@prefix ont: <http://example.org/ontology#> .\n"
            + "".join(f"ont:{n} a owl:ObjectProperty .\n" for n in names)
        )

        code, output = run(
            tmp_path, ["puml2rdf", str(puml), "--merge", str(ontology), "-o", str(ontology)]
        )

        assert code == 1
        for n in names:
            assert f"⚠ ont:{n} is owl:ObjectProperty here" in output
        assert "more" not in output

    def test_strict_writes_nothing_on_a_conflict(self, tmp_path: Path) -> None:
        target, _, _, _ = CASES["datatype-property"]
        puml = tmp_path / "design.puml"
        puml.write_text(DIAGRAM)
        ontology = tmp_path / "ontology.ttl"
        ontology.write_text(target)

        code, output = run(
            tmp_path,
            ["puml2rdf", str(puml), "--merge", str(ontology), "-o", str(ontology), "--strict"],
        )

        assert code == 1
        assert "Aborting due to --strict mode" in output
        assert ontology.read_text() == target

    @pytest.mark.parametrize(
        ("suffix", "rdf_format"), [(".rdf", "xml"), (".jsonld", "json-ld"), (".nt", "nt")]
    )
    def test_target_in_another_format(self, tmp_path: Path, suffix: str, rdf_format: str) -> None:
        """Read by its extension and written back with ``-f``; before #417 it was read as Turtle."""
        target, expected, _, _ = CASES["r417"]
        puml = tmp_path / "design.puml"
        puml.write_text(DIAGRAM)
        ontology = tmp_path / f"ontology{suffix}"
        graph(target).serialize(ontology, format=rdf_format)

        code, output = run(
            tmp_path,
            [
                "puml2rdf",
                str(puml),
                "--merge",
                str(ontology),
                "-o",
                str(ontology),
                "-f",
                rdf_format,
            ],
        )

        assert code == 0, output
        assert_same(Graph().parse(ontology, format=rdf_format), graph(expected))

    def test_unparseable_target_is_refused(self, tmp_path: Path) -> None:
        puml = tmp_path / "design.puml"
        puml.write_text(DIAGRAM)
        ontology = tmp_path / "ontology.rdf"
        ontology.write_text("this is not RDF/XML")
        out = tmp_path / "out.ttl"

        code, output = run(
            tmp_path, ["puml2rdf", str(puml), "--merge", str(ontology), "-o", str(out)]
        )

        assert code == 2
        assert f"Error: Could not parse {ontology} as xml:" in output
        assert not out.exists()


class TestGuide:
    """``PUML2RDF_GUIDE.md``'s merge section runs verbatim and shows what it prints."""

    def test_merge_section_is_the_real_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        guide = GUIDE.read_text(encoding="utf-8")
        section = guide[
            guide.index("## Merging with Existing Ontologies") : guide.index("## Validation")
        ]
        blocks = re.findall(r"```(\w+)\n(.*?)```", section, re.S)
        diagram = next(b for lang, b in blocks if lang == "plantuml")
        ontology, merged = (b for lang, b in blocks if lang == "turtle")
        command = next(b for lang, b in blocks if lang == "bash")
        shown = next(b for lang, b in blocks if lang == "text")
        argv = shlex.split(command)
        assert argv[:2] == ["rdf-construct", "puml2rdf"]

        monkeypatch.chdir(tmp_path)
        Path(argv[2]).write_text(diagram)
        Path(argv[argv.index("--merge") + 1]).write_text(ontology)
        result = CliRunner().invoke(cli, argv[1:])

        assert result.exit_code == 1, result.output
        assert result.output == shown
        written = Graph().parse(tmp_path / argv[argv.index("-o") + 1])
        assert_same(written, Graph().parse(data=merged, format="turtle"))
