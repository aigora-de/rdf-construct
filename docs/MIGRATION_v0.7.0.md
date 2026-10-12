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

Not landed yet. One convention for what each exit code means, applied to every command:
[#286](https://github.com/aigora-de/rdf-construct/issues/286) (PR group P2 on #312).

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

## `profiles`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `uml`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `contexts`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `lint`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `diff`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `docs`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `shacl-gen`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `puml2rdf`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `cq-test`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `stats`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `describe`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `merge`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `split`

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `refactor`

Covers `refactor rename` and `refactor deprecate`; each row names its subcommand.

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|

## `localise`

Covers `localise extract`, `merge`, `report`, `init` and `config`; each row names its subcommand.

Nothing has landed yet.

| Issue | What changed | What to do |
|---|---|---|
