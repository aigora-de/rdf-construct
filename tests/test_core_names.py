"""Unit tests for the shared name checker (#252, lifted from #144's ``diff`` filters).

``core.names.normalise_names`` maps what a user typed to a command's canonical names, or
refuses all the bad ones at once. ``diff``'s filters and ``docs``' entity types both use it;
their CLI refusals are tested in ``test_diff_filters.py`` and ``test_docs.py``.

Relates to: #252, #144
"""

import pytest

from rdf_construct.core.names import normalise_names

CANONICAL = ("apples", "pears", "plums")
SPELLINGS = {"apples": "apples", "apple": "apples", "pears": "pears", "plums": "plums"}


class Refused(ValueError):
    """A caller's own error class."""


def _check(names, label=""):
    return normalise_names(names, SPELLINGS, CANONICAL, "fruit", label, error=Refused)


def test_canonical_once_in_canonical_order() -> None:
    assert _check([" Plums", "apple", "APPLES", "", "pears"]) == ("apples", "pears", "plums")


def test_the_callers_error_is_raised() -> None:
    with pytest.raises(Refused):
        _check(["kiwi"])


def test_the_default_error_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="unknown fruit 'kiwi'"):
        normalise_names(["kiwi"], SPELLINGS, CANONICAL, "fruit")


def test_every_unknown_name_is_named_once_with_a_hint() -> None:
    with pytest.raises(Refused) as err:
        _check(["aples", "Kiwi", "kiwi", "pears"], "--fruit")
    assert str(err.value) == (
        "--fruit: unknown fruits 'aples' (did you mean 'apples'?), 'Kiwi'. "
        "Accepted: apples, pears, plums"
    )


@pytest.mark.parametrize("names", [[], [""], [" ", ""]])
def test_nothing_named_is_refused(names) -> None:
    with pytest.raises(Refused, match="^no fruits named. Accepted: apples, pears, plums$"):
        _check(names)


def test_a_bare_string_is_refused() -> None:
    with pytest.raises(Refused, match="not the string 'apples'; pass {'apples'}"):
        _check("apples")


@pytest.mark.parametrize("names", [["apples", None], [3]])
def test_a_name_that_is_not_a_string_is_refused(names) -> None:
    with pytest.raises(Refused, match="fruits are strings"):
        _check(names)


def test_a_set_is_named_in_sorted_order() -> None:
    bad = {f"zz{i}" for i in range(12)}
    with pytest.raises(Refused) as err:
        _check(bad)
    assert (
        str(err.value).index("'zz0'")
        < str(err.value).index("'zz1'")
        < str(err.value).index("'zz11'")
    )
