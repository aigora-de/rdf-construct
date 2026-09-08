# Order Guide

The `order` command serialises RDF/Turtle in **semantic order** — respecting class and property
hierarchies — instead of the alphabetical order every rdflib serialiser imposes. It is the founding
feature of rdf-construct, and the one command that never delegates its output to rdflib.

Ordering is driven by a YAML configuration file. That file is where all the difficulty lives, and
it is what most of this guide is about.

> **Every fenced command in this guide runs verbatim**, from the repository root, against material
> in `examples/order/`. The sample output was captured from those runs, not written by hand.

## Quick Start

```bash
# List the profiles a configuration defines
rdf-construct profiles examples/order/ordering.yml

# Generate every profile in the configuration
rdf-construct order examples/order/library.ttl examples/order/ordering.yml

# Generate one profile, to a directory of your choosing
rdf-construct order examples/order/library.ttl examples/order/ordering.yml -p hierarchy -o build/
```

The first writes nothing; the second writes one file per profile into `ordered/`.

## Why this exists

Every rdflib serialiser sorts subjects alphabetically. For an ontology that means a file in which
`Anthology` precedes `Work` — a subclass four levels down printed before the class it descends
from — and in which a property appears before the property it specialises. The structure the
ontology asserts is invisible in the file that carries it.

`order` writes the same graph with the structure showing. Nothing is added, removed or rewritten:

```bash
rdf-construct order examples/order/library.ttl examples/order/ordering.yml -p alpha -p hierarchy
```

```
Loading examples/order/library.ttl...
Constructing profile: alpha
  ✓ ordered/library-alpha.ttl
Constructing profile: hierarchy
  ✓ ordered/library-hierarchy.ttl

Constructed 2 profile(s) in ordered/
```

The class order in each:

| `alpha` | `hierarchy` |
|---|---|
| `lib:Anthology` | `lib:Work` |
| `lib:Article` | `lib:Article` |
| `lib:Book` | `lib:Book` |
| `lib:Journal` | `lib:Anthology` |
| `lib:Work` | `lib:Journal` |

Both files contain all 57 triples of the source and are isomorphic to it. Only the order differs.

## CLI Reference

```bash
rdf-construct order [OPTIONS] SOURCE CONFIG
```

### Arguments

| Argument | Description |
|---|---|
| `SOURCE` | Input RDF **Turtle** file. Other RDF syntaxes are not read — use `cast` first. |
| `CONFIG` | YAML configuration file defining ordering profiles |

### Options

| Option | Default | Description |
|---|---|---|
| `-p, --profile NAME` | all profiles | Profile to generate. Repeatable. |
| `-o, --outdir PATH` | `ordered` | Output directory |

### Output files

One file per profile, named `<source-stem>-<profile>.ttl`. The naming is fixed and not configurable,
so `library.ttl` with a profile called `hierarchy` produces `ordered/library-hierarchy.ttl`.

`-o` **creates parent directories as needed**, so `-o build/ontology/ordered` works without
`mkdir -p`. This was reviewed deliberately (issue #128): the run prints every file it writes and
the directory it wrote them to, so a mistyped `-o` is misdirected but never silent.

A profile name that does not exist is rejected before anything is written:

```bash
rdf-construct order examples/order/library.ttl examples/order/ordering.yml -p alpah
```

```
Error: Profile 'alpah' not found in config.
Available profiles: alpha, hierarchy, anchored, schema-only, classes-only
Aborted!
```

## The configuration file

Four top-level keys are read: `defaults`, `selectors`, `prefix_order` and `profiles`. Anything else
is ignored silently.

```yaml
defaults:
  unclaimed: warn

selectors:
  classes:     "owl:Class, rdfs:Class and owl:DeprecatedClass"
  obj_props:   "owl:ObjectProperty, plus the six object-property characteristics"
  individuals: "everything that is not a class or a kind-specific property"

profiles:
  hierarchy:
    description: "Parents before children."
    sections:
      - header: {}
      - classes:           {select: classes,     sort: topological}
      - object_properties: {select: obj_props,   sort: topological}
      - individuals:       {select: individuals, sort: alpha}
```

`examples/order/ordering.yml` is the full version of that file, and every example below uses it.

### Sections

A profile is an ordered list of sections. Each section claims a set of subjects and sorts them; the
output is the sections concatenated, in the order written. A subject is claimed by the **first**
section that selects it, so sections never duplicate.

Three keys are read on a section, plus one special section name:

| Key | Default | Description |
|---|---|---|
| `select` | the section's own name | Which selector to use |
| `sort` | `qname_alpha` | `alpha`/`qname_alpha`, or `topological`/`topological_then_alpha` |
| `roots` | none | CURIEs whose branches are emitted first, in the order listed |

`header: {}` is a section name with a fixed meaning: it claims the `owl:Ontology` subjects, so the
ontology's own metadata leads the file. It takes no keys.

The section's *name* is free text and appears nowhere in the output — it is a label for you, and the
default value of `select`. Writing `- classes: {sort: alpha}` and `- classes: {select: classes,
sort: alpha}` are the same thing.

## Selectors

**This is the part of the configuration most likely to mislead you.**

There are exactly **six** selectors, and they are built in:

| Selector | Claims |
|---|---|
| `classes` | `owl:Class`, `rdfs:Class`, `owl:DeprecatedClass` |
| `obj_props` | `owl:ObjectProperty`, and terms declared only by an object-property characteristic — `owl:TransitiveProperty`, `owl:SymmetricProperty`, `owl:AsymmetricProperty`, `owl:ReflexiveProperty`, `owl:IrreflexiveProperty`, `owl:InverseFunctionalProperty` |
| `data_props` | `owl:DatatypeProperty` |
| `ann_props` | `owl:AnnotationProperty` |
| `other_props` | Properties whose *kind* is not implied by their declaration — `rdf:Property`, `owl:FunctionalProperty`, `owl:DeprecatedProperty` — and which no kind-specific selector claimed |
| `individuals` | Everything that is not a class or a kind-specific property |

**You cannot define a selector of your own.** Selection dispatches on these six *key names*. The
values in the `selectors:` block are documentation for the reader — the tool does not parse them,
and changing one changes nothing. A configuration that renames `obj_props` to `object_properties`
in the `selectors:` block fails:

```
✗ profile 'x', section 'y': unknown selector 'object_properties'. Built-in selector keys:
classes, obj_props, data_props, ann_props, other_props, individuals. Defined in this config: …
```

That error is deliberate (issue #89). A selector that resolved to nothing used to select nothing
silently, which is indistinguishable from "this ontology has none of those" and made the section
vanish from the output.

### Why `other_props` matters

The four obvious property types are a **floor, not the set**. A term declared only as
`owl:TransitiveProperty` is still an object property, and `obj_props` claims it. But
`owl:FunctionalProperty` and `owl:DeprecatedProperty` are subclasses of `rdf:Property` only —
nothing says whether such a term is an object or a datatype property, and guessing would be wrong.

`other_props` is where those terms go. `examples/order/library.ttl` carries one,
`lib:catalogueNumber`, declared only as `owl:FunctionalProperty`.

The distinction between `lib:cites` and `lib:catalogueNumber` in that file is worth understanding,
because it is the whole reason two selectors exist rather than one:

- **`lib:cites a owl:TransitiveProperty`** is under-declared but not ambiguous.
  `owl:TransitiveProperty` is a subclass of `owl:ObjectProperty` in OWL 2, so the declaration is
  entailed and `obj_props` claims it correctly.
- **`lib:catalogueNumber a owl:FunctionalProperty`** is genuinely ambiguous. Functionality applies
  to object *and* datatype properties, so nothing here says which this is, and no amount of
  inference will settle it. `other_props` exists so such a term has somewhere to go that is not a
  guess — and not the individuals bucket, which is where a shortened type list would put it.

Both are legal RDF and both are common in older and hand-maintained ontologies. Declaring the kind
explicitly as well is better practice in a new ontology; these are written this way because handling
the input as it arrives is the point.

A profile with no `other_props` section does not lose the term — `individuals` still claims it, so
it is emitted — but it is filed under individuals, which is not what it is. Give it a section.

## Sorting

`sort: alpha` (or `qname_alpha`) orders by qualified name. It is the right choice when the file's
job is to produce small, readable diffs between versions.

`sort: topological` orders parents before children over `rdfs:subClassOf`, and super-properties
before sub-properties over `rdfs:subPropertyOf`. Ties are broken alphabetically, so the output is
deterministic — the same input always produces the same file, in any process.

> **Check the spelling.** Exactly four values are understood: `alpha`, `qname_alpha`, `topological`
> and `topological_then_alpha`. Anything else — a typo, or the reasonable-looking `topo` — currently
> means **alphabetical**, silently, at exit 0 ([#242](https://github.com/aigora-de/rdf-construct/issues/242)).
> If a profile is not ordering the way you expect, this is the first thing to check.

Which of the two hierarchy predicates a section uses is decided per section, from the types of the
subjects it claimed. In practice: class sections walk `rdfs:subClassOf`, property sections walk
`rdfs:subPropertyOf`.

### Leading with a branch: `roots`

`roots` names one or more CURIEs whose descendants are emitted first, as contiguous branches, in the
order you list them. Everything else follows topologically.

```bash
rdf-construct order examples/order/library.ttl examples/order/ordering.yml -p anchored
```

The `anchored` profile declares `roots: ["lib:Journal"]`, and the class order becomes:

```
lib:Journal  lib:Work  lib:Article  lib:Book  lib:Anthology
```

against `hierarchy`'s `lib:Work  lib:Article  lib:Book  lib:Anthology  lib:Journal`.

**Root CURIEs are resolved against the prefixes of the parsed source file.** A root that does not
resolve, or that resolves to a term the ontology does not contain, is skipped without a message —
see [Known limitations](#known-limitations), because there is a trap here worth knowing about.

## Unclaimed subjects

A profile whose sections do not, between them, claim every subject will drop triples. The
`unclaimed` policy decides what happens then. Set it in `defaults:` for the whole file, or on an
individual profile, which wins:

| Policy | Behaviour |
|---|---|
| `warn` | Emit what was claimed and report the loss on stderr. **The default.** |
| `emit` | Append the unclaimed subjects in a trailing section. Nothing is ever lost. |
| `ignore` | Emit what was claimed, silently. For a profile that filters deliberately. |

The `schema-only` profile omits the individuals section, so it warns:

```bash
rdf-construct order examples/order/library.ttl examples/order/ordering.yml -p schema-only
```

```
Loading examples/order/library.ttl...
Constructing profile: schema-only
  ⚠ profile 'schema-only': 2 subjects claimed by no section — 7 triples dropped.
      lib:GreatExpectations  (lib:Book, owl:NamedIndividual)
      lib:NatureJournal  (lib:Journal, owl:NamedIndividual)
    add a section with `select: individuals`,
    or set `unclaimed: emit` to keep them, or `unclaimed: ignore` if this profile filters deliberately.
  ✓ ordered/library-schema-only.ttl
```

The exit code stays 0 — the output is valid and the loss was reported, so a warning is the honest
answer rather than a failure.

This policy exists because of issue #84, where a shipped example dropped 68 triples of an ontology
at exit 0 with nothing said. The distinction it makes is between a **partial ontology**, which is
usually a mistake, and a **different ontology**, which is a deliberate extract. `ignore` is how you
declare the second.

### Blank nodes are never dropped

Blank-node closure is **unconditional and separate from the `unclaimed` policy**. Blank nodes carry
no identity a section could select them by — they belong to the description of whatever references
them — so every blank node reachable from a claimed subject is pulled in whatever the policy says.

This matters more than it sounds. `classes-only` is an extract that keeps 24 of 57 triples and drops
`lib:publishes` entirely, yet:

```turtle
lib:Journal
    a owl:Class ;
    rdfs:label "Journal"@en ;
    rdfs:subClassOf
        [
            a owl:Restriction ;
            owl:onProperty lib:publishes ;
            owl:someValuesFrom lib:Article
        ] ,
        lib:Work .
```

The restriction survives whole. Without this, an extract could reduce `rdfs:subClassOf [ … ]` to
`rdfs:subClassOf [ ]` — replacing a real axiom with the tautology `Journal ⊑ ⊤`, which asserts
something the source never said.

## Prefixes

Only prefixes **actually used** by the emitted triples are declared. `classes-only` drops the
datatype properties, so `xsd:` disappears from its header — there is no clutter of unused
declarations (issue #50):

```turtle
@prefix lib: <http://example.org/library#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
```

Declarations use Turtle's `@prefix` form, never SPARQL's `PREFIX` (issue #57). Turtle permits both;
mixing them is what caused that bug, and the rule now is that `order` emits `@prefix` only.

Prefix declarations are emitted in alphabetical order. The `prefix_order` key exists and does not
currently change this — see [Known limitations](#known-limitations).

## Hierarchy cycles

A cycle in `rdfs:subClassOf` or `rdfs:subPropertyOf` has defined, deterministic behaviour: the terms
that could be ordered are emitted first, and the members of the cycle follow, alphabetically. No
triple is lost and the run exits 0.

**This is not an error condition.** Mutual `rdfs:subClassOf` between two classes entails
`owl:equivalentClass` — asserting a cycle is an unusual but legitimate way of saying a set of
classes are equivalent. What is true is narrower: there is no parent-before-child order over a set
of mutually subsuming classes, so `order` falls back to alphabetical for those terms.

If you did not intend the cycle, `rdf-construct lint` reports it. `order` does not currently say
anything about it (issue #250).

## What `order` deliberately does not do

- **It is not a reasoner.** No entailments are computed and nothing is materialised. Terms are
  classified by their asserted `rdf:type` triples only, so a class that is only *inferably* a class
  is not claimed by `classes`.
- **It does not rewrite terms.** No IRI, literal, language tag or datatype is changed. Use
  `refactor` to rename and `localise` to manage language tags.
- **It does not change serialisation format.** Turtle in, Turtle out. Use `cast` to convert.
- **It does not give an extract its own identity.** A filtering profile's output keeps the source's
  `owl:Ontology` header verbatim — the same IRI, the same `owl:versionIRI`, the same
  `owl:imports` — while containing only part of the ontology. `ordered/library-classes-only.ttl`
  declares itself to be `<http://example.org/library>` version `1.0.0`, exactly as the full file
  does.

  Under the open-world assumption nothing it asserts is false, which is why this is easy to miss.
  But load it alongside the real 1.0.0 and nothing distinguishes them, and its surviving
  `owl:Restriction` refers to `lib:publishes`, which the extract no longer declares. **This is an
  open design question — issue #90 — not settled behaviour.** If you publish extracts, give them
  their own identity yourself for now.

## The founding invariant

`order` never delegates its output to an rdflib serialiser. Every other command in the toolkit that
writes Turtle has to be examined on this point (issue #95); `order` is the reference
implementation. Its output goes through `core/serialiser.py::serialise_turtle()`, which is the
module that exists because rdflib cannot do this.

A practical consequence: if you find `order` producing alphabetical output from a profile that asks
for `topological`, that is a bug, not a fallback to rdflib. Check the `sort:` spelling first — see
below.

## Known limitations

These are open issues, current as of v0.6.0. They are here because a guide that describes intended
behaviour is worse than no guide.

**This table is a maintenance contract: a fix that lands should delete its row in the same PR.** If
it is still growing three releases from now, that is the signal, not the table.

| Issue | Behaviour today |
|---|---|
| [#242](https://github.com/aigora-de/rdf-construct/issues/242) | A `sort:` value the tool does not recognise **silently means alphabetical**. Only `alpha`, `qname_alpha`, `topological` and `topological_then_alpha` are understood — `topo` and a typo both give you alphabetical order at exit 0. If a profile is not ordering as expected, check this spelling first. |
| [#238](https://github.com/aigora-de/rdf-construct/issues/238) | `prefix_order` does not change the order prefixes are emitted in; output is always alphabetical. `defaults.preserve_prefix_order` has no observable effect either. |
| [#239](https://github.com/aigora-de/rdf-construct/issues/239) | A source prefix that collides with one rdflib binds by default — `org`, `dc`, `foaf`, `skos`, `time`, `geo`, `prov`, `dcat` and others — is **renamed** in the output, so `@prefix org:` comes back as `@prefix org1:`. The graph is unchanged and isomorphic; the CURIEs in the file are not. `lib:` in these examples is unaffected. |
| [#241](https://github.com/aigora-de/rdf-construct/issues/241) | A `roots:` entry that does not resolve, or that names a term absent from the ontology, is skipped with no message. Combined with #239 this bites: a `roots:` written with your source's own prefix can resolve somewhere else entirely. |
| [#243](https://github.com/aigora-de/rdf-construct/issues/243) | Eleven keys accepted in profiles and sections are read by nothing: `tie_breaker`, `comment_blocks`, `bnode_strategy`, `anchors`, `after_anchors`, `cluster`, `within_level`, `group_by`, `group_order`, `explicit_group_sequence`, `within_group_tie`. They appear in `examples/order/sample_profile.yml` and `examples/order/ies_profile.yml`, where they make two profiles byte-identical to two others. **`examples/order/ordering.yml`, used throughout this guide, contains only keys that work.** |
| [#247](https://github.com/aigora-de/rdf-construct/issues/247) | A `selectors:` value beginning `FILTER` is matched by prefix only; the expression is never parsed, and such a selector claims every individual regardless of what it says. |
| [#245](https://github.com/aigora-de/rdf-construct/issues/245) / [#262](https://github.com/aigora-de/rdf-construct/issues/262) | A section containing **only** properties declared by an OWL characteristic is sorted over `rdfs:subClassOf` rather than `rdfs:subPropertyOf`, so its hierarchy is ignored; and such terms are given the individuals' `predicate_order` specification. A mixed section, like the ones in this guide, is unaffected. |
| [#246](https://github.com/aigora-de/rdf-construct/issues/246) | `predicate_order` entries must be written as bare CURIEs. Full IRIs and `<bracketed IRIs>` are silently dropped, though `roots:` accepts all three forms. |
| [#244](https://github.com/aigora-de/rdf-construct/issues/244) | `examples/order/basic_ordering.py` does not run. Use the [programmatic snippet below](#programmatic-use) instead. |

[#264](https://github.com/aigora-de/rdf-construct/issues/264) tracks all of these, with the order
they should be fixed in.

## Programmatic use

The ordering machinery is importable. This runs from the repository root:

```python
from pathlib import Path

from rdflib import Graph
from rdf_construct.core import (
    OrderingConfig,
    bnode_closure,
    build_section_graph,
    select_subjects,
    serialise_turtle,
    sort_subjects,
)

config = OrderingConfig(Path("examples/order/ordering.yml"))
profile = config.get_profile("hierarchy")

graph = Graph(bind_namespaces="none")
graph.parse("examples/order/library.ttl", format="turtle")

ordered: list = []
seen: set = set()

for section in profile.sections:
    name, cfg = next(iter(section.items()))
    cfg = cfg or {}
    if name == "header":
        from rdflib import RDF
        from rdflib.namespace import OWL
        chosen = list(graph.subjects(RDF.type, OWL.Ontology))
    else:
        chosen = list(select_subjects(graph, cfg.get("select", name), config.selectors))
    chosen = [s for s in chosen if s not in seen]
    for subject in sort_subjects(graph, set(chosen), cfg.get("sort", "qname_alpha"), cfg.get("roots")):
        if subject not in seen:
            ordered.append(subject)
            seen.add(subject)

# Blank nodes belong to whatever references them — pull them in unconditionally.
for node in bnode_closure(graph, ordered):
    ordered.append(node)
    seen.add(node)

serialise_turtle(build_section_graph(graph, ordered), ordered, Path("library-hierarchy.ttl"))
print(f"Wrote library-hierarchy.ttl with {len(ordered)} subjects")
```

```
Wrote library-hierarchy.ttl with 17 subjects
```

Two things worth copying from it: parse with `bind_namespaces="none"`, or rdflib's well-known
prefixes will displace your own (#239); and run `bnode_closure` before serialising, or a filtering
selection can strip the interior of a class expression.

That the snippet is this long is itself a finding rather than a style choice — there is no public
"order this graph with this profile" entry point, so a library user has to re-derive the section
loop, and re-deriving it is how the shipped script came to omit the blank-node closure (#244).
Settling what the package exposes is part of
[#263](https://github.com/aigora-de/rdf-construct/issues/263).

## Starting from the template

`templates/ordering_starter.yml` is a commented starting point with two profiles, `hierarchical` and
`alphabetical`. Copy it and edit:

```bash
cp templates/ordering_starter.yml my-ordering.yml
rdf-construct order examples/order/library.ttl my-ordering.yml -o ordered/
```

Two things to know about that file. Its `selectors:` block writes YAML **lists** where the shipped
examples write strings — both work, because neither is read, but do not take the list form as a
grammar you can extend. And it declares no `unclaimed:` key, so a configuration derived from it gets
the default `warn`, which is what you want while you are still adding sections.

The template is not installed with the package; it lives in the repository.

## Relationship to Other Commands

| Command | Purpose |
|---|---|
| `order` | Reorder Turtle with semantic structure; no format change, no term changes |
| `cast` | Change serialisation format; no semantic processing |
| `refactor` | Rename terms and namespaces |
| `split` | Divide an ontology into modules, each with its own identity |
| `lint` | Check ontology quality, including hierarchy cycles; read-only |
| `diff` | Compare two versions semantically; ordering makes its output easier to read |

A common pairing is `order` before `diff`, or `order` as the last step before committing, so that
version-control diffs show what actually changed rather than what moved.

## See Also

- [CLI Reference](CLI_REFERENCE.md) — Full command documentation
- [Getting Started](GETTING_STARTED.md) — Installation and setup
- [Quick Reference](QUICK_REFERENCE.md) — Cheat sheet
- [Cast Guide](CAST_GUIDE.md) — Format conversion
- [Merge and Split Guide](MERGE_SPLIT_GUIDE.md) — Combining and modularising ontologies
- [Lint Guide](LINT_GUIDE.md) — Quality checks, including `circular-subclass`
