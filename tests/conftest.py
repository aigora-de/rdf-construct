"""Pytest configuration and shared fixtures for merge tests.

This module provides fixtures that can either:
1. Generate test ontologies dynamically (default, for unit tests)
2. Load from fixture files (for integration tests)

The fixture files in tests/fixtures/merge/ serve as:
- Documentation examples
- Integration test data
- Manual testing resources
"""

import pytest
from pathlib import Path
from textwrap import dedent

# Path to fixture files
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "merge"


@pytest.fixture
def fixtures_dir():
    """Return the path to the merge fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def core_ontology(temp_dir):
    """Create a simple core ontology file.

    This fixture generates the ontology dynamically for isolation.
    For the equivalent file-based fixture, see fixtures/merge/core.ttl
    """
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
    """Create an extension ontology file.

    For the equivalent file-based fixture, see fixtures/merge/extension.ttl
    """
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
    """Create an ontology with conflicting definitions.

    For the equivalent file-based fixture, see fixtures/merge/conflicting.ttl
    """
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
    """Create a data file with instances.

    For the equivalent file-based fixture, see fixtures/merge/instances.ttl
    """
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


# File-based fixtures for integration tests

@pytest.fixture
def core_ontology_file(fixtures_dir):
    """Load core ontology from fixture file."""
    path = fixtures_dir / "core.ttl"
    if not path.exists():
        pytest.skip(f"Fixture file not found: {path}")
    return path


@pytest.fixture
def extension_ontology_file(fixtures_dir):
    """Load extension ontology from fixture file."""
    path = fixtures_dir / "extension.ttl"
    if not path.exists():
        pytest.skip(f"Fixture file not found: {path}")
    return path


@pytest.fixture
def conflicting_ontology_file(fixtures_dir):
    """Load conflicting ontology from fixture file."""
    path = fixtures_dir / "conflicting.ttl"
    if not path.exists():
        pytest.skip(f"Fixture file not found: {path}")
    return path


@pytest.fixture
def instances_file(fixtures_dir):
    """Load instance data from fixture file."""
    path = fixtures_dir / "instances.ttl"
    if not path.exists():
        pytest.skip(f"Fixture file not found: {path}")
    return path
