# UML Implementation Guide

## Overview

The UML module generates PlantUML class diagrams from RDF ontologies. It's a complete pipeline with YAML-based configuration, flexible entity selection, and comprehensive styling/layout control.

## Implementation Approach

### Design Goals

1. **Flexible Selection**: Multiple strategies for choosing what to include
2. **Property Filtering**: Different modes for different use cases
3. **Visual Customization**: Styling and layout without code changes
4. **Standards Compliance**: Valid PlantUML syntax
5. **Maintainability**: Clear separation of concerns

### Architecture Decisions

#### Why Separate Context, Mapper, Renderer?

**Context** (`context.py`):
- YAML parsing and validation
- Configuration object creation
- No graph dependencies

**Mapper** (`mapper.py`):
- Entity selection logic
- Graph traversal algorithms
- Reusable selection strategies

**Renderer** (`renderer.py`):
- PlantUML text generation
- Styling application
- Layout directive generation

**Benefit**: Each module independently testable, clear responsibilities.

#### Why Optional Styling?

**Reasoning**: Users might want:
- Quick unstyled diagrams for debugging
- Publication-ready styled diagrams
- Different styles for different audiences

**Solution**: Style and layout parameters are optional in `render_plantuml()`.

**Trade-off**: More complex renderer logic, but better flexibility.

## Class Selection Strategies

### Strategy 1: Root Classes with Descendants

**Use Case**: Show a hierarchy starting from specific concepts.

**Implementation**:
```python
def get_descendants(graph, root, max_depth=None):
    """BFS traversal following rdfs:subClassOf."""
    descendants = {root}
    current_level = {root}
    depth = 0
    
    while current_level and (max_depth is None or depth < max_depth):
        next_level = set()
        for cls in current_level:
            for subclass in graph.subjects(RDFS.subClassOf, cls):
                if subclass not in descendants:
                    descendants.add(subclass)
                    next_level.add(subclass)
        current_level = next_level
        depth += 1
    
    return descendants
```

**Features**:
- Optional depth limiting
- Handles multiple roots
- Respects hierarchy

### Strategy 2: Focus Classes (Explicit List)

**Use Case**: Hand-pick important classes.

**Implementation**:
```python
def select_classes(graph, context, selectors):
    if context.focus_classes:
        selected = set()
        for curie in context.focus_classes:
            cls = expand_curie(graph, curie)
            if cls:
                selected.add(cls)
                if context.include_descendants:
                    selected.update(get_descendants(graph, cls))
        return selected
```

**Features**:
- Direct control
- Optional descendant inclusion
- No hierarchy assumption

### Strategy 3: Selector-Based

**Use Case**: Bulk selection using predefined criteria.

**Implementation**: Reuses `core/selector.py` logic.

**Selectors**:
- `classes`: All `owl:Class`/`rdfs:Class`
- `obj_props`: All object properties
- `data_props`: All datatype properties

## Property Selection Modes

### Mode 1: domain_based

**Use Case**: Show properties relevant to selected classes.

**Logic**: Include property if `rdfs:domain` is in selected classes.

**Implementation**:
```python
for prop in all_properties:
    domains = set(graph.objects(prop, RDFS.domain))
    if domains & selected_classes:
        properties.add(prop)
```

### Mode 2: connected

**Use Case**: Show only relationships between selected classes.

**Logic**: For object properties, both domain and range must be selected.

**Implementation**:
```python
for prop in object_properties:
    domains = set(graph.objects(prop, RDFS.domain))
    ranges = set(graph.objects(prop, RDFS.range))
    if (domains & selected_classes) and (ranges & selected_classes):
        properties.add(prop)
```

### Mode 3: explicit

**Use Case**: Hand-pick properties to show.

**Logic**: Only include properties explicitly listed in `property_include`.

**Implementation**:
```python
for curie in context.property_include:
    prop = expand_curie(graph, curie)
    if prop:
        properties.add(prop)
```

### Mode 4: all

**Use Case**: Comprehensive diagrams.

**Logic**: Include all properties in the graph.

### Mode 5: none

**Use Case**: Class hierarchy only.

**Logic**: No properties rendered.

## Rendering Details

### PlantUML Syntax

**Classes**:
```plantuml
class "prefix:ClassName" {
  +propertyName : type
}
```

**Inheritance**:
```plantuml
"Child" --|> "Parent"
```

**Object Properties**:
```plantuml
"Domain" --> "Range" : propertyName
```

**Instances**:
```plantuml
object "Display Label" as prefix:instanceName {
  propertyName = value
}
```

**Instance Relationships**:
```plantuml
"instance" ..|> "Class"
```

### Identifier Quoting

**Problem**: PlantUML requires quotes around identifiers containing colons.

**Solution**: Always quote QNames.

```python
class_name = qname(graph, cls)
if ":" in class_name:
    class_name = f'"{class_name}"'
```

### Property Label Formatting

**Classes**: Use camelCase for technical property names
```python
prop_label = safe_label(graph, prop, camelcase=True)
# "has parent" → "hasParent"
```

**Instances**: Keep original labels readable
```python
instance_label = safe_label(graph, instance, camelcase=False)
# "Alice Smith" stays "Alice Smith"
```

**Reasoning**: Technical identifiers follow convention, display names stay human-readable.

## Styling System

### Color Palette

**PlantUML Format**: `#FILL;line:BORDER;line.STYLE;text:TEXT`

**Implementation**:
```python
class ColorPalette:
    def to_plantuml(self):
        parts = [self.fill]
        if self.border:
            parts.append(f"line:{self.border}")
        if self.line_style:
            parts.append(f"line.{self.line_style}")
        if self.text:
            parts.append(f"text:{self.text}")
        return ";".join(parts)
```

**Example Output**: `#E8F4F8;line:#0066CC;line.bold`

### Color Selection Priority

For classes:
1. Check explicit type mapping (e.g., metaclasses)
2. Check namespace prefix
3. Use default class style

For instances:
1. Use instance style
2. Optionally inherit class border color

**Implementation**:
```python
def get_class_style(self, graph, cls, is_instance=False):
    if is_instance and self.instance_style:
        return self.instance_style
    
    # Check namespace
    qname = graph.namespace_manager.normalizeUri(cls)
    if ":" in qname:
        ns_prefix = qname.split(":")[0]
        ns_key = f"ns:{ns_prefix}"
        if ns_key in self.class_styles:
            return self.class_styles[ns_key]
    
    # Default
    return self.class_styles.get("default")
```

### Stereotype Mapping

**Purpose**: Show semantic role of classes.

**Implementation**:
```python
def get_stereotype(self, graph, cls):
    if not self.show_stereotypes:
        return None
    
    for rdf_type in graph.objects(cls, RDF.type):
        type_qname = graph.namespace_manager.normalizeUri(rdf_type)
        if type_qname in self.stereotype_map:
            return self.stereotype_map[type_qname]
    
    return None
```

**Example**: `owl:Class` → `"«class»"`, `ies:ClassOfElement` → `"«meta»"`

## Layout System

### Direction Control

**PlantUML Directives**:
- `top to bottom direction`
- `left to right direction`
- etc.

**Mapping**:
```python
direction_map = {
    "top_to_bottom": "top to bottom direction",
    "left_to_right": "left to right direction",
    ...
}
```

### Arrow Direction Hints

**Purpose**: Influence PlantUML layout for hierarchies.

**Implementation**:
```python
def get_arrow_syntax(self, relationship_type):
    if relationship_type == "subclass":
        if self.arrow_direction == "up":
            return "-up-|>"  # Children point UP to parents
        # ... other directions
    return "-|>"  # Default
```

**Effect**: In top-to-bottom layout with `arrow_direction: up`:
- `Dog -up-|> Mammal` places Dog below Mammal
- Creates natural hierarchy visualization

### Spacing Control

**Future Feature**: Use PlantUML skinparam directives:
```plantuml
skinparam classMarginTop 10
skinparam classMarginBottom 10
```

**Current Implementation**: Basic support in `LayoutConfig.spacing` dict.

## Known Issues and Solutions

### Issue 1: Namespace Conflicts

**Problem**: rdflib has built-in namespace bindings.

**Example**: `org:` defaults to W3C org ontology.

**Detection**:
```python
for pfx, ns in graph.namespace_manager.namespaces():
    print(f"{pfx}: {ns}")
```

**Workaround**: Use the prefix rdflib assigns in your YAML config.

**Future Solution**: Add prefix override in context config.

### Issue 2: PlantUML Layout Heuristics

**Problem**: Arrow direction hints don't guarantee layout.

**Impact**: Parents might not always appear above children.

**Mitigation**:
- Use arrow direction hints
- Adjust spacing parameters
- Try different layout modes

**Acceptance**: PlantUML's layout engine is a black box; we provide hints, not guarantees.

### Issue 3: Empty Class Rendering

**Problem**: Classes with no attributes look odd in PlantUML.

**Solution 1**: Don't render braces if no attributes:
```plantuml
class "ex:Mammal"  # No braces
```

**Solution 2**: Use `hide_empty_members` layout option:
```plantuml
hide empty members
```

**Current Implementation**: Renderer checks for attributes, skips braces if none.

## Testing Considerations

### Unit Tests Needed

1. **Mapper Tests**:
   - `test_get_descendants()` with various depths
   - `test_select_classes()` for each strategy
   - `test_select_properties()` for each mode

2. **Renderer Tests**:
   - `test_render_class()` with/without attributes
   - `test_render_instance()` with property values
   - `test_render_relationships()` for each type

3. **Style Tests**:
   - `test_color_palette_to_plantuml()`
   - `test_get_class_style()` priority order
   - `test_stereotype_mapping()`

4. **Layout Tests**:
   - `test_get_arrow_syntax()` for each direction
   - `test_get_plantuml_directives()`

### Integration Tests

1. **End-to-End**:
   - Load ontology → select entities → render → verify PlantUML syntax
   - Test with real ontologies (animal, organisation)

2. **Style/Layout Combinations**:
   - Verify all schemes work with all layouts
   - Check no conflicts in generated directives

3. **YAML Config Validation**:
   - Invalid contexts should raise clear errors
   - Missing required fields should be caught

### Visual Validation

**Process**:
1. Generate `.puml` files
2. Render with PlantUML tool
3. Visual inspection of diagrams
4. Compare with expected output

**Tools**:
- PlantUML CLI
- VS Code PlantUML extension
- Online PlantUML editor

## Performance Profile

### Bottlenecks

1. **rdflib parsing**: Dominates for large ontologies
2. **Graph traversal**: Efficient (BFS)
3. **PlantUML generation**: Fast (string concatenation)

### Scalability

**Tested**:
- Up to ~200 classes
- ~1000 triples
- Generation time: <1 second

**Expected Limits**:
- ~1000 classes: Still fast
- ~10K classes: Slower, but usable
- ~100K classes: May need optimization

**Future Optimization**:
- Cache descendant lookups
- Batch property queries
- Streaming PlantUML output

## Extension Points

### Adding New Property Modes

1. Add mode to `select_properties()` in `mapper.py`
2. Update YAML schema documentation
3. Add tests

**Example**: `annotation_only` mode for annotation properties.

### Adding New Arrow Styles

1. Add style to `ArrowStyle` class in `uml_style.py`
2. Add PlantUML directive generation
3. Update YAML schema

**Example**: Dashed arrows for `ies:powertype` relationships.

### Adding New Layout Algorithms

1. Create new layout generator in `uml_layout.py`
2. Add PlantUML directive mapping
3. Test with various ontologies

**Example**: Force-directed layout hints.

## Migration Notes

### From Phase 1 to Phase 2

**Phase 1** (Basic Pipeline):
- Functional rendering
- Simple class/property/instance support
- No styling

**Phase 2** (Styling & Layout):
- Added `uml_style.py` and `uml_layout.py`
- Updated `renderer.py` to apply styles
- Backward compatible (styles optional)

**Breaking Changes**: None. Old code still works.

### Future Phases

**Phase 3** (Advanced Features):
- Clustering/grouping
- Custom PlantUML templates
- Interactive diagram configuration

**Phase 4** (Integration):
- Web UI for diagram configuration
- REST API for programmatic access
- Database backend for saving configs

## Code Quality Checklist

- [ ] Type hints on all public functions
- [ ] Docstrings (Google style) for all modules/classes/functions
- [ ] Unit tests for core logic
- [ ] Integration tests for end-to-end workflows
- [ ] Example ontologies with expected outputs
- [ ] Error handling for invalid configs
- [ ] Clear error messages for users
- [ ] Performance profiling for large ontologies

## References

- **PlantUML Class Diagrams**: https://plantuml.com/class-diagram
- **PlantUML Skinparam**: https://plantuml-documentation.readthedocs.io/en/latest/formatting/all-skin-params.html
- **rdflib Graph API**: https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.html#module-rdflib.graph
- **YAML Anchors**: https://yaml.org/spec/1.2/spec.html#id2765878