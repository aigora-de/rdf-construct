# CLI Reference

Complete command reference for rdf-construct.

## Installation

```bash
# With pip (recommended)
pip install rdf-construct

# With Poetry (for development)
git clone https://github.com/aigora-de/rdf-construct.git
cd rdf-construct
poetry install

# From source
git clone https://github.com/aigora-de/rdf-construct.git
cd rdf-construct
pip install -e .
```

> **Note**: If installed via Poetry, prefix commands with `poetry run` (e.g., `poetry run rdf-construct --help`). Once installed via pip, use `rdf-construct` directly.

## Global Options

```bash
rdf-construct --version    # Show version
rdf-construct --help       # Show help
```

## Commands

### order - Reorder RDF Files

Reorder RDF Turtle files according to semantic profiles.

```bash
rdf-construct order SOURCE CONFIG [OPTIONS]
```

**Arguments**:
- `SOURCE`: Input RDF Turtle file (.ttl)
- `CONFIG`: YAML configuration file defining ordering profiles

**Options**:
- `-p, --profile NAME`: Profile(s) to generate (can specify multiple, default: all)
- `-o, --outdir PATH`: Output directory (default: `src/ontology`)

**Examples**:

```bash
# Generate all profiles defined in config
rdf-construct order ontology.ttl order.yml

# Generate specific profiles only
rdf-construct order ontology.ttl order.yml -p alpha -p logical_topo

# Custom output directory
rdf-construct order ontology.ttl order.yml -o output/
```

---

### profiles - List Ordering Profiles

List available profiles in a configuration file.

```bash
rdf-construct profiles CONFIG
```

**Arguments**:
- `CONFIG`: YAML configuration file to inspect

**Example**:

```bash
rdf-construct profiles order.yml
```

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

### contexts - List UML Contexts

List available UML contexts in a configuration file.

```bash
rdf-construct contexts CONFIG
```

**Arguments**:
- `CONFIG`: YAML configuration file to inspect

**Example**:

```bash
rdf-construct contexts uml_contexts.yml
```

---

### docs - Generate Documentation

Generate HTML, Markdown, or JSON documentation from RDF ontologies.

```bash
rdf-construct docs SOURCE [OPTIONS]
```

**Arguments**:
- `SOURCE`: Input RDF ontology file (.ttl, .rdf, .owl, etc.)

**Options**:
- `-o, --output PATH`: Output directory (default: `docs`)
- `-f, --format FORMAT`: Output format: `html`, `markdown`, `md`, `json` (default: html)
- `-C, --config PATH`: YAML configuration file
- `-t, --template PATH`: Path to custom Jinja2 templates directory
- `--title TEXT`: Documentation title (default: from ontology or filename)
- `--single-page`: Generate single-page documentation
- `--no-search`: Disable search index generation (HTML only)
- `--no-instances`: Exclude instances from documentation
- `--include TYPES`: Include only these entity types (comma-separated: classes, properties, instances)
- `--exclude TYPES`: Exclude these entity types

**Examples**:

```bash
# Generate HTML documentation
rdf-construct docs ontology.ttl -o api-docs/

# Generate Markdown for GitHub wiki
rdf-construct docs ontology.ttl --format markdown -o wiki/

# Generate JSON for custom rendering
rdf-construct docs ontology.ttl --format json -o data/

# Single-page HTML with custom title
rdf-construct docs ontology.ttl --single-page --title "My Ontology"

# Use custom templates
rdf-construct docs ontology.ttl --template my-templates/ -o docs/
```

**Output**:
- HTML: Complete website with navigation, search, and styling
- Markdown: Individual `.md` files per class/property
- JSON: Structured data for programmatic use

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

# Ignore version predicates
rdf-construct diff old.ttl new.ttl --ignore-predicates "owl:versionInfo,dct:modified"

# JSON output for scripting
rdf-construct diff old.ttl new.ttl --format json -o changes.json
```

**Exit Codes**:
- `0`: Graphs are semantically identical
- `1`: Differences were found
- `2`: Error occurred

---

### lint - Check Ontology Quality

Check RDF ontologies for structural issues, missing documentation, and best practice violations.

```bash
rdf-construct lint SOURCE [SOURCE...] [OPTIONS]
```

**Arguments**:
- `SOURCE`: One or more RDF files to check

**Options**:
- `-l, --level LEVEL`: Strictness level: `strict`, `standard`, `relaxed` (default: standard)
- `-f, --format FORMAT`: Output format: `text`, `json` (default: text)
- `-c, --config PATH`: Path to `.rdf-lint.yml` configuration file
- `-e, --enable RULE`: Enable specific rules (can use multiple times)
- `-d, --disable RULE`: Disable specific rules (can use multiple times)
- `--no-colour`: Disable coloured output
- `--list-rules`: List available rules and exit
- `--init`: Generate a default `.rdf-lint.yml` config file and exit

**Available Rules**:

| Rule | Category | Severity | Description |
|------|----------|----------|-------------|
| `orphan-class` | Structural | error | Class with no superclass or subclasses |
| `dangling-reference` | Structural | error | Reference to undefined entity |
| `circular-subclass` | Structural | error | Circular subclass hierarchy |
| `property-no-type` | Structural | error | Property without type declaration |
| `empty-ontology` | Structural | error | Ontology with no classes or properties |
| `missing-label` | Documentation | warning | Entity without rdfs:label |
| `missing-comment` | Documentation | warning | Entity without rdfs:comment |
| `redundant-subclass` | Best Practice | info | Redundant subclass declaration |
| `property-no-domain` | Best Practice | info | Property without rdfs:domain |
| `property-no-range` | Best Practice | info | Property without rdfs:range |
| `inconsistent-naming` | Best Practice | info | Inconsistent naming conventions |

**Examples**:

```bash
# Run all lint rules
rdf-construct lint ontology.ttl

# Strict checking
rdf-construct lint ontology.ttl --level strict

# Check multiple files
rdf-construct lint domain.ttl foundation.ttl

# JSON output for CI
rdf-construct lint ontology.ttl --format json -o lint-results.json

# Enable only specific rules
rdf-construct lint ontology.ttl -e missing-label -e missing-comment

# Disable specific rules
rdf-construct lint ontology.ttl -d orphan-class

# List all available rules
rdf-construct lint --list-rules

# Generate default config file
rdf-construct lint --init
```

**Exit Codes**:
- `0`: No issues found
- `1`: Warnings found (with standard/strict level)
- `2`: Errors found

---

### merge - Combine RDF Ontologies

Merge multiple RDF ontology files with intelligent conflict detection and resolution.

```bash
rdf-construct merge [SOURCES...] -o OUTPUT [OPTIONS]
```

**Arguments**:
- `SOURCES`: One or more RDF files to merge (.ttl, .rdf, .owl)

**Options**:
- `-o, --output PATH`: Output file for merged ontology (required)
- `-c, --config PATH`: YAML configuration file
- `-p, --priority INT`: Priority for each source (can specify multiple, higher wins conflicts)
- `--strategy STRATEGY`: Conflict resolution: `priority`, `first`, `last`, `mark_all` (default: priority)
- `-r, --report PATH`: Write conflict report to file
- `--report-format FORMAT`: Report format: `text`, `markdown`, `md` (default: markdown)
- `--imports STRATEGY`: owl:imports handling: `preserve`, `remove`, `merge` (default: preserve)
- `--migrate-data PATH`: Data file(s) to migrate (can specify multiple)
- `--migration-rules PATH`: YAML file with migration rules
- `--data-output PATH`: Output path for migrated data
- `--dry-run`: Show what would happen without writing files
- `--no-colour`: Disable coloured output
- `--init`: Generate a default merge configuration file

**Conflict Resolution Strategies**:

| Strategy | Description |
|----------|-------------|
| `priority` | Higher priority source wins (default) |
| `first` | First source encountered wins |
| `last` | Last source encountered wins |
| `mark_all` | Mark all conflicts for manual review |

**Examples**:

```bash
# Basic merge of two ontologies
rdf-construct merge core.ttl extension.ttl -o merged.ttl

# With priorities (extension wins conflicts)
rdf-construct merge core.ttl extension.ttl -o merged.ttl -p 1 -p 2

# Mark all conflicts for manual review
rdf-construct merge core.ttl extension.ttl -o merged.ttl --strategy mark_all

# Generate conflict report
rdf-construct merge core.ttl extension.ttl -o merged.ttl --report conflicts.md

# Dry run (preview without writing)
rdf-construct merge core.ttl extension.ttl -o merged.ttl --dry-run

# With data migration
rdf-construct merge core.ttl extension.ttl -o merged.ttl \
    --migrate-data split_instances.ttl --data-output migrated.ttl

# Using configuration file
rdf-construct merge --config merge.yml -o merged.ttl

# Generate default configuration
rdf-construct merge --init
```

**Conflict Markers**:

Unresolved conflicts are marked in the output file:

```turtle
# === CONFLICT: ex:Building rdfs:label ===
# Source: core.ttl (priority 1): "Building"@en
# Source: ext.ttl (priority 2): "Structure"@en
# Resolution: UNRESOLVED - values differ, manual review required
ex:Building a owl:Class ;
    rdfs:label "Building"@en ;
    rdfs:label "Structure"@en .
# === END CONFLICT ===
```

Find conflicts with: `grep -n "=== CONFLICT ===" merged.ttl`

**Configuration File Format**:

```yaml
sources:
  - path: core.ttl
    priority: 1
  - path: extension.ttl
    priority: 2
    namespace_remap:
      "http://old.org/": "http://new.org/"

output:
  path: merged.ttl
  format: turtle

conflicts:
  strategy: priority
  report: conflicts.md

imports: preserve

migrate_data:
  sources:
    - split_instances.ttl
  output: migrated.ttl
  rules:
    - type: rename
      from: "http://old.org/Class"
      to: "http://new.org/Class"
```

**Exit Codes**:
- `0`: Merge successful, no unresolved conflicts
- `1`: Merge successful, but unresolved conflicts marked in output
- `2`: Error (file not found, parse error, etc.)

---

---

### split - Modularise Ontologies

Split a monolithic ontology into multiple modules.
```bash
rdf-construct split SOURCE [OPTIONS]
```

**Arguments**:
- `SOURCE`: RDF ontology file to split (.ttl, .rdf, .owl)

**Options**:
- `-o, --output PATH`: Output directory for modules (default: `modules/`)
- `-c, --config PATH`: YAML configuration file
- `--by-namespace`: Auto-detect modules from namespaces
- `--migrate-data PATH`: Data file(s) to split by instance type (can specify multiple)
- `--data-output PATH`: Output directory for split data files
- `--unmatched STRATEGY`: Strategy for unmatched entities: `common` or `error` (default: common)
- `--common-name NAME`: Name for common module (default: `common`)
- `--no-manifest`: Don't generate manifest.yml
- `--dry-run`: Show what would happen without writing files
- `--no-colour`: Disable coloured output
- `--init`: Generate a default split configuration file

**Examples**:
```bash
# Split by namespace (auto-detect modules)
rdf-construct split large.ttl -o modules/ --by-namespace

# Split using configuration file
rdf-construct split large.ttl -o modules/ -c split.yml

# With data migration
rdf-construct split large.ttl -o modules/ -c split.yml \
    --migrate-data instances.ttl --data-output data/

# Dry run (preview without writing)
rdf-construct split large.ttl -o modules/ --by-namespace --dry-run

# Generate default configuration
rdf-construct split --init
```

**Configuration File Format**:
```yaml
split:
  source: ontology/monolith.ttl
  output_dir: modules/

  modules:
    # By explicit class/property list
    - name: core
      description: "Core concepts"
      output: core.ttl
      include:
        classes:
          - ex:Entity
          - ex:Event
        properties:
          - ex:identifier
      include_descendants: true

    # By namespace
    - name: organisation
      output: organisation.ttl
      namespaces:
        - "http://example.org/ontology/org#"
      auto_imports: true

  unmatched:
    strategy: common
    module: common
    output: common.ttl

  generate_manifest: true
```

**Manifest Output** (`manifest.yml`):
```yaml
source: ontology/monolith.ttl
output_dir: modules/
modules:
  - name: core
    file: core.ttl
    classes: 5
    properties: 3
    triples: 42
    imports: []
    dependencies: []
  - name: organisation
    file: organisation.ttl
    classes: 8
    properties: 5
    triples: 67
    imports: [core.ttl]
    dependencies: [core]
summary:
  total_modules: 2
  total_triples: 109
  unmatched_entities: 0
```

**Exit Codes**:
- `0`: Split successful
- `1`: Split successful, unmatched entities placed in common module
- `2`: Error (file not found, config invalid, etc.)

---

### refactor - Rename and Deprecate Entities

Refactor ontologies by renaming URIs or marking entities as deprecated.

```bash
rdf-construct refactor <subcommand> [OPTIONS]
```

**Subcommands**:
- `rename` - Rename URIs (single entity or bulk namespace)
- `deprecate` - Mark entities as deprecated with OWL annotations

---

#### refactor rename

Rename URIs in ontology files.

```bash
rdf-construct refactor rename SOURCES [OPTIONS]
```

**Arguments**:
- `SOURCES`: One or more RDF files to process (.ttl, .rdf, .owl)

**Options**:
- `--from URI`: Single URI to rename
- `--to URI`: New URI for single rename
- `--from-namespace NS`: Old namespace prefix for bulk rename
- `--to-namespace NS`: New namespace prefix for bulk rename
- `-c, --config PATH`: YAML configuration file with rename mappings
- `-o, --output PATH`: Output file (single source) or directory (multiple sources)
- `--migrate-data PATH`: Data file(s) to migrate (can specify multiple)
- `--data-output PATH`: Output path for migrated data
- `--dry-run`: Preview changes without writing files
- `--no-colour`: Disable coloured output
- `--init`: Generate a template rename configuration file

**Examples**:
```bash
# Fix a single typo
rdf-construct refactor rename ontology.ttl \
    --from "http://example.org/ont#Buiding" \
    --to "http://example.org/ont#Building" \
    -o fixed.ttl

# Bulk namespace change
rdf-construct refactor rename ontology.ttl \
    --from-namespace "http://old.example.org/" \
    --to-namespace "http://new.example.org/" \
    -o migrated.ttl

# With data migration
rdf-construct refactor rename ontology.ttl \
    --from "ex:OldClass" --to "ex:NewClass" \
    --migrate-data instances.ttl \
    --data-output updated-instances.ttl

# From configuration file
rdf-construct refactor rename --config renames.yml

# Preview changes (dry run)
rdf-construct refactor rename ontology.ttl \
    --from "ex:Old" --to "ex:New" --dry-run

# Process multiple files
rdf-construct refactor rename modules/*.ttl \
    --from-namespace "http://old/" --to-namespace "http://new/" \
    -o migrated/

# Generate template config
rdf-construct refactor rename --init
```

**Configuration File Format**:
```yaml
source_files:
  - ontology.ttl

output: renamed.ttl

rename:
  # Namespace mappings (applied first)
  namespaces:
    "http://old.example.org/v1#": "http://example.org/v2#"

  # Individual entity renames (applied after namespace)
  entities:
    "http://example.org/v2#Buiding": "http://example.org/v2#Building"
    "http://example.org/v2#hasAddres": "http://example.org/v2#hasAddress"

# Optional data migration
migrate_data:
  sources:
    - data/*.ttl
  output_dir: data/migrated/
```

---

#### refactor deprecate

Mark ontology entities as deprecated with OWL annotations.

```bash
rdf-construct refactor deprecate SOURCES [OPTIONS]
```

**Arguments**:
- `SOURCES`: One or more RDF files to process (.ttl, .rdf, .owl)

**Options**:
- `--entity URI`: URI of entity to deprecate
- `--replaced-by URI`: URI of replacement entity (adds dcterms:isReplacedBy)
- `-m, --message TEXT`: Deprecation message (added to rdfs:comment)
- `--version VERSION`: Version when deprecated (included in message)
- `-c, --config PATH`: YAML configuration file with deprecation specs
- `-o, --output PATH`: Output file
- `--dry-run`: Preview changes without writing files
- `--no-colour`: Disable coloured output
- `--init`: Generate a template deprecation configuration file

**Examples**:
```bash
# Deprecate with replacement
rdf-construct refactor deprecate ontology.ttl \
    --entity "http://example.org/ont#LegacyTerm" \
    --replaced-by "http://example.org/ont#NewTerm" \
    --message "Use NewTerm instead. Will be removed in v3.0." \
    -o updated.ttl

# Deprecate without replacement
rdf-construct refactor deprecate ontology.ttl \
    --entity "ex:ObsoleteThing" \
    --message "No longer needed." \
    -o updated.ttl

# Bulk deprecation from config
rdf-construct refactor deprecate ontology.ttl \
    -c deprecations.yml \
    -o updated.ttl

# Preview changes (dry run)
rdf-construct refactor deprecate ontology.ttl \
    --entity "ex:Legacy" --replaced-by "ex:Modern" --dry-run

# Generate template config
rdf-construct refactor deprecate --init
```

**Configuration File Format**:
```yaml
source_files:
  - ontology.ttl

output: deprecated.ttl

deprecations:
  - entity: "http://example.org/ont#LegacyPerson"
    replaced_by: "http://example.org/ont#Agent"
    message: "Deprecated in v2.0. Use Agent for both people and organisations."
    version: "2.0.0"

  - entity: "http://example.org/ont#hasAddress"
    replaced_by: "http://example.org/ont#locatedAt"
    message: "Renamed for consistency with location vocabulary."

  - entity: "http://example.org/ont#TemporaryClass"
    # No replacement - just deprecated
    message: "Experimental class removed. No replacement available."
```

**Deprecation Output**:

When you deprecate an entity, the following triples are added:
```turtle
ex:LegacyTerm
    owl:deprecated true ;
    dcterms:isReplacedBy ex:NewTerm ;
    rdfs:comment "DEPRECATED (v2.0): Use NewTerm instead..."@en .
```

**Exit Codes**:
- `0`: Success
- `1`: Success with warnings (some entities not found)
- `2`: Error (file not found, parse error, etc.)

---

### cq-test - Run Competency Question Tests

Validate ontologies against SPARQL-based competency questions.

```bash
rdf-construct cq-test ONTOLOGY TEST_FILE [OPTIONS]
```

**Arguments**:
- `ONTOLOGY`: RDF ontology file to test
- `TEST_FILE`: YAML file containing competency question tests

**Options**:
- `-o, --output PATH`: Write output to file instead of stdout
- `-f, --format FORMAT`: Output format: `text`, `json`, `junit` (default: text)
- `-d, --data PATH`: Additional RDF data files (can specify multiple)
- `-t, --tag TAG`: Run only tests with this tag (can specify multiple)
- `-x, --exclude-tag TAG`: Skip tests with this tag (can specify multiple)
- `--fail-fast`: Stop on first failure
- `-v, --verbose`: Show query text and timing

**Test File Format**:

```yaml
prefixes:
  ex: http://example.org/

questions:
  - name: "Animal hierarchy exists"
    description: "Verify Animal is the root class"
    query: |
      ASK { ex:Animal a owl:Class }
    expect: true
    tags: [schema, required]

  - name: "Dogs are mammals"
    query: |
      SELECT ?dog WHERE {
        ?dog rdfs:subClassOf ex:Mammal
      }
    expect:
      contains:
        - dog: ex:Dog
```

**Examples**:

```bash
# Run all tests
rdf-construct cq-test ontology.ttl tests.yml

# Run tests with specific tag
rdf-construct cq-test ontology.ttl tests.yml --tag schema

# JUnit output for CI
rdf-construct cq-test ontology.ttl tests.yml --format junit -o results.xml

# Verbose output with timing
rdf-construct cq-test ontology.ttl tests.yml --verbose

# Stop on first failure
rdf-construct cq-test ontology.ttl tests.yml --fail-fast

# Include additional test data
rdf-construct cq-test ontology.ttl tests.yml -d test-data.ttl
```

**Exit Codes**:
- `0`: All tests passed
- `1`: One or more tests failed
- `2`: Error occurred (invalid file, parse error, etc.)

---

### stats - Compute Ontology Statistics

Compute and display comprehensive metrics about RDF ontologies.

```bash
rdf-construct stats FILE [FILE...] [OPTIONS]
```

**Arguments**:
- `FILE`: One or more RDF ontology files

**Options**:
- `-o, --output PATH`: Write output to file instead of stdout
- `-f, --format FORMAT`: Output format: `text`, `json`, `markdown`, `md` (default: text)
- `--compare`: Compare two ontology files (requires exactly 2 files)
- `--include CATEGORIES`: Include only these metric categories (comma-separated)
- `--exclude CATEGORIES`: Exclude these metric categories (comma-separated)

**Metric Categories**:
- `basic`: Counts (triples, classes, properties, individuals)
- `hierarchy`: Structure (depth, branching, orphans)
- `properties`: Coverage (domain, range, functional, symmetric)
- `documentation`: Labels and comments coverage
- `complexity`: Multiple inheritance, OWL axioms
- `connectivity`: Most connected class, isolated classes

**Examples**:

```bash
# Basic statistics
rdf-construct stats ontology.ttl

# JSON output for programmatic use
rdf-construct stats ontology.ttl --format json -o stats.json

# Markdown for documentation
rdf-construct stats ontology.ttl --format markdown >> README.md

# Compare two versions
rdf-construct stats v1.ttl v2.ttl --compare

# Only show specific categories
rdf-construct stats ontology.ttl --include basic,documentation

# Exclude some categories
rdf-construct stats ontology.ttl --exclude connectivity,complexity
```

**Exit Codes**:
- `0`: Success
- `1`: Error occurred

---

## Configuration Files

### UML Context Configuration

**File**: `uml_contexts.yml`

```yaml
contexts:
  context_name:
    description: "Human-readable description"

    # Class selection (choose one)
    root_classes:            # Start from roots, include descendants
      - prefix:Class1
      - prefix:Class2
    # OR
    focus_classes:           # Specific classes only
      - prefix:Class1

    include_descendants: true  # Include subclasses of selected classes
    max_depth: 3              # Limit descendant depth (null = unlimited)

    # Property handling
    properties:
      mode: domain_based     # domain_based | connected | explicit | all | none
      include:               # Whitelist (optional)
        - prefix:hasX
      exclude:               # Blacklist (optional)
        - prefix:internalProp

    # Instance handling
    instances:
      include:
        - prefix:Instance1
      show_class_membership: true
```

### Style Configuration

**File**: `uml_styles.yml`

```yaml
schemes:
  scheme_name:
    description: "Visual styling scheme"

    # Namespace-based colours
    namespace_colours:
      "http://example.org/": "#E8F4FD"
      "http://other.org/": "#FFF3E0"

    # Type-based colours
    type_colours:
      owl:Class: "#E3F2FD"
      rdfs:Class: "#E8F5E9"

    # Arrows
    arrows:
      inheritance: "--|>"
      object_property: "-->"
      datatype_property: "..>"

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
    arrow_direction: up       # or down, left, right
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

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (or no differences/issues) |
| `1` | General error (or differences/warnings/failures found) |
| `2` | Command line usage error (or errors found for lint) |

---

## Files and Directories

**Input Files**:
- `.ttl` - RDF/Turtle ontology files
- `.rdf`, `.owl` - RDF/XML ontology files
- `.yml` - YAML configuration files
- `.puml` - PlantUML diagram files

**Output Files**:
- `.puml` - PlantUML diagram files (from `uml` command)
- `.ttl` - Ordered RDF/Turtle files (from `order` command), SHACL shapes (from `shacl-gen`)
- `.json` - Statistics output, lint results, diff results
- `.md` - Markdown output (docs, stats)
- `.html` - HTML documentation (from `docs` command)
- `.xml` - JUnit XML (from `cq-test` command)

**Default Output Directories**:
- `diagrams/` - UML diagram output
- `src/ontology/` - Ordered RDF output
- `docs/` - Documentation output

---

## Common Workflows

### Diagram-First Ontology Design

```bash
# Design in PlantUML, generate RDF
rdf-construct puml2rdf design.puml -o ontology.ttl -n http://example.org/ont#

# Add manual annotations, then update from PlantUML
rdf-construct puml2rdf design.puml --merge ontology.ttl -o ontology.ttl

# Validate ontology quality
rdf-construct lint ontology.ttl --level strict
```

### Complete Quality Pipeline

```bash
# Lint, generate shapes, validate, test competency questions
rdf-construct lint ontology.ttl --format json -o lint.json
rdf-construct shacl-gen ontology.ttl -o shapes.ttl --level strict
pyshacl -s shapes.ttl -d test-data.ttl
rdf-construct cq-test ontology.ttl cq-tests.yml --format junit -o cq-results.xml
```

### Generate Complete Documentation

```bash
# HTML docs, UML diagrams, and SHACL shapes
rdf-construct docs ontology.ttl -o docs/api/
rdf-construct uml ontology.ttl -C contexts.yml -o docs/diagrams/
rdf-construct shacl-gen ontology.ttl -o docs/shapes.ttl
```

### Compare Ontology Versions

```bash
# Generate ordered versions
rdf-construct order v1.ttl order.yml -p canonical -o output/v1/
rdf-construct order v2.ttl order.yml -p canonical -o output/v2/

# Semantic diff
rdf-construct diff output/v1/v1-canonical.ttl output/v2/v2-canonical.ttl

# Or diff the originals directly
rdf-construct diff v1.ttl v2.ttl --format markdown -o RELEASE_NOTES.md
```

### Track Ontology Metrics

```bash
# Generate stats for CI pipeline
rdf-construct stats ontology.ttl --format json -o metrics.json

# Compare versions before release
rdf-construct stats v1.ttl v2.ttl --compare --format markdown >> CHANGELOG.md
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

---

## Tips

### Check Configuration

Before generating, list available contexts/profiles:

```bash
rdf-construct contexts config.yml
rdf-construct profiles order.yml
```

### Start Simple

Generate without styling first:

```bash
rdf-construct uml ontology.ttl -C config.yml -c simple_context
```

Then add styling once you're happy with the structure.

### Use Descriptive Names

In YAML configs:
- **Good**: `animal_taxonomy`, `management_structure`, `key_relationships`
- **Bad**: `context1`, `test`, `temp`

### Organise Output

Use subdirectories for different versions or audiences:

```bash
rdf-construct uml ontology.ttl -C config.yml -o docs/diagrams/public/
rdf-construct uml ontology.ttl -C config.yml -o docs/diagrams/internal/
```

---

## Troubleshooting

### "Command not found"

**Problem**: `rdf-construct: command not found`

**Solution**:
```bash
# If installed with Poetry
poetry run rdf-construct --version

# Or activate poetry shell
poetry shell
rdf-construct --version

# If installed with pip, check PATH
pip show rdf-construct
```

### "Context/Profile not found"

**Problem**: `Error: Context 'xyz' not found`

**Solution**: List available contexts/profiles:
```bash
rdf-construct contexts config.yml
rdf-construct profiles order.yml
```

### "File not found"

**Problem**: `Error: Path 'file.ttl' does not exist`

**Solution**: Check file path is correct:
```bash
ls -la file.ttl
# Use absolute path if needed
rdf-construct uml /full/path/to/file.ttl -C config.yml
```

### Empty Output

**Problem**: Generated file has no classes/properties.

**Solutions**:
1. Check CURIE format in config matches ontology prefixes
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

---

## Getting Help

```bash
rdf-construct --help
rdf-construct order --help
rdf-construct uml --help
rdf-construct docs --help
rdf-construct puml2rdf --help
rdf-construct shacl-gen --help
rdf-construct diff --help
rdf-construct lint --help
rdf-construct cq-test --help
rdf-construct stats --help
```

**Online Resources**:
- Issues: https://github.com/aigora-de/rdf-construct/issues
- Discussions: https://github.com/aigora-de/rdf-construct/discussions

---

## See Also

- **[Getting Started](GETTING_STARTED.md)**: Quick start guide
- **[Docs Guide](DOCS_GUIDE.md)**: Documentation generation
- **[UML Guide](UML_GUIDE.md)**: Complete UML features
- **[PlantUML Import Guide](PLANTUML_IMPORT_GUIDE.md)**: PlantUML to RDF conversion
- **[SHACL Guide](SHACL_GUIDE.md)**: SHACL shape generation
- **[Diff Guide](DIFF_GUIDE.md)**: Ontology comparison
- **[Lint Guide](LINT_GUIDE.md)**: Ontology quality checking
- **[CQ Testing Guide](CQ_TEST_GUIDE.md)**: Competency question testing
- **[Stats Guide](STATS_GUIDE.md)**: Ontology metrics and statistics