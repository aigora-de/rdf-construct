"""Post-write verification: check what a command wrote against what it claims (#266).

Most of the tool's silent failures share one shape. A command claims a relationship between what
went in and what came out, then writes something that breaks it, at exit 0. This module states
each claim once, as a :class:`Contract`, and checks it against graphs that have already been read
back from disk. Each command's claim is declared in :data:`CONTRACTS`.

**It reports and never decides.** Every checker returns a list of :class:`Discrepancy`, which is
empty when the contract holds. Nothing here prints, exits or raises because a contract failed.
That decision belongs to the caller: a test asserts the list is empty, and the opt-in
``--verify`` flag (#308) will map a non-empty list to exit 1. The only exception raised is
``ValueError``, when a caller passes the wrong number of graphs for a contract, or an argument the
contract does not take.

**What a contract can see.** Graphs are compared as RDF, using ``rdflib.compare``, so blank-node
labels never matter and two parses of the same file are the same graph. That cuts both ways:

- **Order is invisible.** Every ordering of a graph is isomorphic to every other, so
  ``ISOMORPHIC`` cannot catch ``order`` sorting wrongly (#195). Ordering has its own tests.
- **Prefixes, comments and layout are invisible.** Only triples count.
- **Literals are compared as terms, not values.** ``"01"^^xsd:integer`` and ``"1"^^xsd:integer``
  are different literals. RDF isomorphism is defined on terms, so a serialiser that normalises a
  lexical form has changed the graph, and is reported.
- **Named graphs are invisible.** Every contract compares :class:`~rdflib.Graph` objects, so a
  triple moved from one named graph to another, or a graph name that is lost, cannot be seen. No
  command carries named graphs end to end today: ``cast`` refuses a quad source unless
  ``--allow-flatten`` is given. A command that does will need a dataset-level contract.
- **Blank nodes are matched by their structure.** Under ``SUPERSET``, a blank node that gains or
  loses a triple in the output no longer matches its source. Its triples then read as missing,
  which is a loud failure and never a silent pass. The other side of this: two blank nodes with
  identical structure are indistinguishable, so ``SUPERSET`` cannot tell one copy of a closure
  from two. ``ISOMORPHIC`` and ``UNION_ISOMORPHIC`` can.

**Using it in a fix's regression test.** Run the command, read its output back, and assert that
the contract for that command holds::

    from rdflib import Graph

    from rdf_construct.core.verify import CONTRACTS, check_contract, describe

    def test_split_union_is_the_source(tmp_path):
        result = CliRunner().invoke(cli, ["split", SRC, "--by-namespace", "-o", str(tmp_path)])
        assert result.exit_code == 0
        modules = [Graph().parse(path) for path in sorted(tmp_path.glob("*.ttl"))]
        discrepancies = check_contract(
            CONTRACTS["split"].contract,
            inputs=[Graph().parse(SRC)],
            outputs=modules,
        )
        assert not discrepancies, describe(discrepancies)

``tests/test_post_write.py`` holds one such test per contract. Each failing one is marked
``xfail(strict=True)`` against its issue. The fix that makes it pass removes the marker.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING

from rdflib import Graph
from rdflib.compare import graph_diff, to_canonical_graph, to_isomorphic
from rdflib.term import BNode, Node

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

#: One RDF statement as a subject, predicate and object.
Triple = tuple[Node, Node, Node]

#: The number of triples a :class:`Discrepancy` keeps as a sample. The counts are always exact.
SAMPLE_SIZE = 10


class Contract(Enum):
    """A relationship a command claims between its input and its output."""

    #: The output is the same graph as the input.
    ISOMORPHIC = "isomorphic"
    #: The output has exactly as many triples as the input.
    TRIPLE_COUNT = "triple-count"
    #: The union of the outputs is the same graph as the input.
    UNION_ISOMORPHIC = "union-isomorphic"
    #: The output contains every triple of every input, except those it claims to drop.
    SUPERSET = "superset"
    #: Several counts of the same things, taken from different artefacts, are all equal.
    COUNTS_AGREE = "counts-agree"


@dataclass(frozen=True)
class Discrepancy:
    """One way in which an output breaks its contract.

    Attributes:
        contract: The contract that was broken.
        message: What was found, in one sentence.
        missing: A sample of triples expected in the output and not there.
        extra: A sample of triples in the output and not expected.
        missing_count: How many triples are missing in total.
        extra_count: How many triples are extra in total.
    """

    contract: Contract
    message: str
    missing: tuple[Triple, ...] = ()
    extra: tuple[Triple, ...] = ()
    missing_count: int = 0
    extra_count: int = 0

    def __str__(self) -> str:
        """Return the message, then each sampled triple in N-Triples form."""
        lines = [f"{self.contract.value}: {self.message}"]
        lines += [f"  - {' '.join(term.n3() for term in t)}" for t in self.missing]
        if self.missing_count > len(self.missing):
            lines.append(f"  - ... and {self.missing_count - len(self.missing)} more missing")
        lines += [f"  + {' '.join(term.n3() for term in t)}" for t in self.extra]
        if self.extra_count > len(self.extra):
            lines.append(f"  + ... and {self.extra_count - len(self.extra)} more extra")
        return "\n".join(lines)


def describe(discrepancies: Iterable[Discrepancy]) -> str:
    """Render discrepancies for an assertion message, one block per discrepancy.

    Args:
        discrepancies: What a checker returned.

    Returns:
        The rendered text, or an empty string when there are none.
    """
    return "\n".join(str(found) for found in discrepancies)


@dataclass(frozen=True)
class CommandContract:
    """The contract a command claims, as #266 states it.

    Attributes:
        command: The command path, as ``rdf-construct`` registers it.
        contract: The relationship between its input and its output.
        ambiguous: True when it is not settled what the command should claim. The ``--verify``
            flag (#308) is offered only where this is False.
        note: The conditions under which the contract applies, or why it is ambiguous.
    """

    command: str
    contract: Contract
    ambiguous: bool = False
    note: str = ""


#: The contract each command claims. Commands that are not listed claim nothing that this module
#: can check.
CONTRACTS: Mapping[str, CommandContract] = MappingProxyType(
    {
        entry.command: entry
        for entry in (
            CommandContract(
                "order",
                Contract.ISOMORPHIC,
                note=(
                    "Lossless profiles only: those with `unclaimed: emit`, or with nothing left "
                    "unclaimed. A profile that drops subjects rewrites the header (#90)."
                ),
            ),
            CommandContract("cast", Contract.ISOMORPHIC),
            CommandContract(
                "refactor rename",
                Contract.TRIPLE_COUNT,
                note="Renaming onto an IRI that is already in use merges two entities (#185).",
            ),
            CommandContract(
                "refactor deprecate",
                Contract.SUPERSET,
                ambiguous=True,
                note=(
                    "#266 states 'the same triple count', but deprecating adds owl:deprecated, "
                    "dcterms:isReplacedBy and a comment, so the count rises by design. Only 'every "
                    "input triple survives' is checked here."
                ),
            ),
            CommandContract("split", Contract.UNION_ISOMORPHIC),
            CommandContract(
                "merge",
                Contract.SUPERSET,
                note="The losing values of the conflicts the merge reports as resolved are excluded.",
            ),
            CommandContract(
                "docs",
                Contract.COUNTS_AGREE,
                note="Entities selected = pages written = index entries = search index entries.",
            ),
            CommandContract(
                "localise merge",
                Contract.ISOMORPHIC,
                note="Merging an unedited `localise extract` back gives the source.",
            ),
            CommandContract(
                "shacl-gen",
                Contract.COUNTS_AGREE,
                note="One sh:NodeShape per selected class.",
            ),
        )
    }
)


def _sample(triples: Iterable[Triple]) -> tuple[Triple, ...]:
    return tuple(sorted(triples, key=lambda triple: tuple(term.n3() for term in triple)))[
        :SAMPLE_SIZE
    ]


def check_isomorphic(
    expected: Graph, actual: Graph, contract: Contract = Contract.ISOMORPHIC
) -> list[Discrepancy]:
    """Check that ``actual`` is the same graph as ``expected``, up to blank-node labels.

    Args:
        expected: The graph the command claims to have written.
        actual: The graph read back from what it wrote.
        contract: The contract to name in a discrepancy.

    Returns:
        One discrepancy listing the missing and extra triples, or an empty list.
    """
    canonical_expected = to_isomorphic(expected)
    canonical_actual = to_isomorphic(actual)
    if canonical_expected == canonical_actual:
        return []
    _, only_expected, only_actual = graph_diff(canonical_expected, canonical_actual)
    return [
        Discrepancy(
            contract,
            f"expected {len(expected)} triples, found {len(actual)}: "
            f"{len(only_expected)} missing and {len(only_actual)} extra",
            missing=_sample(only_expected),
            extra=_sample(only_actual),
            missing_count=len(only_expected),
            extra_count=len(only_actual),
        )
    ]


def check_triple_count(expected: Graph, actual: Graph) -> list[Discrepancy]:
    """Check that ``actual`` has exactly as many triples as ``expected``.

    Args:
        expected: The input graph.
        actual: The graph read back from the output.

    Returns:
        One discrepancy giving both counts, or an empty list.
    """
    if len(expected) == len(actual):
        return []
    return [
        Discrepancy(
            Contract.TRIPLE_COUNT,
            f"expected {len(expected)} triples, found {len(actual)}",
        )
    ]


def check_union_isomorphic(source: Graph, parts: Iterable[Graph]) -> list[Discrepancy]:
    """Check that the union of ``parts`` is the same graph as ``source``.

    A blank node is local to the file it was parsed from. So a blank-node closure that is copied
    into two parts appears twice in the union, and is reported as extra.

    Args:
        source: The graph that was divided.
        parts: The graphs read back from each part that was written.

    Returns:
        One discrepancy listing the missing and extra triples, or an empty list.
    """
    union = Graph()
    for part in parts:
        union += part
    return check_isomorphic(source, union, Contract.UNION_ISOMORPHIC)


def _has_bnode(triple: Triple) -> bool:
    return any(isinstance(term, BNode) for term in triple)


def check_superset(
    sources: Iterable[Graph], output: Graph, excluded: Iterable[Triple] = ()
) -> list[Discrepancy]:
    """Check that ``output`` keeps every source triple, except ``excluded``, which it must drop.

    Triples with no blank node are compared exactly. Triples with a blank node are compared
    after canonicalising both sides. ``excluded`` must contain no blank nodes.

    Args:
        sources: The input graphs.
        output: The graph read back from the output.
        excluded: Source triples the output claims to have removed, such as the losing values of
            the conflicts a merge resolved. Each must be absent from the output.

    Returns:
        One discrepancy listing the source triples the output lacks and the excluded triples it
        still holds, or an empty list.
    """
    union = Graph()
    for source in sources:
        union += source
    dropped = set(excluded)

    grounded_union = {t for t in union if not _has_bnode(t)}
    grounded_output = {t for t in output if not _has_bnode(t)}
    missing = grounded_union - grounded_output - dropped

    union_bnodes = Graph()
    output_bnodes = Graph()
    for graph, part in ((union, union_bnodes), (output, output_bnodes)):
        for t in graph:
            if _has_bnode(t):
                part.add(t)
    missing |= set(to_canonical_graph(union_bnodes)) - set(to_canonical_graph(output_bnodes))

    kept = dropped & grounded_output

    if not missing and not kept:
        return []
    return [
        Discrepancy(
            Contract.SUPERSET,
            f"{len(missing)} source triples are not in the output, and "
            f"{len(kept)} triples it should have dropped are still there",
            missing=_sample(missing),
            extra=_sample(kept),
            missing_count=len(missing),
            extra_count=len(kept),
        )
    ]


def check_counts_agree(counts: Mapping[str, int]) -> list[Discrepancy]:
    """Check that every count in ``counts`` is the same number.

    Args:
        counts: Each count, keyed by what was counted, such as ``"pages written"``.

    Returns:
        One discrepancy naming every count, or an empty list.
    """
    if len(set(counts.values())) <= 1:
        return []
    listed = ", ".join(f"{name} = {value}" for name, value in counts.items())
    return [Discrepancy(Contract.COUNTS_AGREE, f"counts disagree: {listed}")]


def check_contract(
    contract: Contract,
    *,
    inputs: Sequence[Graph] = (),
    outputs: Sequence[Graph] = (),
    excluded: Iterable[Triple] = (),
    counts: Mapping[str, int] | None = None,
) -> list[Discrepancy]:
    """Check one contract. This is the single entry point for tests and for ``--verify``.

    Args:
        contract: The contract to check, usually ``CONTRACTS[command].contract``.
        inputs: The input graphs. ``ISOMORPHIC``, ``TRIPLE_COUNT`` and ``UNION_ISOMORPHIC`` take
            exactly one, and ``SUPERSET`` takes one or more.
        outputs: The graphs read back from the output. ``UNION_ISOMORPHIC`` takes any number,
            and every other graph contract takes exactly one.
        excluded: For ``SUPERSET`` only: source triples the output must not contain.
        counts: For ``COUNTS_AGREE`` only: the counts to compare.

    Returns:
        The discrepancies found, or an empty list when the contract holds.

    Raises:
        ValueError: If the arguments do not fit the contract. That is a mistake in the caller,
            never a finding about the output.
    """
    excluded = tuple(excluded)
    if excluded and contract is not Contract.SUPERSET:
        raise ValueError(f"{contract.name} takes no excluded triples")
    if counts is not None and contract is not Contract.COUNTS_AGREE:
        raise ValueError(f"{contract.name} takes no counts")
    if contract is Contract.COUNTS_AGREE:
        if counts is None or inputs or outputs:
            raise ValueError("COUNTS_AGREE takes counts and no graphs")
        return check_counts_agree(counts)
    if contract is Contract.SUPERSET:
        if not inputs or len(outputs) != 1:
            raise ValueError("SUPERSET needs at least one input and exactly one output")
        return check_superset(inputs, outputs[0], excluded)
    if len(inputs) != 1:
        raise ValueError(f"{contract.name} needs exactly one input")
    if contract is Contract.UNION_ISOMORPHIC:
        return check_union_isomorphic(inputs[0], outputs)
    if len(outputs) != 1:
        raise ValueError(f"{contract.name} needs exactly one output")
    if contract is Contract.TRIPLE_COUNT:
        return check_triple_count(inputs[0], outputs[0])
    return check_isomorphic(inputs[0], outputs[0])
