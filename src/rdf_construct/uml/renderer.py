"""PlantUML renderer with styling and layout support.

Renders RDF entities as PlantUML class diagrams with configurable
colours, arrow styles, stereotypes, and layout control.
"""

from pathlib import Path
from typing import Optional

from rdflib import Graph, URIRef, RDF, RDFS, Literal
from rdflib.namespace import OWL, XSD

# ToDo - remove try block, if unnecessary after development
try:
    from .uml_style import StyleScheme, StyleConfig
    from .uml_layout import LayoutConfig, LayoutConfigManager
except ImportError:
    # Fallback for testing/development
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from uml_style import StyleScheme, StyleConfig
    from uml_layout import LayoutConfig, LayoutConfigManager


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
                label = words[0].lower() + "".join(word.capitalize() for word in words[1:])

        return label

    # Fallback to QName
    return qname(graph, uri)


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
        "ex:MyClass" → "ex.MyClass"

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

    Generates PlantUML syntax for classes, properties, and relationships
    with configurable styling and layout.

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
        style: Optional[StyleScheme] = None,
        layout: Optional[LayoutConfig] = None,
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

    def render_class(self, cls: URIRef) -> list[str]:
        """Render a class with its datatype properties as attributes.

        Applies colour styling and stereotypes if configured.
        Uses proper PlantUML syntax with dot notation.

        Args:
            cls: Class URI to render

        Returns:
            List of PlantUML lines for this class
        """
        lines = []

        # Use dot notation for PlantUML
        class_name = plantuml_identifier(self.graph, cls)
        # No quoting needed with dot notation

        # Get stereotype if enabled
        stereotype = ""
        if self.style and self.style.show_stereotypes:
            stereo = self.style.get_stereotype(self.graph, cls)
            if stereo:
                stereotype = f" {stereo}"

        # Get color styling
        color_spec = ""
        if self.style:
            palette = self.style.get_class_style(self.graph, cls, is_instance=False)
            if palette:
                # to_plantuml() now returns complete spec with # prefix
                color_spec = f" {palette.to_plantuml()}"

        # Collect datatype properties as attributes
        datatype_props = self.entities["datatype_properties"]
        attributes = []

        for prop in sorted(datatype_props, key=lambda p: qname(self.graph, p)):
            # Check if this property has this class as domain
            domains = list(self.graph.objects(prop, RDFS.domain))
            if cls not in domains:
                continue

            # Use camelCase for property names
            prop_label = safe_label(self.graph, prop, camelcase=True)

            # Try to get range for type hint
            ranges = list(self.graph.objects(prop, RDFS.range))
            if ranges:
                range_type = qname(self.graph, ranges[0])
                # Simplify XSD types
                if range_type.startswith("xsd:"):
                    range_type = range_type[4:]
                attributes.append(f"  +{prop_label} : {range_type}")
            else:
                attributes.append(f"  +{prop_label}")

        # Render class with styling
        if attributes:
            lines.append(f"class {class_name}{stereotype}{color_spec} {{")
            lines.extend(attributes)
            lines.append("}")
        else:
            # Check if we should hide empty classes
            if self.layout and self.layout.hide_empty_members:
                return []
            lines.append(f"class {class_name}{stereotype}{color_spec}")

        return lines

    def render_instance(self, instance: URIRef) -> list[str]:
        """Render an instance as a PlantUML object.

        Applies instance styling based on configuration.
        Uses proper PlantUML syntax with dot notation.

        Args:
            instance: Instance URI to render

        Returns:
            List of PlantUML lines for this instance
        """
        lines = []

        # Use dot notation for identifier
        instance_name = plantuml_identifier(self.graph, instance)

        # Keep original label for display (still quoted for readability)
        instance_label = safe_label(self.graph, instance, camelcase=False)

        # Get colour styling for instances
        color_spec = ""
        if self.style:
            palette = self.style.get_class_style(self.graph, instance, is_instance=True)
            if palette:
                # to_plantuml() now returns complete spec with # prefix
                color_spec = f" {palette.to_plantuml()}"

        # Start object definition
        # Label is quoted, identifier uses dot notation
        lines.append(f'object "{instance_label}" as {instance_name}{color_spec} {{')

        # Add datatype property values (use camelCase for property names)
        for prop in sorted(
                self.entities["datatype_properties"], key=lambda p: qname(self.graph, p)
        ):
            values = list(self.graph.objects(instance, prop))
            if values:
                prop_label = safe_label(self.graph, prop, camelcase=True)
                for val in values:
                    if isinstance(val, Literal):
                        val_str = escape_plantuml(str(val))
                        lines.append(f"  {prop_label} = {val_str}")

        lines.append("}")

        return lines

    def render_subclass_relationships(self) -> list[str]:
        """Render rdfs:subClassOf relationships as inheritance arrows.

        Uses layout-configured arrow direction if available.
        Uses proper PlantUML syntax with dot notation.

        Returns:
            List of PlantUML relationship lines
        """
        lines = []

        # Determine arrow syntax based on layout
        arrow_syntax = "-|>"  # Default
        if self.layout and self.layout.arrow_direction:
            direction = self.layout.arrow_direction
            if direction == "up":
                arrow_syntax = "-up-|>"
            elif direction == "down":
                arrow_syntax = "-down-|>"
            elif direction == "left":
                arrow_syntax = "-left-|>"
            elif direction == "right":
                arrow_syntax = "-right-|>"

        # Render subclass relationships
        for cls in self.entities["classes"]:
            for parent in self.graph.objects(cls, RDFS.subClassOf):
                if parent in self.entities["classes"]:
                    # Use dot notation - no quoting needed
                    child_name = plantuml_identifier(self.graph, cls)
                    parent_name = plantuml_identifier(self.graph, parent)

                    lines.append(f"{child_name} {arrow_syntax} {parent_name}")

        return lines

    def render_instance_relationships(self) -> list[str]:
        """Render rdf:type relationships as dashed instance arrows.

        Uses proper PlantUML syntax with dot notation.

        Returns:
            List of PlantUML relationship lines
        """
        lines = []

        for instance in self.entities["instances"]:
            # Use dot notation - no quoting needed
            instance_name = plantuml_identifier(self.graph, instance)

            for cls in self.graph.objects(instance, RDF.type):
                if cls in self.entities["classes"]:
                    class_name = plantuml_identifier(self.graph, cls)

                    # Dashed arrow for instance-of relationship
                    lines.append(f'{instance_name} ..|> {class_name}')

        return lines

    def render_object_properties(self) -> list[str]:
        """Render object properties as associations between classes.

        Uses proper PlantUML syntax with dot notation.

        Returns:
            List of PlantUML association lines
        """
        lines = []

        object_props = self.entities.get("object_properties", set())

        for prop in sorted(object_props, key=lambda p: qname(self.graph, p)):
            # Get property label
            prop_label = safe_label(self.graph, prop, camelcase=True)

            # Get domain and range
            domains = list(self.graph.objects(prop, RDFS.domain))
            ranges = list(self.graph.objects(prop, RDFS.range))

            # Render associations for domain-range pairs
            for domain in domains:
                if domain in self.entities["classes"]:
                    for rng in ranges:
                        if rng in self.entities["classes"]:
                            # Use dot notation - no quoting needed
                            domain_name = plantuml_identifier(self.graph, domain)
                            range_name = plantuml_identifier(self.graph, rng)

                            lines.append(f'{domain_name} --> {range_name} : {prop_label}')

        return lines

    def render(self) -> str:
        """Render complete PlantUML diagram with styling and layout.

        Returns:
            Complete PlantUML diagram as string
        """
        lines = ["@startuml", ""]

        # Add layout directives
        if self.layout:
            layout_directives = self.layout.get_plantuml_directives()
            if layout_directives:
                lines.extend(layout_directives)
                lines.append("")

        # Add style directives (if any)
        if self.style:
            # Could add skinparam directives here for global styling
            # For now, styles are applied inline on each element
            pass

        # Render classes
        for cls in sorted(self.entities["classes"], key=lambda c: qname(self.graph, c)):
            class_lines = self.render_class(cls)
            if class_lines:  # Only add if not filtered out
                lines.extend(class_lines)
                lines.append("")

        # Render instances
        for instance in sorted(
            self.entities["instances"], key=lambda i: qname(self.graph, i)
        ):
            lines.extend(self.render_instance(instance))
            lines.append("")

        # Render relationships
        subclass_lines = self.render_subclass_relationships()
        if subclass_lines:
            lines.extend(subclass_lines)
            lines.append("")

        instance_lines = self.render_instance_relationships()
        if instance_lines:
            lines.extend(instance_lines)
            lines.append("")

        property_lines = self.render_object_properties()
        if property_lines:
            lines.extend(property_lines)
            lines.append("")

        lines.append("@enduml")

        return "\n".join(lines)


def render_plantuml(
    graph: Graph,
    entities: dict[str, set[URIRef]],
    output_path: Path | str,
    style: Optional[StyleScheme] = None,
    layout: Optional[LayoutConfig] = None,
) -> None:
    """Render entities to a PlantUML file with optional styling.

    Args:
        graph: RDF graph containing the entities
        entities: Dictionary of selected entities to render
        output_path: Path to write .puml file to
        style: Optional style scheme to apply
        layout: Optional layout configuration to apply
    """
    renderer = PlantUMLRenderer(graph, entities, style, layout)
    puml_text = renderer.render()

    output_path = Path(output_path)
    output_path.write_text(puml_text, encoding="utf-8")
