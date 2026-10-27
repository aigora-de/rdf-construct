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
| `--from URI` | Single URI or CURIE to rename |
| `--to URI` | New URI or CURIE for single rename |
| `--from-namespace NS` | Old namespace for bulk rename, matched at a `#`, `/` or `:` boundary |
| `--to-namespace NS` | New namespace for bulk rename |
| `-c, --config FILE` | YAML configuration file |
| `-o, --output PATH` | Output file or directory |
| `--migrate-data FILE` | Data files to migrate (repeatable) |
| `--data-output PATH` | Output path for migrated data |
| `--in-place` | Allow `-o` or `--data-output` to name an input, and rewrite it with its own result |
| `--dry-run` | Preview changes without writing |
| `--init` | Generate template configuration |

### Rename Behaviour

1. **Subject, predicate, and object positions** are all renamed
2. **Literals are NOT modified** - text mentioning old URIs in comments is preserved
3. **Namespace bindings** are updated to reflect new namespaces, and the source's own prefixes
   are written back as declared (`org:` stays `org:`)

### Where Output Goes

`-o` names the output file for one source, or a directory for several, where each result keeps
its source's file name. `--data-output` works the same way for the data files given to
`--migrate-data`; without it, each migrated file is written beside its data file as
`migrated_<name>`. A config file's `output:` names one file and `output_dir:` a directory; `-o`
overrides both. Without `-o` or a config `output:`, a single source is renamed and nothing is
written.

Every output path is worked out, and every source and data file read, before anything is written.
The run is refused at exit 2, with nothing written, when:

- two outputs would be the same file: two sources, or two data files, with the same name written
  into one directory (names that differ only in case count as the same), or a data output equal to
  an ontology output;
- an output would replace an input, unless `--in-place` is given and the input is the file the
  output is made from;
- a config's `output:` names one file for several sources;
- a data file cannot be parsed.

Paths are compared as files, so a symbolic link or a `..` reaches the same file it points at:

```bash
rdf-construct refactor rename examples/refactor/typos.ttl \
    --from ex:Buiding --to ex:Building -o examples/refactor/typos.ttl
```

```
Error: Nothing was written:
  examples/refactor/typos.ttl is the input it is made from: writing it would replace that file. Pass --in-place to rewrite it, or choose another path.
```

With `--in-place`, each source named by `-o` (directly, or as the directory it is in) is rewritten
with its own rename, and the data file named by `--data-output` with its own migration. Each one
replaced is reported on stderr as `⚠ Replaced <path>`. An output that would replace a *different*
input, such as `--data-output` naming the ontology, is refused even with `--in-place`.

### CURIEs and Namespace Boundaries

`--from`, `--to`, `--entity`, `--replaced-by` and the entity keys and values in a configuration
file all accept a CURIE. A CURIE resolves against the prefixes the source file declares, plus
`rdf`, `rdfs`, `owl`, `xsd` and `xml`. It never uses rdflib's built-in prefix table, so a file
that declares its own `org:` gets its own `org:`, not the W3C Organization ontology.

A prefix is refused at exit 2, before anything is written, when:

- no source declares it (`ex:Building` in a file without `@prefix ex:`), or
- two sources declare it with different namespaces.

To give an IRI without `://`, such as a URN, write it in angle brackets: `<urn:isbn:0451450523>`.
A bare `urn:isbn:0451450523` reads as a CURIE whose `urn:` prefix is missing.

`--from-namespace` matches at a namespace boundary:

| `--from-namespace` | `…/ont#One` | `…/ont/extra#Three` | `…/ont` (the IRI itself) | `…/ontology#Two` |
|---|---|---|---|---|
| `http://example.org/ont` | moved | moved | moved | kept |
| `http://example.org/ont#` | moved | kept | kept | kept |
| `http://example.org/` | moved | moved | moved | moved |

A namespace that ends in `#`, `/` or `:` matches everything that starts with it. One without a
delimiter matches only where the next character is `#`, `/` or `:`, or where the IRI ends. So
URN-style namespaces work either way: `urn:old:` and `urn:old` both move `urn:old:A`, and neither
moves `urn:older:C`.

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

The data's rename map is built from the sources as they were read, so a rename written back over
its own source (`-o ontology.ttl --in-place`) migrates the same data as one written elsewhere.
Each renamed IRI moves wherever the data uses it: as a subject, as an object, or as a predicate.
Renaming a property therefore moves every triple that uses it, and a namespace rename moves the
data's properties in that namespace as well as its classes. The line printed for each data file
counts every substitution. The shipped `examples/refactor/renames.yml` fixes four typos, one of them
the property `ex:hasAddres`, and migrating `examples/refactor/instances.ttl` with it reports
`Migrated instances.ttl: 7 changes`, two of them the `ex:hasAddres` triples.

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
| 1 | `deprecate` only: success, but some entities were not found |
| 2 | Input refused or run failed (invalid options or config, file not found, parse error) |

## See Also

- [MERGE_SPLIT_GUIDE.md](MERGE_SPLIT_GUIDE.md) - Merging multiple ontology files
- [CLI_REFERENCE.md](CLI_REFERENCE.md) - Complete CLI documentation
