"""Core conversion logic for the ``cast`` command.

This module is intentionally decoupled from Click so that it can be used
programmatically as well as through the CLI.

Typical usage::

    from rdf_construct.cast.converter import CastConverter

    converter = CastConverter()
    result = converter.convert(
        source=Path("ontology.ttl"),
        formats=["xml", "json-ld"],
        output_dir=Path("converted"),
        pipe_mode=False,
    )
    if result.success:
        for f in result.written_files:
            print(f"Wrote {f}")
    else:
        print(f"Error: {result.error}")
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from rdflib import Dataset, Graph
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID, QuotedGraph
from rdflib.term import Variable

from rdf_construct.core.formats import (
    FORMAT_REGISTRY,
    extension_for_format,
    infer_format,
    is_quad_format,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ConversionResult:
    """The outcome of a :meth:`CastConverter.convert` call.

    Attributes:
        success: ``True`` if every format that was attempted converted, and at
            least one was. ``False`` on a fatal error, on a partial failure, and
            when every requested format was the source's own, so that nothing
            was attempted (#330). In pipe mode only the first format that is not
            skipped is attempted, so :attr:`skipped_formats` names only the skips
            before it.
        partial_failure: ``True`` when some formats succeeded and some failed.
            Only relevant in multi-format mode.
        error: Set to a human-readable message on complete failure (parse
            error, all formats failed, quad-guard rejection, every format the
            source's own, etc.).
        written_files: Paths of output files that were actually written.
        stdout_content: Serialised RDF string when in pipe mode; ``None``
            otherwise.
        warnings: Non-fatal messages (skipped source==target format, etc.).
        failed_formats: Canonical format names that failed to serialise.
        skipped_formats: Canonical format names skipped because they are the
            source's own format, each named once.
    """

    success: bool = False
    partial_failure: bool = False
    error: str | None = None
    written_files: list[Path] = field(default_factory=list)
    stdout_content: str | None = None
    warnings: list[str] = field(default_factory=list)
    failed_formats: list[str] = field(default_factory=list)
    skipped_formats: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Same-format requests (#330)
# ---------------------------------------------------------------------------


def nothing_to_cast(source_format: str, formats: Sequence[str]) -> bool:
    """Whether every requested format is the source's own, so nothing can be cast.

    Decided from the request alone, before the source is read: no content can make a
    format that equals the source's worth writing.

    Args:
        source_format: The canonical format of the source, as ``infer_format`` gives it.
        formats: The canonical formats requested.

    Returns:
        ``True`` when *formats* is non-empty and every entry is *source_format*.
    """
    return bool(formats) and all(fmt == source_format for fmt in formats)


def formats_other_than(source_format: str) -> list[str]:
    """Return every canonical format except *source_format*, in registry order.

    Args:
        source_format: The canonical format to leave out.

    Returns:
        The canonical format names ``cast`` could write instead.
    """
    return [fi.canonical for fi in FORMAT_REGISTRY if fi.canonical != source_format]


def nothing_to_cast_message(source: Path, source_format: str, *, allow_flatten: bool) -> str:
    """Explain why a request naming only the source's own format casts nothing.

    The source's format comes from its extension and is never sniffed, so the message
    says so, and says when the extension is unknown and the format a guess. From a quad
    source without *allow_flatten*, it also names the formats that need the flag.

    Args:
        source: The source file.
        source_format: Its canonical format, as ``infer_format`` gives it.
        allow_flatten: Whether ``--allow-flatten`` was given.

    Returns:
        The message, without any ``Error:`` prefix.
    """
    suffix = source.suffix.lower()
    known = any(suffix in fi.extensions for fi in FORMAT_REGISTRY)
    if known:
        what = f"{source.name} is already {source_format} (from its extension)"
    else:
        reason = (
            f"cast does not recognise '{source.suffix}'"
            if source.suffix
            else f"{source.name} has no extension"
        )
        what = f"{source.name} is taken to be {source_format} ({reason})"
    message = f"nothing to cast: {what}, and {source_format} was the only format requested."
    if is_quad_format(source_format) and not allow_flatten:
        other_quads = [fmt for fmt in formats_other_than(source_format) if is_quad_format(fmt)]
        message += (
            f" Every format but {', '.join(other_quads)} is single-graph, and needs "
            f"--allow-flatten (which merges the named graphs) from "
            f"{'an' if source_format[0] in 'aeinosx' else 'a'} {source_format} source."
        )
    return message


# ---------------------------------------------------------------------------
# Named graphs, and what no target can hold (#540, #542)
# ---------------------------------------------------------------------------


def named_graphs_message(
    source: Path, source_format: str, single_graph_targets: Sequence[str]
) -> str:
    """Explain why a source with named graphs is not written to a single-graph format.

    A TriG or N-Quads source is refused on its format, before it is read. A JSON-LD
    source is refused on its content, once the parse shows it holds named graphs. The
    advice names only the quad formats other than the source's own, which ``cast``
    would refuse as nothing to cast (#330).

    Args:
        source: The source file.
        source_format: Its canonical format, as ``infer_format`` gives it.
        single_graph_targets: The requested formats that cannot hold named graphs.

    Returns:
        The message, without any ``Error:`` prefix.
    """
    what = (
        f"uses a multi-graph format ({source_format})"
        if is_quad_format(source_format)
        else "holds named graphs"
    )
    other_quads = [fmt for fmt in formats_other_than(source_format) if is_quad_format(fmt)]
    return (
        f"Source '{source.name}' {what} "
        f"but the requested target format(s) are single-graph: "
        f"{', '.join(single_graph_targets)}. "
        f"Use --allow-flatten to merge all named graphs into the default graph, "
        f"or choose a quad output format ({', '.join(other_quads)})."
    )


def has_named_graphs(dataset: Dataset) -> bool:
    """Whether *dataset* holds a statement outside its default graph.

    Args:
        dataset: A parsed source.

    Returns:
        ``True`` when at least one named graph is not empty.
    """
    return any(
        graph != DATASET_DEFAULT_GRAPH_ID
        for _s, _p, _o, graph in dataset.quads((None, None, None, None))
    )


def n3_only_statements(dataset: Dataset) -> tuple[int, int]:
    """Count the statements holding a term that only N3 can carry (#542).

    An N3 formula (``{ … }``) parses into a ``QuotedGraph`` and an N3 variable
    (``@forAll :x``, ``?x``) into a ``Variable``. Neither is an IRI, a blank node or a
    literal, so no other format can hold them: rdflib's serialisers write the first as
    text that does not parse, or drop the statement. Statements are counted rather than
    formulae, because a formula nested in another makes the latter ambiguous.

    Args:
        dataset: A parsed source.

    Returns:
        The number of statements with a formula, and the number with a variable. A
        statement holding both is counted in each.
    """
    formulae = variables = 0
    for s, p, o, _graph in dataset.quads((None, None, None, None)):
        terms = (s, p, o)
        formulae += any(isinstance(term, QuotedGraph) for term in terms)
        variables += any(isinstance(term, Variable) for term in terms)
    return formulae, variables


def n3_only_message(source: Path, formulae: int, variables: int) -> str:
    """Explain why a source with N3 formulae or variables cannot be cast.

    Args:
        source: The source file.
        formulae: The number of statements holding a formula.
        variables: The number of statements holding a variable.

    Returns:
        The message, without any ``Error:`` prefix.
    """

    def statements(count: int) -> str:
        return f"{count} statement{'' if count == 1 else 's'}"

    counts = []
    if formulae:
        counts.append(f"{statements(formulae)} with a formula ({{ … }})")
    if variables:
        counts.append(f"{variables if formulae else statements(variables)} with a variable")
    return (
        f"Source '{source.name}' holds N3 constructs that no other format can carry: "
        f"{', '.join(counts)}. "
        f"Only N3 can hold them, so there is nothing cast can write."
    )


# ---------------------------------------------------------------------------
# Converter
# ---------------------------------------------------------------------------


class CastConverter:
    """Converts an RDF source file to one or more target formats.

    This class is stateless; a single instance can be used for multiple
    conversions.
    """

    def convert(
        self,
        *,
        source: Path,
        formats: list[str],
        output_dir: Path | None,
        pipe_mode: bool,
        allow_flatten: bool = False,
    ) -> ConversionResult:
        """Convert *source* to the requested *formats*.

        Args:
            source: Path to the source RDF file.  Must exist.
            formats: List of **canonical** rdflib format strings to produce
                (e.g. ``["xml", "json-ld"]``).  Must not be empty.
            output_dir: Directory for output files.  ``None`` means use the
                source file's parent directory.  Ignored in pipe mode.
            pipe_mode: When ``True`` (single-format, stdout output), the
                serialised RDF is returned in
                :attr:`ConversionResult.stdout_content` and no file is
                written.
            allow_flatten: When ``True``, a source with named graphs is
                written to a single-graph format by merging every graph
                into one.  When ``False`` (the default), that conversion is
                an error.  TriG and N-Quads output keeps the graphs either
                way.  A source has named graphs if it is TriG or N-Quads,
                or is JSON-LD and holds one.

        Returns:
            A :class:`ConversionResult` describing what happened.
        """
        result = ConversionResult()

        # --- 1. Detect source format ------------------------------------------
        source_format = infer_format(source)
        is_quad_source = is_quad_format(source_format)

        # --- 1a. Nothing to cast: every format is the source's own (#330) ------
        if nothing_to_cast(source_format, formats):
            result.error = nothing_to_cast_message(
                source, source_format, allow_flatten=allow_flatten
            )
            result.skipped_formats.append(source_format)
            result.success = False
            return result

        # --- 2. Guard: quad source → single-graph target ----------------------
        single_graph_targets = [f for f in formats if not is_quad_format(f)]
        if is_quad_source and single_graph_targets and not allow_flatten:
            result.error = named_graphs_message(source, source_format, single_graph_targets)
            result.success = False
            return result

        # --- 3. Parse source --------------------------------------------------
        try:
            dataset = self._load_dataset(source, source_format)
        except Exception as exc:  # noqa: BLE001
            result.error = (
                f"Failed to parse '{source.name}' as {source_format}: {exc}. "
                f"Check that the file is valid and the format is correct."
            )
            result.success = False
            return result

        # --- 3a. N3 constructs that no other format can carry (#542) ----------
        formulae, variables = n3_only_statements(dataset)
        if formulae or variables:
            result.error = n3_only_message(source, formulae, variables)
            result.success = False
            return result

        # --- 3b. A JSON-LD source holding named graphs is a quad source (#540) -
        holds_graphs = is_quad_source or (source_format == "json-ld" and has_named_graphs(dataset))
        merged_targets = [f for f in single_graph_targets if f != source_format]
        if holds_graphs and merged_targets and not allow_flatten:
            result.error = named_graphs_message(source, source_format, merged_targets)
            result.success = False
            return result

        flatten = holds_graphs and allow_flatten
        if flatten and merged_targets:
            result.warnings.append(
                f"Flattened {source.name} for {', '.join(merged_targets)}: "
                f"all named graphs merged into one graph."
            )

        # --- 4. Serialise to each target format --------------------------------
        effective_dir = output_dir if output_dir is not None else source.parent
        union: Graph | None = None

        for fmt in formats:
            if fmt == source_format:
                result.warnings.append(f"Skipping '{fmt}': source and target format are the same.")
                if fmt not in result.skipped_formats:
                    result.skipped_formats.append(fmt)
                continue

            # A quad target holds the dataset, graphs and all, whatever the flag. A
            # single-graph target holds the default graph, or the union when flattening.
            graph: Graph
            if is_quad_format(fmt):
                graph = dataset
            elif flatten:
                if union is None:
                    union = self._union(dataset)
                graph = union
            else:
                graph = dataset.get_context(DATASET_DEFAULT_GRAPH_ID)

            if pipe_mode:
                # Single format → stdout; we do not write any file.
                try:
                    content = self._serialise(graph, fmt).decode("utf-8")
                    result.stdout_content = content
                    result.success = True
                except Exception as exc:  # noqa: BLE001
                    result.error = f"Failed to serialise to {fmt}: {exc}"
                    result.success = False
                return result  # pipe mode always processes exactly one format

            # File output mode
            ext = extension_for_format(fmt)
            out_path = effective_dir / f"{source.stem}{ext}"
            try:
                effective_dir.mkdir(parents=True, exist_ok=True)
                if fmt == "nquads":
                    # Only N-Quads is rewritten after rdflib serialises it, so only it
                    # is built in memory first. The other formats keep rdflib's own
                    # write to the destination: what a failed write leaves is #409's.
                    out_path.write_bytes(self._serialise(graph, fmt))
                else:
                    graph.serialize(destination=str(out_path), format=fmt)
                result.written_files.append(out_path)
            except Exception as exc:  # noqa: BLE001
                result.failed_formats.append(fmt)
                result.warnings.append(f"Failed to write {out_path.name} ({fmt}): {exc}")

        # --- 5. Determine overall success -------------------------------------
        if result.failed_formats and result.written_files:
            result.partial_failure = True
            result.success = False
        elif result.failed_formats and not result.written_files:
            result.error = (
                f"All target format conversions failed: " f"{', '.join(result.failed_formats)}"
            )
            result.success = False
        else:
            result.success = True

        return result

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _load_dataset(source: Path, source_format: str) -> Dataset:
        """Parse *source* into an rdflib dataset.

        A single-graph source's triples land in the default graph. A source that
        carries named graphs (TriG, N-Quads, JSON-LD) keeps them. A plain
        :class:`~rdflib.Graph` would drop the named graphs, and would be written to
        TriG under its own blank-node identifier (#540).

        Args:
            source: Path to the RDF source file.
            source_format: Canonical rdflib format string.

        Returns:
            The parsed :class:`~rdflib.Dataset`.
        """
        dataset = Dataset()
        dataset.parse(str(source), format=source_format)
        return dataset

    @staticmethod
    def _union(dataset: Dataset) -> Graph:
        """Merge every graph of *dataset* into one plain graph.

        Iterates quads: ``Dataset.triples()`` reads only the default graph.

        Args:
            dataset: The parsed source.

        Returns:
            A plain :class:`~rdflib.Graph` holding each triple once, with the
            dataset's prefix bindings.
        """
        flat = Graph()
        for s, p, o, _graph in dataset.quads((None, None, None, None)):
            flat.add((s, p, o))
        for prefix, ns in dataset.namespaces():
            flat.bind(prefix, ns)
        return flat

    @staticmethod
    def _serialise(graph: Graph, fmt: str) -> bytes:
        """Serialise *graph* to bytes in the given format.

        rdflib writes a default-graph N-Quads statement with two spaces before the
        ``.``, one either side of the graph term it leaves out. That is valid but not
        canonical, so it is rewritten to one. The rewrite is exact: N-Quads escapes
        newlines inside literals, so only a statement can end a line.

        Args:
            graph: The rdflib graph or dataset to serialise.
            fmt: Canonical rdflib format string.

        Returns:
            The serialised RDF, UTF-8 encoded.
        """
        buf = io.BytesIO()
        graph.serialize(destination=buf, format=fmt)
        content = buf.getvalue()
        if fmt == "nquads":
            content = content.replace(b"  .\n", b" .\n")
        return content
