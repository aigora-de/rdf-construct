"""Tests for PlantUML import module.

Tests cover parsing, conversion, validation, and merging functionality.
"""

import pytest
from pathlib import Path
from textwrap import dedent
from click.testing import CliRunner
from rdflib import Graph, Namespace, RDF, RDFS, Literal, URIRef
from rdflib.namespace import OWL, XSD

from rdf_construct.cli import cli
from rdf_construct.puml2rdf import (
    PlantUMLParser,
    PumlToRdfConverter,
    ConversionConfig,
    PumlModel,
    PumlClass,
    PumlAttribute,
    PumlRelationship,
    RelationshipType,
    validate_puml,
    validate_rdf,
    OntologyMerger,
)


# ==============================================================================
# Parser Tests
# ==============================================================================


class TestPlantUMLParser:
    """Tests for PlantUML parsing."""

    def test_parse_simple_class(self):
        """Test parsing a simple class declaration."""
        content = """
        @startuml
        class Building
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        assert len(result.model.classes) == 1
        assert result.model.classes[0].name == "Building"

    def test_parse_class_with_attributes(self):
        """Test parsing a class with attributes."""
        content = """
        @startuml
        class Building {
            floorArea : decimal
            constructionYear : gYear
            name : string
        }
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        assert len(result.model.classes) == 1
        cls = result.model.classes[0]
        assert cls.name == "Building"
        assert len(cls.attributes) == 3

        attr_names = {a.name for a in cls.attributes}
        assert attr_names == {"floorArea", "constructionYear", "name"}

        floor_area = next(a for a in cls.attributes if a.name == "floorArea")
        assert floor_area.datatype == "decimal"

    def test_parse_abstract_class(self):
        """Test parsing abstract class declaration."""
        content = """
        @startuml
        abstract class Entity
        class Building
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        entity = result.model.get_class("Entity")
        assert entity is not None
        assert entity.is_abstract is True

        building = result.model.get_class("Building")
        assert building is not None
        assert building.is_abstract is False

    def test_parse_inheritance(self):
        """Test parsing inheritance relationships."""
        content = """
        @startuml
        class Entity
        class Building
        Building --|> Entity
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        assert len(result.model.relationships) == 1

        rel = result.model.relationships[0]
        assert rel.rel_type == RelationshipType.INHERITANCE
        assert rel.source == "Building"  # Child
        assert rel.target == "Entity"  # Parent

    def test_parse_inheritance_reverse_arrow(self):
        """Test parsing inheritance with reversed arrow."""
        content = """
        @startuml
        class Entity
        class Building
        Entity <|-- Building
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        rel = result.model.relationships[0]
        assert rel.source == "Building"  # Child
        assert rel.target == "Entity"  # Parent

    def test_parse_association_with_label(self):
        """Test parsing labeled association."""
        content = """
        @startuml
        class Building
        class Floor
        Building --> Floor : hasFloor
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        # Find non-inheritance relationships
        assocs = result.model.property_relationships()
        assert len(assocs) >= 1

        rel = assocs[0]
        assert rel.source == "Building"
        assert rel.target == "Floor"
        assert rel.label == "hasFloor"

    def test_parse_package(self):
        """`package "URI" as pfx` is a namespace URI plus a prefix alias (#150).

        The guide leads with this form, and reads the `as` clause as the
        prefix. Read the other way round, the whole URI becomes the package
        name and is later bound as a Turtle prefix, which no parser accepts.
        """
        content = """
        @startuml
        package "http://example.org/building#" as bld {
            class Building
        }
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        assert len(result.model.packages) == 1

        pkg = result.model.packages[0]
        assert pkg.name == "bld"
        assert pkg.namespace_uri == "http://example.org/building#"

        building = result.model.get_class("Building")
        assert building is not None
        assert building.package == "bld"

    def test_parse_class_in_package(self):
        """Test that classes track their containing package."""
        content = """
        @startuml
        package building {
            class Building
            class Floor
        }
        class ExternalClass
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success

        building = result.model.get_class("Building")
        assert building is not None
        assert building.package == "building"

        external = result.model.get_class("ExternalClass")
        assert external is not None
        assert external.package is None

    def test_parse_note_attached_to_class(self):
        """Test parsing notes attached to classes."""
        content = """
        @startuml
        class Building
        note right of Building : A physical structure
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        building = result.model.get_class("Building")
        assert building.note == "A physical structure"

    def test_parse_multiline_note(self):
        """Test parsing multi-line notes."""
        content = """
        @startuml
        class Building
        note right of Building
            A physical structure
            that can be occupied
        end note
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        building = result.model.get_class("Building")
        assert building.note is not None
        assert "physical structure" in building.note

    def test_parse_title(self):
        """Test parsing diagram title."""
        content = """
        @startuml
        title Building Ontology
        class Building
        @enduml
        """
        parser = PlantUMLParser()
        result = parser.parse(content)

        assert result.success
        assert result.model.title == "Building Ontology"


# ==============================================================================
# Converter Tests
# ==============================================================================


class TestPumlToRdfConverter:
    """Tests for PlantUML to RDF conversion."""

    def test_convert_simple_class(self):
        """Test converting a simple class."""
        model = PumlModel(classes=[PumlClass(name="Building")])

        config = ConversionConfig(default_namespace="http://example.org/ont#")
        converter = PumlToRdfConverter(config)
        result = converter.convert(model)

        graph = result.graph
        ns = Namespace("http://example.org/ont#")

        # Check class exists and is typed
        assert (ns.Building, RDF.type, OWL.Class) in graph

    def test_convert_class_with_label(self):
        """Test that classes get labels."""
        model = PumlModel(classes=[PumlClass(name="FloorArea")])

        config = ConversionConfig(
            default_namespace="http://example.org/ont#",
            generate_labels=True,
            camel_to_label=True,
        )
        converter = PumlToRdfConverter(config)
        result = converter.convert(model)

        ns = Namespace("http://example.org/ont#")
        labels = list(result.graph.objects(ns.FloorArea, RDFS.label))

        assert len(labels) == 1
        assert str(labels[0]) == "floor area"

    def test_convert_class_with_comment(self):
        """Test that notes become comments."""
        model = PumlModel(classes=[PumlClass(name="Building", note="A physical structure")])

        converter = PumlToRdfConverter()
        result = converter.convert(model)

        ns = Namespace("http://example.org/ontology#")
        comments = list(result.graph.objects(ns.Building, RDFS.comment))

        assert len(comments) == 1
        assert "physical structure" in str(comments[0])

    def test_convert_attribute_to_datatype_property(self):
        """Test that attributes become datatype properties."""
        model = PumlModel(
            classes=[
                PumlClass(
                    name="Building",
                    attributes=[PumlAttribute(name="floorArea", datatype="decimal")],
                )
            ]
        )

        config = ConversionConfig(default_namespace="http://example.org/ont#")
        converter = PumlToRdfConverter(config)
        result = converter.convert(model)

        ns = Namespace("http://example.org/ont#")
        graph = result.graph

        # Check property type
        assert (ns.floorArea, RDF.type, OWL.DatatypeProperty) in graph

        # Check domain
        domains = list(graph.objects(ns.floorArea, RDFS.domain))
        assert ns.Building in domains

        # Check range
        ranges = list(graph.objects(ns.floorArea, RDFS.range))
        assert XSD.decimal in ranges

    def test_convert_inheritance(self):
        """Test that inheritance becomes subClassOf."""
        model = PumlModel(
            classes=[
                PumlClass(name="Entity"),
                PumlClass(name="Building"),
            ],
            relationships=[
                PumlRelationship(
                    source="Building",
                    target="Entity",
                    rel_type=RelationshipType.INHERITANCE,
                )
            ],
        )

        config = ConversionConfig(default_namespace="http://example.org/ont#")
        converter = PumlToRdfConverter(config)
        result = converter.convert(model)

        ns = Namespace("http://example.org/ont#")
        assert (ns.Building, RDFS.subClassOf, ns.Entity) in result.graph

    def test_convert_association_to_object_property(self):
        """Test that associations become object properties."""
        model = PumlModel(
            classes=[
                PumlClass(name="Building"),
                PumlClass(name="Floor"),
            ],
            relationships=[
                PumlRelationship(
                    source="Building",
                    target="Floor",
                    rel_type=RelationshipType.ASSOCIATION,
                    label="has floor",
                )
            ],
        )

        config = ConversionConfig(default_namespace="http://example.org/ont#")
        converter = PumlToRdfConverter(config)
        result = converter.convert(model)

        ns = Namespace("http://example.org/ont#")
        graph = result.graph

        # Check property exists
        assert (ns.hasFloor, RDF.type, OWL.ObjectProperty) in graph

        # Check domain and range
        assert (ns.hasFloor, RDFS.domain, ns.Building) in graph
        assert (ns.hasFloor, RDFS.range, ns.Floor) in graph

    def test_convert_generates_ontology_header(self):
        """Test that conversion creates ontology declaration."""
        model = PumlModel(title="Building Ontology", classes=[PumlClass(name="Building")])

        config = ConversionConfig(default_namespace="http://example.org/building#")
        converter = PumlToRdfConverter(config)
        result = converter.convert(model)

        ont_uri = Namespace("http://example.org/building")[""]
        # Check for ontology type (URI without trailing #)
        ont_types = list(result.graph.subjects(RDF.type, OWL.Ontology))
        assert len(ont_types) >= 1


# ==============================================================================
# Validator Tests
# ==============================================================================


class TestPumlValidation:
    """Tests for PlantUML model validation."""

    def test_validate_duplicate_classes(self):
        """Test detection of duplicate class names."""
        model = PumlModel(
            classes=[
                PumlClass(name="Building"),
                PumlClass(name="Building"),
            ]
        )

        result = validate_puml(model)
        assert result.has_errors
        assert any("DUPLICATE_CLASS" in str(i) for i in result.issues)

    def test_validate_unknown_relationship_class(self):
        """Test detection of relationships to unknown classes."""
        model = PumlModel(
            classes=[PumlClass(name="Building")],
            relationships=[
                PumlRelationship(
                    source="Building",
                    target="NonExistent",
                    rel_type=RelationshipType.ASSOCIATION,
                )
            ],
        )

        result = validate_puml(model)
        assert result.has_errors
        assert any("UNKNOWN_CLASS" in str(i) for i in result.issues)

    def test_validate_unknown_datatype(self):
        """Test warning for unknown datatypes."""
        model = PumlModel(
            classes=[
                PumlClass(
                    name="Building",
                    attributes=[PumlAttribute(name="custom", datatype="UnknownType")],
                )
            ]
        )

        result = validate_puml(model)
        assert result.has_warnings
        assert any("UNKNOWN_DATATYPE" in str(i) for i in result.issues)

    def test_validate_inheritance_cycle(self):
        """Test detection of inheritance cycles."""
        model = PumlModel(
            classes=[
                PumlClass(name="A"),
                PumlClass(name="B"),
                PumlClass(name="C"),
            ],
            relationships=[
                PumlRelationship(source="A", target="B", rel_type=RelationshipType.INHERITANCE),
                PumlRelationship(source="B", target="C", rel_type=RelationshipType.INHERITANCE),
                PumlRelationship(source="C", target="A", rel_type=RelationshipType.INHERITANCE),
            ],
        )

        result = validate_puml(model)
        assert result.has_errors
        assert any("INHERITANCE_CYCLE" in str(i) for i in result.issues)


class TestRdfValidation:
    """Tests for RDF graph validation."""

    def test_validate_untyped_class(self):
        """Test warning for classes used without type declaration."""
        graph = Graph()
        ns = Namespace("http://example.org/ont#")

        # Add subClassOf without class type
        graph.add((ns.Building, RDFS.subClassOf, ns.Entity))

        result = validate_rdf(graph)
        assert any("UNTYPED_CLASS" in str(i) for i in result.issues)

    def test_validate_missing_domain(self):
        """Test info for properties without domain."""
        graph = Graph()
        ns = Namespace("http://example.org/ont#")

        graph.add((ns.hasFloor, RDF.type, OWL.ObjectProperty))
        # No domain added

        result = validate_rdf(graph)
        assert any("MISSING_DOMAIN" in str(i) for i in result.issues)


# ==============================================================================
# Merger Tests
# ==============================================================================


class TestOntologyMerger:
    """Tests for ontology merging."""

    def test_merge_adds_new_triples(self):
        """Test that new triples are added."""
        existing = Graph()
        ns = Namespace("http://example.org/ont#")
        existing.add((ns.Building, RDF.type, OWL.Class))

        new_graph = Graph()
        new_graph.add((ns.Floor, RDF.type, OWL.Class))

        merger = OntologyMerger()
        result = merger.merge_graphs(new_graph, existing)

        assert (ns.Building, RDF.type, OWL.Class) in result.graph
        assert (ns.Floor, RDF.type, OWL.Class) in result.graph

    def test_merge_preserves_existing_annotations(self):
        """Test that existing annotations are preserved."""
        existing = Graph()
        ns = Namespace("http://example.org/ont#")
        existing.add((ns.Building, RDF.type, OWL.Class))
        existing.add((ns.Building, RDFS.comment, Literal("Manually added comment")))

        new_graph = Graph()
        new_graph.add((ns.Building, RDF.type, OWL.Class))
        # No comment in new

        merger = OntologyMerger()
        result = merger.merge_graphs(new_graph, existing)

        comments = list(result.graph.objects(ns.Building, RDFS.comment))
        assert any("Manually added" in str(c) for c in comments)


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestRoundTrip:
    """Integration tests for full parse-convert workflow."""

    def test_full_conversion(self):
        """Test complete parse and convert workflow."""
        puml = """
        @startuml
        title Building Ontology

        class Building {
            floorArea : decimal
            constructionYear : gYear
        }

        class Floor {
            level : integer
        }

        Building --|> Entity
        Building --> Floor : hasFloor

        note right of Building
            A physical structure
            that can be occupied.
        end note

        @enduml
        """

        # Parse
        parser = PlantUMLParser()
        parse_result = parser.parse(puml)
        assert parse_result.success

        # Add Entity class (referenced but not defined)
        parse_result.model.classes.append(PumlClass(name="Entity"))

        # Convert
        config = ConversionConfig(
            default_namespace="http://example.org/building#",
            generate_labels=True,
        )
        converter = PumlToRdfConverter(config)
        result = converter.convert(parse_result.model)

        # Verify
        graph = result.graph
        ns = Namespace("http://example.org/building#")

        # Classes exist
        assert (ns.Building, RDF.type, OWL.Class) in graph
        assert (ns.Floor, RDF.type, OWL.Class) in graph

        # Inheritance
        assert (ns.Building, RDFS.subClassOf, ns.Entity) in graph

        # Properties
        assert (ns.floorArea, RDF.type, OWL.DatatypeProperty) in graph
        assert (ns.hasFloor, RDF.type, OWL.ObjectProperty) in graph

        # Comment from note
        comments = list(graph.objects(ns.Building, RDFS.comment))
        assert len(comments) >= 1


# ==============================================================================
# CLI summary Tests
# ==============================================================================


class TestPuml2rdfCliSummary:
    """Tests for the puml2rdf command's conversion summary."""

    def test_packaged_diagram_summary_counts_distinct_classes(self, tmp_path: Path) -> None:
        """Summary class count must match distinct classes, not dual-keyed map size.

        Packaged classes are stored under both ``name`` and ``qualified_name``.
        The parse line reports the real class count; the final summary must too.
        """
        puml = tmp_path / "building.puml"
        puml.write_text(
            dedent(
                """
                @startuml
                package "http://example.org/building#" as bld {
                  class Building
                  class Floor
                  class Room
                }
                Building --> Floor : hasFloor
                Floor --> Room : hasRoom
                @enduml
                """
            )
        )
        output = tmp_path / "building.ttl"
        result = CliRunner().invoke(cli, ["puml2rdf", str(puml), "-o", str(output)])

        assert result.exit_code == 0, result.output
        assert "Found: 3 classes" in result.output
        assert "Classes: 3," in result.output
        assert "Classes: 6," not in result.output

        bld = Namespace("http://example.org/building#")
        graph = Graph().parse(output, format="turtle")
        assert (bld.Room, RDF.type, OWL.Class) in graph


# ==============================================================================
# Package namespace tests (#150)
# ==============================================================================


class TestPackageNamespaces:
    """`package "URI" as pfx` writes Turtle that reads back, under the alias.

    The worked example in PUML2RDF_GUIDE.md uses this form. Before #150 the
    parser read the `as` clause the wrong way round, the converter bound the
    whole URI as a Turtle prefix, and the command reported success at exit 0
    on a file rdflib refuses to parse.
    """

    GUIDE_EXAMPLE = dedent(
        """
        @startuml
        title Building Ontology

        package "http://example.org/building#" as bld {
          class Building {
            floorArea : decimal
            constructionYear : gYear
          }
          class Floor {
            level : integer
          }
        }

        Building "1" --> "*" Floor : hasFloor
        @enduml
        """
    )

    def _convert(self, tmp_path: Path, content: str) -> tuple[Graph, str]:
        """Run the CLI over *content* and read the output back as Turtle."""
        puml = tmp_path / "diagram.puml"
        puml.write_text(content, encoding="utf-8")
        output = tmp_path / "diagram.ttl"
        result = CliRunner().invoke(cli, ["puml2rdf", str(puml), "-o", str(output)])

        assert result.exit_code == 0, result.output
        text = output.read_text(encoding="utf-8")
        return Graph().parse(data=text, format="turtle"), text

    def test_guide_example_is_re_parsable(self, tmp_path: Path) -> None:
        """The guide's worked example round-trips: exit 0 and a readable file."""
        graph, _text = self._convert(tmp_path, self.GUIDE_EXAMPLE)

        bld = Namespace("http://example.org/building#")
        assert (bld.Building, RDF.type, OWL.Class) in graph
        assert (bld.Floor, RDF.type, OWL.Class) in graph
        assert (bld.hasFloor, RDF.type, OWL.ObjectProperty) in graph
        assert (bld.floorArea, RDFS.domain, bld.Building) in graph

    def test_guide_example_binds_the_alias_as_prefix(self, tmp_path: Path) -> None:
        """The alias is the Turtle prefix, as the guide's output shows."""
        _graph, text = self._convert(tmp_path, self.GUIDE_EXAMPLE)

        assert "@prefix bld: <http://example.org/building#>" in text
        assert "bld:Building" in text

    def test_uri_package_without_alias_derives_a_prefix(self, tmp_path: Path) -> None:
        """`package "URI" { … }` names the namespace and still binds a legal prefix."""
        content = dedent(
            """
            @startuml
            package "http://example.org/building#" {
              class Building
            }
            @enduml
            """
        )
        _graph, text = self._convert(tmp_path, content)

        assert "@prefix building: <http://example.org/building#>" in text
        assert "building:Building" in text

    def test_simple_package_is_unchanged(self, tmp_path: Path) -> None:
        """`package core { … }` still generates its namespace from the name."""
        content = dedent(
            """
            @startuml
            package core {
              class Entity
            }
            @enduml
            """
        )
        graph, _text = self._convert(tmp_path, content)

        core = Namespace("http://example.org/ontology/core#")
        assert (core.Entity, RDF.type, OWL.Class) in graph

    def _refuse(self, tmp_path: Path, body: str) -> str:
        """Run the CLI over *body* and check it was refused with nothing written.

        Three blank lines follow ``@startuml``: stripping the markers removes all of them, so a
        line number taken from the stripped text would be three short of the file's.
        """
        puml = tmp_path / "diagram.puml"
        puml.write_text(f"@startuml\n\n\n{dedent(body).strip()}\n@enduml\n", encoding="utf-8")
        result = CliRunner().invoke(
            cli, ["puml2rdf", str(puml), "-o", str(tmp_path / "diagram.ttl")]
        )

        assert result.exit_code == 2, result.output
        assert sorted(path.name for path in tmp_path.iterdir()) == ["diagram.puml"]
        return result.output

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            pytest.param(
                'package bld as "http://example.org/building#" {\n  class Building\n}',
                'Line 4: the namespace IRI goes in quotes before "as", and the prefix after it: '
                'package "http://example.org/building#" as bld',
                id="reverse-spelling-quoted",
            ),
            pytest.param(
                "package bld as http://example.org/building# {\n  class Building\n}",
                'Line 4: the namespace IRI goes in quotes before "as", and the prefix after it: '
                'package "http://example.org/building#" as bld',
                id="reverse-spelling-bare",
            ),
            pytest.param(
                'package "http://example.org/second#" as 2nd {\n  class Item\n}',
                'Line 4: "2nd" is not a legal Turtle prefix',
                id="prefix-starts-with-digit",
            ),
            pytest.param(
                'package "http://example.org/pkg#" as pkg. {\n  class Item\n}',
                'Line 4: "pkg." is not a legal Turtle prefix',
                id="prefix-ends-with-dot",
            ),
            pytest.param(
                'package "http://example.org/e#" as : {\n  class Item\n}',
                'Line 4: ":" is not a legal Turtle prefix',
                id="empty-prefix",
            ),
            pytest.param(
                'package "http://example.org/mine#" as owl {\n  class Thing\n}',
                'Line 4: "owl" is a core prefix, bound to <http://www.w3.org/2002/07/owl#>; '
                "it cannot name <http://example.org/mine#>",
                id="core-prefix-on-another-namespace",
            ),
            pytest.param(
                "class rdfs.Thing",
                'Line 4: "rdfs" is a core prefix',
                id="core-prefix-on-a-dotted-class",
            ),
            pytest.param(
                'package "http://example.org/a#" as ex {\n  class A\n}\n'
                'package "http://example.org/b#" as ex {\n  class B\n}',
                'Line 7: "ex" is already the prefix for <http://example.org/a#> (line 4); '
                "one prefix cannot name <http://example.org/b#> as well",
                id="one-prefix-two-namespaces",
            ),
            pytest.param(
                'package "http://example.org/a#" as ex {\n  class A\n}\n'
                'package "http://example.org/a#" as ey {\n  class B\n}',
                'Line 7: <http://example.org/a#> already has the prefix "ex" (line 4); '
                'one namespace cannot have "ey" as well',
                id="one-namespace-two-prefixes",
            ),
            pytest.param(
                'package "http://example.org/one/core#" {\n  class A\n}\n'
                'package "http://example.org/two/Core#" {\n  class B\n}',
                'Line 7: no prefix is named for <http://example.org/two/Core#>, and "core", '
                "derived from it, already names <http://example.org/one/core#> (line 4)",
                id="derived-prefix-already-taken",
            ),
        ],
    )
    def test_prefix_that_cannot_be_written_is_refused(
        self, tmp_path: Path, body: str, expected: str
    ) -> None:
        """A prefix is used as written or refused: exit 2, the line named, nothing written."""
        output = self._refuse(tmp_path, body)

        assert "Parse errors:" in output
        assert expected in output

    def test_alias_taken_by_rdflib_default_is_kept(self, tmp_path: Path) -> None:
        """`as org` writes `org:`; rdflib's own `org:` binding no longer pushes it to `org1:`."""
        content = dedent(
            """
            @startuml
            package "http://example.org/org#" as org {
              class Team
            }
            @enduml
            """
        )
        graph, text = self._convert(tmp_path, content)

        assert "@prefix org: <http://example.org/org#>" in text
        assert (Namespace("http://example.org/org#").Team, RDF.type, OWL.Class) in graph

    def test_core_prefix_on_its_own_namespace_is_accepted(self, tmp_path: Path) -> None:
        """`as owl` on OWL's own namespace is no clash."""
        content = dedent(
            """
            @startuml
            package "http://www.w3.org/2002/07/owl#" as owl {
              class Widget
            }
            @enduml
            """
        )
        graph, text = self._convert(tmp_path, content)

        assert "owl1:" not in text
        widget = URIRef("http://www.w3.org/2002/07/owl#Widget")
        assert (widget, RDF.type, OWL.Class) in graph

    def test_urn_namespace_is_a_uri(self, tmp_path: Path) -> None:
        """A URI is anything with a scheme, so `urn:` names the namespace too."""
        content = dedent(
            """
            @startuml
            package "urn:example:building#" as bld {
              class Building
            }
            @enduml
            """
        )
        graph, text = self._convert(tmp_path, content)

        assert "@prefix bld: <urn:example:building#>" in text
        assert (Namespace("urn:example:building#").Building, RDF.type, OWL.Class) in graph

    def test_urn_ending_in_colon_is_used_as_it_stands(self, tmp_path: Path) -> None:
        """A URN namespace ending in `:` already ends in its delimiter: no `#` is appended."""
        content = dedent(
            """
            @startuml
            package "urn:example:building:" as bld {
              class Building
            }
            @enduml
            """
        )
        graph, text = self._convert(tmp_path, content)

        assert "@prefix bld: <urn:example:building:>" in text
        assert (URIRef("urn:example:building:Building"), RDF.type, OWL.Class) in graph

    def test_quoted_name_that_is_not_a_uri_is_display_text(self, tmp_path: Path) -> None:
        """`package "Building Things" as bld` behaves like `package bld`."""
        content = dedent(
            """
            @startuml
            package "Building Things" as bld {
              class Building
            }
            @enduml
            """
        )
        graph, text = self._convert(tmp_path, content)

        bld = Namespace("http://example.org/ontology/bld#")
        assert "@prefix bld: <http://example.org/ontology/bld#>" in text
        assert (bld.Building, RDF.type, OWL.Class) in graph

    def test_derived_prefix_is_reported(self, tmp_path: Path) -> None:
        """A URI package with no alias says which prefix it was given, and still succeeds."""
        puml = tmp_path / "diagram.puml"
        puml.write_text(
            '@startuml\npackage "urn:example:things#" {\n  class Thing\n}\n@enduml\n',
            encoding="utf-8",
        )
        output = tmp_path / "diagram.ttl"
        result = CliRunner().invoke(cli, ["puml2rdf", str(puml), "-o", str(output)])

        assert result.exit_code == 0, result.output
        assert 'Line 2: derived the prefix "things" for <urn:example:things#>' in result.output
        assert "@prefix things: <urn:example:things#>" in output.read_text(encoding="utf-8")

    def test_every_prefix_is_one_the_diagram_gave(self, tmp_path: Path) -> None:
        """Read back, the file declares exactly the prefixes asked for: none renamed or invented."""
        content = dedent(
            """
            @startuml
            package "http://example.org/building#" as bld {
              class Building {
                floorArea : decimal
              }
            }
            package "http://example.org/org#" as org {
              class Team
            }
            package "http://www.w3.org/2002/07/owl#" as owl {
              class Widget
            }
            package "urn:example:things#" {
              class Thing
            }
            package core {
              class Entity
            }
            class extra.Item
            @enduml
            """
        )
        graph, text = self._convert(tmp_path, content)
        declared = Graph(bind_namespaces="none").parse(data=text, format="turtle")

        assert {prefix for prefix, _ in declared.namespaces()} == {
            "bld",
            "core",
            "extra",
            "org",
            "owl",
            "rdfs",
            "things",
            "xsd",
        }


# ==============================================================================
# The parser's failure path (#151)
# ==============================================================================


def _run(tmp_path: Path, text: str, *options: str, name: str = "diagram.puml"):
    """Write *text* to *name* and run the CLI over it, with ``-o`` beside it."""
    puml = tmp_path / name
    puml.write_text(text, encoding="utf-8")
    output = tmp_path / "diagram.ttl"
    return CliRunner().invoke(cli, ["puml2rdf", str(puml), "-o", str(output), *options])


def _wrote_nothing(tmp_path: Path, name: str = "diagram.puml") -> bool:
    """True when the run left only its input behind."""
    return sorted(path.name for path in tmp_path.iterdir()) == [name]


SHOPPING_LIST = dedent(
    """\
    This is not a PlantUML diagram at all.
    It is a shopping list.

      bread
      milk : semi-skimmed
      eggs
    """
)

TURTLE = dedent(
    """\
    @prefix ex: <http://example.org/> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .

    ex:Animal a owl:Class .
    """
)


class TestDiagramMarkers:
    """A file without `@startuml` … `@enduml` is refused: exit 2, nothing written (#151)."""

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param(SHOPPING_LIST, id="shopping-list"),
            pytest.param("", id="empty-file"),
            pytest.param(TURTLE, id="turtle-renamed"),
        ],
    )
    @pytest.mark.parametrize("options", [(), ("--validate", "--strict")], ids=["run", "validate"])
    def test_no_startuml_is_refused(
        self, tmp_path: Path, text: str, options: tuple[str, ...]
    ) -> None:
        """The issue's three reproducers, which converted to a one-triple ontology at exit 0."""
        result = _run(tmp_path, text, *options, name="shopping.puml")

        assert result.exit_code == 2, result.output
        assert _wrote_nothing(tmp_path, "shopping.puml")
        assert (
            "shopping.puml: no @startuml found — this does not look like a PlantUML diagram. "
            "A fragment must be wrapped in @startuml … @enduml." in result.output
        )

    def test_no_enduml_is_refused(self, tmp_path: Path) -> None:
        """A missing `@enduml` is the sign of a truncated file, refused in its own right."""
        result = _run(tmp_path, "@startuml\nclass Building {\n  floorArea : decimal\n}\n")

        assert result.exit_code == 2, result.output
        assert _wrote_nothing(tmp_path)
        assert "diagram.puml: no @enduml found — the diagram may have been cut short" in (
            result.output
        )

    def test_enduml_before_startuml_is_refused(self, tmp_path: Path) -> None:
        """Only an `@enduml` after the `@startuml` closes the diagram."""
        result = _run(tmp_path, "@enduml\n@startuml\nclass Building\n")

        assert result.exit_code == 2, result.output
        assert "no @enduml found" in result.output

    def test_parse_result_is_not_a_success(self) -> None:
        """`ParseResult.success` can be false, and the model is empty."""
        result = PlantUMLParser().parse("class Building\n")

        assert not result.success
        assert result.errors[0].line_number is None
        assert result.errors[0].message.startswith("no @startuml found")
        assert result.model.classes == []

    @pytest.mark.parametrize(
        "opening", ["@startuml", "@startuml building_model", "@startuml(id=main)", "  @startuml"]
    )
    def test_named_or_indented_markers_are_accepted(self, opening: str) -> None:
        """A named, identified or indented `@startuml` opens a diagram, and is not reported."""
        result = PlantUMLParser().parse(f"{opening}\nclass Building\n@enduml\n")

        assert result.success
        assert result.warnings == []
        assert [cls.name for cls in result.model.classes] == ["Building"]


class TestUnreadLines:
    """A line no pass reads is reported by its file line number, and --strict makes it fatal."""

    def test_lines_not_understood_are_reported_with_file_line_numbers(self, tmp_path: Path) -> None:
        """Blank lines after `@startuml` do not shift the numbers (stripping removed them)."""
        text = (
            "@startuml\n\n\nclass Building\nthis line is junk\nclass Floor\nso is this\n@enduml\n"
        )
        result = _run(tmp_path, text)

        assert result.exit_code == 0, result.output
        assert "⚠ 2 lines not understood (5, 7) — they are not in the output." in result.output
        graph = Graph().parse(tmp_path / "diagram.ttl", format="turtle")
        ns = Namespace("http://example.org/ontology#")
        assert (ns.Floor, RDF.type, OWL.Class) in graph

    def test_one_line_not_understood(self, tmp_path: Path) -> None:
        """One line reads as one."""
        result = _run(tmp_path, "@startuml\nclass Building\nnonsense\n@enduml\n")

        assert "⚠ 1 line not understood (3) — it is not in the output." in result.output

    def test_parse_warnings_carry_line_and_content(self) -> None:
        """Each unread line is a `ParseWarning` with its line, its text and its code."""
        result = PlantUMLParser().parse("@startuml\nclass A\n  junk here\n@enduml\n")

        assert result.success
        [warning] = result.warnings
        assert (warning.line_number, warning.line_content, warning.code) == (
            3,
            "junk here",
            "not-understood",
        )
        assert str(warning) == "Line 3: not understood: junk here"

    def test_a_long_list_is_shortened(self, tmp_path: Path) -> None:
        """Past ten line numbers, the summary says how many more there are."""
        junk = "".join(f"junk {i}\n" for i in range(12))
        result = _run(tmp_path, f"@startuml\nclass A\n{junk}@enduml\n")

        assert (
            "⚠ 12 lines not understood (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, … 2 more)" in result.output
        )

    def test_strict_makes_lines_not_understood_fatal(self, tmp_path: Path) -> None:
        """Under --strict a line not understood stops the run at 1, before anything is written."""
        result = _run(tmp_path, "@startuml\nclass Building\nnonsense\n@enduml\n", "--strict")

        assert result.exit_code == 1, result.output
        assert _wrote_nothing(tmp_path)
        assert "Aborting due to --strict mode" in result.output

    @pytest.mark.parametrize(
        "lines",
        [
            pytest.param("' a comment", id="comment"),
            pytest.param("/' a block\n   comment '/", id="block-comment"),
            pytest.param("/' a one-line block comment '/", id="block-comment-one-line"),
            pytest.param("package core {\n  class Entity\n}", id="package-closing-brace"),
            pytest.param("hide empty members", id="hide"),
            pytest.param("show Building fields", id="show"),
            pytest.param("left to right direction", id="left-to-right"),
            pytest.param("top to bottom direction", id="top-to-bottom"),
            pytest.param("!include common.iuml", id="include"),
            pytest.param("!theme plain", id="theme"),
            pytest.param("skinparam class {\n  BackgroundColor White\n}", id="skinparam-block"),
            pytest.param("skinparam linetype ortho", id="skinparam-line"),
            pytest.param("legend right\n  A legend\nendlegend", id="legend"),
            pytest.param("header Draft", id="header"),
            pytest.param("footer Page 1", id="footer"),
            pytest.param("caption Figure 1", id="caption"),
            pytest.param("header\n  Draft\nend header", id="header-block"),
            pytest.param("title Building Ontology", id="title"),
            pytest.param("title\n  A long title\n  over lines\nend title", id="title-block"),
            pytest.param("together {\n  class Room\n}", id="together"),
            pytest.param("note right of Building\n  A structure.\nend note", id="note-block"),
            pytest.param("note left of Building : A structure", id="note-line"),
            pytest.param('Building "1" --> "*" Floor : hasFloor', id="cardinalities"),
            pytest.param("Building <|-- Floor", id="inheritance"),
            pytest.param("Building --> Floor", id="association"),
        ],
    )
    def test_ignorable_and_understood_lines_are_silent(self, tmp_path: Path, lines: str) -> None:
        """Comments, layout, presentation and everything a pass reads pass --strict silently."""
        text = f"@startuml\nclass Building {{\n  floorArea : decimal\n}}\nclass Floor\n{lines}\n@enduml\n"
        result = _run(tmp_path, text, "--strict")

        assert result.exit_code == 0, result.output
        assert "Parse warnings" not in result.output

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            pytest.param(
                "interface Shape",
                "Line 3: interface Shape is not converted: only classes are, "
                "so Shape is not in the output",
                id="interface",
            ),
            pytest.param(
                "enum Colour {\n  RED\n  GREEN\n}",
                "Line 3: enum Colour is not converted: only classes are, "
                "so Colour is not in the output",
                id="enum",
            ),
            pytest.param(
                "annotation Marker",
                "Line 3: annotation Marker is not converted",
                id="annotation",
            ),
            pytest.param("entity Person", "Line 3: entity Person is not converted", id="entity"),
            pytest.param("struct Point", "Line 3: struct Point is not converted", id="struct"),
            pytest.param(
                "abstract Vehicle",
                "Line 3: abstract Vehicle is not converted, so it is not in the output; "
                'write "abstract class Vehicle" to convert it',
                id="bare-abstract",
            ),
            pytest.param(
                "Car ..|> Shape",
                "Line 3: realisation is not converted, so it is not in the output: Car ..|> Shape",
                id="realisation",
            ),
            pytest.param(
                "Shape <|.. Car",
                "Line 3: realisation is not converted",
                id="realisation-reversed",
            ),
            pytest.param(
                "Car ..> Colour",
                "Line 3: dependency is not converted, so it is not in the output: Car ..> Colour",
                id="dependency",
            ),
            pytest.param(
                "Colour <.. Car", "Line 3: dependency is not converted", id="dependency-reversed"
            ),
        ],
    )
    def test_unmodelled_declarations_are_named(
        self, tmp_path: Path, line: str, expected: str
    ) -> None:
        """Each kind the converter does not model is named as dropped, and --strict refuses it."""
        text = f"@startuml\nclass Car\n{line}\n@enduml\n"
        result = _run(tmp_path, text)

        assert result.exit_code == 0, result.output
        assert expected in result.output
        # An enum's or interface's body belongs to the one warning
        assert "not understood" not in result.output

        strict = _run(tmp_path, text, "--strict")
        assert strict.exit_code == 1, strict.output

    def test_abstract_class_is_not_reported(self, tmp_path: Path) -> None:
        """`abstract class Foo` is converted, so only the bare form is named."""
        result = _run(tmp_path, "@startuml\nabstract class Vehicle\n@enduml\n", "--strict")

        assert result.exit_code == 0, result.output

    def test_note_on_an_unknown_class_is_fatal_under_strict(self, tmp_path: Path) -> None:
        """A note attached to no class is content dropped from the output."""
        text = "@startuml\nclass Building\nnote right of Floor : lost\n@enduml\n"

        assert _run(tmp_path, text).exit_code == 0
        result = _run(tmp_path, text, "--strict")
        assert result.exit_code == 1, result.output
        assert "Note attached to unknown class: Floor" in result.output

    def test_empty_diagram_warns_and_writes(self, tmp_path: Path) -> None:
        """A marked diagram with nothing in it is degenerate, not refused: exit 0, written."""
        result = _run(tmp_path, "@startuml\n@enduml\n")

        assert result.exit_code == 0, result.output
        assert "nothing converted: the diagram has no classes or relationships" in result.output
        assert (tmp_path / "diagram.ttl").exists()

    def test_empty_diagram_is_fatal_under_strict(self, tmp_path: Path) -> None:
        """--strict makes the empty diagram's warning fatal like any other."""
        result = _run(tmp_path, "@startuml\n' only a comment\n@enduml\n", "--strict")

        assert result.exit_code == 1, result.output
        assert _wrote_nothing(tmp_path)

    def test_derived_prefix_is_a_note_never_fatal(self, tmp_path: Path) -> None:
        """A derived prefix drops nothing from the output, so --strict lets it through."""
        text = '@startuml\npackage "urn:example:things#" {\n  class Thing\n}\n@enduml\n'
        result = _run(tmp_path, text, "--strict")

        assert result.exit_code == 0, result.output
        assert "Parse notes:" in result.output
        assert "Parse warnings" not in result.output
        assert 'Line 2: derived the prefix "things"' in result.output

    def test_unread_line_scan_is_linear(self) -> None:
        """Ten times the diagram takes nowhere near a hundred times as long (Sam's scale probe)."""
        import time

        def diagram(n: int) -> str:
            body = "".join(
                f"class C{i} {{\n  a{i} : string\n}}\nC{i} --> C{i + 1} : r{i}\njunk {i}\n"
                for i in range(n)
            )
            return f"@startuml\n{body}class C{n}\n@enduml\n"

        def timed(text: str) -> float:
            start = time.perf_counter()
            PlantUMLParser().parse(text)
            return time.perf_counter() - start

        # 20,000 is where a quadratic line lookup shows: str.count per match is C-fast below it
        small, large = diagram(2000), diagram(20000)
        timed(small)
        assert timed(large) < 30 * max(timed(small), 0.01)


# ==============================================================================
# --validate checks the RDF it would write (#290)
# ==============================================================================


class TestValidateConvertsAndChecks:
    """`--validate` converts, validates the RDF and serialises it in memory; it writes nothing."""

    BAD_IRI = '@startuml\npackage "http://example.org/a b#" as ab {\n  class Thing\n}\n@enduml\n'

    def test_unserialisable_rdf_fails_validation(self, tmp_path: Path) -> None:
        """An IRI the requested format cannot write fails --validate at 2, as a real run would."""
        result = _run(tmp_path, self.BAD_IRI, "--validate")

        assert result.exit_code == 2, result.output
        assert "Validation failed: the RDF cannot be written" in result.output
        assert _wrote_nothing(tmp_path)

    def test_serialised_in_the_requested_format(self, tmp_path: Path) -> None:
        """RDF/XML writes that IRI without complaint, so --validate -f xml passes."""
        result = _run(tmp_path, self.BAD_IRI, "--validate", "-f", "xml")

        assert result.exit_code == 0, result.output
        assert _wrote_nothing(tmp_path)

    def test_validate_converts_and_writes_nothing(self, tmp_path: Path) -> None:
        """The conversion runs, its warnings are counted, and no file appears."""
        text = "@startuml\nclass A {\n  size : Money\n}\nnonsense\n@enduml\n"
        result = _run(tmp_path, text, "--validate")

        assert result.exit_code == 0, result.output
        assert "Converting to RDF..." in result.output
        assert "Conversion warnings:" in result.output
        assert "Validation complete: 3 warnings" in result.output
        assert _wrote_nothing(tmp_path)

    def test_validate_clean_diagram(self, tmp_path: Path) -> None:
        """A clean diagram validates clean."""
        result = _run(tmp_path, "@startuml\nclass A\nclass B\nA <|-- B\n@enduml\n", "--validate")

        assert result.exit_code == 0, result.output
        assert "Validation complete: no issues found" in result.output
        assert _wrote_nothing(tmp_path)

    def test_validate_does_not_merge(self, tmp_path: Path) -> None:
        """--merge belongs to the write path; under --validate the existing file is not read."""
        existing = tmp_path / "existing.ttl"
        existing.write_text("this is not turtle", encoding="utf-8")
        puml = tmp_path / "diagram.puml"
        puml.write_text("@startuml\nclass A\n@enduml\n", encoding="utf-8")
        result = CliRunner().invoke(
            cli, ["puml2rdf", str(puml), "--validate", "--merge", str(existing)]
        )

        assert result.exit_code == 0, result.output
        assert "Merging" not in result.output

    def test_parse_warnings_reach_validate_strict(self, tmp_path: Path) -> None:
        """Parse warnings are fatal under --validate --strict, as in a real run."""
        result = _run(
            tmp_path, "@startuml\nclass A\ninterface I\n@enduml\n", "--validate", "--strict"
        )

        assert result.exit_code == 1, result.output
        assert "interface I is not converted" in result.output

    def test_rdf_warnings_are_fatal_under_strict(self, tmp_path: Path, monkeypatch) -> None:
        """--strict covers RDF validation warnings too, before anything is written.

        The converter's own output never draws one today, so the validator is stubbed.
        """
        import sys

        from rdf_construct.puml2rdf.validators import (
            Severity,
            ValidationIssue,
            ValidationResult,
        )

        # `rdf_construct.cli` the attribute is the Click group, so take the module itself
        cli_module = sys.modules["rdf_construct.cli"]
        warning = ValidationIssue(Severity.WARNING, "UNTYPED_CLASS", "stubbed")
        monkeypatch.setattr(
            cli_module, "validate_rdf", lambda graph: ValidationResult(issues=[warning])
        )
        text = "@startuml\nclass A\n@enduml\n"

        assert _run(tmp_path, text).exit_code == 0
        (tmp_path / "diagram.ttl").unlink()
        result = _run(tmp_path, text, "--strict")
        assert result.exit_code == 1, result.output
        assert _wrote_nothing(tmp_path)
