"""SHACL shape generator from OWL ontologies.

Generates SHACL NodeShapes from OWL class definitions, converting
domain/range, cardinality restrictions, and other OWL patterns
to equivalent SHACL constraints.
"""

from collections import defaultdict
from pathlib import Path
from typing import Any

from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL

from .config import ShaclConfig, Severity, StrictnessLevel
from .converters import PropertyConstraint, get_converters_for_level
from .namespaces import SH, SHACL_PREFIXES


class ShapeGenerator:
    """Generates SHACL shapes from OWL ontology definitions.

    Orchestrates the conversion process, applying converters and
    building the output shapes graph.

    Attributes:
        config: Generation configuration.
        source_graph: The OWL ontology to convert.
        shapes_graph: The output SHACL shapes graph.
    """

    def __init__(self, source_graph: Graph, config: ShaclConfig | None = None):
        """Initialise generator.

        Args:
            source_graph: The OWL ontology graph.
            config: Optional configuration (defaults provided).
        """
        self.config = config or ShaclConfig()
        self.source_graph = source_graph
        self.shapes_graph = Graph()

        # Bind prefixes
        for prefix, ns in SHACL_PREFIXES.items():
            self.shapes_graph.bind(prefix, ns)

        # Copy source prefixes
        for prefix, ns in source_graph.namespaces():
            if prefix and prefix not in ("xml", "xsd", "rdf", "rdfs", "owl"):
                self.shapes_graph.bind(prefix, ns)

        # Determine shape namespace
        self._shape_ns = self._determine_shape_namespace()
        self.shapes_graph.bind("shape", Namespace(self._shape_ns))

    def _determine_shape_namespace(self) -> str:
        """Determine the namespace for generated shapes.

        Uses the ontology namespace if available, otherwise falls back
        to a default.
        """
        # Look for owl:Ontology
        for ont in self.source_graph.subjects(RDF.type, OWL.Ontology):
            if isinstance(ont, URIRef):
                base = str(ont)
                # Append shapes suffix
                if base.endswith("#") or base.endswith("/"):
                    return base[:-1] + "-shapes#"
                return base + "-shapes#"

        # Fallback: use first non-standard namespace
        for prefix, ns in self.source_graph.namespaces():
            ns_str = str(ns)
            if not any(
                    ns_str.startswith(std)
                    for std in (
                            "http://www.w3.org/",
                            "http://purl.org/dc/",
                            "http://xmlns.com/",
                    )
            ):
                if ns_str.endswith("#") or ns_str.endswith("/"):
                    return ns_str[:-1] + "-shapes#"
                return ns_str + "-shapes#"

        return "http://example.org/shapes#"

    def generate(self) -> Graph:
        """Generate SHACL shapes from the source ontology.

        Returns:
            Graph containing the generated SHACL shapes.
        """
        # Get all classes from ontology
        classes = self._get_target_classes()

        # Get converters for current strictness level
        converters = get_converters_for_level(self.config.level)

        # Generate shape for each class
        for cls in classes:
            if not self.config.should_generate_for(cls, self.source_graph):
                continue

            self._create_node_shape(cls, converters)

        return self.shapes_graph

    def _get_target_classes(self) -> list[URIRef]:
        """Get all target classes from the ontology.

        Finds both owl:Class and rdfs:Class entities.

        Returns:
            List of class URIs.
        """
        classes: set[URIRef] = set()

        # OWL classes
        for cls in self.source_graph.subjects(RDF.type, OWL.Class):
            if isinstance(cls, URIRef):
                classes.add(cls)

        # RDFS classes
        for cls in self.source_graph.subjects(RDF.type, RDFS.Class):
            if isinstance(cls, URIRef):
                classes.add(cls)

        # Sort by local name for consistent output
        return sorted(classes, key=lambda c: self._local_name(c))

    def _local_name(self, uri: URIRef) -> str:
        """Extract local name from URI."""
        s = str(uri)
        if "#" in s:
            return s.rsplit("#", 1)[1]
        if "/" in s:
            return s.rsplit("/", 1)[1]
        return s

    def _create_node_shape(self, cls: URIRef, converters: list) -> URIRef:
        """Create a NodeShape for a class.

        Args:
            cls: The class to create a shape for.
            converters: List of converters to apply.

        Returns:
            URI of the created shape.
        """
        shape_uri = URIRef(f"{self._shape_ns}{self._local_name(cls)}Shape")

        # Basic shape definition
        self.shapes_graph.add((shape_uri, RDF.type, SH.NodeShape))
        self.shapes_graph.add((shape_uri, SH.targetClass, cls))

        # Add name from rdfs:label if available
        if self.config.include_labels:
            label = self.source_graph.value(cls, RDFS.label)
            if label:
                self.shapes_graph.add((shape_uri, SH.name, Literal(str(label))))

        # Add description from rdfs:comment
        if self.config.include_descriptions:
            comment = self.source_graph.value(cls, RDFS.comment)
            if comment:
                self.shapes_graph.add((shape_uri, SH.description, Literal(str(comment))))

        # Collect all property constraints
        prop_constraints: dict[URIRef, PropertyConstraint] = {}

        # Apply each converter
        for converter in converters:
            constraints = converter.convert_for_class(
                cls, self.source_graph, self.config
            )

            for constraint in constraints:
                if constraint.path in prop_constraints:
                    # Merge with existing constraint
                    prop_constraints[constraint.path] = prop_constraints[
                        constraint.path
                    ].merge(constraint)
                else:
                    prop_constraints[constraint.path] = constraint

        # Inherit constraints from superclasses if configured
        if self.config.inherit_constraints:
            inherited = self._get_inherited_constraints(cls, converters)
            for path, constraint in inherited.items():
                if path not in prop_constraints:
                    prop_constraints[path] = constraint

        # Add property shapes, sorted by path for consistent output
        order = 1
        for path in sorted(prop_constraints.keys(), key=str):
            constraint = prop_constraints[path]
            constraint.order = order
            order += 1

            prop_shape = constraint.to_rdf(self.shapes_graph)
            self.shapes_graph.add((shape_uri, SH.property, prop_shape))

        # Handle closed shapes
        if self.config.closed and self.config.level == StrictnessLevel.STRICT:
            self.shapes_graph.add((shape_uri, SH.closed, Literal(True)))

            # Add ignored properties
            ignored = self._get_ignored_properties()
            if ignored:
                ignored_list = self._create_rdf_list(ignored)
                self.shapes_graph.add((shape_uri, SH.ignoredProperties, ignored_list))

        return shape_uri

    def _get_inherited_constraints(
            self, cls: URIRef, converters: list
    ) -> dict[URIRef, PropertyConstraint]:
        """Get property constraints from superclasses.

        Args:
            cls: The class to get inherited constraints for.
            converters: Converters to apply.

        Returns:
            Dictionary mapping property URIs to constraints.
        """
        inherited: dict[URIRef, PropertyConstraint] = {}

        # Walk up the class hierarchy
        visited: set[URIRef] = set()
        to_visit = list(self.source_graph.objects(cls, RDFS.subClassOf))

        while to_visit:
            superclass = to_visit.pop()
            if not isinstance(superclass, URIRef) or superclass in visited:
                continue

            visited.add(superclass)

            # Apply converters to superclass
            for converter in converters:
                constraints = converter.convert_for_class(
                    superclass, self.source_graph, self.config
                )

                for constraint in constraints:
                    if constraint.path not in inherited:
                        inherited[constraint.path] = constraint
                    else:
                        inherited[constraint.path] = inherited[constraint.path].merge(
                            constraint
                        )

            # Add parent's parents
            to_visit.extend(self.source_graph.objects(superclass, RDFS.subClassOf))

        return inherited

    def _get_ignored_properties(self) -> list[URIRef]:
        """Get list of properties to ignore in closed shapes."""
        ignored = [RDF.type]  # Always ignore rdf:type

        # Add user-configured ignored properties
        for prop_str in self.config.ignored_properties:
            # Expand CURIE if possible
            expanded = self._expand_curie(prop_str)
            if expanded:
                ignored.append(expanded)

        return ignored

    def _expand_curie(self, curie: str) -> URIRef | None:
        """Expand a CURIE to full URI."""
        if ":" in curie and not curie.startswith("http"):
            prefix, local = curie.split(":", 1)
            for p, ns in self.source_graph.namespaces():
                if p == prefix:
                    return URIRef(str(ns) + local)

        # Already a URI?
        if curie.startswith("http"):
            return URIRef(curie)

        return None

    def _create_rdf_list(self, items: list[URIRef]) -> BNode:
        """Create an RDF list from items."""
        if not items:
            return RDF.nil

        head = BNode()
        current = head

        for i, item in enumerate(items):
            self.shapes_graph.add((current, RDF.first, item))

            if i < len(items) - 1:
                next_node = BNode()
                self.shapes_graph.add((current, RDF.rest, next_node))
                current = next_node
            else:
                self.shapes_graph.add((current, RDF.rest, RDF.nil))

        return head


def generate_shapes(
        source: Path | Graph,
        config: ShaclConfig | None = None,
        output_format: str = "turtle",
) -> tuple[Graph, str]:
    """Generate SHACL shapes from an OWL ontology.

    Main entry point for shape generation.

    Args:
        source: Path to ontology file or pre-loaded Graph.
        config: Optional generation configuration.
        output_format: Output serialisation format.

    Returns:
        Tuple of (shapes graph, serialised string).
    """
    # Load source if path
    if isinstance(source, Path):
        source_graph = Graph()
        source_graph.parse(str(source), format="turtle")
    else:
        source_graph = source

    # Generate shapes
    generator = ShapeGenerator(source_graph, config)
    shapes_graph = generator.generate()

    # Serialise
    output = shapes_graph.serialize(format=output_format)

    return shapes_graph, output


def generate_shapes_to_file(
        source: Path,
        output: Path,
        config: ShaclConfig | None = None,
        output_format: str = "turtle",
) -> Graph:
    """Generate SHACL shapes and write to file.

    Args:
        source: Path to ontology file.
        output: Path to write shapes to.
        config: Optional generation configuration.
        output_format: Output serialisation format.

    Returns:
        The generated shapes graph.
    """
    shapes_graph, serialised = generate_shapes(source, config, output_format)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialised)

    return shapes_graph
