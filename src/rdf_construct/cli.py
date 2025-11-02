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
from .uml import (
    load_uml_config,
    collect_diagram_entities,
    render_plantuml,
)
from .uml.uml_style import load_style_config
from .uml.uml_layout import load_layout_config

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


@cli.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.argument("config", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--context",
    "-c",
    multiple=True,
    help="Context(s) to generate (default: all contexts in config)",
)
@click.option(
    "--outdir",
    "-o",
    type=click.Path(path_type=Path),
    default="diagrams",
    help="Output directory (default: diagrams)",
)
@click.option(
    "--style-config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to style configuration YAML (e.g., examples/uml_styles.yml)"
)
@click.option(
    "--style", "-s",
    help="Style scheme name to use (e.g., 'default', 'ies_semantic')"
)
@click.option(
    "--layout-config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to layout configuration YAML (e.g., examples/uml_layouts.yml)"
)
@click.option(
    "--layout", "-l",
    help="Layout name to use (e.g., 'hierarchy', 'compact')"
)
def uml(source, config, context, outdir, style_config, style, layout_config, layout):
    """Generate UML class diagrams from RDF ontologies.

    SOURCE: Input RDF Turtle file (.ttl)
    CONFIG: YAML configuration file defining UML contexts

    Examples:

        # Basic usage (no styling)
        rdf-construct uml ontology.ttl example/uml_contexts.yml

        # Generate only specific contexts
        rdf-construct uml ontology.ttl example/uml_contexts.yml -c animal_taxonomy

        # With default style and hierarchy layout
        rdf-construct uml ontology.ttl example/uml_contexts.yml \\
            --style-config examples/uml_styles.yml --style default \\
            --layout-config examples/uml_layouts.yml --layout hierarchy
    """
    # Load style if provided
    style_scheme = None
    if style_config and style:
        style_cfg = load_style_config(style_config)
        try:
            style_scheme = style_cfg.get_scheme(style)
            click.echo(f"Using style: {style}")
        except KeyError as e:
            click.secho(str(e), fg="red", err=True)
            click.echo(f"Available styles: {', '.join(style_cfg.list_schemes())}")
            raise click.Abort()

    # Load layout if provided
    layout_cfg = None
    if layout_config and layout:
        layout_mgr = load_layout_config(layout_config)
        try:
            layout_cfg = layout_mgr.get_layout(layout)
            click.echo(f"Using layout: {layout}")
        except KeyError as e:
            click.secho(str(e), fg="red", err=True)
            click.echo(f"Available layouts: {', '.join(layout_mgr.list_layouts())}")
            raise click.Abort()

    # Load UML configuration
    uml_config = load_uml_config(config)

    # Determine which contexts to generate
    if context:
        contexts_to_gen = list(context)
    else:
        contexts_to_gen = uml_config.list_contexts()

    # Validate requested contexts exist
    for ctx_name in contexts_to_gen:
        if ctx_name not in uml_config.contexts:
            click.secho(
                f"Error: Context '{ctx_name}' not found in config.", fg="red", err=True
            )
            available = ", ".join(uml_config.list_contexts())
            click.echo(f"Available contexts: {available}", err=True)
            raise click.Abort()

    # Create output directory
    # ToDo - handle exceptions properly
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Parse source RDF
    click.echo(f"Loading {source}...")
    graph = Graph()
    graph.parse(source.as_posix(), format="turtle")

    # Get selectors from defaults (if any)
    selectors = uml_config.defaults.get("selectors", {})

    # Generate each context
    for ctx_name in contexts_to_gen:
        click.echo(f"Generating diagram: {ctx_name}")
        ctx = uml_config.get_context(ctx_name)

        # Select entities
        entities = collect_diagram_entities(graph, ctx, selectors)

        # Build output filename
        out_file = outdir / f"{source.stem}-{ctx_name}.puml"

        # Render with optional style and layout
        render_plantuml(graph, entities, out_file, style_scheme, layout_cfg)

        click.secho(f"  ✓ {out_file}", fg="green")
        click.echo(
            f"    Classes: {len(entities['classes'])}, "
            f"Properties: {len(entities['object_properties']) + len(entities['datatype_properties'])}, "
            f"Instances: {len(entities['instances'])}"
        )

    click.secho(
        f"\nGenerated {len(contexts_to_gen)} diagram(s) in {outdir}/", fg="cyan"
    )


@cli.command()
@click.argument("config", type=click.Path(exists=True, path_type=Path))
def contexts(config: Path):
    """List available UML contexts in a configuration file.

    CONFIG: YAML configuration file to inspect
    """
    uml_config = load_uml_config(config)

    click.secho("Available UML contexts:", fg="cyan", bold=True)
    click.echo()

    for ctx_name in uml_config.list_contexts():
        ctx = uml_config.get_context(ctx_name)
        click.secho(f"  {ctx_name}", fg="green", bold=True)
        if ctx.description:
            click.echo(f"    {ctx.description}")

        # Show selection strategy
        if ctx.root_classes:
            click.echo(f"    Roots: {', '.join(ctx.root_classes)}")
        elif ctx.focus_classes:
            click.echo(f"    Focus: {', '.join(ctx.focus_classes)}")
        elif ctx.selector:
            click.echo(f"    Selector: {ctx.selector}")

        if ctx.include_descendants:
            depth_str = f"depth={ctx.max_depth}" if ctx.max_depth else "unlimited"
            click.echo(f"    Includes descendants ({depth_str})")

        click.echo(f"    Properties: {ctx.property_mode}")
        click.echo()


if __name__ == "__main__":
    cli()
