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

A pattern is three terms, written as in Turtle: ``?name`` is a variable; ``<…>``, a full IRI or a
CURIE is an IRI; ``a`` in the predicate position is ``rdf:type``; ``"…"``, ``"…"@en``,
``"…"^^xsd:integer``, a bare number and ``true``/``false`` are literals. ``_:x`` is allowed in a
construct pattern only, where it is a fresh blank node for each match. A match matches by RDF term
equality, so ``40`` matches ``"40"^^xsd:integer`` and not ``"40"`` or ``"40.0"^^xsd:decimal``.

A CURIE resolves strictly, against the core five prefixes (rdf, rdfs, owl, xsd, xml) and the
sources the caller gives (`resolve_rules`), and nothing else (#492). The ``merge`` command's
sources are the prefixes each data file declares and the config's ``preferred_prefixes``; a
library caller that gives a graph's own map gives whatever that graph binds, which for a default
``Graph()`` includes rdflib's table. A rule that cannot be read raises `RuleError` before any
graph is changed.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import MAX_EMAX, MAX_PREC, MIN_EMIN, Decimal, Inexact, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

from rdflib import BNode, Graph, Literal, Namespace, URIRef, Variable
from rdflib.namespace import RDF, XSD
from rdflib.term import Node
from rdflib.util import from_n3

from rdf_construct.core.utils import CurieError, extract_prefix_map, resolve_curie
from rdf_construct.merge.config import MigrationRule
from rdf_construct.refactor.config import AmbiguousCurieError, resolve_term

# Bound for every rule, whatever the data declares; a source that binds one of them differently
# is a disagreement, refused like any other (#492)
CORE_PREFIXES: dict[str, str] = {
    "rdf": str(RDF),
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": str(XSD),
    "xml": "http://www.w3.org/XML/1998/namespace",
}

# The datatypes an arithmetic bind computes on: xsd:decimal, xsd:double, xsd:float and the
# integer types derived from xsd:decimal. Anything else is a type error in SPARQL, so its match
# is left unchanged (#492)
_NUMERIC_TYPES = frozenset(
    XSD[name]
    for name in (
        "decimal",
        "double",
        "float",
        "integer",
        "nonPositiveInteger",
        "negativeInteger",
        "long",
        "int",
        "short",
        "byte",
        "nonNegativeInteger",
        "unsignedLong",
        "unsignedInt",
        "unsignedShort",
        "unsignedByte",
        "positiveInteger",
    )
)

# Significant digits kept when a division does not terminate: Python's default
_DIVISION_DIGITS = 28


def parse_declaring(graph: Graph, source: str | Path, **parse_args: Any) -> dict[str, str]:
    """Parse ``source`` into ``graph``, and return every prefix the source declares.

    rdflib keeps one prefix for each namespace, so a file that declares ``xs:`` for XSD loses
    ``xsd:``, and one that declares ``ex:`` and ``ont:`` for one namespace loses one of them.
    A rule may use any prefix the file declares, so the declarations are recorded as rdflib
    reads them (#492).

    Args:
        graph: The graph to parse into.
        source: The file to parse.
        **parse_args: Passed to `Graph.parse`.

    Returns:
        Each prefix the source declares, with its namespace; a prefix declared twice keeps its
        last namespace, as Turtle reads it.
    """
    declared: dict[str, str] = {}
    manager = graph.namespace_manager
    bind = manager.bind

    def recording(prefix: str | None, namespace: Any, *args: Any, **kwargs: Any) -> None:
        if prefix is not None:
            declared[prefix] = str(namespace)
        bind(prefix, namespace, *args, **kwargs)

    manager.bind = recording  # type: ignore[method-assign]
    try:
        graph.parse(source.as_posix() if isinstance(source, Path) else source, **parse_args)
    finally:
        del manager.bind
    return declared


class RuleError(ValueError):
    """A migration rule that cannot be read, so nothing it would do can be trusted (#492).

    Attributes:
        index: The rule's position in the rule list, counting from 0.
        description: The rule's ``description``, possibly empty.
    """

    def __init__(self, index: int, description: str, detail: str) -> None:
        self.index = index
        self.description = description
        named = f" ({description!r})" if description else ""
        super().__init__(f"migration rule {index + 1}{named}: {detail}")


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
    matched_triples: list[tuple[Node, Node, Node]] = field(default_factory=list)


@dataclass(frozen=True)
class Bind:
    """A parsed ``bind:`` expression.

    Attributes:
        function: ``strbefore``, ``strafter`` or ``arithmetic``.
        variable: The variable read, without ``?``.
        target: The variable bound (``AS ?target``), without ``?``.
        delimiter: For ``strbefore`` and ``strafter``.
        subtract: For ``arithmetic``: ``((?v - subtract) * multiply / divide)``.
        multiply: For ``arithmetic``.
        divide: For ``arithmetic``; never 0.
    """

    function: str
    variable: str
    target: str
    delimiter: str = ""
    subtract: Decimal = Decimal(0)
    multiply: Decimal = Decimal(1)
    divide: Decimal = Decimal(1)


@dataclass(frozen=True)
class Construct:
    """One parsed ``construct:`` entry.

    Attributes:
        pattern: Subject, predicate and object; variables are `rdflib.Variable`.
        bind: The entry's ``bind:``, which gives the object's value, if it has one.
    """

    pattern: tuple[Node, Node, Node]
    bind: Bind | None = None


@dataclass(frozen=True)
class ResolvedRule:
    """A migration rule whose terms are all resolved, and which has passed every check.

    Attributes:
        rule: The rule as given.
        index: Its position in the rule list, counting from 0.
        match: For ``transform``: the match pattern.
        constructs: For ``transform``: the construct entries.
        from_iri: For ``rename``: the IRI renamed.
        to_iri: For ``rename``: the IRI it becomes.
    """

    rule: MigrationRule
    index: int
    match: tuple[Node, Node, Node] | None = None
    constructs: tuple[Construct, ...] = ()
    from_iri: URIRef | None = None
    to_iri: URIRef | None = None

    @property
    def label(self) -> str:
        """The name the migration summary gives the rule: its description, else its type."""
        return self.rule.description or self.rule.type

    @property
    def name(self) -> str:
        """The rule as a finding names it: its number, as `RuleError` gives it, and its label."""
        return f"migration rule {self.index + 1} ({self.label!r})"


# A quoted literal with its tag or datatype is one term, whatever it contains; anything else
# runs to the next space
_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"(?:@[A-Za-z][A-Za-z0-9-]*|\^\^\S+)?|\S+')
_QUOTED = re.compile(r'^("(?:[^"\\]|\\.)*")(?:@([A-Za-z][A-Za-z0-9-]*)|\^\^(\S+))?$')
_VARIABLE = re.compile(r"^\?(\w+)$")
_INTEGER = re.compile(r"^[+-]?\d+$")
_DECIMAL = re.compile(r"^[+-]?\d*\.\d+$")
_DOUBLE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)[eE][+-]?\d+$")

_STRBEFORE = re.compile(r"^STRBEFORE\(\?(\w+),\s*['\"](.+)['\"]\)\s*AS\s*\?(\w+)$", re.IGNORECASE)
_STRAFTER = re.compile(r"^STRAFTER\(\?(\w+),\s*['\"](.+)['\"]\)\s*AS\s*\?(\w+)$", re.IGNORECASE)
_ARITHMETIC = re.compile(r"^\(\(\?(\w+)\s*-\s*(\d+)\)\s*\*\s*(\d+)/(\d+)\)\s*AS\s*\?(\w+)$")


class PatternParser:
    """Parses simple SPARQL-like triple patterns.

    Supports patterns like:
    - "?s ex:fullName ?name"
    - "?s a ex:Company"
    - '?s ex:note "hi"@en'

    Variables start with ?, and are returned as `rdflib.Variable`. An IRI is written in full, in
    angle brackets, or as a CURIE whose prefix is bound; a CURIE whose prefix is not bound raises
    `CurieError` (#492).
    """

    def __init__(
        self,
        namespaces: Mapping[str, str | Namespace] | None = None,
        resolve: Callable[[str], URIRef] | None = None,
    ):
        """Initialize the parser.

        Args:
            namespaces: Prefix -> namespace mapping for expanding CURIEs; the whole of what a
                prefix can mean
            resolve: Resolves an IRI or a CURIE, in place of ``namespaces``; it raises
                `CurieError` (or another `ValueError`) for one it cannot resolve
        """
        self.namespaces: Mapping[str, str | Namespace] = namespaces or {}
        self._resolve = resolve

    def resolve(self, text: str) -> URIRef:
        """Resolve an IRI or a CURIE, strictly.

        Raises:
            CurieError: If the text is not an IRI and its prefix is not bound.
        """
        if self._resolve is not None:
            return self._resolve(text)
        return resolve_curie({p: str(ns) for p, ns in self.namespaces.items()}, text)

    def parse_pattern(self, pattern: str) -> tuple[Any, Any, Any]:
        """Parse a triple pattern into (subject, predicate, object).

        Args:
            pattern: Triple pattern string like "?s ex:hasName ?name"

        Returns:
            Tuple of (subject, predicate, object) where variables are `rdflib.Variable` (named
            without the ``?``) and ``_:x`` is a `BNode` marker

        Raises:
            ValueError: If the pattern is not three terms, or a term cannot be read; a
                `CurieError` if a prefix is not bound
        """
        parts = _TOKEN.findall(pattern)
        if len(parts) != 3:
            raise ValueError(f"pattern {pattern!r} is not three terms (found {len(parts)})")

        return (
            self._parse_term(parts[0]),
            RDF.type if parts[1] == "a" else self._parse_term(parts[1]),
            self._parse_term(parts[2]),
        )

    def _parse_term(self, term: str) -> Any:
        """Parse a single term from a pattern.

        Args:
            term: Term string (variable, IRI, CURIE, blank node or literal)

        Returns:
            `Variable`, `URIRef`, `BNode` or `Literal`

        Raises:
            ValueError: If the term cannot be read; a `CurieError` if a prefix is not bound
        """
        term = term.strip()

        if term.startswith("?"):
            variable = _VARIABLE.match(term)
            if not variable:
                raise ValueError(f"{term!r} is not a variable: write ?name")
            return Variable(variable.group(1))

        if term.startswith("_:"):
            if len(term) == 2:
                raise ValueError("'_:' is not a blank node: write _:name")
            return BNode(term[2:])

        if term.startswith('"'):
            return self._parse_literal(term)
        if _INTEGER.match(term):
            return Literal(term, datatype=XSD.integer)
        if _DECIMAL.match(term):
            return Literal(term, datatype=XSD.decimal)
        if _DOUBLE.match(term):
            return Literal(term, datatype=XSD.double)
        if term in ("true", "false"):
            return Literal(term, datatype=XSD.boolean)

        return self.resolve(term)

    def _parse_literal(self, term: str) -> Literal:
        """Parse a quoted literal, with its language tag or datatype if it has one."""
        quoted = _QUOTED.match(term)
        if not quoted:
            raise ValueError(f"{term!r} is not a literal: a quote is not closed")
        lexical, language, datatype = quoted.groups()
        try:
            text = str(from_n3(lexical))
        except Exception as e:
            raise ValueError(f"{term!r} is not a literal: {e}") from e
        if language:
            return Literal(text, lang=language)
        if datatype:
            return Literal(text, datatype=self.resolve(datatype))
        return Literal(text)


def parse_bind(expression: str) -> Bind:
    """Parse a ``bind:`` expression in one of the three forms rules support.

    Raises:
        ValueError: If it is none of them, or it divides by 0.
    """
    text = expression.strip()
    for function, regex in (("strbefore", _STRBEFORE), ("strafter", _STRAFTER)):
        found = regex.match(text)
        if found:
            return Bind(function, found.group(1), found.group(3), delimiter=found.group(2))
    found = _ARITHMETIC.match(text)
    if found:
        if int(found.group(4)) == 0:
            raise ValueError(f"bind {expression!r} divides by 0")
        return Bind(
            "arithmetic",
            found.group(1),
            found.group(5),
            subtract=Decimal(found.group(2)),
            multiply=Decimal(found.group(3)),
            divide=Decimal(found.group(4)),
        )
    raise ValueError(
        f"bind {expression!r} is not a form rules support: STRBEFORE(?var, 'x') AS ?v, "
        f"STRAFTER(?var, 'x') AS ?v, or ((?var - n) * m/d) AS ?v"
    )


def _variables(pattern: tuple[Node, Node, Node]) -> set[str]:
    return {str(term) for term in pattern if isinstance(term, Variable)}


def _check_positions(pattern: tuple[Node, Node, Node], text: str) -> None:
    """Refuse a pattern no triple can have: a literal subject, or a predicate that is not an IRI."""
    subject, predicate, _ = pattern
    if isinstance(subject, Literal):
        raise ValueError(f"pattern {text!r} has a literal as its subject")
    if not isinstance(predicate, URIRef | Variable):
        raise ValueError(f"pattern {text!r} has a predicate that is not an IRI")


def _resolve_one(rule: MigrationRule, index: int, parser: PatternParser) -> ResolvedRule:
    """Resolve and check one rule.

    Raises:
        ValueError: The rule's problem, which `resolve_rules` names the rule in.
    """
    if rule.type == "rename":
        if not rule.from_uri or not rule.to_uri:
            missing = " and ".join(
                k for k, v in (("from", rule.from_uri), ("to", rule.to_uri)) if not v
            )
            raise ValueError(f"a rename rule needs from: and to:, and has no {missing}:")
        return ResolvedRule(
            rule,
            index,
            from_iri=parser.resolve(str(rule.from_uri)),
            to_iri=parser.resolve(str(rule.to_uri)),
        )

    if rule.type != "transform":
        raise ValueError(f"type {rule.type!r} is not 'rename' or 'transform'")
    if not rule.match:
        raise ValueError("a transform rule needs match:")

    match = parser.parse_pattern(rule.match)
    _check_positions(match, rule.match)
    if any(isinstance(term, BNode) for term in match):
        raise ValueError(
            f"match {rule.match!r} has a blank node, which can never equal one in the data: "
            f"write a ?variable"
        )
    bound = _variables(match)

    constructs: list[Construct] = []
    for spec in rule.construct or []:
        if not isinstance(spec, Mapping) or not spec.get("pattern"):
            raise ValueError(f"construct entry {spec!r} needs pattern:")
        text = str(spec["pattern"])
        pattern = parser.parse_pattern(text)
        _check_positions(pattern, text)
        bind = parse_bind(str(spec["bind"])) if spec.get("bind") else None
        available = set(bound)
        if bind is not None:
            if bind.variable not in bound:
                raise ValueError(
                    f"bind {spec['bind']!r} reads ?{bind.variable}, which the match does not bind"
                )
            if pattern[2] != Variable(bind.target):
                raise ValueError(
                    f"bind {spec['bind']!r} binds ?{bind.target}, which is not the object of "
                    f"{text!r}"
                )
            available.add(bind.target)
        unbound = sorted(_variables(pattern) - available)
        if unbound:
            names = ", ".join(f"?{name}" for name in unbound)
            raise ValueError(f"construct {text!r} uses {names}, which the match does not bind")
        constructs.append(Construct(pattern, bind))

    return ResolvedRule(rule, index, match=match, constructs=tuple(constructs))


def resolve_rules(
    rules: Sequence[MigrationRule], sources: Sequence[tuple[Path, Mapping[str, str]]]
) -> list[ResolvedRule]:
    """Resolve every rule's terms and check every rule, before any graph is changed (#492).

    A CURIE means one IRI across ``sources``: a source that does not bind its prefix is not a
    disagreement, two that bind it differently are. The core five (`CORE_PREFIXES`) are a
    source of their own; rdflib's built-in prefix table is never consulted.

    Args:
        rules: The rules, in the order they run.
        sources: Each source of prefixes: the data files (see `parse_declaring`), and the
            config's ``namespaces.preferred_prefixes`` named by the config file.

    Returns:
        One `ResolvedRule` per rule, in order.

    Raises:
        RuleError: Naming the first rule that cannot be read, and why.
    """
    every = [*sources, (Path("the core prefixes"), CORE_PREFIXES)]
    parser = PatternParser(resolve=lambda text: resolve_term(text, every))
    resolved: list[ResolvedRule] = []
    for index, rule in enumerate(rules):
        try:
            resolved.append(_resolve_one(rule, index, parser))
        except (CurieError, AmbiguousCurieError, ValueError) as e:
            raise RuleError(index, rule.description, str(e)) from e
    return resolved


class RuleEngine:
    """Executes transformation rules on RDF graphs.

    Supports:
    - Pattern matching with variable bindings
    - Triple construction from bindings
    - Simple value transformations (STRBEFORE, STRAFTER, arithmetic)
    """

    def __init__(self) -> None:
        """Initialize the rule engine."""
        self.parser = PatternParser()

    def set_namespaces(self, graph: Graph) -> None:
        """Set the parser's prefixes to the graph's own, and no others (#492).

        Args:
            graph: Graph to extract namespaces from
        """
        self.parser.namespaces = extract_prefix_map(graph)

    def apply_rule(self, graph: Graph, rule: ResolvedRule | MigrationRule) -> dict[str, int]:
        """Apply a transformation rule to a graph.

        Modifies the graph in place, as SPARQL's ``DELETE … INSERT … WHERE`` does: every match is
        found first, then the matched triples are removed and the constructed ones added. A match
        whose constructs do not all build (a ``bind`` with no value) is left as it was, and
        counted as ``kept``.

        Args:
            graph: Graph to transform
            rule: The rule; a `MigrationRule` is resolved against the graph's own prefixes

        Returns:
            Statistics: {"added": n, "removed": n, "instances": n, "kept": n}, where
            ``instances`` counts every match

        Raises:
            RuleError: If a `MigrationRule` given cannot be read.
        """
        if isinstance(rule, MigrationRule):
            rule = resolve_rules([rule], [(Path("data"), extract_prefix_map(graph))])[0]

        stats = {"added": 0, "removed": 0, "instances": 0, "kept": 0}
        if rule.match is None:
            return stats

        to_remove: set[tuple[Node, Node, Node]] = set()
        to_add: set[tuple[Node, Node, Node]] = set()
        for match in self._find_matches(graph, rule.match):
            stats["instances"] += 1
            fresh: dict[BNode, BNode] = {}
            built = [self._construct_triple(match, c, fresh) for c in rule.constructs]
            if any(triple is None for triple in built):
                stats["kept"] += 1
                continue
            to_add.update(t for t in built if t is not None)
            if rule.rule.delete_matched:
                to_remove.update(match.matched_triples)

        for triple in to_remove:
            graph.remove(triple)
        stats["removed"] = len(to_remove)
        for triple in to_add:
            if triple not in graph:
                graph.add(triple)
                stats["added"] += 1

        return stats

    def _find_matches(self, graph: Graph, pattern: str | tuple[Node, Node, Node]) -> list[Match]:
        """Find all matches for a pattern in the graph.

        Args:
            graph: Graph to search
            pattern: Pattern string, parsed with this engine's parser, or a parsed pattern

        Returns:
            List of Match objects with bindings

        Raises:
            ValueError: If a pattern string cannot be read, or has a blank node.
        """
        if isinstance(pattern, str):
            pattern = self.parser.parse_pattern(pattern)
        if any(isinstance(term, BNode) for term in pattern):
            raise ValueError("a match pattern cannot hold a blank node: write a ?variable")

        # A Variable is a str, and so is a URIRef: only the Variable test tells them apart (#492)
        query = tuple(None if isinstance(term, Variable) else term for term in pattern)

        matches: list[Match] = []
        for triple in graph.triples(query):  # type: ignore[arg-type]
            bindings: dict[str, Node] = {}
            for term, value in zip(pattern, triple, strict=True):
                if isinstance(term, Variable):
                    name = str(term)
                    # A variable used twice must bind one value
                    if bindings.setdefault(name, value) != value:
                        break
            else:
                matches.append(Match(bindings=bindings, matched_triples=[triple]))

        return matches

    def _construct_triple(
        self, match: Match, construct: Construct, fresh: dict[BNode, BNode]
    ) -> tuple[Node, Node, Node] | None:
        """Construct one triple from a match.

        Args:
            match: Match with variable bindings
            construct: The construct entry
            fresh: This match's blank nodes, by the label the pattern gives them

        Returns:
            The triple, or None if it cannot be built: a ``bind`` with no value, or a binding
            that cannot stand where the pattern puts it
        """
        subject, predicate, obj = (
            (
                fresh.setdefault(term, BNode())
                if isinstance(term, BNode)
                else self._substitute_variable(term, match.bindings)
            )
            for term in construct.pattern
        )
        if construct.bind is not None:
            obj = self._evaluate_bind(construct.bind, match.bindings)

        if subject is None or isinstance(subject, Literal) or not isinstance(predicate, URIRef):
            return None
        if obj is None:
            return None
        return (subject, predicate, obj)

    def _substitute_variable(self, term: Any, bindings: dict[str, Node]) -> Node | None:
        """Substitute a variable with its bound value.

        Args:
            term: Term to substitute (may be a `Variable`)
            bindings: Variable bindings

        Returns:
            Substituted value or None if variable not bound
        """
        if isinstance(term, Variable):
            return bindings.get(str(term))
        return term if isinstance(term, Node) else None

    def _evaluate_bind(self, bind: Bind, bindings: dict[str, Node]) -> Node | None:
        """Evaluate a parsed bind expression.

        Supports:
        - STRBEFORE(?var, 'delimiter') - substring before delimiter, keeping a language tag
        - STRAFTER(?var, 'delimiter') - substring after delimiter, keeping a language tag
        - ((?var - n) * m/d) - in decimal arithmetic, written as an ``xsd:decimal`` in plain
          notation (#465)

        Args:
            bind: The parsed expression
            bindings: Variable bindings

        Returns:
            Evaluated value, or None when there is none: the delimiter is absent, or the value
            is not a literal of a numeric datatype (`_NUMERIC_TYPES`), or is not finite
        """
        value = bindings.get(bind.variable)
        if value is None:
            return None

        if bind.function in ("strbefore", "strafter"):
            text = str(value)
            idx = text.find(bind.delimiter)
            if idx < 0:
                return None
            part = text[:idx] if bind.function == "strbefore" else text[idx + len(bind.delimiter) :]
            language = value.language if isinstance(value, Literal) else None
            return Literal(part, lang=language) if language else Literal(part)

        if not isinstance(value, Literal) or value.datatype not in _NUMERIC_TYPES:
            return None
        try:
            result = _arithmetic(Decimal(str(value)), bind)
        except (InvalidOperation, ArithmeticError):
            # Not the datatype's lexical form
            return None
        if not result.is_finite():
            return None
        return Literal(format(result, "f"), datatype=XSD.decimal)


def _arithmetic(number: Decimal, bind: Bind) -> Decimal:
    """Compute ``((number - subtract) * multiply) / divide`` without rounding any operand.

    The subtraction and multiplication are exact, however many digits the value has. A division
    that terminates is exact too; one that does not (``1/3``) is rounded to `_DIVISION_DIGITS`
    significant digits, or more when the integer part needs them, so the integer part is never
    rounded.

    Args:
        number: The bound value.
        bind: The arithmetic expression.

    Returns:
        The result.
    """
    with localcontext() as context:
        context.prec, context.Emax, context.Emin = MAX_PREC, MAX_EMAX, MIN_EMIN
        numerator = (number - bind.subtract) * bind.multiply
        if not numerator.is_finite():
            return numerator
        digits = len(numerator.as_tuple().digits) + len(bind.divide.as_tuple().digits)
        # A terminating quotient of these has at most this many significant digits
        context.prec = 4 * digits + 2
        context.traps[Inexact] = False
        context.clear_flags()
        result = numerator / bind.divide
        if context.flags[Inexact]:
            quotient = abs(numerator) // bind.divide
            whole = len(str(quotient)) if quotient else 0
            context.prec = max(_DIVISION_DIGITS, whole + _DIVISION_DIGITS)
            result = numerator / bind.divide
    return result
