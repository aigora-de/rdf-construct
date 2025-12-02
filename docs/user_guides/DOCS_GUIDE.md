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
- Client-side search functionality
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
│   └── datatype/
│       └── hasName.html
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
| `--include TYPES` | Include only these types (comma-separated) |
| `--exclude TYPES` | Exclude these types (comma-separated) |

### Entity Type Filtering

Filter which entity types appear in the documentation:

```bash
# Only classes and properties (no instances)
poetry run rdf-construct docs ontology.ttl --exclude instances

# Only classes
poetry run rdf-construct docs ontology.ttl --include classes

# Classes and object properties only
poetry run rdf-construct docs ontology.ttl --include classes,object_properties
```

Valid type names: `classes`, `properties`, `object_properties`, `datatype_properties`, `annotation_properties`, `instances`

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
include_instances: true

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
| `config` | DocsConfig settings |

Entity-specific templates also receive:

- `class.html.jinja`: `class_info`, `inherited_properties`
- `property.html.jinja`: `property_info`
- `instance.html.jinja`: `instance_info`
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