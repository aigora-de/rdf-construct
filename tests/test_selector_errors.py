"""Tests for unresolvable selector keys (issue #89).

A section whose ``select:`` named a key nothing could resolve selected
nothing, and said nothing. The section simply vanished from the output —
the same failure shape as #84 one level down: there a *profile* claimed
nothing, here a *section* did.

Since #88 the loss was usually surfaced by the unclaimed-subjects
warning, but its diagnosis actively misled: it named a section the user
believed they already had.
"""

import pytest
from click.testing import CliRunner
from rdflib import Graph

from rdf_construct.cli import cli
from rdf_construct.core.selector import (
    BUILTIN_SELECTOR_KEYS,
    UnknownSelectorError,
    is_known_selector,
    select_subjects,
)

SELECTORS = {
    "classes": "rdf:type owl:Class",
    "obj_props": "owl:ObjectProperty",
    # A custom name whose value is the same string obj_props carries, in the
    # `rdf:type X` form the classes selector accepts. It resolves for classes
    # and not for properties — the grammar is inconsistent, which is the half
    # of #89 deliberately left to a follow-up.
    "my_props": "rdf:type owl:ObjectProperty",
    "my_inds": "FILTER NOT EXISTS { ?s a owl:Class }",
}

ONTOLOGY = """
@prefix ex: <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:Thing a owl:Class .
ex:hasOwner a owl:ObjectProperty .
"""


@pytest.fixture
def graph() -> Graph:
    g = Graph()
    g.parse(data=ONTOLOGY, format="turtle")
    return g


class TestUnknownSelectorRaises:
    """An unresolvable key is an error, not an empty selection."""

    def test_typo_raises(self, graph: Graph):
        with pytest.raises(UnknownSelectorError) as excinfo:
            select_subjects(graph, "obj_propz", SELECTORS)

        message = str(excinfo.value)
        assert "obj_propz" in message
        # The message has to be actionable: name what is valid, and what this
        # config defines, or the user is left guessing at a spelling.
        assert "obj_props" in message
        assert "my_props" in message

    def test_key_absent_from_config_raises(self, graph: Graph):
        with pytest.raises(UnknownSelectorError):
            select_subjects(graph, "nonesuch", {})

    def test_defined_but_unrecognised_value_raises(self, graph: Graph):
        """The custom-name case, and the more surprising of the two.

        ``my_props`` *is* defined in the config, and its value is the same
        string ``obj_props`` carries. It still resolves to nothing, so it
        must say so rather than emitting an empty section.
        """
        with pytest.raises(UnknownSelectorError) as excinfo:
            select_subjects(graph, "my_props", SELECTORS)

        message = str(excinfo.value)
        assert "my_props" in message
        assert "rdf:type owl:ObjectProperty" in message
        # It should tell them the spelling that would work
        assert "owl:ObjectProperty" in message

    @pytest.mark.parametrize("key", BUILTIN_SELECTOR_KEYS)
    def test_builtin_keys_never_raise(self, graph: Graph, key: str):
        """Every documented key resolves, with or without a config entry."""
        select_subjects(graph, key, {})
        select_subjects(graph, key, SELECTORS)

    def test_custom_name_with_recognised_value_still_works(self, graph: Graph):
        """Config-defined names are not broken by this — only unresolvable ones."""
        selected = select_subjects(graph, "obj_props", SELECTORS)
        assert {str(s) for s in selected} == {"http://example.org/hasOwner"}

    def test_filter_form_still_works(self, graph: Graph):
        """Any value starting FILTER selects individuals, as before."""
        selected = select_subjects(graph, "my_inds", SELECTORS)
        assert isinstance(selected, set)


class TestIsKnownSelector:
    """The predicate callers use when they are probing on purpose."""

    @pytest.mark.parametrize("key", BUILTIN_SELECTOR_KEYS)
    def test_builtins_are_known(self, key: str):
        assert is_known_selector(key, {})

    def test_recognised_config_value_is_known(self):
        assert is_known_selector("obj_props", SELECTORS)
        assert is_known_selector("my_inds", SELECTORS)

    def test_unresolvable_keys_are_not_known(self):
        assert not is_known_selector("obj_propz", SELECTORS)
        assert not is_known_selector("my_props", SELECTORS)

    def test_agrees_with_select_subjects(self, graph: Graph):
        """The predicate and the dispatch must not disagree.

        If they drift, the CLI's unclaimed-subject hinting either crashes
        on a key it was probing or silently skips one that works.
        """
        for key in list(SELECTORS) + list(BUILTIN_SELECTOR_KEYS) + ["obj_propz"]:
            if is_known_selector(key, SELECTORS):
                select_subjects(graph, key, SELECTORS)
            else:
                with pytest.raises(UnknownSelectorError):
                    select_subjects(graph, key, SELECTORS)


class TestOrderCommandSurfacesIt:
    """End to end: the message names the section, and the run fails."""

    @staticmethod
    def _write(tmp_path, profile_body: str):
        model = tmp_path / "model.ttl"
        model.write_text(ONTOLOGY)
        config = tmp_path / "profile.yml"
        config.write_text(
            "selectors:\n"
            '  classes: "rdf:type owl:Class"\n'
            '  obj_props: "owl:ObjectProperty"\n'
            '  my_props: "rdf:type owl:ObjectProperty"\n'
            "\nprofiles:\n" + profile_body
        )
        return model, config

    def test_typo_fails_the_run(self, tmp_path):
        model, config = self._write(
            tmp_path,
            "  typo:\n"
            "    sections:\n"
            "      - classes: {select: classes, sort: alpha}\n"
            "      - object_properties: {select: obj_propz, sort: alpha}\n",
        )
        result = CliRunner().invoke(
            cli, ["order", str(model), str(config), "-p", "typo", "-o", str(tmp_path / "out")]
        )

        assert result.exit_code == 2
        assert "obj_propz" in result.output
        # The section is named, so the user knows which line to fix
        assert "object_properties" in result.output
        assert "typo" in result.output

    def test_nothing_is_written_when_it_fails(self, tmp_path):
        """A half-built profile on disk would be worse than none."""
        model, config = self._write(
            tmp_path,
            "  typo:\n"
            "    sections:\n"
            "      - classes: {select: classes, sort: alpha}\n"
            "      - object_properties: {select: obj_propz, sort: alpha}\n",
        )
        out = tmp_path / "out"
        CliRunner().invoke(cli, ["order", str(model), str(config), "-p", "typo", "-o", str(out)])

        assert not out.exists() or not list(out.glob("*.ttl"))

    def test_valid_profile_is_unaffected(self, tmp_path):
        model, config = self._write(
            tmp_path,
            "  good:\n"
            "    sections:\n"
            "      - classes: {select: classes, sort: alpha}\n"
            "      - object_properties: {select: obj_props, sort: alpha}\n"
            "      - individuals: {select: individuals, sort: alpha}\n",
        )
        out = tmp_path / "out"
        result = CliRunner().invoke(
            cli, ["order", str(model), str(config), "-p", "good", "-o", str(out)]
        )

        assert result.exit_code == 0
        assert list(out.glob("*.ttl"))

    def test_unclaimed_warning_still_works(self, tmp_path):
        """The hinting walks config keys, including unresolvable ones.

        It probes on purpose, so it must skip what it cannot resolve
        rather than dying on it — a regression here would turn a warning
        path into a crash.
        """
        model, config = self._write(
            tmp_path,
            "  partial:\n" "    sections:\n" "      - classes: {select: classes, sort: alpha}\n",
        )
        result = CliRunner().invoke(
            cli, ["order", str(model), str(config), "-p", "partial", "-o", str(tmp_path / "out")]
        )

        assert result.exit_code == 0
        # hasOwner is unclaimed, and the warning should suggest obj_props
        assert "obj_props" in result.output


class TestNonStringSelectorValues:
    """The shipped starter template writes lists, not strings.

    ``templates/ordering_starter.yml`` — the file the docs tell users to
    copy — defines each selector as a YAML list. ``.strip()`` on a list is
    an ``AttributeError`` traceback, so the shipped template did not run
    at all. Found while implementing #89; same line, same function.
    """

    def test_list_valued_builtin_key_still_dispatches(self, graph: Graph):
        """A built-in key dispatches on its *name*, so the value is moot."""
        selectors = {"classes": ["owl:Class", "rdfs:Class"]}
        selected = select_subjects(graph, "classes", selectors)

        assert {str(s) for s in selected} == {"http://example.org/Thing"}

    def test_list_valued_custom_key_errors_rather_than_crashing(self, graph: Graph):
        """An unresolvable one still gets the actionable error, not a traceback."""
        with pytest.raises(UnknownSelectorError):
            select_subjects(graph, "my_list", {"my_list": ["owl:ObjectProperty"]})

    def test_is_known_selector_agrees(self):
        assert is_known_selector("classes", {"classes": ["owl:Class"]})
        assert not is_known_selector("my_list", {"my_list": ["owl:ObjectProperty"]})

    def test_shipped_starter_template_runs(self, tmp_path):
        """End to end, against the real template rather than a copy of it."""
        from pathlib import Path

        template = Path(__file__).parent.parent / "templates" / "ordering_starter.yml"
        assert template.exists(), "the starter template has moved"

        model = tmp_path / "model.ttl"
        model.write_text(ONTOLOGY)
        out = tmp_path / "out"

        result = CliRunner().invoke(cli, ["order", str(model), str(template), "-o", str(out)])

        assert result.exit_code == 0, result.output
        assert list(out.glob("*.ttl"))
