#!/usr/bin/env python3
"""Example: Generate styled PlantUML diagrams from RDF ontologies.

Demonstrates how to use the UML renderer with styling
and layout configurations.
"""

from pathlib import Path

from rdflib import Graph

# Import the modules (adjust paths as needed for your setup)
from uml_style import load_style_config
from uml_layout import load_layout_config
from renderer import render_plantuml

# Import the mapper to select entities
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rdf_construct.uml.mapper import collect_diagram_entities
from rdf_construct.uml.context import load_uml_config


def generate_styled_diagram(
        ontology_file: Path,
        context_file: Path,
        style_file: Path,
        layout_file: Path,
        context_name: str,
        style_name: str,
        layout_name: str,
        output_file: Path,
):
    """Generate a single styled PlantUML diagram.

    Args:
        ontology_file: Path to RDF/Turtle ontology
        context_file: Path to UML contexts YAML
        style_file: Path to styles YAML
        layout_file: Path to layouts YAML
        context_name: Which context to use
        style_name: Which style scheme to use
        layout_name: Which layout to use
        output_file: Where to write the .puml file
    """
    print(f"Loading ontology: {ontology_file}")
    graph = Graph()
    graph.parse(str(ontology_file), format="turtle")

    print(f"Loading configuration: {context_file}")
    uml_config = load_uml_config(context_file)
    context = uml_config.get_context(context_name)

    print(f"Selecting entities for context: {context_name}")
    entities = collect_diagram_entities(
        graph, context, uml_config.config.get("selectors", {})
    )

    print(f"Loading style: {style_name}")
    style_config = load_style_config(style_file)
    style = style_config.get_scheme(style_name)

    print(f"Loading layout: {layout_name}")
    layout_config = load_layout_config(layout_file)
    layout = layout_config.get_layout(layout_name)

    print(f"Rendering PlantUML to: {output_file}")
    render_plantuml(graph, entities, output_file, style, layout)

    print(f"✓ Generated {output_file}")
    print(
        f"  Classes: {len(entities['classes'])}, "
        f"Properties: {len(entities['object_properties']) + len(entities['datatype_properties'])}, "
        f"Instances: {len(entities['instances'])}"
    )


def main():
    """Generate example diagrams with different styling combinations."""
    # Setup paths (adjust for your project structure)
    examples_dir = Path(__file__).parent
    ontology_file = examples_dir / "animal_ontology.ttl"
    context_file = examples_dir / "uml_contexts.yml"
    style_file = examples_dir / "uml_styles.yml"
    layout_file = examples_dir / "uml_layouts.yml"
    output_dir = examples_dir / "styled_diagrams"
    output_dir.mkdir(exist_ok=True)

    # Example 1: Default style with hierarchy layout
    print("\n" + "=" * 60)
    print("Example 1: Animal taxonomy with default style")
    print("=" * 60)
    generate_styled_diagram(
        ontology_file=ontology_file,
        context_file=context_file,
        style_file=style_file,
        layout_file=layout_file,
        context_name="animal_taxonomy",
        style_name="default",
        layout_name="hierarchy",
        output_file=output_dir / "animal_taxonomy_default_hierarchy.puml",
    )

    # Example 2: High contrast style with compact layout
    print("\n" + "=" * 60)
    print("Example 2: Mammals with high contrast style, compact layout")
    print("=" * 60)
    generate_styled_diagram(
        ontology_file=ontology_file,
        context_file=context_file,
        style_file=style_file,
        layout_file=layout_file,
        context_name="mammals_only",
        style_name="high_contrast",
        layout_name="compact",
        output_file=output_dir / "mammals_only_highcontrast_compact.puml",
    )

    # Example 3: Grayscale for documentation
    print("\n" + "=" * 60)
    print("Example 3: Full ontology with grayscale style for docs")
    print("=" * 60)
    generate_styled_diagram(
        ontology_file=ontology_file,
        context_file=context_file,
        style_file=style_file,
        layout_file=layout_file,
        context_name="full",
        style_name="grayscale",
        layout_name="documentation",
        output_file=output_dir / "full_grayscale_docs.puml",
    )

    # Example 4: Minimal style with network layout
    print("\n" + "=" * 60)
    print("Example 4: Key classes with minimal style, network layout")
    print("=" * 60)
    generate_styled_diagram(
        ontology_file=ontology_file,
        context_file=context_file,
        style_file=style_file,
        layout_file=layout_file,
        context_name="key_classes",
        style_name="minimal",
        layout_name="network",
        output_file=output_dir / "key_classes_minimal_network.puml",
    )

    print("\n" + "=" * 60)
    print("All examples generated successfully!")
    print(f"Output directory: {output_dir}")
    print("=" * 60)

    # Print summary of available options
    print("\nAvailable configurations:")

    style_config = load_style_config(style_file)
    print(f"\nStyles: {', '.join(style_config.list_schemes())}")

    layout_config = load_layout_config(layout_file)
    print(f"Layouts: {', '.join(layout_config.list_layouts())}")

    uml_config = load_uml_config(context_file)
    print(f"Contexts: {', '.join(uml_config.list_contexts())}")


if __name__ == "__main__":
    main()
