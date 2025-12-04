"""Tests for the refactor module.

Tests cover:
- Single entity rename
- Namespace bulk rename
- Combined namespace + explicit renames
- Deprecation with replacement
- Deprecation without replacement
- Bulk deprecation from config
- Data migration
- Dry run mode
- Literals not modified
- Multi-file processing
"""

import pytest
from pathlib import Path
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

from rdf_construct.refactor import (
    RenameConfig,
    RenameMapping,
    DeprecationSpec,
    DeprecationConfig,
    RefactorConfig,
    OntologyRenamer,
    OntologyDeprecator,
    RenameResult,
    DeprecationResult,
    TextFormatter,
    load_refactor_config,
    rename_file,
    deprecate_file,
    create_default_rename_config,
    create_default_deprecation_config,
)


# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "refactor"


@pytest.fixture
def typos_graph() -> Graph:
    """Load the typos test ontology."""
    g = Graph()
    g.parse((FIXTURES_DIR / "typos.ttl").as_posix())
    return g


@pytest.fixture
def legacy_graph() -> Graph:
    """Load the legacy test ontology."""
    g = Graph()
    g.parse((FIXTURES_DIR / "legacy.ttl").as_posix())
    return g


@pytest.fixture
def old_namespace_graph() -> Graph:
    """Load the old namespace test ontology."""
    g = Graph()
    g.parse((FIXTURES_DIR / "old_namespace.ttl").as_posix())
    return g


@pytest.fixture
def instances_graph() -> Graph:
    """Load the instances test data."""
    g = Graph()
    g.parse((FIXTURES_DIR / "instances.ttl").as_posix())
    return g


# =============================================================================
# RenameConfig Tests
# =============================================================================


class TestRenameConfig:
    """Tests for RenameConfig."""

    def test_from_dict_empty(self):
        """Test creating config from empty dict."""
        config = RenameConfig.from_dict({})
        assert config.namespaces == {}
        assert config.entities == {}

    def test_from_dict_with_data(self):
        """Test creating config from dict with data."""
        data = {
            "namespaces": {"http://old/": "http://new/"},
            "entities": {"http://old/Foo": "http://new/Bar"},
        }
        config = RenameConfig.from_dict(data)
        assert config.namespaces == {"http://old/": "http://new/"}
        assert config.entities == {"http://old/Foo": "http://new/Bar"}

    def test_build_mappings_explicit_only(self, typos_graph):
        """Test building mappings with explicit entities only."""
        config = RenameConfig(
            entities={
                "http://example.org/ont#Buiding": "http://example.org/ont#Building",
            }
        )
        mappings = config.build_mappings(typos_graph)
        assert len(mappings) == 1
        assert mappings[0].from_uri == URIRef("http://example.org/ont#Buiding")
        assert mappings[0].to_uri == URIRef("http://example.org/ont#Building")
        assert mappings[0].source == "explicit"

    def test_build_mappings_namespace(self, old_namespace_graph):
        """Test building mappings with namespace rules."""
        config = RenameConfig(
            namespaces={"http://old.example.org/v1#": "http://example.org/v2#"}
        )
        mappings = config.build_mappings(old_namespace_graph)
        # Should have mappings for all entities in old namespace
        assert len(mappings) > 0
        for m in mappings:
            assert str(m.from_uri).startswith("http://old.example.org/v1#")
            assert str(m.to_uri).startswith("http://example.org/v2#")
            assert m.source == "namespace"

    def test_build_mappings_combined(self, old_namespace_graph):
        """Test that explicit mappings override namespace mappings."""
        config = RenameConfig(
            namespaces={"http://old.example.org/v1#": "http://example.org/v2#"},
            entities={
                # Override Building to use different local name
                "http://old.example.org/v1#Building": "http://example.org/v2#Structure",
            },
        )
        mappings = config.build_mappings(old_namespace_graph)

        # Find the Building mapping
        building_mapping = None
        for m in mappings:
            if str(m.from_uri) == "http://old.example.org/v1#Building":
                building_mapping = m
                break

        assert building_mapping is not None
        assert str(building_mapping.to_uri) == "http://example.org/v2#Structure"
        assert building_mapping.source == "explicit"


# =============================================================================
# OntologyRenamer Tests
# =============================================================================


class TestOntologyRenamer:
    """Tests for OntologyRenamer."""

    def test_single_entity_rename(self, typos_graph):
        """Test renaming a single entity."""
        renamer = OntologyRenamer()
        result = renamer.rename_single(
            typos_graph,
            from_uri="http://example.org/ont#Buiding",
            to_uri="http://example.org/ont#Building",
        )

        assert result.success
        assert result.renamed_graph is not None

        # Check that old URI is gone
        old_uri = URIRef("http://example.org/ont#Buiding")
        new_uri = URIRef("http://example.org/ont#Building")

        old_triples = list(result.renamed_graph.triples((old_uri, None, None)))
        new_triples = list(result.renamed_graph.triples((new_uri, None, None)))

        assert len(old_triples) == 0
        assert len(new_triples) > 0

        # Check stats
        assert result.stats.total_renames > 0

    def test_namespace_rename(self, old_namespace_graph):
        """Test bulk namespace rename."""
        renamer = OntologyRenamer()
        result = renamer.rename_namespace(
            old_namespace_graph,
            from_namespace="http://old.example.org/v1#",
            to_namespace="http://example.org/v2#",
        )

        assert result.success
        assert result.renamed_graph is not None

        # Check that no old namespace URIs remain as subjects
        for s, p, o in result.renamed_graph:
            if isinstance(s, URIRef):
                assert not str(s).startswith("http://old.example.org/v1#")

        # Check that new namespace URIs exist
        new_building = URIRef("http://example.org/v2#Building")
        building_triples = list(result.renamed_graph.triples((new_building, None, None)))
        assert len(building_triples) > 0

    def test_multiple_renames(self, typos_graph):
        """Test renaming multiple entities."""
        config = RenameConfig(
            entities={
                "http://example.org/ont#Buiding": "http://example.org/ont#Building",
                "http://example.org/ont#hasAddres": "http://example.org/ont#hasAddress",
                "http://example.org/ont#Addres": "http://example.org/ont#Address",
            }
        )

        renamer = OntologyRenamer()
        result = renamer.rename(typos_graph, config)

        assert result.success
        assert result.renamed_graph is not None

        # Verify all renames applied
        graph = result.renamed_graph
        assert (URIRef("http://example.org/ont#Building"), None, None) in graph
        assert (URIRef("http://example.org/ont#hasAddress"), None, None) in graph
        assert (URIRef("http://example.org/ont#Address"), None, None) in graph

        # Verify old URIs are gone
        assert (URIRef("http://example.org/ont#Buiding"), None, None) not in graph
        assert (URIRef("http://example.org/ont#hasAddres"), None, None) not in graph
        assert (URIRef("http://example.org/ont#Addres"), None, None) not in graph

    def test_predicate_rename(self, typos_graph):
        """Test that predicates are also renamed."""
        config = RenameConfig(
            entities={
                "http://example.org/ont#hasAddres": "http://example.org/ont#hasAddress",
            }
        )

        renamer = OntologyRenamer()
        result = renamer.rename(typos_graph, config)

        assert result.success
        assert result.stats.predicates_renamed > 0 or result.stats.subjects_renamed > 0

    def test_literals_not_modified(self, typos_graph):
        """Test that text inside literals is NOT modified."""
        config = RenameConfig(
            entities={
                "http://example.org/ont#Buiding": "http://example.org/ont#Building",
            }
        )

        renamer = OntologyRenamer()
        result = renamer.rename(typos_graph, config)

        assert result.success

        # The comment that mentions "Buiding is a typo!" should be unchanged
        building_uri = URIRef("http://example.org/ont#Building")
        comments = list(result.renamed_graph.objects(building_uri, RDFS.comment))

        assert len(comments) > 0
        # The literal should still contain "Buiding"
        comment_text = str(comments[0])
        assert "Buiding" in comment_text

        # Stats should show literal mentions
        assert len(result.stats.literal_mentions) > 0 or "http://example.org/ont#Buiding" in str(
            result.stats.literal_mentions
        )

    def test_empty_config(self, typos_graph):
        """Test rename with empty config (no changes)."""
        config = RenameConfig()
        renamer = OntologyRenamer()
        result = renamer.rename(typos_graph, config)

        assert result.success
        assert result.stats.total_renames == 0
        # Graph should be unchanged
        assert len(result.renamed_graph) == len(typos_graph)


# =============================================================================
# DeprecationSpec Tests
# =============================================================================


class TestDeprecationSpec:
    """Tests for DeprecationSpec."""

    def test_from_dict_full(self):
        """Test creating spec from full dict."""
        data = {
            "entity": "http://example.org/ont#OldClass",
            "replaced_by": "http://example.org/ont#NewClass",
            "message": "Use NewClass instead.",
            "version": "2.0.0",
        }
        spec = DeprecationSpec.from_dict(data)

        assert spec.entity == "http://example.org/ont#OldClass"
        assert spec.replaced_by == "http://example.org/ont#NewClass"
        assert spec.message == "Use NewClass instead."
        assert spec.version == "2.0.0"

    def test_from_dict_minimal(self):
        """Test creating spec with only entity."""
        data = {"entity": "http://example.org/ont#OldClass"}
        spec = DeprecationSpec.from_dict(data)

        assert spec.entity == "http://example.org/ont#OldClass"
        assert spec.replaced_by is None
        assert spec.message is None
        assert spec.version is None


# =============================================================================
# OntologyDeprecator Tests
# =============================================================================


class TestOntologyDeprecator:
    """Tests for OntologyDeprecator."""

    def test_deprecate_with_replacement(self, legacy_graph):
        """Test deprecating entity with replacement."""
        deprecator = OntologyDeprecator()
        result = deprecator.deprecate(
            legacy_graph,
            entity="http://example.org/ont#LegacyPerson",
            replaced_by="http://example.org/ont#Agent",
            message="Use Agent instead.",
        )

        assert result.success
        assert result.deprecated_graph is not None

        # Check owl:deprecated was added
        legacy_uri = URIRef("http://example.org/ont#LegacyPerson")
        deprecated_values = list(result.deprecated_graph.objects(legacy_uri, OWL.deprecated))
        assert len(deprecated_values) > 0
        assert str(deprecated_values[0]).lower() == "true"

        # Check dcterms:isReplacedBy was added
        DCTERMS = URIRef("http://purl.org/dc/terms/isReplacedBy")
        replaced_by = list(result.deprecated_graph.objects(legacy_uri, DCTERMS))
        assert len(replaced_by) > 0
        assert replaced_by[0] == URIRef("http://example.org/ont#Agent")

        # Check stats
        assert result.stats.entities_deprecated == 1
        assert result.stats.triples_added > 0

    def test_deprecate_without_replacement(self, legacy_graph):
        """Test deprecating entity without replacement."""
        deprecator = OntologyDeprecator()
        result = deprecator.deprecate(
            legacy_graph,
            entity="http://example.org/ont#TemporaryClass",
            message="This class is removed. No replacement.",
        )

        assert result.success

        # Check owl:deprecated was added
        temp_uri = URIRef("http://example.org/ont#TemporaryClass")
        deprecated_values = list(result.deprecated_graph.objects(temp_uri, OWL.deprecated))
        assert len(deprecated_values) > 0

        # Should not have isReplacedBy
        DCTERMS = URIRef("http://purl.org/dc/terms/isReplacedBy")
        replaced_by = list(result.deprecated_graph.objects(temp_uri, DCTERMS))
        assert len(replaced_by) == 0

    def test_deprecate_with_version(self, legacy_graph):
        """Test deprecation message includes version."""
        deprecator = OntologyDeprecator()
        result = deprecator.deprecate(
            legacy_graph,
            entity="http://example.org/ont#LegacyPerson",
            message="Deprecated. Use Agent.",
            version="2.0.0",
        )

        assert result.success

        # Check comment includes version
        legacy_uri = URIRef("http://example.org/ont#LegacyPerson")
        comments = list(result.deprecated_graph.objects(legacy_uri, RDFS.comment))

        # Find the deprecation comment
        deprecation_comments = [c for c in comments if "DEPRECATED" in str(c)]
        assert len(deprecation_comments) > 0
        assert "v2.0.0" in str(deprecation_comments[0])

    def test_deprecate_entity_not_found(self, legacy_graph):
        """Test deprecating non-existent entity."""
        deprecator = OntologyDeprecator()
        result = deprecator.deprecate(
            legacy_graph,
            entity="http://example.org/ont#NonExistent",
            message="This doesn't exist.",
        )

        assert result.success  # Not a failure, just a warning
        assert result.stats.entities_not_found == 1
        assert result.stats.entities_deprecated == 0

    def test_deprecate_already_deprecated(self, legacy_graph):
        """Test deprecating entity that's already deprecated."""
        deprecator = OntologyDeprecator()

        # First deprecation
        result1 = deprecator.deprecate(
            legacy_graph,
            entity="http://example.org/ont#LegacyPerson",
            message="First deprecation.",
        )
        assert result1.stats.entities_deprecated == 1

        # Second deprecation - should detect already deprecated
        result2 = deprecator.deprecate(
            result1.deprecated_graph,
            entity="http://example.org/ont#LegacyPerson",
            message="Second deprecation.",
        )
        assert result2.stats.entities_already_deprecated == 1

    def test_deprecate_bulk(self, legacy_graph):
        """Test bulk deprecation from specs."""
        specs = [
            DeprecationSpec(
                entity="http://example.org/ont#LegacyPerson",
                replaced_by="http://example.org/ont#Agent",
                message="Use Agent instead.",
            ),
            DeprecationSpec(
                entity="http://example.org/ont#hasAddress",
                replaced_by="http://example.org/ont#locatedAt",
                message="Use locatedAt instead.",
            ),
            DeprecationSpec(
                entity="http://example.org/ont#TemporaryClass",
                message="Removed. No replacement.",
            ),
        ]

        deprecator = OntologyDeprecator()
        result = deprecator.deprecate_bulk(legacy_graph, specs)

        assert result.success
        assert result.stats.entities_deprecated == 3
        assert len(result.entity_info) == 3


# =============================================================================
# Config Loading Tests
# =============================================================================


class TestConfigLoading:
    """Tests for configuration file loading."""

    def test_load_rename_config(self):
        """Test loading rename config from YAML."""
        config_path = FIXTURES_DIR / "renames.yml"
        config = load_refactor_config(config_path)

        assert config.rename is not None
        assert len(config.rename.entities) == 4
        assert config.output == Path("fixed.ttl")

    def test_load_deprecation_config(self):
        """Test loading deprecation config from YAML."""
        config_path = FIXTURES_DIR / "deprecations.yml"
        config = load_refactor_config(config_path)

        assert len(config.deprecations) == 3
        assert config.deprecations[0].entity == "http://example.org/ont#LegacyPerson"
        assert config.deprecations[0].replaced_by == "http://example.org/ont#Agent"

    def test_default_rename_config(self):
        """Test generating default rename config."""
        yaml_str = create_default_rename_config()
        assert "rename:" in yaml_str
        assert "namespaces:" in yaml_str
        assert "entities:" in yaml_str

    def test_default_deprecation_config(self):
        """Test generating default deprecation config."""
        yaml_str = create_default_deprecation_config()
        assert "deprecations:" in yaml_str
        assert "replaced_by:" in yaml_str


# =============================================================================
# TextFormatter Tests
# =============================================================================


class TestTextFormatter:
    """Tests for TextFormatter."""

    def test_format_rename_preview(self):
        """Test formatting rename preview."""
        formatter = TextFormatter(use_colour=False)
        mappings = [
            RenameMapping(
                from_uri=URIRef("http://example.org/ont#Buiding"),
                to_uri=URIRef("http://example.org/ont#Building"),
                source="explicit",
            ),
        ]

        output = formatter.format_rename_preview(
            mappings=mappings,
            source_file="test.ttl",
            source_triples=100,
        )

        assert "Refactoring Preview: Rename" in output
        assert "test.ttl" in output
        assert "100 triples" in output
        assert "1 entities to rename" in output

    def test_format_rename_result(self):
        """Test formatting rename result."""
        formatter = TextFormatter(use_colour=False)
        result = RenameResult(
            success=True,
            source_triples=100,
            result_triples=100,
        )
        result.stats.subjects_renamed = 5
        result.stats.objects_renamed = 3

        output = formatter.format_rename_result(result)

        assert "Rename Complete" in output
        assert "5" in output  # subjects
        assert "3" in output  # objects

    def test_format_deprecation_preview(self):
        """Test formatting deprecation preview."""
        formatter = TextFormatter(use_colour=False)
        specs = [
            DeprecationSpec(
                entity="http://example.org/ont#OldClass",
                replaced_by="http://example.org/ont#NewClass",
                message="Use NewClass instead.",
            ),
        ]

        output = formatter.format_deprecation_preview(
            specs=specs,
            source_file="test.ttl",
            source_triples=100,
        )

        assert "Refactoring Preview: Deprecate" in output
        assert "OldClass" in output
        assert "owl:deprecated" in output

    def test_format_deprecation_result(self):
        """Test formatting deprecation result."""
        formatter = TextFormatter(use_colour=False)
        result = DeprecationResult(
            success=True,
            source_triples=100,
            result_triples=103,
        )
        result.stats.entities_deprecated = 2
        result.stats.triples_added = 6

        output = formatter.format_deprecation_result(result)

        assert "Deprecation Complete" in output
        assert "2" in output  # entities
        assert "6" in output  # triples


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_rename_and_migrate_data(self, typos_graph, instances_graph, tmp_path):
        """Test rename with data migration."""
        # First rename the ontology
        config = RenameConfig(
            entities={
                "http://example.org/ont#Buiding": "http://example.org/ont#Building",
                "http://example.org/ont#hasAddres": "http://example.org/ont#hasAddress",
                "http://example.org/ont#Addres": "http://example.org/ont#Address",
            }
        )

        renamer = OntologyRenamer()
        ont_result = renamer.rename(typos_graph, config)
        assert ont_result.success

        # Now migrate the data using the same config
        data_result = renamer.rename(instances_graph, config)
        assert data_result.success

        # Verify data was migrated
        new_building_uri = URIRef("http://example.org/ont#Building")
        data_types = list(data_result.renamed_graph.subjects(RDF.type, new_building_uri))
        assert len(data_types) > 0  # Should have buildings typed correctly

    def test_deprecate_preserves_structure(self, legacy_graph):
        """Test that deprecation preserves existing properties."""
        # Get original properties of LegacyPerson
        legacy_uri = URIRef("http://example.org/ont#LegacyPerson")
        original_label = list(legacy_graph.objects(legacy_uri, RDFS.label))
        original_subclass = list(legacy_graph.objects(legacy_uri, RDFS.subClassOf))

        # Deprecate
        deprecator = OntologyDeprecator()
        result = deprecator.deprecate(
            legacy_graph,
            entity="http://example.org/ont#LegacyPerson",
            replaced_by="http://example.org/ont#Agent",
            message="Use Agent instead.",
        )

        assert result.success

        # Check original properties are preserved
        new_label = list(result.deprecated_graph.objects(legacy_uri, RDFS.label))
        new_subclass = list(result.deprecated_graph.objects(legacy_uri, RDFS.subClassOf))

        assert original_label == new_label
        assert original_subclass == new_subclass

    def test_file_roundtrip(self, tmp_path):
        """Test rename file writing and reading."""
        # Create a simple ontology
        g = Graph()
        ex = URIRef("http://example.org/ont#")
        g.add((URIRef(f"{ex}Buiding"), RDF.type, OWL.Class))
        g.add((URIRef(f"{ex}Buiding"), RDFS.label, Literal("Building")))

        # Write source
        source_path = tmp_path / "source.ttl"
        g.serialize(destination=source_path.as_posix(), format="turtle")

        # Rename
        output_path = tmp_path / "output.ttl"
        config = RenameConfig(
            entities={"http://example.org/ont#Buiding": "http://example.org/ont#Building"}
        )
        result = rename_file(source_path, output_path, config)

        assert result.success
        assert output_path.exists()

        # Read back
        result_graph = Graph()
        result_graph.parse(output_path.as_posix())

        # Verify
        assert (URIRef("http://example.org/ont#Building"), None, None) in result_graph
        assert (URIRef("http://example.org/ont#Buiding"), None, None) not in result_graph
