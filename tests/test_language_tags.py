"""Tests for core.language_tags: BCP 47 shape and canonical case (#159)."""

import pytest

from rdf_construct.core.language_tags import (
    LanguageTagError,
    canonical_case,
    check_tag,
    is_well_formed,
    primary_subtag,
)


@pytest.mark.parametrize(
    "tag",
    [
        "en",
        "EN-gb",
        "en-GB",
        "de",
        "und",
        "x-private",
        "en-x-foo",
        "zh-Hant-TW",
        "sgn-BE-FR",
        "i-klingon",
        "de-CH-1901",
        "es-419",
        "sr-Latn-RS",
        "en-GB-oed",
        "de-DE-u-co-phonebk",
        "zh-min-nan",
        "no",
    ],
)
def test_well_formed(tag: str) -> None:
    assert is_well_formed(tag)


@pytest.mark.parametrize(
    "tag", ["", " ", "en_GB", "en--GB", "not a tag!", "en-", "-en", "123", "q", "toolongprimary"]
)
def test_malformed(tag: str) -> None:
    assert not is_well_formed(tag)


@pytest.mark.parametrize(
    ("tag", "canonical"),
    [
        ("EN-gb", "en-GB"),
        ("en-gb", "en-GB"),
        ("DE", "de"),
        ("ZH-hant-tw", "zh-Hant-TW"),
        ("SGN-be-fr", "sgn-BE-FR"),
        ("I-KLINGON", "i-klingon"),
        ("X-Private", "x-private"),
        ("en-a-bc-x-ab", "en-a-bc-x-ab"),
        ("ES-419", "es-419"),
        ("DE-ch-1901", "de-CH-1901"),
    ],
)
def test_canonical_case(tag: str, canonical: str) -> None:
    assert canonical_case(tag) == canonical


def test_primary_subtag_folds() -> None:
    assert primary_subtag("EN-gb") == "en"


@pytest.mark.parametrize(
    ("value", "says"),
    [
        (None, "is missing"),
        ("", "is blank"),
        ("   ", "is blank"),
        (False, "quote it"),
        (7, "quote it"),
        ("en_GB", "not a well-formed"),
    ],
)
def test_check_tag_refuses(value: object, says: str) -> None:
    with pytest.raises(LanguageTagError, match=says):
        check_tag(value, "target_language")


def test_check_tag_strips_and_keeps_case() -> None:
    assert check_tag(" EN-gb ", "-l") == "EN-gb"
