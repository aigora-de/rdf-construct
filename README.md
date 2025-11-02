# rdf-construct

> *"The ROM construct itself is a hardwired ROM cassette replicating a dead man's skills..."* — William Gibson, Neuromancer

**Semantic RDF manipulation toolkit** for ordering, serializing, and visualizing RDF ontologies.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Features

- ** Semantic Ordering**: Serialize RDF/Turtle with intelligent ordering instead of alphabetical chaos
- ** UML Generation**: Create PlantUML class diagrams from RDF ontologies
- ** Flexible Styling**: Configure colors, layouts, and visual themes for diagrams
- ** Profile-Based**: Define multiple ordering strategies in YAML configuration
- ** Deterministic**: Same input + profile = same output, always
- ** Hierarchy-Aware**: Respects `rdfs:subClassOf` and `rdfs:subPropertyOf` relationships

## Why?

RDFlib's built-in serializers always sort alphabetically, which:
- Obscures semantic structure
- Makes diffs noisy (unrelated changes mixed together)
- Loses author's intentional organization
- Makes large ontologies hard to navigate

**rdf-construct** preserves semantic meaning in serialization, making RDF files more maintainable.

## Quick Start

### Installation

```bash
# From source (for now)
git clone https://github.com/aigora-de/rdf-construct.git
cd rdf-construct
poetry install

# Coming soon: pip install rdf-construct
```

### Generate UML Diagrams

```bash
# Generate diagrams from an example ontology
poetry run rdf-construct uml examples/animal_ontology.ttl examples/uml_contexts.yml

# With styling and layout
poetry run rdf-construct uml examples/animal_ontology.ttl examples/uml_contexts.yml \
  --style-config examples/uml_styles.yml --style default \
  --layout-config examples/uml_layouts.yml --layout hierarchy
```

### Reorder RDF Files

```bash
# Order an ontology using all profiles
poetry run rdf-construct order ontology.ttl order_config.yml

# Generate specific profiles only
poetry run rdf-construct order ontology.ttl order_config.yml -p alpha -p logical_topo
```

## Documentation

📚 **[Complete Documentation](docs/index.md)** - Start here

**For Users**:
- [Getting Started](docs/user_guides/GETTING_STARTED.md) - 5-minute quick start
- [UML Guide](docs/user_guides/UML_GUIDE.md) - Complete UML features
- [CLI Reference](docs/user_guides/CLI_REFERENCE.md) - All commands and options

**For Developers**:
- [Architecture](docs/dev/ARCHITECTURE.md) - System design
- [UML Implementation](docs/dev/UML_IMPLEMENTATION.md) - Technical details
- [Contributing](CONTRIBUTING.md) - Development guide

**Additional**:
- [Code Index](CODE_INDEX.md) - Complete file inventory

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

## UML Diagram Generation

```yaml
# Define what to include in a diagram
contexts:
  animal_taxonomy:
    description: "Complete animal hierarchy"
    root_classes:
      - ex:Animal
    include_descendants: true
    properties:
      mode: domain_based
```

Generates PlantUML diagrams showing:
- Class hierarchies with inheritance arrows
- Properties as attributes or associations
- Instances as objects
- Configurable colors and layouts

## Features in Detail

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

**Root-Based Ordering**: Organize by explicit hierarchy
```yaml
sections:
  - classes:
      sort: topological
      roots: 
        - ex:Mammal
        - ex:Bird
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

### Styling and Layout

**Visual Themes**:
- `default` - Professional blue scheme
- `high_contrast` - Bold colors for presentations
- `grayscale` - Black and white for academic papers
- `minimal` - Bare-bones for debugging

**Layout Control**:
- Direction (top-to-bottom, left-to-right)
- Arrow hints for hierarchy
- Spacing and grouping

## Project Status

**Current**: Alpha - UML generation phase complete  
**Next**: Semantic diff, validation, multi-format support  
**License**: MIT

### Completed
✅ RDF semantic ordering  
✅ Topological sorting with root-based branches  
✅ Custom Turtle serialization (preserves order)  
✅ UML diagram generation from RDF  
✅ Configurable styling and layouts  
✅ Comprehensive documentation

### Planned
- [ ] Semantic diff (compare RDF graphs, generate changesets)
- [ ] Validation module (check for common ontology issues)
- [ ] Multi-format support (JSON-LD, RDF/XML input)
- [ ] Streaming mode for very large graphs
- [ ] Web UI for diagram configuration

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

**Development**:
- black, ruff, mypy
- pytest, pytest-cov
- pre-commit

## Inspiration

Named after the **ROM construct** from William Gibson's *Neuromancer*—preserved, structured knowledge that can be queried and transformed.

The project aims to preserve the semantic structure of RDF ontologies in serialized form, making them as readable and maintainable as the author intended.

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

**Status**: 🚧 Alpha - Active Development  
**Python**: 3.10+ required  
**Maintainer**: See [CONTRIBUTING.md](CONTRIBUTING.md)