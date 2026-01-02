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

from rdf_construct.merge import (
    MergeConfig,
    SourceConfig,
    OutputConfig,
    ConflictConfig,
    ConflictStrategy,
    ImportsStrategy,
    DataMigrationConfig,
    OntologyMerger,
    load_merge_config,
    create_default_config,
    get_formatter,
    migrate_data_files,
    # Split imports
    OntologySplitter,
    SplitConfig,
    SplitResult,
    ModuleDefinition,
    split_by_namespace,
    create_default_split_config,
)

from rdf_construct.refactor import (
    RenameConfig,
    DeprecationSpec,
    RefactorConfig,
    OntologyRenamer,
    OntologyDeprecator,
    TextFormatter as RefactorTextFormatter,
    load_refactor_config,
    create_default_rename_config,
    create_default_deprecation_config,
    rename_file,
    rename_files,
    deprecate_file,
)
from rdf_construct.merge import DataMigrator

from rdf_construct.localise import (
    StringExtractor,
    TranslationMerger,
    CoverageReporter,
    ExtractConfig,
    MergeConfig as LocaliseMergeConfig,
    TranslationFile,
    TranslationStatus,
    ExistingStrategy,
    create_default_config as create_default_localise_config,
    load_localise_config,
    get_formatter as get_localise_formatter,
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


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
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
    "--brief",
    is_flag=True,
    help="Show brief summary only (metadata, metrics, profile)",
)
@click.option(
    "--no-resolve",
    is_flag=True,
    help="Skip import resolution checks",
)
@click.option(
    "--reasoning",
    is_flag=True,
    help="Include reasoning analysis",
)
@click.option(
    "--no-colour",
    "--no-color",
    is_flag=True,
    help="Disable coloured output (text format only)",
)
def describe(
    file: Path,
    output: Path | None,
    output_format: str,
    brief: bool,
    no_resolve: bool,
    reasoning: bool,
    no_colour: bool,
):
    """Describe an ontology: profile, metrics, imports, and structure.

    Provides a comprehensive analysis of an RDF ontology file, including:
    - Profile detection (RDF, RDFS, OWL DL, OWL Full)
    - Basic metrics (classes, properties, individuals)
    - Import analysis with optional resolvability checking
    - Namespace categorisation
    - Class hierarchy analysis
    - Documentation coverage

    FILE: RDF ontology file to describe (.ttl, .rdf, .owl, etc.)

    \b
    Examples:
        # Basic description
        rdf-construct describe ontology.ttl

        # Brief summary only
        rdf-construct describe ontology.ttl --brief

        # JSON output for programmatic use
        rdf-construct describe ontology.ttl --format json -o description.json

        # Markdown for documentation
        rdf-construct describe ontology.ttl --format markdown -o DESCRIPTION.md

        # Skip slow import resolution
        rdf-construct describe ontology.ttl --no-resolve

    \b
    Exit codes:
        0 - Success
        1 - Success with warnings (unresolvable imports, etc.)
        2 - Error (file not found, parse error)
    """
    from rdf_construct.describe import describe_file, format_description

    try:
        click.echo(f"Analysing {file}...", err=True)

        # Perform analysis
        description = describe_file(
            file,
            brief=brief,
            resolve_imports=not no_resolve,
            include_reasoning=reasoning,
        )

        # Format output
        use_colour = not no_colour and output_format == "text" and output is None
        formatted = format_description(
            description,
            format_name=output_format,
            use_colour=use_colour,
        )

        # Write output
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(formatted)
            click.secho(f"✓ Wrote description to {output}", fg="green", err=True)
        else:
            click.echo(formatted)

        # Exit code based on warnings
        if description.imports and description.imports.unresolvable_count > 0:
            sys.exit(1)
        else:
            sys.exit(0)

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
@click.argument("sources", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    required=True,
    help="Output file for merged ontology",
)
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True, path_type=Path),
    help="YAML configuration file",
)
@click.option(
    "--priority",
    "-p",
    multiple=True,
    type=int,
    help="Priority for each source (order matches sources)",
)
@click.option(
    "--strategy",
    type=click.Choice(["priority", "first", "last", "mark_all"], case_sensitive=False),
    default="priority",
    help="Conflict resolution strategy (default: priority)",
)
@click.option(
    "--report",
    "-r",
    type=click.Path(path_type=Path),
    help="Write conflict report to file",
)
@click.option(
    "--report-format",
    type=click.Choice(["text", "markdown", "md"], case_sensitive=False),
    default="markdown",
    help="Format for conflict report (default: markdown)",
)
@click.option(
    "--imports",
    type=click.Choice(["preserve", "remove", "merge"], case_sensitive=False),
    default="preserve",
    help="How to handle owl:imports (default: preserve)",
)
@click.option(
    "--migrate-data",
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    help="Data file(s) to migrate",
)
@click.option(
    "--migration-rules",
    type=click.Path(exists=True, path_type=Path),
    help="YAML file with migration rules",
)
@click.option(
    "--data-output",
    type=click.Path(path_type=Path),
    help="Output path for migrated data",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would happen without writing files",
)
@click.option(
    "--no-colour",
    is_flag=True,
    help="Disable coloured output",
)
@click.option(
    "--init",
    "init_config",
    is_flag=True,
    help="Generate a default merge configuration file",
)
def merge(
    sources: tuple[Path, ...],
    output: Path,
    config_file: Path | None,
    priority: tuple[int, ...],
    strategy: str,
    report: Path | None,
    report_format: str,
    imports: str,
    migrate_data: tuple[Path, ...],
    migration_rules: Path | None,
    data_output: Path | None,
    dry_run: bool,
    no_colour: bool,
    init_config: bool,
):
    """Merge multiple RDF ontology files.

    Combines SOURCES into a single output ontology, detecting and handling
    conflicts between definitions.

    \b
    SOURCES: One or more RDF files to merge (.ttl, .rdf, .owl)

    \b
    Exit codes:
      0 - Merge successful, no unresolved conflicts
      1 - Merge successful, but unresolved conflicts marked in output
      2 - Error (file not found, parse error, etc.)

    \b
    Examples:
      # Basic merge of two files
      rdf-construct merge core.ttl ext.ttl -o merged.ttl

      # With priorities (higher wins conflicts)
      rdf-construct merge core.ttl ext.ttl -o merged.ttl -p 1 -p 2

      # Generate conflict report
      rdf-construct merge core.ttl ext.ttl -o merged.ttl --report conflicts.md

      # Mark all conflicts for manual review
      rdf-construct merge core.ttl ext.ttl -o merged.ttl --strategy mark_all

      # With data migration
      rdf-construct merge core.ttl ext.ttl -o merged.ttl \\
          --migrate-data split_instances.ttl --data-output migrated.ttl

      # Use configuration file
      rdf-construct merge --config merge.yml -o merged.ttl

      # Generate default config file
      rdf-construct merge --init
    """
    # Handle --init flag
    if init_config:
        config_path = Path("merge.yml")
        if config_path.exists():
            click.secho(f"Config file already exists: {config_path}", fg="red", err=True)
            raise click.Abort()

        config_content = create_default_config()
        config_path.write_text(config_content)
        click.secho(f"Created {config_path}", fg="green")
        click.echo("Edit this file to configure your merge, then run:")
        click.echo(f"  rdf-construct merge --config {config_path} -o merged.ttl")
        return

    # Validate we have sources
    if not sources and not config_file:
        click.secho("Error: No source files specified.", fg="red", err=True)
        click.echo("Provide source files or use --config with a configuration file.", err=True)
        raise click.Abort()

    # Build configuration
    if config_file:
        try:
            config = load_merge_config(config_file)
            click.echo(f"Using config: {config_file}")

            # Override output if provided on CLI
            if output:
                config.output = OutputConfig(path=output)
        except (FileNotFoundError, ValueError) as e:
            click.secho(f"Error loading config: {e}", fg="red", err=True)
            raise click.Abort()
    else:
        # Build config from CLI arguments
        priorities_list = list(priority) if priority else list(range(1, len(sources) + 1))

        # Pad priorities if needed
        while len(priorities_list) < len(sources):
            priorities_list.append(len(priorities_list) + 1)

        source_configs = [
            SourceConfig(path=p, priority=pri)
            for p, pri in zip(sources, priorities_list)
        ]

        conflict_strategy = ConflictStrategy[strategy.upper()]
        imports_strategy = ImportsStrategy[imports.upper()]

        # Data migration config
        data_migration = None
        if migrate_data:
            data_migration = DataMigrationConfig(
                data_sources=list(migrate_data),
                output_path=data_output,
            )

        config = MergeConfig(
            sources=source_configs,
            output=OutputConfig(path=output),
            conflicts=ConflictConfig(
                strategy=conflict_strategy,
                report_path=report,
            ),
            imports=imports_strategy,
            migrate_data=data_migration,
            dry_run=dry_run,
        )

    # Execute merge
    click.echo("Merging ontologies...")

    merger = OntologyMerger(config)
    result = merger.merge()

    if not result.success:
        click.secho(f"✗ Merge failed: {result.error}", fg="red", err=True)
        raise SystemExit(2)

    # Display results
    use_colour = not no_colour
    text_formatter = get_formatter("text", use_colour=use_colour)
    click.echo(text_formatter.format_merge_result(result, result.merged_graph))

    # Write output (unless dry run)
    if not dry_run and result.merged_graph and config.output:
        merger.write_output(result, config.output.path)
        click.echo()
        click.secho(f"✓ Wrote {config.output.path}", fg="green")

    # Generate conflict report if requested
    if report and result.conflicts:
        report_formatter = get_formatter(report_format)
        report_content = report_formatter.format_conflict_report(
            result.conflicts, result.merged_graph
        )
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(report_content)
        click.echo(f"  Conflict report: {report}")

    # Handle data migration
    if config.migrate_data and config.migrate_data.data_sources:
        click.echo()
        click.echo("Migrating data...")

        # Build URI map from any namespace remappings
        from rdf_construct.merge import DataMigrator

        migrator = DataMigrator()
        uri_map: dict[URIRef, URIRef] = {}

        # Collect namespace remaps from all sources
        for src in config.sources:
            if src.namespace_remap:
                for old_ns, new_ns in src.namespace_remap.items():
                    # We'd need to scan data files to build complete map
                    # For now, this is a placeholder
                    pass

        # Apply migration
        migration_result = migrate_data_files(
            data_paths=config.migrate_data.data_sources,
            uri_map=uri_map if uri_map else None,
            rules=config.migrate_data.rules if config.migrate_data.rules else None,
            output_path=config.migrate_data.output_path if not dry_run else None,
        )

        if migration_result.success:
            click.echo(text_formatter.format_migration_result(migration_result))
            if config.migrate_data.output_path and not dry_run:
                click.secho(
                    f"✓ Wrote migrated data to {config.migrate_data.output_path}",
                    fg="green",
                )
        else:
            click.secho(
                f"✗ Data migration failed: {migration_result.error}",
                fg="red",
                err=True,
            )

    # Exit code based on unresolved conflicts
    if result.unresolved_conflicts:
        click.echo()
        click.secho(
            f"⚠ {len(result.unresolved_conflicts)} unresolved conflict(s) "
            "marked in output",
            fg="yellow",
        )
        raise SystemExit(1)
    else:
        raise SystemExit(0)


@cli.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(path_type=Path),
    default=Path("modules"),
    help="Output directory for split modules (default: modules/)",
)
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True, path_type=Path),
    help="YAML configuration file for split",
)
@click.option(
    "--by-namespace",
    is_flag=True,
    help="Automatically split by namespace (auto-detect modules)",
)
@click.option(
    "--migrate-data",
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    help="Data file(s) to split by instance type",
)
@click.option(
    "--data-output",
    type=click.Path(path_type=Path),
    help="Output directory for split data files",
)
@click.option(
    "--unmatched",
    type=click.Choice(["common", "error"], case_sensitive=False),
    default="common",
    help="Strategy for unmatched entities (default: common)",
)
@click.option(
    "--common-name",
    default="common",
    help="Name for common module (default: common)",
)
@click.option(
    "--no-manifest",
    is_flag=True,
    help="Don't generate manifest.yml",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would happen without writing files",
)
@click.option(
    "--no-colour",
    is_flag=True,
    help="Disable coloured output",
)
@click.option(
    "--init",
    "init_config",
    is_flag=True,
    help="Generate a default split configuration file",
)
def split(
    source: Path,
    output_dir: Path,
    config_file: Path | None,
    by_namespace: bool,
    migrate_data: tuple[Path, ...],
    data_output: Path | None,
    unmatched: str,
    common_name: str,
    no_manifest: bool,
    dry_run: bool,
    no_colour: bool,
    init_config: bool,
):
    """Split a monolithic ontology into multiple modules.

    SOURCE: RDF ontology file to split (.ttl, .rdf, .owl)

    \b
    Exit codes:
      0 - Split successful
      1 - Split successful with unmatched entities in common module
      2 - Error (file not found, config invalid, etc.)

    \b
    Examples:
      # Split by namespace (auto-detect modules)
      rdf-construct split large.ttl -o modules/ --by-namespace

      # Split using configuration file
      rdf-construct split large.ttl -o modules/ -c split.yml

      # With data migration
      rdf-construct split large.ttl -o modules/ -c split.yml \\
          --migrate-data split_instances.ttl --data-output data/

      # Dry run - show what would be created
      rdf-construct split large.ttl -o modules/ --by-namespace --dry-run

      # Generate default config file
      rdf-construct split --init
    """
    # Handle --init flag
    if init_config:
        config_path = Path("split.yml")
        if config_path.exists():
            click.secho(f"Config file already exists: {config_path}", fg="red", err=True)
            raise click.Abort()

        config_content = create_default_split_config()
        config_path.write_text(config_content)
        click.secho(f"Created {config_path}", fg="green")
        click.echo("Edit this file to configure your split, then run:")
        click.echo(f"  rdf-construct split your-ontology.ttl -c {config_path}")
        return

    # Validate we have a source
    if not source:
        click.secho("Error: SOURCE is required.", fg="red", err=True)
        raise click.Abort()

    # Handle --by-namespace mode
    if by_namespace:
        click.echo(f"Splitting {source.name} by namespace...")

        result = split_by_namespace(source, output_dir, dry_run=dry_run)

        if not result.success:
            click.secho(f"✗ Split failed: {result.error}", fg="red", err=True)
            raise SystemExit(2)

        _display_split_result(result, output_dir, dry_run, not no_colour)
        raise SystemExit(0 if not result.unmatched_entities else 1)

    # Build configuration from file or CLI
    if config_file:
        try:
            config = SplitConfig.from_yaml(config_file)
            # Override source and output_dir if provided
            config.source = source
            config.output_dir = output_dir
            config.dry_run = dry_run
            config.generate_manifest = not no_manifest
            click.echo(f"Using config: {config_file}")
        except (FileNotFoundError, ValueError) as e:
            click.secho(f"Error loading config: {e}", fg="red", err=True)
            raise click.Abort()
    else:
        # Need either --by-namespace or --config
        if not by_namespace:
            click.secho(
                "Error: Specify either --by-namespace or --config.",
                fg="red",
                err=True,
            )
            click.echo("Use --by-namespace for auto-detection or -c for a config file.")
            click.echo("Run 'rdf-construct split --init' to generate a config template.")
            raise click.Abort()

        # Build minimal config
        config = SplitConfig(
            source=source,
            output_dir=output_dir,
            modules=[],
            unmatched=UnmatchedStrategy(
                strategy=unmatched,
                common_module=common_name,
                common_output=f"{common_name}.ttl",
            ),
            generate_manifest=not no_manifest,
            dry_run=dry_run,
        )

    # Add data migration config if specified
    if migrate_data:
        config.split_data = SplitDataConfig(
            sources=list(migrate_data),
            output_dir=data_output if data_output else output_dir,
            prefix="data_",
        )

    # Override unmatched strategy if specified on CLI
    if unmatched:
        config.unmatched = UnmatchedStrategy(
            strategy=unmatched,
            common_module=common_name,
            common_output=f"{common_name}.ttl",
        )

    # Execute split
    click.echo(f"Splitting {source.name}...")

    splitter = OntologySplitter(config)
    result = splitter.split()

    if not result.success:
        click.secho(f"✗ Split failed: {result.error}", fg="red", err=True)
        raise SystemExit(2)

    # Write output (unless dry run)
    if not dry_run:
        splitter.write_modules(result)
        if config.generate_manifest:
            splitter.write_manifest(result)

    _display_split_result(result, output_dir, dry_run, not no_colour)

    # Exit code based on unmatched entities
    if result.unmatched_entities and config.unmatched.strategy == "common":
        click.echo()
        click.secho(
            f"⚠ {len(result.unmatched_entities)} unmatched entities placed in "
            f"{config.unmatched.common_module} module",
            fg="yellow",
        )
        raise SystemExit(1)
    else:
        raise SystemExit(0)


def _display_split_result(
    result: "SplitResult",
    output_dir: Path,
    dry_run: bool,
    use_colour: bool,
) -> None:
    """Display split results to console.

    Args:
        result: SplitResult from split operation.
        output_dir: Output directory.
        dry_run: Whether this was a dry run.
        use_colour: Whether to use coloured output.
    """
    # Header
    if dry_run:
        click.echo("\n[DRY RUN] Would create:")
    else:
        click.echo("\nSplit complete:")

    # Module summary
    click.echo(f"\n  Modules: {result.total_modules}")
    click.echo(f"  Total triples: {result.total_triples}")

    # Module details
    if result.module_stats:
        click.echo("\n  Module breakdown:")
        for stats in result.module_stats:
            deps_str = ""
            if stats.dependencies:
                deps_str = f" (deps: {', '.join(stats.dependencies)})"
            click.echo(
                f"    {stats.file}: {stats.classes} classes, "
                f"{stats.properties} properties, {stats.triples} triples{deps_str}"
            )

    # Unmatched entities
    if result.unmatched_entities:
        click.echo(f"\n  Unmatched entities: {len(result.unmatched_entities)}")
        # Show first few
        sample = list(result.unmatched_entities)[:5]
        for uri in sample:
            click.echo(f"    - {uri}")
        if len(result.unmatched_entities) > 5:
            click.echo(f"    ... and {len(result.unmatched_entities) - 5} more")

    # Output location
    if not dry_run:
        click.echo()
        if use_colour:
            click.secho(f"✓ Wrote modules to {output_dir}/", fg="green")
        else:
            click.echo(f"✓ Wrote modules to {output_dir}/")


# Refactor command group
@cli.group()
def refactor():
    """Refactor ontologies: rename URIs and deprecate entities.

    \b
    Subcommands:
      rename     Rename URIs (single entity or bulk namespace)
      deprecate  Mark entities as deprecated

    \b
    Examples:
      # Fix a typo
      rdf-construct refactor rename ont.ttl --from ex:Buiding --to ex:Building -o fixed.ttl

      # Bulk namespace change
      rdf-construct refactor rename ont.ttl \\
          --from-namespace http://old/ --to-namespace http://new/ -o migrated.ttl

      # Deprecate entity with replacement
      rdf-construct refactor deprecate ont.ttl \\
          --entity ex:OldClass --replaced-by ex:NewClass \\
          --message "Use NewClass instead." -o updated.ttl
    """
    pass


@refactor.command("rename")
@click.argument("sources", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o", "--output",
    type=click.Path(path_type=Path),
    help="Output file (for single source) or directory (for multiple sources).",
)
@click.option(
    "--from", "from_uri",
    help="Single URI to rename (use with --to).",
)
@click.option(
    "--to", "to_uri",
    help="New URI for single rename (use with --from).",
)
@click.option(
    "--from-namespace",
    help="Old namespace prefix for bulk rename.",
)
@click.option(
    "--to-namespace",
    help="New namespace prefix for bulk rename.",
)
@click.option(
    "-c", "--config",
    "config_file",
    type=click.Path(exists=True, path_type=Path),
    help="YAML configuration file with rename mappings.",
)
@click.option(
    "--migrate-data",
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    help="Data files to migrate (can be repeated).",
)
@click.option(
    "--data-output",
    type=click.Path(path_type=Path),
    help="Output path for migrated data.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without writing files.",
)
@click.option(
    "--no-colour", "--no-color",
    is_flag=True,
    help="Disable coloured output.",
)
@click.option(
    "--init",
    "init_config",
    is_flag=True,
    help="Generate a template rename configuration file.",
)
def refactor_rename(
    sources: tuple[Path, ...],
    output: Path | None,
    from_uri: str | None,
    to_uri: str | None,
    from_namespace: str | None,
    to_namespace: str | None,
    config_file: Path | None,
    migrate_data: tuple[Path, ...],
    data_output: Path | None,
    dry_run: bool,
    no_colour: bool,
    init_config: bool,
):
    """Rename URIs in ontology files.

    Supports single entity renames (fixing typos) and bulk namespace changes
    (project migrations). The renamer updates subject, predicate, and object
    positions but intentionally leaves literal values unchanged.

    \b
    SOURCES: One or more RDF files to process (.ttl, .rdf, .owl)

    \b
    Exit codes:
      0 - Success
      1 - Success with warnings (some URIs not found)
      2 - Error (file not found, parse error, etc.)

    \b
    Examples:
      # Fix a single typo
      rdf-construct refactor rename ontology.ttl \\
          --from "http://example.org/ont#Buiding" \\
          --to "http://example.org/ont#Building" \\
          -o fixed.ttl

      # Bulk namespace change
      rdf-construct refactor rename ontology.ttl \\
          --from-namespace "http://old.example.org/" \\
          --to-namespace "http://new.example.org/" \\
          -o migrated.ttl

      # With data migration
      rdf-construct refactor rename ontology.ttl \\
          --from "ex:OldClass" --to "ex:NewClass" \\
          --migrate-data instances.ttl \\
          --data-output updated-instances.ttl

      # From configuration file
      rdf-construct refactor rename --config renames.yml

      # Preview changes (dry run)
      rdf-construct refactor rename ontology.ttl \\
          --from "ex:Old" --to "ex:New" --dry-run

      # Process multiple files
      rdf-construct refactor rename modules/*.ttl \\
          --from-namespace "http://old/" --to-namespace "http://new/" \\
          -o migrated/

      # Generate template config
      rdf-construct refactor rename --init
    """
    # Handle --init flag
    if init_config:
        config_path = Path("refactor_rename.yml")
        if config_path.exists():
            click.secho(f"Config file already exists: {config_path}", fg="red", err=True)
            raise click.Abort()

        config_content = create_default_rename_config()
        config_path.write_text(config_content)
        click.secho(f"Created {config_path}", fg="green")
        click.echo("Edit this file to configure your renames, then run:")
        click.echo(f"  rdf-construct refactor rename --config {config_path}")
        return

    # Validate input options
    if not sources and not config_file:
        click.secho("Error: No source files specified.", fg="red", err=True)
        click.echo("Provide source files or use --config with a configuration file.", err=True)
        raise click.Abort()

    # Validate rename options
    if from_uri and not to_uri:
        click.secho("Error: --from requires --to", fg="red", err=True)
        raise click.Abort()
    if to_uri and not from_uri:
        click.secho("Error: --to requires --from", fg="red", err=True)
        raise click.Abort()
    if from_namespace and not to_namespace:
        click.secho("Error: --from-namespace requires --to-namespace", fg="red", err=True)
        raise click.Abort()
    if to_namespace and not from_namespace:
        click.secho("Error: --to-namespace requires --from-namespace", fg="red", err=True)
        raise click.Abort()

    # Build configuration
    if config_file:
        try:
            config = load_refactor_config(config_file)
            click.echo(f"Using config: {config_file}")

            # Override output if provided on CLI
            if output:
                if len(sources) > 1 or (config.source_files and len(config.source_files) > 1):
                    config.output_dir = output
                else:
                    config.output = output

            # Override sources if provided on CLI
            if sources:
                config.source_files = list(sources)
        except (FileNotFoundError, ValueError) as e:
            click.secho(f"Error loading config: {e}", fg="red", err=True)
            raise click.Abort()
    else:
        # Build config from CLI arguments
        rename_config = RenameConfig()

        if from_namespace and to_namespace:
            rename_config.namespaces[from_namespace] = to_namespace

        if from_uri and to_uri:
            # Expand CURIEs if needed
            rename_config.entities[from_uri] = to_uri

        config = RefactorConfig(
            rename=rename_config,
            source_files=list(sources),
            output=output if len(sources) == 1 else None,
            output_dir=output if len(sources) > 1 else None,
            dry_run=dry_run,
        )

    # Validate we have something to rename
    if config.rename is None or (not config.rename.namespaces and not config.rename.entities):
        click.secho(
            "Error: No renames specified. Use --from/--to, --from-namespace/--to-namespace, "
            "or provide a config file.",
            fg="red",
            err=True,
        )
        raise click.Abort()

    # Execute rename
    formatter = RefactorTextFormatter(use_colour=not no_colour)
    renamer = OntologyRenamer()

    for source_path in config.source_files:
        click.echo(f"\nProcessing: {source_path}")

        # Load source graph
        graph = Graph()
        try:
            graph.parse(source_path.as_posix())
        except Exception as e:
            click.secho(f"✗ Failed to parse: {e}", fg="red", err=True)
            raise SystemExit(2)

        # Build mappings for preview
        mappings = config.rename.build_mappings(graph)

        if dry_run:
            # Show preview
            click.echo()
            click.echo(
                formatter.format_rename_preview(
                    mappings=mappings,
                    source_file=source_path.name,
                    source_triples=len(graph),
                )
            )
        else:
            # Perform rename
            result = renamer.rename(graph, config.rename)

            if not result.success:
                click.secho(f"✗ Rename failed: {result.error}", fg="red", err=True)
                raise SystemExit(2)

            # Show result
            click.echo(formatter.format_rename_result(result))

            # Write output
            if result.renamed_graph:
                out_path = config.output or (config.output_dir / source_path.name if config.output_dir else None)
                if out_path:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    result.renamed_graph.serialize(destination=out_path.as_posix(), format="turtle")
                    click.secho(f"✓ Wrote {out_path}", fg="green")

    # Handle data migration
    if migrate_data and not dry_run:
        click.echo("\nMigrating data...")

        # Build URI map from rename config
        combined_graph = Graph()
        for source_path in config.source_files:
            combined_graph.parse(source_path.as_posix())

        uri_map = {}
        for mapping in config.rename.build_mappings(combined_graph):
            uri_map[mapping.from_uri] = mapping.to_uri

        if uri_map:
            migrator = DataMigrator()
            for data_path in migrate_data:
                data_graph = Graph()
                try:
                    data_graph.parse(data_path.as_posix())
                except Exception as e:
                    click.secho(f"✗ Failed to parse data file {data_path}: {e}", fg="red", err=True)
                    continue

                migration_result = migrator.migrate(data_graph, uri_map=uri_map)

                if migration_result.success and migration_result.migrated_graph:
                    # Determine output path
                    if data_output and len(migrate_data) == 1:
                        out_path = data_output
                    elif data_output:
                        out_path = data_output / data_path.name
                    else:
                        out_path = data_path.parent / f"migrated_{data_path.name}"

                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    migration_result.migrated_graph.serialize(
                        destination=out_path.as_posix(), format="turtle"
                    )
                    click.echo(f"  Migrated {data_path.name}: {migration_result.stats.total_changes} changes")
                    click.secho(f"  ✓ Wrote {out_path}", fg="green")

    raise SystemExit(0)


@refactor.command("deprecate")
@click.argument("sources", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o", "--output",
    type=click.Path(path_type=Path),
    help="Output file.",
)
@click.option(
    "--entity",
    help="URI of entity to deprecate.",
)
@click.option(
    "--replaced-by",
    help="URI of replacement entity (adds dcterms:isReplacedBy).",
)
@click.option(
    "--message", "-m",
    help="Deprecation message (added to rdfs:comment).",
)
@click.option(
    "--version",
    help="Version when deprecated (included in message).",
)
@click.option(
    "-c", "--config",
    "config_file",
    type=click.Path(exists=True, path_type=Path),
    help="YAML configuration file with deprecation specs.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without writing files.",
)
@click.option(
    "--no-colour", "--no-color",
    is_flag=True,
    help="Disable coloured output.",
)
@click.option(
    "--init",
    "init_config",
    is_flag=True,
    help="Generate a template deprecation configuration file.",
)
def refactor_deprecate(
    sources: tuple[Path, ...],
    output: Path | None,
    entity: str | None,
    replaced_by: str | None,
    message: str | None,
    version: str | None,
    config_file: Path | None,
    dry_run: bool,
    no_colour: bool,
    init_config: bool,
):
    """Mark ontology entities as deprecated.

    Adds standard deprecation annotations:
    - owl:deprecated true
    - dcterms:isReplacedBy (if replacement specified)
    - rdfs:comment with "DEPRECATED: ..." message

    Deprecation marks entities but does NOT rename or migrate references.
    Use 'refactor rename' to actually migrate references after deprecation.

    \b
    SOURCES: One or more RDF files to process (.ttl, .rdf, .owl)

    \b
    Exit codes:
      0 - Success
      1 - Success with warnings (some entities not found)
      2 - Error (file not found, parse error, etc.)

    \b
    Examples:
      # Deprecate with replacement
      rdf-construct refactor deprecate ontology.ttl \\
          --entity "http://example.org/ont#LegacyTerm" \\
          --replaced-by "http://example.org/ont#NewTerm" \\
          --message "Use NewTerm instead. Will be removed in v3.0." \\
          -o updated.ttl

      # Deprecate without replacement
      rdf-construct refactor deprecate ontology.ttl \\
          --entity "ex:ObsoleteThing" \\
          --message "No longer needed. Will be removed in v3.0." \\
          -o updated.ttl

      # Bulk deprecation from config
      rdf-construct refactor deprecate ontology.ttl \\
          -c deprecations.yml \\
          -o updated.ttl

      # Preview changes (dry run)
      rdf-construct refactor deprecate ontology.ttl \\
          --entity "ex:Legacy" --replaced-by "ex:Modern" --dry-run

      # Generate template config
      rdf-construct refactor deprecate --init
    """
    # Handle --init flag
    if init_config:
        config_path = Path("refactor_deprecate.yml")
        if config_path.exists():
            click.secho(f"Config file already exists: {config_path}", fg="red", err=True)
            raise click.Abort()

        config_content = create_default_deprecation_config()
        config_path.write_text(config_content)
        click.secho(f"Created {config_path}", fg="green")
        click.echo("Edit this file to configure your deprecations, then run:")
        click.echo(f"  rdf-construct refactor deprecate --config {config_path}")
        return

    # Validate input options
    if not sources and not config_file:
        click.secho("Error: No source files specified.", fg="red", err=True)
        click.echo("Provide source files or use --config with a configuration file.", err=True)
        raise click.Abort()

    # Build configuration
    if config_file:
        try:
            config = load_refactor_config(config_file)
            click.echo(f"Using config: {config_file}")

            # Override output if provided on CLI
            if output:
                config.output = output

            # Override sources if provided on CLI
            if sources:
                config.source_files = list(sources)
        except (FileNotFoundError, ValueError) as e:
            click.secho(f"Error loading config: {e}", fg="red", err=True)
            raise click.Abort()
    else:
        # Build config from CLI arguments
        if not entity:
            click.secho(
                "Error: --entity is required when not using a config file.",
                fg="red",
                err=True,
            )
            raise click.Abort()

        spec = DeprecationSpec(
            entity=entity,
            replaced_by=replaced_by,
            message=message,
            version=version,
        )

        config = RefactorConfig(
            deprecations=[spec],
            source_files=list(sources),
            output=output,
            dry_run=dry_run,
        )

    # Validate we have something to deprecate
    if not config.deprecations:
        click.secho(
            "Error: No deprecations specified. Use --entity or provide a config file.",
            fg="red",
            err=True,
        )
        raise click.Abort()

    # Execute deprecation
    formatter = RefactorTextFormatter(use_colour=not no_colour)
    deprecator = OntologyDeprecator()

    for source_path in config.source_files:
        click.echo(f"\nProcessing: {source_path}")

        # Load source graph
        graph = Graph()
        try:
            graph.parse(source_path.as_posix())
        except Exception as e:
            click.secho(f"✗ Failed to parse: {e}", fg="red", err=True)
            raise SystemExit(2)

        if dry_run:
            # Perform dry run to get entity info
            temp_graph = Graph()
            for triple in graph:
                temp_graph.add(triple)

            result = deprecator.deprecate_bulk(temp_graph, config.deprecations)

            # Show preview
            click.echo()
            click.echo(
                formatter.format_deprecation_preview(
                    specs=config.deprecations,
                    entity_info=result.entity_info,
                    source_file=source_path.name,
                    source_triples=len(graph),
                )
            )
        else:
            # Perform deprecation
            result = deprecator.deprecate_bulk(graph, config.deprecations)

            if not result.success:
                click.secho(f"✗ Deprecation failed: {result.error}", fg="red", err=True)
                raise SystemExit(2)

            # Show result
            click.echo(formatter.format_deprecation_result(result))

            # Write output
            if result.deprecated_graph:
                out_path = config.output or source_path.with_stem(f"{source_path.stem}_deprecated")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                result.deprecated_graph.serialize(destination=out_path.as_posix(), format="turtle")
                click.secho(f"✓ Wrote {out_path}", fg="green")

            # Warn about entities not found
            if result.stats.entities_not_found > 0:
                click.secho(
                    f"\n⚠ {result.stats.entities_not_found} entity/entities not found in graph",
                    fg="yellow",
                )
                raise SystemExit(1)

    raise SystemExit(0)


@cli.group()
def localise():
    """Multi-language translation management.

    Extract translatable strings, merge translations, and track coverage.

    \b
    Commands:
      extract   Extract strings for translation
      merge     Merge translations back into ontology
      report    Generate translation coverage report
      init      Create empty translation file for new language

    \b
    Examples:
      # Extract strings for German translation
      rdf-construct localise extract ontology.ttl --language de -o translations/de.yml

      # Merge completed translations
      rdf-construct localise merge ontology.ttl translations/de.yml -o localised.ttl

      # Check translation coverage
      rdf-construct localise report ontology.ttl --languages en,de,fr
    """
    pass


@localise.command("extract")
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--language",
    "-l",
    "target_language",
    required=True,
    help="Target language code (e.g., de, fr, es)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output YAML file (default: {language}.yml)",
)
@click.option(
    "--source-language",
    default="en",
    help="Source language code (default: en)",
)
@click.option(
    "--properties",
    "-p",
    help="Comma-separated properties to extract (e.g., rdfs:label,rdfs:comment)",
)
@click.option(
    "--include-deprecated",
    is_flag=True,
    help="Include deprecated entities",
)
@click.option(
    "--missing-only",
    is_flag=True,
    help="Only extract strings missing in target language",
)
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True, path_type=Path),
    help="YAML configuration file",
)
def localise_extract(
    source: Path,
    target_language: str,
    output: Path | None,
    source_language: str,
    properties: str | None,
    include_deprecated: bool,
    missing_only: bool,
    config_file: Path | None,
):
    """Extract translatable strings from an ontology.

    Generates a YAML file with source text and empty translation fields,
    ready to be filled in by translators.

    \b
    Examples:
      # Basic extraction
      rdf-construct localise extract ontology.ttl --language de -o de.yml

      # Extract only labels
      rdf-construct localise extract ontology.ttl -l de -p rdfs:label

      # Extract missing strings only (for updates)
      rdf-construct localise extract ontology.ttl -l de --missing-only -o de_update.yml
    """
    from rdflib import Graph
    from rdf_construct.localise import (
        StringExtractor,
        ExtractConfig,
        get_formatter as get_localise_formatter,
    )

    # Load config if provided
    if config_file:
        from rdf_construct.localise import load_localise_config
        config = load_localise_config(config_file)
        extract_config = config.extract
        extract_config.target_language = target_language
    else:
        # Build config from CLI args
        prop_list = None
        if properties:
            prop_list = [_expand_localise_property(p.strip()) for p in properties.split(",")]

        extract_config = ExtractConfig(
            source_language=source_language,
            target_language=target_language,
            properties=prop_list or ExtractConfig().properties,
            include_deprecated=include_deprecated,
            missing_only=missing_only,
        )

    # Load graph
    click.echo(f"Loading {source}...")
    graph = Graph()
    graph.parse(source)

    # Extract
    click.echo(f"Extracting strings for {target_language}...")
    extractor = StringExtractor(extract_config)
    result = extractor.extract(graph, source, target_language)

    # Display result
    formatter = get_localise_formatter("text")
    click.echo(formatter.format_extraction_result(result))

    if not result.success:
        raise SystemExit(2)

    # Save output
    output_path = output or Path(f"{target_language}.yml")
    if result.translation_file:
        result.translation_file.save(output_path)
        click.echo()
        click.secho(f"✓ Wrote {output_path}", fg="green")

    raise SystemExit(0)


@localise.command("merge")
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.argument("translations", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    required=True,
    help="Output file for merged ontology",
)
@click.option(
    "--status",
    type=click.Choice(["pending", "needs_review", "translated", "approved"], case_sensitive=False),
    default="translated",
    help="Minimum status to include (default: translated)",
)
@click.option(
    "--existing",
    type=click.Choice(["preserve", "overwrite"], case_sensitive=False),
    default="preserve",
    help="How to handle existing translations (default: preserve)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would happen without writing files",
)
@click.option(
    "--no-colour",
    is_flag=True,
    help="Disable coloured output",
)
def localise_merge(
    source: Path,
    translations: tuple[Path, ...],
    output: Path,
    status: str,
    existing: str,
    dry_run: bool,
    no_colour: bool,
):
    """Merge translation files back into an ontology.

    Takes completed YAML translation files and adds the translations
    as new language-tagged literals to the ontology.

    \b
    Examples:
      # Merge single translation file
      rdf-construct localise merge ontology.ttl de.yml -o localised.ttl

      # Merge multiple languages
      rdf-construct localise merge ontology.ttl translations/*.yml -o multilingual.ttl

      # Merge only approved translations
      rdf-construct localise merge ontology.ttl de.yml --status approved -o localised.ttl
    """
    from rdflib import Graph
    from rdf_construct.localise import (
        TranslationMerger,
        TranslationFile,
        MergeConfig as LocaliseMergeConfig,
        TranslationStatus,
        ExistingStrategy,
        get_formatter as get_localise_formatter,
    )

    # Load graph
    click.echo(f"Loading {source}...")
    graph = Graph()
    graph.parse(source)

    # Load translation files
    click.echo(f"Loading {len(translations)} translation file(s)...")
    trans_files = [TranslationFile.from_yaml(p) for p in translations]

    # Build config
    config = LocaliseMergeConfig(
        min_status=TranslationStatus(status),
        existing=ExistingStrategy(existing),
    )

    # Merge
    click.echo("Merging translations...")
    merger = TranslationMerger(config)
    result = merger.merge_multiple(graph, trans_files)

    # Display result
    formatter = get_localise_formatter("text", use_colour=not no_colour)
    click.echo(formatter.format_merge_result(result))

    if not result.success:
        raise SystemExit(2)

    # Save output (unless dry run)
    if not dry_run and result.merged_graph:
        output.parent.mkdir(parents=True, exist_ok=True)
        result.merged_graph.serialize(destination=output, format="turtle")
        click.echo()
        click.secho(f"✓ Wrote {output}", fg="green")

    # Exit code based on warnings
    if result.stats.errors > 0:
        raise SystemExit(1)
    else:
        raise SystemExit(0)


@localise.command("report")
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--languages",
    "-l",
    required=True,
    help="Comma-separated language codes to check (e.g., en,de,fr)",
)
@click.option(
    "--source-language",
    default="en",
    help="Base language for translations (default: en)",
)
@click.option(
    "--properties",
    "-p",
    help="Comma-separated properties to check",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file for report",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["text", "markdown", "md"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed missing translation list",
)
@click.option(
    "--no-colour",
    is_flag=True,
    help="Disable coloured output",
)
def localise_report(
    source: Path,
    languages: str,
    source_language: str,
    properties: str | None,
    output: Path | None,
    output_format: str,
    verbose: bool,
    no_colour: bool,
):
    """Generate translation coverage report.

    Analyses an ontology and reports what percentage of translatable
    content has been translated into each target language.

    \b
    Examples:
      # Basic coverage report
      rdf-construct localise report ontology.ttl --languages en,de,fr

      # Detailed report with missing entities
      rdf-construct localise report ontology.ttl -l en,de,fr --verbose

      # Markdown report to file
      rdf-construct localise report ontology.ttl -l en,de,fr -f markdown -o coverage.md
    """
    from rdflib import Graph
    from rdf_construct.localise import (
        CoverageReporter,
        get_formatter as get_localise_formatter,
    )

    # Parse languages
    lang_list = [lang.strip() for lang in languages.split(",")]

    # Parse properties
    prop_list = None
    if properties:
        prop_list = [_expand_localise_property(p.strip()) for p in properties.split(",")]

    # Load graph
    click.echo(f"Loading {source}...")
    graph = Graph()
    graph.parse(source)

    # Generate report
    click.echo("Analysing translation coverage...")
    reporter = CoverageReporter(
        source_language=source_language,
        properties=prop_list,
    )
    report = reporter.report(graph, lang_list, source)

    # Format output
    formatter = get_localise_formatter(output_format, use_colour=not no_colour)
    report_text = formatter.format_coverage_report(report, verbose=verbose)

    # Output
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report_text)
        click.secho(f"✓ Wrote {output}", fg="green")
    else:
        click.echo()
        click.echo(report_text)

    raise SystemExit(0)


@localise.command("init")
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--language",
    "-l",
    "target_language",
    required=True,
    help="Target language code (e.g., de, fr, es)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output YAML file (default: {language}.yml)",
)
@click.option(
    "--source-language",
    default="en",
    help="Source language code (default: en)",
)
def localise_init(
    source: Path,
    target_language: str,
    output: Path | None,
    source_language: str,
):
    """Create empty translation file for a new language.

    Equivalent to 'extract' but explicitly for starting a new language.

    \b
    Examples:
      rdf-construct localise init ontology.ttl --language ja -o translations/ja.yml
    """
    from rdflib import Graph
    from rdf_construct.localise import (
        StringExtractor,
        ExtractConfig,
        get_formatter as get_localise_formatter,
    )

    # Build config
    extract_config = ExtractConfig(
        source_language=source_language,
        target_language=target_language,
    )

    # Load graph
    click.echo(f"Loading {source}...")
    graph = Graph()
    graph.parse(source)

    # Extract
    click.echo(f"Initialising translation file for {target_language}...")
    extractor = StringExtractor(extract_config)
    result = extractor.extract(graph, source, target_language)

    # Display result
    formatter = get_localise_formatter("text")
    click.echo(formatter.format_extraction_result(result))

    if not result.success:
        raise SystemExit(2)

    # Save output
    output_path = output or Path(f"{target_language}.yml")
    if result.translation_file:
        result.translation_file.save(output_path)
        click.echo()
        click.secho(f"✓ Created {output_path}", fg="green")
        click.echo(f"  Fill in translations and run:")
        click.echo(f"    rdf-construct localise merge {source} {output_path} -o localised.ttl")

    raise SystemExit(0)


@localise.command("config")
@click.option(
    "--init",
    "init_config",
    is_flag=True,
    help="Generate a default localise configuration file",
)
def localise_config(init_config: bool):
    """Generate or validate localise configuration.

    \b
    Examples:
      rdf-construct localise config --init
    """
    from rdf_construct.localise import create_default_config as create_default_localise_config

    if init_config:
        config_path = Path("localise.yml")
        if config_path.exists():
            click.secho(f"Config file already exists: {config_path}", fg="red", err=True)
            raise click.Abort()

        config_content = create_default_localise_config()
        config_path.write_text(config_content)
        click.secho(f"Created {config_path}", fg="green")
        click.echo("Edit this file to configure your localisation workflow.")
    else:
        click.echo("Use --init to create a default configuration file.")

    raise SystemExit(0)


def _expand_localise_property(prop: str) -> str:
    """Expand a CURIE to full URI for localise commands."""
    prefixes = {
        "rdfs:": "http://www.w3.org/2000/01/rdf-schema#",
        "skos:": "http://www.w3.org/2004/02/skos/core#",
        "owl:": "http://www.w3.org/2002/07/owl#",
        "rdf:": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "dc:": "http://purl.org/dc/elements/1.1/",
        "dcterms:": "http://purl.org/dc/terms/",
    }

    for prefix, namespace in prefixes.items():
        if prop.startswith(prefix):
            return namespace + prop[len(prefix):]

    return prop


if __name__ == "__main__":
    cli()
