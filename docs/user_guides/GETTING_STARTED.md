# Getting Started with rdf-construct

## What is rdf-construct?

**rdf-construct** is a toolkit for working with RDF ontologies. It provides 14 commands organised into categories:

| Category | Commands | Purpose |
|----------|----------|---------|
| **Analysis** | `describe`, `stats` | Understand ontology structure and metrics |
| **Documentation** | `docs`, `uml` | Generate documentation and diagrams |
| **Validation** | `lint`, `shacl-gen`, `cq-test` | Check quality and run tests |
| **Comparison** | `diff` | Compare ontology versions |
| **Transformation** | `merge`, `split`, `refactor`, `localise` | Combine, modularise, rename, translate |
| **Conversion** | `puml2rdf` | Convert PlantUML to RDF |
| **Ordering** | `order` | Semantic RDF serialisation |

Named after the ROM construct from Gibson's *Neuromancer*—preserved, structured knowledge.

## Quick Start (5 Minutes)

### Installation

```bash
# From PyPI (recommended)
pip install rdf-construct

# For development
git clone https://github.com/aigora-de/rdf-construct.git
cd rdf-construct
poetry install
```

### Your First Commands

```bash
# 1. Describe an ontology (what is this file?)
rdf-construct describe examples/animal_ontology.ttl

# 2. Check quality
rdf-construct lint examples/animal_ontology.ttl

# 3. Generate a UML diagram
rdf-construct uml examples/animal_ontology.ttl -C examples/uml_contexts.yml

# 4. Generate documentation
rdf-construct docs examples/animal_ontology.ttl -o my-docs/
```

## Command Categories Tour

### Analysis: Understanding Ontologies

**describe** - Quick orientation to an unfamiliar ontology:

```bash
# What is this ontology? How big? What does it import?
rdf-construct describe ontology.ttl

# Brief summary for quick triage
rdf-construct describe ontology.ttl --brief

# JSON for scripting
rdf-construct describe ontology.ttl --format json
```

Output includes metadata, metrics, OWL profile detection, import status, and documentation coverage.

**stats** - Detailed metrics and comparison:

```bash
# Full statistics
rdf-construct stats ontology.ttl

# Compare two versions
rdf-construct stats v1.ttl v2.ttl --compare
```

### Documentation: Generating Outputs

**docs** - Generate navigable documentation:

```bash
# HTML with search (default)
rdf-construct docs ontology.ttl -o api-docs/

# Markdown for GitHub wiki
rdf-construct docs ontology.ttl --format markdown -o wiki/

# JSON for custom rendering
rdf-construct docs ontology.ttl --format json
```

**uml** - Generate PlantUML class diagrams:

```bash
# Generate diagrams using context configuration
rdf-construct uml ontology.ttl -C contexts.yml

# With styling
rdf-construct uml ontology.ttl -C contexts.yml \
  --style-config styles.yml --style default
```

### Validation: Checking Quality

**lint** - Check for structural issues and best practices:

```bash
# Run all rules
rdf-construct lint ontology.ttl

# Strict mode
rdf-construct lint ontology.ttl --level strict

# See available rules
rdf-construct lint --list-rules
```

**shacl-gen** - Generate SHACL validation shapes:

```bash
# Generate shapes from OWL definitions
rdf-construct shacl-gen ontology.ttl -o shapes.ttl

# Strict mode with closed shapes
rdf-construct shacl-gen ontology.ttl --level strict --closed
```

**cq-test** - Run competency question tests:

```bash
# SPARQL-based validation
rdf-construct cq-test ontology.ttl tests.yml

# JUnit output for CI
rdf-construct cq-test ontology.ttl tests.yml --format junit -o results.xml
```

### Comparison: Tracking Changes

**diff** - Semantic comparison of ontology versions:

```bash
# See what changed
rdf-construct diff v1.0.ttl v1.1.ttl

# Generate markdown changelog
rdf-construct diff v1.0.ttl v1.1.ttl --format markdown -o CHANGELOG.md
```

Unlike text diff, this ignores reordering, prefix changes, and whitespace.

### Transformation: Modifying Ontologies

**merge** - Combine multiple ontologies:

```bash
# Basic merge
rdf-construct merge core.ttl extension.ttl -o merged.ttl

# With conflict resolution priorities
rdf-construct merge core.ttl extension.ttl -o merged.ttl -p 1 -p 2
```

**split** - Modularise large ontologies:

```bash
# Split by namespace
rdf-construct split large.ttl -o modules/ --by-namespace

# Preview without writing
rdf-construct split large.ttl -o modules/ --by-namespace --dry-run
```

**refactor** - Rename URIs or deprecate entities:

```bash
# Fix a typo
rdf-construct refactor rename ontology.ttl \
  --from "ex:Buiding" --to "ex:Building" -o fixed.ttl

# Deprecate with replacement
rdf-construct refactor deprecate ontology.ttl \
  --entity "ex:Legacy" --replaced-by "ex:Modern" -o updated.ttl
```

**localise** - Multi-language translation management:

```bash
# Extract strings for translation
rdf-construct localise extract ontology.ttl -l de -o translations/de.yml

# Merge translations back
rdf-construct localise merge ontology.ttl translations/de.yml -o localised.ttl
```

### Conversion: Format Transformation

**puml2rdf** - Convert PlantUML diagrams to RDF:

```bash
# Diagram-first ontology design
rdf-construct puml2rdf design.puml -n http://example.org/ont#

# Validate without generating
rdf-construct puml2rdf design.puml --validate
```

### Ordering: Semantic Serialisation

**order** - Reorder RDF with semantic structure:

```bash
# Apply ordering profiles
rdf-construct order ontology.ttl order.yml

# See available profiles
rdf-construct profiles order.yml
```

## Common Patterns

### CI/CD Integration

```bash
# Quality gate
rdf-construct lint ontology.ttl --format json -o lint.json
rdf-construct cq-test ontology.ttl tests.yml --format junit -o results.xml

# Documentation generation
rdf-construct docs ontology.ttl -o docs/
rdf-construct describe ontology.ttl --format markdown >> README.md
```

### Exploring a New Ontology

```bash
# 1. What is it?
rdf-construct describe unknown.ttl

# 2. Any obvious issues?
rdf-construct lint unknown.ttl

# 3. Generate visual overview
rdf-construct uml unknown.ttl -C simple_contexts.yml
```

### Version Comparison Workflow

```bash
# Compare versions
rdf-construct diff v1.0.ttl v1.1.ttl --format markdown > release-notes.md

# Detailed metric changes
rdf-construct stats v1.0.ttl v1.1.ttl --compare
```

## Configuration Files

Most commands support YAML configuration:

| File Type | Commands | Purpose |
|-----------|----------|---------|
| `contexts.yml` | `uml` | Define diagram contexts |
| `styles.yml` | `uml` | Visual styling |
| `order.yml` | `order` | Ordering profiles |
| `.rdf-lint.yml` | `lint` | Rule configuration |
| `merge.yml` | `merge` | Merge configuration |
| `split.yml` | `split` | Split configuration |

Generate defaults with `--init`:

```bash
rdf-construct lint --init          # Creates .rdf-lint.yml
rdf-construct merge --init         # Creates merge.yml
rdf-construct split --init         # Creates split.yml
```

## Getting Help

```bash
# General help
rdf-construct --help

# Command-specific help
rdf-construct describe --help
rdf-construct uml --help

# List available configurations
rdf-construct contexts config.yml
rdf-construct profiles order.yml
rdf-construct lint --list-rules
```

## Next Steps

Now that you've got the basics, explore:

- **[Quick Reference](QUICK_REFERENCE.md)**: Condensed cheat sheet
- **[CLI Reference](CLI_REFERENCE.md)**: Complete command documentation
- **[Describe Guide](DESCRIBE_GUIDE.md)**: Quick ontology orientation
- **[UML Guide](UML_GUIDE.md)**: Complete diagram features
- **[Lint Guide](LINT_GUIDE.md)**: Quality checking rules

## Questions?

- **Issues**: https://github.com/aigora-de/rdf-construct/issues
- **Discussions**: https://github.com/aigora-de/rdf-construct/discussions
