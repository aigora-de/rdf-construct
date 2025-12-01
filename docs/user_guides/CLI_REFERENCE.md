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

### lint - Check Ontology Quality

Check RDF ontologies for quality issues, structural problems, and best practice violations.

```bash
poetry run rdf-construct lint SOURCES [OPTIONS]
```

**Arguments**:
- `SOURCES`: One or more RDF files to check (.ttl, .rdf, .owl, etc.)

**Options**:
- `-l, --level LEVEL`: Strictness level: `strict`, `standard` (default), or `relaxed`
- `-f, --format FORMAT`: Output format: `text` (default) or `json`
- `-c, --config PATH`: Path to `.rdf-lint.yml` configuration file
- `-e, --enable RULE`: Enable specific rule (can specify multiple)
- `-d, --disable RULE`: Disable specific rule (can specify multiple)
- `--no-colour`: Disable coloured output
- `--list-rules`: List available rules and exit
- `--init`: Generate a default `.rdf-lint.yml` config file and exit

**Exit Codes**:
- `0`: No issues found
- `1`: Warnings found (no errors)
- `2`: Errors found

**Examples**:

```bash
# Basic usage
poetry run rdf-construct lint ontology.ttl

# Multiple files
poetry run rdf-construct lint core.ttl domain.ttl

# Strict mode (warnings become errors) - good for CI
poetry run rdf-construct lint ontology.ttl --level strict

# Relaxed mode (skip info-level rules)
poetry run rdf-construct lint ontology.ttl --level relaxed

# JSON output for tooling
poetry run rdf-construct lint ontology.ttl --format json

# Use config file
poetry run rdf-construct lint ontology.ttl --config .rdf-lint.yml

# Enable/disable specific rules
poetry run rdf-construct lint ontology.ttl \
  --enable orphan-class \
  --disable missing-comment \
  --disable inconsistent-naming

# List available rules
poetry run rdf-construct lint --list-rules

# Generate default config
poetry run rdf-construct lint --init
```

**Output**:
```
examples/ontology.ttl:42 info[redundant-subclass] ies:MyClass: Redundant subclass...
examples/ontology.ttl:156 warning[missing-label] ies:myProperty: Property lacks rdfs:label
examples/ontology.ttl:892 error[dangling-reference] ies:Feature: Referenced entity is not defined

Found 1 error, 1 warning, 1 info in 1 file
```

For full documentation, see **[Lint Guide](LINT_GUIDE.md)**.

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

### Lint Configuration

**File**: `.rdf-lint.yml`

```yaml
# Strictness level: strict | standard | relaxed
level: standard

# Enable only specific rules (empty = all rules)
enable:
  - orphan-class
  - missing-label

# Disable specific rules
disable:
  - inconsistent-naming

# Override severity for specific rules
severity:
  missing-comment: info
  property-no-domain: warning
```

**Available Rules**:

| Rule | Category | Default | Description |
|------|----------|---------|-------------|
| `orphan-class` | structural | error | Class has no superclass |
| `dangling-reference` | structural | error | Reference to undefined entity |
| `circular-subclass` | structural | error | Circular inheritance |
| `property-no-type` | structural | error | Property missing rdf:type |
| `empty-ontology` | structural | error | Ontology has no metadata |
| `missing-label` | documentation | warning | Entity lacks rdfs:label |
| `missing-comment` | documentation | warning | Entity lacks rdfs:comment |
| `redundant-subclass` | best-practice | info | Redundant inheritance |
| `property-no-domain` | best-practice | info | Property missing domain |
| `property-no-range` | best-practice | info | Property missing range |
| `inconsistent-naming` | best-practice | info | Naming convention violations |

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

| Code | Command | Meaning |
|------|---------|---------|
| `0` | All | Success / No issues |
| `1` | `lint` | Warnings found (no errors) |
| `1` | Others | General error |
| `2` | `lint` | Errors found |
| `2` | Others | Command line usage error |

## Environment Variables

None currently used.

## Files and Directories

**Input Files**:
- `.ttl` - RDF/Turtle ontology files
- `.yml` - YAML configuration files
- `.rdf-lint.yml` - Lint configuration (auto-discovered)

**Output Files**:
- `.puml` - PlantUML diagram files (from `uml` command)
- `.ttl` - Ordered RDF/Turtle files (from `order` command)

**Default Output Directories**:
- `diagrams/` - UML diagram output
- `src/ontology/` - Ordered RDF output

## Common Workflows

### CI/CD Ontology Validation

```bash
# Strict lint check - fail on any warning or error
poetry run rdf-construct lint ontology.ttl --level strict

# JSON output for parsing
poetry run rdf-construct lint ontology.ttl --format json > lint-results.json
```

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

### Pre-commit Ontology Check

```bash
# Quick lint before committing
poetry run rdf-construct lint ontology.ttl

# If errors, fix and re-run
poetry run rdf-construct lint ontology.ttl --level strict
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
poetry run rdf-construct lint --list-rules
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

### Configure Lint Rules Per Project

Create a `.rdf-lint.yml` in your project root:

```bash
# Generate default config
poetry run rdf-construct lint --init

# Edit to suit your project
# Then just run:
poetry run rdf-construct lint ontology.ttl
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

### Lint Finds Too Many Issues

**Problem**: Hundreds of `missing-label` or `missing-comment` warnings.

**Solutions**:
1. Use `--level relaxed` during early development
2. Disable specific rules: `--disable missing-comment`
3. Create a `.rdf-lint.yml` config to tune rules

### Lint Reports Dangling References for External Imports

**Problem**: References to imported ontologies flagged as dangling.

**Solution**: Load imported ontologies too:
```bash
poetry run rdf-construct lint domain.ttl foundation.ttl
```

## Getting Help

```bash
# Command help
poetry run rdf-construct --help
poetry run rdf-construct lint --help
poetry run rdf-construct uml --help
poetry run rdf-construct order --help

# Online resources
# - Issues: https://github.com/aigora-de/rdf-construct/issues
# - Discussions: https://github.com/aigora-de/rdf-construct/discussions
```

## See Also

- **[Getting Started](GETTING_STARTED.md)**: Quick start guide
- **[UML Guide](UML_GUIDE.md)**: Complete UML features
- **[Lint Guide](LINT_GUIDE.md)**: Ontology quality checking
- **[Examples](../archive/examples/)**: Sample configurations