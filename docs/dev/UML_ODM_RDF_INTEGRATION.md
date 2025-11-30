# ODM Rendering Mode Integration

## Files to Add/Update

### New Files

1. **`src/rdf_construct/uml/odm_renderer.py`**
   
   The main ODM-compliant renderer module. Copy `odm_renderer.py` to your `src/rdf_construct/uml/` directory.

2. **`docs/user_guides/ODM_MODE.md`**
   
   User documentation for the ODM rendering mode. Copy `docs_ODM_MODE.md` to `docs/user_guides/`.

3. **`tests/test_odm_renderer.py`**
   
   Test suite for the ODM renderer. Copy `tests_test_odm_renderer.py` to `tests/`.

### Updated Files

1. **`src/rdf_construct/cli.py`**
   
   Replace with the new `cli.py` which adds:
   - `--rendering-mode` / `-r` option with choices `default` and `odm`
   - Import for `render_odm_plantuml`
   - Conditional rendering based on mode

2. **`src/rdf_construct/uml/__init__.py`**
   
   Add the ODM renderer to exports:
   ```python
   from .odm_renderer import ODMRenderer, render_odm_plantuml
   
   __all__ = [
       # ... existing exports ...
       "ODMRenderer",
       "render_odm_plantuml",
   ]
   ```

## Installation Steps

```bash
# 1. Copy new files
cp odm_renderer.py src/rdf_construct/uml/
cp docs_ODM_MODE.md docs/user_guides/ODM_MODE.md
cp tests_test_odm_renderer.py tests/test_odm_renderer.py

# 2. Replace CLI
cp cli.py src/rdf_construct/cli.py

# 3. Update __init__.py (manually add imports)

# 4. Run tests
poetry run pytest tests/test_odm_renderer.py -v

# 5. Test CLI
poetry run rdf-construct uml --help
```

## Usage Examples

```bash
# Default mode (unchanged behaviour)
poetry run rdf-construct uml ontology.ttl contexts.yml

# ODM mode
poetry run rdf-construct uml ontology.ttl contexts.yml --rendering-mode odm
poetry run rdf-construct uml ontology.ttl contexts.yml -r odm

# ODM mode with IES colour palette (full scheme)
poetry run rdf-construct uml building.ttl contexts.yml -r odm \
    --style-config examples/ies_colour_palette.yml --style ies_full \
    --layout-config examples/uml_layouts.yml --layout hierarchy

# ODM mode with IES core colours
poetry run rdf-construct uml ontology.ttl contexts.yml -r odm \
    --style-config examples/ies_colour_palette.yml --style ies_core

# ODM mode with metaclass-focused IES scheme
poetry run rdf-construct uml ontology.ttl contexts.yml -r odm \
    --style-config examples/ies_colour_palette.yml --style ies_metaclass
```

## IES Colour Palette Support

The ODM renderer fully supports the IES colour palette, including:

- **Class colours**: Entity (yellow), State (gold), Event (pink), etc.
- **Metaclass colours**: ClassOfElement, ClassOfEntity (cyan tones)
- **Instance styling**: Black fill with text colour inherited from class hierarchy
- **Property styling**: Grey for ObjectProperty and DatatypeProperty
- **Arrow colours**: Configurable colours for rdf:type relationships

## Output Differences

### Default Mode Output
```plantuml
class building.Structure << (C, #FFFFFF) owl:Class >> #back:FEFE54;line:968584
building.Structure -u-|> ies.Entity : <<rdfs:subClassOf>>
```

### ODM Mode Output
```plantuml
class building.Structure <<owlClass>> #back:FEFE54;line:968584
building.Structure -u-|> ies.Entity
```

## Key Features

1. **Standard ODM stereotypes**: `<<owlClass>>`, `<<objectProperty>>`, `<<individual>>`, etc.

2. **Property characteristics**: Functional, symmetric, transitive properties shown in stereotype

3. **Cleaner relationship labels**: Uses `<<rdfsDomain>>`, `<<rdfsRange>>`, `<<rdfType>>`

4. **Full styling support**: Works with existing colour palettes and layouts

5. **Backward compatible**: Default mode unchanged; ODM is opt-in via `--rendering-mode odm`