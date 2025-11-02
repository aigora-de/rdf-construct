# Explicit Mode Feature

## Overview

**Explicit mode** is a new UML context selection strategy that provides complete control over diagram contents by directly listing every entity to include. Unlike the default mode's automatic selection strategies, explicit mode requires you to specify exactly which classes, properties, and instances appear in the diagram.

## Why Explicit Mode?

### Problem

The default mode's selection strategies work well for standard hierarchies, but struggle with:

1. **Cross-branch selection**: Concepts from multiple unrelated hierarchies
2. **Partial hierarchies**: Showing specific depths without explosion
3. **Thematic views**: Custom groupings that don't follow class structure
4. **Precision control**: When automatic selection includes too much or too little

### Solution

Explicit mode lets you:
- List classes from any branch in any hierarchy
- Include only specific levels of a deep hierarchy
- Create subject-matter diagrams that cut across structure
- Have complete control over every entity

## Usage

### Basic Syntax

```yaml
contexts:
  my_explicit_context:
    description: "Description of what this shows"
    mode: explicit  # Enable explicit mode
    
    # Directly list classes
    classes:
      - prefix:ClassName1
      - prefix:ClassName2
    
    # Directly list properties
    object_properties:
      - prefix:propertyName1
      - prefix:propertyName2
    
    datatype_properties:
      - prefix:datatypeProp1
    
    annotation_properties:
      - prefix:annotationProp1
    
    # Optionally list instances
    instances:
      - prefix:individualName1
```

### Minimal Example

```yaml
simple_view:
  mode: explicit
  
  classes:
    - ex:Animal
    - ex:Dog
  
  object_properties:
    - ex:hasParent
  
  datatype_properties: []  # None needed
```

### Complete Example

```yaml
animal_care:
  description: "Animal care concepts across taxonomy"
  mode: explicit
  
  classes:
    - ex:Animal       # Root concept
    - ex:Mammal       # From mammal branch
    - ex:Dog          # Deep in mammal hierarchy
    - ex:Eagle        # From bird branch (cross-branch!)
  
  object_properties:
    - ex:hasParent
    - ex:eats
    - ex:livesIn
  
  datatype_properties:
    - ex:averageWeight
    - ex:lifespan
  
  annotation_properties:
    - ex:scientificName
  
  instances:
    - ex:Fido
    - ex:Baldy
```

## Use Cases

### Use Case 1: Cross-Branch Subject Matter

**Scenario**: You're documenting animal care, which involves mammals, birds, and facilities—concepts from unrelated hierarchies.

**Without explicit mode**: Must create separate contexts and manually merge, or use focus_classes with verbose enumeration.

**With explicit mode**:

```yaml
animal_care_facilities:
  mode: explicit
  
  classes:
    - ex:Dog           # From animal/mammal branch
    - ex:Eagle         # From animal/bird branch
    - ex:Facility      # From location hierarchy
    - ex:Veterinarian  # From person hierarchy
  
  object_properties:
    - ex:treatedBy
    - ex:housedAt
    - ex:eats
```

**Result**: Clean diagram showing how these concepts relate, ignoring irrelevant hierarchy members.

### Use Case 2: Partial Hierarchy Display

**Scenario**: Your mammal hierarchy is 5 levels deep, but you only want to show the top 2 levels.

**Without explicit mode**: `max_depth: 2` gives you 2 levels from ALL starting points, but you might want different depths in different branches.

**With explicit mode**:

```yaml
mammals_shallow:
  mode: explicit
  
  classes:
    - ex:Mammal       # Level 0
    - ex:Dog          # Level 1
    - ex:Cat          # Level 1
    - ex:Horse        # Level 1
    # Deliberately stop here
  
  object_properties:
    - ex:hasParent
```

**Result**: Exactly the levels you want, no more, no less.

### Use Case 3: Focused Relationship View

**Scenario**: Create a diagram showing only predator-prey relationships.

**Without explicit mode**: Property modes (connected, domain_based) include properties you don't want.

**With explicit mode**:

```yaml
predation_only:
  mode: explicit
  
  classes:
    - ex:Dog
    - ex:Cat
    - ex:Eagle
    - ex:Sparrow
  
  object_properties:
    - ex:eats  # ONLY this relationship
  
  datatype_properties: []  # None
```

**Result**: Focused diagram showing just predation, nothing else.

## Implementation Details

### How It Works

1. **CURIE Expansion**: Each entity CURIE is expanded to a full URI using the graph's namespace bindings
2. **Validation**: Checks that entities exist and are of the correct type (warnings for mismatches)
3. **Direct Selection**: No automatic traversal or filtering—only specified entities are included
4. **No Inference**: Relationships between entities are rendered if they exist in the graph, but no additional entities are inferred

### Error Handling

**Invalid CURIE**:
```yaml
classes:
  - badprefix:Something  # Unknown prefix
```

**Error**: `ValueError: Cannot expand CURIE: badprefix:Something`

**Missing Entity**:
```yaml
classes:
  - ex:NonexistentClass  # Not in graph
```

**Behavior**: Warning logged, entity skipped.

**Wrong Type**:
```yaml
object_properties:
  - ex:Dog  # This is a class, not a property
```

**Behavior**: Warning logged, entity skipped.

### Validation Strategy

Explicit mode performs:
1. **CURIE expansion** (strict: fails if prefix unknown)
2. **Entity existence** (lenient: warns if not found)
3. **Type checking** (lenient: warns if type mismatch)

This balance allows flexibility while catching obvious errors.

## Comparison: Default vs Explicit Mode

### Feature Matrix

| Feature | Default Mode | Explicit Mode |
|---------|--------------|---------------|
| **Selection** | Automatic (strategies) | Manual (lists) |
| **Hierarchy traversal** | Built-in (descendants) | None (must list all) |
| **Property selection** | Mode-based | Manual list |
| **Cross-branch** | Difficult | Easy |
| **Partial hierarchy** | Limited (max_depth) | Complete control |
| **Verbosity** | Concise | More verbose |
| **Configuration size** | Smaller | Larger |
| **Maintenance** | Auto-adjusts to ontology | Must update lists |
| **Precision** | Good | Excellent |

### When to Use Each

**Default Mode**:
- ✅ Single hierarchy branch
- ✅ Want all descendants
- ✅ Standard property modes work
- ✅ Ontology changes frequently
- ✅ Prefer concise configuration

**Explicit Mode**:
- ✅ Cross-branch concepts
- ✅ Specific hierarchy depths
- ✅ Thematic/conceptual views
- ✅ Maximum precision needed
- ✅ Stable ontology subset
- ✅ Complex selection requirements

### Same Diagram, Both Modes

**Goal**: Show Mammal with direct subclasses.

**Default Mode**:
```yaml
mammals_default:
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
mammals_explicit:
  mode: explicit
  classes:
    - ex:Mammal
    - ex:Dog
    - ex:Cat
    - ex:Horse
  object_properties:
    - ex:hasParent
    - ex:eats
  datatype_properties:
    - ex:averageWeight
    - ex:lifespan
```

**Trade-off**:
- Default: More concise, auto-adjusts if new mammals added
- Explicit: More verbose, complete control over properties, won't change if ontology changes

## Configuration Tips

### Use YAML Anchors for Reusability

```yaml
# Define reusable entity lists
shared:
  common_mammals: &common_mammals
    - ex:Mammal
    - ex:Dog
    - ex:Cat
  
  common_properties: &common_properties
    - ex:hasParent
    - ex:eats

contexts:
  view1:
    mode: explicit
    classes: *common_mammals
    object_properties: *common_properties
    datatype_properties: []
  
  view2:
    mode: explicit
    classes:
      - *common_mammals
      - ex:Eagle  # Add one more
    object_properties: *common_properties
```

### Empty Lists

Explicitly state when a type has no entities:

```yaml
structure_only:
  mode: explicit
  classes:
    - ex:Animal
    - ex:Mammal
  object_properties: []  # Explicitly none
  datatype_properties: []
  annotation_properties: []
  instances: []
```

### Progressive Refinement

Start minimal, then expand:

```yaml
# Version 1: Core structure
v1:
  mode: explicit
  classes:
    - ex:Animal
    - ex:Dog
  object_properties:
    - ex:hasParent
  datatype_properties: []

# Version 2: Add cross-branch
v2:
  mode: explicit
  classes:
    - ex:Animal
    - ex:Dog
    - ex:Eagle  # NEW
  object_properties:
    - ex:hasParent
    - ex:eats   # NEW
  datatype_properties:
    - ex:lifespan  # NEW
```

## Validation and Debugging

### Check Your Configuration

```bash
# List contexts to verify syntax
poetry run rdf-construct contexts config.yml
```

Output shows mode and entity counts:
```
animal_care
  Mode: explicit
  Classes: 4, Properties: 3, Instances: 2
```

### Verify CURIEs

```python
from rdflib import Graph

g = Graph().parse("ontology.ttl", format="turtle")

# Check available prefixes
for pfx, ns in g.namespace_manager.namespaces():
    if pfx:
        print(f"{pfx}: {ns}")

# Check specific entity
from rdflib import RDF
from rdflib.namespace import OWL

for cls in g.subjects(RDF.type, OWL.Class):
    print(g.namespace_manager.normalizeUri(cls))
```

### Common Errors

**Error**: `ValueError: Cannot expand CURIE: xyz:Something`
**Fix**: Check prefix exists in ontology.

**Error**: Empty diagram generated
**Fix**: Verify CURIEs match actual entities in graph.

**Error**: Properties not showing
**Fix**: Ensure properties are in correct list (object vs datatype).

## Examples

See `examples/uml_contexts_explicit_examples.yml` for:
- Cross-branch subject matter diagrams
- Partial hierarchy displays
- Custom concept clusters
- Minimal entity selections
- Comparison with default mode

## Migration Guide

### From Default to Explicit Mode

1. **Generate with default mode** to see what's selected:
   ```bash
   poetry run rdf-construct uml ontology.ttl config.yml -c my_context
   ```

2. **Note entities in output** (check .puml file or console output)

3. **Create explicit version** with those entities:
   ```yaml
   my_context_explicit:
     mode: explicit
     classes:
       - ex:Class1
       - ex:Class2
       # ... (copy from output)
     object_properties:
       - ex:prop1
       # ... (copy from output)
   ```

4. **Compare outputs** to verify equivalence

### From Explicit to Default Mode

If explicit mode becomes too verbose:

1. **Identify selection pattern**:
   - All from one hierarchy? → Use `root_classes`
   - Specific classes? → Use `focus_classes`
   - All classes? → Use `selector: classes`

2. **Convert to strategy**:
   ```yaml
   # Was:
   old:
     mode: explicit
     classes: [ex:Mammal, ex:Dog, ex:Cat]
   
   # Now:
   new:
     mode: default
     root_classes: [ex:Mammal]
     include_descendants: true
     max_depth: 1
   ```

## Future Enhancements

Planned features:
1. **Hybrid mode**: Combine default strategies with additional explicit entities
2. **Negative selection**: Exclude specific entities from automatic selection
3. **Template expansion**: Generate explicit lists from patterns
4. **Import/export**: Convert between modes automatically

## Summary

**Explicit mode** provides maximum control over UML diagram contents by requiring you to list every entity to include. It's ideal for:
- Cross-branch concept diagrams
- Partial hierarchies
- Precise entity selection
- Thematic/subject-matter views

**Trade-off**: More verbose configuration for complete control.

**When to use**: When default mode's automatic selection doesn't match your needs.

## See Also

- [UML Guide](docs/user_guides/UML_GUIDE.md) - Complete UML documentation
- [Getting Started](docs/user_guides/GETTING_STARTED.md) - Quick introduction
- [Examples](examples/uml_contexts_explicit_examples.yml) - Full example configurations