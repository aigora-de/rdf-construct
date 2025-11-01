# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of rdf-construct
- Core ordering functionality with topological and alphabetical sorting
- YAML-based profile configuration system
- CLI with `order` and `profiles` commands
- Custom Turtle serializer that preserves semantic ordering
- Support for root-based branch organization
- Comprehensive type hints throughout codebase
- Unit tests for core ordering logic

### Changed
- N/A (initial release)

### Deprecated
- N/A (initial release)

### Removed
- N/A (initial release)

### Fixed
- N/A (initial release)

### Security
- N/A (initial release)

## [0.1.0] - 2025-11-02

### Added
- Initial public release
- Refactored from `order_turtle.py` monolith into modular package structure
- Modern Python packaging with `pyproject.toml`
- Click-based CLI with rich output
- Programmatic API for library use
- Documentation and examples

[Unreleased]: https://github.com/yourusername/rdf-construct/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/rdf-construct/releases/tag/v0.1.0