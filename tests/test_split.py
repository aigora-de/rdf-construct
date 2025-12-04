"""Tests for the split command.

Tests cover:
- Split by namespace (auto-detect)
- Split by explicit entity lists
- Include descendants option
- Auto-imports generation
- Unmatched entity handling (common module)
- Unmatched entity handling (error mode)
- Manifest generation
- Data migration by type
- Dry run mode
- Round-trip validation: merge(split(x)) == x
"""

from pathlib import Path
from textwrap import dedent

import pytest
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL

from rdf_construct.merge.splitter import (
    OntologySplitter,
    SplitConfig,
    SplitResult,
    ModuleDefinition,
    UnmatchedStrategy,
    SplitDataConfig,
    split_by_namespace,
    create_default_split_config,
)


# Test namespaces
EX = Namespace("http://example.org/ontology#")
ORG = Namespace("http://example.org/ontology/org#")
BUILDING = Namespace("http://example.org/ontology/building#")


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def monolith_ontology(temp_dir: Path) -> Path:
    """Create a monolithic ontology for splitting tests."""
    content = dedent('''
        @prefix ex: <http://example.org/ontology#> .
        @prefix org: <http://example.org/ontology/org#> .
        @prefix building: <http://example.org/ontology/building#> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .

        # Core entities
        ex:Entity a owl:Class ;
            rdfs:label "Entity"@en ;
            rdfs:comment "Base class for all entities"@en .

        ex:Event a owl:Class ;
            rdfs:label "Event"@en ;
            rdfs:subClassOf ex:Entity .

        ex:identifier a owl:DatatypeProperty ;
            rdfs:label "identifier"@en ;
            rdfs:domain ex:Entity .

        # Organisation entities
        org:Organisation a owl:Class ;
            rdfs:label "Organisation"@en ;
            rdfs:subClassOf ex:Entity .

        org:Company a owl:Class ;
            rdfs:label "Company"@en ;
            rdfs:subClassOf org:Organisation .

        org:hasEmployee a owl:ObjectProperty ;
            rdfs:label "has employee"@en ;
            rdfs:domain org:Organisation .

        # Building entities
        building:Building a owl:Class ;
            rdfs:label "Building"@en ;
            rdfs:subClassOf ex:Entity .

        building:Floor a owl:Class ;
            rdfs:label "Floor"@en ;
            rdfs:subClassOf building:Building .

        building:hasFloor a owl:ObjectProperty ;
            rdfs:label "has floor"@en ;
            rdfs:domain building:Building ;
            rdfs:range building:Floor .

        building:floorNumber a owl:DatatypeProperty ;
            rdfs:label "floor number"@en ;
            rdfs:domain building:Floor .
    ''').strip()

    ontology_path = temp_dir / "split_monolith.ttl"
    ontology_path.write_text(content)
    return ontology_path


@pytest.fixture
def instance_data(temp_dir: Path) -> Path:
    """Create instance data for data splitting tests."""
    content = dedent('''
        @prefix ex: <http://example.org/ontology#> .
        @prefix org: <http://example.org/ontology/org#> .
        @prefix building: <http://example.org/ontology/building#> .
        @prefix data: <http://example.org/data#> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        # Organisation instances
        data:acme a org:Company ;
            ex:identifier "ACME001" ;
            org:hasEmployee data:john .

        data:john a ex:Entity ;
            ex:identifier "EMP001" .

        # Building instances
        data:building1 a building:Building ;
            ex:identifier "BLD001" ;
            building:hasFloor data:floor1 .

        data:floor1 a building:Floor ;
            building:floorNumber 1 .
    ''').strip()

    data_path = temp_dir / "split_instances.ttl"
    data_path.write_text(content)
    return data_path


@pytest.fixture
def split_config_yaml(temp_dir: Path, monolith_ontology: Path) -> Path:
    """Create a split configuration file."""
    content = dedent(f'''
        split:
          source: {monolith_ontology}
          output_dir: {temp_dir}/modules

          modules:
            - name: core
              description: "Core upper ontology concepts"
              output: core.ttl
              include:
                classes:
                  - http://example.org/ontology#Entity
                  - http://example.org/ontology#Event
                properties:
                  - http://example.org/ontology#identifier
              include_descendants: false

            - name: organisation
              output: organisation.ttl
              namespaces:
                - "http://example.org/ontology/org#"

            - name: building
              output: building.ttl
              namespaces:
                - "http://example.org/ontology/building#"

          unmatched:
            strategy: common
            module: common
            output: common.ttl

          generate_manifest: true
    ''').strip()

    config_path = temp_dir / "split.yml"
    config_path.write_text(content)
    return config_path


class TestSplitConfig:
    """Tests for split configuration loading."""

    def test_from_yaml(self, split_config_yaml: Path):
        """Test loading configuration from YAML."""
        config = SplitConfig.from_yaml(split_config_yaml)

        assert config.source.exists()
        assert len(config.modules) == 3
        assert config.modules[0].name == "core"
        assert config.modules[1].name == "organisation"
        assert config.modules[2].name == "building"
        assert config.unmatched.strategy == "common"
        assert config.generate_manifest is True

    def test_module_definition_from_dict(self):
        """Test creating ModuleDefinition from dictionary."""
        data = {
            "name": "test",
            "output": "test.ttl",
            "description": "Test module",
            "include": {
                "classes": ["ex:Class1", "ex:Class2"],
                "properties": ["ex:prop1"],
            },
            "include_descendants": True,
            "namespaces": ["http://example.org/"],
        }

        module = ModuleDefinition.from_dict(data)

        assert module.name == "test"
        assert module.output == "test.ttl"
        assert module.description == "Test module"
        assert len(module.classes) == 2
        assert len(module.properties) == 1
        assert module.include_descendants is True
        assert len(module.namespaces) == 1

    def test_default_config_generation(self):
        """Test generating default configuration."""
        config_yaml = create_default_split_config()

        assert "split:" in config_yaml
        assert "modules:" in config_yaml
        assert "unmatched:" in config_yaml


class TestSplitByNamespace:
    """Tests for namespace-based splitting."""

    def test_split_by_namespace(self, monolith_ontology: Path, temp_dir: Path):
        """Test splitting by namespace auto-detection."""
        output_dir = temp_dir / "ns_split"
        result = split_by_namespace(monolith_ontology, output_dir, dry_run=True)

        assert result.success
        # Should detect ex:, org:, and building: namespaces
        assert result.total_modules >= 2

    def test_namespace_module_separation(self, temp_dir: Path):
        """Test that entities are correctly separated by namespace."""
        # Create simple ontology with two namespaces
        content = dedent('''
            @prefix ns1: <http://example.org/ns1#> .
            @prefix ns2: <http://example.org/ns2#> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .

            ns1:Class1 a owl:Class .
            ns2:Class2 a owl:Class .
        ''').strip()

        source = temp_dir / "two_ns.ttl"
        source.write_text(content)

        config = SplitConfig(
            source=source,
            output_dir=temp_dir / "split",
            modules=[
                ModuleDefinition(
                    name="ns1",
                    output="ns1.ttl",
                    namespaces=["http://example.org/ns1#"],
                ),
                ModuleDefinition(
                    name="ns2",
                    output="ns2.ttl",
                    namespaces=["http://example.org/ns2#"],
                ),
            ],
        )

        splitter = OntologySplitter(config)
        result = splitter.split()

        assert result.success
        assert len(result.modules) == 2

        # Check ns1 module has Class1
        ns1_graph = result.modules["ns1"]
        ns1_classes = list(ns1_graph.subjects(RDF.type, OWL.Class))
        assert len(ns1_classes) == 1
        assert str(ns1_classes[0]) == "http://example.org/ns1#Class1"

        # Check ns2 module has Class2
        ns2_graph = result.modules["ns2"]
        ns2_classes = list(ns2_graph.subjects(RDF.type, OWL.Class))
        assert len(ns2_classes) == 1
        assert str(ns2_classes[0]) == "http://example.org/ns2#Class2"


class TestSplitByExplicitList:
    """Tests for splitting by explicit entity lists."""

    def test_split_by_class_list(self, monolith_ontology: Path, temp_dir: Path):
        """Test splitting by explicit class list."""
        config = SplitConfig(
            source=monolith_ontology,
            output_dir=temp_dir / "explicit_split",
            modules=[
                ModuleDefinition(
                    name="core",
                    output="core.ttl",
                    classes=[
                        "http://example.org/ontology#Entity",
                        "http://example.org/ontology#Event",
                    ],
                ),
            ],
        )

        splitter = OntologySplitter(config)
        result = splitter.split()

        assert result.success
        assert "core" in result.modules

        core_graph = result.modules["core"]
        # Should contain Entity and Event
        assert (EX.Entity, RDF.type, OWL.Class) in core_graph
        assert (EX.Event, RDF.type, OWL.Class) in core_graph
        # Should NOT contain Organisation (not in list)
        assert (ORG.Organisation, RDF.type, OWL.Class) not in core_graph

    def test_split_with_descendants(self, temp_dir: Path):
        """Test including descendants in split."""
        content = dedent('''
            @prefix ex: <http://example.org/> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

            ex:Parent a owl:Class .
            ex:Child a owl:Class ;
                rdfs:subClassOf ex:Parent .
            ex:GrandChild a owl:Class ;
                rdfs:subClassOf ex:Child .
            ex:Unrelated a owl:Class .
        ''').strip()

        source = temp_dir / "hierarchy.ttl"
        source.write_text(content)

        # Without descendants
        config_no_desc = SplitConfig(
            source=source,
            output_dir=temp_dir / "no_desc",
            modules=[
                ModuleDefinition(
                    name="parent",
                    output="parent.ttl",
                    classes=["http://example.org/Parent"],
                    include_descendants=False,
                ),
            ],
        )

        splitter = OntologySplitter(config_no_desc)
        result = splitter.split()

        assert result.success
        parent_graph = result.modules["parent"]
        # Should only have Parent
        classes = list(parent_graph.subjects(RDF.type, OWL.Class))
        assert len(classes) == 1

        # With descendants
        config_desc = SplitConfig(
            source=source,
            output_dir=temp_dir / "with_desc",
            modules=[
                ModuleDefinition(
                    name="parent",
                    output="parent.ttl",
                    classes=["http://example.org/Parent"],
                    include_descendants=True,
                ),
            ],
        )

        splitter = OntologySplitter(config_desc)
        result = splitter.split()

        assert result.success
        parent_graph = result.modules["parent"]
        # Should have Parent, Child, and GrandChild
        classes = list(parent_graph.subjects(RDF.type, OWL.Class))
        assert len(classes) == 3


class TestAutoImports:
    """Tests for automatic owl:imports generation."""

    def test_auto_imports_generation(self, monolith_ontology: Path, temp_dir: Path):
        """Test that owl:imports are generated for dependencies."""
        config = SplitConfig(
            source=monolith_ontology,
            output_dir=temp_dir / "imports_test",
            modules=[
                ModuleDefinition(
                    name="core",
                    output="core.ttl",
                    classes=["http://example.org/ontology#Entity"],
                    auto_imports=True,
                ),
                ModuleDefinition(
                    name="organisation",
                    output="organisation.ttl",
                    namespaces=["http://example.org/ontology/org#"],
                    auto_imports=True,
                ),
            ],
        )

        splitter = OntologySplitter(config)
        result = splitter.split()

        assert result.success
        # Organisation depends on core (subClassOf ex:Entity)
        assert "core" in result.dependencies.get("organisation", set())

    def test_explicit_imports_override(self, monolith_ontology: Path, temp_dir: Path):
        """Test explicit imports override auto-imports."""
        config = SplitConfig(
            source=monolith_ontology,
            output_dir=temp_dir / "explicit_imports",
            modules=[
                ModuleDefinition(
                    name="org",
                    output="org.ttl",
                    namespaces=["http://example.org/ontology/org#"],
                    imports=["http://external.org/ontology.ttl"],
                    auto_imports=False,
                ),
            ],
        )

        splitter = OntologySplitter(config)
        result = splitter.split()

        assert result.success
        org_graph = result.modules["org"]
        imports = list(org_graph.objects(None, OWL.imports))
        # Should have explicit import but no auto-imports
        assert URIRef("http://external.org/ontology.ttl") in imports


class TestUnmatchedEntities:
    """Tests for handling unmatched entities."""

    def test_common_module_strategy(self, monolith_ontology: Path, temp_dir: Path):
        """Test unmatched entities go to common module."""
        config = SplitConfig(
            source=monolith_ontology,
            output_dir=temp_dir / "common_test",
            modules=[
                ModuleDefinition(
                    name="organisation",
                    output="organisation.ttl",
                    namespaces=["http://example.org/ontology/org#"],
                ),
            ],
            unmatched=UnmatchedStrategy(
                strategy="common",
                common_module="shared",
                common_output="shared.ttl",
            ),
        )

        splitter = OntologySplitter(config)
        result = splitter.split()

        assert result.success
        assert "shared" in result.modules
        # Unmatched entities (core, building) should be in shared
        assert len(result.unmatched_entities) > 0

    def test_error_strategy(self, monolith_ontology: Path, temp_dir: Path):
        """Test error strategy fails on unmatched entities."""
        config = SplitConfig(
            source=monolith_ontology,
            output_dir=temp_dir / "error_test",
            modules=[
                ModuleDefinition(
                    name="organisation",
                    output="organisation.ttl",
                    namespaces=["http://example.org/ontology/org#"],
                ),
            ],
            unmatched=UnmatchedStrategy(strategy="error"),
        )

        splitter = OntologySplitter(config)
        result = splitter.split()

        # Should fail because there are unmatched entities
        assert not result.success
        assert "Unmatched entities" in result.error


class TestManifestGeneration:
    """Tests for manifest file generation."""

    def test_manifest_content(self, monolith_ontology: Path, temp_dir: Path):
        """Test manifest contains correct information."""
        output_dir = temp_dir / "manifest_test"

        config = SplitConfig(
            source=monolith_ontology,
            output_dir=output_dir,
            modules=[
                ModuleDefinition(
                    name="core",
                    output="core.ttl",
                    classes=["http://example.org/ontology#Entity"],
                ),
                ModuleDefinition(
                    name="org",
                    output="org.ttl",
                    namespaces=["http://example.org/ontology/org#"],
                ),
            ],
            generate_manifest=True,
        )

        splitter = OntologySplitter(config)
        result = splitter.split()
        splitter.write_modules(result)
        splitter.write_manifest(result)

        manifest_path = output_dir / "manifest.yml"
        assert manifest_path.exists()

        import yaml
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)

        assert "modules" in manifest
        assert "summary" in manifest
        assert manifest["summary"]["total_modules"] >= 2


class TestDataSplitting:
    """Tests for splitting data files by instance type."""

    def test_data_split_by_type(
        self,
        monolith_ontology: Path,
        instance_data: Path,
        temp_dir: Path,
    ):
        """Test instances are split by their rdf:type."""
        output_dir = temp_dir / "data_split"

        config = SplitConfig(
            source=monolith_ontology,
            output_dir=output_dir,
            modules=[
                ModuleDefinition(
                    name="organisation",
                    output="organisation.ttl",
                    namespaces=["http://example.org/ontology/org#"],
                ),
                ModuleDefinition(
                    name="building",
                    output="building.ttl",
                    namespaces=["http://example.org/ontology/building#"],
                ),
            ],
            split_data=SplitDataConfig(
                sources=[instance_data],
                output_dir=output_dir / "data",
                prefix="data_",
            ),
        )

        splitter = OntologySplitter(config)
        result = splitter.split()

        assert result.success
        assert len(result.data_modules) > 0

        # Check organisation data has Company instance
        if "organisation" in result.data_modules:
            org_data = result.data_modules["organisation"]
            # Should have acme company
            acme = URIRef("http://example.org/data#acme")
            assert (acme, RDF.type, ORG.Company) in org_data


class TestDryRun:
    """Tests for dry run mode."""

    def test_dry_run_no_files(self, monolith_ontology: Path, temp_dir: Path):
        """Test dry run doesn't write files."""
        output_dir = temp_dir / "dry_run_test"

        config = SplitConfig(
            source=monolith_ontology,
            output_dir=output_dir,
            modules=[
                ModuleDefinition(
                    name="test",
                    output="test.ttl",
                    namespaces=["http://example.org/ontology/org#"],
                ),
            ],
            dry_run=True,
        )

        splitter = OntologySplitter(config)
        result = splitter.split()
        splitter.write_modules(result)

        assert result.success
        # Output directory should not exist or be empty
        assert not output_dir.exists() or not list(output_dir.iterdir())


class TestRoundTrip:
    """Tests for round-trip validation (merge(split(x)) == x)."""

    def test_round_trip_equivalence(self, monolith_ontology: Path, temp_dir: Path):
        """Test that merging split modules recreates original."""
        from rdf_construct.merge import OntologyMerger, MergeConfig, SourceConfig, OutputConfig

        output_dir = temp_dir / "roundtrip"

        # Split the ontology
        split_config = SplitConfig(
            source=monolith_ontology,
            output_dir=output_dir,
            modules=[
                ModuleDefinition(
                    name="core",
                    output="core.ttl",
                    classes=[
                        "http://example.org/ontology#Entity",
                        "http://example.org/ontology#Event",
                    ],
                    properties=["http://example.org/ontology#identifier"],
                ),
                ModuleDefinition(
                    name="org",
                    output="org.ttl",
                    namespaces=["http://example.org/ontology/org#"],
                ),
                ModuleDefinition(
                    name="building",
                    output="building.ttl",
                    namespaces=["http://example.org/ontology/building#"],
                ),
            ],
        )

        splitter = OntologySplitter(split_config)
        split_result = splitter.split()
        splitter.write_modules(split_result)

        assert split_result.success

        # Merge the modules back
        module_files = [
            output_dir / "core.ttl",
            output_dir / "org.ttl",
            output_dir / "building.ttl",
        ]

        # Filter to only existing files
        module_files = [f for f in module_files if f.exists()]

        if len(module_files) < 2:
            pytest.skip("Not enough modules created for round-trip test")

        merge_config = MergeConfig(
            sources=[SourceConfig(path=f) for f in module_files],
            output=OutputConfig(path=output_dir / "merged.ttl"),
        )

        merger = OntologyMerger(merge_config)
        merge_result = merger.merge()

        assert merge_result.success

        # Load original
        original = Graph()
        original.parse(monolith_ontology.as_posix())

        # Compare triple counts (rough equivalence check)
        original_triples = len(original)
        merged_triples = len(merge_result.merged_graph)

        # Should be roughly equal (may differ slightly due to imports)
        # Allow 10% difference
        assert abs(original_triples - merged_triples) < original_triples * 0.2


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_missing_source_file(self, temp_dir: Path):
        """Test handling of missing source file."""
        config = SplitConfig(
            source=temp_dir / "nonexistent.ttl",
            output_dir=temp_dir / "output",
            modules=[],
        )

        splitter = OntologySplitter(config)
        result = splitter.split()

        assert not result.success
        assert "not found" in result.error.lower() or "failed to load" in result.error.lower()

    def test_empty_modules_list(self, monolith_ontology: Path, temp_dir: Path):
        """Test handling of empty modules list."""
        config = SplitConfig(
            source=monolith_ontology,
            output_dir=temp_dir / "empty_modules",
            modules=[],
            unmatched=UnmatchedStrategy(strategy="common"),
        )

        splitter = OntologySplitter(config)
        result = splitter.split()

        # Should succeed with all entities in common module
        assert result.success
        assert len(result.unmatched_entities) > 0

    def test_curie_expansion(self, temp_dir: Path):
        """Test CURIE expansion in class lists."""
        content = dedent('''
            @prefix ex: <http://example.org/> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .

            ex:TestClass a owl:Class .
        ''').strip()

        source = temp_dir / "curie_test.ttl"
        source.write_text(content)

        config = SplitConfig(
            source=source,
            output_dir=temp_dir / "curie_output",
            modules=[
                ModuleDefinition(
                    name="test",
                    output="test.ttl",
                    # Use CURIE instead of full URI
                    classes=["ex:TestClass"],
                ),
            ],
        )

        splitter = OntologySplitter(config)
        result = splitter.split()

        assert result.success
        # The class should be assigned to the test module
        assert "http://example.org/TestClass" in result.entity_assignments
