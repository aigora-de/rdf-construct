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

        Args:
            cls: Class URI to render

        Returns:
            List of PlantUML lines for this class
        """
        lines = []
        class_name = qname(self.graph, cls)

        # Quote class name if it contains a colon
        if ":" in class_name:
            class_name = f'"{class_name}"'

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
                color_spec = f" #{palette.to_plantuml()}"

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
                    range_type = range_type[4:]  # Remove 'xsd:' prefix
                attributes.append(f"  +{prop_label} : {range_type}")
            else:
                attributes.append(f"  +{prop_label}")

        # Render class with styling
        # Only add braces if there are attributes
        if attributes:
            lines.append(f"class {class_name}{stereotype}{color_spec} {{")
            lines.extend(attributes)
            lines.append("}")
        else:
            # Check if we should hide empty classes
            if self.layout and self.layout.hide_empty_members:
                # Don't render, but still return empty list
                return []
            lines.append(f"class {class_name}{stereotype}{color_spec}")

        return lines

    def render_instance(self, instance: URIRef) -> list[str]:
        """Render an instance as a PlantUML object.

        Applies instance styling based on configuration.

        Args:
            instance: Instance URI to render

        Returns:
            List of PlantUML lines for this instance
        """
        lines = []
        instance_name = qname(self.graph, instance)
        # Don't camelCase instance display labels - keep original
        instance_label = safe_label(self.graph, instance, camelcase=False)

        # Quote instance name if it contains a colon
        if ":" in instance_name:
            instance_name = f'"{instance_name}"'

        # Get colour styling for instances
        color_spec = ""
        if self.style:
            palette = self.style.get_class_style(self.graph, instance, is_instance=True)
            if palette:
                color_spec = f" #{palette.to_plantuml()}"

        # Start object definition
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

        Returns:
            List of PlantUML lines for class inheritance
        """
        lines = []
        classes = self.entities["classes"]

        # Get arrow syntax from layout config
        if self.layout:
            arrow = self.layout.get_arrow_syntax("subclass")
        else:
            arrow = "-|>"  # Default: simple inheritance

        for cls in sorted(classes, key=lambda c: qname(self.graph, c)):
            # Get direct superclasses
            for superclass in self.graph.objects(cls, RDFS.subClassOf):
                # Only include if superclass is also in our selected classes
                if superclass in classes and isinstance(superclass, URIRef):
                    subclass_name = qname(self.graph, cls)
                    superclass_name = qname(self.graph, superclass)

                    # Quote names with colons
                    if ":" in subclass_name:
                        subclass_name = f'"{subclass_name}"'
                    if ":" in superclass_name:
                        superclass_name = f'"{superclass_name}"'

                    lines.append(f"{subclass_name} {arrow} {superclass_name}")

        return lines

    def render_instance_relationships(self) -> list[str]:
        """Render rdf:type relationships from instances to classes.

        Uses styled arrows based on configuration.

        Returns:
            List of PlantUML lines for instance-class relationships
        """
        lines = []
        instances = self.entities["instances"]
        classes = self.entities["classes"]

        # Get arrow syntax - dotted for instances
        if self.layout:
            base_arrow = self.layout.get_arrow_syntax("instance")
            # Make it dotted
            arrow = base_arrow.replace("-", ".")
        else:
            arrow = "..|>"  # Default: dotted inheritance

        for instance in sorted(instances, key=lambda i: qname(self.graph, i)):
            # Get classes this instance belongs to
            for cls in self.graph.objects(instance, RDF.type):
                # Only include if class is in our selected classes
                if cls in classes and isinstance(cls, URIRef):
                    instance_name = qname(self.graph, instance)
                    class_name = qname(self.graph, cls)

                    # Quote names with colons
                    if ":" in instance_name:
                        instance_name = f'"{instance_name}"'
                    if ":" in class_name:
                        class_name = f'"{class_name}"'

                    lines.append(f"{instance_name} {arrow} {class_name}")

        return lines

    def render_object_properties(self) -> list[str]:
        """Render object properties as associations between classes.

        Uses layout-configured arrow direction if available.

        Returns:
            List of PlantUML lines for object property associations
        """
        lines = []
        object_props = self.entities["object_properties"]
        classes = self.entities["classes"]

        # Get arrow syntax
        if self.layout:
            arrow = self.layout.get_arrow_syntax("object_property")
        else:
            arrow = "-->"  # Default: simple arrow

        for prop in sorted(object_props, key=lambda p: qname(self.graph, p)):
            # Use camelCase for property labels
            prop_label = safe_label(self.graph, prop, camelcase=True)

            # Get domain and range
            domains = list(self.graph.objects(prop, RDFS.domain))
            ranges = list(self.graph.objects(prop, RDFS.range))

            if not domains or not ranges:
                continue

            # Only render if both domain and range are in selected classes
            for domain in domains:
                if domain not in classes:
                    continue
                for range_cls in ranges:
                    if range_cls not in classes:
                        continue

                    domain_name = qname(self.graph, domain)
                    range_name = qname(self.graph, range_cls)

                    # Quote names with colons
                    if ":" in domain_name:
                        domain_name = f'"{domain_name}"'
                    if ":" in range_name:
                        range_name = f'"{range_name}"'

                    lines.append(f"{domain_name} {arrow} {range_name} : {prop_label}")

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
