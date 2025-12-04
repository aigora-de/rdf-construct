# Refactor Guide

The `refactor` command provides tools for common ontology maintenance tasks:
renaming URIs (fixing typos, changing namespaces) and deprecating entities
with proper OWL annotations.

## Overview

```bash
rdf-construct refactor <subcommand> [options]
```

### Subcommands

- **`rename`** - Rename URIs (single entity or bulk namespace)
- **`deprecate`** - Mark entities as deprecated with OWL annotations

## Rename Subcommand

Use `refactor rename` to fix typos in URIs or migrate to new namespaces.

### Quick Start

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
```

### Options

| Option | Description |
|--------|-------------|
| `--from URI` | Single URI to rename |
| `--to URI` | New URI for single rename |
| `--from-namespace NS` | Old namespace prefix for bulk rename |
| `--to-namespace NS` | New namespace prefix for bulk rename |
| `-c, --config FILE` | YAML configuration file |
| `-o, --output PATH` | Output file or directory |
| `--migrate-data FILE` | Data files to migrate (repeatable) |
| `--data-output PATH` | Output path for migrated data |
| `--dry-run` | Preview changes without writing |
| `--init` | Generate template configuration |

### Rename Behaviour

1. **Subject, predicate, and object positions** are all renamed
2. **Literals are NOT modified** - text mentioning old URIs in comments is preserved
3. **Namespace bindings** are updated to reflect new namespaces

### With Data Migration

When renaming entities, you often need to update instance data as well:

```bash
rdf-construct refactor rename ontology.ttl \
    --from "http://example.org/ont#OldClass" \
    --to "http://example.org/ont#NewClass" \
    --migrate-data instances.ttl \
    --data-output updated-instances.ttl \
    -o fixed.ttl
```

### Configuration File

For complex renames, use a YAML configuration:

```yaml
# refactor_rename.yml
source_files:
  - ontology.ttl

output: renamed.ttl

rename:
  # Namespace mappings (applied first)
  namespaces:
    "http://old.example.org/v1#": "http://example.org/v2#"
    "http://temp.local/": "http://example.org/v2#"

  # Individual entity renames (applied after namespace)
  entities:
    # Fix typos
    "http://example.org/v2#Buiding": "http://example.org/v2#Building"
    "http://example.org/v2#hasAddres": "http://example.org/v2#hasAddress"

# Optional data migration
migrate_data:
  sources:
    - data/*.ttl
  output_dir: data/migrated/
```

Run with:

```bash
rdf-construct refactor rename --config refactor_rename.yml
```

### Dry Run

Preview changes before applying:

```bash
rdf-construct refactor rename ontology.ttl \
    --from "ex:Old" --to "ex:New" \
    --dry-run
```

Output:
```
Refactoring Preview: Rename
===========================

Source: ontology.ttl (1,247 triples)

Entity renames:
  Old → New
    └─ 12 literal mention(s) (NOT changed)

Totals:
  - 1 entities to rename
  - 1 from explicit rules

Run without --dry-run to apply changes.
```

## Deprecate Subcommand

Use `refactor deprecate` to mark entities as deprecated with proper OWL annotations.

### Quick Start

```bash
# Deprecate with replacement
rdf-construct refactor deprecate ontology.ttl \
    --entity "http://example.org/ont#LegacyTerm" \
    --replaced-by "http://example.org/ont#NewTerm" \
    --message "Use NewTerm instead. Will be removed in v3.0." \
    -o updated.ttl

# Deprecate without replacement
rdf-construct refactor deprecate ontology.ttl \
    --entity "http://example.org/ont#ObsoleteThing" \
    --message "No longer needed." \
    -o updated.ttl
```

### Options

| Option | Description |
|--------|-------------|
| `--entity URI` | URI of entity to deprecate |
| `--replaced-by URI` | URI of replacement entity |
| `-m, --message TEXT` | Deprecation message |
| `--version VERSION` | Version when deprecated |
| `-c, --config FILE` | YAML configuration file |
| `-o, --output PATH` | Output file |
| `--dry-run` | Preview changes without writing |
| `--init` | Generate template configuration |

### Deprecation Annotations Added

When you deprecate an entity, the following triples are added:

```turtle
ex:LegacyTerm
    owl:deprecated true ;
    dcterms:isReplacedBy ex:NewTerm ;  # if replacement specified
    rdfs:comment "DEPRECATED: Use NewTerm instead..."@en .
```

### Bulk Deprecation

For deprecating multiple entities, use a configuration file:

```yaml
# deprecations.yml
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

Run with:

```bash
rdf-construct refactor deprecate --config deprecations.yml
```

### Important Note

**Deprecation marks entities but does NOT rename or migrate references.**

References to deprecated entities throughout your ontology and data remain
unchanged. This is intentional - deprecation is about backward compatibility,
allowing consumers to see what's deprecated and what to use instead.

If you want to actually migrate references, use `refactor rename` after
deprecating:

```bash
# First deprecate (for backward compatibility)
rdf-construct refactor deprecate ontology.ttl \
    --entity "ex:OldClass" \
    --replaced-by "ex:NewClass" \
    -o deprecated.ttl

# Then rename references (for actual migration)
rdf-construct refactor rename deprecated.ttl \
    --from "ex:OldClass" \
    --to "ex:NewClass" \
    --migrate-data instances.ttl \
    -o migrated.ttl
```

## Workflow Examples

### Fixing a Typo

```bash
# 1. Preview the change
rdf-construct refactor rename ontology.ttl \
    --from "ex:Buiding" --to "ex:Building" \
    --dry-run

# 2. Apply the change
rdf-construct refactor rename ontology.ttl \
    --from "ex:Buiding" --to "ex:Building" \
    -o fixed.ttl

# 3. Migrate instance data
rdf-construct refactor rename fixed.ttl \
    --from "ex:Buiding" --to "ex:Building" \
    --migrate-data instances.ttl \
    --data-output updated_instances.ttl
```

### Project Namespace Migration

```bash
# 1. Preview namespace changes
rdf-construct refactor rename modules/*.ttl \
    --from-namespace "http://company.internal/" \
    --to-namespace "https://company.example.org/" \
    --dry-run

# 2. Apply changes to all modules
rdf-construct refactor rename modules/*.ttl \
    --from-namespace "http://company.internal/" \
    --to-namespace "https://company.example.org/" \
    -o migrated/
```

### Deprecation Workflow

```bash
# 1. Create deprecation config
rdf-construct refactor deprecate --init

# 2. Edit deprecations.yml with your deprecations

# 3. Preview
rdf-construct refactor deprecate ontology.ttl \
    --config deprecations.yml \
    --dry-run

# 4. Apply deprecations
rdf-construct refactor deprecate ontology.ttl \
    --config deprecations.yml \
    -o v2.0-with-deprecations.ttl
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Success with warnings (e.g., some URIs not found) |
| 2 | Error (file not found, parse error, invalid config) |

## See Also

- [MERGE_GUIDE.md](MERGE_GUIDE.md) - Merging multiple ontology files
- [CLI_REFERENCE.md](CLI_REFERENCE.md) - Complete CLI documentation