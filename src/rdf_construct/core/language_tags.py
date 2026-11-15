"""BCP 47 language tags: whether a tag is well formed, and how it is written (#159).

A language tag is case-insensitive (RFC 5646 §2.1.1): ``en-GB``, ``en-gb`` and ``EN-gb`` are one
tag in three spellings. rdflib keeps a tag exactly as it was typed, both when it parses a file and
when it constructs a literal, and only its term equality folds the case. So code that compares
tags as strings has to fold them itself, and code that writes a tag decides which spelling goes
out.

This module checks the *shape* of a tag against RFC 5646's grammar, and gives its canonical case.
It does not consult the IANA subtag registry: ``english`` is well formed (a five-to-eight letter
primary subtag is reserved, not forbidden), and ``i-klingon`` is not replaced by its preferred
value ``tlh``. Subtags are never matched against each other: ``en`` and ``en-GB`` are different
tags here, and whether a caller treats one as covering the other is that caller's decision.
"""

import re

#: The grandfathered tags of RFC 5646 §2.2.8, lower-cased. They do not fit the grammar, or fit it
#: only by accident, and are well formed by enumeration.
GRANDFATHERED: frozenset[str] = frozenset(
    {
        "en-gb-oed",
        "i-ami",
        "i-bnn",
        "i-default",
        "i-enochian",
        "i-hak",
        "i-klingon",
        "i-lux",
        "i-mingo",
        "i-navajo",
        "i-pwn",
        "i-tao",
        "i-tay",
        "i-tsu",
        "sgn-be-fr",
        "sgn-be-nl",
        "sgn-ch-de",
        "art-lojban",
        "cel-gaulish",
        "no-bok",
        "no-nyn",
        "zh-guoyu",
        "zh-hakka",
        "zh-min",
        "zh-min-nan",
        "zh-xiang",
    }
)

#: RFC 5646 §2.1's ``langtag`` and ``privateuse`` productions, matched without regard to case.
#: Only ever applied to ASCII text: under ``IGNORECASE`` Python lets the Kelvin sign, ``ſ``, ``ı``
#: and ``İ`` match ``[a-z]`` (#425), so :func:`is_well_formed` refuses non-ASCII first.
_LANGTAG = re.compile(
    r"""^(?:
        (?:[a-z]{2,3}(?:-[a-z]{3}){0,3}|[a-z]{4}|[a-z]{5,8})   # language, with extlang
        (?:-[a-z]{4})?                                         # script
        (?:-(?:[a-z]{2}|[0-9]{3}))?                            # region
        (?:-(?:[a-z0-9]{5,8}|[0-9][a-z0-9]{3}))*               # variants
        (?:-[0-9a-wy-z](?:-[a-z0-9]{2,8})+)*                   # extensions
        (?:-x(?:-[a-z0-9]{1,8})+)?                             # private use
      |
        x(?:-[a-z0-9]{1,8})+                                   # a private-use tag on its own
    )$""",
    re.VERBOSE | re.IGNORECASE,
)


class LanguageTagError(ValueError):
    """A language tag that is missing, blank, not text, or not well formed.

    Attributes:
        tag: The value as given.
    """

    def __init__(self, message: str, tag: object) -> None:
        super().__init__(message)
        self.tag = tag


def is_well_formed(tag: str) -> bool:
    """Return whether `tag` has the shape of a BCP 47 language tag.

    Args:
        tag: The tag, in any case.

    Returns:
        True if it matches RFC 5646's grammar or is a grandfathered tag. A tag is ASCII, so
        anything else is not well formed, and so is a tag with a trailing newline.
    """
    if not tag.isascii():
        return False  # also before folding: str.lower() maps the Kelvin sign to "k"
    return tag.lower() in GRANDFATHERED or _LANGTAG.fullmatch(tag) is not None


def canonical_case(tag: str) -> str:
    """Return `tag` in the case RFC 5646 §2.1.1 recommends.

    Everything is lower case except a script subtag, which is title case (``Hant``), and a
    two-letter region subtag, which is upper case (``GB``). Nothing after a singleton (an
    extension or ``x-``) is changed from lower case, and neither is the first subtag.

    Args:
        tag: A well-formed tag, in any case.

    Returns:
        The tag in canonical case: ``EN-gb`` becomes ``en-GB``, ``ZH-hant-tw`` becomes
        ``zh-Hant-TW``.
    """
    subtags = tag.lower().split("-")
    written = [subtags[0]]
    after_singleton = len(subtags[0]) == 1
    for subtag in subtags[1:]:
        if len(subtag) == 1:
            after_singleton = True
        if not after_singleton and len(subtag) == 2:
            subtag = subtag.upper()
        elif not after_singleton and len(subtag) == 4 and subtag.isalpha():
            subtag = subtag.title()
        written.append(subtag)
    return "-".join(written)


def primary_subtag(tag: str) -> str:
    """Return the first subtag of `tag`, lower-cased: ``en`` for ``en-GB``."""
    return tag.split("-", 1)[0].lower()


def check_tag(value: object, what: str) -> str:
    """Return `value` as a language tag, or refuse it.

    Args:
        value: The value as read, from a command line or a YAML file. YAML reads an unquoted
            ``no`` (Norwegian) as a boolean, so anything that is not a string is refused rather
            than converted.
        what: How to name the value in a message, e.g. ``"-l"`` or ``"target_language"``.

    Returns:
        The tag, stripped of surrounding whitespace and otherwise as given.

    Raises:
        LanguageTagError: If the value is missing, blank, not a string or not well formed.
    """
    if value is None:
        raise LanguageTagError(f"{what} is missing; give a language tag such as de or en-GB", value)
    if not isinstance(value, str):
        raise LanguageTagError(
            f"{what} must be a language tag, not {value!r}; in YAML, quote it (e.g. 'no')",
            value,
        )
    tag = value.strip()
    if not tag:
        raise LanguageTagError(f"{what} is blank; give a language tag such as de or en-GB", value)
    if not is_well_formed(tag):
        raise LanguageTagError(
            f"{what} {value!r} is not a well-formed BCP 47 language tag (RFC 5646), "
            "such as de, en-GB or zh-Hant-TW",
            value,
        )
    return tag
