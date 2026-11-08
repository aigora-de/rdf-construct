# Stats Guide

The `rdf-construct stats` command computes comprehensive metrics about an ontology's structure, complexity, and documentation coverage.

## Overview

Understanding an ontology's structure helps with:

- **Assessment**: How complex is this ontology? Is it well-structured?
- **Comparison**: How does this version compare to the previous?
- **Documentation**: What are the key statistics for README/docs?
- **Quality indicators**: High orphan rate or low documentation coverage might suggest issues

## Basic Usage

```bash
# Display statistics for an ontology
rdf-construct stats ontology.ttl

# Output as JSON for programmatic use
rdf-construct stats ontology.ttl --format json

# Write to file
rdf-construct stats ontology.ttl -o stats.json --format json

# Generate markdown for documentation
rdf-construct stats ontology.ttl --format markdown >> README.md

# Figures for a modular ontology, over all of its files
rdf-construct stats src/ontology/*.ttl
```

## Several Files

Given several files without `--compare`, `stats` reports **one set of figures
over their union**: every file is parsed into one graph, and each figure is
computed over that graph. A modular ontology's figures only add up this way,
because a module's classes hang from classes in another file. On its own,
`examples/stats/zoo_care.ttl` reports `care:Patient` as a root; over both files
it sits under `zoo:Mammal`, two levels down.

- **It is a union, not an `owl:imports` closure.** `stats` reads the files you
  name and follows no import. The header says `N files (union)` and lists them,
  and the JSON names them in `sources`.
- **A file named twice is read once.** Another spelling of the same path, or a
  symbolic link to it, is left out with a `Note:` on stderr, and is listed in
  `sources` once. Parsing a file twice would double every blank node in it, and
  every restriction count with it.
- **Whose terms they are is decided over the union.** Each ontology header
  owns its own namespace, as for one file (see Basic Counts). A module with no
  `owl:Ontology` header owns no namespace by its header. Its terms count only
  where it describes them beyond their type, for example with a label, so a
  file that only declares types loses its terms beside a file that names an
  ontology.
- **Distinct files that share triples count them once.** Blank nodes from
  different files are always distinct.
- **Prefixes:** the first file to bind a prefix keeps it. Another file binding
  it to a different namespace has that namespace written with a numbered prefix
  (`ex1:`). Only `Most Connected` is written with prefixes.
- **A file that cannot be parsed is named** in the error, and the run exits 2
  with nothing written.

`stats` prints a `Loaded N triples` line for each file on stderr, then
`Union of N files: M triples`. `M` is less than the sum when files share
triples.

## Metric Categories

The stats command collects metrics in six categories:

### Basic Counts

Fundamental counts of entities in the ontology.

| Metric | Description |
|--------|-------------|
| Triples | Total number of RDF triples |
| Classes | Terms typed `owl:Class`, `rdfs:Class` or `owl:DeprecatedClass` |
| Object Properties | Terms typed `owl:ObjectProperty`, or one of the OWL characteristics that imply it: `owl:TransitiveProperty`, `owl:SymmetricProperty`, `owl:AsymmetricProperty`, `owl:ReflexiveProperty`, `owl:IrreflexiveProperty`, `owl:InverseFunctionalProperty` |
| Datatype Properties | Terms typed `owl:DatatypeProperty` |
| Annotation Properties | Terms typed `owl:AnnotationProperty` |
| Other Properties | Properties whose kind the file does not say: typed `rdf:Property`, `owl:FunctionalProperty` or `owl:DeprecatedProperty`, and none of the types above |
| Individuals | Typed terms that are neither classes nor properties, and terms typed `owl:NamedIndividual` |

These are the type sets every command shares (`rdf_construct.core.vocab`). A
term declared only `owl:TransitiveProperty` is an object property, because OWL
says so. A term declared only `owl:FunctionalProperty` could be an object or a
datatype property, so it is counted under **Other Properties** rather than
guessed. To move it, declare its kind: `ex:hasMother a owl:ObjectProperty ,
owl:FunctionalProperty` is an object property, and not an other property.

**A term declared with two kinds counts under each.** A property typed both
`owl:ObjectProperty` and `owl:DatatypeProperty` adds one to each count. A class
punned as a property adds one to Classes and one to its property count. A class
the file also types `owl:NamedIndividual` adds one to Individuals. Each count
answers "how many terms of this kind are there", and such a term is of both
kinds. `diff`, which reports each change on one line, lists such a term once,
under the first of its kinds (see the [Diff Guide](DIFF_GUIDE.md)).

Every count, in every category, covers the ontology's own terms only. A
class or property the file declares but does not own, such as
`dcterms:creator a owl:AnnotationProperty` or the `prov:wasDerivedFrom` that
`order`, `split` and `merge` stamp a derived file with, is not counted, and
is not counted as an individual either. A term is not the ontology's own
when the file names an ontology, none of its ontologies owns the term's
namespace, and the file describes fewer than two terms there beyond their
type: the same answer `lint` and `docs` use (see
[Whose terms are checked](LINT_GUIDE.md#whose-terms-are-checked)). A class
whose only superclass is foreign counts as a root, and as an orphan if it has
no subclasses, as it would if the superclass were not declared at all.

### Hierarchy

Class hierarchy structure analysis.

| Metric | Description |
|--------|-------------|
| Root Classes | Classes with no superclass (except owl:Thing) |
| Leaf Classes | Classes with no subclasses |
| Max Depth | Maximum depth of the class hierarchy |
| Avg Depth | Average depth across all classes |
| Avg Branching | Average number of direct subclasses per class |
| Orphan Classes | Classes not connected to the main hierarchy |
| Orphan Rate | Proportion of orphan classes (0.0 - 1.0) |

### Properties

Property definition coverage.

| Metric | Description |
|--------|-------------|
| With Domain | Properties with rdfs:domain defined |
| With Range | Properties with rdfs:range defined |
| Domain Coverage | Proportion of properties with domain |
| Range Coverage | Proportion of properties with range |
| Inverse Pairs | Properties with an `owl:inverseOf` |
| Functional | Properties typed `owl:FunctionalProperty`, whatever their kind |
| Symmetric | Properties typed `owl:SymmetricProperty` |

"Properties" here are the ontology's own properties of all four kinds, each
counted once. The coverage figures divide by that number.

### Documentation

Documentation coverage statistics.

| Metric | Description |
|--------|-------------|
| Classes Labelled | Classes with rdfs:label or skos:prefLabel |
| Classes Documented | Classes with rdfs:comment or skos:definition |
| Properties Labelled | Properties, of all four kinds, with labels |

Percentages are also provided (e.g., `classes_labelled_pct`).

### Complexity

Structural complexity indicators.

| Metric | Description |
|--------|-------------|
| Avg Props/Class | Average properties referencing each class |
| Avg Superclasses | Average number of superclasses per class |
| Multiple Inheritance | Classes with 2+ direct superclasses |
| OWL Restrictions | Number of owl:Restriction nodes |
| Equivalent Classes | Number of owl:equivalentClass statements |

### Connectivity

How classes are connected through properties.

| Metric | Description |
|--------|-------------|
| Most Connected Class | Class referenced by the most properties |
| Most Connected Count | Number of property references |
| Isolated Classes | Classes not referenced by any property |

## Output Formats

Each sample below is the output of this command over the two modules in
`examples/stats/`, exactly as printed. Only the JSON's timestamp differs from
run to run:

```bash
rdf-construct stats examples/stats/zoo_core.ttl examples/stats/zoo_care.ttl
```

`zoo_core.ttl` declares the shapes a short type list gets wrong. They include
a property declared only `owl:TransitiveProperty`, an `owl:DeprecatedClass`, an
`owl:FunctionalProperty` alone, an `owl:DeprecatedProperty` alone, an
`rdf:Property`, and a class punned as a named individual. `zoo_care.ttl` hangs
its classes under `zoo_core.ttl`'s. The files' comments say what each term
tests.

### Text (default)

Human-readable aligned columns:

```text
Ontology Statistics: 2 files (union)
  examples/stats/zoo_core.ttl
  examples/stats/zoo_care.ttl
==================================================

BASIC COUNTS
  Triples:                  67
  Classes:                  9
  Object Properties:        5
  Datatype Properties:      1
  Annotation Properties:    1
  Other Properties:         4
  Individuals:              3

HIERARCHY
  Root Classes:             5
  Leaf Classes:             6
  Max Depth:                2
  Avg Depth:                0.6
  Avg Branching:            1.3
  Orphan Classes:           3 (33.3%)

PROPERTIES
  With Domain:              7 (63.6%)
  With Range:               6 (54.5%)
  Inverse Pairs:            0
  Functional:               2
  Symmetric:                1

DOCUMENTATION
  Classes Labelled:         9 (100.0%)
  Classes Documented:       3 (33.3%)
  Properties Labelled:      7 (63.6%)

COMPLEXITY
  Avg Props/Class:          1.3
  Avg Superclasses:         0.4
  Multiple Inheritance:     0
  OWL Restrictions:         0
  Equivalent Classes:       0

CONNECTIVITY
  Most Connected:           zoo:Animal (6 refs)
  Isolated Classes:         1
```

### JSON

Machine-readable format for scripting and CI pipelines (`--format json`).
`sources` is always a list, for one file too:

```json
{
  "sources": [
    "examples/stats/zoo_core.ttl",
    "examples/stats/zoo_care.ttl"
  ],
  "timestamp": "2026-11-08T12:00:00.000000",
  "basic": {
    "triples": 67,
    "classes": 9,
    "object_properties": 5,
    "datatype_properties": 1,
    "annotation_properties": 1,
    "other_properties": 4,
    "individuals": 3
  },
  "hierarchy": {
    "root_classes": 5,
    "leaf_classes": 6,
    "max_depth": 2,
    "avg_depth": 0.56,
    "avg_branching": 1.33,
    "orphan_classes": 3,
    "orphan_rate": 0.333
  },
  "properties": {
    "with_domain": 7,
    "with_range": 6,
    "domain_coverage": 0.636,
    "range_coverage": 0.545,
    "inverse_pairs": 0,
    "functional": 2,
    "symmetric": 1
  },
  "documentation": {
    "classes_labelled": 9,
    "classes_labelled_pct": 1.0,
    "classes_documented": 3,
    "classes_documented_pct": 0.333,
    "properties_labelled": 7,
    "properties_labelled_pct": 0.636
  },
  "complexity": {
    "avg_properties_per_class": 1.33,
    "avg_superclasses_per_class": 0.44,
    "multiple_inheritance_count": 0,
    "owl_restriction_count": 0,
    "owl_equivalent_count": 0
  },
  "connectivity": {
    "most_connected_class": "http://example.org/zoo/core#Animal",
    "most_connected_count": 6,
    "isolated_classes": 1
  }
}
```

### Markdown

For embedding in documentation (`--format markdown`):

```markdown
## Ontology Statistics

**Sources (union of 2 files):**

- `examples/stats/zoo_core.ttl`
- `examples/stats/zoo_care.ttl`

| Metric | Value |
|--------|-------|
| Classes | 9 |
| Object Properties | 5 |
| Datatype Properties | 1 |
| Other Properties | 4 |
| Max Hierarchy Depth | 2 |
| Documentation Coverage | 33.3% |

### Structure

| Metric | Value |
|--------|-------|
| Total Triples | 67 |
| Root Classes | 5 |
| Leaf Classes | 6 |
| Avg Branching Factor | 1.3 |
| Orphan Classes | 3 (33.3%) |

### Properties

| Metric | Value |
|--------|-------|
| With Domain | 7 (63.6%) |
| With Range | 6 (54.5%) |
| Functional | 2 |
| Symmetric | 1 |

### Documentation

| Metric | Value |
|--------|-------|
| Classes Labelled | 9 (100.0%) |
| Classes Documented | 3 (33.3%) |
| Properties Labelled | 7 (63.6%) |

*Generated by rdf-construct stats*
```

## Comparison Mode

Compare two versions of an ontology to track changes:

```bash
rdf-construct stats v1.ttl v2.ttl --compare
```

Output:

```
Comparing: v1.ttl → v2.ttl
==========================

                        v1        v2    Change
Classes                 10        12    +2 (+20.0%) ✓
Max Depth                3         4    +1
Documentation Coverage  60%       67%   +7pp ✓
Orphan Classes           2         1    -1 ✓

Summary: Ontology grew with improved documentation coverage.
```

Indicators:
- ✓ = Improvement
- ⚠ = Degradation

## Filtering Categories

Include only specific categories:

```bash
# Only basic counts and documentation
rdf-construct stats ontology.ttl --include basic,documentation
```

Exclude categories:

```bash
# Everything except connectivity and complexity
rdf-construct stats ontology.ttl --exclude connectivity,complexity
```

Available category names:
- `basic`
- `hierarchy`
- `properties`
- `documentation`
- `complexity`
- `connectivity`

## Integration Examples

### CI Pipeline Quality Gate

```yaml
# .github/workflows/ontology-check.yml
- name: Check ontology metrics
  run: |
    stats=$(rdf-construct stats ontology.ttl --format json)
    orphan_rate=$(echo "$stats" | jq '.hierarchy.orphan_rate')
    if (( $(echo "$orphan_rate > 0.1" | bc -l) )); then
      echo "ERROR: Orphan rate too high: $orphan_rate"
      exit 1
    fi
```

### Generate README Badge Data

```bash
rdf-construct stats ontology.ttl --format json | \
  jq -r '"![Classes](https://img.shields.io/badge/classes-\(.basic.classes)-blue)"'
```

### Track Metrics Over Time

```bash
# Append stats to a CSV
echo "$(date -I),$(rdf-construct stats ontology.ttl --format json | jq -c .)" >> metrics.log
```

## Tips

1. **Run regularly** - Track metrics as part of your CI/CD pipeline
2. **Compare versions** - Use `--compare` before releases to understand changes
3. **Document thresholds** - Define acceptable ranges for orphan rate, documentation coverage, etc.
4. **Export JSON** - Easier to process programmatically than text
5. **Complement with lint** - Stats shows summary; `rdf-construct lint` shows specific issues

## Known Limitations

| Limitation | Issue |
|---|---|
| Every file is parsed as Turtle, whatever its extension: an RDF/XML or JSON-LD file is refused at exit 2 with a parse error | [#146](https://github.com/aigora-de/rdf-construct/issues/146) |
| An `rdfs:subClassOf` cycle is not reported, and the depth figures over it are arbitrary | [#142](https://github.com/aigora-de/rdf-construct/issues/142) |
| A property with an `rdfs:domain`, `rdfs:range` or `rdfs:subPropertyOf` but no property type is counted as an individual, or not at all | [#297](https://github.com/aigora-de/rdf-construct/issues/297) |
| Blank nodes are counted: an `owl:unionOf` class expression as a class, and an `owl:Restriction` or `owl:Axiom` as an individual (an anonymous individual, such as `[ a ex:Identifier ]`, rightly counts as one) | [#529](https://github.com/aigora-de/rdf-construct/issues/529) |
| A term typed `rdfs:Datatype` is counted as an individual | [#530](https://github.com/aigora-de/rdf-construct/issues/530) |
| `--include` and `--exclude` report an excluded category as zeros rather than leaving it out | [#139](https://github.com/aigora-de/rdf-construct/issues/139) |
| Several files are a union of the files named, not an `owl:imports` closure | by design |

## Related Commands

- `rdf-construct lint` - Detailed quality issues (vs. summary metrics)
- `rdf-construct diff` - Semantic changes (vs. metric changes)
- `rdf-construct docs` - Generate documentation from ontology
