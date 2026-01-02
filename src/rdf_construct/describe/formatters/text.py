"""Text formatter for ontology description output.

Produces human-readable terminal output with optional colour.
"""

from rdf_construct.describe.models import (
    OntologyDescription,
    OntologyProfile,
    NamespaceCategory,
    ImportStatus,
)


def format_text(
    description: OntologyDescription,
    use_colour: bool = True,
) -> str:
    """Format ontology description as terminal-friendly text.

    Args:
        description: OntologyDescription to format.
        use_colour: Whether to include ANSI colour codes.

    Returns:
        Formatted text string.
    """
    lines: list[str] = []

    # Header
    lines.append(_header("Ontology Description", use_colour))
    lines.append(f"Source: {description.source}")
    lines.append("")

    # Verdict (one-line summary)
    lines.append(_label("Verdict", use_colour) + description.verdict)
    lines.append("")

    # Metadata section
    lines.append(_section("Metadata", use_colour))
    meta = description.metadata

    if meta.ontology_iri:
        lines.append(f"  IRI: {meta.ontology_iri}")
    else:
        lines.append(f"  IRI: {_dim('(not declared)', use_colour)}")

    if meta.version_iri:
        lines.append(f"  Version IRI: {meta.version_iri}")
    if meta.version_info:
        lines.append(f"  Version: {meta.version_info}")

    if meta.title:
        lines.append(f"  Title: {meta.title}")
    if meta.description:
        # Truncate long descriptions
        desc = meta.description
        if len(desc) > 100:
            desc = desc[:97] + "..."
        lines.append(f"  Description: {desc}")

    if meta.license_uri or meta.license_label:
        license_str = meta.license_label or meta.license_uri
        lines.append(f"  License: {license_str}")

    if meta.creators:
        lines.append(f"  Creator(s): {', '.join(meta.creators)}")

    lines.append("")

    # Metrics section
    lines.append(_section("Metrics", use_colour))
    m = description.metrics
    lines.append(f"  Triples: {m.total_triples:,}")
    lines.append(f"  Classes: {m.classes}")

    # Property breakdown
    if m.total_properties > 0:
        lines.append(f"  Properties: {m.total_properties}")
        if m.object_properties:
            lines.append(f"    Object: {m.object_properties}")
        if m.datatype_properties:
            lines.append(f"    Datatype: {m.datatype_properties}")
        if m.annotation_properties:
            lines.append(f"    Annotation: {m.annotation_properties}")
        if m.rdf_properties:
            lines.append(f"    RDF: {m.rdf_properties}")

    lines.append(f"  Individuals: {m.individuals}")
    lines.append("")

    # Profile section
    lines.append(_section("Profile", use_colour))
    p = description.profile
    profile_colour = _profile_colour(p.profile, use_colour)
    lines.append(f"  Detected: {profile_colour}")
    lines.append(f"  {_dim('(' + p.reasoning_guidance + ')', use_colour)}")

    if p.owl_constructs_found:
        lines.append(f"  Constructs: {', '.join(p.owl_constructs_found[:5])}")
        if len(p.owl_constructs_found) > 5:
            lines.append(f"              ...and {len(p.owl_constructs_found) - 5} more")

    if p.violating_constructs:
        lines.append(f"  {_warn('DL Violations:', use_colour)} {', '.join(p.violating_constructs[:3])}")

    lines.append("")

    # Brief mode stops here
    if description.brief:
        return "\n".join(lines)

    # Namespace section
    lines.append(_section("Namespaces", use_colour))
    ns = description.namespaces

    if ns.local_namespace:
        lines.append(f"  Local: {ns.local_namespace}")

    lines.append(f"  Local: {ns.local_count}, Imported: {ns.imported_count}, External: {ns.external_count}")

    # Show top namespaces by usage
    top_ns = sorted(ns.namespaces, key=lambda x: -x.usage_count)[:5]
    for nsi in top_ns:
        prefix = f"{nsi.prefix}:" if nsi.prefix else ""
        cat_label = {
            NamespaceCategory.LOCAL: _green("[local]", use_colour),
            NamespaceCategory.IMPORTED: _cyan("[imported]", use_colour),
            NamespaceCategory.EXTERNAL: _dim("[external]", use_colour),
        }[nsi.category]
        lines.append(f"    {prefix} {nsi.uri} ({nsi.usage_count} uses) {cat_label}")

    if ns.unimported_external:
        lines.append("")
        lines.append(f"  {_warn('Unimported external:', use_colour)}")
        for uri in ns.unimported_external[:3]:
            lines.append(f"    - {uri}")
        if len(ns.unimported_external) > 3:
            lines.append(f"    ...and {len(ns.unimported_external) - 3} more")

    lines.append("")

    # Imports section
    lines.append(_section("Imports", use_colour))
    imp = description.imports

    if imp.count == 0:
        lines.append(f"  {_dim('No imports declared', use_colour)}")
    else:
        lines.append(f"  Declared: {imp.count} (direct imports only)")

        for imp_info in imp.imports:
            if imp_info.status == ImportStatus.RESOLVABLE:
                status = _green("✓", use_colour)
            elif imp_info.status == ImportStatus.UNRESOLVABLE:
                status = _red("✗", use_colour)
                if imp_info.error:
                    status += f" {_dim(imp_info.error, use_colour)}"
            else:
                status = _dim("?", use_colour)

            lines.append(f"    {status} {imp_info.uri}")

    lines.append("")

    # Hierarchy section
    lines.append(_section("Class Hierarchy", use_colour))
    h = description.hierarchy

    lines.append(f"  Root classes: {h.root_count}")
    if h.root_classes:
        roots_display = ", ".join(h.root_classes[:5])
        if len(h.root_classes) > 5:
            roots_display += f", ...and {len(h.root_classes) - 5} more"
        lines.append(f"    {roots_display}")

    lines.append(f"  Maximum depth: {h.max_depth}")
    lines.append(f"  Orphan classes: {h.orphan_count}")

    if h.has_cycles:
        lines.append(f"  {_warn('Cycles detected:', use_colour)} {', '.join(h.cycle_members[:3])}")

    lines.append("")

    # Documentation section
    lines.append(_section("Documentation Coverage", use_colour))
    d = description.documentation

    # Classes
    label_pct = d.class_label_pct
    def_pct = d.class_definition_pct
    label_bar = _progress_bar(label_pct, use_colour)
    def_bar = _progress_bar(def_pct, use_colour)

    lines.append(f"  Classes with labels:      {label_bar} {label_pct:.0f}% ({d.classes_with_label}/{d.classes_total})")
    lines.append(f"  Classes with definitions: {def_bar} {def_pct:.0f}% ({d.classes_with_definition}/{d.classes_total})")

    # Properties
    if d.properties_total > 0:
        prop_label_pct = d.property_label_pct
        prop_def_pct = d.property_definition_pct
        prop_label_bar = _progress_bar(prop_label_pct, use_colour)
        prop_def_bar = _progress_bar(prop_def_pct, use_colour)

        lines.append(f"  Properties with labels:      {prop_label_bar} {prop_label_pct:.0f}% ({d.properties_with_label}/{d.properties_total})")
        lines.append(f"  Properties with definitions: {prop_def_bar} {prop_def_pct:.0f}% ({d.properties_with_definition}/{d.properties_total})")

    lines.append("")

    # Reasoning section (if included)
    if description.reasoning is not None:
        lines.append(_section("Reasoning Analysis", use_colour))
        r = description.reasoning
        lines.append(f"  Entailment regime: {r.entailment_regime}")

        if r.consistency_notes:
            lines.append(f"  Notes:")
            for note in r.consistency_notes[:3]:
                lines.append(f"    - {note}")

        lines.append("")

    return "\n".join(lines)


def _header(text: str, use_colour: bool) -> str:
    """Format a main header."""
    if use_colour:
        return f"\033[1;36m{text}\033[0m"  # Bold cyan
    return f"=== {text} ==="


def _section(text: str, use_colour: bool) -> str:
    """Format a section header."""
    if use_colour:
        return f"\033[1m{text}\033[0m"  # Bold
    return f"--- {text} ---"


def _label(text: str, use_colour: bool) -> str:
    """Format a label."""
    if use_colour:
        return f"\033[1;33m{text}:\033[0m "  # Bold yellow
    return f"{text}: "


def _dim(text: str, use_colour: bool) -> str:
    """Format dim/grey text."""
    if use_colour:
        return f"\033[2m{text}\033[0m"  # Dim
    return text


def _green(text: str, use_colour: bool) -> str:
    """Format green text."""
    if use_colour:
        return f"\033[32m{text}\033[0m"
    return text


def _red(text: str, use_colour: bool) -> str:
    """Format red text."""
    if use_colour:
        return f"\033[31m{text}\033[0m"
    return text


def _cyan(text: str, use_colour: bool) -> str:
    """Format cyan text."""
    if use_colour:
        return f"\033[36m{text}\033[0m"
    return text


def _warn(text: str, use_colour: bool) -> str:
    """Format warning text (yellow)."""
    if use_colour:
        return f"\033[33m{text}\033[0m"
    return text


def _profile_colour(profile: OntologyProfile, use_colour: bool) -> str:
    """Get coloured profile name based on level."""
    name = profile.display_name

    if not use_colour:
        return name

    colour_map = {
        OntologyProfile.RDF: "\033[2m",  # Dim
        OntologyProfile.RDFS: "\033[36m",  # Cyan
        OntologyProfile.OWL_DL_SIMPLE: "\033[32m",  # Green
        OntologyProfile.OWL_DL_EXPRESSIVE: "\033[33m",  # Yellow
        OntologyProfile.OWL_FULL: "\033[31m",  # Red
    }

    colour = colour_map.get(profile, "")
    return f"{colour}{name}\033[0m"


def _progress_bar(percentage: float, use_colour: bool, width: int = 10) -> str:
    """Create a simple progress bar."""
    filled = int(percentage / 100 * width)
    empty = width - filled

    bar = "█" * filled + "░" * empty

    if use_colour:
        if percentage >= 80:
            return f"\033[32m{bar}\033[0m"  # Green
        elif percentage >= 50:
            return f"\033[33m{bar}\033[0m"  # Yellow
        else:
            return f"\033[31m{bar}\033[0m"  # Red

    return f"[{bar}]"
