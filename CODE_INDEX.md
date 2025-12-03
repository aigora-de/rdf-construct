# rdf-construct Source Code Package

This directory contains the complete refactored **rdf-construct** package code.

## Directory Structure

```
docs/
├── index.md
├── dev/
│   ├── ARCHITECTURE.md
│   └── UML_IMPLEMENTATION.md
└── user_guides/
│   ├── CLI_REFERENCE.md
│   ├── CQ_TEST_GUIDE.md
│   ├── DIFF_GUIDE.md
│   ├── GETTING_STARTED.md
│   ├── LINT_GUIDE.md
│   ├── SHACL_GUIDE.md
│   └── UML_GUIDE.md
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
│   ├── __init__.py
│   ├── context.py
│   ├── mapper.py
│   ├── renderer.py
│   ├── odm_renderer.py
│   ├── uml_style.py
│   └── uml_layout.py
└── stats/
│   ├── __init__.py
│   ├── collector.py
│   ├── comparator.py
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── basic.py
│   │   ├── hierarchy.py
│   │   ├── properties.py
│   │   ├── documentation.py
│   │   ├── complexity.py
│   │   └── connectivity.py
│   └── formatters/
│   │   ├── __init__.py
│   │   ├── text.py
│   │   ├── json_fmt.py
│           └── markdown.py
examples/
├── animal_ontology.ttl
├── building_structure_context.yml
├── cq_tests_animal.yml
├── ies_colour_palette.yml
├── sample_profile.yml
├── uml_contexts.yml
├── uml_layouts.yml
└── uml_styles.yml
│
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
│   └── diff/
│       ├── v1.0.ttl
│       └── v1.1.ttl
├── pyproject.toml              # Modern Python packaging config
├── README.md                   # User documentation
├── CONTRIBUTING.md             # Development guide
├── CHANGELOG.md                # Version history
├── LICENSE                     # MIT license
├── .gitignore                  # Git ignore rules
├── .pre-commit-config.yaml     # Pre-commit hooks
└── CODE_INDEX.md               # This file
```

## File Descriptions

### Core Package Files

**`rdf_construct/__init__.py`** (40 lines)
- Package initialization and exports
- Version number
- Public API definitions

**`rdf_construct/__main__.py`** (5 lines)
- Entry point for `python -m rdf_construct`
- Calls CLI

**`rdf_construct/cli.py`** (174 lines)
- Click-based CLI commands
- `order` command for ordering ontologies
- `profiles` command for listing profiles
- `contexts` command for listing UML contexts
- `uml` command for generating diagrams
- `puml2rdf` command to generate RDF from PUML
- `lint` command for quality checking
- `shacl` command for generating SHACL shapes
- `diff` command for semantic comparison
- `cq-test` command for competency question testing
- `stats` command for ontology metrics
- `doc` command for generating documentation from RDF

### Core Modules

**`core/__init__.py`** (34 lines)
- Core module exports
- Makes functions available at package level

**`core/config.py`** (193 lines)
- YAML loading functions
- Dataclasses for configuration
- `OrderingSpec` for complete config
- `SectionConfig` for section definitions
- `ProfileConfig` for profile definitions
- CURIE expansion
- Prefix rebinding

**`core/profile.py`** (111 lines)
- `OrderingConfig` class - main config manager
- `OrderingProfile` class - individual profile
- Profile loading and access methods
- YAML parsing with error handling

**`core/selector.py`** (65 lines)
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

**`core/serializer.py`** (168 lines)
- `format_term()` - format RDF terms as Turtle strings
- `serialize_turtle()` - custom Turtle writer that preserves order
- `build_section_graph()` - filter graph to specific subjects
- **Critical**: Preserves subject order (rdflib doesn't)

**`core/utils.py`** (90 lines)
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
- UML module exports

**`uml/context.py`**
- `UMLContext` - diagram specification
- `UMLConfig` - manages multiple contexts

**`uml/mapper.py`**
- Entity selection for diagrams
- Class, property, and instance selection strategies

**`uml/renderer.py`**
- PlantUML text generation
- Classes, properties, instances rendering

**`uml/odm_renderer.py`**
- OMG ODM RDF Profile compliant rendering

**`uml/uml_style.py`**
- Color schemes and visual styling
- Namespace-based and type-based coloring

**`uml/uml_layout.py`**
- Layout configuration
- Direction, spacing, grouping controls

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

### Stats Module

**`stats/__init__.py`**
- Public API exports for stats functionality

**`stats/collector.py`**
- `OntologyStats` dataclass - aggregates all metrics
- `collect_stats()` - main collection orchestrator
- Category filtering (include/exclude)

**`stats/comparator.py`**
- `MetricChange` - represents a change in a single metric
- `ComparisonResult` - aggregates all changes between versions
- `compare_stats()` - compares two OntologyStats objects
- Improvement/degradation detection

**`stats/metrics/basic.py`**
- `BasicStats` - counts (triples, classes, properties, individuals)
- `collect_basic_stats()` - count collection
- Helper functions for entity discovery

**`stats/metrics/hierarchy.py`**
- `HierarchyStats` - hierarchy analysis
- Depth calculation (max, average)
- Branching factor
- Orphan class detection

**`stats/metrics/properties.py`**
- `PropertyStats` - property coverage
- Domain/range coverage rates
- Inverse pairs, functional, symmetric counts

**`stats/metrics/documentation.py`**
- `DocumentationStats` - documentation coverage
- Label coverage (rdfs:label, skos:prefLabel)
- Comment coverage (rdfs:comment, skos:definition)

**`stats/metrics/complexity.py`**
- `ComplexityStats` - structural complexity
- Multiple inheritance detection
- OWL restriction and equivalence counts

**`stats/metrics/connectivity.py`**
- `ConnectivityStats` - class connectivity
- Most connected class identification
- Isolated class detection

**`stats/formatters/text.py`**
- Text output with aligned columns
- Human-readable format

**`stats/formatters/json_fmt.py`**
- JSON serialisation
- Machine-readable format

**`stats/formatters/markdown.py`**
- Markdown tables
- README-ready format

### Configuration

**`pyproject.toml`** (134 lines)
- Modern Python packaging configuration
- Dependencies: rdflib, click, pyyaml, rich
- Dev dependencies: black, ruff, mypy, pytest
- Tool configurations for black, ruff, mypy, pytest
- Entry point: `rdf-construct` command

### Documentation

**`README.md`** (154 lines)
- User-facing documentation
- Installation instructions
- Quick start guide
- Configuration examples
- Programmatic API usage
- Roadmap

**`CONTRIBUTING.md`** (development guide)
- How to set up development environment
- Code style guidelines
- How to run tests
- How to contribute

**`CHANGELOG.md`** (version history)
- Release notes
- Version changes

**`LICENSE`** (MIT)
- Open source license text

### Examples

**`examples/basic_ordering.py`**
- Complete working example of programmatic usage
- Shows how to use the API without CLI

**`examples/sample_config.yml`**
- Complete YAML configuration example
- Shows all profile types
- Includes comments explaining options

### Tests

**`tests/test_ordering.py`**
- Basic unit tests for ordering functions
- Needs expansion (currently minimal)

**`tests/test_stats.py`**
- Unit tests for stats module
- Tests for each metric category
- Comparison and formatter tests

**`tests/fixtures/`**
- Directory for test data files
- Currently empty, needs test ontologies

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
Located in `core/serializer.py`, function `serialize_turtle()`:
- **Critical feature**: Preserves exact subject order
- rdflib always sorts alphabetically (can't be configured)
- This custom serializer writes subjects in semantic order
- Makes RDF files readable and maintainable

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

### Hierarchy Depth Calculation
Located in `stats/metrics/hierarchy.py`:
- Recursive depth computation with cycle detection
- Handles multiple inheritance (takes max parent depth)
- Computes both max and average depths

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
- `types-PyYAML>=6.0.0` - Type stubs for PyYAML

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

### Working
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
- UML diagram generation
- Semantic diff
- Ontology statistics

### Future Features
- JSON-LD support
- N-Triples support
- Validation framework
- Graph visualization

## Getting Help

1. Check docstrings: Every function has comprehensive documentation
2. Read the README.md for user guide
3. See examples/ for working code
4. Review ARCHITECTURE.md for system design

## License

MIT License - see LICENSE file for details.
