"""Map RDF ontology entities to UML diagram elements.

This module handles the selection and filtering of classes, properties,
and instances from an RDF graph based on UML context specifications.
"""

from typing import Optional

from rdflib import Graph, URIRef, RDF, RDFS
from rdflib.namespace import OWL

from ..core.utils import expand_curie, qname_sort_key
from ..core.selector import select_subjects
from .context import UMLContext


def get_descendants(
    graph: Graph, root: URIRef, max_depth: Optional[int] = None
) -> set[URIRef]:
    """Get all descendant classes of a root class.

    Traverses rdfs:subClassOf relationships to find all classes that
    inherit from the root, optionally limiting depth.

    Args:
        graph: RDF graph to traverse
        root: Root class URI
        max_depth: Maximum depth to traverse (None = unlimited)

    Returns:
        Set of URIRefs including root and all descendants
    """
    descendants = {root}
    current_level = {root}
    depth = 0

    while current_level:
        if max_depth is not None and depth >= max_depth:
            break

        next_level = set()
        for cls in current_level:
            # Find direct subclasses
            for subclass in graph.subjects(RDFS.subClassOf, cls):
                if isinstance(subclass, URIRef) and subclass not in descendants:
                    descendants.add(subclass)
                    next_level.add(subclass)

        current_level = next_level
        depth += 1

    return descendants


def select_classes(
    graph: Graph, context: UMLContext, selectors: dict[str, str]
) -> set[URIRef]:
    """Select classes for diagram based on context configuration.

    Supports three selection modes:
    1. root_classes: Start from specific roots and optionally include descendants
    2. focus_classes: Explicit list of classes to include
    3. selector: Use selector key (e.g., "classes") to select all matching

    Args:
        graph: RDF graph to select from
        context: UML context specifying selection criteria
        selectors: Selector definitions from config

    Returns:
        Set of URIRefs for selected classes
    """
    selected: set[URIRef] = set()

    # Strategy 1: Root classes with optional descendants
    if context.root_classes:
        for curie in context.root_classes:
            root = expand_curie(graph, curie)
            if root is None:
                continue

            if context.include_descendants:
                descendants = get_descendants(graph, root, context.max_depth)
                selected.update(descendants)
            else:
                selected.add(root)

    # Strategy 2: Explicit focus classes
    elif context.focus_classes:
        for curie in context.focus_classes:
            cls = expand_curie(graph, curie)
            if cls is not None:
                selected.add(cls)

                # Optionally include descendants
                if context.include_descendants:
                    descendants = get_descendants(graph, cls, context.max_depth)
                    selected.update(descendants)

    # Strategy 3: Use selector (e.g., all classes)
    elif context.selector:
        selected = select_subjects(graph, context.selector, selectors)

    return selected


def select_properties(
    graph: Graph, context: UMLContext, selected_classes: set[URIRef]
) -> dict[str, set[URIRef]]:
    """Select properties for diagram based on context and selected classes.

    Returns properties categorized by type (object/datatype/annotation).
    Different modes control which properties are included:
    - 'domain_based': Properties whose domain is in selected classes
    - 'connected': Properties connecting selected classes
    - 'explicit': Only explicitly listed properties
    - 'all': All properties in the graph
    - 'none': No properties

    Args:
        graph: RDF graph to select from
        context: UML context specifying property criteria
        selected_classes: Set of classes already selected for diagram

    Returns:
        Dictionary with keys 'object', 'datatype', 'annotation' mapping to
        sets of URIRefs for each property type
    """
    properties = {
        "object": set(),
        "datatype": set(),
        "annotation": set(),
    }

    # Get all properties by type
    all_obj_props = {s for s in graph.subjects(RDF.type, OWL.ObjectProperty)}
    all_data_props = {s for s in graph.subjects(RDF.type, OWL.DatatypeProperty)}
    all_ann_props = {s for s in graph.subjects(RDF.type, OWL.AnnotationProperty)}

    mode = context.property_mode

    if mode == "none":
        return properties

    elif mode == "all":
        properties["object"] = all_obj_props
        properties["datatype"] = all_data_props
        properties["annotation"] = all_ann_props

    elif mode == "explicit":
        # Only include explicitly listed properties
        for curie in context.property_include:
            prop = expand_curie(graph, curie)
            if prop is None:
                continue

            if prop in all_obj_props:
                properties["object"].add(prop)
            elif prop in all_data_props:
                properties["datatype"].add(prop)
            elif prop in all_ann_props:
                properties["annotation"].add(prop)

    elif mode == "domain_based":
        # Include properties whose domain is in selected classes
        for prop in all_obj_props | all_data_props | all_ann_props:
            domains = set(graph.objects(prop, RDFS.domain))

            # Check if any domain is in selected classes
            if domains & selected_classes:
                if prop in all_obj_props:
                    properties["object"].add(prop)
                elif prop in all_data_props:
                    properties["datatype"].add(prop)
                elif prop in all_ann_props:
                    properties["annotation"].add(prop)

    elif mode == "connected":
        # Include object properties that connect selected classes
        for prop in all_obj_props:
            domains = set(graph.objects(prop, RDFS.domain))
            ranges = set(graph.objects(prop, RDFS.range))

            # Both domain and range must be in selected classes
            if (domains & selected_classes) and (ranges & selected_classes):
                properties["object"].add(prop)

        # For datatype props, just check domain
        for prop in all_data_props:
            domains = set(graph.objects(prop, RDFS.domain))
            if domains & selected_classes:
                properties["datatype"].add(prop)

    # Apply exclusions
    for curie in context.property_exclude:
        prop = expand_curie(graph, curie)
        if prop:
            properties["object"].discard(prop)
            properties["datatype"].discard(prop)
            properties["annotation"].discard(prop)

    return properties


def select_instances(
    graph: Graph, selected_classes: set[URIRef]
) -> set[URIRef]:
    """Select instances of the selected classes.

    Args:
        graph: RDF graph to select from
        selected_classes: Classes whose instances to select

    Returns:
        Set of URIRefs for individuals that are instances of selected classes
    """
    instances = set()

    for cls in selected_classes:
        # Find all instances of this class
        for instance in graph.subjects(RDF.type, cls):
            if isinstance(instance, URIRef):
                instances.add(instance)

    return instances


def collect_explicit_entities(
    graph: Graph, context: UMLContext
) -> dict[str, set[URIRef]]:
    """Collect entities explicitly specified in context.

    In explicit mode, all entities are directly listed in the configuration
    rather than selected via strategies. This provides complete control over
    diagram contents.

    Args:
        graph: RDF graph to validate entities against
        context: UML context with explicit entity lists

    Returns:
        Dictionary with keys:
        - 'classes': Explicitly specified class URIRefs
        - 'object_properties': Explicitly specified object property URIRefs
        - 'datatype_properties': Explicitly specified datatype property URIRefs
        - 'annotation_properties': Explicitly specified annotation property URIRefs
        - 'instances': Explicitly specified instance URIRefs

    Raises:
        ValueError: If a CURIE cannot be expanded or entity doesn't exist
    """
    entities = {
        "classes": set(),
        "object_properties": set(),
        "datatype_properties": set(),
        "annotation_properties": set(),
        "instances": set(),
    }

    # Get all properties by type for validation
    all_obj_props = {s for s in graph.subjects(RDF.type, OWL.ObjectProperty)}
    all_data_props = {s for s in graph.subjects(RDF.type, OWL.DatatypeProperty)}
    all_ann_props = {s for s in graph.subjects(RDF.type, OWL.AnnotationProperty)}

    # Expand and validate classes
    for curie in context.explicit_classes:
        uri = expand_curie(graph, curie)
        if uri is None:
            raise ValueError(f"Cannot expand CURIE: {curie}")

        # Validate it's actually a class
        is_class = (
            (uri, RDF.type, OWL.Class) in graph or
            (uri, RDF.type, RDFS.Class) in graph
        )
        if not is_class:
            # Warning but don't fail - might be a valid use case
            pass

        entities["classes"].add(uri)

    # Expand and validate object properties
    for curie in context.explicit_object_properties:
        uri = expand_curie(graph, curie)
        if uri is None:
            raise ValueError(f"Cannot expand CURIE: {curie}")

        if uri not in all_obj_props:
            # Warning but don't fail
            pass

        entities["object_properties"].add(uri)

    # Expand and validate datatype properties
    for curie in context.explicit_datatype_properties:
        uri = expand_curie(graph, curie)
        if uri is None:
            raise ValueError(f"Cannot expand CURIE: {curie}")

        if uri not in all_data_props:
            pass

        entities["datatype_properties"].add(uri)

    # Expand and validate annotation properties
    for curie in context.explicit_annotation_properties:
        uri = expand_curie(graph, curie)
        if uri is None:
            raise ValueError(f"Cannot expand CURIE: {curie}")

        if uri not in all_ann_props:
            pass

        entities["annotation_properties"].add(uri)

    # Expand instances
    for curie in context.explicit_instances:
        uri = expand_curie(graph, curie)
        if uri is None:
            raise ValueError(f"Cannot expand CURIE: {curie}")

        entities["instances"].add(uri)

    return entities


def collect_diagram_entities(
    graph: Graph, context: UMLContext, selectors: dict[str, str]
) -> dict[str, set[URIRef]]:
    """Collect all entities for a UML diagram based on context.

    This is the main entry point for entity selection. It orchestrates
    the selection of classes, properties, and instances based on the
    context mode (default or explicit).

    Args:
        graph: RDF graph to select from
        context: UML context specifying selection criteria
        selectors: Selector definitions from config

    Returns:
        Dictionary with keys:
        - 'classes': Selected class URIRefs
        - 'object_properties': Selected object property URIRefs
        - 'datatype_properties': Selected datatype property URIRefs
        - 'annotation_properties': Selected annotation property URIRefs
        - 'instances': Selected instance URIRefs
    """
    # Handle explicit mode (direct specification of classes, properties, attributes, & instances)
    if context.mode == "explicit":
        return collect_explicit_entities(graph, context)

    # Default mode: use existing selection strategies
    # Select classes
    classes = select_classes(graph, context, selectors)

    # Select properties based on classes
    properties = select_properties(graph, context, classes)

    # Select instances if requested
    instances = set()
    if context.include_instances:
        instances = select_instances(graph, classes)

    return {
        "classes": classes,
        "object_properties": properties["object"],
        "datatype_properties": properties["datatype"],
        "annotation_properties": properties["annotation"],
        "instances": instances,
    }
