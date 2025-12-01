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

Generate comprehensive HTML, Markdown, or JSON documentation from RDF ontologies.

```bash
poetry run rdf-construct docs SOURCES... [OPTIONS]
```

**Arguments**:
- `SOURCES`: One or more RDF files (Turtle, RDF/XML, etc.)

**Options**:
- `-o, --output PATH`: Output directory (default: `docs/`)
- `-f, --format FORMAT`: Output format: `html`, `markdown`, `json` (default: `html`)
- `-C, --config PATH`: Path to configuration YAML file
- `-t, --template PATH`: Path to custom template directory
- `--single-page`: Generate single-page documentation
- `--title TEXT`: Override ontology title
- `--no-search`: Disable search index (HTML only)
- `--no-instances`: Exclude instances from output
- `--include TYPES`: Include only these types (comma-separated)
- `--exclude TYPES`: Exclude these types (comma-separated)

**Examples**:

```bash
# Basic HTML documentation
poetry run rdf-construct docs ontology.ttl

# Markdown output to custom directory
poetry run rdf-construct docs ontology.ttl --format markdown -o wiki/

# Single-page HTML with custom title
poetry run rdf-construct docs ontology.ttl --single-page --title "My Ontology"

# JSON output for custom rendering
poetry run rdf-construct docs ontology.ttl --format json

# Generate from multiple sources (merged)
poetry run rdf-construct docs domain.ttl foundation.ttl -o docs/

# Use custom templates
poetry run rdf-construct docs ontology.ttl --template my-templates/

# Only classes and properties (no instances)
poetry run rdf-construct docs ontology.ttl --exclude instances

# With configuration file
poetry run rdf-construct docs ontology.ttl --config docs-config.yml
```

**Output**:
- Creates documentation files in output directory
- HTML: navigable pages with search
- Markdown: GitHub/GitLab compatible with frontmatter
- JSON: structured data for custom rendering

### uml - Generate UML Diagrams

Generate PlantUML class diagrams from RDF ontologies.

```bash
poetry run rdf-construct uml SOURCES... -C CONFIG [OPTIONS]
```

**Arguments**:
- `SOURCES`: One or more RDF files (.ttl, .rdf, etc.)
- `-C, --config CONFIG`: YAML configuration file defining contexts (required)

**Options**:
- `-c, --context NAME`: Generate specific context(s) (can specify multiple)
- `-o, --outdir PATH`: Output directory (default: `diagrams`)
- `--style-config PATH`: Path to style configuration YAML
- `-s, --style NAME`: Style scheme name to use
- `--layout-config PATH`: Path to layout configuration YAML
- `-l, --layout NAME`: Layout name to use
- `-r, --rendering-mode MODE`: Rendering mode: `default` or `odm`

**Examples**:

```bash
# Generate all contexts
poetry run rdf-construct uml ontology.ttl -C config.yml

# Specific context
poetry run rdf-construct uml ontology.ttl -C config.yml -c animal_taxonomy

# Multiple contexts
poetry run rdf-construct uml ontology.ttl -C config.yml -c context1 -c context2

# Custom output directory
poetry run rdf-construct uml ontology.ttl -C config.yml -o my-diagrams/

# With styling
poetry run rdf-construct uml ontology.ttl -C config.yml \
  --style-config examples/uml_styles.yml \
  --style default

# With styling and layout
poetry run rdf-construct uml ontology.ttl -C config.yml \
  --style-config examples/uml_styles.yml --style default \
  --layout-config examples/uml_layouts.yml --layout hierarchy

# Multiple source files (merged)
poetry run rdf-construct uml domain.ttl foundation.ttl -C config.yml

# ODM-compliant rendering
poetry run rdf-construct uml ontology.ttl -C config.yml --rendering-mode odm
```

**Output**:
- Creates `.puml` files in output directory
- One file per context: `SOURCE-CONTEXT.puml`
- Shows summary: number of classes, properties, instances

### diff - Compare RDF Files

Compare two RDF files and show semantic differences, ignoring cosmetic changes.

```bash
poetry run rdf-construct diff OLD_FILE NEW_FILE [OPTIONS]
```

**Arguments**:
- `OLD_FILE`: Original RDF file
- `NEW_FILE`: Modified RDF file

**Options**:
- `-o, --output PATH`: Write output to file instead of stdout
- `-f, --format FORMAT`: Output format: `text`, `markdown`, `json` (default: `text`)
- `--show TYPES`: Show only these change types (comma-separated: `added`, `removed`, `modified`)
- `--hide TYPES`: Hide these change types
- `--entities TYPES`: Show only these entity types (comma-separated: `classes`, `properties`, `instances`)
- `--ignore-predicates PREDS`: Ignore these predicates in comparison (comma-separated CURIEs)

**Examples**:

```bash
# Basic comparison
poetry run rdf-construct diff v1.0.ttl v1.1.ttl

# Generate markdown changelog
poetry run rdf-construct diff v1.0.ttl v1.1.ttl --format markdown -o CHANGELOG.md

# Show only additions and removals
poetry run rdf-construct diff old.ttl new.ttl --show added,removed

# Focus on class changes only
poetry run rdf-construct diff old.ttl new.ttl --entities classes

# Ignore timestamp predicates
poetry run rdf-construct diff old.ttl new.ttl --ignore-predicates dcterms:modified
```

**Exit Codes**:
- `0`: Graphs are semantically identical
- `1`: Differences found
- `2`: Error occurred

### lint - Check Ontology Quality

Check RDF ontologies for common issues and best practice violations.

```bash
poetry run rdf-construct lint SOURCES... [OPTIONS]
```

**Arguments**:
- `SOURCES`: One or more RDF files to check

**Options**:
- `--level LEVEL`: Checking level: `strict`, `standard`, `relaxed` (default: `standard`)
- `-f, --format FORMAT`: Output format: `text`, `json` (default: `text`)
- `--enable RULES`: Enable specific rules (comma-separated)
- `--disable RULES`: Disable specific rules (comma-separated)
- `-C, --config PATH`: Path to lint configuration file

**Examples**:

```bash
# Basic lint check
poetry run rdf-construct lint ontology.ttl

# Strict checking
poetry run rdf-construct lint ontology.ttl --level strict

# JSON output for CI
poetry run rdf-construct lint ontology.ttl --format json

# Disable specific rules
poetry run rdf-construct lint ontology.ttl --disable missing-comment

# With configuration
poetry run rdf-construct lint ontology.ttl --config .rdf-lint.yml
```

**Exit Codes**:
- `0`: No issues found
- `1`: Warnings only
- `2`: Errors found

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

# Custom output directory
poetry run rdf-construct order ontology.ttl order.yml -o output/
```

**Output**:
- Creates ordered `.ttl` files in output directory
- One file per profile: `SOURCE-PROFILE.ttl`

### profiles - List Ordering Profiles

List available ordering profiles in a configuration file.

```bash
poetry run rdf-construct profiles CONFIG
```

**Arguments**:
- `CONFIG`: YAML configuration file to inspect

## Configuration Files

### Documentation Configuration

**File**: `docs-config.yml`

```yaml
output_dir: docs/
format: html
title: "My Ontology Documentation"
language: en

include_classes: true
include_object_properties: true
include_datatype_properties: true
include_annotation_properties: false
include_instances: true

include_search: true
include_hierarchy: true
include_statistics: true

# Custom templates
template_dir: my-templates/

# Exclude standard namespaces
exclude_namespaces:
  - http://www.w3.org/2002/07/owl#
  - http://www.w3.org/2000/01/rdf-schema#
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
    description: "Layout arrangement description"
    direction: top_to_bottom
    arrow_direction: up
    hide_empty_members: false
    group_by_namespace: false
```

### Lint Configuration

**File**: `.rdf-lint.yml`

```yaml
level: standard

rules:
  orphan-class: error
  missing-label: warning
  missing-comment: info
  property-no-domain: warning

exclude_namespaces:
  - http://www.w3.org/2002/07/owl#
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
    description: "Human-readable description"
    sections:
      - header: {}
      - classes:
          select: classes
          sort: topological
```

## Exit Codes

| Command | Code | Meaning |
|---------|------|---------|
| All | `0` | Success |
| All | `1` | General error / warnings only (lint) / differences found (diff) |
| All | `2` | Command error / errors found (lint) / file error (diff) |

## Files and Directories

**Input Files**:
- `.ttl` - RDF/Turtle ontology files
- `.rdf`, `.xml`, `.owl` - RDF/XML files
- `.yml` - YAML configuration files

**Output Files**:
- `.html`, `.md`, `.json` - Documentation (from `docs` command)
- `.puml` - PlantUML diagram files (from `uml` command)
- `.ttl` - Ordered RDF/Turtle files (from `order` command)

**Default Output Directories**:
- `docs/` - Documentation output
- `diagrams/` - UML diagram output
- `src/ontology/` - Ordered RDF output

**Configuration Files**:
- `docs-config.yml` - Documentation settings
- `uml_contexts.yml` - UML context definitions
- `uml_styles.yml` - UML styling
- `uml_layouts.yml` - UML layout settings
- `.rdf-lint.yml` - Lint rule configuration
- `order.yml` - Ordering profile definitions

## Common Workflows

### Generate Complete Documentation Set

```bash
# HTML docs with diagrams
poetry run rdf-construct docs ontology.ttl -o docs/

# Generate UML diagrams
poetry run rdf-construct uml ontology.ttl -C contexts.yml -o docs/diagrams/

# Run quality check
poetry run rdf-construct lint ontology.ttl
```

### CI/CD Ontology Validation

```bash
#!/bin/bash
# Lint check (fails on errors)
poetry run rdf-construct lint ontology.ttl --format json > lint-results.json
if [ $? -eq 2 ]; then
  echo "Lint errors found!"
  exit 1
fi

# Generate documentation
poetry run rdf-construct docs ontology.ttl -o public/docs/
```

### Version Comparison Workflow

```bash
# Compare versions
poetry run rdf-construct diff v1.0.ttl v1.1.ttl --format markdown > CHANGES.md

# Generate docs for new version
poetry run rdf-construct docs v1.1.ttl -o docs/v1.1/
```

## Tips

### Check Configuration First

```bash
poetry run rdf-construct contexts config.yml
poetry run rdf-construct profiles order.yml
```

### Start Simple

Generate without styling first, then add customisation:

```bash
# Basic docs
poetry run rdf-construct docs ontology.ttl

# Then add templates
poetry run rdf-construct docs ontology.ttl --template custom/
```

### Use Descriptive Names

In YAML configs:
- **Good**: `animal_taxonomy`, `management_structure`
- **Bad**: `context1`, `test`, `temp`

## Troubleshooting

### "Command not found"

```bash
# Use poetry run
poetry run rdf-construct --version

# Or activate shell
poetry shell
rdf-construct --version
```

### "Context/Profile not found"

```bash
# List available options
poetry run rdf-construct contexts config.yml
poetry run rdf-construct profiles order.yml
```

### Empty Output

Check:
1. CURIE format in config matches ontology prefixes
2. Namespace prefixes are bound in ontology
3. Selection criteria match entities in ontology

## Getting Help

```bash
poetry run rdf-construct --help
poetry run rdf-construct docs --help
poetry run rdf-construct uml --help
poetry run rdf-construct diff --help
poetry run rdf-construct lint --help
```

## See Also

- **[Getting Started](GETTING_STARTED.md)**: Quick start guide
- **[Docs Guide](DOCS_GUIDE.md)**: Documentation generation details
- **[UML Guide](UML_GUIDE.md)**: Complete UML features
- **[Diff Guide](DIFF_GUIDE.md)**: Semantic comparison details
- **[Lint Guide](LINT_GUIDE.md)**: Ontology quality checking