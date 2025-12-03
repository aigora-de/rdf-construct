# rdf-construct Source Code Index

This document provides a complete inventory of the rdf-construct package code.

## Directory Structure

```
docs/
├── index.md
├── dev/
│   ├── ARCHITECTURE.md
│   └── UML_IMPLEMENTATION.md
└── user_guides/
    ├── CLI_REFERENCE.md
    ├── CQ_TEST_GUIDE.md
    ├── DIFF_GUIDE.md
    ├── DOCS_GUIDE.md
    ├── GETTING_STARTED.md
    ├── LINT_GUIDE.md
    ├── PLANTUML_IMPORT_GUIDE.md
    ├── PROJECT_SETUP.md
    ├── QUICK_REFERENCE.md
    ├── SHACL_GUIDE.md
    ├── STATS_GUIDE.md
    └── UML_GUIDE.md

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
│   ├── renderers/
│   │   ├── __init__.py
│   │   ├── html.py
│   │   ├── json.py
│   │   └── markdown.py
│   └── templates/
│       └── html/
│           ├── base.html.jinja
│           ├── class.html.jinja
│           ├── hierarchy.html.jinja
│           ├── index.html.jinja
│           ├── instance.html.jinja
│           ├── namespaces.html.jinja
│           ├── property.html.jinja
│           └── single_page.html.jinja
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
├── stats/
│   ├── __init__.py
│   ├── collector.py
│   ├── comparator.py
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── basic.py
│   │   ├── complexity.py
│   │   ├── connectivity.py
│   │   ├── documentation.py
│   │   ├── hierarchy.py
│   │   └── properties.py
│   └── formatters/
│       ├── __init__.py
│       ├── json.py
│       ├── markdown.py
│       └── text.py
└── uml/
    ├── __init__.py
    ├── context.py
    ├── mapper.py
    ├── odm_renderer.py
    ├── renderer.py
    ├── uml_layout.py
    └── uml_style.py

examples/
├── animal_ontology.ttl
├── basic_ordering.py
├── building_structure_context.yml
├── cq_tests_animal.yml
├── docs_config.yml
├── ies_building_contexts.yml
├── ies_colour_examples.yml
├── ies_colour_palette.yml
├── ies_colour_palette_with_instances.yml
├── ordering_starter.yml
├── organisation_ontology.ttl
├── puml_import.yml
├── rdf_lint.yml
├── sample_profile.yml
├── shacl_config.yml
├── test_profile.yml
├── uml_contexts.yml
├── uml_contexts_explicit.yml
├── uml_contexts_starter.yml
├── uml_layouts.yml
├── uml_styles.yml
└── uml_styles_starter.yml

tests/
├── __init__.py
├── test_cq.py
├── test_diff.py
├── test_docs.py
├── test_explicit_mode.py
├── test_instance_styling.py
├── test_lint.py
├── test_odm_renderer.py
├── test_ordering.py
├── test_plantuml.py
├── test_predicate_order.py
├── test_puml2rdf.py
├── test_shacl_gen.py
├── test_stats.py
└── fixtures/
    └── diff/
        ├── v1_0.ttl
        └── v1_1.ttl

├── pyproject.toml              # Modern Python packaging config
├── poetry.lock                 # Locked dependencies
├── README.md                   # User documentation
├── CONTRIBUTING.md             # Development guide
├── CHANGELOG.md                # Version history
├── CODE_INDEX.md               # This file
├── CODE_OF_CONDUCT.md          # Community guidelines
├── LICENSE                     # MIT license
├── .gitignore                  # Git ignore rules
└── .pre-commit-config.yaml     # Pre-commit hooks
```

## File Descriptions

### Core Package Files

**`rdf_construct/__init__.py`**
- Package initialisation and exports
- Version number (`__version__`)
- Public API definitions

**`rdf_construct/__main__.py`**
- Entry point for `python -m rdf_construct`
- Calls CLI

**`rdf_construct/cli.py`** (174 lines)
- Click-based CLI commands
- `order` command for ordering ontologies
- `profiles` command for listing profiles
- `contexts` command for listing UML contexts
- `uml` command for generating diagrams
- `docs` command for generating documentation
- `puml2rdf` command to generate RDF from PlantUML
- `shacl-gen` command for generating SHACL shapes
- `lint` command for quality checking
- `diff` command for semantic comparison
- `cq-test` command for competency question testing
- `stats` command for ontology metrics

### Core Modules (`core/`)

**`core/__init__.py`**
- Core module exports
- Makes functions available at package level

**`core/config.py`**
- YAML loading functions
- Dataclasses for configuration
- `OrderingSpec` for complete config
- `SectionConfig` for section definitions
- `ProfileConfig` for profile definitions
- CURIE expansion
- Prefix rebinding

**`core/profile.py`**
- `OrderingConfig` class - main config manager
- `OrderingProfile` class - individual profile
- Profile loading and access methods
- YAML parsing with error handling

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

**`core/predicate_ordering.py`**
- `PredicateOrder` dataclass - ordering specification
- `get_predicate_order()` - retrieve ordering for a profile
- Configurable predicate output order within subjects

**`core/utils.py`**
- `extract_prefix_map()` - get namespaces from graph
- `expand_curie()` - expand CURIEs to full IRIs
- `rebind_prefixes()` - set prefix order
- `qname_sort_key()` - generate sortable keys for RDF terms

### Documentation Module (`docs/`)

Generate HTML, Markdown, or JSON documentation from RDF ontologies.

**`docs/__init__.py`**
- Public API exports
- `DocsConfig`, `DocsGenerator`, `load_docs_config`

**`docs/config.py`**
- `DocsConfig` dataclass - documentation settings
- `load_docs_config()` - load from YAML file
- Output format, template, filtering options

**`docs/extractors.py`**
- `OntologyExtractor` class - extract entities from RDF
- Class, property, instance extraction
- Hierarchy building
- Inherited property detection

**`docs/generator.py`**
- `DocsGenerator` class - orchestrate documentation generation
- Format routing (HTML, Markdown, JSON)
- Output file management

**`docs/search.py`**
- `SearchIndexBuilder` - build search.json for HTML
- Entity indexing for client-side search

**`docs/renderers/`**
- `html.py` - Jinja2-based HTML rendering
- `markdown.py` - Markdown file generation
- `json.py` - Structured JSON output

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
- `filter_diff()` - filter diff results by type/entity
- `parse_filter_string()` - parse comma-separated filter strings
- Maps CLI filter names to internal types

**`diff/formatters/`**
- `text.py` - Coloured terminal output
- `markdown.py` - Release notes format/changelogs
- `json.py` - Structured JSON for scripting
- `__init__.py` - `format_diff()` dispatcher

### Lint Module (`lint/`)

Ontology quality checking with configurable rules.

**`lint/__init__.py`**
- Public API exports
- `LintEngine`, `LintConfig`, `LintRule`, `LintIssue`

**`lint/config.py`**
- `LintConfig` dataclass - lint settings
- `load_lint_config()` - load from YAML
- `find_config_file()` - auto-discover `.rdf-lint.yml`
- Rule enable/disable, severity levels

**`lint/engine.py`**
- `LintEngine` class - orchestrate rule execution
- Issue collection and severity filtering
- Exit code determination

**`lint/rules.py`**
- `LintRule` abstract base class
- 11 built-in rules across 3 categories:
  - Structural: `orphan-class`, `dangling-reference`, `circular-subclass`, `property-no-type`, `empty-ontology`
  - Documentation: `missing-label`, `missing-comment`
  - Best Practice: `redundant-subclass`, `property-no-domain`, `property-no-range`, `inconsistent-naming`

**`lint/formatters.py`**
- `TextFormatter` - coloured terminal output
- `JsonFormatter` - machine-readable JSON
- `get_formatter()` - format dispatcher

### `puml2rdf` Module

Convert PlantUML class diagrams to RDF/OWL ontologies.

**`puml2rdf/__init__.py`**
- Public API exports
- `PlantUMLParser`, `PumlToRdfConverter`, `ConversionConfig`

**`puml2rdf/model.py`**
- `PumlClass` dataclass - parsed class definition
- `PumlAttribute` dataclass - class attribute
- `PumlRelationship` dataclass - relationship between classes
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

### SHACL Module (`shacl/`)

Generate SHACL validation shapes from OWL definitions.

**`shacl/__init__.py`**
- Public API exports
- `ShaclGenerator`, `ShaclConfig`

**`shacl/config.py`**
- `ShaclConfig` dataclass - generation settings
- Strictness levels: minimal, standard, strict
- Class filtering, closed shapes, severity options

**`shacl/generator.py`**
- `ShaclGenerator` class - orchestrate shape generation
- Per-class NodeShape creation
- Property constraint generation

**`shacl/converters.py`**
- `convert_domain_range()` - domain/range to sh:property
- `convert_cardinality()` - cardinality to sh:minCount/sh:maxCount
- `convert_functional()` - FunctionalProperty to sh:maxCount 1
- `convert_restrictions()` - OWL restrictions to SHACL constraints

**`shacl/namespaces.py`**
- SHACL namespace bindings
- Prefix management for output

### Stats Module (`stats/`)

Comprehensive ontology metrics and comparison.

**`stats/__init__.py`**
- Public API exports
- `collect_stats()`, `compare_stats()`, `format_stats()`

**`stats/collector.py`**
- `OntologyStats` dataclass - aggregates all metrics
- `collect_stats()` - main collection orchestrator
- Category filtering (include/exclude)

**`stats/comparator.py`**
- `MetricChange` - represents a change in a single metric
- `ComparisonResult` - aggregates all changes between versions
- `compare_stats()` - compares two OntologyStats objects
- Improvement/degradation detection

**`stats/metrics/`**
- `basic.py` - Counts (triples, classes, properties, individuals)
- `hierarchy.py` - Depth, branching factor, orphans
- `properties.py` - Domain/range coverage, functional, symmetric
- `documentation.py` - Label and comment coverage
- `complexity.py` - Multiple inheritance, OWL axioms
- `connectivity.py` - Most connected class, isolated classes

**`stats/formatters/`**
- `text.py` - Aligned columns for terminal
- `json.py` - Machine-readable JSON
- `markdown.py` - README-ready tables

### UML Module (`uml/`)

Generate PlantUML class diagrams from RDF ontologies.

**`uml/__init__.py`**
- Public API exports
- `load_uml_config()`, `collect_diagram_entities()`, `render_plantuml()`

**`uml/context.py`**
- `UmlConfig` class - load and manage contexts
- `UmlContext` dataclass - single context definition
- Class selection strategies (root, focus, selector)
- Property and instance filtering

**`uml/mapper.py`**
- `collect_diagram_entities()` - select classes, properties, instances
- Descendant traversal with depth limiting
- Property mode handling (domain_based, connected, explicit, all, none)

**`uml/renderer.py`**
- `render_plantuml()` - generate PlantUML output
- Class rendering with attributes
- Relationship rendering (inheritance, object properties)
- Instance rendering

**`uml/odm_renderer.py`**
- `render_odm_plantuml()` - OMG ODM RDF Profile compliant output
- Standard stereotypes and notation
- Compliance with UML profile standards

**`uml/uml_style.py`**
- `StyleConfig` class - load style schemes
- `StyleScheme` dataclass - visual styling
- Namespace and type-based colouring
- Arrow styling, stereotypes

**`uml/uml_layout.py`**
- `LayoutConfig` class - load layouts
- `LayoutOptions` dataclass - layout settings
- Direction, spacing, grouping options

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

### Custom Serialisation
Located in `core/serialiser.py`, function `serialise_turtle()`:
- **Critical feature**: Preserves exact subject order
- rdflib always sorts alphabetically (can't be configured)
- This custom serialiser writes subjects in semantic order
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
- `pre-commit>=3.6.0` - Pre-commit hooks

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
poetry run pytest tests/test_stats.py -v
poetry run pytest tests/test_lint.py -v

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
- Custom serialisation
- Multiple profiles
- UML diagram generation
- Configurable styling and layouts
- ODM-compliant rendering
- Semantic diff (text, markdown, JSON output)
- Change filtering by type and entity
- Ontology linting with 11 configurable rules
- Documentation generation (HTML, Markdown, JSON)
- SHACL shape generation
- PlantUML to RDF conversion
- Competency question testing
- Ontology statistics with comparison
- CLI and programmatic API

### Future Features
- JSON-LD input support
- N-Triples input support
- Web UI for configuration
- Additional lint rules
- Graph visualisation

## Getting Help

1. Check docstrings: Every function has comprehensive documentation
2. Read the README.md for user guide
3. See examples/ for working code
4. Review ARCHITECTURE.md for system design
5. Browse user guides in docs/user_guides/

## License

MIT License - see LICENSE file for details.