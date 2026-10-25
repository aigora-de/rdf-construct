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

`docs`, `uml`, `split` and `order` now refuse to write into their default output directory when
it already holds files they did not write, which they previously overwrote in silence. Pass `-o`
to name the directory, or `--overwrite` to write there; either way the directory is marked and
later runs proceed. An explicit `-o` is unaffected. The marker is a small `.rdf-construct` file.
Treat it as part of the output: if you commit the output, commit the marker, or a fresh checkout
will be refused ([#261](https://github.com/aigora-de/rdf-construct/issues/261)).

The default directories are unchanged: `docs/`, `diagrams/`, `modules/` and `ordered/` (`order`'s
moved in [#128](https://github.com/aigora-de/rdf-construct/issues/128); see [`order`](#order)).

- **When it refuses:** the `-o` option was not given, the directory exists, and it holds anything
  other than this command's marker and the files an operating system leaves in any folder
  (`.DS_Store`, `Thumbs.db`, `desktop.ini`, `.directory` and the like) or a `.gitkeep`. The run
  exits **2** before the source is parsed or anything is written, and the message lists some of what it found.
- **Once it has written, it proceeds:** every run that writes leaves `.rdf-construct` in the
  directory, naming the command and the version. Another command's marker counts as someone
  else's: `docs`'s marker in `ordered/` does not let `order` in.
- **A config file's `output_dir` counts as named**, for `docs` and `split -c`
  ([#291](https://github.com/aigora-de/rdf-construct/issues/291)).
- **`--overwrite` deletes nothing.** Files the run does not write stay where they are.

**What to do:** a directory a v0.6.0 run wrote has no marker, so the first v0.7.0 run into it
refuses. If the directory holds only the tool's output, run once with `--overwrite`. If it holds
anything else, pass `-o` with a directory of its own.

### Command-line flags versus configuration files

An option given on the command line overrides the configuration file, and the configuration file
overrides the option's default. Previously an option's default could silently overwrite a value
the configuration file set, because the flag only had to be absent, and `localise extract -c` went
the other way, discarding flags that were given. An option counts as given whenever you pass it,
even at its default value: `--level standard` overrides a file that says `level: strict`.

**What moved:** `lint`'s `level:` ([#206](https://github.com/aigora-de/rdf-construct/issues/206)),
seven `docs` keys ([#251](https://github.com/aigora-de/rdf-construct/issues/251)) and
`localise extract`'s flags alongside `-c`
([#160](https://github.com/aigora-de/rdf-construct/issues/160)), `shacl-gen`'s `level:`
([#225](https://github.com/aigora-de/rdf-construct/issues/225)) and `split -c`'s `unmatched:`,
`output_dir`, `dry_run` and `generate_manifest`
([#291](https://github.com/aigora-de/rdf-construct/issues/291)) each have a row in their command's
section.

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
| [#261](https://github.com/aigora-de/rdf-construct/issues/261) | Without `-o`, the default directory `ordered/` is refused at exit **2** when it holds files `order` did not write, before the source is parsed or anything is written. New `--overwrite` writes there anyway. Every run that writes leaves a `.rdf-construct` marker in its directory, so later runs proceed. | If `ordered/` holds only output from an earlier run, run once with `--overwrite`. Otherwise pass `-o`. |
| [#90](https://github.com/aigora-de/rdf-construct/issues/90), [#280](https://github.com/aigora-de/rdf-construct/issues/280) | **A filtering profile writes an extract that says it is one.** A profile that writes fewer triples than its source, whatever its `unclaimed:` policy, no longer copies the source's `owl:versionIRI` into its output. It adds `prov:wasDerivedFrom` naming the source's version IRI (or its ontology IRI), declared as an `owl:AnnotationProperty`, and the run prints a `◇ extract:` line saying so. A section no longer claims a blank node that belongs to a named term's description, so an anonymous class expression whose axiom was dropped is no longer written as a free-standing `_:n…` block. Profiles that lose nothing are unaffected. | Nothing for a lossless profile. If you diff or publish extracts, expect a one-off change to the header, and point anything that read the extract's `owl:versionIRI` at `prov:wasDerivedFrom`. To publish an extract under its own name, use `split`, or rename it yourself. |
| [#90](https://github.com/aigora-de/rdf-construct/issues/90) | The ontology header is written first even when a profile has no `header:` section. Before, a profile without one wrote it partway down the file, or dropped it. New `header: false` on a profile, or in `defaults:`, leaves it out. `header: false` together with a `header:` section, or a value other than `true` or `false`, is refused at exit **2**. | Nothing, if every profile has a `header:` section, as every shipped one does. To keep a profile headerless, add `header: false`. |

## `profiles`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `uml`

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | A refusal exits **2** instead of 1: an unknown `-c/--context`, `-s/--style` or `-l/--layout`. The list of accepted names now goes to stderr. | If a script tests for exit 1 to catch a rejected invocation, test for 2. |
| [#261](https://github.com/aigora-de/rdf-construct/issues/261) | Without `-o`, the default directory `diagrams/` is refused at exit **2** when it holds files `uml` did not write, before the source is parsed or anything is written. New `--overwrite` writes there anyway. Every run that writes leaves a `.rdf-construct` marker in its directory, so later runs proceed. | If `diagrams/` holds only output from an earlier run, run once with `--overwrite`. Otherwise pass `-o`. |

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
| [#203](https://github.com/aigora-de/rdf-construct/issues/203) | An unknown rule name in `--enable` or `--disable` is refused with exit **2** and the list of available rules, as a config file's `enable:`, `disable:` and `severity:` already were. Previously a typo in `--enable` ran no rules and exited **0** with the file reported clean, and a typo in `--disable` left the rule running. From Python, `LintConfig.get_effective_rules()` raises `ValueError` for an unknown name. | Correct the name; `lint --list-rules` lists them. A gate that has been passing on a typo has been checking nothing. |
| [#293](https://github.com/aigora-de/rdf-construct/issues/293) | A rule selection that leaves no rule to run is refused with exit **2** before any file is read, naming what was enabled and what was disabled. Previously it exited **0** with the file reported clean. `--enable` on the command line still **replaces** a config's `enable:` list, and `--disable` still **adds to** its `disable:` list, so a config that disables a rule plus an `--enable` naming only that rule is one such selection. From Python, `get_effective_rules()`, `LintEngine.lint_file()` and `lint_graph()` raise `ValueError`. | Enable at least one rule that is not disabled, on the command line or in `.rdf-lint.yml`. |
| [#208](https://github.com/aigora-de/rdf-construct/issues/208) | `--level relaxed` now demotes warnings to info without removing any rule from the run. Previously it also dropped the four rules whose default severity is info (`redundant-subclass`, `property-no-domain`, `property-no-range` and `inconsistent-naming`), so a relaxed run reported fewer kinds of problem, not merely quieter ones. This applies to `level: relaxed` in a config too, and a `severity:` override on one of those rules is now honoured under relaxed. On `examples/lint/example_lint_problematic.ttl`, relaxed goes from 5 errors, 0 warnings, 9 info to 5 / 0 / 14. A relaxed run under `--fail-on info` can now exit **1** where it exited **0**. | Use `--disable` to run fewer checks. For the previous relaxed run, add `disable: [redundant-subclass, property-no-domain, property-no-range, inconsistent-naming]` beside `level: relaxed`. |

## `diff`

| Issue | What changed | What to do |
|---|---|---|
| [#143](https://github.com/aigora-de/rdf-construct/issues/143) | **Blank nodes are compared by structure.** A file containing restrictions or other blank nodes no longer differs from a copy of itself (exit **0** where it was 1), and a change made only inside blank nodes is now reported (exit **1** where it was 0: an `owl:Axiom` annotation's comment, a restriction's cardinality, an `owl:AllDisjointClasses` member). A changed structure is written as Turtle under the named subject that refers to it, or that it annotates; one that belongs to none is listed under `BLANK-NODE STRUCTURES`. Removing one of two identical copies is reported. A structure that is not a tree and has more than 500 blank nodes is not compared: the run says so first and exits **1**, never "identical" ([#388](https://github.com/aigora-de/rdf-construct/issues/388)). | If you gate CI on `diff`, expect both changes. Remove any workaround that stripped or skolemised blank nodes. If you diff an OWL-RL closure, diff the asserted files instead. See [Blank Nodes](user_guides/DIFF_GUIDE.md#blank-nodes). |
| [#143](https://github.com/aigora-de/rdf-construct/issues/143) | JSON: `identical` is now true only when nothing changed. A blank-node object is `{"type": "bnode", "turtle": "[ … ]"}`, and its `value` key (a parser's label) is gone. Each `modified` entry gains `structures`, and the top level gains `structures`, both lists of `{"action", "turtle"}`. `summary` gains `structures`. `warnings` lists only structures that were not compared; the advice to skolemise is gone. | Read `turtle` instead of `value` for a blank node, and read both `structures` lists. |
| [#143](https://github.com/aigora-de/rdf-construct/issues/143) | Python API: `TripleChange.turtle`, `EntityChange.added_structures` and `removed_structures`, `GraphDiff.added_structures`, `removed_structures`, `uncompared` and `notes`, and the class `UncomparedStructure`, are new. `GraphDiff.is_identical` counts them all. `blank_node_warning` is now a read-only property, true when `uncompared` is not empty: it means a structure was not compared, no longer that a blank node changed, and passing `blank_node_warning=` to `GraphDiff(...)` raises `TypeError`. | Nothing for code that only reads `is_identical` or formats with `format_diff`. Code that walks `GraphDiff` itself should read the new fields. Code that built a `GraphDiff` with `blank_node_warning=` should pass `uncompared=` instead. |

## `docs`

| Issue | What changed | What to do |
|---|---|---|
| [#251](https://github.com/aigora-de/rdf-construct/issues/251) | Seven config keys take effect when their flag is not given: `output_dir`, `format`, `single_page`, `include_search`, `include_instances`, `include_shapes` and `include_skos`. Previously the flags' defaults overwrote them, so a config's `output_dir:` was ignored in favour of `docs/`, and `include_*: false` was forced back to true. Output can now land in another directory, in another format, and without the files the config excludes. A relative `output_dir` is resolved against the directory you run the command from, not the config file's. | If a script reads the output from `docs/` while its config names another `output_dir`, read it from there or pass `-o docs`. Remove any key you do not mean. |
| [#261](https://github.com/aigora-de/rdf-construct/issues/261) | Without `-o`, the default directory `docs/` is refused at exit **2** when it holds files `docs` did not write, before the source is parsed or anything is written. A config file's `output_dir` counts as named. New `--overwrite` writes there anyway. Every run that writes leaves a `.rdf-construct` marker in its directory, so later runs proceed. | If `docs/` holds only output from an earlier run, run once with `--overwrite`. Otherwise pass `-o`. |

## `shacl-gen`

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | Errors (a missing file, a configuration that will not load, a failed generation) exit **2** instead of 1. | Test for 2. |
| [#225](https://github.com/aigora-de/rdf-construct/issues/225) | `level:` in a `--config` file takes effect. Previously `--level`'s default, `standard`, always overwrote it. A file that says `level: strict` now gets strict shapes: `sh:in` from `owl:oneOf`, and, where it also says `closed: true`, `sh:closed`, which neither key produced before. A closed shape rejects any property it does not declare. **Data that conformed to the shapes can stop conforming.** `default_severity:` now reaches the generator too, but nothing emits `sh:severity` yet ([#223](https://github.com/aigora-de/rdf-construct/issues/223)), so validation still reports every constraint as a violation. | If your config says `level: strict` and you were relying on the standard shapes, remove `level:` or pass `--level standard`. Re-validate data against shapes regenerated from such a config. |

## `puml2rdf`

| Issue | What changed | What to do |
|---|---|---|
| [#150](https://github.com/aigora-de/rdf-construct/issues/150) | `package "http://example.org/x#" as pfx` now means "namespace `http://example.org/x#`, prefix `pfx`", as the guide documents. On v0.6.0 it wrote a `@prefix` line made of the whole URI, a file nothing can read, at exit 0. The reverse spelling (`package pfx as "http://…"`) is now **refused** (exit 2, the line named, nothing written), as is a prefix the diagram names that cannot be used as written: one that is not a legal Turtle prefix, a core prefix (`rdf`, `rdfs`, `owl`, `xsd`, `xml`) on another namespace, one prefix for two IRIs, or one IRI under two prefixes. That includes a simple package's name and the part before the dot in `class pfx.Name`. `as org` now writes `org:`, not `org1:`. A namespace IRI ending in `:`, such as `urn:example:building:`, no longer has `#` appended. `package "URI" { … }` with no alias derives a prefix from the IRI and says which; if that prefix is already taken, the run is refused. Contributed by @rudra337-lgtm (#346). | Re-run the conversion; the old output was unreadable, so there is nothing to diff against. If the run is refused, write the package as `package "<namespace IRI>" as <prefix>` with a prefix that is legal, unique and not a core one. |
| [#151](https://github.com/aigora-de/rdf-construct/issues/151) | `puml2rdf` now refuses a file without `@startuml`/`@enduml` markers: exit 2, `no @startuml found — this does not look like a PlantUML diagram`, nothing written. Previously any file, including an empty one or one that was not PlantUML at all, converted to a one-triple ontology at exit 0, and `--validate --strict` passed it. A missing `@enduml` after `@startuml` is refused too. Lines the parser does not understand are now reported by line number (`⚠ 1 line not understood (7) — it is not in the output.`), and declarations it does not model (`interface`, `enum`, `annotation`, `entity`, `struct`, `abstract Foo`, `..|>`, `..>`) are named as dropped, as are `extends` and `implements` clauses on a class line. Text outside `@startuml` … `@enduml`, which was converted before, is reported and not converted; a file starting with a byte-order mark, whose first line was misread before, now converts. `--strict` makes them fatal at exit 1, with nothing written, and now applies to conversion and RDF warnings too. The derived-prefix message is a note, which `--strict` lets through. Python API: `PlantUMLParser.parse()` on text without the markers returns a result whose `success` is false, carrying that error and an empty model. `ParseResult.warnings` holds `ParseWarning`s (`line_number`, `message`, `line_content`, `code`) instead of strings; `str()` of one gives the old text. `ParseResult.notes` is new, and `ParseError.line_number` may be `None`. | Wrap fragments in `@startuml` … `@enduml`. Read each warning: it names content that is not in the output. Under `--strict`, a diagram the `uml` command generated will usually stop at 1, because its directional arrows (`-u->`) and notes are not read. Code reading `ParseResult.warnings` as strings should use `str(warning)`. |
| [#290](https://github.com/aigora-de/rdf-construct/issues/290) | `puml2rdf --validate` now converts the diagram, validates the RDF and serialises it in memory in the requested format. It still writes nothing, and it does not run `--merge`. It stopped after the model checks, so the RDF validation the guide describes never ran. RDF that cannot be written in the requested format now fails `--validate` at exit 2. Its summary counts every warning, not only the model's. | Nothing, unless a pipeline relied on `--validate` passing a diagram that the real run then failed to write. |

## `cq-test`

| Issue | What changed | What to do |
|---|---|---|
| [#134](https://github.com/aigora-de/rdf-construct/issues/134) | A competency question pairing an ASK query with `has_results`, `no_results` or `count` is now reported as an error. These were never evaluated against the ASK's answer: `has_results` and `count: 1` always passed, `no_results` and `count: 0` always failed. `min_results` and `max_results` are refused the same way, and so are `results` and `contains`, which already errored with `TypeError: 'bool' object is not iterable`. The question's status is `ERROR`, its JUnit element is `<error type="InvalidExpectation">`, the run exits **2**, and the other questions still run. | Use `expect: true` or `expect: false`. A question that has been passing this way has been checking nothing. |
| [#134](https://github.com/aigora-de/rdf-construct/issues/134) | Python API: an `Expectation` subclass declares the query forms it can be checked against in `query_forms`. The default is SELECT, CONSTRUCT and DESCRIBE, so your own subclass is refused on an ASK unless it says otherwise. `CQTestResult` gains `error_type`: `QueryError` or `InvalidExpectation`. | For a subclass that checks ASK answers, set `query_forms = frozenset({"ASK", ...})` on it, and give it a `key` property if `describe()` does not read as its `expect:` spelling. |

## `stats`

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | Errors, including `--compare` with other than two files, exit **2** instead of 1. | Test for 2. |

## `describe`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `merge`

**Anyone who has produced a merged ontology with this tool and believed a priority was honoured
needs to know that it was not.** `--strategy` and `-p/--priority` now affect the merged graph.
Previously they changed only the console summary and the report. Repeated `rdfs:comment`,
`skos:altLabel` and `rdf:type` values are no longer treated as conflicts; conflicting
`rdfs:domain`/`rdfs:range` are marked rather than silently both-written.

| Issue | What changed | What to do |
|---|---|---|
| [#193](https://github.com/aigora-de/rdf-construct/issues/193) | A conflict needs **two sources** that disagree, on a predicate whose tier makes a second value a conflict. Two values from one source never conflict, and a source whose values are a subset of another's agrees with it. Only `rdfs:label` and `skos:prefLabel` (per language tag, compared without case), `rdfs:domain`, `rdfs:range` and properties a source declares `owl:FunctionalProperty` can conflict; every other predicate, `rdf:type` and `rdfs:subClassOf` included, is repeatable. `owl:Ontology` subjects are not checked until #171. Conflict counts fall sharply: `merge_core` + `merge_extension` 2 → 0, the IES pairs 62/161/248 → 0, and under `mark_all` a merely multilingual merge now exits **0** instead of 1. `ignore_predicates` and the new `predicate_tiers` take full IRIs; a prefixed name is refused with exit **2** (it used to match nothing, silently). In the Python API, `ConflictType` is now `AMBIGUOUS`, `MALFORMED` and `CHANGES_MEANING`, and `filter_semantic_conflicts` is removed: nothing ever compared one predicate with another. | If you compare conflict counts with an earlier merge, expect them to fall. Treat a predicate the defaults miss, such as `dcterms:title`, by placing it in a tier under `conflicts.predicate_tiers`. Replace a prefixed name in `ignore_predicates` with the full IRI. |
| [#169](https://github.com/aigora-de/rdf-construct/issues/169) | The resolution is applied: under `priority`, `first` and `last` the losing values of a per-language conflict are **removed** from the output, where before every value from every source was written. `first` and `last` count only the sources that assert the value. `rdfs:domain`/`rdfs:range` conflicts are never picked: both values stay, the conflict is marked, and the run exits **1** under every strategy (`merge_core` + `merge_conflicting -p 1 -p 2` exited 0 and now exits 1). Sources tied at the highest priority (for example a config with no `priority:` lines) are not picked between: the conflict is marked and the run exits **1**. `Conflict.resolution` is replaced by `Conflict.winner`, `kept` and `discarded`. | Re-run any merge whose output you rely on, and check the labels it now drops. If a pipeline expects exit 0 from a merge with differing domains or ranges, decide which one you mean, or accept 1. Give tied sources different priorities, or use `--strategy first`. |
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | A refusal exits **2** instead of 1: no sources, a config that will not load (including malformed YAML, which was a traceback), `--init` over an existing file. | If a script tests for exit 1 to catch a rejected invocation, test for 2. |
| [#170](https://github.com/aigora-de/rdf-construct/issues/170) | A blank-node structure that two sources both state (a restriction, an `owl:unionOf` list, an `owl:AllDisjointClasses`) is written once, not once per source. Only identical structures referred to by the same subject and predicate are combined. The output has fewer triples, and the conflicts the duplicates caused are gone: under `--strategy mark_all`, a merge whose only conflicts were duplicates now exits **0** instead of 1 and writes no conflict header, and `--report` lists fewer conflicts. Labels written as `_:…` are now stable between runs. | If you compare triple counts or conflict counts with an earlier merge, expect them to fall. If a script relied on `mark_all` exiting 1 for such a merge, it no longer will. |
| [#184](https://github.com/aigora-de/rdf-construct/issues/184) | `namespace_remap` matches at a namespace boundary. A key without a trailing `#`, `/` or `:` no longer catches a sibling that shares its spelling (`…/ont` no longer moves `…/ontology#`). A prefix binding now moves with its namespace even when it does not equal the key exactly (`"http://old/": …` also moves `@prefix x: <http://old/core#>`). | If you relied on the substring match, add a key for each namespace you meant to move. |

## `split`

| Issue | What changed | What to do |
|---|---|---|
| [#286](https://github.com/aigora-de/rdf-construct/issues/286) | A refusal exits **2** instead of 1: neither `--by-namespace` nor `--config`, a config that will not load (including malformed YAML, which was a traceback), `--init` over an existing file. | If a script tests for exit 1 to catch a rejected invocation, test for 2. |
| [#261](https://github.com/aigora-de/rdf-construct/issues/261) | Without `-o`, the default directory `modules/` is refused at exit **2** when it holds files `split` did not write, before the source is parsed or anything is written. `--dry-run` refuses the same way. New `--overwrite` writes there anyway. Every run that writes leaves a `.rdf-construct` marker in its directory, so later runs proceed. | If `modules/` holds only output from an earlier run, run once with `--overwrite`. Otherwise pass `-o`. |
| [#177](https://github.com/aigora-de/rdf-construct/issues/177) | `--by-namespace` no longer writes modules for rdflib's built-in prefixes (`brick`, `doap`, `geo`, `schema`, `void`), and a module whose prefix collided with one of rdflib's is now named after the prefix your file declares (`org1.ttl` → `org.ttl`). A module for the empty prefix `:` is named after its namespace's last path segment (`default.ttl` → `ontology.ttl` for `…/ontology#`). Namespaces with no declared prefix, including all of an N-Triples file's, get their own modules named the same way, instead of everything going to `common.ttl` at exit 1; the run exits 0. With `-c` or `OntologySplitter`, a module's `namespaces:` entry matches at a namespace boundary: `http://example.org/ont` no longer takes `…/ontology#X`, which goes to the unmatched module instead. | Delete the stale module files, and update anything that referenced a renamed module or its manifest `name:`. For `namespaces:`, add an entry for each sibling namespace you meant to include. |
| [#176](https://github.com/aigora-de/rdf-construct/issues/176) | `split` no longer discards individuals, SKOS concepts, terms declared only by an OWL characteristic, or blank-node interiors. Every existing `--by-namespace` output changes; modules that previously contained `rdfs:subClassOf [ ]` now carry the restriction it replaced. An individual goes to the module holding its class, a SKOS concept with its scheme, and a blank node with whatever refers to it. A subject with no single module goes to the unmatched module, and the run counts them by reason. Since every subject is now placed, `--by-namespace` has unmatched subjects again, and exits **1** when it does: `ies-env-building.ttl` (5) and `ies-env-building-classification.ttl` (3) exit 1 where they exited 0. `--unmatched` and `--common-name` now apply with `--by-namespace`, so `--unmatched error` refuses such a run at exit **2**. | Expect larger modules and an unmatched module. To have a run fail instead, pass `--unmatched error`. |
| [#178](https://github.com/aigora-de/rdf-construct/issues/178) | `split` no longer writes `http://example.org/<module>` ontology IRIs or `file://` imports. A module's IRI comes from its config, its own namespace, or the source ontology's IRI, and modules that cannot be named get no header and a warning (exit **1**). The run prints each module's IRI and the rung that gave it. A namespace IRI is not used when it is the source's own ontology IRI or a borrowed namespace's (as for #383 below), so `ies-common.ttl`'s module is `…/ies/common/ies`. `owl:imports` name ontology IRIs rather than output filenames, and `imports:` in config now takes IRIs or CURIEs: a file name is refused at exit **2**. The source's header is not copied into any module; each module names it with `prov:wasDerivedFrom`. The unmatched module gets a header and imports for the first time. A config module takes a new `ontology_iri:` key. | Replace file names in `imports:` with the ontology IRIs of the modules meant. Point anything that read a module's `example.org` IRI at its new one, as the run prints it. |
| [#382](https://github.com/aigora-de/rdf-construct/issues/382) | `split`'s unmatched module is now called `unmatched` (`unmatched.ttl`) by default, not `common`. A run whose unmatched module would share its name with another module is now refused at exit **2**, where it used to overwrite that module's file. | Pass `--common-name common`, or set `unmatched: module: common`, to keep the old name. |
| [#383](https://github.com/aigora-de/rdf-construct/issues/383) | In a file with an ontology header, `--by-namespace` makes no module of a borrowed vocabulary, one that no ontology the file declares owns: one on another host, or, on a host many publishers share (`purl.org`, `w3id.org`, `www.w3.org`), one outside the ontology's own IRI. Its declarations (`dcterms:title a owl:AnnotationProperty`) go to the unmatched module. `ies-common.ttl`'s three GeoSPARQL declarations move from `geo.ttl` to `unmatched.ttl`, and the run exits **1**. | Delete stale `dcterms.ttl`, `skos.ttl`, `geo.ttl` and the like. |
| [#291](https://github.com/aigora-de/rdf-construct/issues/291) | With `-c`, the config's `unmatched:` strategy and module name, `output_dir`, `dry_run` and `generate_manifest` now take effect unless the matching option is given. Before, `--unmatched`'s and `-o`'s defaults always replaced them, and `split -c` crashed before it got that far ([#175](https://github.com/aigora-de/rdf-construct/issues/175), now fixed). A config's `output_dir` counts as named, so it is never refused as a default directory. | Read your split config: a key that has never had an effect now does. |

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
| [#157](https://github.com/aigora-de/rdf-construct/issues/157), [#406](https://github.com/aigora-de/rdf-construct/issues/406) | `extract`, `report`: an entity is any subject with an IRI that carries one of the requested properties as a literal, whatever its type. Terms typed only by an OWL characteristic, `owl:DeprecatedClass` or `owl:DeprecatedProperty`, SKOS concepts and schemes, the ontology header, individuals and untyped subjects used to be invisible: not extracted, not counted, not skipped. A translation file records a term typed only `rdfs:Class` as `rdfs:Class`, not `owl:Class`. | Re-extract: the file gains entries, and an existing translation file will not round-trip against the new extraction without a diff. |
| [#159](https://github.com/aigora-de/rdf-construct/issues/159) | All subcommands: language tags are compared case-insensitively, so ontologies with inconsistent tag spellings match differently. `-l` and `--source-language` match a tag exactly and not a range: `-l en` does not select `@en-GB`. When a language matches no literal and a related tag (the same primary subtag) matches some, the run warns, naming the tag, and exits **1**. | If an ontology is tagged `@en-GB`, pass `--source-language en-GB`. Treat exit 1 from `extract`, `init` or `report` as "asked for a language that is not there". |
| [#159](https://github.com/aigora-de/rdf-construct/issues/159) | `merge` writes tags in canonical case (`en-GB`), and finds an existing literal whatever the case of its tag, so `target_language: DE` no longer writes a second label beside an existing `@de`. A `target_language` that is missing, blank, not text (an unquoted `no` is a boolean in YAML), malformed, or the source language is refused at exit **2** with nothing written. It used to merge every translation as an untagged literal, read as the source language, and under `--existing overwrite` replaced the source text. `extract`, `init` and `report` refuse a malformed `-l` or `--source-language` the same way, including `report -l en,,de`. | Fix the translation file's `target_language`; quote `'no'`. Check ontologies produced by earlier merges for duplicate labels in one language spelt two ways, and for untagged translations. |
| [#158](https://github.com/aigora-de/rdf-construct/issues/158) | `report`: every percentage changes, and each now prints its counts: `6/8 (75%)`. Coverage is counted in entities: the denominator for a property is the entities carrying it in at least one language. The base language is no longer 100% by construction; it now measures how much of the labelled material is present in the source language. Coverage can no longer exceed 100% and pending counts can no longer be negative. A second value in one language for `rdfs:label` or `skos:prefLabel` is listed as a warning; a property no entity carries reads `0/0 (—)`. | Re-baseline any coverage threshold you keep. A base row below 100% means terms labelled only in other languages, or only `@und`. |
| [#407](https://github.com/aigora-de/rdf-construct/issues/407) | `report` leaves out deprecated entities, as `extract` does, and prints how many; `--include-deprecated` counts them. A plain-string `owl:deprecated "true"` now marks a term deprecated in both. | Pass `--include-deprecated` to `report` to keep counting deprecated terms. |
| [#405](https://github.com/aigora-de/rdf-construct/issues/405) | `merge --existing preserve`: a repeatable property such as `skos:altLabel` keeps every translation; one is skipped only when the same text already exists in that language. It used to keep the first and drop the rest as "Skipped (exists)". `--missing-only` and `overwrite` on a repeatable property are unchanged (#405 stays open for them). | Re-merge files with several `skos:altLabel` values per entity. |
| [#404](https://github.com/aigora-de/rdf-construct/issues/404) | `extract`, `init`: a destination that already holds translation work is refused at exit **2** and left byte-identical, before the ontology is read. It used to be replaced with empty `pending` entries at exit 0 without a word, including by a plain re-run of the guide's first command with no `-o`. Translation work is any entry whose status isn't `pending`, or whose translation isn't blank. A dangling link is refused too, and a destination that isn't a translation file (an ontology, broken YAML) or is a directory is refused even with `--overwrite`; a translation file with no work in it, or an empty file, is still replaced. | Pass `-o` to write a new file, or `--overwrite` to replace the old one; the run then warns, on stderr, how many finished translations it discarded. To replace a file that isn't a translation file, remove it first. Merging a fresh extraction into an existing file is not supported. |
| [#404](https://github.com/aigora-de/rdf-construct/issues/404) | `extract`, `init`: without `-o`, the file is named after the tag in canonical case, so `-l DE` writes `de.yml`, not `DE.yml`. On a case-insensitive filesystem (macOS, Windows) the two were already one file, so `-l DE` replaced a finished `de.yml`. | On a case-sensitive filesystem, look for `de.yml` where you used to find `DE.yml`, or pass `-o`. |
| [#408](https://github.com/aigora-de/rdf-construct/issues/408) | `merge`: a `translation` that YAML reads as a boolean or a number (an unquoted `Yes`, `No`, `On`, `123`, `0123`) is refused at exit **2**, naming the file, the entity and the key, with nothing written; so is a missing `uri`, `property` or `source`, a `status` that isn't one of the four, and a file that is empty or not a translation file. Every unreadable value in the file is listed. These used to abort the merge with Python's message, or crash with a traceback. A blank `translation:` is untranslated and skipped, as `''` is. A wrong-typed `generated`, `tool`, `source_file`, `type`, `notes` or `summary` is ignored. | Quote any translation YAML would read as a value: `translation: "Yes"`. |
| [#408](https://github.com/aigora-de/rdf-construct/issues/408) | `extract -c`: a scalar `properties:` is refused at exit **2**; it used to extract nothing at exit 0. A switch written as text (`missing_only: 'false'`) is refused; it used to act as true. Any other value of the wrong type (a section that isn't a mapping, an unquoted `no` as a language, a bad `merge.existing` or `min_status`, a number as `output.directory`) and an empty config file are refused, naming the file and the key; most used to crash. | Write `properties:` as a list, switches unquoted (`true`, `false`), and languages as quoted text where YAML would misread them (`'no'`). |
| [#355](https://github.com/aigora-de/rdf-construct/issues/355) | `extract`, `report`: `--properties` resolves a CURIE against the prefixes the ontology declares, plus `rdf`, `rdfs`, `owl`, `xsd` and `xml`. `-p ex:note` used to extract nothing at exit 0, and `dc:` always meant Dublin Core elements, whatever the ontology bound it to. A prefix the ontology does not declare is refused at exit **2**, naming the bound prefixes, with nothing written. That includes `skos:`, `dc:` and `dcterms:` when the ontology does not declare them, and a bare `urn:x`, which reads as a CURIE. `report` prints each property with the ontology's prefixes, so `-p ex:note` is headed `ex:note`, not the full IRI. | Declare the prefix in the ontology, or give the IRI in full or in angle brackets (`<urn:x>`). Re-extract any translation file made with `-p dc:…` from an ontology that binds `dc:` to Dublin Core terms: it was empty. |
| [#355](https://github.com/aigora-de/rdf-construct/issues/355) | `merge`, `extract -c`: a translation file's `property:` and a configuration file's `properties:` are a full IRI, an IRI in angle brackets, or a CURIE on the file format's six prefixes (`rdf`, `rdfs`, `owl`, `skos`, `dc` for Dublin Core elements, `dcterms`), whatever the ontology declares. Anything else is refused at exit **2**, listing every one, with nothing written. `merge` used to add such an entry as a triple on a predicate no ontology uses, such as `<ex:note>`, at exit 0. `extract` writes those six as CURIEs, as before, and every other property as a full IRI. | Write any other property as a full IRI. Check ontologies made by earlier merges for predicates such as `<ex:note>`. |
| [#355](https://github.com/aigora-de/rdf-construct/issues/355) | Python API: `generate_coverage_report(…, properties=…)` and `extract_strings` resolve a CURIE against the source file's own prefixes, as the CLI does; `generate_coverage_report` used to report 0 for `rdfs:label`. An unbound prefix raises `CurieError`, or fails the extraction. `StringExtractor` and `CoverageReporter` resolve against the graph they are given. | Pass full IRIs, or CURIEs on the source's prefixes. |
| [#421](https://github.com/aigora-de/rdf-construct/issues/421) | Python API: `LanguageCoverage.total_strings` is renamed `total_pairs`, because it counts entity and property pairs. No alias is kept. The CLI's output is unchanged, and so is `total_strings` in a translation file's `summary:`. | Read `total_pairs`. |
