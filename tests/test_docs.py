"""Tests for the documentation generation module."""

import json
from pathlib import Path

import pytest
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL, XSD

from rdf_construct.docs import (
    ClassInfo,
    DocsConfig,
    DocsGenerator,
    ExtractedEntities,
    PropertyInfo,
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


# Test namespace
EX = Namespace("http://example.org/")


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
        config = DocsConfig.from_dict({
            "format": "markdown",
            "title": "Custom Title",
            "include_instances": False,
        })

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
        ontology_file.write_text("""
            @prefix ex: <http://example.org/> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

            ex:TestOntology a owl:Ontology ;
                rdfs:label "Test" .

            ex:Thing a owl:Class ;
                rdfs:label "Thing" .
        """)

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

    def test_no_leading_slash_paths_in_any_output(
        self, simple_ontology: Graph, output_dir: Path
    ):
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
                if 'href="/' in line or "src=\"/" in line:
                    offenders.append((html_file.relative_to(output_dir), line.strip()))

        assert not offenders, (
            "Found leading-slash href/src references that would break under "
            "file:// or sub-path hosting:\n" + "\n".join(
                f"  {p}: {line}" for p, line in offenders
            )
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

    def test_entity_links_resolve_to_existing_files(
        self, simple_ontology: Graph, output_dir: Path
    ):
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
                    broken.append(
                        (html_file.relative_to(output_dir), href, target)
                    )

        assert not broken, (
            "Internal links did not resolve to existing files:\n"
            + "\n".join(f"  {p}: href={h!r} -> {t}" for p, h, t in broken)
        )

    def test_explicit_base_url_still_used(
        self, simple_ontology: Graph, output_dir: Path
    ):
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
