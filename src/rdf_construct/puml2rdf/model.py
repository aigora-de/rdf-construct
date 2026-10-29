"""Intermediate representation for parsed PlantUML diagrams.

This module defines dataclasses that represent PlantUML elements in a
structured form, acting as an intermediate representation between the
raw PlantUML text and the generated RDF graph.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RelationshipType(Enum):
    """Types of relationships that can be represented in PlantUML."""

    INHERITANCE = "inheritance"  # --|> or <|--
    ASSOCIATION = "association"  # --> or --
    AGGREGATION = "aggregation"  # o-- or --o
    COMPOSITION = "composition"  # *-- or --*


class PropertyKind(Enum):
    """Kind of property to generate in RDF."""

    DATATYPE = "datatype"  # owl:DatatypeProperty
    OBJECT = "object"  # owl:ObjectProperty
    ANNOTATION = "annotation"  # owl:AnnotationProperty


@dataclass
class PumlAttribute:
    """An attribute within a PlantUML class.

    Attributes represent datatype properties in the generated ontology.

    Attributes:
        name: Attribute name (e.g., 'floorArea')
        datatype: XSD datatype string (e.g., 'decimal', 'string')
        visibility: UML visibility marker (+, -, #, ~)
        is_static: Whether marked as static (underlined)
    """

    name: str
    datatype: Optional[str] = None
    visibility: str = "+"
    is_static: bool = False


@dataclass
class PumlClass:
    """A class definition from PlantUML."""

    name: str  # Local name only (e.g., "Building")
    package: Optional[str] = None  # Namespace prefix (e.g., "building")
    stereotype: Optional[str] = None
    attributes: list[PumlAttribute] = field(default_factory=list)
    note: Optional[str] = None
    is_abstract: bool = False
    display_name: Optional[str] = None  # NEW: From "Display Name" as alias syntax

    @property
    def qualified_name(self) -> str:
        """Return the fully qualified name including package."""
        if self.package:
            return f"{self.package}.{self.name}"
        return self.name


@dataclass
class PumlRelationship:
    """A relationship between two classes in PlantUML.

    Depending on the type, this generates different RDF constructs:
    - INHERITANCE -> rdfs:subClassOf
    - ASSOCIATION -> owl:ObjectProperty
    - AGGREGATION/COMPOSITION -> owl:ObjectProperty with semantics note

    Attributes:
        source: Source class name
        target: Target class name
        rel_type: Type of relationship
        label: Relationship label (becomes property name)
        source_cardinality: Cardinality at source end (e.g., '1', '*', '0..1')
        target_cardinality: Cardinality at target end
        note: Attached note for the relationship
    """

    source: str
    target: str
    rel_type: RelationshipType
    label: Optional[str] = None
    source_cardinality: Optional[str] = None
    target_cardinality: Optional[str] = None
    note: Optional[str] = None


@dataclass
class PumlPackage:
    """A package definition from PlantUML.

    Packages map to RDF namespaces in the generated ontology.

    Attributes:
        name: Display name of the package
        namespace_uri: The URI to use as the namespace (from 'as' clause)
        stereotype: Package stereotype (if any)
    """

    name: str
    namespace_uri: Optional[str] = None
    stereotype: Optional[str] = None


@dataclass
class PumlNote:
    """A standalone note in PlantUML.

    Notes attached to classes become rdfs:comment.
    Standalone notes may be used for ontology metadata.

    Attributes:
        content: The note text
        attached_to: Name of class this note is attached to (if any)
        position: Position relative to attached element
    """

    content: str
    attached_to: Optional[str] = None
    position: Optional[str] = None


@dataclass
class PumlModel:
    """Complete parsed PlantUML model.

    This is the top-level container for all parsed elements,
    ready for conversion to RDF.

    Attributes:
        classes: All parsed classes
        relationships: All parsed relationships
        packages: All parsed packages
        notes: All standalone notes
        title: Diagram title (becomes ontology label)
        skin_params: PlantUML skinparam settings (preserved for round-trip)
    """

    classes: list[PumlClass] = field(default_factory=list)
    relationships: list[PumlRelationship] = field(default_factory=list)
    packages: list[PumlPackage] = field(default_factory=list)
    notes: list[PumlNote] = field(default_factory=list)
    title: Optional[str] = None
    skin_params: dict[str, str] = field(default_factory=dict)

    def get_class(self, name: str) -> Optional[PumlClass]:
        """Find a class by name (local or qualified).

        Args:
            name: Class name - can be "Building" or "building.Building"

        Returns:
            The PumlClass if found, None otherwise
        """
        for cls in self.classes:
            # Match by local name
            if cls.name == name:
                return cls
            # Match by qualified name
            if cls.qualified_name == name:
                return cls
        return None

    def get_package(self, name: str) -> Optional[PumlPackage]:
        """Find a package by name or URI.

        Args:
            name: Package name or namespace URI

        Returns:
            The PumlPackage if found, None otherwise
        """
        for pkg in self.packages:
            if pkg.name == name or pkg.namespace_uri == name:
                return pkg
        return None

    def inheritance_relationships(self) -> list[PumlRelationship]:
        """Return only inheritance relationships (rdfs:subClassOf)."""
        return [r for r in self.relationships if r.rel_type == RelationshipType.INHERITANCE]

    def property_relationships(self) -> list[PumlRelationship]:
        """Return relationships that become object properties."""
        return [
            r
            for r in self.relationships
            if r.rel_type
            in (
                RelationshipType.ASSOCIATION,
                RelationshipType.AGGREGATION,
                RelationshipType.COMPOSITION,
            )
        ]
