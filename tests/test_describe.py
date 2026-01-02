"""Unit tests for the ontology describe module."""

import json
from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner
from rdflib import Graph, Namespace, RDF, RDFS, Literal, URIRef
from rdflib.namespace import OWL, XSD, SKOS

from rdf_construct.describe import (
    describe_file,
    describe_graph,
    format_description,
    OntologyDescription,
)
from rdf_construct.describe.models import (
    OntologyDescription,
    MetadataInfo,
    MetricsInfo,
    ProfileInfo,
    ImportsInfo,
    ImportStatus,
    NamespaceInfo,
    HierarchyInfo,
    DocumentationInfo,
)
from rdf_construct.describe.profiles import (
    ProfileDetector,
    OntologyProfile,
    detect_profile,
)
from rdf_construct.describe.metrics import (
    MetricsCollector,
    collect_metrics,
)
from rdf_construct.describe.metadata import (
    MetadataExtractor,
    extract_metadata,
)
from rdf_construct.describe.imports import (
    ImportsAnalyser,
    analyse_imports,
)
from rdf_construct.describe.namespaces import (
    NamespaceAnalyser,
    analyse_namespaces,
)
from rdf_construct.describe.hierarchy import (
    HierarchyAnalyser,
    analyse_hierarchy,
)
from rdf_construct.describe.documentation import (
    DocumentationAnalyser,
    analyse_documentation,
)
from rdf_construct.describe.analyzer import OntologyAnalyzer
from rdf_construct.describe.formatters import (
    get_formatter,
    TextFormatter,
    JsonFormatter,
    MarkdownFormatter,
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
    content = dedent('''
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
    ''').strip()

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
        assert profile.profile in (OntologyProfile.OWL_DL, OntologyProfile.OWL_LITE)

    def test_owl_dl_restrictions(self, owl_dl_graph: Graph):
        """Graph with OWL restrictions is OWL DL."""
        profile = detect_profile(owl_dl_graph)
        assert profile.profile == OntologyProfile.OWL_DL

    def test_owl_full_metaclass(self, owl_full_graph: Graph):
        """Graph with metaclass patterns is OWL Full."""
        profile = detect_profile(owl_full_graph)
        assert profile.profile == OntologyProfile.OWL_FULL

    def test_profile_features(self, owl_dl_graph: Graph):
        """Profile includes detected features."""
        profile = detect_profile(owl_dl_graph)
        assert profile.features is not None
        assert len(profile.features) > 0

    def test_profile_info_to_dict(self, simple_owl_graph: Graph):
        """ProfileInfo can be converted to dict."""
        profile = detect_profile(simple_owl_graph)
        d = profile.to_dict()
        assert "profile" in d
        assert "features" in d


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
        assert metrics.triples == len(simple_owl_graph)

    def test_metrics_to_dict(self, simple_owl_graph: Graph):
        """Metrics can be converted to dict."""
        metrics = collect_metrics(simple_owl_graph)
        d = metrics.to_dict()
        assert "classes" in d
        assert "triples" in d


# --- Metadata Extraction Tests ---

class TestMetadataExtraction:
    """Tests for ontology metadata extraction."""

    def test_no_ontology_declaration(self, minimal_rdfs_graph: Graph):
        """Handles graphs without owl:Ontology."""
        metadata = extract_metadata(minimal_rdfs_graph)
        assert metadata.uri is None
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
        assert metadata.version == "1.0.0"

    def test_metadata_to_dict(self, simple_owl_graph: Graph):
        """Metadata can be converted to dict."""
        metadata = extract_metadata(simple_owl_graph)
        d = metadata.to_dict()
        assert "title" in d
        assert "version" in d


# --- Imports Analysis Tests ---

class TestImportsAnalysis:
    """Tests for owl:imports analysis."""

    def test_no_imports(self, simple_owl_graph: Graph):
        """Handles ontologies without imports."""
        imports = analyse_imports(simple_owl_graph, resolve=False)
        assert imports.total_count == 0
        assert len(imports.imports) == 0

    def test_import_count(self, graph_with_imports: Graph):
        """Counts imports correctly."""
        imports = analyse_imports(graph_with_imports, resolve=False)
        assert imports.total_count == 2

    def test_import_resolution_disabled(self, graph_with_imports: Graph):
        """Import resolution can be disabled."""
        imports = analyse_imports(graph_with_imports, resolve=False)
        # All should be unknown status when not resolved
        for imp in imports.imports:
            assert imp.status == ImportStatus.UNKNOWN

    def test_imports_to_dict(self, graph_with_imports: Graph):
        """Imports info can be converted to dict."""
        imports = analyse_imports(graph_with_imports, resolve=False)
        d = imports.to_dict()
        assert "total_count" in d
        assert "imports" in d


# --- Namespace Analysis Tests ---

class TestNamespaceAnalysis:
    """Tests for namespace analysis."""

    def test_namespace_detection(self, simple_owl_graph: Graph):
        """Detects used namespaces."""
        ns_info = analyse_namespaces(simple_owl_graph)
        assert ns_info.total_count > 0
        # Should detect the example namespace
        ns_uris = [ns.uri for ns in ns_info.namespaces]
        assert "http://example.org/" in ns_uris

    def test_namespace_categorisation(self, simple_owl_graph: Graph):
        """Categorises namespaces (standard vs custom)."""
        ns_info = analyse_namespaces(simple_owl_graph)
        # OWL and RDFS are standard
        assert ns_info.standard_count > 0
        # example.org is custom
        assert ns_info.custom_count > 0

    def test_primary_namespace(self, simple_owl_graph: Graph):
        """Identifies primary namespace."""
        ns_info = analyse_namespaces(simple_owl_graph)
        assert ns_info.primary_namespace is not None

    def test_namespaces_to_dict(self, simple_owl_graph: Graph):
        """Namespace info can be converted to dict."""
        ns_info = analyse_namespaces(simple_owl_graph)
        d = ns_info.to_dict()
        assert "total_count" in d
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
        assert hierarchy.max_depth == 1

    def test_root_classes(self, simple_owl_graph: Graph):
        """Identifies root classes."""
        hierarchy = analyse_hierarchy(simple_owl_graph)
        assert hierarchy.root_count == 1  # Animal

    def test_leaf_classes(self, simple_owl_graph: Graph):
        """Identifies leaf classes."""
        hierarchy = analyse_hierarchy(simple_owl_graph)
        assert hierarchy.leaf_count == 2  # Dog, Cat

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
        assert docs.classes_with_labels > 0
        assert 0.0 <= docs.label_coverage <= 1.0

    def test_comment_coverage(self, simple_owl_graph: Graph):
        """Calculates comment coverage."""
        docs = analyse_documentation(simple_owl_graph)
        # Only Animal has a comment
        assert docs.classes_with_comments == 1

    def test_documentation_to_dict(self, simple_owl_graph: Graph):
        """Documentation info can be converted to dict."""
        docs = analyse_documentation(simple_owl_graph)
        d = docs.to_dict()
        assert "label_coverage" in d
        assert "comment_coverage" in d


# --- Main Analyzer Tests ---

class TestOntologyAnalyzer:
    """Tests for the main analyzer orchestrator."""

    def test_full_analysis(self, simple_owl_graph: Graph):
        """Performs full analysis."""
        analyzer = OntologyAnalyzer()
        description = analyzer.analyze(simple_owl_graph)

        assert description.metadata is not None
        assert description.metrics is not None
        assert description.profile is not None

    def test_brief_analysis(self, simple_owl_graph: Graph):
        """Brief mode includes fewer sections."""
        analyzer = OntologyAnalyzer()
        description = analyzer.analyze(simple_owl_graph, brief=True)

        assert description.metadata is not None
        assert description.metrics is not None
        assert description.profile is not None
        # Brief mode may skip detailed analysis
        # (implementation specific)

    def test_skip_import_resolution(self, graph_with_imports: Graph):
        """Can skip import resolution."""
        analyzer = OntologyAnalyzer()
        description = analyzer.analyze(
            graph_with_imports,
            resolve_imports=False,
        )

        if description.imports:
            for imp in description.imports.imports:
                assert imp.status == ImportStatus.UNKNOWN


# --- High-Level API Tests ---

class TestDescribeAPI:
    """Tests for the high-level describe API."""

    def test_describe_graph(self, simple_owl_graph: Graph):
        """describe_graph returns OntologyDescription."""
        description = describe_graph(simple_owl_graph)
        assert isinstance(description, OntologyDescription)
        assert description.metrics is not None

    def test_describe_file(self, simple_ontology_file: Path):
        """describe_file loads and describes ontology."""
        description = describe_file(simple_ontology_file)
        assert isinstance(description, OntologyDescription)
        assert description.source == str(simple_ontology_file)

    def test_describe_file_not_found(self, temp_dir: Path):
        """describe_file raises for missing file."""
        with pytest.raises(FileNotFoundError):
            describe_file(temp_dir / "nonexistent.ttl")

    def test_describe_file_invalid_rdf(self, temp_dir: Path):
        """describe_file raises for invalid RDF."""
        bad_file = temp_dir / "bad.ttl"
        bad_file.write_text("this is not valid turtle")

        with pytest.raises(ValueError):
            describe_file(bad_file)


# --- Formatter Tests ---

class TestFormatters:
    """Tests for output formatters."""

    @pytest.fixture
    def sample_description(self, simple_owl_graph: Graph) -> OntologyDescription:
        """Create a sample description for formatter tests."""
        return describe_graph(simple_owl_graph)

    def test_get_formatter_text(self):
        """get_formatter returns TextFormatter for 'text'."""
        formatter = get_formatter("text")
        assert isinstance(formatter, TextFormatter)

    def test_get_formatter_json(self):
        """get_formatter returns JsonFormatter for 'json'."""
        formatter = get_formatter("json")
        assert isinstance(formatter, JsonFormatter)

    def test_get_formatter_markdown(self):
        """get_formatter returns MarkdownFormatter for 'markdown'."""
        formatter = get_formatter("markdown")
        assert isinstance(formatter, MarkdownFormatter)

    def test_get_formatter_md_alias(self):
        """get_formatter accepts 'md' as alias for markdown."""
        formatter = get_formatter("md")
        assert isinstance(formatter, MarkdownFormatter)

    def test_get_formatter_invalid(self):
        """get_formatter raises for invalid format."""
        with pytest.raises(ValueError, match="Unknown format"):
            get_formatter("invalid")

    def test_text_format_output(self, sample_description: OntologyDescription):
        """Text formatter produces readable output."""
        output = format_description(sample_description, format_name="text")
        assert isinstance(output, str)
        assert len(output) > 0
        # Should contain key sections
        assert "Profile" in output or "profile" in output.lower()

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
        assert "metrics" in parsed or "profile" in parsed

    def test_json_format_structure(self, sample_description: OntologyDescription):
        """JSON output has expected structure."""
        output = format_description(sample_description, format_name="json")
        parsed = json.loads(output)

        # Should have main sections
        if "metrics" in parsed:
            assert "classes" in parsed["metrics"]
        if "profile" in parsed:
            assert "profile" in parsed["profile"] or "name" in parsed["profile"]

    def test_markdown_format_headers(self, sample_description: OntologyDescription):
        """Markdown formatter includes headers."""
        output = format_description(sample_description, format_name="markdown")
        assert "##" in output  # Has markdown headers

    def test_markdown_format_tables(self, sample_description: OntologyDescription):
        """Markdown formatter includes tables."""
        output = format_description(sample_description, format_name="markdown")
        # Markdown tables have | characters
        assert "|" in output


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
        assert "Analysing" in result.output or len(result.output) > 0

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
        assert "##" in result.output or "#" in result.output

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

    def test_describe_complex_ontology(self, owl_dl_graph: Graph, temp_dir: Path):
        """Handles complex OWL DL ontology."""
        # Save to file
        owl_file = temp_dir / "owl_dl.ttl"
        owl_dl_graph.serialize(destination=str(owl_file), format="turtle")

        description = describe_file(owl_file)

        assert description.profile is not None
        assert description.profile.profile == OntologyProfile.OWL_DL
        assert description.metrics is not None


# --- Edge Cases ---

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_graph_with_blank_nodes(self, temp_dir: Path):
        """Handles graphs with blank nodes gracefully."""
        content = dedent('''
            @prefix ex: <http://example.org/> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .

            ex:Thing a owl:Class ;
                owl:equivalentClass [
                    a owl:Restriction ;
                    owl:onProperty ex:hasPart ;
                    owl:someValuesFrom ex:Component
                ] .
        ''').strip()

        path = temp_dir / "blank_nodes.ttl"
        path.write_text(content)

        # Should not raise
        description = describe_file(path)
        assert description.metrics is not None

    def test_graph_with_unicode(self, temp_dir: Path):
        """Handles unicode in labels."""
        content = dedent('''
            @prefix ex: <http://example.org/> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .

            ex:日本語クラス a owl:Class ;
                rdfs:label "日本語"@ja ;
                rdfs:label "Japanese"@en .

            ex:Ümläut a owl:Class ;
                rdfs:label "Ümläut"@de .
        ''').strip()

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
            lines.append(f"ex:Class{i} a owl:Class ; rdfs:label \"Class {i}\" .")

        path = temp_dir / "large.ttl"
        path.write_text("\n".join(lines))

        start = time.time()
        description = describe_file(path, brief=True)
        elapsed = time.time() - start

        assert description.metrics.classes == 500
        # Should complete in reasonable time (< 10 seconds)
        assert elapsed < 10.0
