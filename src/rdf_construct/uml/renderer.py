"""Render RDF entities as PlantUML class diagrams.

Converts selected RDF classes, properties, and instances into PlantUML
syntax for visualization.
"""

from pathlib import Path
from typing import Optional

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
    """Renders RDF entities as PlantUML class diagrams.

    Generates PlantUML syntax for classes, properties, and relationships
    without styling (basic version for pipeline step 1).

    Attributes:
        graph: RDF graph being rendered
        entities: Dictionary of selected entities to render
    """

    def __init__(self, graph: Graph, entities: dict[str, set[URIRef]]):
        """Initialize renderer with graph and selected entities.

        Args:
            graph: RDF graph containing the entities
            entities: Dictionary of entity sets (classes, properties, instances)
        """
        self.graph = graph
        self.entities = entities

    def render_class(self, cls: URIRef) -> list[str]:
        """Render a class with its datatype properties as attributes.

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

        # Only add braces if there are attributes
        if attributes:
            lines.append(f"class {class_name} {{")
            lines.extend(attributes)
            lines.append("}")
        else:
            lines.append(f"class {class_name}")

        return lines

    def render_instance(self, instance: URIRef) -> list[str]:
        """Render an instance as a PlantUML object.

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

        # Start object definition
        lines.append(f'object "{instance_label}" as {instance_name} {{')

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

        Returns:
            List of PlantUML lines for class inheritance
        """
        lines = []
        classes = self.entities["classes"]

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

                    lines.append(f"{subclass_name} --|> {superclass_name}")

        return lines

    def render_instance_relationships(self) -> list[str]:
        """Render rdf:type relationships from instances to classes.

        Returns:
            List of PlantUML lines for instance-class relationships
        """
        lines = []
        instances = self.entities["instances"]
        classes = self.entities["classes"]

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

                    lines.append(f"{instance_name} ..|> {class_name}")

        return lines

    def render_object_properties(self) -> list[str]:
        """Render object properties as associations between classes.

        Returns:
            List of PlantUML lines for object property associations
        """
        lines = []
        object_props = self.entities["object_properties"]
        classes = self.entities["classes"]

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

                    lines.append(f"{domain_name} --> {range_name} : {prop_label}")

        return lines

    def render(self) -> str:
        """Render complete PlantUML diagram.

        Returns:
            Complete PlantUML diagram as string
        """
        lines = ["@startuml", ""]

        # Render classes
        for cls in sorted(self.entities["classes"], key=lambda c: qname(self.graph, c)):
            lines.extend(self.render_class(cls))
            lines.append("")

        # Render instances
        for instance in sorted(
            self.entities["instances"], key=lambda i: qname(self.graph, i)
        ):
            lines.extend(self.render_instance(instance))
            lines.append("")

        # Render relationships
        lines.extend(self.render_subclass_relationships())
        lines.append("")

        lines.extend(self.render_instance_relationships())
        lines.append("")

        lines.extend(self.render_object_properties())
        lines.append("")

        lines.append("@enduml")

        return "\n".join(lines)


def render_plantuml(
    graph: Graph, entities: dict[str, set[URIRef]], output_path: Path | str
) -> None:
    """Render entities to a PlantUML file.

    Args:
        graph: RDF graph containing the entities
        entities: Dictionary of selected entities to render
        output_path: Path to write .puml file to
    """
    renderer = PlantUMLRenderer(graph, entities)
    puml_text = renderer.render()

    output_path = Path(output_path)
    output_path.write_text(puml_text, encoding="utf-8")
