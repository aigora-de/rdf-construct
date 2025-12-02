"""Convert parsed PlantUML models to RDF graphs.

This module transforms the intermediate PumlModel representation
into a proper RDF/OWL ontology using rdflib.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from rdflib import Graph, Literal, Namespace, URIRef, RDF, RDFS
from rdflib.namespace import OWL, XSD

from rdf_construct.puml2rdf.model import (
    PumlAttribute,
    PumlClass,
    PumlModel,
    PumlPackage,
    PumlRelationship,
    RelationshipType,
)


# Standard XSD datatype mappings from common PlantUML/UML type names
XSD_TYPE_MAP: dict[str, URIRef] = {
    # String types
    "string": XSD.string,
    "str": XSD.string,
    "text": XSD.string,
    # Numeric types
    "integer": XSD.integer,
    "int": XSD.integer,
    "decimal": XSD.decimal,
    "float": XSD.float,
    "double": XSD.double,
    "number": XSD.decimal,
    # Boolean
    "boolean": XSD.boolean,
    "bool": XSD.boolean,
    # Date/time types
    "date": XSD.date,
    "datetime": XSD.dateTime,
    "time": XSD.time,
    "gYear": XSD.gYear,
    "gyear": XSD.gYear,
    "gYearMonth": XSD.gYearMonth,
    "duration": XSD.duration,
    # URI types
    "uri": XSD.anyURI,
    "anyURI": XSD.anyURI,
    "anyuri": XSD.anyURI,
    "url": XSD.anyURI,
    # Other common types
    "base64": XSD.base64Binary,
    "hexBinary": XSD.hexBinary,
    "language": XSD.language,
    "token": XSD.token,
}


@dataclass
class ConversionConfig:
    """Configuration options for PlantUML to RDF conversion.

    Attributes:
        default_namespace: Default namespace URI for entities without explicit package
        language: Language tag for labels and comments (default: 'en')
        generate_labels: Whether to generate rdfs:label from names
        generate_inverse_properties: Whether to create inverse properties
        camel_to_label: Convert camelCase names to readable labels
        use_owl_thing: Whether to make classes subclass of owl:Thing explicitly
    """

    default_namespace: str = "http://example.org/ontology#"
    language: str = "en"
    generate_labels: bool = True
    generate_inverse_properties: bool = False
    camel_to_label: bool = True
    use_owl_thing: bool = False


@dataclass
class ConversionResult:
    """Result of converting a PlantUML model to RDF.

    Attributes:
        graph: The generated RDF graph
        class_uris: Mapping from class names to their URIs
        property_uris: Mapping from property names to their URIs
        warnings: Any warnings generated during conversion
    """

    graph: Graph
    class_uris: dict[str, URIRef] = field(default_factory=dict)
    property_uris: dict[str, URIRef] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class PumlToRdfConverter:
    """Converts parsed PlantUML models to RDF/OWL ontologies.

    This converter produces OWL 2 ontologies following common patterns:
    - Classes become owl:Class
    - Attributes become owl:DatatypeProperty
    - Associations become owl:ObjectProperty
    - Inheritance becomes rdfs:subClassOf
    - Notes become rdfs:comment

    Example:
        converter = PumlToRdfConverter()
        result = converter.convert(model)
        result.graph.serialize("ontology.ttl", format="turtle")
    """

    def __init__(self, config: Optional[ConversionConfig] = None) -> None:
        """Initialise the converter.

        Args:
            config: Conversion configuration options
        """
        self.config = config or ConversionConfig()
        self._graph: Graph = Graph()
        self._namespaces: dict[str, Namespace] = {}
        self._class_uris: dict[str, URIRef] = {}
        self._property_uris: dict[str, URIRef] = {}
        self._warnings: list[str] = []

    def convert(self, model: PumlModel) -> ConversionResult:
        """Convert a PlantUML model to an RDF graph."""
        self._graph = Graph()
        self._namespaces = {}
        self._class_uris = {}
        self._property_uris = {}
        self._warnings = []

        # Set up namespaces from packages AND class prefixes
        self._setup_namespaces(model.packages, model.classes)

        # Create ontology header
        self._create_ontology_header(model)

        # Convert classes
        for cls in model.classes:
            self._convert_class(cls)

        # Convert relationships
        for rel in model.relationships:
            self._convert_relationship(rel)

        return ConversionResult(
            graph=self._graph,
            class_uris=self._class_uris,
            property_uris=self._property_uris,
            warnings=self._warnings,
        )

    def _setup_namespaces(self, packages: list[PumlPackage], classes: list[PumlClass]) -> None:
        """Set up RDF namespaces from PlantUML packages and class prefixes."""
        # Standard namespaces
        self._graph.bind("owl", OWL)
        self._graph.bind("rdfs", RDFS)
        self._graph.bind("xsd", XSD)

        # Default namespace
        default_ns = Namespace(self.config.default_namespace)
        self._namespaces[None] = default_ns  # None key for unpackaged classes
        self._graph.bind("", default_ns)

        # Collect all unique package prefixes from classes
        prefixes = {cls.package for cls in classes if cls.package}

        # Also add packages from PlantUML package declarations
        for pkg in packages:
            if pkg.namespace_uri:
                ns_uri = pkg.namespace_uri
                if not ns_uri.endswith(("#", "/")):
                    ns_uri += "#"
                ns = Namespace(ns_uri)
                self._namespaces[pkg.name] = ns
                self._graph.bind(pkg.name, ns)
                prefixes.discard(pkg.name)  # Don't auto-generate

        # Auto-generate namespaces for remaining prefixes
        base = self.config.default_namespace.rstrip("#/")
        for prefix in prefixes:
            ns_uri = f"{base}/{prefix}#"
            ns = Namespace(ns_uri)
            self._namespaces[prefix] = ns
            self._graph.bind(prefix, ns)

    def _generate_prefix(self, name: str) -> str:
        """Generate a namespace prefix from a package name.

        Args:
            name: Package name (may be a URI or display name)

        Returns:
            Short lowercase prefix string
        """
        # If it looks like a URI, extract the last segment
        if "://" in name or name.startswith("http"):
            # Extract meaningful part from URI
            name = name.rstrip("#/")
            if "/" in name:
                name = name.rsplit("/", 1)[-1]
            if "#" in name:
                name = name.rsplit("#", 1)[-1]

        # Clean and shorten
        prefix = re.sub(r"[^a-zA-Z0-9]", "", name).lower()
        return prefix[:10] if len(prefix) > 10 else prefix or "ns"

    def _create_ontology_header(self, model: PumlModel) -> None:
        """Create the owl:Ontology declaration."""
        ont_uri = URIRef(self.config.default_namespace.rstrip("#/"))

        self._graph.add((ont_uri, RDF.type, OWL.Ontology))

        if model.title:
            self._graph.add(
                (ont_uri, RDFS.label, Literal(model.title, lang=self.config.language))
            )

    def _convert_class(self, cls: PumlClass) -> None:
        """Convert a PlantUML class to owl:Class and properties."""
        ns = self._get_namespace_for_class(cls)
        class_uri = ns[cls.name]  # Use local name only

        # Store by qualified name for relationship lookups
        self._class_uris[cls.name] = class_uri
        self._class_uris[cls.qualified_name] = class_uri

        self._graph.add((class_uri, RDF.type, OWL.Class))

        # Use display_name for label if available, else convert local name
        if self.config.generate_labels:
            if cls.display_name:
                label = cls.display_name
            elif self.config.camel_to_label:
                label = self._camel_to_label(cls.name)
            else:
                label = cls.name
            self._graph.add(
                (class_uri, RDFS.label, Literal(label, lang=self.config.language))
            )

        # Add comment from note
        if cls.note:
            self._graph.add(
                (class_uri, RDFS.comment, Literal(cls.note, lang=self.config.language))
            )

        # Handle abstract classes - add deprecated or custom annotation
        if cls.is_abstract:
            # We could add a custom annotation here
            pass

        # Convert attributes to datatype properties
        for attr in cls.attributes:
            self._convert_attribute(attr, class_uri, ns)

    def _convert_attribute(
        self, attr: PumlAttribute, domain_class: URIRef, ns: Namespace
    ) -> None:
        """Convert a class attribute to owl:DatatypeProperty."""
        prop_uri = ns[attr.name]
        self._property_uris[attr.name] = prop_uri

        # Add property declaration
        self._graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))

        # Add domain
        self._graph.add((prop_uri, RDFS.domain, domain_class))

        # Add range if datatype specified
        if attr.datatype:
            xsd_type = self._map_datatype(attr.datatype)
            self._graph.add((prop_uri, RDFS.range, xsd_type))

        # Add label
        if self.config.generate_labels:
            label = self._camel_to_label(attr.name) if self.config.camel_to_label else attr.name
            self._graph.add(
                (prop_uri, RDFS.label, Literal(label, lang=self.config.language))
            )

    def _convert_relationship(self, rel: PumlRelationship) -> None:
        """Convert a PlantUML relationship to RDF."""
        # Get class URIs
        source_uri = self._class_uris.get(rel.source)
        target_uri = self._class_uris.get(rel.target)

        if not source_uri:
            self._warnings.append(f"Unknown source class in relationship: {rel.source}")
            return
        if not target_uri:
            self._warnings.append(f"Unknown target class in relationship: {rel.target}")
            return

        if rel.rel_type == RelationshipType.INHERITANCE:
            # Source is subclass of target
            self._graph.add((source_uri, RDFS.subClassOf, target_uri))
        else:
            # Create object property for associations
            self._convert_association(rel, source_uri, target_uri)

    def _convert_association(
        self, rel: PumlRelationship, source_uri: URIRef, target_uri: URIRef
    ) -> None:
        """Convert an association to owl:ObjectProperty."""
        # Generate property name from label or classes
        if rel.label:
            prop_name = self._label_to_property_name(rel.label)
        else:
            # Generate name from class names
            target_name = rel.target
            prop_name = f"has{target_name}"

        # Get namespace from source class
        ns = self._get_namespace_for_class_uri(source_uri)

        prop_uri = ns[prop_name]
        self._property_uris[prop_name] = prop_uri

        # Add property declaration
        self._graph.add((prop_uri, RDF.type, OWL.ObjectProperty))

        # Add domain and range
        self._graph.add((prop_uri, RDFS.domain, source_uri))
        self._graph.add((prop_uri, RDFS.range, target_uri))

        # Add label
        if self.config.generate_labels:
            label = rel.label or self._camel_to_label(prop_name)
            self._graph.add(
                (prop_uri, RDFS.label, Literal(label, lang=self.config.language))
            )

        # Add cardinality constraints as comments for now
        # Full OWL restrictions would be more complex
        if rel.source_cardinality or rel.target_cardinality:
            card_note = f"Cardinality: {rel.source_cardinality or '*'} -> {rel.target_cardinality or '*'}"
            # Could add as annotation or restriction

    def _get_namespace_for_class(self, cls: PumlClass) -> Namespace:
        """Get the appropriate namespace for a class."""
        if cls.package and cls.package in self._namespaces:
            return self._namespaces[cls.package]
        return self._namespaces[None]

    def _get_namespace_for_class_uri(self, class_uri: URIRef) -> Namespace:
        """Get the namespace containing a class URI."""
        uri_str = str(class_uri)
        for ns in self._namespaces.values():
            if uri_str.startswith(str(ns)):
                return ns
        return self._namespaces["default"]

    def _map_datatype(self, type_name: str) -> URIRef:
        """Map a PlantUML type name to XSD datatype."""
        normalised = type_name.lower().strip()

        if normalised in XSD_TYPE_MAP:
            return XSD_TYPE_MAP[normalised]

        # Check for qualified XSD types
        if type_name.startswith("xsd:"):
            local = type_name[4:]
            return XSD[local]

        # Default to string
        self._warnings.append(f"Unknown datatype '{type_name}', defaulting to xsd:string")
        return XSD.string

    def _camel_to_label(self, name: str) -> str:
        """Convert camelCase or PascalCase to readable label.

        Examples:
            'FloorArea' -> 'floor area'
            'hasBuilding' -> 'has building'
            'constructionYear' -> 'construction year'
        """
        # Insert space before uppercase letters
        result = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
        # Insert space between consecutive uppercase and following lowercase
        result = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", result)
        return result.lower()

    def _label_to_property_name(self, label: str) -> str:
        """Convert a relationship label to a valid property name.

        If the label is already a valid identifier (no spaces), preserve it.
        Otherwise, convert multi-word labels to camelCase.

        Examples:
            'hasFloor' -> 'hasFloor' (preserved)
            'has floor' -> 'hasFloor' (converted)
            'is located in' -> 'isLocatedIn'
        """
        label = label.strip()

        # If no spaces, assume it's already a valid property name - preserve case
        if " " not in label:
            # Just remove non-alphanumeric characters
            return re.sub(r"[^a-zA-Z0-9]", "", label)

        # Multi-word: convert to camelCase
        words = label.split()
        if not words:
            return "property"

        # First word lowercase, rest capitalised
        result = words[0].lower()
        for word in words[1:]:
            result += word.capitalize()

        # Remove non-alphanumeric characters
        result = re.sub(r"[^a-zA-Z0-9]", "", result)

        return result
