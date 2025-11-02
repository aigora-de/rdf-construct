# Contributing to rdf-construct

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Poetry (recommended) or pip
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/aigora-de/rdf-construct.git
cd rdf-construct

# Install with Poetry
poetry install

# Or with pip
pip install -e ".[dev]"
```

### Project Structure

```
rdf-construct/
├── src/rdf_construct/         # Main package
│   ├── core/                  # Core RDF operations
│   ├── uml/                   # UML diagram generation
│   ├── cli.py                 # CLI interface
│   └── main.py                # Entry point
├── tests/                     # Test suite
├── examples/                  # Example ontologies and configs
├── docs/                      # Documentation
│   ├── dev/                   # Developer documentation
│   └── user_guides/           # User guides
└── pyproject.toml             # Package configuration
```

## Development Workflow

### Setting Up Your Environment

```bash
# Activate poetry shell
poetry shell

# Install pre-commit hooks
pre-commit install

# Verify installation
rdf-construct --version
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=rdf_construct --cov-report=html

# Run specific test file
pytest tests/test_ordering.py

# Run specific test
pytest tests/test_ordering.py::test_topological_sort
```

### Code Quality

```bash
# Format code with Black
black src/ tests/

# Lint with Ruff
ruff check src/ tests/

# Fix auto-fixable issues
ruff check --fix src/ tests/

# Type check with mypy
mypy src/

# Run all checks (pre-commit)
pre-commit run --all-files
```

## Coding Standards

### Python Style

- **Formatting**: Black (line length: 100)
- **Linting**: Ruff (replaces flake8, isort, etc.)
- **Type Hints**: Required for all public APIs
- **Docstrings**: Google style

### Example Function

```python
def sort_subjects(
    graph: Graph, subjects: set[URIRef], sort_mode: str, roots_cfg: Optional[list[str]] = None
) -> list[URIRef]:
    """Sort subjects according to the specified mode.

    Supported modes:
    - 'alpha' or 'qname_alpha': Alphabetical by QName
    - 'topological': Topological with optional roots

    Args:
        graph: RDF graph containing the relationships
        subjects: Set of subjects to sort
        sort_mode: Sorting mode identifier
        roots_cfg: Optional list of root CURIEs for topological sorting

    Returns:
        List of URIRefs in the specified order

    Raises:
        ValueError: If sort_mode is invalid
    """
    # Implementation
```

### Type Hints

**Required**:
- Function parameters
- Function return types
- Class attributes

**Use**:
- `Path | str` over `Union[Path, str]` (Python 3.10+)
- `list[T]` over `List[T]`
- `dict[K, V]` over `Dict[K, V]`
- `Optional[T]` for nullable values

### Imports

**Order** (managed by Ruff):
1. Standard library
2. Third-party packages
3. Local imports

**Style**:
```python
from pathlib import Path
from typing import Optional

from rdflib import Graph, URIRef

from .utils import expand_curie
```

## Testing Guidelines

### Test Structure

```python
# tests/test_ordering.py

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDFS

from rdf_construct.core.ordering import topo_sort_subset


def test_simple_hierarchy():
    """Test topological sort on a simple parent-child hierarchy."""
    # Setup
    graph = Graph()
    NS = Namespace("http://example.org/")
    
    animal = NS.Animal
    mammal = NS.Mammal
    dog = NS.Dog
    
    graph.add((mammal, RDFS.subClassOf, animal))
    graph.add((dog, RDFS.subClassOf, mammal))
    
    # Execute
    result = topo_sort_subset(graph, {animal, mammal, dog}, RDFS.subClassOf)
    
    # Assert
    assert result.index(animal) < result.index(mammal)
    assert result.index(mammal) < result.index(dog)
```

### Fixtures

**Shared Test Data**:
```python
# tests/conftest.py

import pytest
from rdflib import Graph

@pytest.fixture
def animal_graph():
    """Load animal ontology for testing."""
    graph = Graph()
    graph.parse("examples/animal_ontology.ttl", format="turtle")
    return graph
```

### Coverage Goals

- **Core modules**: >90% coverage
- **CLI**: >80% coverage
- **Edge cases**: Cycles, empty inputs, invalid data

## Adding New Features

### Process

1. **Discuss**: Open an issue describing the feature
2. **Design**: Consider API, backward compatibility
3. **Implement**: Write code with tests
4. **Document**: Update relevant docs
5. **Review**: Submit PR for review

### Example: Adding a New Selector

1. **Update selector.py**:
```python
def select_subjects(graph, selector_key, selectors):
    # ... existing code ...
    
    elif selector_key == "meta_classes":
        # New selector for metaclasses
        classes = {s for s in graph.subjects(RDF.type, OWL.Class)}
        meta_classes = set()
        for cls in classes:
            if (cls, RDF.type, IES.ClassOfElement) in graph:
                meta_classes.add(cls)
        subjects = meta_classes
```

2. **Add tests**:
```python
def test_meta_class_selector(ies_graph):
    selectors = {"meta_classes": ""}
    result = select_subjects(ies_graph, "meta_classes", selectors)
    assert IES.ClassOfElement in result
```

3. **Update documentation**:
   - User guide: Add example YAML config
   - Dev docs: Document implementation approach

4. **Submit PR** with:
   - Clear description
   - Tests passing
   - Docs updated

## Module-Specific Guidelines

### core/ordering.py

**When to Add**:
- New sorting algorithms
- New hierarchy traversal strategies

**Requirements**:
- Must handle cycles gracefully
- Deterministic output (alphabetical tie-breaking)
- Efficient (O(V + E) preferred)

### uml/mapper.py

**When to Add**:
- New class selection strategies
- New property filtering modes

**Requirements**:
- Clear use case documentation
- Examples in YAML config
- Tests with sample ontologies

### uml/renderer.py

**When to Add**:
- New PlantUML features
- Different diagram types

**Requirements**:
- Valid PlantUML syntax
- Maintain backward compatibility
- Document any PlantUML quirks

## Documentation

### Developer Docs (docs/dev/)

**When to Update**:
- New modules or significant refactoring
- Architecture changes
- Implementation approach changes

**Files**:
- `ARCHITECTURE.md`: System design
- `UML_IMPLEMENTATION.md`: UML technical details
- `CONTRIBUTING.md`: This file

### User Guides (docs/user_guides/)

**When to Update**:
- New CLI commands
- New configuration options
- New examples

**Files**:
- `GETTING_STARTED.md`: Quick start
- `UML_GUIDE.md`: Complete UML features
- `CLI_REFERENCE.md`: Command reference

### Docstrings

**Required For**:
- All public functions
- All classes
- All modules

**Format** (Google Style):
```python
"""Brief description.

Longer description if needed, explaining purpose,
approach, or important details.

Args:
    param1: Description
    param2: Description

Returns:
    Description of return value

Raises:
    ExceptionType: When this exception is raised
"""
```

## Release Process

### Versioning

Follow Semantic Versioning (SemVer):
- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes

### Steps

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md** with changes
3. **Run full test suite**
4. **Build package**: `poetry build`
5. **Test installation**: `pip install dist/*.whl`
6. **Tag release**: `git tag v0.2.0`
7. **Push**: `git push --tags`
8. **Publish**: `poetry publish` (to PyPI)

## Common Tasks

### Adding a New CLI Command

1. **Update cli.py**:
```python
@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--option", help="Description")
def mycommand(source, option):
    """Brief description of command."""
    # Implementation
```

2. **Add tests**:
```python
from click.testing import CliRunner
from rdf_construct.cli import cli

def test_mycommand():
    runner = CliRunner()
    result = runner.invoke(cli, ["mycommand", "test.ttl"])
    assert result.exit_code == 0
```

3. **Update CLI_REFERENCE.md**

### Adding Example Ontologies

1. Create `.ttl` file in `examples/`
2. Add YAML config(s) demonstrating usage
3. Generate output(s) for visual verification
4. Add to `EXAMPLES_SHOWCASE.md`

### Debugging Issues

**Enable verbose logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Inspect RDF graphs**:
```python
from rdflib import Graph

g = Graph()
g.parse("ontology.ttl", format="turtle")

# Print all triples
for s, p, o in g:
    print(f"{s} {p} {o}")

# Check namespace bindings
for pfx, ns in g.namespace_manager.namespaces():
    print(f"{pfx}: {ns}")
```

**Test individual modules**:
```python
from rdf_construct.core.ordering import topo_sort_subset

# Test in isolation
result = topo_sort_subset(graph, subjects, RDFS.subClassOf)
print(result)
```

## Questions?

- **Issues**: https://github.com/aigora-de/rdf-construct/issues
- **Discussions**: https://github.com/aigora-de/rdf-construct/discussions
- **Email**: 23141680+aigora-de@users.noreply.github.com

## Code of Conduct

Be respectful, inclusive, and professional. See CODE_OF_CONDUCT.md.

## License

MIT License. See LICENSE file.