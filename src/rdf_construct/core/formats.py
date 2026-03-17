"""Shared RDF format utilities for rdf-construct.

This module is the single source of truth for:
- Format alias normalisation (``"ttl"`` → ``"turtle"``)
- File-extension inference (``Path("ont.ttl")`` → ``"turtle"``)
- Default output extension per canonical format
- Detecting multi-graph (quad) formats
- Computing the default ``cast`` output format set

Other commands that currently duplicate format-detection logic (``uml``,
``cq_test``, ``docs``) should migrate to this module in a follow-up refactor.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Format registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FormatInfo:
    """Metadata for a canonical rdflib serialisation format.

    Attributes:
        canonical: The rdflib format string (e.g. ``"turtle"``).
        extensions: File extensions that map to this format (first is the
            default output extension).
        is_quad: Whether this format supports named graphs / quad streams.
        in_default_cast: Whether this format is included in the default
            ``cast`` output set (when ``--format`` is omitted).
    """

    canonical: str
    extensions: tuple[str, ...]
    is_quad: bool = False
    in_default_cast: bool = False


#: Complete registry of supported formats.
FORMAT_REGISTRY: tuple[FormatInfo, ...] = (
    FormatInfo(
        canonical="turtle",
        extensions=(".ttl", ".turtle"),
        is_quad=False,
        in_default_cast=True,
    ),
    FormatInfo(
        canonical="xml",
        extensions=(".rdf", ".xml", ".owl"),
        is_quad=False,
        in_default_cast=True,
    ),
    FormatInfo(
        canonical="json-ld",
        extensions=(".jsonld", ".json"),
        is_quad=False,
        in_default_cast=True,
    ),
    FormatInfo(
        canonical="nt",
        extensions=(".nt", ".ntriples"),
        is_quad=False,
        in_default_cast=False,
    ),
    FormatInfo(
        canonical="n3",
        extensions=(".n3",),
        is_quad=False,
        in_default_cast=False,  # N3 is a superset of Turtle; opt-in only
    ),
    FormatInfo(
        canonical="trig",
        extensions=(".trig",),
        is_quad=True,
        in_default_cast=False,
    ),
    FormatInfo(
        canonical="nquads",
        extensions=(".nq",),
        is_quad=True,
        in_default_cast=False,
    ),
)

#: Mapping from every accepted alias (lowercased) to canonical format name.
FORMAT_ALIASES: dict[str, str] = {}

#: Mapping from canonical format name to FormatInfo.
_FORMAT_BY_CANONICAL: dict[str, FormatInfo] = {}

#: Mapping from file extension (including dot, lowercased) to canonical format.
_FORMAT_BY_EXTENSION: dict[str, str] = {}

for _fi in FORMAT_REGISTRY:
    _FORMAT_BY_CANONICAL[_fi.canonical] = _fi
    for _ext in _fi.extensions:
        _FORMAT_BY_EXTENSION[_ext.lower()] = _fi.canonical

# Build alias table — covers all extension stems and common variants.
_EXTRA_ALIASES: dict[str, str] = {
    # Turtle
    "ttl": "turtle",
    "turtle": "turtle",
    # XML / RDF/XML
    "xml": "xml",
    "rdf": "xml",
    "rdfxml": "xml",
    "rdf/xml": "xml",
    "owl": "xml",
    # JSON-LD
    "json-ld": "json-ld",
    "jsonld": "json-ld",
    "json_ld": "json-ld",
    # N-Triples
    "nt": "nt",
    "ntriples": "nt",
    "n-triples": "nt",
    # N3
    "n3": "n3",
    # TriG
    "trig": "trig",
    # N-Quads
    "nq": "nquads",
    "nquads": "nquads",
    "n-quads": "nquads",
}
# Add each canonical name as its own alias.
for _fi in FORMAT_REGISTRY:
    _EXTRA_ALIASES.setdefault(_fi.canonical, _fi.canonical)

FORMAT_ALIASES.update(_EXTRA_ALIASES)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalise_format(alias: str) -> str:
    """Return the canonical rdflib format string for an alias.

    Args:
        alias: A format name or alias, e.g. ``"ttl"``, ``"json-ld"``,
            ``"rdfxml"``.

    Returns:
        The canonical format string, e.g. ``"turtle"``.

    Raises:
        ValueError: If the alias is not recognised.

    Examples:
        >>> normalise_format("ttl")
        'turtle'
        >>> normalise_format("jsonld")
        'json-ld'
    """
    key = alias.strip().lower()
    canonical = FORMAT_ALIASES.get(key)
    if canonical is None:
        supported = ", ".join(sorted(FORMAT_ALIASES))
        raise ValueError(
            f"Unknown format '{alias}'. Supported aliases: {supported}"
        )
    return canonical


def extension_for_format(canonical_format: str) -> str:
    """Return the preferred output file extension for a canonical format.

    Args:
        canonical_format: A canonical rdflib format string.

    Returns:
        File extension including the leading dot, e.g. ``".ttl"``.

    Raises:
        KeyError: If the canonical format is not in the registry.

    Examples:
        >>> extension_for_format("turtle")
        '.ttl'
        >>> extension_for_format("json-ld")
        '.jsonld'
    """
    return _FORMAT_BY_CANONICAL[canonical_format].extensions[0]


def infer_format(path: Path) -> str:
    """Infer the canonical rdflib parse format from a file extension.

    Args:
        path: Path to an RDF file.

    Returns:
        A canonical rdflib format string.  Defaults to ``"turtle"`` when the
        extension is not recognised.

    Examples:
        >>> infer_format(Path("ontology.ttl"))
        'turtle'
        >>> infer_format(Path("data.rdf"))
        'xml'
    """
    ext = path.suffix.lower()
    return _FORMAT_BY_EXTENSION.get(ext, "turtle")


def is_quad_format(canonical_format: str) -> bool:
    """Return ``True`` if *canonical_format* supports named graphs (quads).

    Args:
        canonical_format: A canonical rdflib format string.

    Returns:
        ``True`` for ``"trig"`` and ``"nquads"``; ``False`` otherwise.
    """
    info = _FORMAT_BY_CANONICAL.get(canonical_format)
    return info.is_quad if info is not None else False


def default_cast_formats(source_format: str) -> list[str]:
    """Return the default set of output formats for the ``cast`` command.

    The default set is ``turtle``, ``xml``, ``json-ld``, minus whichever
    format the source file is already in.  N3 and quad formats are **not**
    included in the defaults; they must be requested explicitly.

    Args:
        source_format: The canonical format of the source file, used to
            exclude it from the output set.

    Returns:
        A list of canonical format strings to convert to.

    Examples:
        >>> default_cast_formats("turtle")
        ['xml', 'json-ld']
        >>> default_cast_formats("xml")
        ['turtle', 'json-ld']
    """
    return [
        fi.canonical
        for fi in FORMAT_REGISTRY
        if fi.in_default_cast and fi.canonical != source_format
    ]


#: All format aliases accepted by the ``cast --format`` option.
CAST_FORMAT_CHOICES: list[str] = sorted(FORMAT_ALIASES)
