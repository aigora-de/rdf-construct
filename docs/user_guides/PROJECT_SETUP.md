# Project Setup Guide

This guide explains how to set up rdf-construct in your own project.

## Recommended Directory Structure

When using rdf-construct as a pip-installed package, organise your project like this:

```
my-ontology-project/
├── ontology/                     # Your source ontologies
│   ├── my_ontology.ttl
│   └── imported_ontology.ttl
│
├── config/                       # rdf-construct configuration
│   ├── uml_contexts.yml         # UML diagram definitions
│   ├── uml_styles.yml           # Visual styling (optional)
│   ├── uml_layouts.yml          # Layout options (optional)
│   └── ordering_profiles.yml    # RDF ordering profiles
│
├── output/                       # Generated outputs
│   ├── diagrams/                # Generated .puml files
│   └── ordered/                 # Reordered .ttl files
│
├── docs/                        # Rendered diagrams for documentation
│   └── images/                  # .png/.svg rendered from .puml
│
└── README.md
```

This structure keeps source files, configuration, and outputs clearly separated.

## Installation

```bash
# Install from PyPI
pip install rdf-construct

# Or with poetry
poetry add rdf-construct

# Verify installation
rdf-construct --version
```

## Getting Started

### 1. Create Configuration Directory

```bash
mkdir -p config output/diagrams output/ordered
```

### 2. Download Starter Templates

Copy the starter templates from the rdf-construct repository:

```bash
# From GitHub (recommended)
curl -o config/uml_contexts.yml \
  https://raw.githubusercontent.com/aigora-de/rdf-construct/main/templates/uml_contexts_starter.yml

curl -o config/ordering_profiles.yml \
  https://raw.githubusercontent.com/aigora-de/rdf-construct/main/templates/ordering_starter.yml

# Optional styling
curl -o config/uml_styles.yml \
  https://raw.githubusercontent.com/aigora-de/rdf-construct/main/templates/uml_styles_starter.yml
```

Or copy from the examples directory if you cloned the repo:

```bash
cp /path/to/rdf-construct/templates/*.yml config/
```

### 3. Customise Templates

Edit the starter templates to match your ontology:

**Check your ontology's prefixes first:**

```python
from rdflib import Graph
g = Graph().parse("ontology/my_ontology.ttl")
for prefix, namespace in g.namespaces():
    if prefix:
        print(f"{prefix}: {namespace}")
```

**Update `config/uml_contexts.yml`:**

```yaml
prefixes:
  myont: "http://my-organisation.org/ontology#"

contexts:
  main_hierarchy:
    root_classes:
      - myont:TopLevelConcept    # Your actual root class
    include_descendants: true
    properties:
      mode: domain_based
```

### 4. Generate Diagrams

```bash
# Generate all UML diagrams
rdf-construct uml ontology/my_ontology.ttl config/uml_contexts.yml \
  -o output/diagrams

# Generate specific context only
rdf-construct uml ontology/my_ontology.ttl config/uml_contexts.yml \
  -c main_hierarchy -o output/diagrams
```

### 5. Reorder Ontology Files

```bash
# Generate hierarchically-ordered version
rdf-construct order ontology/my_ontology.ttl config/ordering_profiles.yml \
  -p hierarchical -o output/ordered
```

## Configuration File Reference

### UML Contexts (`uml_contexts.yml`)

Defines what appears in each diagram:

| Key | Purpose | Example |
|-----|---------|---------|
| `prefixes` | Namespace mappings | `ex: "http://example.org/"` |
| `contexts.{name}.root_classes` | Starting points for hierarchy | `[ex:Animal]` |
| `contexts.{name}.focus_classes` | Specific classes to include | `[ex:Dog, ex:Cat]` |
| `contexts.{name}.mode` | Selection mode | `explicit` |
| `contexts.{name}.properties.mode` | Property inclusion | `domain_based` |

### Ordering Profiles (`ordering_profiles.yml`)

Defines how to reorder RDF files:

| Key | Purpose | Example |
|-----|---------|---------|
| `prefix_order` | Order of @prefix declarations | `[rdf, rdfs, owl]` |
| `selectors` | Entity type definitions | `classes: [owl:Class]` |
| `profiles.{name}.sections` | Ordered sections | `[header, classes, ...]` |
| `profiles.{name}.sections.{type}.sort` | Sort method | `topological` or `alpha` |

### UML Styles (`uml_styles.yml`)

Defines visual appearance:

| Key | Purpose | Example |
|-----|---------|---------|
| `schemes.{name}.classes.by_namespace` | Per-namespace styling | `ex: {border: "#336699"}` |
| `schemes.{name}.instances` | Individual styling | `{fill: "#333333"}` |
| `schemes.{name}.arrows` | Relationship styling | `{color: "#666666"}` |

## Multiple Ontologies

If your domain ontology imports a foundational ontology, load both:

```bash
# Load multiple source files
rdf-construct uml \
  ontology/foundation.ttl \
  ontology/my_domain.ttl \
  config/uml_contexts.yml \
  -o output/diagrams
```

This ensures styling and selection work correctly across imported concepts.

## Workflow Integration

### With Make

```makefile
ONTOLOGY = ontology/my_ontology.ttl
UML_CONFIG = config/uml_contexts.yml
ORDER_CONFIG = config/ordering_profiles.yml

diagrams: $(ONTOLOGY) $(UML_CONFIG)
	rdf-construct uml $< $(UML_CONFIG) -o output/diagrams

ordered: $(ONTOLOGY) $(ORDER_CONFIG)
	rdf-construct order $< $(ORDER_CONFIG) -o output/ordered

.PHONY: diagrams ordered
```

### With Poetry Scripts

Add to `pyproject.toml`:

```toml
[tool.poetry.scripts]
diagrams = "scripts:generate_diagrams"
```

### In CI/CD

```yaml
# .github/workflows/diagrams.yml
- name: Generate diagrams
  run: |
    pip install rdf-construct
    rdf-construct uml ontology/*.ttl config/uml_contexts.yml -o docs/diagrams
```

## Troubleshooting

### "Prefix not found"

Check that prefix in config matches what rdflib assigned:

```python
from rdflib import Graph
g = Graph().parse("your.ttl")
for p, n in g.namespaces():
    print(f"{p}: {n}")
```

### Empty diagram output

1. Check class URIs are correct (use full URIs or matching prefixes)
2. Verify `root_classes` or `focus_classes` exist in ontology
3. Try `rdf-construct contexts config.yml` to validate config

### Classes missing from hierarchy

If using multiple ontology files, ensure all are loaded:

```bash
rdf-construct uml foundation.ttl domain.ttl config.yml
```

## Next Steps

- **[UML Guide](UML_GUIDE.md)** - Complete feature documentation
- **[CLI Reference](CLI_REFERENCE.md)** - All commands and options
- **[IES Colour Guide](IES_COLOUR_PALETTE_GUIDE.md)** - IES-specific styling

## Questions?

- **Issues**: https://github.com/aigora-de/rdf-construct/issues
- **Discussions**: https://github.com/aigora-de/rdf-construct/discussions