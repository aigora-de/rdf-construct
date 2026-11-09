"""Unit tests for the ontology describe module."""

import json
import re
import warnings
from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner
from rdflib import Graph, Namespace, RDF, RDFS, Literal, URIRef
from rdflib.namespace import OWL, XSD

from rdf_construct.describe import (
    describe_file,
    describe_ontology,
    format_description,
    OntologyDescription,
    OntologyMetadata,
    BasicMetrics,
    ProfileDetection,
    OntologyProfile,
    NamespaceAnalysis,
    NamespaceInfo,
    NamespaceCategory,
    ImportAnalysis,
    ImportInfo,
    ImportStatus,
    HierarchyAnalysis,
    DocumentationCoverage,
    detect_profile,
    collect_metrics,
    extract_metadata,
    analyse_imports,
    analyse_namespaces,
    analyse_hierarchy,
    analyse_documentation,
)


# Test namespaces
EX = Namespace("http://example.org/")
DCTERMS = Namespace("http://purl.org/dc/terms/")


# --- Fixtures ---


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def empty_graph() -> Graph:
    """An empty RDF graph."""
    return Graph()


@pytest.fixture
def minimal_rdfs_graph() -> Graph:
    """A minimal RDFS graph with just classes."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("rdfs", RDFS)

    g.add((EX.Animal, RDF.type, RDFS.Class))
    g.add((EX.Animal, RDFS.label, Literal("Animal")))

    g.add((EX.Dog, RDF.type, RDFS.Class))
    g.add((EX.Dog, RDFS.subClassOf, EX.Animal))

    return g


@pytest.fixture
def simple_owl_graph() -> Graph:
    """A simple OWL ontology with classes and properties."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)

    # Ontology declaration
    g.add((EX.Ontology, RDF.type, OWL.Ontology))
    g.add((EX.Ontology, RDFS.label, Literal("Example Ontology")))
    g.add((EX.Ontology, RDFS.comment, Literal("A simple test ontology.")))
    g.add((EX.Ontology, OWL.versionInfo, Literal("1.0.0")))

    # Classes
    g.add((EX.Animal, RDF.type, OWL.Class))
    g.add((EX.Animal, RDFS.label, Literal("Animal")))
    g.add((EX.Animal, RDFS.comment, Literal("A living creature.")))

    g.add((EX.Dog, RDF.type, OWL.Class))
    g.add((EX.Dog, RDFS.subClassOf, EX.Animal))
    g.add((EX.Dog, RDFS.label, Literal("Dog")))

    g.add((EX.Cat, RDF.type, OWL.Class))
    g.add((EX.Cat, RDFS.subClassOf, EX.Animal))
    g.add((EX.Cat, RDFS.label, Literal("Cat")))

    # Object property
    g.add((EX.hasOwner, RDF.type, OWL.ObjectProperty))
    g.add((EX.hasOwner, RDFS.domain, EX.Animal))
    g.add((EX.hasOwner, RDFS.range, EX.Person))
    g.add((EX.hasOwner, RDFS.label, Literal("has owner")))

    # Datatype property
    g.add((EX.age, RDF.type, OWL.DatatypeProperty))
    g.add((EX.age, RDFS.domain, EX.Animal))
    g.add((EX.age, RDFS.range, XSD.integer))
    g.add((EX.age, RDFS.label, Literal("age")))

    # Annotation property
    g.add((EX.notes, RDF.type, OWL.AnnotationProperty))
    g.add((EX.notes, RDFS.label, Literal("notes")))

    return g


@pytest.fixture
def owl_dl_graph() -> Graph:
    """An OWL DL ontology with restrictions."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)

    # Ontology
    g.add((EX.Ontology, RDF.type, OWL.Ontology))

    # Classes
    g.add((EX.Person, RDF.type, OWL.Class))
    g.add((EX.Employee, RDF.type, OWL.Class))
    g.add((EX.Employee, RDFS.subClassOf, EX.Person))

    # Property restrictions (OWL DL feature)
    restriction = URIRef("http://example.org/_restriction1")
    g.add((restriction, RDF.type, OWL.Restriction))
    g.add((restriction, OWL.onProperty, EX.worksFor))
    g.add((restriction, OWL.someValuesFrom, EX.Company))
    g.add((EX.Employee, RDFS.subClassOf, restriction))

    # Functional property
    g.add((EX.hasManager, RDF.type, OWL.ObjectProperty))
    g.add((EX.hasManager, RDF.type, OWL.FunctionalProperty))

    # Inverse property
    g.add((EX.manages, RDF.type, OWL.ObjectProperty))
    g.add((EX.manages, OWL.inverseOf, EX.hasManager))

    return g


@pytest.fixture
def owl_full_graph() -> Graph:
    """An OWL Full ontology with metaclass patterns."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)

    # Ontology
    g.add((EX.Ontology, RDF.type, OWL.Ontology))

    # Regular class
    g.add((EX.Animal, RDF.type, OWL.Class))

    # Metaclass pattern (class is also instance) - OWL Full
    g.add((EX.Species, RDF.type, OWL.Class))
    g.add((EX.Dog, RDF.type, OWL.Class))
    g.add((EX.Dog, RDF.type, EX.Species))  # Class used as instance

    # Property used as subject of another property - OWL Full
    g.add((EX.hasPart, RDF.type, OWL.ObjectProperty))
    g.add((EX.hasPart, EX.customAnnotation, Literal("test")))

    return g


@pytest.fixture
def graph_with_imports() -> Graph:
    """An ontology that imports other ontologies."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("owl", OWL)

    # Ontology with imports
    g.add((EX.Ontology, RDF.type, OWL.Ontology))
    g.add((EX.Ontology, OWL.imports, URIRef("http://www.w3.org/2004/02/skos/core")))
    g.add((EX.Ontology, OWL.imports, URIRef("http://example.org/nonexistent")))

    return g


@pytest.fixture
def graph_with_individuals() -> Graph:
    """An ontology with named individuals."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)

    # Ontology
    g.add((EX.Ontology, RDF.type, OWL.Ontology))

    # Class
    g.add((EX.Person, RDF.type, OWL.Class))

    # Named individuals
    g.add((EX.alice, RDF.type, OWL.NamedIndividual))
    g.add((EX.alice, RDF.type, EX.Person))
    g.add((EX.alice, RDFS.label, Literal("Alice")))

    g.add((EX.bob, RDF.type, OWL.NamedIndividual))
    g.add((EX.bob, RDF.type, EX.Person))

    return g


@pytest.fixture
def simple_ontology_file(temp_dir) -> Path:
    """Create a simple ontology file for testing."""
    content = dedent(
        """
        @prefix ex: <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

        ex:Ontology a owl:Ontology ;
            rdfs:label "Test Ontology" ;
            owl:versionInfo "1.0" .

        ex:Building a owl:Class ;
            rdfs:label "Building"@en ;
            rdfs:comment "A structure with walls and a roof." .

        ex:House a owl:Class ;
            rdfs:subClassOf ex:Building ;
            rdfs:label "House"@en .

        ex:hasAddress a owl:DatatypeProperty ;
            rdfs:domain ex:Building ;
            rdfs:label "has address" .
    """
    ).strip()

    path = temp_dir / "test_ontology.ttl"
    path.write_text(content)
    return path


# --- Profile Detection Tests ---


class TestProfileDetection:
    """Tests for ontology profile detection."""

    def test_empty_graph_is_rdf(self, empty_graph: Graph):
        """Empty graph is classified as RDF."""
        profile = detect_profile(empty_graph)
        assert profile.profile == OntologyProfile.RDF

    def test_rdfs_classes(self, minimal_rdfs_graph: Graph):
        """Graph with rdfs:Class is classified as RDFS."""
        profile = detect_profile(minimal_rdfs_graph)
        assert profile.profile == OntologyProfile.RDFS

    def test_simple_owl(self, simple_owl_graph: Graph):
        """Graph with owl:Class is classified as OWL."""
        profile = detect_profile(simple_owl_graph)
        # Should be some form of OWL
        assert profile.profile in (
            OntologyProfile.OWL_DL_SIMPLE,
            OntologyProfile.OWL_DL_EXPRESSIVE,
        )

    def test_owl_dl_restrictions(self, owl_dl_graph: Graph):
        """Graph with OWL restrictions is OWL DL."""
        profile = detect_profile(owl_dl_graph)
        assert profile.profile in (
            OntologyProfile.OWL_DL_SIMPLE,
            OntologyProfile.OWL_DL_EXPRESSIVE,
        )

    def test_owl_full_metaclass(self, owl_full_graph: Graph):
        """Graph with metaclass patterns is OWL Full."""
        profile = detect_profile(owl_full_graph)
        assert profile.profile == OntologyProfile.OWL_FULL

    def test_profile_has_features(self, owl_dl_graph: Graph):
        """Profile includes detected features."""
        profile = detect_profile(owl_dl_graph)
        assert isinstance(profile.detected_features, list)

    def test_profile_to_dict(self, simple_owl_graph: Graph):
        """ProfileDetection can be converted to dict."""
        profile = detect_profile(simple_owl_graph)
        d = profile.to_dict()
        assert "profile" in d
        assert "display_name" in d


# --- Metrics Collection Tests ---


class TestMetricsCollection:
    """Tests for metrics collection."""

    def test_empty_graph_metrics(self, empty_graph: Graph):
        """Empty graph returns zero metrics."""
        metrics = collect_metrics(empty_graph)
        assert metrics.classes == 0
        assert metrics.object_properties == 0
        assert metrics.datatype_properties == 0
        assert metrics.individuals == 0

    def test_class_count(self, simple_owl_graph: Graph):
        """Counts OWL classes correctly."""
        metrics = collect_metrics(simple_owl_graph)
        assert metrics.classes == 3  # Animal, Dog, Cat

    def test_property_counts(self, simple_owl_graph: Graph):
        """Counts different property types."""
        metrics = collect_metrics(simple_owl_graph)
        assert metrics.object_properties == 1  # hasOwner
        assert metrics.datatype_properties == 1  # age
        assert metrics.annotation_properties == 1  # notes

    def test_individual_count(self, graph_with_individuals: Graph):
        """Counts named individuals."""
        metrics = collect_metrics(graph_with_individuals)
        assert metrics.individuals == 2  # alice, bob

    def test_triple_count(self, simple_owl_graph: Graph):
        """Triple count is correct."""
        metrics = collect_metrics(simple_owl_graph)
        assert metrics.total_triples == len(simple_owl_graph)

    def test_total_properties(self, simple_owl_graph: Graph):
        """Total properties sums all property types."""
        metrics = collect_metrics(simple_owl_graph)
        expected = (
            metrics.object_properties
            + metrics.datatype_properties
            + metrics.annotation_properties
            + metrics.rdf_properties
        )
        assert metrics.total_properties == expected

    def test_metrics_to_dict(self, simple_owl_graph: Graph):
        """Metrics can be converted to dict."""
        metrics = collect_metrics(simple_owl_graph)
        d = metrics.to_dict()
        assert "classes" in d
        assert "total_triples" in d


# --- Metadata Extraction Tests ---


class TestMetadataExtraction:
    """Tests for ontology metadata extraction."""

    def test_no_ontology_declaration(self, minimal_rdfs_graph: Graph):
        """Handles graphs without owl:Ontology."""
        metadata = extract_metadata(minimal_rdfs_graph)
        assert metadata.ontology_iri is None
        assert metadata.title is None

    def test_ontology_label(self, simple_owl_graph: Graph):
        """Extracts ontology label as title."""
        metadata = extract_metadata(simple_owl_graph)
        assert metadata.title == "Example Ontology"

    def test_ontology_description(self, simple_owl_graph: Graph):
        """Extracts ontology comment as description."""
        metadata = extract_metadata(simple_owl_graph)
        assert metadata.description == "A simple test ontology."

    def test_version_info(self, simple_owl_graph: Graph):
        """Extracts version info."""
        metadata = extract_metadata(simple_owl_graph)
        assert metadata.version_info == "1.0.0"

    def test_metadata_to_dict(self, simple_owl_graph: Graph):
        """Metadata can be converted to dict."""
        metadata = extract_metadata(simple_owl_graph)
        d = metadata.to_dict()
        assert "title" in d
        assert "version_info" in d


# --- Imports Analysis Tests ---


class TestImportsAnalysis:
    """Tests for owl:imports analysis."""

    def test_no_imports(self, simple_owl_graph: Graph):
        """Handles ontologies without imports."""
        imports = analyse_imports(simple_owl_graph, resolve=False)
        assert imports.count == 0
        assert len(imports.imports) == 0

    def test_import_count(self, graph_with_imports: Graph):
        """Counts imports correctly."""
        imports = analyse_imports(graph_with_imports, resolve=False)
        assert imports.count == 2

    def test_import_resolution_disabled(self, graph_with_imports: Graph):
        """Import resolution can be disabled."""
        imports = analyse_imports(graph_with_imports, resolve=False)
        # All should be unchecked status when not resolved
        for imp in imports.imports:
            assert imp.status == ImportStatus.UNCHECKED

    def test_imports_to_dict(self, graph_with_imports: Graph):
        """Imports info can be converted to dict."""
        imports = analyse_imports(graph_with_imports, resolve=False)
        d = imports.to_dict()
        assert "imports" in d
        assert "counts" in d


# --- Namespace Analysis Tests ---


class TestNamespaceAnalysis:
    """Tests for namespace analysis."""

    def test_namespace_detection(self, simple_owl_graph: Graph):
        """Detects used namespaces."""
        ns_info = analyse_namespaces(simple_owl_graph)
        assert len(ns_info.namespaces) > 0
        # Should detect the example namespace
        ns_uris = [ns.uri for ns in ns_info.namespaces]
        assert "http://example.org/" in ns_uris

    def test_namespace_categorisation(self, simple_owl_graph: Graph):
        """Categorises namespaces (local vs external)."""
        ns_info = analyse_namespaces(simple_owl_graph)
        # Should have at least one local and one external
        categories = {ns.category for ns in ns_info.namespaces}
        assert len(categories) >= 1

    def test_local_namespace(self, simple_owl_graph: Graph):
        """Identifies local namespace."""
        ns_info = analyse_namespaces(simple_owl_graph)
        assert ns_info.local_namespace is not None

    def test_namespaces_to_dict(self, simple_owl_graph: Graph):
        """Namespace info can be converted to dict."""
        ns_info = analyse_namespaces(simple_owl_graph)
        d = ns_info.to_dict()
        assert "local_namespace" in d
        assert "namespaces" in d


# --- Hierarchy Analysis Tests ---


class TestHierarchyAnalysis:
    """Tests for class hierarchy analysis."""

    def test_empty_hierarchy(self, empty_graph: Graph):
        """Handles graphs without classes."""
        hierarchy = analyse_hierarchy(empty_graph)
        assert hierarchy.max_depth == 0
        assert hierarchy.root_count == 0

    def test_hierarchy_depth(self, simple_owl_graph: Graph):
        """Calculates hierarchy depth."""
        hierarchy = analyse_hierarchy(simple_owl_graph)
        # Animal -> Dog/Cat = depth 1
        assert hierarchy.max_depth >= 1

    def test_root_classes(self, simple_owl_graph: Graph):
        """Identifies root classes."""
        hierarchy = analyse_hierarchy(simple_owl_graph)
        assert hierarchy.root_count >= 1  # At least Animal

    def test_hierarchy_to_dict(self, simple_owl_graph: Graph):
        """Hierarchy info can be converted to dict."""
        hierarchy = analyse_hierarchy(simple_owl_graph)
        d = hierarchy.to_dict()
        assert "max_depth" in d
        assert "root_count" in d


# --- Documentation Analysis Tests ---


class TestDocumentationAnalysis:
    """Tests for documentation coverage analysis."""

    def test_label_coverage(self, simple_owl_graph: Graph):
        """Calculates label coverage."""
        docs = analyse_documentation(simple_owl_graph)
        assert docs.classes_with_label > 0
        assert 0.0 <= docs.class_label_pct <= 100.0

    def test_definition_coverage(self, simple_owl_graph: Graph):
        """Calculates definition coverage."""
        docs = analyse_documentation(simple_owl_graph)
        # Only Animal has a comment
        assert docs.classes_with_definition >= 1

    def test_documentation_to_dict(self, simple_owl_graph: Graph):
        """Documentation info can be converted to dict."""
        docs = analyse_documentation(simple_owl_graph)
        d = docs.to_dict()
        assert "classes" in d
        assert "properties" in d


# --- High-Level API Tests ---


class TestDescribeAPI:
    """Tests for the high-level describe API."""

    def test_describe_ontology(self, simple_owl_graph: Graph):
        """describe_ontology returns OntologyDescription."""
        description = describe_ontology(simple_owl_graph, source="test.ttl")
        assert isinstance(description, OntologyDescription)
        assert description.metrics is not None

    def test_describe_file(self, simple_ontology_file: Path):
        """describe_file loads and describes ontology."""
        description = describe_file(simple_ontology_file)
        assert isinstance(description, OntologyDescription)
        assert str(simple_ontology_file) in str(description.source)

    def test_describe_file_not_found(self, temp_dir: Path):
        """describe_file raises for missing file."""
        with pytest.raises(FileNotFoundError):
            describe_file(temp_dir / "nonexistent.ttl")

    def test_describe_file_invalid_rdf(self, temp_dir: Path):
        """describe_file raises for invalid RDF."""
        bad_file = temp_dir / "bad.ttl"
        bad_file.write_text("this is not valid turtle")

        with pytest.raises(Exception):  # Could be ValueError or rdflib exception
            describe_file(bad_file)

    def test_describe_brief_mode(self, simple_ontology_file: Path):
        """describe_file supports brief mode."""
        description = describe_file(simple_ontology_file, brief=True)
        assert description.brief is True

    def test_describe_no_resolve(self, simple_ontology_file: Path):
        """describe_file supports resolve_imports=False."""
        description = describe_file(simple_ontology_file, resolve_imports=False)
        assert isinstance(description, OntologyDescription)


# --- Formatter Tests ---


class TestFormatters:
    """Tests for output formatters."""

    @pytest.fixture
    def sample_description(self, simple_owl_graph: Graph) -> OntologyDescription:
        """Create a sample description for formatter tests."""
        return describe_ontology(simple_owl_graph, source="test.ttl")

    def test_text_format_output(self, sample_description: OntologyDescription):
        """Text formatter produces readable output."""
        output = format_description(sample_description, format_name="text")
        assert isinstance(output, str)
        assert len(output) > 0

    def test_text_format_no_colour(self, sample_description: OntologyDescription):
        """Text formatter respects use_colour=False."""
        output = format_description(
            sample_description,
            format_name="text",
            use_colour=False,
        )
        # ANSI escape codes start with \x1b[
        assert "\x1b[" not in output

    def test_json_format_valid(self, sample_description: OntologyDescription):
        """JSON formatter produces valid JSON."""
        output = format_description(sample_description, format_name="json")
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_json_format_structure(self, sample_description: OntologyDescription):
        """JSON output has expected structure."""
        output = format_description(sample_description, format_name="json")
        parsed = json.loads(output)

        # Should have main sections
        assert "metrics" in parsed
        assert "profile" in parsed

    def test_markdown_format_headers(self, sample_description: OntologyDescription):
        """Markdown formatter includes headers."""
        output = format_description(sample_description, format_name="markdown")
        assert "#" in output  # Has markdown headers

    def test_md_alias(self, sample_description: OntologyDescription):
        """'md' is accepted as alias for markdown."""
        output = format_description(sample_description, format_name="md")
        assert "#" in output

    def test_invalid_format_raises(self, sample_description: OntologyDescription):
        """Invalid format name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown format"):
            format_description(sample_description, format_name="invalid")


# --- CLI Tests ---


class TestDescribeCLI:
    """Tests for the describe CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()

    def test_cli_basic(self, runner: CliRunner, simple_ontology_file: Path):
        """Basic CLI invocation works."""
        from rdf_construct.cli import cli

        result = runner.invoke(cli, ["describe", str(simple_ontology_file)])
        assert result.exit_code == 0

    def test_cli_json_format(self, runner: CliRunner, simple_ontology_file: Path):
        """CLI JSON format produces valid JSON."""
        from rdf_construct.cli import cli

        result = runner.invoke(
            cli,
            ["describe", str(simple_ontology_file), "--format", "json"],
        )
        assert result.exit_code == 0

        # Find the JSON in output (may have status messages before it)
        lines = result.output.strip().split("\n")
        json_start = next(
            (i for i, line in enumerate(lines) if line.strip().startswith("{")),
            None,
        )
        if json_start is not None:
            json_text = "\n".join(lines[json_start:])
            parsed = json.loads(json_text)
            assert isinstance(parsed, dict)

    def test_cli_markdown_format(self, runner: CliRunner, simple_ontology_file: Path):
        """CLI markdown format works."""
        from rdf_construct.cli import cli

        result = runner.invoke(
            cli,
            ["describe", str(simple_ontology_file), "--format", "markdown"],
        )
        assert result.exit_code == 0

    def test_cli_brief_mode(self, runner: CliRunner, simple_ontology_file: Path):
        """CLI brief mode works."""
        from rdf_construct.cli import cli

        result = runner.invoke(
            cli,
            ["describe", str(simple_ontology_file), "--brief"],
        )
        assert result.exit_code == 0

    def test_cli_no_resolve(self, runner: CliRunner, simple_ontology_file: Path):
        """CLI --no-resolve option works."""
        from rdf_construct.cli import cli

        result = runner.invoke(
            cli,
            ["describe", str(simple_ontology_file), "--no-resolve"],
        )
        assert result.exit_code == 0

    def test_cli_output_file(
        self,
        runner: CliRunner,
        simple_ontology_file: Path,
        temp_dir: Path,
    ):
        """CLI can write to output file."""
        from rdf_construct.cli import cli

        output_file = temp_dir / "description.txt"
        result = runner.invoke(
            cli,
            ["describe", str(simple_ontology_file), "-o", str(output_file)],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        assert output_file.read_text().strip() != ""

    def test_cli_file_not_found(self, runner: CliRunner):
        """CLI exits with error for missing file."""
        from rdf_construct.cli import cli

        result = runner.invoke(cli, ["describe", "/nonexistent/file.ttl"])
        assert result.exit_code == 2

    def test_cli_no_colour(self, runner: CliRunner, simple_ontology_file: Path):
        """CLI --no-colour option works."""
        from rdf_construct.cli import cli

        result = runner.invoke(
            cli,
            ["describe", str(simple_ontology_file), "--no-colour"],
        )
        assert result.exit_code == 0
        # No ANSI escape codes
        assert "\x1b[" not in result.output


# --- Integration Tests ---


class TestDescribeIntegration:
    """Integration tests for complete describe workflows."""

    def test_roundtrip_file_to_json(self, simple_ontology_file: Path):
        """Full workflow: file -> describe -> JSON -> parse."""
        description = describe_file(simple_ontology_file)
        json_output = format_description(description, format_name="json")
        parsed = json.loads(json_output)

        # Verify key data survived roundtrip
        assert parsed["metrics"]["classes"] == 2  # Building, House

    def test_multiple_formats_consistent(self, simple_ontology_file: Path):
        """All formats report consistent metrics."""
        description = describe_file(simple_ontology_file)

        text_output = format_description(description, format_name="text")
        json_output = format_description(description, format_name="json")
        md_output = format_description(description, format_name="markdown")

        # All should mention the same class count
        parsed_json = json.loads(json_output)
        class_count = parsed_json["metrics"]["classes"]

        assert str(class_count) in text_output
        assert str(class_count) in md_output

    def test_description_to_dict(self, simple_ontology_file: Path):
        """OntologyDescription can be converted to dict."""
        description = describe_file(simple_ontology_file)
        d = description.to_dict()

        assert "source" in d
        assert "metrics" in d
        assert "profile" in d

    def test_verdict_generation(self, simple_ontology_file: Path):
        """Description includes verdict summary."""
        description = describe_file(simple_ontology_file)
        assert description.verdict is not None
        assert len(description.verdict) > 0


# --- Edge Cases ---


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_graph_with_blank_nodes(self, temp_dir: Path):
        """Handles graphs with blank nodes gracefully."""
        content = dedent(
            """
            @prefix ex: <http://example.org/> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .

            ex:Thing a owl:Class ;
                owl:equivalentClass [
                    a owl:Restriction ;
                    owl:onProperty ex:hasPart ;
                    owl:someValuesFrom ex:Component
                ] .
        """
        ).strip()

        path = temp_dir / "blank_nodes.ttl"
        path.write_text(content)

        # Should not raise
        description = describe_file(path)
        assert description.metrics is not None

    def test_graph_with_unicode(self, temp_dir: Path):
        """Handles unicode in labels."""
        content = dedent(
            """
            @prefix ex: <http://example.org/> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .

            ex:日本語クラス a owl:Class ;
                rdfs:label "日本語"@ja ;
                rdfs:label "Japanese"@en .

            ex:Ümläut a owl:Class ;
                rdfs:label "Ümläut"@de .
        """
        ).strip()

        path = temp_dir / "unicode.ttl"
        path.write_text(content, encoding="utf-8")

        description = describe_file(path)
        assert description.metrics.classes == 2

    def test_very_large_ontology_performance(self, temp_dir: Path):
        """Handles larger ontologies without excessive time."""
        import time

        # Generate a moderately large ontology
        lines = [
            "@prefix ex: <http://example.org/> .",
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "",
            "ex:Ontology a owl:Ontology .",
        ]

        # Add 500 classes
        for i in range(500):
            lines.append(f'ex:Class{i} a owl:Class ; rdfs:label "Class {i}" .')

        path = temp_dir / "large.ttl"
        path.write_text("\n".join(lines))

        start = time.time()
        description = describe_file(path, brief=True)
        elapsed = time.time() - start

        assert description.metrics.classes == 500
        # Should complete in reasonable time (< 10 seconds)
        assert elapsed < 10.0


# --- Model Tests ---


class TestModels:
    """Tests for data model classes."""

    def test_ontology_profile_display_name(self):
        """OntologyProfile has display names."""
        assert OntologyProfile.RDF.display_name == "RDF"
        assert "OWL" in OntologyProfile.OWL_DL_SIMPLE.display_name

    def test_ontology_profile_reasoning_guidance(self):
        """OntologyProfile has reasoning guidance."""
        assert OntologyProfile.RDF.reasoning_guidance is not None
        assert OntologyProfile.OWL_FULL.reasoning_guidance is not None

    def test_basic_metrics_summary_line(self):
        """BasicMetrics generates summary line."""
        metrics = BasicMetrics(
            total_triples=100,
            classes=10,
            object_properties=5,
        )
        summary = metrics.summary_line
        assert "100" in summary
        assert "10" in summary

    def test_import_status_values(self):
        """ImportStatus enum has expected values."""
        assert ImportStatus.RESOLVABLE.value == "resolvable"
        assert ImportStatus.UNRESOLVABLE.value == "unresolvable"
        assert ImportStatus.UNCHECKED.value == "unchecked"

    def test_namespace_category_values(self):
        """NamespaceCategory enum has expected values."""
        assert NamespaceCategory.LOCAL.value == "local"
        assert NamespaceCategory.IMPORTED.value == "imported"
        assert NamespaceCategory.EXTERNAL.value == "external"


# --- Deprecated --reasoning (#220; removed in 0.8.0 by #299) ---


class TestReasoningDeprecation:
    """``--reasoning`` and ``include_reasoning`` are deprecated: warned, never analysed (#220)."""

    WELL = Path(__file__).parent.parent / "examples" / "describe" / "well_documented.ttl"
    PREFIX = "⚠ --reasoning is deprecated and will be removed in rdf-construct 0.8.0: "
    WARN_NOTHING = PREFIX + "it never ran a reasoner, and it does nothing"
    WARN_JSON = PREFIX + "it never ran a reasoner, and its JSON 'reasoning' key is kept until then"
    REASONING_JSON = {
        "entailment_regime": "owl-dl",
        "inferred_superclasses": [],
        "inferred_types": [],
        "consistency_notes": [],
    }

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def _run(self, runner: CliRunner, *args: str):
        from rdf_construct.cli import cli

        return runner.invoke(cli, ["describe", *args])

    @staticmethod
    def _mask(text: str) -> str:
        return re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?", "<TS>", text)

    def _assert_warned_once(self, stderr: str, line: str) -> None:
        assert stderr.splitlines().count(line) == 1
        assert stderr.count("is deprecated") == 1  # the library's warning never leaks
        assert stderr.index(line) < stderr.index("Analysing")

    @pytest.mark.parametrize("fmt", ["text", "markdown", "md"])
    def test_text_and_markdown_warn_and_print_no_section(self, runner: CliRunner, fmt: str) -> None:
        """The section is gone; the output equals the run without the flag."""
        base = [str(self.WELL), "--no-resolve", "-f", fmt, "--no-colour"]
        flagged = self._run(runner, *base, "--reasoning")
        plain = self._run(runner, *base)
        assert flagged.exit_code == 0
        self._assert_warned_once(flagged.stderr, self.WARN_NOTHING)
        assert "Reasoning Analysis" not in flagged.stdout
        assert "Entailment regime" not in flagged.stdout
        assert self._mask(flagged.stdout) == self._mask(plain.stdout)

    def test_json_keeps_the_reasoning_key_unchanged(self, runner: CliRunner) -> None:
        """JSON still carries ``reasoning`` exactly as before; nothing else moves."""
        base = [str(self.WELL), "--no-resolve", "-f", "json"]
        flagged = self._run(runner, *base, "--reasoning")
        plain = self._run(runner, *base)
        assert flagged.exit_code == 0
        self._assert_warned_once(flagged.stderr, self.WARN_JSON)
        data = json.loads(flagged.stdout)
        assert data.pop("reasoning") == self.REASONING_JSON
        data.pop("timestamp")
        other = json.loads(plain.stdout)
        other.pop("timestamp")
        assert "reasoning" not in other
        assert data == other

    @pytest.mark.parametrize("fmt", ["JSON", "Json"])
    def test_format_case_does_not_change_the_tail(self, runner: CliRunner, fmt: str) -> None:
        """``-f JSON`` is json: the JSON tail, and the key kept."""
        result = self._run(runner, str(self.WELL), "--no-resolve", "-f", fmt, "--reasoning")
        assert result.exit_code == 0
        self._assert_warned_once(result.stderr, self.WARN_JSON)
        assert json.loads(result.stdout)["reasoning"] == self.REASONING_JSON

    def test_brief_json_has_no_key_and_says_it_does_nothing(self, runner: CliRunner) -> None:
        """Under ``--brief`` the flag already did nothing, in every format."""
        result = self._run(runner, str(self.WELL), "--brief", "-f", "json", "--reasoning")
        assert result.exit_code == 0
        self._assert_warned_once(result.stderr, self.WARN_NOTHING)
        assert "reasoning" not in json.loads(result.stdout)

    def test_brief_text_warns(self, runner: CliRunner) -> None:
        """``--brief`` text warns too."""
        result = self._run(runner, str(self.WELL), "--brief", "--reasoning")
        assert result.exit_code == 0
        self._assert_warned_once(result.stderr, self.WARN_NOTHING)

    def test_with_resolution_warns(self, runner: CliRunner) -> None:
        """Without ``--no-resolve`` the warning is the same (no imports, so offline)."""
        result = self._run(runner, str(self.WELL), "--reasoning")
        assert result.exit_code == 0
        self._assert_warned_once(result.stderr, self.WARN_NOTHING)

    @pytest.mark.parametrize("fmt", ["text", "markdown", "json"])
    def test_output_file_has_no_section_and_stderr_warns(
        self, runner: CliRunner, tmp_path: Path, fmt: str
    ) -> None:
        """With ``-o`` the warning is still about the invocation."""
        out = tmp_path / f"description.{fmt}"
        result = self._run(
            runner, str(self.WELL), "--no-resolve", "-f", fmt, "-o", str(out), "--reasoning"
        )
        assert result.exit_code == 0
        self._assert_warned_once(
            result.stderr, self.WARN_JSON if fmt == "json" else self.WARN_NOTHING
        )
        written = out.read_text()
        assert "Reasoning Analysis" not in written
        if fmt == "json":
            assert json.loads(written)["reasoning"] == self.REASONING_JSON

    def test_unresolvable_import_still_exits_one(self, runner: CliRunner, tmp_path: Path) -> None:
        """The flag never moves the exit code (#286)."""
        src = tmp_path / "unresolvable.ttl"
        src.write_text(
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
            "<http://example.org/o> a owl:Ontology ;\n"
            "    owl:imports <file:///nonexistent/x.ttl> .\n"
        )
        assert self._run(runner, str(src)).exit_code == 1
        flagged = self._run(runner, str(src), "--reasoning")
        assert flagged.exit_code == 1
        self._assert_warned_once(flagged.stderr, self.WARN_NOTHING)
        as_json = self._run(runner, str(src), "-f", "json", "--reasoning")
        assert as_json.exit_code == 1
        self._assert_warned_once(as_json.stderr, self.WARN_JSON)
        assert json.loads(as_json.stdout)["reasoning"]["entailment_regime"] == "owl-dl"

    def test_refused_output_warns_before_the_refusal(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """An ``-o`` naming the input is refused at 2, after the warning."""
        src = tmp_path / "onto.ttl"
        src.write_bytes(self.WELL.read_bytes())
        result = self._run(runner, str(src), "-o", str(src), "--reasoning")
        assert result.exit_code == 2
        assert result.stderr.splitlines().count(self.WARN_NOTHING) == 1
        assert result.stderr.index(self.WARN_NOTHING) < result.stderr.index("Nothing was written")
        assert src.read_bytes() == self.WELL.read_bytes()

    def test_parse_failure_warns_before_the_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """A file that does not parse exits 2, after the warning."""
        src = tmp_path / "broken.ttl"
        src.write_text("@prefix : <http://example.org/> .\n:a :b\n")
        result = self._run(runner, str(src), "--reasoning")
        assert result.exit_code == 2
        self._assert_warned_once(result.stderr, self.WARN_NOTHING)
        assert result.stderr.index(self.WARN_NOTHING) < result.stderr.index("Error parsing RDF")

    def test_without_the_flag_no_warning(self, runner: CliRunner) -> None:
        """No flag, no warning."""
        result = self._run(runner, str(self.WELL), "--no-resolve")
        assert result.exit_code == 0
        assert "deprecated" not in result.stderr

    def test_colour_follows_no_colour(self, runner: CliRunner) -> None:
        """The warning is yellow unless ``--no-colour`` says otherwise."""
        from rdf_construct.cli import cli

        args = ["describe", str(self.WELL), "--no-resolve", "--reasoning"]
        coloured = runner.invoke(cli, args, color=True)
        plain = runner.invoke(cli, [*args, "--no-colour"], color=True)
        assert "\x1b[33m" + self.WARN_NOTHING in coloured.stderr
        assert self.WARN_NOTHING + "\n" in plain.stderr
        assert "\x1b[" not in plain.stderr.split("Analysing")[0]

    def test_help_marks_the_flag_deprecated(self, runner: CliRunner) -> None:
        """``--help`` says the flag is deprecated and when it goes."""
        result = self._run(runner, "--help")
        assert result.exit_code == 0
        assert (
            "--reasoning Deprecated: never ran a reasoner; removed in rdf-construct 0.8.0"
            in " ".join(result.stdout.split())
        )

    def test_cli_survives_the_library_warning_as_an_error(self, runner: CliRunner) -> None:
        """The CLI suppresses the library's own warning, so ``-W error`` cannot exit 2."""
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "error", message="include_reasoning is deprecated", category=DeprecationWarning
            )
            result = self._run(runner, str(self.WELL), "--no-resolve", "-f", "json", "--reasoning")
        assert result.exit_code == 0
        assert json.loads(result.stdout)["reasoning"] == self.REASONING_JSON

    @staticmethod
    def _ours(record) -> list:
        return [
            w
            for w in record
            if issubclass(w.category, DeprecationWarning)
            and str(w.message).startswith("include_reasoning is deprecated")
        ]

    def test_describe_file_warns_once_at_the_caller(self) -> None:
        """``describe_file(include_reasoning=True)`` warns once, pointing at this line."""
        with pytest.deprecated_call() as record:
            describe_file(self.WELL, brief=True, resolve_imports=False, include_reasoning=True)
        ours = self._ours(record)
        assert len(ours) == 1
        assert ours[0].filename == __file__
        with pytest.deprecated_call() as record:
            description = describe_file(self.WELL, resolve_imports=False, include_reasoning=True)
        ours = self._ours(record)
        assert len(ours) == 1
        assert ours[0].filename == __file__
        assert "rdf-construct 0.8.0" in str(ours[0].message)
        assert description.reasoning is not None
        assert description.reasoning.to_dict() == self.REASONING_JSON

    def test_describe_ontology_warns_once_at_the_caller(self) -> None:
        """``describe_ontology(include_reasoning=True)`` warns once, ``brief`` included."""
        graph = Graph().parse(self.WELL)
        for brief in (False, True):
            with pytest.deprecated_call() as record:
                describe_ontology(
                    graph, self.WELL, brief=brief, resolve_imports=False, include_reasoning=True
                )
            ours = self._ours(record)
            assert len(ours) == 1
            assert ours[0].filename == __file__

    def test_no_library_warning_without_the_flag(self) -> None:
        """The default never warns."""
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            describe_file(self.WELL, resolve_imports=False)
            describe_ontology(Graph().parse(self.WELL), self.WELL, resolve_imports=False)
        assert self._ours(record) == []

    def test_formatters_drop_the_section_for_every_caller(self) -> None:
        """A description that carries ``reasoning`` prints no section; its JSON keeps the key."""
        with pytest.deprecated_call():
            description = describe_file(self.WELL, resolve_imports=False, include_reasoning=True)
        for fmt in ("text", "markdown", "md"):
            out = format_description(description, format_name=fmt, use_colour=False)
            assert "Reasoning Analysis" not in out
            assert "Entailment regime" not in out
        data = json.loads(format_description(description, format_name="json"))
        assert data["reasoning"] == self.REASONING_JSON
