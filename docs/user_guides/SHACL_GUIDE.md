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
  - <http://purl.org/dc/terms/modified>
```

`rdf:type` is always ignored, and is listed first; an entry given twice is listed once. Each entry is
a CURIE, an IRI in angle brackets, or a full `http(s)://` IRI. A CURIE resolves against **the source
ontology's own prefixes**, plus `rdf`, `rdfs`, `owl`, `xsd` and `xml`. If your ontology binds `org:`
to its own namespace, `org:secret` means that namespace, not W3C's Organization ontology.

An entry whose prefix the ontology does not bind is refused at exit 2, and nothing is written. Where
the prefix is a well-known one, the message gives the IRI to write instead. Written as
`dcterms:modified`, on an ontology that does not bind `dcterms:`, the entry above is refused:

```text
Error: Selection refused, nothing written:
ignored_properties: 'dcterms:modified': prefix 'dcterms' is not bound in this source (bound: bld, owl, rdf, rdfs, xml, xsd); write <http://purl.org/dc/terms/modified> if you mean dcterms: as http://purl.org/dc/terms/
```

Write the IRI in angle brackets, as above, or bind the prefix in the ontology. Shapes are closed only
with `--closed` at `--level strict`. Otherwise `ignored_properties` has no effect, and the run says so
in a note.

## Targeting Specific Classes

### Include Only Certain Classes

Name each class by its local name:

```bash
rdf-construct shacl-gen ontology.ttl --classes "Building,Floor,Room"
```

Or by a CURIE in one of the ontology's own prefixes:

```bash
rdf-construct shacl-gen ontology.ttl --classes "bld:Building,bld:Floor"
```

An entry is matched exactly against the classes the ontology declares. `Building` selects
`bld:Building`, not `bld:BuildingPart`. The accepted spellings are:

| Spelling | Example | Matches |
|---|---|---|
| Bare local name (no `:`) | `Building` | the declared class whose local name is exactly `Building` |
| CURIE | `bld:Building` | the IRI, using the ontology's prefixes plus `rdf`, `rdfs`, `owl`, `xsd`, `xml` |
| IRI in angle brackets | `<http://example.org/building#Building>` | that IRI; use this for a URN (`<urn:x:Cat>`) |
| Full IRI | `http://example.org/building#Building` | that IRI |

A local name is what follows the IRI's last `#`, else its last `/`, else its last `:`.

Each entry must select a class, or the run is refused at exit 2 with nothing written. Every problem
is listed:

```bash
rdf-construct shacl-gen ontology.ttl --classes "Buildng,Floor"
```

```text
Error: Selection refused, nothing written:
target_classes: 'Buildng' names no class in this source; did you mean Building, BuildingPart?
```

`--classes` fills `target_classes`, so the message uses that name. Besides a name that matches
nothing, these are refused:

- a bare name that matches classes in two namespaces (`a:Cat` and `b:Cat`); the message lists the
  CURIEs to choose from;
- a CURIE whose prefix the ontology does not bind;
- a class declared only as `owl:DeprecatedClass`, which `shacl-gen` does not shape yet
  ([#228](https://github.com/aigora-de/rdf-construct/issues/228));
- an IRI the ontology only refers to, such as an imported superclass, without declaring it a class.

### Using Configuration File

```yaml
target_classes:
  - Building
  - bld:Floor
  - <http://example.org/building#Room>
```

`target_classes`, `exclude_classes` and `ignored_properties` must be lists. `target_classes: Building`
on its own is refused; write `target_classes: [Building]`.

### Exclude Classes

```yaml
exclude_classes:
  - BuildingPart
```

Exclusions use the same spellings, and they apply alongside `--classes`: the shapes are the targets
minus the exclusions. An exclusion that names no class here is a note, not a refusal, so one config
can serve several ontologies. A run whose selection ends up empty is refused.

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
  - bld:Floor

include_labels: true
include_descriptions: true
inherit_constraints: true

ignored_properties:
  - rdf:type
  - rdfs:label
```

An option given on the command line overrides the configuration file, and the configuration file
overrides the option's default: `level: strict` in the file applies unless you pass `--level`.

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

The selection and `ignored_properties` are resolved before anything is generated. A selection that
cannot be honoured raises `ShaclSelectionError`, whose `problems` lists every entry at fault, and
`generate_shapes_to_file` then writes nothing:

```python
from rdf_construct.shacl import ShaclSelectionError

try:
    generate_shapes(Path("ontology.ttl"), ShaclConfig(target_classes=["Buildng"]))
except ShaclSelectionError as error:
    for problem in error.problems:
        print(problem)
```

Given a `Path`, the source is parsed with only its own prefixes plus the core five bound. Given a
`Graph` you loaded yourself, CURIEs resolve against **that graph's bindings, whatever they are**: a
bare `rdflib.Graph()` also binds rdflib's built-in prefixes (`dcterms:`, `skos:`, W3C's `org:` …), so
`dcterms:title` resolves there and is refused from a `Path`. Build your graph with
`Graph(bind_namespaces="core")` to get the command's behaviour. `resolve_selection(graph, config,
shaped)` returns the resolved `Selection` (`classes`, `targets`, `ignored_properties`, `notes`)
without generating anything, and `ShapeGenerator(...).selection` holds the one it used.

### Shape IRIs

Shapes are named `<namespace><LocalName>Shape`. With an `owl:Ontology`, the namespace is the
ontology IRI with `-shapes#` appended (`http://example.org/animals` gives
`http://example.org/animals-shapes#`). Without one, it is the namespace that holds the most declared
classes, with its trailing `#`, `/` or `:` replaced by `-shapes#`; ties go to the alphabetically first
namespace. It is taken over the whole ontology, so `--classes` never moves a shape's IRI.

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

## Known Limitations

| Limitation | Issue |
|---|---|
| A class declared only as `owl:DeprecatedClass` gets no shape, and selecting it is refused | [#228](https://github.com/aigora-de/rdf-construct/issues/228) |
| `--closed` has no effect below `--level strict` | [#224](https://github.com/aigora-de/rdf-construct/issues/224) |
| Two classes with one local name (`a:Cat`, `b:Cat`) share one shape, and each gets the other's constraints | [#485](https://github.com/aigora-de/rdf-construct/issues/485) |
| Output is not byte-identical between runs: blank-node property shapes come out in varying order | [#94](https://github.com/aigora-de/rdf-construct/issues/94) |

## See Also

- [SHACL Specification](https://www.w3.org/TR/shacl/)
- [pySHACL Documentation](https://github.com/RDFLib/pySHACL)
- [CLI Reference](CLI_REFERENCE.md)
