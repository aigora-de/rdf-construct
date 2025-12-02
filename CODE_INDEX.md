# rdf-construct Source Code Package

This directory contains the complete refactored **rdf-construct** package code.

## Directory Structure

```
src/rdf_construct/
├── __init__.py
├── __main__.py
├── cli.py
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── ordering.py
│   ├── predicate_order.py
│   ├── profile.py
│   ├── selector.py
│   ├── serialiser.py
│   └── utils.py
├── cq/
│   ├── __init__.py
│   ├── cli.py
│   ├── expectations.py
│   ├── loader.py
│   ├── runner.py
│   └── formatters/
│       ├── __init__.py
│       ├── text.py
│       ├── json.py
│       └── junit.py
├── diff/
│   ├── __init__.py
│   ├── change_types.py
│   ├── comparator.py
│   ├── filters.py
│   └── formatters/
│       ├── __init__.py
│       ├── text.py
│       ├── markdown.py
│       └── json.py
├── docs/
│   ├── __init__.py
│   ├── config.py
│   ├── extractors.py
│   ├── generator.py
│   ├── search.py
│   └── renderers/
│       ├── __init__.py
│       ├── html.py
│       ├── json_renderer.py
│       └── markdown.py
├── lint/
│   ├── __init__.py
│   ├── config.py
│   ├── engine.py
│   ├── formatters.py
│   └── rules.py
├── puml2rdf/
│   ├── __init__.py
│   ├── config.py
│   ├── converter.py
│   ├── merger.py
│   ├── model.py
│   ├── parser.py
│   └── validators.py
├── shacl/
│   ├── __init__.py
│   ├── config.py
│   ├── converters.py
│   ├── generator.py
│   └── namespaces.py
└── uml/
    ├── __init__.py
    ├── context.py
    ├── mapper.py
    ├── renderer.py
    ├── odm_renderer.py
    ├── uml_style.py
    └── uml_layout.py

examples/
├── animal_ontology.ttl
├── building_structure_context.yml
├── cq_tests_animal.yml
├── ies_colour_palette.yml
├── sample_profile.yml
├── uml_contexts.yml
├── uml_layouts.yml
└── uml_styles.yml

tests/
├── test_cq.py
├── test_diff.py
├── test_explicit_mode.py
├── test_instance_styling.py
├── test_odm_renderer.py
├── test_ordering.py
├── test_plantuml.py
├── test_predicate_order.py
└── fixtures/
    └── diff/
        ├── v1.0.ttl
        └── v1.1.ttl

docs/
├── index.md
├── dev/
│   ├── ARCHITECTURE.md
│   └── UML_IMPLEMENTATION.md
└── user_guides/
    ├── CLI_REFERENCE.md
    ├── CQ_TEST_GUIDE.md
    ├── DIFF_GUIDE.md
    ├── GETTING_STARTED.md
    ├── LINT_GUIDE.md
    ├── SHACL_GUIDE.md
    └── UML_GUIDE.md
```

## File Descriptions

### Core Package Files

**`rdf_construct/__init__.py`**
- Package initialization and exports
- Version number
- Public API definitions

**`rdf_construct/__main__.py`**
- Entry point for `python -m rdf_construct`
- Calls CLI

**`rdf_construct/cli.py`**
- Click-based CLI commands
- `order` command for ordering ontologies
- `uml` command for generating diagrams
- `diff` command for semantic comparison
- `lint` command for quality checking
- `cq-test` command for competency question testing
- `profiles` and `contexts` commands for listing configurations

### Core Modules (`core/`)

**`core/__init__.py`**
- Core module exports
- Makes functions available at package level

**`core/config.py`**
- YAML loading functions
- Dataclasses for configuration
- `OrderingSpec` for complete config
- CURIE expansion and prefix rebinding

**`core/profile.py`**
- `OrderingConfig` class - main config manager
- `OrderingProfile` class - individual profile
- Profile loading and access methods

**`core/selector.py`**
- `select_subjects()` - select RDF subjects by type
- Handles classes (owl:Class, rdfs:Class)
- Handles properties (ObjectProperty, DatatypeProperty, AnnotationProperty)
- Handles individuals (non-class, non-property subjects)

**`core/ordering.py`**
- `build_adjacency()` - create graph adjacency list
- `topo_sort_subset()` - Kahn's algorithm for topological sorting
- `descendants_of()` - find all descendants of a root
- `sort_with_roots()` - root-based branch ordering
- `sort_subjects()` - main sorting dispatcher

**`core/serialiser.py`**
- `format_term()` - format RDF terms as Turtle strings
- `serialise_turtle()` - custom Turtle writer that preserves order
- `build_section_graph()` - filter graph to specific subjects
- **Critical**: Preserves subject order (rdflib doesn't)

**`core/utils.py`**
- `extract_prefix_map()` - get namespaces from graph
- `expand_curie()` - expand CURIEs to full IRIs
- `rebind_prefixes()` - set prefix order
- `qname_sort_key()` - generate sortable keys for RDF terms

### Competency Question Module (`cq/`)

SPARQL-based ontology validation through competency question testing.

**`cq/__init__.py`**
- Public API exports
- `CQTest`, `CQTestSuite`, `CQTestRunner`, `CQTestResult`, `CQStatus`
- Expectation classes and formatters

**`cq/expectations.py`**
- `Expectation` abstract base class
- `BooleanExpectation` - ASK query true/false matching
- `HasResultsExpectation` - query returns ≥1 results
- `NoResultsExpectation` - query returns 0 results
- `CountExpectation` - exact, min, max count matching
- `ValuesExpectation` - exact result set matching
- `ContainsExpectation` - subset matching
- `parse_expectation()` - parse YAML expect values

**`cq/loader.py`**
- `CQTest` dataclass - single test definition
- `CQTestSuite` dataclass - complete test suite
- `load_test_suite()` - parse YAML test files
- `filter_by_tags()` - include/exclude tag filtering
- `build_query_with_prefixes()` - inject PREFIX declarations

**`cq/runner.py`**
- `CQStatus` enum - PASS, FAIL, ERROR, SKIP
- `CQTestResult` dataclass - single test result
- `CQTestResults` dataclass - complete results with stats
- `CQTestRunner` class - execute tests with fail-fast support
- `run_tests()` - convenience function for file paths

**`cq/cli.py`**
- `cq_test` Click command
- Tag filtering, format selection, output handling
- Exit codes: 0 (pass), 1 (fail), 2 (error)

**`cq/formatters/`**
- `text.py` - Human-readable console output with colours
- `json.py` - Structured JSON for programmatic use
- `junit.py` - JUnit XML for CI integration
- `__init__.py` - `format_results()` dispatcher

### Diff Module (`diff/`)

Semantic comparison of RDF graphs, identifying meaningful changes while ignoring cosmetic differences.

**`diff/__init__.py`**
- Public API exports
- `compare_graphs()`, `compare_files()`, `format_diff()`, `filter_diff()`

**`diff/change_types.py`**
- `ChangeType` enum - ADDED, REMOVED, MODIFIED
- `EntityType` enum - CLASS, OBJECT_PROPERTY, DATATYPE_PROPERTY, etc.
- `TripleChange` dataclass - single triple change
- `EntityChange` dataclass - changes to one entity
- `GraphDiff` dataclass - complete diff result
- `categorise_predicate()` - classify predicates semantically

**`diff/comparator.py`**
- `compare_graphs()` - core comparison using set operations
- `compare_files()` - convenience wrapper for file paths
- `_determine_entity_type()` - classify entities
- `_get_label()` - extract human-readable labels
- `_get_superclasses()` - find class hierarchy

**`diff/filters.py`**
- `filter_diff()` - filter by change type and entity type
- `parse_filter_string()` - parse comma-separated filter strings
- Maps CLI filter names to internal types

**`diff/formatters/`**
- `text.py` - Plain text output for terminals
- `markdown.py` - Markdown for release notes/changelogs
- `json.py` - JSON for programmatic use
- `__init__.py` - `format_diff()` dispatcher

### UML Module (`uml/`)

PlantUML diagram generation from RDF ontologies.

**`uml/__init__.py`**
- Public API exports
- `load_uml_config()`, `collect_diagram_entities()`, `render_plantuml()`

**`uml/context.py`**
- `UMLConfig` class - configuration manager
- `UMLContext` dataclass - diagram context definition
- YAML loading and validation

**`uml/mapper.py`**
- `collect_diagram_entities()` - select entities for diagram
- Selection strategies (root_classes, focus_classes, explicit)
- Property filtering by mode

**`uml/renderer.py`**
- `render_plantuml()` - generate PlantUML syntax
- Class, property, and instance rendering
- Relationship arrows

**`uml/odm_renderer.py`**
- `render_odm_plantuml()` - OMG ODM RDF Profile compliant output
- Standards-based stereotypes and formatting

**`uml/uml_style.py`**
- `StyleConfig` class - visual theme configuration
- Color schemes, line styles, stereotypes
- Namespace and type-based styling

**`uml/uml_layout.py`**
- `LayoutConfig` class - diagram arrangement
- Direction, spacing, grouping hints

### UML `puml2rdf` Module

Convert PlantUML class diagrams to RDF/OWL ontologies.

**`puml2rdf/__init__.py`**
- Public API exports
- `PlantUMLParser`, `PumlToRdfConverter`, `validate_puml`, `validate_rdf`

**`puml2rdf/model.py`**
- `PumlClass` dataclass - parsed class with name, package, attributes, notes
- `PumlAttribute` dataclass - class attributes with datatypes
- `PumlRelationship` dataclass - inheritance and associations
- `PumlPackage` dataclass - namespace mappings
- `PumlModel` dataclass - complete parsed diagram
- `RelationshipType` enum - INHERITANCE, ASSOCIATION, AGGREGATION, COMPOSITION

**`puml2rdf/parser.py`**
- `PlantUMLParser` class - regex-based multi-pass parser
- `parse_dotted_name()` - split `building.Building` into package and local name
- Handles `"Display Name" as alias` syntax
- Supports direction hints (`-u-|>`, `-d-|>`, etc.)
- Ignores PlantUML styling attributes (`#back:XXX;line:XXX`)

**`puml2rdf/converter.py`**
- `PumlToRdfConverter` class - transform parsed model to RDF graph
- `ConversionConfig` dataclass - conversion options
- Auto-generate namespaces from package prefixes
- XSD datatype mapping for attributes
- Label generation with camelCase conversion

**`puml2rdf/config.py`**
- `PumlImportConfig` dataclass - YAML configuration
- `NamespaceMapping` - package to namespace URI mappings
- `DatatypeMapping` - custom type conversions
- `load_import_config()` - load from YAML file

**`puml2rdf/merger.py`**
- `OntologyMerger` class - merge generated RDF with existing ontologies
- Preserves manual annotations while updating structure
- Conflict detection and reporting

**`puml2rdf/validators.py`**
- `PumlModelValidator` - validate parsed PlantUML model
- `RdfValidator` - validate generated RDF graph
- Check for duplicate classes, unknown references, inheritance cycles
- Severity levels: ERROR, WARNING, INFO

## Key Algorithms

### Topological Sorting
Located in `core/ordering.py`, function `topo_sort_subset()`:
- Uses Kahn's algorithm
- Handles cycles gracefully
- Alphabetical tie-breaking for determinism

### Root-Based Ordering
Located in `core/ordering.py`, function `sort_with_roots()`:
- Emits branches contiguously (all descendants together)
- Respects hierarchy within each branch
- Multiple roots processed in declaration order

### Custom Serialization
Located in `core/serialiser.py`, function `serialise_turtle()`:
- **Critical feature**: Preserves exact subject order
- rdflib always sorts alphabetically (can't be configured)
- This custom serializer writes subjects in semantic order

### Semantic Diff
Located in `diff/comparator.py`, function `compare_graphs()`:
- Uses set operations on triples: `added = new - old`, `removed = old - new`
- Groups changes by subject
- Classifies entities as added/removed/modified
- Ignores cosmetic changes (order, prefixes, whitespace)

### Competency Question Testing
Located in `cq/runner.py`, class `CQTestRunner`:
- Executes SPARQL queries against combined ontology + test data
- Supports ASK and SELECT queries
- Multiple expectation types for flexible validation
- Fail-fast mode for quick debugging

## Dependencies

### Runtime
- `rdflib>=7.0.0` - RDF parsing and manipulation
- `click>=8.1.0` - CLI framework
- `pyyaml>=6.0` - YAML configuration parsing
- `rich>=13.0.0` - Terminal formatting
- `jinja2>=3.1.0` - Template rendering

### Development
- `black>=24.0.0` - Code formatting
- `ruff>=0.1.0` - Fast linting
- `mypy>=1.8.0` - Type checking
- `pytest>=8.0.0` - Testing framework
- `pytest-cov>=4.1.0` - Coverage reporting

## Python Version

Requires Python 3.10 or higher (uses modern type hint syntax like `dict[str, str]` instead of `Dict[str, str]`).

## Testing the Code

```bash
# Install in editable mode
poetry install

# Run the CLI
poetry run rdf-construct --help
poetry run rdf-construct diff --help

# Run all tests
poetry run pytest

# Run specific test modules
poetry run pytest tests/test_diff.py -v
poetry run pytest tests/test_ordering.py -v
poetry run pytest tests/test_cq.py -v

# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## What's Implemented

### ✅ Working
- Alphabetical sorting
- Topological sorting
- Root-based ordering
- Header sections (owl:Ontology metadata)
- Prefix ordering
- Custom serialization
- Multiple profiles
- UML diagram generation
- Configurable styling and layouts
- Semantic diff (text, markdown, JSON output)
- Change filtering by type and entity
- Ontology linting with configurable rules
- Documentation generation (HTML, Markdown, JSON)
- SHACL shape generation
- PlantUML to RDF conversion
- Competency question testing
- CLI and programmatic API

### ❌ Future Features
- Stats module (ontology metrics)
- JSON-LD support
- N-Triples support
- Streaming mode for very large graphs

## License

MIT License - see LICENSE file for details.

## Summary

This is a **complete, working package** providing:

- Modern Python packaging
- Modular, testable design
- Type safety throughout
- Comprehensive documentation
- Both CLI and programmatic API
- Professional code quality