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
