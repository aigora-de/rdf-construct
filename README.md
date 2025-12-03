# rdf-construct

> *"The ROM construct itself is a hardwired ROM cassette replicating a dead man's skills..."* — William Gibson, Neuromancer

**Semantic RDF manipulation toolkit** for ordering, documenting, validating, comparing, and visualising RDF ontologies.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/rdf-construct.svg)](https://pypi.org/project/rdf-construct/)
[![Downloads](https://pepy.tech/badge/rdf-construct)](https://pepy.tech/project/rdf-construct)

## Features

- **Semantic Ordering**: Serialise RDF/Turtle with intelligent ordering instead of alphabetical chaos
- **Documentation Generation**: Create navigable HTML, Markdown, or JSON documentation from ontologies
- **UML Generation**: Create PlantUML class diagrams from RDF ontologies
- **PUML2RDF**: Convert PlantUML diagrams to RDF/OWL ontologies (diagram-first design)
- **SHACL Generation**: Generate SHACL validation shapes from OWL definitions
- **Semantic Diff**: Compare ontology versions and identify meaningful changes
- **Ontology Linting**: Check quality with 11 configurable rules
- **Competency Question Testing**: Validate ontologies against SPARQL-based tests
- **Ontology Statistics**: Comprehensive metrics with comparison mode
- **Flexible Styling**: Configure colours, layouts, and visual themes for diagrams
- **Profile-Based**: Define multiple strategies in YAML configuration
- **Deterministic**: Same input + profile = same output, always

## Why?

RDFlib's built-in serialisers always sort alphabetically, which:
- Obscures semantic structure
- Makes diffs noisy (unrelated changes mixed together)
- Loses author's intentional organisation
- Makes large ontologies hard to navigate

**rdf-construct** preserves semantic meaning in serialisation, making RDF files more maintainable.

## Quick Start

### Installation

```bash
# From PyPI (recommended)
pip install rdf-construct

# From source
git clone https://github.com/aigora-de/rdf-construct.git
cd rdf-construct
pip install -e .

# For development
poetry install
```

### Compare Ontology Versions

```bash
# Basic comparison
rdf-construct diff v1.0.ttl v1.1.ttl

# Generate markdown changelog
rdf-construct diff v1.0.ttl v1.1.ttl --format markdown -o CHANGELOG.md

# JSON output for CI/scripting
rdf-construct diff old.ttl new.ttl --format json
```

### Generate Documentation

```bash
# HTML documentation with search
rdf-construct docs ontology.ttl -o api-docs/

# Markdown for GitHub wiki
rdf-construct docs ontology.ttl --format markdown

# JSON for custom rendering
rdf-construct docs ontology.ttl --format json
```

### Generate UML Diagrams

```bash
# Generate diagrams from an example ontology
rdf-construct uml examples/animal_ontology.ttl -C examples/uml_contexts.yml

# With styling and layout
rdf-construct uml examples/animal_ontology.ttl -C examples/uml_contexts.yml \
  --style-config examples/uml_styles.yml --style default \
  --layout-config examples/uml_layouts.yml --layout hierarchy
```

### Reorder RDF Files

```bash
# Order an ontology using all profiles
rdf-construct order ontology.ttl order_config.yml

# Generate specific profiles only
rdf-construct order ontology.ttl order_config.yml -p alpha -p logical_topo
```

### Check Ontology Quality

```bash
# Run all lint rules
rdf-construct lint ontology.ttl

# Strict checking for CI
rdf-construct lint ontology.ttl --level strict --format json
```

### Run Competency Question Tests

```bash
# Run tests
rdf-construct cq-test ontology.ttl tests.yml

# JUnit output for CI
rdf-construct cq-test ontology.ttl tests.yml --format junit -o results.xml
```

### Generate SHACL Shapes

```bash
# Basic generation
rdf-construct shacl-gen ontology.ttl -o shapes.ttl

# Strict mode with closed shapes
rdf-construct shacl-gen ontology.ttl --level strict --closed
```

### Ontology Statistics

```bash
# Display statistics
rdf-construct stats ontology.ttl

# Compare two versions
rdf-construct stats v1.ttl v2.ttl --compare --format markdown
```

## Documentation

📚 **[Complete Documentation](docs/index.md)** - Start here

**For Users**:
- [Getting Started](docs/user_guides/GETTING_STARTED.md) - 5-minute quick start
- [Docs Guide](docs/user_guides/DOCS_GUIDE.md) - Documentation generation
- [UML Guide](docs/user_guides/UML_GUIDE.md) - Complete UML features
- [PlantUML Import Guide](docs/user_guides/PLANTUML_IMPORT_GUIDE.md) - Diagram-first design
- [SHACL Guide](docs/user_guides/SHACL_GUIDE.md) - SHACL shape generation
- [Diff Guide](docs/user_guides/DIFF_GUIDE.md) - Semantic ontology comparison
- [Lint Guide](docs/user_guides/LINT_GUIDE.md) - Ontology quality checking
- [CQ Testing Guide](docs/user_guides/CQ_TEST_GUIDE.md) - Competency question testing
- [Stats Guide](docs/user_guides/STATS_GUIDE.md) - Ontology metrics
- [CLI Reference](docs/user_guides/CLI_REFERENCE.md) - All commands and options

**For Developers**:
- [Architecture](docs/dev/ARCHITECTURE.md) - System design
- [UML Implementation](docs/dev/UML_IMPLEMENTATION.md) - Technical details
- [Contributing](CONTRIBUTING.md) - Development guide

**Additional**:
- [Code Index](CODE_INDEX.md) - Complete file inventory
- [Quick Reference](docs/user_guides/QUICK_REFERENCE.md) - Cheat sheet

## Example

### Input (Alphabetically Ordered - Hard to Read)

```turtle
ex:Bird rdfs:subClassOf ex:Animal .
ex:Cat rdfs:subClassOf ex:Mammal .
ex:Dog rdfs:subClassOf ex:Mammal .
ex:Eagle rdfs:subClassOf ex:Bird .
ex:Mammal rdfs:subClassOf ex:Animal .
ex:Sparrow rdfs:subClassOf ex:Bird .
```

### Output (Semantically Ordered - Easy to Understand)

```turtle
# Root class first
ex:Animal a owl:Class .

# Then its direct subclasses
ex:Mammal rdfs:subClassOf ex:Animal .
ex:Bird rdfs:subClassOf ex:Animal .

# Then their subclasses
ex:Dog rdfs:subClassOf ex:Mammal .
ex:Cat rdfs:subClassOf ex:Mammal .

ex:Eagle rdfs:subClassOf ex:Bird .
ex:Sparrow rdfs:subClassOf ex:Bird .
```

## Semantic Diff

Compare ontology versions and see what actually changed:

```bash
$ rdf-construct diff v1.0.ttl v1.1.ttl

Comparing v1.0.ttl → v1.1.ttl

ADDED (2 entities):
  + Class ex:SmartBuilding (subclass of ex:Building)
  + DataProperty ex:energyRating

REMOVED (1 entity):
  - Class ex:DeprecatedStructure

MODIFIED (1 entity):
  ~ Class ex:Building
    + rdfs:comment "A constructed physical structure."@en

Summary: 2 added, 1 removed, 1 modified
```

Unlike text-based `diff`, semantic diff ignores:
- Statement reordering
- Prefix rebinding (`ex:` → `example:`)
- Whitespace and formatting changes

## Complete Toolkit

### Semantic Ordering

**Topological Sort**: Parents before children using Kahn's algorithm
```yaml
profiles:
  logical_topo:
    sections:
      - classes:
          sort: topological
          roots: ["ies:Element"]
```

**Root-Based Ordering**: Organise by explicit hierarchy
```yaml
sections:
  - classes:
      sort: topological
      roots:
        - ex:Mammal
        - ex:Bird
```

### Documentation Generation

Generate professional documentation in multiple formats:

```bash
# HTML with search, navigation, and cross-references
rdf-construct docs ontology.ttl -o docs/

# Markdown for GitHub/GitLab wikis
rdf-construct docs ontology.ttl --format markdown

# JSON for custom rendering
rdf-construct docs ontology.ttl --format json
```

### UML Context System

**Root Classes Strategy**: Start from specific concepts
```yaml
animal_taxonomy:
  root_classes: [ex:Animal]
  include_descendants: true
```

**Focus Classes Strategy**: Hand-pick classes
```yaml
key_concepts:
  focus_classes: [ex:Dog, ex:Cat, ex:Eagle]
```

**Property Filtering**: Control what relationships show
```yaml
properties:
  mode: domain_based  # or connected, explicit, all, none
```

### Quality Checking

11 built-in lint rules across three categories:

| Category | Rules |
|----------|-------|
| Structural | orphan-class, dangling-reference, circular-subclass, property-no-type, empty-ontology |
| Documentation | missing-label, missing-comment |
| Best Practice | redundant-subclass, property-no-domain, property-no-range, inconsistent-naming |

### Styling and Layout

**Visual Themes**:
- `default` - Professional blue scheme
- `high_contrast` - Bold colours for presentations
- `grayscale` - Black and white for academic papers
- `minimal` - Bare-bones for debugging

**Layout Control**:
- Direction (top-to-bottom, left-to-right)
- Arrow hints for hierarchy
- Spacing and grouping

## Project Status

**Current**: v0.2.0 - Feature complete for core ontology workflows  
**License**: MIT

### Implemented
✅ RDF semantic ordering  
✅ Topological sorting with root-based branches  
✅ Custom Turtle serialisation (preserves order)  
✅ PlantUML diagram generation from RDF  
✅ PlantUML to RDF conversion  
✅ Configurable styling and layouts  
✅ Semantic diff (compare ontology versions)  
✅ Documentation generation (HTML, Markdown, JSON)  
✅ SHACL shape generation  
✅ Ontology linting (11 rules)  
✅ Competency question testing  
✅ Ontology statistics  
✅ Comprehensive documentation

### (Possible) Roadmap
- [ ] Multi-format input support (JSON-LD, RDF/XML)
- [ ] Streaming mode for very large graphs
- [ ] Web UI for diagram configuration
- [ ] Additional lint rules

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Setup development environment
git clone https://github.com/aigora-de/rdf-construct.git
cd rdf-construct
poetry install
pre-commit install

# Run tests
pytest

# Format and lint
black src/ tests/
ruff check src/ tests/
```

## Dependencies

**Runtime**:
- Python 3.10+
- rdflib >= 7.0.0
- click >= 8.1.0
- pyyaml >= 6.0
- rich >= 13.0.0
- jinja2 >= 3.1.0

**Development**:
- black, ruff, mypy
- pytest, pytest-cov
- pre-commit

## Inspiration

Named after the **ROM construct** from William Gibson's *Neuromancer*—preserved, structured knowledge that can be queried and transformed.

The project aims to preserve the semantic structure of RDF ontologies in serialised form, making them as readable and maintainable as the author intended.

## Credits

Built on the excellent [rdflib](https://github.com/RDFLib/rdflib) library.

Influenced by the need for better RDF tooling in ontology engineering and the [IES (Information Exchange Standard)](http://informationexchangestandard.org/) work.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Links

- **Documentation**: [docs/index.md](docs/index.md)
- **Issues**: https://github.com/aigora-de/rdf-construct/issues
- **Discussions**: https://github.com/aigora-de/rdf-construct/discussions

---

**Status**: v0.2.0  
**Python**: 3.10+ required  
**Maintainer**: See [CONTRIBUTING.md](CONTRIBUTING.md)