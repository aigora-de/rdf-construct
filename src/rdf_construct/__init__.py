"""rdf-construct: Semantic RDF manipulation toolkit.

Named after the ROM construct from William Gibson's Neuromancer -
preserved, structured knowledge that can be queried and transformed.
"""

__version__ = "0.2.0"

from . import core, uml
from .cli import cli

__all__ = ["core", "uml", "cli"]
