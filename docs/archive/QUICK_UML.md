# Quick Start Guide

## Install & Run

```bash
# 1. Install dependencies
pip install rdflib pyyaml click

# 2. Set Python path
export PYTHONPATH=./src:$PYTHONPATH

# 3. Try it out
python -m rdf_construct.cli uml examples/animal_ontology.ttl examples/uml_contexts.yml
```

## What You Get

Generated `.puml` files in `diagrams/` directory, ready to render with PlantUML.

## Commands

```bash
# List available contexts
python -m rdf_construct.cli contexts examples/uml_contexts.yml

# Generate specific context
python -m rdf_construct.cli uml SOURCE.ttl CONFIG.yml -c CONTEXT_NAME

# Custom output directory
python -m rdf_construct.cli uml SOURCE.ttl CONFIG.yml -o my-diagrams/

# Generate all contexts
python -m rdf_construct.cli uml SOURCE.ttl CONFIG.yml
```

## Create Your Own Context

Edit `examples/uml_contexts.yml`:

```yaml
contexts:
  my_diagram:
    description: "My custom diagram"
    root_classes:
      - my:RootClass
    include_descendants: true
    properties:
      mode: domain_based
    include_instances: false
```

Then generate:
```bash
python -m rdf_construct.cli uml my_ontology.ttl examples/uml_contexts.yml -c my_diagram
```

## Property Selection Modes

- `domain_based` - Properties whose domain is in selected classes
- `connected` - Properties connecting selected classes  
- `explicit` - Only specified properties
- `all` - All properties
- `none` - No properties

## Examples Included

Try these:
```bash
# Animal taxonomy
python -m rdf_construct.cli uml examples/animal_ontology.ttl examples/uml_contexts.yml -c animal_taxonomy

# Management structure with people
python -m rdf_construct.cli uml examples/organisation_ontology.ttl examples/uml_contexts.yml -c management

# Full ontology
python -m rdf_construct.cli uml examples/animal_ontology.ttl examples/uml_contexts.yml -c full
```

## Troubleshooting

**Namespace conflicts**: If your ontology uses common prefixes like `org:`, check what rdflib assigns:
```python
from rdflib import Graph
g = Graph()
g.parse("your_ontology.ttl", format="turtle")
for pfx, ns in g.namespace_manager.namespaces():
    if pfx: print(f"{pfx}: {ns}")
```

Use the assigned prefix in your YAML config.

## Next Steps

See `UML_PIPELINE_SUMMARY.md` for full documentation and `EXAMPLES_SHOWCASE.md` for detailed examples.