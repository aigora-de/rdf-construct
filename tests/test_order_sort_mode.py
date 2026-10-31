"""Tests for `order`'s refusal of a `sort:` mode it does not recognise (issue #242).

A section whose ``sort:`` named an unknown mode — a typo, or the natural
``topo`` — was ordered alphabetically, silently, at exit 0: the founding
feature switched off, with output identical to any rdflib serialiser. A
non-string value crashed on ``.lower()``.

The same change moves the check, and ``select:``'s, ahead of the first write:
``order`` writes each profile as it goes, so a refusal found in the second
profile used to leave the first one's file behind.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from rdf_construct.cli import cli
from rdf_construct.core import SORT_MODES

ONTOLOGY = """\
@prefix ex: <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:Zoo a owl:Class .
ex:Mammal a owl:Class ; rdfs:subClassOf ex:Zoo .
ex:Aardvark a owl:Class ; rdfs:subClassOf ex:Mammal .
"""

#: Parent first; alphabetical order is the exact reverse.
HIERARCHY = ["Zoo", "Mammal", "Aardvark"]


def _run(tmp_path: Path, profiles: str, *args: str) -> tuple[Result, Path]:
    """Write the ontology and a config holding ``profiles``, then run ``order``."""
    model = tmp_path / "model.ttl"
    model.write_text(ONTOLOGY, encoding="utf-8")
    config = tmp_path / "order.yml"
    config.write_text("profiles:\n" + profiles, encoding="utf-8")
    out = tmp_path / "out"
    result = CliRunner().invoke(cli, ["order", str(model), str(config), "-o", str(out), *args])
    return result, out


def _one_section(sort_line: str) -> str:
    """A single-profile config whose one section carries ``sort_line`` verbatim."""
    return "  p:\n    sections:\n      - classes:\n          select: classes\n" + sort_line


def _class_order(out: Path, profile: str = "p") -> list[str]:
    text = (out / f"model-{profile}.ttl").read_text(encoding="utf-8")
    return [line[len("ex:") :] for line in text.splitlines() if line.startswith("ex:")]


@pytest.mark.parametrize(
    "value",
    ["topolgical", "topo", '""', "null", "", "42", "true", "[topological]"],
    ids=["typo", "topo", "empty-string", "null", "bare-key", "int", "bool", "list"],
)
def test_unknown_sort_mode_is_refused_and_nothing_written(tmp_path: Path, value: str):
    """Exit 2, the profile, section and value named, the modes listed, no output directory."""
    result, out = _run(tmp_path, _one_section(f"          sort: {value}\n"))

    assert result.exit_code == 2, result.output
    assert not isinstance(result.exception, AttributeError)
    assert "profile 'p', section 'classes'" in result.output
    assert "unknown sort mode" in result.output
    for mode in SORT_MODES:
        assert mode in result.output
    assert not out.exists()


def test_typo_is_named_as_written(tmp_path: Path):
    result, _ = _run(tmp_path, _one_section("          sort: topolgical\n"))
    assert "'topolgical'" in result.output


def test_missing_sort_key_is_alphabetical(tmp_path: Path):
    """Omitting `sort:` is the default, not a refusal."""
    result, out = _run(tmp_path, _one_section(""))
    assert result.exit_code == 0, result.output
    assert _class_order(out) == sorted(HIERARCHY)


@pytest.mark.parametrize("mode", ["topological", "topological_then_alpha", "TOPOLOGICAL"])
def test_topological_spellings_order_parents_first(tmp_path: Path, mode: str):
    result, out = _run(tmp_path, _one_section(f"          sort: {mode}\n"))
    assert result.exit_code == 0, result.output
    assert _class_order(out) == HIERARCHY


@pytest.mark.parametrize("mode", ["alpha", "qname_alpha"])
def test_alphabetical_spellings(tmp_path: Path, mode: str):
    result, out = _run(tmp_path, _one_section(f"          sort: {mode}\n"))
    assert result.exit_code == 0, result.output
    assert _class_order(out) == sorted(HIERARCHY)


GOOD = "  a_good:\n    sections:\n      - classes: {sort: topological}\n"


@pytest.mark.parametrize(
    "bad",
    [
        "  b_bad:\n    sections:\n      - classes: {sort: 42}\n",
        "  b_bad:\n    sections:\n      - classes: {sort: topo}\n",
        "  b_bad:\n    sections:\n      - classes: {select: clases}\n",
    ],
    ids=["sort-int", "sort-topo", "select-typo"],
)
def test_a_later_bad_profile_stops_the_earlier_one_being_written(tmp_path: Path, bad: str):
    """The refusal used to come mid-run, after `a_good`'s file was on disk."""
    result, out = _run(tmp_path, GOOD + bad)

    assert result.exit_code == 2, result.output
    assert "Nothing was written" in result.output
    assert "profile 'b_bad', section 'classes'" in result.output
    assert not out.exists()


def test_every_problem_is_reported_at_once(tmp_path: Path):
    bad = (
        "  b_bad:\n    sections:\n"
        "      - classes: {sort: topo}\n"
        "      - individuals: {select: individualz}\n"
    )
    result, out = _run(tmp_path, GOOD + bad)

    assert result.exit_code == 2
    assert "'topo'" in result.output
    assert "'individualz'" in result.output
    assert not out.exists()


def test_a_profile_not_requested_is_not_checked(tmp_path: Path):
    """`-p` limits the run, and so limits what can refuse it."""
    result, out = _run(
        tmp_path, GOOD + "  b_bad:\n    sections:\n      - classes: {sort: topo}\n", "-p", "a_good"
    )
    assert result.exit_code == 0, result.output
    assert _class_order(out, "a_good") == HIERARCHY


def test_defined_selector_with_a_bad_value_is_refused_before_writing(tmp_path: Path):
    model = tmp_path / "model.ttl"
    model.write_text(ONTOLOGY, encoding="utf-8")
    config = tmp_path / "order.yml"
    config.write_text(
        'selectors:\n  mine: "owl:Klass"\n'
        "profiles:\n" + GOOD + "  b_bad:\n    sections:\n      - classes: {select: mine}\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    result = CliRunner().invoke(cli, ["order", str(model), str(config), "-o", str(out)])

    assert result.exit_code == 2, result.output
    assert "'owl:Klass'" in result.output
    assert not out.exists()


def test_header_section_needs_no_sort(tmp_path: Path):
    """A `header` section is not sorted, so it is not checked."""
    result, _ = _run(
        tmp_path, "  p:\n    sections:\n      - header: {}\n      - classes: {sort: alpha}\n"
    )
    assert result.exit_code == 0, result.output
