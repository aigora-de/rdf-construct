"""`refactor rename` refuses to merge two entities by accident (#185).

A collision is a rename target that already has triples of its own as a subject and is not
itself renamed away, two renames onto one target, or an axiom that keeps two things apart
made reflexive. Each is refused at exit 2 with nothing written, unless ``--merge-entities``
(or the config's ``merge_entities: true``) lets it through. A target that is only referenced
is renamed onto, and the run says so.

The fixtures are built so a wrong answer is visible: a merge leaves one class with two labels,
and a swap done wrong leaves one class instead of two.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDFS

from rdf_construct.cli import cli
from rdf_construct.core import preserve_literal_forms
from rdf_construct.refactor import (
    OntologyRenamer,
    RenameConfig,
    find_collisions,
    find_references,
    rename_file,
)
from tests.test_cli_smoke import assert_no_crash, assert_wrote_nothing, snapshot

REPO = Path(__file__).parent.parent
REFACTOR = REPO / "examples" / "refactor"
TYPOS = REFACTOR / "typos.ttl"
ANIMAL = REPO / "examples" / "animal_ontology.ttl"

EX = Namespace("http://example.org/")
ONT = Namespace("http://example.org/ont#")
OLD = Namespace("http://old.example/#")
NEW = Namespace("http://new.example/#")

PREFIXES = """\
@prefix ex: <http://example.org/> .
@prefix old: <http://old.example/#> .
@prefix new: <http://new.example/#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
"""

TWO_CLASSES = 'ex:A a owl:Class ; rdfs:label "A" .\nex:B a owl:Class ; rdfs:label "B" .\n'


def _ttl(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(PREFIXES + body)
    return path


def _yaml(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body)
    return path


def _invoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: tuple[object, ...]) -> Result:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["refactor", "rename", *map(str, args)])
    assert_no_crash(result)
    return result


def _refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *args: object) -> str:
    """Run a rename that must be refused: exit 2, nothing written. Returns its output."""
    argv = ["refactor", "rename", *map(str, args)]
    before = snapshot(argv, tmp_path)
    result = _invoke(tmp_path, monkeypatch, args)
    assert result.exit_code == 2, result.output
    assert_wrote_nothing(before, snapshot(argv, tmp_path))
    return result.output


def _ran(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *args: object) -> str:
    """Run a rename that must succeed at exit 0. Returns its output."""
    result = _invoke(tmp_path, monkeypatch, args)
    assert result.exit_code == 0, result.output
    return result.output


def _parse(path: Path) -> Graph:
    with preserve_literal_forms():
        return Graph().parse(path)


def _labels(graph: Graph, subject: URIRef) -> set[str]:
    return {str(o) for o in graph.objects(subject, RDFS.label)}


# ---------------------------------------------------------------------------
# Refused: the target already has triples of its own
# ---------------------------------------------------------------------------


def test_the_issue_reproducer_is_refused(tmp_path, monkeypatch):
    out = tmp_path / "collide.ttl"
    output = _refused(
        tmp_path, monkeypatch, TYPOS, "--from", ONT.Addres, "--to", ONT.Structure, "-o", out
    )
    assert "Error: Nothing was written:\n  1 rename would merge two entities:\n" in output
    assert f"<{ONT.Structure}> has 3 triples of its own in {TYPOS}" in output
    assert f"renaming <{ONT.Addres}> onto it merges them" in output


def test_the_refusal_says_what_to_do_next(tmp_path, monkeypatch):
    output = _refused(
        tmp_path, monkeypatch, TYPOS, "--from", ONT.Addres, "--to", ONT.Structure, "-o", "x.ttl"
    )
    assert "Pass --merge-entities to merge them deliberately." in output
    # Quoted for the shell: an IRI with a # in it would otherwise start a comment
    assert (
        f"rdf-construct refactor deprecate {TYPOS} --entity '{ONT.Addres}' "
        f"--replaced-by '{ONT.Structure}'"
    ) in output


def test_a_curie_target_is_checked_after_it_is_resolved(tmp_path, monkeypatch):
    """#182 ──► #185: an unexpanded `ex:` CURIE would never match the graph."""
    output = _refused(
        tmp_path, monkeypatch, TYPOS, "--from", "ex:Addres", "--to", "ex:Structure", "-o", "x.ttl"
    )
    assert f"<{ONT.Structure}> has 3 triples" in output


def test_the_post_write_case_is_refused(tmp_path, monkeypatch):
    """Formerly `test_post_write.py`'s `onto-existing-iri` row, a strict xfail against #185."""
    output = _refused(
        tmp_path,
        monkeypatch,
        ANIMAL,
        "--from",
        "http://example.org/animals#Animal",
        "--to",
        "http://example.org/animals#Bird",
        "-o",
        tmp_path / "renamed.ttl",
    )
    assert "<http://example.org/animals#Bird> has 4 triples of its own" in output


def test_a_namespace_rename_onto_names_that_exist_is_refused(tmp_path, monkeypatch):
    src = _ttl(
        tmp_path,
        "ns.ttl",
        'old:Thing a owl:Class ; rdfs:label "old" .\n'
        'new:Thing a owl:Class ; rdfs:label "new" .\n'
        "new:Other a owl:Class .\n",
    )
    output = _refused(
        tmp_path,
        monkeypatch,
        src,
        "--from-namespace",
        "http://old.example/#",
        "--to-namespace",
        "http://new.example/#",
        "-o",
        tmp_path / "out.ttl",
    )
    assert f"<{NEW.Thing}> has 2 triples of its own in {src}" in output
    assert f"renaming <{OLD.Thing}> onto it" in output
    assert str(NEW.Other) not in output


def test_a_chain_whose_last_target_exists_is_refused(tmp_path, monkeypatch):
    src = _ttl(tmp_path, "abc.ttl", TWO_CLASSES + 'ex:C a owl:Class ; rdfs:label "C" .\n')
    config = _yaml(
        tmp_path,
        "chain.yml",
        'rename:\n  entities:\n    "http://example.org/A": "http://example.org/B"\n'
        '    "http://example.org/B": "http://example.org/C"\n',
    )
    output = _refused(tmp_path, monkeypatch, src, "-c", config, "-o", tmp_path / "out.ttl")
    assert f"<{EX.C}> has 2 triples of its own" in output
    # B is renamed away, so renaming A onto it merges nothing
    assert f"<{EX.B}> has" not in output


def test_punning_is_refused_although_the_count_cannot_see_it(tmp_path, monkeypatch):
    """A class renamed onto an individual merges two descriptions and keeps 4 triples."""
    src = _ttl(
        tmp_path,
        "pun.ttl",
        'ex:Buiding a owl:Class ; rdfs:label "Buiding" .\n'
        'ex:Building a owl:NamedIndividual ; rdfs:label "a building" .\n',
    )
    output = _refused(
        tmp_path, monkeypatch, src, "--from", "ex:Buiding", "--to", "ex:Building", "-o", "o.ttl"
    )
    assert f"<{EX.Building}> has 2 triples of its own" in output


def test_a_rename_onto_the_ontology_iri_is_refused(tmp_path, monkeypatch):
    src = _ttl(
        tmp_path,
        "ont.ttl",
        '<http://example.org/> a owl:Ontology ; rdfs:label "Ont" .\n'
        'ex:A a owl:Class ; rdfs:label "A" .\n',
    )
    output = _refused(
        tmp_path, monkeypatch, src, "--from", EX.A, "--to", "http://example.org/", "-o", "o.ttl"
    )
    assert "<http://example.org/> has 2 triples of its own" in output


def test_a_target_described_in_another_source_is_refused(tmp_path, monkeypatch):
    """A split module set: neither file collides alone, but the set would describe it twice."""
    m1 = _ttl(tmp_path, "m1.ttl", "ex:Buiding a owl:Class ; rdfs:subClassOf ex:Thing .\n")
    m2 = _ttl(tmp_path, "m2.ttl", 'ex:Building a owl:Class ; rdfs:label "Building" .\n')
    output = _refused(
        tmp_path,
        monkeypatch,
        m1,
        m2,
        "--from",
        "ex:Buiding",
        "--to",
        "ex:Building",
        "-o",
        tmp_path / "out",
    )
    assert f"<{EX.Building}> has 2 triples of its own in {m2}" in output
    assert f"rdf-construct refactor deprecate {m1} --entity" in output


def test_a_target_described_in_two_sources_names_each(tmp_path, monkeypatch):
    m1 = _ttl(tmp_path, "m1.ttl", 'ex:A a owl:Class .\nex:B rdfs:label "B" .\n')
    m2 = _ttl(tmp_path, "m2.ttl", 'ex:B a owl:Class ; rdfs:comment "b" .\n')
    output = _refused(
        tmp_path, monkeypatch, m1, m2, "--from", "ex:A", "--to", "ex:B", "-o", tmp_path / "out"
    )
    assert f"<{EX.B}> has 3 triples of its own (1 in {m1}, 2 in {m2})" in output


def test_a_data_file_that_describes_the_target_is_refused(tmp_path, monkeypatch):
    src = _ttl(tmp_path, "ont.ttl", "ex:A a owl:Class .\n")
    data = _ttl(tmp_path, "data.ttl", 'ex:i1 a ex:A .\nex:B rdfs:label "data B" .\n')
    output = _refused(
        tmp_path,
        monkeypatch,
        src,
        "--from",
        "ex:A",
        "--to",
        "ex:B",
        "-o",
        tmp_path / "out.ttl",
        "--migrate-data",
        data,
        "--data-output",
        tmp_path / "data-out.ttl",
    )
    assert f"<{EX.B}> has 1 triple of its own in {data}" in output
    # The advice deprecates the term where the ontology declares it, never in the data
    assert f"rdf-construct refactor deprecate {src} --entity" in output


# ---------------------------------------------------------------------------
# Refused: two renames onto one target
# ---------------------------------------------------------------------------


def test_two_renames_onto_one_target_are_refused(tmp_path, monkeypatch):
    src = _ttl(tmp_path, "ab.ttl", "ex:A a owl:Class ; ex:n 1 .\nex:B a owl:Class ; ex:n 2 .\n")
    config = _yaml(
        tmp_path,
        "many.yml",
        'rename:\n  entities:\n    "http://example.org/A": "http://example.org/C"\n'
        '    "http://example.org/B": "http://example.org/C"\n',
    )
    output = _refused(tmp_path, monkeypatch, src, "-c", config, "-o", tmp_path / "out.ttl")
    assert f"<{EX.C}> is the target of both <{EX.A}> and <{EX.B}>, which become one" in output
    assert "deprecate SOURCE --entity OLD --replaced-by NEW" in output


def test_a_namespace_rule_and_an_entity_rename_onto_one_iri_are_refused(tmp_path, monkeypatch):
    src = _ttl(tmp_path, "xy.ttl", 'old:X a owl:Class ; rdfs:label "X" .\nold:Y a owl:Class .\n')
    config = _yaml(
        tmp_path,
        "mixed.yml",
        'rename:\n  namespaces:\n    "http://old.example/#": "http://new.example/#"\n'
        '  entities:\n    "http://old.example/#Y": "http://new.example/#X"\n',
    )
    output = _refused(tmp_path, monkeypatch, src, "-c", config, "-o", tmp_path / "out.ttl")
    assert f"<{NEW.X}> is the target of both <{OLD.X}> and <{OLD.Y}>" in output


# ---------------------------------------------------------------------------
# Refused: an axiom that keeps two things apart, made reflexive
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("predicate", "phrase"),
    [
        ("owl:disjointWith", "disjoint with"),
        ("owl:propertyDisjointWith", "disjoint with"),
        ("owl:complementOf", "the complement of"),
        ("owl:differentFrom", "different from"),
    ],
)
def test_a_contradiction_made_reflexive_is_refused(tmp_path, monkeypatch, predicate, phrase):
    src = _ttl(tmp_path, "refl.ttl", f"ex:Buiding {predicate} ex:Building .\n")
    output = _refused(
        tmp_path, monkeypatch, src, "--from", "ex:Buiding", "--to", "ex:Building", "-o", "o.ttl"
    )
    assert (
        f"<{EX.Buiding}> {predicate} <{EX.Building}> in {src}: the rename makes "
        f"<{EX.Building}> {phrase} itself."
    ) in output


# ---------------------------------------------------------------------------
# Refused at scale: a count line, then every target
# ---------------------------------------------------------------------------


def test_a_bulk_namespace_collision_lists_every_target(tmp_path, monkeypatch):
    body = "".join(f"old:C{i} a owl:Class .\nnew:C{i} a owl:Class .\n" for i in range(2000))
    src = _ttl(tmp_path, "bulk.ttl", body)
    output = _refused(
        tmp_path,
        monkeypatch,
        src,
        "--from-namespace",
        "http://old.example/#",
        "--to-namespace",
        "http://new.example/#",
        "-o",
        tmp_path / "out.ttl",
    )
    assert "2000 renames would each merge two entities:" in output
    assert output.count("has 1 triple of its own") == 2000


# ---------------------------------------------------------------------------
# Not collisions
# ---------------------------------------------------------------------------


def test_a_swap_keeps_two_classes(tmp_path, monkeypatch):
    src = _ttl(tmp_path, "ab.ttl", TWO_CLASSES)
    config = _yaml(
        tmp_path,
        "swap.yml",
        'rename:\n  entities:\n    "http://example.org/A": "http://example.org/B"\n'
        '    "http://example.org/B": "http://example.org/A"\n',
    )
    out = tmp_path / "out.ttl"
    _ran(tmp_path, monkeypatch, src, "-c", config, "-o", out)
    graph = _parse(out)
    assert _labels(graph, EX.A) == {"B"}
    assert _labels(graph, EX.B) == {"A"}


def test_a_chain_does_not_chain(tmp_path, monkeypatch):
    src = _ttl(tmp_path, "ab.ttl", TWO_CLASSES)
    config = _yaml(
        tmp_path,
        "chain.yml",
        'rename:\n  entities:\n    "http://example.org/A": "http://example.org/B"\n'
        '    "http://example.org/B": "http://example.org/C"\n',
    )
    out = tmp_path / "out.ttl"
    _ran(tmp_path, monkeypatch, src, "-c", config, "-o", out)
    graph = _parse(out)
    assert _labels(graph, EX.B) == {"A"}
    assert _labels(graph, EX.C) == {"B"}
    assert len(graph) == 4


def test_a_rename_onto_itself_is_not_refused(tmp_path, monkeypatch):
    """It merges nothing, so it is written; it renames nothing, so it exits 1 (#183)."""
    src = _ttl(tmp_path, "a.ttl", TWO_CLASSES)
    out = tmp_path / "out.ttl"
    result = _invoke(tmp_path, monkeypatch, (src, "--from", "ex:A", "--to", "ex:A", "-o", out))
    assert result.exit_code == 1, result.output
    assert f"<{EX.A}> renames onto itself." in result.stderr
    assert len(_parse(out)) == 4


def test_a_mapping_whose_source_is_absent_is_not_refused(tmp_path, monkeypatch):
    """`renames.yml` over `legacy.ttl`: it defines `hasAddress` and `Address`, not the typos.

    Not a collision, so it is written; every mapping renames nothing, so it exits 1 (#183).
    """
    out = tmp_path / "out.ttl"
    result = _invoke(
        tmp_path,
        monkeypatch,
        (REFACTOR / "legacy.ttl", "-c", REFACTOR / "renames.yml", "-o", out),
    )
    assert result.exit_code == 1, result.output
    assert "4 renames matched nothing in any file of the run:" in result.stderr
    assert len(_parse(out)) == len(_parse(REFACTOR / "legacy.ttl"))


def test_the_guides_typo_workflow_runs_to_the_end(tmp_path, monkeypatch):
    """Step 3 of REFACTOR_GUIDE's typo workflow renames the already-fixed file again."""
    fixed = tmp_path / "fixed.ttl"
    rename = ("--from", ONT.Buiding, "--to", ONT.Building)
    _ran(tmp_path, monkeypatch, TYPOS, *rename, "-o", fixed)
    _ran(
        tmp_path,
        monkeypatch,
        fixed,
        *rename,
        "-o",
        tmp_path / "again.ttl",
        "--migrate-data",
        REFACTOR / "instances.ttl",
        "--data-output",
        tmp_path / "updated_instances.ttl",
    )
    assert (None, None, ONT.Buiding) not in _parse(tmp_path / "updated_instances.ttl")


def test_a_referenced_target_is_renamed_onto_and_reported(tmp_path, monkeypatch):
    src = _ttl(
        tmp_path,
        "ref.ttl",
        'ex:Buiding a owl:Class ; rdfs:label "Building" .\n'
        "ex:x ex:p ex:Building .\nex:y a ex:Building .\n",
    )
    out = tmp_path / "out.ttl"
    output = _ran(
        tmp_path, monkeypatch, src, "--from", "ex:Buiding", "--to", "ex:Building", "-o", out
    )
    assert (
        f"Note: <{EX.Building}> was already referenced 2 times in {src}; "
        "those references now reach the renamed entity."
    ) in output
    graph = _parse(out)
    assert (EX.Building, RDFS.label, Literal("Building")) in graph
    assert len(graph) == 4


def test_a_target_used_only_as_a_predicate_is_referenced(tmp_path, monkeypatch):
    src = _ttl(
        tmp_path,
        "pred.ttl",
        'ex:hasPart a owl:ObjectProperty ; rdfs:label "has part" .\nex:x ex:part ex:y .\n',
    )
    output = _ran(
        tmp_path, monkeypatch, src, "--from", "ex:hasPart", "--to", "ex:part", "-o", "o.ttl"
    )
    assert f"Note: <{EX.part}> was already referenced 1 time in {src}" in output


def test_a_reflexive_triple_is_reported_not_refused(tmp_path, monkeypatch):
    src = _ttl(tmp_path, "taut.ttl", "ex:Buiding a owl:Class ; rdfs:subClassOf ex:Building .\n")
    output = _ran(
        tmp_path, monkeypatch, src, "--from", "ex:Buiding", "--to", "ex:Building", "-o", "o.ttl"
    )
    assert (
        f"Note: <{EX.Building}> rdfs:subClassOf <{EX.Building}> is now reflexive "
        f"(was <{EX.Buiding}> rdfs:subClassOf <{EX.Building}>)."
    ) in output


# ---------------------------------------------------------------------------
# --merge-entities and merge_entities: true
# ---------------------------------------------------------------------------


def test_merge_entities_writes_the_merge_and_says_so(tmp_path, monkeypatch):
    out = tmp_path / "collide.ttl"
    output = _ran(
        tmp_path,
        monkeypatch,
        TYPOS,
        "--from",
        ONT.Addres,
        "--to",
        ONT.Structure,
        "--merge-entities",
        "-o",
        out,
    )
    assert f"Merged (--merge-entities): <{ONT.Structure}> has 3 triples of its own" in output
    assert _labels(_parse(out), ONT.Structure) == {"Address", "Structure"}


def test_the_config_key_merges_too(tmp_path, monkeypatch):
    src = _ttl(tmp_path, "ab.ttl", TWO_CLASSES)
    config = _yaml(
        tmp_path,
        "merge.yml",
        "rename:\n  merge_entities: true\n"
        '  entities:\n    "http://example.org/A": "http://example.org/B"\n',
    )
    out = tmp_path / "out.ttl"
    _ran(tmp_path, monkeypatch, src, "-c", config, "-o", out)
    assert _labels(_parse(out), EX.B) == {"A", "B"}


def test_the_flag_combines_with_a_config(tmp_path, monkeypatch):
    """A setting, not an operation: P57 (#352) must keep it combinable with -c."""
    src = _ttl(tmp_path, "ab.ttl", TWO_CLASSES)
    config = _yaml(
        tmp_path,
        "plain.yml",
        'rename:\n  entities:\n    "http://example.org/A": "http://example.org/B"\n',
    )
    out = tmp_path / "out.ttl"
    _ran(tmp_path, monkeypatch, src, "-c", config, "--merge-entities", "-o", out)
    assert _labels(_parse(out), EX.B) == {"A", "B"}


def test_a_config_key_that_is_not_a_boolean_is_refused(tmp_path, monkeypatch):
    src = _ttl(tmp_path, "ab.ttl", TWO_CLASSES)
    config = _yaml(
        tmp_path,
        "bad.yml",
        'rename:\n  merge_entities: "yes"\n'
        '  entities:\n    "http://example.org/A": "http://example.org/B"\n',
    )
    output = _refused(tmp_path, monkeypatch, src, "-c", config, "-o", tmp_path / "out.ttl")
    assert "merge_entities must be true or false" in output


def test_merge_entities_merges_the_data_too(tmp_path, monkeypatch):
    src = _ttl(tmp_path, "ont.ttl", "ex:A a owl:Class .\n")
    data = _ttl(tmp_path, "data.ttl", 'ex:i1 a ex:A .\nex:B rdfs:label "data B" .\n')
    output = _ran(
        tmp_path,
        monkeypatch,
        src,
        "--from",
        "ex:A",
        "--to",
        "ex:B",
        "--merge-entities",
        "-o",
        tmp_path / "out.ttl",
        "--migrate-data",
        data,
        "--data-output",
        tmp_path / "data-out.ttl",
    )
    assert f"Merged (--merge-entities): <{EX.B}> has 1 triple of its own in {data}" in output


# ---------------------------------------------------------------------------
# --dry-run
# ---------------------------------------------------------------------------


def test_a_dry_run_previews_then_refuses(tmp_path, monkeypatch):
    output = _refused(
        tmp_path, monkeypatch, TYPOS, "--from", ONT.Addres, "--to", ONT.Structure, "--dry-run"
    )
    assert output.index("Refactoring Preview: Rename") < output.index("Nothing was written:")
    assert f"<{ONT.Structure}> has 3 triples of its own" in output


def test_a_dry_run_with_merge_entities_lists_the_merges(tmp_path, monkeypatch):
    before = snapshot([str(TYPOS)], tmp_path)
    output = _ran(
        tmp_path,
        monkeypatch,
        TYPOS,
        "--from",
        ONT.Addres,
        "--to",
        ONT.Structure,
        "--merge-entities",
        "--dry-run",
    )
    assert f"Would merge (--merge-entities): <{ONT.Structure}> has 3 triples" in output
    assert_wrote_nothing(before, snapshot([str(TYPOS)], tmp_path))


def test_a_dry_run_shows_the_referenced_note(tmp_path, monkeypatch):
    src = _ttl(tmp_path, "ref.ttl", "ex:Buiding a owl:Class .\nex:x ex:p ex:Building .\n")
    output = _ran(
        tmp_path, monkeypatch, src, "--from", "ex:Buiding", "--to", "ex:Building", "--dry-run"
    )
    assert f"Note: <{EX.Building}> was already referenced 1 time" in output


# ---------------------------------------------------------------------------
# The library
# ---------------------------------------------------------------------------


def _graph(body: str) -> Graph:
    return Graph().parse(data=PREFIXES + body, format="turtle")


def test_the_library_fails_a_collision_and_renames_nothing():
    graph = _graph(TWO_CLASSES)
    result = OntologyRenamer().rename(graph, RenameConfig(entities={str(EX.A): str(EX.B)}))
    assert not result.success
    assert result.renamed_graph is None
    assert [(c.target, c.sources, c.kind, c.triples) for c in result.collisions] == [
        (EX.B, (EX.A,), "described", 2)
    ]
    assert f"<{EX.B}> has 2 triples of its own" in (result.error or "")


def test_the_library_merges_when_told_to():
    graph = _graph(TWO_CLASSES)
    config = RenameConfig(entities={str(EX.A): str(EX.B)}, merge_entities=True)
    result = OntologyRenamer().rename(graph, config)
    assert result.success
    assert result.renamed_graph is not None
    assert _labels(result.renamed_graph, EX.B) == {"A", "B"}
    assert [c.target for c in result.collisions] == [EX.B]


def test_rename_file_writes_nothing_on_a_collision(tmp_path):
    src = _ttl(tmp_path, "ab.ttl", TWO_CLASSES)
    out = tmp_path / "out.ttl"
    result = rename_file(src, out, RenameConfig(entities={str(EX.A): str(EX.B)}))
    assert not result.success
    assert not out.exists()


def test_resolved_keeps_merge_entities():
    config = RenameConfig(entities={str(EX.A): str(EX.B)}, merge_entities=True)
    assert config.resolved([(Path("x.ttl"), {})]).merge_entities


def test_find_collisions_ignores_renamed_away_and_absent_sources():
    graph = _graph(TWO_CLASSES)
    swap = RenameConfig(entities={str(EX.A): str(EX.B), str(EX.B): str(EX.A)})
    assert find_collisions(graph, swap.build_mappings(graph)) == []
    absent = RenameConfig(entities={str(EX.Z): str(EX.A)})
    assert find_collisions(graph, absent.build_mappings(graph)) == []


def test_find_references_counts_objects_and_predicates():
    graph = _graph("ex:Buiding a owl:Class .\nex:x ex:Building ex:y .\nex:y ex:p ex:Building .\n")
    config = RenameConfig(entities={str(EX.Buiding): str(EX.Building)})
    references, reflexive = find_references(graph, config.build_mappings(graph))
    assert [(r.target, r.count) for r in references] == [(EX.Building, 2)]
    assert reflexive == []


def test_find_references_names_each_reflexive_triple():
    graph = _graph(
        "ex:Buiding owl:equivalentClass ex:Building .\nex:Building rdfs:subClassOf ex:Buiding .\n"
    )
    config = RenameConfig(entities={str(EX.Buiding): str(EX.Building)})
    _, reflexive = find_references(graph, config.build_mappings(graph))
    assert sorted((t.triple[1], t.original) for t in reflexive) == sorted(
        [
            (OWL.equivalentClass, (EX.Buiding, OWL.equivalentClass, EX.Building)),
            (RDFS.subClassOf, (EX.Building, RDFS.subClassOf, EX.Buiding)),
        ]
    )


# ---------------------------------------------------------------------------
# REFACTOR_GUIDE.md: the commands run verbatim and print what the guide shows
# ---------------------------------------------------------------------------


def _guide_blocks() -> list[tuple[str, str]]:
    import re

    guide = (REPO / "docs" / "user_guides" / "REFACTOR_GUIDE.md").read_text()
    start = guide.index("### Renaming onto an Existing IRI")
    section = guide[start : guide.index("### With Data Migration")]
    return re.findall(r"```(bash|text)\n(.*?)```", section, re.S)


def _argv(command: str) -> list[str]:
    import shlex

    argv = shlex.split(command.replace("\\\n", " "))
    assert argv[0] == "rdf-construct"
    return argv[1:]


def test_guide_refusal_is_the_real_output(monkeypatch):
    (kind, command), (_, shown) = _guide_blocks()[:2]
    assert kind == "bash"
    monkeypatch.chdir(REPO)
    before = TYPOS.read_bytes()
    result = CliRunner().invoke(cli, _argv(command))
    assert result.exit_code == 2
    assert result.output == shown
    assert TYPOS.read_bytes() == before
    assert not (REPO / "collide.ttl").exists()


def test_guide_advice_and_merge_run_verbatim(tmp_path, monkeypatch):
    import shutil

    (tmp_path / "examples").mkdir()
    shutil.copytree(REFACTOR, tmp_path / "examples" / "refactor")
    monkeypatch.chdir(tmp_path)
    blocks = _guide_blocks()

    # The deprecate command the refusal advises, as printed
    advice = blocks[1][1].splitlines()[-1].strip()
    result = CliRunner().invoke(cli, _argv(advice))
    assert result.exit_code == 0, result.output
    assert (tmp_path / "examples" / "refactor" / "typos_deprecated.ttl").exists()

    merge = [command for kind, command in blocks if kind == "bash"][1]
    assert "--merge-entities" in merge
    result = CliRunner().invoke(cli, _argv(merge))
    assert result.exit_code == 0, result.output
    merged_line = next(text for kind, text in blocks if text.startswith("⚠ Merged"))
    assert merged_line in result.output
    assert _labels(_parse(tmp_path / "collide.ttl"), ONT.Structure) == {"Address", "Structure"}
