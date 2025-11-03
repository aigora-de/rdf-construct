"""PlantUML renderer with everything-as-class approach.

Renders RDF entities as PlantUML class diagrams where:
- Classes, properties, and instances all render as UML classes
- Stereotypes indicate entity type
- Relationships use appropriately styled arrows
- Datatype property values render as notes with dotted connections
"""

from pathlib import Path
from typing import Optional
from collections import defaultdict

from rdflib import Graph, URIRef, RDF, RDFS, Literal
from rdflib.namespace import OWL, XSD


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


def safe_label(graph: Graph, uri: URIRef, camelcase: bool = False) -> str:
    """Get a safe label for display in PlantUML.

    Uses rdfs:label if available, otherwise falls back to QName.
    Strips quotes and handles multi-line labels.

    Args:
        graph: RDF graph containing the entity
        uri: URI to get label for
        camelcase: Whether to convert spaces to camelCase (for property names)

    Returns:
        Safe string for use in PlantUML
    """
    # Try to get rdfs:label
    labels = list(graph.objects(uri, RDFS.label))
    if labels:
        label = str(labels[0])
        # Clean up label for PlantUML
        label = label.replace('"', "'").replace("\n", " ").strip()

        # Convert spaces to camelCase only if requested (for property names)
        if camelcase:
            words = label.split()
            if len(words) > 1:
                # Ensure first word is lowercase for camelCase properties
                label = words[0].lower() + "".join(word.capitalize() for word in words[1:])

        return label

    # Fallback to QName
    qn = qname(graph, uri)

    # For camelCase, ensure first character is lowercase
    if camelcase and qn:
        # Only lowercase the local part after the namespace prefix
        if ":" in qn:
            prefix, local = qn.split(":", 1)
            if local:
                local = local[0].lower() + local[1:]
                qn = f"{prefix}:{local}"
        else:
            qn = qn[0].lower() + qn[1:]

    return qn


def escape_plantuml(text: str) -> str:
    """Escape special characters for PlantUML.

    Args:
        text: Text to escape

    Returns:
        Escaped text safe for PlantUML
    """
    # PlantUML is generally forgiving, but we'll handle basic escaping
    return text.replace('"', "'")


def plantuml_identifier(graph: Graph, uri: URIRef) -> str:
    """Convert RDF URI to PlantUML identifier using dot notation.

    PlantUML uses package.Class notation, not prefix:Class notation.
    This function converts RDF QNames to proper PlantUML identifiers.

    Examples:
        "building:Building" → "building.Building"
        "ies:Entity" → "ies.Entity"

    Args:
        graph: RDF graph with namespace bindings
        uri: URI to convert to PlantUML identifier

    Returns:
        PlantUML identifier string with dot notation
    """
    qn = qname(graph, uri)

    # Convert prefix:local to prefix.local for PlantUML
    if ":" in qn:
        prefix, local = qn.split(":", 1)
        return f"{prefix}.{local}"

    # No namespace prefix - return as is
    return qn


class PlantUMLRenderer:
    """Renders RDF entities as styled PlantUML class diagrams.

    Everything renders as a UML class:
    - OWL/RDFS classes with stereotypes like <<owl:Class>>
    - Properties as classes with stereotypes like <<owl:ObjectProperty>>
    - Instances as classes with stereotypes showing their types

    Relationships:
    - rdfs:subClassOf and rdfs:subPropertyOf: --|> with labels
    - rdf:type: red --> with <<rdf:type>> [#red] label
    - domain/range: black --> with <<rdfs:domain>>/<<rdfs:range>> labels
    - Object properties between instances: black --> with property name
    - Datatype properties: dotted line to note .. with property name

    Attributes:
        graph: RDF graph being rendered
        entities: Dictionary of selected entities to render
        style: Style scheme to apply (optional)
        layout: Layout configuration to apply (optional)
    """

    def __init__(
        self,
        graph: Graph,
        entities: dict[str, set[URIRef]],
        style: Optional = None,  # Will import StyleScheme type hint later
        layout: Optional = None,  # Will import LayoutConfig type hint later
    ):
        """Initialise renderer with graph, entities, and optional styling.

        Args:
            graph: RDF graph containing the entities
            entities: Dictionary of entity sets (classes, properties, instances)
            style: Optional style scheme to apply
            layout: Optional layout configuration to apply
        """
        self.graph = graph
        self.entities = entities
        self.style = style
        self.layout = layout
        self._note_counter = 0  # For generating unique note IDs

    def _get_arrow_direction(self) -> str:
        """Get arrow direction hint from layout config.

        Returns:
            Direction string: 'u' (up), 'd' (down), 'l' (left), 'r' (right), or ''
        """
        if self.layout and self.layout.arrow_direction:
            direction_map = {
                "up": "u",
                "down": "d",
                "left": "l",
                "right": "r",
            }
            return direction_map.get(self.layout.arrow_direction, "u")
        return "u"  # Default: up (for top-to-bottom layout)

    def _get_class_stereotype(self, cls: URIRef) -> str:
        """Get stereotype for a class entity.

        Checks rdf:type to determine if it's owl:Class, rdfs:Class, etc.

        Args:
            cls: Class URI

        Returns:
            Stereotype string like <<owl:Class>> or <<rdfs:Class>>
        """
        # Check if it's typed as owl:Class or rdfs:Class
        types = list(self.graph.objects(cls, RDF.type))

        for t in types:
            type_qn = qname(self.graph, t)
            if type_qn in ("owl:Class", "rdfs:Class", "owl:Restriction"):
                return f"<< (C, #FFFFFF) {type_qn} >>"

        # Default to rdfs:Class if not explicitly typed
        return "<< (C, #FFFFFF) rdfs:Class >>"

    def _get_property_stereotype(self, prop: URIRef) -> str:
        """Get stereotype for a property entity.

        Args:
            prop: Property URI

        Returns:
            Stereotype string like <<owl:ObjectProperty>>
        """
        types = list(self.graph.objects(prop, RDF.type))

        for t in types:
            type_qn = qname(self.graph, t)
            if type_qn in (
                "owl:ObjectProperty",
                "owl:DatatypeProperty",
                "owl:AnnotationProperty",
                "rdf:Property",
            ):
                if type_qn == "owl:ObjectProperty":
                    type_symbol = "O"
                elif type_qn == "owl:DatatypeProperty":
                    type_symbol = "D"
                elif type_qn == "owl:AnnotationProperty":
                    type_symbol = "A"
                else:
                    type_symbol = "P"
                return f"<< ({type_symbol}, #FFFFFF) {type_qn} >>"

        # Default
        return "<< (P, #FFFFFF) rdf:Property >>"

    def _get_instance_stereotype(self, instance: URIRef) -> str:
        """Get stereotype for an instance showing all its types.

        For instances with multiple types, create comma-separated stereotype.
        Example: <<ies:Entity>> or <<building:Structure, ies:Asset>>

        Args:
            instance: Instance URI

        Returns:
            Stereotype string with all types
        """
        types = list(self.graph.objects(instance, RDF.type))

        # Filter out property/class types (instances shouldn't have these)
        type_qnames = []
        for t in types:
            type_qn = qname(self.graph, t)
            # Skip metaclass types
            if type_qn not in ("owl:Class", "rdfs:Class", "owl:ObjectProperty",
                             "owl:DatatypeProperty", "owl:AnnotationProperty"):
                type_qnames.append(type_qn)

        if type_qnames:
            return f"<< (I, #FFFFFF) {', '.join(type_qnames)} >>"

        # Fallback if no suitable types found
        return " (I, #FFFFFF) <<owl:NamedIndividual>>"

    def render_class(self, cls: URIRef) -> list[str]:
        """Render a RDF concept as PlantUML class.

        Classes render without attributes (datatype properties become
        dotted-line relationships instead).

        Args:
            cls: Class URI to render

        Returns:
            List of PlantUML lines for this class
        """
        lines = []

        class_name = plantuml_identifier(self.graph, cls)
        stereotype = self._get_class_stereotype(cls)

        # Get colour styling if configured
        color_spec = ""
        if self.style:
            # Use style system if available
            palette = self.style.get_class_style(self.graph, cls, is_instance=False)
            if palette and hasattr(palette, 'to_plantuml'):
                color_spec = f" {palette.to_plantuml()}"

        # Render as empty class with stereotype
        lines.append(f"class {class_name} {stereotype}{color_spec}")

        return lines

    def render_property(self, prop: URIRef) -> list[str]:
        """Render a property as a class.

        Properties render as gray classes with appropriate stereotypes.

        Args:
            prop: Property URI to render

        Returns:
            List of PlantUML lines for this property
        """
        lines = []

        prop_name = plantuml_identifier(self.graph, prop)
        stereotype = self._get_property_stereotype(prop)

        # Properties are typically gray
        # Use style system if available, otherwise default gray
        color_spec = " #CCCCCC"
        if self.style:
            palette = self.style.get_property_style(self.graph, prop)
            if palette and hasattr(palette, 'to_plantuml'):
                color_spec = f" {palette.to_plantuml()}"

        lines.append(f"class {prop_name} {stereotype}{color_spec}")

        return lines

    def render_instance(self, instance: URIRef) -> list[str]:
        """Render an instance as a class with type stereotype.

        Args:
            instance: Instance URI to render

        Returns:
            List of PlantUML lines for this instance
        """
        lines = []

        instance_name = plantuml_identifier(self.graph, instance)
        instance_label = safe_label(self.graph, instance, camelcase=False)
        stereotype = self._get_instance_stereotype(instance)

        # Get colour styling for instances
        color_spec = ""
        if self.style:
            palette = self.style.get_class_style(self.graph, instance, is_instance=True)
            if palette and hasattr(palette, 'to_plantuml'):
                color_spec = f" {palette.to_plantuml()}"

        # Render as class with stereotype and optional custom label
        if instance_label != qname(self.graph, instance):
            lines.append(f'class "{instance_label}" as {instance_name} {stereotype}{color_spec}')
        else:
            lines.append(f"class {instance_name} {stereotype}{color_spec}")

        return lines

    def render_subclass_relationships(self) -> list[str]:
        """Render rdfs:subClassOf relationships with labels.

        Uses layout-configured arrow direction if available.

        Returns:
            List of PlantUML relationship lines
        """
        lines = []
        direction = self._get_arrow_direction()

        for cls in self.entities.get("classes", set()):
            for parent in self.graph.objects(cls, RDFS.subClassOf):
                if parent in self.entities.get("classes", set()):
                    child_name = plantuml_identifier(self.graph, cls)
                    parent_name = plantuml_identifier(self.graph, parent)

                    lines.append(
                        f"{child_name} -{direction}-|> {parent_name} : <<rdfs:subClassOf>>"
                    )

        return lines

    def render_subproperty_relationships(self) -> list[str]:
        """Render rdfs:subPropertyOf relationships with labels.

        Returns:
            List of PlantUML relationship lines
        """
        lines = []
        direction = self._get_arrow_direction()

        # Collect all properties
        all_props = (
            self.entities.get("object_properties", set()) |
            self.entities.get("datatype_properties", set()) |
            self.entities.get("annotation_properties", set())
        )

        for prop in all_props:
            for parent_prop in self.graph.objects(prop, RDFS.subPropertyOf):
                if parent_prop in all_props:
                    child_name = plantuml_identifier(self.graph, prop)
                    parent_name = plantuml_identifier(self.graph, parent_prop)

                    lines.append(
                        f"{child_name} -{direction}-|> {parent_name} : <<rdfs:subPropertyOf>>"
                    )

        return lines

    def render_type_relationships(self) -> list[str]:
        """Render rdf:type relationships as red arrows.

        Red arrows from instances to their type classes.

        Returns:
            List of PlantUML relationship lines
        """
        lines = []
        direction = self._get_arrow_direction()

        for instance in self.entities.get("instances", set()):
            instance_name = plantuml_identifier(self.graph, instance)

            for cls in self.graph.objects(instance, RDF.type):
                # Skip metaclass types
                type_qn = qname(self.graph, cls)
                if type_qn in ("owl:Class", "rdfs:Class", "owl:ObjectProperty",
                               "owl:DatatypeProperty", "owl:AnnotationProperty"):
                    continue

                if cls in self.entities.get("classes", set()):
                    class_name = plantuml_identifier(self.graph, cls)

                    # Get arrow color from style
                    arrow_color = "#FF0000"  # Default red
                    if self.style and hasattr(self.style, 'arrow_colors'):
                        arrow_color = self.style.arrow_colors.get_color("type")

                    lines.append(f"{instance_name} -{direction}[{arrow_color}]-> {class_name} : <<rdf:type>>")

        return lines

    def render_property_domain_range(self) -> list[str]:
        """Render domain and range relationships from property classes.

        Black arrows from property to domain/range classes.

        Returns:
            List of PlantUML relationship lines
        """
        lines = []
        direction = self._get_arrow_direction()

        # Collect all properties
        all_props = (
            self.entities.get("object_properties", set()) |
            self.entities.get("datatype_properties", set()) |
            self.entities.get("annotation_properties", set())
        )

        for prop in all_props:
            prop_name = plantuml_identifier(self.graph, prop)

            # Render domain relationships
            for domain in self.graph.objects(prop, RDFS.domain):
                if domain in self.entities.get("classes", set()):
                    domain_name = plantuml_identifier(self.graph, domain)
                    lines.append(
                        f"{prop_name} -{direction}-> {domain_name} : <<rdfs:domain>>"
                    )

            # Render range relationships
            for range_cls in self.graph.objects(prop, RDFS.range):
                # Check if range is a class (for object properties)
                if range_cls in self.entities.get("classes", set()):
                    range_name = plantuml_identifier(self.graph, range_cls)
                    lines.append(
                        f"{prop_name} -{direction}-> {range_name} : <<rdfs:range>>"
                    )
                # For datatype properties, range might be XSD type - skip those

        return lines

    def render_instance_object_properties(self) -> list[str]:
        """Render object property relationships between instances.

        Black arrows labeled with property name (camelCase).

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
                        subj_name = plantuml_identifier(self.graph, subj)
                        obj_name = plantuml_identifier(self.graph, obj)
                        prop_qname = qname(self.graph, prop)

                        # Ensure property name is camelCase
                        prop_label = safe_label(self.graph, prop, camelcase=True)

                        lines.append(
                            f"{subj_name} -{direction}-> {obj_name} : <<{prop_qname}>>"
                        )

        return lines

    def render_instance_datatype_properties(self) -> list[str]:
        """Render datatype property values as notes with dotted connections.

        Creates a note for each literal value and connects with dotted line.

        Returns:
            List of PlantUML lines for notes and connections
        """
        lines = []
        direction = self._get_arrow_direction()

        datatype_props = self.entities.get("datatype_properties", set())
        instances = self.entities.get("instances", set())

        for instance in instances:
            instance_name = plantuml_identifier(self.graph, instance)

            for prop in datatype_props:
                for value in self.graph.objects(instance, prop):
                    if isinstance(value, Literal):
                        # Create unique note ID
                        self._note_counter += 1
                        note_id = f"N{self._note_counter}"

                        # Escape literal value for PlantUML
                        value_str = escape_plantuml(str(value))

                        # Create note
                        lines.append(f'note "{value_str}" as {note_id}')

                        # Connect with dotted line
                        prop_qname = qname(self.graph, prop)
                        lines.append(
                            f"{instance_name} .{direction}. {note_id} : <<{prop_qname}>>"
                        )

        return lines

    def render_class_datatype_properties(self) -> list[str]:
        """Render datatype properties on classes as dotted lines to notes.

        For classes with domain restrictions, show the range as a note.

        Returns:
            List of PlantUML lines for notes and connections
        """
        lines = []
        direction = self._get_arrow_direction()

        datatype_props = self.entities.get("datatype_properties", set())
        classes = self.entities.get("classes", set())

        for cls in classes:
            cls_name = plantuml_identifier(self.graph, cls)

            for prop in datatype_props:
                # Check if this property has this class as domain
                domains = list(self.graph.objects(prop, RDFS.domain))
                if cls not in domains:
                    continue

                # Get range to show type
                ranges = list(self.graph.objects(prop, RDFS.range))
                if ranges:
                    # Create note showing the property and its type
                    self._note_counter += 1
                    note_id = f"N{self._note_counter}"

                    range_type = qname(self.graph, ranges[0])
                    # Simplify XSD types
                    if range_type.startswith("xsd:"):
                        range_type = range_type[4:]

                    prop_label = safe_label(self.graph, prop, camelcase=True)

                    lines.append(f'note "{prop_label}: {range_type}" as {note_id}')

                    prop_qname = qname(self.graph, prop)
                    lines.append(
                        f"{cls_name} .{direction}. {note_id} : <<{prop_qname}>>"
                    )

        return lines

    def render(self) -> str:
        """Render complete PlantUML diagram.

        Returns:
            Complete PlantUML diagram as string
        """
        lines = ["@startuml", ""]

        # Add layout directives
        if self.layout:
            directives = getattr(self.layout, 'get_plantuml_directives', lambda: [])()
            lines.extend(directives)
            lines.append("")

        # Add style directives
        if self.style:
            directives = getattr(self.style, 'get_plantuml_directives', lambda: [])()
            if directives:
                lines.extend(directives)
                lines.append("")

        # Render all classes
        for cls in sorted(self.entities.get("classes", set()), key=lambda x: qname(self.graph, x)):
            lines.extend(self.render_class(cls))

        if self.entities.get("classes"):
            lines.append("")

        # Render all properties as classes
        all_props = (
            self.entities.get("object_properties", set()) |
            self.entities.get("datatype_properties", set()) |
            self.entities.get("annotation_properties", set())
        )
        for prop in sorted(all_props, key=lambda x: qname(self.graph, x)):
            lines.extend(self.render_property(prop))

        if all_props:
            lines.append("")

        # Render all instances as classes
        for instance in sorted(self.entities.get("instances", set()), key=lambda x: qname(self.graph, x)):
            lines.extend(self.render_instance(instance))

        if self.entities.get("instances"):
            lines.append("")

        # Render relationships
        lines.extend(self.render_subclass_relationships())
        lines.extend(self.render_subproperty_relationships())
        lines.extend(self.render_type_relationships())
        lines.extend(self.render_property_domain_range())
        lines.extend(self.render_instance_object_properties())

        if any([self.entities.get("classes"), all_props, self.entities.get("instances")]):
            lines.append("")

        # Render datatype properties as notes
        lines.extend(self.render_instance_datatype_properties())
        lines.extend(self.render_class_datatype_properties())

        lines.append("")
        lines.append("@enduml")

        return "\n".join(lines)


def render_plantuml(
    graph: Graph,
    entities: dict[str, set[URIRef]],
    output_path: Optional[Path] = None,
    style: Optional = None,
    layout: Optional = None,
) -> str:
    """Render entities from RDF graph as PlantUML class diagram.

    Args:
        graph: RDF graph containing entities
        entities: Dictionary of entity sets to render
        output_path: Optional path to write PlantUML file
        style: Optional style scheme
        layout: Optional layout configuration

    Returns:
        PlantUML diagram text
    """
    renderer = PlantUMLRenderer(graph, entities, style=style, layout=layout)
    diagram = renderer.render()

    if output_path:
        output_path.write_text(diagram)

    return diagram
