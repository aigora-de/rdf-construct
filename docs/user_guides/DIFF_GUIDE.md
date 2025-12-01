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
| `-o, --output FILE` | Write output to file instead of stdout |
| `-f, --format FORMAT` | Output format: `text` (default), `markdown`, `json` |
| `--show TYPES` | Show only these change types (comma-separated) |
| `--hide TYPES` | Hide these change types (comma-separated) |
| `--entities TYPES` | Show only these entity types (comma-separated) |
| `--ignore-predicates PREDS` | Ignore these predicates (comma-separated CURIEs) |

### Exit Codes

- `0` — Graphs are semantically identical
- `1` — Differences were found  
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
4. **Blank node labels** — `_:b1` vs `_:genid123` (if structurally equivalent)

The diff detects these as **changes**:

1. **URI changes** — Even if labels are the same
2. **Literal type changes** — `"42"` (string) vs `42` (integer)
3. **Language tag changes** — `"Building"@en` vs `"Building"`

## Known Limitations

### Blank Nodes

Blank nodes are challenging for diff. The current implementation:

- **Detects** that blank node changes occurred
- **Does not** perform deep structural comparison of blank node neighbourhoods

If your ontology uses blank nodes extensively, consider skolemising them before comparison:

```bash
# Skolemise blank nodes first (using rapper or similar)
rapper -i turtle -o turtle old.ttl > old-skolem.ttl
rapper -i turtle -o turtle new.ttl > new-skolem.ttl
rdf-construct diff old-skolem.ttl new-skolem.ttl
```

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