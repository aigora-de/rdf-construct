"""Command-line interface for rdf-construct."""

from pathlib import Path

import click
from rdflib import Graph, RDF
from rdflib.namespace import OWL

from .core import (
    OrderingConfig,
    build_section_graph,
    extract_prefix_map,
    rebind_prefixes,
    select_subjects,
    serialise_turtle,
    sort_subjects,
)


@click.group()
@click.version_option()
def cli():
    """rdf-construct: Semantic RDF manipulation toolkit.

    Reorder, serialise, and manipulate RDF ontologies with semantic awareness.
    """
    pass


@cli.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.argument("config", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--profile",
    "-p",
    multiple=True,
    help="Profile(s) to generate (default: all profiles in config)",
)
@click.option(
    "--outdir",
    "-o",
    type=click.Path(path_type=Path),
    default="src/ontology",
    help="Output directory (default: src/ontology)",
)
def order(source: Path, config: Path, profile: tuple[str, ...], outdir: Path):
    """Reorder RDF Turtle files according to semantic profiles.

    SOURCE: Input RDF Turtle file (.ttl)
    CONFIG: YAML configuration file defining ordering profiles

    Examples:

        # Generate all profiles defined in config
        rdf-construct order ontology.ttl order.yml

        # Generate only specific profiles
        rdf-construct order ontology.ttl order.yml -p alpha -p logical_topo

        # Custom output directory
        rdf-construct order ontology.ttl order.yml -o output/
    """
    # Load configuration
    ordering_config = OrderingConfig(config)

    # Determine which profiles to generate
    if profile:
        profiles_to_gen = list(profile)
    else:
        profiles_to_gen = ordering_config.list_profiles()

    # Validate requested profiles exist
    for prof_name in profiles_to_gen:
        if prof_name not in ordering_config.profiles:
            click.secho(
                f"Error: Profile '{prof_name}' not found in config.", fg="red", err=True
            )
            available = ", ".join(ordering_config.list_profiles())
            click.echo(f"Available profiles: {available}", err=True)
            raise click.Abort()

    # Create output directory
    outdir.mkdir(parents=True, exist_ok=True)

    # Parse source RDF
    click.echo(f"Loading {source}...")
    graph = Graph()
    graph.parse(source.as_posix(), format="turtle")
    prefix_map = extract_prefix_map(graph)

    # Generate each profile
    for prof_name in profiles_to_gen:
        click.echo(f"Constructing profile: {prof_name}")
        prof = ordering_config.get_profile(prof_name)

        ordered_subjects: list = []
        seen: set = set()

        # Process each section
        for sec in prof.sections:
            if not isinstance(sec, dict) or not sec:
                continue

            sec_name, sec_cfg = next(iter(sec.items()))

            # Handle header section - ontology metadata
            if sec_name == "header":
                ontology_subjects = [
                    s for s in graph.subjects(RDF.type, OWL.Ontology) if s not in seen
                ]
                for s in ontology_subjects:
                    ordered_subjects.append(s)
                    seen.add(s)
                continue

            # Regular sections
            sec_cfg = sec_cfg or {}
            select_key = sec_cfg.get("select", sec_name)
            sort_mode = sec_cfg.get("sort", "qname_alpha")
            roots_cfg = sec_cfg.get("roots")

            # Select and sort subjects
            chosen = select_subjects(graph, select_key, ordering_config.selectors)
            chosen = [s for s in chosen if s not in seen]

            ordered = sort_subjects(graph, set(chosen), sort_mode, roots_cfg)

            for s in ordered:
                if s not in seen:
                    ordered_subjects.append(s)
                    seen.add(s)

        # Build output graph
        out_graph = build_section_graph(graph, ordered_subjects)

        # Rebind prefixes if configured
        if ordering_config.defaults.get("preserve_prefix_order", True):
            if ordering_config.prefix_order:
                rebind_prefixes(out_graph, ordering_config.prefix_order, prefix_map)

        # Serialise
        out_file = outdir / f"{source.stem}-{prof_name}.ttl"
        serialise_turtle(out_graph, ordered_subjects, out_file)
        click.secho(f"  ✓ {out_file}", fg="green")

    click.secho(
        f"\nConstructed {len(profiles_to_gen)} profile(s) in {outdir}/", fg="cyan"
    )


@cli.command()
@click.argument("config", type=click.Path(exists=True, path_type=Path))
def profiles(config: Path):
    """List available profiles in a configuration file.

    CONFIG: YAML configuration file to inspect
    """
    ordering_config = OrderingConfig(config)

    click.secho("Available profiles:", fg="cyan", bold=True)
    click.echo()

    for prof_name in ordering_config.list_profiles():
        prof = ordering_config.get_profile(prof_name)
        click.secho(f"  {prof_name}", fg="green", bold=True)
        if prof.description:
            click.echo(f"    {prof.description}")
        click.echo(f"    Sections: {len(prof.sections)}")
        click.echo()


if __name__ == "__main__":
    cli()
