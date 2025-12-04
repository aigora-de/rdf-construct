"""Core split logic for modularising RDF ontologies.

This module provides the OntologySplitter class that:
- Splits a monolithic ontology into multiple modules
- Supports namespace-based and explicit entity-based splitting
- Tracks cross-module dependencies
- Generates owl:imports declarations
- Produces a manifest documenting the split
- Supports data migration by instance type
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rdflib import Graph, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, OWL


def select_classes(graph: Graph) -> set[URIRef]:
    """Select all class entities from a graph.

    Args:
        graph: RDF graph to select from.

    Returns:
        Set of URIRefs for classes (owl:Class and rdfs:Class).
    """
    classes: set[URIRef] = set()
    for s in graph.subjects(RDF.type, OWL.Class):
        if isinstance(s, URIRef):
            classes.add(s)
    for s in graph.subjects(RDF.type, RDFS.Class):
        if isinstance(s, URIRef):
            classes.add(s)
    return classes


def select_properties(graph: Graph) -> set[URIRef]:
    """Select all property entities from a graph.

    Args:
        graph: RDF graph to select from.

    Returns:
        Set of URIRefs for properties (owl:ObjectProperty, DatatypeProperty, etc.).
    """
    properties: set[URIRef] = set()
    property_types = [
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        RDF.Property,
    ]
    for prop_type in property_types:
        for s in graph.subjects(RDF.type, prop_type):
            if isinstance(s, URIRef):
                properties.add(s)
    return properties


@dataclass
class ModuleDefinition:
    """Definition of a single module to extract.

    Attributes:
        name: Module identifier (used in manifest).
        output: Output filename.
        description: Human-readable description.
        classes: Explicit list of class URIs to include.
        properties: Explicit list of property URIs to include.
        namespaces: Namespace prefixes to include (for auto-detection).
        include_descendants: Whether to include rdfs:subClassOf/subPropertyOf descendants.
        imports: Explicit owl:imports to add.
        auto_imports: Whether to generate imports from detected dependencies.
    """

    name: str
    output: str
    description: str | None = None
    classes: list[str] = field(default_factory=list)
    properties: list[str] = field(default_factory=list)
    namespaces: list[str] = field(default_factory=list)
    include_descendants: bool = False
    imports: list[str] = field(default_factory=list)
    auto_imports: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModuleDefinition":
        """Create from dictionary.

        Args:
            data: Dictionary with module configuration.

        Returns:
            ModuleDefinition instance.
        """
        include = data.get("include", {})
        return cls(
            name=data["name"],
            output=data.get("output", f"{data['name']}.ttl"),
            description=data.get("description"),
            classes=include.get("classes", data.get("classes", [])),
            properties=include.get("properties", data.get("properties", [])),
            namespaces=data.get("namespaces", []),
            include_descendants=data.get("include_descendants", False),
            imports=data.get("imports", []),
            auto_imports=data.get("auto_imports", True),
        )


@dataclass
class UnmatchedStrategy:
    """Configuration for handling entities that don't match any module.

    Attributes:
        strategy: Either 'common' (put in common module) or 'error' (fail).
        common_module: Name of the common module if strategy is 'common'.
        common_output: Output filename for common module.
    """

    strategy: str = "common"  # "common" or "error"
    common_module: str = "common"
    common_output: str = "common.ttl"


@dataclass
class SplitDataConfig:
    """Configuration for splitting data files by instance type.

    Attributes:
        sources: Data files to split.
        output_dir: Directory for split data files.
        prefix: Prefix for output filenames (e.g., "data_").
    """

    sources: list[Path] = field(default_factory=list)
    output_dir: Path | None = None
    prefix: str = "data_"


@dataclass
class SplitConfig:
    """Complete configuration for a split operation.

    Attributes:
        source: Path to the source ontology file.
        output_dir: Directory for output module files.
        modules: List of module definitions.
        unmatched: Strategy for unmatched entities.
        split_data: Optional data splitting configuration.
        generate_manifest: Whether to generate manifest.yml.
        dry_run: If True, report what would happen without writing.
    """

    source: Path
    output_dir: Path
    modules: list[ModuleDefinition] = field(default_factory=list)
    unmatched: UnmatchedStrategy = field(default_factory=UnmatchedStrategy)
    split_data: SplitDataConfig | None = None
    generate_manifest: bool = True
    dry_run: bool = False

    @classmethod
    def from_yaml(cls, path: Path) -> "SplitConfig":
        """Load configuration from a YAML file.

        Args:
            path: Path to YAML configuration file.

        Returns:
            SplitConfig instance.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            ValueError: If config is invalid.
        """
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data, config_dir=path.parent)

    @classmethod
    def from_dict(cls, data: dict[str, Any], config_dir: Path | None = None) -> "SplitConfig":
        """Create from dictionary.

        Args:
            data: Dictionary with configuration.
            config_dir: Directory containing config file (for relative paths).

        Returns:
            SplitConfig instance.
        """
        config_dir = config_dir or Path(".")
        split_data = data.get("split", data)

        # Parse source
        source = Path(split_data.get("source", ""))
        if not source.is_absolute():
            source = config_dir / source

        # Parse output directory
        output_dir = Path(split_data.get("output_dir", "modules"))
        if not output_dir.is_absolute():
            output_dir = config_dir / output_dir

        # Parse modules
        modules = [
            ModuleDefinition.from_dict(m)
            for m in split_data.get("modules", [])
        ]

        # Parse unmatched strategy
        unmatched_data = split_data.get("unmatched", {})
        unmatched = UnmatchedStrategy(
            strategy=unmatched_data.get("strategy", "common"),
            common_module=unmatched_data.get("module", "common"),
            common_output=unmatched_data.get("output", "common.ttl"),
        )

        # Parse data splitting config
        split_data_config = None
        if "split_data" in split_data:
            sd = split_data["split_data"]
            sources = [
                config_dir / Path(p) if not Path(p).is_absolute() else Path(p)
                for p in sd.get("sources", [])
            ]
            output = sd.get("output_dir")
            split_data_config = SplitDataConfig(
                sources=sources,
                output_dir=config_dir / Path(output) if output else None,
                prefix=sd.get("prefix", "data_"),
            )

        return cls(
            source=source,
            output_dir=output_dir,
            modules=modules,
            unmatched=unmatched,
            split_data=split_data_config,
            generate_manifest=split_data.get("generate_manifest", True),
            dry_run=split_data.get("dry_run", False),
        )


@dataclass
class ModuleStats:
    """Statistics for a single module.

    Attributes:
        name: Module name.
        file: Output filename.
        classes: Number of classes in module.
        properties: Number of properties in module.
        triples: Total triples in module.
        imports: List of owl:imports.
        dependencies: Modules this module depends on.
    """

    name: str
    file: str
    classes: int = 0
    properties: int = 0
    triples: int = 0
    imports: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


@dataclass
class SplitResult:
    """Result of a split operation.

    Attributes:
        modules: Dictionary of module name -> Graph.
        module_stats: Statistics per module.
        entity_assignments: Mapping of entity URI -> module name.
        unmatched_entities: Entities not assigned to any module.
        dependencies: Cross-module dependency graph.
        success: Whether split completed without errors.
        error: Error message if success is False.
        data_modules: Split data graphs by module (if data splitting enabled).
    """

    modules: dict[str, Graph] = field(default_factory=dict)
    module_stats: list[ModuleStats] = field(default_factory=list)
    entity_assignments: dict[str, str] = field(default_factory=dict)
    unmatched_entities: set[str] = field(default_factory=set)
    dependencies: dict[str, set[str]] = field(default_factory=dict)
    success: bool = True
    error: str | None = None
    data_modules: dict[str, Graph] = field(default_factory=dict)

    @property
    def total_modules(self) -> int:
        """Total number of modules created."""
        return len(self.modules)

    @property
    def total_triples(self) -> int:
        """Total triples across all modules."""
        return sum(len(g) for g in self.modules.values())


class OntologySplitter:
    """Splits a monolithic ontology into multiple modules.

    The splitter:
    1. Loads the source ontology
    2. Assigns entities to modules based on configuration
    3. Handles unmatched entities per strategy
    4. Detects cross-module dependencies
    5. Generates owl:imports declarations
    6. Writes module files
    7. Produces a manifest documenting the split

    Example:
        config = SplitConfig.from_yaml(Path("split.yml"))
        splitter = OntologySplitter(config)
        result = splitter.split()

        if result.success:
            splitter.write_modules(result)
    """

    def __init__(self, config: SplitConfig):
        """Initialize the splitter.

        Args:
            config: Split configuration.
        """
        self.config = config
        self.source_graph: Graph | None = None
        self.namespace_map: dict[str, str] = {}  # namespace -> module name

    def split(self) -> SplitResult:
        """Execute the split operation.

        Returns:
            SplitResult with module graphs and statistics.
        """
        result = SplitResult()

        # Load source ontology
        try:
            self.source_graph = self._load_source()
        except Exception as e:
            result.success = False
            result.error = f"Failed to load source: {e}"
            return result

        # Build namespace -> module mapping (for namespace-based splitting)
        self._build_namespace_map()

        # Assign entities to modules
        assignments = self._assign_entities(result)

        if not result.success:
            return result

        # Create module graphs
        self._create_module_graphs(assignments, result)

        # Handle unmatched entities
        if result.unmatched_entities:
            self._handle_unmatched(result)

        # Detect dependencies and generate imports
        self._detect_dependencies(result)
        self._add_imports(result)

        # Calculate statistics
        self._calculate_stats(result)

        # Split data if configured
        if self.config.split_data and self.config.split_data.sources:
            self._split_data(result)

        return result

    def _load_source(self) -> Graph:
        """Load the source ontology file.

        Returns:
            Loaded RDF graph.

        Raises:
            FileNotFoundError: If source doesn't exist.
            ValueError: If source can't be parsed.
        """
        if not self.config.source.exists():
            raise FileNotFoundError(f"Source not found: {self.config.source}")

        graph = Graph()

        # Determine format from extension
        ext = self.config.source.suffix.lower()
        format_map = {
            ".ttl": "turtle",
            ".turtle": "turtle",
            ".rdf": "xml",
            ".xml": "xml",
            ".owl": "xml",
            ".n3": "n3",
            ".nt": "nt",
            ".jsonld": "json-ld",
        }
        rdf_format = format_map.get(ext, "turtle")

        graph.parse(self.config.source.as_posix(), format=rdf_format)

        return graph

    def _build_namespace_map(self) -> None:
        """Build mapping from namespaces to module names."""
        self.namespace_map = {}

        for module in self.config.modules:
            for ns in module.namespaces:
                self.namespace_map[ns] = module.name

    def _assign_entities(self, result: SplitResult) -> dict[str, set[URIRef]]:
        """Assign entities to modules.

        Args:
            result: SplitResult to populate with assignments.

        Returns:
            Dictionary of module name -> set of entity URIs.
        """
        if self.source_graph is None:
            result.success = False
            result.error = "Source graph not loaded"
            return {}

        assignments: dict[str, set[URIRef]] = {m.name: set() for m in self.config.modules}

        # Get all classes and properties from source
        all_classes = select_classes(self.source_graph)
        all_properties = select_properties(self.source_graph)
        all_entities = all_classes | all_properties

        # Assign entities to modules
        for module in self.config.modules:
            # By explicit class list
            for cls_uri in module.classes:
                uri = self._expand_curie(cls_uri)
                if uri in all_entities:
                    assignments[module.name].add(uri)
                    result.entity_assignments[str(uri)] = module.name

                    # Include descendants if requested
                    if module.include_descendants:
                        descendants = self._get_descendants(uri, all_classes)
                        for desc in descendants:
                            if str(desc) not in result.entity_assignments:
                                assignments[module.name].add(desc)
                                result.entity_assignments[str(desc)] = module.name

            # By explicit property list
            for prop_uri in module.properties:
                uri = self._expand_curie(prop_uri)
                if uri in all_entities:
                    assignments[module.name].add(uri)
                    result.entity_assignments[str(uri)] = module.name

                    # Include descendants if requested
                    if module.include_descendants:
                        descendants = self._get_descendants(uri, all_properties, is_property=True)
                        for desc in descendants:
                            if str(desc) not in result.entity_assignments:
                                assignments[module.name].add(desc)
                                result.entity_assignments[str(desc)] = module.name

            # By namespace
            for ns in module.namespaces:
                for entity in all_entities:
                    if str(entity).startswith(ns):
                        if str(entity) not in result.entity_assignments:
                            assignments[module.name].add(entity)
                            result.entity_assignments[str(entity)] = module.name

        # Find unmatched entities
        for entity in all_entities:
            if str(entity) not in result.entity_assignments:
                result.unmatched_entities.add(str(entity))

        return assignments

    def _expand_curie(self, curie: str) -> URIRef:
        """Expand a CURIE to a full URI using the source graph's namespace bindings.

        Args:
            curie: CURIE or full URI string.

        Returns:
            URIRef of the expanded URI.
        """
        if self.source_graph is None:
            return URIRef(curie)

        # If already a full URI
        if curie.startswith("http://") or curie.startswith("https://"):
            return URIRef(curie)

        # Try to expand as CURIE
        if ":" in curie:
            prefix, local = curie.split(":", 1)
            for ns_prefix, ns_uri in self.source_graph.namespace_manager.namespaces():
                if ns_prefix == prefix:
                    return URIRef(str(ns_uri) + local)

        return URIRef(curie)

    def _get_descendants(
        self,
        uri: URIRef,
        entity_set: set[URIRef],
        is_property: bool = False,
    ) -> set[URIRef]:
        """Get all descendants (subclasses/subproperties) of an entity.

        Args:
            uri: Parent entity URI.
            entity_set: Set of all entities to consider.
            is_property: Whether to look for subPropertyOf instead of subClassOf.

        Returns:
            Set of descendant URIs.
        """
        if self.source_graph is None:
            return set()

        predicate = RDFS.subPropertyOf if is_property else RDFS.subClassOf
        descendants: set[URIRef] = set()
        to_check = [uri]

        while to_check:
            parent = to_check.pop()
            for s, p, o in self.source_graph.triples((None, predicate, parent)):
                if isinstance(s, URIRef) and s in entity_set:
                    if s not in descendants:
                        descendants.add(s)
                        to_check.append(s)

        return descendants

    def _create_module_graphs(
        self,
        assignments: dict[str, set[URIRef]],
        result: SplitResult,
    ) -> None:
        """Create RDF graphs for each module.

        Args:
            assignments: Entity assignments per module.
            result: SplitResult to populate with graphs.
        """
        if self.source_graph is None:
            return

        for module in self.config.modules:
            module_graph = Graph()

            # Copy namespace bindings
            for prefix, ns in self.source_graph.namespace_manager.namespaces():
                module_graph.bind(prefix, ns)

            # Add triples for assigned entities
            entities = assignments.get(module.name, set())
            for entity in entities:
                # All triples where entity is subject
                for s, p, o in self.source_graph.triples((entity, None, None)):
                    module_graph.add((s, p, o))

            result.modules[module.name] = module_graph

    def _handle_unmatched(self, result: SplitResult) -> None:
        """Handle entities that weren't assigned to any module.

        Args:
            result: SplitResult with unmatched entities.
        """
        if not result.unmatched_entities:
            return

        if self.config.unmatched.strategy == "error":
            result.success = False
            result.error = (
                f"Unmatched entities ({len(result.unmatched_entities)}): "
                + ", ".join(list(result.unmatched_entities)[:5])
                + ("..." if len(result.unmatched_entities) > 5 else "")
            )
            return

        # Create common module
        common_graph = Graph()

        if self.source_graph is not None:
            # Copy namespace bindings
            for prefix, ns in self.source_graph.namespace_manager.namespaces():
                common_graph.bind(prefix, ns)

            # Add triples for unmatched entities
            for entity_str in result.unmatched_entities:
                entity = URIRef(entity_str)
                for s, p, o in self.source_graph.triples((entity, None, None)):
                    common_graph.add((s, p, o))

                # Record assignment
                result.entity_assignments[entity_str] = self.config.unmatched.common_module

        result.modules[self.config.unmatched.common_module] = common_graph

    def _detect_dependencies(self, result: SplitResult) -> None:
        """Detect cross-module dependencies.

        A module depends on another if it references entities from that module.

        Args:
            result: SplitResult to populate with dependencies.
        """
        if self.source_graph is None:
            return

        for module_name, graph in result.modules.items():
            deps: set[str] = set()

            for s, p, o in graph:
                # Check if object references an entity in another module
                if isinstance(o, URIRef):
                    o_str = str(o)
                    if o_str in result.entity_assignments:
                        other_module = result.entity_assignments[o_str]
                        if other_module != module_name:
                            deps.add(other_module)

            result.dependencies[module_name] = deps

    def _add_imports(self, result: SplitResult) -> None:
        """Add owl:imports declarations to module graphs.

        Args:
            result: SplitResult with module graphs.
        """
        for module in self.config.modules:
            if module.name not in result.modules:
                continue

            graph = result.modules[module.name]

            # Find or create ontology declaration
            ontology_uri = self._get_or_create_ontology_uri(graph, module)

            # Add explicit imports
            for imp in module.imports:
                graph.add((ontology_uri, OWL.imports, URIRef(imp)))

            # Add auto-generated imports from dependencies
            if module.auto_imports:
                deps = result.dependencies.get(module.name, set())
                for dep in deps:
                    # Find the module definition to get its output filename
                    dep_file = self._get_module_file(dep, result)
                    if dep_file:
                        graph.add((ontology_uri, OWL.imports, URIRef(dep_file)))

    def _get_or_create_ontology_uri(self, graph: Graph, module: ModuleDefinition) -> URIRef:
        """Get or create the ontology URI for a module.

        Args:
            graph: Module graph.
            module: Module definition.

        Returns:
            Ontology URI.
        """
        # Look for existing ontology declaration
        for s in graph.subjects(RDF.type, OWL.Ontology):
            return s

        # Create one based on module name
        base_ns = None
        for prefix, ns in graph.namespace_manager.namespaces():
            if prefix == "":
                base_ns = str(ns)
                break

        if base_ns:
            ont_uri = URIRef(base_ns.rstrip("#/"))
        else:
            ont_uri = URIRef(f"http://example.org/{module.name}")

        graph.add((ont_uri, RDF.type, OWL.Ontology))
        return ont_uri

    def _get_module_file(self, module_name: str, result: SplitResult) -> str | None:
        """Get the output filename for a module.

        Args:
            module_name: Name of the module.
            result: SplitResult.

        Returns:
            Output filename or None.
        """
        # Check defined modules
        for module in self.config.modules:
            if module.name == module_name:
                return module.output

        # Check common module
        if module_name == self.config.unmatched.common_module:
            return self.config.unmatched.common_output

        return None

    def _calculate_stats(self, result: SplitResult) -> None:
        """Calculate statistics for each module.

        Args:
            result: SplitResult to populate with stats.
        """
        for module in self.config.modules:
            if module.name not in result.modules:
                continue

            graph = result.modules[module.name]
            stats = self._calculate_module_stats(module.name, module.output, graph, result)
            result.module_stats.append(stats)

        # Stats for common module
        if self.config.unmatched.common_module in result.modules:
            graph = result.modules[self.config.unmatched.common_module]
            stats = self._calculate_module_stats(
                self.config.unmatched.common_module,
                self.config.unmatched.common_output,
                graph,
                result,
            )
            result.module_stats.append(stats)

    def _calculate_module_stats(
        self,
        name: str,
        output: str,
        graph: Graph,
        result: SplitResult,
    ) -> ModuleStats:
        """Calculate statistics for a single module.

        Args:
            name: Module name.
            output: Output filename.
            graph: Module graph.
            result: SplitResult.

        Returns:
            ModuleStats instance.
        """
        # Count classes and properties
        classes = set(graph.subjects(RDF.type, OWL.Class)) | set(
            graph.subjects(RDF.type, RDFS.Class)
        )
        properties = (
            set(graph.subjects(RDF.type, OWL.ObjectProperty))
            | set(graph.subjects(RDF.type, OWL.DatatypeProperty))
            | set(graph.subjects(RDF.type, OWL.AnnotationProperty))
            | set(graph.subjects(RDF.type, RDF.Property))
        )

        # Get imports
        imports = [str(o) for s, p, o in graph.triples((None, OWL.imports, None))]

        # Get dependencies
        deps = list(result.dependencies.get(name, set()))

        return ModuleStats(
            name=name,
            file=output,
            classes=len(classes),
            properties=len(properties),
            triples=len(graph),
            imports=imports,
            dependencies=deps,
        )

    def _split_data(self, result: SplitResult) -> None:
        """Split data files by instance type.

        Instances are assigned to the module containing their rdf:type.

        Args:
            result: SplitResult to populate with data modules.
        """
        if self.config.split_data is None:
            return

        # Load all data files
        data_graph = Graph()
        for data_path in self.config.split_data.sources:
            if data_path.exists():
                data_graph.parse(data_path.as_posix())

        # Create data graphs per module
        data_modules: dict[str, Graph] = {m.name: Graph() for m in self.config.modules}
        if self.config.unmatched.common_module in result.modules:
            data_modules[self.config.unmatched.common_module] = Graph()

        # Copy namespace bindings to all data modules
        for module_name in data_modules:
            for prefix, ns in data_graph.namespace_manager.namespaces():
                data_modules[module_name].bind(prefix, ns)

        # Assign instances by type
        for s, p, o in data_graph.triples((None, RDF.type, None)):
            if isinstance(o, URIRef):
                type_str = str(o)
                if type_str in result.entity_assignments:
                    module_name = result.entity_assignments[type_str]
                    if module_name in data_modules:
                        # Add all triples for this subject
                        for triple in data_graph.triples((s, None, None)):
                            data_modules[module_name].add(triple)

        result.data_modules = data_modules

    def write_modules(self, result: SplitResult) -> None:
        """Write module files to disk.

        Args:
            result: SplitResult with module graphs.
        """
        if self.config.dry_run:
            return

        # Ensure output directory exists
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # Write module files
        for module in self.config.modules:
            if module.name in result.modules:
                output_path = self.config.output_dir / module.output
                result.modules[module.name].serialize(
                    destination=output_path.as_posix(), format="turtle"
                )

        # Write common module
        if self.config.unmatched.common_module in result.modules:
            output_path = self.config.output_dir / self.config.unmatched.common_output
            result.modules[self.config.unmatched.common_module].serialize(
                destination=output_path.as_posix(), format="turtle"
            )

        # Write data modules
        if result.data_modules and self.config.split_data:
            data_dir = self.config.split_data.output_dir or self.config.output_dir
            data_dir.mkdir(parents=True, exist_ok=True)

            for module_name, graph in result.data_modules.items():
                if len(graph) > 0:
                    prefix = self.config.split_data.prefix
                    output_path = data_dir / f"{prefix}{module_name}.ttl"
                    graph.serialize(destination=output_path.as_posix(), format="turtle")

    def write_manifest(self, result: SplitResult) -> None:
        """Write manifest file documenting the split.

        Args:
            result: SplitResult with statistics.
        """
        if self.config.dry_run or not self.config.generate_manifest:
            return

        manifest = {
            "source": str(self.config.source),
            "output_dir": str(self.config.output_dir),
            "modules": [],
            "summary": {
                "total_modules": result.total_modules,
                "total_triples": result.total_triples,
                "unmatched_entities": len(result.unmatched_entities),
            },
        }

        for stats in result.module_stats:
            manifest["modules"].append({
                "name": stats.name,
                "file": stats.file,
                "classes": stats.classes,
                "properties": stats.properties,
                "triples": stats.triples,
                "imports": stats.imports,
                "dependencies": stats.dependencies,
            })

        # Generate dependency graph as ASCII art
        dep_lines = self._format_dependency_graph(result)
        if dep_lines:
            manifest["dependency_graph"] = dep_lines

        manifest_path = self.config.output_dir / "manifest.yml"
        with open(manifest_path, "w") as f:
            yaml.safe_dump(manifest, f, default_flow_style=False, sort_keys=False)

    def _format_dependency_graph(self, result: SplitResult) -> str:
        """Format dependency graph as ASCII tree.

        Args:
            result: SplitResult with dependencies.

        Returns:
            ASCII representation of dependency graph.
        """
        if not result.dependencies:
            return ""

        # Find root modules (those with no dependents)
        all_deps: set[str] = set()
        for deps in result.dependencies.values():
            all_deps.update(deps)

        roots = [m for m in result.modules if m not in all_deps]

        if not roots:
            roots = list(result.modules.keys())[:1]

        lines = []
        for root in roots:
            self._format_tree(root, result.dependencies, lines, "")

        return "\n".join(lines)

    def _format_tree(
        self,
        node: str,
        deps: dict[str, set[str]],
        lines: list[str],
        prefix: str,
        visited: set[str] | None = None,
    ) -> None:
        """Recursively format a dependency tree.

        Args:
            node: Current node.
            deps: Dependency graph.
            lines: Output lines.
            prefix: Current prefix for indentation.
            visited: Already visited nodes (to detect cycles).
        """
        if visited is None:
            visited = set()

        # Get the output file for this node
        file_name = self._get_module_file(node, SplitResult(modules={node: Graph()})) or node
        lines.append(f"{prefix}{file_name}")

        if node in visited:
            return

        visited.add(node)

        # Find modules that depend on this one
        dependents = [m for m, d in deps.items() if node in d]

        for i, dep in enumerate(dependents):
            is_last = i == len(dependents) - 1
            child_prefix = prefix + ("└── " if is_last else "├── ")
            next_prefix = prefix + ("    " if is_last else "│   ")
            self._format_tree(dep, deps, lines, child_prefix, visited.copy())


def split_by_namespace(
    source: Path,
    output_dir: Path,
    dry_run: bool = False,
) -> SplitResult:
    """Convenience function to split an ontology by namespace.

    Automatically detects modules from distinct namespaces in the source.

    Args:
        source: Path to source ontology.
        output_dir: Directory for output modules.
        dry_run: If True, don't write files.

    Returns:
        SplitResult with split information.
    """
    # Load source to detect namespaces
    graph = Graph()
    graph.parse(source.as_posix())

    # Find distinct namespaces used in the ontology
    namespaces: dict[str, str] = {}  # namespace -> prefix
    for prefix, ns in graph.namespace_manager.namespaces():
        ns_str = str(ns)
        # Skip common namespaces
        if any(
            skip in ns_str
            for skip in ["w3.org", "purl.org", "xmlns.com"]
        ):
            continue
        namespaces[ns_str] = prefix or "default"

    # Create module definitions
    modules = []
    for ns, prefix in namespaces.items():
        modules.append(
            ModuleDefinition(
                name=prefix,
                output=f"{prefix}.ttl",
                namespaces=[ns],
            )
        )

    config = SplitConfig(
        source=source,
        output_dir=output_dir,
        modules=modules,
        dry_run=dry_run,
    )

    splitter = OntologySplitter(config)
    result = splitter.split()

    if result.success and not dry_run:
        splitter.write_modules(result)
        splitter.write_manifest(result)

    return result


def create_default_split_config() -> str:
    """Generate default split configuration as YAML string.

    Returns:
        YAML configuration template.
    """
    return '''# rdf-construct split configuration
# See MERGE_GUIDE.md for full documentation

split:
  # Source ontology to split
  source: ontology/split_monolith.ttl

  # Output directory for modules
  output_dir: modules/

  # Module definitions
  modules:
    # Split by explicit class list
    - name: core
      description: "Core upper ontology concepts"
      output: core.ttl
      include:
        classes:
          - ex:Entity
          - ex:Event
          - ex:State
        properties:
          - ex:identifier
          - ex:name
      include_descendants: true

    # Split by namespace
    - name: organisation
      description: "Organisation domain module"
      output: organisation.ttl
      namespaces:
        - "http://example.org/ontology/org#"

    # Module with explicit imports
    - name: building
      description: "Building domain module"
      output: building.ttl
      namespaces:
        - "http://example.org/ontology/building#"
      imports:
        - core.ttl
      auto_imports: true

  # Handling for entities that don't match any module
  unmatched:
    strategy: common  # "common" or "error"
    module: common
    output: common.ttl

  # Generate manifest file
  generate_manifest: true

  # Optional: Split data files by instance type
  # split_data:
  #   sources:
  #     - data/split_instances.ttl
  #   output_dir: data/
  #   prefix: data_
'''