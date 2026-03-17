"""Tests for inline blank node serialisation in the order command.

Verifies that blank nodes with exactly one incoming arc are written using
Turtle's anonymous ``[ \u2026 ]`` syntax, matching authorial intent and
preserving readability.  Blank nodes referenced by more than one triple
should continue to be emitted as top-level ``_:bN`` stubs.

Relates to: #51
"""

import pytest
from textwrap import dedent

from rdflib import Graph, BNode, Namespace, RDF, Literal
from rdflib.namespace import RDFS
from rdflib.compare import isomorphic

from rdf_construct.core.serialiser import collect_inline_bnodes, serialise_turtle


# ---------------------------------------------------------------------------
# Shared namespace
# ---------------------------------------------------------------------------

EX = Namespace("http://example.org/ont#")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(turtle: str) -> Graph:
    """Parse a Turtle string into a fresh graph."""
    g = Graph()
    g.parse(data=dedent(turtle), format="turtle")
    return g


def _serialise(graph: Graph, subjects: list, tmp_path) -> str:
    """Serialise *subjects* to a temp file and return the file contents."""
    out = tmp_path / "output.ttl"
    serialise_turtle(graph, subjects, out)
    return out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests for collect_inline_bnodes()
# ---------------------------------------------------------------------------


class TestCollectInlineBnodes:
    """Unit tests for the collect_inline_bnodes() helper function."""

    def test_single_arc_bnode_is_inline_candidate(self) -> None:
        """A blank node referenced by exactly one triple is eligible for inlining."""
        g = Graph()
        g.bind("ex", EX)
        bn = BNode()
        g.add((EX.Thing, EX.hasName, bn))
        g.add((bn, RDF.type, EX.Name))
        g.add((bn, EX.value, Literal("Alice")))

        inline = collect_inline_bnodes(g)

        assert bn in inline

    def test_multi_arc_bnode_is_not_inline_candidate(self) -> None:
        """A blank node referenced by more than one triple must not be inlined."""
        g = Graph()
        g.bind("ex", EX)
        bn = BNode()
        g.add((EX.Thing1, EX.hasName, bn))
        g.add((EX.Thing2, EX.hasName, bn))  # second incoming arc
        g.add((bn, RDF.type, EX.Name))
        g.add((bn, EX.value, Literal("Shared")))

        inline = collect_inline_bnodes(g)

        assert bn not in inline

    def test_reification_bnode_is_not_inline_candidate(self) -> None:
        """A blank node that is the subject of rdf:type rdf:Statement must not be inlined."""
        g = Graph()
        g.bind("ex", EX)
        stmt = BNode()
        g.add((stmt, RDF.type, RDF.Statement))
        g.add((stmt, RDF.subject, EX.Thing))
        g.add((stmt, RDF.predicate, RDFS.label))
        g.add((stmt, RDF.object, Literal("A thing")))
        # Only one incoming arc \u2014 but it's a reification stub
        g.add((EX.Thing, EX.reifiedAs, stmt))

        inline = collect_inline_bnodes(g)

        assert stmt not in inline

    def test_empty_graph_returns_empty_set(self) -> None:
        """An empty graph should yield no inline candidates."""
        g = Graph()
        assert collect_inline_bnodes(g) == set()

    def test_graph_without_bnodes_returns_empty_set(self) -> None:
        """A graph with only named nodes should yield no inline candidates."""
        g = Graph()
        g.bind("ex", EX)
        g.add((EX.Dog, RDFS.subClassOf, EX.Animal))
        assert collect_inline_bnodes(g) == set()

    def test_multiple_independent_bnodes_all_inline(self) -> None:
        """Multiple unconnected single-arc bnodes should all be inline candidates."""
        g = Graph()
        g.bind("ex", EX)
        bn1, bn2, bn3 = BNode(), BNode(), BNode()
        g.add((EX.Thing, EX.hasName, bn1))
        g.add((bn1, EX.value, Literal("Alice")))
        g.add((EX.Thing, EX.hasAddress, bn2))
        g.add((bn2, EX.street, Literal("123 Main St")))
        g.add((EX.Thing, EX.hasContact, bn3))
        g.add((bn3, EX.email, Literal("alice@example.org")))

        inline = collect_inline_bnodes(g)

        assert bn1 in inline
        assert bn2 in inline
        assert bn3 in inline

    def test_nested_bnodes_both_inline(self) -> None:
        """A bnode that is the sole object of another bnode should also be inline."""
        g = Graph()
        g.bind("ex", EX)
        outer = BNode()
        inner = BNode()
        g.add((EX.Thing, EX.hasAddress, outer))
        g.add((outer, RDF.type, EX.Address))
        g.add((outer, EX.location, inner))  # outer -> inner: one arc
        g.add((inner, EX.postCode, Literal("SW1A 1AA")))

        inline = collect_inline_bnodes(g)

        assert outer in inline
        assert inner in inline


# ---------------------------------------------------------------------------
# Tests for serialise_turtle() inline rendering
# ---------------------------------------------------------------------------


class TestInlineBnodeSerialisation:
    """Integration tests: blank nodes rendered inline in serialise_turtle()."""

    def test_single_inline_bnode_no_stub(self, tmp_path) -> None:
        """A single-arc bnode should not appear as a top-level subject."""
        g = Graph()
        g.bind("ex", EX)
        g.bind("rdfs", RDFS)
        bn = BNode()
        g.add((EX.Thing, EX.hasName, bn))
        g.add((bn, RDF.type, EX.Name))
        g.add((bn, EX.value, Literal("Alice")))

        content = _serialise(g, [EX.Thing], tmp_path)

        # The inline blank node must appear using [ \u2026 ] syntax
        assert "[" in content
        assert "]" in content
        # The bnode must NOT appear as a standalone top-level subject block
        lines = content.splitlines()
        top_level = [
            line for line in lines
            if line
            and not line.startswith(" ")
            and not line.startswith("PREFIX ")
            and line.strip()
        ]
        assert not any(line.startswith("_:") for line in top_level)

    def test_inline_bnode_syntax_structure(self, tmp_path) -> None:
        """Inline blank node must be written as `ex:pred [ \u2026 ]`, not a bare ref."""
        turtle_in = """
            @prefix ex: <http://example.org/ont#> .

            ex:Thing ex:hasName [
                a ex:Name ;
                ex:value "Alice" ;
            ] .
        """
        g = _parse(turtle_in)
        content = _serialise(g, [EX.Thing], tmp_path)

        assert "ex:hasName" in content
        assert "[" in content
        assert "ex:Name" in content
        assert "Alice" in content

    def test_multiple_inline_bnodes(self, tmp_path) -> None:
        """Multiple inline blank nodes on the same subject are all rendered inline."""
        turtle_in = """
            @prefix ex: <http://example.org/ont#> .

            ex:Thing
                ex:hasName [ a ex:Name ; ex:value "Alice" ] ;
                ex:hasAddress [ a ex:Address ; ex:street "123 Main St" ] .
        """
        g = _parse(turtle_in)
        content = _serialise(g, [EX.Thing], tmp_path)

        # Both bnodes inline \u2014 no top-level _: stubs
        lines = content.splitlines()
        assert not any(
            line.strip().startswith("_:") and not line.startswith(" ")
            for line in lines
        )
        assert content.count("[") >= 2
        assert content.count("]") >= 2

    def test_nested_inline_bnodes(self, tmp_path) -> None:
        """Nested single-arc bnodes are rendered as nested [ [ \u2026 ] ] blocks."""
        turtle_in = """
            @prefix ex: <http://example.org/ont#> .

            ex:Thing ex:hasAddress [
                a ex:Address ;
                ex:location [
                    ex:postCode "SW1A 1AA" ;
                ] ;
            ] .
        """
        g = _parse(turtle_in)
        content = _serialise(g, [EX.Thing], tmp_path)

        assert content.count("[") >= 2
        assert content.count("]") >= 2
        assert "ex:Address" in content
        assert "SW1A 1AA" in content
        lines = content.splitlines()
        assert not any(
            line.strip().startswith("_:") and not line.startswith(" ")
            for line in lines
        )

    def test_shared_bnode_remains_top_level_stub(self, tmp_path) -> None:
        """A bnode referenced by two triples must remain a top-level stub."""
        g = Graph()
        g.bind("ex", EX)
        shared = BNode()
        g.add((EX.Thing1, EX.hasName, shared))
        g.add((EX.Thing2, EX.hasName, shared))  # second arc
        g.add((shared, EX.value, Literal("Shared")))

        content = _serialise(g, [EX.Thing1, EX.Thing2, shared], tmp_path)

        # The shared bnode must be emitted as a top-level subject block
        lines = content.splitlines()
        non_indented = [
            line for line in lines
            if line and not line.startswith(" ") and line.strip()
        ]
        top_level_bnodes = [
            line for line in non_indented
            if not line.startswith("PREFIX ") and not line.startswith("ex:")
        ]
        assert len(top_level_bnodes) >= 1

    def test_reification_stub_remains_top_level(self, tmp_path) -> None:
        """A reification bnode (rdf:type rdf:Statement) must stay top-level."""
        g = Graph()
        g.bind("ex", EX)
        g.bind("rdf", RDF)
        stmt = BNode()
        g.add((stmt, RDF.type, RDF.Statement))
        g.add((stmt, RDF.subject, EX.Thing))
        g.add((stmt, RDF.predicate, RDFS.label))
        g.add((stmt, RDF.object, Literal("A thing")))
        g.add((EX.Thing, EX.reifiedAs, stmt))

        content = _serialise(g, [EX.Thing, stmt], tmp_path)

        assert "rdf:Statement" in content
        assert content.find("rdf:Statement") != -1
        assert content.find("ex:Thing") != -1


# ---------------------------------------------------------------------------
# Round-trip isomorphism tests
# ---------------------------------------------------------------------------


class TestInlineBnodeRoundTrip:
    """Verify that parse(serialise(parse(x))) is isomorphic to parse(x)."""

    def test_round_trip_single_inline(self, tmp_path) -> None:
        """Single inline bnode: round-trip preserves graph semantics."""
        source = """
            @prefix ex: <http://example.org/ont#> .

            ex:Thing ex:hasName [
                a ex:Name ;
                ex:value "Alice" ;
            ] .
        """
        g_orig = _parse(source)
        content = _serialise(g_orig, [EX.Thing], tmp_path)

        g_rt = _parse(content)
        assert isomorphic(g_orig, g_rt), (
            f"Round-trip produced a non-isomorphic graph.\nOutput was:\n{content}"
        )

    def test_round_trip_multiple_inline(self, tmp_path) -> None:
        """Multiple inline bnodes: round-trip preserves graph semantics."""
        source = """
            @prefix ex: <http://example.org/ont#> .

            ex:Thing
                ex:hasName [ a ex:Name ; ex:value "Alice" ] ;
                ex:hasAddress [ a ex:Address ; ex:street "123 Main St" ; ex:city "London" ] .
        """
        g_orig = _parse(source)
        content = _serialise(g_orig, [EX.Thing], tmp_path)

        g_rt = _parse(content)
        assert isomorphic(g_orig, g_rt), (
            f"Round-trip produced a non-isomorphic graph.\nOutput was:\n{content}"
        )

    def test_round_trip_nested_inline(self, tmp_path) -> None:
        """Nested inline bnodes: round-trip preserves graph semantics."""
        source = """
            @prefix ex: <http://example.org/ont#> .

            ex:Thing ex:hasAddress [
                a ex:Address ;
                ex:location [
                    ex:postCode "SW1A 1AA" ;
                ] ;
            ] .
        """
        g_orig = _parse(source)
        content = _serialise(g_orig, [EX.Thing], tmp_path)

        g_rt = _parse(content)
        assert isomorphic(g_orig, g_rt), (
            f"Round-trip produced a non-isomorphic graph.\nOutput was:\n{content}"
        )

    def test_round_trip_shared_bnode(self, tmp_path) -> None:
        """Shared bnode (multi-arc): round-trip preserves graph semantics."""
        g_orig = Graph()
        g_orig.bind("ex", EX)
        shared = BNode()
        g_orig.add((EX.Thing1, EX.hasName, shared))
        g_orig.add((EX.Thing2, EX.hasName, shared))
        g_orig.add((shared, EX.value, Literal("Shared")))

        content = _serialise(g_orig, [EX.Thing1, EX.Thing2, shared], tmp_path)
        g_rt = _parse(content)

        assert isomorphic(g_orig, g_rt), (
            f"Round-trip produced a non-isomorphic graph.\nOutput was:\n{content}"
        )


# ---------------------------------------------------------------------------
# Predicate ordering inside inline blank nodes
# ---------------------------------------------------------------------------


class TestInlineBnodePredicateOrdering:
    """Predicate ordering must apply inside inline blank node blocks."""

    def test_rdf_type_first_inside_inline(self, tmp_path) -> None:
        """rdf:type should appear first within an inline blank node block."""
        source = """
            @prefix ex: <http://example.org/ont#> .

            ex:Thing ex:hasName [
                ex:value "Alice" ;
                a ex:Name ;
            ] .
        """
        g = _parse(source)
        content = _serialise(g, [EX.Thing], tmp_path)

        # Within the inline block, 'a' (rdf:type) must precede 'ex:value'
        type_pos = content.find(" a ")
        value_pos = content.find("ex:value")
        assert type_pos != -1, "rdf:type shorthand 'a' not found in output"
        assert value_pos != -1, "ex:value not found in output"
        assert type_pos < value_pos, (
            "rdf:type should appear before ex:value inside the inline block"
        )
