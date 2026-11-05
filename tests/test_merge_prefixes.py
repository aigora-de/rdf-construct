"""`merge` writes each source's own prefixes, under one rule when sources disagree (#357).

The fixtures in ``tests/fixtures/merge/prefixes/``:

- ``a.ttl`` and ``b.ttl`` each declare ``:`` and ``ex:`` for namespaces of their own; ``a.ttl``
  also declares ``org:``, which rdflib's built-in table binds to the W3C Organization ontology.
- ``c.ttl`` declares ``y:`` for the namespace ``a.ttl`` calls ``org:``.
- ``d.ttl``'s ``:`` namespace ends in a segment that is not a valid prefix (``…/2024#``).
- ``f.ttl`` declares ``ont:``, the name ``b.ttl``'s ``:`` would otherwise be given.
- ``g.ttl`` declares ``org:`` and also uses the W3C ``org`` namespace, written in full.
- ``e.nt`` is N-Triples, so it can declare no prefix at all.
- ``h.ttl`` declares ``ex1:`` for ``a.ttl``'s ``ex:`` namespace, so that name is not free.
- ``k.ttl`` declares ``o2:`` for OWL's namespace.

Every test checks a ``@prefix`` line *and* the graph by IRI, so a prefix that names the wrong
namespace cannot pass.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import yaml
from click.testing import CliRunner, Result
from rdflib import Graph, Literal, URIRef
from rdflib.compare import isomorphic

from rdf_construct.cli import cli
from tests.test_cli_smoke import assert_no_crash

FIXTURES = Path(__file__).parent / "fixtures" / "merge" / "prefixes"
CONFLICTS = Path(__file__).parent / "fixtures" / "merge" / "conflicts"
EXAMPLES = Path(__file__).parent.parent / "examples"
SKOS = "http://www.w3.org/2004/02/skos/core#"


def _f(name: str) -> Path:
    return FIXTURES / name


def _merge(tmp_path: Path, *argv: object) -> tuple[Result, str]:
    out = tmp_path / "merged.ttl"
    result = CliRunner().invoke(cli, ["merge", *[str(a) for a in argv], "-o", str(out)])
    assert_no_crash(result)
    return result, (out.read_text() if out.exists() else "")


def _prefixes(text: str) -> dict[str, str]:
    """The ``@prefix`` lines of a Turtle file, prefix to namespace."""
    return dict(re.findall(r"^@prefix ([^:\s]*): <([^>]*)> \.$", text, re.MULTILINE))


def _graph(text: str) -> Graph:
    return Graph().parse(data=text, format="turtle")


def _union(*names: str) -> Graph:
    g = Graph()
    for name in names:
        g.parse(_f(name))
    return g


def _notes(result: Result) -> list[str]:
    return [line for line in result.stderr.splitlines() if line.startswith("Note: ")]


class TestOwnPrefixes:
    def test_a_source_prefix_rdflib_also_binds_is_kept(self, tmp_path):
        source = EXAMPLES / "organisation_ontology.ttl"
        result, text = _merge(tmp_path, source)
        assert result.exit_code == 0, result.output
        assert _prefixes(text)["org"] == "http://example.org/organisation#"
        assert "org1" not in _prefixes(text)
        assert isomorphic(_graph(text), Graph().parse(source))
        assert _notes(result) == []

    def test_a_curie_in_the_output_names_the_sources_namespace(self, tmp_path):
        result, text = _merge(tmp_path, _f("a.ttl"))
        assert result.exit_code == 0, result.output
        assert "org:Team a owl:Class" in text
        assert (URIRef("http://example.org/organisation#Team"), None, None) in _graph(text)


class TestOnePrefixTwoNamespaces:
    def test_the_first_source_keeps_it_and_the_other_is_renamed(self, tmp_path):
        result, text = _merge(tmp_path, _f("a.ttl"), _f("b.ttl"))
        assert result.exit_code == 0, result.output
        prefixes = _prefixes(text)
        assert prefixes[""] == "http://a.example/ont#"
        assert prefixes["ont"] == "http://b.example/ont#"
        assert prefixes["ex"] == "http://a.example/ex#"
        assert prefixes["ex1"] == "http://b.example/ex#"
        assert "default1" not in prefixes
        assert "ont:B a owl:Class" in text and "ex1:Y a owl:Class" in text
        assert isomorphic(_graph(text), _union("a.ttl", "b.ttl"))

    def test_each_renamed_binding_is_noted(self, tmp_path):
        result, _ = _merge(tmp_path, _f("a.ttl"), _f("b.ttl"))
        assert _notes(result) == [
            'Note: b.ttl declares ":" for <http://b.example/ont#>, which a.ttl uses for '
            '<http://a.example/ont#>; written as "ont:". Set namespaces.preferred_prefixes '
            "to choose.",
            'Note: b.ttl declares "ex:" for <http://b.example/ex#>, which a.ttl uses for '
            '<http://a.example/ex#>; written as "ex1:". Set namespaces.preferred_prefixes '
            "to choose.",
        ]
        assert "Note:" not in result.stdout

    def test_command_line_order_decides(self, tmp_path):
        result, text = _merge(tmp_path, _f("b.ttl"), _f("a.ttl"))
        assert result.exit_code == 0, result.output
        prefixes = _prefixes(text)
        assert prefixes[""] == "http://b.example/ont#"
        assert prefixes["ont"] == "http://a.example/ont#"
        assert prefixes["ex1"] == "http://a.example/ex#"
        assert isomorphic(_graph(text), _union("a.ttl", "b.ttl"))

    def test_priority_does_not_decide(self, tmp_path):
        _, first = _merge(tmp_path, _f("a.ttl"), _f("b.ttl"))
        _, prioritised = _merge(tmp_path, _f("a.ttl"), _f("b.ttl"), "-p", "1", "-p", "9")
        assert _prefixes(prioritised) == _prefixes(first)

    def test_a_generated_name_never_takes_a_declared_prefix(self, tmp_path):
        # f.ttl, given last, declares ont:; b.ttl's ":" must not take it from f.ttl
        result, text = _merge(tmp_path, _f("a.ttl"), _f("b.ttl"), _f("f.ttl"))
        assert result.exit_code == 0, result.output
        prefixes = _prefixes(text)
        assert prefixes["ont"] == "http://f.example/ontology#"
        assert prefixes["ont1"] == "http://b.example/ont#"
        assert isomorphic(_graph(text), _union("a.ttl", "b.ttl", "f.ttl"))

    def test_a_generated_name_avoids_a_prefix_declared_only_in_passing(self, tmp_path):
        # h.ttl's ex1: is dropped (its namespace is a.ttl's ex:), but it is still declared
        result, text = _merge(tmp_path, _f("a.ttl"), _f("b.ttl"), _f("h.ttl"))
        assert result.exit_code == 0, result.output
        prefixes = _prefixes(text)
        assert prefixes["ex"] == "http://a.example/ex#"
        assert prefixes["ex2"] == "http://b.example/ex#"
        assert "ex1" not in prefixes
        assert isomorphic(_graph(text), _union("a.ttl", "b.ttl", "h.ttl"))

    def test_a_segment_that_is_no_prefix_falls_back_to_default(self, tmp_path):
        result, text = _merge(tmp_path, _f("a.ttl"), _f("d.ttl"))
        assert result.exit_code == 0, result.output
        prefixes = _prefixes(text)
        assert prefixes["default1"] == "http://d.example/2024#"
        assert "2024" not in prefixes
        assert isomorphic(_graph(text), _union("a.ttl", "d.ttl"))


class TestOneNamespaceTwoPrefixes:
    def test_the_first_prefix_is_kept_and_the_other_noted(self, tmp_path):
        result, text = _merge(tmp_path, _f("a.ttl"), _f("c.ttl"))
        assert result.exit_code == 0, result.output
        prefixes = _prefixes(text)
        assert prefixes["org"] == "http://example.org/organisation#"
        assert "y" not in prefixes
        assert "org:Unit a owl:Class" in text
        assert isomorphic(_graph(text), _union("a.ttl", "c.ttl"))
        assert _notes(result) == [
            'Note: c.ttl declares "y:" for <http://example.org/organisation#>, which is '
            'written as "org:".'
        ]

    def test_owl_keeps_owl(self, tmp_path):
        result, text = _merge(tmp_path, _f("k.ttl"))
        assert result.exit_code == 0, result.output
        prefixes = _prefixes(text)
        assert prefixes["owl"] == "http://www.w3.org/2002/07/owl#"
        assert "o2" not in prefixes
        assert isomorphic(_graph(text), Graph().parse(_f("k.ttl")))
        assert _notes(result) == [
            'Note: k.ttl declares "o2:" for <http://www.w3.org/2002/07/owl#>, which is '
            'written as "owl:".'
        ]


class TestNamespaceRemap:
    def test_a_remapped_source_keeps_its_own_org(self, tmp_path):
        config = tmp_path / "merge.yml"
        config.write_text(
            yaml.safe_dump(
                {
                    "sources": [
                        {
                            "path": str(_f("a.ttl")),
                            "namespace_remap": {"http://a.example/ex#": "http://a.example/v2#"},
                        }
                    ]
                }
            )
        )
        result, text = _merge(tmp_path, "-c", config)
        assert result.exit_code == 0, result.output
        prefixes = _prefixes(text)
        assert prefixes["org"] == "http://example.org/organisation#"
        assert prefixes["ex"] == "http://a.example/v2#"
        assert (URIRef("http://a.example/v2#X"), None, None) in _graph(text)
        assert (URIRef("http://example.org/organisation#Team"), None, None) in _graph(text)


class TestPreferredPrefixes:
    def _config(self, tmp_path: Path, preferred: dict[str, str]) -> Path:
        path = tmp_path / "merge.yml"
        path.write_text(
            yaml.safe_dump(
                {
                    "sources": [{"path": str(_f("a.ttl"))}, {"path": str(_f("b.ttl"))}],
                    "namespaces": {"preferred_prefixes": preferred},
                }
            )
        )
        return path

    def test_a_preference_claims_a_prefix_a_source_holds(self, tmp_path):
        config = self._config(tmp_path, {"ex": "http://b.example/ex#"})
        result, text = _merge(tmp_path, "-c", config)
        assert result.exit_code == 0, result.output
        prefixes = _prefixes(text)
        assert prefixes["ex"] == "http://b.example/ex#"
        assert prefixes["ex1"] == "http://a.example/ex#"
        assert "ex:Y a owl:Class" in text
        assert isomorphic(_graph(text), _union("a.ttl", "b.ttl"))
        assert (
            'Note: a.ttl declares "ex:" for <http://a.example/ex#>, which '
            "namespaces.preferred_prefixes gives to <http://b.example/ex#>; written as "
            '"ex1:". Set namespaces.preferred_prefixes to choose.'
        ) in _notes(result)

    def test_a_preference_is_not_itself_noted(self, tmp_path):
        config = self._config(tmp_path, {"bex": "http://b.example/ex#"})
        result, text = _merge(tmp_path, "-c", config)
        assert result.exit_code == 0, result.output
        assert _prefixes(text)["bex"] == "http://b.example/ex#"
        assert _prefixes(text)["ex"] == "http://a.example/ex#"
        assert not any("<http://b.example/ex#>" in note for note in _notes(result))

    def test_a_preference_for_org_takes_effect(self, tmp_path):
        config = self._config(tmp_path, {"org": "http://example.org/organisation#"})
        result, text = _merge(tmp_path, "-c", config)
        assert result.exit_code == 0, result.output
        assert _prefixes(text)["org"] == "http://example.org/organisation#"
        assert "org1" not in _prefixes(text)


class TestUndeclaredNamespaces:
    def test_rdflibs_table_names_what_no_source_names(self, tmp_path):
        result, text = _merge(tmp_path, _f("e.nt"))
        assert result.exit_code == 0, result.output
        prefixes = _prefixes(text)
        assert prefixes["foaf"] == "http://xmlns.com/foaf/0.1/"
        assert prefixes["skos"] == SKOS
        assert "ns1" not in prefixes
        assert isomorphic(_graph(text), Graph().parse(_f("e.nt"), format="nt"))

    def test_rdflibs_table_never_displaces_a_source_prefix(self, tmp_path):
        result, text = _merge(tmp_path, _f("g.ttl"))
        assert result.exit_code == 0, result.output
        prefixes = _prefixes(text)
        assert prefixes["org"] == "http://example.org/organisation#"
        # Nothing names W3C org's namespace: rdflib's table may not take org: or rename it
        assert "org1" not in prefixes
        assert (
            URIRef("http://example.org/organisation#Team"),
            URIRef("http://www.w3.org/ns/org#purpose"),
            None,
        ) in _graph(text)
        assert isomorphic(_graph(text), Graph().parse(_f("g.ttl")))
        assert _notes(result) == []


class TestDeterminism:
    def test_the_same_output_under_two_hash_seeds(self, tmp_path):
        outputs = []
        for seed in ("1", "2"):
            out = tmp_path / f"merged-{seed}.ttl"
            env = {**os.environ, "PYTHONHASHSEED": seed}
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "rdf_construct.cli",
                    "merge",
                    str(_f("a.ttl")),
                    str(_f("b.ttl")),
                    str(_f("c.ttl")),
                    str(_f("d.ttl")),
                    "-o",
                    str(out),
                ],
                env=env,
                check=True,
                capture_output=True,
            )
            outputs.append(out.read_text())
        assert outputs[0] == outputs[1]
        assert "ont:" in outputs[0] and "default1:" in outputs[0]


class TestConfigCuries:
    """#357 brings what #379 deferred: a CURIE in the conflicts section resolves."""

    def _config(self, tmp_path: Path, a: str, b: str, **sections: object) -> Path:
        data = {
            "sources": [
                {"path": str(CONFLICTS / a), "priority": 1},
                {"path": str(CONFLICTS / b), "priority": 2},
            ],
            **sections,
        }
        path = tmp_path / "merge.yml"
        path.write_text(yaml.safe_dump(data))
        return path

    def _detected(self, result: Result) -> int:
        for line in result.output.splitlines():
            if line.strip().startswith("Detected:"):
                return int(line.split(":")[1])
        assert "No conflicts detected" in result.output, result.output
        return 0

    def test_a_core_curie_resolves_and_takes_effect(self, tmp_path):
        plain = self._config(tmp_path, "labels_a.ttl", "labels_b.ttl")
        result, _ = _merge(tmp_path, "-c", plain)
        assert self._detected(result) > 0
        config = self._config(
            tmp_path,
            "labels_a.ttl",
            "labels_b.ttl",
            conflicts={"ignore_predicates": ["rdfs:label"]},
        )
        result, _ = _merge(tmp_path, "-c", config)
        assert result.exit_code == 0, result.output
        assert self._detected(result) == 0

    def test_an_unbound_prefix_is_refused_with_advice(self, tmp_path):
        config = self._config(
            tmp_path,
            "preflabel_a.ttl",
            "preflabel_b.ttl",
            conflicts={"ignore_predicates": ["skos:prefLabel"]},
        )
        result, text = _merge(tmp_path, "-c", config)
        assert result.exit_code == 2, result.output
        assert "'skos:prefLabel' is not an IRI" in result.output
        assert "namespaces.preferred_prefixes" in result.output
        assert text == ""

    def test_a_preferred_prefix_resolves(self, tmp_path):
        plain = self._config(tmp_path, "preflabel_a.ttl", "preflabel_b.ttl")
        result, _ = _merge(tmp_path, "-c", plain)
        assert self._detected(result) > 0
        config = self._config(
            tmp_path,
            "preflabel_a.ttl",
            "preflabel_b.ttl",
            namespaces={"preferred_prefixes": {"skos": SKOS}},
            conflicts={"ignore_predicates": ["skos:prefLabel"]},
        )
        result, text = _merge(tmp_path, "-c", config)
        assert result.exit_code == 0, result.output
        assert self._detected(result) == 0
        labels = set(_graph(text).objects(None, URIRef(SKOS + "prefLabel")))
        assert all(isinstance(label, Literal) for label in labels) and len(labels) > 1


class TestTheGuide:
    """``MERGE_SPLIT_GUIDE.md``'s "Prefixes in the Output" runs verbatim and says what it shows."""

    def _section(self) -> list[str]:
        guide = (EXAMPLES.parent / "docs" / "user_guides" / "MERGE_SPLIT_GUIDE.md").read_text()
        start = guide.index("#### Prefixes in the Output")
        section = guide[start : guide.index("### owl:imports Handling", start)]
        return re.findall(r"```(?:bash|yaml)?\n(.*?)```", section, re.S)

    def test_the_command_prints_the_note_shown(self, tmp_path):
        command, shown, _ = self._section()
        argv = shlex.split(command)
        assert argv[0] == "rdf-construct"
        argv = [str(EXAMPLES.parent / a) if a.startswith("examples/") else a for a in argv[1:]]
        argv = [str(tmp_path / a) if a == "merged.ttl" else a for a in argv]
        result = CliRunner().invoke(cli, argv)
        assert_no_crash(result)
        assert result.exit_code == 0, result.output
        assert result.stderr == shown
        prefixes = _prefixes((tmp_path / "merged.ttl").read_text())
        assert prefixes["ex"] == "http://example.org/animals#"
        assert prefixes["ex1"] == "http://example.org/test#"

    def test_the_preference_shown_takes_effect(self, tmp_path):
        _, _, preferences = self._section()
        config = yaml.safe_load(preferences)
        config["sources"] = [
            {"path": str(EXAMPLES / "animal_ontology.ttl")},
            {"path": str(EXAMPLES / "simple_ontology.ttl")},
        ]
        path = tmp_path / "merge.yml"
        path.write_text(yaml.safe_dump(config))
        result, text = _merge(tmp_path, "-c", path)
        assert result.exit_code == 0, result.output
        prefixes = _prefixes(text)
        assert prefixes["animal"] == "http://example.org/animals#"
        assert prefixes["ex"] == "http://example.org/test#"
        assert _notes(result) == []
