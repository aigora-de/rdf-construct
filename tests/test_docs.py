"""Tests for the documentation generation module."""

import json
import re
from pathlib import Path

import pytest
from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL, SH, XSD

from rdf_construct.docs import (
    ClassInfo,
    ConceptInfo,
    DocsConfig,
    DocsGenerator,
    EntityKind,
    ExtractedEntities,
    PropertyInfo,
    ShapeInfo,
    build_concept_tree,
    extract_all,
    generate_docs,
)
from rdf_construct.docs.config import (
    entity_to_filename,
    entity_to_path,
    entity_to_url,
    relative_url_prefix,
)
from rdf_construct.docs.search import extract_keywords, generate_search_index


# Test namespaces
EX = Namespace("http://example.org/")
EX_NI = Namespace("http://example.org/ni#")


@pytest.fixture
def simple_ontology() -> Graph:
    """Create a simple test ontology."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)

    # Ontology declaration
    g.add((EX.TestOntology, RDF.type, OWL.Ontology))
    g.add((EX.TestOntology, RDFS.label, Literal("Test Ontology")))
    g.add((EX.TestOntology, RDFS.comment, Literal("A test ontology for documentation generation.")))

    # Classes
    g.add((EX.Animal, RDF.type, OWL.Class))
    g.add((EX.Animal, RDFS.label, Literal("Animal")))
    g.add((EX.Animal, RDFS.comment, Literal("A living creature.")))

    g.add((EX.Mammal, RDF.type, OWL.Class))
    g.add((EX.Mammal, RDFS.subClassOf, EX.Animal))
    g.add((EX.Mammal, RDFS.label, Literal("Mammal")))

    g.add((EX.Dog, RDF.type, OWL.Class))
    g.add((EX.Dog, RDFS.subClassOf, EX.Mammal))
    g.add((EX.Dog, RDFS.label, Literal("Dog")))
    g.add((EX.Dog, RDFS.comment, Literal("A domesticated canine.")))

    # Object property
    g.add((EX.hasOwner, RDF.type, OWL.ObjectProperty))
    g.add((EX.hasOwner, RDFS.domain, EX.Animal))
    g.add((EX.hasOwner, RDFS.range, EX.Person))
    g.add((EX.hasOwner, RDFS.label, Literal("has owner")))

    # Datatype property
    g.add((EX.hasName, RDF.type, OWL.DatatypeProperty))
    g.add((EX.hasName, RDFS.domain, EX.Animal))
    g.add((EX.hasName, RDFS.range, XSD.string))
    g.add((EX.hasName, RDFS.label, Literal("has name")))

    # Person class (for range)
    g.add((EX.Person, RDF.type, OWL.Class))
    g.add((EX.Person, RDFS.label, Literal("Person")))

    # Instance
    g.add((EX.Fido, RDF.type, EX.Dog))
    g.add((EX.Fido, RDFS.label, Literal("Fido")))
    g.add((EX.Fido, EX.hasName, Literal("Fido the Dog")))

    return g


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory."""
    out = tmp_path / "docs"
    out.mkdir()
    return out


class TestExtractors:
    """Tests for entity extraction."""

    def test_extract_all_classes(self, simple_ontology: Graph):
        """Test that all classes are extracted."""
        entities = extract_all(simple_ontology)

        assert len(entities.classes) == 4  # Animal, Mammal, Dog, Person
        class_qnames = {c.qname for c in entities.classes}
        assert "ex:Animal" in class_qnames
        assert "ex:Dog" in class_qnames

    def test_extract_class_info(self, simple_ontology: Graph):
        """Test class information extraction."""
        entities = extract_all(simple_ontology)

        # Find Dog class
        dog = next((c for c in entities.classes if "Dog" in c.qname), None)
        assert dog is not None
        assert dog.label == "Dog"
        assert dog.definition == "A domesticated canine."
        assert len(dog.superclasses) == 1  # Mammal

    def test_extract_class_hierarchy(self, simple_ontology: Graph):
        """Test that class hierarchy is correctly extracted."""
        entities = extract_all(simple_ontology)

        mammal = next((c for c in entities.classes if "Mammal" in c.qname), None)
        assert mammal is not None
        assert len(mammal.subclasses) == 1  # Dog
        assert len(mammal.superclasses) == 1  # Animal

    def test_extract_properties(self, simple_ontology: Graph):
        """Test property extraction."""
        entities = extract_all(simple_ontology)

        assert len(entities.object_properties) == 1
        assert len(entities.datatype_properties) == 1

        obj_prop = entities.object_properties[0]
        assert "hasOwner" in obj_prop.qname
        assert obj_prop.property_type == "object"

        data_prop = entities.datatype_properties[0]
        assert "hasName" in data_prop.qname
        assert data_prop.property_type == "datatype"

    def test_extract_property_domain_range(self, simple_ontology: Graph):
        """Test property domain and range extraction."""
        entities = extract_all(simple_ontology)

        obj_prop = entities.object_properties[0]
        assert len(obj_prop.domain) == 1
        assert len(obj_prop.range) == 1

    def test_extract_instances(self, simple_ontology: Graph):
        """Test instance extraction."""
        entities = extract_all(simple_ontology)

        assert len(entities.instances) == 1
        fido = entities.instances[0]
        assert "Fido" in fido.qname
        assert fido.label == "Fido"
        assert len(fido.types) == 1

    def test_extract_ontology_info(self, simple_ontology: Graph):
        """Test ontology metadata extraction."""
        entities = extract_all(simple_ontology)

        assert entities.ontology.title == "Test Ontology"
        assert "test ontology" in entities.ontology.description.lower()
        assert len(entities.ontology.namespaces) > 0


class TestConfig:
    """Tests for configuration handling."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DocsConfig()

        assert config.format == "html"
        assert config.include_instances is True
        assert config.include_search is True

    def test_config_from_dict(self):
        """Test configuration from dictionary."""
        config = DocsConfig.from_dict(
            {
                "format": "markdown",
                "title": "Custom Title",
                "include_instances": False,
            }
        )

        assert config.format == "markdown"
        assert config.title == "Custom Title"
        assert config.include_instances is False

    def test_entity_to_filename(self):
        """Test filename generation from QNames."""
        assert entity_to_filename("ex:Building") == "Building"
        assert entity_to_filename("Building") == "Building"
        assert entity_to_filename("ex:has/slash") == "has_slash"

    def test_entity_to_path(self):
        """Test path generation for entities."""
        config = DocsConfig(format="html")

        path = entity_to_path("ex:Building", "class", config)
        assert path == Path("classes/Building.html")

        path = entity_to_path("ex:hasOwner", "object_property", config)
        assert path == Path("properties/object/hasOwner.html")

        path = entity_to_path("ex:Fido", "instance", config)
        assert path == Path("instances/Fido.html")


class TestSearch:
    """Tests for search index generation."""

    def test_extract_keywords(self):
        """Test keyword extraction from text."""
        keywords = extract_keywords("A large building with many rooms")

        assert "large" in keywords
        assert "building" in keywords
        assert "rooms" in keywords
        # Stop words should be excluded
        assert "a" not in keywords
        assert "with" not in keywords

    def test_extract_keywords_empty(self):
        """Test keyword extraction with empty/None input."""
        assert extract_keywords(None) == []
        assert extract_keywords("") == []

    def test_generate_search_index(self, simple_ontology: Graph):
        """Test search index generation."""
        entities = extract_all(simple_ontology)
        config = DocsConfig()

        index = generate_search_index(entities, config)

        assert len(index) > 0
        # Should have entries for classes, properties, instances
        entry_types = {e.entity_type for e in index}
        assert "class" in entry_types

    def test_search_entry_has_required_fields(self, simple_ontology: Graph):
        """Test that search entries have all required fields."""
        entities = extract_all(simple_ontology)
        config = DocsConfig()

        index = generate_search_index(entities, config)

        for entry in index:
            assert entry.uri is not None
            assert entry.qname is not None
            assert entry.entity_type is not None
            assert entry.label is not None
            assert entry.url is not None
            assert isinstance(entry.keywords, list)


class TestGenerator:
    """Tests for the documentation generator."""

    def test_generator_html_output(self, simple_ontology: Graph, output_dir: Path):
        """Test HTML documentation generation."""
        config = DocsConfig(output_dir=output_dir, format="html")
        generator = DocsGenerator(config)

        result = generator.generate(simple_ontology)

        assert result.output_dir == output_dir
        assert result.total_pages > 0
        assert (output_dir / "index.html").exists()
        assert (output_dir / "hierarchy.html").exists()

    def test_generator_markdown_output(self, simple_ontology: Graph, output_dir: Path):
        """Test Markdown documentation generation."""
        config = DocsConfig(output_dir=output_dir, format="markdown")
        generator = DocsGenerator(config)

        result = generator.generate(simple_ontology)

        assert (output_dir / "index.md").exists()
        assert (output_dir / "hierarchy.md").exists()

    def test_generator_json_output(self, simple_ontology: Graph, output_dir: Path):
        """Test JSON documentation generation."""
        config = DocsConfig(output_dir=output_dir, format="json")
        generator = DocsGenerator(config)

        result = generator.generate(simple_ontology)

        assert (output_dir / "index.json").exists()

        # Validate JSON structure
        with open(output_dir / "index.json") as f:
            data = json.load(f)

        assert "ontology" in data
        assert "classes" in data
        assert "statistics" in data

    def test_generator_creates_class_pages(self, simple_ontology: Graph, output_dir: Path):
        """Test that individual class pages are created."""
        config = DocsConfig(output_dir=output_dir, format="html")
        generator = DocsGenerator(config)

        result = generator.generate(simple_ontology)

        # Check class pages exist
        classes_dir = output_dir / "classes"
        assert classes_dir.exists()
        assert (classes_dir / "Animal.html").exists()
        assert (classes_dir / "Dog.html").exists()

    def test_generator_creates_property_pages(self, simple_ontology: Graph, output_dir: Path):
        """Test that individual property pages are created."""
        config = DocsConfig(output_dir=output_dir, format="html")
        generator = DocsGenerator(config)

        result = generator.generate(simple_ontology)

        # Check property pages exist
        assert (output_dir / "properties" / "object" / "hasOwner.html").exists()
        assert (output_dir / "properties" / "datatype" / "hasName.html").exists()

    def test_generator_single_page(self, simple_ontology: Graph, output_dir: Path):
        """Test single-page documentation generation."""
        config = DocsConfig(output_dir=output_dir, format="html", single_page=True)
        generator = DocsGenerator(config)

        result = generator.generate(simple_ontology)

        assert (output_dir / "index.html").exists()
        # Single page should not have separate class pages
        assert not (output_dir / "classes").exists()

    def test_generator_search_index(self, simple_ontology: Graph, output_dir: Path):
        """Test that search index is generated for HTML output."""
        config = DocsConfig(output_dir=output_dir, format="html", include_search=True)
        generator = DocsGenerator(config)

        result = generator.generate(simple_ontology)

        search_file = output_dir / "search.json"
        assert search_file.exists()

        with open(search_file) as f:
            data = json.load(f)

        assert "entities" in data
        assert len(data["entities"]) > 0

    def test_generator_no_instances(self, simple_ontology: Graph, output_dir: Path):
        """Test generation without instances."""
        config = DocsConfig(output_dir=output_dir, format="html", include_instances=False)
        generator = DocsGenerator(config)

        result = generator.generate(simple_ontology)

        assert result.instances_count == 0
        assert not (output_dir / "instances").exists()

    def test_generator_assets_copied(self, simple_ontology: Graph, output_dir: Path):
        """Test that CSS assets are copied for HTML output."""
        config = DocsConfig(output_dir=output_dir, format="html")
        generator = DocsGenerator(config)

        result = generator.generate(simple_ontology)

        assert (output_dir / "assets" / "style.css").exists()

    def test_generator_title_override(self, simple_ontology: Graph, output_dir: Path):
        """Test title override in configuration."""
        config = DocsConfig(
            output_dir=output_dir,
            format="html",
            title="Custom Documentation Title",
        )
        generator = DocsGenerator(config)

        result = generator.generate(simple_ontology)

        # Check title appears in index
        index_content = (output_dir / "index.html").read_text()
        assert "Custom Documentation Title" in index_content


class TestConvenienceFunction:
    """Tests for the generate_docs convenience function."""

    def test_generate_docs_basic(self, tmp_path: Path):
        """Test basic usage of generate_docs function."""
        # Create a minimal test ontology file
        ontology_file = tmp_path / "test.ttl"
        ontology_file.write_text(
            """
            @prefix ex: <http://example.org/> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

            ex:TestOntology a owl:Ontology ;
                rdfs:label "Test" .

            ex:Thing a owl:Class ;
                rdfs:label "Thing" .
        """
        )

        output_dir = tmp_path / "docs"

        result = generate_docs(
            source=ontology_file,
            output_dir=output_dir,
            output_format="html",
        )

        assert result.output_dir == output_dir
        assert (output_dir / "index.html").exists()


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_ontology(self, output_dir: Path):
        """Test generation with minimal/empty ontology."""
        g = Graph()
        g.bind("ex", EX)

        config = DocsConfig(output_dir=output_dir, format="html")
        generator = DocsGenerator(config)

        result = generator.generate(g)

        assert result.classes_count == 0
        assert (output_dir / "index.html").exists()

    def test_class_without_label(self, output_dir: Path):
        """Test handling of classes without labels."""
        g = Graph()
        g.bind("ex", EX)
        g.add((EX.UnlabelledClass, RDF.type, OWL.Class))

        config = DocsConfig(output_dir=output_dir, format="html")
        generator = DocsGenerator(config)

        result = generator.generate(g)

        # Should still generate, using QName as fallback
        assert result.classes_count == 1

    def test_circular_hierarchy(self, output_dir: Path):
        """Test handling of circular class hierarchies."""
        g = Graph()
        g.bind("ex", EX)

        # Create circular hierarchy (shouldn't happen in valid ontologies)
        g.add((EX.A, RDF.type, OWL.Class))
        g.add((EX.B, RDF.type, OWL.Class))
        g.add((EX.A, RDFS.subClassOf, EX.B))
        g.add((EX.B, RDFS.subClassOf, EX.A))

        config = DocsConfig(output_dir=output_dir, format="html")
        generator = DocsGenerator(config)

        # Should not crash
        result = generator.generate(g)
        assert result.classes_count == 2


class TestPathResolution:
    """Tests for HTML path resolution across the docs output tree.

    Regression tests for issue #59: with the default empty ``base_url``,
    generated HTML used leading-slash references (``/assets/style.css``,
    ``/index.html``, …) that resolve against the filesystem or web root
    rather than the docs directory, breaking ``file://`` browsing and
    sub-path hosting (GitHub Pages project sites, etc.).
    """

    def test_relative_url_prefix_top_level(self):
        """A page at the root has prefix '.'."""
        assert relative_url_prefix(Path("index.html")) == "."
        assert relative_url_prefix("hierarchy.html") == "."

    def test_relative_url_prefix_one_level_deep(self):
        """A page in a sub-folder has prefix '..'."""
        assert relative_url_prefix(Path("classes/Foo.html")) == ".."
        assert relative_url_prefix(Path("instances/Bar.html")) == ".."

    def test_relative_url_prefix_two_levels_deep(self):
        """A page two levels deep has prefix '../..'."""
        assert relative_url_prefix(Path("properties/object/has_foo.html")) == "../.."
        assert relative_url_prefix(Path("properties/datatype/has_bar.html")) == "../.."

    def test_entity_to_url_default_no_from_path(self):
        """Without from_path, entity_to_url returns a bare relative path."""
        config = DocsConfig(format="html")
        url = entity_to_url("ex:Building", "class", config)
        assert url == "classes/Building.html"

    def test_entity_to_url_with_from_path_top_level(self):
        """From a top-level page, entity_to_url returns the bare path."""
        config = DocsConfig(format="html")
        url = entity_to_url("ex:Building", "class", config, from_path=Path("index.html"))
        assert url == "classes/Building.html"

    def test_entity_to_url_with_from_path_sub_folder(self):
        """From a sub-folder page, entity_to_url returns a '..'-prefixed path."""
        config = DocsConfig(format="html")
        url = entity_to_url(
            "ex:Building",
            "class",
            config,
            from_path=Path("classes/Other.html"),
        )
        assert url == "../classes/Building.html"

    def test_entity_to_url_with_from_path_two_levels(self):
        """From a two-level-deep page, entity_to_url uses '../..'."""
        config = DocsConfig(format="html")
        url = entity_to_url(
            "ex:Building",
            "class",
            config,
            from_path=Path("properties/object/has_part.html"),
        )
        assert url == "../../classes/Building.html"

    def test_entity_to_url_base_url_overrides_from_path(self):
        """When base_url is set, from_path is ignored (existing behaviour)."""
        config = DocsConfig(format="html", base_url="https://example.com/docs")
        url = entity_to_url(
            "ex:Building",
            "class",
            config,
            from_path=Path("classes/Other.html"),
        )
        assert url == "https://example.com/docs/classes/Building.html"

    def test_no_leading_slash_paths_in_any_output(self, simple_ontology: Graph, output_dir: Path):
        """Default config must not emit leading-slash href/src refs anywhere.

        With ``base_url=""`` (the default), every layout asset and nav link
        used to be written as ``/assets/style.css``, ``/index.html``, etc.
        These break under ``file://`` and sub-path hosting. None should
        appear in any output file.
        """
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(simple_ontology)

        offenders: list[tuple[Path, str]] = []
        for html_file in output_dir.rglob("*.html"):
            for line in html_file.read_text().splitlines():
                if 'href="/' in line or 'src="/' in line:
                    offenders.append((html_file.relative_to(output_dir), line.strip()))

        assert not offenders, (
            "Found leading-slash href/src references that would break under "
            "file:// or sub-path hosting:\n" + "\n".join(f"  {p}: {line}" for p, line in offenders)
        )

    def test_layout_assets_resolve_from_top_level_pages(
        self, simple_ontology: Graph, output_dir: Path
    ):
        """The CSS reference on a top-level page resolves to assets/style.css."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(simple_ontology)

        index_html = (output_dir / "index.html").read_text()
        assert 'href="./assets/style.css"' in index_html
        assert 'href="./index.html"' in index_html
        assert 'href="./hierarchy.html"' in index_html
        assert 'href="./namespaces.html"' in index_html

    def test_layout_assets_resolve_from_sub_folder_pages(
        self, simple_ontology: Graph, output_dir: Path
    ):
        """A class page at depth 1 references layout assets via '..'."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(simple_ontology)

        dog_html = (output_dir / "classes" / "Dog.html").read_text()
        assert 'href="../assets/style.css"' in dog_html
        assert 'href="../index.html"' in dog_html
        assert 'href="../hierarchy.html"' in dog_html
        assert 'href="../namespaces.html"' in dog_html

    def test_layout_assets_resolve_from_two_level_pages(
        self, simple_ontology: Graph, output_dir: Path
    ):
        """A property page at depth 2 references layout assets via '../..'."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(simple_ontology)

        prop_html = (output_dir / "properties" / "object" / "hasOwner.html").read_text()
        assert 'href="../../assets/style.css"' in prop_html
        assert 'href="../../index.html"' in prop_html
        assert 'href="../../hierarchy.html"' in prop_html
        assert 'href="../../namespaces.html"' in prop_html

    def test_entity_links_resolve_to_existing_files(self, simple_ontology: Graph, output_dir: Path):
        """Entity-to-entity links must resolve to files that actually exist.

        The bug also affected entity links from sub-folder pages: from
        ``classes/Dog.html``, the link ``classes/Animal.html`` resolved
        to ``classes/classes/Animal.html``. Following each ``href`` in
        every page should land on a real file.
        """
        import re

        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(simple_ontology)

        broken: list[tuple[Path, str, Path]] = []
        href_pat = re.compile(r'href="([^"#?]+)"')
        for html_file in output_dir.rglob("*.html"):
            page_dir = html_file.parent
            for href in href_pat.findall(html_file.read_text()):
                # Skip external links and anchors
                if href.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                # Skip script/CSS — covered by separate tests
                if href.endswith((".css", ".js")):
                    continue
                target = (page_dir / href).resolve()
                if not target.exists():
                    broken.append((html_file.relative_to(output_dir), href, target))

        assert not broken, "Internal links did not resolve to existing files:\n" + "\n".join(
            f"  {p}: href={h!r} -> {t}" for p, h, t in broken
        )

    def test_explicit_base_url_still_used(self, simple_ontology: Graph, output_dir: Path):
        """When base_url is set, layout/entity URLs use it (not relative paths)."""
        config = DocsConfig(
            output_dir=output_dir,
            format="html",
            base_url="https://example.com/docs",
        )
        DocsGenerator(config).generate(simple_ontology)

        for rel in ("index.html", "classes/Dog.html"):
            html = (output_dir / rel).read_text()
            assert 'href="https://example.com/docs/assets/style.css"' in html
            assert 'href="https://example.com/docs/index.html"' in html
            # And no relative-prefix paths on layout assets
            assert 'href="./assets/style.css"' not in html
            assert 'href="../assets/style.css"' not in html

    @pytest.mark.parametrize("fixture_name", ["shape_ontology", "skos_vocabulary"])
    def test_all_links_resolve_for_every_entity_kind(
        self,
        fixture_name: str,
        request: pytest.FixtureRequest,
        output_dir: Path,
    ):
        """Every page of every entity kind must have resolvable links.

        The sibling tests above run against ``simple_ontology``, which has
        no SHACL shapes — so they cannot see a render method that skips
        ``_render_page()`` and leaves its pages on the ``.`` fallback.
        ``render_shape`` was added that way in #60 and every reference on a
        ``shapes/`` page broke.

        This runs the same walk over an ontology carrying a class, an
        instance, a property and both shape kinds, so a new entity type
        added without going through ``_render_page()`` fails here rather
        than shipping. It runs again over the SKOS vocabulary (#63) for
        the same reason: a guard is only as general as its fixture.
        """
        import re

        graph = request.getfixturevalue(fixture_name)
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(graph)

        # The point of the test is lost if the fixture stops producing
        # pages at depth — assert the tree actually has them.
        subdir = "shapes" if fixture_name == "shape_ontology" else "concepts"
        assert list(output_dir.glob(f"{subdir}/*.html")), "fixture generated no pages at depth"

        broken: list[tuple[Path, str, Path]] = []
        ref_pat = re.compile(r'(?:href|src)="([^"#?]+)"')
        for html_file in output_dir.rglob("*.html"):
            for ref in ref_pat.findall(html_file.read_text()):
                if ref.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = (html_file.parent / ref).resolve()
                if not target.exists():
                    broken.append((html_file.relative_to(output_dir), ref, target))

        assert not broken, "References did not resolve to existing files:\n" + "\n".join(
            f"  {p}: {r!r} -> {t}" for p, r, t in broken
        )


# ---------------------------------------------------------------------------
# SHACL shape support — issue #60 / milestone v0.5.0 stage 1
# ---------------------------------------------------------------------------


@pytest.fixture
def shape_ontology() -> Graph:
    """Create an ontology with SHACL shapes for testing.

    Includes:
    - A class (Person) and an instance (Alice) — for verifying that
      shapes don't pollute the instance bucket and for cross-references.
    - A datatype property (hasName) — referenced by sh:path.
    - A NodeShape (PersonShape) with one blank-node PropertyShape
      (constraints on hasName) and one named PropertyShape arc
      (AgeConstraint).
    - A named PropertyShape (AgeConstraint) with its own URI and
      constraints — referenced from PersonShape.property and also
      standing alone.
    - A long-tail SHACL constraint (sh:severity) on the blank-node
      PropertyShape — exercises the generic fallback rendering.
    """
    g = Graph()
    g.bind("ex", EX)
    g.bind("sh", SH)

    g.add((EX.MyOnt, RDF.type, OWL.Ontology))
    g.add((EX.MyOnt, RDFS.label, Literal("Shape Demo")))

    # Class + property + instance for context
    g.add((EX.Person, RDF.type, OWL.Class))
    g.add((EX.Person, RDFS.label, Literal("Person")))
    g.add((EX.hasName, RDF.type, OWL.DatatypeProperty))
    g.add((EX.hasName, RDFS.domain, EX.Person))
    g.add((EX.hasName, RDFS.range, XSD.string))
    g.add((EX.hasName, RDFS.label, Literal("has name")))
    g.add((EX.Alice, RDF.type, EX.Person))
    g.add((EX.Alice, RDFS.label, Literal("Alice")))

    # NodeShape with blank-node and named PropertyShape arcs
    g.add((EX.PersonShape, RDF.type, SH.NodeShape))
    g.add((EX.PersonShape, RDFS.label, Literal("Person Shape")))
    g.add((EX.PersonShape, RDFS.comment, Literal("Constraints on Person.")))
    g.add((EX.PersonShape, SH.targetClass, EX.Person))
    g.add((EX.PersonShape, SH.closed, Literal(False)))

    ps_name = BNode()
    g.add((EX.PersonShape, SH.property, ps_name))
    g.add((ps_name, SH.path, EX.hasName))
    g.add((ps_name, SH.minCount, Literal(1)))
    g.add((ps_name, SH.maxCount, Literal(1)))
    g.add((ps_name, SH.datatype, XSD.string))
    g.add((ps_name, SH.maxLength, Literal(100)))
    # Long-tail SHACL constraint — exercises the generic fallback
    g.add((ps_name, SH.severity, SH.Violation))

    # Named PropertyShape, also referenced from PersonShape
    g.add((EX.AgeConstraint, RDF.type, SH.PropertyShape))
    g.add((EX.AgeConstraint, RDFS.label, Literal("Age Constraint")))
    g.add((EX.AgeConstraint, SH.path, EX.hasAge))
    g.add((EX.AgeConstraint, SH.datatype, XSD.integer))
    g.add((EX.AgeConstraint, SH.minInclusive, Literal(0)))
    g.add((EX.AgeConstraint, SH.maxInclusive, Literal(150)))
    g.add((EX.PersonShape, SH.property, EX.AgeConstraint))

    return g


class TestShapeExtraction:
    """Tests for ShapeInfo extraction (acceptance criteria 1 & 2 of #60)."""

    def test_node_shape_extracted(self, shape_ontology: Graph):
        """NodeShape is recognised as a shape with the right kinds."""
        entities = extract_all(shape_ontology)
        person_shape = next(
            (s for s in entities.shapes if "PersonShape" in s.qname),
            None,
        )
        assert person_shape is not None
        assert EntityKind.SHAPE in person_shape.kinds
        assert EntityKind.NODE_SHAPE in person_shape.kinds
        assert EntityKind.PROPERTY_SHAPE not in person_shape.kinds

    def test_named_property_shape_extracted(self, shape_ontology: Graph):
        """Named PropertyShape gets its own ShapeInfo entry."""
        entities = extract_all(shape_ontology)
        age_constraint = next(
            (s for s in entities.shapes if "AgeConstraint" in s.qname),
            None,
        )
        assert age_constraint is not None
        assert EntityKind.SHAPE in age_constraint.kinds
        assert EntityKind.PROPERTY_SHAPE in age_constraint.kinds
        assert EntityKind.NODE_SHAPE not in age_constraint.kinds

    def test_node_shape_target_class(self, shape_ontology: Graph):
        """NodeShape's sh:targetClass populates target_classes."""
        entities = extract_all(shape_ontology)
        person_shape = next(s for s in entities.shapes if "PersonShape" in s.qname)
        assert len(person_shape.target_classes) == 1
        assert str(person_shape.target_classes[0]) == str(EX.Person)

    def test_blank_node_property_shape_inline_on_parent(self, shape_ontology: Graph):
        """Blank-node PropertyShapes appear inline on their parent NodeShape.

        They do NOT get their own standalone ShapeInfo entry — they're
        only accessible via the parent's `properties` list.
        """
        entities = extract_all(shape_ontology)
        person_shape = next(s for s in entities.shapes if "PersonShape" in s.qname)

        # Should have 2 property arcs: one blank (hasName), one named (AgeConstraint)
        assert len(person_shape.properties) == 2
        blank_props = [p for p in person_shape.properties if p.is_blank]
        named_props = [p for p in person_shape.properties if not p.is_blank]
        assert len(blank_props) == 1
        assert len(named_props) == 1

        # The blank one constrains hasName
        assert str(blank_props[0].path) == str(EX.hasName)

        # And it has no standalone ShapeInfo entry
        blank_node_shapes = [
            s for s in entities.shapes if s.uri is None or "hasName" in str(s.uri).lower()
        ]
        assert blank_node_shapes == [], "Blank-node PropertyShape leaked as standalone"

    def test_named_property_shape_referenced_inline_too(self, shape_ontology: Graph):
        """Named PropertyShape appears both standalone and inline on parent."""
        entities = extract_all(shape_ontology)
        person_shape = next(s for s in entities.shapes if "PersonShape" in s.qname)
        # Inline reference on parent
        named_inline = [p for p in person_shape.properties if not p.is_blank]
        assert len(named_inline) == 1
        assert "AgeConstraint" in (named_inline[0].qname or "")
        # Standalone entry
        age_constraint = next(s for s in entities.shapes if "AgeConstraint" in s.qname)
        assert age_constraint is not None

    def test_first_class_constraints_extracted(self, shape_ontology: Graph):
        """All populated first-class constraints land in named fields."""
        entities = extract_all(shape_ontology)
        person_shape = next(s for s in entities.shapes if "PersonShape" in s.qname)
        blank_ps = next(p for p in person_shape.properties if p.is_blank)

        assert str(blank_ps.path) == str(EX.hasName)
        assert blank_ps.min_count == 1
        assert blank_ps.max_count == 1
        assert str(blank_ps.datatype) == str(XSD.string)
        assert blank_ps.max_length == 100

    def test_long_tail_constraint_falls_back(self, shape_ontology: Graph):
        """Unknown SHACL predicates land in other_constraints, not silently dropped."""
        entities = extract_all(shape_ontology)
        person_shape = next(s for s in entities.shapes if "PersonShape" in s.qname)
        blank_ps = next(p for p in person_shape.properties if p.is_blank)

        # sh:severity isn't first-class — should be in other_constraints
        severity_pred = SH.severity
        assert severity_pred in blank_ps.other_constraints
        values = blank_ps.other_constraints[severity_pred]
        assert len(values) == 1

    def test_shapes_excluded_from_instances(self, shape_ontology: Graph):
        """Shapes do not appear in the instances list (the central #60 bug)."""
        entities = extract_all(shape_ontology)
        instance_qnames = {i.qname for i in entities.instances}
        # Alice should be there
        assert "ex:Alice" in instance_qnames
        # PersonShape and AgeConstraint should NOT
        assert "ex:PersonShape" not in instance_qnames
        assert "ex:AgeConstraint" not in instance_qnames

    def test_node_shapes_property_filters_correctly(self, shape_ontology: Graph):
        """ExtractedEntities.node_shapes returns only NodeShapes."""
        entities = extract_all(shape_ontology)
        ns = entities.node_shapes
        assert len(ns) == 1
        assert "PersonShape" in ns[0].qname

    def test_property_shapes_property_filters_correctly(self, shape_ontology: Graph):
        """ExtractedEntities.property_shapes returns only PropertyShapes."""
        entities = extract_all(shape_ontology)
        ps = entities.property_shapes
        assert len(ps) == 1
        assert "AgeConstraint" in ps[0].qname

    def test_multi_kind_node_shape_also_named_individual(self):
        """A NodeShape that's also owl:NamedIndividual still appears in shapes.

        This is the canonical multi-kind case the panel review highlighted.
        Should appear in shapes (priority order places shape ahead of
        named_individual) — and must NOT also appear in instances.
        """
        g = Graph()
        g.bind("ex", EX)
        g.add((EX.MyShape, RDF.type, SH.NodeShape))
        g.add((EX.MyShape, RDF.type, OWL.NamedIndividual))

        entities = extract_all(g)
        shape_qnames = {s.qname for s in entities.shapes}
        instance_qnames = {i.qname for i in entities.instances}

        assert "ex:MyShape" in shape_qnames
        # And shouldn't double-up in instances
        assert "ex:MyShape" not in instance_qnames

    def test_sh_in_walks_rdf_list(self):
        """sh:in is an rdf:List — its members should be walked into in_values."""
        g = Graph()
        g.bind("ex", EX)
        g.add((EX.S, RDF.type, SH.PropertyShape))
        g.add((EX.S, SH.path, EX.colour))

        # rdf:List of three values: red, green, blue
        list_head = BNode()
        list_mid = BNode()
        list_tail = BNode()
        g.add((EX.S, SH["in"], list_head))
        g.add((list_head, RDF.first, Literal("red")))
        g.add((list_head, RDF.rest, list_mid))
        g.add((list_mid, RDF.first, Literal("green")))
        g.add((list_mid, RDF.rest, list_tail))
        g.add((list_tail, RDF.first, Literal("blue")))
        g.add((list_tail, RDF.rest, RDF.nil))

        entities = extract_all(g)
        shape = next(s for s in entities.shapes if "S" == s.qname.split(":")[-1])
        assert shape.property_shape is not None
        assert shape.property_shape.in_values == ["red", "green", "blue"]


class TestShapeRendering:
    """Tests for shape rendering across HTML, Markdown, and JSON formats.

    Covers acceptance criteria 3, 4, 5, 6, 7 of #60: shape pages
    appear with kind badges, blank-node and named PropertyShapes
    render correctly, all 21 first-class constraints render, the
    generic fallback works, and JSON output uses the new schema.
    """

    def test_html_renders_shape_pages(self, shape_ontology: Graph, output_dir: Path):
        """HTML format produces shape pages under shapes/."""
        config = DocsConfig(output_dir=output_dir, format="html")
        result = DocsGenerator(config).generate(shape_ontology)

        assert result.shapes_count == 2
        assert (output_dir / "shapes" / "PersonShape.html").exists()
        assert (output_dir / "shapes" / "AgeConstraint.html").exists()

    def test_markdown_renders_shape_pages(self, shape_ontology: Graph, output_dir: Path):
        """Markdown format produces shape pages under shapes/."""
        config = DocsConfig(output_dir=output_dir, format="markdown")
        result = DocsGenerator(config).generate(shape_ontology)

        assert result.shapes_count == 2
        assert (output_dir / "shapes" / "PersonShape.md").exists()
        assert (output_dir / "shapes" / "AgeConstraint.md").exists()

    def test_json_renders_shape_pages(self, shape_ontology: Graph, output_dir: Path):
        """JSON format produces shape pages under shapes/."""
        config = DocsConfig(output_dir=output_dir, format="json")
        result = DocsGenerator(config).generate(shape_ontology)

        assert result.shapes_count == 2
        assert (output_dir / "shapes" / "PersonShape.json").exists()
        assert (output_dir / "shapes" / "AgeConstraint.json").exists()

    def test_html_kind_badges(self, shape_ontology: Graph, output_dir: Path):
        """HTML shape pages include kind badges (node_shape / property_shape)."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(shape_ontology)

        ns_html = (output_dir / "shapes" / "PersonShape.html").read_text()
        assert "node_shape" in ns_html
        assert "node shape" in ns_html  # human-readable label

        ps_html = (output_dir / "shapes" / "AgeConstraint.html").read_text()
        assert "property_shape" in ps_html
        assert "property shape" in ps_html

    def test_html_blank_property_shape_inline(self, shape_ontology: Graph, output_dir: Path):
        """Blank-node PropertyShape constraints render inline on parent NodeShape."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(shape_ontology)

        ns_html = (output_dir / "shapes" / "PersonShape.html").read_text()
        # Constraint table values from the blank-node PropertyShape
        assert "Min Count" in ns_html
        assert "Max Length" in ns_html
        assert "Datatype" in ns_html
        # Path should resolve to a link (hasName is in the ontology)
        assert 'href="' in ns_html and "hasName" in ns_html

    def test_html_named_property_shape_linked_inline(self, shape_ontology: Graph, output_dir: Path):
        """Named PropertyShape inline reference includes a link to its own page."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(shape_ontology)

        ns_html = (output_dir / "shapes" / "PersonShape.html").read_text()
        # Should link to AgeConstraint.html somewhere in the page
        assert "AgeConstraint.html" in ns_html

    def test_html_long_tail_constraint_visible(self, shape_ontology: Graph, output_dir: Path):
        """Long-tail SHACL predicates render in the generic fallback area, not silently dropped."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(shape_ontology)

        ns_html = (output_dir / "shapes" / "PersonShape.html").read_text()
        # sh:severity is a long-tail constraint — should appear by URI
        assert "shacl#severity" in ns_html

    def test_html_target_class_cross_reference(self, shape_ontology: Graph, output_dir: Path):
        """sh:targetClass links to the class's docs page when in the ontology."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(shape_ontology)

        ns_html = (output_dir / "shapes" / "PersonShape.html").read_text()
        # The target class Person is in the ontology — should link
        assert 'href="' in ns_html and "Person.html" in ns_html

    def test_markdown_kind_in_frontmatter(self, shape_ontology: Graph, output_dir: Path):
        """Markdown frontmatter type field carries the most-specific kind."""
        config = DocsConfig(output_dir=output_dir, format="markdown")
        DocsGenerator(config).generate(shape_ontology)

        ns_md = (output_dir / "shapes" / "PersonShape.md").read_text()
        assert "type: node_shape" in ns_md

        ps_md = (output_dir / "shapes" / "AgeConstraint.md").read_text()
        assert "type: property_shape" in ps_md

    def test_markdown_constraint_table(self, shape_ontology: Graph, output_dir: Path):
        """Markdown shape pages include a GFM constraint table."""
        config = DocsConfig(output_dir=output_dir, format="markdown")
        DocsGenerator(config).generate(shape_ontology)

        ns_md = (output_dir / "shapes" / "PersonShape.md").read_text()
        # GFM table header
        assert "| Constraint | Value |" in ns_md
        assert "| --- | --- |" in ns_md
        # First-class constraint values
        assert "Min Count" in ns_md
        assert "Datatype" in ns_md

    def test_json_breaking_change_shapes_not_in_instances(
        self, shape_ontology: Graph, output_dir: Path
    ):
        """Breaking change: shapes are NOT in the instances array of index.json."""
        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(shape_ontology)

        idx = json.loads((output_dir / "index.json").read_text())
        instance_qnames = {i["qname"] for i in idx["instances"]}
        assert "ex:PersonShape" not in instance_qnames
        assert "ex:AgeConstraint" not in instance_qnames
        # And ex:Alice (a real instance) IS there
        assert "ex:Alice" in instance_qnames

    def test_json_top_level_shapes_array(self, shape_ontology: Graph, output_dir: Path):
        """index.json gains a top-level 'shapes' array with shape summaries."""
        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(shape_ontology)

        idx = json.loads((output_dir / "index.json").read_text())
        assert "shapes" in idx
        shape_qnames = {s["qname"] for s in idx["shapes"]}
        assert "ex:PersonShape" in shape_qnames
        assert "ex:AgeConstraint" in shape_qnames
        # Each summary entry includes kinds
        for s in idx["shapes"]:
            assert "kinds" in s
            assert isinstance(s["kinds"], list)

    def test_json_statistics_includes_shapes(self, shape_ontology: Graph, output_dir: Path):
        """index.json statistics object includes a 'shapes' count."""
        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(shape_ontology)

        idx = json.loads((output_dir / "index.json").read_text())
        assert idx["statistics"]["shapes"] == 2

    def test_json_full_shape_schema(self, shape_ontology: Graph, output_dir: Path):
        """A full shape JSON file has the agreed schema keys."""
        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(shape_ontology)

        ps_json = json.loads((output_dir / "shapes" / "PersonShape.json").read_text())
        # Top-level keys
        for key in [
            "uri",
            "qname",
            "kinds",
            "label",
            "definition",
            "target_classes",
            "target_nodes",
            "target_subjects_of",
            "target_objects_of",
            "closed",
            "ignored_properties",
            "properties",
            "property_shape",
            "annotations",
            "other_constraints",
        ]:
            assert key in ps_json, f"shape JSON missing key: {key}"

        # Inline blank PropertyShape schema
        prop = ps_json["properties"][0]
        for key in [
            "uri",
            "qname",
            "is_blank",
            "path",
            "name",
            "description",
            "datatype",
            "class",
            "node_kind",
            "min_count",
            "max_count",
            "min_length",
            "max_length",
            "min_inclusive",
            "max_inclusive",
            "pattern",
            "has_value",
            "in_values",
            "other_constraints",
        ]:
            assert key in prop, f"property shape JSON missing key: {key}"

    def test_json_uses_class_not_class_underscore(self, shape_ontology: Graph, output_dir: Path):
        """JSON key is 'class' (matches SHACL spec), not 'class_'."""
        # Add a sh:class constraint to verify
        g = shape_ontology
        ps_extra = BNode()
        g.add((EX.PersonShape, SH.property, ps_extra))
        g.add((ps_extra, SH.path, EX.knows))
        g.add((ps_extra, SH["class"], EX.Person))

        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(g)

        ps_json = json.loads((output_dir / "shapes" / "PersonShape.json").read_text())
        # Find the property shape that has a class constraint
        with_class = [p for p in ps_json["properties"] if p.get("class") is not None]
        assert len(with_class) >= 1
        assert "class_" not in with_class[0]


class TestShapeIndexAndSinglePage:
    """Tests for shapes appearing in index and single-page outputs."""

    def test_html_index_has_shapes_section(self, shape_ontology: Graph, output_dir: Path):
        """HTML index.html includes a Shapes section."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(shape_ontology)

        idx = (output_dir / "index.html").read_text()
        assert "<h2>Shapes</h2>" in idx
        assert "PersonShape" in idx or "Person Shape" in idx

    def test_markdown_index_has_shapes_section(self, shape_ontology: Graph, output_dir: Path):
        """Markdown index.md includes a Shapes section."""
        config = DocsConfig(output_dir=output_dir, format="markdown")
        DocsGenerator(config).generate(shape_ontology)

        idx = (output_dir / "index.md").read_text()
        assert "## Shapes" in idx

    def test_html_single_page_has_shapes(self, shape_ontology: Graph, output_dir: Path):
        """HTML single-page output includes a Shapes section."""
        config = DocsConfig(output_dir=output_dir, format="html", single_page=True)
        DocsGenerator(config).generate(shape_ontology)

        text = (output_dir / "index.html").read_text()
        assert '<section id="shapes">' in text


class TestShapeSearchIndex:
    """Tests for shapes appearing in the search index."""

    def test_shapes_appear_in_search_index(self, shape_ontology: Graph):
        """Shapes appear with entity_type='shape' and the right kinds."""
        entities = extract_all(shape_ontology)
        config = DocsConfig()
        index = generate_search_index(entities, config)

        shape_entries = [e for e in index if e.entity_type == "shape"]
        assert len(shape_entries) == 2
        qnames = {e.qname for e in shape_entries}
        assert "ex:PersonShape" in qnames
        assert "ex:AgeConstraint" in qnames

    def test_search_entry_kinds_field_populated(self, shape_ontology: Graph):
        """SearchEntry.kinds carries the full multi-kind list."""
        entities = extract_all(shape_ontology)
        config = DocsConfig()
        index = generate_search_index(entities, config)

        ns_entry = next(e for e in index if e.qname == "ex:PersonShape")
        assert "node_shape" in ns_entry.kinds
        assert "shape" in ns_entry.kinds

    def test_search_target_class_indexed(self, shape_ontology: Graph):
        """Searching for the target class name surfaces the shape."""
        entities = extract_all(shape_ontology)
        config = DocsConfig()
        index = generate_search_index(entities, config)

        ns_entry = next(e for e in index if e.qname == "ex:PersonShape")
        # 'person' (from Person target class) should be a keyword
        assert "person" in ns_entry.keywords


class TestIncludeShapesFlag:
    """Tests for the --include-shapes / config.include_shapes toggle."""

    def test_default_include_shapes_true(self):
        """include_shapes defaults to True."""
        assert DocsConfig().include_shapes is True

    def test_include_shapes_from_dict(self):
        """include_shapes is settable via from_dict (YAML config)."""
        cfg = DocsConfig.from_dict({"include_shapes": False})
        assert cfg.include_shapes is False

    def test_include_shapes_false_excludes_pages(self, shape_ontology: Graph, output_dir: Path):
        """include_shapes=False produces no shape pages or shapes/ dir."""
        config = DocsConfig(
            output_dir=output_dir,
            format="html",
            include_shapes=False,
        )
        result = DocsGenerator(config).generate(shape_ontology)
        assert result.shapes_count == 0
        assert not (output_dir / "shapes").exists()

    def test_include_shapes_false_excludes_from_search(self, shape_ontology: Graph):
        """include_shapes=False excludes shapes from the search index."""
        entities = extract_all(shape_ontology)
        config = DocsConfig(include_shapes=False)
        index = generate_search_index(entities, config)
        shape_entries = [e for e in index if e.entity_type == "shape"]
        assert shape_entries == []


class TestShapeRouting:
    """Tests for shape URL/path generation."""

    def test_shape_path_under_shapes_directory(self):
        """entity_to_path routes shapes under shapes/."""
        config = DocsConfig(format="html")
        path = entity_to_path("ex:PersonShape", "shape", config)
        assert path == Path("shapes/PersonShape.html")

    def test_shape_path_with_entity_kind_enum(self):
        """entity_to_path accepts an EntityKind member directly (str-equivalent)."""
        config = DocsConfig(format="html")
        path = entity_to_path("ex:PersonShape", EntityKind.SHAPE, config)
        assert path == Path("shapes/PersonShape.html")


class TestEntityKindEnum:
    """Tests for the EntityKind enum behaviour.

    These verify the str-mixin contract that the rest of the docs
    module relies on: enum members compare equal to their string
    values, render as their values in templates and JSON, and survive
    round-tripping through json.dumps as plain strings.
    """

    def test_enum_equals_string_value(self):
        assert EntityKind.SHAPE == "shape"
        assert "shape" == EntityKind.SHAPE
        assert EntityKind.NODE_SHAPE == "node_shape"

    def test_str_returns_value(self):
        """str() returns the enum value (overrides 3.11+ default)."""
        assert str(EntityKind.SHAPE) == "shape"
        assert str(EntityKind.NODE_SHAPE) == "node_shape"

    def test_fstring_renders_value(self):
        """f-strings render the value, not 'EntityKind.SHAPE'."""
        assert f"{EntityKind.SHAPE}" == "shape"

    def test_json_serialises_as_plain_string(self):
        """json.dumps emits the value as a plain string."""
        assert json.dumps(EntityKind.SHAPE) == '"shape"'
        assert json.dumps([EntityKind.SHAPE, EntityKind.NODE_SHAPE]) == '["shape", "node_shape"]'

    def test_enum_in_string_list(self):
        """String-based 'in' checks work both ways."""
        kinds = [EntityKind.SHAPE, EntityKind.NODE_SHAPE]
        assert "shape" in kinds
        assert EntityKind.SHAPE in kinds
        assert "instance" not in kinds


# ---------------------------------------------------------------------------
# SKOS support — issue #63 / milestone v0.6.0 stage 2
# ---------------------------------------------------------------------------


SKOS_FIXTURE = Path(__file__).parent / "fixtures" / "docs" / "skos_vocabulary.ttl"


@pytest.fixture
def skos_vocabulary() -> Graph:
    """Load the tracked SKOS test vocabulary.

    The repository had no SKOS structure at all before #63 — no
    ``skos:Concept``, ``skos:ConceptScheme``, ``broader``, ``narrower`` or
    ``inScheme`` anywhere — so this fixture is the material the acceptance
    criteria are demonstrated against. See the file's own header for what
    it exercises, including the deliberate ``skos:broader`` cycle.
    """
    g = Graph()
    g.parse(SKOS_FIXTURE, format="turtle")
    return g


def _concept(entities: ExtractedEntities, local_name: str) -> ConceptInfo:
    """Find a concept by the local part of its qname."""
    return next(c for c in entities.concepts if c.qname.split(":")[-1] == local_name)


class TestSKOSExtraction:
    """Tests for ConceptInfo / ConceptSchemeInfo extraction."""

    def test_concepts_extracted(self, skos_vocabulary: Graph):
        """skos:Concept subjects land in the concepts bucket with the right kind."""
        entities = extract_all(skos_vocabulary)
        qnames = {c.qname for c in entities.concepts}
        assert "ex:Building" in qnames
        assert "ex:Dwelling" in qnames
        for concept in entities.concepts:
            assert EntityKind.SKOS_CONCEPT in concept.kinds

    def test_concept_schemes_extracted(self, skos_vocabulary: Graph):
        """skos:ConceptScheme subjects get their own bucket and kind."""
        entities = extract_all(skos_vocabulary)
        qnames = {s.qname for s in entities.concept_schemes}
        assert qnames == {"ex:BuildingScheme", "ex:HeritageScheme"}
        for scheme in entities.concept_schemes:
            assert EntityKind.SKOS_CONCEPT_SCHEME in scheme.kinds

    def test_concepts_excluded_from_instances(self, skos_vocabulary: Graph):
        """The central #63 change: SKOS entities leave the Instances bucket."""
        entities = extract_all(skos_vocabulary)
        instance_qnames = {i.qname for i in entities.instances}
        # The plain instance is still there
        assert "ex:MainSite" in instance_qnames
        # Concepts and schemes are not
        assert "ex:Building" not in instance_qnames
        assert "ex:BuildingScheme" not in instance_qnames
        assert "ex:Outbuilding" not in instance_qnames

    def test_concept_also_named_individual_routes_to_concepts(self, skos_vocabulary: Graph):
        """A concept that is also owl:NamedIndividual is documented once, as a concept."""
        entities = extract_all(skos_vocabulary)
        building = _concept(entities, "Building")
        assert str(OWL.NamedIndividual) in [str(t) for t in building.types]
        assert "ex:Building" not in {i.qname for i in entities.instances}

    def test_punned_class_keeps_its_class_page(self, skos_vocabulary: Graph):
        """A subject typed both owl:Class and skos:Concept stays a class.

        Classes outrank SKOS in the routing order, so ``ex:Warehouse`` gets
        one page rather than two. It remains visible as a member of its
        scheme, which cross-links to the class page.
        """
        entities = extract_all(skos_vocabulary)
        assert "ex:Warehouse" in {c.qname for c in entities.classes}
        assert "ex:Warehouse" not in {c.qname for c in entities.concepts}
        scheme = next(s for s in entities.concept_schemes if s.qname == "ex:BuildingScheme")
        assert any("Warehouse" in str(uri) for uri in scheme.concepts)

    def test_labels_grouped_by_language(self, skos_vocabulary: Graph):
        """pref/alt/hidden labels group into one row per language tag."""
        entities = extract_all(skos_vocabulary)
        building = _concept(entities, "Building")
        by_lang = {group.language: group for group in building.labels}
        assert set(by_lang) == {"en", "fr"}
        assert by_lang["en"].preferred == ["Building"]
        assert by_lang["en"].alternative == ["Structure"]
        assert by_lang["en"].hidden == ["buildin"]
        assert by_lang["fr"].preferred == ["Bâtiment"]
        assert by_lang["fr"].alternative == ["Édifice"]
        assert by_lang["fr"].hidden == []

    def test_all_seven_note_types_extracted(self, skos_vocabulary: Graph):
        """All seven SKOS documentation properties are captured, with languages."""
        entities = extract_all(skos_vocabulary)
        building = _concept(entities, "Building")
        assert set(building.notes) == {
            "definition",
            "scopeNote",
            "example",
            "note",
            "historyNote",
            "editorialNote",
            "changeNote",
        }
        languages = {value.language for value in building.notes["definition"]}
        assert languages == {"en", "fr"}

    def test_notes_not_duplicated_in_annotations(self, skos_vocabulary: Graph):
        """SKOS notes render from `notes`, so get_annotations' copies are dropped."""
        entities = extract_all(skos_vocabulary)
        building = _concept(entities, "Building")
        for name in ("note", "example", "scopeNote", "historyNote", "editorialNote"):
            assert name not in building.annotations

    def test_broader_materialises_the_inverse_of_narrower(self, skos_vocabulary: Graph):
        """SKOS declares broader/narrower inverse, so one assertion gives both.

        ``ex:ListedBuilding`` asserts ``skos:broader ex:Building`` and
        nothing asserts the narrower direction — the concept still has to
        appear under Building.
        """
        entities = extract_all(skos_vocabulary)
        building = _concept(entities, "Building")
        listed = _concept(entities, "ListedBuilding")
        assert any("ListedBuilding" in str(uri) for uri in building.narrower)
        assert any("Building" in str(uri) for uri in listed.broader)

    def test_broader_and_narrower_deduplicated(self, skos_vocabulary: Graph):
        """A relation asserted in both directions is not listed twice."""
        entities = extract_all(skos_vocabulary)
        dwelling = _concept(entities, "Dwelling")
        assert len(dwelling.broader) == len(set(dwelling.broader))
        assert sum("Building" in str(uri) for uri in dwelling.broader) == 1

    def test_related_is_symmetric(self, skos_vocabulary: Graph):
        """skos:related is symmetric, so both ends carry the relation."""
        entities = extract_all(skos_vocabulary)
        detached = _concept(entities, "DetachedHouse")
        listed = _concept(entities, "ListedBuilding")
        assert any("ListedBuilding" in str(uri) for uri in detached.related)
        assert any("DetachedHouse" in str(uri) for uri in listed.related)

    def test_concept_in_two_schemes(self, skos_vocabulary: Graph):
        """Multiple skos:inScheme memberships are all kept."""
        entities = extract_all(skos_vocabulary)
        listed = _concept(entities, "ListedBuilding")
        assert len(listed.in_schemes) == 2

    def test_top_concept_of_implies_in_scheme(self, skos_vocabulary: Graph):
        """skos:topConceptOf is a sub-property of skos:inScheme."""
        entities = extract_all(skos_vocabulary)
        listed = _concept(entities, "ListedBuilding")
        heritage = next(s for s in entities.concept_schemes if s.qname == "ex:HeritageScheme")
        # ListedBuilding declares topConceptOf HeritageScheme but no inScheme for it
        assert heritage.uri in listed.in_schemes
        assert heritage.uri in listed.top_concept_of

    def test_scheme_members_and_top_concepts(self, skos_vocabulary: Graph):
        """A scheme lists its members and its declared top concepts."""
        entities = extract_all(skos_vocabulary)
        scheme = next(s for s in entities.concept_schemes if s.qname == "ex:BuildingScheme")
        member_names = {str(uri).split("#")[-1] for uri in scheme.concepts}
        assert {"Building", "Dwelling", "DetachedHouse", "ListedBuilding"} <= member_names
        assert [str(uri).split("#")[-1] for uri in scheme.top_concepts] == ["Building"]

    def test_scheme_top_concept_from_inverse(self, skos_vocabulary: Graph):
        """hasTopConcept and topConceptOf are inverses; either assertion counts."""
        entities = extract_all(skos_vocabulary)
        heritage = next(s for s in entities.concept_schemes if s.qname == "ex:HeritageScheme")
        # Only ex:ListedBuilding skos:topConceptOf ex:HeritageScheme is asserted
        assert [str(uri).split("#")[-1] for uri in heritage.top_concepts] == ["ListedBuilding"]

    def test_concept_with_no_scheme_still_extracted(self, skos_vocabulary: Graph):
        """An orphan concept is documented rather than lost."""
        entities = extract_all(skos_vocabulary)
        outbuilding = _concept(entities, "Outbuilding")
        assert outbuilding.in_schemes == []

    def test_mappings_land_in_other_properties(self, skos_vocabulary: Graph):
        """skos:exactMatch gets no special treatment but stays visible."""
        entities = extract_all(skos_vocabulary)
        listed = _concept(entities, "ListedBuilding")
        preds = {str(pred) for pred in listed.properties}
        assert "http://www.w3.org/2004/02/skos/core#exactMatch" in preds

    def test_structural_predicates_not_repeated_in_properties(self, skos_vocabulary: Graph):
        """broader/narrower/inScheme render structurally, not as key-value rows."""
        entities = extract_all(skos_vocabulary)
        dwelling = _concept(entities, "Dwelling")
        preds = {str(pred) for pred in dwelling.properties}
        assert "http://www.w3.org/2004/02/skos/core#broader" not in preds
        assert "http://www.w3.org/2004/02/skos/core#inScheme" not in preds
        assert "http://www.w3.org/2004/02/skos/core#prefLabel" not in preds


class TestSKOSHierarchy:
    """Tests for build_concept_tree, including the cyclic case."""

    def test_tree_nests_three_levels(self, skos_vocabulary: Graph):
        """The broader/narrower tree nests to the depth the vocabulary declares."""
        entities = extract_all(skos_vocabulary)
        scheme = next(s for s in entities.concept_schemes if s.qname == "ex:BuildingScheme")
        tree = build_concept_tree(entities.concepts, scheme.uri)

        building = next(node for node in tree if node.concept.qname == "ex:Building")
        dwelling = next(node for node in building.children if node.concept.qname == "ex:Dwelling")
        assert [child.concept.qname for child in dwelling.children] == ["ex:DetachedHouse"]

    def test_tree_is_rooted_at_declared_top_concepts(self, skos_vocabulary: Graph):
        """Declared top concepts anchor the tree."""
        entities = extract_all(skos_vocabulary)
        scheme = next(s for s in entities.concept_schemes if s.qname == "ex:BuildingScheme")
        tree = build_concept_tree(entities.concepts, scheme.uri)
        assert tree[0].concept.qname == "ex:Building"

    def test_cyclic_broader_terminates(self, skos_vocabulary: Graph):
        """A broader cycle must not send the walker into infinite recursion.

        SKOS does not promise acyclicity. ``ex:LoopA`` and ``ex:LoopB`` are
        each other's broader concept; the walker has to stop and still
        render both.
        """
        entities = extract_all(skos_vocabulary)
        scheme = next(s for s in entities.concept_schemes if s.qname == "ex:BuildingScheme")
        tree = build_concept_tree(entities.concepts, scheme.uri)

        def walk(nodes, depth=0):
            assert depth < 20, "concept tree recursed further than the vocabulary is deep"
            names = []
            for node in nodes:
                names.append(node.concept.qname)
                names.extend(walk(node.children, depth + 1))
            return names

        rendered = walk(tree)
        assert "ex:LoopA" in rendered
        assert "ex:LoopB" in rendered

    def test_cycle_members_are_not_dropped(self, skos_vocabulary: Graph):
        """Every member of the scheme appears in the tree, cycle or not."""
        entities = extract_all(skos_vocabulary)
        scheme = next(s for s in entities.concept_schemes if s.qname == "ex:BuildingScheme")
        tree = build_concept_tree(entities.concepts, scheme.uri)

        def collect(nodes):
            found = set()
            for node in nodes:
                found.add(node.concept.qname)
                found |= collect(node.children)
            return found

        member_concepts = {c.qname for c in entities.concepts if scheme.uri in c.in_schemes}
        assert member_concepts <= collect(tree)

    def test_tree_without_scheme_covers_every_concept(self, skos_vocabulary: Graph):
        """Called with no scheme, the tree spans all concepts including orphans."""
        entities = extract_all(skos_vocabulary)
        tree = build_concept_tree(entities.concepts)

        def collect(nodes):
            found = set()
            for node in nodes:
                found.add(node.concept.qname)
                found |= collect(node.children)
            return found

        assert {c.qname for c in entities.concepts} <= collect(tree)


class TestSKOSRendering:
    """Tests for concept and scheme pages in all three formats."""

    def test_html_renders_concept_pages(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(skos_vocabulary)

        assert (output_dir / "concepts" / "Building.html").exists()
        assert (output_dir / "concepts" / "BuildingScheme.html").exists()

    def test_markdown_renders_concept_pages(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="markdown")
        DocsGenerator(config).generate(skos_vocabulary)

        assert (output_dir / "concepts" / "Building.md").exists()
        assert (output_dir / "concepts" / "BuildingScheme.md").exists()

    def test_json_renders_concept_pages(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(skos_vocabulary)

        assert (output_dir / "concepts" / "Building.json").exists()
        assert (output_dir / "concepts" / "BuildingScheme.json").exists()

    def test_html_kind_badges(self, skos_vocabulary: Graph, output_dir: Path):
        """Concept and scheme pages carry their kind badges."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(skos_vocabulary)

        concept_html = (output_dir / "concepts" / "Building.html").read_text()
        assert 'class="entity-type skos_concept"' in concept_html

        scheme_html = (output_dir / "concepts" / "BuildingScheme.html").read_text()
        assert 'class="entity-type skos_concept_scheme"' in scheme_html

    def test_html_badge_css_present(self, skos_vocabulary: Graph, output_dir: Path):
        """The SKOS badge colours ship in the default stylesheet."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(skos_vocabulary)

        css = (output_dir / "assets" / "style.css").read_text()
        assert ".entity-type.skos_concept { background: #1d4ed8; }" in css
        assert ".entity-type.skos_concept_scheme { background: #1e3a8a; }" in css

    def test_html_multilingual_label_table(self, skos_vocabulary: Graph, output_dir: Path):
        """Labels render one row per language, not as duplicate triples."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(skos_vocabulary)

        html = (output_dir / "concepts" / "Building.html").read_text()
        assert "<th>Preferred</th>" in html
        assert "Bâtiment" in html
        assert "Édifice" in html
        assert "buildin" in html  # hidden label

    def test_html_notes_carry_language_tags(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(skos_vocabulary)

        html = (output_dir / "concepts" / "Building.html").read_text()
        assert "skos:scopeNote" in html
        assert "skos:changeNote" in html
        assert '<span class="lang-tag">fr</span>' in html

    def test_html_scheme_page_has_hierarchy(self, skos_vocabulary: Graph, output_dir: Path):
        """The scheme page carries the vocabulary tree."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(skos_vocabulary)

        html = (output_dir / "concepts" / "BuildingScheme.html").read_text()
        assert "Concept Hierarchy" in html
        assert 'class="concept-tree"' in html
        assert "DetachedHouse.html" in html

    def test_html_concept_cross_references(self, skos_vocabulary: Graph, output_dir: Path):
        """inScheme and broader/narrower render as links, both ways."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(skos_vocabulary)

        html = (output_dir / "concepts" / "Dwelling.html").read_text()
        assert "BuildingScheme.html" in html  # scheme link
        assert "Building.html" in html  # broader link
        assert "DetachedHouse.html" in html  # narrower link

    def test_html_punned_class_member_links_to_class_page(
        self, skos_vocabulary: Graph, output_dir: Path
    ):
        """A member that is documented as a class links to its class page."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(skos_vocabulary)

        html = (output_dir / "concepts" / "BuildingScheme.html").read_text()
        assert "classes/Warehouse.html" in html
        assert not (output_dir / "concepts" / "Warehouse.html").exists()

    def test_markdown_kind_in_frontmatter(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="markdown")
        DocsGenerator(config).generate(skos_vocabulary)

        concept_md = (output_dir / "concepts" / "Building.md").read_text()
        assert "type: skos_concept" in concept_md

        scheme_md = (output_dir / "concepts" / "BuildingScheme.md").read_text()
        assert "type: skos_concept_scheme" in scheme_md

    def test_markdown_label_and_note_tables(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="markdown")
        DocsGenerator(config).generate(skos_vocabulary)

        md = (output_dir / "concepts" / "Building.md").read_text()
        assert "| Language | Preferred | Alternative | Hidden |" in md
        assert "| `fr` | Bâtiment | Édifice |  |" in md
        assert "`skos:historyNote`" in md
        assert "_(fr)_" in md

    def test_markdown_scheme_hierarchy(self, skos_vocabulary: Graph, output_dir: Path):
        """The Markdown scheme page renders the tree as an indented list."""
        config = DocsConfig(output_dir=output_dir, format="markdown")
        DocsGenerator(config).generate(skos_vocabulary)

        md = (output_dir / "concepts" / "BuildingScheme.md").read_text()
        assert "## Concept Hierarchy" in md
        assert "  - [Dwelling]" in md
        assert "    - [Detached House]" in md

    def test_json_breaking_change_concepts_not_in_instances(
        self, skos_vocabulary: Graph, output_dir: Path
    ):
        """JSON instances array no longer carries concepts or schemes."""
        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(skos_vocabulary)

        data = json.loads((output_dir / "index.json").read_text())
        instance_qnames = {i["qname"] for i in data["instances"]}
        assert "ex:Building" not in instance_qnames
        assert "ex:BuildingScheme" not in instance_qnames

    def test_json_top_level_skos_arrays(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(skos_vocabulary)

        data = json.loads((output_dir / "index.json").read_text())
        assert {c["qname"] for c in data["concepts"]} >= {"ex:Building", "ex:Dwelling"}
        assert {s["qname"] for s in data["concept_schemes"]} == {
            "ex:BuildingScheme",
            "ex:HeritageScheme",
        }
        assert data["statistics"]["concepts"] == 7
        assert data["statistics"]["concept_schemes"] == 2

    def test_json_concept_schema(self, skos_vocabulary: Graph, output_dir: Path):
        """The per-concept JSON keeps labels, notes and relations structured."""
        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(skos_vocabulary)

        data = json.loads((output_dir / "concepts" / "Building.json").read_text())
        # ex:Building is also owl:NamedIndividual, so it carries both kinds (#64)
        assert data["kinds"] == ["skos_concept", "named_individual"]
        assert {"labels", "notes", "broader", "narrower", "in_schemes"} <= set(data)

        french = next(group for group in data["labels"] if group["language"] == "fr")
        assert french["preferred"] == ["Bâtiment"]

        definitions = data["notes"]["definition"]
        assert {d["language"] for d in definitions} == {"en", "fr"}

    def test_json_scheme_carries_hierarchy(self, skos_vocabulary: Graph, output_dir: Path):
        """The scheme JSON ships the tree so consumers need not rebuild it."""
        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(skos_vocabulary)

        data = json.loads((output_dir / "concepts" / "BuildingScheme.json").read_text())
        roots = {node["qname"] for node in data["hierarchy"]}
        assert "ex:Building" in roots
        building = next(n for n in data["hierarchy"] if n["qname"] == "ex:Building")
        assert {child["qname"] for child in building["children"]} == {
            "ex:Dwelling",
            "ex:ListedBuilding",
        }

    def test_json_single_page_has_skos_arrays(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="json", single_page=True)
        DocsGenerator(config).generate(skos_vocabulary)

        data = json.loads((output_dir / "ontology.json").read_text())
        assert len(data["concepts"]) == 7
        assert len(data["concept_schemes"]) == 2


class TestSKOSIndexAndSinglePage:
    """Tests for the SKOS section on index and single-page output."""

    def test_html_index_has_skos_section(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(skos_vocabulary)

        html = (output_dir / "index.html").read_text()
        assert "SKOS Vocabulary" in html
        assert "concepts/Building.html" in html
        assert "concepts/BuildingScheme.html" in html

    def test_markdown_index_has_skos_section(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="markdown")
        DocsGenerator(config).generate(skos_vocabulary)

        md = (output_dir / "index.md").read_text()
        assert "## SKOS Vocabulary" in md
        assert "`skos_concept`" in md
        assert "`skos_concept_scheme`" in md

    def test_html_single_page_has_skos(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="html", single_page=True)
        DocsGenerator(config).generate(skos_vocabulary)

        html = (output_dir / "index.html").read_text()
        assert 'id="skos"' in html
        assert "Loop A" in html

    def test_markdown_single_page_has_skos(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="markdown", single_page=True)
        DocsGenerator(config).generate(skos_vocabulary)

        md = (output_dir / "index.md").read_text()
        assert "## SKOS Vocabulary" in md
        assert "- [SKOS Vocabulary](#skos-vocabulary)" in md


class TestSKOSSearchIndex:
    """Tests for SKOS entries in the search index."""

    def test_concepts_appear_in_search_index(self, skos_vocabulary: Graph):
        entities = extract_all(skos_vocabulary)
        config = DocsConfig()
        entries = generate_search_index(entities, config)

        by_type = {e.entity_type for e in entries}
        assert "skos_concept" in by_type
        assert "skos_concept_scheme" in by_type

    def test_search_entry_kinds_and_url(self, skos_vocabulary: Graph):
        entities = extract_all(skos_vocabulary)
        entries = generate_search_index(entities, DocsConfig())

        entry = next(e for e in entries if e.qname == "ex:Building")
        assert entry.kinds == ["skos_concept", "named_individual"]
        assert entry.url == "concepts/Building.html"

    def test_alt_and_hidden_labels_indexed(self, skos_vocabulary: Graph):
        """Hidden labels exist to catch misspellings — they must be searchable."""
        entities = extract_all(skos_vocabulary)
        entries = generate_search_index(entities, DocsConfig())

        detached = next(e for e in entries if e.qname == "ex:DetachedHouse")
        assert "detatched" in detached.keywords  # skos:hiddenLabel
        assert "standalone" in detached.keywords  # skos:altLabel


class TestIncludeSkosFlag:
    """Tests for the include_skos configuration flag."""

    def test_default_include_skos_true(self):
        assert DocsConfig().include_skos is True

    def test_include_skos_from_dict(self):
        config = DocsConfig.from_dict({"include_skos": False})
        assert config.include_skos is False

    def test_include_skos_false_excludes_pages(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="html", include_skos=False)
        DocsGenerator(config).generate(skos_vocabulary)

        assert not (output_dir / "concepts").exists()
        html = (output_dir / "index.html").read_text()
        assert "SKOS Vocabulary" not in html

    def test_include_skos_false_excludes_from_search(self, skos_vocabulary: Graph):
        entities = extract_all(skos_vocabulary)
        entries = generate_search_index(entities, DocsConfig(include_skos=False))

        assert not [e for e in entries if e.entity_type.startswith("skos_")]

    def test_include_skos_false_does_not_leak_into_instances(
        self, skos_vocabulary: Graph, output_dir: Path
    ):
        """Excluded means excluded — concepts do not fall back to Instances."""
        config = DocsConfig(output_dir=output_dir, format="json", include_skos=False)
        DocsGenerator(config).generate(skos_vocabulary)

        data = json.loads((output_dir / "index.json").read_text())
        assert "ex:Building" not in {i["qname"] for i in data["instances"]}


class TestSKOSRouting:
    """Tests for SKOS URL/path generation."""

    def test_concept_path_under_concepts_directory(self):
        config = DocsConfig(format="html")
        assert entity_to_path("ex:Building", "skos_concept", config) == Path(
            "concepts/Building.html"
        )

    def test_scheme_shares_the_concepts_directory(self):
        config = DocsConfig(format="html")
        assert entity_to_path("ex:BuildingScheme", "skos_concept_scheme", config) == Path(
            "concepts/BuildingScheme.html"
        )

    def test_concept_path_with_entity_kind_enum(self):
        config = DocsConfig(format="html")
        assert entity_to_path("ex:Building", EntityKind.SKOS_CONCEPT, config) == Path(
            "concepts/Building.html"
        )


# ---------------------------------------------------------------------------
# owl:NamedIndividual badging — issue #64 / milestone v0.6.0 stage 3
# ---------------------------------------------------------------------------


NAMED_INDIVIDUAL_FIXTURE = Path(__file__).parent / "fixtures" / "docs" / "named_individuals.ttl"


@pytest.fixture
def named_individual_ontology() -> Graph:
    """Load the tracked owl:NamedIndividual test ontology.

    No RDF file in the repository contained ``owl:NamedIndividual`` at all
    before #64. The fixture carries the three cases the badge turns on:
    class-typed *and* declared (``ex:Alice``), class-typed only
    (``ex:Bob``, the false-positive guard) and declared with no class
    typing at all (``ex:Carol``).
    """
    g = Graph()
    g.parse(NAMED_INDIVIDUAL_FIXTURE, format="turtle")
    return g


def _instance(entities: ExtractedEntities, local_name: str):
    """Find an instance by the local part of its qname."""
    return next(i for i in entities.instances if i.qname.split(":")[-1] == local_name)


class TestNamedIndividualExtraction:
    """Tests for the NAMED_INDIVIDUAL kind."""

    def test_explicit_declaration_carries_the_kind(self, named_individual_ontology: Graph):
        """An entity typed both by its class and owl:NamedIndividual gets both kinds."""
        entities = extract_all(named_individual_ontology)
        alice = _instance(entities, "Alice")
        assert alice.kinds == [EntityKind.INSTANCE, EntityKind.NAMED_INDIVIDUAL]

    def test_redundant_declaration_still_shows(self, named_individual_ontology: Graph):
        """The kind records what the source asserts, not what is inferable.

        ``ex:Alice`` is already an individual by virtue of her ``ex:Person``
        typing, so the ``owl:NamedIndividual`` triple is redundant in OWL DL
        terms. It is surfaced anyway: the redundancy tells a reader the
        author was explicit, which is the same policy ``kinds`` follows
        everywhere else.
        """
        entities = extract_all(named_individual_ontology)
        alice = _instance(entities, "Alice")
        assert EntityKind.NAMED_INDIVIDUAL in alice.kinds
        assert str(EX_NI.Person) in [str(t) for t in alice.types]

    def test_class_typed_only_does_not_get_the_kind(self, named_individual_ontology: Graph):
        """The false-positive guard: no declaration, no badge."""
        entities = extract_all(named_individual_ontology)
        bob = _instance(entities, "Bob")
        assert bob.kinds == [EntityKind.INSTANCE]
        assert EntityKind.NAMED_INDIVIDUAL not in bob.kinds

    def test_declaration_alone_is_documented(self, named_individual_ontology: Graph):
        """An entity typed *only* owl:NamedIndividual is still an instance.

        With no class typing, the declaration is the only thing saying this
        is an individual — so it must neither be dropped nor land in some
        other bucket.
        """
        entities = extract_all(named_individual_ontology)
        carol = _instance(entities, "Carol")
        assert carol.kinds == [EntityKind.INSTANCE, EntityKind.NAMED_INDIVIDUAL]
        assert [str(t) for t in carol.types] == [str(OWL.NamedIndividual)]

    def test_classes_and_properties_do_not_get_the_kind(self, named_individual_ontology: Graph):
        """Classes and properties are not individuals; nothing badges them."""
        entities = extract_all(named_individual_ontology)
        for class_info in entities.classes:
            assert EntityKind.NAMED_INDIVIDUAL not in class_info.kinds
        for prop in entities.properties:
            assert EntityKind.NAMED_INDIVIDUAL not in prop.kinds

    def test_shape_that_is_also_a_named_individual(self):
        """Stage 1 routed such a shape to shapes/; it now records the declaration.

        The routing is unchanged — the shape is documented once, under
        Shapes, and does not appear in Instances.
        """
        g = Graph()
        g.bind("ex", EX)
        g.add((EX.MyShape, RDF.type, SH.NodeShape))
        g.add((EX.MyShape, RDF.type, OWL.NamedIndividual))

        entities = extract_all(g)
        shape = next(s for s in entities.shapes if s.qname == "ex:MyShape")
        assert shape.kinds == [
            EntityKind.SHAPE,
            EntityKind.NODE_SHAPE,
            EntityKind.NAMED_INDIVIDUAL,
        ]
        assert "ex:MyShape" not in {i.qname for i in entities.instances}

    def test_concept_that_is_also_a_named_individual(self, skos_vocabulary: Graph):
        """The SKOS multi-kind case: badge added, routing unchanged."""
        entities = extract_all(skos_vocabulary)
        building = _concept(entities, "Building")
        assert building.kinds == [EntityKind.SKOS_CONCEPT, EntityKind.NAMED_INDIVIDUAL]
        assert "ex:Building" not in {i.qname for i in entities.instances}

    def test_concept_without_the_declaration_is_unaffected(self, skos_vocabulary: Graph):
        entities = extract_all(skos_vocabulary)
        dwelling = _concept(entities, "Dwelling")
        assert dwelling.kinds == [EntityKind.SKOS_CONCEPT]


class TestNamedIndividualRendering:
    """Tests for the badge in HTML, Markdown and JSON output."""

    def test_html_instance_badge(self, named_individual_ontology: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(named_individual_ontology)

        alice = (output_dir / "instances" / "Alice.html").read_text()
        assert 'class="entity-type named_individual"' in alice
        assert "named individual" in alice

    def test_html_no_badge_without_declaration(
        self, named_individual_ontology: Graph, output_dir: Path
    ):
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(named_individual_ontology)

        bob = (output_dir / "instances" / "Bob.html").read_text()
        assert 'class="entity-type named_individual"' not in bob
        assert 'class="entity-type instance"' in bob

    def test_html_badge_css_present(self, named_individual_ontology: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(named_individual_ontology)

        css = (output_dir / "assets" / "style.css").read_text()
        assert ".entity-type.named_individual { background: #047857; }" in css

    def test_html_index_shows_the_badge(self, named_individual_ontology: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(named_individual_ontology)

        html = (output_dir / "index.html").read_text()
        assert 'class="entity-type named_individual"' in html

    def test_html_single_page_shows_the_badge(
        self, named_individual_ontology: Graph, output_dir: Path
    ):
        config = DocsConfig(output_dir=output_dir, format="html", single_page=True)
        DocsGenerator(config).generate(named_individual_ontology)

        html = (output_dir / "index.html").read_text()
        assert 'class="entity-type named_individual"' in html

    def test_markdown_kinds_line(self, named_individual_ontology: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="markdown")
        DocsGenerator(config).generate(named_individual_ontology)

        alice = (output_dir / "instances" / "Alice.md").read_text()
        assert "**Kinds:** `instance` `named_individual`" in alice

        bob = (output_dir / "instances" / "Bob.md").read_text()
        assert "**Kinds:** `instance`" in bob
        assert "named_individual" not in bob

    def test_json_kinds_array(self, named_individual_ontology: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(named_individual_ontology)

        alice = json.loads((output_dir / "instances" / "Alice.json").read_text())
        assert alice["kinds"] == ["instance", "named_individual"]

        bob = json.loads((output_dir / "instances" / "Bob.json").read_text())
        assert bob["kinds"] == ["instance"]

    def test_json_no_new_top_level_array(self, named_individual_ontology: Graph, output_dir: Path):
        """Named individuals stay in `instances` — this stage is not breaking."""
        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(named_individual_ontology)

        data = json.loads((output_dir / "index.json").read_text())
        assert "named_individuals" not in data
        assert {"ex:Alice", "ex:Bob", "ex:Carol"} <= {i["qname"] for i in data["instances"]}

    def test_markdown_concept_shows_both_kinds(self, skos_vocabulary: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="markdown")
        DocsGenerator(config).generate(skos_vocabulary)

        md = (output_dir / "concepts" / "Building.md").read_text()
        assert "**Kinds:** `skos_concept` `named_individual`" in md


class TestNamedIndividualSearchIndex:
    """Tests for the search index treatment."""

    def test_kinds_field_populated(self, named_individual_ontology: Graph):
        entities = extract_all(named_individual_ontology)
        entries = generate_search_index(entities, DocsConfig())

        alice = next(e for e in entries if e.qname == "ex:Alice")
        assert alice.kinds == ["instance", "named_individual"]
        assert alice.entity_type == "instance"

    def test_kind_is_searchable(self, named_individual_ontology: Graph):
        entities = extract_all(named_individual_ontology)
        entries = generate_search_index(entities, DocsConfig())

        alice = next(e for e in entries if e.qname == "ex:Alice")
        assert "named_individual" in alice.keywords

        bob = next(e for e in entries if e.qname == "ex:Bob")
        assert "named_individual" not in bob.keywords

    def test_no_new_entity_type(self, named_individual_ontology: Graph):
        """Named individuals are not a separate search bucket."""
        entities = extract_all(named_individual_ontology)
        entries = generate_search_index(entities, DocsConfig())

        assert not [e for e in entries if e.entity_type == "named_individual"]


class TestNamedIndividualEnum:
    """The new enum member follows the same str-mixin contract."""

    def test_value_and_str(self):
        assert EntityKind.NAMED_INDIVIDUAL == "named_individual"
        assert str(EntityKind.NAMED_INDIVIDUAL) == "named_individual"

    def test_json_serialises_as_plain_string(self):
        assert json.dumps(EntityKind.NAMED_INDIVIDUAL) == '"named_individual"'


# ---------------------------------------------------------------------------
# Characteristic-only declarations — issue #76
# ---------------------------------------------------------------------------


CHARACTERISTIC_FIXTURE = (
    Path(__file__).parent / "fixtures" / "docs" / "characteristic_properties.ttl"
)


@pytest.fixture
def characteristic_ontology() -> Graph:
    """Load the tracked characteristic-only-declaration ontology.

    Every property in it was extracted as an *instance* before #76,
    because the extractor recognised only the obvious four property
    types. See the fixture's header for the two groups it separates.
    """
    g = Graph()
    g.parse(CHARACTERISTIC_FIXTURE, format="turtle")
    return g


def _prop(entities: ExtractedEntities, local_name: str) -> PropertyInfo:
    """Find a property by the local part of its qname."""
    return next(p for p in entities.properties if p.qname.split(":")[-1] == local_name)


class TestCharacteristicOnlyProperties:
    """A term declared solely by an OWL characteristic is still a property."""

    @pytest.mark.parametrize(
        "local_name",
        ["hasPart", "adjacentTo", "precedes", "sameAgeAs", "differentFrom", "hasIdentifier"],
    )
    def test_characteristic_implies_object_property(
        self, characteristic_ontology: Graph, local_name: str
    ):
        """The six characteristics that are owl:ObjectProperty subclasses.

        Declaring one alone is legal and common in older ontologies, and
        OWL 2 makes each a subclass of owl:ObjectProperty — so the kind is
        inferable and the term belongs in the object-property bucket.
        """
        entities = extract_all(characteristic_ontology)
        prop = _prop(entities, local_name)
        assert prop.property_type == "object"
        assert prop.kinds == [EntityKind.PROPERTY, EntityKind.OBJECT_PROPERTY]

    @pytest.mark.parametrize("local_name", ["hasParent", "oldProperty", "plainProperty"])
    def test_kind_not_inferable_goes_to_other(
        self, characteristic_ontology: Graph, local_name: str
    ):
        """owl:FunctionalProperty and owl:DeprecatedProperty imply no kind.

        Both are subclasses of rdf:Property only, so nothing says object or
        datatype. They must land somewhere rather than being guessed into a
        bucket — the CLAUDE.md invariant is explicit about this.
        """
        entities = extract_all(characteristic_ontology)
        prop = _prop(entities, local_name)
        assert prop.property_type == "rdf"
        assert prop.kinds == [EntityKind.PROPERTY, EntityKind.RDF_PROPERTY]
        assert prop in entities.other_properties

    def test_no_property_is_extracted_as_an_instance(self, characteristic_ontology: Graph):
        """The central #76 bug: properties misfiled into the instance bucket."""
        entities = extract_all(characteristic_ontology)
        instance_qnames = {i.qname for i in entities.instances}

        for local_name in (
            "hasPart",
            "adjacentTo",
            "precedes",
            "sameAgeAs",
            "differentFrom",
            "hasIdentifier",
            "hasParent",
            "oldProperty",
            "plainProperty",
        ):
            assert f"ex:{local_name}" not in instance_qnames

        # The genuine individual is untouched
        assert "ex:alice" in instance_qnames

    def test_explicit_kind_beats_the_characteristic(self, characteristic_ontology: Graph):
        """A characteristic alongside an explicit kind does not override it."""
        entities = extract_all(characteristic_ontology)
        assert _prop(entities, "knows").property_type == "object"
        assert _prop(entities, "retiredName").property_type == "datatype"

    def test_deprecated_class_is_a_class(self, characteristic_ontology: Graph):
        """owl:DeprecatedClass has the same problem on the class side."""
        entities = extract_all(characteristic_ontology)
        assert "ex:OldClass" in {c.qname for c in entities.classes}
        assert "ex:OldClass" not in {i.qname for i in entities.instances}

    def test_class_not_listed_among_its_metaclass_instances(self, characteristic_ontology: Graph):
        """ex:OldClass is typed ex:Thing, but it is a class, not an instance of one."""
        entities = extract_all(characteristic_ontology)
        thing = next(c for c in entities.classes if c.qname == "ex:Thing")
        assert not any("OldClass" in str(uri) for uri in thing.instances)
        assert any("alice" in str(uri) for uri in thing.instances)

    def test_domain_and_range_still_extracted(self, characteristic_ontology: Graph):
        """A characteristic-only property keeps the rest of its metadata."""
        entities = extract_all(characteristic_ontology)
        has_part = _prop(entities, "hasPart")
        assert [str(u) for u in has_part.domain] == ["http://example.org/char#Thing"]
        assert [str(u) for u in has_part.range] == ["http://example.org/char#Thing"]
        assert has_part.label == "has part"


class TestOtherPropertiesRendering:
    """Properties of unstated kind need somewhere to go, not just a bucket."""

    def test_html_pages_under_properties_other(
        self, characteristic_ontology: Graph, output_dir: Path
    ):
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(characteristic_ontology)

        assert (output_dir / "properties" / "other" / "hasParent.html").exists()
        assert (output_dir / "properties" / "other" / "plainProperty.html").exists()
        # And the inferable ones are with the object properties
        assert (output_dir / "properties" / "object" / "hasPart.html").exists()

    def test_nothing_lands_in_the_junk_directory(
        self, characteristic_ontology: Graph, output_dir: Path
    ):
        """`entity_to_path` falls back to `other/` for an unknown type.

        Before #76 an rdf:Property-only term routed there and was never
        rendered at all, so the fallback should now be unreachable.
        """
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(characteristic_ontology)

        assert not (output_dir / "other").exists()

    def test_markdown_and_json_pages(self, characteristic_ontology: Graph, output_dir: Path):
        for fmt, ext in (("markdown", ".md"), ("json", ".json")):
            target = output_dir / fmt
            config = DocsConfig(output_dir=target, format=fmt)
            DocsGenerator(config).generate(characteristic_ontology)
            assert (target / "properties" / "other" / f"hasParent{ext}").exists()

    def test_html_badge_and_css(self, characteristic_ontology: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(characteristic_ontology)

        page = (output_dir / "properties" / "other" / "hasParent.html").read_text()
        assert 'class="entity-type rdf"' in page

        css = (output_dir / "assets" / "style.css").read_text()
        assert ".entity-type.rdf { background: #334155; }" in css

    def test_html_index_lists_them(self, characteristic_ontology: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(characteristic_ontology)

        html = (output_dir / "index.html").read_text()
        assert "Other Properties" in html
        assert "properties/other/hasParent.html" in html

    def test_markdown_index_lists_them(self, characteristic_ontology: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="markdown")
        DocsGenerator(config).generate(characteristic_ontology)

        md = (output_dir / "index.md").read_text()
        assert "## Other Properties" in md

    def test_json_other_properties_array(self, characteristic_ontology: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="json")
        DocsGenerator(config).generate(characteristic_ontology)

        data = json.loads((output_dir / "index.json").read_text())
        qnames = {p["qname"] for p in data["other_properties"]}
        assert qnames == {"ex:hasParent", "ex:oldProperty", "ex:plainProperty"}
        assert data["statistics"]["other_properties"] == 3
        # They left the instances array, where they used to be
        assert not qnames & {i["qname"] for i in data["instances"]}

    def test_search_index_includes_them(self, characteristic_ontology: Graph):
        entities = extract_all(characteristic_ontology)
        entries = generate_search_index(entities, DocsConfig())

        entry = next(e for e in entries if e.qname == "ex:hasParent")
        assert entry.entity_type == "rdf_property"
        assert entry.url == "properties/other/hasParent.html"
        assert entry.kinds == ["property", "rdf_property"]

    def test_include_other_properties_false(self, characteristic_ontology: Graph, output_dir: Path):
        config = DocsConfig(output_dir=output_dir, format="html", include_other_properties=False)
        DocsGenerator(config).generate(characteristic_ontology)

        assert not (output_dir / "properties" / "other").exists()
        entries = generate_search_index(
            extract_all(characteristic_ontology),
            DocsConfig(include_other_properties=False),
        )
        assert not [e for e in entries if e.entity_type == "rdf_property"]

    def test_default_include_other_properties_true(self):
        assert DocsConfig().include_other_properties is True
        assert (
            DocsConfig.from_dict({"include_other_properties": False}).include_other_properties
            is False
        )

    def test_routing(self):
        config = DocsConfig(format="html")
        assert entity_to_path("ex:hasParent", "rdf_property", config) == Path(
            "properties/other/hasParent.html"
        )
        # A term reachable only via rdfs:domain, carrying no rdf:type at all,
        # keeps the default "property" type — it lands with its siblings
        # rather than in the junk directory.
        assert entity_to_path("ex:untyped", "property", config) == Path(
            "properties/other/untyped.html"
        )


# ---------------------------------------------------------------------------
# Search overlay path resolution — issue #86
# ---------------------------------------------------------------------------


class TestSearchOverlayPaths:
    """The search overlay has to work from a page at any depth.

    ``assets/search.js`` made two root-relative assumptions that #59 did
    not reach, because #59 covered the Jinja templates only: it fetched
    ``search.json`` page-relatively, and it injected the index's
    root-relative result URLs verbatim as hrefs. On the animal-ontology
    corpus that left the index unreachable from 16 of 19 pages and 256
    (page, result) pairs pointing at files that do not exist.

    These tests check the arithmetic the script performs rather than
    driving a browser: the failure mode is a dead input and a 404, both
    of which are decided entirely by these two path computations.
    """

    @staticmethod
    def _docs_root(page: Path) -> str:
        """Extract the per-page DOCS_ROOT the template declared."""
        import re

        match = re.search(r'window\.DOCS_ROOT = "([^"]*)"', page.read_text())
        assert match is not None, f"{page} declares no DOCS_ROOT"
        return match.group(1)

    def test_docs_root_declared_on_every_page(self, shape_ontology: Graph, output_dir: Path):
        """Every page states where the docs root is, relative to itself."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(shape_ontology)

        for page in output_dir.rglob("*.html"):
            expected = relative_url_prefix(page.relative_to(output_dir))
            assert self._docs_root(page) == expected

    def test_index_fetch_resolves_from_every_page(self, shape_ontology: Graph, output_dir: Path):
        """`fetch(docsRoot + '/search.json')` has to hit the real file.

        This is the half that made the box inert: the request 404s, the
        index never loads, and typing does nothing at all — no error, no
        empty-results message.
        """
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(shape_ontology)

        unreachable = [
            str(page.relative_to(output_dir))
            for page in output_dir.rglob("*.html")
            if not (page.parent / f"{self._docs_root(page)}/search.json").resolve().exists()
        ]
        assert not unreachable, f"search.json unreachable from: {unreachable}"

    def test_every_result_link_resolves_from_every_page(
        self, skos_vocabulary: Graph, output_dir: Path
    ):
        """A result clicked from any page has to land on a real file.

        Run over the SKOS fixture because its pages sit in a sub-folder,
        which is precisely where the old behaviour broke.
        """
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(skos_vocabulary)

        entries = json.loads((output_dir / "search.json").read_text())["entities"]
        assert entries, "fixture produced an empty search index"

        broken = [
            (str(page.relative_to(output_dir)), entry["url"])
            for page in output_dir.rglob("*.html")
            for entry in entries
            if not (page.parent / f"{self._docs_root(page)}/{entry['url']}").resolve().exists()
        ]
        assert not broken, f"{len(broken)} broken result links, e.g. {broken[:3]}"

    def test_script_does_not_hardcode_the_root(self, simple_ontology: Graph, output_dir: Path):
        """The old page-relative fetch must not come back."""
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(simple_ontology)

        js = (output_dir / "assets" / "search.js").read_text()
        assert "fetch('search.json')" not in js
        assert "docsRoot" in js

    def test_explicit_base_url_is_used(self, simple_ontology: Graph, output_dir: Path):
        """A configured base_url wins, as it does for every other link."""
        config = DocsConfig(
            output_dir=output_dir,
            format="html",
            base_url="https://example.com/docs",
        )
        DocsGenerator(config).generate(simple_ontology)

        for rel in ("index.html", "classes/Dog.html"):
            assert self._docs_root(output_dir / rel) == "https://example.com/docs"

    def test_file_protocol_is_explained_not_silent(self, simple_ontology: Graph, output_dir: Path):
        """Under file:// the box says why it cannot work.

        `fetch` is CORS-blocked on file:// whatever the path, so search
        genuinely cannot work from a double-clicked page. Rendering an
        input that silently does nothing is the worst of the options
        available.
        """
        config = DocsConfig(output_dir=output_dir, format="html")
        DocsGenerator(config).generate(simple_ontology)

        js = (output_dir / "assets" / "search.js").read_text()
        assert "window.location.protocol === 'file:'" in js
        assert "searchInput.disabled = true" in js
        assert "placeholder" in js


# ---------------------------------------------------------------------------
# Search index determinism — issue #107
# ---------------------------------------------------------------------------


class TestSearchIndexDeterminism:
    """Generated output must be byte-identical between runs.

    ``extract_keywords()`` and every ``*_to_search_entry`` ended with
    ``list(set(...))``. Python randomises string hashing per process, so
    the key order in ``search.json`` changed on every run over identical
    input — for every entity kind. Regenerating a committed docs site
    showed a diff with no semantic change, and the project's own
    verification technique (generate at two commits, diff the output)
    could not be used on this command without pinning the hash seed.
    """

    def test_keywords_are_sorted(self, skos_vocabulary: Graph):
        """Every entry's keyword list is in a defined order."""
        entities = extract_all(skos_vocabulary)
        entries = generate_search_index(entities, DocsConfig())

        assert entries
        for entry in entries:
            assert entry.keywords == sorted(entry.keywords)
            assert len(entry.keywords) == len(set(entry.keywords))

    def test_extract_keywords_returns_sorted(self):
        """Enough words that a sorted result cannot be luck.

        With three words there is a one-in-six chance an unsorted
        implementation comes out sorted anyway under a given hash seed,
        and pytest picks a fresh seed each session — so the input is
        long enough to make that vanishingly unlikely.
        """
        text = "Zebra apple Mango apple Kiwi banana Cherry damson elder fig"
        assert extract_keywords(text) == [
            "apple",
            "banana",
            "cherry",
            "damson",
            "elder",
            "fig",
            "kiwi",
            "mango",
            "zebra",
        ]

    @pytest.mark.parametrize("output_format", ["html", "markdown", "json"])
    def test_output_is_byte_identical_across_processes(self, tmp_path: Path, output_format: str):
        """Two runs in separate processes produce identical bytes.

        The second process is given a different ``PYTHONHASHSEED``, which
        is what makes this a real test: within a single process,
        ``list(set(...))`` iterates in a stable order, so generating twice
        in-process passes even on the broken code.
        """
        import os
        import subprocess
        import sys

        source = Path(__file__).parent / "fixtures" / "docs" / "skos_vocabulary.ttl"
        runs = []

        for index, hash_seed in enumerate(("1", "99999")):
            out = tmp_path / f"run{index}"
            script = (
                "from pathlib import Path\n"
                "from rdf_construct.docs import generate_docs\n"
                f"generate_docs(Path({str(source)!r}), Path({str(out)!r}), "
                f"None, {output_format!r})\n"
            )
            result = subprocess.run(
                [sys.executable, "-c", script],
                env={**os.environ, "PYTHONHASHSEED": hash_seed},
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, result.stderr
            runs.append(out)

        first, second = runs
        first_files = sorted(p.relative_to(first) for p in first.rglob("*") if p.is_file())
        second_files = sorted(p.relative_to(second) for p in second.rglob("*") if p.is_file())
        assert first_files == second_files, "the two runs produced different file sets"
        assert first_files, "no files generated"

        differing = [
            str(rel)
            for rel in first_files
            if (first / rel).read_bytes() != (second / rel).read_bytes()
        ]
        assert not differing, f"output differs between runs: {differing}"


# ---------------------------------------------------------------------------
# Markdown link resolution — issue #113, and the helper #87 needs
# ---------------------------------------------------------------------------


MARKDOWN_LINK = re.compile(r"\]\(([^)]+)\)")
MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$", re.MULTILINE)


def _heading_slug(text: str) -> str:
    """Slugify a heading the way GitHub and MkDocs both do.

    Lowercase, drop anything that is not alphanumeric, space or hyphen,
    then spaces to hyphens. The two differ on collisions and on some
    punctuation; this covers the headings this project emits.
    """
    cleaned = re.sub(r"[^a-z0-9 \-]", "", text.lower())
    return re.sub(r"\s+", "-", cleaned.strip())


def broken_markdown_links(root: Path) -> list[tuple[str, str]]:
    """Find Markdown links that do not resolve, anywhere under ``root``.

    The Markdown counterpart of
    ``TestPathResolution::test_all_links_resolve_for_every_entity_kind``.
    There was no equivalent for Markdown, which is a fair part of why
    #87, #105 and #113 all survived as long as they did — a renderer
    with no link walk over its own output has nothing holding it to
    account.

    Two kinds of link are checked:

    - **File links** resolve against the directory of the file that
      contains them, which is what every Markdown consumer does and what
      makes a root-relative link from a sub-folder page wrong (#87).
    - **Anchor links** (``#section``) must match a heading in the same
      file, slugified — that is what single-page output relies on.

    External links (``http``, ``https``, ``mailto``) are skipped.

    Args:
        root: Directory of generated Markdown to walk.

    Returns:
        ``(file, link)`` pairs, one per unresolved link, sorted.
    """
    broken: list[tuple[str, str]] = []

    for page in sorted(root.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        slugs = {_heading_slug(h) for h in MARKDOWN_HEADING.findall(text)}

        for target in MARKDOWN_LINK.findall(text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if target.startswith("#"):
                if target[1:] not in slugs:
                    broken.append((str(page.relative_to(root)), target))
                continue
            path_part = target.split("#", 1)[0]
            if not (page.parent / path_part).resolve().exists():
                broken.append((str(page.relative_to(root)), target))

    return broken


class TestSinglePageMarkdownLinks:
    """Single-page Markdown must not link to pages it never writes.

    Single-page output produces exactly one file. Cross-references were
    rendered as links to each entity's own page — `concepts/Dwelling.md`,
    `classes/Person.md` — none of which exist in that mode. Every one was
    a dead link (#113).
    """

    @pytest.mark.parametrize(
        "fixture_name", ["skos_vocabulary", "shape_ontology", "simple_ontology"]
    )
    def test_no_dead_links_in_single_page_output(
        self,
        fixture_name: str,
        request: pytest.FixtureRequest,
        output_dir: Path,
    ):
        graph = request.getfixturevalue(fixture_name)
        config = DocsConfig(output_dir=output_dir, format="markdown", single_page=True)
        DocsGenerator(config).generate(graph)

        assert (output_dir / "index.md").exists()
        assert broken_markdown_links(output_dir) == []

    def test_single_page_writes_exactly_one_file(self, skos_vocabulary: Graph, output_dir: Path):
        """The premise of the bug: there is nowhere for a link to point."""
        config = DocsConfig(output_dir=output_dir, format="markdown", single_page=True)
        DocsGenerator(config).generate(skos_vocabulary)

        assert [p.name for p in output_dir.rglob("*.md")] == ["index.md"]

    def test_references_stay_visible_as_qnames(self, skos_vocabulary: Graph, output_dir: Path):
        """Unlinked does not mean dropped — the reference is still readable.

        A qname in code formatting is greppable within the single
        document, which is the navigation story once a link is not
        available.
        """
        config = DocsConfig(output_dir=output_dir, format="markdown", single_page=True)
        DocsGenerator(config).generate(skos_vocabulary)

        content = (output_dir / "index.md").read_text()
        assert "**Broader:** `ex:Dwelling`" in content
        assert "**In scheme:** `ex:BuildingScheme`" in content

    def test_shape_targets_too(self, shape_ontology: Graph, output_dir: Path):
        """The Shapes section had the same defect, and predates the SKOS one."""
        config = DocsConfig(output_dir=output_dir, format="markdown", single_page=True)
        DocsGenerator(config).generate(shape_ontology)

        content = (output_dir / "index.md").read_text()
        assert "**Target classes:** `ex:Person`" in content

    def test_table_of_contents_anchors_resolve(self, skos_vocabulary: Graph, output_dir: Path):
        """The anchors single-page output does rely on must actually exist."""
        config = DocsConfig(output_dir=output_dir, format="markdown", single_page=True)
        DocsGenerator(config).generate(skos_vocabulary)

        content = (output_dir / "index.md").read_text()
        assert "- [SKOS Vocabulary](#skos-vocabulary)" in content
        assert "## SKOS Vocabulary" in content

    def test_multi_page_links_are_still_links(self, skos_vocabulary: Graph, output_dir: Path):
        """Only single-page output drops the links; multi-page keeps them."""
        config = DocsConfig(output_dir=output_dir, format="markdown")
        DocsGenerator(config).generate(skos_vocabulary)

        content = (output_dir / "concepts" / "Dwelling.md").read_text()
        assert "](" in content
        assert "Building.md" in content


# ---------------------------------------------------------------------------
# Entity-type filtering and cross-references — issue #115
# ---------------------------------------------------------------------------


EXCLUSION_FLAGS = [
    "include_classes",
    "include_object_properties",
    "include_datatype_properties",
    "include_annotation_properties",
    "include_other_properties",
    "include_instances",
    "include_shapes",
    "include_skos",
]


@pytest.fixture
def mixed_ontology() -> Graph:
    """One graph carrying every entity type, so exclusions have something to bite."""
    g = Graph()
    g.parse(SKOS_FIXTURE, format="turtle")
    g.parse(CHARACTERISTIC_FIXTURE, format="turtle")
    return g


class TestExcludedEntityLinks:
    """Filtering decides what is generated; it must decide what is linked.

    `--include` / `--exclude` were honoured by the generator and ignored
    by the templates, so excluding an entity type filled the output with
    links to pages that were never written. `--include classes` alone
    produced 43 dead links in HTML (#115).
    """

    @pytest.mark.parametrize("flag", EXCLUSION_FLAGS)
    def test_html_has_no_dead_links_under_any_exclusion(
        self, mixed_ontology: Graph, output_dir: Path, flag: str
    ):
        import re

        config = DocsConfig(output_dir=output_dir, format="html", **{flag: False})
        DocsGenerator(config).generate(mixed_ontology)

        ref_pat = re.compile(r'(?:href|src)="([^"#?]+)"')
        broken = [
            (str(page.relative_to(output_dir)), ref)
            for page in output_dir.rglob("*.html")
            for ref in ref_pat.findall(page.read_text())
            if not ref.startswith(("http://", "https://", "mailto:", "#"))
            and not (page.parent / ref).resolve().exists()
        ]
        assert not broken, f"{flag}=False left {len(broken)} dead links, e.g. {broken[:3]}"

    def test_html_include_classes_only(self, output_dir: Path):
        """The documented 'only classes' workflow, which was the worst case."""
        import re

        graph = Graph()
        graph.parse("examples/animal_ontology.ttl", format="turtle")
        config = DocsConfig(
            output_dir=output_dir,
            format="html",
            include_object_properties=False,
            include_datatype_properties=False,
            include_annotation_properties=False,
            include_other_properties=False,
            include_instances=False,
            include_skos=False,
            include_shapes=False,
        )
        DocsGenerator(config).generate(graph)

        ref_pat = re.compile(r'(?:href|src)="([^"#?]+)"')
        broken = [
            (str(page.relative_to(output_dir)), ref)
            for page in output_dir.rglob("*.html")
            for ref in ref_pat.findall(page.read_text())
            if not ref.startswith(("http://", "https://", "mailto:", "#"))
            and not (page.parent / ref).resolve().exists()
        ]
        assert not broken, f"{len(broken)} dead links, e.g. {broken[:3]}"

    @pytest.mark.parametrize("flag", EXCLUSION_FLAGS)
    def test_markdown_never_links_to_an_ungenerated_page(
        self, mixed_ontology: Graph, output_dir: Path, flag: str
    ):
        """Markdown links must at least *name a file that exists*.

        Checked by filename rather than by resolved path: #87 (root-relative
        Markdown links, open in #105) makes every Markdown link resolve from
        the wrong directory, which would mask this. Once #105 lands,
        ``broken_markdown_links`` covers both at once.
        """
        import re

        config = DocsConfig(output_dir=output_dir, format="markdown", **{flag: False})
        DocsGenerator(config).generate(mixed_ontology)

        written = {p.name for p in output_dir.rglob("*.md")}
        missing = [
            (str(page.relative_to(output_dir)), ref)
            for page in output_dir.rglob("*.md")
            for ref in re.findall(r"\]\(([^)#]+)\)", page.read_text())
            if not ref.startswith(("http://", "https://", "mailto:"))
            and Path(ref).name not in written
        ]
        assert not missing, f"{flag}=False left {len(missing)} links to nothing, e.g. {missing[:3]}"

    def test_excluded_reference_stays_visible(self, output_dir: Path):
        """Unlinked, not deleted — the fact is still in the document.

        Hiding the row would misrepresent the ontology: a class whose
        properties were filtered out of the *documentation* has not lost
        its properties.
        """
        graph = Graph()
        graph.parse(CHARACTERISTIC_FIXTURE, format="turtle")
        config = DocsConfig(
            output_dir=output_dir, format="markdown", include_object_properties=False
        )
        DocsGenerator(config).generate(graph)

        content = (output_dir / "classes" / "Thing.md").read_text()
        assert "`ex:hasPart`" in content
        assert "hasPart.md)" not in content

    def test_html_excluded_reference_stays_visible(self, output_dir: Path):
        graph = Graph()
        graph.parse(CHARACTERISTIC_FIXTURE, format="turtle")
        config = DocsConfig(output_dir=output_dir, format="html", include_object_properties=False)
        DocsGenerator(config).generate(graph)

        content = (output_dir / "classes" / "Thing.html").read_text()
        assert "<code>ex:hasPart</code>" in content
        assert "hasPart.html" not in content

    @pytest.mark.parametrize(
        "flag,heading",
        [
            ("include_classes", "Classes"),
            ("include_object_properties", "Object Properties"),
            ("include_datatype_properties", "Datatype Properties"),
        ],
    )
    def test_index_sections_respect_the_flags(
        self, mixed_ontology: Graph, output_dir: Path, flag: str, heading: str
    ):
        """The index listed excluded types, which is where most links came from.

        Four of the six index sections already checked their flag — the
        ones added in #60, #63 and #76. The older three did not.
        """
        for fmt, name in (("html", "index.html"), ("markdown", "index.md")):
            target = output_dir / fmt
            config = DocsConfig(output_dir=target, format=fmt, **{flag: False})
            DocsGenerator(config).generate(mixed_ontology)
            assert f">{heading}<" not in (target / name).read_text()
            assert f"## {heading}" not in (target / name).read_text()

    def test_entity_type_included_defaults_to_true(self):
        """An unknown type links rather than silently unlinking.

        A new entity kind should be visible before someone remembers to
        give it a flag.
        """
        from rdf_construct.docs.config import entity_type_included

        config = DocsConfig()
        assert entity_type_included("class", config) is True
        assert entity_type_included("something_new", config) is True
        assert entity_type_included("class", DocsConfig(include_classes=False)) is False
