# Poetry Setup Guide for rdf-construct

## Prerequisites

1. **Python 3.10, 3.11, or 3.12 installed**
   ```bash
   python3.11 --version  # Check version
   ```

2. **Poetry installed**
   ```bash
   # Install Poetry if you haven't
   curl -sSL https://install.python-poetry.org | python3 -
   
   # Or with pip (not recommended, but works)
   pip install poetry
   
   # Verify installation
   poetry --version
   ```

## Quick Start

### 1. Set Up Project

```bash
# Navigate to your project directory
cd rdf-construct

# Configure Poetry to create venv in project directory (.venv/)
poetry config virtualenvs.in-project true

# Use specific Python version
poetry env use python3.11  # or python3.10, python3.12

# Replace the existing pyproject.toml with the Poetry version
cp pyproject.toml.poetry pyproject.toml

# Install all dependencies (creates .venv/ automatically)
poetry install

# Check the virtual environment
poetry env info
```

### 2. Activate and Use

```bash
# Option A: Activate the virtual environment
poetry shell
rdf-construct --help
pytest

# Option B: Run commands without activating (prefixed with 'poetry run')
poetry run rdf-construct --help
poetry run pytest
poetry run mypy src/
```

### 3. Verify Everything Works

```bash
# Activate environment
poetry shell

# Test CLI
rdf-construct --version
rdf-construct profiles examples/sample_profile.yml

# Run tests
pytest

# Type check
mypy src/

# Format code
black src/ tests/

# Lint
ruff check src/ tests/
```

## Common Poetry Commands

### Dependency Management

```bash
# Add a new dependency
poetry add requests

# Add a dev dependency
poetry add --group dev pytest-asyncio

# Update dependencies
poetry update

# Show installed packages
poetry show

# Show dependency tree
poetry show --tree
```

### Environment Management

```bash
# Show venv info
poetry env info

# List all venvs for this project
poetry env list

# Remove current venv
poetry env remove python3.11

# Create fresh venv
poetry install
```

### Development Workflow

```bash
# Install with all groups (including dev)
poetry install

# Install without dev dependencies (for production)
poetry install --without dev

# Update lock file without installing
poetry lock --no-update

# Show outdated packages
poetry show --outdated
```

### Running Commands

```bash
# Inside activated shell
poetry shell
rdf-construct order ontology.ttl config.yml

# Without activating
poetry run rdf-construct order ontology.ttl config.yml

# Run tests with coverage
poetry run pytest --cov=rdf_construct --cov-report=html

# Format and lint
poetry run black src/ tests/
poetry run ruff check --fix src/ tests/
poetry run mypy src/
```

## Project Structure with Poetry

```
rdf-construct/
├── .venv/                      # Virtual environment (created by Poetry)
├── src/
│   └── rdf_construct/         # Your package code
├── tests/                      # Tests
├── examples/                   # Examples
├── pyproject.toml             # Poetry config (use pyproject.toml.poetry)
├── poetry.lock                # Lock file (created by Poetry)
└── README.md
```

## Key Differences from pip/venv

| Task | pip/venv | Poetry |
|------|----------|--------|
| Create venv | `python -m venv venv` | `poetry install` (automatic) |
| Activate | `source venv/bin/activate` | `poetry shell` |
| Install package | `pip install -e .` | `poetry install` |
| Add dependency | Edit pyproject.toml, `pip install` | `poetry add package` |
| Run command | `python script.py` | `poetry run python script.py` |
| Install dev deps | `pip install -e ".[dev]"` | `poetry install` (includes dev) |

## Poetry Configuration

### Useful Settings

```bash
# Create .venv in project directory (recommended)
poetry config virtualenvs.in-project true

# Don't create venv (if using system Python)
poetry config virtualenvs.create false

# Show current config
poetry config --list
```

## Pre-commit with Poetry

```bash
# Install pre-commit hooks
poetry run pre-commit install

# Run hooks manually
poetry run pre-commit run --all-files

# Update hook versions
poetry run pre-commit autoupdate
```

## Publishing to PyPI

When ready to publish:

```bash
# Build package
poetry build

# Publish to PyPI (requires API token)
poetry publish

# Or do both at once
poetry publish --build

# Publish to TestPyPI first (recommended)
poetry config repositories.testpypi https://test.pypi.org/legacy/
poetry publish -r testpypi --build
```

## Troubleshooting

### Poetry can't find Python 3.11

```bash
# Use full path to Python
poetry env use /usr/local/bin/python3.11

# Or use pyenv
pyenv install 3.11.7
poetry env use 3.11.7
```

### Lock file out of sync

```bash
# Regenerate lock file
poetry lock

# Install from updated lock
poetry install
```

### .venv not in project directory

```bash
# Set config and recreate
poetry config virtualenvs.in-project true
poetry env remove python3.11
poetry install
```

### Import errors after install

```bash
# Make sure package is installed
poetry install

# Check it's in the right place
poetry run python -c "import rdf_construct; print(rdf_construct.__file__)"

# Try reinstalling
poetry env remove python3.11
poetry install
```

## Development Workflow Example

```bash
# 1. Morning setup
cd rdf-construct
poetry shell  # Activate venv

# 2. Make changes to code
vim src/rdf_construct/core/ordering.py

# 3. Run tests
pytest

# 4. Format and lint (pre-commit does this automatically on commit)
black src/
ruff check --fix src/

# 5. Type check
mypy src/

# 6. Test CLI
rdf-construct order examples/sample.ttl examples/config.yml

# 7. Commit (pre-commit hooks run automatically)
git add .
git commit -m "Add feature X"
```

## Updating Dependencies

```bash
# Update all dependencies to latest compatible versions
poetry update

# Update specific package
poetry update rdflib

# Update and regenerate lock file
poetry update --lock

# Show what would be updated (dry run)
poetry update --dry-run
```

## Comparison: Before and After

### Before (pip)
```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
pip list
```

### After (Poetry)
```bash
poetry install
poetry shell
poetry show
```

Much cleaner! Poetry handles:
- Virtual environment creation
- Dependency resolution
- Lock files for reproducibility
- Dev/prod dependency separation
- Publishing to PyPI

## Next Steps

1. **Replace pyproject.toml**: `mv pyproject.toml.poetry pyproject.toml`
2. **Install**: `poetry install`
3. **Activate**: `poetry shell`
4. **Test**: `rdf-construct --help`
5. **Develop**: Start coding!

## Additional Resources

- Poetry docs: https://python-poetry.org/docs/
- Poetry commands: https://python-poetry.org/docs/cli/
- Dependency specification: https://python-poetry.org/docs/dependency-specification/