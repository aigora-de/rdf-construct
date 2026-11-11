# Cast Guide: RDF Format Conversion

The `rdf-construct cast` command converts an RDF file from one serialisation format to another. It is designed to be **Unix pipe-friendly**: when you request a single output format, the converted RDF goes to stdout so it can be piped directly to other tools.

## Quick Start

```bash
# Convert Turtle to RDF/XML
rdf-construct cast ontology.ttl --format xml

# Pipe directly to grep — output goes to stdout, diagnostics to stderr
rdf-construct cast ontology.ttl --format n3 | grep rdf:type

# Convert to several formats at once (writes files)
rdf-construct cast ontology.ttl --format xml --format nt --format json-ld

# Default: convert to all standard formats, excluding the source format
rdf-construct cast ontology.rdf
```

## Why cast?

RDF data is routinely exchanged in multiple serialisation formats. Tools often accept only one or two, and translating by hand (or writing throwaway Python scripts) is tedious. `cast` handles the job with a single command, and because it writes clean RDF to stdout when given a single `--format`, it slots naturally into shell pipelines alongside `grep`, `jq`, `rapper`, and any other Unix tool.

## Command Reference

```
rdf-construct cast SOURCE [OPTIONS]
```

### Arguments

- `SOURCE` — Input RDF file. Any format rdflib can parse is accepted.

### Options

| Option | Description |
|--------|-------------|
| `-f, --format FORMAT` | Output format (repeatable). Omit for all standard formats except source. |
| `-o, --output-dir PATH` | Directory for output files (default: same directory as source). |
| `--allow-flatten` | Allow a source with named graphs to be written to a single-graph format by merging every graph into one. Lossy: graph names are discarded. TriG and N-Quads output always keeps the graphs. |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Every requested format was written |
| `1` | Finished with something to report — a format was skipped (the source's own) or failed, and at least one was written |
| `2` | Not done — refused (every requested format the source's own, a source with named graphs without `--allow-flatten`, or an N3 source with formulae or variables), a parse error, or every format failed |

## Supported Formats

The table below lists every format alias `cast` accepts. Aliases are case-insensitive.

| Canonical name | Accepted aliases | Output extension | Quad format? |
|----------------|-----------------|------------------|--------------|
| `turtle` | `ttl`, `turtle` | `.ttl` | No |
| `xml` | `xml`, `rdf`, `rdfxml` | `.rdf` | No |
| `json-ld` | `json-ld`, `jsonld` | `.jsonld` | No |
| `nt` | `nt`, `ntriples` | `.nt` | No |
| `n3` | `n3` | `.n3` | No |
| `trig` | `trig` | `.trig` | Yes |
| `nquads` | `nq`, `nquads` | `.nq` | Yes |

Two formats can hold more than the table says, and `cast` treats them accordingly:

- **JSON-LD can hold named graphs.** A JSON-LD *source* that holds one is treated as a quad
  source: see [Quad Formats](#quad-formats-trig-and-n-quads). As a *target*, JSON-LD is written
  as a single graph ([#543](https://github.com/aigora-de/rdf-construct/issues/543)).
- **N3 can hold more than RDF.** A source with formulae (`{ … }`) or variables (`@forAll :x`,
  `?x`) cannot be cast: see [N3 Formulae and Variables](#n3-formulae-and-variables).

### Default output set

When `--format` is omitted, `cast` converts to **`turtle`, `xml`, and `json-ld`**, excluding whichever of those three the source file already is. N3 and quad formats are not included in the defaults — they must be requested explicitly.

```bash
# Source is Turtle → writes .rdf and .jsonld
rdf-construct cast ontology.ttl

# Source is RDF/XML → writes .ttl and .jsonld
rdf-construct cast ontology.rdf

# Source is JSON-LD → writes .ttl and .rdf
rdf-construct cast ontology.jsonld
```

## Pipe Mode

When **exactly one `--format`** is given and no `--output-dir` is set, `cast` writes the converted RDF to **stdout** and sends all diagnostic messages (file loading, warnings, success ticks) to **stderr**. This keeps stdout clean for piping.

```bash
# Count owl:Class declarations
rdf-construct cast ontology.rdf --format ttl | grep -c 'owl:Class'

# Feed to rapper for further conversion
rdf-construct cast ontology.ttl --format nt | rapper -i ntriples -o dot /dev/stdin

# Redirect stdout to a file without using --output-dir
rdf-construct cast ontology.ttl --format xml > converted.rdf

# Pipe to jq for JSON-LD inspection
rdf-construct cast ontology.ttl --format json-ld | jq '.["@context"]'
```

If you pass `--output-dir` together with a single `--format`, the file is written to disk rather than stdout — useful in scripts that always set the output location explicitly.

## File Output Mode

When **multiple `--format` flags** are given, or when `--format` is omitted (default all), `cast` writes one output file per format. Output filenames are derived from the source filename with the extension substituted.

```bash
# ontology.ttl → ontology.rdf, ontology.jsonld
rdf-construct cast ontology.ttl

# ontology.ttl → converted/ontology.rdf, converted/ontology.jsonld
rdf-construct cast ontology.ttl --output-dir converted/

# Explicit multi-format
rdf-construct cast ontology.ttl --format xml --format nt --format json-ld
```

At the end of a successful multi-format run, `cast` prints a summary to stderr:

```
Casting ontology.ttl...
  Formats: xml, json-ld
  Output:  ./

  ✓ ontology.rdf
  ✓ ontology.jsonld

Cast 2 file(s) to ./
```

## Prefix Bindings

rdflib preserves prefix bindings on the graph object when parsing Turtle and N3 files. This means:

- **Turtle/N3 → any format**: prefix bindings are preserved in the output.
- **XML/JSON-LD/N-Triples → Turtle/N3**: output will use rdflib's default well-known prefix bindings rather than whatever prefixes appeared in the source file. This is a known rdflib limitation.

If prefix fidelity matters when converting from XML or JSON-LD, run `order` on the output to apply a canonical prefix set.

## Literal Forms

`cast` writes every typed literal in the form the source wrote it: `"007"^^xsd:integer` stays
`"007"`, and `"1"^^xsd:boolean` beside `"true"^^xsd:boolean` stays two triples
([#377](https://github.com/aigora-de/rdf-construct/issues/377)). Turtle, TriG and N3 output write a
literal bare (`true`, `7`) only when that bare form reads back as the same literal, and as
`"lexical"^^datatype` otherwise. Three exceptions, all rdflib's:

- **A bare number in a Turtle or N3 source** (`007`, `+5`) is canonicalised by the parser, so it is
  written as `7` and `5`.
- **A JSON-LD source** gives its numbers and booleans as JSON values, which have only one form.
- **JSON-LD output** writes booleans and numbers from their value, so `"007"^^xsd:integer` becomes
  `7`, and `"1"^^xsd:boolean` beside `"true"` is written as `true` twice, which reads back as one
  triple ([#462](https://github.com/aigora-de/rdf-construct/issues/462)). Use N-Triples, RDF/XML,
  Turtle, TriG or N3 where the form matters.

## Quad Formats (TriG and N-Quads)

TriG and N-Quads are **multi-graph** formats: a single file can hold a default graph and any number of named graphs. Turtle, RDF/XML, N-Triples and N3 are **single-graph** formats. `cast` reads every source into a dataset, so what a quad format is given is what it writes.

### Writing TriG and N-Quads

**From a single-graph source**, the triples go in the default graph:

```bash
rdf-construct cast ontology.ttl --format trig
rdf-construct cast ontology.ttl --format nq
```

- TriG writes the default graph as one unnamed `{ … }` block. That is valid TriG, and means the same as triples written outside any block, but a tool that reads only Turtle will not accept it.
- N-Quads writes each triple with no graph term, so the lines are the ones `--format nt` writes.

**From a quad source**, every graph is kept, under its own name:

```bash
# TriG to N-Quads, and back
rdf-construct cast dataset.trig --format nq
rdf-construct cast dataset.nq --format trig
```

The default graph, each named graph, a triple stated in two graphs, and a blank node shared between graphs all come through. Two things to know:

- **A graph named by a blank node** keeps a blank-node name, but not the same label: blank-node labels are local to a file.
- **TriG labels every blank node** (`_:n…`), where Turtle writes a single-use one inline as `[ … ]`. So TriG output from a source with blank nodes differs from run to run, and is the same graph each time.

### Writing a single-graph format from a source with named graphs

A single-graph format has nowhere to put a graph's name. By default `cast` refuses, before it reads the source:

```
✗ Source 'dataset.trig' uses a multi-graph format (trig) but the requested target format(s) are single-graph: turtle. Use --allow-flatten to merge all named graphs into the default graph, or choose a quad output format (nquads).
```

`--allow-flatten` permits it. Every graph is merged into one, a triple stated in several graphs is written once, and a warning on stderr names the formats that were merged:

```bash
rdf-construct cast dataset.trig --format ttl --allow-flatten
#   ⚠ Flattened dataset.trig for turtle: all named graphs merged into one graph.
```

> **Note:** Flattening is lossy: graph names are discarded. Use `--allow-flatten` only when you do not need to know which graph a triple came from.

**The flag never merges for TriG or N-Quads output.** In a request for both kinds, the quad file keeps the graphs and the single-graph file gets the merge:

```bash
rdf-construct cast dataset.trig --format nq --format ttl --allow-flatten --output-dir out/
# out/dataset.nq keeps every graph; out/dataset.ttl holds them merged
```

To get one merged quad file, flatten to Turtle first and cast that.

**A TriG or N-Quads source is refused on its format**, whatever it holds: a `.trig` file with only a default graph still needs the flag for a single-graph target.

### JSON-LD sources with named graphs

JSON-LD can hold named graphs: a node with both `@id` and `@graph` is one, and that includes a document whose top level has an `@id` beside its `@graph`. Most JSON-LD files hold none, so `cast` decides from the content, after reading it. A JSON-LD source that holds a named graph is treated as a quad source:

```bash
rdf-construct cast dataset.jsonld --format ttl
# ✗ Source 'dataset.jsonld' holds named graphs but the requested target format(s) are single-graph: turtle. Use --allow-flatten to merge all named graphs into the default graph, or choose a quad output format (trig, nquads).

rdf-construct cast dataset.jsonld --format trig                   # keeps the graphs
rdf-construct cast dataset.jsonld --format ttl --allow-flatten    # merges them
```

The default invocation (`rdf-construct cast dataset.jsonld`) asks for Turtle and RDF/XML, so it is refused too. A JSON-LD source with no named graph is cast as any single-graph source is.

## N3 Formulae and Variables

N3 is a superset of Turtle, and some of what it adds is not RDF. `cast` refuses a source that holds:

- **a formula**, a quoted graph written `{ … }`, as in a rule `{ :a :b :c } => { :d :e :f } .`;
- **a variable**, declared with `@forAll` or written `?x`.

No other format can hold either, so there is nothing to write, and N3 to N3 is [nothing to cast](#source-format-same-as-target). The refusal exits with code `2`, writes nothing, and counts the statements involved:

```bash
rdf-construct cast rules.n3 --format ttl
# ✗ Source 'rules.n3' holds N3 constructs that no other format can carry: 1 statement with a formula ({ … }). Only N3 can hold them, so there is nothing cast can write.
```

N3 that is plain RDF underneath casts as usual: `@forSome` and the path shorthands `:a!:b` and `:a^:b` become ordinary blank nodes.

## Source Format Same as Target

The source's format comes from its file extension; `cast` never reads the content to decide it. A requested format that is the source's own is never written, so `cast` never overwrites the source with itself.

**When every requested format is the source's own**, there is nothing to cast. `cast` refuses with exit code `2` before reading the source, in pipe mode as well as with `--output-dir`. Nothing is written, no directory is created, and stdout stays empty:

```bash
rdf-construct cast ontology.ttl --format ttl
# Error: nothing to cast: ontology.ttl is already turtle (from its extension), and turtle was the only format requested.
# Accepted: xml, json-ld, nt, n3, trig, nquads
```

The format is named canonically (`turtle` for `ttl`). For an extension `cast` does not recognise, the source is taken to be Turtle, and the message says so: `ontology.ont is taken to be turtle (cast does not recognise '.ont')`. From a TriG or N-Quads source without `--allow-flatten`, the message adds that every format but the other quad format is single-graph and needs the flag, which merges the named graphs.

To re-serialise Turtle as Turtle, use `order`: `cast` does not reorder.

**When some requested formats are the source's own and others are not**, `cast` writes the others, warns about the skip, and exits with code `1`:

```bash
rdf-construct cast ontology.ttl --format ttl --format nt --output-dir out/
#   ⚠ Skipping 'turtle': source and target format are the same.
#
#   ✓ ontology.nt
#
# Cast 1 file(s) to out/; skipped turtle (the source's own format).
```

The default invocation (`rdf-construct cast ontology.ttl`) never requests the source's own format, so it is unaffected.

## Partial Failure

In multi-format mode, if one format fails to serialise (e.g., due to a rdflib limitation with a particular combination) but others succeed, `cast` exits with code `1` and reports which formats succeeded and which failed:

```
✗ Partial failure: json-ld could not be converted.
  ✓ ontology.rdf
```

A format skipped because it is the source's own is reported the same way, at `1`, when at least one other format was written (see [Source Format Same as Target](#source-format-same-as-target)).

A complete failure (e.g., the source file cannot be parsed) always exits with code `2`. So does a run that skips one format and fails the rest, since nothing asked for was written.

## Programmatic Use

`cast`'s core logic lives in `rdf_construct.cast.converter` and can be used directly from Python without going through the CLI:

```python
from pathlib import Path
from rdf_construct.cast.converter import CastConverter

converter = CastConverter()

# Convert to a single format and capture as a string
result = converter.convert(
    source=Path("ontology.ttl"),
    formats=["xml"],
    output_dir=None,
    pipe_mode=True,       # Return serialised content instead of writing a file
)
if result.success:
    print(result.stdout_content)   # The RDF/XML string

# Convert to multiple formats and write files
result = converter.convert(
    source=Path("ontology.ttl"),
    formats=["xml", "json-ld"],
    output_dir=Path("converted/"),
    pipe_mode=False,
)
if result.success:
    for path in result.written_files:
        print(f"Wrote {path}")
for warning in result.warnings:
    print(f"Warning: {warning}")
```

Called from Python, `CastConverter` (like every `rdf_construct` function) uses rdflib's defaults,
which normalise typed literals as they are read: `"007"^^xsd:integer` becomes `"7"`. To read and
write them as the CLI does (see [Literal Forms](#literal-forms)), wrap the work in
`preserve_literal_forms()`:

```python
from pathlib import Path
from rdf_construct.cast.converter import CastConverter
from rdf_construct.core import preserve_literal_forms

with preserve_literal_forms():
    result = CastConverter().convert(
        source=Path("ontology.ttl"), formats=["nt"], output_dir=None, pipe_mode=True
    )
```

It sets rdflib's settings for the whole process and restores them on exit, so it is not
thread-safe.

### `ConversionResult` fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | `True` if every format attempted succeeded and at least one was; `False` on a partial failure, a fatal error, or when every requested format was the source's own |
| `partial_failure` | `bool` | `True` when some formats succeeded and some failed |
| `error` | `str \| None` | Human-readable message on complete failure |
| `written_files` | `list[Path]` | Paths of files that were written |
| `stdout_content` | `str \| None` | Serialised RDF in pipe mode; `None` otherwise |
| `warnings` | `list[str]` | Non-fatal messages (skips, flatten notices, etc.) |
| `failed_formats` | `list[str]` | Canonical format names that failed |
| `skipped_formats` | `list[str]` | Canonical format names skipped as the source's own, each once |

### Format utilities

The `rdf_construct.core.formats` module exposes the format registry used by `cast` and is useful for build scripts or other tooling:

```python
from rdf_construct.core.formats import (
    normalise_format,     # "ttl" → "turtle"
    infer_format,         # Path("ont.rdf") → "xml"
    extension_for_format, # "json-ld" → ".jsonld"
    is_quad_format,       # "trig" → True
    default_cast_formats, # default_cast_formats("turtle") → ["xml", "json-ld"]
)
```

## Examples

### Batch conversion in a shell loop

```bash
# Convert every Turtle file in a directory to RDF/XML
for f in ontologies/*.ttl; do
    rdf-construct cast "$f" --format xml --output-dir converted/
done
```

### Pipeline: validate then cast

```bash
# Only convert if lint passes
rdf-construct lint ontology.ttl && \
    rdf-construct cast ontology.ttl --output-dir dist/
```

### Inspect JSON-LD context in a pipeline

```bash
rdf-construct cast ontology.ttl --format json-ld | \
    python3 -c "import json,sys; d=json.load(sys.stdin); print(list(d[0]['@context'].keys()))"
```

### Convert and order in sequence

`cast` intentionally does not reorder triples — that is `order`'s job. Chain them when you need both:

```bash
# Convert XML to Turtle, then apply semantic ordering
rdf-construct cast schema.rdf --format ttl
rdf-construct order schema.ttl order.yml -o ordered/
```

## Relationship to Other Commands

| Command | Purpose |
|---------|---------|
| `cast` | Change serialisation format; no semantic processing |
| `order` | Reorder Turtle with semantic structure; no format change |
| `lint` | Check ontology quality; read-only |
| `diff` | Compare two files semantically; read-only |
| `merge` | Combine multiple ontologies; semantic-aware |

## See Also

- [CLI Reference](CLI_REFERENCE.md) — Full command documentation
- [Getting Started](GETTING_STARTED.md) — Installation and setup
- [Diff Guide](DIFF_GUIDE.md) — Semantic comparison of ontology versions
- [Merge and Split Guide](MERGE_SPLIT_GUIDE.md) — Combining and modularising ontologies
