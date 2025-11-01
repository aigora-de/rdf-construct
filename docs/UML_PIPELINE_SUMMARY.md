# RDF to PlantUML Pipeline - Implementation Summary

## Overview
We've successfully implemented a basic RDF → PlantUML class diagram pipeline for the rdf-construct toolkit. This allows generation of UML diagrams from RDF/OWL ontologies using YAML-based context configurations.

## Architecture

### Module Structure
```
src/rdf_construct/
├── uml/
│   ├── __init__.py          # Module exports
│   ├── context.py           # YAML context configuration loading
│   ├── mapper.py            # RDF entity selection and filtering
│   └── renderer.py          # PlantUML text generation
├── core/                    # Existing core functionality (reused)
└── cli.py                   # Updated CLI with `uml` command
```

### Pipeline Flow
1. **Load** RDF ontology (Turtle format) using rdflib
2. **Configure** via YAML context specifying what to include
3. **Select** classes, properties, and instances based on context rules
4. **Render** to PlantUML syntax
5. **Output** .puml files ready for visualization

## Features Implemented

### Class Selection Strategies
- **Root classes** with optional descendants (hierarchy traversal)
- **Focus classes** (explicit list)
- **Selector-based** (reuse selectors from ordering configs)
- **Max depth** limiting for hierarchy traversal

### Property Selection Modes
- **domain_based**: Include properties where domain is in selected classes
- **connected**: Properties connecting selected classes
- **explicit**: Only specified properties
- **all**: All properties in the ontology
- **none**: No properties

### Rendering Features
- Classes with datatype properties as attributes
- Inheritance relationships (rdfs:subClassOf) as generalization arrows
- Object properties as associations
- Instances as objects with property values
- Instance-to-class relationships (rdf:type)

## CLI Commands

### Generate UML Diagrams
```bash
# Generate all contexts from config
rdf-construct uml ontology.ttl uml_contexts.yml

# Generate specific context(s)
rdf-construct uml ontology.ttl uml_contexts.yml -c animal_taxonomy

# Custom output directory
rdf-construct uml ontology.ttl uml_contexts.yml -o diagrams/
```

### List Available Contexts
```bash
rdf-construct contexts uml_contexts.yml
```

## Example YAML Configuration

```yaml
defaults:
  include_properties: true
  include_instances: false

contexts:
  animal_taxonomy:
    description: "Complete animal class hierarchy"
    root_classes:
      - ex:Animal
    include_descendants: true
    max_depth: null  # Unlimited
    properties:
      mode: domain_based
    include_instances: false

  management:
    description: "Management relationships"
    focus_classes:
      - org1:Manager
      - org1:Employee
    properties:
      mode: explicit
      include:
        - org1:manages
        - org1:reportsTo
    include_instances: true
```

## Example Outputs

### Animal Taxonomy (7 classes, 5 properties)
```plantuml
class ex:Animal {
  +average weight: decimal
  +lifespan: integer
}
class ex:Mammal {
}
class ex:Dog {
}

ex:Mammal --|> ex:Animal
ex:Dog --|> ex:Mammal

ex:Animal --> ex:Animal : eats
ex:Animal --> ex:Animal : has parent
```

### Management (4 classes, 3 properties, 4 instances)
```plantuml
class org1:Manager {
}
class org1:Employee {
}

object "Alice Smith" as org1:AliceSmith {
}

org1:Manager --|> org1:Employee
org1:AliceSmith ..|> org1:CEO
org1:Manager --> org1:Employee : manages
```

## Known Issues & Notes

### Namespace Conflicts
**Issue**: RDFlib has built-in namespace bindings that can conflict with ontology prefixes.

**Example**: `org:` prefix defaults to `http://www.w3.org/ns/org#` in rdflib, but our
organisation ontology uses `http://example.org/organisation#`. When parsed, rdflib
assigns `org1:` to our ontology.

**Solution**: Use the prefix that rdflib assigns (check with namespace inspection) or
rename prefixes in the source ontology to avoid conflicts.

**Future work**: Could implement prefix override mechanism in config.

## Testing Results

✅ **Animal Ontology** (examples/animal_ontology.ttl)
- animal_taxonomy: 7 classes, 5 properties ✓
- mammals_only: 3 classes, 2 instances ✓
- key_classes: 3 classes, 4 properties ✓
- full: 7 classes, 6 properties, 3 instances ✓

✅ **Organisation Ontology** (examples/organisation_ontology.ttl)
- management: 4 classes, 3 properties, 4 instances ✓
- people_roles: 5 classes, 7 properties, 4 instances ✓
- org_hierarchy: Works with corrected namespace ✓

## Next Steps (Phase 2: Styling & Layout)

### Styling Features to Add
1. **Color schemes** for classes, properties, arrows
2. **Semantic coloring** (by namespace, hierarchy level, metaclass)
3. **Instance styling** (black fill with class-colored borders)
4. **Property-specific arrow colors** (red for rdf:type, etc.)
5. **Custom styles** via YAML configuration

### Layout Features
1. **Direction control** (top-to-bottom, left-to-right)
2. **Layout hints** for PlantUML
3. **Grouping/clustering** of related classes
4. **Hide empty members** option

### Configuration Extensions
```yaml
styling:
  schemes:
    ies_semantic:
      classes:
        by_namespace:
          ies: "#E8F4F8;line:#0066CC;line.bold"
        by_type:
          meta_class: "#FFE6E6;line:#CC0000"
      properties:
        rdf_type: "#line:red;line.bold"
        object_property: "#line:blue"
      instances:
        fill: "#000000"
        border_from_class: true

layout:
  direction: top_to_bottom
  hide_empty_members: true
```

## Code Quality

- ✅ Type hints throughout
- ✅ Docstrings (Google style)
- ✅ Modular design (easy to extend)
- ✅ Reuses existing core functionality
- ✅ Clean CLI interface
- ⏳ Unit tests (TODO)
- ⏳ Integration tests (TODO)

## Dependencies

- `rdflib` - RDF parsing and graph operations
- `pyyaml` - YAML configuration loading
- `click` - CLI framework

## Files Generated

This implementation includes:
- `src/rdf_construct/uml/` - Complete UML module
- `examples/uml_contexts.yml` - Example configuration
- Generated `.puml` files in `output/diagrams/`
- This documentation

## Usage Example

```bash
# 1. Create or use existing ontology
examples/animal_ontology.ttl

# 2. Create UML context configuration
examples/uml_contexts.yml

# 3. Generate diagrams
cd /home/claude
export PYTHONPATH=/home/claude/src:$PYTHONPATH
python -m rdf_construct.cli uml examples/animal_ontology.ttl examples/uml_contexts.yml

# 4. View/render with PlantUML
# (PlantUML can render .puml files to PNG/SVG/etc.)
```

## Summary

✅ **Phase 1 Complete**: Basic RDF→PlantUML pipeline fully functional
- Class hierarchy visualization
- Property inclusion with multiple modes
- Instance rendering with data
- Flexible YAML-based configuration
- Clean CLI interface

🎯 **Ready for Phase 2**: Styling and layout enhancements

The foundation is solid and extensible. All core functionality works as designed,
with clear patterns for adding styling and layout features.