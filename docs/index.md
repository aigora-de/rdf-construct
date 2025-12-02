# rdf-construct Documentation

## Quick Links

**New User?** → [Getting Started](user_guides/GETTING_STARTED.md)  
**Generate Documentation?** → [Docs Guide](user_guides/DOCS_GUIDE.md)  
**Generate Diagrams?** → [UML Guide](user_guides/UML_GUIDE.md)  
**Import from PlantUML?** → [PlantUML Import Guide](user_guides/PUML_IMPORT_GUIDE.md)  
**Generate SHACL Shapes?** → [SHACL Guide](user_guides/SHACL_GUIDE.md)  
**Compare Ontologies?** → [Diff Guide](user_guides/DIFF_GUIDE.md)  
**Check Quality?** → [Lint Guide](user_guides/LINT_GUIDE.md)  
**Need Command Syntax?** → [CLI Reference](user_guides/CLI_REFERENCE.md)  
**Contributing?** → [Contributing Guide](../CONTRIBUTING.md)  
**Code Reference?** → [Code Index](../CODE_INDEX.md)

## Documentation Structure

### User Guides (docs/user_guides/)

For users of rdf-construct who want to generate diagrams and work with RDF ontologies.

- **[Getting Started](user_guides/GETTING_STARTED.md)** - 5-minute quick start
  - Installation
  - Your first diagram
  - Basic concepts
  - Common tasks
  - Simple examples

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

- **[PlantUML Import Guide](user_guides/PUML_IMPORT_GUIDE.md)** - Convert PlantUML to RDF
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
  - Available rules
  - Configuration
  - CI integration

- **[CLI Reference](user_guides/CLI_REFERENCE.md)** - Command reference
  - All commands with options
  - Configuration file formats
  - Common workflows
  - Troubleshooting

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
- **Documentation Generation**: Create navigable HTML/Markdown docs from ontologies
- **UML Generation**: Create PlantUML class diagrams from ontologies
- **PlantUML Import**: Convert PlantUML diagrams to RDF ontologies
- **SHACL Generation**: Generate validation shapes from OWL definitions
- **Semantic Diff**: Compare ontologies and identify meaningful changes
- **Ontology Linting**: Check ontology quality with configurable rules
- **Flexible Configuration**: YAML-based control without code changes

Named after the ROM construct from William Gibson's *Neuromancer*—preserved, structured knowledge.

## Quick Examples

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

### Reorder RDF Files

```bash
# Semantic ordering
poetry run rdf-construct order ontology.ttl order.yml

# Specific profile
poetry run rdf-construct order ontology.ttl order.yml -p logical_topo
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
