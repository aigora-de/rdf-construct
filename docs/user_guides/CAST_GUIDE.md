# Cast Guide: RDF Format Conversion

The `rdf-construct cast` command converts an RDF file from one serialisation format to another. It is designed to be **Unix pipe-friendly**: when you request a single output format, the converted RDF goes to stdout so it can be piped directly to other tools.

## Quick Start

```bash
# Convert Turtle to RDF/XML
rdf-construct cast ontology.ttl --format xml

# Pipe directly to grep — output goes to stdout, diagnostics to stderr
rdf-construct cast ontology.ttl --format n3 | grep rdf:type

# Convert to several formats at once (writes files)
rdf-construct cast ontology.ttl --format ttl --format xml --format json-ld

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
| `--allow-flatten` | Merge all named graphs into the default graph when converting from a quad format. |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All conversions succeeded |
| `1` | Partial failure — some formats failed, at least one succeeded |
| `2` | Complete failure — parse error, or all formats failed |

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

## Quad Formats (TriG and N-Quads)

TriG and N-Quads are **multi-graph** formats: a single file can contain multiple named graphs. Turtle, RDF/XML, JSON-LD, and N-Triples are **single-graph** formats.

By default, `cast` refuses to convert a quad-format source to a single-graph target and prints a clear error:

```
✗ Source 'dataset.trig' uses a multi-graph format (trig) but the requested
  target format(s) are single-graph: turtle.
  Use --allow-flatten to merge all named graphs into the default graph,
  or choose a quad output format (trig, nquads).
```

Use `--allow-flatten` to override this. All triples from all named graphs will be merged into the default graph, and a warning will appear in stderr:

```bash
# Flatten a TriG dataset to Turtle
rdf-construct cast dataset.trig --format ttl --allow-flatten

# Convert between quad formats (no flattening needed)
rdf-construct cast dataset.trig --format nq
```

> **Note:** Flattening is a lossy operation — named graph identity is discarded. Only use `--allow-flatten` when you are certain you do not need to preserve graph provenance.

## Source Format Same as Target

If a requested target format is the same as the inferred source format, `cast` emits a warning and skips that format without failing:

```bash
# ontology.ttl with --format ttl: warns and skips, exits 0
rdf-construct cast ontology.ttl --format ttl
# ⚠ Skipping 'turtle': source and target format are the same.
```

This means the default invocation (`rdf-construct cast ontology.ttl`) is always safe — it will never overwrite the source file with itself.

## Partial Failure

In multi-format mode, if one format fails to serialise (e.g., due to a rdflib limitation with a particular combination) but others succeed, `cast` exits with code `1` and reports which formats succeeded and which failed:

```
✗ Partial failure: json-ld could not be converted.
  ✓ ontology.rdf
```

A complete failure (e.g., the source file cannot be parsed) always exits with code `2`.

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

### `ConversionResult` fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | `True` if at least one format succeeded |
| `partial_failure` | `bool` | `True` when some formats succeeded and some failed |
| `error` | `str \| None` | Human-readable message on complete failure |
| `written_files` | `list[Path]` | Paths of files that were written |
| `stdout_content` | `str \| None` | Serialised RDF in pipe mode; `None` otherwise |
| `warnings` | `list[str]` | Non-fatal messages (skips, flatten notices, etc.) |
| `failed_formats` | `list[str]` | Canonical format names that failed |

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
