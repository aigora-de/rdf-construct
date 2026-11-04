"""SHACL shape generator from OWL ontologies.

Generates SHACL NodeShapes from OWL class definitions, converting
domain/range, cardinality restrictions, and other OWL patterns
to equivalent SHACL constraints.
"""

import hashlib
import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL

from rdf_construct.core.utils import extract_prefix_map

from .config import ShaclConfig, Severity
from .converters import PropertyConstraint, get_converters_for_level
from .namespaces import SH, SHACL_PREFIXES
from .selection import declared_classes, local_name, namespace_of, resolve_selection

#: An absolute IRI (a scheme, then no spaces or angle brackets) ending in a delimiter.
_NAMESPACE_IRI = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*:[^\s<>\"]*[#/:]")

_SEVERITIES: dict[Severity, URIRef] = {
    Severity.VIOLATION: SH.Violation,
    Severity.WARNING: SH.Warning,
    Severity.INFO: SH.Info,
}


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

        The class selection and the ignored properties are resolved here, against the
        source graph's own prefix bindings, so a selection that cannot be honoured is
        refused before anything is generated. Shape IRIs are fixed here too, over every
        class the source declares and never the selection, so choosing classes cannot
        rename a shape.

        Args:
            source_graph: The OWL ontology graph.
            config: Optional configuration (defaults provided).

        Raises:
            ShaclSelectionError: If the selection or an ignored property cannot be resolved.
            ValueError: If ``shape_namespace`` is not a full namespace IRI.
        """
        self.config = config or ShaclConfig()
        self.source_graph = source_graph
        self._declared = declared_classes(source_graph)
        self._home_ns = self._home_namespace()
        self._shape_ns = self._determine_shape_namespace()
        self.selection = resolve_selection(source_graph, self.config, self._get_target_classes())
        self.shapes_graph = Graph(bind_namespaces="core")

        # Bind prefixes
        for prefix, ns in SHACL_PREFIXES.items():
            self.shapes_graph.bind(prefix, ns)

        # Copy source prefixes
        for prefix, ns in source_graph.namespaces():
            if prefix and prefix not in ("xml", "xsd", "rdf", "rdfs", "owl"):
                self.shapes_graph.bind(prefix, ns)

        # Bind the shape namespace, and name every declared class's shape
        self.shapes_graph.bind("shape", Namespace(self._shape_ns))
        self._shape_names = self._name_shapes()

    def _home_namespace(self) -> str | None:
        """The namespace holding the most declared classes, ties to the smaller IRI.

        Taken over the whole source, never the selection (#484).
        """
        counts: dict[str, int] = defaultdict(int)
        for cls in self._declared:
            ns = namespace_of(str(cls))
            if ns:
                counts[ns] += 1
        if not counts:
            return None
        return min(counts, key=lambda ns: (-counts[ns], ns))

    def _determine_shape_namespace(self) -> str:
        """Determine the namespace for generated shapes.

        ``shape_namespace`` when it is set, which must be a full namespace IRI. Otherwise
        the ontology IRI plus ``-shapes#``, or, with no ``owl:Ontology``, the home namespace
        (see `_home_namespace`) plus ``-shapes#``.

        Raises:
            ValueError: If ``shape_namespace`` is set and is not a full namespace IRI.
        """
        configured = self.config.shape_namespace
        if configured is not None:
            if not isinstance(configured, str) or not _NAMESPACE_IRI.fullmatch(configured):
                raise ValueError(
                    f"shape_namespace must be a full namespace IRI ending in '#', '/' or ':', "
                    f"such as 'http://example.org/my-shapes#'; got {configured!r}. "
                    "Omit it to derive the namespace from the ontology"
                )
            return configured

        # Look for owl:Ontology
        for ont in self.source_graph.subjects(RDF.type, OWL.Ontology):
            if isinstance(ont, URIRef):
                base = str(ont)
                # Append shapes suffix
                if base.endswith("#") or base.endswith("/"):
                    return base[:-1] + "-shapes#"
                return base + "-shapes#"

        # Fallback: the home namespace, so the selection cannot move a shape's IRI (#484)
        if self._home_ns is not None:
            ns_str = self._home_ns
            if ns_str.endswith(("#", "/", ":")):
                ns_str = ns_str[:-1]
            return ns_str + "-shapes#"

        return "http://example.org/shapes#"

    def generate(self) -> Graph:
        """Generate SHACL shapes from the source ontology.

        Returns:
            Graph containing the generated SHACL shapes.
        """
        # Get converters for current strictness level
        converters = get_converters_for_level(self.config.level)

        # Generate shape for each selected class
        for cls in self.selection.classes:
            self._create_node_shape(cls, converters)

        return self.shapes_graph

    def _get_target_classes(self) -> list[URIRef]:
        """Get all target classes from the ontology.

        Every named class declared with a type in `core.vocab.CLASS_TYPES`, so
        ``owl:DeprecatedClass`` too (#228).

        Returns:
            List of class URIs, by local name and then IRI.
        """
        return sorted(self._declared, key=lambda c: (local_name(str(c)), str(c)))

    def _name_shapes(self) -> dict[URIRef, str]:
        """Name every declared class's shape: its local name, qualified only on a collision.

        A local name no other declared class has is used as it is. When two or more
        classes share one, the class in the home namespace keeps it and every other is
        qualified with its namespace's prefix in the source (``b_Cat``), or, with no prefix,
        a hash of its namespace (``ns1a2b3c4d_Cat``). The hash is also the fallback when a
        qualified name is taken. Names depend only on the source, never on the selection
        (#485).

        Returns:
            Class to the shape's local part, without the ``Shape`` suffix.
        """
        groups: dict[str, list[URIRef]] = defaultdict(list)
        for cls in self._declared:
            groups[local_name(str(cls))].append(cls)

        names: dict[URIRef, str] = {}
        to_qualify: list[tuple[URIRef, str]] = []
        for local, members in groups.items():
            for cls in members:
                if len(members) == 1 or namespace_of(str(cls)) == self._home_ns:
                    names[cls] = local
                else:
                    to_qualify.append((cls, local))

        prefixes = extract_prefix_map(self.source_graph)
        taken = set(names.values())
        for cls, local in sorted(to_qualify, key=lambda item: str(item[0])):
            ns = namespace_of(str(cls))
            bound = sorted(p for p, iri in prefixes.items() if p and iri == ns)
            name = f"{bound[0]}_{local}" if bound else None
            if name is None or name in taken:
                digest = hashlib.sha1(ns.encode("utf-8")).hexdigest()[:8]
                name = f"ns{digest}_{local}"
            taken.add(name)
            names[cls] = name
        return names

    def _class_paths(self, cls: URIRef) -> set[URIRef]:
        """The properties the ontology gives a class: by ``rdfs:domain``, or a restriction."""
        paths = {p for p in self.source_graph.subjects(RDFS.domain, cls) if isinstance(p, URIRef)}
        for superclass in self.source_graph.objects(cls, RDFS.subClassOf):
            if isinstance(superclass, BNode):
                on_prop = self.source_graph.value(superclass, OWL.onProperty)
                if isinstance(on_prop, URIRef):
                    paths.add(on_prop)
        return paths

    def _related_classes(self, cls: URIRef) -> set[URIRef]:
        """A class, its named superclasses and its named subclasses, transitively.

        A ``rdfs:subClassOf`` cycle is walked once.
        """
        graph = self.source_graph
        supers = _walk(cls, lambda c: graph.objects(c, RDFS.subClassOf))
        subs = _walk(cls, lambda c: graph.subjects(RDFS.subClassOf, c))
        return {cls} | supers | subs

    def _allowed_paths(self, cls: URIRef) -> set[URIRef]:
        """What a closed shape for ``cls`` admits: the paths of its whole hierarchy.

        Its own, its superclasses' and its subclasses', at any level and whether or not
        constraints are inherited. A superclass's paths, because an instance has them; a
        subclass's, because SHACL targets a subclass's instances with the superclass's
        shape wherever the data graph says ``rdfs:subClassOf`` (#224).
        """
        allowed: set[URIRef] = set()
        for related in self._related_classes(cls):
            allowed |= self._class_paths(related)
        return allowed

    def _create_node_shape(self, cls: URIRef, converters: list) -> URIRef:
        """Create a NodeShape for a class.

        Args:
            cls: The class to create a shape for.
            converters: List of converters to apply.

        Returns:
            URI of the created shape.
        """
        shape_uri = URIRef(f"{self._shape_ns}{self._shape_names[cls]}Shape")
        severity = (
            _SEVERITIES[self.config.default_severity]
            if self.config.default_severity is not None
            else None
        )

        # Basic shape definition
        self.shapes_graph.add((shape_uri, RDF.type, SH.NodeShape))
        self.shapes_graph.add((shape_uri, SH.targetClass, cls))

        # Severity, when one is set, on the node shape (sh:closed's results) and on every
        # property shape (#223)
        if severity is not None:
            self.shapes_graph.add((shape_uri, SH.severity, severity))

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
            constraints = converter.convert_for_class(cls, self.source_graph, self.config)

            for constraint in constraints:
                if constraint.path in prop_constraints:
                    # Merge with existing constraint
                    prop_constraints[constraint.path] = prop_constraints[constraint.path].merge(
                        constraint
                    )
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
            if severity is not None:
                self.shapes_graph.add((prop_shape, SH.severity, severity))
            self.shapes_graph.add((shape_uri, SH.property, prop_shape))

        # Closed shapes, at any level (#224): rdf:type and ignored_properties first, then
        # every path the hierarchy allows that is not already a property shape
        if self.config.closed:
            self.shapes_graph.add((shape_uri, SH.closed, Literal(True)))

            ignored = self._get_ignored_properties()
            ignored += sorted(
                (
                    path
                    for path in self._allowed_paths(cls)
                    if path not in prop_constraints and path not in ignored
                ),
                key=str,
            )
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
                        inherited[constraint.path] = inherited[constraint.path].merge(constraint)

            # Add parent's parents
            to_visit.extend(self.source_graph.objects(superclass, RDFS.subClassOf))

        return inherited

    def _get_ignored_properties(self) -> list[URIRef]:
        """Get list of properties to ignore in closed shapes: rdf:type first, no repeats."""
        return list(self.selection.ignored_properties)

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


def _walk(start: URIRef, step: Callable[[URIRef], Iterable[Any]]) -> set[URIRef]:
    """Every named node reachable from ``start`` by repeating ``step``, ``start`` excluded."""
    found: set[URIRef] = set()
    to_visit = [start]
    while to_visit:
        for other in step(to_visit.pop()):
            if isinstance(other, URIRef) and other != start and other not in found:
                found.add(other)
                to_visit.append(other)
    return found


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

    Raises:
        ShaclSelectionError: If the selection or an ignored property cannot be resolved;
            nothing is generated.
    """
    # Load source if path. A pre-loaded graph's selection resolves against its own
    # bindings, whatever they are.
    if isinstance(source, Path):
        source_graph = Graph(bind_namespaces="core")
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
