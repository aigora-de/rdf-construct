# RDF-Construct UML Module

This directory contains the complete implementation of the RDF → PlantUML pipeline.

## Contents

- `src/rdf_construct/` - Source code for the UML module and core
- `examples/` - Example ontologies and UML context configurations
- `diagrams/` - Generated PlantUML diagrams
- `UML_PIPELINE_SUMMARY.md` - Detailed implementation documentation

## Quick Start

```bash
# Install dependencies
pip install rdflib pyyaml click

# Run from this directory
export PYTHONPATH=./src:$PYTHONPATH

# List available contexts
python -m rdf_construct.cli contexts examples/uml_contexts.yml

# Generate diagrams
python -m rdf_construct.cli uml examples/animal_ontology.ttl examples/uml_contexts.yml -o output/

# Generate specific context
python -m rdf_construct.cli uml examples/organisation_ontology.ttl examples/uml_contexts.yml -c management
```

## Documentation

See `UML_PIPELINE_SUMMARY.md` for complete documentation including:
- Architecture overview
- Feature descriptions
- Configuration examples
- Known issues
- Next steps for Phase 2 (styling)