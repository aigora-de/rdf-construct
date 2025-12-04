"""Example: Programmatic use of rdf-construct.

This example shows how to use rdf-construct as a library
in your own Python code, rather than using the CLI.
"""

from pathlib import Path

from rdflib import Graph, RDF
from rdflib.namespace import OWL

from rdf_construct import (
    OrderingConfig,
    build_section_graph,
    extract_prefix_map,
    rebind_prefixes,
    select_subjects,
    serialize_turtle,
    sort_subjects,
)


def order_ontology_programmatically():
    """Example of ordering an ontology using the API."""

    # Load configuration
    config_path = Path("sample_profile.yml")
    config = OrderingConfig(config_path)

    # Get a specific profile
    profile = config.get_profile("logical_topo")
    print(f"Using profile: {profile.name}")
    print(f"Description: {profile.description}")

    # Load RDF graph
    ontology_path = Path("ontology.ttl")
    graph = Graph()
    graph.parse(ontology_path, format="turtle")

    prefix_map = extract_prefix_map(graph)

    # Process sections according to profile
    ordered_subjects = []
    seen = set()

    for section in profile.sections:
        if not isinstance(section, dict) or not section:
            continue

        section_name, section_cfg = next(iter(section.items()))

        # Handle header section
        if section_name == "header":
            ontology_subjects = [
                s for s in graph.subjects(RDF.type, OWL.Ontology) if s not in seen
            ]
            ordered_subjects.extend(ontology_subjects)
            seen.update(ontology_subjects)
            continue

        # Regular sections
        section_cfg = section_cfg or {}
        select_key = section_cfg.get("select", section_name)
        sort_mode = section_cfg.get("sort", "qname_alpha")
        roots_cfg = section_cfg.get("roots")

        # Select subjects for this section
        chosen = select_subjects(graph, select_key, config.selectors)
        chosen = [s for s in chosen if s not in seen]

        # Sort according to configuration
        ordered = sort_subjects(graph, set(chosen), sort_mode, roots_cfg)

        # Add to output
        for s in ordered:
            if s not in seen:
                ordered_subjects.append(s)
                seen.add(s)

    print(f"\nOrdered {len(ordered_subjects)} subjects")

    # Build filtered graph with only the ordered subjects
    output_graph = build_section_graph(graph, ordered_subjects)

    # Rebind prefixes in preferred order
    if config.prefix_order:
        rebind_prefixes(output_graph, config.prefix_order, prefix_map)

    # Serialize to file
    output_path = Path(f"ontology-{profile.name}.ttl")
    serialize_turtle(output_graph, ordered_subjects, output_path)
    print(f"Wrote: {output_path}")


def list_available_profiles():
    """Example of inspecting available profiles."""
    config_path = Path("sample_profile.yml")
    config = OrderingConfig(config_path)

    print("Available profiles:")
    for prof_name in config.list_profiles():
        prof = config.get_profile(prof_name)
        print(f"\n  {prof_name}")
        print(f"    Description: {prof.description}")
        print(f"    Sections: {len(prof.sections)}")


if __name__ == "__main__":
    print("=== Listing Profiles ===")
    list_available_profiles()

    print("\n=== Ordering Ontology ===")
    order_ontology_programmatically()
