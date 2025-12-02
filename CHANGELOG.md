# Changelog

All notable changes to rdf-construct will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **New `cq-test` command** for competency question testing
  - Validate ontologies against SPARQL-based competency questions
  - YAML test file format with prefixes, inline data, and questions
  - Multiple expectation types:
    - Boolean (ASK query true/false)
    - `has_results` / `no_results` for existence checks
    - `count`, `min_count`, `max_count` for result counting
    - `results` for exact result set matching
    - `contains` for subset matching
  - Tag-based test filtering (`--tag`, `--exclude-tag`)
  - Three output formats: `text` (console), `json` (scripting), `junit` (CI)
  - Verbose mode with query text and timing
  - Fail-fast mode for quick debugging
  - Skip tests with reasons
  - Exit codes: 0 (all passed), 1 (failures), 2 (errors)
- New module: `src/rdf_construct/cq/`
  - `expectations.py` - Polymorphic expectation classes
  - `loader.py` - YAML test file parsing
  - `runner.py` - Test execution engine
  - `cli.py` - Click command integration
  - `formatters/` - Text, JSON, JUnit output formatters
- New documentation: `docs/user_guides/CQ_TESTING_GUIDE.md`
- New example: `examples/cq_tests_animal.yml`
- New tests: `tests/test_cq.py`

- **New `puml2rdf` command** for PlantUML to RDF conversion
  - Convert PlantUML class diagrams to RDF/OWL ontologies
  - Diagram-first ontology design workflow
  - Parse classes, attributes, inheritance, and associations
  - Support for dotted namespace prefixes (e.g., `building.Building` → `building:Building`)
  - Handle `"Display Name" as alias` syntax for human-readable labels
  - Direction hints in relationships (`-u-|>`, `-d-|>`, etc.)
  - PlantUML styling attributes ignored gracefully (`#back:XXX;line:XXX`)
  - Multi-line notes attached to classes become `rdfs:comment`
  - Automatic namespace generation from package prefixes
  - Custom datatype mappings (PlantUML types to XSD)
  - Merge with existing ontologies (preserves manual annotations)
  - Validation mode for CI integration (`--validate --strict`)
  - YAML configuration file support for complex setups
  - Output formats: Turtle, RDF/XML, JSON-LD, N-Triples
- New module: `src/rdf_construct/puml2rdf/`
  - `model.py` - Intermediate representation dataclasses
  - `parser.py` - Regex-based PlantUML parser
  - `converter.py` - Model to RDF/OWL conversion
  - `config.py` - YAML configuration handling
  - `merger.py` - Ontology merge logic
  - `validators.py` - Model and RDF validation
- New documentation: `docs/user_guides/PUML_IMPORT_GUIDE.md`
- New example: `examples/puml_import_config.yml`
- New tests: `tests/test_puml2rdf.py`

- **New SHACL Shape Generator** (`shacl-gen` command)

  - Generate SHACL NodeShapes from OWL ontology definitions
  - Convert domain/range to sh:property with sh:class/sh:datatype
  - Convert cardinality restrictions to sh:minCount/sh:maxCount
  - Convert owl:FunctionalProperty to sh:maxCount 1
  - Convert owl:someValuesFrom/allValuesFrom to type constraints
  - Convert owl:oneOf enumerations to sh:in
  - Support for qualified cardinality restrictions
  - Three strictness levels: minimal, standard, strict
  - Constraint inheritance from superclasses
  - Closed shape generation with configurable ignored properties
  - YAML configuration file support
  - Include rdfs:label as sh:name and rdfs:comment as sh:description
  - Output formats: Turtle, JSON-LD
- Documentation
  - Added SHACL Guide (docs/user_guides/SHACL_GUIDE.md)
  - Updated CLI Reference with shacl-gen command
  - Updated documentation index with SHACL module

- **New `docs` command** for generating documentation from RDF ontologies
  - Three output formats: `html` (navigable website), `markdown` (GitHub/GitLab compatible), `json` (structured data)
  - Comprehensive entity extraction: classes, object/datatype/annotation properties, instances
  - Class hierarchy visualisation with tree structure
  - Individual pages for each entity with cross-references
  - Client-side search functionality for HTML output (search.json index)
  - Custom Jinja2 template support for branding/customisation
  - Single-page documentation mode (`--single-page`)
  - Entity type filtering (`--include`, `--exclude`): classes, properties, instances
  - Configuration file support for complex setups
  - Namespace filtering: only displays namespaces actually used in triples
  - Inherited property detection for class documentation
  - Circular hierarchy protection (handles malformed ontologies gracefully)
  - Responsive CSS styling with property-type colour coding
  - YAML frontmatter for Markdown output (Jekyll/Hugo compatible)
- New dependency: `jinja2 >= 3.1.0`
- New documentation: `docs/user_guides/DOCS_GUIDE.md`
- Example configuration: `examples/docs-config.yml`

- **New `diff` command** for semantic ontology comparison
  - Compares two RDF graphs and reports meaningful changes
  - Ignores cosmetic differences (statement order, prefix bindings, whitespace)
  - Three output formats: `text` (terminal), `markdown` (release notes), `json` (scripting)
  - Change type filtering (`--show`, `--hide`): added, removed, modified
  - Entity type filtering (`--entities`): classes, properties, instances
  - Predicate exclusion (`--ignore-predicates`): skip timestamps, version info, etc.
  - Exit codes for CI: 0 (identical), 1 (differences found), 2 (error)
  - Entity classification: classes, object/datatype/annotation properties, individuals
  - Superclass detection for added classes
  - Blank node warning (detected but not deeply analysed)
- New documentation: `docs/user_guides/DIFF_GUIDE.md`
- Test fixtures: `tests/fixtures/diff/v1.0.ttl`, `v1.1.ttl`

- **New `lint` command** for ontology quality checking with 11 rules across three categories:
  - Structural (error): `orphan-class`, `dangling-reference`, `circular-subclass`, `property-no-type`, `empty-ontology`
  - Documentation (warning): `missing-label`, `missing-comment`
  - Best Practice (info): `redundant-subclass`, `property-no-domain`, `property-no-range`, `inconsistent-naming`
- Strictness levels (`--level strict|standard|relaxed`) for flexible enforcement
- Configuration file support (`.rdf-lint.yml`) with auto-discovery
- JSON output format (`--format json`) for CI/tooling integration
- Exit codes for CI integration: 0 (clean), 1 (warnings), 2 (errors)
- Rule enable/disable via CLI (`--enable`, `--disable`) and config file
- `--list-rules` option to display available rules
- `--init` option to generate default `.rdf-lint.yml` config
- Line number detection in lint output (best-effort source file search)
- Namespace-aware entity formatting in output (e.g., `ies:Building` not just `Building`)
- Inheritance-aware checking for `property-no-domain` and `property-no-range` (respects `rdfs:subPropertyOf`)
- New documentation: `docs/user_guides/LINT_GUIDE.md`

### Changed

- Updated `README.md` with semantic diff feature and examples
- Updated `docs/index.md` to reference docs, diff, lint, and cq-test functionality
- Updated `docs/user_guides/CLI_REFERENCE.md` with full docs, diff, lint, and cq-test command documentation

## [0.1.0] - 2025-11-30

Initial public release.

### Added

#### Core Features
- `order` command for semantic RDF/Turtle ordering
  - Topological sorting respecting `rdfs:subClassOf` and `rdfs:subPropertyOf`
  - Alphabetical sorting for deterministic output
  - Anchor-based ordering for key concepts
  - Configurable predicate ordering within subjects
  - Custom serialiser preserving subject order (rdflib always sorts alphabetically)

- `uml` command for PlantUML class diagram generation
  - Root-based class selection with descendant traversal
  - Focus-based class selection for specific views
  - Explicit mode for precise control over diagram contents
  - Configurable depth limiting for large ontologies
  - Instance (individual) rendering with class relationships

#### Property Handling
- Multiple property selection modes: `domain_based`, `connected`, `explicit`, `all`, `none`
- Object property and datatype property distinction
- Property filtering via include/exclude lists

#### Styling System
- Namespace-based class colouring
- Type-based styling for meta-classes
- Instance styling with class border inheritance
- Arrow styling for different relationship types
- IES colour palette support with semantic colouring
- Stereotype mapping and display

#### Layout Options
- Direction control (top-to-bottom, left-to-right)
- Orthogonal line routing
- Inheritance arrow merging
- Class grouping by namespace
- Configurable spacing

#### ODM Compliance
- ODM (Ontology Definition Metamodel) rendering mode
- RDF vocabulary styling (rdf:type as dependency arrows)
- Standards-compliant diagram generation

#### CLI
- Click-based command-line interface
- Multiple source file support
- Profile/context selection
- Output directory configuration
- Context and profile listing commands

### Documentation
- Getting Started guide
- UML Guide with complete feature reference
- CLI Reference with all commands and options
- Architecture documentation for contributors
- IES Colour Palette guides
- Project Setup guide for end users
- Quick Reference card

### Examples
- Animal ontology (simple hierarchy)
- Organisation ontology (multiple roots)
- IES Building ontology (complex real-world example)
- Sample configuration files for all features

---

## Version History Summary

| Version | Date           | Highlights |
|---------|----------------|------------|
| [0.2.0] | 2025-11-30     | Add starter templates, PROJECT_SETUP.md and QUICKE_REFERENCE.md |
| [0.1.0] | 2025-11-30     | Initial release: ordering, UML generation, styling |

[Unreleased]: https://github.com/aigora-de/rdf-construct/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/aigora-de/rdf-construct/releases/tag/v0.2.0
[0.1.0]: https://github.com/aigora-de/rdf-construct/releases/tag/v0.1.0