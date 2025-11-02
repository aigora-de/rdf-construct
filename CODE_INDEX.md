# rdf-construct Code Index

## Overview

This document provides a comprehensive index of all code, documentation, and configuration files in the rdf-construct project. Use this as a reference for understanding project structure and locating specific components.

**Last Updated**: 2025-11-02
**Project Status**: Active development - UML generation phase complete  
**License**: MIT

---

## Directory Structure

```
rdf-construct/
├── src/                                    # Source code (to be organized)
│   ├── rdf_construct/
│   │   ├── core/                          # Core RDF operations
│   │   │   ├── config.py
│   │   │   ├── profile.py
│   │   │   ├── selector.py
│   │   │   ├── ordering.py
│   │   │   ├── serialiser.py
│   │   │   └── utils.py
│   │   ├── uml/                           # UML diagram generation
│   │   │   ├── context.py
│   │   │   ├── mapper.py
│   │   │   ├── renderer.py
│   │   │   ├── uml_style.py
│   │   │   └── uml_layout.py
│   │   ├── cli.py                         # Command-line interface
│   │   └── main.py                        # Entry point
├── examples/                               # Example ontologies and configs
│   ├── animal_ontology.ttl
│   ├── organisation_ontology.ttl
│   ├── simple_ontology.ttl
│   ├── test_profile.yml
│   ├── sample_profile.yml
│   ├── uml_contexts.yml
│   └── example_styled_uml.py
├── docs/                                   # Documentation
│   ├── README.md                          # Documentation index
│   ├── REFACTORING_SUMMARY.md             # Doc refactoring details
│   ├── FINAL_STRUCTURE.md                 # Final doc structure
│   ├── dev/                               # Developer documentation
│   │   ├── ARCHITECTURE.md                # System design
│   │   └── UML_IMPLEMENTATION.md          # Technical details
│   ├── user_guides/                       # User documentation
│   │   ├── GETTING_STARTED.md             # Quick start
│   │   ├── UML_GUIDE.md                   # Complete UML features
│   │   └── CLI_REFERENCE.md               # Command reference
│   └── archive/                           # Archived documentation
│       ├── ARCHIVED_FILES.md
│       └── docs_*.md                      # Original 10 doc files
├── tests/                                  # Test suite (to be added)
│   └── (pending implementation)
├── pyproject.toml                          # Package configuration
├── CONTRIBUTING.md                         # Development guide
├── CODE_INDEX.md                          # This file
├── DOCUMENTATION_REFACTORING.md           # Doc refactoring summary
└── project-dev.md                         # Project instructions
```

---

## Source Code Files

### Core Package (`src/rdf_construct/core/`)

#### config.py (193 lines)
**Purpose**: Configuration loading and dataclasses  
**Key Components**:
- `SectionConfig`: Section configuration dataclass
- `ProfileConfig`: Profile configuration dataclass
- `OrderingSpec`: Complete YAML specification
- `load_yaml()`: YAML file loader
- `load_ordering_spec()`: Parse and validate ordering configs

**Dependencies**: `yaml`, `pathlib`, `dataclasses`, `rdflib`

#### profile.py (111 lines)
**Purpose**: Profile and configuration management  
**Key Components**:
- `OrderingProfile`: Single profile representation
- `OrderingConfig`: Manages multiple profiles
- `get_profile()`: Profile accessor
- `list_profiles()`: List available profiles

**Dependencies**: `yaml`, `pathlib`, `typing`

#### selector.py (65 lines)
**Purpose**: RDF subject selection logic  
**Key Components**:
- `select_subjects()`: Main selection function
- Supports: classes, obj_props, data_props, ann_props, individuals

**Dependencies**: `rdflib` (Graph, RDF, RDFS, OWL)

**Selection Modes**:
- `classes`: owl:Class and rdfs:Class entities
- `obj_props`: owl:ObjectProperty
- `data_props`: owl:DatatypeProperty
- `ann_props`: owl:AnnotationProperty
- `individuals`: Non-class, non-property subjects

#### ordering.py (220 lines)
**Purpose**: Sorting algorithms for RDF subjects  
**Key Components**:
- `build_adjacency()`: Build graph adjacency list
- `topo_sort_subset()`: Kahn's algorithm for topological sorting
- `descendants_of()`: Find all descendants of a root
- `sort_with_roots()`: Root-based branch ordering
- `sort_subjects()`: Main sorting dispatcher

**Algorithms**:
- Topological sort: O(V + E) complexity
- Handles cycles gracefully
- Alphabetical tie-breaking for determinism

**Dependencies**: `rdflib` (Graph, URIRef, RDF, RDFS, OWL)

#### serialiser.py (168 lines)
**Purpose**: Custom RDF serialization (preserves semantic ordering)  
**Key Components**:
- `format_term()`: Format RDF terms as Turtle strings
- `serialise_turtle()`: Custom Turtle writer
- `build_section_graph()`: Filter graph to selected subjects

**Critical Feature**: Unlike rdflib's built-in serializers, preserves exact subject order

**Dependencies**: `rdflib` (Graph, URIRef, Literal, RDF)

#### utils.py (90 lines)
**Purpose**: Utility functions for prefixes, CURIEs, namespaces  
**Key Components**:
- `extract_prefix_map()`: Get namespaces from graph
- `expand_curie()`: Expand CURIE to full URI
- `rebind_prefixes()`: Set prefix order
- `qname_sort_key()`: Generate sortable keys

**Dependencies**: `rdflib` (Graph, Namespace, URIRef)

---

### UML Package (`src/rdf_construct/uml/`)

#### context.py (120+ lines)
**Purpose**: UML context configuration  
**Key Components**:
- `UMLContext`: Diagram specification
- `UMLConfig`: Manages multiple contexts
- `load_uml_config()`: Load config from YAML

**Context Features**:
- Root classes with descendants
- Focus classes (explicit list)
- Selector-based bulk selection
- Property filtering modes
- Instance inclusion

**Dependencies**: `yaml`, `pathlib`, `typing`

#### mapper.py (200+ lines)
**Purpose**: Entity selection for diagrams  
**Key Components**:
- `get_descendants()`: BFS traversal of class hierarchy
- `select_classes()`: Class selection with multiple strategies
- `select_properties()`: Property filtering (5 modes)
- `select_instances()`: Instance selection by class membership
- `collect_diagram_entities()`: Main entry point

**Selection Strategies**:
1. Root classes with descendants
2. Focus classes (explicit list)
3. Selector-based bulk selection

**Property Modes**:
- `domain_based`: Properties where domain matches selected classes
- `connected`: Properties connecting selected classes
- `explicit`: Hand-picked properties
- `all`: All properties
- `none`: No properties

**Dependencies**: `rdflib` (Graph, URIRef, RDF, RDFS, OWL)

#### renderer.py (300+ lines)
**Purpose**: PlantUML text generation  
**Key Components**:
- `qname()`: Get qualified name for URI
- `safe_label()`: Get display label from rdfs:label
- `escape_plantuml()`: Escape special characters
- `PlantUMLRenderer`: Main renderer class
  - `render_class()`: Class with attributes
  - `render_instance()`: Instance as object
  - `render_subclass_relationships()`: Inheritance arrows
  - `render_instance_relationships()`: Instance-class links
  - `render_object_properties()`: Property associations
  - `render()`: Complete diagram generation

**PlantUML Syntax**:
- Classes: `class "prefix:Name" { +attr : type }`
- Inheritance: `"Child" --|> "Parent"`
- Object properties: `"Domain" --> "Range" : propertyName`
- Instances: `object "Label" as prefix:name { attr = value }`
- Instance-class: `"instance" ..|> "Class"`

**Dependencies**: `rdflib`, `.uml_style`, `.uml_layout`

#### uml_style.py (300+ lines)
**Purpose**: Visual styling configuration  
**Key Components**:
- `ColorPalette`: Border, fill, text colors
- `ArrowStyle`: Relationship arrow styling
- `StyleScheme`: Complete visual theme
- `StyleConfig`: Manages multiple schemes

**Styling Features**:
- Namespace-based coloring
- Type-based coloring (metaclasses)
- Instance styling with class inheritance
- Stereotype display
- PlantUML color format: `#FILL;line:BORDER;line.STYLE;text:TEXT`

**Dependencies**: `yaml`, `pathlib`, `rdflib` (Graph, URIRef, RDF)

#### uml_layout.py (200+ lines)
**Purpose**: Spatial arrangement configuration  
**Key Components**:
- `LayoutConfig`: Direction, spacing, grouping
- `LayoutConfigManager`: Manages multiple layouts

**Layout Features**:
- Direction control (top-to-bottom, left-to-right, etc.)
- Arrow direction hints for hierarchy
- Hide empty members option
- PlantUML directive generation
- Spacing control via skinparam

**Dependencies**: `yaml`, `pathlib`, `typing`

---

### CLI and Main (`src/rdf_construct/`)

#### cli.py (174 lines)
**Purpose**: Command-line interface  
**Key Components**:
- `cli()`: Main CLI group
- `order()`: Reorder RDF files command
- `profiles()`: List ordering profiles
- `uml()`: Generate UML diagrams
- `contexts()`: List UML contexts

**Commands**:
```bash
rdf-construct order SOURCE CONFIG [OPTIONS]
rdf-construct profiles CONFIG
rdf-construct uml SOURCE CONFIG [OPTIONS]
rdf-construct contexts CONFIG
```

**Dependencies**: `click`, all core and uml modules

#### main.py (5 lines)
**Purpose**: Entry point for `python -m rdf_construct`  
**Content**: Imports and calls CLI

---

## Configuration Files

### pyproject.toml (134 lines)
**Purpose**: Modern Python packaging configuration  
**Package Info**:
- Name: rdf-construct
- Version: 0.1.0
- License: MIT
- Python: ^3.10

**Dependencies**:
- Runtime: rdflib, click, pyyaml, rich
- Dev: black, ruff, mypy, pytest, pytest-cov, pre-commit

**Tools Configured**:
- Black (line length: 100)
- Ruff (linting)
- Mypy (type checking)
- Pytest (testing)

**Entry Point**: `rdf-construct` command

---

## Example Files

### Ontologies

#### animal_ontology.ttl
**Content**: Simple animal class hierarchy  
**Classes**: Animal → Mammal/Bird → Dog/Cat/Eagle/Sparrow  
**Properties**: hasParent, eats, livesIn, lifespan, averageWeight, scientificName  
**Instances**: Fido (Dog), Whiskers (Cat), Baldy (Eagle)

#### organisation_ontology.ttl
**Content**: Organizational structure ontology  
**Classes**: Organisation, Person, Department hierarchies  
**Properties**: worksFor, manages, reportsTo, hasDepartment, memberOf  
**Instances**: TechCorpInc, AliceSmith (CEO), BobJones (Manager), etc.

#### simple_ontology.ttl
**Content**: Minimal test ontology  
**Classes**: Animal → Mammal → Dog/Cat  
**Properties**: hasParent

### Configuration Files

#### test_profile.yml / sample_profile.yml
**Purpose**: Ordering profile examples  
**Profiles**: alpha, topo, animal_topo, org_topo, mixed, compact  
**Features**: Demonstrates all sorting modes and root-based ordering

#### uml_contexts.yml
**Purpose**: UML context examples  
**Contexts**: 
- animal_taxonomy: Full hierarchy
- mammals_only: Subset with depth limit
- key_classes: Explicit focus classes
- properties_focus: Specific properties
- full: Everything
- org_hierarchy: Organization structure
- people_roles: People and management
- management: Management relationships

### Example Scripts

#### example_styled_uml.py
**Purpose**: Demonstrates UML generation with styling and layout  
**Content**: Complete working examples with different style/layout combinations

---

## Documentation Files

### Root Level

#### CONTRIBUTING.md (446 lines)
**Purpose**: Development guide  
**Content**:
- Getting started (prerequisites, installation)
- Development workflow (testing, code quality)
- Coding standards (style, type hints, imports)
- Testing guidelines
- Adding new features
- Module-specific guidelines
- Documentation requirements
- Release process
- Common tasks

#### CODE_INDEX.md (This file)
**Purpose**: Comprehensive code and file index

#### DOCUMENTATION_REFACTORING.md
**Purpose**: Documentation reorganization summary

#### project-dev.md
**Purpose**: Project instructions and development principles

### Documentation Directory (docs/)

See `docs/README.md` for complete documentation index.

**Key Files**:
- `docs/README.md`: Documentation landing page
- `docs/REFACTORING_SUMMARY.md`: Detailed refactoring notes
- `docs/FINAL_STRUCTURE.md`: Final structure reference

**Developer Docs** (`docs/dev/`):
- `ARCHITECTURE.md`: System design (371 lines)
- `UML_IMPLEMENTATION.md`: Technical implementation (550+ lines)

**User Guides** (`docs/user_guides/`):
- `GETTING_STARTED.md`: Quick start (419 lines)
- `UML_GUIDE.md`: Complete UML features (650+ lines)
- `CLI_REFERENCE.md`: Command reference (450+ lines)

---

## Key Design Patterns

### Custom Serialization
**Problem**: rdflib always sorts subjects alphabetically  
**Solution**: Custom `serialise_turtle()` that preserves semantic order  
**Location**: `src/rdf_construct/core/serialiser.py`

### Topological Sorting
**Algorithm**: Kahn's algorithm  
**Purpose**: Parent-before-child ordering  
**Location**: `src/rdf_construct/core/ordering.py`  
**Complexity**: O(V + E)

### Strategy Pattern
**Used For**: Class selection (root/focus/selector strategies)  
**Location**: `src/rdf_construct/uml/mapper.py`  
**Benefit**: Flexible entity selection without code changes

### Configuration-Driven
**Format**: YAML  
**Benefit**: Change behavior without code changes  
**Used For**: Profiles, contexts, styles, layouts

---

## Testing Status

**Current**: Minimal tests exist  
**Needed**:
- Unit tests for core modules (>90% coverage target)
- Integration tests for end-to-end workflows
- Example-based tests using sample ontologies
- Visual verification of PlantUML output

**Test Framework**: pytest (configured in pyproject.toml)

---

## Module Dependencies

### Core Dependencies
```
rdflib >= 7.0.0    # RDF parsing and manipulation
click >= 8.1.0     # CLI framework
pyyaml >= 6.0      # YAML configuration
rich >= 13.0.0     # Terminal output (not yet used)
```

### Development Dependencies
```
black >= 24.0.0         # Code formatting
ruff >= 0.1.0          # Linting
mypy >= 1.8.0          # Type checking
pytest >= 8.0.0        # Testing
pytest-cov >= 4.1.0    # Coverage
types-pyyaml >= 6.0.0  # Type stubs
pre-commit >= 3.6.0    # Git hooks
```

---

## Code Quality Standards

### Formatting
- **Tool**: Black
- **Line Length**: 100
- **Target Versions**: Python 3.10, 3.11, 3.12

### Linting
- **Tool**: Ruff (replaces flake8, isort)
- **Rules**: E, W, F, I, UP, B, C4, SIM, TCH
- **Ignore**: E501 (line too long - handled by Black)

### Type Checking
- **Tool**: Mypy
- **Mode**: Strict
- **Required**: All public functions must have type hints

### Documentation
- **Docstring Style**: Google
- **Required**: All public functions, classes, modules

---

## Performance Characteristics

### Topological Sort
- **Complexity**: O(V + E) where V=nodes, E=edges
- **Scale**: Handles thousands of classes efficiently
- **Bottleneck**: Graph parsing (rdflib), not our code

### Memory Usage
- **In-Memory**: rdflib loads entire graph
- **Limitation**: Very large ontologies (millions of triples) may need streaming
- **Current Target**: Ontologies up to ~100K triples

---

## Known Issues

### Namespace Conflicts
**Problem**: rdflib has built-in namespace bindings  
**Example**: `org:` defaults to W3C org ontology  
**Workaround**: Check actual bindings, use assigned prefix  
**Future**: Add prefix override mechanism

### PlantUML Layout
**Problem**: Layout engine doesn't always obey hints  
**Impact**: Diagrams may not match exact desired layout  
**Mitigation**: Use arrow direction hints, adjust spacing

---

## Future Development

### Planned Features
1. Semantic diff module (compare RDF graphs, generate changesets)
2. Validation module (check for common ontology issues)
3. Multi-format support (JSON-LD, RDF/XML input)

### Under Consideration
1. Streaming mode for very large graphs
2. Plugin system for user-defined selectors and sorters
3. Web UI for browser-based diagram configuration

---

## References

### External Resources
- **rdflib docs**: https://rdflib.readthedocs.io/
- **PlantUML**: https://plantuml.com/
- **Click**: https://click.palletsprojects.com/
- **Black**: https://black.readthedocs.io/
- **Ruff**: https://beta.ruff.rs/docs/

### Internal Documentation
- **Architecture**: `docs/dev/ARCHITECTURE.md`
- **UML Implementation**: `docs/dev/UML_IMPLEMENTATION.md`
- **User Guide**: `docs/user_guides/GETTING_STARTED.md`
- **CLI Reference**: `docs/user_guides/CLI_REFERENCE.md`

---

## Quick Reference

### Find Source Code
```bash
# Core functionality
ls src/rdf_construct/core/

# UML functionality
ls src/rdf_construct/uml/

# CLI
cat src/rdf_construct/cli.py
```

### Run Tests
```bash
pytest                                    # All tests
pytest --cov=rdf_construct               # With coverage
pytest tests/test_ordering.py            # Specific test
```

### Code Quality
```bash
black src/ tests/                        # Format
ruff check src/ tests/                   # Lint
mypy src/                                # Type check
pre-commit run --all-files               # All checks
```

### Generate Diagrams
```bash
# All contexts
rdf-construct uml examples/animal_ontology.ttl examples/uml_contexts.yml

# Specific context
rdf-construct uml examples/animal_ontology.ttl examples/uml_contexts.yml -c animal_taxonomy

# With styling
rdf-construct uml examples/animal_ontology.ttl examples/uml_contexts.yml \
  --style-config examples/uml_styles.yml --style default \
  --layout-config examples/uml_layouts.yml --layout hierarchy
```

---

## Contributing

See `CONTRIBUTING.md` for complete development guidelines.

**Quick Start**:
1. Clone repository
2. Install: `poetry install`
3. Setup hooks: `pre-commit install`
4. Make changes
5. Test: `pytest`
6. Format: `black src/ tests/`
7. Submit PR

---

## License

MIT License - See LICENSE file for details.

**Status**: ✅ Active Development  
**Last Updated**: 2025-11-02
**Maintainer**: See CONTRIBUTING.md