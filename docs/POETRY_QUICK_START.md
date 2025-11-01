# Poetry Quick Start - rdf-construct

## TL;DR - Get Running in 5 Commands

```bash
poetry config virtualenvs.in-project true        # 1. Configure local venv
poetry env use python3.11                        # 2. Set Python version
cp pyproject.toml.poetry pyproject.toml          # 3. Use Poetry config
poetry install                                   # 4. Install everything
poetry shell                                     # 5. Activate environment
```

Then test it:
```bash
rdf-construct --version
pytest
```

---

## Python Version

**Use Python 3.11 or 3.12** (recommended) or **3.10** (minimum).

The code uses Python 3.10+ syntax:
- `Path | str` (union types with `|`)
- `dict[str, str]` (built-in generics)

---

## Full Setup

```bash
# 0. Install Poetry (if needed)
curl -sSL https://install.python-poetry.org | python3 -

# 1. Configure Poetry for local .venv/
poetry config virtualenvs.in-project true

# 2. Navigate to project
cd rdf-construct

# 3. Set Python version
poetry env use python3.11  # or python3.10, python3.12

# 4. Replace pyproject.toml
mv pyproject.toml pyproject.toml.original
cp pyproject.toml.poetry pyproject.toml

# 5. Install dependencies
poetry install

# 6. Activate environment
poetry shell

# 7. Verify
rdf-construct --help
pytest
```

---

## Daily Usage

### Option A: Activate Shell (Recommended)
```bash
poetry shell                    # Activate once
rdf-construct --help            # Use normally
pytest                          # Run commands
exit                            # Deactivate
```

### Option B: Prefix with 'poetry run'
```bash
poetry run rdf-construct --help
poetry run pytest
poetry run mypy src/
```

---

## Common Commands

```bash
# Install dependencies
poetry install

# Add new package
poetry add requests

# Add dev dependency  
poetry add --group dev ipython

# Update dependencies
poetry update

# Show installed packages
poetry show

# Check environment
poetry env info
```

---

## Development Workflow

```bash
poetry shell                              # Activate
vim src/rdf_construct/core/ordering.py   # Edit code
pytest                                    # Test
black src/ tests/                         # Format
ruff check --fix src/                     # Lint
mypy src/                                 # Type check
git commit -m "Add feature"               # Commit (pre-commit runs)
```

---

## Pre-commit Hooks

```bash
poetry run pre-commit install            # Install hooks
poetry run pre-commit run --all-files    # Run manually
```

On each commit, automatically runs:
- Black (formatting)
- Ruff (linting)
- MyPy (type checking)
- YAML/TOML validation

---

## Publishing

```bash
poetry build           # Create wheel and sdist
poetry publish         # Publish to PyPI
# or
poetry publish --build # Both at once
```

---

## Troubleshooting

**Can't find Python 3.11?**
```bash
poetry env use /usr/local/bin/python3.11  # Full path
```

**Lock file issues?**
```bash
poetry lock            # Regenerate
poetry install         # Reinstall
```

**.venv not in project?**
```bash
poetry config virtualenvs.in-project true
rm -rf $(poetry env info --path)
poetry install
```

**Import errors?**
```bash
poetry install         # Reinstall
poetry run python -c "import rdf_construct; print('OK')"
```

---

## File Changes

### Replace
- `pyproject.toml` → Use `pyproject.toml.poetry`

### Created by Poetry
- `poetry.lock` - Lock file (commit to git)
- `.venv/` - Virtual environment (add to .gitignore)

### No Changes Needed
- All Python source code
- Tests
- Examples
- Tool configs (Black, Ruff, MyPy)

---

## What's Different?

| Before (pip) | After (Poetry) |
|--------------|----------------|
| `python -m venv venv` | `poetry install` |
| `source venv/bin/activate` | `poetry shell` |
| `pip install -e ".[dev]"` | `poetry install` |
| `pip install requests` | `poetry add requests` |
| Manual version management | `poetry.lock` |

---

## Verification

✅ Everything works if:
```bash
poetry run rdf-construct --version     # Shows 0.1.0
poetry run pytest                      # Tests pass
poetry run mypy src/                   # Type check passes
poetry show rdflib                     # Shows installed version
ls .venv/                              # Venv exists (with in-project config)
```

---

## Next Steps

1. ✅ Set up Poetry (done above)
2. ⏭️ Update placeholders in pyproject.toml (name, email, GitHub URL)
3. ⏭️ Expand test coverage
4. ⏭️ Implement missing YAML features
5. ⏭️ Publish to PyPI

---

## Help

- **Full guide**: See `POETRY_SETUP.md`
- **Migration details**: See `POETRY_MIGRATION.md`
- **Poetry docs**: https://python-poetry.org/docs/

---

## Summary

1. **Use Python 3.11** (or 3.10+)
2. **Configure local venv**: `poetry config virtualenvs.in-project true`
3. **Replace pyproject.toml** with Poetry version
4. **Install**: `poetry install`
5. **Activate**: `poetry shell`
6. **Code!** Everything works exactly the same

Your `.venv/` will be in the project directory, making it clear which environment you're using.