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

### docs - Generate Documentation

Generate HTML, Markdown, or JSON documentation from RDF ontologies.

```bash
rdf-construct docs SOURCE [OPTIONS]
```

**Arguments**:
- `SOURCE`: Input RDF ontology file (.ttl, .rdf, .owl, etc.)

**Options**:
- `-o, --output PATH`: Output directory (default: `docs-output`)
- `-f, --format FORMAT`: Output format: `html`, `markdown`, `md`, `json` (default: html)
- `-C, --config PATH`: YAML configuration file
- `--template PATH`: Path to custom Jinja2 templates directory
- `--title TEXT`: Documentation title (default: from ontology or filename)
- `--no-search`: Disable search index generation (HTML only)
- `--no-hierarchy`: Don't generate class hierarchy pages
- `--include-imports`: Include imported ontology entities

**Examples**:

```bash
# Generate HTML documentation
rdf-construct docs ontology.ttl -o api-docs/

# Generate Markdown for GitHub wiki
rdf-construct docs ontology.ttl --format markdown -o wiki/

# Generate JSON for custom rendering
rdf-construct docs ontology.ttl --format json -o data/

# With custom title
rdf-construct docs ontology.ttl --title "My Ontology API" -o docs/

# Use custom templates
rdf-construct docs ontology.ttl --template my-templates/ -o docs/
```

**Output**:
- HTML: Complete website with navigation, search, and styling
- Markdown: Individual `.md` files per class/property
- JSON: Structured data for programmatic use

---

### uml - Generate UML Diagrams

Generate PlantUML class diagrams from RDF ontologies.

```bash
rdf-construct uml SOURCE [SOURCE...] -C CONFIG [OPTIONS]
```

**Arguments**:
- `SOURCE`: One or more RDF files (.ttl, .rdf, .owl). First file is primary; additional files provide supporting definitions.
- `-C, --config`: YAML configuration file defining contexts (required)

**Options**:
- `-c, --context NAME`: Generate specific context(s) (can specify multiple)
- `-o, --outdir PATH`: Output directory (default: `diagrams`)
- `--style-config PATH`: Path to style configuration YAML
- `-s, --style NAME`: Style scheme name to use
- `--layout-config PATH`: Path to layout configuration YAML
- `-l, --layout NAME`: Layout name to use
- `-r, --rendering-mode`: Rendering mode: `default` or `odm` (OMG ODM RDF Profile)

**Examples**:

```bash
# Generate all contexts
rdf-construct uml ontology.ttl -C config.yml

# Specific context
rdf-construct uml ontology.ttl -C config.yml -c animal_taxonomy

# Multiple sources (primary + imports)
rdf-construct uml domain.ttl imports/core.ttl -C config.yml

# With styling and layout
rdf-construct uml ontology.ttl -C config.yml \
  --style-config styles.yml --style default \
  --layout-config layouts.yml --layout hierarchy

# ODM-compliant rendering
rdf-construct uml ontology.ttl -C config.yml --rendering-mode odm
```

**Output**:
- Creates `.puml` files in output directory
- One file per context: `SOURCE-CONTEXT.puml`
- Shows summary: number of classes, properties, instances

---

### shacl-gen - Generate SHACL Shapes

Generate SHACL validation shapes from OWL ontology definitions.

```bash
rdf-construct shacl-gen SOURCE [OPTIONS]
```

**Arguments**:
- `SOURCE`: Input RDF ontology file (.ttl, .rdf, .owl, etc.)

**Options**:
- `-o, --output PATH`: Output file path (default: `<source>-shapes.ttl`)
- `-f, --format FORMAT`: Output format: `turtle`, `ttl`, `json-ld`, `jsonld` (default: turtle)
- `-l, --level LEVEL`: Strictness level: `minimal`, `standard`, `strict` (default: standard)
- `-C, --config PATH`: YAML configuration file
- `--classes LIST`: Comma-separated list of classes to generate shapes for
- `--closed`: Generate closed shapes (no extra properties allowed)
- `--default-severity LEVEL`: Default severity: `violation`, `warning`, `info`
- `--no-labels`: Don't include rdfs:label as sh:name
- `--no-descriptions`: Don't include rdfs:comment as sh:description
- `--no-inherit`: Don't inherit constraints from superclasses

**Strictness Levels**:
- `minimal`: Basic type constraints only (sh:class, sh:datatype)
- `standard`: Adds cardinality and functional property constraints
- `strict`: Maximum constraints including enumerations, closed shapes

**Examples**:

```bash
# Basic generation
rdf-construct shacl-gen ontology.ttl

# Generate with strict constraints
rdf-construct shacl-gen ontology.ttl --level strict --closed

# Custom output path and format
rdf-construct shacl-gen ontology.ttl -o shapes.ttl --format turtle

# Focus on specific classes
rdf-construct shacl-gen ontology.ttl --classes "ex:Building,ex:Floor"

# Use configuration file
rdf-construct shacl-gen ontology.ttl --config shacl-config.yml

# Generate warnings instead of violations
rdf-construct shacl-gen ontology.ttl --default-severity warning
```

**Output**:
- Creates SHACL shapes file with NodeShapes for each class
- Converts domain/range to sh:property constraints
- Converts cardinality restrictions to sh:minCount/sh:maxCount
- Converts functional properties to sh:maxCount 1

---

### diff - Compare RDF Files

Compare two RDF files and show semantic differences.

```bash
rdf-construct diff OLD_FILE NEW_FILE [OPTIONS]
```

**Arguments**:
- `OLD_FILE`: Original RDF file
- `NEW_FILE`: Updated RDF file

**Options**:
- `-o, --output PATH`: Write output to file instead of stdout
- `-f, --format FORMAT`: Output format: `text`, `markdown`, `md`, `json` (default: text)
- `--show TYPES`: Show only these change types (comma-separated: added,removed,modified)
- `--hide TYPES`: Hide these change types
- `--entities TYPES`: Show only these entity types (comma-separated: classes,properties,instances)
- `--ignore-predicates LIST`: Ignore these predicates in comparison (comma-separated CURIEs)

**Examples**:

```bash
# Basic comparison
rdf-construct diff v1.0.ttl v1.1.ttl

# Generate markdown changelog
rdf-construct diff v1.0.ttl v1.1.ttl --format markdown -o CHANGELOG.md

# Show only added and removed (hide modified)
rdf-construct diff old.ttl new.ttl --show added,removed

# Focus on class changes only
rdf-construct diff old.ttl new.ttl --entities classes

# Ignore timestamp predicates
rdf-construct diff old.ttl new.ttl --ignore-predicates dcterms:modified
```

**Exit Codes**:
- `0`: Graphs are semantically identical
- `1`: Differences were found
- `2`: Error occurred

---

### lint - Check Ontology Quality

Run quality checks on RDF ontologies.

```bash
rdf-construct lint SOURCE [OPTIONS]
```

**Arguments**:
- `SOURCE`: Input RDF ontology file(s) (.ttl, .rdf, .owl, etc.)

**Options**:
- `-o, --output PATH`: Write output to file instead of stdout
- `-f, --format FORMAT`: Output format: `text`, `json`, `sarif` (default: text)
- `-l, --level LEVEL`: Strictness level: `relaxed`, `standard`, `strict` (default: standard)
- `-C, --config PATH`: YAML configuration file (`.rdf-lint.yml`)
- `--enable RULES`: Enable only these rules (comma-separated)
- `--disable RULES`: Disable these rules (comma-separated)

**Available Rules**:

| Rule | Category | Description |
|------|----------|-------------|
| `orphan-class` | Structural | Class has no rdfs:subClassOf |
| `dangling-reference` | Structural | Reference to undefined entity |
| `circular-subclass` | Structural | Class is subclass of itself |
| `missing-label` | Documentation | Entity lacks rdfs:label |
| `missing-comment` | Documentation | Class/property lacks rdfs:comment |
| `missing-domain` | Best Practice | Property lacks rdfs:domain |
| `missing-range` | Best Practice | Property lacks rdfs:range |
| `inconsistent-naming` | Best Practice | Mixed naming conventions |

**Examples**:

```bash
# Basic lint check
rdf-construct lint ontology.ttl

# Strict checking
rdf-construct lint ontology.ttl --level strict

# JSON output for CI
rdf-construct lint ontology.ttl --format json -o lint-results.json

# SARIF output for GitHub Actions
rdf-construct lint ontology.ttl --format sarif -o results.sarif

# Enable only specific rules
rdf-construct lint ontology.ttl --enable missing-label,missing-comment

# Disable noisy rules
rdf-construct lint ontology.ttl --disable orphan-class
```

**Exit Codes**:
- `0`: No issues found
- `1`: Warnings only
- `2`: Errors found

---

### contexts - List UML Contexts

List available UML contexts in a configuration file.

```bash
rdf-construct contexts CONFIG
```

**Arguments**:
- `CONFIG`: YAML configuration file to inspect

**Examples**:

```bash
rdf-construct contexts examples/uml_contexts.yml
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
```

---

### order - Reorder RDF Files

Reorder RDF/Turtle files according to semantic profiles.

```bash
rdf-construct order SOURCE CONFIG [OPTIONS]
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
rdf-construct order ontology.ttl order.yml

# Specific profiles
rdf-construct order ontology.ttl order.yml -p alpha -p logical_topo

# Custom output directory
rdf-construct order ontology.ttl order.yml -o output/
```

**Output**:
- Creates ordered `.ttl` files in output directory
- One file per profile: `SOURCE-PROFILE.ttl`
- Preserves semantic ordering in output

---

### profiles - List Ordering Profiles

List available ordering profiles in a configuration file.

```bash
rdf-construct profiles CONFIG
```

**Arguments**:
- `CONFIG`: YAML configuration file to inspect

**Examples**:

```bash
rdf-construct profiles order.yml
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
```

---

## Configuration Files

### SHACL Configuration

**File**: `shacl-config.yml`

```yaml
# Strictness level: minimal, standard, strict
level: standard

# Default severity: violation, warning, info
default_severity: violation

# Generate closed shapes
closed: false

# Target specific classes (empty = all)
target_classes: []
  # - Building
  # - Floor

# Exclude classes
exclude_classes: []
  # - owl:Thing

# Include labels and descriptions
include_labels: true
include_descriptions: true

# Inherit from superclasses
inherit_constraints: true

# Properties to ignore in closed shapes
ignored_properties:
  - rdf:type
  - rdfs:label
```

### Lint Configuration

**File**: `.rdf-lint.yml`

```yaml
# Strictness level
level: standard

# Rule configuration
rules:
  orphan-class:
    enabled: true
    severity: warning
  
  missing-label:
    enabled: true
    severity: error
  
  missing-comment:
    enabled: true
    severity: warning

# Ignore patterns
ignore:
  namespaces:
    - "http://www.w3.org/2002/07/owl#"
  entities:
    - "ex:DeprecatedClass"
```

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
    
    classes:
      by_namespace:
        prefix:
          border: "#0066CC"
          fill: "#E8F4F8"
      default:
        border: "#000000"
        fill: "#FFFFFF"
    
    instances:
      border: "#000000"
      fill: "#000000"
      text: "#FFFFFF"
    
    arrows:
      subclass:
        color: "#0066CC"
        style: bold
```

### Layout Configuration

**File**: `uml_layouts.yml`

```yaml
layouts:
  layout_name:
    description: "Layout arrangement"
    direction: top_to_bottom
    arrow_direction: up
    hide_empty_members: false
    group_by_namespace: false
```

### Ordering Profile Configuration

**File**: `order.yml`

```yaml
prefix_order:
  - rdf
  - rdfs
  - owl

selectors:
  classes: "rdf:type owl:Class"
  obj_props: "rdf:type owl:ObjectProperty"

profiles:
  profile_name:
    description: "Profile description"
    sections:
      - header: {}
      - classes:
          select: classes
          sort: topological
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (or no differences/issues) |
| `1` | General error (or differences/warnings found) |
| `2` | Command line usage error (or errors found for lint) |

---

## Common Workflows

### Generate Complete Documentation

```bash
# HTML docs, UML diagrams, and SHACL shapes
rdf-construct docs ontology.ttl -o docs/api/
rdf-construct uml ontology.ttl -C contexts.yml -o docs/diagrams/
rdf-construct shacl-gen ontology.ttl -o docs/shapes.ttl
```

### CI Quality Pipeline

```bash
# Lint, generate shapes, validate
rdf-construct lint ontology.ttl --format sarif -o lint.sarif
rdf-construct shacl-gen ontology.ttl -o shapes.ttl --level strict
pyshacl -s shapes.ttl -d test-data.ttl
```

### Compare Ontology Versions

```bash
# Semantic diff with changelog
rdf-construct diff v1.0.ttl v1.1.ttl --format markdown -o CHANGELOG.md
```

### Generate Presentation Diagrams

```bash
rdf-construct uml ontology.ttl -C config.yml \
  --style-config styles.yml --style high_contrast \
  --layout-config layouts.yml --layout presentation
```

---

## Troubleshooting

### "Command not found"

```bash
# With poetry
poetry run rdf-construct --version

# Or activate shell
poetry shell
rdf-construct --version
```

### "Context/Profile not found"

```bash
# List available options
rdf-construct contexts config.yml
rdf-construct profiles order.yml
```

### Empty Output

1. Check CURIE format in config matches ontology prefixes
2. Verify namespace prefixes
3. Check selection criteria

---

## Getting Help

```bash
rdf-construct --help
rdf-construct docs --help
rdf-construct uml --help
rdf-construct shacl-gen --help
rdf-construct diff --help
rdf-construct lint --help
```

**Online**:
- Issues: https://github.com/aigora-de/rdf-construct/issues
- Discussions: https://github.com/aigora-de/rdf-construct/discussions

---

## See Also

- **[Getting Started](GETTING_STARTED.md)**: Quick start guide
- **[Docs Guide](DOCS_GUIDE.md)**: Documentation generation
- **[UML Guide](UML_GUIDE.md)**: Complete UML features
- **[SHACL Guide](SHACL_GUIDE.md)**: SHACL shape generation
- **[Diff Guide](DIFF_GUIDE.md)**: Ontology comparison
- **[Lint Guide](LINT_GUIDE.md)**: Ontology quality checking