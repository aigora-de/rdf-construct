"""PlantUML layout configuration for RDF class diagrams.

Provides control over diagram direction, spacing, grouping,
and other layout-related aspects.
"""

from pathlib import Path
from typing import Any, Literal

import yaml


LayoutDirection = Literal[
    "top_to_bottom",
    "bottom_to_top",
    "left_to_right",
    "right_to_left",
]


class LayoutConfig:
    """Layout configuration for PlantUML diagrams.

    Attributes:
        name: Layout identifier
        description: Human-readable description
        direction: Primary layout direction
        hide_empty_members: Whether to hide classes with no attributes/methods
        spacing: Spacing configuration (future use)
        group_by_namespace: Whether to group classes by namespace
        arrow_direction: Direction hint for arrows ('up', 'down', 'left', 'right')
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
        # This affects how we render inheritance arrows
        arrow_dir = config.get("arrow_direction", "up")
        self.arrow_direction = self._validate_arrow_direction(arrow_dir)

        # Grouping
        self.group_by_namespace = config.get("group_by_namespace", False)

        # Spacing (for future PlantUML skinparam settings)
        self.spacing = config.get("spacing", {})

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
            if self.arrow_direction == "up":
                return f"-{self.arrow_direction}-{arrow_glyph}"
            elif self.arrow_direction == "down":
                return f"-{self.arrow_direction}-{arrow_glyph}"
            elif self.arrow_direction == "left":
                return f"-{self.arrow_direction}-{arrow_glyph}"
            elif self.arrow_direction == "right":
                return f"-{self.arrow_direction}-{arrow_glyph}"

        # Default: no direction hint
        return f"-{arrow_glyph}"

    def get_plantuml_directives(self) -> list[str]:
        """Generate PlantUML directives for layout control.

        Returns:
            List of PlantUML directive strings (skinparam, etc.)
        """
        directives = []

        # Layout direction
        direction_map = {
            "top_to_bottom": "top to bottom direction",
            "bottom_to_top": "bottom to top direction",
            "left_to_right": "left to right direction",
            "right_to_left": "right to left direction",
        }
        if self.direction in direction_map:
            directives.append(direction_map[self.direction])

        # Hide empty members
        if self.hide_empty_members:
            directives.append("hide empty members")

        # Spacing settings (if any)
        if self.spacing:
            for key, value in self.spacing.items():
                directives.append(f"skinparam {key} {value}")

        return directives

    def __repr__(self) -> str:
        return (
            f"LayoutConfig(name={self.name!r}, "
            f"direction={self.direction}, "
            f"arrow_dir={self.arrow_direction})"
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
