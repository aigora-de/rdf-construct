"""Command-line interface for rdf-construct."""

import sys
from pathlib import Path

import click
from rdflib import Graph, RDF, URIRef
from rdflib.namespace import OWL

from rdf_construct.core import (
    OrderingConfig,
    build_section_graph,
    extract_prefix_map,
    rebind_prefixes,
    select_subjects,
    serialise_turtle,
    sort_subjects,
    expand_curie,
)
from rdf_construct.uml import (
    load_uml_config,
    collect_diagram_entities,
    render_plantuml,
)
from rdf_construct.uml.uml_style import load_style_config
from rdf_construct.uml.uml_layout import load_layout_config
from rdf_construct.uml.odm_renderer import render_odm_plantuml

from rdf_construct.diff import compare_files, format_diff, filter_diff, parse_filter_string

# Valid rendering modes
RENDERING_MODES = ["default", "odm"]

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

        # Get predicate ordering for this profile
        predicate_order = ordering_config.get_predicate_order(prof_name)

        # Serialise with predicate ordering
        out_file = outdir / f"{source.stem}-{prof_name}.ttl"
        serialise_turtle(out_graph, ordered_subjects, out_file, predicate_order)
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
@click.argument("sources", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--config",
    "-C",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="YAML configuration file defining UML contexts",
)
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
@click.option(
    "--rendering-mode", "-r",
    type=click.Choice(RENDERING_MODES, case_sensitive=False),
    default="default",
    help="Rendering mode: 'default' (custom stereotypes) or 'odm' (OMG ODM RDF Profile compliant)"
)
def uml(sources, config, context, outdir, style_config, style, layout_config, layout, rendering_mode):
    """Generate UML class diagrams from RDF ontologies.

    SOURCES: One or more RDF Turtle files (.ttl). The first file is the primary
    source; additional files provide supporting definitions (e.g., imported
    ontologies for complete class hierarchies).

    Examples:

        # Basic usage - single source
        rdf-construct uml ontology.ttl -C contexts.yml

        # Multiple sources - primary + supporting ontology
        rdf-construct uml building.ttl ies4.ttl -C contexts.yml

        # Multiple sources with styling (hierarchy inheritance works!)
        rdf-construct uml building.ttl ies4.ttl -C contexts.yml \\
            --style-config ies_colours.yml --style ies_full

        # Generate specific context with ODM mode
        rdf-construct uml building.ttl ies4.ttl -C contexts.yml -c core -r odm
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

    # Display rendering mode
    if rendering_mode == "odm":
        click.echo("Using rendering mode: ODM RDF Profile (OMG compliant)")
    else:
        click.echo("Using rendering mode: default")

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

    # Parse source RDF files into a single graph
    # The first source is considered the "primary" (used for output naming)
    primary_source = sources[0]
    graph = Graph()

    for source in sources:
        click.echo(f"Loading {source}...")
        # Guess format from extension
        suffix = source.suffix.lower()
        if suffix in (".ttl", ".turtle"):
            fmt = "turtle"
        elif suffix in (".rdf", ".xml", ".owl"):
            fmt = "xml"
        elif suffix in (".nt", ".ntriples"):
            fmt = "nt"
        elif suffix in (".n3",):
            fmt = "n3"
        elif suffix in (".jsonld", ".json"):
            fmt = "json-ld"
        else:
            fmt = "turtle"  # Default to turtle

        graph.parse(source.as_posix(), format=fmt)

    if len(sources) > 1:
        click.echo(f"  Merged {len(sources)} source files ({len(graph)} triples total)")

    # Get selectors from defaults (if any)
    selectors = uml_config.defaults.get("selectors", {})

    # Generate each context
    for ctx_name in contexts_to_gen:
        click.echo(f"Generating diagram: {ctx_name}")
        ctx = uml_config.get_context(ctx_name)

        # Select entities
        entities = collect_diagram_entities(graph, ctx, selectors)

        # Build output filename (include mode suffix for ODM)
        if rendering_mode == "odm":
            out_file = outdir / f"{primary_source.stem}-{ctx_name}-odm.puml"
        else:
            out_file = outdir / f"{primary_source.stem}-{ctx_name}.puml"

        # Render with optional style and layout
        if rendering_mode == "odm":
            render_odm_plantuml(graph, entities, out_file, style_scheme, layout_cfg)
        else:
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


@cli.command()
@click.argument("old_file", type=click.Path(exists=True, path_type=Path))
@click.argument("new_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Write output to file instead of stdout",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["text", "markdown", "md", "json"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--show",
    type=str,
    help="Show only these change types (comma-separated: added,removed,modified)",
)
@click.option(
    "--hide",
    type=str,
    help="Hide these change types (comma-separated: added,removed,modified)",
)
@click.option(
    "--entities",
    type=str,
    help="Show only these entity types (comma-separated: classes,properties,instances)",
)
@click.option(
    "--ignore-predicates",
    type=str,
    help="Ignore these predicates in comparison (comma-separated CURIEs)",
)
def diff(
    old_file: Path,
    new_file: Path,
    output: Path | None,
    output_format: str,
    show: str | None,
    hide: str | None,
    entities: str | None,
    ignore_predicates: str | None,
):
    """Compare two RDF files and show semantic differences.

    Compares OLD_FILE to NEW_FILE and reports changes, ignoring cosmetic
    differences like statement order, prefix bindings, and whitespace.

    \b
    Examples:
        rdf-construct diff v1.0.ttl v1.1.ttl
        rdf-construct diff v1.0.ttl v1.1.ttl --format markdown -o CHANGELOG.md
        rdf-construct diff old.ttl new.ttl --show added,removed
        rdf-construct diff old.ttl new.ttl --entities classes

    \b
    Exit codes:
        0 - Graphs are semantically identical
        1 - Differences were found
        2 - Error occurred
    """

    try:
        # Parse ignored predicates
        ignore_preds: set[URIRef] | None = None
        if ignore_predicates:
            temp_graph = Graph()
            temp_graph.parse(str(old_file), format="turtle")

            ignore_preds = set()
            for pred_str in ignore_predicates.split(","):
                pred_str = pred_str.strip()
                uri = expand_curie(temp_graph, pred_str)
                if uri:
                    ignore_preds.add(uri)
                else:
                    click.secho(
                        f"Warning: Could not expand predicate '{pred_str}'",
                        fg="yellow",
                        err=True,
                    )

        # Perform comparison
        click.echo(f"Comparing {old_file.name} → {new_file.name}...", err=True)
        diff_result = compare_files(old_file, new_file, ignore_predicates=ignore_preds)

        # Apply filters
        if show or hide or entities:
            show_types = parse_filter_string(show) if show else None
            hide_types = parse_filter_string(hide) if hide else None
            entity_types = parse_filter_string(entities) if entities else None

            diff_result = filter_diff(
                diff_result,
                show_types=show_types,
                hide_types=hide_types,
                entity_types=entity_types,
            )

        # Load graph for CURIE formatting
        graph_for_format = None
        if output_format in ("text", "markdown", "md"):
            graph_for_format = Graph()
            graph_for_format.parse(str(new_file), format="turtle")

        # Format output
        formatted = format_diff(diff_result, format_name=output_format, graph=graph_for_format)

        # Write output
        if output:
            output.write_text(formatted)
            click.secho(f"✓ Wrote diff to {output}", fg="green", err=True)
        else:
            click.echo(formatted)

        # Exit code: 0 if identical, 1 if different
        if diff_result.is_identical:
            click.secho("Graphs are semantically identical.", fg="green", err=True)
            sys.exit(0)
        else:
            sys.exit(1)

    except FileNotFoundError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        sys.exit(2)
    except ValueError as e:
        click.secho(f"Error parsing RDF: {e}", fg="red", err=True)
        sys.exit(2)
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        sys.exit(2)

if __name__ == "__main__":
    cli()
