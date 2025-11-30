# IES Colour Palette Guide

## Overview

The IES (Information Exchange Standard) colour palette provides semantic visual encoding for IES ontology class diagrams. The colour scheme reflects the fundamental structure of the IES ontology, making the type hierarchy and metaclass relationships immediately apparent.

## Design Principles

### 1. **Hierarchy Through Colour**

Each major branch of the IES hierarchy has a distinct colour family:

- **Entity** (yellow): Things that exist spatially and temporally
- **State** (golden): Characteristics or conditions of entities
- **Event** (pink): Occurrences with temporal extent
- **Temporal** (orange): Time periods and temporal relationships
- **Metaclasses** (cyan/turquoise): Types that classify other types

### 2. **Border Inheritance for Metaclasses**

Metaclasses inherit their border colour from the hierarchy they classify:

```
ClassOfEntity      → Border: Entity yellow (#FEFE54)
ClassOfState       → Border: State golden (#F7D748)
ClassOfEvent       → Border: Event pink (#F5C2CB)
```

This creates immediate visual association between types and their metatypes.

### 3. **Lightness for Metalevel**

Second-order metaclasses (ClassOfClassOf...) use lighter shades of cyan (#74FAFC) than first-order metaclasses (#5CC9FA), indicating their position in the type hierarchy.

### 4. **Instance Styling**

All instances use:
- **Black border and fill** (#000000): Consistent base
- **Text colour inherited from class**: Creates clear visual connection to type

For example:
- Instance of Entity → Yellow text (#FEFE54)
- Instance of Event → Pink text (#F5C2CB)
- Instance of ClassOfElement → Cyan text (#5CC9FA)

## Colour Reference

### Core Hierarchy

| Class | Border RGB | Fill RGB | Hex Border | Hex Fill |
|-------|-----------|----------|------------|----------|
| Thing | 0, 0, 0 | 255, 255, 255 | #000000 | #FFFFFF |
| Element | 0, 0, 0 | 255, 255, 255 | #000000 | #FFFFFF |
| Entity | 150, 133, 132 | 254, 254, 84 | #968584 | #FEFE54 |
| State | 0, 0, 0 | 247, 215, 72 | #000000 | #F7D748 |
| Event | 150, 133, 132 | 245, 194, 203 | #968584 | #F5C2CB |
| PeriodOfTime | 150, 133, 132 | 243, 177, 105 | #968584 | #F3B169 |

### Metaclass Hierarchy (First Order)

| Class | Border RGB | Fill RGB | Hex Border | Hex Fill |
|-------|-----------|----------|------------|----------|
| ClassOfElement | 252, 252, 252 | 92, 201, 250 | #FCFCFC | #5CC9FA |
| ClassOfEntity | 254, 254, 84 | 92, 201, 250 | #FEFE54 | #5CC9FA |
| ClassOfState | 247, 215, 72 | 92, 201, 250 | #F7D748 | #5CC9FA |
| ClassOfEvent | 245, 194, 203 | 92, 201, 250 | #F5C2CB | #5CC9FA |
| TimeBoundedClass | 255, 255, 255 | 92, 201, 250 | #FFFFFF | #5CC9FA |

### Metaclass Hierarchy (Second Order)

| Class | Border RGB | Fill RGB | Hex Border | Hex Fill |
|-------|-----------|----------|------------|----------|
| ClassOfClassOfElement | 252, 252, 252 | 116, 250, 252 | #FCFCFC | #74FAFC |
| ClassOfClassOfEntity | 254, 254, 84 | 116, 250, 252 | #FEFE54 | #74FAFC |
| ClassOfClassOfState | 247, 215, 72 | 116, 250, 252 | #F7D748 | #74FAFC |
| ClassOfClassOfEvent | 245, 194, 203 | 116, 250, 252 | #F5C2CB | #74FAFC |

### Participation Classes

| Class | Border RGB | Fill RGB | Hex Border | Hex Fill |
|-------|-----------|----------|------------|----------|
| EventParticipant | 0, 0, 0 | 125, 48, 215 | #000000 | #7D30D7 |
| ActiveEventParticipant | 0, 0, 0 | 196, 155, 249 | #000000 | #C49BF9 |

### Instance Styling

| Element | Border RGB | Fill RGB | Text Colour |
|---------|-----------|----------|-------------|
| All instances | 0, 0, 0 | 0, 0, 0 | Inherits from class |

## Available Schemes

### `ies_full`

**Complete IES ontology colour scheme**

- All IES classes explicitly styled
- Metaclass border inheritance
- Instance text colour inheritance
- Suitable for: Comprehensive IES documentation

```bash
rdf-construct uml ies_ontology.ttl contexts.yml \
  --style-config ies_colour_palette.yml \
  --style ies_full
```

### `ies_core`

**Simplified scheme - main hierarchies only**

- Entity, State, Event, PeriodOfTime explicitly coloured
- Other IES classes use namespace default
- Cleaner for: Basic hierarchy diagrams

```bash
rdf-construct uml ies_ontology.ttl contexts.yml \
  --style-config ies_colour_palette.yml \
  --style ies_core
```

### `ies_metaclass`

**Metaclass-focused scheme**

- Base classes (Entity, State, Event) use muted colours
- Metaclasses (ClassOf...) in bright, bold colours
- Second-order metaclasses even brighter
- Stereotypes enabled (e.g., «meta»)
- Suitable for: Powertype pattern documentation

```bash
rdf-construct uml ies_ontology.ttl contexts.yml \
  --style-config ies_colour_palette.yml \
  --style ies_metaclass
```

## Usage Examples

### Example 1: Entity Hierarchy Diagram

Show Entity and its subclasses with instances:

**Context file** (`entity_hierarchy.yml`):
```yaml
contexts:
  entity_hierarchy:
    description: "Entity classification hierarchy"
    root_classes:
      - ies:Entity
    include_descendants: true
    max_depth: 3
    properties:
      mode: domain_based
    include_instances: true
```

**Command**:
```bash
rdf-construct uml ies.ttl entity_hierarchy.yml \
  --style-config ies_colour_palette.yml \
  --style ies_full
```

**Result**: 
- All Entity subclasses in yellow (#FEFE54)
- Instances with black fill and yellow text
- Clear visual grouping of Entity family

### Example 2: Metaclass Power-type Relationships

Emphasise ClassOf relationships:

**Context file** (`metaclass_diagram.yml`):
```yaml
contexts:
  metaclass_patterns:
    description: "Metaclass and powertype relationships"
    focus_classes:
      - ies:Entity
      - ies:ClassOfEntity
      - ies:ClassOfClassOfEntity
    properties:
      mode: explicit
      include:
        - ies:powertype
```

**Command**:
```bash
rdf-construct uml ies.ttl metaclass_diagram.yml \
  --style-config ies_colour_palette.yml \
  --style ies_metaclass
```

**Result**:
- Entity in muted yellow
- ClassOfEntity in bright cyan with yellow border
- ClassOfClassOfEntity in lighter cyan with yellow border
- Powertype relationships in bold cyan arrows

### Example 3: Multi-Hierarchy Comparison

Show Entity, State, and Event together:

**Context file** (`multi_hierarchy.yml`):
```yaml
contexts:
  core_hierarchies:
    description: "Core IES hierarchies"
    focus_classes:
      - ies:Entity
      - ies:State
      - ies:Event
    include_descendants: true
    max_depth: 2
    properties:
      mode: connected
```

**Command**:
```bash
rdf-construct uml ies.ttl multi_hierarchy.yml \
  --style-config ies_colour_palette.yml \
  --style ies_full
```

**Result**:
- Entity branch in yellow
- State branch in golden
- Event branch in pink
- Properties connecting branches shown
- Immediate visual differentiation

## Customisation

### Adding Custom Classes

To add styling for domain-specific IES extensions:

```yaml
schemes:
  my_ies_extension:
    description: "IES with custom domain classes"
    
    classes:
      by_type:
        # Include all standard IES colours
        ies:Entity:
          border: "#968584"
          fill: "#FEFE54"
          text: "#000000"
        
        # Add your custom classes
        myns:CustomEntity:
          border: "#968584"
          fill: "#FEFE54"      # Match Entity yellow
          text: "#000000"
        
        myns:CustomState:
          border: "#000000"
          fill: "#F7D748"      # Match State golden
          text: "#000000"
```

### Adjusting Instance Styling

To use different instance colours:

```yaml
instances:
  border: "#333333"          # Dark grey instead of black
  fill: "#1A1A1A"            # Very dark grey instead of black
  text: "#FFFFFF"
  inherit_class_text: false  # Use white text for all instances
```

### Custom Arrow Styles

To add special relationship styling:

```yaml
arrows:
  # Standard relationships
  subclass:
    color: "#000000"
    thickness: 1
    style: bold
  
  # Custom IES relationships
  ies_inPeriod:
    color: "#F3B169"         # Orange for temporal
    thickness: 1
    style: dashed
  
  ies_isParticipantIn:
    color: "#7D30D7"         # Purple for participation
    thickness: 2
    style: bold
```

## Visual Design Notes

### Accessibility

The colour palette has been designed with these accessibility considerations:

1. **Colour + Border**: Classes are distinguishable by both fill and border colour
2. **High Contrast**: All text uses black (#000000) on light backgrounds
3. **Pattern Recognition**: Border inheritance provides an additional visual cue beyond colour
4. **Instance Differentiation**: Black base makes instances immediately distinct from classes

### Print Compatibility

The scheme works well in greyscale:
- Yellow (Entity) → Light grey
- Golden (State) → Medium grey
- Pink (Event) → Light-medium grey
- Cyan (Metaclass) → Medium grey
- Black borders remain distinct

### Presentation Usage

For slides or presentations:
- Use `ies_metaclass` scheme for emphasis on type relationships
- Consider adding `line_style: bold` to key classes
- Increase arrow thickness for visibility at distance

## Technical Notes

### PlantUML Colour Format

The YAML colours are converted to PlantUML's format:

```
#FILL;line:BORDER;line.STYLE;text:TEXT
```

Example:
```yaml
border: "#968584"
fill: "#FEFE54"
text: "#000000"
line_style: bold
```

Becomes: `#FEFE54;line:#968584;line.bold;text:#000000`

### Inheritance Mechanism

The `inherit_class_text: true` option in instance styling uses rdflib to:

1. Find instance's rdf:type
2. Look up class's fill colour
3. Apply that colour to instance text

This creates visual association: "this instance belongs to that class family."

### Performance

Colour lookup is O(1) with the `by_type` dictionary approach. For large ontologies with thousands of classes, consider:

- Using `by_namespace` for broad categories
- Using `default` for unspecified classes
- Limiting `by_type` to key classes only

## Future Enhancements

Possible extensions to the colour system:

1. **Gradient support**: Subtle gradients for class hierarchies
2. **Pattern fills**: Stripes or dots for specific class types
3. **Dynamic schemes**: Generate colours based on graph properties
4. **Theme inheritance**: Compose schemes from base themes
5. **Colour validation**: Check accessibility and contrast ratios

## Troubleshooting

### Colours Not Appearing

1. Check PlantUML version supports hex colours
2. Verify YAML syntax (quotes around hex values optional)
3. Ensure class URIs match exactly (case-sensitive)

### Text Unreadable

If text is hard to read:
- Adjust `text` colour explicitly
- Use darker border colours
- Increase font size via layout configuration

### Wrong Colours Applied

Check selection priority:
1. `by_type` matches first
2. `by_namespace` matches second
3. `default` matches last

Ensure your class URIs match the YAML exactly.

## References

- IES Ontology: https://github.com/dstl/IES4
- PlantUML Colour Reference: https://plantuml.com/color
- rdf-construct Documentation: See `docs/user_guides/UML_GUIDE.md`

---

**Maintained by**: rdf-construct project  
**Version**: 1.0  
**Last Updated**: 2025-11-02