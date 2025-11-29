"""PlantUML layout configuration for RDF class diagrams.

Provides control over diagram direction, spacing, grouping,
and other layout-related aspects.

Enhanced features:
- together: Group classes to be placed adjacent
- linetype: Orthogonal or polyline routing
- group_inheritance: Merge arrow heads for multiple subclasses
- layout_hints: Hidden links to influence positioning
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import yaml


LayoutDirection = Literal[
    "top_to_bottom",
    "bottom_to_top",
    "left_to_right",
    "right_to_left",
]

LineType = Literal["ortho", "polyline", "spline"]


@dataclass
class LayoutHint:
    """A hidden link hint to influence layout positioning.

    Attributes:
        from_entity: Source entity CURIE (e.g., 'ies:Entity')
        to_entity: Target entity CURIE (e.g., 'building:Building')
        direction: Optional direction hint ('up', 'down', 'left', 'right')
        weight: Number of hidden links (higher = stronger influence)
    """
    from_entity: str
    to_entity: str
    direction: Optional[str] = None
    weight: int = 1


class LayoutConfig:
    """Layout configuration for PlantUML diagrams.

    Attributes:
        name: Layout identifier
        description: Human-readable description
        direction: Primary layout direction
        hide_empty_members: Whether to hide classes with no attributes/methods
        spacing: Spacing configuration dict
        group_by_namespace: Whether to group classes by namespace
        arrow_direction: Direction hint for arrows ('up', 'down', 'left', 'right')
        linetype: Line routing style ('ortho', 'polyline', 'spline')
        group_inheritance: Threshold for merging inheritance arrows (0 = disabled)
        together_groups: List of class groups to place adjacent
        layout_hints: List of hidden link hints for positioning
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize layout configuration.

        Args:
            name: Layout identifier
            config: Layout configuration dictionary from YAML
        """
        self.name = name
        self.description = config.get("description", "")

        # Layout direction
        direction_str = config.get("direction", "top_to_bottom")
        self.direction: LayoutDirection = self._validate_direction(direction_str)

        # Display options
        self.hide_empty_members = config.get("hide_empty_members", False)
        self.show_arrows = config.get("show_arrows", True)

        # Arrow direction hints for hierarchy
        arrow_dir = config.get("arrow_direction", "up")
        self.arrow_direction = self._validate_arrow_direction(arrow_dir)

        # Grouping
        self.group_by_namespace = config.get("group_by_namespace", False)

        # Spacing (PlantUML skinparam settings)
        self.spacing = config.get("spacing", {})

        # NEW: Line type for edge routing
        linetype = config.get("linetype")
        self.linetype: Optional[LineType] = self._validate_linetype(linetype)

        # NEW: Group inheritance threshold
        self.group_inheritance = config.get("group_inheritance", 0)

        # NEW: Together groups - classes to place adjacent
        self.together_groups: list[list[str]] = config.get("together", [])

        # NEW: Layout hints - hidden links to influence positioning
        self.layout_hints: list[LayoutHint] = []
        for hint in config.get("layout_hints", []):
            if isinstance(hint, dict) and "from" in hint and "to" in hint:
                self.layout_hints.append(LayoutHint(
                    from_entity=hint["from"],
                    to_entity=hint["to"],
                    direction=hint.get("direction"),
                    weight=hint.get("weight", 1),
                ))

    def _validate_direction(self, direction: str) -> LayoutDirection:
        """Validate and normalize layout direction.

        Args:
            direction: Direction string from config

        Returns:
            Validated LayoutDirection
        """
        direction_map = {
            "top_to_bottom": "top_to_bottom",
            "ttb": "top_to_bottom",
            "tb": "top_to_bottom",
            "bottom_to_top": "bottom_to_top",
            "btt": "bottom_to_top",
            "bt": "bottom_to_top",
            "left_to_right": "left_to_right",
            "ltr": "left_to_right",
            "lr": "left_to_right",
            "right_to_left": "right_to_left",
            "rtl": "right_to_left",
            "rl": "right_to_left",
        }

        normalized = direction_map.get(direction.lower(), "top_to_bottom")
        return normalized  # type: ignore

    def _validate_arrow_direction(self, arrow_dir: str) -> str:
        """Validate arrow direction hint.

        Args:
            arrow_dir: Arrow direction from config

        Returns:
            Validated arrow direction ('up', 'down', 'left', 'right')
        """
        valid_directions = {"up", "down", "left", "right"}
        if arrow_dir.lower() in valid_directions:
            return arrow_dir.lower()
        return "up"  # Default: parents above children

    def _validate_linetype(self, linetype: Optional[str]) -> Optional[LineType]:
        """Validate line type setting.

        Args:
            linetype: Line type from config

        Returns:
            Validated LineType or None
        """
        if linetype is None:
            return None
        valid_types = {"ortho", "polyline", "spline"}
        if linetype.lower() in valid_types:
            return linetype.lower()  # type: ignore
        return None

    def get_arrow_syntax(self, relationship_type: str) -> str:
        """Get PlantUML arrow syntax with direction hint.

        For subclass relationships (inheritance), we can specify arrow
        direction to influence layout. For example:
        - '-up->' : child points up to parent
        - '-down->' : parent points down to child
        - '-->' : no direction hint

        Args:
            relationship_type: Type of relationship ('subclass', 'instance',
                             'object_property', etc.)

        Returns:
            PlantUML arrow syntax with optional direction hint
        """
        if not self.show_arrows:
            return "--"

        # Map relationship types to arrow styles
        arrow_map = {
            "subclass": "|>",  # Inheritance (triangle)
            "instance": "|>",  # Instance-of (typically dotted)
            "object_property": ">",  # Association
        }

        arrow_glyph = arrow_map.get(relationship_type, ">")

        # Add direction hint for hierarchical relationships
        if relationship_type in ("subclass", "instance"):
            if self.arrow_direction in ("up", "down", "left", "right"):
                return f"-{self.arrow_direction}-{arrow_glyph}"

        # Default: no direction hint
        return f"-{arrow_glyph}"

    def get_plantuml_directives(self) -> list[str]:
        """Generate PlantUML directives for layout control.

        Note: PlantUML only reliably supports 'top to bottom direction' and
        'left to right direction'. Other directions may not work as expected.

        Returns:
            List of PlantUML directive strings (skinparam, etc.)
        """
        directives = []

        # Layout direction
        # Note: Only top_to_bottom and left_to_right are reliably supported
        direction_map = {
            "top_to_bottom": "top to bottom direction",
            "left_to_right": "left to right direction",
            # These are not reliably supported by PlantUML:
            # "bottom_to_top": "bottom to top direction",
            # "right_to_left": "right to left direction",
        }
        if self.direction in direction_map:
            directives.append(direction_map[self.direction])

        # Hide empty members
        if self.hide_empty_members:
            directives.append("hide empty members")

        # Line type (edge routing)
        if self.linetype:
            directives.append(f"skinparam linetype {self.linetype}")

        # Group inheritance (merge arrow heads)
        if self.group_inheritance and self.group_inheritance > 0:
            directives.append(f"skinparam groupInheritance {self.group_inheritance}")

        # Spacing settings
        if self.spacing:
            for key, value in self.spacing.items():
                directives.append(f"skinparam {key} {value}")

        return directives

    def get_together_blocks(self, id_resolver: Optional[callable] = None) -> list[str]:
        """Generate PlantUML 'together' blocks for class grouping.

        Args:
            id_resolver: Optional function to convert CURIEs to PlantUML identifiers.
                        If None, CURIEs are used as-is with colons replaced.

        Returns:
            List of PlantUML 'together' block strings
        """
        if not self.together_groups:
            return []

        lines = []
        for group in self.together_groups:
            if not group:
                continue

            lines.append("together {")
            for curie in group:
                if id_resolver:
                    class_id = id_resolver(curie)
                else:
                    # Simple conversion: replace : with . for PlantUML
                    class_id = curie.replace(":", ".")
                lines.append(f"  class {class_id}")
            lines.append("}")
            lines.append("")

        return lines

    def get_hidden_links(self, id_resolver: Optional[callable] = None) -> list[str]:
        """Generate PlantUML hidden links for layout hints.

        Args:
            id_resolver: Optional function to convert CURIEs to PlantUML identifiers.
                        If None, CURIEs are used as-is with colons replaced.

        Returns:
            List of PlantUML hidden link strings
        """
        if not self.layout_hints:
            return []

        lines = []
        for hint in self.layout_hints:
            if id_resolver:
                from_id = id_resolver(hint.from_entity)
                to_id = id_resolver(hint.to_entity)
            else:
                from_id = hint.from_entity.replace(":", ".")
                to_id = hint.to_entity.replace(":", ".")

            # Build arrow syntax
            if hint.direction:
                arrow = f"-[hidden,{hint.direction}]->"
            else:
                arrow = "-[hidden]->"

            # Repeat for weight (more links = stronger influence)
            for _ in range(hint.weight):
                lines.append(f"{from_id} {arrow} {to_id}")

        return lines

    def __repr__(self) -> str:
        return (
            f"LayoutConfig(name={self.name!r}, "
            f"direction={self.direction}, "
            f"arrow_dir={self.arrow_direction}, "
            f"linetype={self.linetype}, "
            f"group_inheritance={self.group_inheritance}, "
            f"together_groups={len(self.together_groups)}, "
            f"layout_hints={len(self.layout_hints)})"
        )


class LayoutConfigManager:
    """Manager for layout configurations.

    Loads and manages YAML-based layout specifications with support
    for multiple layouts and shared configuration via YAML anchors.

    Attributes:
        defaults: Default layout settings
        layouts: Dictionary of available layout configurations
    """

    def __init__(self, yaml_path: Path | str):
        """Load layout configuration from a YAML file.

        Args:
            yaml_path: Path to YAML layout configuration file
        """
        yaml_path = Path(yaml_path)
        self.config = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        self.defaults = self.config.get("defaults", {}) or {}

        # Load layouts
        self.layouts = {}
        for layout_name, layout_config in (
            self.config.get("layouts", {}) or {}
        ).items():
            self.layouts[layout_name] = LayoutConfig(layout_name, layout_config)

    def get_layout(self, name: str) -> LayoutConfig:
        """Get a layout configuration by name.

        Args:
            name: Layout identifier

        Returns:
            LayoutConfig instance

        Raises:
            KeyError: If layout name not found
        """
        if name not in self.layouts:
            raise KeyError(
                f"Layout '{name}' not found. Available layouts: "
                f"{', '.join(self.layouts.keys())}"
            )
        return self.layouts[name]

    def list_layouts(self) -> list[str]:
        """Get list of available layout names.

        Returns:
            List of layout identifier strings
        """
        return list(self.layouts.keys())

    def __repr__(self) -> str:
        return f"LayoutConfigManager(layouts={list(self.layouts.keys())})"


def load_layout_config(path: Path | str) -> LayoutConfigManager:
    """Load layout configuration from a YAML file.

    Args:
        path: Path to YAML layout configuration file

    Returns:
        LayoutConfigManager instance
    """
    return LayoutConfigManager(path)
