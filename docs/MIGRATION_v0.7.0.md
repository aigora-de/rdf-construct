# Migrating to v0.7.0

v0.7.0 breaks things deliberately, and does it once. The
[#126 audit](https://github.com/aigora-de/rdf-construct/issues/126) walked every command against
its own documentation and found behaviour that is silently wrong: an exit code of 1 that means
both "input rejected" and "completed with findings", command-line defaults that quietly overwrite
what a configuration file says, output written where nobody asked for it. Most of those fixes cannot land without changing what an existing script sees. Rather than
spread that across several releases, they ship together, behind one version and this one note.

The plan is tracking issue [#312](https://github.com/aigora-de/rdf-construct/issues/312), and the
work is milestone
[v0.7.0 - Hardening: every breaking fix, one migration](https://github.com/aigora-de/rdf-construct/milestone/3).

**This note is filled in as each fix lands, until v0.7.0 is tagged.** A section that says nothing
has landed yet means nothing there has changed *so far*, not that nothing will. Read
[Every command](#every-command) first, then the section for each command you use.

## Every command

These changes cut across several commands. Each lands in a single PR that covers every command it
touches, so the affected rows appear together.

### Exit codes

Exit codes are now consistent across every command ([#286](https://github.com/aigora-de/rdf-construct/issues/286)): **0** success, **1** the run
completed and has something to report, **2** the input was refused or the run failed. Previously
several commands rejected input with exit 1 — the same code others use for findings — and `lint`
reported error-severity findings as 2. `lint` gains `--fail-on` (default `error`) so a pipeline can
still gate on severity.

| Code | Meaning |
|---|---|
| `0` | The command did what you asked. |
| `1` | The command finished and has something to report: differences, conflicts, unmatched entities, failing questions, lint findings, entities not found. |
| `2` | The command did not do it: input refused, run failed, or a usage error. |

**What moved:** refusals in `order`, `uml`, `lint`, `merge`, `split`, `refactor` and
`localise config` (1 → 2); errors in `stats` and `shacl-gen` (1 → 2); and `lint`'s findings (see
[`lint`](#lint)). A refusal no longer prints `Aborted!`. A crash — an error no command handled —
exited 1, Python's default, which read as "finished with findings"; it now exits 2, with the
traceback still on stderr ([#320](https://github.com/aigora-de/rdf-construct/issues/320)). **What did not move:** every command's
"completed with findings" code was already 1, and `diff`, `cast`, `cq-test`, `describe` and
`puml2rdf` are unchanged. `docs` still reports malformed input as a traceback, now at 2, until
[#301](https://github.com/aigora-de/rdf-construct/issues/301) lands.

**What to do:** anywhere a script tests for `1` to detect a rejected command line or config, test
for `2` instead. Anywhere it tests `lint` for `2`, read the [`lint`](#lint) section.

| Issue | What changed | What to do |
|---|---|---|
| [#320](https://github.com/aigora-de/rdf-construct/issues/320) | Every command: a crash (an error no command handled) exits **2** instead of 1, with `Error: rdf-construct flatlined: …` and the traceback on stderr. Exit 1 now always means the run finished with something to report. | If a script treats 1 as "findings, carry on", a crash now fails it instead, which is the intent. A script that tests for non-zero is unaffected. |

### Default output directories

Not landed yet. How `docs`, `uml`, `split` and `order` treat a default output directory that
already holds something else:
[#261](https://github.com/aigora-de/rdf-construct/issues/261) (PR group P12). `order`'s default
directory has already moved; see [`order`](#order).

### Command-line flags versus configuration files

Not landed yet. A flag will override the configuration file only when you actually pass it; today
a command-line default can silently overwrite a value the configuration file sets:
[#160](https://github.com/aigora-de/rdf-construct/issues/160),
[#206](https://github.com/aigora-de/rdf-construct/issues/206),
[#225](https://github.com/aigora-de/rdf-construct/issues/225),
[#251](https://github.com/aigora-de/rdf-construct/issues/251) and
[#291](https://github.com/aigora-de/rdf-construct/issues/291) (PR group P9).

## `cast`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `order`

| Issue | What changed | What to do |
|---|---|---|
| [#128](https://github.com/aigora-de/rdf-construct/issues/128) | Without `-o/--outdir`, output is written to `ordered/` instead of `src/ontology/`. An explicit `-o` is unaffected. | Pass `-o src/ontology` to keep the previous location, or point whatever reads the output at `ordered/`. See the [Order Guide](user_guides/ORDER_GUIDE.md). |
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | A refusal exits **2** instead of 1: an unknown `-p/--profile`, or an invalid `unclaimed:` policy. | If a script tests for exit 1 to catch a rejected invocation, test for 2. |
| [#339](https://github.com/aigora-de/rdf-construct/issues/339) | `sort: topological` ignores a term that is its own subclass or subproperty (`C rdfs:subClassOf C`, which RDFS inference adds for every class and property). Before, each such term and everything beneath it came out alphabetical, so an inferred graph was effectively unsorted. Graphs without such triples are unchanged. | Nothing, unless you compare against `order` output previously generated from an inferred graph: expect a one-off reorder into hierarchical order. |

## `profiles`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `uml`

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | A refusal exits **2** instead of 1: an unknown `-c/--context`, `-s/--style` or `-l/--layout`. The list of accepted names now goes to stderr. | If a script tests for exit 1 to catch a rejected invocation, test for 2. |

## `contexts`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `lint`

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | **Error-severity findings exit 1, not 2.** A run with only warnings exits **0**, not 1. A new `--fail-on error\|warning\|info\|never` (default `error`) sets the lowest severity that exits 1. A refusal (a config that will not load, `--init` over an existing file) exits **2** instead of 1. | Gate on findings with `-ne 0` or `--fail-on`, not by testing for 2. To keep failing on warnings, pass `--fail-on warning`. `--level strict` still turns warnings into errors, so `--level strict` pipelines still fail on them. |
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | Python API: `LintSummary.exit_code` is removed. The engine reports severities, and the CLI decides the exit code. | Read `total_errors`, `total_warnings` and `total_info` instead. |
| [#302](https://github.com/aigora-de/rdf-construct/issues/302) | `orphan-class` defaults to `warning`, not `error`. A root class is not a defect. A run whose only errors were `orphan-class` now exits **0**. | To keep it as an error, set `severity: {orphan-class: error}` in `.rdf-lint.yml`, or use `--level strict`. |

## `diff`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `docs`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `shacl-gen`

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | Errors (a missing file, a configuration that will not load, a failed generation) exit **2** instead of 1. | Test for 2. |

## `puml2rdf`

| Issue | What changed | What to do |
|---|---|---|
| [#150](https://github.com/aigora-de/rdf-construct/issues/150) | `package "http://example.org/x#" as pfx` now means "namespace URI `http://example.org/x#`, prefix `pfx`", as the guide documents. It was read the other way round: the URI became the package name, `pfx` was discarded, and the whole URI was bound as a `@prefix`, so the output could not be parsed by any tool — at exit 0, with a success message. `package "URI" { … }` with no alias now binds a shortened prefix (the URI's last segment) instead of the URI. | Re-run the conversion. The previous output was unreadable, so there is nothing to diff against: classes now land in the declared namespace under the alias (`bld:Building` in the guide's example). A diagram that relied on the whole URI appearing as a prefix name was relying on a file nothing could read. |

## `cq-test`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `stats`

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | Errors, including `--compare` with other than two files, exit **2** instead of 1. | Test for 2. |

## `describe`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `merge`

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | A refusal exits **2** instead of 1: no sources, a config that will not load (including malformed YAML, which was a traceback), `--init` over an existing file. | If a script tests for exit 1 to catch a rejected invocation, test for 2. |

## `split`

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | A refusal exits **2** instead of 1: neither `--by-namespace` nor `--config`, a config that will not load (including malformed YAML, which was a traceback), `--init` over an existing file. | If a script tests for exit 1 to catch a rejected invocation, test for 2. |

## `refactor`

Covers `refactor rename` and `refactor deprecate`; each row names its subcommand.

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | `rename`: a refusal exits **2** instead of 1: unpaired `--from`/`--to` or `--from-namespace`/`--to-namespace`, nothing to rename, a config that will not load (including malformed YAML), `--init` over an existing file. `--help` no longer documents an exit 1, which no path produced ([#183](https://github.com/aigora-de/rdf-construct/issues/183)). | If a script tests for exit 1 to catch a rejected invocation, test for 2. |
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | `deprecate`: a refusal exits **2** instead of 1: no `--entity`, nothing to deprecate, a config that will not load (including malformed YAML), `--init` over an existing file. "Entity not found" still exits 1. | If a script tests for exit 1 to catch a rejected invocation, test for 2. |

## `localise`

Covers `localise extract`, `merge`, `report`, `init` and `config`; each row names its subcommand.

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | `config`: `--init` over an existing `localise.yml` exits **2** instead of 1. | If a script tests for exit 1 to catch a rejected invocation, test for 2. |
