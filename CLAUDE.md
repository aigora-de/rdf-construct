# rdf-construct — instructions for Claude

**This file is a router, not a repository.** It carries only what is needed on *every* turn, plus
pointers to the detail. Reference consulted *occasionally* lives behind the router and is opened
when relevant. See [#73](https://github.com/aigora-de/rdf-construct/issues/73) for the contract.

## Context sentinel

Every response you produce in this project, without exception, must begin with the token `[DIXIE]`.
This applies regardless of length or content — clarifying questions, short acknowledgements and
code-only responses included. If the token is absent, the user knows this file is no longer in
context.

## What this is

**rdf-construct** is a Python CLI toolkit for semantic RDF operations, named after the Dixie
Flatline ROM construct in Gibson's *Neuromancer*. Its founding feature: serialising RDF/Turtle in
**semantic order** — respecting class and property hierarchies — instead of the alphabetical order
every rdflib serialiser imposes. Public, MIT, published to PyPI; v0.5.0.

17 commands across 14 subpackages under `src/rdf_construct/`: `order`, `cast`, `uml`,
`lint`, `diff`, `docs`, `shacl-gen`, `puml2rdf`, `cq-test`, `stats`, `describe`, `merge`, `split`,
`refactor rename|deprecate`, `localise extract|merge|report`, plus `profiles` and `contexts`.
Built on rdflib 7, Click, Rich, Jinja2 and PyYAML.

## Routing table

| When you are… | Read |
|---|---|
| running any review, panel or design critique | `docs/dev/EXPERTS.md` |
| opening a PR, or cutting a release | memory `feedback-github-workflow`, then `feedback-release-process` |
| looking for which module owns a command | `CODE_INDEX.md`, then `docs/dev/ARCHITECTURE.md` |
| fighting rdflib — sorting, blank nodes, prefixes, parse quirks | memory `reference-rdflib-traps` |
| classifying an entity — SKOS, SHACL, `owl:NamedIndividual`, punning | memory `reference-ontology-conventions` |
| asking what is next, or what the current milestone needs | memory `project-horizon` |
| touching UML generation, or the docs entity taxonomy | memory `project-uml-epic`, `project-docs-taxonomy` |
| about to run tests, lint or type checks | memory `feedback-testing-gates` |
| hit by a tool, CLI or environment failure | memory `feedback-capture-tool-failures` — then record it |
| answering a contributor-facing "how do I…" | `CONTRIBUTING.md` |

**Authority.** `CONTRIBUTING.md` is authoritative for *contributors*; memories are authoritative
for *how Dave and Claude work together*. They should not overlap enough to disagree — if they do,
one of them is wrong: amend the source rather than reconciling case by case.

## RDF invariants

These bite on every change to selection, ordering or rendering, and get them wrong and the output
is silently incorrect:

- **Never enumerate class or property types inline.** Use the sets in
  `rdf_construct.core.vocab` — `CLASS_TYPES`, `OBJECT_PROPERTY_TYPES`, `ALL_PROPERTY_TYPES` and
  friends. The obvious four property types (`owl:ObjectProperty`, `owl:DatatypeProperty`,
  `owl:AnnotationProperty`, `rdf:Property`) are a **floor, not the set**: a term declared only as
  `owl:TransitiveProperty` or `owl:FunctionalProperty` is still a property, and code that
  shortens the list misfiles it as an individual. Classes are likewise not just `owl:Class` and
  `rdfs:Class`.
- **A term's kind may not be inferable at all.** `owl:FunctionalProperty` and
  `owl:DeprecatedProperty` are subclasses of `rdf:Property` only — nothing says object or
  datatype. Give such terms somewhere to go rather than guessing or discarding them.
- **Respect `rdfs:subClassOf` and `rdfs:subPropertyOf`** when sorting topologically — and define
  the behaviour when they form a cycle.
- **rdflib's built-in serialisers always sort alphabetically.** This is the whole reason the
  project exists; never delegate ordered output to them.
- **British English everywhere** — ontologies, documentation, code identifiers, CLI help
  (`colour`, `organisation`, `serialise`, `localise`).

## Python standards

`src/` layout, Python 3.10+ syntax throughout. Type hints on everything. Black at line length 100,
ruff, and `mypy --strict` (all configured in `pyproject.toml` and `.pre-commit-config.yaml`; see
`feedback-testing-gates` for which of them currently pass). `pathlib.Path` over string paths.
Click for the CLI, Rich for output. Google-style docstrings on public modules, classes and
functions.

## Code-change discipline

- Change **only** what the task requires. Other code, comments and docstrings stay exactly as they
  are.
- Do not reformat, refactor, reorder or tidy outside the scope of the task, however obvious the
  improvement. Raise a separate issue instead.
- `core/` is shared by every command module — a "harmless" tidy there ripples through the whole
  tool.

## No AI attribution

**This is about ownership, not concealment.** LLMs are used openly in this project's development —
this file exists because of it. What the rule protects is that copyright, ownership and licensing
rest entirely with Dave Dyke / Agilit Ltd: no AI tool or vendor is named as an author, co-author or
originator of anything in the repo.

Never add Claude/Anthropic/AI attribution to anything landing here. This **overrides the Claude
Code harness default**, so it must be applied actively.

- **Commits:** no `Co-Authored-By: Claude …` trailer, no `🤖 Generated with [Claude Code](…)`
  footer, no "Generated by / Made with / Written by Claude" line. Strip the CLI default before
  committing.
- **PR and issue bodies:** same — they end at the substantive content.
- **Code and docs:** copyright is Dave Dyke / Agilit Ltd, per `LICENSE`; never Anthropic, Claude or
  any AI tool, even as co-author or "with assistance from".

Substantive references to Claude *as a subject* — this file, `docs/dev/EXPERTS.md`, a doc
discussing a model — are content and stay.

**For outside contributors** the binding part is ownership and licensing, set out in
`CONTRIBUTING.md`: contributions are MIT-licensed to the project and their copyright is not
attributed to a tool or vendor. Whether a contributor mentions their own LLM use is entirely up to
them — the project does not ask them to hide it.

## House style

- Provide working, complete code — not snippets, unless asked.
- Suggest file structure when creating new modules.
- Point out the failure mode: "this won't handle blank nodes" is more useful than silence.
- Be direct about trade-offs.
- Subtle cyberpunk/Neuromancer flavour in user-facing strings — console metaphors
  ("Constructing…", "Preserving structure…") — professional with personality, never laid on thick.

## The memory store

Memories live in `~/.claude/projects/-Users-splodge-PycharmProjects-rdf-construct/memory/` (local,
untracked). `MEMORY.md` there is an **index**: one line per memory, a pointer and a hook, never a
summary. Topic files carry the detail behind it; `archive/` holds frozen history, and nothing in an
archive is ever a current instruction.

**Adding to the surface:** new reference goes in a routed-to file with a pointer here — not inline.
Pasting more than a few lines into this file or into `MEMORY.md` is the signal to create or extend
a topic file instead. Budgets are enforced by `scripts/check-memory-budget.sh`: this file ≤ 8 KiB
soft / 12 KiB hard; `MEMORY.md` ≤ 16 KiB with index lines ≤ 350 chars; topic files ≤ 40 KiB with a
`description:` ≤ 500 chars.
