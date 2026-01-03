# rdf-construct Quick Reference

A condensed cheat sheet for all rdf-construct commands. For detailed documentation, see the [CLI Reference](CLI_REFERENCE.md).

## Commands at a Glance

| Command | Purpose | Quick Example |
|---------|---------|---------------|
| `describe` | Quick ontology orientation | `rdf-construct describe ontology.ttl` |
| `order` | Semantic RDF ordering | `rdf-construct order ontology.ttl config.yml` |
| `uml` | Generate UML diagrams | `rdf-construct uml ontology.ttl -C contexts.yml` |
| `docs` | Generate documentation | `rdf-construct docs ontology.ttl -o api/` |
| `puml2rdf` | PlantUML to RDF conversion | `rdf-construct puml2rdf design.puml` |
| `diff` | Compare ontology versions | `rdf-construct diff v1.ttl v2.ttl` |
| `lint` | Check ontology quality | `rdf-construct lint ontology.ttl` |
| `shacl-gen` | Generate SHACL shapes | `rdf-construct shacl-gen ontology.ttl` |
| `cq-test` | Run competency questions | `rdf-construct cq-test ontology.ttl tests.yml` |
| `stats` | Ontology metrics | `rdf-construct stats ontology.ttl` |
| `merge` | Combine ontologies | `rdf-construct merge a.ttl b.ttl -o merged.ttl` |
| `split` | Modularise ontologies | `rdf-construct split large.ttl -o modules/` |
| `refactor` | Rename/deprecate URIs | `rdf-construct refactor rename ...` |
| `localise` | Multi-language support | `rdf-construct localise extract ...` |

## Analysis & Documentation

```bash
# Quick orientation to unfamiliar ontology
rdf-construct describe ontology.ttl
rdf-construct describe ontology.ttl --brief          # Faster, less detail
rdf-construct describe ontology.ttl --format json    # For scripting

# Generate documentation
rdf-construct docs ontology.ttl -o docs/             # HTML (default)
rdf-construct docs ontology.ttl --format markdown    # Markdown
rdf-construct docs ontology.ttl --format json        # JSON

# Ontology statistics
rdf-construct stats ontology.ttl
rdf-construct stats v1.ttl v2.ttl --compare          # Compare versions
```

## Visualisation

```bash
# UML diagrams
rdf-construct uml ontology.ttl -C contexts.yml
rdf-construct uml ontology.ttl -C contexts.yml -c specific_context
rdf-construct contexts contexts.yml                   # List available contexts

# With styling
rdf-construct uml ontology.ttl -C contexts.yml \
  --style-config styles.yml --style default
```

## Validation & Testing

```bash
# Lint for quality issues
rdf-construct lint ontology.ttl
rdf-construct lint ontology.ttl --level strict
rdf-construct lint --list-rules                       # Show available rules

# SHACL shape generation
rdf-construct shacl-gen ontology.ttl -o shapes.ttl
rdf-construct shacl-gen ontology.ttl --level strict --closed

# Competency question testing
rdf-construct cq-test ontology.ttl tests.yml
rdf-construct cq-test ontology.ttl tests.yml --format junit -o results.xml
```

## Comparison & Ordering

```bash
# Semantic diff
rdf-construct diff old.ttl new.ttl
rdf-construct diff old.ttl new.ttl --format markdown -o CHANGELOG.md

# Semantic ordering
rdf-construct order ontology.ttl config.yml
rdf-construct order ontology.ttl config.yml -p profile_name
rdf-construct profiles config.yml                     # List available profiles
```

## Transformation

```bash
# Merge ontologies
rdf-construct merge core.ttl ext.ttl -o merged.ttl
rdf-construct merge core.ttl ext.ttl -o merged.ttl -p 1 -p 2  # With priorities
rdf-construct merge core.ttl ext.ttl --dry-run                # Preview

# Split ontologies
rdf-construct split large.ttl -o modules/ --by-namespace
rdf-construct split large.ttl -o modules/ -c split.yml
rdf-construct split large.ttl --dry-run                       # Preview

# Refactor (rename)
rdf-construct refactor rename ontology.ttl \
  --from "ex:Old" --to "ex:New" -o fixed.ttl
rdf-construct refactor rename ontology.ttl \
  --from-namespace "http://old/" --to-namespace "http://new/" -o migrated.ttl

# Refactor (deprecate)
rdf-construct refactor deprecate ontology.ttl \
  --entity "ex:Legacy" --replaced-by "ex:Modern" -o updated.ttl
```

## Conversion

```bash
# PlantUML to RDF
rdf-construct puml2rdf design.puml
rdf-construct puml2rdf design.puml -n http://example.org/ont#
rdf-construct puml2rdf design.puml --merge existing.ttl
rdf-construct puml2rdf design.puml --validate          # Validate only
```

## Multi-Language

```bash
# Extract for translation
rdf-construct localise extract ontology.ttl -l de -o de.yml

# Merge translations
rdf-construct localise merge ontology.ttl de.yml -o localised.ttl

# Coverage report
rdf-construct localise report ontology.ttl -l en,de,fr
```

## Common Options

| Option | Meaning |
|--------|---------|
| `-o, --output` | Output file/directory |
| `-f, --format` | Output format (text, json, markdown, etc.) |
| `-c, --config` | Configuration file |
| `--dry-run` | Preview without writing |
| `--no-colour` | Disable coloured output |
| `-v, --verbose` | More detailed output |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success / No issues |
| `1` | Warnings / Differences found / Tests failed |
| `2` | Errors / Invalid input |

## Output Formats

| Command | Formats |
|---------|---------|
| `describe` | text, json, markdown |
| `docs` | html, markdown, json |
| `diff` | text, markdown, json |
| `lint` | text, json |
| `stats` | text, json, markdown |
| `cq-test` | text, json, junit |
| `shacl-gen` | turtle, json-ld |
| `localise report` | text, markdown |

## Configuration Files

| File | Used By |
|------|---------|
| `*_contexts.yml` | `uml` - diagram contexts |
| `*_styles.yml` | `uml` - visual styling |
| `*_layouts.yml` | `uml` - diagram layout |
| `order.yml` | `order` - ordering profiles |
| `.rdf-lint.yml` | `lint` - rule configuration |
| `merge.yml` | `merge` - merge configuration |
| `split.yml` | `split` - split configuration |

## Tips

```bash
# Check what's available
rdf-construct --help
rdf-construct <command> --help
rdf-construct contexts config.yml
rdf-construct profiles order.yml
rdf-construct lint --list-rules

# CI-friendly outputs
rdf-construct lint ontology.ttl --format json
rdf-construct cq-test ontology.ttl tests.yml --format junit
rdf-construct stats ontology.ttl --format json
```

## Links

- **Full CLI Reference**: [CLI_REFERENCE.md](CLI_REFERENCE.md)
- **Getting Started**: [GETTING_STARTED.md](GETTING_STARTED.md)
- **GitHub**: https://github.com/aigora-de/rdf-construct
- **Issues**: https://github.com/aigora-de/rdf-construct/issues
