# rdf-construct Documentation

## Quick Links

**New User?** → [Getting Started](user_guides/GETTING_STARTED.md)  
**Need Feature Details?** → [UML Guide](user_guides/UML_GUIDE.md)  
**Compare Ontologies?** → [Diff Guide](user_guides/DIFF_GUIDE.md)  
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

- **[UML Guide](user_guides/UML_GUIDE.md)** - Complete UML feature reference
  - Context configuration
  - Class selection strategies
  - Property filtering modes
  - Instance rendering
  - Styling and layout
  - Complete examples
  - Tips and techniques

- **[Diff Guide](user_guides/DIFF_GUIDE.md)** - Semantic ontology comparison
  - Comparing ontology versions
  - Output formats (text, markdown, JSON)
  - Filtering changes
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

- **Semantic Ordering**: Serialize RDF/Turtle with meaningful order (not alphabetical)
- **UML Generation**: Create PlantUML class diagrams from ontologies
- **Semantic Diff**: Compare ontologies and identify meaningful changes
- **Flexible Configuration**: YAML-based control without code changes

Named after the ROM construct from William Gibson's *Neuromancer*—preserved, structured knowledge.

## Quick Examples

### Generate UML Diagrams

```bash
# All contexts
poetry run rdf-construct uml ontology.ttl config.yml

# Specific context
poetry run rdf-construct uml ontology.ttl config.yml -c animal_taxonomy

# With styling and layout
poetry run rdf-construct uml ontology.ttl config.yml \
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

See [Refactoring Summary](REFACTORING_SUMMARY.md) for documentation reorganization details.

---

## Archive

Previous documentation versions are preserved in [docs/archive/](archive/) for reference.