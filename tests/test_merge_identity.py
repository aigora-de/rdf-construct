"""``merge`` writes at most one ontology header (#171).

Named by ``--ontology-iri`` or ``namespaces.base`` (the flag wins), a merge gets one header and a
``prov:wasDerivedFrom`` per source; unnamed, it gets none and warns with the command that names
it. Sources that share one header keep it. Every other source header is demoted: it loses its
``owl:Ontology`` type, ``owl:versionIRI`` and the predicates only an ontology takes, and keeps
the rest, a punned class declaration included.
"""

from __future__ import annotations

import re
import shlex
import shutil
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner, Result
from rdflib import Graph, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, OWL, PROV, RDF

from rdf_construct.cli import cli
from rdf_construct.core import preserve_literal_forms
from rdf_construct.merge import create_default_config, merge_files
from tests.test_cli_smoke import assert_no_crash, assert_wrote_nothing, snapshot

FIXTURES = Path(__file__).parent / "fixtures" / "merge" / "identity"
IES = Path(__file__).parent / "fixtures" / "ies"
A, B = FIXTURES / "a.ttl", FIXTURES / "b.ttl"
PLAIN, BLANK = FIXTURES / "plain.ttl", FIXTURES / "blank.ttl"

ONT_A = URIRef("http://example.org/a")
ONT_B = URIRef("http://example.org/b")
MERGED = URIRef("http://example.org/merged")


def _run(*argv: object) -> Result:
    result = CliRunner().invoke(cli, ["merge", *[str(a) for a in argv]])
    assert_no_crash(result)
    return result


def _read(path: Path) -> Graph:
    with preserve_literal_forms():
        return Graph().parse(path, format="turtle")


def _headers(graph: Graph) -> set:
    return set(graph.subjects(RDF.type, OWL.Ontology))


def _config(tmp_path: Path, **namespaces: object) -> Path:
    path = tmp_path / "merge.yml"
    data: dict[str, object] = {"sources": [{"path": str(A)}, {"path": str(B)}]}
    if namespaces:
        data["namespaces"] = namespaces
    path.write_text(yaml.safe_dump(data))
    return path


def _assert_demoted(graph: Graph) -> None:
    """A's and B's headers are demoted, precisely."""
    for header in (ONT_A, ONT_B):
        assert (header, RDF.type, OWL.Ontology) not in graph
        assert (header, OWL.versionIRI, None) not in graph
        for predicate in (
            OWL.imports,
            OWL.priorVersion,
            OWL.backwardCompatibleWith,
            OWL.incompatibleWith,
        ):
            assert (header, predicate, None) not in graph
    # What describes the source stays on its own IRI, the punned class declaration included
    assert (ONT_A, RDF.type, OWL.Class) in graph
    assert (ONT_A, OWL.versionInfo, Literal("1.0.0")) in graph
    assert (ONT_A, DCTERMS.title, Literal("Ontology A", lang="en")) in graph
    assert (ONT_B, DCTERMS.title, Literal("Ontology B", lang="en")) in graph


class TestNamed:
    def test_by_the_flag(self, tmp_path):
        out = tmp_path / "m.ttl"
        result = _run(A, B, "-o", out, "--ontology-iri", MERGED)
        assert result.exit_code == 0, result.output
        graph = _read(out)
        assert _headers(graph) == {MERGED}
        assert (MERGED, OWL.versionIRI, None) not in graph
        assert set(graph.objects(MERGED, PROV.wasDerivedFrom)) == {
            URIRef("http://example.org/a/1.0.0"),
            URIRef("http://example.org/b/2.0.0"),
        }
        # Imports move to the merged header, except of what the merge contains
        assert set(graph.objects(MERGED, OWL.imports)) == {
            URIRef("http://example.org/common"),
            URIRef("http://example.org/other"),
        }
        _assert_demoted(graph)
        assert f"Ontology: <{MERGED}> (from: --ontology-iri)" in result.output
        assert "No ontology header written" not in result.stderr

    def test_a_source_description_of_the_stamp_is_kept(self, tmp_path):
        out = tmp_path / "m.ttl"
        _run(A, B, "-o", out, "--ontology-iri", MERGED)
        graph = _read(out)
        types = set(graph.objects(PROV.wasDerivedFrom, RDF.type))
        assert types == {OWL.ObjectProperty}

    def test_by_namespaces_base(self, tmp_path):
        out = tmp_path / "m.ttl"
        result = _run("-c", _config(tmp_path, base=str(MERGED)), "-o", out)
        assert result.exit_code == 0, result.output
        assert _headers(_read(out)) == {MERGED}
        assert "(from: namespaces.base)" in result.output

    def test_base_is_used_as_given(self, tmp_path):
        out = tmp_path / "m.ttl"
        _run("-c", _config(tmp_path, base="http://example.org/merged#"), "-o", out)
        assert _headers(_read(out)) == {URIRef("http://example.org/merged#")}

    def test_the_flag_overrides_the_config(self, tmp_path):
        out = tmp_path / "m.ttl"
        config = _config(tmp_path, base="http://example.org/from-config")
        result = _run("-c", config, "-o", out, "--ontology-iri", MERGED)
        assert result.exit_code == 0, result.output
        assert _headers(_read(out)) == {MERGED}

    @pytest.mark.parametrize("strategy", ["preserve", "merge"])
    def test_imports_are_carried_unless_removed(self, tmp_path, strategy):
        out = tmp_path / "m.ttl"
        _run(A, B, "-o", out, "--ontology-iri", MERGED, "--imports", strategy)
        assert len(set(_read(out).objects(MERGED, OWL.imports))) == 2

    def test_imports_remove_carries_none(self, tmp_path):
        out = tmp_path / "m.ttl"
        _run(A, B, "-o", out, "--ontology-iri", MERGED, "--imports", "remove")
        graph = _read(out)
        assert (None, OWL.imports, None) not in graph
        assert _headers(graph) == {MERGED}

    def test_a_source_without_a_header_is_not_stamped(self, tmp_path):
        out = tmp_path / "m.ttl"
        result = _run(A, PLAIN, BLANK, "-o", out, "--ontology-iri", MERGED)
        assert result.exit_code == 0, result.output
        graph = _read(out)
        assert set(graph.objects(MERGED, PROV.wasDerivedFrom)) == {
            URIRef("http://example.org/a/1.0.0")
        }
        assert "Not recorded as derived from: plain.ttl (no ontology header)" in result.output
        assert "blank.ttl (a blank-node header, which nothing names)" in result.output
        assert _headers(graph) == {MERGED}

    def test_stamp_names_the_source_as_read_before_a_remap(self, tmp_path):
        config = tmp_path / "merge.yml"
        config.write_text(
            yaml.safe_dump(
                {
                    "sources": [
                        {
                            "path": str(A),
                            "namespace_remap": {"http://example.org/": "http://new.example.org/"},
                        },
                        {"path": str(B)},
                    ],
                    "namespaces": {"base": str(MERGED)},
                }
            )
        )
        out = tmp_path / "m.ttl"
        result = _run("-c", config, "-o", out)
        assert result.exit_code == 0, result.output
        graph = _read(out)
        assert URIRef("http://example.org/a/1.0.0") in set(
            graph.objects(MERGED, PROV.wasDerivedFrom)
        )
        assert URIRef("http://new.example.org/a/1.0.0") not in set(graph.all_nodes())

    def test_a_source_ontology_iri_is_accepted_with_a_note(self, tmp_path):
        out = tmp_path / "m.ttl"
        result = _run(A, B, "-o", out, "--ontology-iri", ONT_A)
        assert result.exit_code == 0, result.output
        graph = _read(out)
        assert _headers(graph) == {ONT_A}
        assert (ONT_A, OWL.versionIRI, None) not in graph
        assert (ONT_A, RDF.type, OWL.Class) in graph
        assert "is the ontology IRI of a.ttl" in result.stderr

    def test_a_source_term_is_accepted_with_a_note(self, tmp_path):
        out = tmp_path / "m.ttl"
        term = "http://example.org/a#Thing"
        result = _run(A, B, "-o", out, "--ontology-iri", term)
        assert result.exit_code == 0, result.output
        graph = _read(out)
        assert _headers(graph) == {URIRef(term)}
        assert (URIRef(term), RDF.type, OWL.Class) in graph
        assert "is already a term in the sources" in result.stderr

    def test_a_renamed_prov_prefix_is_noted(self, tmp_path):
        other = tmp_path / "other.ttl"
        other.write_text(
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
            "@prefix prov: <http://example.org/not-prov#> .\n"
            "<http://example.org/p> a owl:Ontology .\n"
            "prov:Thing a owl:Class .\n"
        )
        out = tmp_path / "m.ttl"
        result = _run(A, other, "-o", out, "--ontology-iri", MERGED)
        assert result.exit_code == 0, result.output
        assert 'written as "prov1:"' in result.stderr

    def test_the_library_names_it_too(self, tmp_path):
        out = tmp_path / "m.ttl"
        result = merge_files([A, B], out, ontology_iri=str(MERGED))
        assert result.success
        assert result.identity is not None
        assert result.identity.ontology == MERGED
        assert [str(h) for h, _ in result.identity.demoted] == [str(ONT_A), str(ONT_B)]
        assert _headers(_read(out)) == {MERGED}


class TestUnnamed:
    def test_no_header_and_a_warning(self, tmp_path):
        out = tmp_path / "m.ttl"
        result = _run(A, B, "-o", out)
        assert result.exit_code == 0, result.output
        graph = _read(out)
        assert _headers(graph) == set()
        assert (None, OWL.imports, None) not in graph
        assert (None, PROV.wasDerivedFrom, None) not in graph
        _assert_demoted(graph)
        assert "No ontology header written: 2 source header(s) demoted" in result.stderr
        assert f"Demoted: <{ONT_A}> (a.ttl)" in result.output
        assert "<http://example.org/common>" in result.stderr

    def test_the_command_shown_names_it(self, tmp_path):
        out = tmp_path / "m.ttl"
        result = _run(A, B, "-o", out)
        lines = result.stderr.splitlines()
        shown = lines[lines.index(next(x for x in lines if "To name it" in x)) + 1].strip()
        argv = shlex.split(shown.replace(" IRI", f" {MERGED}"))
        assert argv[:2] == ["rdf-construct", "merge"]
        out.unlink()
        rerun = CliRunner().invoke(cli, argv[1:])
        assert_no_crash(rerun)
        assert rerun.exit_code == 0, rerun.output
        assert _headers(_read(out)) == {MERGED}

    def test_a_config_run_also_points_at_namespaces_base(self, tmp_path):
        config = _config(tmp_path)
        result = _run("-c", config, "-o", tmp_path / "m.ttl")
        assert result.exit_code == 0, result.output
        assert f"or set namespaces.base: IRI in {config}" in result.stderr

    def test_dry_run_exits_the_same_and_warns_the_same(self, tmp_path):
        out = tmp_path / "m.ttl"
        result = _run(A, B, "-o", out, "--dry-run")
        assert result.exit_code == 0, result.output
        assert "No ontology header written" in result.stderr
        assert not out.exists()

    def test_one_headed_source_with_a_headerless_one(self, tmp_path):
        out = tmp_path / "m.ttl"
        result = _run(A, PLAIN, "-o", out)
        assert result.exit_code == 0, result.output
        assert _headers(_read(out)) == set()
        assert "1 source header(s) demoted" in result.stderr

    def test_a_blank_node_header_is_named_by_its_file(self, tmp_path):
        out = tmp_path / "m.ttl"
        result = _run(A, BLANK, "-o", out)
        assert result.exit_code == 0, result.output
        assert "Demoted: a blank-node header in blank.ttl" in result.output
        assert _headers(_read(out)) == set()

    def test_one_file_with_two_headers(self, tmp_path):
        out = tmp_path / "m.ttl"
        result = _run(IES / "ies-env-building.ttl", "-o", out)
        assert result.exit_code == 0, result.output
        assert _headers(_read(out)) == set()
        assert "2 source header(s) demoted" in result.stderr


class TestKept:
    @pytest.mark.parametrize("copies", [1, 2, 3])
    def test_one_identity_is_left_as_it_is(self, tmp_path, copies):
        out = tmp_path / "m.ttl"
        result = _run(*([A] * copies), "-o", out)
        assert result.exit_code == 0, result.output
        assert isomorphic(_read(out), _read(A))
        assert "No ontology header written" not in result.stderr
        assert "Ontology: kept" in result.output

    def test_a_different_version_is_not_one_identity(self, tmp_path):
        later = tmp_path / "a2.ttl"
        later.write_text(A.read_text().replace("a/1.0.0", "a/1.1.0"))
        out = tmp_path / "m.ttl"
        result = _run(A, later, "-o", out)
        assert result.exit_code == 0, result.output
        assert _headers(_read(out)) == set()


class TestRefused:
    @pytest.mark.parametrize("dry_run", [False, True])
    @pytest.mark.parametrize(
        ("value", "says"),
        [
            ("", "it is empty"),
            ("   ", "it is empty"),
            ("merged", "no scheme"),
            ("http://example.org/a b", "which an IRI cannot"),
            ("<http://example.org/m>", "which an IRI cannot"),
            ("a:Merged", "reads as a prefixed name"),
            ("owl:Merged", "reads as a prefixed name"),
        ],
    )
    def test_refused_and_nothing_written(self, tmp_path, value, says, dry_run):
        argv = [str(A), str(B), "-o", str(tmp_path / "m.ttl"), "--ontology-iri", value]
        if dry_run:
            argv.append("--dry-run")
        before = snapshot(argv, tmp_path)
        result = _run(*argv)
        assert result.exit_code == 2, result.output
        assert says in result.output
        assert_wrote_nothing(before, snapshot(argv, tmp_path))

    def test_a_bad_base_in_the_config_is_refused(self, tmp_path):
        argv = ["-c", str(_config(tmp_path, base="merged")), "-o", str(tmp_path / "m.ttl")]
        before = snapshot(argv, tmp_path)
        result = _run(*argv)
        assert result.exit_code == 2, result.output
        assert "namespaces.base is not an ontology IRI" in result.output
        assert_wrote_nothing(before, snapshot(argv, tmp_path))


def test_the_init_template_shows_an_ontology_iri():
    template = create_default_config()
    assert '# base: "http://example.org/merged"\n' in template
    assert "merged#" not in template


class TestTheGuide:
    """The guide's Ontology Identity commands run verbatim and print what it shows."""

    GUIDE = Path(__file__).parent.parent / "docs" / "user_guides" / "MERGE_SPLIT_GUIDE.md"

    def _blocks(self) -> list[str]:
        guide = self.GUIDE.read_text()
        start = guide.index("### Ontology Identity")
        section = guide[start : guide.index("### Blank Nodes", start)]
        return re.findall(r"```(?:bash|turtle)?\n(.*?)```", section, re.S)

    def _run_shown(self, command: str, tmp_path: Path, monkeypatch) -> Result:
        examples = tmp_path / "examples" / "merge"
        examples.mkdir(parents=True)
        for name in ("merge_core.ttl", "merge_extension.ttl"):
            shutil.copy(Path(__file__).parent.parent / "examples" / "merge" / name, examples)
        monkeypatch.chdir(tmp_path)
        argv = shlex.split(command)
        assert argv[0] == "rdf-construct"
        result = CliRunner().invoke(cli, argv[1:])
        assert_no_crash(result)
        return result

    def test_the_unnamed_merge_prints_the_warning_shown(self, tmp_path, monkeypatch):
        command, shown, _, _ = self._blocks()
        result = self._run_shown(command, tmp_path, monkeypatch)
        assert result.exit_code == 0, result.output
        assert result.stderr == shown

    def test_the_named_merge_writes_the_header_shown(self, tmp_path, monkeypatch):
        _, _, command, shown = self._blocks()
        result = self._run_shown(command, tmp_path, monkeypatch)
        assert result.exit_code == 0, result.output
        prefixes = (
            "@prefix ex: <http://example.org/> .\n@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        )
        prefixes += "@prefix prov: <http://www.w3.org/ns/prov#> .\n"
        expected = Graph().parse(data=prefixes + shown, format="turtle")
        written = _read(tmp_path / "merged.ttl")
        merged = URIRef("http://example.org/merged")
        assert set(written.triples((merged, None, None))) == set(expected)


def test_the_example_config_runs_and_names_the_merge(tmp_path, monkeypatch):
    root = Path(__file__).parent.parent
    monkeypatch.chdir(root)
    out = tmp_path / "m.ttl"
    result = _run("--config", "examples/merge/merge_config.yml", "-o", out)
    assert result.exit_code == 0, result.output
    assert _headers(_read(out)) == {MERGED}
