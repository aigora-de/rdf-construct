# Competency Question Testing Guide

## Overview

Competency Questions (CQs) are natural language questions that an ontology should be able to answer. They're fundamental to ontology engineering:

1. **Requirements capture**: "What should this ontology be able to tell us?"
2. **Validation**: "Can the ontology actually answer these questions?"
3. **Regression testing**: "Did this change break existing capabilities?"

The `cq-test` command automates CQ testing by running SPARQL queries against your ontology and checking that results match expectations.

## Quick Start

```bash
# Run all tests in a test suite
rdf-construct cq-test ontology.ttl cq-tests.yml

# Run with verbose output
rdf-construct cq-test ontology.ttl cq-tests.yml --verbose

# Generate JUnit XML for CI
rdf-construct cq-test ontology.ttl cq-tests.yml --format junit -o results.xml
```

## Test File Format

Test files use YAML format with the following structure:

```yaml
# Optional metadata
version: "1.0"
name: "My Ontology CQ Tests"
description: "Validates core competency questions"

# Shared prefix definitions
prefixes:
  ex: "http://example.org/ontology#"
  owl: "http://www.w3.org/2002/07/owl#"
  rdfs: "http://www.w3.org/2000/01/rdf-schema#"

# Optional sample data for testing
data:
  inline: |
    ex:Thing1 a ex:MyClass ;
        rdfs:label "Thing 1" .
  # Or reference external files
  files:
    - sample-data.ttl

# Competency questions
questions:
  - id: cq-001
    name: "MyClass exists"
    description: "The ontology should define MyClass"
    tags: [schema, core]
    query: "ASK { ex:MyClass a owl:Class }"
    expect: true
```

## Question Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (e.g., "cq-001") |
| `name` | No | Human-readable name (defaults to id) |
| `description` | No | Longer description of what's being tested |
| `tags` | No | List of tags for filtering |
| `query` | Yes | SPARQL query (ASK or SELECT) |
| `expect` | Yes | Expected result (see Expectation Types) |
| `skip` | No | Set to `true` to skip this test |
| `skip_reason` | No | Reason for skipping |

## Expectation Types

### Boolean (ASK Queries)

For ASK queries that return true/false:

```yaml
query: "ASK { ex:Animal a owl:Class }"
expect: true

query: "ASK { ex:NonExistent a owl:Class }"
expect: false
```

### Existence Checks

Check whether a query returns any results:

```yaml
# At least one result
expect: has_results

# Zero results
expect: no_results
```

### Count Checks

Check the number of results:

```yaml
# Exact count
expect:
  count: 5

# Minimum count
expect:
  min_results: 1

# Maximum count
expect:
  max_results: 10

# Range
expect:
  min_results: 1
  max_results: 10
```

### Value Checks

Check for specific result values:

```yaml
# Exact match (all rows must match exactly)
expect:
  results:
    - building: "http://example.org/Building1"
      floors: 3

# Subset match (results must contain these bindings)
expect:
  contains:
    - building: "http://example.org/Building1"
```

## Schema vs Data Tests

Competency questions fall into two categories:

### Schema Tests

Test the ontology structure itself. These don't need sample data:

```yaml
- id: cq-schema-001
  name: "Building class defined"
  tags: [schema]
  query: |
    ASK {
      ex:Building a owl:Class .
    }
  expect: true

- id: cq-schema-002
  name: "hasFloor property has correct domain"
  tags: [schema]
  query: |
    ASK {
      ex:hasFloor rdfs:domain ex:Building .
    }
  expect: true
```

### Data Tests

Test query patterns against instance data. These need sample data:

```yaml
data:
  inline: |
    ex:Building1 a ex:Building ;
        ex:hasFloor ex:Floor1, ex:Floor2 .

questions:
  - id: cq-data-001
    name: "Can query building floors"
    tags: [data]
    query: |
      SELECT ?floor WHERE {
        ex:Building1 ex:hasFloor ?floor .
      }
    expect:
      min_results: 1
```

## CLI Options

```
Usage: rdf-construct cq-test [OPTIONS] ONTOLOGY TEST_FILE

Options:
  -d, --data PATH           Additional data file(s) to load
  -t, --tag TEXT            Only run tests with these tags
  -x, --exclude-tag TEXT    Exclude tests with these tags
  -f, --format [text|json|junit]
                            Output format (default: text)
  -o, --output PATH         Write output to file
  -v, --verbose             Show verbose output
  --fail-fast               Stop on first failure
  --help                    Show this message and exit
```

### Examples

```bash
# Run only 'core' tests
rdf-construct cq-test ontology.ttl tests.yml --tag core

# Exclude slow tests
rdf-construct cq-test ontology.ttl tests.yml --exclude-tag slow

# Run with additional instance data
rdf-construct cq-test ontology.ttl tests.yml --data split_instances.ttl

# Verbose mode (shows query text and timing)
rdf-construct cq-test ontology.ttl tests.yml --verbose

# Stop on first failure
rdf-construct cq-test ontology.ttl tests.yml --fail-fast
```

## Exit Codes

The command returns meaningful exit codes for CI integration:

| Code | Meaning |
|------|---------|
| 0 | All tests passed |
| 1 | One or more tests failed |
| 2 | Error occurred (file not found, parse error, etc.) |

## Output Formats

### Text (Default)

Human-readable console output:

```
Competency Question Tests: building.ttl
========================================

[PASS] cq-001: Building class exists
[PASS] cq-002: hasFloor property defined (2 results)
[FAIL] cq-003: Floor count
       Expected: exactly 3
       Actual:   2
[SKIP] cq-004: Inference test (Requires reasoner)

Results: 2 passed, 1 failed, 1 skipped
```

### JSON

Structured JSON for programmatic use:

```json
{
  "ontology": "building.ttl",
  "questions": [
    {
      "id": "cq-001",
      "name": "Building class exists",
      "status": "pass",
      "duration_ms": 12.5
    }
  ],
  "summary": {
    "total": 4,
    "passed": 2,
    "failed": 1,
    "skipped": 1
  }
}
```

### JUnit XML

Standard JUnit format for CI systems:

```xml
<?xml version="1.0" ?>
<testsuite name="Competency Questions" tests="4" failures="1" skipped="1">
  <testcase name="cq-001: Building class exists" time="0.012"/>
  <testcase name="cq-003: Floor count" time="0.015">
    <failure message="Count mismatch">
      Expected: exactly 3
      Actual: 2
    </failure>
  </testcase>
</testsuite>
```

## CI Integration

### GitHub Actions

```yaml
name: Ontology Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install rdf-construct
      
      - name: Run CQ tests
        run: |
          rdf-construct cq-test ontology.ttl tests/cq-tests.yml \
            --format junit -o test-results.xml
      
      - name: Publish Test Results
        uses: dorny/test-reporter@v1
        if: always()
        with:
          name: Competency Questions
          path: test-results.xml
          reporter: java-junit
```

### GitLab CI

```yaml
test:ontology:
  stage: test
  script:
    - pip install rdf-construct
    - rdf-construct cq-test ontology.ttl tests/cq-tests.yml --format junit -o cq-results.xml
  artifacts:
    reports:
      junit: cq-results.xml
```

## Best Practices

### Organise Tests with Tags

Use tags to categorise tests:

```yaml
- id: cq-schema-001
  tags: [schema, core]
  # ...

- id: cq-data-001
  tags: [data, slow]
  # ...
```

Then run subsets:

```bash
# Only schema tests (fast)
rdf-construct cq-test ontology.ttl tests.yml --tag schema

# Exclude slow tests
rdf-construct cq-test ontology.ttl tests.yml --exclude-tag slow
```

### Test Both Schema and Data

Schema tests validate ontology structure:

```yaml
- id: cq-schema-001
  name: "Class hierarchy correct"
  query: "ASK { ex:Dog rdfs:subClassOf ex:Animal }"
  expect: true
```

Data tests validate query patterns work:

```yaml
- id: cq-data-001
  name: "Can find dogs"
  query: "SELECT ?dog WHERE { ?dog a ex:Dog }"
  expect: has_results
```

### Use Descriptive IDs

Follow a naming convention:

- `cq-schema-NNN` for schema tests
- `cq-data-NNN` for data tests
- `cq-neg-NNN` for negative tests
- `cq-perf-NNN` for performance tests

### Document with Descriptions

Include descriptions explaining what each test validates:

```yaml
- id: cq-001
  name: "Buildings have addresses"
  description: |
    Validates CQ-7 from requirements: "What is the address 
    of a given building?" The ontology must support linking
    buildings to their postal addresses.
  query: |
    ASK {
      ex:Building1 ex:hasAddress ?addr .
      ?addr a ex:PostalAddress .
    }
  expect: true
```

### Skip Tests Gracefully

Use skip for tests that require features not yet implemented:

```yaml
- id: cq-infer-001
  name: "Transitive closure of partOf"
  skip: true
  skip_reason: "Requires OWL reasoner support"
  query: |
    ASK {
      ex:Room1 ex:partOf+ ex:Building1 .
    }
  expect: true
```

## Programmatic Usage

You can also use the CQ testing module programmatically:

```python
from pathlib import Path
from rdflib import Graph

from rdf_construct.cq import load_test_suite, CQTestRunner, format_results

# Load ontology
ontology = Graph()
ontology.parse("ontology.ttl", format="turtle")

# Load and filter test suite
suite = load_test_suite(Path("cq-tests.yml"))
suite = suite.filter_by_tags(include_tags={"core"})

# Run tests
runner = CQTestRunner(fail_fast=False, verbose=True)
results = runner.run(ontology, suite)

# Check results
print(f"Passed: {results.passed_count}/{results.total_count}")

if not results.all_passed:
    print(format_results(results, format_name="text"))
```

## Troubleshooting

### "No prefix for namespace" Errors

Make sure all prefixes used in queries are declared:

```yaml
prefixes:
  ex: "http://example.org/"
  # Don't forget standard prefixes if using them
  owl: "http://www.w3.org/2002/07/owl#"
  rdfs: "http://www.w3.org/2000/01/rdf-schema#"
  rdf: "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
```

### SPARQL Syntax Errors

Test your queries in a SPARQL endpoint first. Common issues:

- Missing prefixes
- Unbalanced braces
- Invalid property paths
- Case sensitivity

### Unexpected Results

Use `--verbose` to see what's happening:

```bash
rdf-construct cq-test ontology.ttl tests.yml --verbose
```

This shows the actual query results and timing.

## See Also

- [CLI Reference](CLI_REFERENCE.md) - Full command documentation
- [Lint Guide](LINT_GUIDE.md) - Static analysis for ontologies