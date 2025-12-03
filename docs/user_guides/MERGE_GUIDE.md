# Merge Guide

The `merge` command combines multiple RDF ontology files into a single output, with intelligent conflict detection, namespace management, and optional data migration.

## Quick Start

```bash
# Basic merge of two ontologies
rdf-construct merge core.ttl extension.ttl -o merged.ttl

# View what would happen without writing
rdf-construct merge core.ttl extension.ttl -o merged.ttl --dry-run

# Generate a starter configuration file
rdf-construct merge --init
```

## Use Cases

- **Combining modular ontologies** for deployment
- **Merging contributions** from multiple authors
- **Integrating external ontologies** into your project
- **Consolidating legacy ontologies** with different namespaces
- **Migrating instance data** when ontology structure changes

## CLI Reference

```bash
rdf-construct merge [OPTIONS] [SOURCES]...
```

### Arguments

| Argument | Description |
|----------|-------------|
| `SOURCES` | One or more RDF files to merge (.ttl, .rdf, .owl) |

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output PATH` | Output file (required) | - |
| `-c, --config PATH` | YAML configuration file | - |
| `-p, --priority INT` | Priority for each source (repeatable) | 1, 2, 3... |
| `--strategy` | Conflict resolution: `priority`, `first`, `last`, `mark_all` | `priority` |
| `-r, --report PATH` | Write conflict report | - |
| `--report-format` | Report format: `text`, `markdown` | `markdown` |
| `--imports` | owl:imports handling: `preserve`, `remove`, `merge` | `preserve` |
| `--migrate-data PATH` | Data file(s) to migrate (repeatable) | - |
| `--migration-rules PATH` | YAML file with migration rules | - |
| `--data-output PATH` | Output path for migrated data | - |
| `--dry-run` | Show what would happen without writing | `False` |
| `--no-colour` | Disable coloured output | `False` |
| `--init` | Generate default configuration file | - |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Merge successful, no unresolved conflicts |
| 1 | Merge successful, but unresolved conflicts marked in output |
| 2 | Error (file not found, parse error, etc.) |

## Conflict Detection

The merge command detects conflicts when:

1. **Same subject + predicate** has different values across sources
2. **Semantic contradictions** exist (e.g., disjoint + subclass)

### Conflict Types

| Type | Description | Example |
|------|-------------|---------|
| Value Difference | Different literal values | `rdfs:label "Building"` vs `"Structure"` |
| Type Difference | Different rdf:type declarations | `owl:Class` vs `rdfs:Class` |
| Hierarchy Difference | Different subClassOf | `ex:A` subClassOf `ex:B` vs `ex:C` |
| Semantic Contradiction | Logically incompatible | disjointWith + subClassOf |

### Resolution Strategies

#### Priority (default)

Higher priority source wins. Set priorities with `-p`:

```bash
# extension.ttl (priority 2) wins over core.ttl (priority 1)
rdf-construct merge core.ttl extension.ttl -o merged.ttl -p 1 -p 2
```

#### First / Last

First or last source encountered wins:

```bash
rdf-construct merge a.ttl b.ttl c.ttl -o merged.ttl --strategy first
rdf-construct merge a.ttl b.ttl c.ttl -o merged.ttl --strategy last
```

#### Mark All

Leave all conflicts unresolved for manual review:

```bash
rdf-construct merge core.ttl ext.ttl -o merged.ttl --strategy mark_all
```

### Conflict Markers

Unresolved conflicts are marked in the output file:

```turtle
# === CONFLICT: ex:Building rdfs:label ===
# Source: core.ttl (priority 1): "Building"@en
# Source: ext.ttl (priority 2): "Structure"@en
# Resolution: UNRESOLVED - values differ, manual review required
# To resolve: keep one value below, delete the other and this comment block
ex:Building a owl:Class ;
    rdfs:label "Building"@en ;      # from core.ttl
    rdfs:label "Structure"@en ;     # from ext.ttl - CONFLICT
    rdfs:subClassOf ex:PhysicalObject .
# === END CONFLICT ===
```

Find conflicts with `grep`:

```bash
grep -n "=== CONFLICT ===" merged.ttl
```

### Conflict Reports

Generate a detailed report:

```bash
rdf-construct merge core.ttl ext.ttl -o merged.ttl --report conflicts.md
```

The Markdown report includes:
- Summary statistics
- Unresolved conflicts with details
- Auto-resolved conflicts
- Recommendations

## Namespace Management

### Namespace Remapping

Remap namespaces during merge (via config file):

```yaml
sources:
  - path: legacy.ttl
    priority: 1
    namespace_remap:
      "http://old.example.org/": "http://example.org/"
```

### Preferred Prefixes

Standardise prefix bindings in output:

```yaml
namespaces:
  preferred_prefixes:
    ex: "http://example.org/"
    rdfs: "http://www.w3.org/2000/01/rdf-schema#"
```

## owl:imports Handling

Control how `owl:imports` statements are handled:

```bash
# Keep all imports from all sources (default)
rdf-construct merge ... --imports preserve

# Remove all imports
rdf-construct merge ... --imports remove

# Deduplicate imports
rdf-construct merge ... --imports merge
```

## Data Migration

When ontology structure changes, instance data may need updates.

### Simple Migration (URI Substitution)

When namespaces are remapped, instance data can be automatically migrated:

```bash
rdf-construct merge core.ttl ext.ttl -o merged.ttl \
    --migrate-data instances.ttl \
    --data-output migrated.ttl
```

### Complex Migration (Transformation Rules)

For structural changes, define migration rules in YAML:

```yaml
# migration-rules.yml
migrations:
  # Simple rename
  - type: rename
    from: "http://old.example.org/ont#LegacyClass"
    to: "http://example.org/ont#ModernClass"
    description: "Rename legacy class"

  # Property split
  - type: transform
    description: "Split fullName into givenName and familyName"
    match: "?s ex:fullName ?name"
    construct:
      - pattern: "?s ex:givenName ?given"
        bind: "STRBEFORE(?name, ' ') AS ?given"
      - pattern: "?s ex:familyName ?family"
        bind: "STRAFTER(?name, ' ') AS ?family"
    delete_matched: true

  # Type migration
  - type: transform
    description: "Migrate Company to Organisation"
    match: "?s a ex:Company"
    construct:
      - pattern: "?s a ex:Organisation"
      - pattern: "?s ex:organisationType ex:Commercial"
    delete_matched: true
```

Apply with:

```bash
rdf-construct merge core.ttl ext.ttl -o merged.ttl \
    --migrate-data data/*.ttl \
    --migration-rules migration-rules.yml \
    --data-output migrated/
```

### Supported Transformations

| Function | Description | Example |
|----------|-------------|---------|
| `STRBEFORE` | Substring before delimiter | `STRBEFORE(?name, ' ')` |
| `STRAFTER` | Substring after delimiter | `STRAFTER(?name, ', ')` |
| Arithmetic | Basic math operations | `((?f - 32) * 5/9)` |

## Configuration File

For complex merges, use a YAML configuration file:

```yaml
# merge.yml

# Source files with priorities
sources:
  - path: core.ttl
    priority: 1
  - path: domain/buildings.ttl
    priority: 2
  - path: domain/people.ttl
    priority: 2
  - path: extensions.ttl
    priority: 3
    namespace_remap:
      "http://legacy.example.org/": "http://example.org/"

# Output configuration
output:
  path: merged.ttl
  format: turtle

# Namespace handling
namespaces:
  base: "http://example.org/"
  preferred_prefixes:
    ex: "http://example.org/"
    ies: "http://ies.data.gov.uk/ontology/ies4#"

# Conflict resolution
conflicts:
  strategy: priority
  report: reports/conflicts.md
  ignore_predicates:
    - "http://www.w3.org/2000/01/rdf-schema#isDefinedBy"

# owl:imports handling
imports: merge

# Data migration
migrate_data:
  sources:
    - data/instances.ttl
    - data/relationships.ttl
  output: data/migrated.ttl
  rules_file: migration-rules.yml
```

Use with:

```bash
rdf-construct merge --config merge.yml
```

## Examples

### Merge with Priorities

```bash
# Core ontology has priority 1, extensions have priority 2
rdf-construct merge \
    core.ttl \
    ext/buildings.ttl \
    ext/people.ttl \
    -o merged.ttl \
    -p 1 -p 2 -p 2
```

### Generate Conflict Report

```bash
rdf-construct merge core.ttl ext.ttl -o merged.ttl \
    --strategy mark_all \
    --report conflicts.md

# Review and resolve
grep -n "CONFLICT" merged.ttl
```

### Migrate Data with Namespace Change

```bash
# Using config with namespace remapping
rdf-construct merge --config migrate-config.yml
```

### Dry Run for CI/CD

```bash
# Check for conflicts without writing
rdf-construct merge core.ttl ext.ttl -o merged.ttl --dry-run

# Exit code 0 = no conflicts, 1 = conflicts, 2 = error
echo "Exit code: $?"
```

## Best Practices

1. **Start with dry run** to preview conflicts before committing
2. **Use consistent priorities** - higher numbers for more authoritative sources
3. **Generate conflict reports** for team review
4. **Version control** your merge configuration
5. **Run `lint`** on merged output to catch issues
6. **Test data migration** on a sample before full migration

## Troubleshooting

### "No conflicts but labels differ"

Some predicates like `rdfs:comment` may have multiple values legitimately. Use `--ignore-predicates` (in config) to skip these.

### "Parse error on source file"

Ensure source files are valid RDF. Run `rdf-construct lint` first.

### "Too many unresolved conflicts"

Consider:
- Using `--strategy priority` with clear priority ordering
- Breaking large merges into smaller steps
- Using configuration file for fine-grained control

## Related Commands

- `rdf-construct lint` - Check merged output for quality issues
- `rdf-construct diff` - Compare merged result with original
- `rdf-construct docs` - Generate documentation for merged ontology
