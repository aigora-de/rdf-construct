"""`lint` sees every declared term (#204), and a file it cannot parse exits 2 (#322).

#204: `lint`'s class and property getters, and `property-no-type`'s set, are `core.vocab`'s
`CLASS_TYPES` and `ALL_PROPERTY_TYPES`, so a term declared only by an OWL characteristic or as
`owl:DeprecatedClass`/`owl:DeprecatedProperty` is checked. A finding on a deprecated term (either
type, or `owl:deprecated` true) is info under every rule and level, unless a `severity:` override
names the rule (ruled on #233, 2026-11-07).

#322: an unparseable file is `LintResult.parse_error`, not a finding. It is printed in file order
in `parse_into`'s wording, the summary line counts it apart, and the run exits 2 whatever
`--fail-on` says. A directory is refused before any file is read.

Findings are asserted by rule, term IRI and severity through `LintEngine`; `lint --format json`
crashes (#201). The CLI is asserted for exit codes and output. Every fixture is written into
`tmp_path`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner, Result
from rdflib import Graph, URIRef
from rdflib.namespace import OWL

from rdf_construct.cli import Refusal, cli, parse_into
from rdf_construct.core import preserve_literal_forms
from rdf_construct.core.vocab import ALL_PROPERTY_TYPES, CLASS_TYPES, is_deprecated
from rdf_construct.lint import JsonFormatter, LintEngine
from rdf_construct.lint.engine import LintConfig
from rdf_construct.lint.rules import Severity
from tests.test_cli_smoke import assert_no_crash

if TYPE_CHECKING:
    from pathlib import Path

EX = "http://example.org/x#"

PREFIXES = """\
@prefix ex: <http://example.org/x#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
"""

INVISIBLE = """\
ex:ancestorOf a owl:TransitiveProperty .
ex:OldThing a owl:DeprecatedClass .
"""

BAD_TTL = "@prefix ex: <http://example.org/x#> .\nex:A a owl:Class .\n"
GOOD_TTL = PREFIXES + "ex:Good a owl:Class .\n"


def _write(tmp_path: Path, name: str, body: str, prefixes: str = PREFIXES) -> Path:
    path = tmp_path / name
    path.write_text(prefixes + body)
    return path


def _raw(tmp_path: Path, name: str, content: str | bytes) -> Path:
    path = tmp_path / name
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)
    return path


def _run(*argv: object) -> Result:
    with preserve_literal_forms():
        result = CliRunner().invoke(cli, [str(a) for a in argv])
    assert_no_crash(result)
    return result


def _findings(path: Path, **config: object) -> set[tuple[str, str, Severity]]:
    """(rule, term IRI, severity) for each finding on a named term."""
    with preserve_literal_forms():
        result = LintEngine(LintConfig(**config)).lint_file(path)  # type: ignore[arg-type]
    assert result.parse_error is None, result.parse_error
    return {(i.rule_id, str(i.entity), i.severity) for i in result.issues if i.entity is not None}


def _on(findings: set[tuple[str, str, Severity]], term: str) -> dict[str, Severity]:
    """Rule → severity for one term."""
    return {rule: sev for rule, iri, sev in findings if iri == EX + term}


# -----------------------------------------------------------------------------
# #204: every declared term is seen
# -----------------------------------------------------------------------------


class TestEveryDeclarationIsSeen:
    def test_invisible_terms_are_now_checked(self, tmp_path: Path) -> None:
        findings = _findings(_write(tmp_path, "invisible.ttl", INVISIBLE))
        assert _on(findings, "ancestorOf") == {
            "missing-label": Severity.WARNING,
            "missing-comment": Severity.WARNING,
        }
        # owl:DeprecatedClass is a class; its findings are demoted (#233)
        assert _on(findings, "OldThing") == {
            "orphan-class": Severity.INFO,
            "missing-label": Severity.INFO,
            "missing-comment": Severity.INFO,
        }

    @pytest.mark.parametrize("prop_type", sorted(ALL_PROPERTY_TYPES), ids=str)
    def test_each_property_type_alone_declares_a_property(
        self, tmp_path: Path, prop_type: URIRef
    ) -> None:
        path = _write(tmp_path, "p.ttl", f"ex:term a <{prop_type}> .\n")
        rules = _on(_findings(path), "term")
        assert "missing-label" in rules
        assert "missing-comment" in rules
        assert "orphan-class" not in rules

    @pytest.mark.parametrize("class_type", sorted(CLASS_TYPES), ids=str)
    def test_each_class_type_alone_declares_a_class(
        self, tmp_path: Path, class_type: URIRef
    ) -> None:
        path = _write(tmp_path, "c.ttl", f"ex:Term a <{class_type}> .\n")
        rules = _on(_findings(path), "Term")
        assert {"missing-label", "missing-comment", "orphan-class"} <= set(rules)

    def test_a_kindless_property_gets_the_documentation_rules_not_domain_or_range(
        self, tmp_path: Path
    ) -> None:
        # Q2: owl:FunctionalProperty says nothing about object or datatype; domain and
        # range checks are #205's
        path = _write(tmp_path, "f.ttl", "ex:HasId a owl:FunctionalProperty .\n")
        assert set(_on(_findings(path), "HasId")) == {
            "missing-label",
            "missing-comment",
            "inconsistent-naming",
        }

    def test_property_no_type_accepts_a_characteristic(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "t.ttl",
            "ex:hasPart a owl:TransitiveProperty ; rdfs:domain ex:A .\n"
            "ex:untyped rdfs:domain ex:A .\n",
        )
        findings = _findings(path)
        assert "property-no-type" not in _on(findings, "hasPart")
        assert "property-no-type" in _on(findings, "untyped")

    def test_a_blank_node_class_is_not_a_term(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "b.ttl",
            "[] a owl:Class ; owl:unionOf ( ex:A ex:B ) .\n"
            "[] a owl:DeprecatedClass .\n"
            "[] a owl:TransitiveProperty .\n",
        )
        with preserve_literal_forms():
            result = LintEngine().lint_file(path)
        assert all(isinstance(i.entity, URIRef) for i in result.issues if i.entity is not None)
        assert result.issues == []

    def test_a_newly_visible_foreign_term_is_still_skipped(self, tmp_path: Path) -> None:
        # P62's skip (#368) applies to what #204 adds
        path = _write(
            tmp_path,
            "own.ttl",
            "<http://example.org/x> a owl:Ontology ; rdfs:label 'x' .\n"
            "prov:wasDerivedFrom a owl:FunctionalProperty .\n",
        )
        iris = {iri for _, iri, _ in _findings(path)}
        assert "http://www.w3.org/ns/prov#wasDerivedFrom" not in iris


# -----------------------------------------------------------------------------
# #204 / #233: deprecated terms are reported at info
# -----------------------------------------------------------------------------


DEPRECATED = """\
ex:ByClassType a owl:DeprecatedClass .
ex:byPropertyType a owl:DeprecatedProperty .
ex:ByTypedTrue a owl:Class ; owl:deprecated true .
ex:ByPlainTrue a owl:Class ; owl:deprecated "true" .
ex:ByOne a owl:Class ; owl:deprecated "1"^^xsd:boolean .
ex:NotByFalse a owl:Class ; owl:deprecated false .
ex:NotByUpper a owl:Class ; owl:deprecated "TRUE" .
"""


class TestDeprecatedTermsAreInfo:
    @pytest.mark.parametrize(
        "term", ["ByClassType", "byPropertyType", "ByTypedTrue", "ByPlainTrue", "ByOne"]
    )
    @pytest.mark.parametrize("level", ["standard", "strict"])
    def test_every_mechanism_demotes_at_every_level(
        self, tmp_path: Path, term: str, level: str
    ) -> None:
        rules = _on(_findings(_write(tmp_path, "d.ttl", DEPRECATED), level=level), term)
        assert "missing-label" in rules
        assert set(rules.values()) == {Severity.INFO}

    @pytest.mark.parametrize("term", ["NotByFalse", "NotByUpper"])
    def test_not_deprecated_is_not_demoted(self, tmp_path: Path, term: str) -> None:
        rules = _on(_findings(_write(tmp_path, "d.ttl", DEPRECATED)), term)
        assert rules["missing-label"] == Severity.WARNING
        rules = _on(_findings(_write(tmp_path, "d.ttl", DEPRECATED), level="strict"), term)
        assert rules["missing-label"] == Severity.ERROR

    def test_an_override_naming_the_rule_wins(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "d.ttl", DEPRECATED)
        rules = _on(
            _findings(path, severity_overrides={"missing-label": Severity.ERROR}), "ByClassType"
        )
        assert rules["missing-label"] == Severity.ERROR
        assert rules["missing-comment"] == Severity.INFO

    def test_a_structural_rule_is_demoted_too(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "cycle.ttl",
            "ex:Old a owl:DeprecatedClass ; rdfs:subClassOf ex:Live .\n"
            "ex:Live a owl:Class ; rdfs:subClassOf ex:Old .\n",
        )
        findings = _findings(path)
        assert _on(findings, "Old")["circular-subclass"] == Severity.INFO
        assert _on(findings, "Live")["circular-subclass"] == Severity.ERROR

    def test_a_deprecated_only_file_passes_a_strict_gate(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "d.ttl", "ex:Old a owl:DeprecatedClass .\n")
        assert _run("lint", "--level", "strict", path).exit_code == 0
        assert _run("lint", "--fail-on", "info", path).exit_code == 1

    def test_lint_graph_demotes_too(self) -> None:
        graph = Graph().parse(data=PREFIXES + INVISIBLE, format="turtle")
        result = LintEngine(LintConfig(level="strict")).lint_graph(graph)
        old = {i.severity for i in result.issues if i.entity == URIRef(EX + "OldThing")}
        assert old == {Severity.INFO}

    def test_is_deprecated_reads_by_value(self, tmp_path: Path) -> None:
        graph = Graph().parse(_write(tmp_path, "d.ttl", DEPRECATED))
        deprecated = {"ByClassType", "byPropertyType", "ByTypedTrue", "ByPlainTrue"}
        for term in deprecated | {"ByOne"}:
            assert is_deprecated(graph, URIRef(EX + term)), term
        for term in ("NotByFalse", "NotByUpper"):
            assert not is_deprecated(graph, URIRef(EX + term)), term
        assert OWL.DeprecatedClass in CLASS_TYPES


# -----------------------------------------------------------------------------
# #322: a file that cannot be parsed exits 2
# -----------------------------------------------------------------------------


class TestUnparseableFileExits2:
    @pytest.mark.parametrize("fail_on", ["error", "warning", "info", "never"])
    def test_exit_2_whatever_fail_on_says(self, tmp_path: Path, fail_on: str) -> None:
        bad = _raw(tmp_path, "bad.ttl", BAD_TTL)
        result = _run("lint", "--fail-on", fail_on, bad)
        assert result.exit_code == 2
        assert f"Could not parse {bad} as turtle: " in result.output
        assert 'Prefix "owl:" not bound' in result.output
        assert result.output.rstrip().endswith(
            "Found 0 errors, 0 warnings, 0 info in 1 file; 1 file could not be parsed"
        )
        assert "parse-error" not in result.output

    def test_mixed_run_reports_both_in_file_order_and_exits_2(self, tmp_path: Path) -> None:
        good = _raw(tmp_path, "good.ttl", GOOD_TTL)
        bad = _raw(tmp_path, "bad.ttl", BAD_TTL)
        result = _run("lint", good, bad)
        assert result.exit_code == 2
        out = result.output
        assert "warning[orphan-class] ex:Good" in out
        assert out.index("ex:Good") < out.index(f"Could not parse {bad} as turtle")
        assert "Found 0 errors, 3 warnings, 0 info in 2 files; 1 file could not be parsed" in out

    def test_two_bad_files_are_counted(self, tmp_path: Path) -> None:
        one = _raw(tmp_path, "one.ttl", BAD_TTL)
        two = _raw(tmp_path, "two.ttl", BAD_TTL)
        result = _run("lint", one, two)
        assert result.exit_code == 2
        assert "2 files could not be parsed" in result.output

    @pytest.mark.parametrize(
        ("name", "content", "fmt"),
        [
            ("bad.jsonld", "{ not json", "json-ld"),
            (
                "bad.rdf",
                "<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'><x>",
                "xml",
            ),
            (
                "q.nq",
                f"<{EX}A> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> "
                f"<http://www.w3.org/2002/07/owl#Class> <{EX}g> .\n",
                "turtle",
            ),
            ("t.trig", PREFIXES + "ex:g { ex:A a owl:Class . }\n", "turtle"),
            ("bin.ttl", b"\xff\xfe\x00garbage", "turtle"),
        ],
    )
    def test_each_unreadable_shape_exits_2_naming_the_format(
        self, tmp_path: Path, name: str, content: str | bytes, fmt: str
    ) -> None:
        path = _raw(tmp_path, name, content)
        result = _run("lint", "--fail-on", "never", path)
        assert result.exit_code == 2
        assert f"Could not parse {path} as {fmt}: " in result.output

    def test_a_directory_is_refused_before_anything_is_read(self, tmp_path: Path) -> None:
        good = _raw(tmp_path, "good.ttl", GOOD_TTL)
        folder = tmp_path / "folder"
        folder.mkdir()
        result = _run("lint", good, folder)
        assert result.exit_code == 2
        assert "is a directory" in result.output
        assert "Scanning" not in result.output

    def test_an_empty_file_parses(self, tmp_path: Path) -> None:
        result = _run("lint", _raw(tmp_path, "empty.ttl", ""))
        assert result.exit_code == 0
        assert "could not be parsed" not in result.output

    @pytest.mark.parametrize(
        ("name", "content"),
        [
            ("data.json", f'{{"@id": "{EX}A", "@type": "http://www.w3.org/2002/07/owl#Class"}}'),
            ("data.txt", GOOD_TTL),
        ],
    )
    def test_json_and_an_unknown_suffix_still_parse(
        self, tmp_path: Path, name: str, content: str
    ) -> None:
        result = _run("lint", _raw(tmp_path, name, content))
        assert result.exit_code == 0
        assert "could not be parsed" not in result.output

    def test_the_python_api(self, tmp_path: Path) -> None:
        good = _raw(tmp_path, "good.ttl", GOOD_TTL)
        bad = _raw(tmp_path, "bad.ttl", BAD_TTL)
        summary = LintEngine().lint_files([good, bad])
        result = summary.results[1]
        assert result.parse_error is not None
        assert result.parse_error.startswith(f"Could not parse {bad} as turtle: ")
        assert result.issues == []
        assert result.error_count == 0
        assert result.graph is None
        assert summary.unparsed == [result]
        assert summary.total_errors == 0

    def test_json_formatter_reports_it(self, tmp_path: Path) -> None:
        import json

        bad = _raw(tmp_path, "bad.ttl", BAD_TTL)
        summary = LintEngine().lint_files([bad])
        data = json.loads(JsonFormatter().format_summary(summary))
        assert data["files"][0]["parse_error"].startswith("Could not parse ")
        assert data["files"][0]["issues"] == []
        assert data["summary"]["unparsed"] == 1
        assert data["summary"]["errors"] == 0

    def test_parse_into_wording_is_unchanged(self, tmp_path: Path) -> None:
        bad = _raw(tmp_path, "bad.ttl", BAD_TTL)
        with pytest.raises(Refusal) as caught:
            parse_into(Graph(), bad, "turtle")
        assert caught.value.message.startswith(f"Could not parse {bad} as turtle: at line 2")

    def test_help_says_so(self) -> None:
        result = _run("lint", "--help")
        flat = " ".join(result.output.split())
        assert "'never' exits 0 unless a file could not be parsed" in flat
        assert "2 - Input refused, a file could not be parsed, or run failed" in flat


# -----------------------------------------------------------------------------
# LINT_GUIDE.md's examples run as written
# -----------------------------------------------------------------------------


class TestGuideExamples:
    def test_deprecated_terms_and_parse_errors_print_what_the_guide_shows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tests.test_own_terms import GUIDE, _blocks

        guide = GUIDE.read_text(encoding="utf-8")
        deprecated = guide[
            guide.index("### Deprecated terms") : guide.index("## Enabling and Disabling Rules")
        ]
        parse = guide[guide.index("### Parse Errors") :]

        (catalogue,) = _blocks(deprecated, "turtle")
        (broken,) = _blocks(parse, "turtle")
        (tmp_path / "catalogue.ttl").write_text(catalogue)
        (tmp_path / "broken.ttl").write_text(broken)
        monkeypatch.chdir(tmp_path)

        for section, code in ((deprecated, 1), (parse, 2)):
            (command,) = _blocks(section, "bash")
            (shown,) = _blocks(section, "text")
            argv = command.strip().split()
            assert argv[0] == "rdf-construct"
            result = _run(*argv[1:])
            assert result.exit_code == code, command
            assert result.output.strip() == shown.strip(), command
