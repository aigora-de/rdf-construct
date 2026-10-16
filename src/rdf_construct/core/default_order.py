"""The built-in default subject ordering, for Turtle writers that have no profile (#303).

``order`` takes its sections from a profile. Every other command that writes Turtle routes its
output through ``serialise_turtle_str()`` / ``serialise_turtle()`` with the list built here
(#95), so that every Turtle file the tool writes puts superclasses before subclasses and
superproperties before subproperties.

The sections, each subject placed once by the first that claims it (punning):

1. the ``owl:Ontology`` header;
2. classes, topologically over ``rdfs:subClassOf``;
3. object, datatype, annotation and *other* properties, each topologically over
   ``rdfs:subPropertyOf``. *Other* is a property of no inferable kind — declared only
   ``rdf:Property``, ``owl:FunctionalProperty`` or ``owl:DeprecatedProperty`` — whose kind is
   never guessed;
4. individuals: named subjects with an ``rdf:type`` no earlier section claimed;
5. unclaimed named subjects — those with no ``rdf:type`` at all — which are emitted, never
   dropped;
6. blank nodes: those reachable from the named subjects, then the root ones (an
   ``owl:AllDisjointClasses``, an ``owl:Axiom``) sorted by their content, each followed by what
   it reaches.

Each named section is sorted with its edge fixed, not inferred from its members: an annotation
property hierarchy is not sorted over ``rdfs:subClassOf``, and a class punned as an object
property does not send the class section over ``rdfs:subPropertyOf`` (#245).

Blank nodes are never sorted by label. rdflib draws a fresh label for every parse, so a label
order is a different order on every run.
"""

from collections import Counter
from collections.abc import Iterable

from rdflib import RDF, RDFS, BNode, Graph, URIRef
from rdflib.namespace import OWL
from rdflib.term import Node

from .ordering import topo_sort_subset
from .selector import select_subjects
from .serialiser import bnode_closure, collect_inline_bnodes, format_term
from .utils import qname_sort_key

#: The hierarchy sections after the header: a built-in selector key, and the edge its
#: section is sorted over.
_HIERARCHY_SECTIONS: tuple[tuple[str, URIRef], ...] = (
    ("classes", RDFS.subClassOf),
    ("obj_props", RDFS.subPropertyOf),
    ("data_props", RDFS.subPropertyOf),
    ("ann_props", RDFS.subPropertyOf),
    ("other_props", RDFS.subPropertyOf),
)

# How many missing or duplicated subjects the guard names before summarising.
_GUARD_EXAMPLES = 5


class IncompleteSubjectOrderError(RuntimeError):
    """A subject list that would not write every triple of its graph exactly once.

    ``serialise_turtle()`` writes only the subjects it is given, so a short list loses triples
    without a word. Raised where a list is built for a whole graph, never inside the serialiser:
    ``order``'s ``skip`` and ``warn`` policies omit subjects on purpose. A routing that raises
    this has a bug, not bad input.
    """


def default_subject_order(graph: Graph) -> list[Node]:
    """Order every subject of a graph in the built-in default sections.

    Args:
        graph: RDF graph whose subjects to order.

    Returns:
        Every subject with triples, each exactly once, ready for ``serialise_turtle_str()``.

    Raises:
        IncompleteSubjectOrderError: If the list would not write every triple. That is a bug
            here, or the one input the serialiser cannot write (a cycle of blank nodes each
            referenced once, which no subject can reach: #341).
    """
    ordered: list[Node] = []
    seen: set[Node] = set()

    def place(nodes: Iterable[Node]) -> None:
        for node in nodes:
            if node not in seen:
                ordered.append(node)
                seen.add(node)

    def unseen_named(nodes: Iterable[Node]) -> set[Node]:
        return {n for n in nodes if isinstance(n, URIRef) and n not in seen}

    def alpha(nodes: set[Node]) -> list[Node]:
        return sorted(nodes, key=lambda n: qname_sort_key(graph, n))

    place(alpha(unseen_named(graph.subjects(RDF.type, OWL.Ontology))))

    for selector_key, edge in _HIERARCHY_SECTIONS:
        members = unseen_named(select_subjects(graph, selector_key, {}))
        place(topo_sort_subset(graph, members, edge))

    place(alpha(unseen_named(graph.subjects(RDF.type, None))))
    place(alpha(unseen_named(graph.subjects())))

    # Blank nodes belong to the description of whatever references them.
    place(bnode_closure(graph, ordered))

    # What is left is reachable from no named subject. Its roots are the blank nodes nothing
    # left references; a remainder with no root is a cycle, placed by the same key.
    remaining = {s for s in graph.subjects() if isinstance(s, BNode) and s not in seen}
    referenced = {o for s in remaining for o in graph.objects(s) if o in remaining}
    roots = remaining - referenced
    for start in (roots, remaining):
        for root in sorted(start, key=lambda b: _bnode_content_key(graph, b)):
            if root not in seen:
                place([root])
                place(bnode_closure(graph, [root]))

    check_subject_order_complete(graph, ordered)
    return ordered


def check_subject_order_complete(graph: Graph, subjects: list[Node]) -> None:
    """Fail unless serialising ``subjects`` would write every triple of ``graph`` exactly once.

    Every subject with triples must either be in the list exactly once, or be a blank node the
    serialiser writes inline — one reached through inline blank nodes from a listed subject. A
    listed inline blank node does not count on its own: the serialiser skips it at the top
    level and writes it only where it is referenced.

    Args:
        graph: The graph the list will be serialised from.
        subjects: The subject list to check.

    Raises:
        IncompleteSubjectOrderError: Naming how many subjects are missing or repeated, and the
            first few of each.
    """
    duplicates = [s for s, count in Counter(subjects).items() if count > 1]

    inline = collect_inline_bnodes(graph)
    covered = {s for s in subjects if not (isinstance(s, BNode) and s in inline)}
    queue = list(covered)
    while queue:
        for obj in graph.objects(queue.pop()):
            if isinstance(obj, BNode) and obj in inline and obj not in covered:
                covered.add(obj)
                queue.append(obj)

    missing = [s for s in set(graph.subjects()) if s not in covered]
    if not missing and not duplicates:
        return

    problems = []
    if missing:
        problems.append(
            f"{len(missing)} subject(s) with triples would not be written: "
            f"{_examples(graph, missing)}"
        )
    if duplicates:
        problems.append(
            f"{len(duplicates)} subject(s) listed more than once: {_examples(graph, duplicates)}"
        )
    raise IncompleteSubjectOrderError("; ".join(problems))


def _examples(graph: Graph, nodes: list[Node]) -> str:
    """Name the first few of ``nodes``, in a stable order, for an error message."""
    names = sorted(format_term(graph, n) for n in nodes)
    shown = ", ".join(names[:_GUARD_EXAMPLES])
    more = len(names) - _GUARD_EXAMPLES
    return f"{shown} and {more} more" if more > 0 else shown


def _bnode_content_key(graph: Graph, bnode: BNode) -> str:
    """Sort key for a blank node from what it says, never from its label.

    The sorted predicate–object pairs of the node and of every blank node it reaches, with
    each blank node written ``[]``. Only nodes whose descriptions match once blank nodes are
    masked can tie, and only their relative order is left to chance.
    """

    def text(term: Node) -> str:
        return "[]" if isinstance(term, BNode) else format_term(graph, term)

    nodes: list[Node] = [bnode, *bnode_closure(graph, [bnode])]
    pairs = sorted(f"{text(p)} {text(o)}" for n in nodes for p, o in graph.predicate_objects(n))
    return "\n".join(pairs)
