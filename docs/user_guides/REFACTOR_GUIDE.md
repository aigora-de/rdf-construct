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
| `--from-namespace NS` | Old namespace for bulk rename, matched at a namespace boundary (below) |
| `--to-namespace NS` | New namespace for bulk rename |
| `-c, --config FILE` | YAML configuration file |
| `-o, --output PATH` | Output file or directory |
| `--migrate-data FILE` | Data files to migrate (repeatable) |
| `--data-output PATH` | Output path for migrated data |
| `--in-place` | Allow `-o` or `--data-output` to name an input, and rewrite it with its own result |
| `--merge-entities` | Allow a rename that merges two entities (see [Renaming onto an Existing IRI](#renaming-onto-an-existing-iri)) |
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
overrides both. `-o` is read against the sources the run processes: source arguments replace the
config's `source_files:` first, so one source given with a config that lists two takes `-o` as a
file.

A rename that would write nothing is refused at exit 2:

```bash
rdf-construct refactor rename examples/refactor/typos.ttl --from ex:Buiding --to ex:Building
```

```text
Error: Nothing was written:
  no output was named, so the renamed ontology would be thrown away.
Pass -o FILE (-o DIR/ for several sources), or set output: or output_dir: in the config.
```

`--dry-run` writes nothing by design, so it needs no `-o`. A run with `--migrate-data` but no `-o`
writes only the migrated data, and says so on stderr:

```text
Note: no -o, so the renamed ontology is not written; only the migrated data is.
```

Every output path is worked out, and every source and data file read, before anything is written.
The run is refused at exit 2, with nothing written, when:

- two outputs would be the same file: two sources, or two data files, with the same name written
  into one directory (names that differ only in case count as the same), or a data output equal to
  an ontology output;
- an output would replace an input, unless `--in-place` is given and the input is the file the
  output is made from;
- a config's `output:` names one file for several sources;
- `-o` (or `--data-output`) names an existing directory for one input, or an existing file for
  several;
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

A namespace that ends in anything but a letter or a digit matches everything that starts with it:
`#`, `/` and `:`, and also a stem such as OBO's `http://purl.obolibrary.org/obo/GO_`, which moves
`GO_0008150`, or `http://example.org/items?id=`. One that ends in a letter or a digit matches
only where the next character is `#`, `/` or `:`, or where the IRI ends. So URN-style namespaces
work either way: `urn:old:` and `urn:old` both move `urn:old:A`, and neither moves `urn:older:C`.

An IRI's authority (its host, port and user information) is never divided. `http://example.org`
moves `http://example.org/ont#Y` but not `http://example.org:8080/a#X`, which is another server;
to move that one, name its port: `http://example.org:8080`.

When a config's `namespaces` overlap, each IRI moves by the **longest** rule that contains it,
whatever order the rules are written in, and moves once: an IRI is never moved again by a rule
its new IRI falls within. A prefix binding moves by the same rule as the terms in it. The run
names each pair of rules where one lies within the other:

```text
Note: http://e.org/core/sub/ lies within http://e.org/core/; each IRI moves by the longest rule that contains it.
```

### Renaming onto an Existing IRI

A rename onto an IRI that already has triples of its own would make two entities one: the result
carries both labels, both comments and both sets of axioms, and nothing in it says which came from
where. `refactor rename` refuses it at exit 2, before anything is written:

```bash
rdf-construct refactor rename examples/refactor/typos.ttl \
    --from ex:Addres --to ex:Structure -o collide.ttl
```

```text
Error: Nothing was written:
  1 rename would merge two entities:
  <http://example.org/ont#Structure> has 3 triples of its own in examples/refactor/typos.ttl; renaming <http://example.org/ont#Addres> onto it merges them.
Pass --merge-entities to merge them deliberately. To keep both, deprecate the old term instead:
  rdf-construct refactor deprecate examples/refactor/typos.ttl --entity 'http://example.org/ont#Addres' --replaced-by 'http://example.org/ont#Structure'
```

Three things are refused this way, each listed with the file it was found in:

| Refused | Why |
|---|---|
| A target that is a **subject** in a source, and is not itself renamed away | Its description and the renamed term's become one. A swap (`A → B`, `B → A`) and a chain (`A → B`, `B → C`) are fine: renames are simultaneous, so a target renamed away leaves nothing behind. |
| Two renames onto **one target** (`A → C`, `B → C`, from a config, or a namespace rule and an entity rename that land on one IRI) | Two entities become one by construction. |
| A rename that makes `owl:disjointWith`, `owl:propertyDisjointWith`, `owl:complementOf` or `owl:differentFrom` **reflexive** | The source said the two terms are kept apart. Renamed into one, a class is disjoint with itself (unsatisfiable), or an individual different from itself (an inconsistent ontology). |

The checks cover **every source of the run together**: renaming `ex:Buiding` in one module onto
an `ex:Building` that another module describes is refused, because the module set would describe
it twice. Each `--migrate-data` file is checked the same way, against the rename map the data is
migrated with. A mapping whose old IRI a file never mentions renames nothing there, and is never a
collision: re-running a typo fix over the already-fixed file is not refused. It exits 1, because
the fix [matched nothing](#a-rename-that-matches-nothing).

A term renamed onto an individual (punning) is refused too, although the triple count does not
change. Every collision is listed: a bulk namespace rename can collide in thousands of places, so
the first line gives the count.

**A target that is only referenced** — an object or a predicate, never a subject — is not a
collision. Renaming `ex:Buiding` onto an `ex:Building` that other axioms already mention is what a
rename is for. The run renames it and says so on stderr, because under the open world the target
may be described in a file the run never read:

```text
Note: <http://example.org/Building> was already referenced 2 times in ontology.ttl; those references now reach the renamed entity.
```

A rename that makes any other triple reflexive is reported the same way, and written. Some say
nothing (`C rdfs:subClassOf C`), but others are new claims — `P owl:inverseOf P` makes `P`
symmetric — so read each one:

```text
Note: <http://example.org/Building> rdfs:subClassOf <http://example.org/Building> is now reflexive (was <http://example.org/Buiding> rdfs:subClassOf <http://example.org/Building>).
```

**What to do instead.** If both terms should survive, deprecate the old one and point it at the
other, as the refusal suggests; `refactor deprecate` writes `typos_deprecated.ttl` beside the
source. If the two terms really are the same entity and both descriptions should be kept,
asserting `ex:Addres owl:sameAs ex:Structure` says exactly that, without losing which description
came from where. If one entity is what you want, merge deliberately:

```bash
rdf-construct refactor rename examples/refactor/typos.ttl \
    --from ex:Addres --to ex:Structure --merge-entities -o collide.ttl
```

The merge is written, and each one is named on stderr:

```text
⚠ Merged (--merge-entities): <http://example.org/ont#Structure> has 3 triples of its own in examples/refactor/typos.ttl; renaming <http://example.org/ont#Addres> onto it merges them.
```

In a config file, `merge_entities: true` under `rename:` does the same. `--merge-entities` can be
given with `-c`.

### A Rename That Matches Nothing

A mapping that renames nothing in **any** file of the run is listed on stderr after the run, which
exits 1, each with the reason. The files are judged together: in a module set most terms appear in only one or two
files, so a mapping absent from one file is normal. An entity mapping counts as matched if its old
IRI occurs in a source or in a `--migrate-data` file. A namespace rule counts if it moves at least
one IRI of the sources itself, not through a longer rule or an entity mapping. Namespace rules are
expanded from the sources only, so an IRI that only the data uses is not migrated, and a rule that
matches only the data is listed ([#471](https://github.com/aigora-de/rdf-construct/issues/471)). A mapping onto
itself renames nothing too.

```bash
rdf-construct refactor rename examples/refactor/typos.ttl \
    --from "http://example.org/ont#DoesNotExist" --to "http://example.org/ont#Nope" -o out.ttl
```

```text
⚠ 1 rename matched nothing:
  <http://example.org/ont#DoesNotExist> → <http://example.org/ont#Nope>: <http://example.org/ont#DoesNotExist> occurs in no file of the run.
```

The output is still written: exit 1 means the run finished with something to report. `--dry-run`
lists the same and exits the same way.

**Known limitations**

| Limitation | Issue |
|---|---|
| A contradiction through a list axiom — `owl:AllDisjointClasses`, `owl:AllDifferent`, `owl:AllDisjointProperties` or `owl:disjointUnionOf` naming both terms — is not detected, so the rename writes it. | [#467](https://github.com/aigora-de/rdf-construct/issues/467) |
| A rename's run time grows with mappings × triples (the scan for literal mentions): a namespace rename of 3,000 terms over 24,000 triples takes about 48 s. A refused run stops before that scan. | [#194](https://github.com/aigora-de/rdf-construct/issues/194) |

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

Each migrated file keeps its data file's own prefixes (`org:` stays `org:`), and a prefix moves
with its namespace. After `--from-namespace`, the data's own prefix for the old namespace is
written for the new one, as the ontology's is. A namespace the data uses without declaring it, as
in an N-Triples file, gets rdflib's usual prefix for it (`foaf:`) when no prefix of the data's
holds that name.

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

  # Merge two entities deliberately instead of refusing (--merge-entities)
  # merge_entities: true

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

A dry run checks for collisions too. It prints the preview and any notes, then refuses at exit 2
with the same list as the real run; with `--merge-entities` it names each merge it would make and
exits 0. It checks the planned outputs the same way, and exits 1 for a rename that matches nothing.

### Configuration and the Command Line

`-c` cannot be combined with an operation flag (`--from`, `--to`, `--from-namespace`,
`--to-namespace`). The run is refused at exit 2 before the config is read, naming each flag given.
Put the rename in the config's `rename:` section, or run it as a separate command. Settings combine
with `-c`: the sources, `-o`, `--dry-run`, `--no-colour`, `--migrate-data`, `--data-output`,
`--in-place` and `--merge-entities`.

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
| `-o, --output PATH` | Output file for one source, or directory for several |
| `--in-place` | Allow `-o` to name a source, and rewrite it with its own deprecations |
| `--dry-run` | Preview changes without writing |
| `--init` | Generate template configuration |

### Where Deprecated Output Goes

Without `-o`, each result is written beside its source as `<stem>_deprecated.ttl`. With one source,
`-o` names the output file; with several, a directory, where each result keeps its source's file
name. A config's `output:` and `output_dir:` work the same way, and `-o` overrides both. Every output
is worked out before anything is written, and the run is refused at exit 2 with nothing written
when:

- two outputs would be the same file;
- an output would replace a source, unless `--in-place` is given and it is that source's own result
  (`-o ontology.ttl --in-place`);
- `-o` names an existing directory for one source, or an existing file for several;
- a config's `output:` names one file for several sources.

`-c` cannot be combined with `--entity`, `--replaced-by`, `--message` or `--version`: put the
deprecation in the config's `deprecations:` section. `--message ""` counts as given.

**An entity is found if any source describes it** (has it as a subject). A module set declares a
term in one file and refers to it from others, so every source is processed and only an entity
that no source describes is reported, once, after every file is written:

```text
⚠ 1 entity is a subject in no source, so not deprecated:
  <http://example.org/ont#Nope>
```

That run exits 1, and so does its `--dry-run`. Every source is written, including those the run
did not change. The per-file summary still says "not found" for each
file that does not describe the entity.

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

# 2. Apply the change, and migrate the instance data with it
rdf-construct refactor rename ontology.ttl \
    --from "ex:Buiding" --to "ex:Building" \
    -o fixed.ttl \
    --migrate-data instances.ttl \
    --data-output updated_instances.ttl
```

Data found later can be migrated against the already-fixed ontology. Without `-o`, only the data is
written:

```bash
rdf-construct refactor rename fixed.ttl \
    --from "ex:Buiding" --to "ex:Building" \
    --migrate-data more_instances.ttl \
    --data-output updated_more_instances.ttl
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

# 2. Edit refactor_deprecate.yml with your deprecations

# 3. Preview
rdf-construct refactor deprecate ontology.ttl \
    --config refactor_deprecate.yml \
    --dry-run

# 4. Apply deprecations
rdf-construct refactor deprecate ontology.ttl \
    --config refactor_deprecate.yml \
    -o v2.0-with-deprecations.ttl
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Finished, with something to report: a rename that matched nothing in any file of the run, or an entity that no source describes. The outputs are written (with `--dry-run`, nothing is) |
| 2 | Input refused or run failed (invalid options or config, file not found, parse error, a rename that would merge two entities, nothing to write, an output over an input, `-c` with an operation flag) |

## See Also

- [MERGE_SPLIT_GUIDE.md](MERGE_SPLIT_GUIDE.md) - Merging multiple ontology files
- [CLI_REFERENCE.md](CLI_REFERENCE.md) - Complete CLI documentation
