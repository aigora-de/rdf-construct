# Localise Guide

The `localise` command helps manage translations in RDF ontologies. It provides tools to extract translatable strings, merge completed translations, and track translation coverage across languages.

## Overview

Standards like IES require labels in multiple languages. The localise workflow makes this manageable:

1. **Extract** translatable strings to YAML files for translators
2. **Translate** the YAML files (manually or with translation tools)
3. **Merge** completed translations back into the ontology
4. **Report** on translation coverage to track progress

## Quick Start

```bash
# Extract strings for German translation
rdf-construct localise extract ontology.ttl --language de -o translations/de.yml

# Send de.yml to translator, then merge when complete
rdf-construct localise merge ontology.ttl translations/de.yml -o localised.ttl

# Check coverage across languages
rdf-construct localise report ontology.ttl --languages en,de,fr
```

## Commands

### `localise extract`

Extracts translatable strings from an ontology into a YAML file ready for translation.

```bash
# Basic extraction
rdf-construct localise extract ontology.ttl --language de -o de.yml

# Extract specific properties only
rdf-construct localise extract ontology.ttl -l de \
    -p rdfs:label,rdfs:comment -o de.yml

# Extract only missing translations (for updates)
rdf-construct localise extract ontology.ttl -l de --missing-only -o de_update.yml

# Include deprecated entities
rdf-construct localise extract ontology.ttl -l de --include-deprecated -o de.yml
```

#### Options

| Option | Description |
|--------|-------------|
| `--language, -l` | Target language code (required) |
| `--output, -o` | Output YAML file (default: `{language}.yml`) |
| `--source-language` | Source language (default: `en`) |
| `--properties, -p` | Comma-separated properties to extract |
| `--include-deprecated` | Include deprecated entities |
| `--missing-only` | Only extract strings without target translations |
| `--config, -c` | YAML configuration file |

#### Default Properties

By default, these properties are extracted:

- `rdfs:label`
- `rdfs:comment`
- `skos:prefLabel`
- `skos:definition`

### `localise merge`

Merges completed translation files back into an ontology, adding new language-tagged literals.

```bash
# Merge single file
rdf-construct localise merge ontology.ttl de.yml -o localised.ttl

# Merge multiple languages
rdf-construct localise merge ontology.ttl translations/*.yml -o multilingual.ttl

# Merge only approved translations
rdf-construct localise merge ontology.ttl de.yml --status approved -o localised.ttl

# Preview without writing (dry run)
rdf-construct localise merge ontology.ttl de.yml -o test.ttl --dry-run
```

#### Options

| Option | Description |
|--------|-------------|
| `--output, -o` | Output file (required) |
| `--status` | Minimum status to include: `pending`, `needs_review`, `translated`, `approved` |
| `--existing` | How to handle existing translations: `preserve` or `overwrite` |
| `--dry-run` | Show what would happen without writing |
| `--no-colour` | Disable coloured output |

#### Status Filtering

Translations have a status field that tracks their progress:

- `pending` - Not yet translated
- `needs_review` - Translated but uncertain
- `translated` - Translation complete
- `approved` - Reviewed and approved

By default, only `translated` and `approved` entries are merged. Use `--status pending` to include all entries.

### `localise report`

Generates a translation coverage report showing what percentage of content has been translated.

```bash
# Basic report
rdf-construct localise report ontology.ttl --languages en,de,fr

# Detailed report with missing entities
rdf-construct localise report ontology.ttl -l en,de,fr --verbose

# Markdown report to file
rdf-construct localise report ontology.ttl -l en,de,fr -f markdown -o coverage.md

# Check specific properties
rdf-construct localise report ontology.ttl -l en,de -p rdfs:label
```

#### Options

| Option | Description |
|--------|-------------|
| `--languages, -l` | Comma-separated language codes (required) |
| `--source-language` | Base language (default: `en`) |
| `--properties, -p` | Comma-separated properties to check |
| `--output, -o` | Output file for report |
| `--format, -f` | Output format: `text` or `markdown` |
| `--verbose, -v` | Show detailed missing translation list |
| `--no-colour` | Disable coloured output |

#### Example Output

```
Translation Coverage Report
========================================

Source: ontology.ttl
Entities: 57
Properties: rdfs:label, rdfs:comment

Language    rdfs:label  rdfs:comment  Overall  Status
--------    ----------  ------------  -------  ------
en (base)   100%        89%           94%      ✓ Complete
de          92%         45%           68%      ⚠ 14 pending
fr          78%         12%           45%      ⚠ 58 pending
es          0%          0%            0%       ✗ Not started
```

### `localise init`

Creates an empty translation file for a new language. This is equivalent to `extract` but emphasises starting fresh.

```bash
rdf-construct localise init ontology.ttl --language ja -o translations/ja.yml
```

### `localise config`

Generates a default configuration file for localisation workflows.

```bash
rdf-construct localise config --init
```

## Translation File Format

The YAML translation file format is designed to be:

- **Readable** - Clear structure for translators
- **Editable** - Easy to fill in with a text editor
- **Trackable** - Status field for progress tracking

### Example Translation File

```yaml
# =============================================================================
# Translation File
# =============================================================================
# Source: ontology.ttl
# Source language: en
# Target language: de
# Generated: 2025-01-15T10:30:00
#
# Instructions:
# 1. Fill in the 'translation' field for each entry
# 2. Set 'status' to 'translated' when complete
# 3. Use 'needs_review' if uncertain about translation
# 4. Leave 'status' as 'pending' for incomplete entries
# =============================================================================

metadata:
  source_file: ontology.ttl
  source_language: en
  target_language: de
  generated: 2025-01-15T10:30:00
  tool: rdf-construct localise
  properties:
    - rdfs:label
    - rdfs:comment

entities:
  - uri: "http://example.org/ont#Building"
    type: owl:Class
    labels:
      - property: rdfs:label
        source: "Building"
        translation: "Gebäude"
        status: translated

      - property: rdfs:comment
        source: "A permanent structure with walls and roof."
        translation: "Ein dauerhaftes Bauwerk mit Wänden und Dach."
        status: translated

  - uri: "http://example.org/ont#SmartBuilding"
    type: owl:Class
    labels:
      - property: rdfs:label
        source: "Smart Building"
        translation: ""
        status: pending

      - property: rdfs:comment
        source: "A building with automated systems."
        translation: ""
        status: pending
        notes: "Consider: 'intelligentes Gebäude' or 'Smart Building'"

summary:
  total_entities: 2
  total_strings: 4
  by_status:
    translated: 2
    pending: 2
  coverage: "50.0%"
```

### Translation Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Not yet translated |
| `needs_review` | Translation needs verification |
| `translated` | Translation complete |
| `approved` | Reviewed and confirmed |

### Notes Field

Add the optional `notes` field to include guidance for translators:

```yaml
- property: rdfs:label
  source: "Smart Building"
  translation: ""
  status: pending
  notes: "Technical term - consider keeping English or using 'intelligentes Gebäude'"
```

## Configuration File

For complex workflows, use a YAML configuration file:

```yaml
# localise.yml
localise:
  # Properties to extract (in display order)
  properties:
    - rdfs:label
    - skos:prefLabel
    - rdfs:comment
    - skos:definition
    - skos:altLabel

  # Language configuration
  languages:
    source: en
    targets:
      - de
      - fr
      - es

  # Output settings
  output:
    directory: translations/
    naming: "{language}.yml"

  # Extraction options
  extract:
    include_unlabelled: false
    include_deprecated: false

  # Merge options
  merge:
    existing: preserve      # preserve | overwrite
    min_status: translated  # pending | needs_review | translated | approved
```

Use the config file:

```bash
rdf-construct localise extract ontology.ttl -l de -c localise.yml
```

## Workflow Examples

### Complete Translation Workflow

```bash
# 1. Set up directory structure
mkdir -p translations

# 2. Extract for all target languages
for lang in de fr es; do
    rdf-construct localise extract ontology.ttl -l $lang -o translations/$lang.yml
done

# 3. Check initial coverage
rdf-construct localise report ontology.ttl -l en,de,fr,es

# 4. After translations are complete, merge them
rdf-construct localise merge ontology.ttl translations/*.yml -o ontology_multilingual.ttl

# 5. Verify final coverage
rdf-construct localise report ontology_multilingual.ttl -l en,de,fr,es
```

### Incremental Translation Updates

When the source ontology changes, extract only new strings:

```bash
# Extract only missing translations
rdf-construct localise extract ontology.ttl -l de --missing-only -o translations/de_new.yml

# Translator fills in de_new.yml, then merge
rdf-construct localise merge ontology.ttl translations/de_new.yml -o ontology.ttl
```

### Quality-Controlled Workflow

Use the status field for a review workflow:

```bash
# Translator marks entries as 'translated'
# Reviewer marks approved entries as 'approved'

# First merge: only approved translations
rdf-construct localise merge ontology.ttl de.yml --status approved -o stable.ttl

# Later: include all translations for testing
rdf-construct localise merge ontology.ttl de.yml --status translated -o beta.ttl
```

## Best Practices

### 1. Version Control Translation Files

Keep translation YAML files in version control alongside your ontology. This provides:
- History of translation changes
- Easy collaboration with multiple translators
- Ability to revert problematic translations

### 2. Use Meaningful Status Values

- Mark uncertain translations as `needs_review`
- Only mark as `translated` when confident
- Use `approved` for reviewed translations in production workflows

### 3. Document Special Terms

Use the `notes` field to explain:
- Technical terms that should remain in English
- Multiple valid translations
- Context-specific meanings

### 4. Regular Coverage Reports

Generate coverage reports before releases:

```bash
rdf-construct localise report ontology.ttl -l en,de,fr \
    -f markdown -o docs/translation_coverage.md
```

### 5. Handle Untagged Literals

The extractor treats literals without language tags as the source language. If your ontology uses untagged English literals, they will be extracted for translation.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Success with warnings (some translations skipped) |
| 2 | Error (file not found, invalid format) |

## Related Commands

- `rdf-construct lint` - Check for missing labels (undocumented entities)
- `rdf-construct docs` - Generate documentation including all language labels
- `rdf-construct diff` - Compare ontology versions (including label changes)
