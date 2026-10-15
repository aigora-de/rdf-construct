"""Run the CLI as ``python -m rdf_construct``, the same as the ``rdf-construct`` script.

``cli`` runs in Click's standalone mode, which exits by itself, so nothing here calls
``sys.exit``: only ``cli.py`` may (#286).
"""

from rdf_construct.cli import cli

if __name__ == "__main__":
    cli(prog_name="rdf-construct")
