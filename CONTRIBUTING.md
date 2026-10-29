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
6. **Run the checks**: `scripts/ci-local.sh` — see [the pre-PR ritual](#scriptsci-localsh--the-pre-pr-ritual)
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
pre-commit install

# Let `git blame` skip the repo-wide formatting sweep (once per clone)
git config blame.ignoreRevsFile .git-blame-ignore-revs

# Make changes
git checkout -b dev/my-feature

# Check everything before opening a PR — this is the one command that matters
scripts/ci-local.sh

# Commit and push
git add .
git commit -m "feat(core): clear description of changes"
git push origin dev/my-feature
```

### `scripts/ci-local.sh` — the pre-PR ritual

**There is no hosted CI.** Nothing runs on push or on a pull request, so `scripts/ci-local.sh` is
the gate. It runs every check, reports them all, and fails only if a *gate* step failed:

| Step | Severity |
|---|---|
| test suite (`pytest`) | **gate** |
| version consistency (`pyproject.toml` vs `__init__.py`) | **gate** |
| instruction/memory size guard | **gate** |
| `black --check` | **gate** |
| `ruff check` | advisory |
| `mypy --strict` | advisory |

The two advisory steps carry substantial pre-existing debt across the repository — see
[#78](https://github.com/aigora-de/rdf-construct/issues/78) and
[#79](https://github.com/aigora-de/rdf-construct/issues/79). **Keep the files your change touches
clean; you are not expected to fix the rest.** Each becomes a gate as its debt reaches zero, as
black did in [#77](https://github.com/aigora-de/rdf-construct/issues/77).

Useful variants: `--tests-only` (the fast gate alone), `--lint-only` (everything else), and
`CI_LOCAL_PYRUN=""` if you are already inside an activated virtualenv.

The pre-commit hooks (`pre-commit install`) are a lighter, separate thing: file hygiene plus
`black`. Because the repository is black-clean, the hook only ever reformats the file you are
already editing. `ruff` and `mypy` are deliberately **not** commit hooks — against their current
debt the first rewrote files far beyond the change being committed, and mypy refused the commit
outright.

If the black gate fails, `poetry run black .` fixes it; the usual cause is not having run
`pre-commit install`.

## Pull Request Process

1. Run `scripts/ci-local.sh` and ensure the gate is green
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

**`scripts/release.sh` runs the release**, as `scripts/ci-local.sh` runs the pre-PR checks.

Prepare the release by hand — these are judgement calls, so the script checks them rather than
making them:

1. Bump the version in `pyproject.toml` **and** `src/rdf_construct/__init__.py`, following
   [SemVer](https://semver.org/): MAJOR for breaking changes, MINOR for backward-compatible
   features, PATCH for backward-compatible fixes
2. Date the CHANGELOG entry, empty `[Unreleased]`, add the version's `compare/…` link to the
   footer, and move the `[Unreleased]` link on to the new version
3. Update the version where prose states it — `README.md` and `CLAUDE.md`

Then:

```bash
scripts/release.sh --check   # changes nothing; tells you what is not ready
scripts/release.sh           # clean build, verify the wheel, tag, push, dry run
poetry publish               # yours to run — see below
scripts/release.sh --post    # GitHub release from the CHANGELOG, close the milestone
```

The script refuses rather than assists: every check names what to fix and it never edits a file
to make itself pass. It also stops short of publishing. **A version can never be replaced on
PyPI once uploaded**, so that one command stays deliberate and human.

It builds *before* it tags, and tags the exact commit it built. A pushed tag cannot be quietly
retracted once anyone has fetched it, so nothing reaches origin until the artefact exists and has
been proven to work.

`--check` verifies: `main`, clean, in sync; the `ci-local.sh` gate; that the version agrees across
`pyproject.toml`, `__init__.py`, `CHANGELOG.md`, `README.md` and `CLAUDE.md`; that the CHANGELOG's
top entry is dated and `[Unreleased]` is empty; and that the tag does not already exist. After
building it installs the wheel into a throwaway virtualenv and asks it for `--version`, because a
non-editable install is where a version read from package metadata goes wrong ([#66]).

There is **no hosted release automation** — `.github/workflows/` is empty, so nothing runs on push
or on tag. The script is local, like every other gate here.

[#66]: https://github.com/aigora-de/rdf-construct/issues/66

## Ownership, Licensing, and AI Tools

**Using an LLM or AI coding assistant is fine, and you do not need to hide it.** They are used in
this project's own development. Whether you mention your use of one in a PR is entirely your
choice.

What *is* binding is ownership and licensing, and it is the same whether or not a tool was
involved:

- Contributions are licensed to the project under the **MIT Licence** (see the section below).
- Copyright and ownership of the codebase rest with **Dave Dyke / Agilit Ltd**. No AI tool, model
  or vendor is named as an author, co-author or originator of anything in the repository — not in
  copyright headers, and not in commit or PR metadata.
- Practically, this means **no AI-attribution boilerplate in commits or PRs**: no
  `Co-Authored-By: Claude …` trailer, no "🤖 Generated with …" footer. Some assistants add these
  automatically — please strip them before pushing. You remain the author of your contribution.

If you want to describe how you built something, the PR description is the right place; it is
content, not attribution metadata.

## Questions?

Open an issue with the `question` label or start a discussion.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
