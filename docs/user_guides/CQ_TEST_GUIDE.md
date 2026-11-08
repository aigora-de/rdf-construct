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
| `query` | Yes | SPARQL query (ASK, SELECT, CONSTRUCT or DESCRIBE) |
| `expect` | Yes | Expected result (see Expectation Types) |
| `skip` | No | Set to `true` to skip this test. Unquoted: `"false"` is text, and is refused |
| `skip_reason` | No | Reason for skipping |

## What a Test File May Contain

The file is checked before anything runs. A test file of the wrong shape is refused at exit 2,
naming what is wrong and what is accepted, rather than run as something its author did not write.

| Where | Accepted keys |
|-------|---------------|
| top level | `version`, `name`, `description`, `prefixes`, `data`, `questions` |
| a question | `id`, `name`, `description`, `tags`, `query`, `expect`, `skip`, `skip_reason` |
| `data:` | `inline`, `files` |
| an `expect:` mapping | one of `count`, `min_results` and/or `max_results`, `results`, `contains` |

Any other key, at any of these levels, is refused. A misspelling gets a suggestion:

```
Error: Error parsing t1: unknown key 'expectt' in question 't1'. Did you mean 'expect'? Accepted keys: id, name, description, tags, query, expect, skip, skip_reason
```

The top level must be a mapping: a file that is a bare list of questions is refused with
`must be a mapping with a 'questions:' list, not a list`. An `expect:` mapping takes one form:
`{count: 2, max_results: 1}` is refused, because it would check only one of them. YAML anchors
work, but define one at its first use (`expect: &yes true`, then `expect: *yes`), not under a key
of its own: an extra top-level key such as `defaults:` is refused like any other.

## Sample Data

`data:` adds triples to the ontology for the questions to query. It takes a file path, a list of
paths, or a mapping with `inline` Turtle and/or `files`:

```yaml
data: sample-data.ttl                   # one file
data: [people.ttl, places.ttl]          # several
data:                                   # the long form
  inline: |
    ex:Thing1 a ex:MyClass .
  files: [sample-data.ttl]
```

- Relative paths resolve against the test file's directory, not the working directory.
- `inline` data is read with the file's `prefixes:`.
- **Every source must hold at least one triple.** A file or `inline` block that loads none is
  refused at exit 2, naming it: a `no_results` or `max_results` question would otherwise pass on
  data that never loaded.
- Files given with `-d/--data` are loaded as well, not instead.

## Expectation Types

An ASK query answers true or false; it has no results to count or bind, so it takes only
`expect: true` or `expect: false`. Any other expectation on an ASK is reported as that question's
`ERROR`, and the run exits 2. The other questions still run. Likewise, `results` and `contains`
match variable bindings, so they take only a SELECT.

| Expectation | ASK | SELECT | CONSTRUCT, DESCRIBE |
|-------------|-----|--------|---------------------|
| `true` / `false` | the ASK's answer | `true` = at least one row | `true` = at least one triple |
| `has_results` / `no_results` | `ERROR` | rows | triples |
| `count`, `min_results`, `max_results` | `ERROR` | rows | triples |
| `results`, `contains` | `ERROR` | row bindings | `ERROR`: triples have no variable bindings |

A CONSTRUCT result is a graph, so its count is of distinct triples, not of solutions: a template
that writes the same triple for three solutions counts 1, and a solution that leaves a template
variable unbound writes no triple. What DESCRIBE returns is left to the implementation by SPARQL;
rdflib returns the resource's own triples and follows its blank nodes, so `DESCRIBE ex:A` on a
class with one `owl:Restriction` counts the restriction's triples too.

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

A value check compares a literal by its value, so `floors: 3` matches `"3"^^xsd:integer` and
`"03"^^xsd:integer` alike. A literal constant **inside the query's graph pattern** matches by term:
`ASK { ?b ex:floors 3 }` does not match `"03"^^xsd:integer`, which the ontology is read with as
written ([#377](https://github.com/aigora-de/rdf-construct/issues/377)). To compare by value, bind
a variable and filter it: `ASK { ?b ex:floors ?n FILTER(?n = 3) }`.

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
prefixes:
  ex: "http://example.org/building#"

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
  --fail-fast               Stop after the first question that fails or errors;
                            the rest are reported as not run
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

# Stop after the first failure or error
rdf-construct cq-test ontology.ttl tests.yml --fail-fast
```

## Exit Codes

The command returns meaningful exit codes for CI integration:

| Code | Meaning |
|------|---------|
| 0 | All tests passed |
| 1 | One or more tests failed |
| 2 | Error occurred (file not found, parse error, a test file of the wrong shape, no questions to run, a question whose query fails or whose expectation does not fit its query form, etc.) |

### When There Is Nothing to Run

A run that checked nothing did not do what was asked, so it exits 2 and says why, rather than
passing a CI build that tested nothing:

| Cause | Message |
|-------|---------|
| no `questions:` key | `no questions to run: tests.yml has no 'questions:' list (top-level keys found: prefixes)` |
| `questions: []` | `no questions to run: 'questions:' in tests.yml is an empty list` |
| a `--tag` no question has, and nothing else selected | `no questions to run: --tag scheme matches no question in tests.yml`, then `Tags defined: …` |
| exclusions remove everything | `no questions to run: --exclude-tag core removes every question --tag core selected`, then `Tags defined: …` |
| every selected question has `skip: true` | `no questions to run: every selected question has skip: true` |

A file keyed `tests:` instead of `questions:` is refused first, as an unknown key, with
`Did you mean 'questions'?`.

A misspelt tag beside one that does select questions is not refused: the run goes ahead with
what the other tag selected. Check the `Running N test(s)` line.

### `--fail-fast`

`--fail-fast` stops after the first question that fails **or errors**. The questions after it are
not run, and are reported as such: the total is always every selected question, so a dashboard
does not see the suite shrink on the run that fails. The exit code is that of the question that
stopped the run (1 for a failure, 2 for an error); the questions not run add nothing to it.

```
[PASS] cq-ff-pass: Animal is a class
[FAIL] cq-ff-fail: A class the ontology does not define
       Expected: True
       Actual:   False
[NOT RUN] cq-ff-not-run: Dog is a class

Results: 1 passed, 1 failed
2 of 3 run — stopped by --fail-fast after 'cq-ff-fail'
```

In JSON, a question not run has `"status": "not_run"` and is counted in `summary.not_run`;
`summary.skipped` counts only questions with `skip: true`. In JUnit XML, each is a `<testcase>`
holding `<skipped message="not run: --fail-fast stopped after cq-ff-fail"/>`, and the `skipped`
attribute counts every `<skipped>` element, so *tests − failures − errors − skipped* is the number
that passed. A skip with a `skip_reason` carries the reason as its `message`, so the two can be
told apart. A question after the stop that has `skip: true` is still reported as skipped, with its
reason: it was never going to run. A question that stops the run because its expectation does not fit its query form is
an error that ran: it is counted in `errors`, and the questions after it are the ones not run.

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
    "errors": 0,
    "skipped": 1,
    "not_run": 0
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

## Known Limitations

These are open issues, current as of v0.7.0. They are here because a guide that describes intended
behaviour is worse than no guide. **A fix that lands should delete its row in the same PR.**

| Issue | Behaviour today |
|---|---|
| [#386](https://github.com/aigora-de/rdf-construct/issues/386) | A SELECT solution whose projected variables are all unbound is not counted, so a variable-less `SELECT *` that matches counts 0 rows, and `OPTIONAL` columns undercount. |
| [#439](https://github.com/aigora-de/rdf-construct/issues/439) | `-o` naming a file listed under the test file's `data:` replaces it with the results, at exit 0. (`-o` naming the ontology, the test file or a `-d` file is refused.) |
| [#136](https://github.com/aigora-de/rdf-construct/issues/136) | `-o` writes the text format's colour escapes into the file, and `--verbose` does not show the query text. |
| [#523](https://github.com/aigora-de/rdf-construct/issues/523) | A `-d/--data` file that loads no triples is accepted; a `data:` source that loads none is refused. |
| [#524](https://github.com/aigora-de/rdf-construct/issues/524) | Two questions with the same `id` both run, and are reported under one name. |
| [#527](https://github.com/aigora-de/rdf-construct/issues/527) | A `--tag` or `--exclude-tag` that matches no question is ignored when another tag still selects some. |
| [#526](https://github.com/aigora-de/rdf-construct/issues/526) | `query`, `id` and the counts in `expect:` are not type-checked: `count: "2"` fails against 2 results. |
| [#522](https://github.com/aigora-de/rdf-construct/issues/522) | A SPARQL syntax error's line number counts the `PREFIX` lines added from `prefixes:`, so a one-line query reports `line:3`. |
| [#146](https://github.com/aigora-de/rdf-construct/issues/146) | The ontology's and data files' formats are read from their extensions by a map of `cq-test`'s own, not the shared one, and a parse error does not name the file. |
| [#149](https://github.com/aigora-de/rdf-construct/issues/149) | `examples/cq-test/` has no ontology of its own: run it against `examples/animal_ontology.ttl`. |

## See Also

- [CLI Reference](CLI_REFERENCE.md) - Full command documentation
- [Lint Guide](LINT_GUIDE.md) - Static analysis for ontologies
