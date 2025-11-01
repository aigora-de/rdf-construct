# Contributing to rdf-construct

Thank you for considering contributing to rdf-construct! We welcome contributions of all kinds.

## Code of Conduct

Be respectful, constructive, and professional. We're all here to build better RDF tools.

## How to Contribute

### Reporting Issues

- Check existing issues first to avoid duplicates
- Provide clear reproduction steps
- Include Python version, OS, and rdflib version
- Attach sample RDF files if relevant (anonymized if needed)

### Suggesting Features

- Open an issue with the `enhancement` label
- Explain the use case and expected behavior
- Consider backward compatibility implications

### Contributing Code

1. **Fork and clone** the repository
2. **Create a branch** for your feature/fix: `git checkout -b feature-name`
3. **Install dev dependencies**: `pip install -e ".[dev]"`
4. **Make your changes** following the code standards below
5. **Add tests** for new functionality
6. **Run the test suite**: `pytest`
7. **Format your code**: `black src/ tests/`
8. **Lint**: `ruff check src/ tests/`
9. **Commit** with clear, descriptive messages
10. **Push** and create a pull request

## Code Standards

### Style

- **Black** formatting (line length: 100)
- **Ruff** linting
- **Type hints** for all functions (Python 3.10+ syntax)
- **Docstrings** (Google style) for public functions and classes

Example:

```python
def example_function(graph: Graph, subjects: set[URIRef]) -> list[URIRef]:
    """Brief description of what this does.
    
    More detailed explanation if needed.
    
    Args:
        graph: RDF graph containing the data
        subjects: Set of subject URIRefs to process
        
    Returns:
        List of processed URIRefs in desired order
        
    Raises:
        ValueError: If subjects set is empty
    """
    if not subjects:
        raise ValueError("subjects cannot be empty")
    return sorted(subjects)
```

### Testing

- Write tests for new functionality
- Aim for >80% coverage
- Use descriptive test names: `test_topo_sort_respects_hierarchy`
- Use fixtures for common test data
- Test edge cases (empty sets, cycles, etc.)

### Commits

Write clear commit messages:

```
Add topological sorting for properties

- Implement sort_with_roots() for property hierarchies
- Handle rdfs:subPropertyOf relationships
- Add tests for edge cases with disconnected properties
```

### Documentation

- Update README.md if adding user-facing features
- Add docstrings to new functions/classes
- Include examples in docstrings for complex functionality
- Update CHANGELOG.md following [Keep a Changelog](https://keepachangelog.com/)

## Development Workflow

```bash
# Setup
git clone https://github.com/yourusername/rdf-construct.git
cd rdf-construct
pip install -e ".[dev]"

# Make changes
git checkout -b my-feature

# Test
pytest
pytest --cov=rdf_construct --cov-report=html  # with coverage

# Format
black src/ tests/
ruff check --fix src/ tests/

# Type check
mypy src/

# Commit and push
git add .
git commit -m "Clear description of changes"
git push origin my-feature
```

## Pull Request Process

1. Ensure all tests pass
2. Update documentation as needed
3. Add entry to CHANGELOG.md under "Unreleased"
4. Reference related issues in the PR description
5. Wait for review - maintainers will provide feedback
6. Make requested changes if needed
7. Once approved, maintainers will merge

## Release Process

(For maintainers)

1. Update version in `pyproject.toml` and `src/rdf_construct/__init__.py`
2. Update CHANGELOG.md with release date
3. Create git tag: `git tag -a v0.2.0 -m "Release 0.2.0"`
4. Push tag: `git push origin v0.2.0`
5. GitHub Actions will automatically publish to PyPI

## Questions?

Open an issue with the `question` label or start a discussion.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.