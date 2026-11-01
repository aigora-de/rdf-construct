"""Keep the lexical form of every typed literal the tool reads and writes (#377).

By default rdflib normalises a typed literal's lexical form whenever one is constructed
(``rdflib.NORMALIZE_LITERALS``), and a parse constructs every literal it reads. So
``"007"^^xsd:integer`` became ``"7"``, and ``"1"^^xsd:boolean`` beside ``"true"^^xsd:boolean`` on
one subject and predicate became a single triple. RDF 1.1 says they are different terms with the
same value, and a triple store keeps both.

Switching normalisation off is not enough on its own. rdflib's Turtle serialiser, and the TriG and
N3 serialisers built on it, write a literal of a shorthand datatype (``xsd:integer``,
``xsd:boolean``, ``xsd:decimal``, ``xsd:double``, ``owl:rational``) bare, without checking that
the bare token reads back as the same term. ``"1"^^xsd:boolean`` was written as ``1``, which
reads back as ``"1"^^xsd:integer``; ``"007"^^xsd:integer`` was written as ``007``, which rdflib's
parser reads back as ``"7"`` whatever the flag says. So :func:`preserve_literal_forms` also swaps in
serialisers that write a literal bare only when that is faithful, and ``"lexical"^^datatype``
otherwise.

The CLI applies it once, around every command (``CrashHandlingGroup.main`` in ``cli.py``). A
program that imports ``rdf_construct`` keeps rdflib's defaults unless it uses the context manager
itself.

What it cannot do:

- **A bare number in a Turtle source** (``007``, ``+5``) is canonicalised by rdflib's parser
  either way, so "as the source wrote it" applies to quoted typed literals.
- **JSON-LD** is not guarded. rdflib's JSON-LD serialiser writes booleans and numbers from their
  Python value, so their lexical form is lost and equal-valued forms can still merge. JSON-LD
  input arrives as JSON values, so its forms are canonical anyway.
- ``longturtle`` is not guarded, because no command writes it.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import rdflib
from rdflib import plugin
from rdflib.plugins.serializers.n3 import N3Serializer
from rdflib.plugins.serializers.trig import TrigSerializer
from rdflib.plugins.serializers.turtle import _GEN_QNAME_FOR_DT, TurtleSerializer
from rdflib.serializer import Serializer
from rdflib.term import Literal, Node

if TYPE_CHECKING:
    from collections.abc import Iterator


def bare_form_is_faithful(literal: Literal, text: str) -> bool:
    """Say whether writing ``literal`` as the bare token ``text`` reads back as the same term.

    A bare token is faithful only when all three hold:

    - the literal is well-typed (an ill-typed one has no bare form);
    - its lexical form is the one rdflib normalises it to, because rdflib's parser canonicalises
      every bare numeric token, so a non-canonical form would not survive the read;
    - ``text`` is that lexical form, character for character. rdflib writes ``xsd:double`` from its
      value (``2e+01`` for ``"20.0"``) and adds ``.0`` to a whole ``xsd:decimal``, and neither
      reads back as the form written.

    "Canonical" here is rdflib's normalised form, not XSD's canonical representation. The two
    differ only for datatypes that are never written bare, such as an ``xsd:dateTime`` time zone.

    Args:
        literal: A literal with a datatype.
        text: The bare token rdflib's serialiser would write for it.

    Returns:
        True when the bare token is faithful, False when the literal must be written quoted, with
        its datatype.
    """
    if literal.datatype is None or literal.ill_typed:
        return False
    lexical = str(literal)
    canonical = Literal(lexical, datatype=literal.datatype, normalize=True)
    return str(canonical) == lexical and text == lexical


class _LiteralFormGuard(TurtleSerializer):
    """Writes a shorthand literal bare only when :func:`bare_form_is_faithful` says so."""

    def label(self, node: Node, position: int) -> str:
        """Return the text written for ``node``, quoting any literal whose bare form would change.

        Args:
            node: The term to write.
            position: Its position in the triple (subject, verb or object).

        Returns:
            rdflib's own label, unless it is a bare literal that would read back as a different
            term, in which case the quoted ``"lexical"^^datatype`` form.
        """
        text: str = super().label(node, position)
        if (
            isinstance(node, Literal)
            and not text.startswith(('"', "'"))
            and node.datatype is not None
            and not bare_form_is_faithful(node, text)
        ):
            # The same datatype callback rdflib's TurtleSerializer.label passes.
            quoted: str = node._literal_n3(
                use_plain=False,
                qname_callback=lambda dt: self.get_pname(dt, _GEN_QNAME_FOR_DT),
            )
            return quoted
        return text


class LiteralFormTurtleSerializer(_LiteralFormGuard):
    """rdflib's Turtle serialiser, writing every typed literal so it reads back unchanged."""


class LiteralFormTrigSerializer(_LiteralFormGuard, TrigSerializer):
    """rdflib's TriG serialiser, writing every typed literal so it reads back unchanged."""


class LiteralFormN3Serializer(_LiteralFormGuard, N3Serializer):
    """rdflib's N3 serialiser, writing every typed literal so it reads back unchanged."""


#: Every rdflib format name, alias included, whose serialiser is guarded.
GUARDED_FORMATS: dict[str, type[Serializer]] = {
    "turtle": LiteralFormTurtleSerializer,
    "ttl": LiteralFormTurtleSerializer,
    "text/turtle": LiteralFormTurtleSerializer,
    "trig": LiteralFormTrigSerializer,
    "application/trig": LiteralFormTrigSerializer,
    "n3": LiteralFormN3Serializer,
    "text/n3": LiteralFormN3Serializer,
}


def _register(name: str, cls: type[Any]) -> None:
    plugin.register(name, Serializer, cls.__module__, cls.__name__)


@contextmanager
def preserve_literal_forms() -> Iterator[None]:
    """Read and write typed literals in the lexical form they were given, inside the block.

    Sets ``rdflib.NORMALIZE_LITERALS`` to False and registers the guarded serialisers in
    :data:`GUARDED_FORMATS`. On leaving, by any path, both are put back as they were, so blocks
    nest and a library caller's rdflib is left as it was found.

    Both settings are process-wide, so this is not thread-safe: another thread parsing or writing
    during the block sees them too. The CLI runs one command in one thread, which is why it can
    apply this around everything it does.

    Example::

        from rdflib import Graph
        from rdf_construct.core import preserve_literal_forms

        with preserve_literal_forms():
            graph = Graph().parse("ontology.ttl")
            graph.serialize("copy.ttl", format="turtle")

    Yields:
        None.
    """
    saved_flag = rdflib.NORMALIZE_LITERALS
    saved = {name: plugin.get(name, Serializer) for name in GUARDED_FORMATS}
    try:
        rdflib.NORMALIZE_LITERALS = False
        for name, cls in GUARDED_FORMATS.items():
            _register(name, cls)
        yield
    finally:
        rdflib.NORMALIZE_LITERALS = saved_flag
        for name, cls in saved.items():
            _register(name, cls)
