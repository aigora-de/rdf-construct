# Describe Guide

The `rdf-construct describe` command provides a quick orientation to an unfamiliar ontology file, answering essential questions: *"What is this?"*, *"How big is it?"*, *"What does it depend on?"*, and *"Can I work with it?"*

## Overview

When you encounter a new ontology file, you need to understand it quickly before deciding what to do with it. The `describe` command analyses an ontology and produces a comprehensive summary covering:

- **Identity**: What is this ontology? (title, version, description)
- **Scale**: How big is it? (classes, properties, individuals)
- **Profile**: What OWL expressiveness level? (RDF, RDFS, OWL DL, OWL Full)
- **Dependencies**: What does it import? Can those imports be resolved?
- **Structure**: How deep is the hierarchy? What namespaces are used?
- **Quality**: How well documented is it?

This is typically the first command you run when exploring a new ontology.

## Basic Usage

```bash
# Describe an ontology file
rdf-construct describe ontology.ttl

# Quick overview (metadata, metrics, profile only)
rdf-construct describe ontology.ttl --brief

# Output as JSON
rdf-construct describe ontology.ttl --format json

# Output as Markdown (for documentation)
rdf-construct describe ontology.ttl --format markdown

# Save to file
rdf-construct describe ontology.ttl -o description.md --format markdown

# Skip import resolution (faster, no network)
rdf-construct describe ontology.ttl --no-resolve

# Disable coloured output
rdf-construct describe ontology.ttl --no-colour
```

## Output Sections

### Verdict

A one-line summary at the top of the output:

```
OWL 2 DL (simple) | 1,247 triples, 47 classes, 38 properties | 3 imports OK
```

This tells you at a glance:
- The ontology profile (what reasoning capabilities it supports)
- The scale (how much content)
- The import status (whether dependencies resolve)

### Metadata

Information extracted from the `owl:Ontology` declaration:

| Field | Source Properties |
|-------|------------------|
| Title | `rdfs:label`, `dcterms:title`, `dc:title` |
| Description | `rdfs:comment`, `dcterms:description`, `dc:description` |
| Version | `owl:versionInfo` |
| Version IRI | `owl:versionIRI` |
| License | `dcterms:license`, `cc:license` |
| Creators | `dcterms:creator`, `dc:creator` |

### Metrics

Basic counts of ontology elements:

| Metric | Description |
|--------|-------------|
| Total Triples | Number of RDF statements |
| Classes | `owl:Class` and `rdfs:Class` entities |
| Object Properties | `owl:ObjectProperty` entities |
| Datatype Properties | `owl:DatatypeProperty` entities |
| Annotation Properties | `owl:AnnotationProperty` entities |
| Individuals | `owl:NamedIndividual` entities |

### Profile Detection

The detected OWL expressiveness level:

| Profile | Description | Reasoning |
|---------|-------------|-----------|
| RDF | No schema vocabulary | Not applicable |
| RDFS | Uses `rdfs:Class`, `rdfs:subClassOf` | Subclass/subproperty inference |
| OWL 2 DL (simple) | Basic OWL constructs | Standard DL reasoning, efficient |
| OWL 2 DL (expressive) | Complex restrictions, cardinality | Full DL reasoning, may be expensive |
| OWL 2 Full | Metaclasses, property punning | Undecidable, may not terminate |

The profile detection also lists:
- **Detected features**: OWL constructs found (restrictions, cardinality, etc.)
- **Violating constructs**: Features that push the profile to OWL Full

### Imports Analysis

Lists all `owl:imports` declarations and their resolution status:

```
Imports (3 total, 1 unresolvable):
  ✓ http://www.w3.org/2004/02/skos/core
  ✓ http://purl.org/dc/terms/
  ✗ http://internal.example.org/core (404 Not Found)
```

When `--no-resolve` is used, imports are listed without checking:

```
Imports (3 total, unchecked):
  ? http://www.w3.org/2004/02/skos/core
  ? http://purl.org/dc/terms/
  ? http://internal.example.org/core
```

### Namespace Analysis

Shows namespaces used in the ontology:

```
Namespaces:
  Local:    http://example.org/ontology#  (prefix: ex)
  Standard: owl, rdfs, rdf, xsd, skos
  External: http://purl.org/dc/terms/ (not imported)
```

The "external" category identifies namespaces referenced but not declared via `owl:imports`.

### Hierarchy Analysis

Class hierarchy structure:

| Metric | Description |
|--------|-------------|
| Root Classes | Classes with no superclass (except `owl:Thing`) |
| Leaf Classes | Classes with no subclasses |
| Max Depth | Deepest point in the hierarchy |
| Orphan Classes | Classes not connected to the main hierarchy |
| Cycles | Whether circular `rdfs:subClassOf` relationships exist |

### Documentation Coverage

How well documented the ontology is:

| Metric | Description |
|--------|-------------|
| Classes with labels | Have `rdfs:label` or `skos:prefLabel` |
| Classes with definitions | Have `rdfs:comment` or `skos:definition` |
| Properties with labels | Have labels |
| Properties with definitions | Have comments/definitions |

Coverage percentages help assess documentation quality.

## Output Formats

### Text (default)

Coloured, human-readable output for terminals:

```
╭─────────────────────────────────────────────────────────────╮
│  ONTOLOGY DESCRIPTION                                       │
│  examples/organisation_ontology.ttl                         │
╰─────────────────────────────────────────────────────────────╯

Verdict: OWL 2 DL (simple) | 156 triples, 12 classes, 8 properties

METADATA
  Title:       Organisation Ontology
  Version:     1.2.0
  Description: An ontology for modelling organisational structures.

METRICS
  Triples:              156
  Classes:               12
  Object Properties:      5
  Datatype Properties:    3
  Individuals:            0

PROFILE
  Detected: OWL 2 DL (simple)
  Features: owl:Class, rdfs:subClassOf, owl:ObjectProperty,
            rdfs:domain, rdfs:range, owl:FunctionalProperty

IMPORTS (2 total)
  ✓ http://www.w3.org/2004/02/skos/core
  ✓ http://purl.org/dc/terms/

HIERARCHY
  Root Classes:    2
  Leaf Classes:    5
  Max Depth:       3
  Orphan Classes:  0

DOCUMENTATION
  Classes:    12/12 labelled (100%), 8/12 documented (67%)
  Properties:  8/8 labelled (100%), 5/8 documented (63%)
```

### JSON

Machine-readable format for scripting and integration:

```json
{
  "source": "organisation_ontology.ttl",
  "timestamp": "2024-11-15T10:30:00Z",
  "verdict": "OWL 2 DL (simple) | 156 triples, 12 classes, 8 properties",
  "metadata": {
    "ontology_iri": "http://example.org/organisation#",
    "title": "Organisation Ontology",
    "version_info": "1.2.0",
    "description": "An ontology for modelling organisational structures."
  },
  "metrics": {
    "total_triples": 156,
    "classes": 12,
    "object_properties": 5,
    "datatype_properties": 3,
    "annotation_properties": 0,
    "individuals": 0
  },
  "profile": {
    "profile": "owl_dl_simple",
    "display_name": "OWL 2 DL (simple)",
    "detected_features": ["owl:Class", "rdfs:subClassOf", "owl:ObjectProperty"]
  },
  "imports": {
    "imports": [
      {"uri": "http://www.w3.org/2004/02/skos/core", "status": "resolvable"},
      {"uri": "http://purl.org/dc/terms/", "status": "resolvable"}
    ],
    "counts": {"total": 2, "resolvable": 2, "unresolvable": 0}
  }
}
```

### Markdown

For embedding in documentation or README files:

```markdown
## Ontology Description

**Source:** organisation_ontology.ttl  
**Profile:** OWL 2 DL (simple)

### Metadata

| Property | Value |
|----------|-------|
| Title | Organisation Ontology |
| Version | 1.2.0 |
| Description | An ontology for modelling organisational structures. |

### Metrics

| Metric | Count |
|--------|-------|
| Classes | 12 |
| Object Properties | 5 |
| Datatype Properties | 3 |
| Total Triples | 156 |

### Documentation Coverage

- Classes: 100% labelled, 67% documented
- Properties: 100% labelled, 63% documented
```

## Brief Mode

Use `--brief` for a quick summary (metadata, metrics, and profile only):

```bash
rdf-construct describe large_ontology.ttl --brief
```

This skips:
- Import resolution
- Detailed namespace analysis
- Hierarchy analysis
- Documentation coverage

Brief mode is faster for large ontologies or when you only need the basics.

## Command Options

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Write output to file instead of stdout |
| `-f, --format FORMAT` | Output format: `text` (default), `json`, `markdown`, `md` |
| `-b, --brief` | Quick overview (metadata + metrics + profile only) |
| `--no-resolve` | Skip import resolution (no network requests) |
| `--reasoning` | Include reasoning analysis (experimental) |
| `--no-colour` | Disable ANSI colour codes |

## Programmatic Usage

The describe functionality is available as a Python API:

```python
from pathlib import Path
from rdf_construct.describe import describe_file, format_description

# Analyse an ontology file
description = describe_file(Path("ontology.ttl"))

# Access individual sections
print(f"Title: {description.metadata.title}")
print(f"Classes: {description.metrics.classes}")
print(f"Profile: {description.profile.display_name}")

# Check import status
for imp in description.imports.imports:
    print(f"{imp.uri}: {imp.status.value}")

# Format as JSON
json_output = format_description(description, format_name="json")

# Brief mode
brief_description = describe_file(
    Path("ontology.ttl"),
    brief=True,
    resolve_imports=False,
)
```

For in-memory graphs:

```python
from rdflib import Graph
from rdf_construct.describe import describe_ontology

graph = Graph()
graph.parse("ontology.ttl")

description = describe_ontology(graph, source="ontology.ttl")
```

## Use Cases

### Evaluating an Unfamiliar Ontology

Before integrating an external ontology:

```bash
rdf-construct describe downloaded_ontology.owl
```

Check:
- Is the profile compatible with your reasoner?
- Are imports resolvable?
- Is documentation adequate?

### Pre-merge Assessment

Before merging ontologies:

```bash
rdf-construct describe ontology_a.ttl
rdf-construct describe ontology_b.ttl
```

Compare profiles and namespaces to anticipate conflicts.

### CI/CD Integration

Add to your pipeline to document ontology characteristics:

```yaml
- name: Describe ontology
  run: |
    rdf-construct describe ontology.ttl --format json > description.json
    # Check profile is not OWL Full
    profile=$(jq -r '.profile.profile' description.json)
    if [ "$profile" = "owl_full" ]; then
      echo "Warning: OWL Full profile detected"
    fi
```

### Documentation Generation

Generate a description section for your README:

```bash
rdf-construct describe ontology.ttl --format markdown >> README.md
```

### Quick Triage

When you have many ontology files:

```bash
for f in *.ttl; do
  echo "=== $f ==="
  rdf-construct describe "$f" --brief
done
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Success with warnings (e.g., unresolvable imports) |
| 2 | Error (file not found, parse error) |

## Tips

1. **Start with describe** - It's the fastest way to understand what you're working with
2. **Use brief mode for large files** - Full analysis can be slow on very large ontologies
3. **Check the profile** - OWL Full ontologies may cause reasoning problems
4. **Note unresolvable imports** - These might cause issues downstream
5. **Look at documentation coverage** - Low coverage suggests the ontology may be hard to use

## Related Commands

- `rdf-construct stats` - Detailed metrics and comparison between versions
- `rdf-construct lint` - Quality issues and style problems
- `rdf-construct merge` - Combine multiple ontologies
- `rdf-construct docs` - Generate full documentation
