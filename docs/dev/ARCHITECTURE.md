# rdf-construct Architecture

## Overview

**rdf-construct** is a Python CLI toolkit for RDF graph operations, named after the ROM construct from William Gibson's Neuromancer. The core feature is semantic ordering of RDF serialization—allowing Turtle output to be ordered by meaning rather than alphabetical sorting.

## System Design

### Core Principles

1. **Separation of Concerns**: Distinct modules for configuration, selection, ordering, and serialization
2. **Custom Serialization**: rdflib always sorts alphabetically; we preserve semantic ordering
3. **YAML-Driven**: Flexible configuration without code changes
4. **Composable**: Unix philosophy—do one thing well, support piping

### Module Structure

```
src/rdf_construct/
├── core/                      # Core RDF operations
│   ├── config.py             # YAML loading, dataclasses
│   ├── profile.py            # OrderingConfig, profile management
│   ├── selector.py           # Subject selection (classes/properties/individuals)
│   ├── ordering.py           # Topological sort, root-based ordering
│   ├── serialiser.py         # Custom Turtle writer (preserves order)
│   └── utils.py              # CURIE expansion, QName sorting
├── uml/                       # UML diagram generation
│   ├── context.py            # UML context configuration
│   ├── mapper.py             # Entity selection for diagrams
│   ├── renderer.py           # PlantUML generation
│   ├── uml_style.py          # Color schemes and styling
│   └── uml_layout.py         # Layout configuration
├── cli.py                     # Click-based CLI
└── main.py                    # Entry point
```

## Data Flow

### RDF Ordering Pipeline

```
1. Load YAML config → OrderingConfig
2. Parse RDF file → rdflib.Graph
3. For each profile:
   a. For each section:
      - Select subjects (selector.py)
      - Sort subjects (ordering.py)
   b. Build filtered graph
   c. Serialize with preserved order (serialiser.py)
4. Write output files
```

### UML Generation Pipeline

```
1. Load YAML context → UMLContext
2. Parse RDF file → rdflib.Graph
3. Select entities:
   - Classes (root/focus/selector strategies)
   - Properties (domain-based/connected/explicit modes)
   - Instances (optional)
4. Render to PlantUML (renderer.py)
5. Apply styling and layout (optional)
6. Write .puml files
```

## Key Algorithms

### Topological Sorting (ordering.py)

Uses Kahn's algorithm for parent-before-child ordering:

1. Build adjacency list from `rdfs:subClassOf`/`rdfs:subPropertyOf`
2. Find nodes with zero incoming edges
3. Process in order, decrementing incoming edges
4. Alphabetical tie-breaking for determinism
5. Handle cycles by appending remaining nodes

### Root-Based Branch Ordering

For explicit hierarchy control:

1. Expand root CURIEs to IRIs
2. For each root:
   - Find all descendants (BFS traversal)
   - Topologically sort branch
   - Emit in order
3. Emit remaining disconnected components

### Custom Turtle Serialization

**Critical difference from rdflib:**

- rdflib: Always sorts subjects alphabetically
- Our serializer: Respects exact subject order provided

Implementation:
1. Write prefixes alphabetically
2. Iterate subjects in provided order
3. For each subject:
   - Write `rdf:type` first (using `a` shorthand)
   - Sort other predicates alphabetically
   - Sort objects alphabetically within predicate
4. Proper Turtle syntax (`;` and `,` separators)

## Module Responsibilities

### core/config.py & core/profile.py

**Purpose**: Configuration management

- Parse YAML into typed Python dataclasses
- Validate structure and references
- Provide profile access interface

**Key Classes**:
- `OrderingSpec`: Complete specification from YAML
- `OrderingConfig`: Manages multiple profiles
- `ProfileConfig`: Single profile definition
- `SectionConfig`: Section within a profile

### core/selector.py

**Purpose**: Subject identification

- Query graph for specific RDF types
- Handle both `owl:Class` and `rdfs:Class`
- Identify individuals (non-class, non-property subjects)

**Selection Modes**:
- `classes`: `owl:Class` or `rdfs:Class` entities
- `obj_props`: `owl:ObjectProperty`
- `data_props`: `owl:DatatypeProperty`
- `ann_props`: `owl:AnnotationProperty`
- `individuals`: Everything else

### core/ordering.py

**Purpose**: Sorting algorithms

**Functions**:
- `topo_sort_subset()`: Topological sort with Kahn's algorithm
- `sort_with_roots()`: Root-based branch ordering
- `sort_subjects()`: Main sorting interface
- `descendants_of()`: Hierarchy traversal

**Sort Modes**:
- `alpha`: Alphabetical by QName
- `topological`: Parent-before-child

### core/serialiser.py

**Purpose**: Custom RDF output

**Critical Feature**: Preserves exact subject order (rdflib can't do this)

**Functions**:
- `serialise_turtle()`: Main serialization with order preservation
- `build_section_graph()`: Filter graph to selected subjects
- `format_term()`: Convert RDF terms to Turtle syntax

### uml/context.py

**Purpose**: UML-specific configuration

**Key Classes**:
- `UMLContext`: Diagram specification
- `UMLConfig`: Manages multiple contexts

**Context Features**:
- Root classes with optional descendants
- Focus classes (explicit list)
- Selector-based bulk selection
- Property filtering modes
- Instance inclusion

### uml/mapper.py

**Purpose**: Entity selection for diagrams

**Selection Strategies**:
1. **Classes**: Root + descendants, focus list, or selector
2. **Properties**: Domain-based, connected, explicit, all, or none
3. **Instances**: By class membership

**Functions**:
- `select_classes()`: Class selection with traversal
- `select_properties()`: Property filtering
- `select_instances()`: Instance identification
- `collect_diagram_entities()`: Main entry point

### uml/renderer.py

**Purpose**: PlantUML text generation

**Rendering**:
- Classes with datatype properties as attributes
- Inheritance relationships (`--|>`)
- Object property associations (`-->`)
- Instances as objects with property values
- Instance-to-class relationships (`..|>`)

### uml/uml_style.py

**Purpose**: Visual styling configuration

**Key Classes**:
- `ColorPalette`: Border, fill, text colors
- `ArrowStyle`: Relationship arrow styling
- `StyleScheme`: Complete visual theme
- `StyleConfig`: Manages multiple schemes

**Features**:
- Namespace-based coloring
- Type-based coloring (metaclasses)
- Instance styling with class inheritance
- Stereotype display

### uml/uml_layout.py

**Purpose**: Spatial arrangement

**Key Classes**:
- `LayoutConfig`: Direction, spacing, grouping
- `LayoutConfigManager`: Manages multiple layouts

**Features**:
- Direction control (top-to-bottom, etc.)
- Arrow direction hints for hierarchy
- Hide empty members option
- PlantUML directive generation

## Critical Design Decisions

### Why Custom Serialization?

**Problem**: rdflib's built-in serializers always sort subjects alphabetically.

**Impact**: Destroys semantic structure in output files.

**Solution**: Custom serializer in `serialiser.py` that respects provided order.

**Trade-off**: More maintenance, but essential for project goals.

### Why YAML Configuration?

**Reasoning**:
- Human-readable and writable
- Supports reusable definitions (YAML anchors)
- No code changes needed for new profiles
- Industry standard for config

**Alternative considered**: Python DSL (rejected—less accessible)

### Why Separate UML Module?

**Reasoning**:
- Different audience (diagram generation vs. serialization)
- Different dependencies (PlantUML)
- Independent evolution
- Clear module boundaries

### Arrow Direction in Layouts

**Problem**: PlantUML's auto-layout doesn't always place parents above children.

**Solution**: Use arrow direction hints (`-up-|>`, `-down-|>`) to influence layout.

**Trade-off**: Not guaranteed (PlantUML heuristics), but works in practice.

## Extension Points

### Adding New Selection Modes

1. Add mode to `selector.py`
2. Update YAML schema documentation
3. Add tests for new mode

### Adding New Sort Modes

1. Implement algorithm in `ordering.py`
2. Update `sort_subjects()` dispatch
3. Add tests and examples

### Adding New Output Formats

1. Create new serializer module (e.g., `serialiser_jsonld.py`)
2. Implement format-specific logic
3. Update CLI to support new format

## Testing Strategy

### Unit Tests
- Each module independently testable
- Mock rdflib.Graph for isolation
- Test edge cases (cycles, empty graphs)

### Integration Tests
- End-to-end workflows
- Real ontology files
- Verify output correctness

### Example-Based Testing
- `examples/` directory as test corpus
- Generated outputs should be reproducible
- Visual inspection of diagrams

## Performance Considerations

### Topological Sort
- **Complexity**: O(V + E) where V=nodes, E=edges
- **Scale**: Handles thousands of classes efficiently
- **Bottleneck**: Graph parsing (rdflib), not our code

### Memory Usage
- **In-memory graphs**: rdflib loads entire graph
- **Limitation**: Very large ontologies (millions of triples) may need streaming
- **Current target**: Ontologies up to ~100K triples

## Known Issues

### Namespace Conflicts

**Problem**: rdflib has built-in namespace bindings that may conflict with ontology prefixes.

**Example**: `org:` defaults to W3C org ontology, not user's ontology.

**Workaround**: Check actual bindings, use assigned prefix in YAML.

**Future**: Could add prefix override mechanism in config.

### PlantUML Layout Limitations

**Problem**: PlantUML's layout engine has heuristics that don't always obey hints.

**Impact**: Diagrams may not match exact desired layout.

**Mitigation**: Use arrow direction hints, adjust spacing parameters.

## Dependencies

### Core
- `rdflib`: RDF parsing and manipulation
- `pyyaml`: YAML configuration parsing
- `click`: CLI framework

### Development
- `black`: Code formatting
- `ruff`: Linting
- `mypy`: Type checking
- `pytest`: Testing

## Future Architecture Changes

### Planned
1. **Semantic diff module**: Compare RDF graphs, generate changesets
2. **Validation module**: Check for common ontology issues
3. **Multi-format support**: JSON-LD, RDF/XML input

### Under Consideration
1. **Streaming mode**: For very large graphs
2. **Plugin system**: User-defined selectors and sorters
3. **Web UI**: Browser-based diagram configuration

## References

- **rdflib docs**: https://rdflib.readthedocs.io/
- **PlantUML**: https://plantuml.com/
- **Click**: https://click.palletsprojects.com/
- **Neuromancer**: William Gibson (inspiration)