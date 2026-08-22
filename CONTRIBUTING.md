# Contributing to rdf-construct

Thank you for considering contributing to rdf-construct! We welcome contributions of all kinds.

## Code of Conduct

Be respectful, constructive, and professional. We're all here to build better RDF tools.

## How to Contribute

### Reporting Issues

- Check existing issues first to avoid duplicates
- Provide clear reproduction steps
- Include Python version, OS, and rdflib version
- Attach sample RDF files if relevant (anonymised if needed)

### Suggesting Features

- Open an issue with the `enhancement` label
- Explain the use case and expected behaviour
- Consider backward compatibility implications

### Labels and Milestones

A minimal label set: `bug`, `enhancement`, `documentation`, `question`, `chore`,
`good-first-issue`, `backlog`. Add `breaking-change` when a change affects the public API.

Milestones group related issues into a release. A feature developed across several issues and PRs
shares one milestone (e.g. `v0.5.0 - Entity-type taxonomy in docs`), which makes it clear what is
required before that release is ready.

### Contributing Code

1. **Fork and clone** the repository
2. **Create a branch** for your feature/fix — see [Branches](#branches) for the naming convention
3. **Install dependencies**: `poetry install --with dev`
4. **Make your changes** following the code standards below
5. **Add tests** for new functionality
6. **Run the test suite**: `poetry run pytest`
7. **Format your code**: `poetry run black src/ tests/`
8. **Lint**: `poetry run ruff check src/ tests/`
9. **Commit** with clear, descriptive messages — see [Commits](#commits)
10. **Push** and create a pull request

### Branches

`<type>/<short-description>` or `<type>/<description>-<issue-number>`, in kebab-case.

| Type | Purpose | Example |
|------|---------|---------|
| `main` | Stable, release-ready code | — |
| `dev/*` | Feature development | `dev/shacl-generation`, `dev/merge-tool-23` |
| `fix/*` | Bug fixes | `fix/blank-node-handling`, `fix/cli-crash-45` |
| `refactor/*` | Code restructuring (no new features) | `refactor/serializer-module` |
| `docs/*` | Documentation only | `docs/cli-reference` |
| `chore/*` | Tooling, process, repo hygiene | `chore/routed-memories-73` |
| `experiment/*` | Exploratory work (may be discarded) | `experiment/sparql-support` |

`main` is always deployable — never commit directly to it except for trivial fixes. Branch from
`main`, and delete the branch once it is merged.

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

[Conventional Commits](https://www.conventionalcommits.org/) style:

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

| Type | When to use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or updating tests |
| `chore` | Build, config, tooling changes |
| `style` | Formatting, whitespace (no logic change) |
| `perf` | Performance improvement |

**Scope** is optional and names the area affected (`cli`, `serialiser`, `shacl`, `merge`, `uml`).

**Subject:** imperative mood ("add", not "added" or "adds"), lowercase first letter, no full stop,
around 50 characters.

**Body:** use it when the subject alone is not enough. Explain *what* and *why*, not *how* — the
code shows how.

**Footer:** reference issues (`Closes #42`, `Fixes #17`) or note breaking changes
(`BREAKING CHANGE: description`).

```
feat(cli): add --format option to order command
fix(serialiser): handle blank nodes in property ranges
docs: update CLI reference with merge examples
refactor(core): extract triple sorting into separate module
test(shacl): add coverage for circular dependencies
chore: bump rdflib to 7.0.0
feat!: rename --output to --out (breaking change)
```

### Documentation

- Update README.md if adding user-facing features
- Add docstrings to new functions/classes
- Include examples in docstrings for complex functionality
- Update CHANGELOG.md following [Keep a Changelog](https://keepachangelog.com/)

## Development Workflow

```bash
# Setup
git clone https://github.com/aigora-de/rdf-construct.git
cd rdf-construct
poetry install --with dev

# Make changes
git checkout -b dev/my-feature

# Test
poetry run pytest
poetry run pytest --cov=rdf_construct --cov-report=html  # with coverage

# Format
poetry run black src/ tests/
poetry run ruff check --fix src/ tests/

# Type check
poetry run mypy src/

# Commit and push
git add .
git commit -m "feat(core): clear description of changes"
git push origin dev/my-feature
```

**A note on the current state of the checks:** the test suite is green, but `black`, `ruff` and
`mypy --strict` all carry substantial pre-existing debt across the repository. Keep *your* changed
files clean; you are not expected to fix the rest. See
[#74](https://github.com/aigora-de/rdf-construct/issues/74), which tracks a local CI runner and the
debt behind each check.

## Pull Request Process

1. Ensure all tests pass
2. Update documentation as needed
3. Add entry to CHANGELOG.md under "Unreleased"
4. Reference related issues in the PR description
5. Wait for review - maintainers will provide feedback
6. Make requested changes if needed
7. Once approved, maintainers will merge

**PR title:** should read as a changelog entry — clear, imperative, concise.

**PR description:** the repository template
(`.github/PULL_REQUEST_TEMPLATE.md`) covers summary, related issues, changes, testing and breaking
changes. Fill it in rather than replacing it.

## Release Process

(For maintainers)

Not every merged PR triggers a release. Cut one when a milestone is complete, when a significant
bug fix needs to reach users, when smaller improvements have accumulated, or immediately for a
security fix. Partial features are not released.

1. Ensure `main` is stable and the test suite passes
2. Update version in `pyproject.toml` **and** `src/rdf_construct/__init__.py` — they must match
3. Update CHANGELOG.md with the release notes and date, following
   [SemVer](https://semver.org/): MAJOR for breaking changes, MINOR for backward-compatible
   features, PATCH for backward-compatible fixes
4. Create an annotated git tag: `git tag -a v0.5.0 -m "Release v0.5.0"`
5. Push the tag: `git push origin v0.5.0`
6. Build and publish: `poetry build && poetry publish`

There is **no release automation** — `.github/workflows/` is empty, so nothing runs on push or on
tag. Publishing is a manual step today.

## Questions?

Open an issue with the `question` label or start a discussion.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.