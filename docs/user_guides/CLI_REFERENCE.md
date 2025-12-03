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

### puml2rdf - Convert PlantUML to RDF

Convert PlantUML class diagrams to RDF/OWL ontologies, enabling diagram-first ontology design.

```bash
rdf-construct puml2rdf SOURCE [OPTIONS]
```

**Arguments**:
- `SOURCE`: PlantUML file (.puml or .plantuml)

**Options**:
- `-o, --output PATH`: Output file path (default: source name with .ttl extension)
- `-f, --format FORMAT`: Output format: `turtle`, `ttl`, `xml`, `rdfxml`, `jsonld`, `json-ld`, `nt`, `ntriples` (default: turtle)
- `-n, --namespace URI`: Default namespace URI for the ontology
- `-C, --config PATH`: Path to YAML configuration file
- `-m, --merge PATH`: Existing ontology file to merge with
- `-v, --validate`: Validate only, don't generate output
- `--strict`: Treat warnings as errors
- `-l, --language TAG`: Language tag for labels/comments (default: en)
- `--no-labels`: Don't auto-generate rdfs:label triples

**Supported PlantUML Syntax**:
- Classes: `class Building`, `class "Display Name" as pkg.Building`
- Attributes: `floorArea : decimal`, `name : string`
- Inheritance: `Building --|> Entity`, `Entity <|-- Building`
- Associations: `Building --> Floor : hasFloor`
- Packages: `package "http://example.org/building#" as bld { ... }`
- Notes: `note right of Building : A physical structure`
- Direction hints: `-u-|>`, `-d-|>`, `-l-|>`, `-r-|>` (up, down, left, right)

**RDF Mapping**:
| PlantUML | RDF |
|----------|-----|
| `class Building` | `Building rdf:type owl:Class` |
| `floorArea : decimal` | `floorArea rdf:type owl:DatatypeProperty ; rdfs:range xsd:decimal` |
| `Building --\|> Entity` | `Building rdfs:subClassOf Entity` |
| `Building --> Floor : hasFloor` | `hasFloor rdf:type owl:ObjectProperty ; rdfs:domain Building ; rdfs:range Floor` |
| Note attached to class | `rdfs:comment` |

**Examples**:

```bash
# Basic conversion
rdf-construct puml2rdf design.puml

# Custom output and namespace
rdf-construct puml2rdf design.puml -o ontology.ttl -n http://example.org/ont#

# Validate without generating
rdf-construct puml2rdf design.puml --validate

# Merge with existing ontology (preserves manual annotations)
rdf-construct puml2rdf design.puml --merge existing.ttl

# Use configuration file for namespace mappings
rdf-construct puml2rdf design.puml -C puml-config.yml

# Strict mode for CI
rdf-construct puml2rdf design.puml --validate --strict
```

**Exit Codes**:
- `0`: Success
- `1`: Validation warnings (with --strict)
- `2`: Parse or validation errors

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

### cq-test - Test Competency Questions

Validate ontologies against competency questions expressed as SPARQL queries with expected results.

```bash
rdf-construct cq-test ONTOLOGY TEST_FILE [OPTIONS]
```

**Arguments**:
- `ONTOLOGY`: Input RDF ontology file (.ttl, .rdf, .owl, etc.)
- `TEST_FILE`: YAML file containing competency question tests

**Options**:
- `-d, --data PATH`: Additional data files to load (can specify multiple)
- `-t, --tag TAG`: Only run tests with this tag (can specify multiple)
- `-x, --exclude-tag TAG`: Exclude tests with this tag (can specify multiple)
- `-f, --format FORMAT`: Output format: `text`, `json`, `junit` (default: text)
- `-o, --output PATH`: Write output to file instead of stdout
- `-v, --verbose`: Show detailed output including query text and timing
- `--fail-fast`: Stop on first test failure

**Test File Format**:

```yaml
version: "1.0"
name: "Animal Ontology Tests"
description: "Competency questions for validating the animal ontology"

prefixes:
  ex: "http://example.org/animals#"
  owl: "http://www.w3.org/2002/07/owl#"
  rdfs: "http://www.w3.org/2000/01/rdf-schema#"

# Optional inline test data
data: |
  @prefix ex: <http://example.org/animals#> .
  ex:Fido a ex:Dog .
  ex:Rex a ex:Dog .

# Or reference external files
data_files:
  - test-data/instances.ttl

questions:
  - id: cq-001
    name: "Animal class exists"
    description: "The ontology should define an Animal class"
    tags: [schema, required]
    query: "ASK { ex:Animal a owl:Class }"
    expect: true

  - id: cq-002
    name: "Dogs are animals"
    description: "Dog should be a subclass of Animal"
    tags: [schema, hierarchy]
    query: |
      ASK { 
        ex:Dog rdfs:subClassOf ex:Animal 
      }
    expect: true

  - id: cq-003
    name: "At least one dog instance"
    tags: [data]
    query: "SELECT ?dog WHERE { ?dog a ex:Dog }"
    expect:
      min_count: 1

  - id: cq-004
    name: "Exactly two dogs"
    tags: [data]
    query: "SELECT ?dog WHERE { ?dog a ex:Dog }"
    expect:
      count: 2

  - id: cq-005
    name: "Fido exists"
    tags: [data, instances]
    query: "SELECT ?dog WHERE { ?dog a ex:Dog }"
    expect:
      contains:
        - dog: "http://example.org/animals#Fido"
```

**Expectation Types**:

| Type | Description | Example |
|------|-------------|---------|
| `true` / `false` | ASK query result | `expect: true` |
| `has_results` | Query returns ≥1 results | `expect: has_results` |
| `no_results` | Query returns 0 results | `expect: no_results` |
| `count` | Exact result count | `expect: { count: 5 }` |
| `min_count` | Minimum results | `expect: { min_count: 1 }` |
| `max_count` | Maximum results | `expect: { max_count: 10 }` |
| `results` | Exact result set | `expect: { results: [...] }` |
| `contains` | Subset matching | `expect: { contains: [...] }` |

**Examples**:

```bash
# Run all tests
rdf-construct cq-test ontology.ttl tests.yml

# With additional instance data
rdf-construct cq-test ontology.ttl tests.yml --data instances.ttl

# Filter by tag
rdf-construct cq-test ontology.ttl tests.yml --tag schema

# Exclude data tests
rdf-construct cq-test ontology.ttl tests.yml --exclude-tag data

# JUnit output for CI
rdf-construct cq-test ontology.ttl tests.yml --format junit -o results.xml

# JSON output for scripting
rdf-construct cq-test ontology.ttl tests.yml --format json

# Verbose with fail-fast
rdf-construct cq-test ontology.ttl tests.yml --verbose --fail-fast
```

**Exit Codes**:
- `0`: All tests passed
- `1`: One or more tests failed
- `2`: Error occurred (parse error, file not found, etc.)

**Output Formats**:
- `text`: Human-readable console output with colours
- `json`: Structured JSON for programmatic use
- `junit`: JUnit XML for CI integration (GitHub Actions, GitLab CI, Jenkins)

---

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

---

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

---

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
```

---

Comparing: v1.ttl → v2.ttl
==========================

                        v1        v2    Change
Classes                 10        12    +2 (+20.0%) ✓
Max Depth                3         4    +1
Documentation Coverage  60%       67%   +7pp ✓

Summary: Ontology grew with improved documentation coverage.
```

**Exit Codes**:
- `0`: Success
- `1`: Error occurred

## Configuration Files

### PlantUML Import Configuration

**File**: `puml-import.yml`

```yaml
# Default namespace for entities without explicit package
default_namespace: "http://example.org/ontology#"

# Language tag for labels and comments
language: "en"

# Automatically generate rdfs:label from entity names
generate_labels: true

# Convert camelCase names to readable labels
camel_to_label: true

# Map PlantUML packages to RDF namespaces
namespace_mappings:
  - package: "building"
    namespace_uri: "http://example.org/building#"
    prefix: "bld"

# Custom datatype mappings
datatype_mappings:
  Money: "xsd:decimal"
  Percentage: "xsd:decimal"

# Preferred prefix ordering in output
prefix_order:
  - ""
  - "owl"
  - "rdfs"
  - "xsd"

# URIs to include as owl:imports
ontology_imports: []
```

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

### Competency Question Test Configuration

**File**: `cq-tests.yml`

```yaml
version: "1.0"
name: "Ontology Competency Tests"
description: "SPARQL-based validation of ontology requirements"

prefixes:
  ex: "http://example.org/ontology#"
  owl: "http://www.w3.org/2002/07/owl#"
  rdfs: "http://www.w3.org/2000/01/rdf-schema#"

# Inline test data (Turtle format)
data: |
  @prefix ex: <http://example.org/ontology#> .
  ex:Instance1 a ex:Class1 .

# Or external data files
data_files:
  - test-data/instances.ttl
  - test-data/more-data.ttl

questions:
  - id: cq-001
    name: "Test name"
    description: "Optional longer description"
    tags: [schema, required]
    query: "ASK { ... }"
    expect: true
    
  - id: cq-002
    name: "Skipped test"
    skip: true
    skip_reason: "Feature not yet implemented"
    query: "ASK { ... }"
    expect: true
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

| Code | Meaning |
|------|---------|
| `0` | Success (or no differences/issues) |
| `1` | General error (or differences/warnings/failures found) |
| `2` | Command line usage error (or errors found for lint) |

## Files and Directories

**Input Files**:
- `.ttl` - RDF/Turtle ontology files
- `.yml` - YAML configuration files

**Output Files**:
- `.puml` - PlantUML diagram files (from `uml` command)
- `.ttl` - Ordered RDF/Turtle files (from `order` command)
- `.json` - Statistics output (from `stats --format json`)
- `.md` - Markdown output (from `stats --format markdown`)

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

### Diagram-First Ontology Design

```bash
# Design in PlantUML, generate RDF
rdf-construct puml2rdf design.puml -o ontology.ttl -n http://example.org/ont#

# Add manual annotations, then update from PlantUML
rdf-construct puml2rdf design.puml --merge ontology.ttl -o ontology.ttl

# Validate ontology quality
```bash
# Lint, generate shapes, validate, test competency questions
rdf-construct lint ontology.ttl --format sarif -o lint.sarif
rdf-construct shacl-gen ontology.ttl -o shapes.ttl --level strict
pyshacl -s shapes.ttl -d test-data.ttl
rdf-construct cq-test ontology.ttl cq-tests.yml --format junit -o cq-results.xml
```

### Compare Ontology Versions

```bash
# Generate ordered versions
poetry run rdf-construct order v1.ttl order.yml -p canonical -o output/v1/
poetry run rdf-construct order v2.ttl order.yml -p canonical -o output/v2/

### Generate Complete Documentation

```bash
# HTML docs, UML diagrams, and SHACL shapes
rdf-construct docs ontology.ttl -o docs/api/
rdf-construct uml ontology.ttl -C contexts.yml -o docs/diagrams/
rdf-construct shacl-gen ontology.ttl -o docs/shapes.ttl
```

# Diff them
diff output/v1/v1-canonical.ttl output/v2/v2-canonical.ttl
```

### Track Ontology Metrics

```bash
# Generate stats for CI pipeline
poetry run rdf-construct stats ontology.ttl --format json -o metrics.json

# Compare versions before release
poetry run rdf-construct stats v1.ttl v2.ttl --compare --format markdown >> CHANGELOG.md
```

### Generate Presentation Diagrams

```bash
# High contrast, large spacing
poetry run rdf-construct uml ontology.ttl config.yml \
  --style-config styles.yml --style high_contrast \
  --layout-config layouts.yml --layout presentation
```

### Test-Driven Ontology Development

```bash
# Write competency questions first
rdf-construct cq-test ontology.ttl cq-tests.yml --tag required

# Iterate until all pass
rdf-construct cq-test ontology.ttl cq-tests.yml --verbose

# Run full test suite in CI
rdf-construct cq-test ontology.ttl cq-tests.yml --format junit -o results.xml
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
rdf-construct --help
rdf-construct docs --help
rdf-construct uml --help
rdf-construct puml2rdf --help
rdf-construct shacl-gen --help
rdf-construct diff --help
rdf-construct lint --help
rdf-construct cq-test --help
```

# Online resources
# - Issues: https://github.com/aigora-de/rdf-construct/issues
# - Discussions: https://github.com/aigora-de/rdf-construct/discussions
```

## See Also

- **[Getting Started](GETTING_STARTED.md)**: Quick start guide
- **[Docs Guide](DOCS_GUIDE.md)**: Documentation generation
- **[UML Guide](UML_GUIDE.md)**: Complete UML features
- **[PlantUML Import Guide](PUML_IMPORT_GUIDE.md)**: PlantUML to RDF conversion
- **[SHACL Guide](SHACL_GUIDE.md)**: SHACL shape generation
- **[Diff Guide](DIFF_GUIDE.md)**: Ontology comparison
- **[Lint Guide](LINT_GUIDE.md)**: Ontology quality checking
- **[CQ Testing Guide](CQ_TEST_GUIDE.md)**: Competency question testing
- **[Stats Guide](STATS_GUIDE.md)**: Ontology metrics and statistics