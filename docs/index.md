# rdf-construct Documentation

## Quick Links

**New User?** → [Getting Started](user_guides/GETTING_STARTED.md)  
**Quick Ontology Overview?** → [Describe Guide](user_guides/DESCRIBE_GUIDE.md)  
**Generate Documentation?** → [Docs Guide](user_guides/DOCS_GUIDE.md)  
**Generate Diagrams?** → [UML Guide](user_guides/UML_GUIDE.md)  
**Import from PlantUML?** → [PUML2RDF Guide](user_guides/PUML2RDF_GUIDE.md)  
**Generate SHACL Shapes?** → [SHACL Guide](user_guides/SHACL_GUIDE.md)  
**Compare Ontologies?** → [Diff Guide](user_guides/DIFF_GUIDE.md)  
**Check Quality?** → [Lint Guide](user_guides/LINT_GUIDE.md)  
**Test Competency Questions?** → [CQ Testing Guide](user_guides/CQ_TEST_GUIDE.md)  
**Ontology Metrics?** → [Stats Guide](user_guides/STATS_GUIDE.md)  
**Merge Ontologies?** → [Merge & Split Guide](user_guides/MERGE_SPLIT_GUIDE.md)  
**Split Ontologies?** → [Merge & Split Guide](user_guides/MERGE_SPLIT_GUIDE.md#split-command)  
**Refactor URIs?** → [Refactor Guide](user_guides/REFACTOR_GUIDE.md)  
**Multi-Language Support?** → [Localise Guide](user_guides/LOCALISE_GUIDE.md)  
**Need Command Syntax?** → [CLI Reference](user_guides/CLI_REFERENCE.md)  
**Quick Cheat Sheet?** → [Quick Reference](user_guides/QUICK_REFERENCE.md)  
**Contributing?** → [Contributing Guide](../CONTRIBUTING.md)  
**Code Reference?** → [Code Index](../CODE_INDEX.md)

## Documentation Structure

### User Guides (docs/user_guides/)

For users of rdf-construct who want to generate diagrams and work with RDF ontologies.

- **[Getting Started](user_guides/GETTING_STARTED.md)** - 5-minute quick start
  - Installation
  - Command categories overview
  - Basic concepts
  - Common tasks

- **[Describe Guide](user_guides/DESCRIBE_GUIDE.md)** - Quick ontology orientation
  - Metadata and metrics extraction
  - OWL profile detection
  - Import resolution analysis
  - Hierarchy and documentation coverage

- **[Docs Guide](user_guides/DOCS_GUIDE.md)** - Documentation generation
  - HTML, Markdown, and JSON output
  - Custom templates
  - Search index generation
  - Programmatic usage

- **[UML Guide](user_guides/UML_GUIDE.md)** - Complete UML feature reference
  - Context configuration
  - Class selection strategies
  - Property filtering modes
  - Instance rendering
  - Styling and layout
  - Complete examples
  - Tips and techniques

- **[PUML2RDF Guide](user_guides/PUML2RDF_GUIDE.md)** - Convert PlantUML to RDF
  - Diagram-first ontology design
  - Supported PlantUML syntax
  - Namespace handling
  - Merge with existing ontologies
  - Validation and configuration

- **[SHACL Guide](user_guides/SHACL_GUIDE.md)** - SHACL shape generation
  - Generating shapes from OWL
  - Strictness levels (minimal, standard, strict)
  - Configuration options
  - OWL pattern coverage
  - Validation with pySHACL
  - CI integration

- **[Diff Guide](user_guides/DIFF_GUIDE.md)** - Semantic ontology comparison
  - Comparing ontology versions
  - Output formats (text, markdown, JSON)
  - Filtering changes
  - CI integration

- **[Lint Guide](user_guides/LINT_GUIDE.md)** - Ontology quality checking
  - Available rules (11 across 3 categories)
  - Configuration
  - CI integration

- **[CQ Testing Guide](user_guides/CQ_TEST_GUIDE.md)** - Competency question testing
  - SPARQL-based ontology validation
  - Test file format
  - Expectation types
  - CI integration with JUnit output

- **[Stats Guide](user_guides/STATS_GUIDE.md)** - Ontology metrics and statistics
  - Basic counts (classes, properties, triples)
  - Hierarchy analysis (depth, branching, orphans)
  - Documentation coverage
  - Comparison mode
  - Output formats (text, JSON, markdown)

- **[Merge & Split Guide](user_guides/MERGE_SPLIT_GUIDE.md)** - Combining and modularising ontologies
  - Merging with conflict detection and resolution
  - Namespace remapping
  - Data migration
  - Splitting monolithic ontologies into modules
  - Configuration options

- **[Refactor Guide](user_guides/REFACTOR_GUIDE.md)** - Renaming and deprecation
  - Single entity and bulk namespace renames
  - Deprecation with owl:deprecated and dcterms:isReplacedBy
  - Data migration for instance graphs
  - Dry-run preview mode

- **[Localise Guide](user_guides/LOCALISE_GUIDE.md)** - Multi-language translation
  - Extract translatable strings to YAML
  - Merge completed translations back
  - Translation coverage reports
  - Status tracking workflow

- **[CLI Reference](user_guides/CLI_REFERENCE.md)** - Command reference
  - All commands with options
  - Configuration file formats
  - Common workflows
  - Troubleshooting

- **[Quick Reference](user_guides/QUICK_REFERENCE.md)** - Cheat sheet
  - Command summary
  - Common patterns
  - Exit codes

- **[Project Setup](user_guides/PROJECT_SETUP.md)** - Setting up a new project
  - Starter templates
  - Directory structure
  - Configuration basics

### Developer Documentation (docs/dev/)

For contributors and maintainers who want to understand or extend rdf-construct.

- **[Architecture](dev/ARCHITECTURE.md)** - System design
  - Module structure
  - Data flow
  - Key algorithms
  - Design decisions
  - Extension points

- **[UML Implementation](dev/UML_IMPLEMENTATION.md)** - Technical details
  - Implementation approach
  - Selection strategies
  - Rendering details
  - Styling system
  - Layout system
  - Known issues

- **[Contributing](../CONTRIBUTING.md)** - Development guide
  - Setting up development environment
  - Coding standards
  - Testing guidelines
  - Adding features
  - Release process

## What is rdf-construct?

A Python CLI toolkit for RDF operations:

- **Semantic Ordering**: Serialise RDF/Turtle with meaningful order (not alphabetical)
- **Ontology Description**: Quick orientation with profile detection and metrics
- **Documentation Generation**: Create navigable HTML/Markdown docs from ontologies
- **UML Generation**: Create PlantUML class diagrams from ontologies
- **PlantUML Import**: Convert PlantUML diagrams to RDF ontologies
- **SHACL Generation**: Generate validation shapes from OWL definitions
- **Semantic Diff**: Compare ontologies and identify meaningful changes
- **Ontology Merging**: Combine multiple ontologies with conflict detection and data migration
- **Ontology Splitting**: Split monolithic ontologies into modules with dependency tracking
- **Ontology Refactoring**: Rename URIs and deprecate entities with proper OWL annotations
- **Multi-Language Support**: Extract, translate, and merge translations for internationalised ontologies
- **Ontology Linting**: Check ontology quality with configurable rules
- **Competency Question Testing**: Validate ontologies against SPARQL-based tests
- **Ontology Statistics**: Comprehensive metrics with comparison mode
- **Flexible Configuration**: YAML-based control without code changes

Named after the ROM construct from William Gibson's *Neuromancer*—preserved, structured knowledge.

## Quick Examples

> **Note**: If installed via pip, use `rdf-construct` directly. If using Poetry for development, prefix with `poetry run`.

### Describe an Ontology

```bash
# Quick orientation to an unfamiliar ontology
poetry run rdf-construct describe ontology.ttl

# Brief summary (metadata + metrics + profile)
poetry run rdf-construct describe ontology.ttl --brief

# JSON output for scripting
poetry run rdf-construct describe ontology.ttl --format json
```

### Generate Documentation

```bash
# HTML documentation with search
poetry run rdf-construct docs ontology.ttl -o api-docs/

# Markdown for GitHub wiki
poetry run rdf-construct docs ontology.ttl --format markdown

# JSON for custom rendering
poetry run rdf-construct docs ontology.ttl --format json
```

### Generate UML Diagrams

```bash
# All contexts
poetry run rdf-construct uml ontology.ttl -C config.yml

# Specific context
poetry run rdf-construct uml ontology.ttl -C config.yml -c animal_taxonomy

# With styling and layout
poetry run rdf-construct uml ontology.ttl -C config.yml \
  --style-config styles.yml --style default \
  --layout-config layouts.yml --layout hierarchy
```

### Reorder RDF Files

```bash
# Semantic ordering
poetry run rdf-construct order ontology.ttl order.yml

# Specific profile
poetry run rdf-construct order ontology.ttl order.yml -p logical_topo
```

### Import from PlantUML

```bash
# Basic conversion
poetry run rdf-construct puml2rdf design.puml

# Custom namespace
poetry run rdf-construct puml2rdf design.puml -n http://example.org/ont#

# Merge with existing ontology
poetry run rdf-construct puml2rdf design.puml --merge existing.ttl

# Validate only
poetry run rdf-construct puml2rdf design.puml --validate
```

### Generate SHACL Shapes

```bash
# Basic generation
poetry run rdf-construct shacl-gen ontology.ttl -o shapes.ttl

# Strict mode with closed shapes
poetry run rdf-construct shacl-gen ontology.ttl --level strict --closed

# With configuration file
poetry run rdf-construct shacl-gen ontology.ttl --config shacl-config.yml
```

### Compare Ontology Versions

```bash
# Basic comparison
poetry run rdf-construct diff v1.0.ttl v1.1.ttl

# Generate markdown changelog
poetry run rdf-construct diff v1.0.ttl v1.1.ttl --format markdown -o CHANGELOG.md
```

### Check Ontology Quality

```bash
# Run all lint rules
poetry run rdf-construct lint ontology.ttl

# Strict checking
poetry run rdf-construct lint ontology.ttl --level strict
```

### Test Competency Questions

```bash
# Run competency question tests
poetry run rdf-construct cq-test ontology.ttl tests.yml

# With JUnit output for CI
poetry run rdf-construct cq-test ontology.ttl tests.yml --format junit -o results.xml

# Filter by tag
poetry run rdf-construct cq-test ontology.ttl tests.yml --tag schema
```

### Ontology Statistics

```bash
# Display statistics
poetry run rdf-construct stats ontology.ttl

# Compare two versions
poetry run rdf-construct stats v1.ttl v2.ttl --compare

# JSON output for CI pipelines
poetry run rdf-construct stats ontology.ttl --format json
```

### Merge Ontologies

```bash
# Basic merge
poetry run rdf-construct merge core.ttl extension.ttl -o merged.ttl

# With priorities (higher wins conflicts)
poetry run rdf-construct merge core.ttl extension.ttl -o merged.ttl -p 1 -p 2

# Generate conflict report
poetry run rdf-construct merge core.ttl extension.ttl -o merged.ttl --report conflicts.md
```

### Split Ontologies
```bash
# Split by namespace (auto-detect modules)
poetry run rdf-construct split large.ttl -o modules/ --by-namespace

# Split with configuration
poetry run rdf-construct split large.ttl -o modules/ -c split.yml

# Dry run preview
poetry run rdf-construct split large.ttl -o modules/ --by-namespace --dry-run
```

### Refactor Ontologies
```bash
# Fix a typo
poetry run rdf-construct refactor rename ontology.ttl \
  --from "ex:Buiding" --to "ex:Building" -o fixed.ttl

# Bulk namespace change
poetry run rdf-construct refactor rename ontology.ttl \
  --from-namespace "http://old/" --to-namespace "http://new/" -o migrated.ttl

# Deprecate an entity
poetry run rdf-construct refactor deprecate ontology.ttl \
  --entity "ex:LegacyClass" --replaced-by "ex:NewClass" \
  --message "Use NewClass instead." -o updated.ttl
```

### Multi-Language Translations
```bash
# Extract strings for German translation
poetry run rdf-construct localise extract ontology.ttl --language de -o translations/de.yml

# Merge completed translations
poetry run rdf-construct localise merge ontology.ttl translations/de.yml -o localised.ttl

# Check translation coverage
poetry run rdf-construct localise report ontology.ttl --languages en,de,fr
```

## Repository

- **GitHub**: https://github.com/aigora-de/rdf-construct
- **Issues**: https://github.com/aigora-de/rdf-construct/issues
- **Discussions**: https://github.com/aigora-de/rdf-construct/discussions

## Additional References

- **[Code Index](../CODE_INDEX.md)**: Complete project file inventory and structure
- **[Contributing](../CONTRIBUTING.md)**: Development setup and guidelines

## License

MIT License. See [LICENSE](../LICENSE) file.

## Recent Changes

See [CHANGELOG.md](../CHANGELOG.md) for version history.

---

## Archive

Previous documentation versions are preserved in [docs/archive/](archive/) for reference.
