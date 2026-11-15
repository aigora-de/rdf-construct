"""``shacl-gen``'s class selection and ignored properties, through the CLI (#226, #356, #484).

Every test runs the real command, then reads the shapes back from disk and compares IRIs,
never text. Each refusal is checked to exit 2 and to leave no output file.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import RDF, Graph, Namespace, URIRef
from rdflib.collection import Collection

from rdf_construct.cli import cli
from rdf_construct.shacl import (
    SH,
    ShaclConfig,
    ShaclSelectionError,
    StrictnessLevel,
    generate_shapes,
)

REPO = Path(__file__).parent.parent
FIXTURES = REPO / "tests" / "fixtures" / "shacl"
ANIMAL = REPO / "examples" / "animal_ontology.ttl"
SHIPPED_CONFIG = REPO / "examples" / "shacl" / "shacl_config.yml"

PETS = Namespace("http://example.org/pets#")
ANIMALS = Namespace("http://example.org/animals#")
A = Namespace("http://example.org/a#")
B = Namespace("http://example.org/b#")
MYORG = Namespace("http://example.org/myorg#")
RDFS_NS = Namespace("http://www.w3.org/2000/01/rdf-schema#")


def _run(tmp_path: Path, *argv: object) -> tuple[Result, Path]:
    """Run ``shacl-gen`` with ``-o`` in ``tmp_path``; return the result and the output path."""
    out = tmp_path / "shapes.ttl"
    result = CliRunner().invoke(cli, ["shacl-gen", *(str(a) for a in argv), "-o", str(out)])
    return result, out


def _config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yml"
    path.write_text(text)
    return path


def _targets(out: Path) -> set[URIRef]:
    g = Graph()
    g.parse(out, format="turtle")
    return {o for o in g.objects(None, SH.targetClass) if isinstance(o, URIRef)}


def _ignored_lists(out: Path) -> list[list[URIRef]]:
    g = Graph()
    g.parse(out, format="turtle")
    return [list(Collection(g, head)) for head in g.objects(None, SH.ignoredProperties)]


def _refused(result: Result, out: Path) -> None:
    assert result.exit_code == 2, result.output
    assert not out.exists(), "a refusal must write nothing"


# ---------------------------------------------------------------------------
# Selection by equality (#226)
# ---------------------------------------------------------------------------


def test_bare_name_selects_only_that_class(tmp_path):
    """``Cat`` selects ``Cat``, not ``Category`` or ``Catalogue``."""
    result, out = _run(tmp_path, FIXTURES / "substr.ttl", "--classes", "Cat")
    assert result.exit_code == 0, result.output
    assert _targets(out) == {PETS.Cat}
    assert "Target classes: ex:Cat" in result.stdout
    assert "Generated 1 shape(s)" in result.stdout


def test_bare_exclusion_removes_only_that_class(tmp_path):
    """``exclude_classes: [Cat]`` removes ``Cat`` alone."""
    config = _config(tmp_path, "exclude_classes: [Cat]\n")
    result, out = _run(tmp_path, FIXTURES / "substr.ttl", "-C", config)
    assert result.exit_code == 0, result.output
    assert _targets(out) == {PETS.Category, PETS.Catalogue, PETS.Dog}


def test_documented_curie_form_selects(tmp_path):
    """``CLI_REFERENCE.md``'s ``--classes "ex:…,ex:…"`` form selects those classes."""
    result, out = _run(tmp_path, ANIMAL, "--classes", "ex:Animal,ex:Dog")
    assert result.exit_code == 0, result.output
    assert _targets(out) == {ANIMALS.Animal, ANIMALS.Dog}
    assert "Target classes: ex:Animal, ex:Dog" in result.stdout


@pytest.mark.parametrize(
    "spelling",
    ["<http://example.org/animals#Dog>", "http://example.org/animals#Dog", "ex:Dog", "Dog"],
    ids=["bracketed", "full-iri", "curie", "bare"],
)
def test_every_spelling_selects_the_same_class(tmp_path, spelling):
    result, out = _run(tmp_path, ANIMAL, "--classes", spelling)
    assert result.exit_code == 0, result.output
    assert _targets(out) == {ANIMALS.Dog}


def test_urn_classes(tmp_path):
    """A URN's local name follows its last ``:``; the IRI itself is written in brackets."""
    result, out = _run(tmp_path, FIXTURES / "urn.ttl", "--classes", "Cat,<urn:example:Kitten>")
    assert result.exit_code == 0, result.output
    assert _targets(out) == {URIRef("urn:example:Cat"), URIRef("urn:example:Kitten")}


def test_unbracketed_urn_is_refused_with_the_bracketed_form(tmp_path):
    result, out = _run(tmp_path, FIXTURES / "urn.ttl", "--classes", "urn:example:Cat")
    _refused(result, out)
    assert "<urn:example:Cat>" in result.stderr


def test_targets_minus_exclusions(tmp_path):
    """Targets and exclusions both apply (#226's five lines dropped the exclusion)."""
    config = _config(tmp_path, "exclude_classes: [Cat]\n")
    result, out = _run(tmp_path, FIXTURES / "substr.ttl", "-C", config, "--classes", "Cat,Dog")
    assert result.exit_code == 0, result.output
    assert _targets(out) == {PETS.Dog}
    assert "ex:Cat is also a target; it is excluded" in result.stderr


def test_exclusion_emptying_the_selection_is_refused(tmp_path):
    config = _config(tmp_path, "exclude_classes: [Cat]\n")
    result, out = _run(tmp_path, FIXTURES / "substr.ttl", "-C", config, "--classes", "Cat")
    _refused(result, out)
    assert "selection is empty" in result.stderr


def test_exclusions_that_exclude_nothing_are_notes(tmp_path):
    """A shared config's exclusions may not apply to this source: a note each, exit 0."""
    config = _config(tmp_path, 'exclude_classes: [Nope, "qq:Foo"]\n')
    result, out = _run(tmp_path, FIXTURES / "substr.ttl", "-C", config)
    assert result.exit_code == 0, result.output
    assert _targets(out) == {PETS.Cat, PETS.Category, PETS.Catalogue, PETS.Dog}
    assert "'Nope' names no class in this source; it excludes nothing" in result.stderr
    assert "prefix 'qq' is not bound" in result.stderr


# ---------------------------------------------------------------------------
# Refusals: exit 2, nothing written
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "classes", "message"),
    [
        (ANIMAL, "ex:Unicorn", "'ex:Unicorn' names no class in this source"),
        (ANIMAL, "Dgo", "did you mean Dog?"),
        (FIXTURES / "two_cats.ttl", "Cat", "matches 2 classes (a:Cat, b:Cat)"),
        (ANIMAL, "zz:Dog", "prefix 'zz' is not bound"),
        (ANIMAL, "Dog,", "an empty entry (a stray comma?)"),
        (FIXTURES / "kinds.ttl", "x:Animal", "only referenced, not declared as a class"),
    ],
    ids=[
        "unmatched-curie",
        "unmatched-bare",
        "ambiguous",
        "unbound",
        "empty-entry",
        "referenced",
    ],
)
def test_target_refusals(tmp_path, source, classes, message):
    result, out = _run(tmp_path, source, "--classes", classes)
    _refused(result, out)
    assert message in result.stderr


@pytest.mark.parametrize("spelling", ["Old", "a:Old"], ids=["bare", "curie"])
def test_deprecated_class_is_selectable(tmp_path, spelling):
    """A class declared only ``owl:DeprecatedClass`` is shaped, so it may be selected (#228)."""
    result, out = _run(tmp_path, FIXTURES / "kinds.ttl", "--classes", spelling)
    assert result.exit_code == 0, result.output
    assert _targets(out) == {A.Old}


def test_every_problem_is_listed_at_once(tmp_path):
    result, out = _run(tmp_path, ANIMAL, "--classes", "ex:Unicorn,Dgo,ex:Dog")
    _refused(result, out)
    assert "ex:Unicorn" in result.stderr and "Dgo" in result.stderr


def test_class_typed_both_ways_is_selectable(tmp_path):
    """``owl:Class`` plus ``owl:DeprecatedClass`` is shaped, so it may be selected."""
    result, out = _run(tmp_path, FIXTURES / "kinds.ttl", "--classes", "a:Both")
    assert result.exit_code == 0, result.output
    assert _targets(out) == {A.Both}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("target_classes: Cat\n", "target_classes must be a list, got str 'Cat'"),
        ("exclude_classes: Cat\n", "exclude_classes must be a list"),
        ("ignored_properties: rdfs:label\n", "ignored_properties must be a list"),
        ("target_classes: [1]\n", "target_classes must be a list of strings"),
    ],
    ids=["targets", "excludes", "ignored", "non-string"],
)
def test_a_scalar_is_refused(tmp_path, text, message):
    """``target_classes: Cat`` was iterated by character and selected every class."""
    result, out = _run(tmp_path, FIXTURES / "substr.ttl", "-C", _config(tmp_path, text))
    _refused(result, out)
    assert message in result.stderr


# ---------------------------------------------------------------------------
# ignored_properties (#356)
# ---------------------------------------------------------------------------


def test_ignored_property_in_the_files_own_prefix(tmp_path):
    """``org:secret`` is the file's ``org:``, and the output binds ``org:`` to it too."""
    config = _config(tmp_path, 'ignored_properties: ["org:secret"]\n')
    result, out = _run(
        tmp_path, FIXTURES / "org.ttl", "-C", config, "--level", "strict", "--closed"
    )
    assert result.exit_code == 0, result.output
    assert _ignored_lists(out) == [[RDF.type, MYORG.secret]]

    written = Graph(bind_namespaces="none")
    written.parse(out, format="turtle")
    bound = dict(written.namespaces())
    assert str(bound["org"]) == str(MYORG)
    assert "org1" not in bound


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ("zz:nope", "prefix 'zz' is not bound in this source"),
        ("dcterms:title", "write <http://purl.org/dc/terms/title>"),
        ("secret", "'secret' is not a CURIE or an IRI"),
    ],
    ids=["unknown-prefix", "rdflib-knows-it", "bare"],
)
def test_unresolvable_ignored_property_is_refused(tmp_path, entry, message):
    config = _config(tmp_path, f'ignored_properties: ["{entry}"]\n')
    result, out = _run(
        tmp_path, FIXTURES / "org.ttl", "-C", config, "--level", "strict", "--closed"
    )
    _refused(result, out)
    assert message in result.stderr


def test_shipped_config_executed(tmp_path):
    """The shipped config's list, de-duplicated: ``rdf:type`` was written twice."""
    result, out = _run(tmp_path, ANIMAL, "-C", SHIPPED_CONFIG, "--level", "strict", "--closed")
    assert result.exit_code == 0, result.output
    lists = _ignored_lists(out)
    assert lists
    assert all(lst == [RDF.type, RDFS_NS.label, RDFS_NS.comment] for lst in lists)


def test_ignored_properties_without_closed_shapes_is_a_note(tmp_path):
    result, out = _run(tmp_path, ANIMAL, "-C", SHIPPED_CONFIG)
    assert result.exit_code == 0, result.output
    assert "ignored_properties has no effect" in result.stderr
    assert _ignored_lists(out) == []


@pytest.mark.parametrize("level", ["minimal", "standard", "strict"])
def test_closed_gives_no_note_at_any_level(tmp_path, level):
    """``--closed`` alone closes shapes, so the list takes effect at every level (#224)."""
    result, out = _run(tmp_path, ANIMAL, "-C", SHIPPED_CONFIG, "--level", level, "--closed")
    assert result.exit_code == 0, result.output
    assert "ignored_properties has no effect" not in result.stderr
    assert _ignored_lists(out)


def test_a_preloaded_graph_resolves_against_its_own_bindings():
    """Library callers: a bare ``Graph()`` binds rdflib's table, so ``dcterms:`` resolves."""
    g = Graph()
    g.parse(FIXTURES / "org.ttl", format="turtle")
    config = ShaclConfig(
        level=StrictnessLevel.STRICT, closed=True, ignored_properties=["dcterms:title"]
    )
    shapes, _ = generate_shapes(g, config)
    heads = list(shapes.objects(None, SH.ignoredProperties))
    assert [list(Collection(shapes, h)) for h in heads] == [
        [RDF.type, URIRef("http://purl.org/dc/terms/title")]
    ]


def test_library_refusal_raises_before_generating():
    with pytest.raises(ShaclSelectionError, match="names no class"):
        generate_shapes(ANIMAL, ShaclConfig(target_classes=["ex:Unicorn"]))


# ---------------------------------------------------------------------------
# The fallback shape namespace (#484)
# ---------------------------------------------------------------------------


def _shape_namespaces(out: Path) -> set[str]:
    g = Graph()
    g.parse(out, format="turtle")
    return {str(s).rsplit("#", 1)[0] + "#" for s in g.subjects(RDF.type, SH.NodeShape)}


def test_no_header_uses_the_classes_namespace(tmp_path):
    result, out = _run(tmp_path, FIXTURES / "no_header.ttl")
    assert result.exit_code == 0, result.output
    assert _shape_namespaces(out) == {"http://example.org/m-shapes#"}


def test_prefix_order_does_not_move_the_namespace(tmp_path):
    text = (FIXTURES / "no_header.ttl").read_text()
    lines = text.splitlines(keepends=True)
    prefixes = [line for line in lines if line.startswith("@prefix")]
    rest = [line for line in lines if not line.startswith("@prefix")]
    swapped = tmp_path / "swapped.ttl"
    swapped.write_text("".join(reversed(prefixes)) + "".join(rest))
    result, out = _run(tmp_path, swapped)
    assert result.exit_code == 0, result.output
    assert _shape_namespaces(out) == {"http://example.org/m-shapes#"}


def test_selection_does_not_move_the_namespace(tmp_path):
    result, out = _run(tmp_path, FIXTURES / "no_header.ttl", "--classes", "a:Lone")
    assert result.exit_code == 0, result.output
    assert _shape_namespaces(out) == {"http://example.org/m-shapes#"}
    assert "brickschema" not in out.read_text()


# ---------------------------------------------------------------------------
# SHACL_GUIDE.md's selection examples run verbatim
# ---------------------------------------------------------------------------


def _guide_commands() -> list[str]:
    import re

    guide = (REPO / "docs" / "user_guides" / "SHACL_GUIDE.md").read_text()
    start = guide.index("## Targeting Specific Classes")
    section = guide[start : guide.index("\n## ", start + 1)]
    return re.findall(r"```bash\n(rdf-construct shacl-gen .*?)\n```", section, re.S)


BLD = Namespace("http://example.org/building#")

GUIDE_EXPECTED = [
    (0, {BLD.Building, BLD.Floor, BLD.Room}),
    (0, {BLD.Building, BLD.Floor}),
    (2, None),
]


def test_guide_selection_examples(tmp_path, monkeypatch):
    import shlex

    commands = _guide_commands()
    assert len(commands) == len(GUIDE_EXPECTED)
    for command, (exit_code, targets) in zip(commands, GUIDE_EXPECTED, strict=True):
        work = tmp_path / str(len(list(tmp_path.iterdir())))
        work.mkdir()
        shutil.copy(FIXTURES / "building.ttl", work / "ontology.ttl")
        monkeypatch.chdir(work)
        argv = shlex.split(command)
        assert argv[0] == "rdf-construct"
        result = CliRunner().invoke(cli, argv[1:])
        assert result.exit_code == exit_code, (command, result.output)
        out = work / "ontology-shapes.ttl"
        if targets is None:
            assert not out.exists()
        else:
            assert _targets(out) == targets


def test_guide_python_refusal_example(tmp_path, monkeypatch, capsys):
    """The guide's ``ShaclSelectionError`` snippet runs verbatim and prints the problem."""
    import re

    guide = (REPO / "docs" / "user_guides" / "SHACL_GUIDE.md").read_text()
    (block,) = re.findall(
        r"```python\n(from rdf_construct\.shacl import ShaclSelectionError\n.*?)```", guide, re.S
    )
    shutil.copy(FIXTURES / "building.ttl", tmp_path / "ontology.ttl")
    monkeypatch.chdir(tmp_path)
    exec(block, {"Path": Path, "generate_shapes": generate_shapes, "ShaclConfig": ShaclConfig})
    assert "'Buildng' names no class in this source" in capsys.readouterr().out


def test_a_path_is_parsed_with_only_its_own_prefixes():
    """``generate_shapes(Path)``: the file's ``org:``, and no ``dcterms:`` from rdflib's table."""
    config = ShaclConfig(
        level=StrictnessLevel.STRICT, closed=True, ignored_properties=["org:secret"]
    )
    shapes, _ = generate_shapes(FIXTURES / "org.ttl", config)
    heads = list(shapes.objects(None, SH.ignoredProperties))
    assert [list(Collection(shapes, h)) for h in heads] == [[RDF.type, MYORG.secret]]

    with pytest.raises(ShaclSelectionError, match="prefix 'dcterms' is not bound"):
        generate_shapes(FIXTURES / "org.ttl", ShaclConfig(ignored_properties=["dcterms:title"]))
