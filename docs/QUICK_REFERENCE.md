# rdf-construct Quick Reference

## Installation

```bash
cd /home/claude
pip install -e .                 # Install package
pip install -e ".[dev]"          # Install with dev dependencies
```

## CLI Commands

```bash
# Order ontology with all profiles
rdf-construct order ontology.ttl order.yml

# Specific profiles only
rdf-construct order ontology.ttl order.yml -p alpha -p logical_topo

# Custom output directory
rdf-construct order ontology.ttl order.yml -o output/

# List profiles in config
rdf-construct profiles order.yml

# Get help
rdf-construct --help
rdf-construct order --help
```

## Python API

```python
from rdf_construct import OrderingConfig, serialize_turtle
from rdflib import Graph

# Load config
config = OrderingConfig("order.yml")
profile = config.get_profile("logical_topo")

# Parse RDF
graph = Graph()
graph.parse("ontology.ttl", format="turtle")

# ... process sections (see full example in REFACTORING_SUMMARY.md)

# Serialize with preserved order
serialize_turtle(graph, ordered_subjects, "output.ttl")
```

## Module Reference

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `core/config.py` | `load_ordering_spec()` | YAML loading, configs |
| `core/profile.py` | `OrderingConfig`, `OrderingProfile` | Profile management |
| `core/selector.py` | `select_subjects()` | Find classes/properties/individuals |
| `core/ordering.py` | `sort_subjects()`, `topo_sort_subset()` | Topological sorting |
| `core/serializer.py` | `serialize_turtle()` | Custom Turtle writer |
| `core/utils.py` | `expand_curie()`, `qname_sort_key()` | Utilities |

## YAML Config Structure

```yaml
# Optional: control prefix ordering
prefix_order:
  - rdf
  - rdfs
  - owl

# Define subject selectors
selectors:
  classes: "rdf:type owl:Class"
  obj_props: "rdf:type owl:ObjectProperty"
  data_props: "rdf:type owl:DatatypeProperty"
  ann_props: "rdf:type owl:AnnotationProperty"
  individuals: "FILTER NOT EXISTS ..."

# Define ordering profiles
profiles:
  profile_name:
    description: "Human-readable description"
    sections:
      - header: {}                    # owl:Ontology metadata
      - classes:
          select: classes             # Use selector
          sort: alpha                 # or topological
          roots: ["ies:Element"]      # Optional: root concepts
      - object_properties:
          select: obj_props
          sort: topological
```

## Sort Modes

- `alpha` or `qname_alpha` - Alphabetical by QName
- `topological` or `topological_then_alpha` - Parents before children

## Common Workflows

### Create New Profile

1. Edit `order.yml`:
```yaml
profiles:
  my_profile:
    description: "My custom ordering"
    sections:
      - header: {}
      - classes:
          select: classes
          sort: topological
```

2. Generate:
```bash
rdf-construct order ontology.ttl order.yml -p my_profile
```

### Compare Profiles

```bash
# Generate both
rdf-construct order ontology.ttl order.yml -p alpha -p logical_topo

# Diff them
diff ontology-alpha.ttl ontology-logical_topo.ttl
```

### Validate Config

```bash
# List profiles (validates YAML)
rdf-construct profiles order.yml
```

## Development Commands

```bash
# Run tests
pytest
pytest --cov=rdf_construct --cov-report=html

# Format code
black src/ tests/

# Lint
ruff check src/ tests/
ruff check --fix src/ tests/

# Type check
mypy src/

# Install pre-commit hooks
pre-commit install
pre-commit run --all-files
```

## Troubleshooting

### Import Error
```python
# Error: No module named 'rdf_construct'
# Solution: Install package
pip install -e .
```

### Profile Not Found
```bash
# Error: Profile 'xyz' not found
# Solution: List available profiles
rdf-construct profiles order.yml
```

### Empty Output
- Check selector definitions in YAML
- Verify ontology has matching types (owl:Class, owl:ObjectProperty, etc.)
- Try `sort: alpha` first to debug

### Wrong Order
- Verify `sort: topological` is used
- Check `roots` list has correct CURIEs
- Inspect prefix bindings in source RDF

## Examples Location

- `/home/claude/examples/basic_ordering.py` - Programmatic usage
- `/home/claude/examples/sample_config.yml` - Complete YAML example

## File Locations

- **Source code**: `/home/claude/src/rdf_construct/`
- **Tests**: `/home/claude/tests/`
- **Config**: `/home/claude/pyproject.toml`
- **Original script**: `/mnt/project/order_turtle.py` (reference only)

## Project Files

The original files from your project are still available:
- `/mnt/project/order_turtle.py` - Original monolithic script
- `/mnt/project/ontology_order.yml` - Example YAML config
- `/mnt/project/project-dev.md` - Development instructions

## Status Check

```bash
# Verify installation
rdf-construct --version

# Run a simple test
rdf-construct profiles /mnt/project/ontology_order.yml

# Test ordering (requires an ontology file)
# rdf-construct order your_ontology.ttl /mnt/project/ontology_order.yml -p alpha
```

## Next Steps

1. **Implement missing features**: `group_by`, `anchors` in YAML
2. **Add Rich output**: Use the installed Rich library for colored CLI
3. **Expand tests**: Increase coverage beyond basic cases
4. **Documentation**: Set up MkDocs site
5. **Publish**: Update URLs in pyproject.toml and publish to PyPI

## Getting Help

- Check docstrings: `python -c "from rdf_construct import OrderingConfig; help(OrderingConfig)"`
- Read README: `/home/claude/README.md`
- See examples: `/home/claude/examples/`
- Review code: All modules have comprehensive docstrings