"""Checking names a user gives against the set a command accepts.

A name that resolves to nothing is an error that names the valid set (#265): dropping it
narrows what a command does without saying so. ``diff``'s filters (#144) and ``docs``'
entity types (#252) both map what was typed to canonical names here, so both refuse the
same shapes with the same message.
"""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


def normalise_names(
    names: Iterable[str],
    spellings: Mapping[str, str],
    canonical: tuple[str, ...],
    kind: str,
    label: str = "",
    error: type[ValueError] = ValueError,
) -> tuple[str, ...]:
    """Map names to canonical ones, or refuse them all at once.

    Names are trimmed and matched without regard to case. Empty names are skipped, but a
    collection with no name left in it is refused. Every unknown name is reported once, as
    first written, in the order given, with a near match where there is one, then the
    accepted names.

    Args:
        names: The names given, in any case, possibly padded with whitespace
        spellings: Every accepted spelling, lower-cased, to its canonical name
        canonical: The canonical names, in the order they are listed and returned
        kind: What a name is, for the message: ``change type`` or ``entity type``
        label: What the names were given as, prefixed to the message; empty for none
        error: The exception to raise, a ``ValueError``

    Returns:
        The canonical names, each once, in canonical order

    Raises:
        ValueError: As ``error``, if ``names`` is a string, holds something that is not a
            string, names nothing, or holds any name not in ``spellings``
    """
    prefix = f"{label}: " if label else ""
    if isinstance(names, str):
        raise error(
            f"{prefix}expected a collection of {kind}s, not the string {names!r}; "
            f"pass {{{names!r}}}"
        )
    listed = list(names)
    strange = [name for name in listed if not isinstance(name, str)]
    if strange:
        raise error(f"{prefix}{kind}s are strings, not {strange[0]!r}")
    # A set has no order of its own: sort it, so the message is the same on every run
    ordered = sorted(listed) if isinstance(names, set | frozenset) else listed
    given = [name.strip() for name in ordered]
    given = [name for name in given if name]
    accepted = ", ".join(canonical)
    if not given:
        raise error(f"{prefix}no {kind}s named. Accepted: {accepted}")
    # Each unknown name once, as first written, in the order given; case does not make it new
    first: dict[str, str] = {}
    for name in given:
        if name.lower() not in spellings:
            first.setdefault(name.lower(), name)
    unknown = list(first.values())
    if unknown:
        parts = []
        for name in unknown:
            nearest = difflib.get_close_matches(name.lower(), list(spellings), n=1)
            hint = f" (did you mean '{spellings[nearest[0]]}'?)" if nearest else ""
            parts.append(f"'{name}'{hint}")
        plural = "s" if len(unknown) > 1 else ""
        raise error(f"{prefix}unknown {kind}{plural} {', '.join(parts)}. Accepted: {accepted}")
    chosen = {spellings[name.lower()] for name in given}
    return tuple(name for name in canonical if name in chosen)
