"""PlantUML styling configuration for RDF class diagrams.

Provides color schemes, arrow styles, and visual formatting for different
RDF entity types based on their semantic roles.
"""

from pathlib import Path
from typing import Any, Optional

import yaml
from rdflib import Graph, URIRef, RDF, RDFS
from rdflib.namespace import OWL


class ColorPalette:
    """Color definitions for a single entity type.

    Attributes:
        border: Border/line color (hex or PlantUML color name)
        fill: Fill/background color (hex or PlantUML color name)
        text: Text color (optional, defaults to black)
        line_style: Line style (e.g., 'bold', 'dashed', 'dotted')
    """

    def __init__(self, config: dict[str, Any]):
        """Initialize color palette from configuration.

        Args:
            config: Dictionary with color specifications
        """
        self.border = config.get("border", "#000000")
        self.fill = config.get("fill", "#FFFFFF")
        self.text = config.get("text")
        self.line_style = config.get("line_style")

    def to_plantuml(self) -> str:
        """Generate PlantUML color specification string.

        Creates properly formatted PlantUML color syntax following the pattern:
        #back:RRGGBB;line:RRGGBB;line.STYLE;text:RRGGBB

        The method handles:
        - Fill color (background) with 'back:' prefix
        - Border color (line) with 'line:' prefix
        - Line style (e.g., 'bold', 'dashed') with 'line.' prefix
        - Text color with 'text:' prefix

        All hex color values have any leading '#' stripped, as PlantUML
        doesn't use '#' after the colon in color specifications.

        Returns:
            Complete PlantUML color specification starting with '#',
            or empty string if no colors are defined.

        Examples:
            >>> palette = ColorPalette({"fill": "#FEFE54", "border": "#968584"})
            >>> palette.to_plantuml()
            '#back:FEFE54;line:968584'

            >>> palette = ColorPalette({
            ...     "fill": "#FFFFFF",
            ...     "border": "#000000",
            ...     "text": "#000000",
            ...     "line_style": "bold"
            ... })
            >>> palette.to_plantuml()
            '#back:FFFFFF;line:000000;line.bold;text:000000'
        """
        parts = []

        # Fill/background colour
        if self.fill:
            fill_hex = self.fill.lstrip('#')
            parts.append(f"back:{fill_hex}")

        # Border/line colour
        if self.border:
            border_hex = self.border.lstrip('#')
            parts.append(f"line:{border_hex}")

        # Line style
        if self.line_style:
            parts.append(f"line.{self.line_style}")

        # Text colour
        if self.text:
            text_hex = self.text.lstrip('#')
            parts.append(f"text:{text_hex}")

        # Return with # prefix, or empty if no styling
        return f"#{';'.join(parts)}" if parts else ""


class ArrowStyle:
    """Style specification for relationship arrows.

    Attributes:
        color: Arrow line color
        thickness: Line thickness (e.g., 1, 2, 3)
        style: Line style ('bold', 'dashed', 'dotted', 'hidden')
        label_color: Color for relationship labels
    """

    def __init__(self, config: dict[str, Any]):
        """Initialize arrow style from configuration.

        Args:
            config: Dictionary with arrow style specifications
        """
        self.color = config.get("color", "#000000")
        self.thickness = config.get("thickness")
        self.style = config.get("style")
        self.label_color = config.get("label_color")

    def to_plantuml_directive(self) -> Optional[str]:
        """Generate PlantUML skinparam directive for this arrow style.

        Returns:
            Skinparam directive or None if no customization needed
        """
        if not (self.color or self.thickness or self.style):
            return None

        parts = []
        if self.color:
            parts.append(f"skinparam arrowColor {self.color}")
        if self.thickness:
            parts.append(f"skinparam arrowThickness {self.thickness}")

        return "\n".join(parts) if parts else None

    def __repr__(self) -> str:
        return f"ArrowStyle(color={self.color}, style={self.style})"


class StyleScheme:
    """Complete styling scheme for UML diagrams.

    Attributes:
        name: Scheme identifier
        description: Human-readable description
        class_styles: Mapping of class patterns to color palettes
        instance_style: Style for instances (individuals)
        arrow_styles: Mapping of relationship types to arrow styles
        show_stereotypes: Whether to display UML stereotypes
        stereotype_map: Mapping of RDF types to stereotype labels
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize style scheme from configuration.

        Args:
            name: Scheme identifier
            config: Style configuration dictionary from YAML
        """
        self.name = name
        self.description = config.get("description", "")

        # Class styling
        class_config = config.get("classes", {})
        self.class_styles = {}

        # By namespace
        by_namespace = class_config.get("by_namespace", {})
        for ns_prefix, palette_config in by_namespace.items():
            self.class_styles[f"ns:{ns_prefix}"] = ColorPalette(palette_config)

        # By type (for specific classes)
        by_type = class_config.get("by_type", {})
        for type_key, palette_config in by_type.items():
            self.class_styles[f"type:{type_key}"] = ColorPalette(palette_config)

        # Default class style
        if "default" in class_config:
            self.class_styles["default"] = ColorPalette(class_config["default"])

        # Instance styling
        instance_config = config.get("instances", {})
        self.instance_style = ColorPalette(instance_config) if instance_config else None
        self.instance_inherit_class_border = instance_config.get(
            "inherit_class_border", False
        )

        # Arrow styling
        arrow_config = config.get("arrows", {})
        self.arrow_styles = {}
        for arrow_type, arrow_cfg in arrow_config.items():
            self.arrow_styles[arrow_type] = ArrowStyle(arrow_cfg)

        # Stereotype configuration
        self.show_stereotypes = config.get("show_stereotypes", False)
        self.stereotype_map = config.get("stereotype_map", {})

    def get_class_style(
            self, graph: Graph, cls: URIRef, is_instance: bool = False
    ) -> Optional[ColorPalette]:
        """Get color palette for a specific class or instance.

        Selection priority:
        1. Instance style (if is_instance=True)
        2. Explicit type mapping (by_type)
        3. Inheritance-based lookup (traverse rdfs:subClassOf)
        4. Namespace-based coloring (by_namespace)
        5. Default class style

        Args:
            graph: RDF graph containing the class
            cls: Class URI
            is_instance: Whether this is an instance rather than a class

        Returns:
            ColorPalette or None if no style defined
        """
        # Priority 1: Instance style
        if is_instance and self.instance_style:
            return self.instance_style

        # Priority 2: Check for explicit type mapping
        # (e.g., for specific classes like ies:Entity, ies:State)
        qn = graph.namespace_manager.normalizeUri(cls)
        type_key = f"type:{qn}"
        if type_key in self.class_styles:
            return self.class_styles[type_key]

        # Priority 3: INHERITANCE-BASED LOOKUP (NEW!)
        # Walk up rdfs:subClassOf hierarchy to find styled superclass
        style = self._get_inherited_style(graph, cls)
        if style:
            return style

        # Priority 4: Namespace-based coloring
        if ":" in qn:
            ns_prefix = qn.split(":")[0]
            ns_key = f"ns:{ns_prefix}"
            if ns_key in self.class_styles:
                return self.class_styles[ns_key]

        # Priority 5: Default
        return self.class_styles.get("default")

    def _get_inherited_style(
            self, graph: Graph, cls: URIRef, visited: Optional[set] = None
    ) -> Optional[ColorPalette]:
        """Walk up rdfs:subClassOf hierarchy to find styled superclass.

        This enables classes to inherit styles from their superclasses.
        For example, building:Structure inherits from ies:Entity,
        so it should get Entity's yellow color.

        Args:
            graph: RDF graph containing the class hierarchy
            cls: Class URI to find style for
            visited: Set of already-visited classes (prevents infinite loops)

        Returns:
            ColorPalette from nearest styled superclass, or None
        """
        if visited is None:
            visited = set()

        # Prevent infinite loops in case of circular inheritance
        if cls in visited:
            return None
        visited.add(cls)

        # Get all direct superclasses
        superclasses = list(graph.objects(cls, RDFS.subClassOf))

        # Check each superclass
        for superclass in superclasses:
            # Skip if not a proper URI (could be blank node)
            if not isinstance(superclass, URIRef):
                continue

            # Check if this superclass has explicit styling
            super_qn = graph.namespace_manager.normalizeUri(superclass)
            type_key = f"type:{super_qn}"

            if type_key in self.class_styles:
                # Found a styled superclass!
                return self.class_styles[type_key]

            # Recursively check this superclass's parents
            inherited = self._get_inherited_style(graph, superclass, visited)
            if inherited:
                return inherited

        # No styled superclass found
        return None

    def get_arrow_style(self, relationship_type: str) -> Optional[ArrowStyle]:
        """Get arrow style for a relationship type.

        Args:
            relationship_type: Type of relationship ('subclass', 'instance',
                             'object_property', 'rdf_type', etc.)

        Returns:
            ArrowStyle or None if no specific style defined
        """
        return self.arrow_styles.get(relationship_type)

    def get_stereotype(self, graph: Graph, cls: URIRef) -> Optional[str]:
        """Get UML stereotype label for a class based on its RDF types.

        Args:
            graph: RDF graph containing the class
            cls: Class URI

        Returns:
            Stereotype string or None if stereotypes disabled or not found
        """
        if not self.show_stereotypes:
            return None

        # Check RDF types of this class
        for rdf_type in graph.objects(cls, RDF.type):
            type_qname = graph.namespace_manager.normalizeUri(rdf_type)
            if type_qname in self.stereotype_map:
                return self.stereotype_map[type_qname]

        return None

    def __repr__(self) -> str:
        return f"StyleScheme(name={self.name!r}, classes={len(self.class_styles)})"


class StyleConfig:
    """Configuration for PlantUML styling.

    Loads and manages YAML-based style specifications with support
    for multiple schemes and shared configuration via YAML anchors.

    Attributes:
        defaults: Default styling settings
        schemes: Dictionary of available style schemes
    """

    def __init__(self, yaml_path: Path | str):
        """Load style configuration from a YAML file.

        Args:
            yaml_path: Path to YAML style configuration file
        """
        yaml_path = Path(yaml_path)
        self.config = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        self.defaults = self.config.get("defaults", {}) or {}

        # Load schemes
        self.schemes = {}
        for scheme_name, scheme_config in (self.config.get("schemes", {}) or {}).items():
            self.schemes[scheme_name] = StyleScheme(scheme_name, scheme_config)

    def get_scheme(self, name: str) -> StyleScheme:
        """Get a style scheme by name.

        Args:
            name: Scheme identifier

        Returns:
            StyleScheme instance

        Raises:
            KeyError: If scheme name not found
        """
        if name not in self.schemes:
            raise KeyError(
                f"Style scheme '{name}' not found. Available schemes: "
                f"{', '.join(self.schemes.keys())}"
            )
        return self.schemes[name]

    def list_schemes(self) -> list[str]:
        """Get list of available scheme names.

        Returns:
            List of scheme identifier strings
        """
        return list(self.schemes.keys())

    def __repr__(self) -> str:
        return f"StyleConfig(schemes={list(self.schemes.keys())})"


def load_style_config(path: Path | str) -> StyleConfig:
    """Load style configuration from a YAML file.

    Args:
        path: Path to YAML style configuration file

    Returns:
        StyleConfig instance
    """
    return StyleConfig(path)
