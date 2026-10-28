"""Merge generated RDF with existing ontologies.

This module provides functionality to merge newly generated RDF
from PlantUML with existing ontology files, preserving manually
added content while updating what's defined in the diagram.

A diagram can express only part of an ontology (#417): ``owl:Class``, ``owl:ObjectProperty`` and
``owl:DatatypeProperty`` declarations, superclasses between named classes, and named domains and
ranges. Everything else the existing ontology says about a term, such as an OWL characteristic,
a punned ``owl:NamedIndividual`` or a restriction, is kept, because the diagram's silence about
it is not a statement that it is false.
"""

from dataclasses import dataclass, field
from pathlib import Path

from rdflib import RDF, RDFS, Graph
from rdflib.namespace import OWL
from rdflib.term import BNode, Node, URIRef

from rdf_construct.core.formats import infer_format
from rdf_construct.core.vocab import (
    ANNOTATION_PROPERTY_TYPES,
    CLASS_TYPES,
    DATATYPE_PROPERTY_TYPES,
    OBJECT_PROPERTY_TYPES,
)

#: The kind each type declares its subject to be. A type in none of these sets (a generic
#: property type such as ``owl:FunctionalProperty``, or ``owl:NamedIndividual``) has no kind,
#: so it clashes with nothing.
_KINDS: tuple[tuple[str, frozenset[URIRef]], ...] = (
    ("class", CLASS_TYPES),
    ("object property", OBJECT_PROPERTY_TYPES),
    ("datatype property", DATATYPE_PROPERTY_TYPES),
    ("annotation property", ANNOTATION_PROPERTY_TYPES),
)


def _kind(rdf_type: Node) -> str | None:
    """The kind of term ``rdf_type`` declares, or None if it declares no particular kind."""
    for kind, types in _KINDS:
        if rdf_type in types:
            return kind
    return None


@dataclass(frozen=True)
class MergeConflict:
    """A value in the existing ontology that the diagram disagreed with.

    Attributes:
        code: ``replaced`` when the diagram's value was written in place of the existing one;
            ``kind-clash`` when the diagram declares the term a different kind of thing (a class
            where the existing ontology has a property, or an object property where it has a
            datatype property).
        subject: The term the two disagree about.
        predicate: ``rdf:type``, ``rdfs:subClassOf``, ``rdfs:domain``, ``rdfs:range`` or
            ``rdfs:subPropertyOf``.
        existing: The existing ontology's values involved.
        new: The diagram's values involved.
        message: One line saying what was written, with prefixed names.
    """

    code: str
    subject: Node
    predicate: URIRef
    existing: tuple[Node, ...]
    new: tuple[Node, ...]
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class MergeResult:
    """Result of merging two graphs.

    Every count is taken from the merged graph against the existing one, so it says what the
    merge writes.

    Attributes:
        graph: The merged graph
        added_count: Number of triples in the merged graph that the existing one did not have
        updated_count: Number of existing triples replaced by the diagram's values
        preserved_count: Number of existing triples kept
        conflicts: Every existing value the diagram disagreed with, in a stable order
    """

    graph: Graph
    added_count: int = 0
    updated_count: int = 0
    preserved_count: int = 0
    conflicts: list[MergeConflict] = field(default_factory=list)


class OntologyMerger:
    """Merges generated RDF with existing ontology content.

    The merger follows these principles:
    1. Types are added, never removed. A type the diagram gives a term joins the ones the
       existing ontology gives it, unless the two declare different kinds of term: then the
       existing type wins by default, and the clash is reported.
    2. A superclass, domain, range or superproperty in the existing file is replaced only by
       one the diagram gives the same term, only when it is a named term the diagram itself
       declares (for a datatype property's range, any named datatype), and every replacement
       is reported. A blank-node value (a restriction, a union) is never replaced.
    3. Additional annotations (comments, labels) in the existing file are preserved
    4. Entities only in the existing file are preserved
    5. An existing ontology with its own ``owl:Ontology`` header does not gain the diagram's

    Example:
        merger = OntologyMerger()
        result = merger.merge(new_graph, existing_path)
        result.graph.serialize("merged.ttl", format="turtle")
    """

    # Predicates that PlantUML defines authoritatively
    AUTHORITATIVE_PREDICATES = {
        RDF.type,
        RDFS.subClassOf,
        RDFS.domain,
        RDFS.range,
        RDFS.subPropertyOf,
    }

    # Predicates to merge (keep both if different)
    MERGEABLE_PREDICATES = {
        RDFS.label,
        RDFS.comment,
        RDFS.seeAlso,
    }

    def __init__(self, preserve_existing: bool = True) -> None:
        """Initialise the merger.

        Args:
            preserve_existing: If True, an existing type wins over the diagram's when the two
                declare different kinds of term. If False, the diagram's type replaces it.
                Either way the clash is reported.
        """
        self.preserve_existing = preserve_existing

    def merge(
        self,
        new_graph: Graph,
        existing_path: Path,
        input_format: str | None = None,
    ) -> MergeResult:
        """Merge new graph with existing ontology file.

        Args:
            new_graph: Newly generated RDF graph
            existing_path: Path to existing ontology file
            input_format: RDF format of the existing file; inferred from its extension if None

        Returns:
            MergeResult with merged graph and statistics
        """
        # Load existing graph, binding only the prefixes it declares (#354)
        existing = Graph(bind_namespaces="core")
        existing.parse(str(existing_path), format=input_format or infer_format(existing_path))

        return self.merge_graphs(new_graph, existing)

    def merge_graphs(
        self,
        new_graph: Graph,
        existing: Graph,
    ) -> MergeResult:
        """Merge two graphs.

        Args:
            new_graph: Newly generated RDF graph
            existing: Existing ontology graph

        Returns:
            MergeResult with merged graph and statistics
        """
        merged = Graph(bind_namespaces="core")

        # Copy all prefixes from both
        for prefix, ns in existing.namespace_manager.namespaces():
            merged.bind(prefix, ns, override=False)
        for prefix, ns in new_graph.namespace_manager.namespaces():
            merged.bind(prefix, ns, override=False)

        def name(node: Node) -> str:
            return node.n3(merged.namespace_manager)

        conflicts: list[MergeConflict] = []
        for triple in existing:
            merged.add(triple)

        # The diagram's ontology header is only its own if the existing file has none
        skipped: set[Node] = set()
        if (None, RDF.type, OWL.Ontology) in existing:
            skipped = set(new_graph.subjects(RDF.type, OWL.Ontology))

        declared = set(new_graph.subjects(RDF.type, None))

        for subject in sorted(set(new_graph.subjects()) - skipped, key=str):
            # Types: added, unless the diagram declares a different kind of term
            existing_types = set(existing.objects(subject, RDF.type))
            existing_kinds = {_kind(t) for t in existing_types} - {None}
            for new_type in sorted(new_graph.objects(subject, RDF.type), key=str):
                kind = _kind(new_type)
                if kind is None or not existing_kinds or kind in existing_kinds:
                    continue
                clashing = tuple(
                    sorted((t for t in existing_types if _kind(t) is not None), key=str)
                )
                if self.preserve_existing:
                    message = (
                        f"{name(subject)} is {', '.join(name(t) for t in clashing)} here; "
                        f"the diagram's {name(new_type)} was not written."
                    )
                else:
                    for existing_type in clashing:
                        merged.remove((subject, RDF.type, existing_type))
                    message = (
                        f"{name(subject)} was {', '.join(name(t) for t in clashing)}; "
                        f"the diagram's {name(new_type)} replaced it."
                    )
                conflicts.append(
                    MergeConflict("kind-clash", subject, RDF.type, clashing, (new_type,), message)
                )

            # Hierarchy, domain and range: a named value the diagram could have drawn is replaced
            is_datatype_property = (subject, RDF.type, OWL.DatatypeProperty) in new_graph
            for predicate in sorted(self.AUTHORITATIVE_PREDICATES - {RDF.type}, key=str):
                new_values = set(new_graph.objects(subject, predicate))
                if not new_values:
                    continue
                for value in sorted(
                    set(existing.objects(subject, predicate)) - new_values, key=str
                ):
                    if isinstance(value, BNode):
                        continue
                    drawn = value in declared or (
                        predicate == RDFS.range
                        and is_datatype_property
                        and isinstance(value, URIRef)
                    )
                    if not drawn:
                        continue
                    merged.remove((subject, predicate, value))
                    shown = ", ".join(name(v) for v in sorted(new_values, key=str))
                    conflicts.append(
                        MergeConflict(
                            "replaced",
                            subject,
                            predicate,
                            (value,),
                            tuple(sorted(new_values, key=str)),
                            f"{name(subject)} {name(predicate)} {name(value)} was replaced "
                            f"by the diagram's {shown}.",
                        )
                    )

        # Add triples from new graph
        withheld = {(c.subject, RDF.type, c.new[0]) for c in conflicts if c.code == "kind-clash"}
        for triple in new_graph:
            if triple[0] in skipped:
                continue
            if self.preserve_existing and triple in withheld:
                continue
            merged.add(triple)

        existing_triples = set(existing)
        merged_triples = set(merged)
        return MergeResult(
            graph=merged,
            added_count=len(merged_triples - existing_triples),
            updated_count=len(existing_triples - merged_triples),
            preserved_count=len(existing_triples & merged_triples),
            conflicts=conflicts,
        )


def merge_with_existing(
    new_graph: Graph,
    existing_path: Path,
    output_path: Path | None = None,
    output_format: str = "turtle",
    input_format: str | None = None,
) -> MergeResult:
    """Convenience function to merge and optionally save.

    Args:
        new_graph: Newly generated RDF graph
        existing_path: Path to existing ontology
        output_path: Path to write merged result (optional)
        output_format: RDF serialization format of the output
        input_format: RDF format of the existing ontology; inferred from its extension if None

    Returns:
        MergeResult with merged graph and statistics
    """
    merger = OntologyMerger()
    result = merger.merge(new_graph, existing_path, input_format)

    if output_path:
        result.graph.serialize(str(output_path), format=output_format)

    return result
