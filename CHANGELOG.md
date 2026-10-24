# Changelog

All notable changes to rdf-construct will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

**If you gate CI on `lint`'s exit code, it has changed.** Error findings now exit
1, not 2, and a run with only warnings exits 0. Pass `--fail-on warning` to keep
failing on warnings. Every command now uses one convention: 0 success, 1
completed with findings, 2 refused or failed. See
[Exit codes](https://github.com/aigora-de/rdf-construct/blob/main/docs/MIGRATION_v0.7.0.md#exit-codes)
in the migration note.

**If you run `order` without `-o`, your output moves.** The default output
directory is now `ordered/` instead of `src/ontology/`. Pass `-o src/ontology`
to keep the previous location.

**`docs`, `uml`, `split` and `order` now refuse to write into their default
output directory when it already holds files they did not write**, which they
previously overwrote in silence. Pass `-o` to name the directory, or
`--overwrite` to write there; either way the directory is marked and later runs
proceed. An explicit `-o` is unaffected. The marker is a small `.rdf-construct`
file. Treat it as part of the output: if you commit the output, commit the
marker, or a fresh checkout will be refused. See
[Default output directories](https://github.com/aigora-de/rdf-construct/blob/main/docs/MIGRATION_v0.7.0.md#default-output-directories)
in the migration note.

**If you publish extracts from a filtering `order` profile, their header
changes.** Any run that writes fewer of the source's triples than it read now
drops the source's `owl:versionIRI` and adds `prov:wasDerivedFrom` naming the
source, whatever the profile's `unclaimed:` policy. The ontology IRI,
`owl:versionInfo` and `owl:imports` stay. Profiles that lose nothing are
unaffected. See
[`order`](https://github.com/aigora-de/rdf-construct/blob/main/docs/MIGRATION_v0.7.0.md#order)
in the migration note.

**A `lint` gate that passed can now fail, because it now checks what it
claimed to.** A misspelt rule name in `--enable` or `--disable`, or a rule
selection that leaves nothing to run, is refused with exit 2; before, `lint`
ran no rules and reported the file clean at exit 0. `--level relaxed` now runs
every rule, so a relaxed run under `--fail-on info` reports four more kinds of
finding. See
[`lint`](https://github.com/aigora-de/rdf-construct/blob/main/docs/MIGRATION_v0.7.0.md#lint)
in the migration note.

**If you have merged ontologies with `merge` and believed a priority was
honoured, it was not.** `--strategy` and `-p/--priority` now affect the merged
graph; before, they changed only the console summary and the report, and every
value from every source was written. Conflicts are now only found between
sources, and only on predicates where a second value matters, so a multilingual
ontology no longer conflicts with itself. A merge that leaves conflicting
`rdfs:domain` or `rdfs:range` values for review now exits 1 under every
strategy. See
[`merge`](https://github.com/aigora-de/rdf-construct/blob/main/docs/MIGRATION_v0.7.0.md#merge)
in the migration note.

**If you split with `split --by-namespace`, every module changes.** Individuals,
SKOS concepts, characteristic-only properties and blank-node interiors are no
longer dropped, so modules grow and an `unmatched.ttl` module (no longer
`common.ttl`) collects what has no single home, at exit 1. Each module now has
an honest ontology IRI, printed with the rule that gave it, instead of
`http://example.org/<module>`, and `owl:imports` name ontology IRIs instead of
`file://` paths. `split -c` runs for the first time. See
[`split`](https://github.com/aigora-de/rdf-construct/blob/main/docs/MIGRATION_v0.7.0.md#split)
in the migration note.

**A `cq-test` suite that passed can now exit 2.** An ASK query paired with
`has_results`, `no_results`, `count`, `min_results`, `max_results`, `results`
or `contains` is reported as that question's error; `has_results` and
`count: 1` on an ASK always passed whatever it answered. Use `expect: true` or
`expect: false`. See
[`cq-test`](https://github.com/aigora-de/rdf-construct/blob/main/docs/MIGRATION_v0.7.0.md#cq-test)
in the migration note.

**If you gate CI on `diff`, its verdict changes for any file with a blank
node.** Blank nodes are now compared by structure. A file containing
restrictions or other blank nodes is identical to a copy of itself (exit 0,
where it was 1), and a change made only inside blank nodes is reported (exit 1,
where it was "semantically identical" at exit 0). Remove any workaround that
stripped or skolemised blank nodes. See
[`diff`](https://github.com/aigora-de/rdf-construct/blob/main/docs/MIGRATION_v0.7.0.md#diff)
in the migration note.

**v0.7.0 changes behaviour in most commands, deliberately and once.** Every
change, and what to do about it, is listed command by command in the
[v0.7.0 migration note](https://github.com/aigora-de/rdf-construct/blob/main/docs/MIGRATION_v0.7.0.md).

### Added
- **`docs/MIGRATION_v0.7.0.md`, the single migration note for v0.7.0** (#312).
  It has a section for changes that cut across commands (exit codes, default
  output directories, flags versus configuration files) and then one section
  per command, each a table of issue, what changed and what to do. The note is
  built as fixes land: every PR that closes a `breaking` issue, or changes
  output, adds or amends its own row in the same PR.
- **`docs/user_guides/ORDER_GUIDE.md`, a guide to `order`** (#127). `order` is
  the founding feature, and it was the only substantial command without a
  guide. The guide is written from the command's audited behaviour rather than
  its intended behaviour. Where the two differ, it states what the command does
  today and links the issue. Open findings are listed in a "Known limitations"
  table, and a fix deletes its row in the same PR. The guide covers:
  - how the configuration file's sections compose;
  - the six built-in selectors;
  - the `unclaimed:` policy;
  - sorting, roots and hierarchy cycles;
  - prefix handling.
- **`examples/order/library.ttl` and `ordering.yml`**, the guide's worked
  material. The ontology is built so that alphabetical and hierarchical order
  visibly disagree, and every key in the configuration is one the tool reads.
  Every command in the guide runs verbatim against these files.
- **Tests that execute the guide's material** (`tests/test_unclaimed_subjects.py`).
  They assert that complete profiles preserve every triple, that the two orders
  differ, that unclaimed subjects are reported, and that a filtering profile
  keeps its blank-node closure. Nothing executed the shipped ordering examples
  before.
- **Three pinned IES ontologies in `tests/fixtures/ies/`, the first realistic
  test material in the repository** (#307). They are `ies-common` 5.0.3,
  `ies-env-building` 1.0.0 and `ies-env-building-classification` 1.0.0,
  copied verbatim from public UK Government repositories under the MIT
  Licence, © Crown Copyright. A README records each file's source and commit.
  `tests/test_ies_fixtures.py` checks each file's bytes against its pinned
  commit and its declared versions, so a silent upstream swap fails the suite.
  The release process now runs every command over them before a tag.
- **A built-in default ordering for Turtle written without a profile** (#303).
  `core.default_order.default_subject_order()` places the ontology header,
  then classes, object, datatype, annotation and other properties, then
  individuals, so superclasses come before subclasses and superproperties
  before subproperties. Both ends of an `rdfs:subClassOf` arc count as classes,
  declared or not, so an imported parent still comes first. A punned term is
  placed once, a property of no
  inferable kind goes to other properties, and a subject no section claims is
  still written. `check_subject_order_complete()` raises if a subject list
  would lose triples, and `serialise_turtle_str()` returns the Turtle that
  `serialise_turtle()` writes. This is groundwork: no command uses it yet, so
  no output changes.
- **`--overwrite` on `docs`, `uml`, `split` and `order`** (#261). It writes
  into a default output directory that holds files the command did not write,
  and marks it. It deletes nothing, and with an explicit `-o` it has no effect.
- **`core.outdir`, the one place that knows what an output collision is**
  (#261). `foreign_entries()` lists what in a directory a command did not
  write, ignoring the files operating systems leave in any folder (`.DS_Store`,
  `Thumbs.db`, `desktop.ini`, `.directory`) and `.gitkeep`;
  `mark_output_dir()` writes the `.rdf-construct` marker, which names the
  command and the version. `cast`'s overwrite warning (#191) will call the same
  check.
- **`core.provenance`, what a derived artefact may claim about itself** (#90).
  `derivation_targets()` names a source by its `owl:versionIRI`, else its
  ontology IRI; `strip_version_iri()` removes only that triple; and
  `stamp_derivation()` adds `prov:wasDerivedFrom`, declares it an
  `owl:AnnotationProperty` unless the graph already gives it a property type,
  and binds `prov:`. `order` composes them through
  `stamp_extract()`, with `missing_triples()` as the trigger. `split` (#178) and
  `merge` (#171) will call the same functions.
- **`header: false` on an `order` profile, or in `defaults:`** (#90), the one
  way to leave the ontology header out. Combined with a `header` section in the
  same profile, or given anything but `true` or `false`, it is refused at exit 2
  before anything is written.
- **`ontology_iri:` on a `split` config module** (#178): the module's ontology
  IRI, as an IRI or a CURIE of the source's prefixes.

### Changed
- **`split`'s unmatched module is called `unmatched` by default** (#382), not
  `common`, and a run whose unmatched module would take another module's name
  is refused at exit 2 instead of overwriting it. `--common-name common` keeps
  the old name.
- **A default output directory the tool has not marked is refused** (#261).
  Without `-o`, `docs`, `uml`, `split` and `order` exit 2 before parsing the
  source when `docs/`, `diagrams/`, `modules/` or `ordered/` holds anything but
  that command's `.rdf-construct` marker and operating-system clutter. The
  message lists up to five of the entries and the two ways on. Every run that
  writes marks its directory just before its first output file, so a re-run
  proceeds, and a run refused before then marks nothing. `split --dry-run`
  refuses the same way. `docs` counts a config file's `output_dir` as named.
- **`order` defaults `-o/--outdir` to `ordered/`, not `src/ontology/`** (#128).
  `src/` is a Python packaging convention that says nothing about ordered RDF,
  and the old default silently created a two-level tree wherever the command
  happened to be run. `ordered/` names what it holds, matching `uml` →
  `diagrams/`, `docs` → `docs/` and `split` → `modules/`. An explicit `-o` is
  unaffected, and `-o src/ontology` restores the previous behaviour.
- **A filtering `order` profile writes an extract that says it is one** (#90).
  When the written graph is missing any of the source's triples, each ontology
  header keeps its IRI, `owl:versionInfo` and `owl:imports`, loses
  `owl:versionIRI`, and gains `prov:wasDerivedFrom` naming the source's version
  IRI, or its ontology IRI when it has none. The trigger is what was written,
  not the `unclaimed:` policy, so `warn` profiles are stamped too, and the run
  prints a `◇ extract:` line under every policy. Previously the extract claimed
  to be the release it was cut from. A source's own description of
  `prov:wasDerivedFrom` follows the header unless a section claims it, so an
  extract keeps PROV-O's `owl:ObjectProperty` type where the source states it,
  and an extract run back through the same profile is written unchanged.
- **The ontology header is no longer a section's to lose** (#90). A profile
  without a `header` section writes the header first. Before, it was written
  partway down the file by an `individuals` section, reported as unclaimed under
  `warn`, or dropped in silence under `ignore`. A `header` section still places
  it wherever it stands.
- **`order` sections no longer claim a blank node that a named term
  references** (#280). The `owl:unionOf` behind a property's range is a blank
  node typed `owl:Class`, and a `classes` section claimed it, so a profile that
  dropped the property wrote the union as a free-standing `_:n…` class with a
  fresh label on every run. It now goes with its property. A blank node no
  named term references, such as an `owl:AllDisjointClasses`, is still claimed.
  `select_subjects()` applies this for every selector and every caller.
- **One exit-code convention across every command** (#286): 0 the command did
  what you asked, 1 it finished and has something to report, 2 it did not do it.
  The 30 `click.Abort()` refusals in `order`, `uml`, `lint`, `merge`, `split`,
  `refactor` and `localise config` now exit 2, not 1, through one `Refusal`
  exception that names what was refused and what is accepted. `stats` and
  `shacl-gen` errors exit 2, not 1. A malformed YAML config in `merge`, `split`
  and `refactor` is refused at 2 instead of a traceback.
- **`lint` error findings exit 1, not 2, and `--fail-on` sets the gate** (#286).
  `--fail-on error|warning|info|never` (default `error`) is the lowest severity
  that exits 1, so a warnings-only run now exits 0. The severity-to-exit-code
  mapping moved out of the engine: `LintSummary.exit_code` is removed.
- **`orphan-class` defaults to `warning`** (#302). A root class is not a
  defect, and 16 of 17 shipped example ontologies failed the linter on it.
- **`lint --init --list-rules` is refused** (#202). The two cannot be
  combined. Previously `--init` ran and the rule listing was silently dropped.
  It now exits 2. Run them separately.
- **`lint` refuses an unknown rule name in `--enable` or `--disable`** (#203).
  Either exits 2 with the list of available rules, the same message a config
  file's `enable:`, `disable:` and `severity:` already gave; one validator now
  serves all five. Before, a typo in `--enable` ran no rules and reported the
  file clean at exit 0, and a typo in `--disable` left the rule running. From
  Python, `LintConfig.get_effective_rules()` raises `ValueError` for an
  unknown name in `enabled_rules`, `disabled_rules` or `severity_overrides`.
- **`lint` refuses a rule selection that leaves no rule to run** (#293).
  `--enable X --disable X`, `--disable` naming every rule, or a config's
  `disable:` covering every rule a CLI `--enable` names, now exits 2 before any
  file is read. The message names what was enabled and what was disabled, and,
  when a config was loaded, that `--enable` replaces its `enable:` list while
  `--disable` adds to its `disable:` list. From Python, `get_effective_rules()`,
  `LintEngine.lint_file()` and `lint_graph()` raise `ValueError`.
- **`--level relaxed` demotes and never deselects** (#208). Relaxed reports
  warnings as info; it no longer drops the four rules whose default severity is
  info (`redundant-subclass`, `property-no-domain`, `property-no-range`,
  `inconsistent-naming`). Every rule runs at every level, so a `severity:`
  override on one of them is now honoured under relaxed too. On
  `examples/lint/example_lint_problematic.ttl`, relaxed goes from 5 errors,
  0 warnings, 9 info to 5 errors, 0 warnings, 14 info. Use `--disable` to run
  fewer checks.
- **`localise extract -c` honours the flags given alongside it** (#160).
  `--properties`, `--source-language`, `--missing-only` and
  `--include-deprecated` were silently discarded whenever a config file was
  passed. An option given on the command line now overrides the config file,
  and the config file overrides the option's default.

### Fixed
- **`diff` compares blank nodes by structure, in both directions** (#143). It
  compared triples by the labels rdflib gives blank nodes at parse time, and
  then skipped every blank-node subject. So any file with an `owl:Restriction`
  differed from a byte-identical copy of itself at exit 1, and a change made
  only inside blank nodes, such as an `owl:Axiom` annotation's comment, printed
  "Graphs are semantically identical." at exit 0; the warning meant for that
  case came after the early return, and advised a `rapper` command that
  skolemises nothing. Both graphs are now labelled by content
  (`core.blank_nodes.label_by_content`, #170), so a structure both files state
  drops out and a changed one is reported whole. It is written as Turtle
  (`+ rdfs:subClassOf [ a owl:Restriction ; owl:cardinality "99"^^xsd:integer ;
  … ]`), never as a parser's label, under the named subject that refers to it.
  An axiom annotation, a reified statement or a negative property assertion is
  listed under the subject it is about, and anything else under a new
  `BLANK-NODE STRUCTURES` section. Shared and cyclic structures are compared
  too. One that is not a tree and has more than 500 blank nodes is set aside,
  named before anything else in the output, and the run exits 1. `diff X X`
  now exits 0 for every IES fixture and every shipped example. New
  `examples/diff/v1.ttl` and `v2.ttl` differ only inside blank nodes (#149's
  `diff` slice), and `DIFF_GUIDE.md`'s blank-node sections are rewritten from
  their output.
- **`cq-test` refuses an ASK query checked with a count-based expectation**
  (#134). On an ASK, `has_results`, `no_results` and `count` counted the one
  boolean rdflib yields, so `has_results` and `count: 1` always passed and
  `no_results` and `count: 0` always failed, whether the ASK answered true or
  false; `min_results` and `max_results` likewise. The question is now
  reported as an `ERROR` naming its id and expectation and saying that an ASK
  takes `expect: true` or `expect: false`; the run exits 2, and the other
  questions still run. `results` and `contains` on an ASK give the same message
  instead of `TypeError: 'bool' object is not iterable`, and on a CONSTRUCT
  or DESCRIBE they are refused in the same way, saying that the query returns
  triples, instead of a `ValueError` about a dictionary update. JUnit types the
  `<error>` `InvalidExpectation`, and a query that fails to run stays
  `QueryError`. `expect: true|false` on a SELECT, CONSTRUCT or DESCRIBE still
  means "at least one row or triple", and its message no longer says "ASK
  query matched".
- **`split` places every subject of the source** (#176). It placed only
  classes and properties, so individuals, SKOS concepts, terms declared only by
  an OWL characteristic such as `owl:TransitiveProperty`, and the inside of
  every blank node were dropped at exit 0: `rdfs:subClassOf [ ]` stood where a
  restriction had been. #176's 18-triple reproducer kept 4; a 10,202-triple
  file lost 6,302. Now an individual goes to the module holding its class, a
  SKOS concept with its scheme, and a blank node with whatever refers to it.
  A borrowed vocabulary's declarations (`dcterms:title a
  owl:AnnotationProperty`) make no module of their own in a file with an
  ontology header (#383). Whatever has no single module goes to the unmatched
  module, which `--unmatched` now sees on `--by-namespace` too, and the run
  counts it by reason.
- **`split` gives each module an honest identity** (#178). Every module was
  called `http://example.org/<module>`, and its `owl:imports` named output files
  as `file://` paths on the machine that ran it. A module's IRI now comes from
  `ontology_iri:`, its own namespace, or the source ontology's IRI, and the run
  prints which; a namespace that is the source's own IRI, or that the source
  does not own (another host, or outside its own IRI on a shared host such as
  `purl.org`), is not used. `owl:imports` name ontology IRIs. The source's header is no longer
  lost without a trace: each module names it with `prov:wasDerivedFrom`, and
  no module copies its `owl:versionIRI`.
- **`split -c` runs** (#175). It crashed on every invocation with
  `NameError: UnmatchedStrategy`. Data split with `--migrate-data` keeps the
  data file's own prefixes (`org:`, not `org1:`).
- **A `split` config's `unmatched:`, `output_dir`, `dry_run` and
  `generate_manifest` take effect** (#291). The defaults of `--unmatched` and
  `-o` replaced them on every run.
- **`split --by-namespace` builds modules from the namespaces the source's
  classes and properties use** (#177). It took them from rdflib's prefix table
  instead, so every run wrote `brick`, `doap`, `geo`, `schema` and `void`
  modules holding one invented triple each, an empty file included. A file's
  own `org:` came out as `org1.ttl`, because rdflib binds `org` itself. Modules
  are now named after the prefixes the file declares. A namespace without one
  is named after its last path segment (`…/ontology#` → `ontology.ttl`), which
  covers N-Triples, undeclared namespaces and the empty prefix `:`. Clashing
  names get `-2`, `-3`, …. An entity belongs to the longest namespace that
  contains it, so with `env:` a prefix of `blg-class:`, the 185
  `blg-class:` terms of `ies-env-building-classification.ttl` now go to
  `blg-class.ttl`, not `env.ttl`. Module files bind the file's prefixes and
  rdflib's core five, never `org1:`. N-Triples input, which found no module
  and put everything in `common.ttl` at exit 1, now gets one module per
  namespace at exit 0. In a split configuration, a prefixed name in `classes:`
  or `properties:` now means the source's own prefix, and one the source does
  not bind fails the split instead of matching nothing. A configured module's `namespaces:` now match at a
  namespace boundary, as `merge`'s `namespace_remap` does since #184:
  `http://example.org/ont` takes `…/ont#Y` but no longer `…/ontology#X`.
  Placing entities
  no longer slows with the number of modules: 10,001 modules took 41 s and now
  take 13 s.
- **`merge` compares sources when it looks for conflicts** (#193). It put every
  source into one index and reported any predicate with two values, so a file
  merged on its own conflicted with itself: #193's three-language reproducer
  gave 3 conflicts, `ies-env-building.ttl` merged with itself 62, and a
  5,000-concept vocabulary in ten languages merged with itself 10,000. All of
  them are now 0. A conflict needs two sources whose values, merged, would
  assert a combination no single source asserts, on a predicate whose tier
  makes a second value a conflict. The tiers are one map in
  `rdf_construct.core.predicate_tiers`: `rdfs:comment`, `skos:altLabel`,
  `skos:note`, `rdfs:seeAlso` and every unlisted predicate (including
  `rdf:type` and `rdfs:subClassOf`) are repeatable; `rdfs:label` and
  `skos:prefLabel` conflict only within one language tag, compared without
  case; `rdfs:domain`, `rdfs:range` and any property a source declares
  `owl:FunctionalProperty` are load-bearing. A configuration file can move a
  predicate between tiers with `conflicts.predicate_tiers`. The ontology header
  is not checked until #171. Detection no longer slows quadratically with the
  values on one subject: 20,000 labels on one subject took 118.6 s and now take
  0.28 s.
- **`merge` applies the resolution it reports** (#169). The losing values of a
  per-language conflict are now removed from the output, so `priority`, `first`
  and `last` write different graphs. `rdfs:domain`/`rdfs:range` conflicts are
  never picked: both values are kept and marked, and the marker says that two
  values mean their intersection instead of telling you to delete one. A
  second `skos:prefLabel` in one tag is reported as malformed (SKOS S14), a
  second `rdfs:label` as ambiguous. Sources tied at the highest priority are
  not picked between: the conflict is marked and the run exits 1.
- **`merge` refuses a predicate in `ignore_predicates` that is not an IRI**
  (#193). `ignore_predicates: ["rdfs:label"]` silently matched nothing; a
  prefixed name is now refused with exit 2 until `merge` resolves prefixes by
  the project's binding rule (#357).
- **`merge` writes a blank-node structure its sources share once** (#170).
  Every restriction, `owl:unionOf` list or `owl:AllDisjointClasses` that two
  sources both stated was written twice, because each parse gives blank nodes
  fresh identities, and the duplicate was reported as a conflict. Merging #170's
  reproducer with itself read 7 triples, wrote 11, and found one conflict; it
  now writes 7 and finds none. Two structures are the same only when they are
  identical, including the subject that refers to them. The same restriction
  under two different classes, or a person called "Bob" known by two different
  people, stays two. A file merged with itself, or alone, comes back unchanged,
  even if it states something twice. The labels of blank nodes that `merge`
  writes as `_:…` are now derived from their content, so they no longer change
  from run to run.
- **`uml` no longer draws an anonymous class expression as a class** (#280).
  A context with `selector: classes` drew the `owl:unionOf` behind a property's
  range as a box named after a fresh blank-node label, with the range arrow
  pointing at it. The box is gone. That range is not drawn at all, because `uml`
  has no notation for a class expression. None of the shipped examples contains
  one.
- **`docs` refuses what it cannot use, with a message instead of a traceback**
  (#301). A source that does not parse, in any format, a directory given as a
  source, a malformed `-C` config, a `--template` directory without the HTML
  entry template the run starts from (`html/index.html.jinja`, or
  `html/single_page.html.jinja` with `--single-page`), and an `-o` that is, or
  sits under, a file now exit 2 with a message naming the file. A parse failure
  carries rdflib's line and excerpt. The exit code was already 2, but it came
  from the crash handler, with a traceback that read as a bug. Every check runs
  before anything is written, so a refused run no longer leaves an empty output
  directory behind, as a bad `--template` did.
- **`refactor` resolves CURIEs, against the source's own prefixes** (#182).
  `--from ex:Buiding --to ex:Building`, the form `--help` documents, renamed
  nothing and exited 0, and a CURIE in `--to` or `--replaced-by` was written
  into the graph as the IRI `<ex:Building>`. `--from`, `--to`, `--entity`,
  `--replaced-by` and a config file's entities now resolve against the
  prefixes the file declares, plus `rdf`, `rdfs`, `owl`, `xsd` and `xml`, never
  against rdflib's built-in table. A file's own `org:` is no longer read as the
  W3C Organization ontology, and is written back as `org:`, not `org1:`. A
  prefix no source binds, or one that two sources bind differently, is refused
  at exit 2 before anything is written. Write a URN as `<urn:…>`.
- **A namespace rename stops at the namespace boundary** (#184).
  `refactor rename --from-namespace`, `merge`'s `namespace_remap` and data
  migration matched by string prefix, so moving `http://example.org/ont` also
  rewrote `http://example.org/ontology#` as `http://example.org/NEWology#`. A
  namespace ending in `#`, `/` or `:` now matches as given. One without a
  delimiter matches only where the next character is `#`, `/` or `:`, or where
  the IRI ends.
  `merge` now also moves the prefix binding of every namespace it remaps, not
  only a binding that equals the remapped namespace exactly.
- **Config keys are no longer overwritten by the defaults of flags you did not
  pass** (#206, #225, #251). Click supplies an option's default whenever the
  flag is absent, and `lint`, `shacl-gen` and `docs` copied those defaults over
  the loaded config, so the keys did nothing. A flag is now applied only when it
  was given, even at its default value. Fixed: `lint`'s `level:`, including in
  an auto-discovered `.rdf-lint.yml`; `shacl-gen`'s `level:` and
  `default_severity:`; and `docs`' `output_dir`, `format`, `single_page` and the
  four `include_*` keys, which a config could not turn off.
- **`lint --list-rules` and `lint --init` run without a source** (#202). Both
  are documented as standalone, but `SOURCES` was required, so Click refused
  them with "Missing argument" unless a file was passed, which they then
  ignored. A source given alongside either is still ignored. A bare `lint`
  still exits 2, now with "No source files specified."
- **`sort: topological` no longer turns alphabetical on inferred graphs** (#339).
  RDFS entailment materialises `C rdfs:subClassOf C` for every class (`rdfs10`)
  and `P rdfs:subPropertyOf P` for every property (`rdfs6`). Each self-loop was
  treated as a cycle, so the term and everything beneath it fell out of the
  sort and was emitted alphabetically. A self-loop is a tautology, not a cycle,
  and is now ignored. Graphs without self-loops order exactly as before.
- **`sort: topological` is no longer quadratic** (#300). Each sort key is computed
  once and the ready set is a heap, so 6,000 classes sort in 0.11 s instead of
  6.0 s (3,000: 2.4 s → 0.05 s). The order produced is unchanged.
- **`python -m rdf_construct` now runs the CLI** (#200). `__main__.py` was
  empty, so the module form exited 0 having done nothing. It now behaves exactly
  like the `rdf-construct` script, and its usage line names `rdf-construct`.
- **`puml2rdf` no longer doubles the class count for packaged diagrams** (#154).
  Each class is stored under both `name` and `qualified_name` for relationship
  lookup; the summary now counts distinct URIs so it matches the parse line.

## [0.6.0] - 2026-09-04

Completes the `docs` entity-type taxonomy carried over from v0.5.0, and fixes
much of the output around it: links that resolved from the wrong place, entity
filtering that was honoured by page generation but not by links, non-reproducible
search output, and a badge palette in which four of twelve colours failed WCAG AA
contrast.

**If you consume the JSON output, two arrays have moved.** `skos:Concept` and
`skos:ConceptScheme` subjects leave `instances` for top-level `concepts` and
`concept_schemes`; properties whose kind the source does not state leave it for
`other_properties`. Both are described below, and both mirror what v0.5.0 did for
shapes.

**If you publish generated HTML, ten of the twelve badge colours have changed.**
The palette was re-derived as a set so that all of them clear WCAG AA — four did
not — and so that no two are closer than 5.3 CIEDE2000 units under simulated
colour-vision deficiency. Only the class and shape badges keep their previous
values. Regenerated documentation will look different.

**If you run `order` with a hand-written profile, check your selector names.** A
section whose `select:` names something that cannot be resolved now fails the run
instead of silently emitting a file with that section missing. A profile that has
been quietly producing short output will start reporting it.

Everything else is additive.

### Added
- **First-class SKOS support in the `docs` command** (#63). `skos:Concept` and
  `skos:ConceptScheme` are now rendered as a distinct entity type alongside
  Classes, Properties, Instances and Shapes, in HTML, Markdown and JSON output:
  - Concepts and schemes get their own pages under `concepts/`, sharing the
    directory and distinguished by kind badges (`skos concept`,
    `skos concept scheme`) — the arrangement NodeShapes and PropertyShapes
    already have in `shapes/`
  - Labels are grouped **by language**: one row per language tag carrying
    `skos:prefLabel`, `skos:altLabel` and `skos:hiddenLabel` together, rather
    than rendering as duplicate triples
  - All **seven** SKOS documentation properties render with their language
    tags — `skos:definition`, `skos:scopeNote`, `skos:example`, `skos:note`,
    `skos:historyNote`, `skos:editorialNote` and `skos:changeNote` (the
    seventh is beyond the six the issue listed, but the SKOS spec defines it
    alongside them and it was already being collected)
  - `skos:broader` / `skos:narrower` render as a tree on the scheme page and
    as inline cross-links on each concept page. **`skos:broader` is not
    treated as `rdfs:subClassOf`** — nothing is inherited along it; the tree
    is a navigation aid
  - `skos:broader`/`skos:narrower` are materialised **in both directions**,
    since SKOS declares them inverses, so a vocabulary that asserts only one
    direction documents the same hierarchy. `skos:related` is treated as
    symmetric and `skos:topConceptOf` as implying `skos:inScheme`, which it is
    a sub-property of
  - **Cyclic `skos:broader` is tolerated.** SKOS does not promise acyclicity:
    the tree walker never expands a concept twice on one path, and any concept
    a cycle leaves unreachable from a root is promoted to a root rather than
    silently dropped
  - `skos:inScheme` membership renders on both sides — the concept links to
    its scheme, the scheme lists its members. A concept in **no** scheme is
    still documented
  - Mappings (`skos:exactMatch` and friends) and any other predicate get a
    visible key-value fallback rather than being dropped
  - Search index entries cover concepts and schemes, indexing alternative and
    hidden labels across all languages — hidden labels exist to catch
    misspellings, which is exactly what a search index is for
  - New `--no-skos` flag; `concepts` accepted in `--include` / `--exclude`;
    new `include_skos` config key. One toggle covers both SKOS kinds
  - `skos:Collection`, `skos:OrderedCollection` and SKOS-XL are deferred —
    no real-world material in the test set exercises them
- New `EntityKind` members `SKOS_CONCEPT` and `SKOS_CONCEPT_SCHEME`, and new
  `ConceptInfo`, `ConceptSchemeInfo`, `ConceptNode`, `LabelGroup` and
  `NoteValue` dataclasses, all exported from `rdf_construct.docs` along with
  `build_concept_tree()`
- New tracked SKOS test fixture (`tests/fixtures/docs/skos_vocabulary.ttl`).
  The repository previously contained no `skos:Concept`, `skos:ConceptScheme`,
  `skos:broader`, `skos:narrower` or `skos:inScheme` at all, so there was
  nothing to demonstrate the feature against. It deliberately includes a
  `skos:broader` cycle, which is why it is a fixture rather than a shipped
  example
- SKOS badge colours, chosen against measured figures rather than by eye:
  `skos_concept` `#1d4ed8` (6.70:1 against white) and `skos_concept_scheme`
  `#1e3a8a` (10.36:1), both clearing WCAG AA for normal text. The indigo
  family originally proposed was rejected on measurement — it sits 11.3
  CIEDE2000 units from the existing object-property violet (10.7 under
  simulated deuteranopia); blue keeps 15.3 / 17.7 / 21.3 (normal /
  deuteranopia / protanopia). Its weakest axis is tritanopia at 6.0 against
  the instance emerald, where the badge's text label carries the category
- **`owl:NamedIndividual` surfaced as a distinct kind** (#64). An entity
  explicitly typed `owl:NamedIndividual` now carries a `named individual`
  badge in HTML and Markdown, and `"named_individual"` in its `kinds` array
  in JSON:
  - This is a refinement on an entity's existing kinds, **not** a new
    bucket. Named individuals stay where they were routed — an individual
    under `instances/`, a SKOS concept under `concepts/`, a NodeShape under
    `shapes/`. No new directory, no new top-level JSON array, no CLI flag,
    and nothing breaking
  - The badge shows whenever the declaration is **asserted**, including when
    it is redundant in OWL DL terms (an entity that already has a class
    typing). `kinds` records what the source says rather than what a
    reasoner could infer, consistently with every other kind — and the
    redundancy is itself information: it says the author was explicit
  - An entity typed *only* `owl:NamedIndividual`, with no class typing at
    all, is documented as an instance carrying the kind — that declaration
    is the only thing marking it as an individual
  - No false positives: an entity typed only by its class carries just
    `["instance"]`. Classes and properties never gain the kind
  - Searchable — the kind joins the entity's search keywords, so a literal
    search for `named_individual` finds them. The search `entity_type` is
    unchanged, so named individuals are not a separate search bucket
  - `rdfs:Datatype` and `owl:DeprecatedClass` / `owl:DeprecatedProperty`
    remain out of scope. Deprecation is orthogonal to entity kind and needs
    its own design
- **Deprecated terms are now marked in `docs` output** (#108). A term the
  source marks deprecated carries a visible marker — an outlined badge beside
  its kind badge in HTML, a `> **Deprecated.**` banner on Markdown pages, a
  `deprecated` boolean in JSON, and a `deprecated` search keyword. Previously
  the only trace was a row in the annotations table, next to `seeAlso`:
  - **Both OWL mechanisms are recognised** — an `rdf:type` of
    `owl:DeprecatedClass` / `owl:DeprecatedProperty`, and the `owl:deprecated`
    annotation. Real ontologies use either or both, and before this the type
    form produced no trace at all
  - **The annotation is read by value, not presence.** `owl:deprecated false`
    is legal and means the opposite; truthiness alone gets it backwards,
    because an untyped `"false"` literal is a non-empty string
  - **Deprecation is orthogonal to entity kind**, so it is a marker rather
    than an `EntityKind` member: a class, any property, an instance, a SKOS
    concept and a SHACL shape can each be deprecated, and each keeps its own
    kind badge. Nothing changes bucket
  - **It does not propagate** — a property whose domain is a deprecated class
    is not itself marked, and nor are the subclasses of one
  - The badge is an outline rather than a fill, so it composes with a kind
    badge instead of competing with one, and needs no slot in the kind palette
  - Deprecated terms are still documented; hiding them behind a flag needs
    per-entity link handling rather than the per-type `--include` / `--exclude`
    machinery, so it is deferred
- New `EntityKind` member `NAMED_INDIVIDUAL`, and a new tracked fixture
  (`tests/fixtures/docs/named_individuals.ttl`) — the repository previously
  contained no `owl:NamedIndividual` in any RDF file
- Named-individual badge colour `#047857`, 5.48:1 against white (clears
  WCAG AA), a deeper emerald than the `#10b981` instance badge it sits
  beside so the two read as one family — 21.7 CIEDE2000 units apart in
  normal vision, 15.3 under simulated deuteranopia

### Changed
- **Breaking (JSON output):** `skos:Concept` and `skos:ConceptScheme` subjects
  have left the `instances` array for new top-level `concepts` and
  `concept_schemes` arrays, mirroring what v0.5.0 did for shapes. The
  `statistics` block gains `concepts` and `concept_schemes` counts. Consumers
  reading `instances` for SKOS entities must read the new arrays
- A subject typed both `skos:Concept` and `owl:Class` (or a property, or a
  SHACL shape) keeps its existing page and does not gain a second one: classes,
  properties and shapes outrank SKOS in routing. It remains listed as a member
  of its scheme, cross-linked to the page it does have

### Fixed
- **Markdown cross-references now resolve from the page that contains them**
  (#87, contributed by @tasodoufu). Entity links were emitted as a path from
  the docs root regardless of where the page sat, so from `classes/Dog.md` a
  link to `Mammal` read `classes/Mammal.md` and resolved as
  `classes/classes/Mammal.md` — broken in GitHub's blob view, in MkDocs and in
  any local previewer. The renderer now threads the page being written through
  to the link helper, as the HTML renderer has done since #59. Two follow-ons
  landed with it:
  - `render_concept` and `render_concept_scheme` set the current page too.
    Without it the SKOS pages inherited whatever rendered last, which happened
    to be the right depth when instances were present and one level too high
    when they were not — 38 wrong-depth links under `--no-instances`
  - Link extensions are stated rather than derived from `config.format`, whose
    map knows `"markdown"` but not the `"md"` alias `DocsGenerator` accepts.
    Under that alias the files were written `.md` while every link pointed at
    `.html`
  A Markdown link walk now covers all of it — the counterpart of the HTML walk
  that has caught this class of bug since #60, and whose absence is a fair part
  of why #87 lasted as long as it did
- **Every entity-kind badge now clears WCAG AA contrast** (#106). Four failed
  outright — `annotation` 2.15:1, `datatype` 2.43:1, `instance` 2.54:1 and
  `object` 4.23:1, against badge text that is 12px bold and so needs 4.5:1,
  not 3.0:1. The closest pair in the palette was also 2.1 CIEDE2000 units
  apart, below the ~2.3 just-noticeable difference:
  - The palette was **re-derived as a set**, not patched colour by colour,
    because darkening one badge to pass moves it toward its neighbours.
    Chosen by constrained search: maximise the smallest pairwise distance
    across normal vision and simulated deuteranopia, protanopia and
    tritanopia, subject to the contrast floor, to each family keeping its hue,
    and to the derived kind staying the darker of its pair. Worst pair is now
    **5.3**, lowest contrast **4.71:1**
  - **Hue identity is preserved wherever a badge has shipped** — classes stay
    blue, object properties violet, datatypes cyan, annotations amber,
    instances emerald, shapes red-rose. Only the shade moves
  - **SKOS moves from blue to fuchsia.** It collided with the Class badge,
    which has always been blue via `--primary-colour`; SKOS arrived in this
    unreleased version, so no user has ever seen it and the move costs nothing
  - The **Class badge was missing from the original inventory** — it carries
    no kind class and falls through to `--primary-colour`, so it was invisible
    to a survey of `.entity-type.*` rules. It passes at 5.17:1 and is unchanged
  - A test now reads the stylesheet the renderer emits and fails if any badge
    drops below AA, so a kind added later cannot ship unchecked
- **`order` now fails on a section whose `select:` names a selector nothing can
  resolve** (#89), instead of selecting nothing and saying nothing. The section
  simply vanished from the output — the same failure shape as #84 one level
  down: there a *profile* claimed nothing, here a *section* did. Worse, the
  unclaimed-subjects warning added in #88 then misdiagnosed it, telling the user
  to "add a section with `select: obj_props`" when their profile had exactly
  that section, misspelled. The run now exits 2, names the profile and the
  section, and lists both the built-in selector keys and the ones the config
  defines. Two spellings are affected: a key that resolves to nothing at all,
  and a key defined in `selectors:` whose *value* is not one this version
  recognises
- **The shipped `templates/ordering_starter.yml` now runs.** It defines each
  selector as a YAML list, and selector resolution called `.strip()` on the
  value — so the template the documentation tells users to copy exited 1 with an
  `AttributeError` traceback. Non-string values no longer crash: a built-in key
  dispatches on its name regardless, and anything unresolvable gets the
  actionable error above. Found while fixing #89, on the same line
- **`--include` / `--exclude` are now honoured by links, not just by page
  generation** (#115). Filtering decided what was *generated* and nothing
  decided what was *linked to*, so excluding an entity type filled the output
  with links to pages that were never written. The workflow DOCS_GUIDE
  advertises as "only classes" produced **43 dead links** in HTML. Two causes,
  both fixed:
  - Four of the six index sections checked their config flag — the ones added
    in #60, #63 and #76 — and the older Classes, Object Properties and
    Datatype Properties sections did not. Same split in the Markdown index,
    and in the index statistics cards
  - Entity pages cross-linked to excluded entities. A class page linked to its
    properties with no guard, which is why `--exclude properties` broke every
    class page while `--exclude instances` broke nothing: the Instances section
    of that same template was already guarded
  A reference to an excluded entity is now rendered **unlinked but still
  visible** (`ex:hasPart` in code formatting) rather than dropped — a document
  that filtered properties out of the *documentation* must not imply the class
  has no properties. Output with default configuration is byte-identical
- **Single-page Markdown no longer links to pages it never writes** (#113).
  `--format markdown --single-page` produces exactly one file, but rendered
  cross-references as links to each entity's own page — `concepts/Dwelling.md`,
  `classes/Person.md` — every one of them dead. Both the SKOS section and the
  Shapes section were affected; the latter since v0.5.0. References now render
  as the entity's qname in code formatting, which stays greppable within the
  single document and matches what the HTML single-page template already did.
  Multi-page Markdown output is unchanged, byte for byte
- **`docs` output is now byte-reproducible between runs** (#107). Keyword lists
  in `search.json` were built with `list(set(...))`, and Python randomises
  string hashing per process, so two runs over identical input produced a
  different key order every time — for every entity kind. Regenerating a
  committed docs site showed a diff with no semantic change, and the project's
  own verification technique (generate output at two commits and diff it) could
  not be used on this command without pinning `PYTHONHASHSEED`. Keyword order
  has never been meaningful to `search.js`, which substring-matches over the
  whole list
- **The search overlay now works on every page, not just the three at the docs
  root** (#86). `assets/search.js` made two root-relative assumptions that the
  #59 fix did not reach, because that fix covered the Jinja templates only:
  - It fetched `search.json` page-relatively, so from `classes/Dog.html` the
    browser requested `classes/search.json`, got a 404, and the index never
    loaded — typing in the box did nothing at all, with no error and no
    empty-results message. On `examples/animal_ontology.ttl` the index was
    unreachable from **16 of 19 pages**
  - It injected the index's root-relative result URLs verbatim as hrefs, so a
    result clicked from a sub-folder page resolved one level too deep —
    **256 broken (page, result) pairs** on the same corpus
  Both now resolve against a per-page `window.DOCS_ROOT`, set by
  `base.html.jinja` from the same `link_root` every other link already uses, so
  an explicit `base_url` keeps working unchanged
- **The search box now says why it is unavailable under `file://`** instead of
  rendering and silently doing nothing. `fetch` is CORS-blocked on `file://`
  whatever the path, so search genuinely cannot work from a double-clicked
  page; the input is disabled and explains itself
- **`docs` no longer misfiles properties declared only by an OWL characteristic**
  (#76). A term declared solely `owl:TransitiveProperty`, `owl:SymmetricProperty`,
  `owl:AsymmetricProperty`, `owl:ReflexiveProperty`, `owl:IrreflexiveProperty`
  or `owl:InverseFunctionalProperty` was extracted as a generic **instance** and
  documented as an individual — the extractor recognised only `owl:ObjectProperty`,
  `owl:DatatypeProperty`, `owl:AnnotationProperty` and `rdf:Property`. All six are
  subclasses of `owl:ObjectProperty` in OWL 2, so they are now documented as object
  properties. `owl:DeprecatedClass` had the same problem on the class side and is
  now documented as a class
- **Properties whose kind the source does not state now have somewhere to go.**
  `owl:FunctionalProperty` and `owl:DeprecatedProperty` are subclasses of
  `rdf:Property` only, so nothing says whether such a term is an object or a
  datatype property. These, and plain `rdf:Property` declarations, are documented
  under `properties/other/` with a neutral `rdf property` badge (`#334155`,
  10.35:1 against white), listed in an **Other Properties** section, and carried
  in a new top-level `other_properties` JSON array. `rdf:Property`-only terms
  previously got **no page at all**: they were extracted, routed to an unreachable
  `other/` directory and never rendered
- The `docs` extractor now takes its class and property type sets from
  `rdf_construct.core.vocab` rather than repeating shortened lists, so the sets
  cannot drift between commands again. The `order` command moved to them in v0.5.0
- New `include_other_properties` config key; `other_properties` accepted in
  `--include` / `--exclude`, and `properties` covers it

### Contributors
- Thanks to @tasodoufu for diagnosing and fixing #87, and for reviewing the
  follow-on commit that closed the two gaps `main` had opened underneath it

## [0.5.0] - 2026-08-22

### Added
- **First-class SHACL shape support in the `docs` command** (#60). NodeShapes
  (`sh:NodeShape`) and named PropertyShapes (`sh:PropertyShape` with their own
  URI) are now rendered as a distinct entity type alongside Classes, Properties,
  and Instances, in HTML, Markdown, and JSON output:
  - Each shape gets its own page under `shapes/`, with kind badges
    (`shape`, `node_shape`, `property_shape`) distinguishing NodeShapes from
    named PropertyShapes
  - The 21 most-used SHACL constraints (`sh:path`, `sh:minCount`, `sh:maxCount`,
    `sh:datatype`, `sh:class`, `sh:nodeKind`, `sh:in`, `sh:hasValue`,
    `sh:pattern`, `sh:minLength`, `sh:maxLength`, `sh:minInclusive`,
    `sh:maxInclusive`, `sh:targetClass`, `sh:targetNode`, `sh:targetSubjectsOf`,
    `sh:targetObjectsOf`, `sh:closed`, `sh:ignoredProperties`, `sh:name`,
    `sh:description`) get explicit per-format rendering; everything else
    (including `sh:severity`, `sh:order`, `sh:qualifiedValueShape`, etc.) falls
    back to a generic visible-but-plain key-value display rather than being
    silently dropped
  - Blank-node PropertyShapes attached to a NodeShape via `sh:property` render
    inline on the parent shape's page as a constraint table; named
    PropertyShapes get their own pages plus an inline reference + link from any
    NodeShape that uses them
  - `sh:targetClass`, `sh:path`, and references to named PropertyShapes resolve
    to clickable cross-references when the target is in the ontology, falling
    back to plain code-formatted URIs otherwise
  - Logical operators (`sh:and`, `sh:or`, `sh:xone`) and `sh:qualifiedValueShape`
    are deferred — they need their own design pass and will be handled in a
    future release
- **Multi-kind data model.** Entities now carry a `kinds` list of
  `EntityKind` enum members. Default values: `[CLASS]` for classes,
  `[PROPERTY, <type>_PROPERTY]` for properties, `[INSTANCE]` for instances,
  and `[SHAPE, NODE_SHAPE]` / `[SHAPE, PROPERTY_SHAPE]` for shapes. A NodeShape
  that is also typed `owl:NamedIndividual` is placed in the Shapes section
  rather than Instances, so it is documented once rather than twice. It does
  not yet carry a named-individual kind — there is no `NAMED_INDIVIDUAL` member
  in the enum, and recognising that type is stage 2/3 work. The `kinds` list is
  the extension point for it, and for SKOS support
- New `other_props` selector for properties whose kind is not implied by their declaration —
  `rdf:Property`, `owl:FunctionalProperty`, `owl:DeprecatedProperty`. These remain visible to
  the `individuals` selector, so existing profiles keep emitting them; adding an `other_props`
  section before `individuals` groups them instead
- New `rdf_construct.core.vocab` module holding the class and property type sets in one place,
  so consumers no longer reproduce (and shorten) the list
- New `EntityKind` enum (str-mixin) exported from `rdf_construct.docs`,
  centralising kind values. Members: `CLASS`, `PROPERTY`, `OBJECT_PROPERTY`,
  `DATATYPE_PROPERTY`, `ANNOTATION_PROPERTY`, `RDF_PROPERTY`, `INSTANCE`,
  `SHAPE`, `NODE_SHAPE`, `PROPERTY_SHAPE`. Compares equal to its string
  values and serialises to JSON as plain strings
- New `ShapeInfo` and `PropertyShapeInfo` dataclasses, exported from
  `rdf_construct.docs`. `ShapeInfo` covers NodeShapes and named PropertyShapes;
  `PropertyShapeInfo` covers individual property constraint blocks (whether
  blank-node arcs of a NodeShape or top-level constraint sets of a named
  PropertyShape)
- New `extract_all_shapes()` extractor and `extract_shape_info()` /
  `extract_property_shape_info()` helpers
- New `ExtractedEntities.shapes`, `node_shapes`, and `property_shapes` fields
  / computed properties
- New `DocsConfig.include_shapes` flag (default `True`) parallels
  `include_instances`. When `False`, shapes are excluded from the output
  pages and from the search index
- New `--no-shapes` CLI flag and `shapes` accepted in the `--include` /
  `--exclude` filter values
- New `shape.html.jinja` template; `shape` entity type added to
  `entity_to_path` / `entity_to_url` routing under `shapes/`
- CSS for shape badges in HTML output: `.entity-type.shape` (`#dc2626`,
  4.83:1 contrast), `.entity-type.node_shape` (`#b91c1c`, 6.47:1),
  `.entity-type.property_shape` (`#e11d48`, 4.70:1) — all WCAG AA against
  the badge's white text. Single hue family (red-rose) signals
  NodeShape/PropertyShape kinship; brightness gradient reads as
  parent-child. Distinct from the existing purple/cyan/amber/green
  badges under common colour-vision deficiencies; descriptive uppercase
  badge text labels (`"NODE SHAPE"`, `"PROPERTY SHAPE"`) carry the
  category meaning regardless of perceived colour
- `BaseRenderer.render_shape()` abstract method, implemented in all three
  renderers (HTML / Markdown / JSON)
- Comprehensive test coverage: 44 new tests in 7 classes covering shape
  extraction, multi-kind handling, all three renderers, JSON schema, search
  index integration, the `include_shapes` toggle, routing, and the
  `EntityKind` enum contract
- `order` profiles accept an `unclaimed` policy, in `defaults:` or on an individual
  profile, controlling what happens to subjects no section of the profile claims:
  `warn` (default) reports the loss on stderr and exits 0, `emit` appends them in a
  trailing section so nothing is lost, and `ignore` is silent — for a profile such as
  `test_profile.yml`'s `compact` that filters on purpose. The warning names the terms
  and the `select:` key that would have claimed them (#84)

### Changed
- **Breaking change to JSON output**: SHACL shapes used to appear in the
  `instances` array of `index.json` and `ontology.json` because the extractor
  didn't filter them out. They now have their own top-level `shapes` array,
  and shapes have been removed from `instances`. JSON consumers updating from
  v0.4.x must read both arrays to see all entities. The new top-level
  `shapes` array contains complete `ShapeInfo` JSON for each shape (single-page
  mode) or summary entries (index mode) — see `docs/user_guides/DOCS_GUIDE.md`
  for the full schema. The `statistics` object also gains a `shapes` count (#60)
- All entity entries in JSON output now include a `kinds` array carrying the
  full multi-kind list. Existing fields are unchanged. This is additive —
  consumers that ignore unknown fields are unaffected (#60)

### Fixed
- `rdf-construct --version` reports the version in the source rather than the one recorded
  in the installed distribution metadata. `@click.version_option()` with no argument
  resolves through `importlib.metadata`, so an editable install whose metadata predated a
  version bump reported the stale number — v0.4.0 for a v0.4.7 checkout — until someone
  re-ran `poetry install`. The same call also named the group function rather than the
  tool, printing `cli, version …`; it now prints `rdf-construct, version …` (#66)
- `order` no longer emits an empty `[ ]` in place of a blank node that no section
  claimed. `build_section_graph()` copies triples by subject, so an `owl:Restriction`
  or an `owl:unionOf` list lost its own triples while the reference to it survived —
  producing not a partial ontology but a different one, asserting an anonymous class
  with no axioms. Blank nodes reachable from the selected subjects are now pulled in
  transitively, whatever the `unclaimed` policy says: a blank node carries no identity
  a profile could select it *by*, so it belongs to the description of whatever
  references it (#84)
- `order` no longer silently drops subjects that no profile section claims. Copying the
  shipped `examples/order/sample_profile.yml` was enough to hit it: its `doc_order` and
  `props_by_domain` profiles had no `annotation_properties` section, so
  `animals:scientificName` and its three triples were absent from the output with no
  warning and exit code 0. Both those profiles — and the matching pair in
  `ies_profile.yml` — now have the missing section, and the default policy reports any
  remaining gap (#84)
- `order` no longer drops terms declared only as `rdf:Property`. They were excluded from the
  `individuals` selector while no other selector claimed them, so their triples were silently
  absent from the ordered output — 10 triples in, 8 out, with no warning
- Terms declared only by an OWL property characteristic (`owl:TransitiveProperty`,
  `owl:SymmetricProperty`, `owl:AsymmetricProperty`, `owl:ReflexiveProperty`,
  `owl:IrreflexiveProperty`, `owl:InverseFunctionalProperty`) are now selected as object
  properties rather than classified as individuals. Each is a subclass of `owl:ObjectProperty`
  in OWL 2, and declaring one alone is legal and common in older ontologies
- `owl:DeprecatedClass` is now recognised by the `classes` selector
- Quoted the CURIEs in the `together:` flow sequences of `examples/uml/uml_layouts.yml`. Unquoted
  `building:Building` inside `[ … ]` is rejected by stricter YAML parsers than the one this project
  uses, so the example failed to load for anyone whose toolchain is spec-conformant. The parsed
  data is unchanged
- `docs` no longer emits leading-slash paths (`/assets/style.css`, `/index.html`, …) for the
  stylesheet, the navigation tabs and the search script when `base_url` is unset. These
  resolved against the filesystem or web root rather than the docs directory, so the generated
  documentation was unstyled and unnavigable under `file://` and under any sub-path host
  (GitHub Pages project sites among them). The same root cause also broke entity-to-entity
  links from sub-folder pages, where a bare `classes/Animal.html` resolved as
  `classes/classes/Animal.html` — 62 of the 157 broken references in a 19-page sample. Layout
  assets and entity links are now resolved relative to the page being rendered (`./` at the
  root, `../` under `classes/` and `instances/`, `../../` under `properties/object/` and its
  siblings); an explicitly configured `base_url` still takes precedence and produces the same
  absolute URLs as before (#59)
- Fixed `_walk_rdf_list` and `extract_property_shape_info` silently truncating
  `rdf:List` members at the first cell when the list-rest pointer was a blank
  node (the rdflib default representation). In practice this meant `sh:in`
  constraints with multiple values lost everything except the first member
  during extraction. Both call sites now accept blank-node list pointers.
  Found while writing tests for #60

### Contributors
- Thanks to @otellomaria for reporting #59 with a clean reproducer
- Thanks to @algojogacor, @hyldmh and @mayank-dev-15, who each independently diagnosed the same
  root cause and proposed a fix for it in #67, #68, #70 and #71

**Note:** `docs` entity extraction has the same gap that `order`'s selectors had — a property
declared only by an OWL characteristic is missed. It is not addressed here and is tracked as #76.

**Note:** the #59 fix covers the generated HTML only. Two related defects with the same root cause
remain, both raised out of it: the search overlay is inert on any sub-folder page (#86), and the
Markdown renderer emits root-relative entity links (#87).

## [0.4.7] - 2026-05-07

### Fixed
- Fixed `lint --init` generating a malformed first line in the "Available rules" comment
  block: a stray `# ` prefix outside the f-string caused the first rule to render as
  `# #   - <rule>` while subsequent rules rendered correctly. Cosmetic only — the
  generated config remained valid YAML — but visually inconsistent (#58)

### Contributors
- Thanks to @otellomaria for their first contribution to rdf-construct

## [0.4.6] - 2026-03-27

### Fixed
- Fixed `order` command emitting SPARQL-style `PREFIX` declarations instead of valid Turtle
  `@prefix … .` directives. Strictly conformant parsers (triple stores, validators, rdflib in
  strict mode) reject the `PREFIX` form, which is N3/SPARQL syntax not valid Turtle per the
  W3C spec (#56)

## [0.4.5] - 2026-03-17

### Added
- New documentation guide: `docs/user_guides/CAST_GUIDE.md` covering pipe mode, file output,
  format aliases, quad flattening, prefix binding behaviour, programmatic API, and examples

### Changed
- Updated `docs/user_guides/CLI_REFERENCE.md` with full `cast` command section (options, format
  aliases table, pipe mode note, examples, workflow snippet)
- Updated `docs/user_guides/QUICK_REFERENCE.md` — added `cast` to commands table, new Format
  Conversion section, output formats table, and Cast Guide link
- Updated `docs/user_guides/GETTING_STARTED.md` — command count 14 → 15, added Format
  conversion category with `cast` and `puml2rdf`, added cast to CI/CD pattern and Next Steps

## [0.4.4] - 2026-03-17

### Added
- **New `cast` command** for converting an RDF file between serialisation formats (#53)
  - Accepts any format rdflib can parse: `ttl`, `turtle`, `n3`, `nt`, `ntriples`, `xml`, `rdf`,
    `rdfxml`, `json-ld`, `jsonld`, `trig`, `nq`, `nquads`
  - **Unix pipe-friendly**: a single `--format` flag writes RDF to stdout with all diagnostics
    routed to stderr — `rdf-construct cast ontology.ttl --format n3 | grep rdf:type` works as
    expected
  - Multiple `--format` flags write one output file per format to the output directory
  - Default output (no `--format`): converts to `ttl`, `xml`, and `json-ld`, excluding the
    source format
  - `--output-dir` overrides the output directory (default: same directory as source)
  - `--allow-flatten` merges all named graphs into the default graph when converting from a
    quad format (TriG, N-Quads) to a single-graph format; without this flag, such conversions
    are rejected with a clear error
  - Source format equal to target format: warns and skips without error
  - Exit codes: 0 (success), 1 (partial failure — some formats failed), 2 (complete failure)
- New module `src/rdf_construct/core/formats.py` — shared format utilities
  - `normalise_format()`: normalises format aliases (`"ttl"` → `"turtle"`, etc.)
  - `infer_format()`: infers rdflib format from file extension
  - `extension_for_format()`: returns preferred output extension for a canonical format
  - `is_quad_format()`: detects multi-graph formats (TriG, N-Quads)
  - `default_cast_formats()`: computes default output format set excluding source format
  - Exported from `rdf_construct.core` for use by other commands
- New module `src/rdf_construct/cast/` — programmatic conversion API
  - `CastConverter.convert()`: callable as a Python API independently of the CLI
  - `ConversionResult` dataclass with `success`, `partial_failure`, `written_files`,
    `stdout_content`, `warnings`, `failed_formats`, and `error` fields

## [0.4.3] - 2026-03-17

### Fixed
- Fixed `order` command expanding anonymous (implicit) blank nodes into separate top-level named stubs. Blank nodes with exactly one incoming arc are now serialised using Turtle's `[ … ]` inline syntax, preserving authorial intent and readability. Blank nodes referenced by more than one triple, or that are reification stubs, continue to be emitted as top-level `_:bN` subjects (#51)
- Fixed `format_term()` emitting bare rdflib internal identifiers (e.g. `Nff2ed53a…`) for stub blank nodes instead of the `_:id` form required by the Turtle grammar, which caused parse failures on round-trip

## [0.4.2] - 2026-02-05

### Fixed
- Fixed `order` command outputting extraneous prefix declarations (e.g. `brick:`, `csvw:`, `foaf:`, `odrl:`) that were not present in the source file. rdflib's `Graph()` auto-registers ~30 well-known namespace defaults; the serialiser now uses `bind_namespaces="none"` and explicitly binds only namespaces actually used in the output triples (#49)
- Fixed `collect_used_namespaces` not scanning `Literal.datatype` URIs, causing datatype namespaces like `xsd:` to be dropped from the output when no other terms used them
- Added `namespace_source` parameter to `collect_used_namespaces` to support scanning one graph's triples while matching against another graph's namespace registry

### Changed
- `build_section_graph` now creates its sub-graph with `bind_namespaces="none"` and binds only used namespaces from the base graph, ensuring clean prefix declarations in output

## [0.4.1] - 2026-01-06

### Fixed
- Fixed `lint` command crash with `AttributeError: 'TextFormatter' object has no attribute 'format_summary'` caused by import name collision between `rdf_construct.lint.get_formatter` and `rdf_construct.merge.get_formatter`

## [0.4.0] - 2026-01-03

### Added

- **New `describe` command** for quick ontology orientation
  - Provides comprehensive analysis of unfamiliar ontology files
  - Metadata extraction: title, version, description, license, creators
  - Basic metrics: triples, classes, properties (object, datatype, annotation), individuals
  - Profile detection: RDF, RDFS, OWL 2 DL (simple/expressive), OWL 2 Full
  - Import analysis with resolution status checking
  - Namespace categorisation: local, standard, external (with unimported detection)
  - Hierarchy analysis: root/leaf classes, max depth, orphans, cycle detection
  - Documentation coverage percentages for classes and properties
  - One-line "verdict" summary for quick triage
  - Three output formats: `text` (coloured), `json`, `markdown`
  - Brief mode (`--brief`) for quick overview without deep analysis
  - Skip import resolution (`--no-resolve`) for offline/fast usage
  - Exit codes: 0 (success), 1 (warnings e.g. unresolvable imports), 2 (error)
- New module: `src/rdf_construct/describe/`
  - `analyser.py` - Core ontology analysis logic
  - `profile.py` - OWL profile detection
  - `imports.py` - Import resolution and status checking
  - `hierarchy.py` - Class hierarchy analysis
  - `formatters/` - Text, JSON, Markdown output formatters
- New documentation: `docs/user_guides/DESCRIBE_GUIDE.md`
- New examples: `examples/describe/`
- New tests: `tests/test_describe.py` (67 test cases)

### Changed

- Updated documentation to include `describe` command across all relevant guides
- Expanded `QUICK_REFERENCE.md` to cover all 14 commands
- Expanded `GETTING_STARTED.md` with grouped command category tour
- Renamed `MERGE_GUIDE.md` to `MERGE_SPLIT_GUIDE.md` with expanded split documentation
- Fixed broken documentation links (`PLANTUML_IMPORT_GUIDE.md` → `PUML2RDF_GUIDE.md`)
- Updated README roadmap to reflect implemented features
- Added `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1)

## [0.3.0] - 2025-12-04

### Added

- **New `localise` command** for multi-language translation management
  - `localise extract` - Extract translatable strings (rdfs:label, rdfs:comment, skos:prefLabel, etc.) to YAML files
  - `localise merge` - Merge completed translations back into ontologies as language-tagged literals
  - `localise report` - Generate translation coverage reports across languages
  - `localise init` - Create empty translation file for a new language
  - `localise config --init` - Generate default configuration file
  - Four-level status tracking: pending → needs_review → translated → approved
  - Property-aware extraction (configurable properties to extract)
  - Missing-only mode for incremental translation updates
  - Preserve/overwrite strategies for existing translations
  - Text and Markdown output formatters
  - Exit codes: 0 (success), 1 (warnings), 2 (error)
- New module: `src/rdf_construct/localise/`
  - `config.py` - Configuration dataclasses (TranslationEntry, TranslationFile, etc.)
  - `extractor.py` - String extraction from ontologies
  - `merger.py` - Merge translations back into graphs
  - `reporter.py` - Coverage analysis
  - `formatters/` - Text and Markdown output formatters
- New documentation: `docs/user_guides/LOCALISE_GUIDE.md`
- New example: `examples/localise_config.yml`
- New tests: `tests/test_localise.py` (27 test cases)

- **New `refactor` command group** for URI renaming and deprecation
  - `refactor rename` subcommand for URI renaming:
    - Single entity renames (fixing typos): `--from ex:Buiding --to ex:Building`
    - Bulk namespace changes: `--from-namespace http://old/ --to-namespace http://new/`
    - Combined namespace + explicit entity renames
    - Data migration support using shared `merge/migrator.py` infrastructure
    - Literals intentionally NOT modified (preserves comments mentioning old URIs)
    - YAML configuration file support for complex renames
    - Dry-run preview mode
  - `refactor deprecate` subcommand for marking entities deprecated:
    - Adds `owl:deprecated true`
    - Adds `dcterms:isReplacedBy` when replacement specified
    - Prepends "DEPRECATED:" to `rdfs:comment` with custom message
    - Bulk deprecation from YAML configuration
    - Preserves all existing entity properties
    - Dry-run preview mode
  - Exit codes: 0 (success), 1 (warnings), 2 (error)
- New module: `src/rdf_construct/refactor/`
  - `config.py` - Configuration dataclasses (RenameConfig, DeprecationSpec, etc.)
  - `renamer.py` - OntologyRenamer class for URI substitution
  - `deprecator.py` - OntologyDeprecator class for deprecation workflow
  - `formatters/text.py` - Dry-run preview formatting
- New documentation: `docs/user_guides/REFACTOR_GUIDE.md`
- New examples: `examples/refactor_renames.yml`, `examples/refactor_deprecations.yml`, `examples/refactor_*.ttl`
- New tests: `tests/test_refactor.py` (25+ test cases)

- **New `split` command** for modularising monolithic ontologies
  - Namespace-based auto-detection mode (`--by-namespace`)
  - Configuration file support for explicit module definitions
  - Entity assignment by class list, property list, or namespace
  - `include_descendants` option for capturing class hierarchies
  - Automatic `owl:imports` generation from detected dependencies
  - Manifest file (`manifest.yml`) with module statistics and dependency graph
  - Instance data splitting by `rdf:type`
  - Dry-run preview mode
  - Round-trip validation: `merge(split(x)) ≈ x`
  - Exit codes: 0 (success), 1 (unmatched in common), 2 (error)
- Extended merge module: `src/rdf_construct/merge/splitter.py`
- New examples: `examples/split_monolith.ttl`, `examples/split_instances.ttl`, `examples/split_config.yml`
- New tests: `tests/test_split.py` (18 test cases)
- **New `merge` command** for combining multiple RDF ontology files
  - Intelligent conflict detection (same subject+predicate, different values)
  - Four resolution strategies: `priority`, `first`, `last`, `mark_all`
  - Conflict markers (`# === CONFLICT ===`) in output for manual review
  - Namespace remapping during merge
  - owl:imports handling (preserve, remove, merge)
  - Conflict report generation (text and markdown formats)
  - Data migration support:
    - Simple URI substitution for renames and namespace changes
    - Complex CONSTRUCT-style transformation rules
    - Property splits, type migrations, value transformations
  - YAML configuration file support for complex merges
  - Dry-run mode for previewing changes
  - Exit codes: 0 (success), 1 (unresolved conflicts), 2 (error)
- New module: `src/rdf_construct/merge/`
  - `config.py` - Configuration dataclasses (MergeConfig, MigrationRule, etc.)
  - `conflicts.py` - Conflict detection and marking
  - `merger.py` - Core OntologyMerger class
  - `migrator.py` - Data graph migration (shared infrastructure for future split/refactor commands)
  - `rules.py` - SPARQL-like transformation rule engine
  - `formatters.py` - Text and Markdown output formatters
- New documentation: `docs/user_guides/MERGE_GUIDE.md`
- New example: `examples/merge_config.yml`
- New tests: `tests/test_merge.py` (28 test cases)

## [0.2.1] - 2025-12-03

### Changed
- Added PyPI badges to README
- Updated `pyproject.toml`

## [0.2.0] - 2025-12-03

### Added

- **Stats command** - New `rdf-construct stats` command for computing ontology metrics
  - Basic counts: triples, classes, properties (object, datatype, annotation), individuals
  - Hierarchy analysis: root/leaf classes, max/average depth, branching factor, orphan detection
  - Property metrics: domain/range coverage, inverse pairs, functional/symmetric properties
  - Documentation coverage: label and comment coverage for classes and properties
  - Complexity metrics: multiple inheritance, OWL restrictions, equivalent classes
  - Connectivity analysis: most connected class, isolated classes
  - Comparison mode (`--compare`) for tracking changes between ontology versions
  - Three output formats: text (default), JSON, markdown
  - Category filtering with `--include` and `--exclude` options
- New documentation: `docs/user_guides/STATS_GUIDE.md`
- Unit tests for all stats metrics and formatters

- **New `cq-test` command** for competency question testing
  - Validate ontologies against SPARQL-based competency questions
  - YAML test file format with prefixes, inline data, and questions
  - Multiple expectation types:
    - Boolean (ASK query true/false)
    - `has_results` / `no_results` for existence checks
    - `count`, `min_count`, `max_count` for result counting
    - `results` for exact result set matching
    - `contains` for subset matching
  - Tag-based test filtering (`--tag`, `--exclude-tag`)
  - Three output formats: `text` (console), `json` (scripting), `junit` (CI)
  - Verbose mode with query text and timing
  - Fail-fast mode for quick debugging
  - Skip tests with reasons
  - Exit codes: 0 (all passed), 1 (failures), 2 (errors)
- New module: `src/rdf_construct/cq/`
  - `expectations.py` - Polymorphic expectation classes
  - `loader.py` - YAML test file parsing
  - `runner.py` - Test execution engine
  - `cli.py` - Click command integration
  - `formatters/` - Text, JSON, JUnit output formatters
- New documentation: `docs/user_guides/CQ_TEST_GUIDE.md`
- New example: `examples/cq_tests_animal.yml`
- New tests: `tests/test_cq.py`

- **New `puml2rdf` command** for PlantUML to RDF conversion
  - Convert PlantUML class diagrams to RDF/OWL ontologies
  - Diagram-first ontology design workflow
  - Parse classes, attributes, inheritance, and associations
  - Support for dotted namespace prefixes (e.g., `building.Building` → `building:Building`)
  - Handle `"Display Name" as alias` syntax for human-readable labels
  - Direction hints in relationships (`-u-|>`, `-d-|>`, etc.)
  - PlantUML styling attributes ignored gracefully (`#back:XXX;line:XXX`)
  - Multi-line notes attached to classes become `rdfs:comment`
  - Automatic namespace generation from package prefixes
  - Custom datatype mappings (PlantUML types to XSD)
  - Merge with existing ontologies (preserves manual annotations)
  - Validation mode for CI integration (`--validate --strict`)
  - YAML configuration file support for complex setups
  - Output formats: Turtle, RDF/XML, JSON-LD, N-Triples
- New module: `src/rdf_construct/puml2rdf/`
  - `model.py` - Intermediate representation dataclasses
  - `parser.py` - Regex-based PlantUML parser
  - `converter.py` - Model to RDF/OWL conversion
  - `config.py` - YAML configuration handling
  - `merger.py` - Ontology merge logic
  - `validators.py` - Model and RDF validation
- New documentation: `docs/user_guides/PUML2RDF_GUIDE.md`
- New example: `examples/puml2rdf_config.yml`
- New tests: `tests/test_puml2rdf.py`

- **New SHACL Shape Generator** (`shacl-gen` command)
  - Generate SHACL NodeShapes from OWL ontology definitions
  - Convert domain/range to sh:property with sh:class/sh:datatype
  - Convert cardinality restrictions to sh:minCount/sh:maxCount
  - Convert owl:FunctionalProperty to sh:maxCount 1
  - Convert owl:someValuesFrom/allValuesFrom to type constraints
  - Convert owl:oneOf enumerations to sh:in
  - Support for qualified cardinality restrictions
  - Three strictness levels: minimal, standard, strict
  - Constraint inheritance from superclasses
  - Closed shape generation with configurable ignored properties
  - YAML configuration file support
  - Include rdfs:label as sh:name and rdfs:comment as sh:description
  - Output formats: Turtle, JSON-LD
- New module: `src/rdf_construct/shacl/`
- New documentation: `docs/user_guides/SHACL_GUIDE.md`
- New tests: `tests/test_shacl_gen.py`

- **New `docs` command** for generating documentation from RDF ontologies
  - Three output formats: `html` (navigable website), `markdown` (GitHub/GitLab compatible), `json` (structured data)
  - Comprehensive entity extraction: classes, object/datatype/annotation properties, instances
  - Class hierarchy visualisation with tree structure
  - Individual pages for each entity with cross-references
  - Client-side search functionality for HTML output (search.json index)
  - Custom Jinja2 template support for branding/customisation
  - Single-page documentation mode (`--single-page`)
  - Entity type filtering (`--include`, `--exclude`): classes, properties, instances
  - Configuration file support for complex setups
  - Namespace filtering: only displays namespaces actually used in triples
  - Inherited property detection for class documentation
  - Circular hierarchy protection (handles malformed ontologies gracefully)
  - Responsive CSS styling with property-type colour coding
  - YAML frontmatter for Markdown output (Jekyll/Hugo compatible)
- New dependency: `jinja2 >= 3.1.0`
- New module: `src/rdf_construct/docs/`
- New documentation: `docs/user_guides/DOCS_GUIDE.md`
- Example configuration: `examples/docs_config.yml`
- New tests: `tests/test_docs.py`

- **New `diff` command** for semantic ontology comparison
  - Compares two RDF graphs and reports meaningful changes
  - Ignores cosmetic differences (statement order, prefix bindings, whitespace)
  - Three output formats: `text` (terminal), `markdown` (release notes), `json` (scripting)
  - Change type filtering (`--show`, `--hide`): added, removed, modified
  - Entity type filtering (`--entities`): classes, properties, instances
  - Predicate exclusion (`--ignore-predicates`): skip timestamps, version info, etc.
  - Exit codes for CI: 0 (identical), 1 (differences found), 2 (error)
  - Entity classification: classes, object/datatype/annotation properties, individuals
  - Superclass detection for added classes
  - Blank node warning (detected but not deeply analysed)
- New module: `src/rdf_construct/diff/`
- New documentation: `docs/user_guides/DIFF_GUIDE.md`
- Test fixtures: `tests/fixtures/diff/v1_0.ttl`, `v1_1.ttl`
- New tests: `tests/test_diff.py`

- **New `lint` command** for ontology quality checking with 11 rules across three categories:
  - Structural (error): `orphan-class`, `dangling-reference`, `circular-subclass`, `property-no-type`, `empty-ontology`
  - Documentation (warning): `missing-label`, `missing-comment`
  - Best Practice (info): `redundant-subclass`, `property-no-domain`, `property-no-range`, `inconsistent-naming`
- Strictness levels (`--level strict|standard|relaxed`) for flexible enforcement
- Configuration file support (`.rdf-lint.yml`) with auto-discovery
- JSON output format (`--format json`) for CI/tooling integration
- Exit codes for CI integration: 0 (clean), 1 (warnings), 2 (errors)
- Rule enable/disable via CLI (`--enable`, `--disable`) and config file
- `--list-rules` option to display available rules
- `--init` option to generate default `.rdf-lint.yml` config
- Line number detection in lint output (best-effort source file search)
- Namespace-aware entity formatting in output (e.g., `ies:Building` not just `Building`)
- Inheritance-aware checking for `property-no-domain` and `property-no-range` (respects `rdfs:subPropertyOf`)
- New module: `src/rdf_construct/lint/`
- New documentation: `docs/user_guides/LINT_GUIDE.md`
- New tests: `tests/test_lint.py`

- Starter templates for new projects:
  - `uml_contexts_starter.yml` - Basic UML context configuration
  - `uml_styles_starter.yml` - Basic styling configuration
  - `ordering_starter.yml` - Basic ordering profile
- New documentation: `docs/user_guides/PROJECT_SETUP.md`
- New documentation: `docs/user_guides/QUICK_REFERENCE.md`

### Changed

- Updated `docs/index.md` to include all new command guides
- Updated `CODE_INDEX.md` with all new modules
- Updated `README.md` with all new features and commands
- Updated `docs/user_guides/CLI_REFERENCE.md` with full command documentation

## [0.1.0] - 2025-11-30

Initial public release.

### Added

#### Core Features
- `order` command for semantic RDF/Turtle ordering
  - Topological sorting respecting `rdfs:subClassOf` and `rdfs:subPropertyOf`
  - Alphabetical sorting for deterministic output
  - Anchor-based ordering for key concepts
  - Configurable predicate ordering within subjects
  - Custom serialiser preserving subject order (rdflib always sorts alphabetically)

- `uml` command for PlantUML class diagram generation
  - Root-based class selection with descendant traversal
  - Focus-based class selection for specific views
  - Explicit mode for precise control over diagram contents
  - Configurable depth limiting for large ontologies
  - Instance (individual) rendering with class relationships

#### Property Handling
- Multiple property selection modes: `domain_based`, `connected`, `explicit`, `all`, `none`
- Object property and datatype property distinction
- Property filtering via include/exclude lists

#### Styling System
- Namespace-based class colouring
- Type-based styling for meta-classes
- Instance styling with class border inheritance
- Arrow styling for different relationship types
- IES colour palette support with semantic colouring
- Stereotype mapping and display

#### Layout Options
- Direction control (top-to-bottom, left-to-right)
- Orthogonal line routing
- Inheritance arrow merging
- Class grouping by namespace
- Configurable spacing

#### ODM Compliance
- ODM (Ontology Definition Metamodel) rendering mode
- RDF vocabulary styling (rdf:type as dependency arrows)
- Standards-compliant diagram generation

#### CLI
- Click-based command-line interface
- Multiple source file support
- Profile/context selection
- Output directory configuration
- Context and profile listing commands

### Documentation
- Getting Started guide
- UML Guide with complete feature reference
- CLI Reference with all commands and options
- Architecture documentation for contributors
- IES Colour Palette guides
- Project Setup guide for end users
- Quick Reference card

### Examples
- Animal ontology (simple hierarchy)
- Organisation ontology (multiple roots)
- IES Building ontology (complex real-world example)
- Sample configuration files for all features

---

## Version History Summary

| Version | Date       | Highlights                                                                                          |
|---------|------------|-----------------------------------------------------------------------------------------------------|
| [0.6.0] | 2026-09-04 | SKOS, named individuals and deprecation in `docs`; link, contrast and determinism fixes             |
| [0.5.0] | 2026-08-22 | SHACL shapes in `docs`; `order` no longer drops unclaimed subjects                                  |
| [0.4.7] | 2026-05-07 | Fix cosmetic glitch in `lint --init` generated config                                               |
| [0.4.6] | 2026-03-27 | Fix invalid Turtle prefix declarations in `order` output                                            |
| [0.4.5] | 2026-03-17 | Documentation for `cast` command                                                                    |
| [0.4.4] | 2026-03-17 | Add `cast` command for pipe-friendly RDF format conversion                                          |
| [0.4.3] | 2026-03-17 | Fix inline blank node serialisation in `order` output                                               |
| [0.4.2] | 2026-02-05 | Fix extraneous prefix declarations in order output                                                  |
| [0.4.1] | 2026-01-06 | Fix lint command import collision                                                                   |
| [0.4.0] | 2026-01-03 | Add describe command, documentation improvements                                                    |
| [0.3.0] | 2025-12-04 | Add merge/split, refactor, and localise                                                             |
| [0.2.0] | 2025-12-03 | Stats, CQ testing, SHACL gen, docs gen, diff, lint, puml2rdf                                        |
| [0.1.0] | 2025-11-30 | Initial release: ordering, UML generation, styling                                                  |

[Unreleased]: https://github.com/aigora-de/rdf-construct/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/aigora-de/rdf-construct/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/aigora-de/rdf-construct/compare/v0.4.7...v0.5.0
[0.4.7]: https://github.com/aigora-de/rdf-construct/compare/v0.4.6...v0.4.7
[0.4.6]: https://github.com/aigora-de/rdf-construct/compare/v0.4.5...v0.4.6
[0.4.5]: https://github.com/aigora-de/rdf-construct/compare/v0.4.4...v0.4.5
[0.4.4]: https://github.com/aigora-de/rdf-construct/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/aigora-de/rdf-construct/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/aigora-de/rdf-construct/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/aigora-de/rdf-construct/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/aigora-de/rdf-construct/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/aigora-de/rdf-construct/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/aigora-de/rdf-construct/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/aigora-de/rdf-construct/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/aigora-de/rdf-construct/releases/tag/v0.1.0
