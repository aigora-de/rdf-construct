"""``shacl-gen``'s validation contract, through the CLI (#223, #224, #227, #228, #485, #487).

Every test runs the real command and reads the shapes back from disk by IRI, never by text.
Each refusal is checked to exit 2 and to leave no output file. Each fixture is built so a wrong
answer shows: severities on some shapes but not others, a closed shape missing a path its
hierarchy declares, a shape shared by two classes, an enumeration in the wrong order.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection

from rdf_construct.cli import cli
from rdf_construct.shacl import SH, PropertyConstraint
from rdf_construct.shacl.selection import declared_classes, local_name, namespace_of
from tests.determinism import without_coverage

REPO = Path(__file__).parent.parent
FIXTURES = REPO / "tests" / "fixtures" / "shacl"
IES = REPO / "tests" / "fixtures" / "ies"
ANIMAL = REPO / "examples" / "animal_ontology.ttl"
SHIPPED_CONFIG = REPO / "examples" / "shacl" / "shacl_config.yml"

ZOO = Namespace("http://example.org/zoo#")
ENUM = Namespace("http://example.org/enum#")
A = Namespace("http://example.org/a#")
B = Namespace("http://example.org/b#")
C = Namespace("http://example.org/c#")
RDFS_NS = Namespace("http://www.w3.org/2000/01/rdf-schema#")

LEVELS = ["minimal", "standard", "strict"]


def _run(tmp_path: Path, *argv: object) -> tuple[Result, Path]:
    """Run ``shacl-gen`` with ``-o`` in ``tmp_path``; return the result and the output path."""
    out = tmp_path / "shapes.ttl"
    result = CliRunner().invoke(cli, ["shacl-gen", *(str(a) for a in argv), "-o", str(out)])
    return result, out


def _ok(tmp_path: Path, *argv: object) -> tuple[Result, Graph]:
    result, out = _run(tmp_path, *argv)
    assert result.exit_code == 0, result.output
    return result, Graph().parse(out, format="turtle")


def _refused(result: Result, out: Path) -> None:
    assert result.exit_code == 2, result.output
    assert not out.exists(), "a refusal must write nothing"


def _config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yml"
    path.write_text(text)
    return path


def _node_shapes(g: Graph) -> set[URIRef]:
    return {s for s in g.subjects(RDF.type, SH.NodeShape) if isinstance(s, URIRef)}


def _shape_for(g: Graph, cls: URIRef) -> URIRef:
    shapes = [s for s in g.subjects(SH.targetClass, cls) if isinstance(s, URIRef)]
    assert len(shapes) == 1, f"{cls} has shapes {shapes}"
    return shapes[0]


def _paths(g: Graph, shape: URIRef) -> set[URIRef]:
    return {g.value(p, SH.path) for p in g.objects(shape, SH.property)}


def _ignored(g: Graph, shape: URIRef) -> list[URIRef]:
    head = g.value(shape, SH.ignoredProperties)
    assert head is not None, f"{shape} has no sh:ignoredProperties"
    return list(Collection(g, head))


def _in_list(g: Graph, shape: URIRef, path: URIRef) -> list[object]:
    for prop in g.objects(shape, SH.property):
        if g.value(prop, SH.path) == path:
            head = g.value(prop, SH["in"])
            return [] if head is None else list(Collection(g, head))
    raise AssertionError(f"{shape} has no property shape for {path}")


# ---------------------------------------------------------------------------
# default_severity (#223)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("how", "expected"),
    [
        (("--default-severity", "warning"), SH.Warning),
        (("--default-severity", "violation"), SH.Violation),
        (("config", "info"), SH.Info),
    ],
    ids=["flag-warning", "flag-violation-explicit", "config-info"],
)
def test_severity_is_on_every_node_and_property_shape(tmp_path, how, expected):
    argv = ("-C", _config(tmp_path, f"default_severity: {how[1]}\n")) if how[0] == "config" else how
    _, g = _ok(tmp_path, ANIMAL, "--closed", *argv)
    nodes = _node_shapes(g)
    props = set(g.objects(None, SH.property))
    assert nodes and props
    for shape in nodes | props:
        assert list(g.objects(shape, SH.severity)) == [expected], shape
    assert set(g.subjects(SH.severity, None)) == nodes | props


@pytest.mark.parametrize(
    "argv",
    [(), ("-C", SHIPPED_CONFIG), ("-C", "null")],
    ids=["no-flag", "shipped-config", "null-in-config"],
)
def test_no_severity_when_none_is_set(tmp_path, argv):
    if argv and argv[1] == "null":
        argv = ("-C", _config(tmp_path, "default_severity: ~\n"))
    _, g = _ok(tmp_path, ANIMAL, *argv)
    assert not list(g.triples((None, SH.severity, None)))


# ---------------------------------------------------------------------------
# --closed at every level, and what a closed shape admits (#224)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("level", LEVELS)
def test_closed_at_every_level(tmp_path, level):
    result, g = _ok(tmp_path, ANIMAL, "--closed", "--level", level)
    nodes = _node_shapes(g)
    assert set(g.subjects(SH.closed, Literal(True))) == nodes
    for shape in nodes:
        assert _ignored(g, shape)[0] == RDF.type
    assert f"closed shapes enabled: {len(nodes)} closed" in result.stdout


@pytest.mark.parametrize("level", LEVELS)
def test_no_closed_summary_without_closed_shapes(tmp_path, level):
    result, g = _ok(tmp_path, ANIMAL, "--level", level)
    assert not list(g.triples((None, SH.closed, None)))
    assert "closed shapes enabled" not in result.stdout


def test_closed_shape_admits_its_whole_hierarchy(tmp_path):
    """Superclass paths are inherited; subclass paths are ignored; ``tag`` comes from a
    restriction; ``nickname`` has no domain, so no closed shape admits it."""
    _, g = _ok(tmp_path, FIXTURES / "hierarchy.ttl", "--closed")
    animal, dog, puppy = (_shape_for(g, ZOO[c]) for c in ("Animal", "Dog", "Puppy"))

    assert _paths(g, animal) == {ZOO.name, ZOO.tag}
    assert _ignored(g, animal) == [RDF.type, ZOO.barks, ZOO.wags]

    assert _paths(g, dog) == {ZOO.name, ZOO.tag, ZOO.barks}
    assert _ignored(g, dog) == [RDF.type, ZOO.wags]

    assert _paths(g, puppy) == {ZOO.name, ZOO.tag, ZOO.barks, ZOO.wags}
    assert _ignored(g, puppy) == [RDF.type]

    admitted = set().union(*(_paths(g, s) | set(_ignored(g, s)) for s in (animal, dog, puppy)))
    assert ZOO.nickname not in admitted


def test_closed_without_inheritance_ignores_the_superclass_paths(tmp_path):
    """``--no-inherit`` used to close Dog with none of Animal's paths, rejecting every Dog."""
    _, g = _ok(tmp_path, FIXTURES / "hierarchy.ttl", "--closed", "--no-inherit")
    dog = _shape_for(g, ZOO.Dog)
    assert _paths(g, dog) == {ZOO.barks}
    assert _ignored(g, dog) == [RDF.type, ZOO.name, ZOO.tag, ZOO.wags]


def test_closed_at_minimal_admits_a_restricted_property(tmp_path):
    """At minimal no converter reads restrictions, so ``tag`` is no property shape; the closed
    shape must still admit it."""
    _, g = _ok(tmp_path, FIXTURES / "hierarchy.ttl", "--closed", "--level", "minimal")
    animal = _shape_for(g, ZOO.Animal)
    assert _paths(g, animal) == {ZOO.name}
    assert _ignored(g, animal) == [RDF.type, ZOO.barks, ZOO.tag, ZOO.wags]


def test_closed_with_a_subclass_cycle_terminates(tmp_path):
    source = tmp_path / "cycle.ttl"
    source.write_text(
        "@prefix ex: <http://example.org/zoo#> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "ex:P a owl:Class ; rdfs:subClassOf ex:Q .\n"
        "ex:Q a owl:Class ; rdfs:subClassOf ex:P .\n"
        "ex:p a owl:DatatypeProperty ; rdfs:domain ex:P .\n"
        "ex:q a owl:DatatypeProperty ; rdfs:domain ex:Q .\n"
    )
    _, g = _ok(tmp_path, source, "--closed", "--no-inherit")
    p_shape = _shape_for(g, ZOO.P)
    assert _paths(g, p_shape) == {ZOO.p}
    assert _ignored(g, p_shape) == [RDF.type, ZOO.q]


# ---------------------------------------------------------------------------
# shape_namespace (#223)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "namespace",
    ["http://example.org/my-shapes#", "http://example.org/shapes/", "urn:example:shapes:"],
    ids=["hash", "slash", "urn"],
)
def test_shape_namespace_is_honoured(tmp_path, namespace):
    config = _config(tmp_path, f'shape_namespace: "{namespace}"\n')
    _, g = _ok(tmp_path, ANIMAL, "-C", config)
    shapes = _node_shapes(g)
    assert len(shapes) == 7
    assert {namespace_of(str(s)) for s in shapes} == {namespace}
    assert _shape_for(g, URIRef("http://example.org/animals#Dog")) == URIRef(f"{namespace}DogShape")


def test_no_shape_namespace_keeps_the_derivation(tmp_path):
    _, g = _ok(tmp_path, ANIMAL)
    assert {namespace_of(str(s)) for s in _node_shapes(g)} == {"http://example.org/animals-shapes#"}


@pytest.mark.parametrize(
    "value",
    ['"shapes#"', '"http://example.org/no-delimiter"', '"not an iri#"', "42"],
    ids=["suffix", "no-delimiter", "no-scheme", "not-a-string"],
)
def test_invalid_shape_namespace_is_refused(tmp_path, value):
    config = _config(tmp_path, f"shape_namespace: {value}\n")
    result, out = _run(tmp_path, ANIMAL, "-C", config)
    _refused(result, out)
    assert "shape_namespace must be a full namespace IRI" in result.output


# ---------------------------------------------------------------------------
# generate_property_shapes is removed (#223)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["false", "true"])
def test_removed_key_is_refused(tmp_path, value):
    config = _config(tmp_path, f"generate_property_shapes: {value}\n")
    result, out = _run(tmp_path, ANIMAL, "-C", config)
    _refused(result, out)
    assert "'generate_property_shapes' was removed in rdf-construct 0.7.0" in result.output
    assert "Delete it from the config" in result.output


# ---------------------------------------------------------------------------
# Shape names (#485)
# ---------------------------------------------------------------------------


def test_colliding_classes_get_their_own_shapes(tmp_path):
    _, g = _ok(tmp_path, FIXTURES / "colliding.ttl")
    ns = "http://example.org/zoo-shapes#"
    assert _shape_for(g, A.Cat) == URIRef(f"{ns}CatShape")
    assert _shape_for(g, B.Cat) == URIRef(f"{ns}b_CatShape")
    assert _paths(g, URIRef(f"{ns}CatShape")) == {A.purrs}
    assert _paths(g, URIRef(f"{ns}b_CatShape")) == {B.meows}
    assert set(g.objects(URIRef(f"{ns}CatShape"), SH.targetClass)) == {A.Cat}


def test_a_third_colliding_class_renames_neither(tmp_path):
    source = tmp_path / "three.ttl"
    source.write_text(
        (FIXTURES / "colliding.ttl").read_text()
        + "@prefix c: <http://example.org/c#> .\nc:Cat a owl:Class .\n"
    )
    _, g = _ok(tmp_path, source)
    ns = "http://example.org/zoo-shapes#"
    assert _shape_for(g, A.Cat) == URIRef(f"{ns}CatShape")
    assert _shape_for(g, B.Cat) == URIRef(f"{ns}b_CatShape")
    assert _shape_for(g, C.Cat) == URIRef(f"{ns}c_CatShape")


def test_a_namespace_without_a_prefix_is_hashed(tmp_path):
    source = tmp_path / "unbound.ttl"
    source.write_text(
        (FIXTURES / "colliding.ttl").read_text() + "<http://example.org/x#Cat> a owl:Class .\n"
    )
    _, g = _ok(tmp_path, source)
    digest = hashlib.sha1(b"http://example.org/x#").hexdigest()[:8]
    assert _shape_for(g, URIRef("http://example.org/x#Cat")) == URIRef(
        f"http://example.org/zoo-shapes#ns{digest}_CatShape"
    )


def test_the_selection_does_not_rename_a_shape(tmp_path):
    _, g = _ok(tmp_path, FIXTURES / "colliding.ttl", "--classes", "b:Cat")
    assert _node_shapes(g) == {URIRef("http://example.org/zoo-shapes#b_CatShape")}


def test_urn_classes_take_their_last_segment(tmp_path):
    _, g = _ok(tmp_path, FIXTURES / "urn.ttl")
    assert _node_shapes(g) == {
        URIRef("urn:example:zoo-shapes#CatShape"),
        URIRef("urn:example:zoo-shapes#KittenShape"),
    }


@pytest.mark.parametrize(
    "source",
    [ANIMAL, *sorted(IES.glob("*.ttl"))],
    ids=lambda p: Path(p).stem,
)
def test_collision_free_shape_iris_are_unchanged(tmp_path, source):
    """With no local-name collision, every shape is ``<namespace><local>Shape``, as before."""
    _, g = _ok(tmp_path, source)
    src = Graph(bind_namespaces="core").parse(source, format="turtle")
    ns = namespace_of(str(next(iter(_node_shapes(g)))))
    expected = {URIRef(f"{ns}{local_name(str(c))}Shape") for c in declared_classes(src)}
    assert _node_shapes(g) == expected


# ---------------------------------------------------------------------------
# Enumerations at the default level, in source order (#227)
# ---------------------------------------------------------------------------

ENUM_EXPECTED = {
    ENUM.hasColour: [ENUM.blue, ENUM.red, ENUM.green],
    ENUM.hasTrim: [ENUM.chrome, ENUM.black],
    ENUM.size: [Literal("S"), Literal("M"), Literal("L")],
}


@pytest.mark.parametrize("level", ["standard", "strict"])
def test_enumerations_at_the_default_level_in_source_order(tmp_path, level):
    _, g = _ok(tmp_path, FIXTURES / "enumerations.ttl", "--level", level)
    car = _shape_for(g, ENUM.Car)
    for path, members in ENUM_EXPECTED.items():
        assert _in_list(g, car, path) == members


def test_no_enumeration_at_minimal(tmp_path):
    _, g = _ok(tmp_path, FIXTURES / "enumerations.ttl", "--level", "minimal")
    assert not list(g.triples((None, SH["in"], None)))


def test_enumeration_order_survives_every_hash_seed(tmp_path):
    for seed in (0, 1, 2, 3):
        out = tmp_path / f"shapes-{seed}.ttl"
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "rdf_construct",
                "shacl-gen",
                str(FIXTURES / "enumerations.ttl"),
                "-o",
                str(out),
            ],
            env={**without_coverage(os.environ), "PYTHONHASHSEED": str(seed)},
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr.decode(errors="replace")
        g = Graph().parse(out, format="turtle")
        car = _shape_for(g, ENUM.Car)
        for path, members in ENUM_EXPECTED.items():
            assert _in_list(g, car, path) == members, f"seed {seed}"


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ([A.x, A.y, A.z], [A.z, A.x], [A.x, A.z]),
        (None, [A.y, A.x], [A.y, A.x]),
        ([A.y, A.x], None, [A.y, A.x]),
        ([A.x], [A.y], []),
        (None, None, None),
    ],
    ids=["intersect-in-first-order", "left-unset", "right-unset", "disjoint", "both-unset"],
)
def test_merging_enumerations_intersects(first, second, expected):
    left = PropertyConstraint(path=A.p, in_values=first)
    right = PropertyConstraint(path=A.p, in_values=second)
    assert left.merge(right).in_values == expected


def test_a_disjoint_merge_allows_nothing():
    """An empty intersection is ``sh:in ()``, not a dropped constraint."""
    g = Graph()
    merged = PropertyConstraint(path=A.p, in_values=[A.x]).merge(
        PropertyConstraint(path=A.p, in_values=[A.y])
    )
    shape = merged.to_rdf(g)
    assert g.value(shape, SH["in"]) == RDF.nil


# ---------------------------------------------------------------------------
# Deprecated classes (#228)
# ---------------------------------------------------------------------------


def test_a_deprecated_class_gets_a_shape(tmp_path):
    _, g = _ok(tmp_path, FIXTURES / "kinds.ttl")
    shape = _shape_for(g, A.Old)
    assert (shape, RDF.type, SH.NodeShape) in g
    assert not list(g.triples((shape, SH.deactivated, None)))


# ---------------------------------------------------------------------------
# Blank-node ranges are never written as sh:class or sh:datatype (#487)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("level", LEVELS)
def test_no_blank_node_class_or_datatype(tmp_path, level):
    _, g = _ok(tmp_path, FIXTURES / "blank_ranges.ttl", "--level", level)
    for predicate in (SH["class"], SH.datatype):
        assert not [o for o in g.objects(None, predicate) if isinstance(o, BNode)], predicate
    pet = _shape_for(g, URIRef("http://example.org/blank#Pet"))
    expected = {URIRef("http://example.org/blank#likes"), URIRef("http://example.org/blank#age")}
    assert expected <= _paths(g, pet)


def test_a_blank_qualification_keeps_its_cardinality(tmp_path):
    _, g = _ok(tmp_path, FIXTURES / "blank_ranges.ttl")
    pet = _shape_for(g, URIRef("http://example.org/blank#Pet"))
    friend = next(
        p
        for p in g.objects(pet, SH.property)
        if g.value(p, SH.path) == URIRef("http://example.org/blank#friend")
    )
    assert g.value(friend, SH.minCount) == Literal(1)
    assert g.value(friend, SH.maxCount) == Literal(1)
    assert g.value(friend, SH["class"]) is None


# ---------------------------------------------------------------------------
# The shipped config, as shipped and closed
# ---------------------------------------------------------------------------


def test_shipped_config_as_shipped(tmp_path):
    result, g = _ok(tmp_path, ANIMAL, "-C", SHIPPED_CONFIG)
    assert len(_node_shapes(g)) == 7
    assert not list(g.triples((None, SH.severity, None)))
    assert not list(g.triples((None, SH.closed, None)))
    assert {namespace_of(str(s)) for s in _node_shapes(g)} == {"http://example.org/animals-shapes#"}
    assert "ignored_properties has no effect" in result.stderr


def test_shipped_config_closed_at_strict(tmp_path):
    result, g = _ok(tmp_path, ANIMAL, "-C", SHIPPED_CONFIG, "--level", "strict", "--closed")
    nodes = _node_shapes(g)
    assert len(nodes) == 7
    assert set(g.subjects(SH.closed, Literal(True))) == nodes
    for shape in nodes:
        assert _ignored(g, shape) == [RDF.type, RDFS_NS.label, RDFS_NS.comment]
    assert not list(g.triples((None, SH.severity, None)))
    assert "closed shapes enabled: 7 closed" in result.stdout


def test_no_closed_summary_when_no_shape_is_written(tmp_path):
    """The summary is derived from what was written: --closed over no classes closes nothing."""
    source = tmp_path / "empty.ttl"
    source.write_text(
        "@prefix ex: <http://example.org/e#> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "ex:p a owl:DatatypeProperty .\n"
    )
    result, g = _ok(tmp_path, source, "--closed")
    assert not _node_shapes(g)
    assert "closed shapes enabled" not in result.stdout


# ---------------------------------------------------------------------------
# SHACL_GUIDE.md's closed-shape, severity and configuration examples run verbatim
# ---------------------------------------------------------------------------

GUIDE = REPO / "docs" / "user_guides" / "SHACL_GUIDE.md"


def _section(heading: str) -> str:
    guide = GUIDE.read_text()
    start = guide.index(f"\n{heading}\n")
    return guide[start : guide.index("\n## ", start + 1)]


def _guide_command(heading: str) -> list[str]:
    import re
    import shlex

    (command,) = re.findall(r"```bash\n(rdf-construct shacl-gen .*?)\n```", _section(heading))
    argv = shlex.split(command)
    assert argv[0] == "rdf-construct"
    return argv[1:]


def test_guide_closed_shapes_example(tmp_path, monkeypatch):
    """The section's command on its own example hierarchy, and the shape it quotes."""
    import re

    shutil.copy(FIXTURES / "hierarchy.ttl", tmp_path / "ontology.ttl")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, _guide_command("## Closed Shapes"))
    assert result.exit_code == 0, result.output
    assert "(closed shapes enabled: 3 closed)" in result.stdout
    assert "(closed shapes enabled: 3 closed)" in _section("## Closed Shapes")
    g = Graph().parse(tmp_path / "ontology-shapes.ttl", format="turtle")
    animal = _shape_for(g, ZOO.Animal)
    assert _ignored(g, animal) == [RDF.type, ZOO.barks, ZOO.wags]
    quoted = re.search(r"sh:ignoredProperties \( (.*?) \)", _section("## Closed Shapes"))
    assert quoted is not None and quoted.group(1) == "rdf:type ex:barks ex:wags"


def test_guide_severity_example(tmp_path, monkeypatch):
    shutil.copy(ANIMAL, tmp_path / "ontology.ttl")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, _guide_command("## Severity Levels"))
    assert result.exit_code == 0, result.output
    g = Graph().parse(tmp_path / "ontology-shapes.ttl", format="turtle")
    shapes = _node_shapes(g) | set(g.objects(None, SH.property))
    assert {o for s in shapes for o in g.objects(s, SH.severity)} == {SH.Warning}
    assert set(g.subjects(SH.severity, None)) == shapes


def test_guide_configuration_sample(tmp_path, monkeypatch):
    """The sample ``shacl-config.yml`` loads and runs on the guide's building ontology."""
    import re

    (sample,) = re.findall(
        r"Example `shacl-config.yml`:\n\n```yaml\n(.*?)```", _section("## Configuration File"), re.S
    )
    (tmp_path / "shacl-config.yml").write_text(sample)
    shutil.copy(FIXTURES / "building.ttl", tmp_path / "ontology.ttl")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, _guide_command("## Configuration File"))
    assert result.exit_code == 0, result.output
    g = Graph().parse(tmp_path / "ontology-shapes.ttl", format="turtle")
    assert {namespace_of(str(s)) for s in _node_shapes(g)} == {
        "http://example.org/building-shapes#"
    }
    assert set(g.objects(None, SH.severity)) == {SH.Warning}
