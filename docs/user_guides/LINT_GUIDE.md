# Lint Guide

The `lint` command performs static analysis on RDF ontologies to detect quality issues, structural problems, and best practice violations.

## Quick Start

```bash
# Check a single ontology
rdf-construct lint ontology.ttl

# Check multiple files
rdf-construct lint core.ttl domain.ttl

# Strict mode (warnings become errors)
rdf-construct lint ontology.ttl --level strict

# JSON output for CI integration
rdf-construct lint ontology.ttl --format json
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No issues found |
| 1 | Warnings found (no errors) |
| 2 | Errors found |

Use exit codes in CI pipelines:

```bash
rdf-construct lint ontology.ttl --level strict || exit 1
```

## Strictness Levels

### Standard (default)

Uses default severity for each rule. Suitable for regular development.

```bash
rdf-construct lint ontology.ttl
# or explicitly:
rdf-construct lint ontology.ttl --level standard
```

### Strict

Upgrades warnings to errors. Recommended for CI/CD pipelines and releases.

```bash
rdf-construct lint ontology.ttl --level strict
```

### Relaxed

Downgrades warnings to info and skips info-level rules. Useful for early development.

```bash
rdf-construct lint ontology.ttl --level relaxed
```

## Rules Reference

### Structural Rules (Default: Error)

| Rule ID | Description |
|---------|-------------|
| `orphan-class` | Class has no `rdfs:subClassOf` declaration (and isn't `owl:Thing`) |
| `dangling-reference` | Reference to an entity not defined in the ontology |
| `circular-subclass` | Class is a subclass of itself (directly or transitively) |
| `property-no-type` | Property has domain/range but no `rdf:type` declaration |
| `empty-ontology` | `owl:Ontology` declaration has no metadata |

### Documentation Rules (Default: Warning)

| Rule ID | Description |
|---------|-------------|
| `missing-label` | Class or property lacks `rdfs:label` |
| `missing-comment` | Class or property lacks `rdfs:comment` |

### Best Practice Rules (Default: Info)

| Rule ID | Description |
|---------|-------------|
| `redundant-subclass` | Class has redundant inheritance (A → B → C, but also A → C) |
| `property-no-domain` | Object property has no `rdfs:domain` |
| `property-no-range` | Object property has no `rdfs:range` |
| `inconsistent-naming` | Entity names don't follow OWL conventions (UpperCamelCase for classes, lowerCamelCase for properties) |

## Enabling and Disabling Rules

### From Command Line

```bash
# Enable only specific rules
rdf-construct lint ontology.ttl --enable orphan-class --enable missing-label

# Disable specific rules
rdf-construct lint ontology.ttl --disable inconsistent-naming

# Combine both
rdf-construct lint ontology.ttl --enable orphan-class --disable dangling-reference
```

### From Configuration File

Create a `.rdf-lint.yml` file in your project root:

```yaml
level: standard

# Enable only these rules (empty = all)
enable:
  - orphan-class
  - missing-label

# Disable these rules
disable:
  - inconsistent-naming

# Override severity
severity:
  missing-comment: info
```

## Configuration File

### Generating a Default Config

```bash
rdf-construct lint --init
# Creates .rdf-lint.yml with commented defaults
```

### Config File Format

```yaml
# Strictness level: strict | standard | relaxed
level: standard

# Enable only specific rules (empty = all rules)
enable:
  - orphan-class
  - missing-label

# Disable specific rules
disable:
  - inconsistent-naming

# Override severity for specific rules
severity:
  missing-comment: info
  property-no-domain: warning
```

### Config File Discovery

The linter automatically searches for configuration files in this order:

1. Explicit `--config path/to/config.yml`
2. `.rdf-lint.yml` in current directory
3. `.rdf-lint.yaml` in current directory
4. Parent directories (up to filesystem root)

## Output Formats

### Text Output (default)

Human-readable output with optional colours:

```
ontology.ttl:12: error[orphan-class]: 'Building' Class has no rdfs:subClassOf declaration
ontology.ttl:18: warning[missing-label]: 'hasFloor' Property lacks rdfs:label
ontology.ttl:24: info[property-no-domain]: 'builtIn' Object property has no rdfs:domain

Found 1 error, 1 warning, 1 info in 1 file
```

Disable colours for piping:

```bash
rdf-construct lint ontology.ttl --no-colour | tee results.txt
```

### JSON Output

Machine-readable output for CI integration:

```bash
rdf-construct lint ontology.ttl --format json
```

```json
{
  "files": [
    {
      "path": "ontology.ttl",
      "issues": [
        {
          "rule": "orphan-class",
          "severity": "error",
          "entity": "http://example.org/Building",
          "message": "Class has no rdfs:subClassOf declaration",
          "line": null
        }
      ],
      "summary": {"errors": 1, "warnings": 0, "info": 0}
    }
  ],
  "summary": {"errors": 1, "warnings": 0, "info": 0, "files": 1}
}
```

## CI Integration

### GitHub Actions

```yaml
name: Lint Ontology

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      
      - name: Install rdf-construct
        run: pip install rdf-construct
      
      - name: Lint ontology
        run: rdf-construct lint src/ontology/*.ttl --level strict --format json
```

### GitLab CI

```yaml
lint:
  stage: test
  script:
    - pip install rdf-construct
    - rdf-construct lint src/ontology/*.ttl --level strict
  allow_failure: false
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: rdf-lint
        name: Lint RDF ontologies
        entry: rdf-construct lint
        language: system
        files: \.ttl$
        args: [--level, standard]
```

## Listing Available Rules

```bash
rdf-construct lint --list-rules
```

Output:

```
Available lint rules:

  Structural
    orphan-class: error - Class has no rdfs:subClassOf declaration
    dangling-reference: error - Reference to undefined entity
    ...

  Documentation
    missing-label: warning - Entity lacks rdfs:label annotation
    ...

  Best-Practice
    redundant-subclass: info - Class has redundant subclass declaration
    ...
```

## Examples

### Typical Development Workflow

```bash
# During development - relaxed mode
rdf-construct lint ontology.ttl --level relaxed

# Before committing - standard mode
rdf-construct lint ontology.ttl

# Before release - strict mode
rdf-construct lint ontology.ttl --level strict
```

### Checking Multiple Related Ontologies

```bash
# Check all Turtle files in a directory
rdf-construct lint ontologies/*.ttl

# Check with specific config
rdf-construct lint ontologies/*.ttl --config ci/strict-lint.yml
```

### Focusing on Specific Issues

```bash
# Only check for structural issues
rdf-construct lint ontology.ttl \
  --enable orphan-class \
  --enable dangling-reference \
  --enable circular-subclass

# Check documentation completeness
rdf-construct lint ontology.ttl \
  --enable missing-label \
  --enable missing-comment \
  --level strict
```

## Troubleshooting

### "Unknown rule" Error

Check available rules with `--list-rules`. Rule names are case-sensitive and use hyphens.

### Many False Positives

Consider:

1. Using `--level relaxed` during early development
2. Disabling specific rules in config
3. Checking if your ontology imports external definitions that aren't loaded

### External References Flagged as Dangling

The linter only checks entities within the loaded files. If your ontology imports external definitions:

```bash
# Load the imported ontology too
rdf-construct lint domain.ttl foundation.ttl
```

### Parse Errors

If your file can't be parsed, you'll see a `parse-error` issue. Check:

1. File encoding (should be UTF-8)
2. Turtle syntax validity
3. File extension matches format (.ttl for Turtle)