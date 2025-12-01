# SHACL Shape Generator Guide

Generate SHACL validation shapes from OWL ontology definitions.

## Overview

The `shacl-gen` command converts OWL class definitions into SHACL NodeShapes,
extracting constraints from domain/range declarations, cardinality restrictions,
functional properties, and other OWL patterns.

This saves hours of boilerplate writing and ensures shapes stay aligned with
your ontology definitions.

## Quick Start

```bash
# Generate shapes with default settings
rdf-construct shacl-gen ontology.ttl

# Output: ontology-shapes.ttl
```

## Basic Usage

### Generate Shapes for an Ontology

```bash
rdf-construct shacl-gen building-ontology.ttl -o building-shapes.ttl
```

This produces SHACL shapes for all classes in the ontology, converting:

- `rdfs:domain/range` → `sh:property` with `sh:class` or `sh:datatype`
- `owl:cardinality` → `sh:minCount` + `sh:maxCount`
- `owl:FunctionalProperty` → `sh:maxCount 1`
- `rdfs:label` → `sh:name`
- `rdfs:comment` → `sh:description`

### Example Conversion

**OWL Input:**
```turtle
ex:Building a owl:Class ;
    rdfs:label "Building" ;
    rdfs:comment "A permanent structure with walls and roof" .

ex:hasFloor a owl:ObjectProperty ;
    rdfs:domain ex:Building ;
    rdfs:range ex:Floor .

ex:Building rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty ex:hasFloor ;
    owl:minCardinality 1
] .

ex:hasAddress a owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain ex:Building ;
    rdfs:range xsd:string .
```

**SHACL Output:**
```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix shape: <http://example.org/-shapes#> .

shape:BuildingShape a sh:NodeShape ;
    sh:targetClass ex:Building ;
    sh:name "Building" ;
    sh:description "A permanent structure with walls and roof" ;
    
    sh:property [
        sh:path ex:hasFloor ;
        sh:class ex:Floor ;
        sh:minCount 1 ;
        sh:order 1 ;
    ] ;
    
    sh:property [
        sh:path ex:hasAddress ;
        sh:datatype xsd:string ;
        sh:maxCount 1 ;
        sh:order 2 ;
    ] .
```

## Strictness Levels

Control how many OWL patterns are converted to SHACL constraints:

### Minimal Level

```bash
rdf-construct shacl-gen ontology.ttl --level minimal
```

Converts only:
- `rdfs:range` → `sh:class` or `sh:datatype`

Useful for lightweight validation or when you want to add constraints manually.

### Standard Level (Default)

```bash
rdf-construct shacl-gen ontology.ttl --level standard
```

Adds:
- Cardinality restrictions (`owl:cardinality`, `owl:minCardinality`, etc.)
- Functional properties → `sh:maxCount 1`
- `owl:someValuesFrom` → `sh:minCount 1`

### Strict Level

```bash
rdf-construct shacl-gen ontology.ttl --level strict
```

Maximum constraints:
- All standard level conversions
- Enumerations (`owl:oneOf` → `sh:in`)
- Support for closed shapes

## Closed Shapes

Generate shapes that reject unexpected properties:

```bash
rdf-construct shacl-gen ontology.ttl --level strict --closed
```

This adds `sh:closed true` to all shapes. Instances with properties not
defined in the shape will fail validation.

Configure ignored properties in the config file:

```yaml
closed: true
ignored_properties:
  - rdf:type
  - rdfs:label
  - dcterms:modified
```

## Targeting Specific Classes

### Include Only Certain Classes

```bash
rdf-construct shacl-gen ontology.ttl --classes "Building,Floor,Room"
```

### Using Configuration File

```yaml
target_classes:
  - Building
  - Floor
  - http://example.org/Room
```

### Exclude Classes

```yaml
exclude_classes:
  - owl:Thing
  - rdfs:Resource
  - DeprecatedClass
```

## Constraint Inheritance

By default, subclass shapes inherit property constraints from superclasses.

**Example:**
If `Person` has `hasName` with `sh:maxCount 1`, then `Employee`
(a subclass of `Person`) will also have this constraint.

Disable inheritance:

```bash
rdf-construct shacl-gen ontology.ttl --no-inherit
```

Or in config:

```yaml
inherit_constraints: false
```

## Configuration File

For complex settings, use a YAML configuration file:

```bash
rdf-construct shacl-gen ontology.ttl --config shacl-config.yml
```

Example `shacl-config.yml`:

```yaml
level: standard
default_severity: violation
closed: false

target_classes:
  - Building
  - Floor

include_labels: true
include_descriptions: true
inherit_constraints: true

ignored_properties:
  - rdf:type
  - rdfs:label
```

CLI options override configuration file settings.

## Output Formats

### Turtle (Default)

```bash
rdf-construct shacl-gen ontology.ttl -o shapes.ttl --format turtle
```

### JSON-LD

```bash
rdf-construct shacl-gen ontology.ttl -o shapes.json --format json-ld
```

## Severity Levels

Control how constraint violations are reported:

```bash
rdf-construct shacl-gen ontology.ttl --default-severity warning
```

Options:
- `violation` - Validation fails (default)
- `warning` - Logged as warning but validation passes
- `info` - Informational only

## OWL Pattern Coverage

### Fully Supported

| OWL Pattern | SHACL Equivalent |
|-------------|------------------|
| `rdfs:domain` | `sh:targetClass` + `sh:property` |
| `rdfs:range` (class) | `sh:class` |
| `rdfs:range` (datatype) | `sh:datatype` |
| `owl:cardinality` | `sh:minCount` + `sh:maxCount` |
| `owl:minCardinality` | `sh:minCount` |
| `owl:maxCardinality` | `sh:maxCount` |
| `owl:FunctionalProperty` | `sh:maxCount 1` |
| `owl:someValuesFrom` | `sh:minCount 1` + type |
| `owl:allValuesFrom` | `sh:class` or `sh:datatype` |
| `owl:oneOf` | `sh:in` |
| `owl:qualifiedCardinality` | Cardinality + type |
| `rdfs:label` | `sh:name` |
| `rdfs:comment` | `sh:description` |

### Not Converted (Requires Manual SHACL)

Some OWL patterns cannot be directly expressed in SHACL Core:

- **Complex class expressions** (unions, intersections)
- **Inverse functional uniqueness** (requires SPARQL)
- **Transitive property closures**
- **Property chains**
- **owl:complementOf**

When these patterns are encountered, the generator continues without them.
Consider adding SPARQL-based SHACL constraints manually.

## Programmatic Usage

```python
from rdf_construct.shacl import (
    generate_shapes,
    generate_shapes_to_file,
    ShaclConfig,
    StrictnessLevel,
)
from pathlib import Path

# Simple generation
shapes_graph, turtle = generate_shapes(Path("ontology.ttl"))

# With configuration
config = ShaclConfig(
    level=StrictnessLevel.STRICT,
    closed=True,
    target_classes=["Building", "Floor"],
)

shapes_graph, turtle = generate_shapes(
    Path("building.ttl"),
    config,
)

# Generate to file
generate_shapes_to_file(
    Path("ontology.ttl"),
    Path("shapes.ttl"),
    config,
)
```

## Validation with pySHACL

Use the generated shapes with pySHACL:

```bash
# Install pySHACL
pip install pyshacl

# Validate data against shapes
pyshacl -s shapes.ttl -d data.ttl
```

Or programmatically:

```python
from pyshacl import validate

conforms, report, text = validate(
    data_graph,
    shacl_graph=shapes_graph,
)
```

## CI Integration

Example GitHub Actions workflow:

```yaml
- name: Generate and validate SHACL
  run: |
    # Generate shapes from ontology
    rdf-construct shacl-gen ontology.ttl -o shapes.ttl --level strict
    
    # Validate sample data
    pyshacl -s shapes.ttl -d sample-data.ttl
```

## Tips

1. **Start with standard level** - Generate shapes, review them, then increase
   strictness if needed.

2. **Review inherited constraints** - Inheritance can create deep constraint
   chains. Use `--no-inherit` if shapes get too complex.

3. **Combine with lint** - Run `rdf-construct lint` on your ontology first
   to catch issues before generating shapes.

4. **Iterate** - Generate shapes, validate sample data, adjust configuration,
   repeat until shapes match your validation requirements.

5. **Version control shapes** - Generated shapes are deterministic. Commit
   them alongside your ontology for traceability.

## See Also

- [SHACL Specification](https://www.w3.org/TR/shacl/)
- [pySHACL Documentation](https://github.com/RDFLib/pySHACL)
- [CLI Reference](CLI_REFERENCE.md)