# Merge & Split Guide

This guide covers two complementary commands for managing ontology modules:
- **merge**: Combine multiple ontologies into one
- **split**: Divide a monolithic ontology into modules

## Merge Command

The `merge` command combines multiple RDF ontology files into a single output, with intelligent conflict detection, namespace management, and optional data migration.

### Quick Start

```bash
# Basic merge of two ontologies
rdf-construct merge core.ttl extension.ttl -o merged.ttl

# View what would happen without writing
rdf-construct merge core.ttl extension.ttl -o merged.ttl --dry-run

# Generate a starter configuration file
rdf-construct merge --init
```

### Use Cases

- **Combining modular ontologies** for deployment
- **Merging contributions** from multiple authors
- **Integrating external ontologies** into your project
- **Consolidating legacy ontologies** with different namespaces
- **Migrating instance data** when ontology structure changes

### CLI Reference

```bash
rdf-construct merge [OPTIONS] [SOURCES]...
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `SOURCES` | One or more RDF files to merge (.ttl, .rdf, .owl) |

#### Options

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

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Merged; every conflict was resolved by `--strategy`, or there were none |
| 1 | Merged, with conflicts marked in the output for review: always for `rdfs:domain`, `rdfs:range` and functional properties; for labels under `mark_all`, or when the highest-priority sources are tied |
| 2 | Input refused or run failed (invalid options or config, file not found, parse error) |

### Conflict Detection

A conflict is a place where the sources disagree **and** a second value would change what the
merged ontology says. Two things must both be true:

1. **The sources disagree.** For one subject and predicate (and, for labels, one language tag),
   merging them would assert a combination of values that no single source asserts. So two values
   from one source are never a conflict, a source that says nothing is not a disagreement, and a
   source whose values are a subset of another's agrees with it. A file merged alone, or with
   itself, has no conflicts.
2. **The predicate's tier makes a second value a conflict.** Under the open-world assumption most
   predicates take any number of values, so only the predicates below can conflict at all:

| Tier | Predicates | A second value is | Behaviour |
|------|------------|-------------------|-----------|
| repeatable | `rdfs:comment`, `skos:altLabel`, `skos:note`, `rdfs:seeAlso`, `rdf:type`, `rdfs:subClassOf` and **every predicate not listed here** | another assertion | keep both, report nothing |
| per language tag | `rdfs:label`, `skos:prefLabel` | a conflict only within one tag | `--strategy` picks, per tag |
| load-bearing | `rdfs:domain`, `rdfs:range`, and any property a source declares `owl:FunctionalProperty` | a change of meaning | marked under every strategy, never picked |

A correctly multilingual file is not a conflict:

```bash
rdf-construct merge tests/fixtures/merge/conflicts/multilang.ttl \
    tests/fixtures/merge/conflicts/multilang.ttl -o merged.ttl --strategy mark_all
```

```
✓ No conflicts detected
```

Language tags are compared without regard to case (`@en-GB` and `@en-gb` are one tag), and an
untagged literal is its own bucket. Subtags are not matched: `@en` and `@en-gb` are different tags.

The conflict types say why a second value matters:

| Type | Tier | Meaning |
|------|------|---------|
| Ambiguous | per language | Two `rdfs:label`s in one tag are legal RDF, but a reader cannot tell which is the name |
| Malformed | per language | Two `skos:prefLabel`s in one tag break SKOS integrity condition S14 |
| Changes meaning | load-bearing | Two `rdfs:domain` or `rdfs:range` values mean their intersection, which no source said; two values of a functional property make the ontology inconsistent (literals) or the values one individual (IRIs) |

`merge` does not reason. It does not check one predicate against another (such as a class that is
both `owl:disjointWith` and `rdfs:subClassOf` another); run a reasoner over the merged output for
that.

#### Moving a predicate between tiers

The tiers can be overridden in the configuration file, by full IRI:

```yaml
conflicts:
  ignore_predicates:            # never a conflict: the same as repeatable
    - "http://www.w3.org/2000/01/rdf-schema#isDefinedBy"
  predicate_tiers:
    repeatable:   ["http://www.w3.org/2000/01/rdf-schema#label"]
    per_language: ["http://purl.org/dc/terms/title"]
    load_bearing: ["<http://example.org/maxOccupancy>"]
```

The configuration wins over the defaults and over a source's `owl:FunctionalProperty`
declaration. A predicate placed in two tiers, an unknown tier name, or a prefixed name such as
`rdfs:label` is refused with exit 2.

#### Resolution Strategies

`--strategy` decides the per-language tier. The winner is a source: its values for that subject,
predicate and tag are kept, and the values only the other sources assert are **removed from the
output**. Load-bearing conflicts are never picked.

| Strategy | Keeps the values of |
|----------|---------------------|
| `priority` (default) | the highest-priority source that asserts them; set priorities with `-p` |
| `first` | the first source, in command-line order, that asserts them |
| `last` | the last source that asserts them |
| `mark_all` | nobody: every conflict is marked and every value kept |

Three sources disagree on an English label and agree on the French one:

```bash
rdf-construct merge tests/fixtures/merge/conflicts/labels_a.ttl \
    tests/fixtures/merge/conflicts/labels_b.ttl \
    tests/fixtures/merge/conflicts/labels_c.ttl \
    -p 1 -p 3 -p 2 --strategy priority -o merged.ttl
```

```turtle
ex:Thing a owl:Class ;
    rdfs:label "Beta"@en,
        "Chose"@fr ;
    rdfs:comment "Said by a."@en,
        "Said by b."@en,
        "Said by c."@en .
```

`first` keeps `"Alpha"@en`, `last` keeps `"Gamma"@en`, and `mark_all` keeps all three and exits 1.
The comments are repeatable, so all three stay under every strategy.

**Tied priorities are not picked between.** When the highest-priority sources that assert a value
disagree with each other, the conflict is marked and the run exits 1. A configuration file whose
sources have no `priority:` gives every source priority 1, so give them different priorities, or
use `--strategy first` or `last` to decide by order.

#### Conflict Markers

Every conflict that was not picked is listed in a comment block at the top of the output file:

```bash
rdf-construct merge tests/fixtures/merge/conflicts/domain_range_a.ttl \
    tests/fixtures/merge/conflicts/domain_range_b.ttl -o merged.ttl
```

```turtle
# === CONFLICT: ex:hasPart rdfs:domain ===
# Source: tests/fixtures/merge/conflicts/domain_range_a.ttl (priority 1): http://example.org/Assembly
# Source: tests/fixtures/merge/conflicts/domain_range_b.ttl (priority 2): http://example.org/Machine
# Changes meaning: two rdfs:domain values mean their intersection, which no source said; both are kept.
# Not picked under any --strategy.
# To resolve: if every value is meant, delete this block; otherwise delete the value you do not mean, then this block.
# === END CONFLICT ===
```

The triples stay as the sources stated them, so both domains are in the file:

```turtle
ex:hasPart a owl:ObjectProperty ;
    rdfs:domain ex:Assembly,
        ex:Machine ;
    rdfs:range ex:Component,
        ex:Part .
```

A per-language conflict under `mark_all` says which kind it is:

```turtle
# === CONFLICT: ex:car skos:prefLabel ===
# Source: tests/fixtures/merge/conflicts/preflabel_a.ttl (priority 1): "Car"@en
# Source: tests/fixtures/merge/conflicts/preflabel_b.ttl (priority 2): "Automobile"@en
# Malformed: SKOS allows one skos:prefLabel per language tag (S14), and the merged values tagged @en are more than one; both are kept.
# Not picked: --strategy mark_all marks every conflict.
# To resolve: keep one, or demote the others to skos:altLabel, then delete this block.
# === END CONFLICT ===
```

A marker lists only the values the sources do not all share. Find conflicts with `grep`:

```bash
grep -n "=== CONFLICT" merged.ttl
```

#### Conflict Reports

Generate a detailed report:

```bash
rdf-construct merge examples/merge/merge_core.ttl examples/merge/merge_conflicting.ttl \
    -o merged.ttl --report conflicts.md
```

The Markdown report includes:
- Summary statistics
- Unresolved conflicts, with the reason each was not picked
- Resolved conflicts, with the values kept and the values discarded (which are not in the output)
- Recommendations

#### Known limitations

| Limitation | Issue |
|------------|-------|
| The ontology header (`owl:Ontology` subjects) is not checked: two sources' header labels are both written | #171 |
| Predicates in the configuration must be full IRIs; prefixed names are refused rather than resolved | #357 |
| Conflict markers come out in a different order from run to run | #173 |
| Values are compared as written, so `"1.0"` and `"1.00"` (`xsd:decimal`) on a functional property are reported as a conflict | — |

### Blank Nodes

A blank node has no identity outside the file it is in, so `merge` decides when two of them are the
same. A blank-node structure, such as a restriction, an `owl:unionOf` list or an
`owl:AllDisjointClasses`, that two sources state identically, referred to by the same subject and
predicate, is written once:

```turtle
# In both core.ttl and module.ttl: the merge writes this restriction once
ex:A rdfs:subClassOf [ a owl:Restriction ;
        owl:onProperty ex:pA ;
        owl:someValuesFrom ex:B ] .
```

Merging a file with itself gives the file back, with no conflicts.

Everything else is kept apart:

- **The same restriction under two classes** is two restrictions. Nothing says `ex:A`'s and
  `ex:F`'s are one node.
- **`[ foaf:name "Eve" ]` known by two different people** is two people called Eve.
- **A structure that differs at all**, such as one carrying an `rdfs:comment` the other lacks, or
  a list in a different order, is a different structure, and both are written.
- **A structure stated twice in one source** is written twice, so a file merged with itself, or
  alone, is unchanged.

Blank nodes are compared after namespace remapping, so a remapped source shares its structures
with the sources it is merged with. A blank node `merge` writes with a label (`_:b…`, used when
more than one triple refers to it) is labelled from its content, so the label is the same on every
run.

**Not handled:** `merge` does not remove a structure that is merely implied by another. If one
source refers to a node from two subjects and another source gives each subject its own copy, all
three are written. Removing that kind of redundancy is a separate, much harder problem (finding a
graph's *lean* core).

### Namespace Management

#### Namespace Remapping

Remap namespaces during merge (via config file):

```yaml
sources:
  - path: legacy.ttl
    priority: 1
    namespace_remap:
      "http://old.example.org/": "http://example.org/"
```

A key ending in `#`, `/` or `:` matches every IRI that starts with it. A key without one matches
only at a namespace boundary: `http://example.org/ont` remaps `…/ont#One` and `…/ont/extra#Three`, but
not `…/ontology#Two`. Prefix bindings move with the namespaces they name.

#### Preferred Prefixes

Standardise prefix bindings in output:

```yaml
namespaces:
  preferred_prefixes:
    ex: "http://example.org/"
    rdfs: "http://www.w3.org/2000/01/rdf-schema#"
```

### owl:imports Handling

Control how `owl:imports` statements are handled:

```bash
# Keep all imports from all sources (default)
rdf-construct merge ... --imports preserve

# Remove all imports
rdf-construct merge ... --imports remove

# Deduplicate imports
rdf-construct merge ... --imports merge
```

### Data Migration

When ontology structure changes, instance data may need updates.

#### Simple Migration (URI Substitution)

When namespaces are remapped, instance data can be automatically migrated:

```bash
rdf-construct merge core.ttl ext.ttl -o merged.ttl \
    --migrate-data split_instances.ttl \
    --data-output migrated.ttl
```

#### Complex Migration (Transformation Rules)

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

### Configuration File

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
    - data/split_instances.ttl
    - data/relationships.ttl
  output: data/migrated.ttl
  rules_file: migration-rules.yml
```

Use with:

```bash
rdf-construct merge --config merge.yml
```

### Merge Examples

#### Merge with Priorities

```bash
# Core ontology has priority 1, extensions have priority 2
rdf-construct merge \
    core.ttl \
    ext/buildings.ttl \
    ext/people.ttl \
    -o merged.ttl \
    -p 1 -p 2 -p 2
```

The two extensions share priority 2, so where they disagree with each other on a label, the
conflict is marked rather than picked.

#### Generate Conflict Report

```bash
rdf-construct merge core.ttl ext.ttl -o merged.ttl \
    --strategy mark_all \
    --report conflicts.md

# Review and resolve
grep -n "CONFLICT" merged.ttl
```

#### Migrate Data with Namespace Change

```bash
# Using config with namespace remapping
rdf-construct merge --config migrate-config.yml
```

#### Dry Run for CI/CD

```bash
# Check for conflicts without writing
rdf-construct merge core.ttl ext.ttl -o merged.ttl --dry-run

# Exit code 0 = merged, 1 = conflicts marked for review, 2 = refused or failed
echo "Exit code: $?"
```

### Merge Best Practices

1. **Start with dry run** to preview conflicts before committing
2. **Use consistent priorities** - higher numbers for more authoritative sources
3. **Generate conflict reports** for team review
4. **Version control** your merge configuration
5. **Run `lint`** on merged output to catch issues
6. **Test data migration** on a sample before full migration

---

## Split Command

The `split` command is the inverse of `merge` — it takes a monolithic ontology and splits it into multiple modules.

### Quick Start

```bash
# Split by namespace (auto-detect modules)
rdf-construct split large.ttl -o modules/ --by-namespace

# Split using configuration file
rdf-construct split large.ttl -o modules/ -c split.yml

# Generate a starter configuration file
rdf-construct split --init
```

### Use Cases

- **Modularising large ontologies** for better maintainability
- **Creating domain-specific modules** from a unified ontology
- **Enabling selective imports** (load only what you need)
- **Supporting parallel development** by different teams
- **Migrating instance data** to match new module structure

### CLI Reference

```bash
rdf-construct split SOURCE [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `SOURCE` | RDF ontology file to split (.ttl, .rdf, .owl) |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output PATH` | Output directory for modules | `modules/` |
| `--overwrite` | Write into `modules/` even if it holds files `split` did not write. Deletes nothing. | `False` |
| `-c, --config PATH` | YAML configuration file | - |
| `--by-namespace` | Auto-detect modules from namespaces | `False` |
| `--migrate-data PATH` | Data file(s) to split (repeatable) | - |
| `--data-output PATH` | Output directory for split data | - |
| `--unmatched` | Strategy: `common` or `error` | `common` |
| `--common-name` | Name for common module | `common` |
| `--no-manifest` | Don't generate manifest.yml | `False` |
| `--dry-run` | Show what would happen without writing | `False` |
| `--no-colour` | Disable coloured output | `False` |
| `--init` | Generate default configuration file | - |

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Split successful |
| 1 | Split successful, unmatched entities in common module |
| 2 | Input refused or run failed (invalid options or config, file not found, parse error) |

### When `modules/` already holds other files

Without `-o`, `split` writes into `modules/` only if the directory is new, empty, or was written by
`split` before. Every run that writes leaves a small `.rdf-construct` file there, naming the
command and the version, and that marker is how a later run knows the directory is its own. A
directory holding anything else is refused at exit 2 before the source is parsed, and nothing is
written ([#261](https://github.com/aigora-de/rdf-construct/issues/261)):

```
Error: modules/ already holds files that rdf-construct split did not write (core.ttl). Leaving it untouched. Pass -o <dir> to write somewhere else, or --overwrite to write into modules/ anyway.
```

`--overwrite` writes there anyway and marks the directory, so it is needed once. It deletes
nothing: `core.ttl` stays. An explicit `-o` is never refused. Files an operating system leaves in
any folder (`.DS_Store`, `Thumbs.db`, `desktop.ini`, `.directory`) and a `.gitkeep` do not count.
A directory a v0.6.0 run wrote has no marker, so the first v0.7.0 run into it is refused.

`--dry-run` is refused the same way, so a preview never promises a run that would refuse. Until
[#291](https://github.com/aigora-de/rdf-construct/issues/291) is fixed, a `-c` config's
`output_dir` is ignored, so only `-o` names the directory.

### Splitting Strategies

#### Namespace-Based (Auto-Detect)

The simplest approach — entities are assigned to modules based on their namespace:

```bash
rdf-construct split ontology.ttl -o modules/ --by-namespace
```

If your ontology uses distinct namespaces for different domains (e.g., `org:`, `building:`), this will automatically create separate modules.

#### Configuration-Based (Explicit)

For fine-grained control, define modules in a YAML configuration:

```yaml
split:
  source: ontology/split_monolith.ttl
  output_dir: modules/

  modules:
    # By explicit class/property list
    - name: core
      description: "Core upper ontology concepts"
      output: core.ttl
      include:
        classes:
          - ex:Entity
          - ex:Event
          - ex:State
        properties:
          - ex:identifier
          - ex:name
      include_descendants: true

    # By namespace
    - name: organisation
      description: "Organisation domain module"
      output: organisation.ttl
      namespaces:
        - "http://example.org/ontology/org#"

    # With explicit imports
    - name: building
      output: building.ttl
      namespaces:
        - "http://example.org/ontology/building#"
      imports:
        - core.ttl
      auto_imports: true

  # Handle entities that don't match any module
  unmatched:
    strategy: common  # or "error"
    module: common
    output: common.ttl

  generate_manifest: true
```

### Include Descendants

When `include_descendants: true`, the splitter includes all subclasses and subproperties:

```yaml
modules:
  - name: entities
    include:
      classes:
        - ex:Entity  # Will include all subclasses
    include_descendants: true
```

### Dependency Tracking

The splitter automatically detects cross-module dependencies (when one module references entities from another) and can generate `owl:imports` declarations:

```turtle
# In organisation.ttl
@prefix owl: <http://www.w3.org/2002/07/owl#> .

<http://example.org/ontology/org> a owl:Ontology ;
    owl:imports <core.ttl> .

org:Organisation a owl:Class ;
    rdfs:subClassOf ex:Entity .  # Reference to core module
```

Control imports with:

- `auto_imports: true` — Generate imports from detected dependencies (default)
- `auto_imports: false` — No automatic imports
- `imports: [core.ttl]` — Explicit import list

### Unmatched Entities

Entities that don't match any module definition are handled according to strategy:

**Common module (default):**
```yaml
unmatched:
  strategy: common
  module: common
  output: common.ttl
```

**Error (fail if unmatched):**
```yaml
unmatched:
  strategy: error
```

### Manifest Generation

The split command generates a `manifest.yml` documenting the split:

```yaml
source: ontology/split_monolith.ttl
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
  total_modules: 3
  total_triples: 156
  unmatched_entities: 2

dependency_graph: |
  core.ttl
  ├── organisation.ttl
  └── building.ttl
```

Disable with `--no-manifest` or `generate_manifest: false`.

### Data Migration

Split instance data alongside the ontology:

```bash
rdf-construct split large.ttl -o modules/ -c split.yml \
    --migrate-data split_instances.ttl \
    --data-output data/
```

Instances are assigned to modules based on their `rdf:type`:

- Instance of `org:Company` → `data_organisation.ttl`
- Instance of `building:Floor` → `data_building.ttl`

Configuration:

```yaml
split_data:
  sources:
    - data/split_instances.ttl
    - data/relationships.ttl
  output_dir: data/
  prefix: data_  # Output: data_core.ttl, data_org.ttl, etc.
```

### Round-Trip Validation

A well-configured split should satisfy:

```
merge(split(ontology)) ≈ ontology
```

Test with:

```bash
# Split
rdf-construct split large.ttl -o modules/ -c split.yml

# Merge back
rdf-construct merge modules/*.ttl -o reconstructed.ttl

# Compare
rdf-construct diff large.ttl reconstructed.ttl
```

Minor differences may occur due to:
- Added `owl:imports` declarations
- Namespace binding order
- Blank node identifiers

### Split Examples

#### Basic Namespace Split

```bash
rdf-construct split ies.ttl -o ies-modules/ --by-namespace
```

Output:
```
ies-modules/
├── ies.ttl
├── common.ttl
└── manifest.yml
```

#### Split with Data Migration

```bash
rdf-construct split ontology.ttl -o modules/ -c split.yml \
    --migrate-data instances/*.ttl \
    --data-output data/
```

Output:
```
modules/
├── core.ttl
├── organisation.ttl
├── building.ttl
├── manifest.yml
data/
├── data_core.ttl
├── data_organisation.ttl
└── data_building.ttl
```

#### Dry Run Preview

```bash
rdf-construct split large.ttl -o modules/ --by-namespace --dry-run
```

Shows what would be created without writing files.

### Split Best Practices

1. **Start with dry run** to preview the split structure
2. **Use explicit configuration** for production splits
3. **Enable `include_descendants`** to capture class hierarchies
4. **Review the manifest** to understand module dependencies
5. **Run `lint`** on each module to catch issues
6. **Test round-trip** to validate the split preserves semantics

---

## Related Commands

- `rdf-construct lint` - Check merged/split output for quality issues
- `rdf-construct diff` - Compare merged result with original
- `rdf-construct docs` - Generate documentation for merged ontology
- `rdf-construct describe` - Quick overview of module contents

## Troubleshooting

### Merge: "No conflicts but labels differ"

That is usually correct. Labels in different language tags never conflict, a source whose labels
are a subset of another's agrees with it, and the ontology header is not checked yet (#171). Any
predicate not in the tier table, such as `dcterms:title`, is repeatable. To have one treated as a
label, place it in a tier in the configuration file:

```yaml
conflicts:
  predicate_tiers:
    per_language: ["http://purl.org/dc/terms/title"]
```

### Merge: "Parse error on source file"

Ensure source files are valid RDF. Run `rdf-construct lint` first.

### Merge: "Too many unresolved conflicts"

Consider:
- Using `--strategy priority` with clear priority ordering
- Breaking large merges into smaller steps
- Using configuration file for fine-grained control

### Split: "Unmatched entities in common module"

Some entities don't match any module definition. Either:
- Add them to a module's class/property list
- Include their namespace in a module
- Accept them in the common module
- Use `--unmatched error` to identify what's missing

### Split: "Too many cross-module dependencies"

Consider reorganising modules or accepting some coupling. Use the manifest's dependency graph to visualise.

### Split: "Missing triples after split"

Ensure all entity types (classes, properties, individuals) are covered. The split only includes triples where the subject is an assigned entity.
