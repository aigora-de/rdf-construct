# CLI Reference

Complete command reference for rdf-construct.

## Installation

```bash
# With Poetry
cd rdf-construct
poetry install

# With pip
pip install rdf-construct

# From source
git clone https://github.com/aigora-de/rdf-construct.git
cd rdf-construct
pip install -e .
```

## Global Options

```bash
rdf-construct --version    # Show version
rdf-construct --help       # Show help
```

## Commands

### uml - Generate UML Diagrams

Generate PlantUML class diagrams from RDF ontologies.

```bash
poetry run rdf-construct uml SOURCE CONFIG [OPTIONS]
```

**Arguments**:
- `SOURCE`: Input RDF/Turtle file (.ttl)
- `CONFIG`: YAML configuration file defining contexts

**Options**:
- `-c, --context NAME`: Generate specific context(s) (can specify multiple)
- `-o, --outdir PATH`: Output directory (default: `diagrams`)
- `--style-config PATH`: Path to style configuration YAML
- `-s, --style NAME`: Style scheme name to use
- `--layout-config PATH`: Path to layout configuration YAML
- `-l, --layout NAME`: Layout name to use

**Examples**:

```bash
# Generate all contexts
poetry run rdf-construct uml ontology.ttl config.yml

# Specific context
poetry run rdf-construct uml ontology.ttl config.yml -c animal_taxonomy

# Multiple contexts
poetry run rdf-construct uml ontology.ttl config.yml -c context1 -c context2

# Custom output directory
poetry run rdf-construct uml ontology.ttl config.yml -o my-diagrams/

# With styling
poetry run rdf-construct uml ontology.ttl config.yml \
  --style-config examples/uml_styles.yml \
  --style default

# With styling and layout
poetry run rdf-construct uml ontology.ttl config.yml \
  --style-config examples/uml_styles.yml --style default \
  --layout-config examples/uml_layouts.yml --layout hierarchy

# Full example
poetry run rdf-construct uml examples/animal_ontology.ttl examples/uml_contexts.yml \
  -c animal_taxonomy \
  -o output/diagrams/ \
  --style-config examples/uml_styles.yml --style high_contrast \
  --layout-config examples/uml_layouts.yml --layout compact
```

**Output**:
- Creates `.puml` files in output directory
- One file per context: `SOURCE-CONTEXT.puml`
- Shows summary: number of classes, properties, instances

### contexts - List UML Contexts

List available UML contexts in a configuration file.

```bash
poetry run rdf-construct contexts CONFIG
```

**Arguments**:
- `CONFIG`: YAML configuration file to inspect

**Examples**:

```bash
# List contexts
poetry run rdf-construct contexts examples/uml_contexts.yml
```

**Output**:
```
Available UML contexts:

  animal_taxonomy
    Complete animal hierarchy
    Roots: ex:Animal
    Includes descendants (unlimited)
    Properties: domain_based

  mammals_only
    Mammal classes
    Roots: ex:Mammal
    Includes descendants (depth=2)
    Properties: domain_based

  ...
```

### order - Reorder RDF Files

Reorder RDF/Turtle files according to semantic profiles.

```bash
poetry run rdf-construct order SOURCE CONFIG [OPTIONS]
```

**Arguments**:
- `SOURCE`: Input RDF/Turtle file (.ttl)
- `CONFIG`: YAML configuration file defining ordering profiles

**Options**:
- `-p, --profile NAME`: Profile(s) to generate (can specify multiple)
- `-o, --outdir PATH`: Output directory (default: `src/ontology`)

**Examples**:

```bash
# Generate all profiles
poetry run rdf-construct order ontology.ttl order.yml

# Specific profiles
poetry run rdf-construct order ontology.ttl order.yml -p alpha -p logical_topo

# Multiple profiles
poetry run rdf-construct order ontology.ttl order.yml -p profile1 -p profile2

# Custom output directory
poetry run rdf-construct order ontology.ttl order.yml -o output/
```

**Output**:
- Creates ordered `.ttl` files in output directory
- One file per profile: `SOURCE-PROFILE.ttl`
- Preserves semantic ordering in output

### profiles - List Ordering Profiles

List available ordering profiles in a configuration file.

```bash
poetry run rdf-construct profiles CONFIG
```

**Arguments**:
- `CONFIG`: YAML configuration file to inspect

**Examples**:

```bash
# List profiles
poetry run rdf-construct profiles order.yml
```

**Output**:
```
Available profiles:

  alpha
    Alphabetical ordering - good for diffs
    Sections: 6

  logical_topo
    Parents before children - preserves hierarchy
    Sections: 6

  ...
```

## Configuration Files

### UML Context Configuration

**File**: `uml_contexts.yml`

```yaml
contexts:
  context_name:
    description: "Human-readable description"
    
    # Class selection (choose one)
    root_classes: [prefix:Class, ...]
    focus_classes: [prefix:Class, ...]
    selector: classes
    
    # Options
    include_descendants: true
    max_depth: 3
    
    # Properties
    properties:
      mode: domain_based  # or connected, explicit, all, none
      include: [prefix:property, ...]
      exclude: [prefix:property, ...]
    
    # Instances
    include_instances: false
```

### Style Configuration

**File**: `uml_styles.yml`

```yaml
schemes:
  scheme_name:
    description: "Visual theme description"
    
    # Class styling
    classes:
      by_namespace:
        prefix:
          border: "#0066CC"
          fill: "#E8F4F8"
          line_style: bold
      
      by_type:
        type_key:
          border: "#CC0000"
          fill: "#FFE6E6"
      
      default:
        border: "#000000"
        fill: "#FFFFFF"
    
    # Instance styling
    instances:
      border: "#000000"
      fill: "#000000"
      text: "#FFFFFF"
      inherit_class_border: true
    
    # Arrow styling
    arrows:
      subclass:
        color: "#0066CC"
        style: bold
      rdf_type:
        color: "#D32F2F"
        style: bold
    
    # Stereotypes
    show_stereotypes: true
    stereotype_map:
      owl:Class: "«class»"
      prefix:MetaClass: "«meta»"
```

### Layout Configuration

**File**: `uml_layouts.yml`

```yaml
layouts:
  layout_name:
    description: "Layout arrangement description"
    direction: top_to_bottom  # or left_to_right, etc.
    arrow_direction: up  # or down, left, right
    hide_empty_members: false
    group_by_namespace: false
    spacing:
      classMarginTop: 10
      classMarginBottom: 10
```

### Ordering Profile Configuration

**File**: `order.yml`

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

# Define ordering profiles
profiles:
  profile_name:
    description: "Human-readable description"
    sections:
      - header: {}
      - classes:
          select: classes
          sort: alpha  # or topological
          roots: [prefix:RootClass, ...]
      - object_properties:
          select: obj_props
          sort: topological
```

## Exit Codes

- `0`: Success
- `1`: General error
- `2`: Command line usage error

## Environment Variables

None currently used.

## Files and Directories

**Input Files**:
- `.ttl` - RDF/Turtle ontology files
- `.yml` - YAML configuration files

**Output Files**:
- `.puml` - PlantUML diagram files (from `uml` command)
- `.ttl` - Ordered RDF/Turtle files (from `order` command)

**Default Output Directories**:
- `diagrams/` - UML diagram output
- `src/ontology/` - Ordered RDF output

## Common Workflows

### Generate Documentation Diagrams

```bash
# Create multiple views of an ontology
poetry run rdf-construct uml ontology.ttl config.yml \
  -c overview \
  -c detailed \
  -c examples \
  -o docs/diagrams/ \
  --style-config styles.yml --style default \
  --layout-config layouts.yml --layout hierarchy
```

### Compare Ontology Versions

```bash
# Generate ordered versions
poetry run rdf-construct order v1.ttl order.yml -p canonical -o output/v1/
poetry run rdf-construct order v2.ttl order.yml -p canonical -o output/v2/

# Diff them
diff output/v1/v1-canonical.ttl output/v2/v2-canonical.ttl
```

### Generate Presentation Diagrams

```bash
# High contrast, large spacing
poetry run rdf-construct uml ontology.ttl config.yml \
  --style-config styles.yml --style high_contrast \
  --layout-config layouts.yml --layout presentation
```

### Generate Academic Paper Diagrams

```bash
# Grayscale, documentation layout
poetry run rdf-construct uml ontology.ttl config.yml \
  --style-config styles.yml --style grayscale \
  --layout-config layouts.yml --layout documentation
```

## Tips

### Check Configuration

Before generating, list available contexts/profiles:

```bash
poetry run rdf-construct contexts config.yml
poetry run rdf-construct profiles order.yml
```

### Start Simple

Generate without styling first:

```bash
poetry run rdf-construct uml ontology.ttl config.yml -c simple_context
```

Then add styling once you're happy with the structure.

### Use Descriptive Names

In YAML configs:
- **Good**: `animal_taxonomy`, `management_structure`, `key_relationships`
- **Bad**: `context1`, `test`, `temp`

### Organize Output

Use subdirectories for different versions or audiences:

```bash
poetry run rdf-construct uml ontology.ttl config.yml -o docs/diagrams/public/
poetry run rdf-construct uml ontology.ttl config.yml -o docs/diagrams/internal/
```

## Troubleshooting

### "Command not found"

**Problem**: `rdf-construct: command not found`

**Solution**:
```bash
# With poetry
poetry run rdf-construct --version

# Or activate poetry shell
poetry shell
rdf-construct --version
```

### "Context/Profile not found"

**Problem**: `Error: Context 'xyz' not found`

**Solution**: List available contexts/profiles:
```bash
poetry run rdf-construct contexts config.yml
poetry run rdf-construct profiles order.yml
```

### "File not found"

**Problem**: `Error: Path 'file.ttl' does not exist`

**Solution**: Check file path is correct:
```bash
ls -la file.ttl
# Use absolute path if needed
poetry run rdf-construct uml /full/path/to/file.ttl config.yml
```

### Empty Output

**Problem**: Generated file has no classes/properties.

**Solutions**:
1. Check CURIE format in config
2. Verify namespace prefixes match ontology
3. Check class/property selection criteria

**Debug**:
```python
from rdflib import Graph, RDF, OWL
g = Graph().parse("ontology.ttl", format="turtle")
print(f"Classes: {len(list(g.subjects(RDF.type, OWL.Class)))}")
for pfx, ns in g.namespace_manager.namespaces():
    if pfx: print(f"{pfx}: {ns}")
```

## Getting Help

```bash
# Command help
poetry run rdf-construct --help
poetry run rdf-construct uml --help
poetry run rdf-construct order --help

# Online resources
# - Issues: https://github.com/aigora-de/rdf-construct/issues
# - Discussions: https://github.com/aigora-de/rdf-construct/discussions
```

## See Also

- **[Getting Started](GETTING_STARTED.md)**: Quick start guide
- **[UML Guide](UML_GUIDE.md)**: Complete UML features
- **[Examples](../archive/examples/)**: Sample configurations