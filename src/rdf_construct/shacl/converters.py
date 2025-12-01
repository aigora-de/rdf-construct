"""OWL to SHACL conversion rules.

Each converter handles a specific OWL pattern and produces equivalent SHACL
constraints. Converters are composable and applied by the generator.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef, XSD
from rdflib.namespace import OWL

from .namespaces import SH

if TYPE_CHECKING:
    from .config import ShaclConfig


@dataclass
class PropertyConstraint:
    """Represents a property constraint to be added to a shape.

    Accumulates constraints that will become a sh:property blank node.

    Attributes:
        path: The property path (usually the property URI).
        node_class: Expected class for object values (sh:class).
        datatype: Expected datatype for literal values (sh:datatype).
        min_count: Minimum cardinality (sh:minCount).
        max_count: Maximum cardinality (sh:maxCount).
        node_kind: Node kind constraint (sh:nodeKind).
        name: Human-readable name (sh:name).
        description: Description (sh:description).
        in_values: Enumeration of allowed values (sh:in).
        pattern: Regex pattern for string values (sh:pattern).
        min_inclusive: Minimum value inclusive (sh:minInclusive).
        max_inclusive: Maximum value inclusive (sh:maxInclusive).
        order: Property display order (sh:order).
    """

    path: URIRef
    node_class: URIRef | None = None
    datatype: URIRef | None = None
    min_count: int | None = None
    max_count: int | None = None
    node_kind: URIRef | None = None
    name: str | None = None
    description: str | None = None
    in_values: list[URIRef | Literal] = field(default_factory=list)
    pattern: str | None = None
    min_inclusive: Literal | None = None
    max_inclusive: Literal | None = None
    order: int | None = None

    def merge(self, other: "PropertyConstraint") -> "PropertyConstraint":
        """Merge another constraint into this one.

        Values from other take precedence for single-value fields.
        Lists are combined.

        Args:
            other: Constraint to merge from.

        Returns:
            New merged PropertyConstraint.
        """
        return PropertyConstraint(
            path=self.path,
            node_class=other.node_class or self.node_class,
            datatype=other.datatype or self.datatype,
            min_count=max(
                filter(None, [self.min_count, other.min_count]), default=None
            ),
            max_count=min(
                filter(None, [self.max_count, other.max_count]), default=None
            ) if self.max_count is not None or other.max_count is not None else None,
            node_kind=other.node_kind or self.node_kind,
            name=other.name or self.name,
            description=other.description or self.description,
            in_values=list(set(self.in_values + other.in_values)),
            pattern=other.pattern or self.pattern,
            min_inclusive=other.min_inclusive or self.min_inclusive,
            max_inclusive=other.max_inclusive or self.max_inclusive,
            order=other.order or self.order,
        )

    def to_rdf(self, shapes_graph: Graph) -> BNode:
        """Convert constraint to RDF representation.

        Creates a blank node with sh:property predicates.

        Args:
            shapes_graph: Graph to add triples to.

        Returns:
            Blank node representing the property shape.
        """
        prop_shape = BNode()

        shapes_graph.add((prop_shape, SH.path, self.path))

        if self.node_class:
            shapes_graph.add((prop_shape, SH["class"], self.node_class))

        if self.datatype:
            shapes_graph.add((prop_shape, SH.datatype, self.datatype))

        if self.min_count is not None:
            shapes_graph.add((prop_shape, SH.minCount, Literal(self.min_count)))

        if self.max_count is not None:
            shapes_graph.add((prop_shape, SH.maxCount, Literal(self.max_count)))

        if self.node_kind:
            shapes_graph.add((prop_shape, SH.nodeKind, self.node_kind))

        if self.name:
            shapes_graph.add((prop_shape, SH.name, Literal(self.name)))

        if self.description:
            shapes_graph.add((prop_shape, SH.description, Literal(self.description)))

        if self.in_values:
            # Create an RDF list for sh:in
            in_list = _create_rdf_list(shapes_graph, self.in_values)
            shapes_graph.add((prop_shape, SH["in"], in_list))

        if self.pattern:
            shapes_graph.add((prop_shape, SH.pattern, Literal(self.pattern)))

        if self.min_inclusive is not None:
            shapes_graph.add((prop_shape, SH.minInclusive, self.min_inclusive))

        if self.max_inclusive is not None:
            shapes_graph.add((prop_shape, SH.maxInclusive, self.max_inclusive))

        if self.order is not None:
            shapes_graph.add((prop_shape, SH.order, Literal(self.order)))

        return prop_shape


def _create_rdf_list(graph: Graph, items: list) -> BNode:
    """Create an RDF list from Python list.

    Args:
        graph: Graph to add list triples to.
        items: Items to include in list.

    Returns:
        Head node of the RDF list.
    """
    if not items:
        return RDF.nil

    head = BNode()
    current = head

    for i, item in enumerate(items):
        graph.add((current, RDF.first, item))

        if i < len(items) - 1:
            next_node = BNode()
            graph.add((current, RDF.rest, next_node))
            current = next_node
        else:
            graph.add((current, RDF.rest, RDF.nil))

    return head


class Converter(ABC):
    """Base class for OWL to SHACL converters.

    Each converter handles a specific OWL pattern and produces
    property constraints or modifies the shape graph directly.
    """

    @abstractmethod
    def convert_for_class(
            self,
            cls: URIRef,
            source_graph: Graph,
            config: "ShaclConfig",
    ) -> list[PropertyConstraint]:
        """Extract constraints for a given class.

        Args:
            cls: The class to extract constraints for.
            source_graph: The OWL ontology graph.
            config: Generation configuration.

        Returns:
            List of property constraints for this class.
        """
        pass


class DomainRangeConverter(Converter):
    """Convert rdfs:domain/range to sh:property with sh:class/sh:datatype.

    For each property with rdfs:domain pointing to this class, creates
    a property constraint. The rdfs:range determines whether sh:class
    or sh:datatype is used.
    """

    # Common XSD datatypes
    XSD_DATATYPES = {
        XSD.string, XSD.integer, XSD.int, XSD.long, XSD.short, XSD.byte,
        XSD.decimal, XSD.float, XSD.double, XSD.boolean, XSD.date,
        XSD.dateTime, XSD.time, XSD.duration, XSD.gYear, XSD.gMonth,
        XSD.gDay, XSD.gYearMonth, XSD.gMonthDay, XSD.anyURI, XSD.base64Binary,
        XSD.hexBinary, XSD.normalizedString, XSD.token, XSD.language,
        XSD.nonPositiveInteger, XSD.negativeInteger, XSD.nonNegativeInteger,
        XSD.positiveInteger, XSD.unsignedLong, XSD.unsignedInt,
        XSD.unsignedShort, XSD.unsignedByte,
    }

    def convert_for_class(
            self,
            cls: URIRef,
            source_graph: Graph,
            config: "ShaclConfig",
    ) -> list[PropertyConstraint]:
        """Find properties with domain of this class and create constraints."""
        constraints: list[PropertyConstraint] = []

        # Find all properties with this class as domain
        for prop in source_graph.subjects(RDFS.domain, cls):
            if not isinstance(prop, URIRef):
                continue

            constraint = PropertyConstraint(path=prop)

            # Get range if defined
            range_value = source_graph.value(prop, RDFS.range)
            if range_value:
                if self._is_datatype(range_value, source_graph):
                    constraint.datatype = range_value
                else:
                    constraint.node_class = range_value

            # Add label as name if configured
            if config.include_labels:
                label = source_graph.value(prop, RDFS.label)
                if label:
                    constraint.name = str(label)

            # Add comment as description if configured
            if config.include_descriptions:
                comment = source_graph.value(prop, RDFS.comment)
                if comment:
                    constraint.description = str(comment)

            constraints.append(constraint)

        return constraints

    def _is_datatype(self, uri: URIRef, graph: Graph) -> bool:
        """Check if URI represents a datatype."""
        if uri in self.XSD_DATATYPES:
            return True

        # Check if it's declared as rdfs:Datatype
        if (uri, RDF.type, RDFS.Datatype) in graph:
            return True

        # Check namespace - XSD URIs are datatypes
        return str(uri).startswith(str(XSD))


class CardinalityConverter(Converter):
    """Convert OWL cardinality restrictions to sh:minCount/sh:maxCount.

    Handles:
    - owl:cardinality → sh:minCount + sh:maxCount
    - owl:minCardinality → sh:minCount
    - owl:maxCardinality → sh:maxCount
    - owl:qualifiedCardinality (with owl:onClass/owl:onDataRange)
    - owl:someValuesFrom → sh:minCount 1
    """

    def convert_for_class(
            self,
            cls: URIRef,
            source_graph: Graph,
            config: "ShaclConfig",
    ) -> list[PropertyConstraint]:
        """Extract cardinality restrictions from class definition."""
        constraints: list[PropertyConstraint] = []

        # Find restrictions that this class is a subclass of
        for superclass in source_graph.objects(cls, RDFS.subClassOf):
            if not isinstance(superclass, BNode):
                continue

            # Check if it's an owl:Restriction
            if (superclass, RDF.type, OWL.Restriction) not in source_graph:
                continue

            on_prop = source_graph.value(superclass, OWL.onProperty)
            if not isinstance(on_prop, URIRef):
                continue

            constraint = PropertyConstraint(path=on_prop)
            has_constraint = False

            # Exact cardinality
            exact = source_graph.value(superclass, OWL.cardinality)
            if exact:
                constraint.min_count = int(exact)
                constraint.max_count = int(exact)
                has_constraint = True

            # Minimum cardinality
            min_card = source_graph.value(superclass, OWL.minCardinality)
            if min_card:
                constraint.min_count = int(min_card)
                has_constraint = True

            # Maximum cardinality
            max_card = source_graph.value(superclass, OWL.maxCardinality)
            if max_card:
                constraint.max_count = int(max_card)
                has_constraint = True

            # Qualified cardinality
            qual_card = source_graph.value(superclass, OWL.qualifiedCardinality)
            if qual_card:
                constraint.min_count = int(qual_card)
                constraint.max_count = int(qual_card)
                # Also get the qualification
                on_class = source_graph.value(superclass, OWL.onClass)
                if on_class:
                    constraint.node_class = on_class
                on_data = source_graph.value(superclass, OWL.onDataRange)
                if on_data:
                    constraint.datatype = on_data
                has_constraint = True

            # Qualified min cardinality
            qual_min = source_graph.value(superclass, OWL.minQualifiedCardinality)
            if qual_min:
                constraint.min_count = int(qual_min)
                on_class = source_graph.value(superclass, OWL.onClass)
                if on_class:
                    constraint.node_class = on_class
                has_constraint = True

            # Qualified max cardinality
            qual_max = source_graph.value(superclass, OWL.maxQualifiedCardinality)
            if qual_max:
                constraint.max_count = int(qual_max)
                on_class = source_graph.value(superclass, OWL.onClass)
                if on_class:
                    constraint.node_class = on_class
                has_constraint = True

            # someValuesFrom implies at least one value
            some_from = source_graph.value(superclass, OWL.someValuesFrom)
            if some_from:
                constraint.min_count = 1
                if isinstance(some_from, URIRef):
                    # Could be a class or datatype
                    if self._is_datatype(some_from, source_graph):
                        constraint.datatype = some_from
                    else:
                        constraint.node_class = some_from
                has_constraint = True

            # allValuesFrom constrains the type but not cardinality
            all_from = source_graph.value(superclass, OWL.allValuesFrom)
            if all_from and isinstance(all_from, URIRef):
                if self._is_datatype(all_from, source_graph):
                    constraint.datatype = all_from
                else:
                    constraint.node_class = all_from
                has_constraint = True

            if has_constraint:
                constraints.append(constraint)

        return constraints

    def _is_datatype(self, uri: URIRef, graph: Graph) -> bool:
        """Check if URI represents a datatype."""
        return str(uri).startswith(str(XSD)) or (uri, RDF.type, RDFS.Datatype) in graph


class FunctionalPropertyConverter(Converter):
    """Convert owl:FunctionalProperty to sh:maxCount 1.

    Also handles owl:InverseFunctionalProperty (adds maxCount 1 for the property).
    """

    def convert_for_class(
            self,
            cls: URIRef,
            source_graph: Graph,
            config: "ShaclConfig",
    ) -> list[PropertyConstraint]:
        """Find functional properties with domain of this class."""
        constraints: list[PropertyConstraint] = []

        # Get all functional properties
        functional_props = set(source_graph.subjects(RDF.type, OWL.FunctionalProperty))

        # Find properties with this class as domain
        for prop in source_graph.subjects(RDFS.domain, cls):
            if prop in functional_props and isinstance(prop, URIRef):
                constraints.append(PropertyConstraint(path=prop, max_count=1))

        return constraints


class EnumerationConverter(Converter):
    """Convert owl:oneOf to sh:in constraint.

    When a property's range is a class defined with owl:oneOf,
    creates a sh:in constraint with the enumerated values.
    """

    def convert_for_class(
            self,
            cls: URIRef,
            source_graph: Graph,
            config: "ShaclConfig",
    ) -> list[PropertyConstraint]:
        """Find properties with enumerated ranges."""
        constraints: list[PropertyConstraint] = []

        # Find properties with domain of this class
        for prop in source_graph.subjects(RDFS.domain, cls):
            if not isinstance(prop, URIRef):
                continue

            range_value = source_graph.value(prop, RDFS.range)
            if not range_value:
                continue

            # Check if range has owl:oneOf
            one_of = source_graph.value(range_value, OWL.oneOf)
            if one_of:
                values = self._extract_list(source_graph, one_of)
                if values:
                    constraints.append(PropertyConstraint(path=prop, in_values=values))

        return constraints

    def _extract_list(self, graph: Graph, head: BNode | URIRef) -> list:
        """Extract values from RDF list."""
        values = []
        current = head

        while current and current != RDF.nil:
            first = graph.value(current, RDF.first)
            if first:
                values.append(first)
            current = graph.value(current, RDF.rest)

        return values


class SymmetricPropertyConverter(Converter):
    """Handle symmetric properties.

    For symmetric properties, if domain is defined, the property
    should also be valid in the reverse direction.
    """

    def convert_for_class(
            self,
            cls: URIRef,
            source_graph: Graph,
            config: "ShaclConfig",
    ) -> list[PropertyConstraint]:
        """Handle symmetric properties - no additional SHACL needed."""
        # Symmetric properties don't need special SHACL handling
        # beyond what domain/range provides
        return []


# All converters in order of application
ALL_CONVERTERS: list[type[Converter]] = [
    DomainRangeConverter,
    CardinalityConverter,
    FunctionalPropertyConverter,
    EnumerationConverter,
]


def get_converters_for_level(level: "StrictnessLevel") -> list[Converter]:
    """Get converter instances appropriate for strictness level.

    Args:
        level: The strictness level.

    Returns:
        List of instantiated converters.
    """
    from .config import StrictnessLevel

    if level == StrictnessLevel.MINIMAL:
        return [DomainRangeConverter()]

    elif level == StrictnessLevel.STANDARD:
        return [
            DomainRangeConverter(),
            CardinalityConverter(),
            FunctionalPropertyConverter(),
        ]

    else:  # STRICT
        return [
            DomainRangeConverter(),
            CardinalityConverter(),
            FunctionalPropertyConverter(),
            EnumerationConverter(),
        ]
