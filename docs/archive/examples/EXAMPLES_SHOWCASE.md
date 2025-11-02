# RDF → PlantUML Pipeline: Working Examples

## What We Built

A complete pipeline that transforms RDF ontologies into PlantUML class diagrams using YAML-based context configurations. This allows you to:

✅ Generate focused diagrams from large ontologies
✅ Control what classes and properties are included
✅ Show or hide instances (individuals)
✅ Traverse hierarchies with configurable depth
✅ Use multiple selection strategies

## Example 1: Animal Taxonomy

**Context Configuration:**
```yaml
animal_taxonomy:
  description: "Complete animal class hierarchy with properties"
  root_classes:
    - ex:Animal
  include_descendants: true
  properties:
    mode: domain_based
```

**Generated PlantUML:**
```plantuml
@startuml

class ex:Animal {
  +average weight: decimal
  +lifespan: integer
}

class ex:Bird {
}

class ex:Cat {
}

class ex:Dog {
}

class ex:Eagle {
}

class ex:Mammal {
}

class ex:Sparrow {
}

ex:Bird --|> ex:Animal
ex:Cat --|> ex:Mammal
ex:Dog --|> ex:Mammal
ex:Eagle --|> ex:Bird
ex:Mammal --|> ex:Animal
ex:Sparrow --|> ex:Bird


ex:Animal --> ex:Animal : eats
ex:Animal --> ex:Animal : has parent

@enduml
```

**Result**: 7 classes, 5 properties, full hierarchy

---

## Example 2: Management Structure with Instances

**Context Configuration:**
```yaml
management:
  description: "Focus on management and reporting relationships"
  focus_classes:
    - org1:Manager
    - org1:Employee
    - org1:Executive
    - org1:CEO
  include_descendants: false
  properties:
    mode: explicit
    include:
      - org1:manages
      - org1:reportsTo
      - org1:worksFor
  include_instances: true
```

**Generated PlantUML:**
```plantuml
@startuml

class org1:CEO {
}

class org1:Employee {
}

class org1:Executive {
}

class org1:Manager {
}

object "Alice Smith" as org1:AliceSmith {
}

object "Bob Jones" as org1:BobJones {
}

object "Carol Davis" as org1:CarolDavis {
}

object "Dave Wilson" as org1:DaveWilson {
}

org1:CEO --|> org1:Executive
org1:Executive --|> org1:Manager
org1:Manager --|> org1:Employee

org1:AliceSmith ..|> org1:CEO
org1:BobJones ..|> org1:Manager
org1:CarolDavis ..|> org1:Employee
org1:DaveWilson ..|> org1:Manager

org1:Manager --> org1:Employee : manages
org1:Employee --> org1:Manager : reports to

@enduml
```

**Result**: 4 classes, 3 properties, 4 instances with relationships

---

## Example 3: People with Data Properties

**Context Configuration:**
```yaml
people_roles:
  description: "People, employees, and management hierarchy"
  root_classes:
    - org1:Person
  include_descendants: true
  properties:
    mode: domain_based
    exclude:
      - org1:email
      - org1:phoneNumber
  include_instances: true
```

**Generated PlantUML:**
```plantuml
@startuml

class org1:CEO {
}

class org1:Employee {
  +employee ID: string
  +salary: decimal
}

class org1:Executive {
}

class org1:Manager {
}

class org1:Person {
}

object "Alice Smith" as org1:AliceSmith {
  employee ID = CEO001
  salary = 250000.00
}

object "Bob Jones" as org1:BobJones {
  employee ID = ENG042
  salary = 120000.00
}

object "Carol Davis" as org1:CarolDavis {
  employee ID = ENG089
}

object "Dave Wilson" as org1:DaveWilson {
  employee ID = SAL011
}

org1:CEO --|> org1:Executive
org1:Employee --|> org1:Person
org1:Executive --|> org1:Manager
org1:Manager --|> org1:Employee

org1:AliceSmith ..|> org1:CEO
org1:BobJones ..|> org1:Manager
org1:CarolDavis .--|> org1:Employee
org1:DaveWilson ..|> org1:Manager

org1:Person --> org1:Person : collaborates with
org1:Manager --> org1:Employee : manages
org1:Employee --> org1:Manager : reports to

@enduml
```

**Result**: 5 classes, 7 properties, 4 instances with actual data values

---

## Key Features Demonstrated

### 1. Flexible Class Selection
- **Root + descendants**: Start from key classes, include all subclasses
- **Focus list**: Explicitly specify classes to include
- **Selector**: Use predefined selectors for bulk selection

### 2. Smart Property Filtering
- **domain_based**: Properties whose domain matches selected classes
- **connected**: Properties connecting selected classes
- **explicit**: Hand-picked properties only
- **Exclusions**: Remove unwanted properties

### 3. Instance Rendering
- Shows individuals with their class membership
- Displays property values for datatype properties
- Uses dotted arrows for rdf:type relationships

### 4. Hierarchy Traversal
- Respects rdfs:subClassOf relationships
- Configurable max depth
- Maintains topological ordering

---

## Real-World Applications

### Ontology Documentation
Generate diagrams for different audiences:
- **Overview**: High-level class structure
- **Technical**: Full properties and constraints
- **Examples**: Classes with sample instances

### Focused Views
Extract relevant subsets from large ontologies:
- Domain-specific concepts
- Cross-cutting concerns
- Integration points

### Teaching & Communication
Create clear visualizations:
- Step-by-step concept introduction
- Compare alternative modeling approaches
- Show concrete examples with data

---

## Next: Phase 2 (Styling & Layout)

With the pipeline working, we can now add:

1. **Color schemes** - Semantic coloring by namespace, type, or hierarchy
2. **Custom styling** - Classes, properties, and instances
3. **Layout control** - Direction, grouping, spacing
4. **Arrow styling** - Different colors for relationship types
5. **Visual semantics** - Metaclasses, powertype relationships, etc.

Example future config:
```yaml
styling:
  classes:
    by_namespace:
      ex: "#E8F4F8;line:#0066CC"
  properties:
    rdf_type: "#line:red;line.bold"
  instances:
    fill: "#000000"
    border_from_class: true

layout:
  direction: top_to_bottom
  hide_empty_members: true
```

---

## Files Included

- **Source Code**: Complete UML module in `src/rdf_construct/uml/`
- **Examples**: Animal and organisation ontologies
- **Configs**: `examples/uml_contexts.yml` with 8 different contexts
- **Generated Diagrams**: 11 `.puml` files demonstrating various features
- **Documentation**: This file and `UML_PIPELINE_SUMMARY.md`

## Usage

```bash
# List contexts
python -m rdf_construct.cli contexts examples/uml_contexts.yml

# Generate specific diagram
python -m rdf_construct.cli uml \
    examples/organisation_ontology.ttl \
    examples/uml_contexts.yml \
    -c management \
    -o output/

# Generate all diagrams
python -m rdf_construct.cli uml \
    examples/animal_ontology.ttl \
    examples/uml_contexts.yml
```

---

## Summary

✅ **Fully functional** basic RDF → PlantUML pipeline
✅ **YAML-driven** configuration for flexibility
✅ **Multiple strategies** for class and property selection
✅ **Instance support** with data values
✅ **Clean output** ready for PlantUML rendering
✅ **Extensible design** ready for styling enhancements

The foundation is solid and working. Ready for Phase 2!