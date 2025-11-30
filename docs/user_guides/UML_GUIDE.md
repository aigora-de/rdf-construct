# UML Diagram Generation Guide

## Overview

Generate PlantUML class diagrams from RDF ontologies with full control over what's included, how it's styled, and how it's arranged.

## Table of Contents

- [Basic Usage](#basic-usage)
- [Context Configuration](#context-configuration)
- [Selection Modes](#selection-modes)
  - [Default Mode](#default-mode-strategies)
  - [Explicit Mode](#explicit-mode-complete-control)
- [Class Selection (Default Mode)](#class-selection-default-mode)
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
    mode: default  # or 'explicit'
    
    # For default mode:
    root_classes: [...]        # Start from roots
    focus_classes: [...]       # Explicit list
    selector: classes          # Use selector
    include_descendants: true
    max_depth: 3
    properties:
      mode: domain_based
      include: [...]
      exclude: [...]
    include_instances: false
    
    # For explicit mode:
    classes: [...]
    object_properties: [...]
    datatype_properties: [...]
    annotation_properties: [...]
    instances: [...]
```

## Selection Modes

### Default Mode (Strategies)

**Use When**: You want automatic entity selection based on hierarchies or patterns.

The traditional mode with selection strategies:
- Root classes with descendants
- Focus classes
- Selector-based bulk selection
- Property modes (domain_based, connected, etc.)

**Best For**:
- Complete hierarchies
- Standard ontology views
- When you want automatic property inclusion

### Explicit Mode (Complete Control)

**Use When**: You need precise control over every entity in the diagram.

Directly list every class, property, and instance to include. No automatic selection.

**Best For**:
- Cross-branch subject matter diagrams
- Partial hierarchies (specific depths)
- Custom concept clusters
- When hierarchies are too broad or deep

**Example**:

```yaml
animal_care:
  description: "Animal care concepts across branches"
  mode: explicit
  
  classes:
    - ex:Animal
    - ex:Dog          # From mammal branch
    - ex:Eagle        # From bird branch (cross-branch!)
  
  object_properties:
    - ex:hasParent
    - ex:livesIn
  
  datatype_properties:
    - ex:lifespan
  
  instances:
    - ex:Fido
```

**Key Differences**:

| Feature | Default Mode | Explicit Mode |
|---------|--------------|---------------|
| Class selection | Automatic (roots/focus/selector) | Manual list |
| Descendants | Optional automatic | Must list individually |
| Property selection | Mode-based (domain/connected) | Manual list |
| Instance selection | All of selected classes | Manual list |
| Flexibility | Good for standard views | Maximum control |
| Verbosity | Concise | More verbose |

## Class Selection (Default Mode)

### Strategy 1: Root Classes

**Use Case**: Show a hierarchy starting from specific concepts.

```yaml
animal_taxonomy:
  description: "Complete animal hierarchy"
  mode: default  # Optional, this is the default
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

## Explicit Mode (Complete Control)

### Use Case 1: Cross-Branch Subject Matter

**Problem**: Want concepts from multiple hierarchies that aren't naturally grouped.

**Solution**: Explicitly list classes from different branches.

```yaml
animal_care:
  description: "Animal care cutting across taxonomy"
  mode: explicit
  
  classes:
    - ex:Animal       # Root
    - ex:Mammal       # One branch
    - ex:Dog          # Deep in that branch
    - ex:Eagle        # Different branch!
    - ex:Veterinarian # Related but different hierarchy
  
  object_properties:
    - ex:hasParent
    - ex:treatedBy
  
  datatype_properties:
    - ex:lifespan
  
  instances:
    - ex:Fido
```

### Use Case 2: Partial Hierarchy Display

**Problem**: Hierarchy is deep but you only want a specific slice.

**Solution**: List exactly the levels you want.

```yaml
mammals_top_level:
  description: "Just Mammal and direct subclasses"
  mode: explicit
  
  classes:
    - ex:Mammal
    - ex:Dog
    - ex:Cat
    # Deliberately omit deeper descendants
  
  object_properties:
    - ex:hasParent
  
  datatype_properties:
    - ex:averageWeight
```

**Result**: Clean diagram without explosion of subclasses.

### Use Case 3: Custom Concept Cluster

**Problem**: Want a diagram focused on specific relationships or themes.

**Solution**: Hand-pick relevant concepts and properties.

```yaml
predator_relationships:
  description: "Predator-prey relationships only"
  mode: explicit
  
  classes:
    - ex:Dog
    - ex:Cat
    - ex:Eagle
    - ex:Sparrow  # Prey
  
  object_properties:
    - ex:eats  # Only predation
  
  datatype_properties: []  # None needed
```

### Minimal Diagrams

```yaml
classes_only:
  description: "Structure without properties"
  mode: explicit
  
  classes:
    - ex:Animal
    - ex:Mammal
    - ex:Bird
  
  object_properties: []
  datatype_properties: []
```

### Validation in Explicit Mode

Explicit mode validates that:
1. CURIEs can be expanded (valid prefixes)
2. Entities exist in the graph (warnings for missing)
3. Entity types are correct (class vs property)

**Error Example**:
```yaml
classes:
  - ex:NonexistentClass  # Raises ValueError
```

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

### Enable Instances (Default Mode)

```yaml
with_examples:
  root_classes:
    - ex:Dog
  include_descendants: true
  include_instances: true  # Show individuals
```

### Explicit Mode Instances

```yaml
specific_individuals:
  mode: explicit
  
  classes:
    - ex:Dog
    - ex:Cat
  
  datatype_properties:
    - ex:lifespan
  
  instances:
    - ex:Fido     # Specific dog
    - ex:Whiskers # Specific cat
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

### Example 1: Cross-Branch with Explicit Mode

**Goal**: Show animal care concepts across different taxonomic branches.

**Config**:
```yaml
animal_care:
  description: "Care concepts across taxonomy"
  mode: explicit
  
  classes:
    - ex:Animal
    - ex:Mammal
    - ex:Dog
    - ex:Eagle        # Different branch
  
  object_properties:
    - ex:hasParent
    - ex:livesIn
  
  datatype_properties:
    - ex:lifespan
    - ex:averageWeight
  
  instances:
    - ex:Fido
    - ex:Baldy
```

**Generate**:
```bash
poetry run rdf-construct uml examples/animal_ontology.ttl config.yml \
  -c animal_care \
  --style-config examples/uml_styles.yml --style default
```

**Result**:
- 4 classes (from different branches)
- 2 object properties
- 2 datatype properties
- 2 instances with their values

### Example 2: Partial Hierarchy

**Goal**: Show only top levels of a deep hierarchy.

**Config**:
```yaml
mammals_top_level:
  description: "Mammal with direct subclasses only"
  mode: explicit
  
  classes:
    - ex:Mammal
    - ex:Dog
    - ex:Cat
    # Stop here - no deeper levels
  
  object_properties:
    - ex:hasParent
  
  datatype_properties:
    - ex:averageWeight
```

**Result**: Clean 3-class diagram without explosion.

### Example 3: Comparison (Default vs Explicit)

**Same diagram, two approaches:**

**Default Mode**:
```yaml
comparison_default:
  mode: default
  root_classes:
    - ex:Mammal
  include_descendants: true
  max_depth: 1
  properties:
    mode: domain_based
```

**Explicit Mode**:
```yaml
comparison_explicit:
  mode: explicit
  classes:
    - ex:Mammal
    - ex:Dog
    - ex:Cat
  object_properties:
    - ex:hasParent
    - ex:eats
    - ex:livesIn
  datatype_properties:
    - ex:averageWeight
    - ex:lifespan
```

**When to use which**:
- Default: Faster to write, good for standard hierarchies
- Explicit: More control, better for custom views

## Advanced Techniques

### Mixing Modes (Future Enhancement)

Not currently supported, but planned:

```yaml
# Future: hybrid mode
hybrid_view:
  mode: default
  root_classes:
    - ex:Mammal
  include_descendants: true
  max_depth: 1
  
  # Additional classes to include
  additional_classes:  # PLANNED
    - ex:Eagle
    - ex:Habitat
```

### Empty Entity Lists

You can omit entity types you don't need:

```yaml
structure_only:
  mode: explicit
  classes:
    - ex:Animal
    - ex:Mammal
  object_properties: []  # Explicitly none
  datatype_properties: []
```

## Tips for Great Diagrams

### When to Use Explicit Mode

✅ **Use explicit mode when:**
- Diagram crosses multiple hierarchies
- You need specific hierarchy depth that's hard to specify
- Creating thematic/conceptual views
- Standard modes produce too much/too little

❌ **Use default mode when:**
- Working with single, clean hierarchies
- Want all descendants of a root
- Standard property modes work well
- Want less verbose configuration

### Start Simple

Begin with a basic explicit context:
```yaml
simple_start:
  mode: explicit
  classes:
    - your:KeyClass1
    - your:KeyClass2
  object_properties:
    - your:keyProperty
  datatype_properties: []
```

Generate and view. Then add more entities.

### Check Your Prefixes

Explicit mode requires correct CURIEs. Verify prefixes:

```python
from rdflib import Graph
g = Graph().parse("ontology.ttl", format="turtle")
for pfx, ns in g.namespace_manager.namespaces():
    if pfx: print(f"{pfx}: {ns}")
```

### Validate Before Generating

Use the `contexts` command to check configuration:

```bash
poetry run rdf-construct contexts config.yml
```

## Troubleshooting

### "Cannot expand CURIE"

**Problem**: `ValueError: Cannot expand CURIE: xyz:Something`

**Cause**: Prefix not defined in ontology.

**Solution**: Check prefix with:
```python
from rdflib import Graph
g = Graph().parse("ontology.ttl", format="turtle")
print([(p, n) for p, n in g.namespace_manager.namespaces()])
```

### Empty Diagram in Explicit Mode

**Problem**: Generated .puml has no entities.

**Cause**: CURIEs don't match entities in ontology.

**Debug**:
```python
from rdflib import Graph, RDF, OWL
g = Graph().parse("ontology.ttl", format="turtle")
from rdflib.namespace import OWL, RDF
classes = list(g.subjects(RDF.type, OWL.Class))
for cls in classes:
    print(g.namespace_manager.normalizeUri(cls))
```

### Too Verbose

**Problem**: Explicit mode requires listing everything.

**Solution**: 
1. Use default mode for this diagram, or
2. Create reusable YAML anchors:

```yaml
# Define reusable lists
shared:
  common_classes: &common_classes
    - ex:Animal
    - ex:Mammal
    - ex:Dog

contexts:
  view1:
    mode: explicit
    classes: *common_classes  # Reuse
```

## Next Steps

- **[Getting Started](GETTING_STARTED.md)**: Quick start guide
- **[CLI Reference](CLI_REFERENCE.md)**: All commands
- **[Examples](examples/)**: Sample ontologies and configs

## Questions?

- **Issues**: https://github.com/aigora-de/rdf-construct/issues
- **Discussions**: https://github.com/aigora-de/rdf-construct/discussions