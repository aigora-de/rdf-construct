"""PlantUML styling configuration for RDF class diagrams.

Provides color schemes, arrow styles, and visual formatting for different
RDF entity types based on their semantic roles.

Added instance-specific styling based on rdf:type hierarchy.
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
        """Initialise colour palette from configuration.

        Args:
            config: Dictionary with colour specifications
        """
        self.border = config.get("border", "#000000")
        self.fill = config.get("fill", "#FFFFFF")
        self.text = config.get("text")
        self.line_style = config.get("line_style")

    def to_plantuml(self) -> str:
        """Generate PlantUML color specification.

        Returns string in format: #back:FILL;line:BORDER;line.STYLE;text:TEXT
        Not just #FILL

        Returns:
            PlantUML color spec string with # prefix, or empty if no styling
        """
        if not self.fill and not self.border and not self.text:
            return ""

        parts = []

        # Background fill (note: PlantUML uses 'back:', not just fill)
        if self.fill:
            fill_hex = self.fill.lstrip('#')
            parts.append(f"back:{fill_hex}")

        # Border colour and style
        if self.border:
            border_hex = self.border.lstrip('#')
            parts.append(f"line:{border_hex}")

        if self.line_style:
            parts.append(f"line.{self.line_style}")

        # Text colour
        if self.text:
            text_hex = self.text.lstrip('#')
            parts.append(f"text:{text_hex}")

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


class ArrowColorConfig:
    """Configuration for arrow colors based on relationship type.

    Attributes:
        type_arrow_color: Color for rdf:type relationships (default red)
        subclass_arrow_color: Color for rdfs:subClassOf relationships
        property_arrow_color: Color for object property relationships
        domain_range_arrow_color: Color for domain/range relationships
        datatype_arrow_color: Color for datatype property relationships
    """

    def __init__(self, config: dict[str, str]):
        """Initialize arrow colors from configuration.

        Args:
            config: Dictionary mapping relationship types to hex colors
        """
        self.type_arrow_color = config.get("type", "#FF0000")  # Red
        self.subclass_arrow_color = config.get("subclass", "#000000")  # Black
        self.property_arrow_color = config.get("property", "#000000")  # Black
        self.domain_range_arrow_color = config.get("domain_range", "#000000")  # Black
        self.datatype_arrow_color = config.get("datatype", "#000000")  # Black

    def get_color(self, relationship_type: str) -> str:
        """Get color for a specific relationship type.

        Args:
            relationship_type: Type of relationship
                ('type', 'subclass', 'property', 'domain_range', 'datatype')

        Returns:
            Hex color code
        """
        color_map = {
            "type": self.type_arrow_color,
            "subclass": self.subclass_arrow_color,
            "property": self.property_arrow_color,
            "domain_range": self.domain_range_arrow_color,
            "datatype": self.datatype_arrow_color,
        }
        return color_map.get(relationship_type, "#000000")


class StyleScheme:
    """Complete styling scheme for UML diagrams.

    Attributes:
        name: Scheme identifier
        description: Human-readable description
        class_styles: Mapping of class patterns to color palettes
        instance_styles: Mapping of instance type patterns to colour palettes
        instance_style_default: Default style for instances (fallback)
        arrow_styles: Mapping of relationship types to arrow styles
        show_stereotypes: Whether to display UML stereotypes
        stereotype_map: Mapping of RDF types to stereotype labels
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialise style scheme from configuration.

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
        self.instance_styles = {}

        # Load by_type instance styles
        by_type_instances = instance_config.get("by_type", {})
        for type_key, palette_config in by_type_instances.items():
            self.instance_styles[f"type:{type_key}"] = ColorPalette(palette_config)

        # Default instance style (fallback if no by_type match)
        if "default" in instance_config:
            self.instance_style_default = ColorPalette(instance_config["default"])
        else:
            # Legacy support: if no 'default' key but instance_config has color keys
            # treat the whole config as a palette
            if any(k in instance_config for k in ["border", "fill", "text"]):
                self.instance_style_default = ColorPalette(instance_config)
            else:
                self.instance_style_default = None

        # Legacy support for inherit_class_border flag
        self.instance_inherit_class_border = instance_config.get(
            "inherit_class_border", False
        )
        # Inherit_class_text flag (for text colour matching class fill)
        self.instance_inherit_class_text = instance_config.get(
            "inherit_class_text", False
        )

        # Arrow styling
        arrow_config = config.get("arrows", {})
        self.arrow_styles = {}
        for arrow_type, arrow_cfg in arrow_config.items():
            self.arrow_styles[arrow_type] = ArrowStyle(arrow_cfg)

        # Arrow color configuration
        arrow_color_config = config.get("arrow_colors", {})
        self.arrow_colors = ArrowColorConfig(arrow_color_config)

        # Stereotype configuration
        self.show_stereotypes = config.get("show_stereotypes", False)
        self.stereotype_map = config.get("stereotype_map", {})

    def get_class_style(
            self, graph: Graph, cls: URIRef, is_instance: bool = False
    ) -> Optional[ColorPalette]:
        """Get color palette for a specific class or instance.

        Selection priority:
        1. Instance-specific styling (if is_instance=True) via get_instance_style()
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
        # Priority 1: Instance-specific styling
        if is_instance:
            return self.get_instance_style(graph, cls)

        # Priority 2: Check for explicit type mapping
        qn = graph.namespace_manager.normalizeUri(cls)
        type_key = f"type:{qn}"
        if type_key in self.class_styles:
            return self.class_styles[type_key]

        # Priority 3: INHERITANCE-BASED LOOKUP
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

    def get_instance_style(
            self, graph: Graph, instance: URIRef
    ) -> Optional[ColorPalette]:
        """Get color palette for an instance based on its rdf:type hierarchy.

        Selection priority:
        1. Explicit type mapping in instances.by_type (using first rdf:type)
        2. Walk up rdf:type's superclass hierarchy to find styled class
        3. Default instance style
        4. Fall back to None

        If inherit_class_text is enabled, text color matches the class border color.

        Args:
            graph: RDF graph containing the instance
            instance: Instance URI

        Returns:
            ColorPalette for the instance, or None if no style defined
        """
        # Get all rdf:type declarations for this instance
        instance_types = list(graph.objects(instance, RDF.type))

        # Filter out metaclass types that shouldn't affect instance styling
        metaclass_types = {
            OWL.Class, RDFS.Class,
            OWL.ObjectProperty, OWL.DatatypeProperty,
            OWL.AnnotationProperty, RDF.Property
        }
        valid_types = [t for t in instance_types if t not in metaclass_types]

        if not valid_types:
            # No valid types - use default
            return self.instance_style_default

        # Use the first declared type as primary
        primary_type = valid_types[0]
        primary_type_qn = graph.namespace_manager.normalizeUri(primary_type)

        # Priority 1: Check for explicit instance type styling
        type_key = f"type:{primary_type_qn}"
        if type_key in self.instance_styles:
            palette = self.instance_styles[type_key]

            # Apply text color inheritance if enabled
            if self.instance_inherit_class_text and palette:
                return self._apply_class_text_inheritance(
                    graph, primary_type, palette
                )
            return palette

        # Priority 2: Walk up the type's class hierarchy to find styled class
        # This allows instances to inherit colors from their class hierarchy
        styled_class_palette = self._get_inherited_style(graph, primary_type)
        if styled_class_palette:
            # Create instance-specific palette based on class colors
            instance_palette = ColorPalette({
                "border": styled_class_palette.border,
                "fill": "#000000",  # Instances have black fill
                "text": styled_class_palette.border
            })
            return instance_palette

        # Priority 3: Default instance style
        if self.instance_style_default:
            if self.instance_inherit_class_text:
                return self._apply_class_text_inheritance(
                    graph, primary_type, self.instance_style_default
                )
            return self.instance_style_default

        # No styling found
        return None

    def _apply_class_text_inheritance(
            self, graph: Graph, class_uri: URIRef, base_palette: ColorPalette
    ) -> ColorPalette:
        """Apply class text color inheritance to an instance palette.

        Looks up the class's border color and applies it as text color.

        Args:
            graph: RDF graph
            class_uri: Class URI to get colors from
            base_palette: Base instance palette to modify

        Returns:
            New ColorPalette with inherited text color
        """
        # Get the class's styling
        class_palette = self.get_class_style(graph, class_uri, is_instance=False)

        if class_palette and class_palette.border:
            # Use class border color as instance text color
            return ColorPalette({
                "border": base_palette.border,
                "fill": base_palette.fill,
                "text": class_palette.border,
                "line_style": base_palette.line_style
            })

        return base_palette

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

    def get_property_style(
            self, graph: Graph, prop: URIRef
    ) -> Optional[ColorPalette]:
        """Get colour palette for property class.

        Properties render as classes with specific styling (typically gray).
        Can be customised by namespace or specific property types.

        Args:
            graph: RDF graph containing the property
            prop: Property URI

        Returns:
            Color palette for the property, or None for default styling
        """
        # Check for property-specific styling first
        # Get QName using graph's namespace manager
        prop_qname = graph.namespace_manager.normalizeUri(prop)
        if prop_qname in self.class_styles:
            return self.class_styles[prop_qname]

        # Check namespace-based styling
        if ":" in prop_qname:
            ns_prefix = prop_qname.split(":")[0]
            ns_key = f"ns:{ns_prefix}"
            if ns_key in self.class_styles:
                return self.class_styles[ns_key]

        # Check for property type styling
        # (e.g., different colors for ObjectProperty vs DatatypeProperty)
        for prop_type in graph.objects(prop, RDF.type):
            # Get QName using graph's namespace manager
            type_qname = graph.namespace_manager.normalizeUri(prop_type)
            type_key = f"type:{type_qname}"
            if type_key in self.class_styles:
                return self.class_styles[type_key]

        # Default: gray for all properties
        return ColorPalette({
            "fill": "#CCCCCC",
            "border": "#666666",
            "text": "#000000"
        })

    def get_arrow_style(self, relationship_type: str) -> Optional[ArrowStyle]:
        """Get arrow style for a relationship type.

        Args:
            relationship_type: Type of relationship ('subclass', 'instance',
                             'object_property', 'rdf_type', etc.)

        Returns:
            ArrowStyle or None if no specific style defined
        """
        return self.arrow_styles.get(relationship_type)

    def get_stereotype(
            self, graph: Graph, entity: URIRef, is_instance: bool = False
    ) -> Optional[str]:
        """Get stereotype label for entity."""
        if not self.show_stereotypes:
            return None

        # Handle instances with multiple types
        if is_instance:
            types = []
            metaclass_types = {
                "owl:Class", "rdfs:Class",
                "owl:ObjectProperty", "owl:DatatypeProperty",
                "owl:AnnotationProperty", "rdf:Property"
            }

            for rdf_type in graph.objects(entity, RDF.type):
                # Get QName using graph's namespace manager
                type_qname = graph.namespace_manager.normalizeUri(rdf_type)
                if type_qname not in metaclass_types:
                    types.append(type_qname)

            if types:
                types.sort()
                return f"<<{', '.join(types)}>>"
            return "<<owl:NamedIndividual>>"

        # Handle classes/properties (existing logic)
        for rdf_type in graph.objects(entity, RDF.type):
            # Get QName using graph's namespace manager
            type_qname = graph.namespace_manager.normalizeUri(rdf_type)
            if type_qname in self.stereotype_map:
                return self.stereotype_map[type_qname]
            if type_qname in ("owl:Class", "rdfs:Class",
                              "owl:ObjectProperty", "owl:DatatypeProperty",
                              "owl:AnnotationProperty", "rdf:Property"):
                return f"<<{type_qname}>>"

        return None

    def __repr__(self) -> str:
        return (
            f"StyleScheme(name={self.name!r}, "
            f"classes={len(self.class_styles)}, "
            f"instances={len(self.instance_styles)})"
        )


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
