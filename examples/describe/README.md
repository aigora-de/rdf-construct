# Describe Command Examples

This directory contains example ontologies and sample outputs for the `rdf-construct describe` command.

## Files

### Sample Ontologies

- `well_documented.ttl` - A well-structured OWL DL ontology with complete metadata and documentation
- `minimal.ttl` - A minimal RDFS ontology with basic structure
- `owl_full_example.ttl` - An OWL Full ontology demonstrating metaclass patterns

### Sample Outputs

- `output_text.txt` - Example text output from `describe`
- `output_json.json` - Example JSON output
- `output_markdown.md` - Example Markdown output

## Running the Examples

```bash
# Basic description
rdf-construct describe examples/describe/well_documented.ttl

# Brief mode
rdf-construct describe examples/describe/well_documented.ttl --brief

# JSON output
rdf-construct describe examples/describe/well_documented.ttl --format json

# Markdown for documentation
rdf-construct describe examples/describe/well_documented.ttl --format markdown

# Compare different profile levels
rdf-construct describe examples/describe/minimal.ttl
rdf-construct describe examples/describe/owl_full_example.ttl
```

## What to Look For

### well_documented.ttl
- Profile: OWL 2 DL (simple)
- High documentation coverage (100% labels, 80%+ definitions)
- Proper ontology metadata (title, version, description)
- Clean hierarchy with no orphans

### minimal.ttl
- Profile: RDFS
- Basic class hierarchy only
- No ontology declaration
- Demonstrates minimal valid structure

### owl_full_example.ttl
- Profile: OWL Full
- Contains metaclass patterns (class used as instance)
- Shows violating constructs in profile detection
- Reasoning guidance warns about undecidability
