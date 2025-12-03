"""Migration rule parsing and execution.

This module handles complex transformation rules using a SPARQL-like
pattern matching approach:

- Match patterns: Find triples matching a pattern
- Construct patterns: Create new triples from matches
- Delete patterns: Remove matched triples

This enables structural transformations like:
- Property splits (fullName → givenName + familyName)
- Type migrations (Company → Organisation)
- Value transformations
"""

import re
from dataclasses import dataclass, field
from typing import Any

from rdflib import Graph, URIRef, Literal, BNode, Namespace
from rdflib.namespace import RDF, RDFS, XSD
from rdflib.term import Node

from rdf_construct.merge.config import MigrationRule


@dataclass
class Binding:
    """A variable binding from pattern matching.

    Attributes:
        variable: Variable name (without ?)
        value: Bound RDF value
    """

    variable: str
    value: Node


@dataclass
class Match:
    """A single match result from pattern matching.

    Attributes:
        bindings: Dictionary of variable -> value bindings
        matched_triples: Triples that were matched
    """

    bindings: dict[str, Node] = field(default_factory=dict)
    matched_triples: list[tuple] = field(default_factory=list)


class PatternParser:
    """Parses simple SPARQL-like triple patterns.

    Supports patterns like:
    - "?s ex:fullName ?name"
    - "?s a ex:Company"

    Variables start with ?
    URIs can be full or prefixed (requires namespace context)
    """

    # Pattern for variables like ?s, ?name
    VARIABLE_PATTERN = re.compile(r"\?(\w+)")

    def __init__(self, namespaces: dict[str, Namespace] | None = None):
        """Initialize the parser.

        Args:
            namespaces: Prefix -> Namespace mapping for expanding CURIEs
        """
        self.namespaces = namespaces or {}

    def parse_pattern(self, pattern: str) -> tuple[Any, Any, Any]:
        """Parse a triple pattern into (subject, predicate, object).

        Args:
            pattern: Triple pattern string like "?s ex:hasName ?name"

        Returns:
            Tuple of (subject, predicate, object) where variables are
            represented as strings starting with ?
        """
        # Handle special "a" for rdf:type
        pattern = pattern.replace(" a ", f" {RDF.type} ")

        parts = pattern.strip().split(None, 2)
        if len(parts) != 3:
            raise ValueError(f"Invalid pattern (expected 3 parts): {pattern}")

        return (
            self._parse_term(parts[0]),
            self._parse_term(parts[1]),
            self._parse_term(parts[2]),
        )

    def _parse_term(self, term: str) -> Any:
        """Parse a single term from a pattern.

        Args:
            term: Term string (variable, URI, or literal)

        Returns:
            Parsed term: string for variables, URIRef for URIs, etc.
        """
        term = term.strip()

        # Variable
        if term.startswith("?"):
            return term  # Keep as string marker

        # Full URI in angle brackets
        if term.startswith("<") and term.endswith(">"):
            return URIRef(term[1:-1])

        # Already a URIRef (from pattern replacement like RDF.type)
        if isinstance(term, URIRef):
            return term
        if term.startswith("http://") or term.startswith("https://"):
            return URIRef(term)

        # Prefixed name
        if ":" in term:
            prefix, local = term.split(":", 1)
            if prefix in self.namespaces:
                return URIRef(str(self.namespaces[prefix]) + local)
            # If prefix not found, return as-is (may be handled later)
            return URIRef(term)

        # Literal (quoted string)
        if term.startswith('"') and term.endswith('"'):
            return Literal(term[1:-1])

        # Default: treat as local name (would need base URI)
        return term


class RuleEngine:
    """Executes transformation rules on RDF graphs.

    Supports:
    - Pattern matching with variable bindings
    - Triple construction from bindings
    - Simple value transformations (STRBEFORE, STRAFTER)
    """

    def __init__(self):
        """Initialize the rule engine."""
        self.parser = PatternParser()

    def set_namespaces(self, graph: Graph) -> None:
        """Update parser namespaces from a graph.

        Args:
            graph: Graph to extract namespaces from
        """
        self.parser.namespaces = {
            prefix: Namespace(str(ns))
            for prefix, ns in graph.namespace_manager.namespaces()
        }

    def apply_rule(self, graph: Graph, rule: MigrationRule) -> dict[str, int]:
        """Apply a transformation rule to a graph.

        Modifies the graph in place.

        Args:
            graph: Graph to transform
            rule: Transformation rule to apply

        Returns:
            Statistics: {"added": n, "removed": n, "instances": n}
        """
        self.set_namespaces(graph)

        if rule.type != "transform" or not rule.match:
            return {"added": 0, "removed": 0, "instances": 0}

        stats = {"added": 0, "removed": 0, "instances": 0}

        # Find all matches
        matches = self._find_matches(graph, rule.match)

        for match in matches:
            stats["instances"] += 1

            # Construct new triples
            if rule.construct:
                for construct_spec in rule.construct:
                    new_triples = self._construct_triples(
                        match, construct_spec, graph
                    )
                    for triple in new_triples:
                        graph.add(triple)
                        stats["added"] += 1

            # Delete matched triples if configured
            if rule.delete_matched:
                for triple in match.matched_triples:
                    graph.remove(triple)
                    stats["removed"] += 1

        return stats

    def _find_matches(self, graph: Graph, pattern_str: str) -> list[Match]:
        """Find all matches for a pattern in the graph.

        Args:
            graph: Graph to search
            pattern_str: Pattern string to match

        Returns:
            List of Match objects with bindings
        """
        try:
            pattern = self.parser.parse_pattern(pattern_str)
        except ValueError:
            return []

        matches: list[Match] = []

        # Build query pattern for graph iteration
        query_s = None if isinstance(pattern[0], str) else pattern[0]
        query_p = None if isinstance(pattern[1], str) else pattern[1]
        query_o = None if isinstance(pattern[2], str) else pattern[2]

        for s, p, o in graph.triples((query_s, query_p, query_o)):
            bindings: dict[str, Node] = {}

            # Check and bind each position
            if isinstance(pattern[0], str):  # Variable
                bindings[pattern[0][1:]] = s  # Remove ? prefix
            elif pattern[0] != s:
                continue

            if isinstance(pattern[1], str):
                bindings[pattern[1][1:]] = p
            elif pattern[1] != p:
                continue

            if isinstance(pattern[2], str):
                bindings[pattern[2][1:]] = o
            elif pattern[2] != o:
                continue

            matches.append(
                Match(bindings=bindings, matched_triples=[(s, p, o)])
            )

        return matches

    def _construct_triples(
        self,
        match: Match,
        construct_spec: dict[str, str],
        graph: Graph,
    ) -> list[tuple]:
        """Construct new triples from a match and specification.

        Args:
            match: Match with variable bindings
            construct_spec: Construction specification with pattern and optional bind
            graph: Graph for namespace resolution

        Returns:
            List of new triples to add
        """
        pattern_str = construct_spec.get("pattern", "")
        bind_expr = construct_spec.get("bind")

        try:
            pattern = self.parser.parse_pattern(pattern_str)
        except ValueError:
            return []

        # Substitute variables in pattern
        result_s = self._substitute_variable(pattern[0], match.bindings)
        result_p = self._substitute_variable(pattern[1], match.bindings)

        if bind_expr:
            # Evaluate bind expression
            result_o = self._evaluate_bind(bind_expr, match.bindings)
        else:
            result_o = self._substitute_variable(pattern[2], match.bindings)

        if result_s is None or result_p is None or result_o is None:
            return []

        return [(result_s, result_p, result_o)]

    def _substitute_variable(
        self, term: Any, bindings: dict[str, Node]
    ) -> Node | None:
        """Substitute a variable with its bound value.

        Args:
            term: Term to substitute (may be a variable string)
            bindings: Variable bindings

        Returns:
            Substituted value or None if variable not bound
        """
        if isinstance(term, str) and term.startswith("?"):
            var_name = term[1:]
            return bindings.get(var_name)
        return term

    def _evaluate_bind(
        self, expression: str, bindings: dict[str, Node]
    ) -> Node | None:
        """Evaluate a simple bind expression.

        Supports:
        - STRBEFORE(?var, 'delimiter') - substring before delimiter
        - STRAFTER(?var, 'delimiter') - substring after delimiter
        - Simple arithmetic with +, -, *, /

        Args:
            expression: Bind expression string
            bindings: Variable bindings

        Returns:
            Evaluated value or None
        """
        # Handle STRBEFORE
        strbefore_match = re.match(
            r"STRBEFORE\(\?(\w+),\s*['\"](.+)['\"]\)\s*AS\s*\?(\w+)",
            expression,
            re.IGNORECASE,
        )
        if strbefore_match:
            var_name = strbefore_match.group(1)
            delimiter = strbefore_match.group(2)
            if var_name in bindings:
                value = str(bindings[var_name])
                idx = value.find(delimiter)
                if idx >= 0:
                    return Literal(value[:idx])
            return None

        # Handle STRAFTER
        strafter_match = re.match(
            r"STRAFTER\(\?(\w+),\s*['\"](.+)['\"]\)\s*AS\s*\?(\w+)",
            expression,
            re.IGNORECASE,
        )
        if strafter_match:
            var_name = strafter_match.group(1)
            delimiter = strafter_match.group(2)
            if var_name in bindings:
                value = str(bindings[var_name])
                idx = value.find(delimiter)
                if idx >= 0:
                    return Literal(value[idx + len(delimiter) :])
            return None

        # Handle simple arithmetic: ((?var - n) * m / d) AS ?result
        arith_match = re.match(
            r"\(\(\?(\w+)\s*-\s*(\d+)\)\s*\*\s*(\d+)/(\d+)\)\s*AS\s*\?(\w+)",
            expression,
        )
        if arith_match:
            var_name = arith_match.group(1)
            sub = float(arith_match.group(2))
            mult = float(arith_match.group(3))
            div = float(arith_match.group(4))
            if var_name in bindings:
                try:
                    value = float(str(bindings[var_name]))
                    result = ((value - sub) * mult) / div
                    return Literal(result, datatype=XSD.decimal)
                except (ValueError, ZeroDivisionError):
                    return None
            return None

        return None
