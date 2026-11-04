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
- `rdfs:range` → `sh:class` or `sh:datatype`, when the range is an IRI (see
  [OWL Pattern Coverage](#owl-pattern-coverage) for a blank-node range)

Useful for lightweight validation or when you want to add constraints manually.

### Standard Level (Default)

```bash
rdf-construct shacl-gen ontology.ttl --level standard
```

Adds:
- Cardinality restrictions (`owl:cardinality`, `owl:minCardinality`, etc.)
- Functional properties → `sh:maxCount 1`
- `owl:someValuesFrom` → `sh:minCount 1`
- Enumerations (`owl:oneOf` → `sh:in`), whether the range is a named enumerated class, an inline
  `[ owl:oneOf ( … ) ]` or an inline enumerated datatype. Members keep the order the ontology
  lists them in, each once.

### Strict Level

```bash
rdf-construct shacl-gen ontology.ttl --level strict
```

Currently the same as standard. It is kept for constraints a later release may add. Closed shapes
are not a level: `--closed` works at every level (see below).

## Closed Shapes

Generate shapes that reject unexpected properties, at any level:

```bash
rdf-construct shacl-gen ontology.ttl --closed
```

This adds `sh:closed true` to every shape. A closed shape admits `rdf:type`, your
`ignored_properties`, and **every property the class's hierarchy declares**, by `rdfs:domain` or
by an `owl:Restriction`: its own, its superclasses' and its subclasses'. Those that are not already
`sh:property` paths go in `sh:ignoredProperties`, after `rdf:type`. For an `Animal` with a `Dog`
subclass and a `Puppy` below that, each declaring one property, `Animal` restricting `ex:tag`:

```text
shape:AnimalShape a sh:NodeShape ;
    sh:closed true ;
    sh:ignoredProperties ( rdf:type ex:barks ex:wags ) ;
    sh:property [ sh:maxCount 1 ;
            sh:order 2 ;
            sh:path ex:tag ],
        [ sh:datatype xsd:string ;
            sh:order 1 ;
            sh:path ex:name ] ;
    sh:targetClass ex:Animal .
```

**Why both directions:**

- **Superclasses:** an instance carries its superclasses' properties. This holds under
  `--no-inherit` too, where those paths become ignored properties instead of property shapes.
- **Subclasses:** SHACL's `sh:targetClass` also selects instances of subclasses wherever the data
  graph says `rdfs:subClassOf` (data validated together with its ontology, or inferred data). A
  closed `AnimalShape` that didn't admit `ex:barks` would reject every dog.

**The price is on upper classes.** On `tests/fixtures/ies/ies-common.ttl`, the closed shape for
`ies:Thing` admits 174 of the file's 187 domained properties: 8 of its own and 166 from its
subclasses. The more general the class, the less its closure says.

**Still rejected by every closed shape:**

- a property the ontology gives no `rdfs:domain` and no restriction;
- one whose domain is a class expression (`rdfs:domain [ owl:unionOf … ]`);
- one restricted only inside an `owl:equivalentClass` definition, which the generator does not read;
- a subproperty used in place of a domained one.

List them in `ignored_properties`.

The summary line says how many shapes were closed: `(closed shapes enabled: 3 closed)`. It is
printed only when `sh:closed` was written.

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

Write the IRI in angle brackets, as above, or bind the prefix in the ontology. `ignored_properties`
takes effect only with `--closed` (or `closed: true`). Without it, the list has no effect, and the
run says so in a note.

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
default_severity: warning
closed: false
shape_namespace: "http://example.org/building-shapes#"

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
overrides the option's default: `level: minimal` in the file applies unless you pass `--level`.

`shape_namespace` is a full namespace IRI, ending in `#`, `/` or `:`. Anything else, such as the
suffix `"shapes#"`, is refused at exit 2 with nothing written. Leave it out to derive the namespace
(see [Shape IRIs](#shape-iris)).

`generate_property_shapes` was removed in 0.7.0. Nothing ever read it, so a config that still sets
it, even to `false`, is refused at exit 2: delete the line.

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

Set the `sh:severity` of every generated shape:

```bash
rdf-construct shacl-gen ontology.ttl --default-severity warning
```

`sh:severity` goes on every node shape (results from `sh:closed`) and on every property shape. The
values are `violation`, `warning` and `info`. With neither the flag nor `default_severity:` in the
config, no `sh:severity` is written, and SHACL reads that as `sh:Violation`. Setting `violation`
explicitly writes `sh:Violation`.

**Severity doesn't decide conformance.** In SHACL a report conforms only when it has no results at
all, whatever their severity: `sh:Warning` and `sh:Info` change how a result is labelled, not
whether the data conforms. pySHACL reports `Conforms: False` for a report holding only warnings. To
treat warnings as passing, filter the report's results by `sh:resultSeverity`; some processors have
an option for this (pySHACL's `--allow-warnings`).

## OWL Pattern Coverage

### Fully Supported

| OWL Pattern | SHACL Equivalent | From level |
|-------------|------------------|------------|
| `owl:Class`, `rdfs:Class`, `owl:DeprecatedClass` | one `sh:NodeShape` each, `sh:targetClass` | minimal |
| `rdfs:domain` | `sh:property` on the domain's shape | minimal |
| `rdfs:range` (class IRI) | `sh:class` | minimal |
| `rdfs:range` (datatype IRI) | `sh:datatype` | minimal |
| `owl:cardinality` | `sh:minCount` + `sh:maxCount` | standard |
| `owl:minCardinality` | `sh:minCount` | standard |
| `owl:maxCardinality` | `sh:maxCount` | standard |
| `owl:FunctionalProperty` | `sh:maxCount 1` | standard |
| `owl:someValuesFrom` | `sh:minCount 1` + type | standard |
| `owl:allValuesFrom` (IRI) | `sh:class` or `sh:datatype` | standard |
| `owl:oneOf` | `sh:in`, in the ontology's order | standard |
| `owl:qualifiedCardinality` | Cardinality + type (the type only when `owl:onClass`/`owl:onDataRange` is an IRI) | standard |
| `rdfs:label` | `sh:name` | minimal |
| `rdfs:comment` | `sh:description` | minimal |

A deprecated class (`owl:DeprecatedClass`, or `owl:deprecated true`) gets an ordinary shape: its
instances still exist while data migrates, and they still need validating.

### Not Converted (Requires Manual SHACL)

Some OWL patterns cannot be directly expressed in SHACL Core:

- **Complex class expressions** (unions, intersections, inline datatype restrictions). When
  `rdfs:range`, `owl:onClass` or `owl:onDataRange` is a blank node, no `sh:class` or
  `sh:datatype` is written for it. The property shape keeps its other constraints, and an inline
  `owl:oneOf` still gives `sh:in`. `sh:class` and `sh:datatype` take only IRIs.
- **Inverse functional uniqueness** (requires SPARQL)
- **Transitive property closures**
- **Property chains**
- **owl:complementOf**

When these patterns are encountered, the generator continues without them, and nothing reports
that they were dropped ([#229](https://github.com/aigora-de/rdf-construct/issues/229)). Consider
adding SPARQL-based SHACL constraints manually.

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

Shapes are named `<namespace><LocalName>Shape`. `shape_namespace` sets the namespace when it is
given. Otherwise:

- **With an `owl:Ontology`**, the namespace is the ontology IRI with `-shapes#` appended
  (`http://example.org/animals` gives `http://example.org/animals-shapes#`).
- **Without one**, it is the **home namespace**, the namespace that holds the most declared classes
  (ties go to the alphabetically first), with its trailing `#`, `/` or `:` replaced by `-shapes#`.

The local name is the part after the last `#`, else `/`, else `:`, so `<urn:example:Cat>` gives
`CatShape`.

**When two classes share a local name** (`a:Cat` and `b:Cat`), each still gets its own shape:

- the one in the home namespace keeps `CatShape`;
- any other is qualified with its namespace's prefix in the ontology (`b_CatShape`);
- with no prefix bound, it is qualified with a short hash of its namespace (`ns1a2b3c4d_CatShape`).

A home-namespace shape keeps its name when another class with the same local name is added. Only
adding enough classes in another namespace to change which one is home can rename a shape, and then
only a colliding one.

Names and the namespace are worked out over the whole ontology, never the selection, so
`--classes` never renames or moves a shape.

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
| A construct that cannot be expressed (a blank-node range, `owl:hasValue`) is dropped without a report | [#229](https://github.com/aigora-de/rdf-construct/issues/229) |
| An enumerated class's own shape has no `sh:in`, and `sh:class` fails an enumerated member the data does not type | [#488](https://github.com/aigora-de/rdf-construct/issues/488) |
| A property with several `rdfs:range` values is constrained by one of them | [#489](https://github.com/aigora-de/rdf-construct/issues/489) |
| A declared `owl:Thing` gets a shape that targets every typed node | [#490](https://github.com/aigora-de/rdf-construct/issues/490) |
| Output is not byte-identical between runs: blank-node property shapes come out in varying order | [#94](https://github.com/aigora-de/rdf-construct/issues/94) |

## See Also

- [SHACL Specification](https://www.w3.org/TR/shacl/)
- [pySHACL Documentation](https://github.com/RDFLib/pySHACL)
- [CLI Reference](CLI_REFERENCE.md)
