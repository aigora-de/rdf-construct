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

## Language Tags and Which Terms Are Translated

These rules are the same in `extract`, `merge` and `report`.

**`-l` and `--source-language` take a language tag, not a range.** Tags are compared without regard
to case, so `-l en-gb`, `-l EN-GB` and `-l en-GB` are the same, but they are matched exactly:
`-l en` does not match `@en-GB`, and `-l en-GB` does not match `@en`. When the tag you give matches
no literal and a related tag (one with the same primary subtag) matches some, the command says so
and exits 1:

```
⚠ Found 2 literals tagged en-GB; --source-language en does not match them. Did you mean --source-language en-GB?
```

The warning is given only when the tag you asked for matches nothing. An ontology that carries
both `@en` and `@en-GB` is read without a warning, and each tag counts only its own literals.

**A malformed tag is refused** at exit 2, before anything is written: a blank `-l`, `en_GB`, or a
`target_language` in a translation file that is missing, blank or not a well-formed BCP 47 tag.
In YAML, quote a tag that reads as a boolean, such as Norwegian: `target_language: 'no'`. A
target language that is the source language is refused too.

**`merge` writes tags in canonical case** (`en-GB`, `zh-Hant-TW`), whatever case the translation
file uses. An existing literal whose tag differs only in case counts as existing.

**An untagged literal counts as the source language**, so untagged English labels are extracted and
counted as English. **`@und` is never read as the source language**, or as any language you did
not ask for by that tag: a term labelled only `@und` is measured, but counts as missing in every
row of a report unless `-l und` is one of them.

**An entity is any subject with an IRI that carries one of the requested properties as a
literal**, whatever its type: classes and properties of every kind, individuals, SKOS concepts, the
ontology header, and untyped subjects. A deprecated entity (`owl:deprecated true`, as a boolean
or as the string `"true"`, or a type of `owl:DeprecatedClass` or `owl:DeprecatedProperty`) is
skipped by `extract` and left out of `report` unless `--include-deprecated` is given.

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
| `--language, -l` | Target language tag (required). A tag, not a range: `en` does not match `en-GB` |
| `--output, -o` | Output YAML file (default: `{language}.yml`) |
| `--source-language` | Source language tag (default: `en`) |
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

Generates a translation coverage report showing how much of the content exists in each language.

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
| `--languages, -l` | Comma-separated language tags (required). Each is a tag, not a range |
| `--source-language` | Base language tag (default: `en`) |
| `--include-deprecated` | Count deprecated entities (left out by default) |
| `--properties, -p` | Comma-separated properties to check |
| `--output, -o` | Output file for report |
| `--format, -f` | Output format: `text` or `markdown` |
| `--verbose, -v` | Show detailed missing translation list |
| `--no-colour` | Disable coloured output |

#### How Coverage Is Counted

Coverage counts **entities, not literals**. For each property, the denominator is the entities that
carry that property in at least one language, and each language's figure is how many of them carry
it in that language. Counts print beside the percentage, so `6/8 (75%)` reads "6 of the 8 labelled
entities have an English label".

- The **base row is measured the same way**: it says how much of the labelled material exists in
  the source language. A term labelled only in German counts against it.
- **Overall** adds up every entity and property pair, and **pending** is the number of pairs
  missing in that language. Neither can exceed what was measured.
- A property no entity carries reads `0/0 (—)` and is left out of Overall.
- A second literal in one language adds nothing to the figure. For a property that takes one
  value per language (`rdfs:label`, `skos:prefLabel`) it is listed as a warning. Several
  `skos:altLabel` or `rdfs:comment` values in one language are normal and are not.

#### Example Output

Generated from [`tests/fixtures/localise/coverage.ttl`](../../tests/fixtures/localise/coverage.ttl),
whose comments say what each term demonstrates:

```bash
rdf-construct localise report tests/fixtures/localise/coverage.ttl -l en,de,fr --no-colour
```

```
Translation Coverage Report
========================================

Source: tests/fixtures/localise/coverage.ttl
Entities: 8
Deprecated: 1 (not counted; --include-deprecated counts them)
Properties: rdfs:label, rdfs:comment

Language   rdfs:label  rdfs:comment  Overall     Status
-------------------------------------------------------
en (base)  6/8 (75%)   2/2 (100%)    8/10 (80%)  ⚠ 2 pending
de         5/8 (63%)   1/2 (50%)     6/10 (60%)  ✗ 4 pending
fr         2/8 (25%)   0/2 (0%)      2/10 (20%)  ✗ 8 pending

⚠ 1 entity has more than one de value for a property that takes one per language:
  - Cottage rdfs:label
```

The base row is 6/8 because `ex:Tower` is labelled only in German and `ex:grade` only `@und`;
`ex:Listing`'s untagged label counts as English. `ex:Cottage`'s two German labels count once.

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

The extractor treats literals without language tags as the source language. If your ontology uses untagged English literals, they will be extracted for translation. A literal tagged `@und` ("undetermined") matches no language, so it is never extracted; see [Language Tags](#language-tags-and-which-terms-are-translated).

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Completed with findings: `merge` found translated entities that are not in the ontology; `extract`, `init` or `report` was given a language that matched no literal while a related tag did |
| 2 | Input refused or run failed (invalid options or config, a malformed, missing or blank language tag, a target language that is the source language, file not found, parse error) |

## Related Commands

- `rdf-construct lint` - Check for missing labels (undocumented entities)
- `rdf-construct docs` - Generate documentation including all language labels
- `rdf-construct diff` - Compare ontology versions (including label changes)
