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
`puml2rdf` are unchanged. `docs` exits 2 on malformed input, as every crash does since #320, but
now as a refusal with a message rather than a traceback
([#301](https://github.com/aigora-de/rdf-construct/issues/301)).

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

An option given on the command line overrides the configuration file, and the configuration file
overrides the option's default. Previously an option's default could silently overwrite a value
the configuration file set, because the flag only had to be absent, and `localise extract -c` went
the other way, discarding flags that were given. An option counts as given whenever you pass it,
even at its default value: `--level standard` overrides a file that says `level: strict`.

**What moved:** `lint`'s `level:` ([#206](https://github.com/aigora-de/rdf-construct/issues/206)),
seven `docs` keys ([#251](https://github.com/aigora-de/rdf-construct/issues/251)) and
`localise extract`'s flags alongside `-c`
([#160](https://github.com/aigora-de/rdf-construct/issues/160)) and `shacl-gen`'s `level:`
([#225](https://github.com/aigora-de/rdf-construct/issues/225)) each have a row in their command's
section. **Not landed yet:** `split`'s
`unmatched:` ([#291](https://github.com/aigora-de/rdf-construct/issues/291)) comes with
[#176](https://github.com/aigora-de/rdf-construct/issues/176) (PR group P18), because `split -c`
does not run until then ([#175](https://github.com/aigora-de/rdf-construct/issues/175)).

**What to do:** read the configuration files your commands load, including any `.rdf-lint.yml`
that `lint` finds without `-c`. A key that has never had an effect now does: remove it, or pass
the flag, if it says something you do not mean.

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
| [#202](https://github.com/aigora-de/rdf-construct/issues/202) | `--init` and `--list-rules` together are refused with exit **2**. Previously `--init` ran alone and exited 0, and the rule listing was silently dropped. Both flags now run without a source. | Run `lint --init` and `lint --list-rules` as separate commands. |
| [#206](https://github.com/aigora-de/rdf-construct/issues/206) | `level:` in a config file takes effect, including a `.rdf-lint.yml` found without `-c`. Previously `--level`'s default, `standard`, always overwrote it. A file that says `level: strict` turns warnings into errors, so a run that exited **0** can now exit **1**. | Check any `.rdf-lint.yml` in the current directory or its parents. To keep the previous result, remove `level:` or pass `--level standard`. |

## `diff`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `docs`

| Issue | What changed | What to do |
|---|---|---|
| [#251](https://github.com/aigora-de/rdf-construct/issues/251) | Seven config keys take effect when their flag is not given: `output_dir`, `format`, `single_page`, `include_search`, `include_instances`, `include_shapes` and `include_skos`. Previously the flags' defaults overwrote them, so a config's `output_dir:` was ignored in favour of `docs/`, and `include_*: false` was forced back to true. Output can now land in another directory, in another format, and without the files the config excludes. A relative `output_dir` is resolved against the directory you run the command from, not the config file's. | If a script reads the output from `docs/` while its config names another `output_dir`, read it from there or pass `-o docs`. Remove any key you do not mean. |

## `shacl-gen`

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | Errors (a missing file, a configuration that will not load, a failed generation) exit **2** instead of 1. | Test for 2. |
| [#225](https://github.com/aigora-de/rdf-construct/issues/225) | `level:` in a `--config` file takes effect. Previously `--level`'s default, `standard`, always overwrote it. A file that says `level: strict` now gets strict shapes: `sh:in` from `owl:oneOf`, and, where it also says `closed: true`, `sh:closed`, which neither key produced before. A closed shape rejects any property it does not declare. **Data that conformed to the shapes can stop conforming.** `default_severity:` now reaches the generator too, but nothing emits `sh:severity` yet ([#223](https://github.com/aigora-de/rdf-construct/issues/223)), so validation still reports every constraint as a violation. | If your config says `level: strict` and you were relying on the standard shapes, remove `level:` or pass `--level standard`. Re-validate data against shapes regenerated from such a config. |

## `puml2rdf`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

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
| [#184](https://github.com/aigora-de/rdf-construct/issues/184) | `namespace_remap` matches at a namespace boundary. A key without a trailing `#`, `/` or `:` no longer catches a sibling that shares its spelling (`…/ont` no longer moves `…/ontology#`). A prefix binding now moves with its namespace even when it does not equal the key exactly (`"http://old/": …` also moves `@prefix x: <http://old/core#>`). | If you relied on the substring match, add a key for each namespace you meant to move. |

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
| [#182](https://github.com/aigora-de/rdf-construct/issues/182) | `rename` and `deprecate`: a CURIE in `--from`, `--to`, `--entity`, `--replaced-by` or a config file's entities now resolves against the source's own prefixes, plus `rdf`, `rdfs`, `owl`, `xsd` and `xml`. It used to rename nothing (`--from`) or be written as the IRI `<ex:…>` (`--to`, `--replaced-by`). A prefix no source binds, or one that two sources bind differently, is refused at exit **2** before anything is written. A bare `urn:…` is read as a CURIE. | Check output you produced with a CURIE: it may contain `<ex:…>` IRIs. Write a URN as `<urn:…>`. |
| [#182](https://github.com/aigora-de/rdf-construct/issues/182) | `rename` and `deprecate`: a source prefix that collides with one of rdflib's built-in prefixes (`org`, `dc`, `foaf`, `skos`, `time`, `geo`, `prov` and others) is written back as declared, not renamed (`org1:` → `org:`). `--migrate-data` output is not yet covered ([#358](https://github.com/aigora-de/rdf-construct/issues/358)). | None; expect a one-time diff in the `@prefix` lines and every CURIE using them. |
| [#184](https://github.com/aigora-de/rdf-construct/issues/184) | `rename`: `--from-namespace` and a config file's `namespaces` match at a namespace boundary. `…/ont` moves `…/ont#One`, `…/ont/extra#Three` and `…/ont` itself, and no longer moves `…/ontology#Two`. `…/ont#` moves only that namespace. | If you relied on the substring match, rename each namespace you meant to move. |

## `localise`

Covers `localise extract`, `merge`, `report`, `init` and `config`; each row names its subcommand.

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | `config`: `--init` over an existing `localise.yml` exits **2** instead of 1. | If a script tests for exit 1 to catch a rejected invocation, test for 2. |
| [#160](https://github.com/aigora-de/rdf-construct/issues/160) | `extract`: options given on the command line override the config file. Previously `-c` silently discarded `--properties`, `--source-language`, `--missing-only` and `--include-deprecated`. `--source-language` in particular meant the wrong source strings were extracted and recorded as though they were right. | If you pass any of these flags with `-c`, the output now follows the flags. Re-extract any translation file made that way with `--source-language`: its source strings, and the language it records, are those of the config file, not the flag. |
