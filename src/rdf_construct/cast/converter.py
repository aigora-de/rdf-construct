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

from rdflib import ConjunctiveGraph, Graph

from rdf_construct.core.formats import (
    extension_for_format,
    infer_format,
    is_quad_format,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ConversionResult:
    """The outcome of a :meth:`CastConverter.convert` call.

    Attributes:
        success: ``True`` if at least one format was converted without fatal
            error (even when :attr:`partial_failure` is ``True``).
        partial_failure: ``True`` when some formats succeeded and some failed.
            Only relevant in multi-format mode.
        error: Set to a human-readable message on complete failure (parse
            error, all formats failed, quad-guard rejection, etc.).
        written_files: Paths of output files that were actually written.
        stdout_content: Serialised RDF string when in pipe mode; ``None``
            otherwise.
        warnings: Non-fatal messages (skipped source==target format, etc.).
        failed_formats: Canonical format names that failed to serialise.
    """

    success: bool = False
    partial_failure: bool = False
    error: str | None = None
    written_files: list[Path] = field(default_factory=list)
    stdout_content: str | None = None
    warnings: list[str] = field(default_factory=list)
    failed_formats: list[str] = field(default_factory=list)


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
            allow_flatten: When ``True``, multi-graph (quad) source files are
                flattened into the default graph before conversion.  When
                ``False`` (the default), converting a quad source to a
                single-graph format is an error.

        Returns:
            A :class:`ConversionResult` describing what happened.
        """
        result = ConversionResult()

        # --- 1. Detect source format ------------------------------------------
        source_format = infer_format(source)
        is_quad_source = is_quad_format(source_format)

        # --- 2. Guard: quad source → single-graph target ----------------------
        single_graph_targets = [f for f in formats if not is_quad_format(f)]
        if is_quad_source and single_graph_targets and not allow_flatten:
            result.error = (
                f"Source '{source.name}' uses a multi-graph format ({source_format}) "
                f"but the requested target format(s) are single-graph: "
                f"{', '.join(single_graph_targets)}. "
                f"Use --allow-flatten to merge all named graphs into the default graph, "
                f"or choose a quad output format (trig, nquads)."
            )
            result.success = False
            return result

        # --- 3. Parse source --------------------------------------------------
        try:
            graph = self._load_graph(
                source,
                source_format,
                flatten=is_quad_source and allow_flatten,
            )
        except Exception as exc:  # noqa: BLE001
            result.error = (
                f"Failed to parse '{source.name}' as {source_format}: {exc}. "
                f"Check that the file is valid and the format is correct."
            )
            result.success = False
            return result

        if is_quad_source and allow_flatten and single_graph_targets:
            result.warnings.append(
                f"Flattened {source.name}: all named graphs merged into the default graph."
            )

        # --- 4. Serialise to each target format --------------------------------
        effective_dir = output_dir if output_dir is not None else source.parent

        for fmt in formats:
            if fmt == source_format:
                result.warnings.append(
                    f"Skipping '{fmt}': source and target format are the same."
                )
                continue

            if pipe_mode:
                # Single format → stdout; we do not write any file.
                try:
                    content = self._serialise_to_string(graph, fmt)
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
                graph.serialize(destination=str(out_path), format=fmt)
                result.written_files.append(out_path)
            except Exception as exc:  # noqa: BLE001
                result.failed_formats.append(fmt)
                result.warnings.append(f"Failed to write {out_path.name} ({fmt}): {exc}")

        # --- 5. Determine overall success -------------------------------------
        # If every format was skipped (same-as-source) and nothing was attempted:
        if not result.written_files and not result.failed_formats and not result.stdout_content:
            # All formats were same-as-source; warn-and-skip is not a failure
            result.success = True
            return result

        if result.failed_formats and result.written_files:
            result.partial_failure = True
            result.success = False
        elif result.failed_formats and not result.written_files:
            result.error = (
                f"All target format conversions failed: "
                f"{', '.join(result.failed_formats)}"
            )
            result.success = False
        else:
            result.success = True

        return result

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _load_graph(source: Path, source_format: str, *, flatten: bool) -> Graph:
        """Parse *source* and return an rdflib graph.

        Args:
            source: Path to the RDF source file.
            source_format: Canonical rdflib format string.
            flatten: If ``True``, parse as a :class:`~rdflib.ConjunctiveGraph`
                and return a plain :class:`~rdflib.Graph` containing all
                triples from all named graphs merged into the default graph.

        Returns:
            A parsed rdflib :class:`~rdflib.Graph`.
        """
        if flatten:
            cg = ConjunctiveGraph()
            cg.parse(str(source), format=source_format)
            # Merge all quads into a plain Graph
            flat = Graph()
            for s, p, o in cg.triples((None, None, None)):
                flat.add((s, p, o))
            # Copy prefix bindings from conjunctive graph default context
            for prefix, ns in cg.namespaces():
                flat.bind(prefix, ns)
            return flat
        else:
            g = Graph()
            g.parse(str(source), format=source_format)
            return g

    @staticmethod
    def _serialise_to_string(graph: Graph, fmt: str) -> str:
        """Serialise *graph* to a string in the given format.

        Args:
            graph: The rdflib graph to serialise.
            fmt: Canonical rdflib format string.

        Returns:
            The serialised RDF as a string.
        """
        buf = io.BytesIO()
        graph.serialize(destination=buf, format=fmt)
        return buf.getvalue().decode("utf-8")
