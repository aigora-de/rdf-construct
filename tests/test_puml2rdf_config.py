"""Tests for puml2rdf's one datatype map and its -C config (#155, #152, #480).

Every test runs the CLI and reads back what it wrote, so a mapping that is parsed and not applied
— #152's failure — shows as a wrong IRI or range rather than passing.
"""

import re
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner, Result
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from rdf_construct.cli import cli
from rdf_construct.puml2rdf import (
    ConversionConfig,
    PlantUMLParser,
    PumlAttribute,
    PumlClass,
    PumlModel,
    PumlToRdfConverter,
    validate_puml,
)
from rdf_construct.puml2rdf.config import REMOVED_KEYS, _parse_config
from rdf_construct.puml2rdf.datatypes import BUILTIN_DATATYPES, DatatypeMap

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "puml2rdf"
GUIDE = Path(__file__).resolve().parent.parent / "docs" / "user_guides" / "PUML2RDF_GUIDE.md"
DEFAULT = Namespace("http://example.org/ontology#")
BLD = Namespace("http://example.org/building#")


def _run(
    tmp_path: Path, diagram: str, config: dict | str | None = None, *options: str
) -> tuple[Result, Graph | None]:
    """Run puml2rdf over *diagram*, with *config* as its -C file; return the result and output."""
    puml = tmp_path / "diagram.puml"
    puml.write_text(f"@startuml\n{diagram}\n@enduml\n", encoding="utf-8")
    output = tmp_path / "diagram.ttl"
    args = ["puml2rdf", str(puml), "-o", str(output), *options]
    if config is not None:
        path = tmp_path / "config.yml"
        text = config if isinstance(config, str) else yaml.safe_dump(config, sort_keys=False)
        path.write_text(text, encoding="utf-8")
        args += ["-C", str(path)]
    result = CliRunner().invoke(cli, args)
    if not output.exists():
        return result, None
    graph = Graph(bind_namespaces="none")
    graph.parse(output, format="turtle")
    return result, graph


def _range(graph: Graph, prop: URIRef) -> URIRef:
    """Return the one rdfs:range of *prop*."""
    ranges = list(graph.objects(prop, RDFS.range))
    assert len(ranges) == 1, ranges
    return ranges[0]  # type: ignore[return-value]


def _prefixes(graph: Graph) -> dict[str, str]:
    """Return the prefixes the written file declares for this diagram's namespaces."""
    core = {"owl", "rdf", "rdfs", "xsd", "xml"}
    return {
        p: str(n) for p, n in graph.namespaces() if p not in core and str(n).startswith("http://ex")
    }


# ==============================================================================
# One datatype map (#155)
# ==============================================================================


class TestBuiltInDatatypes:
    """Every built-in type name is reachable, whatever its case."""

    @pytest.mark.parametrize(
        ("written", "expected"),
        [
            ("gYearMonth", XSD.gYearMonth),
            ("hexBinary", XSD.hexBinary),
            ("anyURI", XSD.anyURI),
            ("gYear", XSD.gYear),
            ("GYEARMONTH", XSD.gYearMonth),
            ("HexBinary", XSD.hexBinary),
            ("String", XSD.string),
            ("INTEGER", XSD.integer),
            ("dateTime", XSD.dateTime),
        ],
    )
    def test_reachable(self, tmp_path: Path, written: str, expected: URIRef) -> None:
        result, graph = _run(tmp_path, f"class A {{\n  v : {written}\n}}", None, "--strict")

        assert result.exit_code == 0, result.output
        assert "Unknown datatype" not in result.output
        assert graph is not None
        assert _range(graph, DEFAULT.v) == expected

    def test_every_key_is_folded(self) -> None:
        """A key with a capital in it can never match a folded lookup: that was #155."""
        assert all(key == key.casefold() for key in BUILTIN_DATATYPES)


class TestOneMap:
    """The validator and the converter read one map, so they agree on every type."""

    NAMES = [*BUILTIN_DATATYPES, "Money", "Widget", "java:Date", "Thing"]

    @pytest.mark.parametrize("name", NAMES)
    def test_validator_warns_exactly_when_converter_falls_back(self, name: str) -> None:
        datatypes = DatatypeMap({"Money": "xsd:decimal", "string": "xsd:normalizedString"})
        model = PumlModel(
            classes=[PumlClass(name="A", attributes=[PumlAttribute(name="v", datatype=name)])]
        )
        warned = any(
            issue.code == "UNKNOWN_DATATYPE" for issue in validate_puml(model, datatypes).issues
        )
        graph = PumlToRdfConverter(ConversionConfig(datatypes=datatypes)).convert(model).graph
        written = _range(graph, DEFAULT.v)

        assert warned == (datatypes.resolve(name) is None)
        if not warned:
            assert written == datatypes.resolve(name)
        else:
            assert written == XSD.string

    def test_one_warning_per_unknown_type(self, tmp_path: Path) -> None:
        result, graph = _run(tmp_path, "class A {\n  cost : Widget\n  other : Gadget\n}")

        assert result.exit_code == 0, result.output
        assert result.output.count("Unknown datatype 'Widget'") == 1
        assert result.output.count("Unknown datatype 'Gadget'") == 1
        assert "Conversion warnings:" not in result.output
        assert graph is not None and _range(graph, DEFAULT.cost) == XSD.string


class TestCurieTypes:
    """An attribute typed as a CURIE keeps its whole type (#480)."""

    def test_xsd_curie_is_read_whole(self, tmp_path: Path) -> None:
        result, graph = _run(
            tmp_path, "class A {\n  q : xsd:gYearMonth\n  l : rdf:langString\n}", None, "--strict"
        )

        assert result.exit_code == 0, result.output
        assert graph is not None
        assert _range(graph, DEFAULT.q) == XSD.gYearMonth
        assert _range(graph, DEFAULT.l) == RDF.langString

    def test_curie_after_a_visibility_marker(self, tmp_path: Path) -> None:
        """The full attribute pattern reads the CURIE too, not only the fallback."""
        result, graph = _run(tmp_path, "class A {\n  + q : xsd:gYearMonth\n}", None, "--strict")

        assert result.exit_code == 0, result.output
        assert graph is not None and _range(graph, DEFAULT.q) == XSD.gYearMonth

    def test_curie_before_trailing_text(self, tmp_path: Path) -> None:
        """The fallback pattern, which reads a line the full one does not, keeps the CURIE too."""
        result, graph = _run(tmp_path, "class A {\n  q : xsd:gYearMonth [0..1]\n}")

        assert result.exit_code == 0, result.output
        assert graph is not None and _range(graph, DEFAULT.q) == XSD.gYearMonth

    def test_xsd_name_that_is_no_datatype_is_refused(self, tmp_path: Path) -> None:
        result, graph = _run(tmp_path, "class A {\n  q : xsd:Foo\n}")

        assert result.exit_code == 2, result.output
        assert "NOT_A_DATATYPE" in result.output
        assert graph is None

    def test_wrong_case_curie_names_the_datatype(self, tmp_path: Path) -> None:
        result, _ = _run(tmp_path, "class A {\n  q : xsd:gyearmonth\n}")

        assert result.exit_code == 2, result.output
        assert "Did you mean xsd:gYearMonth?" in result.output

    def test_unknown_prefix_warns(self, tmp_path: Path) -> None:
        result, graph = _run(tmp_path, "class A {\n  d : java:Date\n}")

        assert result.exit_code == 0, result.output
        assert "Unknown datatype 'java:Date'" in result.output
        assert graph is not None and _range(graph, DEFAULT.d) == XSD.string


# ==============================================================================
# datatype_mappings (#152)
# ==============================================================================


class TestDatatypeMappings:
    """A config's datatype_mappings go into the one map."""

    def test_mapping_is_applied_folded(self, tmp_path: Path) -> None:
        config = {"datatype_mappings": {"Money": "xsd:decimal"}}
        result, graph = _run(tmp_path, "class A {\n  a : Money\n  b : MONEY\n}", config, "--strict")

        assert result.exit_code == 0, result.output
        assert graph is not None
        assert _range(graph, DEFAULT.a) == XSD.decimal
        assert _range(graph, DEFAULT.b) == XSD.decimal

    def test_override_of_a_built_in_is_a_note(self, tmp_path: Path) -> None:
        config = {"datatype_mappings": {"string": "xsd:normalizedString"}}
        result, graph = _run(tmp_path, "class A {\n  s : String\n}", config, "--strict")

        assert result.exit_code == 0, result.output
        assert "Config notes:" in result.output
        assert "replaces the built-in type" in result.output
        assert graph is not None and _range(graph, DEFAULT.s) == XSD.normalizedString

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("<http://example.org/dt#money>", URIRef("http://example.org/dt#money")),
            ("http://example.org/dt#money", URIRef("http://example.org/dt#money")),
            ("rdf:langString", RDF.langString),
            ("rdfs:Literal", RDFS.Literal),
            ("owl:real", URIRef(f"{OWL}real")),
        ],
    )
    def test_accepted_values(self, tmp_path: Path, value: str, expected: URIRef) -> None:
        result, graph = _run(
            tmp_path, "class A {\n  a : Money\n}", {"datatype_mappings": {"Money": value}}
        )

        assert result.exit_code == 0, result.output
        assert graph is not None and _range(graph, DEFAULT.a) == expected

    @pytest.mark.parametrize(
        ("mappings", "says"),
        [
            ({"Money": "xsd:Foo"}, "is not a datatype"),
            ({"Money": "foo:Bar"}, "is not a datatype"),
            ({"Money": "decimal"}, "is not a datatype"),
            ({"Money": "<http://www.w3.org/2001/XMLSchema#Foo>"}, "is not a datatype"),
            ({"Money": "xsd:decimal", "money": "xsd:string"}, "are the same type name"),
            ({"Money": 3}, "must be a datatype"),
        ],
    )
    def test_refused(self, tmp_path: Path, mappings: dict, says: str) -> None:
        result, graph = _run(tmp_path, "class A {\n  a : Money\n}", {"datatype_mappings": mappings})

        assert result.exit_code == 2, result.output
        assert "Error loading config config.yml" in result.output
        assert says in result.output
        assert graph is None

    def test_list_form(self, tmp_path: Path) -> None:
        config = {"datatype_mappings": [{"puml_type": "Money", "rdf_type": "xsd:decimal"}]}
        result, graph = _run(tmp_path, "class A {\n  a : Money\n}", config)

        assert result.exit_code == 0, result.output
        assert graph is not None and _range(graph, DEFAULT.a) == XSD.decimal


# ==============================================================================
# namespace_mappings (#152, under #150's prefix rules)
# ==============================================================================


def _mapping(package: str, uri: str, prefix: str | None = None) -> dict:
    """One namespace_mappings entry."""
    entry = {"package": package, "namespace_uri": uri}
    if prefix is not None:
        entry["prefix"] = prefix
    return entry


class TestNamespaceMappings:
    """What a mapping may do to a package."""

    def test_simple_package_gets_iri_and_prefix(self, tmp_path: Path) -> None:
        config = {
            "namespace_mappings": [_mapping("building", "http://example.org/building", "bld")]
        }
        result, graph = _run(
            tmp_path, "package building {\n  class Building\n}", config, "--strict"
        )

        assert result.exit_code == 0, result.output
        assert graph is not None
        assert (BLD.Building, RDF.type, OWL.Class) in graph
        assert _prefixes(graph) == {"bld": str(BLD)}

    def test_prefix_defaults_to_the_package_name(self, tmp_path: Path) -> None:
        config = {"namespace_mappings": [_mapping("building", "http://example.org/building/")]}
        result, graph = _run(tmp_path, "package building {\n  class Building\n}", config)

        assert result.exit_code == 0, result.output
        assert graph is not None
        assert _prefixes(graph) == {"building": "http://example.org/building/"}

    def test_same_iri_as_the_diagram_is_a_no_op(self, tmp_path: Path) -> None:
        diagram = 'package "http://example.org/building#" as building {\n  class Building\n}'
        config = {"namespace_mappings": [_mapping("building", "http://example.org/building#")]}
        result, graph = _run(tmp_path, diagram, config, "--strict")

        assert result.exit_code == 0, result.output
        assert graph is not None and _prefixes(graph) == {"building": str(BLD)}

    def test_different_iri_from_the_diagram_is_refused(self, tmp_path: Path) -> None:
        diagram = 'package "http://example.org/other#" as building {\n  class Building\n}'
        config = {"namespace_mappings": [_mapping("building", "http://example.org/building#")]}
        result, graph = _run(tmp_path, diagram, config)

        assert result.exit_code == 2, result.output
        assert "Line 2:" in result.output
        assert "namespace_mappings entry for package 'building'" in result.output
        assert "<http://example.org/other#>" in result.output
        assert graph is None

    def test_renaming_a_prefix_the_diagram_gives_with_its_iri_is_refused(
        self, tmp_path: Path
    ) -> None:
        diagram = 'package "http://example.org/building#" as building {\n  class Building\n}'
        config = {
            "namespace_mappings": [_mapping("building", "http://example.org/building#", "bld")]
        }
        result, graph = _run(tmp_path, diagram, config)

        assert result.exit_code == 2, result.output
        assert 'gives the prefix "bld", but this package names "building"' in result.output
        assert graph is None

    def test_mapping_names_a_derived_prefix(self, tmp_path: Path) -> None:
        diagram = 'package "http://example.org/building#" {\n  class Building\n}'
        config = {
            "namespace_mappings": [_mapping("building", "http://example.org/building#", "bld")]
        }
        result, graph = _run(tmp_path, diagram, config, "--strict")

        assert result.exit_code == 0, result.output
        assert "derived the prefix" not in result.output
        assert graph is not None and _prefixes(graph) == {"bld": str(BLD)}

    def test_nested_package_by_its_path(self, tmp_path: Path) -> None:
        diagram = "package site {\n  package zone {\n    class Room\n  }\n}"
        config = {"namespace_mappings": [_mapping("site.zone", "http://example.org/zone#", "zone")]}
        result, graph = _run(tmp_path, diagram, config, "--strict")

        assert result.exit_code == 0, result.output
        assert graph is not None
        assert (URIRef("http://example.org/zone#Room"), RDF.type, OWL.Class) in graph
        assert _prefixes(graph)["zone"] == "http://example.org/zone#"

    def test_dotted_class_without_a_package(self, tmp_path: Path) -> None:
        config = {
            "namespace_mappings": [_mapping("building", "http://example.org/building#", "bld")]
        }
        result, graph = _run(tmp_path, "class building.Building", config, "--strict")

        assert result.exit_code == 0, result.output
        assert graph is not None
        assert (BLD.Building, RDF.type, OWL.Class) in graph
        assert _prefixes(graph) == {"bld": str(BLD)}

    def test_unmatched_mapping_is_a_note_even_under_strict(self, tmp_path: Path) -> None:
        config = {"namespace_mappings": [_mapping("geo", "http://example.org/geo#")]}
        result, graph = _run(tmp_path, "class Building", config, "--strict")

        assert result.exit_code == 0, result.output
        assert "Parse notes:" in result.output
        assert "package 'geo' matches no package" in result.output
        assert graph is not None and (DEFAULT.Building, RDF.type, OWL.Class) in graph

    def test_cli_namespace_wins_and_mappings_still_apply(self, tmp_path: Path) -> None:
        config = {
            "default_namespace": "http://example.org/config#",
            "namespace_mappings": [_mapping("building", "http://example.org/building#", "bld")],
        }
        result, graph = _run(
            tmp_path,
            "class Loose\npackage building {\n  class Building\n}",
            config,
            "-n",
            "http://example.org/cli#",
        )

        assert result.exit_code == 0, result.output
        assert graph is not None
        assert (URIRef("http://example.org/cli#Loose"), RDF.type, OWL.Class) in graph
        assert (BLD.Building, RDF.type, OWL.Class) in graph

    @pytest.mark.parametrize(
        ("diagram", "mappings", "says"),
        [
            (
                "package building {\n  class Building\n}",
                [_mapping("building", "http://example.org/b#", "owl")],
                '"owl" is a core prefix',
            ),
            (
                "package building {\n  class Building\n}",
                [_mapping("building", "http://example.org/b#", "1bad")],
                "is not a legal Turtle prefix",
            ),
            (
                "package a {\n  class A\n}\npackage b {\n  class B\n}",
                [
                    _mapping("a", "http://example.org/a#", "x"),
                    _mapping("b", "http://example.org/b#", "x"),
                ],
                "one prefix cannot name",
            ),
            (
                "package a {\n  class A\n}\npackage b {\n  class B\n}",
                [
                    _mapping("a", "http://example.org/same#"),
                    _mapping("b", "http://example.org/same#"),
                ],
                "one namespace cannot have",
            ),
            (
                "package building {\n  class Building\n}",
                [_mapping("building", "http://example.org/ontology#", "bld")],
                "the default namespace",
            ),
            (
                "package a {\n  class A\n}\npackage geo {\n  class G\n}",
                [_mapping("a", "http://example.org/ontology/geo#")],
                "the namespace generated for package 'geo'",
            ),
            (
                "package building {\n  class Building\n}\npackage bld {\n  class B\n}",
                [_mapping("building", "http://example.org/building#", "bld")],
                "which names package 'bld'",
            ),
            (
                "package building {\n  class Building\n}\nclass bld.B",
                [_mapping("building", "http://example.org/building#", "bld")],
                "which names package 'bld'",
            ),
        ],
    )
    def test_refused(self, tmp_path: Path, diagram: str, mappings: list, says: str) -> None:
        result, graph = _run(tmp_path, diagram, {"namespace_mappings": mappings})

        assert result.exit_code == 2, result.output
        assert says in result.output
        assert "namespace_mappings entry for package" in result.output
        assert graph is None

    def test_parser_without_mappings_is_unchanged(self) -> None:
        """The Python API's parser takes no mappings unless given them."""
        result = PlantUMLParser().parse("@startuml\npackage building {\n  class B\n}\n@enduml\n")

        assert result.success
        assert [(p.name, p.namespace_uri, p.prefix) for p in result.model.packages] == [
            ("building", None, None)
        ]


# ==============================================================================
# The config's keys (#152, the allow-list #268 asks for)
# ==============================================================================


class TestConfigKeys:
    """A key the config does not accept stops the run, naming it."""

    @pytest.mark.parametrize("key", sorted(REMOVED_KEYS))
    def test_removed_key(self, tmp_path: Path, key: str) -> None:
        result, graph = _run(tmp_path, "class A", {key: []})

        assert result.exit_code == 2, result.output
        assert f"'{key}' was removed in rdf-construct 0.7.0" in result.output
        assert graph is None

    def test_prefix_order_says_where_it_is_honoured(self, tmp_path: Path) -> None:
        result, _ = _run(tmp_path, "class A", {"prefix_order": ["owl"]})

        assert "The `order` command honours prefix_order" in result.output

    def test_misspelt_key(self, tmp_path: Path) -> None:
        result, graph = _run(tmp_path, "class A", {"defualt_namespace": "http://example.org/x#"})

        assert result.exit_code == 2, result.output
        assert "unknown key 'defualt_namespace'" in result.output
        assert "Did you mean 'default_namespace'?" in result.output
        assert "Accepted keys: default_namespace, language" in result.output
        assert graph is None

    @pytest.mark.parametrize(
        ("config", "says"),
        [
            ('generate_labels: "false"\n', "'generate_labels' must be true or false"),
            ("camel_to_label: yes please\n", "'camel_to_label' must be true or false"),
            ("default_namespace: 3\n", "'default_namespace' must be a string"),
            ("namespace_mappings: building\n", "'namespace_mappings' must be a list"),
            (
                "namespace_mappings:\n  - package: b\n    uri: http://x#\n",
                "has an unknown key 'uri'",
            ),
            (
                "namespace_mappings:\n  - package: b\n    namespace_uri: not-an-iri\n",
                "is not an IRI",
            ),
            (
                "namespace_mappings:\n  - package: b\n    namespace_uri: http://x#\n"
                "  - package: b\n    namespace_uri: http://y#\n",
                "maps package 'b' a second time",
            ),
            (
                'namespace_mappings:\n  - package: b\n    namespace_uri: http://x#\n    prefix: ""\n',
                "'prefix' is empty",
            ),
        ],
    )
    def test_mistyped_value(self, tmp_path: Path, config: str, says: str) -> None:
        result, graph = _run(tmp_path, "class A", config)

        assert result.exit_code == 2, result.output
        assert says in result.output
        assert graph is None

    def test_false_means_false(self, tmp_path: Path) -> None:
        result, graph = _run(tmp_path, "class A", {"generate_labels": False})

        assert result.exit_code == 0, result.output
        assert graph is not None and not list(graph.objects(DEFAULT.A, RDFS.label))

    def test_default_config_template_loads(self) -> None:
        from rdf_construct.puml2rdf import create_default_config

        config = _parse_config(yaml.safe_load(create_default_config()))
        assert [m.package for m in config.namespace_mappings] == ["building"]


# ==============================================================================
# Shipped material (#152 is `shipped-material`)
# ==============================================================================


class TestShippedExample:
    """The example config, run over the example diagram that uses every mapping it carries."""

    CONFIG = EXAMPLES / "puml2rdf_config.yml"
    DIAGRAM = EXAMPLES / "building.puml"

    def test_every_mapping_takes_effect(self, tmp_path: Path) -> None:
        output = tmp_path / "building.ttl"
        result = CliRunner().invoke(
            cli,
            ["puml2rdf", str(self.DIAGRAM), "-C", str(self.CONFIG), "-o", str(output), "--strict"],
        )

        assert result.exit_code == 0, result.output
        assert "Found: 3 classes, 2 relationships" in result.output
        graph = Graph(bind_namespaces="none")
        graph.parse(output, format="turtle")
        config = yaml.safe_load(self.CONFIG.read_text(encoding="utf-8"))

        # Every namespace mapping is bound, under the prefix it names
        bound = {p: str(n) for p, n in graph.namespaces()}
        for mapping in config["namespace_mappings"]:
            prefix = mapping.get("prefix", mapping["package"])
            assert bound[prefix] == mapping["namespace_uri"]

        # Every datatype mapping is used by the diagram, and written as the config says
        used = {type_name.casefold() for _, _, type_name in _attributes(self.DIAGRAM)}
        for name in config["datatype_mappings"]:
            assert name.casefold() in used, f"{name} is mapped but the example never uses it"
        datatypes = DatatypeMap(config["datatype_mappings"])
        for package, attribute, type_name in _attributes(self.DIAGRAM):
            mapping = next(m for m in config["namespace_mappings"] if m["package"] == package)
            prop = URIRef(f"{mapping['namespace_uri']}{attribute}")
            assert _range(graph, prop) == datatypes.resolve(type_name), attribute


def _attributes(diagram: Path) -> list[tuple[str, str, str]]:
    """Return (package, attribute, type) for each attribute line in a simple example diagram."""
    found = []
    package = ""
    for raw in diagram.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("package "):
            package = line.split()[1]
        elif " : " in line and "-->" not in line:
            name, type_name = (part.strip() for part in line.split(" : ", 1))
            found.append((package, name, type_name))
    return found


class TestGuide:
    """``PUML2RDF_GUIDE.md`` states the map and the config as the code has them."""

    TEXT = GUIDE.read_text(encoding="utf-8")

    def test_datatype_table_is_the_map(self) -> None:
        start = self.TEXT.index("### Supported Datatypes")
        section = self.TEXT[start : self.TEXT.index("### Relationships", start)]
        rows = re.findall(r"^\| (`.+?`) \| `xsd:(\w+)` \|$", section, re.M)
        documented = {
            name.casefold(): XSD[local]
            for names, local in rows
            for name in re.findall(r"`([^`]+)`", names)
        }
        assert documented == BUILTIN_DATATYPES

    def test_config_sample_runs(self, tmp_path: Path) -> None:
        section = self.TEXT[self.TEXT.index("## Configuration File") : self.TEXT.index("### Keys")]
        sample = re.search(r"```yaml\n(.*?)```", section, re.S)
        assert sample is not None
        diagram = (
            "class Loose\npackage building {\n  class Building {\n    value : Money\n"
            "    occupancy : Percentage\n  }\n}\npackage core {\n  class Asset\n}"
        )
        result, graph = _run(tmp_path, diagram, sample.group(1), "--strict")

        assert result.exit_code == 0, result.output
        assert graph is not None
        assert _range(graph, BLD.value) == XSD.decimal
        assert _range(graph, BLD.occupancy) == XSD.decimal
        assert _prefixes(graph) == {
            "": str(DEFAULT),
            "bld": str(BLD),
            "core": "http://example.org/core#",
        }
