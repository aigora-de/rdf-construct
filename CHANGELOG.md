# Changelog

All notable changes to rdf-construct will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/aigora-de/rdf-construct/compare/v0.5.0...HEAD
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
