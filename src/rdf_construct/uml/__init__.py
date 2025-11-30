"""UML diagram generation from RDF ontologies.

This module provides functionality to generate PlantUML class diagrams
from RDF/OWL ontologies based on YAML-defined contexts.
"""

from .context import UMLConfig, UMLContext, load_uml_config
from .mapper import collect_diagram_entities
from .renderer import render_plantuml
from .odm_renderer import ODMRenderer, render_odm_plantuml

__all__ = [
    "UMLConfig",
    "UMLContext",
    "load_uml_config",
    "collect_diagram_entities",
    "render_plantuml",
    "uml_layout",
    "uml_style",
    "ODMRenderer",
    "render_odm_plantuml",
]
