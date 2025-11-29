"""ODM RDF Profile renderer for PlantUML diagrams.

This module provides ODM (Ontology Definition Metamodel) compliant rendering
of RDF/OWL ontologies as PlantUML class diagrams. The ODM is an OMG standard
that defines UML profiles for RDF and OWL modelling.

Key differences from the default renderer:
- Uses standard ODM stereotype names (<<owlClass>>, <<objectProperty>>, etc.)
- Supports rendering properties as UML associations (not just classes)
- Uses <<individual>> stereotype for instances
- Follows OMG ODM 1.1 specification conventions

References:
- OMG ODM 1.1: https://www.omg.org/spec/ODM/1.1/
- W3C OWL UML Concrete Syntax: https://www.w3.org/2007/OWL/wiki/UML_Concrete_Syntax
"""

from pathlib import Path
from typing import Optional

from rdflib import Graph, URIRef, RDF, RDFS, Literal
from rdflib.namespace import OWL, XSD


# ODM stereotype mappings for RDF/OWL concepts
# These follow the OMG ODM 1.1 specification naming conventions
ODM_CLASS_STEREOTYPES = {
    str(OWL.Class): "owlClass",
    str(RDFS.Class): "rdfsClass",
    str(OWL.Restriction): "restriction",
    str(RDFS.Datatype): "rdfsDatatype",
    str(OWL.Ontology): "owlOntology",
}

ODM_PROPERTY_STEREOTYPES = {
    str(OWL.ObjectProperty): "objectProperty",
    str(OWL.DatatypeProperty): "datatypeProperty",
    str(OWL.AnnotationProperty): "annotationProperty",
    str(OWL.OntologyProperty): "ontologyProperty",
    str(OWL.FunctionalProperty): "functionalProperty",
    str(OWL.InverseFunctionalProperty): "inverseFunctionalProperty",
    str(OWL.SymmetricProperty): "symmetricProperty",
    str(OWL.TransitiveProperty): "transitiveProperty",
    str(RDF.Property): "rdfProperty",
}

ODM_INDIVIDUAL_STEREOTYPE = "individual"

# Relationship stereotypes
ODM_RELATIONSHIP_STEREOTYPES = {
    "subclass": "rdfsSubClassOf",
    "subproperty": "rdfsSubPropertyOf",
    "type": "rdfType",
    "domain": "rdfsDomain",
    "range": "rdfsRange",
    "equivalent_class": "owlEquivalentClass",
    "disjoint_with": "owlDisjointWith",
    "inverse_of": "owlInverseOf",
}


def qname(graph: Graph, uri: URIRef) -> str:
    """Get qualified name (prefix:local) for a URI.

    Args:
        graph: RDF graph with namespace bindings
        uri: URI to convert to QName

    Returns:
        QName string (e.g., 'ex:Animal') or full URI if no prefix found
    """
    try:
        return graph.namespace_manager.normalizeUri(uri)
    except Exception:
        return str(uri)


def local_name(graph: Graph, uri: URIRef) -> str:
    """Get local name only (without prefix) for a URI.

    Args:
        graph: RDF graph with namespace bindings
        uri: URI to extract local name from

    Returns:
        Local name string (e.g., 'Animal' from 'ex:Animal')
    """
    qn = qname(graph, uri)
    if ":" in qn:
        return qn.split(":", 1)[1]
    # Try to extract from full URI
    uri_str = str(uri)
    if "#" in uri_str:
        return uri_str.split("#")[-1]
    if "/" in uri_str:
        return uri_str.split("/")[-1]
    return uri_str


def plantuml_identifier(graph: Graph, uri: URIRef) -> str:
    """Convert RDF URI to PlantUML identifier using dot notation.

    PlantUML uses package.Class notation. This converts RDF QNames
    to proper PlantUML identifiers.

    Args:
        graph: RDF graph with namespace bindings
        uri: URI to convert

    Returns:
        PlantUML identifier string (e.g., 'ex.Animal')
    """
    qn = qname(graph, uri)
    if ":" in qn:
        prefix, local = qn.split(":", 1)
        return f"{prefix}.{local}"
    return qn


def escape_plantuml(text: str) -> str:
    """Escape special characters for PlantUML.

    Args:
        text: Text to escape

    Returns:
        Escaped text safe for PlantUML
    """
    return text.replace('"', "'").replace("\n", " ").strip()


def safe_label(graph: Graph, uri: URIRef) -> str:
    """Get a safe display label for an entity.

    Uses rdfs:label if available, otherwise falls back to QName.

    Args:
        graph: RDF graph containing the entity
        uri: URI to get label for

    Returns:
        Safe string for use in PlantUML
    """
    labels = list(graph.objects(uri, RDFS.label))
    if labels:
        return escape_plantuml(str(labels[0]))
    return qname(graph, uri)


class ODMRenderer:
    """Renders RDF ontologies as ODM-compliant PlantUML class diagrams.

    This renderer follows the OMG Ontology Definition Metamodel (ODM) 1.1
    specification for representing RDF and OWL constructs in UML.

    Key features:
    - Standard ODM stereotype names (<<owlClass>>, <<objectProperty>>, etc.)
    - Properties can render as associations or classes
    - Individuals use <<individual>> stereotype
    - Domain/range shown with <<rdfsDomain>>/<<rdfsRange>> stereotypes

    Attributes:
        graph: RDF graph being rendered
        entities: Dictionary of selected entities to render
        style: Optional style scheme
        layout: Optional layout configuration
        property_style: How to render properties ('class' or 'association')
    """

    def __init__(
        self,
        graph: Graph,
        entities: dict[str, set[URIRef]],
        style: Optional[object] = None,
        layout: Optional[object] = None,
        property_style: str = "class",
    ):
        """Initialise ODM renderer.

        Args:
            graph: RDF graph containing the entities
            entities: Dictionary of entity sets (classes, properties, instances)
            style: Optional style scheme to apply
            layout: Optional layout configuration
            property_style: How to render properties - 'class' (as UML classes)
                          or 'association' (as UML associations)
        """
        self.graph = graph
        self.entities = entities
        self.style = style
        self.layout = layout
        self.property_style = property_style
        self._note_counter = 0

    def _get_arrow_direction(self) -> str:
        """Get arrow direction hint from layout config.

        Returns:
            Direction string: 'u', 'd', 'l', 'r', or ''
        """
        if self.layout and hasattr(self.layout, 'arrow_direction'):
            direction_map = {
                "up": "u",
                "down": "d",
                "left": "l",
                "right": "r",
            }
            return direction_map.get(self.layout.arrow_direction, "u")
        return "u"

    def _get_class_stereotype(self, cls: URIRef) -> str:
        """Get ODM stereotype for a class entity.

        Args:
            cls: Class URI

        Returns:
            ODM stereotype string like <<owlClass>> or <<rdfsClass>>
        """
        types = list(self.graph.objects(cls, RDF.type))

        for t in types:
            type_str = str(t)
            if type_str in ODM_CLASS_STEREOTYPES:
                return f"<<{ODM_CLASS_STEREOTYPES[type_str]}>>"

        # Default to rdfsClass
        return "<<rdfsClass>>"

    def _get_property_stereotype(self, prop: URIRef) -> str:
        """Get ODM stereotype for a property entity.

        Includes all applicable property characteristics as stereotypes.

        Args:
            prop: Property URI

        Returns:
            ODM stereotype string, possibly with multiple stereotypes
        """
        types = list(self.graph.objects(prop, RDF.type))
        stereotypes = []

        # Primary type stereotype
        for t in types:
            type_str = str(t)
            if type_str in ODM_PROPERTY_STEREOTYPES:
                stereotypes.append(ODM_PROPERTY_STEREOTYPES[type_str])

        if not stereotypes:
            stereotypes.append("rdfProperty")

        # Check for property characteristics
        characteristic_types = [
            (OWL.FunctionalProperty, "functional"),
            (OWL.InverseFunctionalProperty, "inverseFunctional"),
            (OWL.SymmetricProperty, "symmetric"),
            (OWL.TransitiveProperty, "transitive"),
            (OWL.ReflexiveProperty, "reflexive"),
            (OWL.IrreflexiveProperty, "irreflexive"),
            (OWL.AsymmetricProperty, "asymmetric"),
        ]

        for prop_type, short_name in characteristic_types:
            if prop_type in types and short_name not in stereotypes:
                # Only add if not already primary type
                if short_name not in [s.replace("Property", "") for s in stereotypes]:
                    stereotypes.append(short_name)

        return f"<<{', '.join(stereotypes)}>>"

    def _get_instance_stereotype(self, instance: URIRef) -> str:
        """Get ODM stereotype for an individual.

        For ODM compliance, individuals use <<individual>> stereotype,
        optionally with their class types shown.

        Args:
            instance: Instance URI

        Returns:
            ODM stereotype string
        """
        types = list(self.graph.objects(instance, RDF.type))

        # Filter out metaclass types
        metaclass_uris = {
            OWL.Class, RDFS.Class, OWL.ObjectProperty,
            OWL.DatatypeProperty, OWL.AnnotationProperty,
            RDF.Property, OWL.NamedIndividual
        }

        type_names = []
        for t in types:
            if t not in metaclass_uris:
                type_names.append(qname(self.graph, t))

        if type_names:
            # Show individual stereotype with type information
            return f"<<{ODM_INDIVIDUAL_STEREOTYPE}: {', '.join(sorted(type_names)[:3])}>>"

        return f"<<{ODM_INDIVIDUAL_STEREOTYPE}>>"

    def _get_colour_spec(self, entity: URIRef, is_instance: bool = False) -> str:
        """Get PlantUML colour specification for an entity.

        Uses the style system to look up colours based on:
        - Explicit type mappings (by_type)
        - Inheritance through rdfs:subClassOf hierarchy
        - Namespace-based defaults (by_namespace)
        - Global defaults

        For instances, uses get_instance_style() which supports:
        - Instance-specific type mappings
        - inherit_class_text for text colour from class hierarchy
        - Black fill with coloured text/border

        Args:
            entity: Entity URI
            is_instance: Whether this is an instance (uses instance styling)

        Returns:
            PlantUML colour specification string or empty string
        """
        if not self.style:
            return ""

        try:
            if hasattr(self.style, 'get_class_style'):
                palette = self.style.get_class_style(self.graph, entity, is_instance=is_instance)
                if palette and hasattr(palette, 'to_plantuml'):
                    colour_spec = palette.to_plantuml()
                    if colour_spec:
                        return f" {colour_spec}"
        except Exception:
            # If style lookup fails, continue without styling
            pass

        return ""

    def _get_property_colour_spec(self, prop: URIRef) -> str:
        """Get PlantUML colour specification for a property.

        Args:
            prop: Property URI

        Returns:
            PlantUML colour specification string
        """
        if self.style and hasattr(self.style, 'get_property_style'):
            try:
                palette = self.style.get_property_style(self.graph, prop)
                if palette and hasattr(palette, 'to_plantuml'):
                    colour_spec = palette.to_plantuml()
                    if colour_spec:
                        return f" {colour_spec}"
            except Exception:
                pass

        # Default grey for properties
        return " #CCCCCC"

    def _curie_to_plantuml_id(self, curie: str) -> str:
        """Convert a CURIE (e.g., 'building:Building') to PlantUML identifier.

        This is used by layout together/hints which use CURIEs in config.

        Args:
            curie: CURIE string like 'building:Building'

        Returns:
            PlantUML identifier like 'building.Building'
        """
        if ":" in curie:
            prefix, local = curie.split(":", 1)
            return f"{prefix}.{local}"
        return curie

    def render_class(self, cls: URIRef) -> list[str]:
        """Render a class as an ODM-compliant PlantUML class.

        Args:
            cls: Class URI to render

        Returns:
            List of PlantUML lines
        """
        lines = []

        class_id = plantuml_identifier(self.graph, cls)
        stereotype = self._get_class_stereotype(cls)
        colour_spec = self._get_colour_spec(cls)

        # Get display name - use rdfs:label if different from QName
        display_name = safe_label(self.graph, cls)
        class_qname = qname(self.graph, cls)

        if display_name != class_qname:
            lines.append(f'class "{display_name}" as {class_id} {stereotype}{colour_spec}')
        else:
            lines.append(f"class {class_id} {stereotype}{colour_spec}")

        return lines

    def render_property_as_class(self, prop: URIRef) -> list[str]:
        """Render a property as an ODM-compliant PlantUML class.

        Args:
            prop: Property URI to render

        Returns:
            List of PlantUML lines
        """
        lines = []

        prop_id = plantuml_identifier(self.graph, prop)
        stereotype = self._get_property_stereotype(prop)
        colour_spec = self._get_property_colour_spec(prop)

        # Get display name - use rdfs:label if different from QName
        display_name = safe_label(self.graph, prop)
        prop_qname = qname(self.graph, prop)

        if display_name != prop_qname:
            lines.append(f'class "{display_name}" as {prop_id} {stereotype}{colour_spec}')
        else:
            lines.append(f"class {prop_id} {stereotype}{colour_spec}")

        return lines

    def render_individual(self, instance: URIRef) -> list[str]:
        """Render an individual as an ODM-compliant PlantUML class.

        Instances are styled using the instance styling rules which typically
        include black fill with text colour inherited from their class hierarchy.

        Args:
            instance: Instance URI to render

        Returns:
            List of PlantUML lines
        """
        lines = []

        instance_id = plantuml_identifier(self.graph, instance)
        stereotype = self._get_instance_stereotype(instance)
        # Pass is_instance=True to get instance-specific styling
        colour_spec = self._get_colour_spec(instance, is_instance=True)

        # Get display name - use rdfs:label if different from QName
        display_name = safe_label(self.graph, instance)
        instance_qname = qname(self.graph, instance)

        if display_name != instance_qname:
            lines.append(f'class "{display_name}" as {instance_id} {stereotype}{colour_spec}')
        else:
            lines.append(f"class {instance_id} {stereotype}{colour_spec}")

        return lines

    def render_subclass_relationships(self) -> list[str]:
        """Render rdfs:subClassOf as UML generalisations.

        Returns:
            List of PlantUML relationship lines
        """
        lines = []
        direction = self._get_arrow_direction()

        for cls in self.entities.get("classes", set()):
            for parent in self.graph.objects(cls, RDFS.subClassOf):
                if parent in self.entities.get("classes", set()):
                    child_id = plantuml_identifier(self.graph, cls)
                    parent_id = plantuml_identifier(self.graph, parent)
                    lines.append(
                        f"{child_id} -{direction}-|> {parent_id}"
                    )

        return lines

    def render_subproperty_relationships(self) -> list[str]:
        """Render rdfs:subPropertyOf as UML generalisations.

        Returns:
            List of PlantUML relationship lines
        """
        lines = []
        direction = self._get_arrow_direction()

        all_props = (
            self.entities.get("object_properties", set()) |
            self.entities.get("datatype_properties", set()) |
            self.entities.get("annotation_properties", set())
        )

        for prop in all_props:
            for parent_prop in self.graph.objects(prop, RDFS.subPropertyOf):
                if parent_prop in all_props:
                    child_id = plantuml_identifier(self.graph, prop)
                    parent_id = plantuml_identifier(self.graph, parent_prop)
                    lines.append(
                        f"{child_id} -{direction}-|> {parent_id}"
                    )

        return lines

    def render_type_relationships(self) -> list[str]:
        """Render rdf:type relationships with <<rdfType>> stereotype.

        Uses arrow colour from style config if available.

        Returns:
            List of PlantUML relationship lines
        """
        lines = []
        direction = self._get_arrow_direction()

        metaclass_uris = {
            OWL.Class, RDFS.Class, OWL.ObjectProperty,
            OWL.DatatypeProperty, OWL.AnnotationProperty
        }

        # Get arrow colour from style config
        arrow_color = "#FF0000"  # Default red
        if self.style and hasattr(self.style, 'arrow_colors'):
            arrow_color = self.style.arrow_colors.get_color("type")

        for instance in self.entities.get("instances", set()):
            instance_id = plantuml_identifier(self.graph, instance)

            for cls in self.graph.objects(instance, RDF.type):
                if cls in metaclass_uris:
                    continue

                if cls in self.entities.get("classes", set()):
                    class_id = plantuml_identifier(self.graph, cls)
                    lines.append(
                        f"{instance_id} -{direction}-[{arrow_color}]-> {class_id} : <<rdfType>>"
                    )

        return lines

    def render_domain_range_relationships(self) -> list[str]:
        """Render domain and range with ODM stereotypes.

        Returns:
            List of PlantUML relationship lines
        """
        lines = []
        direction = self._get_arrow_direction()

        all_props = (
            self.entities.get("object_properties", set()) |
            self.entities.get("datatype_properties", set()) |
            self.entities.get("annotation_properties", set())
        )

        for prop in all_props:
            prop_id = plantuml_identifier(self.graph, prop)

            # Render domain relationships
            for domain in self.graph.objects(prop, RDFS.domain):
                if domain in self.entities.get("classes", set()):
                    domain_id = plantuml_identifier(self.graph, domain)
                    lines.append(
                        f"{prop_id} -{direction}-> {domain_id} : <<rdfsDomain>>"
                    )

            # Render range relationships
            for range_cls in self.graph.objects(prop, RDFS.range):
                if range_cls in self.entities.get("classes", set()):
                    range_id = plantuml_identifier(self.graph, range_cls)
                    lines.append(
                        f"{prop_id} -{direction}-> {range_id} : <<rdfsRange>>"
                    )

        return lines

    def render_instance_properties(self) -> list[str]:
        """Render object property relationships between individuals.

        Returns:
            List of PlantUML relationship lines
        """
        lines = []
        direction = self._get_arrow_direction()

        obj_props = self.entities.get("object_properties", set())
        instances = self.entities.get("instances", set())

        for subj in instances:
            for prop in obj_props:
                for obj in self.graph.objects(subj, prop):
                    if obj in instances:
                        subj_id = plantuml_identifier(self.graph, subj)
                        obj_id = plantuml_identifier(self.graph, obj)
                        prop_qn = qname(self.graph, prop)
                        lines.append(
                            f"{subj_id} -{direction}-> {obj_id} : {prop_qn}"
                        )

        return lines

    def render_together_blocks(self) -> list[str]:
        """Render PlantUML 'together' blocks from layout config.

        Together blocks group classes so they are placed adjacent
        in the diagram.

        Returns:
            List of PlantUML lines for together blocks
        """
        if not self.layout or not hasattr(self.layout, 'get_together_blocks'):
            return []

        return self.layout.get_together_blocks(
            id_resolver=self._curie_to_plantuml_id
        )

    def render_layout_hints(self) -> list[str]:
        """Render hidden links from layout hints.

        Hidden links influence PlantUML's layout engine without
        being visible in the diagram.

        Returns:
            List of PlantUML hidden link lines
        """
        if not self.layout or not hasattr(self.layout, 'get_hidden_links'):
            return []

        return self.layout.get_hidden_links(
            id_resolver=self._curie_to_plantuml_id
        )

    def render_datatype_property_notes(self) -> list[str]:
        """Render datatype property values as notes.

        Returns:
            List of PlantUML lines for notes
        """
        lines = []
        direction = self._get_arrow_direction()

        datatype_props = self.entities.get("datatype_properties", set())
        instances = self.entities.get("instances", set())

        for instance in instances:
            instance_id = plantuml_identifier(self.graph, instance)

            for prop in datatype_props:
                for value in self.graph.objects(instance, prop):
                    if isinstance(value, Literal):
                        self._note_counter += 1
                        note_id = f"N{self._note_counter}"
                        value_str = escape_plantuml(str(value))
                        prop_local = local_name(self.graph, prop)

                        lines.append(f'note "{prop_local}: {value_str}" as {note_id}')
                        lines.append(f"{instance_id} .{direction}. {note_id}")

        return lines

    def render(self) -> str:
        """Render complete ODM-compliant PlantUML diagram.

        Returns:
            Complete PlantUML diagram as string
        """
        lines = ["@startuml", ""]

        # Add title comment
        lines.append("' ODM RDF Profile compliant diagram")
        lines.append("' Generated by rdf-construct")
        lines.append("")

        # Add layout directives
        if self.layout and hasattr(self.layout, 'get_plantuml_directives'):
            directives = self.layout.get_plantuml_directives()
            lines.extend(directives)
            lines.append("")

        # Add style directives
        if self.style and hasattr(self.style, 'get_plantuml_directives'):
            directives = self.style.get_plantuml_directives()
            if directives:
                lines.extend(directives)
                lines.append("")

        # Add together blocks (grouping hints - must come before class definitions)
        together_blocks = self.render_together_blocks()
        if together_blocks:
            lines.append("' Layout groupings")
            lines.extend(together_blocks)

        # Render classes
        classes = sorted(
            self.entities.get("classes", set()),
            key=lambda x: qname(self.graph, x)
        )
        for cls in classes:
            lines.extend(self.render_class(cls))

        if classes:
            lines.append("")

        # Render properties (as classes in this mode)
        all_props = sorted(
            self.entities.get("object_properties", set()) |
            self.entities.get("datatype_properties", set()) |
            self.entities.get("annotation_properties", set()),
            key=lambda x: qname(self.graph, x)
        )
        for prop in all_props:
            lines.extend(self.render_property_as_class(prop))

        if all_props:
            lines.append("")

        # Render individuals
        instances = sorted(
            self.entities.get("instances", set()),
            key=lambda x: qname(self.graph, x)
        )
        for instance in instances:
            lines.extend(self.render_individual(instance))

        if instances:
            lines.append("")

        # Render relationships
        lines.extend(self.render_subclass_relationships())
        lines.extend(self.render_subproperty_relationships())
        lines.extend(self.render_type_relationships())
        lines.extend(self.render_domain_range_relationships())
        lines.extend(self.render_instance_properties())

        # Add hidden layout hints (after visible relationships)
        layout_hints = self.render_layout_hints()
        if layout_hints:
            lines.append("")
            lines.append("' Hidden layout hints")
            lines.extend(layout_hints)

        if any([classes, all_props, instances]):
            lines.append("")

        # Render datatype property values as notes
        lines.extend(self.render_datatype_property_notes())

        lines.append("")
        lines.append("@enduml")

        return "\n".join(lines)


def render_odm_plantuml(
    graph: Graph,
    entities: dict[str, set[URIRef]],
    output_path: Optional[Path] = None,
    style: Optional[object] = None,
    layout: Optional[object] = None,
    property_style: str = "class",
) -> str:
    """Render entities as ODM-compliant PlantUML class diagram.

    Args:
        graph: RDF graph containing entities
        entities: Dictionary of entity sets to render
        output_path: Optional path to write PlantUML file
        style: Optional style scheme
        layout: Optional layout configuration
        property_style: How to render properties ('class' or 'association')

    Returns:
        PlantUML diagram text
    """
    renderer = ODMRenderer(
        graph, entities,
        style=style,
        layout=layout,
        property_style=property_style
    )
    diagram = renderer.render()

    if output_path:
        output_path.write_text(diagram, encoding="utf-8")

    return diagram
