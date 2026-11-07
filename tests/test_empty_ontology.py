"""What counts as metadata for lint's `empty-ontology` (#505).

A header has metadata when it carries any triple other than `rdf:type` and `owl:imports`
(`lint.rules.HEADER_STRUCTURE`): every OWL 2 ontology annotation, the `prov:wasDerivedFrom` stamp
the tool writes, and `owl:versionIRI`. A header with nothing but its type and imports is still a
finding. A blank-node header is skipped.

Since P35 (#504) a named `merge` writes a header carrying only the stamp, and `order`'s filtered
extract of a source whose header has only `owl:versionIRI` is stamped the same way (P13, #90);
both failed `lint`. A headerless source's `split` modules (#517) and an untitled `puml2rdf`
diagram (#518) still get bare or imports-only headers, which stay findings.

Findings are asserted by rule and term IRI. `lint --format json` crashes (#201), so the IRIs come
from `LintEngine`, and the CLI is asserted for exit codes. Every fixture is written into `tmp_path`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DC, DCTERMS, OWL, PROV, RDF, RDFS, SKOS, XSD

from rdf_construct.cli import cli
from rdf_construct.core import preserve_literal_forms
from rdf_construct.lint import LintEngine
from rdf_construct.lint.engine import LintConfig
from rdf_construct.lint.rules import HEADER_STRUCTURE, Severity
from tests.test_cli_smoke import assert_no_crash

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "examples"
FIXTURES = ROOT / "tests" / "fixtures"

RULE = "empty-ontology"
ONT = URIRef("http://example.org/ont")
EX = "http://example.org/"
VANN_PREFIX = URIRef("http://purl.org/vocab/vann/preferredNamespacePrefix")

MESSAGE = (
    "owl:Ontology has no metadata: no annotation "
    "(label, comment, title, provenance, …) and no owl:versionIRI"
)

# The bare headers in the corpus: they say nothing, and stay findings.
BARE_CORPUS = [
    "examples/lint/example_lint_problematic.ttl",
    "tests/fixtures/shacl/blank_ranges.ttl",
    "tests/fixtures/shacl/building.ttl",
    "tests/fixtures/shacl/colliding.ttl",
    "tests/fixtures/shacl/enumerations.ttl",
    "tests/fixtures/shacl/hierarchy.ttl",
    "tests/fixtures/shacl/kinds.ttl",
    "tests/fixtures/shacl/org.ttl",
    "tests/fixtures/shacl/substr.ttl",
    "tests/fixtures/shacl/two_cats.ttl",
    "tests/fixtures/shacl/urn.ttl",
    "tests/fixtures/split/residue/prov_typed.ttl",
]

# One of each kind of metadata a header can carry, and an object for it.
COUNTED: list[tuple[URIRef, object]] = [
    (RDFS.label, Literal("Ontology", lang="en")),
    (RDFS.comment, Literal("What it is.")),
    (RDFS.seeAlso, URIRef(EX + "doc")),
    (OWL.versionInfo, Literal("1.0.0")),
    (OWL.versionIRI, URIRef(EX + "ont/1.0.0")),
    (OWL.priorVersion, URIRef(EX + "ont/0.9.0")),
    (OWL.backwardCompatibleWith, URIRef(EX + "ont/0.9.0")),
    (OWL.incompatibleWith, URIRef(EX + "ont/0.1.0")),
    (OWL.deprecated, Literal(True)),
    (DCTERMS.title, Literal("Ontology")),
    (DC.creator, Literal("A. Person")),
    (SKOS.prefLabel, Literal("Ontology")),
    (VANN_PREFIX, Literal("ex")),
    (PROV.wasDerivedFrom, URIRef(EX + "source/1.0.0")),
]


def _run(*argv: object) -> Result:
    result = CliRunner().invoke(cli, [str(a) for a in argv])
    assert_no_crash(result)
    return result


def _issues(path: Path) -> list[tuple[str, str, Severity]]:
    """Every finding as (rule, term IRI, severity), with the CLI's default config."""
    result = LintEngine(LintConfig()).lint_file(path)
    return [(i.rule_id, str(i.entity), i.severity) for i in result.issues if i.entity is not None]


def _flagged(path: Path) -> set[str]:
    """The headers `empty-ontology` fired on."""
    return {entity for rule, entity, _ in _issues(path) if rule == RULE}


def _headers(path: Path) -> set[str]:
    """Every named `owl:Ontology` in a file."""
    graph = Graph()
    with preserve_literal_forms():
        graph.parse(path, format="turtle")
    return {str(s) for s in graph.subjects(RDF.type, OWL.Ontology) if isinstance(s, URIRef)}


def _header_file(tmp_path: Path, *triples: tuple[object, URIRef, object]) -> Path:
    """A file whose graph is exactly ``triples``."""
    graph = Graph()
    for triple in triples:
        graph.add(triple)  # type: ignore[arg-type]
    path = tmp_path / "header.ttl"
    graph.serialize(path, format="turtle")
    return path


def _lint_exit(path: Path) -> int:
    """`lint`'s exit code with only this rule running."""
    return _run("lint", path, "--enable", RULE).exit_code


class TestWhatCounts:
    """Any triple but `rdf:type` and `owl:imports` is metadata; `owl:versionIRI` still counts."""

    @pytest.mark.parametrize(("predicate", "value"), COUNTED, ids=lambda v: str(v))
    def test_each_kind_of_metadata_counts_alone(
        self, tmp_path: Path, predicate: URIRef, value: object
    ) -> None:
        path = _header_file(tmp_path, (ONT, RDF.type, OWL.Ontology), (ONT, predicate, value))
        assert _flagged(path) == set()
        assert _lint_exit(path) == 0

    @pytest.mark.parametrize("predicate", sorted(HEADER_STRUCTURE), ids=str)
    def test_structure_alone_is_not_metadata(self, tmp_path: Path, predicate: URIRef) -> None:
        value = OWL.NamedIndividual if predicate == RDF.type else URIRef(EX + "imported")
        path = _header_file(tmp_path, (ONT, RDF.type, OWL.Ontology), (ONT, predicate, value))
        assert _flagged(path) == {str(ONT)}
        assert _lint_exit(path) == 1

    def test_header_structure_is_exactly_type_and_imports(self) -> None:
        assert frozenset({RDF.type, OWL.imports}) == HEADER_STRUCTURE

    def test_a_bare_header_is_a_finding(self, tmp_path: Path) -> None:
        path = _header_file(tmp_path, (ONT, RDF.type, OWL.Ontology))
        assert _flagged(path) == {str(ONT)}
        assert _lint_exit(path) == 1

    @pytest.mark.parametrize("name", BARE_CORPUS)
    def test_the_bare_corpus_headers_stay_findings(self, name: str) -> None:
        path = ROOT / name
        assert _flagged(path) == _headers(path) != set()

    def test_a_dcterms_title_only_header_has_metadata(self) -> None:
        path = FIXTURES / "split" / "residue" / "borrowed.ttl"
        assert _headers(path) != set()
        assert _flagged(path) == set()


class TestEdgeShapes:
    """#505 Q6."""

    def test_a_blank_node_header_is_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "blank.ttl"
        path.write_text("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n[] a owl:Ontology .\n")
        assert _flagged(path) == set()
        assert _lint_exit(path) == 0

    def test_a_deprecated_bare_header_is_a_finding_demoted_to_info(self, tmp_path: Path) -> None:
        # Punned with owl:DeprecatedClass: a second rdf:type is still not metadata, and P24
        # (#513) demotes a finding on a deprecated term to info.
        path = _header_file(
            tmp_path, (ONT, RDF.type, OWL.Ontology), (ONT, RDF.type, OWL.DeprecatedClass)
        )
        assert [(r, e, s) for r, e, s in _issues(path) if r == RULE] == [
            (RULE, str(ONT), Severity.INFO)
        ]
        assert _lint_exit(path) == 0

    def test_two_headers_are_judged_separately(self, tmp_path: Path) -> None:
        other = URIRef(EX + "other")
        path = _header_file(
            tmp_path,
            (ONT, RDF.type, OWL.Ontology),
            (ONT, RDFS.label, Literal("Labelled")),
            (other, RDF.type, OWL.Ontology),
        )
        assert _flagged(path) == {str(other)}

    def test_two_bare_headers_are_both_findings(self, tmp_path: Path) -> None:
        other = URIRef(EX + "other")
        path = _header_file(
            tmp_path, (ONT, RDF.type, OWL.Ontology), (other, RDF.type, OWL.Ontology)
        )
        assert _flagged(path) == {str(ONT), str(other)}

    @pytest.mark.parametrize(
        "label",
        [Literal(""), Literal("Ontologie", lang="fr"), Literal("x", datatype=XSD.string)],
        ids=["empty", "language-tagged", "typed"],
    )
    def test_any_label_counts(self, tmp_path: Path, label: Literal) -> None:
        path = _header_file(tmp_path, (ONT, RDF.type, OWL.Ontology), (ONT, RDFS.label, label))
        assert _flagged(path) == set()

    def test_an_ies_style_header_without_rdfs_label_has_metadata(self, tmp_path: Path) -> None:
        path = _header_file(
            tmp_path,
            (ONT, RDF.type, OWL.Ontology),
            (ONT, DCTERMS.title, Literal("IES Common")),
            (ONT, DCTERMS.description, Literal("The common core.")),
            (ONT, VANN_PREFIX, Literal("ies")),
            (ONT, OWL.imports, URIRef(EX + "imported")),
        )
        assert _flagged(path) == set()


class TestWhatTheToolWrites:
    """The headers `merge`, `order`, `split` and `puml2rdf` write, linted."""

    def test_a_named_merge_lints_clean_of_empty_ontology(self, tmp_path: Path) -> None:
        out = tmp_path / "merged.ttl"
        merged = _run(
            "merge",
            EXAMPLES / "merge" / "merge_core.ttl",
            EXAMPLES / "merge" / "merge_extension.ttl",
            "--ontology-iri",
            "http://example.org/merged",
            "-o",
            out,
        )
        assert merged.exit_code == 0, merged.output
        assert _headers(out) == {"http://example.org/merged"}
        assert _flagged(out) == set()
        # The migration note's lead: name the merge, and the output passes lint.
        assert _run("lint", out).exit_code == 0

    @pytest.fixture
    def version_iri_only(self, tmp_path: Path) -> Path:
        """`examples/order/library.ttl`, its header cut down to `owl:versionIRI`."""
        text = (EXAMPLES / "order" / "library.ttl").read_text()
        for line in (
            '    rdfs:label "Library Ontology"@en ;\n',
            '    rdfs:comment "Worked example for the rdf-construct ordering guide."@en ;\n',
            '    owl:versionInfo "1.0.0" .\n',
        ):
            assert line in text
            text = text.replace(line, "")
        text = text.replace(
            "owl:versionIRI <http://example.org/library/1.0.0> ;",
            "owl:versionIRI <http://example.org/library/1.0.0> .",
        )
        path = tmp_path / "viri.ttl"
        path.write_text(text)
        assert _flagged(path) == set()
        return path

    def test_an_order_extract_of_a_version_iri_only_header(
        self, tmp_path: Path, version_iri_only: Path
    ) -> None:
        # P13 (#90) removes owl:versionIRI from a filtered extract and stamps it instead.
        config = tmp_path / "classes.yml"
        config.write_text(
            "defaults:\n  unclaimed: ignore\nprofiles:\n  classes:\n    sections:\n"
            "      - header: {}\n      - classes: {select: classes, sort: alpha}\n"
        )
        outdir = tmp_path / "ordered"
        ordered = _run("order", version_iri_only, config, "-o", outdir)
        assert ordered.exit_code == 0, ordered.output
        extract = outdir / "viri-classes.ttl"
        assert _headers(extract) == {"http://example.org/library"}
        assert _flagged(extract) == set()

    def test_a_named_merge_over_a_version_iri_only_header(
        self, tmp_path: Path, version_iri_only: Path
    ) -> None:
        out = tmp_path / "merged.ttl"
        merged = _run(
            "merge",
            version_iri_only,
            EXAMPLES / "merge" / "merge_extension.ttl",
            "--ontology-iri",
            "http://example.org/m2",
            "-o",
            out,
        )
        assert merged.exit_code == 0, merged.output
        assert _flagged(out) == set()

    @pytest.mark.parametrize(
        ("source", "modules"),
        [
            ("ies/ies-common.ttl", {"ies.ttl", "unmatched.ttl"}),
            ("ies/ies-env-building.ttl", {"building.ttl", "env.ttl"}),
        ],
    )
    def test_a_headed_sources_split_modules_are_stamped_and_pass(
        self, tmp_path: Path, source: str, modules: set[str]
    ) -> None:
        outdir = tmp_path / "modules"
        _run("split", FIXTURES / source, "--by-namespace", "-o", outdir)
        for name in sorted(modules):
            module = outdir / name
            assert _headers(module) != set(), name
            assert _flagged(module) == set(), name

    def test_a_headerless_sources_split_modules_stay_findings(self, tmp_path: Path) -> None:
        # Bare (ex.ttl) or owl:imports only (org.ttl, building.ttl): #517.
        outdir = tmp_path / "modules"
        _run("split", EXAMPLES / "split" / "split_monolith.ttl", "--by-namespace", "-o", outdir)
        for name in ("ex.ttl", "org.ttl", "building.ttl"):
            module = outdir / name
            assert _flagged(module) == _headers(module) != set(), name

    def test_an_untitled_puml2rdf_diagram_stays_a_finding(self, tmp_path: Path) -> None:
        # A bare header: #518.
        out = tmp_path / "diagram.ttl"
        converted = _run("puml2rdf", FIXTURES / "smoke" / "diagram.puml", "-o", out)
        assert converted.exit_code == 0, converted.output
        assert _flagged(out) == _headers(out) != set()

    def test_a_named_merge_of_headerless_sources_stays_a_finding(self, tmp_path: Path) -> None:
        # No source has a header, so nothing is stamped and the header is bare: #520.
        sources = []
        for name in ("a", "b"):
            path = tmp_path / f"{name}.ttl"
            path.write_text(
                "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
                "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
                f'<{EX}{name.upper()}> a owl:Class ; rdfs:label "{name}" .\n'
            )
            sources.append(path)
        out = tmp_path / "merged.ttl"
        merged = _run("merge", *sources, "--ontology-iri", EX + "x", "-o", out)
        assert merged.exit_code == 0, merged.output
        assert _flagged(out) == _headers(out) == {EX + "x"}


class TestWording:
    """#505 Q5: one wording for the rule."""

    def test_the_message(self, tmp_path: Path) -> None:
        path = _header_file(tmp_path, (ONT, RDF.type, OWL.Ontology))
        messages = {
            i.message for i in LintEngine(LintConfig()).lint_file(path).issues if i.rule_id == RULE
        }
        assert messages == {MESSAGE}

    def test_the_list_rules_description(self) -> None:
        result = _run("lint", "--list-rules")
        assert result.exit_code == 0
        assert (
            " ".join(result.output.split()).count(
                "empty-ontology: error - owl:Ontology header says nothing about the ontology "
                "(no annotation or owl:versionIRI)"
            )
            == 1
        )


class TestGuides:
    """The guides' examples and workaround, run as written."""

    def test_lint_guides_ontology_headers_example(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tests.test_own_terms import GUIDE, _blocks

        guide = GUIDE.read_text(encoding="utf-8")
        section = guide[guide.index("### Ontology headers") : guide.index("### Deprecated terms")]
        (turtle,) = _blocks(section, "turtle")
        (command,) = _blocks(section, "bash")
        (shown,) = _blocks(section, "text")
        (tmp_path / "headers.ttl").write_text(turtle)
        monkeypatch.chdir(tmp_path)

        argv = command.strip().split()
        assert argv[0] == "rdf-construct"
        result = _run(*argv[1:])
        assert result.exit_code == 1, command
        assert result.output.strip() == shown.strip(), command
        assert _flagged(tmp_path / "headers.ttl") == {"https://example.org/catalogue-stub"}

    def test_the_split_guides_workaround_clears_a_headerless_sources_modules(
        self, tmp_path: Path
    ) -> None:
        guide = (ROOT / "docs" / "user_guides" / "MERGE_SPLIT_GUIDE.md").read_text()
        row = next(line for line in guide.splitlines() if "| #517 |" in line)
        (snippet,) = (s for s in row.split("`") if s.startswith("severity:"))
        assert snippet == "severity: {empty-ontology: warning}"
        config = tmp_path / ".rdf-lint.yml"
        config.write_text(snippet + "\n")

        outdir = tmp_path / "modules"
        _run("split", EXAMPLES / "split" / "split_monolith.ttl", "--by-namespace", "-o", outdir)
        module = outdir / "ex.ttl"
        assert _run("lint", module, "--enable", RULE).exit_code == 1
        assert _run("lint", module, "--enable", RULE, "-c", config).exit_code == 0
