"""Blank-node structures in a diff: whom each belongs to, and how it is written (#143).

``compare_graphs`` relabels both graphs with :func:`rdf_construct.core.blank_nodes.label_by_content`,
so a blank-node structure that both files state carries the same labels in each and drops out of
the set difference. What is left over is whole components: a changed structure leaves with every
triple that touches it, including the triple that refers to it. This module turns those triples
into something a reader can act on.

**Attribution.**

- A structure that a named subject refers to (``ex:Dog rdfs:subClassOf [ … ]``) belongs to that
  subject, and to each of them if several do.
- A structure that nothing refers to belongs to the named subject of its ``owl:annotatedSource``,
  ``rdf:subject`` or ``owl:sourceIndividual``: an axiom annotation, a reified statement or a
  negative property assertion is about that subject.
- Anything else, such as ``owl:AllDisjointClasses`` or a bare anonymous individual, has no owner
  and is listed on its own.

**Rendering is Turtle, never a parser's label.**

- A structure in which every blank node is referred to once is written inline as ``[ … ]``, with
  ``( … )`` for a well-formed ``rdf:List``.
- A structure with a blank node referred to twice, or with a cycle, cannot be written inline. It is
  written as statements, and only the nodes that need one get a label: ``_:s1``, ``_:s2`` and so
  on, numbered in content order, so the same structure reads the same in every run.

The renderer keeps its own stack rather than recursing, so a 5,000-cell chain that is not a
well-formed list costs no more per cell than a short one, and cannot exhaust Python's stack.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import NamedTuple, TypeAlias

from rdflib import RDF, Graph, URIRef
from rdflib.namespace import OWL
from rdflib.term import BNode, Node

from rdf_construct.core.blank_nodes import blank_node_components
from rdf_construct.core.serialiser import format_term

#: Predicates from a root structure to the named subject the structure is about.
OWNER_PREDICATES = (OWL.annotatedSource, RDF.subject, OWL.sourceIndividual)

Triple = tuple[Node, Node, Node]


class _Text(NamedTuple):
    """Finished text in the renderer's token stream.

    A plain ``str`` cannot mark it: rdflib's ``BNode`` and ``URIRef`` are ``str`` subclasses, so
    ``isinstance(token, str)`` would not tell text from a node still to be written.
    """

    text: str


#: A token is finished text, or a blank node still to be written.
_Token: TypeAlias = "_Text | Node"


@dataclass
class Pointer:
    """A triple from a named subject to a blank-node structure, with the structure written inline.

    Attributes:
        subject: The named subject that refers to the structure.
        predicate: The predicate it refers to it by.
        node: The structure's blank node, labelled by content.
        turtle: The structure, written inline as Turtle.
    """

    subject: URIRef
    predicate: URIRef
    node: BNode
    turtle: str


@dataclass
class Structures:
    """The changed blank-node structures on one side of a diff.

    Attributes:
        pointers: Triples from a named subject to a structure written inline.
        attached: Structures written as a whole, with the named subject each belongs to.
        ownerless: Structures that belong to no named subject.
    """

    pointers: list[Pointer] = field(default_factory=list)
    attached: list[tuple[URIRef, str]] = field(default_factory=list)
    ownerless: list[str] = field(default_factory=list)


def describe_structures(triples: Iterable[Triple], prefixes: Graph) -> Structures:
    """Attribute and render the blank-node structures that changed on one side of a diff.

    Args:
        triples: The changed triples that touch a blank node. Each component must be whole, as it
            is when both graphs were labelled by content.
        prefixes: The graph whose namespace bindings the Turtle is written with.

    Returns:
        The structures, each attributed and rendered.
    """
    holder = Graph()
    for triple in triples:
        holder.add(triple)

    renderer = _Renderer(prefixes)
    structures = Structures()
    for component in blank_node_components(holder):
        _describe_component(list(component), renderer, structures)
    return structures


class _Renderer:
    """Write the blank nodes of one component at a time as Turtle."""

    def __init__(self, prefixes: Graph) -> None:
        self._prefixes = prefixes
        self._terms: dict[Node, str] = {}
        self._out: dict[Node, list[tuple[Node, Node]]] = {}
        self._indegree: Counter[Node] = Counter()
        self._lists: dict[Node, list[Node] | None] = {}
        self.labels: dict[Node, str] = {}

    def begin(
        self,
        out: dict[Node, list[tuple[Node, Node]]],
        indegree: Counter[Node],
        labelled: set[Node],
    ) -> None:
        """Start on a component: its outgoing pairs, in-degrees and the nodes that need a label."""
        self._out = out
        self._indegree = indegree
        self._lists = {}
        ordered = sorted(labelled, key=str)
        self.labels = {node: f"_:s{place}" for place, node in enumerate(ordered, 1)}

    def term(self, node: Node) -> str:
        """Write a named term or literal, as the serialiser does."""
        text = self._terms.get(node)
        if text is None:
            text = format_term(self._prefixes, node)
            self._terms[node] = text
        return text

    def pairs(self, node: Node) -> list[tuple[Node, Node]]:
        """The predicate-object pairs of a blank node within the current component."""
        return self._out.get(node, [])

    def predicate(self, predicate: Node) -> str:
        return "a" if predicate == RDF.type else self.term(predicate)

    def object_key(self, node: Node) -> tuple[int, str]:
        return (1, str(node)) if isinstance(node, BNode) else (0, self.term(node))

    def inline(self, node: Node) -> str:
        """Write a node as an object: its label, a collection, or a ``[ … ]`` block."""
        return self._render([node])

    def body(self, node: Node) -> str:
        """Write a node's predicate-object list, for a statement with the node as its subject."""
        return self._render(self._body(node))

    def _render(self, tokens: list[_Token]) -> str:
        """Write a sequence of tokens, expanding each blank node in place.

        This keeps its own stack instead of recursing, for two reasons. A chain of cells that is
        not a well-formed list nests one ``[ … ]`` inside the next, so recursion would pass
        Python's limit of about 1,000 frames on a long one. And building each node's text from its
        children's would copy the inner text at every level, which is quadratic in the depth. Here
        each node pushes its parts back **in reverse**, so they come off the stack in writing
        order, and every piece of text is appended exactly once.
        """
        parts: list[str] = []
        stack = list(reversed(tokens))
        while stack:
            token = stack.pop()
            if isinstance(token, _Text):
                parts.append(token.text)
                continue
            if token in self.labels:
                parts.append(self.labels[token])
                continue
            items = self._list_items(token)
            if items is not None:
                expanded: list[_Token] = [_Text("(")]
                for item in items:
                    expanded.append(_Text(" "))
                    expanded.append(item if isinstance(item, BNode) else _Text(self.term(item)))
                expanded.append(_Text(" )"))
                stack.extend(reversed(expanded))
                continue
            if not self.pairs(token):
                parts.append("[]")
                continue
            stack.extend(reversed([_Text("[ "), *self._body(token), _Text(" ]")]))
        return "".join(parts)

    def _body(self, node: Node) -> list[_Token]:
        groups: dict[Node, list[Node]] = defaultdict(list)
        for predicate, obj in self.pairs(node):
            groups[predicate].append(obj)
        predicates = sorted(groups, key=lambda p: (p != RDF.type, self.term(p)))

        tokens: list[_Token] = []
        for i, predicate in enumerate(predicates):
            if i:
                tokens.append(_Text(" ; "))
            tokens.append(_Text(f"{self.predicate(predicate)} "))
            for j, obj in enumerate(sorted(groups[predicate], key=self.object_key)):
                if j:
                    tokens.append(_Text(" , "))
                tokens.append(obj if isinstance(obj, BNode) else _Text(self.term(obj)))
        return tokens

    def _list_items(self, head: Node) -> list[Node] | None:
        """The members of a well-formed list starting at ``head``, or None if it is not one.

        A cell must have exactly one ``rdf:first`` and one ``rdf:rest`` and nothing else, must be
        referred to only by the cell before it, and the chain must end at ``rdf:nil``. When a
        chain fails, every cell before the failure fails as a head too, and is remembered, so a
        long chain is walked once.
        """
        if head in self._lists:
            return self._lists[head]

        chain: list[Node] = []
        members: list[Node] = []
        node: Node = head
        seen: set[Node] = set()
        while True:
            if node in seen or node in self.labels:
                break
            if node != head and self._indegree[node] != 1:
                break
            pairs = self.pairs(node)
            values = dict(pairs)
            if len(pairs) != 2 or set(values) != {RDF.first, RDF.rest}:
                break
            seen.add(node)
            chain.append(node)
            members.append(values[RDF.first])
            rest = values[RDF.rest]
            if rest == RDF.nil:
                self._lists[head] = members
                return members
            if not isinstance(rest, BNode) or self._lists.get(rest, ()) is None:
                break
            node = rest

        for cell in chain:
            self._lists[cell] = None
        self._lists[head] = None
        return None


def _describe_component(triples: list[Triple], renderer: _Renderer, structures: Structures) -> None:
    out: dict[Node, list[tuple[Node, Node]]] = defaultdict(list)
    indegree: Counter[Node] = Counter()
    refs: list[Triple] = []
    nodes: set[Node] = set()
    for s, p, o in triples:
        if isinstance(s, BNode):
            nodes.add(s)
            out[s].append((p, o))
        else:
            refs.append((s, p, o))
        if isinstance(o, BNode):
            nodes.add(o)
            indegree[o] += 1

    roots = sorted((node for node in nodes if indegree[node] == 0), key=str)
    labelled = {node for node in nodes if indegree[node] > 1}

    # A cycle that nothing outside it refers to is reached by none of the starts: label one node.
    reached = _reach([o for _, _, o in refs] + roots + sorted(labelled, key=str), out, labelled)
    for node in sorted(nodes - reached, key=str):
        if node not in reached:
            labelled.add(node)
            reached |= _reach([node], out, labelled)

    renderer.begin(out, indegree, labelled)

    owners = sorted({s for s, _, _ in refs if isinstance(s, URIRef)}, key=str)
    if not owners:
        owners = sorted(
            {
                o
                for root in roots
                for p, o in out[root]
                if p in OWNER_PREDICATES and isinstance(o, URIRef)
            },
            key=str,
        )

    if not labelled:
        for s, p, o in refs:
            if isinstance(s, URIRef) and isinstance(p, URIRef) and isinstance(o, BNode):
                structures.pointers.append(Pointer(s, p, o, renderer.inline(o)))
        texts = [renderer.inline(root) for root in roots]
    else:
        texts = [_block(refs, roots, renderer)]

    for text in texts:
        if owners:
            structures.attached.extend((owner, text) for owner in owners)
        else:
            structures.ownerless.append(text)


def _reach(
    starts: list[Node], out: dict[Node, list[tuple[Node, Node]]], labelled: set[Node]
) -> set[Node]:
    """The blank nodes written from ``starts``: each start, and every node inlined below one."""
    reached: set[Node] = set()
    stack = [node for node in starts if isinstance(node, BNode)]
    while stack:
        node = stack.pop()
        if node in reached:
            continue
        reached.add(node)
        for _, obj in out.get(node, []):
            if isinstance(obj, BNode) and obj not in labelled and obj not in reached:
                stack.append(obj)
    return reached


def _block(refs: list[Triple], roots: list[Node], renderer: _Renderer) -> str:
    """Write a structure that cannot be inlined as Turtle statements, labelling only what must be."""
    statements: list[str] = []
    for s, p, o in sorted(
        refs, key=lambda t: (renderer.term(t[0]), renderer.term(t[1]), renderer.object_key(t[2]))
    ):
        statements.append(f"{renderer.term(s)} {renderer.predicate(p)} {renderer.inline(o)} .")
    for node, label in sorted(renderer.labels.items(), key=lambda item: int(item[1][3:])):
        if renderer.pairs(node):
            statements.append(f"{label} {renderer.body(node)} .")
    for root in roots:
        if root not in renderer.labels:
            statements.append(f"{renderer.inline(root)} .")
    return " ".join(statements)
