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
```

## Metric Categories

The stats command collects metrics in six categories:

### Basic Counts

Fundamental counts of entities in the ontology.

| Metric | Description |
|--------|-------------|
| Triples | Total number of RDF triples |
| Classes | owl:Class + rdfs:Class entities |
| Object Properties | owl:ObjectProperty entities |
| Datatype Properties | owl:DatatypeProperty entities |
| Annotation Properties | owl:AnnotationProperty entities |
| Individuals | Named individuals (non-class, non-property) |

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
| Inverse Pairs | Number of owl:inverseOf relationships |
| Functional | Number of owl:FunctionalProperty |
| Symmetric | Number of owl:SymmetricProperty |

### Documentation

Documentation coverage statistics.

| Metric | Description |
|--------|-------------|
| Classes Labelled | Classes with rdfs:label or skos:prefLabel |
| Classes Documented | Classes with rdfs:comment or skos:definition |
| Properties Labelled | Properties with labels |

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

### Text (default)

Human-readable aligned columns:

```
Ontology Statistics: examples/animal_ontology.ttl
==================================================

BASIC COUNTS
  Triples:                   89
  Classes:                   12
  Object Properties:          5
  Datatype Properties:        3
  Individuals:                0

HIERARCHY
  Root Classes:               1
  Leaf Classes:               5
  Max Depth:                  4
  Avg Depth:                2.3
  Avg Branching:            2.0
  Orphan Classes:             0 (0.0%)

PROPERTIES
  With Domain:                7 (87.5%)
  With Range:                 6 (75.0%)
  Functional:                 1

DOCUMENTATION
  Classes Labelled:          12 (100.0%)
  Classes Documented:         8 (66.7%)
  Properties Labelled:        8 (100.0%)
```

### JSON

Machine-readable format for scripting and CI pipelines:

```json
{
  "source": "ontology.ttl",
  "timestamp": "2024-11-15T10:30:00Z",
  "basic": {
    "triples": 1247,
    "classes": 47,
    "object_properties": 23,
    "datatype_properties": 15,
    "annotation_properties": 8,
    "individuals": 156
  },
  "hierarchy": {
    "root_classes": 5,
    "leaf_classes": 18,
    "max_depth": 6,
    "avg_depth": 3.2,
    "avg_branching": 2.1,
    "orphan_classes": 2,
    "orphan_rate": 0.043
  }
}
```

### Markdown

For embedding in documentation:

```markdown
## Ontology Statistics

| Metric | Value |
|--------|-------|
| Classes | 47 |
| Properties | 38 |
| Max Depth | 6 |
| Documentation Coverage | 81% |

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

## Related Commands

- `rdf-construct lint` - Detailed quality issues (vs. summary metrics)
- `rdf-construct diff` - Semantic changes (vs. metric changes)
- `rdf-construct docs` - Generate documentation from ontology
