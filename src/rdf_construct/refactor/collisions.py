"""Find renames that would merge two entities, or make an axiom contradict itself (#185).

A rename substitutes IRIs simultaneously: each IRI is mapped once, so ``A → B`` with
``B → C`` does not chain, and a swap ``A ↔ B`` is legal. What a rename must not do by
accident is make two entities one. That happens in three ways:

- **described:** the target already has triples of its own as a subject, and is not itself
  renamed away. A target that is only referenced (an object or a predicate) is not a
  collision: connecting those references to the renamed entity is what a rename is for;
- **many:** two renames share a target;
- **contradiction:** the rename makes an axiom that keeps two things apart reflexive, so a
  class is disjoint with itself (unsatisfiable) or an individual different from itself
  (an inconsistent ontology).

Only *live* mappings count: a mapping whose source occurs nowhere in the graph renames
nothing there, so it can merge nothing. Without that rule, a config of typo fixes run over a
file that already holds the fixed spellings would refuse every one of them.

Every lookup is one of rdflib's indexed patterns, so the check costs one pass over the
mappings, not a scan of the graph per mapping.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS
from rdflib.term import Node

from rdf_construct.refactor.config import RenameMapping

#: Predicates that keep their subject and object apart. Made reflexive by a rename, each
#: one contradicts itself: a class disjoint with itself or its own complement, a property
#: disjoint with itself, an individual different from itself.
CONTRADICTORY: frozenset[URIRef] = frozenset(
    {OWL.disjointWith, OWL.propertyDisjointWith, OWL.complementOf, OWL.differentFrom}
)

_SELF_PHRASES: dict[URIRef, str] = {
    OWL.disjointWith: "disjoint with",
    OWL.propertyDisjointWith: "disjoint with",
    OWL.complementOf: "the complement of",
    OWL.differentFrom: "different from",
}

_SHORT_NAMESPACES = (("rdf:", str(RDF)), ("rdfs:", str(RDFS)), ("owl:", str(OWL)))

Triple = tuple[Node, Node, Node]


@dataclass(frozen=True)
class RenameCollision:
    """A rename that would merge two entities, or make an axiom contradict itself.

    Attributes:
        target: The IRI the renames lead to.
        sources: The IRIs renamed onto it, sorted.
        kind: ``described`` (the target has triples of its own), ``many`` (several renames
            share the target) or ``contradiction`` (an axiom made reflexive).
        triples: The target's own triples, for ``described``; otherwise 0.
        axiom: The source triple made reflexive, for ``contradiction``.
    """

    target: URIRef
    sources: tuple[URIRef, ...]
    kind: Literal["described", "many", "contradiction"]
    triples: int = 0
    axiom: Triple | None = None

    def describe(self, where: str = "") -> str:
        """One line naming the collision, for a refusal or a library error.

        Args:
            where: Where the target's triples or the axiom were found, such as
                ``" in typos.ttl"``. Empty when the caller knows only one graph.

        Returns:
            The line, with full IRIs in angle brackets.
        """
        if self.kind == "contradiction" and self.axiom is not None:
            s, p, o = self.axiom
            phrase = _SELF_PHRASES.get(URIRef(str(p)), "contradict")
            return (
                f"{short(s)} {short(p)} {short(o)}{where}: the rename makes <{self.target}> "
                f"{phrase} itself."
            )
        names = join_iris(self.sources)
        if self.kind == "described":
            noun = "triple" if self.triples == 1 else "triples"
            return (
                f"<{self.target}> has {self.triples} {noun} of its own{where}; "
                f"renaming {names} onto it merges them."
            )
        both = "both " if len(self.sources) == 2 else ""
        return f"<{self.target}> is the target of {both}{names}, which become one entity."


@dataclass(frozen=True)
class TargetReference:
    """A rename target that the graph mentions but does not describe.

    Attributes:
        target: The IRI renamed onto.
        count: Triples that use it as an object or a predicate.
    """

    target: URIRef
    count: int


@dataclass(frozen=True)
class ReflexiveTriple:
    """A triple that a rename makes reflexive without contradicting anything.

    Not always a tautology: ``C rdfs:subClassOf C`` says nothing, but ``P owl:inverseOf P``
    says P is symmetric, and ``x ex:knows x`` is a new fact. So it is reported, never refused.

    Attributes:
        triple: The triple as the rename writes it.
        original: The triple as the source has it.
    """

    triple: Triple
    original: Triple

    def describe(self) -> str:
        """One line naming the reflexive triple and the triple it was, for a note."""
        written = " ".join(short(term) for term in self.triple)
        was = " ".join(short(term) for term in self.original)
        return f"{written} is now reflexive (was {was})."


def short(term: Node) -> str:
    """Write a term for a message: rdf, rdfs and owl terms as CURIEs, any other IRI in full.

    Never uses a graph's namespace manager, which can mint ``ns1:`` prefixes as it goes.

    Args:
        term: The term to write.

    Returns:
        ``rdfs:subClassOf``, ``<http://example.org/A>``, or the term's N3 form.
    """
    if isinstance(term, URIRef):
        text = str(term)
        for prefix, namespace in _SHORT_NAMESPACES:
            local = text[len(namespace) :]
            if text.startswith(namespace) and local.isidentifier():
                return prefix + local
        return f"<{text}>"
    return term.n3()


def join_iris(iris: Iterable[URIRef]) -> str:
    """Join IRIs as ``<a>``, ``<a> and <b>`` or ``<a>, <b> and <c>``.

    Args:
        iris: The IRIs, in the order to name them.

    Returns:
        The joined text.
    """
    names = [f"<{iri}>" for iri in iris]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _occurs(graph: Graph, iri: URIRef) -> bool:
    """Whether ``iri`` appears in ``graph`` as a subject, a predicate or an object."""
    return (iri, None, None) in graph or (None, iri, None) in graph or (None, None, iri) in graph


def live_mappings(graph: Graph, mappings: Iterable[RenameMapping]) -> list[RenameMapping]:
    """The mappings that rename something in ``graph``.

    A mapping onto itself renames nothing, and neither does one whose source the graph never
    mentions.

    Args:
        graph: The graph the mappings would be applied to.
        mappings: Concrete mappings, as ``RenameConfig.build_mappings`` returns them.

    Returns:
        The live mappings, in the order given.
    """
    return [m for m in mappings if m.from_uri != m.to_uri and _occurs(graph, m.from_uri)]


def _own_triples(graph: Graph, iri: URIRef) -> int:
    return sum(1 for _ in graph.triples((iri, None, None)))


def find_collisions(graph: Graph, mappings: Iterable[RenameMapping]) -> list[RenameCollision]:
    """Every way the mappings would merge two entities in ``graph``.

    Args:
        graph: The graph the mappings would be applied to.
        mappings: Concrete mappings, as ``RenameConfig.build_mappings`` returns them.

    Returns:
        The collisions, sorted by target, then kind.
    """
    live = live_mappings(graph, mappings)
    uri_map: dict[Node, Node] = {m.from_uri: m.to_uri for m in live}
    by_target: dict[URIRef, list[URIRef]] = defaultdict(list)
    for m in live:
        by_target[m.to_uri].append(m.from_uri)

    found: list[RenameCollision] = []
    for target, sources in by_target.items():
        # A target that is itself renamed away leaves its triples behind: a swap, a chain.
        own = 0 if target in uri_map else _own_triples(graph, target)
        if own:
            found.append(RenameCollision(target, tuple(sorted(sources)), "described", own))
        elif len(sources) > 1:
            found.append(RenameCollision(target, tuple(sorted(sources)), "many"))

    for predicate in CONTRADICTORY:
        for s, o in graph.subject_objects(predicate):
            if s == o or (s not in uri_map and o not in uri_map):
                continue
            new_s = uri_map.get(s, s)
            if new_s == uri_map.get(o, o):
                renamed = tuple(sorted(URIRef(str(t)) for t in (s, o) if t in uri_map))
                found.append(
                    RenameCollision(
                        URIRef(str(new_s)), renamed, "contradiction", axiom=(s, predicate, o)
                    )
                )

    found.sort(key=lambda c: (str(c.target), c.kind, [str(t) for t in c.axiom or ()]))
    return found


def find_references(
    graph: Graph, mappings: Iterable[RenameMapping]
) -> tuple[list[TargetReference], list[ReflexiveTriple]]:
    """What a rename connects to without merging anything, for the run to report.

    Args:
        graph: The graph the mappings would be applied to.
        mappings: Concrete mappings, as ``RenameConfig.build_mappings`` returns them.

    Returns:
        The targets that the graph references but does not describe, each with its count,
        and every triple the rename makes reflexive outside ``CONTRADICTORY``, both sorted.
    """
    live = live_mappings(graph, mappings)
    uri_map: dict[Node, Node] = {m.from_uri: m.to_uri for m in live}

    references: list[TargetReference] = []
    for target in sorted({m.to_uri for m in live}, key=str):
        if target in uri_map or (target, None, None) in graph:
            continue
        count = sum(1 for _ in graph.triples((None, None, target)))
        count += sum(1 for _ in graph.triples((None, target, None)))
        if count:
            references.append(TargetReference(target, count))

    originals: set[Triple] = set()
    for source in uri_map:
        for p, o in graph.predicate_objects(source):
            originals.add((source, p, o))
        for s, p in graph.subject_predicates(source):
            originals.add((s, p, source))

    reflexive: list[ReflexiveTriple] = []
    for s, p, o in originals:
        if s == o or p in CONTRADICTORY:
            continue
        new_s = uri_map.get(s, s)
        if new_s == uri_map.get(o, o):
            new_p = uri_map.get(p, p)
            reflexive.append(ReflexiveTriple((new_s, new_p, new_s), (s, p, o)))
    reflexive.sort(key=lambda t: [str(x) for x in (*t.triple, *t.original)])
    return references, reflexive
