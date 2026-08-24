# Documentation Generator Guide

Generate comprehensive, navigable documentation from RDF ontologies in HTML, Markdown, or JSON formats.

## Quick Start

```bash
# Generate HTML documentation
poetry run rdf-construct docs ontology.ttl

# Generate Markdown for GitHub/GitLab
poetry run rdf-construct docs ontology.ttl --format markdown

# Custom output directory
poetry run rdf-construct docs ontology.ttl -o api-docs/
```

## Output Formats

### HTML

The default format produces a complete, navigable website with:

- Index page with entity listings
- Class hierarchy visualisation
- Individual pages for each class, property, and instance
- Client-side search functionality (needs an HTTP server — see below)
- Responsive CSS styling
- Namespace reference page

```bash
poetry run rdf-construct docs ontology.ttl --format html
```

Output structure:
```
docs/
├── index.html
├── hierarchy.html
├── namespaces.html
├── search.json
├── classes/
│   ├── Building.html
│   └── Room.html
├── properties/
│   ├── object/
│   │   └── hasRoom.html
│   ├── datatype/
│   │   └── hasName.html
│   └── other/
│       └── hasParent.html
├── instances/
│   └── HeadOffice.html
└── assets/
    ├── style.css
    └── search.js
```

### Markdown

Generates GitHub/GitLab-compatible Markdown with YAML frontmatter for static site generators:

```bash
poetry run rdf-construct docs ontology.ttl --format markdown -o wiki/
```

Features:

- Jekyll/Hugo frontmatter support
- Cross-linked pages
- Table of contents
- Namespace tables

### JSON

Produces structured JSON for custom rendering or API integration:

```bash
poetry run rdf-construct docs ontology.ttl --format json
```

The JSON output includes:

- Complete ontology metadata
- All entity information
- Hierarchy structure
- Suitable for building custom documentation UIs

#### JSON schema (v0.5.0+)

The top-level shape of `index.json` is:

```json
{
  "ontology": { "uri": "...", "title": "...", ... },
  "statistics": {
    "classes": 12,
    "object_properties": 8,
    "datatype_properties": 5,
    "annotation_properties": 2,
    "other_properties": 1,
    "instances": 3,
    "shapes": 4,
    "concepts": 7,
    "concept_schemes": 2
  },
  "classes":               [{ "uri": "...", "qname": "...", "label": "..." }, ...],
  "object_properties":     [{ "uri": "...", "qname": "...", "label": "..." }, ...],
  "datatype_properties":   [{ "uri": "...", "qname": "...", "label": "..." }, ...],
  "annotation_properties": [{ "uri": "...", "qname": "...", "label": "..." }, ...],
  "other_properties":      [{ "uri": "...", "qname": "...", "label": "..." }, ...],
  "instances":             [{ "uri": "...", "qname": "...", "label": "..." }, ...],
  "shapes":                [{ "uri": "...", "qname": "...", "label": "...",
                              "kinds": ["shape", "node_shape"] }, ...],
  "concepts":              [{ "uri": "...", "qname": "...", "label": "...",
                              "kinds": ["skos_concept"] }, ...],
  "concept_schemes":       [{ "uri": "...", "qname": "...", "label": "...",
                              "kinds": ["skos_concept_scheme"] }, ...]
}
```

Each entity also gets a full per-page JSON file under its type directory
(`classes/`, `properties/object/`, `properties/datatype/`,
`properties/annotation/`, `properties/other/`, `instances/`, `shapes/`, or
`concepts/`).
Per-page files contain the complete entity record including all fields.

> **Breaking change in v0.5.0.** SHACL shapes
> (`sh:NodeShape` / `sh:PropertyShape` instances) used to appear in the
> `instances` array because the extractor didn't filter them out.
> v0.5.0 introduces a top-level `shapes` array; shapes no longer appear
> in `instances`. JSON consumers updating from v0.4.x must read both
> arrays. See "SHACL Shapes" below for the per-page schema.

> **Breaking change in v0.6.0.** SKOS concepts and concept schemes
> (`skos:Concept` / `skos:ConceptScheme`) used to appear in the
> `instances` array for the same reason. v0.6.0 introduces top-level
> `concepts` and `concept_schemes` arrays; neither appears in
> `instances` any more. See "SKOS Vocabularies" below for the per-page
> schema.

## Search

HTML output ships a client-side search index (`search.json`) and a small
overlay. It works from any page at any depth, and honours `base_url` when
one is set.

**It needs the docs to be served over HTTP.** Browsers block `fetch` on
`file://` for security reasons regardless of the path, so search cannot
work from a double-clicked `index.html`. The box disables itself and says
so rather than appearing to work. Any static server will do:

```bash
poetry run rdf-construct docs ontology.ttl -o docs/
cd docs && python3 -m http.server 8000
```

Disable the index entirely with `--no-search`.

## Properties Whose Kind the Source Does Not State

Ontologies declare properties in more ways than the obvious four types, and
`docs` recognises all of them.

**Where the kind is inferable, it is used.** `owl:TransitiveProperty`,
`owl:SymmetricProperty`, `owl:AsymmetricProperty`, `owl:ReflexiveProperty`,
`owl:IrreflexiveProperty` and `owl:InverseFunctionalProperty` are all
subclasses of `owl:ObjectProperty` in OWL 2, so a term declared *solely*
with one of them is documented as an object property:

```turtle
ex:hasPart a owl:TransitiveProperty .   # an object property
```

**Where it is not inferable, the term is not guessed at.**
`owl:FunctionalProperty` and `owl:DeprecatedProperty` are subclasses of
`rdf:Property` only — nothing in the source says whether such a term is an
object property or a datatype property:

```turtle
ex:hasParent a owl:FunctionalProperty .  # kind unstated
```

These, along with plain `rdf:Property` declarations, are documented under
`properties/other/` with a neutral `rdf property` badge, listed in an
**Other Properties** section, and given their own `other_properties` array
in JSON output. The badge says the source did not state a kind; it does not
claim a fourth kind exists.

`owl:DeprecatedClass` gets the same treatment on the class side — a term
declared only with it is documented as a class.

Before this, every one of these was extracted as a generic **instance** and
documented as an individual, and `rdf:Property`-only terms got no page at
all.

## SHACL Shapes

`rdf-construct docs` recognises SHACL shapes (`sh:NodeShape` and
`sh:PropertyShape`) as a first-class entity type, alongside Classes,
Properties, and Instances. NodeShapes and named PropertyShapes get
their own pages; blank-node PropertyShapes attached to a NodeShape via
`sh:property` are rendered inline on the parent shape's page.

A NodeShape that is also typed as `owl:NamedIndividual` is treated as a
shape (it appears in the Shapes section, not in Instances) and carries
the `named individual` badge as well. The `kinds` field on each shape
entry carries the full multi-kind list so JSON consumers can
distinguish, for example, an `owl:NamedIndividual`-flagged NodeShape
from a plain one.

Twenty-one SHACL constraints get explicit per-format rendering:

`sh:path`, `sh:minCount`, `sh:maxCount`, `sh:datatype`, `sh:class`,
`sh:nodeKind`, `sh:in`, `sh:hasValue`, `sh:pattern`, `sh:minLength`,
`sh:maxLength`, `sh:minInclusive`, `sh:maxInclusive`, `sh:targetClass`,
`sh:targetNode`, `sh:targetSubjectsOf`, `sh:targetObjectsOf`,
`sh:closed`, `sh:ignoredProperties`, `sh:name`, `sh:description`.

Anything outside that list (e.g. `sh:severity`, `sh:order`,
`sh:qualifiedValueShape`) is rendered in a generic key-value fallback
so it stays visible without bespoke template work. Logical operators
(`sh:and` / `sh:or` / `sh:xone`) are deferred — a future release will
give them dedicated rendering.

### Shape JSON schema

A full shape entry (in per-page files and in the `shapes` array of
`render_single_page` output) looks like:

```json
{
  "uri": "http://example.org/PersonShape",
  "qname": "ex:PersonShape",
  "kinds": ["shape", "node_shape"],
  "label": "Person Shape",
  "definition": "Constraints on Person instances.",
  "target_classes":      ["http://example.org/Person"],
  "target_nodes":        [],
  "target_subjects_of":  [],
  "target_objects_of":   [],
  "closed": false,
  "ignored_properties": [],
  "properties": [
    {
      "uri": null,
      "qname": null,
      "is_blank": true,
      "path": "http://example.org/hasName",
      "name": null,
      "description": null,
      "datatype": "http://www.w3.org/2001/XMLSchema#string",
      "class": null,
      "node_kind": null,
      "min_count": 1,
      "max_count": 1,
      "min_length": null,
      "max_length": 100,
      "min_inclusive": null,
      "max_inclusive": null,
      "pattern": null,
      "has_value": null,
      "in_values": [],
      "other_constraints": {
        "http://www.w3.org/ns/shacl#severity": [
          "http://www.w3.org/ns/shacl#Violation"
        ]
      }
    }
  ],
  "property_shape": null,
  "annotations": {},
  "other_constraints": {}
}
```

Schema notes:

- `kinds` is the multi-kind list (always includes `"shape"`; also
  contains `"node_shape"` and/or `"property_shape"` as appropriate).
- `class` (without trailing underscore) is used as the JSON key for
  the `sh:class` constraint on PropertyShapes — matching the SHACL
  spec.
- `in_values` (rather than `in`) avoids the Python keyword issue at
  the consumer end too.
- `is_blank` distinguishes blank-node PropertyShapes (no stable URI)
  from named PropertyShapes (which also appear as standalone entries
  in the `shapes` array).
- `property_shape` is non-`null` only when the entity is itself a
  PropertyShape; for NodeShapes it is `null` and the property
  constraints live in `properties`.
- `other_constraints` is a `predicate URI -> [values]` map for any
  SHACL predicate not in the first-class set. Order is the order in
  which the predicates were encountered.

## SKOS Vocabularies

`rdf-construct docs` recognises `skos:Concept` and `skos:ConceptScheme`
as a first-class entity type, so a controlled vocabulary documents as a
vocabulary rather than as a heap of generic instances. Concepts and
schemes share the `concepts/` directory and are told apart by their kind
badges (`skos concept`, `skos concept scheme`) — the same arrangement
NodeShapes and PropertyShapes have in `shapes/`.

Each concept page carries:

- **Labels grouped by language.** One row per language tag, with
  `skos:prefLabel`, `skos:altLabel` and `skos:hiddenLabel` side by side,
  so "what does this look like in French" is one line rather than a
  scatter of duplicate triples.
- **Semantic relations.** `skos:broader`, `skos:narrower` and
  `skos:related`, rendered as cross-links.
- **Scheme membership.** `skos:inScheme` and `skos:topConceptOf`, linking
  to the scheme page; the scheme page lists its members in return.
- **All seven SKOS documentation properties** — `skos:definition`,
  `skos:scopeNote`, `skos:example`, `skos:note`, `skos:historyNote`,
  `skos:editorialNote` and `skos:changeNote` — each keeping its language
  tag.
- **Anything else asserted about the concept**, including mappings such
  as `skos:exactMatch`, in a visible key-value fallback rather than being
  dropped.

The scheme page additionally carries the vocabulary's
`skos:broader`/`skos:narrower` tree.

### What the renderer infers, and what it does not

- **`skos:broader` and `skos:narrower` are treated as inverses**, because
  SKOS declares them to be. A vocabulary that only ever asserts one
  direction still documents both, and the hierarchy is the same either
  way. `skos:related` is likewise treated as symmetric, and
  `skos:topConceptOf` as implying `skos:inScheme` (it is a sub-property
  of it).
- **`skos:broader` is not `rdfs:subClassOf`.** It renders as a tree
  because that is how vocabularies are navigated, not because a concept
  hierarchy is a class hierarchy; nothing is inherited along it.
- **Cycles are tolerated.** SKOS does not promise an acyclic hierarchy.
  The tree walker will not expand a concept twice on one path, and any
  concept a cycle leaves unreachable is promoted to a root of its own
  rather than disappearing.
- **A concept in no scheme is still documented.** It appears in the index
  and gets its own page; only the per-scheme tree needs a scheme.

### Punning: a subject that is a concept *and* something else

Classes, properties and SHACL shapes outrank SKOS in routing, so a
subject typed both `owl:Class` and `skos:Concept` keeps its class page
and does not get a second page under `concepts/`. It stays visible in
its scheme's member list, which links to the class page. A concept that
is also `owl:NamedIndividual` routes to `concepts/`.

### Concept JSON schema

```json
{
  "uri": "http://example.org/vocab#Building",
  "qname": "ex:Building",
  "kinds": ["skos_concept"],
  "label": "Building",
  "definition": "A permanent, roofed construction intended for occupation.",
  "labels": [
    { "language": "en", "preferred": ["Building"],
      "alternative": ["Structure"], "hidden": ["buildin"] },
    { "language": "fr", "preferred": ["Bâtiment"],
      "alternative": ["Édifice"], "hidden": [] }
  ],
  "notes": {
    "definition": [
      { "text": "A permanent, roofed construction...", "language": "en" },
      { "text": "Construction permanente et couverte...", "language": "fr" }
    ],
    "scopeNote": [{ "text": "Excludes temporary structures.", "language": "en" }]
  },
  "broader":        [],
  "narrower":       ["http://example.org/vocab#Dwelling"],
  "related":        [],
  "in_schemes":     ["http://example.org/vocab#BuildingScheme"],
  "top_concept_of": ["http://example.org/vocab#BuildingScheme"],
  "types":          ["http://www.w3.org/2004/02/skos/core#Concept"],
  "properties":     {},
  "annotations":    {}
}
```

A concept scheme entry carries `labels`, `notes`, `top_concepts`,
`concepts` (its members) and — in the per-page file only — `hierarchy`,
the nested broader/narrower tree, so a consumer does not have to rebuild
it:

```json
{
  "qname": "ex:BuildingScheme",
  "kinds": ["skos_concept_scheme"],
  "top_concepts": ["http://example.org/vocab#Building"],
  "concepts": ["http://example.org/vocab#Building", "..."],
  "hierarchy": [
    { "uri": "...", "qname": "ex:Building", "label": "Building",
      "children": [{ "qname": "ex:Dwelling", "children": [] }] }
  ]
}
```

Schema notes:

- An untagged literal appears under `"language": ""` rather than being
  dropped.
- `broader` and `narrower` include inverse-derived neighbours, as
  described above.
- `notes` keys are the SKOS property local names.

Not covered: `skos:Collection` / `skos:OrderedCollection` and SKOS-XL
(`skosxl:Label`). Both fall through to their existing treatment; file an
issue if a real vocabulary needs them.

## Named Individuals

An entity explicitly typed `owl:NamedIndividual` carries a
`named individual` badge alongside whatever else it is, and its `kinds`
list gains `"named_individual"`.

This is a *refinement*, not a bucket: named individuals stay exactly
where they were routed. An individual stays under `instances/`, a
concept under `concepts/`, a shape under `shapes/`. There is no
`named_individuals/` directory, no new top-level JSON array and no CLI
flag — nothing about this stage is a breaking change.

What the badge tells you is that the **source says so**. Three cases:

| Source | Kinds | Why |
|---|---|---|
| `:alice a :Person, owl:NamedIndividual` | `["instance", "named_individual"]` | Declared, though the class typing already implies it |
| `:bob a :Person` | `["instance"]` | Nothing declared — no badge |
| `:carol a owl:NamedIndividual` | `["instance", "named_individual"]` | The declaration is the only thing saying Carol is an individual |

The badge shows on `:alice` even though the declaration is **redundant**
in OWL DL terms — `:Person` already makes her an individual, and a
reasoner would infer the `owl:NamedIndividual` typing anyway. It is
surfaced because `kinds` records what the source asserts rather than
what could be inferred, which is the same policy every other kind
follows. In practice the distinction tells you something real: tools
like Protégé emit these declarations consistently, hand-written
ontologies often omit them, and seeing which you have is useful when
merging the two.

Not covered: `rdfs:Datatype`, and the deprecation markers
`owl:DeprecatedClass` / `owl:DeprecatedProperty`. Deprecation is
orthogonal to entity kind — a deprecated class and a deprecated property
want different visual treatment — so it needs its own design rather than
another kind.

## Command Options

```bash
rdf-construct docs [OPTIONS] SOURCES...
```

| Option | Description |
|--------|-------------|
| `SOURCES` | One or more RDF files (Turtle, RDF/XML, etc.) |
| `-o, --output PATH` | Output directory (default: `docs/`) |
| `-f, --format FORMAT` | Output format: `html`, `markdown`, `json` |
| `-C, --config PATH` | Configuration YAML file |
| `-t, --template PATH` | Custom template directory |
| `--single-page` | Generate single-page documentation |
| `--title TEXT` | Override ontology title |
| `--no-search` | Disable search index (HTML only) |
| `--no-instances` | Exclude instances from output |
| `--no-shapes` | Exclude SHACL shapes from output |
| `--no-skos` | Exclude SKOS concepts and concept schemes from output |
| `--include TYPES` | Include only these types (comma-separated) |
| `--exclude TYPES` | Exclude these types (comma-separated) |

### Entity Type Filtering

Filter which entity types appear in the documentation:

```bash
# Only classes and properties (no instances or shapes)
poetry run rdf-construct docs ontology.ttl --exclude instances,shapes

# Only classes
poetry run rdf-construct docs ontology.ttl --include classes

# Classes and shapes only
poetry run rdf-construct docs ontology.ttl --include classes,shapes

# A vocabulary's SKOS entities only
poetry run rdf-construct docs vocabulary.ttl --include concepts
```

Valid type names: `classes`, `properties`, `object_properties`, `datatype_properties`, `annotation_properties`, `other_properties`, `instances`, `shapes`, `concepts`

`properties` covers all four property groups, `other_properties` included.

Excluding a type removes its pages, its index section and its statistics
card. References to it from pages that *are* generated stay visible but
stop being links — a class page still lists the properties whose domain it
is, in code formatting rather than as links to pages this run did not
write.

`concepts` covers both SKOS kinds — concepts and concept schemes are one
toggle. `concept_schemes` and `skos` are accepted as spellings of it.

## Configuration File

For complex documentation setups, use a YAML configuration file:

```yaml
# docs-config.yml
output_dir: docs/
format: html
title: "Building Ontology Documentation"
language: en

include_classes: true
include_object_properties: true
include_datatype_properties: true
include_annotation_properties: false
include_other_properties: true
include_instances: true
include_shapes: true
include_skos: true

include_search: true
include_hierarchy: true
include_statistics: true

# Exclude standard ontology namespaces
exclude_namespaces:
  - http://www.w3.org/2002/07/owl#
  - http://www.w3.org/2000/01/rdf-schema#
```

Use with:

```bash
poetry run rdf-construct docs ontology.ttl --config docs-config.yml
```

## Custom Templates

Override the default templates with your own Jinja2 templates:

```bash
poetry run rdf-construct docs ontology.ttl --template my-templates/
```

Template directory structure:

```
my-templates/
├── html/
│   ├── base.html.jinja      # Base layout
│   ├── index.html.jinja     # Index page
│   ├── class.html.jinja     # Class pages
│   ├── property.html.jinja  # Property pages
│   ├── instance.html.jinja  # Instance pages
│   ├── hierarchy.html.jinja # Hierarchy page
│   ├── namespaces.html.jinja
│   └── single_page.html.jinja
└── assets/
    └── style.css            # Custom stylesheet
```

### Template Variables

All templates receive these context variables:

| Variable | Description |
|----------|-------------|
| `ontology` | Ontology metadata (title, description, namespaces) |
| `classes` | List of all ClassInfo objects |
| `object_properties` | List of object PropertyInfo objects |
| `datatype_properties` | List of datatype PropertyInfo objects |
| `annotation_properties` | List of annotation PropertyInfo objects |
| `instances` | List of InstanceInfo objects |
| `shapes` | List of all ShapeInfo objects (NodeShapes and named PropertyShapes) |
| `node_shapes` | NodeShapes only (filtered subset of `shapes`) |
| `property_shapes` | Named PropertyShapes only (filtered subset of `shapes`) |
| `config` | DocsConfig settings |

Entity-specific templates also receive:

- `class.html.jinja`: `class_info`, `inherited_properties`
- `property.html.jinja`: `property_info`
- `instance.html.jinja`: `instance_info`
- `shape.html.jinja`: `shape_info`
- `hierarchy.html.jinja`: `hierarchy` (tree structure)

### Custom Filters

Templates have access to these custom Jinja2 filters:

| Filter | Usage | Description |
|--------|-------|-------------|
| `entity_url` | `{{ qname \| entity_url('class') }}` | Generate URL to entity page |
| `qname_local` | `{{ qname \| qname_local }}` | Extract local name from QName |

## Multiple Source Files

Merge multiple ontology files into a single documentation set:

```bash
# Primary ontology + imported foundation
poetry run rdf-construct docs domain.ttl foundation.ttl -o docs/

# Multiple domain ontologies
poetry run rdf-construct docs buildings.ttl people.ttl events.ttl
```

The graphs are merged before documentation generation, so cross-references between files will work correctly.

## Single-Page Documentation

Generate all documentation in a single HTML or Markdown file:

```bash
poetry run rdf-construct docs ontology.ttl --single-page
```

This is useful for:

- Small ontologies
- PDF generation (print the single page)
- Offline documentation
- Quick reference sheets

## Programmatic Usage

Use the docs module directly in Python:

```python
from pathlib import Path
from rdf_construct.docs import DocsConfig, DocsGenerator, generate_docs

# Simple usage
result = generate_docs(
    source=Path("ontology.ttl"),
    output_dir=Path("docs/"),
    output_format="html",
)
print(f"Generated {result.total_pages} pages")

# With configuration
config = DocsConfig(
    output_dir=Path("api-docs/"),
    format="markdown",
    title="API Reference",
    include_instances=False,
    include_search=False,
)

generator = DocsGenerator(config)
result = generator.generate_from_file(Path("ontology.ttl"))
```

### Working with Extracted Entities

Access extracted entity information directly:

```python
from rdflib import Graph
from rdf_construct.docs import extract_all

graph = Graph()
graph.parse("ontology.ttl", format="turtle")

entities = extract_all(graph)

# Access ontology metadata
print(f"Title: {entities.ontology.title}")
print(f"Namespaces: {len(entities.ontology.namespaces)}")

# Iterate over classes
for cls in entities.classes:
    print(f"Class: {cls.qname}")
    print(f"  Label: {cls.label}")
    print(f"  Superclasses: {len(cls.superclasses)}")
    print(f"  Properties: {len(cls.domain_of)}")
```

## Examples

### Basic HTML Documentation

```bash
poetry run rdf-construct docs examples/animal_ontology.ttl -o animal-docs/
```

### Markdown Wiki

```bash
poetry run rdf-construct docs ontology.ttl \
    --format markdown \
    --title "Ontology Wiki" \
    -o wiki/
```

### JSON for Custom UI

```bash
poetry run rdf-construct docs ontology.ttl \
    --format json \
    --single-page \
    -o api/
```

### Production Documentation

```bash
poetry run rdf-construct docs \
    domain.ttl foundation.ttl \
    --config docs-config.yml \
    --template corporate-templates/ \
    -o public/docs/
```

## Tips

### Improving Documentation Quality

1. **Add labels and comments** to all entities in your ontology — these become the documentation text
2. **Use `rdfs:label`** for display names and `rdfs:comment` for definitions
3. **Define domain/range** on properties to show relationships in class pages
4. **Use consistent naming** — QNames become filenames and URLs

### Deployment

The HTML output is static and can be deployed to:

- GitHub Pages
- GitLab Pages
- Any static hosting (S3, Netlify, etc.)
- Local file server

For GitHub Pages, output directly to the `docs/` folder and enable Pages in repository settings.

### Styling

To customise the appearance without creating full custom templates:

1. Generate documentation with default templates
2. Copy `assets/style.css` and modify
3. Use `--template` with just the modified CSS in an assets folder

## See Also

- **[Getting Started](GETTING_STARTED.md)** — Installation and first steps
- **[UML Guide](UML_GUIDE.md)** — Generate diagrams alongside documentation
- **[CLI Reference](CLI_REFERENCE.md)** — Complete command reference
