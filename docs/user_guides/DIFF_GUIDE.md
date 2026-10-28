# Semantic Diff Guide

The `rdf-construct diff` command compares two RDF ontologies and reports **semantic differences**, filtering out cosmetic changes like statement order, prefix bindings, and whitespace.

## Quick Start

```bash
# Basic comparison
rdf-construct diff old.ttl new.ttl

# Generate a markdown changelog
rdf-construct diff v1.0.ttl v1.1.ttl --format markdown -o CHANGELOG.md

# JSON output for scripting
rdf-construct diff old.ttl new.ttl --format json | jq '.summary'
```

## Why Semantic Diff?

Standard text diff tools (like `diff` or `git diff`) show every reordered statement as a change. When working with RDF ontologies, this creates noise that obscures actual semantic changes:

| What Changed | Text Diff Shows | Semantic Diff Shows |
|--------------|-----------------|---------------------|
| Statement reordering | Many "changes" | Nothing (identical) |
| Prefix rebinding (`ex:` → `example:`) | Every triple changed | Nothing (identical) |
| New class added | One line added | "Added: Class ex:NewClass" |
| Label modified | Two lines changed | "Modified: ex:Entity label changed" |

## Command Reference

```
rdf-construct diff [OPTIONS] OLD_FILE NEW_FILE
```

### Arguments

- `OLD_FILE` — The baseline/original RDF file
- `NEW_FILE` — The new/updated RDF file

### Options

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Write output to file instead of stdout. Refused (exit 2) if it names either input |
| `-f, --format FORMAT` | Output format: `text` (default), `markdown`, `json` |
| `--show TYPES` | Show only these change types (comma-separated) |
| `--hide TYPES` | Hide these change types (comma-separated) |
| `--entities TYPES` | Show only these entity types (comma-separated) |
| `--ignore-predicates PREDS` | Ignore these predicates (comma-separated CURIEs) |

### Exit Codes

- `0` — Graphs are semantically identical, blank nodes included
- `1` — Differences were found, or a blank-node structure was too large to compare (see [Blank Nodes](#blank-nodes))
- `2` — Error occurred (file not found, parse error, etc.)

## Output Formats

### Text (default)

Designed for terminal display with clear visual markers:

```
Comparing v1.0.ttl → v1.1.ttl

ADDED (2 entities):
  + Class SmartBuilding (subclass of Building)
  + DataProperty energyRating

REMOVED (1 entity):
  - Class DeprecatedStructure

MODIFIED (1 entity):
  ~ Class Building
    + rdfs:comment "A constructed physical structure."@en

Summary: 2 added, 1 removed, 1 modified
```

### Markdown

Perfect for release notes and changelogs:

```bash
rdf-construct diff v1.0.ttl v1.1.ttl --format markdown -o CHANGELOG.md
```

Produces:

```markdown
# Ontology Changes: v1.0.ttl → v1.1.ttl

## Summary

- **2** entities added
- **1** entities removed
- **1** entities modified

## Added

### Classes
- **SmartBuilding** — subclass of Building

### Datatype Properties
- **energyRating**

## Removed

### Classes
- **DeprecatedStructure**

## Modified

### Building

**Added:**
- `rdfs:comment` → "A constructed physical structure."@en
```

### JSON

For programmatic use and scripting:

```bash
rdf-construct diff old.ttl new.ttl --format json
```

```json
{
  "comparison": {
    "old": "v1.0.ttl",
    "new": "v1.1.ttl"
  },
  "identical": false,
  "added": {
    "classes": [
      {
        "uri": "http://example.org/SmartBuilding",
        "label": "SmartBuilding",
        "type": "class",
        "superclasses": ["http://example.org/Building"]
      }
    ],
    "datatype_properties": [
      {
        "uri": "http://example.org/energyRating",
        "label": "energyRating",
        "type": "datatype_property"
      }
    ]
  },
  "removed": { ... },
  "modified": [ ... ],
  "summary": {
    "added": 2,
    "removed": 1,
    "modified": 1
  }
}
```

## Filtering

### By Change Type

Show only specific types of changes:

```bash
# Show only additions and removals
rdf-construct diff old.ttl new.ttl --show added,removed

# Hide modifications (show only structural changes)
rdf-construct diff old.ttl new.ttl --hide modified
```

Valid change types: `added`, `removed`, `modified`

### By Entity Type

Focus on specific types of entities:

```bash
# Show only class changes
rdf-construct diff old.ttl new.ttl --entities classes

# Show only property changes
rdf-construct diff old.ttl new.ttl --entities properties

# Show classes and instances
rdf-construct diff old.ttl new.ttl --entities classes,instances
```

Valid entity types:

- `classes` — OWL/RDFS classes
- `properties` — All property types
- `object_properties` — OWL ObjectProperty
- `datatype_properties` — OWL DatatypeProperty
- `annotation_properties` — OWL AnnotationProperty
- `individuals` / `instances` — Named instances

### Ignoring Predicates

Ignore specific predicates (useful for timestamps, version info):

```bash
# Ignore modification timestamps
rdf-construct diff old.ttl new.ttl --ignore-predicates dcterms:modified

# Ignore multiple predicates
rdf-construct diff old.ttl new.ttl --ignore-predicates dcterms:modified,dcterms:created
```

## CI Integration

Use exit codes for CI pipelines:

```bash
# Fail CI if ontology changed unexpectedly
rdf-construct diff expected.ttl current.ttl
if [ $? -eq 1 ]; then
    echo "Ontology changes detected - please review"
    exit 1
fi
```

Generate changelogs in CI:

```bash
# Generate changelog from previous release
rdf-construct diff release/v1.0.ttl develop/onto.ttl \
    --format markdown \
    -o docs/CHANGELOG.md
```

## Semantic Equivalence

The diff considers these as **identical** (no changes):

1. **Statement order** — Triples in different order
2. **Prefix bindings** — Same URIs with different prefixes
3. **Whitespace** — Formatting differences
4. **Blank node labels** — `_:b1` vs `_:genid123`: a blank-node structure with the same content, including the named subject that refers to it, is the same structure

The diff detects these as **changes**:

1. **URI changes** — Even if labels are the same
2. **Literal type changes** — `"42"` (string) vs `42` (integer)
3. **Language tag changes** — `"Building"@en` vs `"Building"`
4. **Changes inside blank nodes** — a restriction's cardinality, an axiom annotation's comment, a list's members (see [Blank Nodes](#blank-nodes))

## Blank Nodes

A blank node has no name of its own: the parser labels it afresh every time it reads a file. So
`diff` compares a blank-node structure, such as a restriction, an `owl:Axiom` annotation or an
`rdf:List`, by its **content**, including the named subject that refers to it. A file compared with
a copy of itself is identical, however many restrictions it has. A change anywhere inside a
structure is reported as that whole structure removed and its new version added, written as Turtle.

`examples/diff/` holds a pair of files that differ **only** inside blank nodes:

```bash
rdf-construct diff examples/diff/v1.ttl examples/diff/v2.ttl
```

```text
Comparing v1.ttl → v2.ttl

MODIFIED (2 entities):
  ~ Class bld:Building
    + rdfs:subClassOf [ a owl:Restriction ; owl:minCardinality "2"^^xsd:nonNegativeInteger ; owl:onProperty bld:hasFloor ]
    - rdfs:subClassOf [ a owl:Restriction ; owl:minCardinality "1"^^xsd:nonNegativeInteger ; owl:onProperty bld:hasFloor ]
  ~ Class bld:Room
    + [ a owl:Axiom ; owl:annotatedProperty rdfs:subClassOf ; owl:annotatedSource bld:Room ; owl:annotatedTarget bld:Space ; rdfs:comment "A room is an enclosed space."@en ]
    - [ a owl:Axiom ; owl:annotatedProperty rdfs:subClassOf ; owl:annotatedSource bld:Room ; owl:annotatedTarget bld:Space ; rdfs:comment "A room is a space."@en ]

BLANK-NODE STRUCTURES (1 added, 1 removed):
  + [ a owl:AllDisjointClasses ; owl:members ( bld:Building bld:Door bld:Floor bld:Room ) ]
  - [ a owl:AllDisjointClasses ; owl:members ( bld:Building bld:Floor bld:Room ) ]

Summary: 0 added, 0 removed, 2 modified; blank-node structures: 1 added, 1 removed
```

The exit code is 1. The restriction on `bld:Room` and the `owl:unionOf` on `bld:Space` are the same
in both files, so they are not listed.

**Where a change is listed:**

- A structure that a named subject refers to is listed under that subject, after the predicate
  that refers to it (`bld:Building` above). If several subjects refer to one structure, it is
  listed under each of them.
- A structure that nothing refers to is listed under the subject it is about: the
  `owl:annotatedSource` of an axiom annotation (`bld:Room` above), the `rdf:subject` of a reified
  statement, or the `owl:sourceIndividual` of a negative property assertion.
- Anything else, such as `owl:AllDisjointClasses`, is listed under **BLANK-NODE STRUCTURES**
  (in Markdown, `## Blank-node structures`), and the summary counts them as added and removed.

**How a structure is written.** A structure in which every blank node is referred to once is
written inline, as `[ … ]`, with `( … )` for a well-formed list. A blank node that is referred to
twice, or one in a cycle, cannot be written inline. Its structure is written as Turtle statements
instead, and only those nodes get a label: `_:s1`, `_:s2` and so on. These labels belong to the line
they are on, and are the same in every run. No label the parser invented is ever shown.

**Repeated structures count.** If a class states the same restriction twice and the new file
states it once, the diff reports one copy removed.

**In JSON**, a blank-node object is `{"type": "bnode", "turtle": "[ … ]"}`. Each entry in `modified`
has a `structures` list, and the top level has one for structures that belong to no entity. Each
item in these lists is `{"action": "added" | "removed", "turtle": "…"}`. `summary.structures`
counts the top-level list.

**Ignored predicates** are removed before structures are compared. So with
`--ignore-predicates rdfs:comment`, an axiom annotation whose only change is its comment is the
same in both files.

## Known Limitations

### Blank-node structures too large to compare

Most structures are trees: no blank node in them is referred to by two others, and there is no
cycle. A tree of any size is compared quickly. A structure that is not a tree is
compared exactly too, but the cost grows steeply with its size. So `diff` sets aside any structure
that is not a tree and has more than 500 blank nodes. It names the structure first, before
anything else in the output, and exits 1, never claiming the files are identical:

```text
Note: A blank-node structure in old.ttl was not compared: it is not a tree, and it has 5,000 blank nodes, over the limit of 500, under ex:U owl:unionOf. Its changes, if any, are not shown. Each of its blank nodes is owl:sameAs itself, which an OWL-RL closure adds; diff the asserted files instead.
```

The usual cause is a reasoner's output: an OWL-RL closure states that every blank node is
`owl:sameAs` itself, which turns every list into a structure that is not a tree. Compare the
asserted files instead. Everything outside the set-aside structure is still compared and
reported. [#388](https://github.com/aigora-de/rdf-construct/issues/388) records the cost and the options for removing the limit.

### Large Ontologies

The diff loads both graphs into memory. For very large ontologies (>100k triples), consider:

- Splitting into modules before comparison
- Using `--entities` to focus on specific entity types
- Running on a machine with adequate RAM

## Programmatic Use

The diff module can be used directly in Python:

```python
from pathlib import Path
from rdf_construct.diff import compare_files, format_diff, filter_diff

# Compare files
diff = compare_files(Path("v1.0.ttl"), Path("v1.1.ttl"))

# Check if identical
if diff.is_identical:
    print("No changes")
else:
    # Get summary
    print(f"Added: {diff.summary['added']}")
    print(f"Removed: {diff.summary['removed']}")
    print(f"Modified: {diff.summary['modified']}")

# Filter and format
filtered = filter_diff(diff, show_types={"added"})
print(format_diff(filtered, format_name="text"))
```

## Examples

### Generate Release Notes

```bash
# Compare tagged releases
git checkout v1.0.0 -- ontology.ttl && mv ontology.ttl old.ttl
git checkout v1.1.0 -- ontology.ttl && mv ontology.ttl new.ttl

rdf-construct diff old.ttl new.ttl \
    --format markdown \
    -o docs/release-notes/v1.1.0.md
```

### Review Pull Request Changes

```bash
# Compare main branch to PR branch
rdf-construct diff main-onto.ttl pr-onto.ttl --format text
```

### Validate No Unintended Changes

```bash
# In CI: ensure serialisation didn't change semantics
rdf-construct diff original.ttl serialised.ttl
# Exit code 0 means identical
```

## See Also

- [CLI Reference](CLI_REFERENCE.md) — Full command documentation
- [Getting Started](GETTING_STARTED.md) — Installation and setup
- [Lint Guide](LINT_GUIDE.md) — Ontology quality checking
