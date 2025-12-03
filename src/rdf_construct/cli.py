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

from rdf_construct.lint import (
    LintEngine,
    LintConfig,
    load_lint_config,
    find_config_file,
    get_formatter,
    list_rules,
    get_all_rules,
)

LINT_LEVELS = ["strict", "standard", "relaxed"]
LINT_FORMATS = ["text", "json"]

from rdf_construct.diff import compare_files, format_diff, filter_diff, parse_filter_string

from rdf_construct.puml2rdf import (
    ConversionConfig,
    PlantUMLParser,
    PumlToRdfConverter,
    load_import_config,
    merge_with_existing,
    validate_puml,
    validate_rdf,
)

from rdf_construct.cq import load_test_suite, CQTestRunner, format_results

from rdf_construct.stats import (
    collect_stats,
    compare_stats,
    format_stats,
    format_comparison,
)

# Valid rendering modes
RENDERING_MODES = ["default", "odm"]

@click.group()
@click.version_option()
def cli():
    """rdf-construct: Semantic RDF manipulation toolkit.

    Tools for working with RDF ontologies:

    \b
    - lint: Check ontology quality (structural issues, documentation, best practices)
    - uml: Generate PlantUML class diagrams
    - order: Reorder Turtle files with semantic awareness

    Use COMMAND --help for detailed options.
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
@click.argument("sources", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--level",
    "-l",
    type=click.Choice(["strict", "standard", "relaxed"], case_sensitive=False),
    default="standard",
    help="Strictness level (default: standard)",
)
@click.option(
    "--format",
    "-f",
    "output_format",  # Renamed to avoid shadowing builtin
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to .rdf-lint.yml configuration file",
)
@click.option(
    "--enable",
    "-e",
    multiple=True,
    help="Enable specific rules (can be used multiple times)",
)
@click.option(
    "--disable",
    "-d",
    multiple=True,
    help="Disable specific rules (can be used multiple times)",
)
@click.option(
    "--no-colour",
    "--no-color",
    is_flag=True,
    help="Disable coloured output",
)
@click.option(
    "--list-rules",
    "list_rules_flag",
    is_flag=True,
    help="List available rules and exit",
)
@click.option(
    "--init",
    "init_config",
    is_flag=True,
    help="Generate a default .rdf-lint.yml config file and exit",
)
def lint(
    sources: tuple[Path, ...],
    level: str,
    output_format: str,
    config: Path | None,
    enable: tuple[str, ...],
    disable: tuple[str, ...],
    no_colour: bool,
    list_rules_flag: bool,  # Must match the name above
    init_config: bool,
):
    """Check RDF ontologies for quality issues.

    Performs static analysis to detect structural problems, missing
    documentation, and best practice violations.

    \b
    SOURCES: One or more RDF files to check (.ttl, .rdf, .owl, etc.)

    \b
    Exit codes:
      0 - No issues found
      1 - Warnings found (no errors)
      2 - Errors found

    \b
    Examples:
      # Basic usage
      rdf-construct lint ontology.ttl

      # Multiple files
      rdf-construct lint core.ttl domain.ttl

      # Strict mode (warnings become errors)
      rdf-construct lint ontology.ttl --level strict

      # JSON output for CI
      rdf-construct lint ontology.ttl --format json

      # Use config file
      rdf-construct lint ontology.ttl --config .rdf-lint.yml

      # Enable/disable specific rules
      rdf-construct lint ontology.ttl --enable orphan-class --disable missing-comment

      # List available rules
      rdf-construct lint --list-rules
    """
    # Handle --init flag
    if init_config:
        from .lint import create_default_config

        config_path = Path(".rdf-lint.yml")
        if config_path.exists():
            click.secho(f"Config file already exists: {config_path}", fg="red", err=True)
            raise click.Abort()

        config_content = create_default_config()
        config_path.write_text(config_content)
        click.secho(f"Created {config_path}", fg="green")
        return

    # Handle --list-rules flag
    if list_rules_flag:
        from .lint import get_all_rules

        rules = get_all_rules()
        click.secho("Available lint rules:", fg="cyan", bold=True)
        click.echo()

        # Group by category
        categories: dict[str, list] = {}
        for rule_id, spec in sorted(rules.items()):
            cat = spec.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(spec)

        for category, specs in sorted(categories.items()):
            click.secho(f"  {category.title()}", fg="yellow", bold=True)
            for spec in specs:
                severity_color = {
                    "error": "red",
                    "warning": "yellow",
                    "info": "blue",
                }[spec.default_severity.value]
                click.echo(
                    f"    {spec.rule_id}: "
                    f"{click.style(spec.default_severity.value, fg=severity_color)} - "
                    f"{spec.description}"
                )
            click.echo()

        return

    # Validate we have sources for actual linting
    if not sources:
        click.secho("Error: No source files specified.", fg="red", err=True)
        raise click.Abort()

    lint_config: LintConfig

    if config:
        # Load from specified config file
        try:
            lint_config = load_lint_config(config)
            click.echo(f"Using config: {config}")
        except (FileNotFoundError, ValueError) as e:
            click.secho(f"Error loading config: {e}", fg="red", err=True)
            raise click.Abort()
    else:
        # Try to find config file automatically
        found_config = find_config_file()
        if found_config:
            try:
                lint_config = load_lint_config(found_config)
                click.echo(f"Using config: {found_config}")
            except (FileNotFoundError, ValueError) as e:
                click.secho(f"Error loading config: {e}", fg="red", err=True)
                raise click.Abort()
        else:
            lint_config = LintConfig()

    # Apply CLI overrides
    lint_config.level = level

    if enable:
        lint_config.enabled_rules = set(enable)
    if disable:
        lint_config.disabled_rules.update(disable)

    # Create engine and run
    engine = LintEngine(lint_config)

    click.echo(f"Scanning {len(sources)} file(s)...")
    click.echo()

    summary = engine.lint_files(list(sources))

    # Format and output results
    use_colour = not no_colour and output_format == "text"
    formatter = get_formatter(output_format, use_colour=use_colour)

    output = formatter.format_summary(summary)
    click.echo(output)

    # Exit with appropriate code
    raise SystemExit(summary.exit_code)


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


@cli.command()
@click.argument("sources", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="docs",
    help="Output directory (default: docs)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["html", "markdown", "md", "json"], case_sensitive=False),
    default="html",
    help="Output format (default: html)",
)
@click.option(
    "--config",
    "-C",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration YAML file",
)
@click.option(
    "--template",
    "-t",
    type=click.Path(exists=True, path_type=Path),
    help="Path to custom template directory",
)
@click.option(
    "--single-page",
    is_flag=True,
    help="Generate single-page documentation",
)
@click.option(
    "--title",
    help="Override ontology title",
)
@click.option(
    "--no-search",
    is_flag=True,
    help="Disable search index generation (HTML only)",
)
@click.option(
    "--no-instances",
    is_flag=True,
    help="Exclude instances from documentation",
)
@click.option(
    "--include",
    type=str,
    help="Include only these entity types (comma-separated: classes,properties,instances)",
)
@click.option(
    "--exclude",
    type=str,
    help="Exclude these entity types (comma-separated: classes,properties,instances)",
)
def docs(
    sources: tuple[Path, ...],
    output: Path,
    output_format: str,
    config: Path | None,
    template: Path | None,
    single_page: bool,
    title: str | None,
    no_search: bool,
    no_instances: bool,
    include: str | None,
    exclude: str | None,
):
    """Generate documentation from RDF ontologies.

    SOURCES: One or more RDF files to generate documentation from.

    \b
    Examples:
        # Basic HTML documentation
        rdf-construct docs ontology.ttl

        # Markdown output to custom directory
        rdf-construct docs ontology.ttl --format markdown -o api-docs/

        # Single-page HTML with custom title
        rdf-construct docs ontology.ttl --single-page --title "My Ontology"

        # JSON output for custom rendering
        rdf-construct docs ontology.ttl --format json

        # Use custom templates
        rdf-construct docs ontology.ttl --template my-templates/

        # Generate from multiple sources (merged)
        rdf-construct docs domain.ttl foundation.ttl -o docs/

    \b
    Output formats:
        html      - Navigable HTML pages with search (default)
        markdown  - GitHub/GitLab compatible Markdown
        json      - Structured JSON for custom rendering
    """
    from rdflib import Graph

    from rdf_construct.docs import DocsConfig, DocsGenerator, load_docs_config

    # Load or create configuration
    if config:
        doc_config = load_docs_config(config)
    else:
        doc_config = DocsConfig()

    # Apply CLI overrides
    doc_config.output_dir = output
    doc_config.format = "markdown" if output_format == "md" else output_format
    doc_config.single_page = single_page
    doc_config.include_search = not no_search
    doc_config.include_instances = not no_instances

    if template:
        doc_config.template_dir = template
    if title:
        doc_config.title = title

    # Parse include/exclude filters
    if include:
        types = [t.strip().lower() for t in include.split(",")]
        doc_config.include_classes = "classes" in types
        doc_config.include_object_properties = "properties" in types or "object_properties" in types
        doc_config.include_datatype_properties = "properties" in types or "datatype_properties" in types
        doc_config.include_annotation_properties = "properties" in types or "annotation_properties" in types
        doc_config.include_instances = "instances" in types

    if exclude:
        types = [t.strip().lower() for t in exclude.split(",")]
        if "classes" in types:
            doc_config.include_classes = False
        if "properties" in types:
            doc_config.include_object_properties = False
            doc_config.include_datatype_properties = False
            doc_config.include_annotation_properties = False
        if "instances" in types:
            doc_config.include_instances = False

    # Load RDF sources
    click.echo(f"Loading {len(sources)} source file(s)...")
    graph = Graph()

    for source in sources:
        click.echo(f"  Parsing {source.name}...")

        # Determine format from extension
        suffix = source.suffix.lower()
        format_map = {
            ".ttl": "turtle",
            ".turtle": "turtle",
            ".rdf": "xml",
            ".xml": "xml",
            ".owl": "xml",
            ".nt": "nt",
            ".ntriples": "nt",
            ".n3": "n3",
            ".jsonld": "json-ld",
            ".json": "json-ld",
        }
        rdf_format = format_map.get(suffix, "turtle")

        graph.parse(str(source), format=rdf_format)

    click.echo(f"  Total: {len(graph)} triples")
    click.echo()

    # Generate documentation
    click.echo(f"Generating {doc_config.format} documentation...")

    generator = DocsGenerator(doc_config)
    result = generator.generate(graph)

    # Summary
    click.echo()
    click.secho(f"✓ Generated {result.total_pages} files to {result.output_dir}/", fg="green")
    click.echo(f"  Classes: {result.classes_count}")
    click.echo(f"  Properties: {result.properties_count}")
    click.echo(f"  Instances: {result.instances_count}")

    # Show entry point
    if doc_config.format == "html":
        index_path = result.output_dir / "index.html"
        click.echo()
        click.secho(f"Open {index_path} in your browser to view the documentation.", fg="cyan")


@cli.command("shacl-gen")
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path (default: <source>-shapes.ttl)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["turtle", "ttl", "json-ld", "jsonld"], case_sensitive=False),
    default="turtle",
    help="Output format (default: turtle)",
)
@click.option(
    "--level",
    "-l",
    type=click.Choice(["minimal", "standard", "strict"], case_sensitive=False),
    default="standard",
    help="Strictness level for constraint generation (default: standard)",
)
@click.option(
    "--config",
    "-C",
    type=click.Path(exists=True, path_type=Path),
    help="YAML configuration file",
)
@click.option(
    "--classes",
    type=str,
    help="Comma-separated list of classes to generate shapes for",
)
@click.option(
    "--closed",
    is_flag=True,
    help="Generate closed shapes (no extra properties allowed)",
)
@click.option(
    "--default-severity",
    type=click.Choice(["violation", "warning", "info"], case_sensitive=False),
    default="violation",
    help="Default severity for generated constraints",
)
@click.option(
    "--no-labels",
    is_flag=True,
    help="Don't include rdfs:label as sh:name",
)
@click.option(
    "--no-descriptions",
    is_flag=True,
    help="Don't include rdfs:comment as sh:description",
)
@click.option(
    "--no-inherit",
    is_flag=True,
    help="Don't inherit constraints from superclasses",
)
def shacl_gen(
        source: Path,
        output: Path | None,
        output_format: str,
        level: str,
        config: Path | None,
        classes: str | None,
        closed: bool,
        default_severity: str,
        no_labels: bool,
        no_descriptions: bool,
        no_inherit: bool,
):
    """Generate SHACL validation shapes from OWL ontology.

    Converts OWL class definitions to SHACL NodeShapes, extracting
    constraints from domain/range declarations, cardinality restrictions,
    functional properties, and other OWL patterns.

    SOURCE: Input RDF ontology file (.ttl, .rdf, .owl, etc.)

    \b
    Strictness levels:
      minimal   - Basic type constraints only (sh:class, sh:datatype)
      standard  - Adds cardinality and functional property constraints
      strict    - Maximum constraints including sh:closed, enumerations

    \b
    Examples:
        # Basic generation
        rdf-construct shacl-gen ontology.ttl

        # Generate with strict constraints
        rdf-construct shacl-gen ontology.ttl --level strict --closed

        # Custom output path and format
        rdf-construct shacl-gen ontology.ttl -o shapes.ttl --format turtle

        # Focus on specific classes
        rdf-construct shacl-gen ontology.ttl --classes "ex:Building,ex:Floor"

        # Use configuration file
        rdf-construct shacl-gen ontology.ttl --config shacl-config.yml

        # Generate warnings instead of violations
        rdf-construct shacl-gen ontology.ttl --default-severity warning
    """
    from rdf_construct.shacl import (
        generate_shapes_to_file,
        load_shacl_config,
        ShaclConfig,
        StrictnessLevel,
        Severity,
    )

    # Determine output path
    if output is None:
        suffix = ".json" if "json" in output_format.lower() else ".ttl"
        output = source.with_stem(f"{source.stem}-shapes").with_suffix(suffix)

    # Normalise format string
    if output_format.lower() in ("ttl", "turtle"):
        output_format = "turtle"
    elif output_format.lower() in ("json-ld", "jsonld"):
        output_format = "json-ld"

    try:
        # Load configuration from file or build from CLI options
        if config:
            shacl_config = load_shacl_config(config)
            click.echo(f"Loaded configuration from {config}")
        else:
            shacl_config = ShaclConfig()

        # Apply CLI overrides
        shacl_config.level = StrictnessLevel(level.lower())

        if classes:
            shacl_config.target_classes = [c.strip() for c in classes.split(",")]

        if closed:
            shacl_config.closed = True

        shacl_config.default_severity = Severity(default_severity.lower())

        if no_labels:
            shacl_config.include_labels = False

        if no_descriptions:
            shacl_config.include_descriptions = False

        if no_inherit:
            shacl_config.inherit_constraints = False

        # Generate shapes
        click.echo(f"Generating SHACL shapes from {source}...")
        click.echo(f"  Level: {shacl_config.level.value}")

        if shacl_config.target_classes:
            click.echo(f"  Target classes: {', '.join(shacl_config.target_classes)}")

        shapes_graph = generate_shapes_to_file(
            source,
            output,
            shacl_config,
            output_format,
        )

        # Count generated shapes
        from rdf_construct.shacl import SH
        num_shapes = len(list(shapes_graph.subjects(
            predicate=None, object=SH.NodeShape
        )))

        click.secho(f"✓ Generated {num_shapes} shape(s) to {output}", fg="green")

        if shacl_config.closed:
            click.echo("  (closed shapes enabled)")

    except FileNotFoundError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1)
    except ValueError as e:
        click.secho(f"Configuration error: {e}", fg="red", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.secho(f"Error generating shapes: {e}", fg="red", err=True)
        raise SystemExit(1)


# Output format choices
OUTPUT_FORMATS = ["turtle", "ttl", "xml", "rdfxml", "jsonld", "json-ld", "nt", "ntriples"]


@cli.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path (default: source name with .ttl extension)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS, case_sensitive=False),
    default="turtle",
    help="Output RDF format (default: turtle)",
)
@click.option(
    "--namespace",
    "-n",
    help="Default namespace URI for the ontology",
)
@click.option(
    "--config",
    "-C",
    type=click.Path(exists=True, path_type=Path),
    help="Path to YAML configuration file",
)
@click.option(
    "--merge",
    "-m",
    type=click.Path(exists=True, path_type=Path),
    help="Existing ontology file to merge with",
)
@click.option(
    "--validate",
    "-v",
    is_flag=True,
    help="Validate only, don't generate output",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Treat warnings as errors",
)
@click.option(
    "--language",
    "-l",
    default="en",
    help="Language tag for labels/comments (default: en)",
)
@click.option(
    "--no-labels",
    is_flag=True,
    help="Don't auto-generate rdfs:label triples",
)
def puml2rdf(
    source: Path,
    output: Path | None,
    output_format: str,
    namespace: str | None,
    config: Path | None,
    merge: Path | None,
    validate: bool,
    strict: bool,
    language: str,
    no_labels: bool,
):
    """Convert PlantUML class diagram to RDF ontology.

    Parses a PlantUML file and generates an RDF/OWL ontology.
    Supports classes, attributes, inheritance, and associations.

    SOURCE: PlantUML file (.puml or .plantuml)

    \b
    Examples:
        # Basic conversion
        rdf-construct puml2rdf design.puml

        # Custom output and namespace
        rdf-construct puml2rdf design.puml -o ontology.ttl -n http://example.org/ont#

        # Validate without generating
        rdf-construct puml2rdf design.puml --validate

        # Merge with existing ontology
        rdf-construct puml2rdf design.puml --merge existing.ttl

        # Use configuration file
        rdf-construct puml2rdf design.puml -C import-config.yml

    \b
    Exit codes:
        0 - Success
        1 - Validation warnings (with --strict)
        2 - Parse or validation errors
    """
    # Normalise output format
    format_map = {
        "ttl": "turtle",
        "rdfxml": "xml",
        "json-ld": "json-ld",
        "jsonld": "json-ld",
        "ntriples": "nt",
    }
    rdf_format = format_map.get(output_format.lower(), output_format.lower())

    # Determine output path
    if output is None and not validate:
        ext_map = {"turtle": ".ttl", "xml": ".rdf", "json-ld": ".jsonld", "nt": ".nt"}
        ext = ext_map.get(rdf_format, ".ttl")
        output = source.with_suffix(ext)

    # Load configuration if provided
    if config:
        try:
            import_config = load_import_config(config)
            conversion_config = import_config.to_conversion_config()
        except Exception as e:
            click.secho(f"Error loading config: {e}", fg="red", err=True)
            sys.exit(2)
    else:
        conversion_config = ConversionConfig()

    # Override config with CLI options
    if namespace:
        conversion_config.default_namespace = namespace
    if language:
        conversion_config.language = language
    if no_labels:
        conversion_config.generate_labels = False

    # Parse PlantUML file
    click.echo(f"Parsing {source.name}...")
    parser = PlantUMLParser()

    try:
        parse_result = parser.parse_file(source)
    except Exception as e:
        click.secho(f"Error reading file: {e}", fg="red", err=True)
        sys.exit(2)

    # Report parse errors
    if parse_result.errors:
        click.secho("Parse errors:", fg="red", err=True)
        for error in parse_result.errors:
            click.echo(f"  Line {error.line_number}: {error.message}", err=True)
        sys.exit(2)

    # Report parse warnings
    if parse_result.warnings:
        click.secho("Parse warnings:", fg="yellow", err=True)
        for warning in parse_result.warnings:
            click.echo(f"  {warning}", err=True)

    model = parse_result.model
    click.echo(
        f"  Found: {len(model.classes)} classes, "
        f"{len(model.relationships)} relationships"
    )

    # Validate model
    model_validation = validate_puml(model)

    if model_validation.has_errors:
        click.secho("Model validation errors:", fg="red", err=True)
        for issue in model_validation.errors():
            click.echo(f"  {issue}", err=True)
        sys.exit(2)

    if model_validation.has_warnings:
        click.secho("Model validation warnings:", fg="yellow", err=True)
        for issue in model_validation.warnings():
            click.echo(f"  {issue}", err=True)
        if strict:
            click.secho("Aborting due to --strict mode", fg="red", err=True)
            sys.exit(1)

    # If validate-only mode, stop here
    if validate:
        if model_validation.has_warnings:
            click.secho(
                f"Validation complete: {model_validation.warning_count} warnings",
                fg="yellow",
            )
        else:
            click.secho("Validation complete: no issues found", fg="green")
        sys.exit(0)

    # Convert to RDF
    click.echo("Converting to RDF...")
    converter = PumlToRdfConverter(conversion_config)
    conversion_result = converter.convert(model)

    if conversion_result.warnings:
        click.secho("Conversion warnings:", fg="yellow", err=True)
        for warning in conversion_result.warnings:
            click.echo(f"  {warning}", err=True)

    graph = conversion_result.graph
    click.echo(f"  Generated: {len(graph)} triples")

    # Validate generated RDF
    rdf_validation = validate_rdf(graph)
    if rdf_validation.has_warnings:
        click.secho("RDF validation warnings:", fg="yellow", err=True)
        for issue in rdf_validation.warnings():
            click.echo(f"  {issue}", err=True)

    # Merge with existing if requested
    if merge:
        click.echo(f"Merging with {merge.name}...")
        try:
            merge_result = merge_with_existing(graph, merge)
            graph = merge_result.graph
            click.echo(
                f"  Added: {merge_result.added_count}, "
                f"Preserved: {merge_result.preserved_count}"
            )
            if merge_result.conflicts:
                click.secho("Merge conflicts:", fg="yellow", err=True)
                for conflict in merge_result.conflicts[:5]:  # Limit output
                    click.echo(f"  {conflict}", err=True)
                if len(merge_result.conflicts) > 5:
                    click.echo(
                        f"  ... and {len(merge_result.conflicts) - 5} more",
                        err=True,
                    )
        except Exception as e:
            click.secho(f"Error merging: {e}", fg="red", err=True)
            sys.exit(2)

    # Serialise output
    try:
        graph.serialize(str(output), format=rdf_format)
        click.secho(f"✓ Wrote {output}", fg="green")
        click.echo(
            f"  Classes: {len(conversion_result.class_uris)}, "
            f"Properties: {len(conversion_result.property_uris)}"
        )
    except Exception as e:
        click.secho(f"Error writing output: {e}", fg="red", err=True)
        sys.exit(2)


@cli.command("cq-test")
@click.argument("ontology", type=click.Path(exists=True, path_type=Path))
@click.argument("test_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--data",
    "-d",
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    help="Additional data file(s) to load alongside the ontology",
)
@click.option(
    "--tag",
    "-t",
    multiple=True,
    help="Only run tests with these tags (can specify multiple)",
)
@click.option(
    "--exclude-tag",
    "-x",
    multiple=True,
    help="Exclude tests with these tags (can specify multiple)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["text", "json", "junit"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Write output to file instead of stdout",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show verbose output (query text, timing details)",
)
@click.option(
    "--fail-fast",
    is_flag=True,
    help="Stop on first failure",
)
def cq_test(
    ontology: Path,
    test_file: Path,
    data: tuple[Path, ...],
    tag: tuple[str, ...],
    exclude_tag: tuple[str, ...],
    output_format: str,
    output: Path | None,
    verbose: bool,
    fail_fast: bool,
):
    """Run competency question tests against an ontology.

    Validates whether an ontology can answer competency questions expressed
    as SPARQL queries with expected results.

    ONTOLOGY: RDF file containing the ontology to test
    TEST_FILE: YAML file containing competency question tests

    \b
    Examples:
        # Run all tests
        rdf-construct cq-test ontology.ttl cq-tests.yml

        # Run with additional sample data
        rdf-construct cq-test ontology.ttl cq-tests.yml --data sample-data.ttl

        # Run only tests tagged 'core'
        rdf-construct cq-test ontology.ttl cq-tests.yml --tag core

        # Generate JUnit XML for CI
        rdf-construct cq-test ontology.ttl cq-tests.yml --format junit -o results.xml

        # Verbose output with timing
        rdf-construct cq-test ontology.ttl cq-tests.yml --verbose

    \b
    Exit codes:
        0 - All tests passed
        1 - One or more tests failed
        2 - Error occurred (invalid file, parse error, etc.)
    """
    try:
        # Load ontology
        click.echo(f"Loading ontology: {ontology.name}...", err=True)
        graph = Graph()
        graph.parse(str(ontology), format=_infer_format(ontology))

        # Load additional data files
        if data:
            for data_file in data:
                click.echo(f"Loading data: {data_file.name}...", err=True)
                graph.parse(str(data_file), format=_infer_format(data_file))

        # Load test suite
        click.echo(f"Loading tests: {test_file.name}...", err=True)
        suite = load_test_suite(test_file)

        # Filter by tags
        if tag or exclude_tag:
            include_tags = set(tag) if tag else None
            exclude_tags = set(exclude_tag) if exclude_tag else None
            suite = suite.filter_by_tags(include_tags, exclude_tags)

        if not suite.questions:
            click.secho("No tests to run (check tag filters)", fg="yellow", err=True)
            sys.exit(0)

        # Run tests
        click.echo(f"Running {len(suite.questions)} test(s)...", err=True)
        click.echo("", err=True)

        runner = CQTestRunner(fail_fast=fail_fast, verbose=verbose)
        results = runner.run(graph, suite, ontology_file=ontology)

        # Format output
        formatted = format_results(results, format_name=output_format, verbose=verbose)

        # Write output
        if output:
            output.write_text(formatted)
            click.secho(f"✓ Results written to {output}", fg="green", err=True)
        else:
            click.echo(formatted)

        # Exit code based on results
        if results.has_errors:
            sys.exit(2)
        elif results.has_failures:
            sys.exit(1)
        else:
            sys.exit(0)

    except FileNotFoundError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        sys.exit(2)
    except ValueError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        sys.exit(2)
    except Exception as e:
        click.secho(f"Error: {type(e).__name__}: {e}", fg="red", err=True)
        sys.exit(2)


def _infer_format(path: Path) -> str:
    """Infer RDF format from file extension."""
    suffix = path.suffix.lower()
    format_map = {
        ".ttl": "turtle",
        ".turtle": "turtle",
        ".rdf": "xml",
        ".xml": "xml",
        ".owl": "xml",
        ".nt": "nt",
        ".ntriples": "nt",
        ".n3": "n3",
        ".jsonld": "json-ld",
        ".json": "json-ld",
    }
    return format_map.get(suffix, "turtle")


@cli.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
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
    type=click.Choice(["text", "json", "markdown", "md"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--compare",
    is_flag=True,
    help="Compare two ontology files (requires exactly 2 files)",
)
@click.option(
    "--include",
    type=str,
    help="Include only these metric categories (comma-separated: basic,hierarchy,properties,documentation,complexity,connectivity)",
)
@click.option(
    "--exclude",
    type=str,
    help="Exclude these metric categories (comma-separated)",
)
def stats(
    files: tuple[Path, ...],
    output: Path | None,
    output_format: str,
    compare: bool,
    include: str | None,
    exclude: str | None,
):
    """Compute and display ontology statistics.

    Analyses one or more RDF ontology files and displays comprehensive metrics
    about structure, complexity, and documentation coverage.

    \b
    Examples:
        # Basic statistics
        rdf-construct stats ontology.ttl

        # JSON output for programmatic use
        rdf-construct stats ontology.ttl --format json -o stats.json

        # Markdown for documentation
        rdf-construct stats ontology.ttl --format markdown >> README.md

        # Compare two versions
        rdf-construct stats v1.ttl v2.ttl --compare

        # Only show specific categories
        rdf-construct stats ontology.ttl --include basic,documentation

        # Exclude some categories
        rdf-construct stats ontology.ttl --exclude connectivity,complexity

    \b
    Metric Categories:
        basic         - Counts (triples, classes, properties, individuals)
        hierarchy     - Structure (depth, branching, orphans)
        properties    - Coverage (domain, range, functional, symmetric)
        documentation - Labels and comments
        complexity    - Multiple inheritance, OWL axioms
        connectivity  - Most connected class, isolated classes

    \b
    Exit codes:
        0 - Success
        1 - Error occurred
    """
    try:
        # Validate file count for compare mode
        if compare:
            if len(files) != 2:
                click.secho(
                    "Error: --compare requires exactly 2 files",
                    fg="red",
                    err=True,
                )
                sys.exit(1)

        # Parse include/exclude categories
        include_set: set[str] | None = None
        exclude_set: set[str] | None = None

        if include:
            include_set = {cat.strip().lower() for cat in include.split(",")}
        if exclude:
            exclude_set = {cat.strip().lower() for cat in exclude.split(",")}

        # Load graphs
        graphs: list[tuple[Graph, Path]] = []
        for filepath in files:
            click.echo(f"Loading {filepath}...", err=True)
            graph = Graph()
            graph.parse(str(filepath), format="turtle")
            graphs.append((graph, filepath))
            click.echo(f"  Loaded {len(graph)} triples", err=True)

        if compare:
            # Comparison mode
            old_graph, old_path = graphs[0]
            new_graph, new_path = graphs[1]

            click.echo("Collecting statistics...", err=True)
            old_stats = collect_stats(
                old_graph,
                source=str(old_path),
                include=include_set,
                exclude=exclude_set,
            )
            new_stats = collect_stats(
                new_graph,
                source=str(new_path),
                include=include_set,
                exclude=exclude_set,
            )

            click.echo("Comparing versions...", err=True)
            comparison = compare_stats(old_stats, new_stats)

            # Format output
            formatted = format_comparison(
                comparison,
                format_name=output_format,
                graph=new_graph,
            )
        else:
            # Single file or multiple files (show stats for first)
            graph, filepath = graphs[0]

            click.echo("Collecting statistics...", err=True)
            ontology_stats = collect_stats(
                graph,
                source=str(filepath),
                include=include_set,
                exclude=exclude_set,
            )

            # Format output
            formatted = format_stats(
                ontology_stats,
                format_name=output_format,
                graph=graph,
            )

        # Write output
        if output:
            output.write_text(formatted)
            click.secho(f"✓ Wrote stats to {output}", fg="green", err=True)
        else:
            click.echo(formatted)

        sys.exit(0)

    except ValueError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
