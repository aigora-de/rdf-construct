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
| 0 | No findings at or above `--fail-on` |
| 1 | Findings at or above `--fail-on` |
| 2 | Input refused or run failed (invalid options or config, an unknown rule name, a selection that leaves no rule to run, file not found, a directory given as a file), or a file could not be parsed |

`--fail-on` sets the lowest severity that counts: `error` (the default), `warning`, `info` or
`never`. With the default, a run with only warnings exits 0. A file that could not be parsed exits
2 whatever `--fail-on` says, `never` included: no rule ran on it (see [Parse Errors](#parse-errors)).

Use exit codes in CI pipelines:

```bash
# Fail on errors only (the default)
rdf-construct lint ontology.ttl || exit 1

# Fail on warnings too
rdf-construct lint ontology.ttl --fail-on warning || exit 1
```

A `1` always means the run completed and found something; a `2` means it could not check the file
at all. Before v0.7.0, error findings exited 2 — see the
[migration note](../MIGRATION_v0.7.0.md#lint).

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

Downgrades warnings to info. Every rule still runs: relaxed changes how findings are reported, not
which checks are made, so the output is quieter but no shorter. To run fewer checks,
[disable them](#enabling-and-disabling-rules).

```bash
rdf-construct lint ontology.ttl --level relaxed
```

## Rules Reference

### Structural Rules (Default: Error)

| Rule ID | Description |
|---------|-------------|
| `orphan-class` | Class has no `rdfs:subClassOf` declaration (and isn't `owl:Thing`) |
| `dangling-reference` | Reference to an entity not defined in the ontology, in a namespace the file claims (see [Whose terms are checked](#whose-terms-are-checked)) |
| `circular-subclass` | Class is a subclass of itself (directly or transitively) |
| `property-no-type` | Property has domain/range but no `rdf:type` declaration |
| `empty-ontology` | `owl:Ontology` header says nothing about the ontology: no annotation and no `owl:versionIRI` (see [Ontology headers](#ontology-headers)) |

### Documentation Rules (Default: Warning)

| Rule ID | Description |
|---------|-------------|
| `missing-label` | One of the ontology's own classes or properties lacks `rdfs:label` |
| `missing-comment` | One of the ontology's own classes or properties lacks `rdfs:comment` |

A term the file only borrows, such as `dcterms:creator a owl:AnnotationProperty`, which OWL 2 DL
asks you to declare, is not the file's to document, and neither rule reports it. See
[Whose terms are checked](#whose-terms-are-checked).

### Best Practice Rules (Default: Info)

| Rule ID | Description |
|---------|-------------|
| `redundant-subclass` | Class has redundant inheritance (A → B → C, but also A → C) |
| `property-no-domain` | Object property has no `rdfs:domain` |
| `property-no-range` | Object property has no `rdfs:range` |
| `inconsistent-naming` | Entity names don't follow OWL conventions (UpperCamelCase for classes, lowerCamelCase for properties) |

### Which declarations each rule sees

A **class** is any named subject typed `owl:Class`, `rdfs:Class` or `owl:DeprecatedClass`. A
**property** is any named subject typed with one of the property types: `rdf:Property`,
`owl:ObjectProperty`, `owl:DatatypeProperty`, `owl:AnnotationProperty`, an OWL characteristic
(`owl:TransitiveProperty`, `owl:SymmetricProperty`, `owl:AsymmetricProperty`,
`owl:ReflexiveProperty`, `owl:IrreflexiveProperty`, `owl:InverseFunctionalProperty`,
`owl:FunctionalProperty`) or `owl:DeprecatedProperty`. A term declared only as
`ex:ancestorOf a owl:TransitiveProperty` is a property, gets `missing-label` and
`missing-comment`, and is not `property-no-type`. A blank node (an anonymous class expression)
is never a term.

`property-no-domain` and `property-no-range` look at `owl:ObjectProperty` only, so far; a term
declared only by a characteristic, or as `owl:FunctionalProperty`, gets neither yet
([#205](https://github.com/aigora-de/rdf-construct/issues/205)).

### Ontology headers

`empty-ontology` reports a named `owl:Ontology` header that says nothing about the ontology. Any
triple on the header counts as metadata **except `rdf:type` and `owl:imports`**: an `rdfs:label`
or `rdfs:comment`, `owl:versionInfo`, `owl:priorVersion`, `owl:deprecated`, `dcterms:title`,
`skos:prefLabel`, `vann:preferredNamespacePrefix`, the `prov:wasDerivedFrom` stamp that `merge`,
`split` and `order` write, or any other annotation, and also `owl:versionIRI`. A header whose only
triples are its type and its imports is reported. A blank-node header is not checked.

`headers.ttl` declares three:

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix prov: <http://www.w3.org/ns/prov#> .

# A title is metadata
<https://example.org/catalogue> a owl:Ontology ;
    dcterms:title "Catalogue" .

# So is the derivation a named merge writes
<https://example.org/catalogue-merged> a owl:Ontology ;
    prov:wasDerivedFrom <https://example.org/catalogue> .

# Imports alone are not
<https://example.org/catalogue-stub> a owl:Ontology ;
    owl:imports <https://example.org/catalogue> .
```

```bash
rdf-construct lint headers.ttl
```

```text
Scanning 1 file(s)...

headers.ttl:14 error[empty-ontology] ns1:catalogue-stub: owl:Ontology has no metadata: no annotation (label, comment, title, provenance, …) and no owl:versionIRI

Found 1 error, 0 warnings, 0 info in 1 file
```

The run exits 1. (`ns1:` is rdflib's name for a namespace the file binds no prefix to:
[#507](https://github.com/aigora-de/rdf-construct/issues/507).)

### Deprecated terms

A term is deprecated when it is typed `owl:DeprecatedClass` or `owl:DeprecatedProperty`, or has
`owl:deprecated` true: `true` or `1`, as an `xsd:boolean` or a plain string
(`owl:deprecated false` means the opposite, and `"TRUE"` is not a boolean). Every rule still
reports a deprecated term, **at info**, whatever the level: a withdrawn term is worth knowing
about, but not worth failing a gate over. A `severity:` override naming the rule in
`.rdf-lint.yml` still wins, so `severity: {missing-label: error}` makes a deprecated term's
missing label an error again. Run with `--fail-on info` to fail on them.

`catalogue.ttl` withdraws one class, and declares a property only as `owl:FunctionalProperty`:

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <https://example.org/catalogue#> .

ex:Item a owl:Class ;
    rdfs:label "Item" ;
    rdfs:comment "Something the catalogue lists." ;
    rdfs:subClassOf owl:Thing .

# Withdrawn: still reported, at info
ex:LegacyItem a owl:DeprecatedClass .

# Declared only by a characteristic: still a property
ex:shelfMark a owl:FunctionalProperty ;
    rdfs:label "shelf mark" .
```

```bash
rdf-construct lint --level strict catalogue.ttl
```

```text
Scanning 1 file(s)...

catalogue.ttl:11 info[orphan-class] ex:LegacyItem: Class has no rdfs:subClassOf declaration
catalogue.ttl:11 info[missing-label] ex:LegacyItem: Class lacks rdfs:label
catalogue.ttl:11 info[missing-comment] ex:LegacyItem: Class lacks rdfs:comment
catalogue.ttl:14 error[missing-comment] ex:shelfMark: Property lacks rdfs:comment

Found 1 error, 0 warnings, 3 info in 1 file
```

`--level strict` makes `ex:shelfMark`'s missing comment an error, and the run exits 1; the
withdrawn class's findings stay info.

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

Every rule name is checked. An unknown name in `--enable` or `--disable` is refused with exit 2 and
the list of available rules, as it already was in a config file:

```bash
rdf-construct lint ontology.ttl --enable orpahn-class
# Error: Unknown rule 'orpahn-class' in --enable. Available rules: circular-subclass, ...
```

A selection that leaves no rule to run is refused too, because a run with no rules would report
every file clean:

```bash
rdf-construct lint ontology.ttl --enable orphan-class --disable orphan-class
# Error: No lint rules left to run: enabled orphan-class; disabled orphan-class. A run with no
# rules would report every file clean.
```

On the command line, `--enable` **replaces** a config file's `enable:` list, while `--disable` **adds
to** its `disable:` list. A config that disables a rule, plus an `--enable` naming only that rule,
leaves nothing to run; the refusal says so. `--level` never changes which rules run.

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

# Namespaces whose terms are not this ontology's own
external_namespaces:
  - base:
  - http://purl.org/dc/terms/
```

`external_namespaces` lists namespaces that belong to someone else: a reference into one is never
reported as dangling, and its terms need no label or comment here. Each entry is a full IRI, an
IRI in angle brackets (`<urn:example:>`), or a CURIE such as `base:`, which is resolved against the
prefixes each linted file declares, plus `rdf`, `rdfs`, `owl`, `xsd` and `xml`. An entry matches at
a boundary, so `http://example.org/ont` takes `http://example.org/ont#X` but not
`http://example.org/ontology#X`. A malformed list or entry is refused with exit code 2 before any
file is read, and so is a CURIE whose prefix a linted file does not declare. See
[Whose terms are checked](#whose-terms-are-checked).

### Config File Discovery

The linter automatically searches for configuration files in this order:

1. Explicit `--config path/to/config.yml`
2. `.rdf-lint.yml` in current directory
3. `.rdf-lint.yaml` in current directory
4. Parent directories (up to filesystem root)

An option given on the command line overrides the config file, and the config file overrides the
option's default: a `.rdf-lint.yml` that says `level: strict` applies unless you pass `--level`.

## Whose terms are checked

A file declares terms it does not own. OWL 2 DL asks it to declare every annotation property it
uses, so `dcterms:creator a owl:AnnotationProperty`, or the `prov:wasDerivedFrom` that `order`,
`split` and `merge` stamp a derived file with, sits beside the ontology's own classes. `lint`
reports on the ontology's own terms only.

**A term is not the ontology's own** when either of these holds:

- **It is borrowed.** The file names an ontology (`<…> a owl:Ontology`), and none of its
  ontologies owns the term's namespace. An ontology owns everything on its own host, so
  `http://example.org/lib` owns `http://example.org/lib#Book` and `http://example.org/other#X`,
  and nothing on `http://purl.org/dc/terms/`. On `purl.org`, `w3id.org` and `www.w3.org`, which
  many publishers share, it owns only the space under its own IRI. **But a namespace the file
  describes is its own whatever the host:** where the file says something beyond `rdf:type`
  (a label, a superclass, a domain) about two or more terms in one namespace, those terms are
  its own. So an ontology at `<https://w3id.org/x/ontology>` keeps its terms at
  `https://w3id.org/x/`, while `dcterms:creator a owl:AnnotationProperty`, a declaration and
  nothing more, stays borrowed.
- **It is in an `external_namespaces` entry.**

`missing-label` and `missing-comment` skip such a term. `dangling-reference` never checks a
reference to one.

**`dangling-reference` checks a reference only where the file claims the namespace.** A
reference to an undefined term is reported when the term is the ontology's own and either:

- the file defines two or more entities (any IRI subject with an `rdf:type`) in the term's
  namespace, so a single node minted at a bare base namespace claims nothing; or
- the term lies within one of the file's own ontology IRIs, so a typo in a one-class ontology is
  still caught.

**References to documents are not term references.** The objects of `owl:imports`,
`owl:versionIRI`, `owl:priorVersion`, `owl:backwardCompatibleWith` and `owl:incompatibleWith`,
and every object of the ontology header's own triples (its `prov:wasDerivedFrom`,
`rdfs:seeAlso`, `dcterms:hasVersion` and the rest), are never reported.

### A worked example

`domain.ttl` imports a base vocabulary and adds two classes to it:

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix base: <https://example.org/base#> .
@prefix ex: <https://example.org/domain#> .

<https://example.org/domain> a owl:Ontology ;
    rdfs:label "Domain" ;
    owl:imports <https://example.org/base> ;
    dcterms:creator "A. Author" .

dcterms:creator a owl:AnnotationProperty .

# Two terms this file adds to the base vocabulary
base:Annex a owl:Class ;
    rdfs:label "Annex" ;
    rdfs:comment "A building joined to another." ;
    rdfs:subClassOf base:Structure .

base:Shed a owl:Class ;
    rdfs:label "Shed" ;
    rdfs:comment "A small outbuilding." ;
    rdfs:subClassOf base:Structure .

ex:Building a owl:Class ;
    rdfs:label "Building" ;
    rdfs:comment "A built structure." ;
    rdfs:subClassOf base:Structure .

ex:House a owl:Class ;
    rdfs:label "House" ;
    rdfs:comment "A dwelling." ;
    rdfs:subClassOf ex:Building, ex:Dwelling .
```

```bash
rdf-construct lint domain.ttl
```

```text
Scanning 1 file(s)...

domain.ttl:18 error[dangling-reference] base:Structure: Referenced entity is not defined in this ontology
domain.ttl:33 error[dangling-reference] ex:Dwelling: Referenced entity is not defined in this ontology

Found 2 errors, 0 warnings, 0 info in 1 file
```

`dcterms:creator` is borrowed, so it needs no label, and the `owl:imports` target is not a term
reference. But the file defines two classes in `base:`, so it claims that namespace, and
`base:Structure`, which the base vocabulary defines, is reported. Say that `base:` is someone
else's with `external.yml`:

```yaml
external_namespaces:
  - base:
```

```bash
rdf-construct lint domain.ttl -c external.yml
```

```text
Using config: external.yml
Scanning 1 file(s)...

domain.ttl:33 error[dangling-reference] ex:Dwelling: Referenced entity is not defined in this ontology

Found 1 error, 0 warnings, 0 info in 1 file
```

`ex:Dwelling` is a real finding: the file claims `ex:` and defines no such class.

### Known limitations

| Limitation | What you see | Issue |
|---|---|---|
| `lint` does not resolve `owl:imports`. A term an import defines is reported as dangling wherever the file claims its namespace. | On the public IES `ies-env-building.ttl`, `external_namespaces: [ies:]` clears the 46 `ies:` terms that `ies-common.ttl` 5.0.3 defines, and also the seven it does not (`ies:Flow`, `ies:Member` and five more), because they share one namespace. | [#309](https://github.com/aigora-de/rdf-construct/issues/309) |
| An ontology whose terms are off its header's host (or, on `purl.org`, `w3id.org` and `www.w3.org`, outside its header's IRI) and which describes fewer than two of them beyond their type is treated as borrowing them: its terms get no `missing-label`, no `dangling-reference`, no `docs` page and no count. | A skeleton such as `<https://w3id.org/x/ontology> a owl:Ontology` over bare `x:A a owl:Class` declarations. Labelling two of its terms makes them its own. | — |
| A file that describes two or more terms of another vocabulary claims that vocabulary. | A file that labels `prov:Entity` and `prov:used` owns `prov:`, so the `prov:wasDerivedFrom` stamp is asked for a label again. List the namespace in `external_namespaces`. | — |
| A file that names no ontology borrows nothing: every term in it is its own. | `dcterms:creator a owl:AnnotationProperty` with no `owl:Ontology` header still gets `missing-label`. List the namespace in `external_namespaces`. | — |
| Two publishers on one host are not told apart, except on `purl.org`, `w3id.org` and `www.w3.org`. | An ontology at `http://example.org/a` treats `http://example.org/b#` as its own. List it in `external_namespaces`. | — |

## Output Formats

### Text Output (default)

Human-readable output with optional colours:

```
ontology.ttl:12: warning[orphan-class]: 'Building' Class has no rdfs:subClassOf declaration
ontology.ttl:18: warning[missing-label]: 'hasFloor' Property lacks rdfs:label
ontology.ttl:24: info[property-no-domain]: 'builtIn' Object property has no rdfs:domain

Found 0 errors, 2 warnings, 1 info in 1 file
```

Disable colours for piping:

```bash
rdf-construct lint ontology.ttl --no-colour | tee results.txt
```

### JSON Output

Machine-readable output for CI integration. **`--format json` currently crashes**
([#201](https://github.com/aigora-de/rdf-construct/issues/201)); the shape below is what it will
write once that is fixed:

```bash
rdf-construct lint ontology.ttl --format json
```

```json
{
  "files": [
    {
      "path": "ontology.ttl",
      "parse_error": null,
      "issues": [
        {
          "rule": "orphan-class",
          "severity": "warning",
          "entity": "http://example.org/Building",
          "message": "Class has no rdfs:subClassOf declaration",
          "line": null
        }
      ],
      "summary": {"errors": 0, "warnings": 1, "info": 0}
    }
  ],
  "summary": {"errors": 0, "warnings": 1, "info": 0, "files": 1, "unparsed": 0}
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

With the default `--fail-on error`, a file with only warnings passes this hook. Add
`--fail-on, warning` to `args` to block on warnings as well.

## Listing Available Rules

```bash
rdf-construct lint --list-rules
```

Output:

```
Available lint rules:

  Structural
    orphan-class: warning - Class has no rdfs:subClassOf declaration
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
# During development - relaxed mode (warnings reported as info; every rule still runs)
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

An unknown name in `--enable`, `--disable`, or a config's `enable:`, `disable:` or `severity:` is
refused, and the message lists the available rules. Check them with `--list-rules`. Rule names are
case-sensitive and use hyphens.

### "No lint rules left to run" Error

Your `--enable`, `--disable` and config settings together select no rule at all. The message names
what was enabled and what was disabled. Remember that `--enable` on the command line replaces the
config's `enable:` list but `--disable` adds to its `disable:` list.

### Many False Positives

To run fewer checks, disable the rules that do not apply to your ontology:

1. Disable them in `.rdf-lint.yml` (`disable:`), so every run in the project agrees, or for a
   single run with `--disable`
2. Lower a rule's severity under `severity:` if you still want to see its findings without them
   failing your gate
3. If the findings are on another vocabulary's terms, list its namespace in
   `external_namespaces` (see [Whose terms are checked](#whose-terms-are-checked))

`--level relaxed` makes the output quieter, not shorter: warnings are reported as info, but every
rule still runs and every finding is still listed.

Before v0.7.0, relaxed also skipped the four rules whose default severity is info. To get that run
back, disable them alongside it:

```yaml
level: relaxed
disable: [redundant-subclass, property-no-domain, property-no-range, inconsistent-naming]
```

or for a single run:

```bash
rdf-construct lint ontology.ttl --level relaxed \
  --disable redundant-subclass --disable property-no-domain \
  --disable property-no-range --disable inconsistent-naming
```

### External References Flagged as Dangling

`lint` reads each file on its own and does not follow `owl:imports`, so naming the imported
ontology on the same command line changes nothing: each file is linted in its own graph. Add the
imported vocabulary's namespace to `external_namespaces` instead. See
[Whose terms are checked](#whose-terms-are-checked).

### Parse Errors

A file that cannot be parsed is reported in its place among the other files' results, in the
same words every command uses: the file, the format `lint` read it as, and the parser's own
message with the line. It is not a finding, so it is not counted in the errors; the summary line
counts it separately, and the run **exits 2**, whatever `--fail-on` says. Here `broken.ttl` uses
`owl:` without declaring it, beside the `catalogue.ttl` of [Deprecated terms](#deprecated-terms):

```turtle
@prefix ex: <https://example.org/catalogue#> .

ex:Item a owl:Class .
```

```bash
rdf-construct lint catalogue.ttl broken.ttl
```

```text
Scanning 2 file(s)...

catalogue.ttl:11 info[orphan-class] ex:LegacyItem: Class has no rdfs:subClassOf declaration
catalogue.ttl:11 info[missing-label] ex:LegacyItem: Class lacks rdfs:label
catalogue.ttl:11 info[missing-comment] ex:LegacyItem: Class lacks rdfs:comment
catalogue.ttl:14 warning[missing-comment] ex:shelfMark: Property lacks rdfs:comment

Could not parse broken.ttl as turtle: at line 3 of <>:
Bad syntax (Prefix "owl:" not bound) at ^ in:
"b'@prefix ex: <https://example.org/catalogue#> .\n\nex:Item a '^b'owl:Class .\n'"

Found 0 errors, 1 warning, 3 info in 2 files; 1 file could not be parsed
```

`lint` reads the format from the file's extension: `.ttl` and `.turtle` as Turtle, `.rdf`,
`.xml` and `.owl` as RDF/XML, `.nt` and `.ntriples` as N-Triples, `.n3` as N3, `.jsonld` and `.json` as JSON-LD,
and anything else as Turtle. If the message names a format the file is not in, rename the file.
Otherwise check:

1. File encoding (should be UTF-8)
2. The syntax at the line the message names

An empty Turtle or N-Triples file parses, to no triples, and is reported clean
([#512](https://github.com/aigora-de/rdf-construct/issues/512)); an empty RDF/XML or JSON-LD file is
not a valid document in its format, and exits 2. A directory is refused before any file is read.
