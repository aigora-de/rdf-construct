# Changelog

All notable changes to rdf-construct will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Nothing yet

## [0.1.0] - 2025-11-30

Initial public release.

### Added

#### Core Features
- `order` command for semantic RDF/Turtle ordering
  - Topological sorting respecting `rdfs:subClassOf` and `rdfs:subPropertyOf`
  - Alphabetical sorting for deterministic output
  - Anchor-based ordering for key concepts
  - Configurable predicate ordering within subjects
  - Custom serialiser preserving subject order (rdflib always sorts alphabetically)

- `uml` command for PlantUML class diagram generation
  - Root-based class selection with descendant traversal
  - Focus-based class selection for specific views
  - Explicit mode for precise control over diagram contents
  - Configurable depth limiting for large ontologies
  - Instance (individual) rendering with class relationships

#### Property Handling
- Multiple property selection modes: `domain_based`, `connected`, `explicit`, `all`, `none`
- Object property and datatype property distinction
- Property filtering via include/exclude lists

#### Styling System
- Namespace-based class colouring
- Type-based styling for meta-classes
- Instance styling with class border inheritance
- Arrow styling for different relationship types
- IES colour palette support with semantic colouring
- Stereotype mapping and display

#### Layout Options
- Direction control (top-to-bottom, left-to-right)
- Orthogonal line routing
- Inheritance arrow merging
- Class grouping by namespace
- Configurable spacing

#### ODM Compliance
- ODM (Ontology Definition Metamodel) rendering mode
- RDF vocabulary styling (rdf:type as dependency arrows)
- Standards-compliant diagram generation

#### CLI
- Click-based command-line interface
- Multiple source file support
- Profile/context selection
- Output directory configuration
- Context and profile listing commands

### Documentation
- Getting Started guide
- UML Guide with complete feature reference
- CLI Reference with all commands and options
- Architecture documentation for contributors
- IES Colour Palette guides
- Project Setup guide for end users
- Quick Reference card

### Examples
- Animal ontology (simple hierarchy)
- Organisation ontology (multiple roots)
- IES Building ontology (complex real-world example)
- Sample configuration files for all features

---

## Version History Summary

| Version | Date       | Highlights |
|---------|------------|------------|
| 0.1.0 | 2025-11-30 | Initial release: ordering, UML generation, styling |

[Unreleased]: https://github.com/aigora-de/rdf-construct/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/aigora-de/rdf-construct/releases/tag/v0.1.0