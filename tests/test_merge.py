"""Tests for the merge module.

Tests cover:
- Configuration loading and validation
- Conflict detection
- Conflict resolution strategies
- Namespace remapping
- owl:imports handling
- Data migration (simple and complex)
- Output formatting
"""

import pytest
from pathlib import Path
from textwrap import dedent

from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL

# Import from the merge module
from rdf_construct.merge import (
    # Config
    MergeConfig,
    SourceConfig,
    ConflictConfig,
    ConflictStrategy,
    ImportsStrategy,
    MigrationRule,
    load_merge_config,
    create_default_config,
    # Conflicts
    Conflict,
    ConflictType,
    ConflictValue,
    ConflictDetector,
    SourceGraph,
    generate_conflict_marker,
    # Merger
    OntologyMerger,
    MergeResult,
    merge_files,
    # Migrator
    DataMigrator,
    MigrationResult,
    migrate_data_files,
    # Rules
    RuleEngine,
    PatternParser,
    # Formatters
    TextFormatter,
    MarkdownFormatter,
    get_formatter,
)


# Test fixtures
@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def core_ontology(temp_dir):
    """Create a simple core ontology file."""
    content = dedent('''
        @prefix ex: <http://example.org/> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .

        ex:Ontology a owl:Ontology ;
            rdfs:label "Core Ontology" .

        ex:Building a owl:Class ;
            rdfs:label "Building"@en ;
            rdfs:comment "A constructed structure." .

        ex:hasLocation a owl:ObjectProperty ;
            rdfs:domain ex:Building ;
            rdfs:range ex:Place .

        ex:Place a owl:Class ;
            rdfs:label "Place" .
    ''').strip()

    path = temp_dir / "core.ttl"
    path.write_text(content)
    return path


@pytest.fixture
def extension_ontology(temp_dir):
    """Create an extension ontology file."""
    content = dedent('''
        @prefix ex: <http://example.org/> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .

        ex:Ontology a owl:Ontology ;
            rdfs:label "Extension Ontology" .

        ex:CommercialBuilding a owl:Class ;
            rdfs:subClassOf ex:Building ;
            rdfs:label "Commercial Building"@en .

        ex:ResidentialBuilding a owl:Class ;
            rdfs:subClassOf ex:Building ;
            rdfs:label "Residential Building"@en .
    ''').strip()

    path = temp_dir / "extension.ttl"
    path.write_text(content)
    return path


@pytest.fixture
def conflicting_ontology(temp_dir):
    """Create an ontology with conflicting definitions."""
    content = dedent('''
        @prefix ex: <http://example.org/> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .

        ex:Building a owl:Class ;
            rdfs:label "Structure"@en ;
            rdfs:comment "A physical structure." .

        ex:hasLocation a owl:ObjectProperty ;
            rdfs:range ex:Location .
    ''').strip()

    path = temp_dir / "conflicting.ttl"
    path.write_text(content)
    return path


@pytest.fixture
def data_file(temp_dir):
    """Create a data file with instances."""
    content = dedent('''
        @prefix ex: <http://example.org/> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

        ex:building1 a ex:Building ;
            rdfs:label "Office Tower" ;
            ex:hasLocation ex:location1 .

        ex:building2 a ex:Building ;
            rdfs:label "Shopping Centre" ;
            ex:hasLocation ex:location2 .

        ex:location1 a ex:Place ;
            rdfs:label "Downtown" .
    ''').strip()

    path = temp_dir / "data.ttl"
    path.write_text(content)
    return path


# Configuration tests
class TestMergeConfig:
    """Tests for merge configuration."""

    def test_source_config_from_path_string(self):
        """Test creating SourceConfig from a simple path string."""
        config = SourceConfig.from_dict("path/to/file.ttl")
        assert config.path == Path("path/to/file.ttl")
        assert config.priority == 1
        assert config.namespace_remap == {}

    def test_source_config_from_dict(self):
        """Test creating SourceConfig from a dictionary."""
        config = SourceConfig.from_dict({
            "path": "file.ttl",
            "priority": 5,
            "namespace_remap": {"http://old/": "http://new/"},
        })
        assert config.path == Path("file.ttl")
        assert config.priority == 5
        assert "http://old/" in config.namespace_remap

    def test_migration_rule_rename(self):
        """Test creating a rename migration rule."""
        rule = MigrationRule.from_dict({
            "type": "rename",
            "from": "http://old.org/Class",
            "to": "http://new.org/Class",
            "description": "Rename class",
        })
        assert rule.type == "rename"
        assert rule.from_uri == "http://old.org/Class"
        assert rule.to_uri == "http://new.org/Class"

    def test_migration_rule_transform(self):
        """Test creating a transform migration rule."""
        rule = MigrationRule.from_dict({
            "type": "transform",
            "description": "Split name",
            "match": "?s ex:fullName ?name",
            "construct": [
                {"pattern": "?s ex:givenName ?given", "bind": "STRBEFORE(?name, ' ') AS ?given"},
            ],
            "delete_matched": True,
        })
        assert rule.type == "transform"
        assert rule.match == "?s ex:fullName ?name"
        assert len(rule.construct) == 1

    def test_create_default_config(self):
        """Test generating default configuration."""
        yaml_str = create_default_config()
        assert "sources:" in yaml_str
        assert "conflicts:" in yaml_str
        assert "priority" in yaml_str


# Conflict detection tests
class TestConflictDetector:
    """Tests for conflict detection."""

    def test_detect_no_conflicts(self, core_ontology, extension_ontology):
        """Test detection when there are no conflicts."""
        g1 = Graph()
        g1.parse(core_ontology)
        g2 = Graph()
        g2.parse(extension_ontology)

        sources = [
            SourceGraph(graph=g1, path=str(core_ontology), priority=1),
            SourceGraph(graph=g2, path=str(extension_ontology), priority=2),
        ]

        detector = ConflictDetector()
        conflicts = detector.detect_conflicts(sources)

        # Should find conflicts for ex:Ontology rdfs:label (different values)
        # but not for non-overlapping content
        label_conflicts = [c for c in conflicts if str(c.predicate) == str(RDFS.label)]
        # Both have ex:Ontology rdfs:label with different values
        assert any(
            "Ontology" in str(c.subject) for c in label_conflicts
        )

    def test_detect_label_conflict(self, core_ontology, conflicting_ontology):
        """Test detection of conflicting labels."""
        g1 = Graph()
        g1.parse(core_ontology)
        g2 = Graph()
        g2.parse(conflicting_ontology)

        sources = [
            SourceGraph(graph=g1, path=str(core_ontology), priority=1),
            SourceGraph(graph=g2, path=str(conflicting_ontology), priority=2),
        ]

        detector = ConflictDetector()
        conflicts = detector.detect_conflicts(sources)

        # Should find conflict for ex:Building rdfs:label
        building_uri = URIRef("http://example.org/Building")
        building_conflicts = [c for c in conflicts if c.subject == building_uri]
        assert len(building_conflicts) > 0

    def test_detect_range_conflict(self, core_ontology, conflicting_ontology):
        """Test detection of conflicting range declarations."""
        g1 = Graph()
        g1.parse(core_ontology)
        g2 = Graph()
        g2.parse(conflicting_ontology)

        sources = [
            SourceGraph(graph=g1, path=str(core_ontology), priority=1),
            SourceGraph(graph=g2, path=str(conflicting_ontology), priority=2),
        ]

        detector = ConflictDetector()
        conflicts = detector.detect_conflicts(sources)

        # Should find conflict for ex:hasLocation rdfs:range
        property_uri = URIRef("http://example.org/hasLocation")
        range_conflicts = [
            c for c in conflicts
            if c.subject == property_uri and c.predicate == RDFS.range
        ]
        assert len(range_conflicts) == 1
        assert len(range_conflicts[0].values) == 2

    def test_ignore_predicates(self, core_ontology, conflicting_ontology):
        """Test that ignored predicates don't trigger conflicts."""
        g1 = Graph()
        g1.parse(core_ontology)
        g2 = Graph()
        g2.parse(conflicting_ontology)

        sources = [
            SourceGraph(graph=g1, path=str(core_ontology), priority=1),
            SourceGraph(graph=g2, path=str(conflicting_ontology), priority=2),
        ]

        # Ignore label conflicts
        detector = ConflictDetector(ignore_predicates={str(RDFS.label)})
        conflicts = detector.detect_conflicts(sources)

        # Should not find any label conflicts
        label_conflicts = [c for c in conflicts if c.predicate == RDFS.label]
        assert len(label_conflicts) == 0


# Conflict resolution tests
class TestConflictResolution:
    """Tests for conflict resolution strategies."""

    def test_resolve_by_priority(self):
        """Test priority-based resolution."""
        conflict = Conflict(
            subject=URIRef("http://example.org/Test"),
            predicate=RDFS.label,
            values=[
                ConflictValue(Literal("Low"), "low.ttl", 1),
                ConflictValue(Literal("High"), "high.ttl", 5),
            ],
        )

        conflict.resolve_by_priority()

        assert conflict.is_resolved
        assert conflict.resolution is not None
        assert str(conflict.resolution.value) == "High"

    def test_resolve_by_first(self):
        """Test first-wins resolution."""
        conflict = Conflict(
            subject=URIRef("http://example.org/Test"),
            predicate=RDFS.label,
            values=[
                ConflictValue(Literal("First"), "first.ttl", 1),
                ConflictValue(Literal("Second"), "second.ttl", 5),
            ],
        )

        conflict.resolve_by_first()

        assert conflict.is_resolved
        assert str(conflict.resolution.value) == "First"

    def test_resolve_by_last(self):
        """Test last-wins resolution."""
        conflict = Conflict(
            subject=URIRef("http://example.org/Test"),
            predicate=RDFS.label,
            values=[
                ConflictValue(Literal("First"), "first.ttl", 1),
                ConflictValue(Literal("Last"), "last.ttl", 5),
            ],
        )

        conflict.resolve_by_last()

        assert conflict.is_resolved
        assert str(conflict.resolution.value) == "Last"


# Merger tests
class TestOntologyMerger:
    """Tests for the ontology merger."""

    def test_basic_merge(self, core_ontology, extension_ontology, temp_dir):
        """Test basic merge of two ontologies."""
        output_path = temp_dir / "merged.ttl"

        result = merge_files(
            sources=[core_ontology, extension_ontology],
            output=output_path,
        )

        assert result.success
        assert result.merged_graph is not None
        assert output_path.exists()

        # Check that both ontologies' classes are present
        merged = Graph()
        merged.parse(output_path)

        building = URIRef("http://example.org/Building")
        commercial = URIRef("http://example.org/CommercialBuilding")

        assert (building, RDF.type, OWL.Class) in merged
        assert (commercial, RDF.type, OWL.Class) in merged

    def test_merge_with_conflicts(self, core_ontology, conflicting_ontology, temp_dir):
        """Test merge with conflicts."""
        output_path = temp_dir / "merged.ttl"

        result = merge_files(
            sources=[core_ontology, conflicting_ontology],
            output=output_path,
            conflict_strategy="priority",
        )

        assert result.success
        assert len(result.conflicts) > 0

    def test_merge_dry_run(self, core_ontology, extension_ontology, temp_dir):
        """Test dry run doesn't write output."""
        output_path = temp_dir / "merged.ttl"

        result = merge_files(
            sources=[core_ontology, extension_ontology],
            output=output_path,
            dry_run=True,
        )

        assert result.success
        assert not output_path.exists()

    def test_merge_mark_all_strategy(self, core_ontology, conflicting_ontology, temp_dir):
        """Test mark_all leaves conflicts unresolved."""
        output_path = temp_dir / "merged.ttl"

        result = merge_files(
            sources=[core_ontology, conflicting_ontology],
            output=output_path,
            conflict_strategy="mark_all",
        )

        assert result.success
        # All conflicts should be unresolved
        assert len(result.unresolved_conflicts) == len(result.conflicts)


# Data migration tests
class TestDataMigrator:
    """Tests for data migration."""

    def test_simple_uri_substitution(self, data_file, temp_dir):
        """Test simple URI substitution."""
        data = Graph()
        data.parse(data_file)

        migrator = DataMigrator()
        uri_map = {
            URIRef("http://example.org/Building"): URIRef("http://example.org/Structure"),
        }

        result = migrator.migrate(data, uri_map=uri_map)

        assert result.success
        assert result.stats.subjects_updated > 0 or result.stats.objects_updated > 0

        # Check that new class is used
        structure = URIRef("http://example.org/Structure")
        building = URIRef("http://example.org/Building")

        assert (None, RDF.type, structure) in result.migrated_graph
        # Original class should not be present
        assert (None, RDF.type, building) not in result.migrated_graph

    def test_namespace_remap(self, data_file, temp_dir):
        """Test namespace remapping."""
        data = Graph()
        data.parse(data_file)

        migrator = DataMigrator()
        uri_map = migrator.build_uri_map_from_namespaces(
            data,
            {"http://example.org/": "http://newexample.org/"},
        )

        result = migrator.migrate(data, uri_map=uri_map)

        assert result.success

        # Check that new namespace is used
        new_building = URIRef("http://newexample.org/building1")
        old_building = URIRef("http://example.org/building1")

        assert new_building in [s for s, _, _ in result.migrated_graph]
        assert old_building not in [s for s, _, _ in result.migrated_graph]


# Rule engine tests
class TestRuleEngine:
    """Tests for the rule engine."""

    def test_pattern_parser_variable(self):
        """Test parsing patterns with variables."""
        parser = PatternParser()
        s, p, o = parser.parse_pattern("?s ?p ?o")

        assert s == "?s"
        assert p == "?p"
        assert o == "?o"

    def test_pattern_parser_uri(self):
        """Test parsing patterns with URIs."""
        parser = PatternParser()
        s, p, o = parser.parse_pattern("?s <http://example.org/prop> ?o")

        assert s == "?s"
        assert p == URIRef("http://example.org/prop")
        assert o == "?o"

    def test_pattern_parser_type_shorthand(self):
        """Test parsing 'a' shorthand for rdf:type."""
        parser = PatternParser()
        s, p, o = parser.parse_pattern("?s a ?type")

        assert s == "?s"
        assert p == RDF.type
        assert o == "?type"

    def test_rule_engine_find_matches(self, data_file):
        """Test finding matches in a graph."""
        data = Graph()
        data.parse(data_file)

        engine = RuleEngine()
        engine.set_namespaces(data)

        matches = engine._find_matches(data, "?s a ex:Building")

        # Should find the building instances
        assert len(matches) >= 2


# Formatter tests
class TestFormatters:
    """Tests for output formatters."""

    def test_text_formatter_merge_result(self):
        """Test text formatting of merge results."""
        result = MergeResult(
            source_stats={"core.ttl": 100, "ext.ttl": 50},
            total_triples=140,
            conflicts=[],
            success=True,
        )

        formatter = TextFormatter(use_colour=False)
        output = formatter.format_merge_result(result)

        assert "core.ttl" in output
        assert "100" in output
        assert "140" in output

    def test_markdown_formatter_conflict_report(self):
        """Test Markdown formatting of conflict report."""
        conflicts = [
            Conflict(
                subject=URIRef("http://example.org/Test"),
                predicate=RDFS.label,
                values=[
                    ConflictValue(Literal("Value1"), "a.ttl", 1),
                    ConflictValue(Literal("Value2"), "b.ttl", 2),
                ],
            ),
        ]

        formatter = MarkdownFormatter()
        output = formatter.format_conflict_report(conflicts)

        assert "# Merge Conflict Report" in output
        assert "Unresolved" in output
        assert "Value1" in output
        assert "Value2" in output

    def test_get_formatter(self):
        """Test formatter factory function."""
        text = get_formatter("text")
        assert isinstance(text, TextFormatter)

        md = get_formatter("markdown")
        assert isinstance(md, MarkdownFormatter)

        md2 = get_formatter("md")
        assert isinstance(md2, MarkdownFormatter)

    def test_get_formatter_invalid(self):
        """Test error for invalid formatter."""
        with pytest.raises(ValueError):
            get_formatter("invalid")


# Integration tests
class TestMergeIntegration:
    """Integration tests for the complete merge workflow."""

    def test_full_merge_workflow(self, core_ontology, extension_ontology, data_file, temp_dir):
        """Test complete merge with data migration."""
        merged_output = temp_dir / "merged.ttl"
        data_output = temp_dir / "migrated.ttl"
        report_output = temp_dir / "report.md"

        # Merge ontologies
        merge_result = merge_files(
            sources=[core_ontology, extension_ontology],
            output=merged_output,
            priorities=[1, 2],
        )

        assert merge_result.success
        assert merged_output.exists()

        # Generate conflict report
        formatter = MarkdownFormatter()
        report = formatter.format_merge_result(merge_result)
        report_output.write_text(report)

        assert report_output.exists()

        # Migrate data (no actual changes needed for this test)
        data = Graph()
        data.parse(data_file)

        migrator = DataMigrator()
        migration_result = migrator.migrate(data)

        assert migration_result.success

    def test_merge_with_namespace_remap(self, temp_dir):
        """Test merge with namespace remapping."""
        # Create ontology with old namespace
        old_content = dedent('''
            @prefix old: <http://old.example.org/> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .

            old:Thing a owl:Class ;
                rdfs:label "Thing" .
        ''').strip()

        old_path = temp_dir / "old.ttl"
        old_path.write_text(old_content)

        # Create config with namespace remapping
        config = MergeConfig(
            sources=[
                SourceConfig(
                    path=old_path,
                    priority=1,
                    namespace_remap={"http://old.example.org/": "http://new.example.org/"},
                ),
            ],
            output=None,
        )

        merger = OntologyMerger(config)
        result = merger.merge()

        assert result.success

        # Check that new namespace is used
        new_thing = URIRef("http://new.example.org/Thing")
        old_thing = URIRef("http://old.example.org/Thing")

        assert (new_thing, RDF.type, OWL.Class) in result.merged_graph
        assert (old_thing, RDF.type, OWL.Class) not in result.merged_graph


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
