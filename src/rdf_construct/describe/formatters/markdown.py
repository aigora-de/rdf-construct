"""Markdown formatter for ontology description output.

Produces GitHub/GitLab compatible Markdown for documentation.
"""

from rdf_construct.describe.models import (
    OntologyDescription,
    OntologyProfile,
    NamespaceCategory,
    ImportStatus,
)


def format_markdown(description: OntologyDescription) -> str:
    """Format ontology description as Markdown.

    Args:
        description: OntologyDescription to format.

    Returns:
        Markdown string.
    """
    lines: list[str] = []

    # Header
    meta = description.metadata
    title = meta.title or "Ontology Description"
    lines.append(f"# {title}")
    lines.append("")

    # Summary box
    lines.append("> **Verdict:** " + description.verdict)
    lines.append("")

    # Metadata section
    lines.append("## Metadata")
    lines.append("")

    lines.append("| Property | Value |")
    lines.append("|----------|-------|")

    if meta.ontology_iri:
        lines.append(f"| IRI | `{meta.ontology_iri}` |")
    else:
        lines.append("| IRI | *(not declared)* |")

    if meta.version_iri:
        lines.append(f"| Version IRI | `{meta.version_iri}` |")
    if meta.version_info:
        lines.append(f"| Version | {meta.version_info} |")
    if meta.license_uri or meta.license_label:
        license_str = meta.license_label or f"`{meta.license_uri}`"
        lines.append(f"| License | {license_str} |")
    if meta.creators:
        lines.append(f"| Creator(s) | {', '.join(meta.creators)} |")

    lines.append("")

    if meta.description:
        lines.append(f"**Description:** {meta.description}")
        lines.append("")

    # Metrics section
    lines.append("## Metrics")
    lines.append("")

    m = description.metrics
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Triples | {m.total_triples:,} |")
    lines.append(f"| Classes | {m.classes} |")
    lines.append(f"| Properties | {m.total_properties} |")

    if m.total_properties > 0:
        parts = []
        if m.object_properties:
            parts.append(f"{m.object_properties} object")
        if m.datatype_properties:
            parts.append(f"{m.datatype_properties} datatype")
        if m.annotation_properties:
            parts.append(f"{m.annotation_properties} annotation")
        if m.rdf_properties:
            parts.append(f"{m.rdf_properties} rdf")
        lines.append(f"| ↳ Breakdown | {', '.join(parts)} |")

    lines.append(f"| Individuals | {m.individuals} |")
    lines.append("")

    # Profile section
    lines.append("## Profile")
    lines.append("")

    p = description.profile
    profile_badge = _profile_badge(p.profile)
    lines.append(f"**Detected:** {profile_badge}")
    lines.append("")
    lines.append(f"*{p.reasoning_guidance}*")
    lines.append("")

    if p.owl_constructs_found:
        lines.append("**OWL Constructs:**")
        lines.append("")
        for construct in p.owl_constructs_found[:10]:
            lines.append(f"- {construct}")
        if len(p.owl_constructs_found) > 10:
            lines.append(f"- *...and {len(p.owl_constructs_found) - 10} more*")
        lines.append("")

    if p.violating_constructs:
        lines.append("⚠️ **DL Violations:**")
        lines.append("")
        for violation in p.violating_constructs:
            lines.append(f"- {violation}")
        lines.append("")

    # Brief mode stops here
    if description.brief:
        return "\n".join(lines)

    # Namespace section
    lines.append("## Namespaces")
    lines.append("")

    ns = description.namespaces
    lines.append(f"- **Local:** {ns.local_count}")
    lines.append(f"- **Imported:** {ns.imported_count}")
    lines.append(f"- **External:** {ns.external_count}")
    lines.append("")

    if ns.local_namespace:
        lines.append(f"Primary namespace: `{ns.local_namespace}`")
        lines.append("")

    # Top namespaces table
    if ns.namespaces:
        lines.append("### Top Namespaces by Usage")
        lines.append("")
        lines.append("| Prefix | Namespace | Usage | Category |")
        lines.append("|--------|-----------|-------|----------|")

        top_ns = sorted(ns.namespaces, key=lambda x: -x.usage_count)[:10]
        for nsi in top_ns:
            prefix = f"`{nsi.prefix}:`" if nsi.prefix else "-"
            category = {
                NamespaceCategory.LOCAL: "🏠 Local",
                NamespaceCategory.IMPORTED: "📦 Imported",
                NamespaceCategory.EXTERNAL: "🔗 External",
            }[nsi.category]
            lines.append(f"| {prefix} | `{nsi.uri}` | {nsi.usage_count} | {category} |")

        lines.append("")

    if ns.unimported_external:
        lines.append("### ⚠️ Unimported External Namespaces")
        lines.append("")
        lines.append("These namespaces are referenced but not declared via `owl:imports`:")
        lines.append("")
        for uri in ns.unimported_external:
            lines.append(f"- `{uri}`")
        lines.append("")

    # Imports section
    lines.append("## Imports")
    lines.append("")

    imp = description.imports
    if imp.count == 0:
        lines.append("*No imports declared.*")
        lines.append("")
    else:
        lines.append(f"**{imp.count} direct import(s) declared:**")
        lines.append("")

        for imp_info in imp.imports:
            if imp_info.status == ImportStatus.RESOLVABLE:
                status = "✅"
            elif imp_info.status == ImportStatus.UNRESOLVABLE:
                status = "❌"
                if imp_info.error:
                    status += f" ({imp_info.error})"
            else:
                status = "❓"

            lines.append(f"- {status} `{imp_info.uri}`")

        lines.append("")

    # Hierarchy section
    lines.append("## Class Hierarchy")
    lines.append("")

    h = description.hierarchy
    lines.append(f"- **Root classes:** {h.root_count}")
    lines.append(f"- **Maximum depth:** {h.max_depth}")
    lines.append(f"- **Orphan classes:** {h.orphan_count}")

    if h.has_cycles:
        lines.append("")
        lines.append("⚠️ **Cycles detected in hierarchy:**")
        for member in h.cycle_members[:5]:
            lines.append(f"- `{member}`")

    lines.append("")

    if h.root_classes and h.root_count <= 15:
        lines.append("### Root Classes")
        lines.append("")
        for root in h.root_classes:
            lines.append(f"- `{root}`")
        lines.append("")

    # Documentation section
    lines.append("## Documentation Coverage")
    lines.append("")

    d = description.documentation
    lines.append("| Entity | Labels | Definitions |")
    lines.append("|--------|--------|-------------|")

    class_label = f"{d.class_label_pct:.0f}% ({d.classes_with_label}/{d.classes_total})"
    class_def = f"{d.class_definition_pct:.0f}% ({d.classes_with_definition}/{d.classes_total})"
    lines.append(f"| Classes | {class_label} | {class_def} |")

    if d.properties_total > 0:
        prop_label = f"{d.property_label_pct:.0f}% ({d.properties_with_label}/{d.properties_total})"
        prop_def = f"{d.property_definition_pct:.0f}% ({d.properties_with_definition}/{d.properties_total})"
        lines.append(f"| Properties | {prop_label} | {prop_def} |")

    lines.append("")

    # Coverage assessment
    overall = (d.class_label_pct + d.class_definition_pct) / 2
    if overall >= 80:
        lines.append("📗 **Well documented**")
    elif overall >= 50:
        lines.append("📙 **Partially documented**")
    else:
        lines.append("📕 **Needs documentation**")

    lines.append("")

    # Reasoning section (if included)
    if description.reasoning is not None:
        lines.append("## Reasoning Analysis")
        lines.append("")

        r = description.reasoning
        lines.append(f"**Entailment regime:** {r.entailment_regime}")
        lines.append("")

        if r.consistency_notes:
            lines.append("### Notes")
            lines.append("")
            for note in r.consistency_notes:
                lines.append(f"- {note}")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Generated by rdf-construct describe at {description.timestamp.isoformat()}*")
    lines.append("")

    return "\n".join(lines)


def _profile_badge(profile: OntologyProfile) -> str:
    """Get a badge/emoji for the profile level."""
    badges = {
        OntologyProfile.RDF: "📄 RDF",
        OntologyProfile.RDFS: "📋 RDFS",
        OntologyProfile.OWL_DL_SIMPLE: "🟢 OWL 2 DL (simple)",
        OntologyProfile.OWL_DL_EXPRESSIVE: "🟡 OWL 2 DL (expressive)",
        OntologyProfile.OWL_FULL: "🔴 OWL 2 Full",
    }
    return badges.get(profile, profile.display_name)
