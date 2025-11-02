# UML Diagram Generation Guide

## Overview

Generate PlantUML class diagrams from RDF ontologies with full control over what's included, how it's styled, and how it's arranged.

## Table of Contents

- [Basic Usage](#basic-usage)
- [Context Configuration](#context-configuration)
- [Class Selection](#class-selection)
- [Property Filtering](#property-filtering)
- [Instance Rendering](#instance-rendering)
- [Styling](#styling)
- [Layout Control](#layout-control)
- [Complete Examples](#complete-examples)

## Basic Usage

### Generate Diagrams

```bash
# All contexts in config
poetry run rdf-construct uml ontology.ttl config.yml

# Specific context
poetry run rdf-construct uml ontology.ttl config.yml -c my_context

# With styling and layout
poetry run rdf-construct uml ontology.ttl config.yml \
  --style-config styles.yml --style default \
  --layout-config layouts.yml --layout hierarchy
```

### List Contexts

```bash
poetry run rdf-construct contexts config.yml
```

## Context Configuration

### Basic Structure

```yaml
contexts:
  context_name:
    description: "Human-readable description"
    
    # Class selection (choose one strategy)
    root_classes: [...]        # Start from roots
    focus_classes: [...]       # Explicit list
    selector: classes          # Use selector
    
    # Options
    include_descendants: true
    max_depth: 3
    
    # Properties
    properties:
      mode: domain_based
      include: [...]
      exclude: [...]
    
    # Instances
    include_instances: false
```

## Class Selection

### Strategy 1: Root Classes

**Use Case**: Show a hierarchy starting from specific concepts.

```yaml
animal_taxonomy:
  description: "Complete animal hierarchy"
  root_classes:
    - ex:Animal
  include_descendants: true
  max_depth: null  # No limit
```

**What You Get**:
- ex:Animal
- ex:Mammal (subclass of Animal)
- ex:Dog (subclass of Mammal)
- ex:Cat (subclass of Mammal)
- ex:Bird (subclass of Animal)
- etc.

**With Depth Limit**:
```yaml
mammals_shallow:
  root_classes:
    - ex:Mammal
  include_descendants: true
  max_depth: 1  # Only direct subclasses
```

**Result**: Mammal, Dog, Cat (but not further subclasses of Dog/Cat).

### Strategy 2: Focus Classes

**Use Case**: Hand-pick specific classes, regardless of hierarchy.

```yaml
key_concepts:
  description: "Important classes only"
  focus_classes:
    - ex:Animal
    - ex:Dog
    - ex:Eagle
  include_descendants: false
```

**What You Get**: Exactly those three classes, nothing more.

**With Descendants**:
```yaml
key_concepts_expanded:
  focus_classes:
    - ex:Mammal
    - ex:Bird
  include_descendants: true  # Include subclasses
  max_depth: 2
```

**Result**: Mammal, Bird, and their descendants up to 2 levels deep.

### Strategy 3: Selector

**Use Case**: Bulk selection using predefined criteria.

```yaml
all_classes:
  description: "Everything in the ontology"
  selector: classes  # All owl:Class / rdfs:Class
```

**Available Selectors**:
- `classes`: All classes
- `obj_props`: All object properties
- `data_props`: All datatype properties

## Property Filtering

### Mode: domain_based (Default)

**Include properties where domain is in selected classes.**

```yaml
properties:
  mode: domain_based
```

**Example**: If you selected `ex:Animal`, you'll get:
- `ex:averageWeight` (domain: Animal)
- `ex:lifespan` (domain: Animal)
- `ex:hasParent` (domain: Animal)

### Mode: connected

**Include only properties connecting selected classes.**

```yaml
properties:
  mode: connected
```

**Example**: If you selected `ex:Animal` and `ex:Habitat`:
- ✓ `ex:livesIn` (domain: Animal, range: Habitat)
- ✗ `ex:averageWeight` (domain: Animal, range: decimal)

**Use Case**: Show relationships between specific concepts.

### Mode: explicit

**Hand-pick properties to include.**

```yaml
properties:
  mode: explicit
  include:
    - ex:hasParent
    - ex:eats
  exclude:
    - ex:scientificName
```

**Result**: Only hasParent and eats shown, regardless of domain/range.

### Mode: all

**Include all properties in the ontology.**

```yaml
properties:
  mode: all
```

**Use Case**: Comprehensive documentation diagrams.

### Mode: none

**No properties, just class hierarchy.**

```yaml
properties:
  mode: none
```

**Use Case**: Simple structure overview.

## Instance Rendering

### Enable Instances

```yaml
with_examples:
  root_classes:
    - ex:Dog
  include_descendants: true
  include_instances: true  # Show individuals
```

**Output**:
```plantuml
class "ex:Dog" {
  +lifespan : integer
}

object "Fido" as "ex:Fido" {
  lifespan = 12
}

"ex:Fido" ..|> "ex:Dog"
```

### Instance Features

- **Display names**: Uses `rdfs:label` if available
- **Property values**: Shows datatype property values
- **Type relationships**: Dotted arrows to classes

## Styling

### Using Style Schemes

```bash
poetry run rdf-construct uml ontology.ttl config.yml \
  --style-config examples/uml_styles.yml \
  --style ies_semantic
```

### Available Styles

**default**: Professional blue scheme
```yaml
schemes:
  default:
    classes:
      default:
        border: "#0066CC"
        fill: "#E8F4F8"
```

**ies_semantic**: IES ontology with metaclass colors
```yaml
schemes:
  ies_semantic:
    classes:
      by_namespace:
        ies:
          border: "#0066CC"
          fill: "#E8F4F8"
      by_type:
        meta_class:
          border: "#CC0000"
          fill: "#FFE6E6"
```

**high_contrast**: Bold colors for presentations
```yaml
schemes:
  high_contrast:
    classes:
      by_namespace:
        ex:
          border: "#000000"
          fill: "#FFEB3B"
```

**grayscale**: Black and white for academic papers
```yaml
schemes:
  grayscale:
    classes:
      by_namespace:
        ies:
          border: "#000000"
          fill: "#CCCCCC"
```

**minimal**: Bare-bones for debugging
```yaml
schemes:
  minimal:
    classes:
      default:
        border: "#000000"
        fill: "#FFFFFF"
```

### Custom Style Configuration

Create `my_styles.yml`:

```yaml
schemes:
  my_scheme:
    description: "My custom colors"
    
    # Class styling
    classes:
      by_namespace:
        ex:
          border: "#2E7D32"  # Green border
          fill: "#E8F5E9"    # Light green fill
          line_style: bold
      
      by_type:
        meta_class:
          border: "#CC0000"  # Red for metaclasses
          fill: "#FFE6E6"
      
      default:
        border: "#000000"
        fill: "#FFFFFF"
    
    # Instance styling
    instances:
      border: "#000000"
      fill: "#000000"
      text: "#FFFFFF"
      inherit_class_border: true  # Use parent class color
    
    # Arrow styling
    arrows:
      subclass:
        color: "#0066CC"
        style: bold
      
      rdf_type:
        color: "#D32F2F"
        style: bold
    
    # Stereotypes
    show_stereotypes: true
    stereotype_map:
      owl:Class: "«class»"
      ies:ClassOfElement: "«meta»"
```

Then use:
```bash
poetry run rdf-construct uml ontology.ttl config.yml \
  --style-config my_styles.yml --style my_scheme
```

## Layout Control

### Using Layouts

```bash
poetry run rdf-construct uml ontology.ttl config.yml \
  --layout-config examples/uml_layouts.yml \
  --layout hierarchy
```

### Available Layouts

**hierarchy**: Top-down with parents above
```yaml
layouts:
  hierarchy:
    direction: top_to_bottom
    arrow_direction: up  # Children point up to parents
```

**flat**: Left-to-right for networks
```yaml
layouts:
  flat:
    direction: left_to_right
    arrow_direction: right
```

**compact**: Minimal spacing
```yaml
layouts:
  compact:
    direction: top_to_bottom
    hide_empty_members: true
    spacing:
      classMarginTop: 5
      classMarginBottom: 5
```

**documentation**: Grouped by namespace
```yaml
layouts:
  documentation:
    direction: top_to_bottom
    group_by_namespace: true
```

**presentation**: Large spacing for slides
```yaml
layouts:
  presentation:
    direction: top_to_bottom
    spacing:
      classMarginTop: 20
      classMarginBottom: 20
```

### Custom Layout Configuration

Create `my_layouts.yml`:

```yaml
layouts:
  my_layout:
    description: "My custom arrangement"
    direction: top_to_bottom
    arrow_direction: up
    hide_empty_members: false
    group_by_namespace: false
    spacing:
      classMarginTop: 10
      classMarginBottom: 10
```

## Complete Examples

### Example 1: Animal Taxonomy

**Goal**: Show complete animal class hierarchy with properties.

**Config**:
```yaml
contexts:
  animal_taxonomy:
    description: "Complete animal hierarchy"
    root_classes:
      - ex:Animal
    include_descendants: true
    properties:
      mode: domain_based
    include_instances: false
```

**Generate**:
```bash
poetry run rdf-construct uml examples/animal_ontology.ttl config.yml \
  -c animal_taxonomy \
  --style-config examples/uml_styles.yml --style default \
  --layout-config examples/uml_layouts.yml --layout hierarchy
```

**Result**:
- 7 classes (Animal, Mammal, Bird, Dog, Cat, Eagle, Sparrow)
- 5 properties (hasParent, eats, livesIn, averageWeight, lifespan)
- Clean top-down hierarchy

### Example 2: Management Structure

**Goal**: Show management relationships with actual people.

**Config**:
```yaml
contexts:
  management:
    description: "Management and reporting"
    focus_classes:
      - org:Manager
      - org:Employee
      - org:CEO
    properties:
      mode: explicit
      include:
        - org:manages
        - org:reportsTo
    include_instances: true
```

**Generate**:
```bash
poetry run rdf-construct uml examples/organisation_ontology.ttl config.yml \
  -c management \
  --style-config examples/uml_styles.yml --style high_contrast \
  --layout-config examples/uml_layouts.yml --layout compact
```

**Result**:
- 3 classes (Manager, Employee, CEO)
- 2 properties (manages, reportsTo)
- 4 instances (Alice, Bob, Carol, Dave with their roles)

### Example 3: Focused View

**Goal**: Show specific classes with selected relationships.

**Config**:
```yaml
contexts:
  key_relationships:
    description: "Core concepts and relationships"
    focus_classes:
      - ex:Animal
      - ex:Dog
      - ex:Cat
    include_descendants: false
    properties:
      mode: explicit
      include:
        - ex:hasParent
      exclude:
        - ex:scientificName
    include_instances: false
```

**Generate**:
```bash
poetry run rdf-construct uml examples/animal_ontology.ttl config.yml \
  -c key_relationships \
  --style-config examples/uml_styles.yml --style minimal
```

**Result**:
- 3 classes (Animal, Dog, Cat)
- 1 property (hasParent)
- Minimal styling for clarity

## Advanced Techniques

### Multiple Root Hierarchies

```yaml
org_structure:
  description: "Multiple hierarchies in one diagram"
  root_classes:
    - org:Organisation
    - org:Person
    - org:Department
  include_descendants: true
```

**Result**: Three separate hierarchies in one diagram.

### Mixed Selection Strategies

```yaml
custom_view:
  description: "Combine root and focus"
  root_classes:
    - ex:Mammal  # Include this hierarchy
  focus_classes:
    - ex:Eagle   # Plus this specific class
  include_descendants: true
  max_depth: 2
```

**Result**: Mammal hierarchy (2 levels) plus Eagle.

### Property Exclusions

```yaml
no_metadata:
  root_classes:
    - ex:Animal
  include_descendants: true
  properties:
    mode: domain_based
    exclude:
      - ex:scientificName
      - ex:commonName
```

**Result**: All domain-based properties except the excluded ones.

## Tips for Great Diagrams

### Start Small

Begin with a single root class:
```yaml
simple_start:
  root_classes:
    - your:KeyClass
  include_descendants: true
  max_depth: 1
```

Generate, view, iterate.

### Use Depth Limiting

For large ontologies:
```yaml
limited_depth:
  root_classes:
    - ies:Element
  include_descendants: true
  max_depth: 3  # Prevent explosion
```

### Choose Property Mode Carefully

- **Quick overview**: `mode: none`
- **Structure with context**: `mode: domain_based`
- **Focused relationships**: `mode: explicit`
- **Complete reference**: `mode: all`

### Match Style to Audience

- **Internal docs**: `default` style
- **Presentations**: `high_contrast` style
- **Academic papers**: `grayscale` style
- **Debugging**: `minimal` style

### Match Layout to Content

- **Hierarchies**: `hierarchy` layout
- **Networks**: `flat` or `network` layout
- **Quick reference**: `compact` layout
- **Detailed docs**: `documentation` layout

## Rendering Diagrams

### Online PlantUML Editor

1. Go to https://www.plantuml.com/plantuml/
2. Paste `.puml` file contents
3. View rendered diagram
4. Download as PNG/SVG

### VS Code

1. Install "PlantUML" extension
2. Open `.puml` file
3. Press `Alt+D` to preview

### Command Line

```bash
# Install PlantUML
brew install plantuml  # macOS
apt install plantuml   # Ubuntu

# Render to PNG
plantuml diagram.puml

# Render to SVG
plantuml -tsvg diagram.puml
```

## Troubleshooting

### Classes Not Showing

**Check**:
1. CURIE format: `ex:Animal` not `Animal`
2. Namespace prefix matches ontology
3. Class exists in ontology

**Debug**:
```python
from rdflib import Graph, RDF, OWL
g = Graph().parse("ontology.ttl", format="turtle")
classes = list(g.subjects(RDF.type, OWL.Class))
for cls in classes:
    print(g.namespace_manager.normalizeUri(cls))
```

### Properties Not Showing

**Check**:
1. Property mode setting
2. Domain/range match selected classes
3. Property exists in ontology

### Layout Issues

**Remember**: PlantUML's layout is heuristic. Arrow direction hints help but don't guarantee.

**Try**:
- Different `arrow_direction` values
- Adjusting spacing
- Different PlantUML renderer

### Namespace Conflicts

**Problem**: `org:` in config doesn't match ontology.

**Solution**: Check actual prefixes:
```python
from rdflib import Graph
g = Graph().parse("ontology.ttl", format="turtle")
for pfx, ns in g.namespace_manager.namespaces():
    if pfx: print(f"{pfx}: {ns}")
```

Use the assigned prefix.

## Next Steps

- **[Getting Started](GETTING_STARTED.md)**: Quick start guide
- **[CLI Reference](CLI_REFERENCE.md)**: All commands
- **[Examples](../archive/examples/)**: Sample ontologies and configs

## Questions?

- **Issues**: https://github.com/aigora-de/rdf-construct/issues
- **Discussions**: https://github.com/aigora-de/rdf-construct/discussions