# rdf-construct

> *"The ROM construct itself is a hardwired ROM cassette replicating a dead man's skills..."* — Neuromancer

A Python CLI toolkit for semantic RDF manipulation. Serialize RDF/Turtle with intelligent ordering instead of alphabetical chaos.

## Features

- **Semantic Ordering**: Order RDF subjects by hierarchy (topological), alphabetically, or custom profiles
- **Profile-Based**: Define multiple ordering strategies in YAML config
- **Deterministic Output**: Same input + profile = same output, always
- **Preserve Structure**: Respects `rdfs:subClassOf`, `rdfs:subPropertyOf` hierarchies
- **Root-Aware**: Organize by explicit root concepts with branches kept together
- Built on `rdflib` for robust RDF handling

## Installation

```bash
# From PyPI (once published)
pip install rdf-construct

# From source
git clone https://github.com/yourusername/rdf-construct.git
cd rdf-construct
pip install -e .
```

## Quick Start

```bash
# Order an ontology using all profiles in config
rdf-construct order ontology.ttl order.yml

# Generate specific profiles only
rdf-construct order ontology.ttl order.yml -p alpha -p logical_topo

# List available profiles
rdf-construct profiles order.yml

# Custom output directory
rdf-construct order ontology.ttl order.yml -o output/
```

## Configuration

Create a YAML file defining ordering profiles:

```yaml
prefix_order:
  - rdf
  - rdfs
  - owl
  - xsd

selectors:
  classes: "rdf:type owl:Class"
  obj_props: "rdf:type owl:ObjectProperty"

profiles:
  alpha:
    description: "Pure alphabetical ordering"
    sections:
      - header: {}
      - classes:
          select: classes
          sort: alpha
      - object_properties:
          select: obj_props
          sort: alpha
          
  logical_topo:
    description: "Parents before children"
    sections:
      - header: {}
      - classes:
          select: classes
          sort: topological
          roots: ["ies:Element", "ies:ClassOfElement"]
```

See [examples/sample_config.yml](examples/sample_profile.yml) for a complete example.

## Programmatic Use

```python
from rdf_construct import OrderingConfig, sort_subjects, serialize_turtle
from rdflib import Graph

# Load configuration
config = OrderingConfig("order.yml")
profile = config.get_profile("logical_topo")

# Load RDF graph
graph = Graph()
graph.parse("ontology.ttl", format="turtle")

# Process sections and build ordered output
ordered_subjects = []
# ... (see CLI implementation for full logic)

# Serialize with preserved order
serialize_turtle(graph, ordered_subjects, "output.ttl")
```

## Why?

RDFlib's built-in serializers always sort alphabetically, which:
- Obscures semantic structure
- Makes diffs noisy (unrelated changes mixed together)
- Loses author's intentional organization
- Makes large ontologies hard to navigate

**rdf-construct** preserves semantic meaning in serialization, making RDF files more maintainable.

## Roadmap

- [ ] RDF -> PlantUML
- [ ] Semantic diff tool
- [ ] RDF Changeset generation
- [ ] JSON-LD support
- [ ] N-Triples support
- [ ] Validation rules
- [ ] Graph visualization

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/
ruff check src/ tests/

# Type checking
mypy src/
```

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built on the excellent [rdflib](https://github.com/RDFLib/rdflib)
- Inspired by the need for better RDF tooling
- Named after the ROM construct from William Gibson's *Neuromancer*