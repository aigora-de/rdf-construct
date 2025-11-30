# rdf-construct Quick Reference

## Commands

```bash
# UML Diagrams
rdf-construct uml ONTOLOGY CONFIG [-c CONTEXT] [-o OUTDIR]
rdf-construct uml ONTOLOGY... CONFIG           # Multiple ontology files
rdf-construct contexts CONFIG                   # List available contexts

# RDF Ordering
rdf-construct order ONTOLOGY CONFIG [-p PROFILE] [-o OUTDIR]
rdf-construct profiles CONFIG                   # List available profiles

# Help
rdf-construct --help
rdf-construct uml --help
```

## UML Context Selection

| Strategy | Use When | Config |
|----------|----------|--------|
| Root classes | Full hierarchy from top | `root_classes: [ex:Root]` |
| Focus classes | Specific classes only | `focus_classes: [ex:A, ex:B]` |
| Explicit mode | Maximum control | `mode: explicit` |

## Property Modes

| Mode | Shows |
|------|-------|
| `domain_based` | Properties where domain ∈ selected classes |
| `connected` | Properties linking selected classes |
| `explicit` | Only listed properties |
| `all` | All properties in ontology |
| `none` | No properties |

## Sort Methods (Ordering)

| Sort | Order |
|------|-------|
| `alpha` | Alphabetical by QName |
| `topological` | Parents before children |
| `topological_then_alpha` | Hierarchy, then alphabetical |

## Common Patterns

### Basic Hierarchy Diagram
```yaml
contexts:
  my_diagram:
    root_classes: [ex:RootClass]
    include_descendants: true
    properties:
      mode: domain_based
```

### Explicit Selection
```yaml
contexts:
  custom:
    mode: explicit
    classes: [ex:A, ex:B]
    object_properties: [ex:hasRelation]
```

### With Styling
```bash
rdf-construct uml ontology.ttl contexts.yml \
  --style-config styles.yml --style default
```

### Hierarchical Ordering
```yaml
profiles:
  hierarchical:
    sections:
      - header: {}
      - classes:
          select: classes
          sort: topological
```

## Project Structure

```
my-project/
├── ontology/           # Source .ttl files
├── config/             # YAML configs
│   ├── uml_contexts.yml
│   └── ordering.yml
└── output/
    ├── diagrams/       # Generated .puml
    └── ordered/        # Reordered .ttl
```

## Check Ontology Prefixes

```python
from rdflib import Graph
g = Graph().parse("your.ttl")
for p, n in g.namespaces():
    if p: print(f"{p}: {n}")
```

## Render PlantUML

```bash
# Online
# Paste .puml content at https://www.plantuml.com/plantuml/

# VS Code
# Install PlantUML extension, press Alt+D

# Command line
plantuml diagrams/*.puml
```

## Links

- Docs: https://github.com/aigora-de/rdf-construct
- Issues: https://github.com/aigora-de/rdf-construct/issues