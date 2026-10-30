"""Core split logic for modularising RDF ontologies.

This module provides the OntologySplitter class that:
- Splits a monolithic ontology into multiple modules
- Supports namespace-based and explicit entity-based splitting
- Tracks cross-module dependencies
- Generates owl:imports declarations
- Produces a manifest documenting the split
- Supports data migration by instance type
"""

import re
from collections.abc import Container, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import yaml
from rdflib import BNode, Graph, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, OWL, SKOS
from rdflib.term import Node

from rdf_construct.core.blank_nodes import component_digest
from rdf_construct.core.outdir import OUTPUT_MARKER, mark_output_dir
from rdf_construct.core.output_paths import PlannedOutput, colliding_outputs, outputs_over_inputs
from rdf_construct.core.provenance import WAS_DERIVED_FROM, derivation_targets, stamp_derivation
from rdf_construct.core.serialiser import bnode_closure
from rdf_construct.core.utils import CurieError, in_namespace, resolve_curie
from rdf_construct.core.vocab import ALL_PROPERTY_TYPES, CLASS_TYPES


def select_classes(graph: Graph) -> set[URIRef]:
    """Select all class entities from a graph.

    Args:
        graph: RDF graph to select from.

    Returns:
        Set of URIRefs for classes: every subject typed by one of ``core.vocab.CLASS_TYPES``.
    """
    classes: set[URIRef] = set()
    for class_type in CLASS_TYPES:
        for s in graph.subjects(RDF.type, class_type):
            if isinstance(s, URIRef):
                classes.add(s)
    return classes


def select_properties(graph: Graph) -> set[URIRef]:
    """Select all property entities from a graph.

    Args:
        graph: RDF graph to select from.

    Returns:
        Set of URIRefs for properties: every subject typed by one of
        ``core.vocab.ALL_PROPERTY_TYPES``, so a term declared only ``owl:TransitiveProperty`` or
        ``owl:FunctionalProperty`` is a property too (#176).
    """
    properties: set[URIRef] = set()
    for prop_type in ALL_PROPERTY_TYPES:
        for s in graph.subjects(RDF.type, prop_type):
            if isinstance(s, URIRef):
                properties.add(s)
    return properties


_NAMESPACE_DELIMITERS = "#/:"


def _derived_namespace(iri: str) -> str:
    """The namespace an IRI implies by itself: everything up to its last ``#``, ``/`` or ``:``.

    Args:
        iri: The IRI to cut.

    Returns:
        The IRI up to and including its last delimiter, or the IRI unchanged if it has none.
    """
    cut = max(iri.rfind(d) for d in _NAMESPACE_DELIMITERS)
    return iri[: cut + 1] if cut >= 0 else iri


def _claiming_namespace(iri: str, namespaces: Container[str]) -> str | None:
    """The longest of `namespaces` that contains `iri`, matched as `core.utils.in_namespace` does.

    Every namespace that can contain an IRI is the IRI itself, or the IRI cut just before or just
    after one of its delimiters, so the candidates are looked up rather than tested one by one.
    That keeps the claim linear in the length of the IRI whatever the number of namespaces, and
    independent of the order they were declared in (#177).

    Args:
        iri: The IRI to place.
        namespaces: The candidate namespaces.

    Returns:
        The longest namespace containing `iri`, or None if none does.
    """
    best = iri if iri in namespaces else None
    for i, ch in enumerate(iri):
        if ch in _NAMESPACE_DELIMITERS:
            for candidate in (iri[: i + 1], iri[:i]):
                if candidate in namespaces and (best is None or len(candidate) > len(best)):
                    best = candidate
    return best


def _fallback_name(namespace: str) -> str:
    """A module name for a namespace with no declared prefix: its last path segment.

    ``http://example.org/ontology#`` gives ``ontology``. Characters that are unsafe in a file
    name become ``_``.

    Args:
        namespace: The namespace IRI.

    Returns:
        A non-empty name.
    """
    segments = [s for s in re.split(r"[#/:]", namespace.rstrip(_NAMESPACE_DELIMITERS)) if s]
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", segments[-1] if segments else "").strip(".")
    return name or "namespace"


def source_ontologies(graph: Graph) -> list[URIRef]:
    """The ontology IRIs a source declares: its named ``owl:Ontology`` subjects, sorted.

    Args:
        graph: The source graph.

    Returns:
        The IRIs, sorted. A blank-node header has no IRI and is left out.
    """
    return sorted(s for s in graph.subjects(RDF.type, OWL.Ontology) if isinstance(s, URIRef))


def _host(iri: str) -> str:
    """The authority part of an IRI, lower-cased: ``www.w3.org`` for W3C's vocabularies."""
    return urlsplit(iri).netloc.lower()


#: Hosts where many publishers each own a part of the space: a persistent-identifier service, or
#: W3C's, whose vocabularies are separate ontologies with separate owners. On these, sharing the
#: host says nothing about who owns a namespace (#385's panel). ``purl.obolibrary.org`` is not
#: here: OBO terms all share ``…/obo/``, so no test by namespace can tell one ontology's from
#: another's.
SHARED_HOSTS: frozenset[str] = frozenset({"purl.org", "w3id.org", "www.w3.org"})


def _owns(ontology: URIRef, namespace: str) -> bool:
    """Whether an ontology owns a namespace: on its own host, or within its own IRI.

    On an ordinary host, the whole host is the ontology's. On one of :data:`SHARED_HOSTS`, only
    the space under the ontology's own IRI is: ``http://purl.org/myont`` owns
    ``http://purl.org/myont#`` but not ``http://purl.org/dc/terms/``.
    """
    host = _host(str(ontology))
    if host != _host(namespace):
        return False
    if host in SHARED_HOSTS:
        return in_namespace(
            _lower_authority(namespace), _lower_authority(str(ontology)).rstrip("#/")
        )
    return True


def _lower_authority(iri: str) -> str:
    """The IRI with its scheme and host lower-cased, which RFC 3986 compares without case."""
    parts = urlsplit(iri)
    authority = f"{parts.scheme}://{parts.netloc}"
    if not iri.startswith(authority):
        return iri
    return authority.lower() + iri[len(authority) :]


def is_borrowed(namespace: str, ontologies: list[URIRef]) -> bool:
    """Whether a namespace belongs to someone other than the source (#383, #178).

    A namespace is borrowed when no ontology the source declares owns it (:func:`_owns`):
    ``dcterms:`` or GeoSPARQL's in a file whose ontology lives elsewhere, or ``dcterms:`` in one
    that lives elsewhere on ``purl.org``. A source that declares no ontology gives nothing to
    judge by, so nothing is borrowed.

    Args:
        namespace: The namespace IRI.
        ontologies: The source's ontology IRIs, from :func:`source_ontologies`.

    Returns:
        True if the namespace is borrowed.
    """
    return bool(ontologies) and not any(_owns(o, namespace) for o in ontologies)


#: The reasons a subject goes to the unmatched module, as the run reports them (#176)
REASON_NO_MODULE = "a class or property no module claims"
REASON_BORROWED = "a borrowed vocabulary's term"
REASON_UNTYPED = "no rdf:type"
REASON_FOREIGN_TYPE = "typed only by classes no module holds"
REASON_TYPE_UNMATCHED = "typed by an unmatched class"
REASON_TYPES_SPLIT = "typed by classes in more than one module"
REASON_SCHEME_NO_MODULE = "a concept scheme in no module's namespace"
REASON_SCHEME_UNMATCHED = "a concept in an unmatched scheme"
REASON_SCHEMES_SPLIT = "a concept in schemes in more than one module"
REASON_CONCEPT_NO_MODULE = "a concept with no scheme, in no module's namespace"
REASON_BNODE_SPLIT = "a blank-node structure naming terms of more than one module"
REASON_BNODE_NONE = "a blank-node structure naming no module's terms"

#: How a module's ontology IRI was arrived at: the four rungs of #178's ladder
RUNG_CONFIG = "config"
RUNG_NAMESPACE = "namespace"
RUNG_NAMESPACE_UNCHECKED = "namespace, unchecked: the source declares no ontology"
RUNG_SOURCE = "source ontology"
RUNG_NONE = "none"


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
        imports: Explicit owl:imports to add: ontology IRIs or CURIEs, never file names.
        auto_imports: Whether to generate imports from detected dependencies.
        ontology_iri: The module's ontology IRI, the first rung of the ladder (#178).
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
    ontology_iri: str | None = None

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
            ontology_iri=data.get("ontology_iri"),
        )


@dataclass
class UnmatchedStrategy:
    """Configuration for handling entities that don't match any module.

    Attributes:
        strategy: Either 'common' (collect them in one module) or 'error' (fail).
        common_module: Name of the module that collects them if strategy is 'common'.
        common_output: Output filename for that module.
    """

    strategy: str = "common"  # "common" or "error"
    common_module: str = "unmatched"
    common_output: str = "unmatched.ttl"


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
        output_dir_named: Whether the configuration file set ``output_dir`` itself.
    """

    source: Path
    output_dir: Path
    modules: list[ModuleDefinition] = field(default_factory=list)
    unmatched: UnmatchedStrategy = field(default_factory=UnmatchedStrategy)
    split_data: SplitDataConfig | None = None
    generate_manifest: bool = True
    dry_run: bool = False
    output_dir_named: bool = False

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
        modules = [ModuleDefinition.from_dict(m) for m in split_data.get("modules", [])]

        # Parse unmatched strategy
        unmatched_data = split_data.get("unmatched", {})
        unmatched = UnmatchedStrategy(
            strategy=unmatched_data.get("strategy", "common"),
            common_module=unmatched_data.get("module", "unmatched"),
            common_output=unmatched_data.get("output", "unmatched.ttl"),
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
            output_dir_named="output_dir" in split_data,
        )


MANIFEST_NAME = "manifest.yml"
"""The manifest's file name, in the output directory."""


class SplitOutputError(ValueError):
    """A split whose outputs collide, leave their directory or replace an input (#413).

    Raised before the source is parsed, so nothing has been written.

    Attributes:
        problems: Every problem the plan found, one line each.
    """

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Nothing was written:\n  " + "\n  ".join(problems))


@dataclass(frozen=True)
class _PlannedFile:
    """A file a split means to write, as the config gives it.

    Attributes:
        label: What the file is, as a refusal names it.
        given: The path as written, relative to ``directory``.
        directory: The directory it must stay inside.
        directory_key: What names ``directory`` (``output_dir``, the data directory), for the
            advice.
    """

    label: str
    given: str
    directory: Path
    directory_key: str

    @property
    def path(self) -> Path:
        """Where the file is written."""
        return self.directory / self.given


def data_output_dir(config: SplitConfig) -> Path:
    """The directory data modules are written to: ``split_data``'s own, else ``output_dir``.

    Args:
        config: Split configuration.

    Returns:
        The data directory.
    """
    if config.split_data and config.split_data.output_dir:
        return config.split_data.output_dir
    return config.output_dir


def _plan_files(config: SplitConfig, problems: list[str]) -> list[_PlannedFile]:
    """Work out every file the split could write, refusing names that clash (#382, #413).

    The plan is the worst case, made from the config alone: the unmatched module whenever the
    strategy is ``common``, and a data file for every module whenever data is given. A config
    that is wrong is wrong whatever the source holds.

    Two modules with one name are one module to the splitter: their subjects merge, and they
    share an ontology IRI and a data file. A name is compared without case, as the data file
    named after it is. A module refused by name is not planned further, so each mistake is
    reported once.

    Args:
        config: Split configuration.
        problems: Where a name clash is reported.

    Returns:
        The planned files, in the order they would be written.
    """
    out = config.output_dir
    files: list[_PlannedFile] = []
    names: dict[str, ModuleDefinition] = {}
    for module in config.modules:
        first = names.setdefault(module.name.casefold(), module)
        if first is not module:
            problems.append(
                f"Modules {first.name!r} and {module.name!r} share a name, so they would be "
                "written as one module. Rename one."
            )
            continue
        files.append(
            _PlannedFile(
                f"module {module.name!r} (output: {module.output})",
                module.output,
                out,
                "output_dir",
            )
        )

    unmatched = config.unmatched
    common = unmatched.strategy == "common"
    if common:
        for module in names.values():
            if (
                module.name.casefold() == unmatched.common_module.casefold()
                or module.output.casefold() == unmatched.common_output.casefold()
            ):
                problems.append(
                    f"The unmatched module {unmatched.common_module!r} "
                    f"({unmatched.common_output}) would overwrite module {module.name!r} "
                    f"({module.output}). Give the unmatched module another name with "
                    "--common-name or unmatched: module:."
                )
                common = False
                break
    if common:
        files.append(
            _PlannedFile(
                f"the unmatched module {unmatched.common_module!r} "
                f"(output: {unmatched.common_output})",
                unmatched.common_output,
                out,
                "output_dir",
            )
        )

    if config.generate_manifest:
        files.append(
            _PlannedFile(f"the manifest ({MANIFEST_NAME})", MANIFEST_NAME, out, "output_dir")
        )
    files.append(
        _PlannedFile(f"split's marker ({OUTPUT_MARKER})", OUTPUT_MARKER, out, "output_dir")
    )

    if config.split_data and config.split_data.sources:
        prefix = config.split_data.prefix
        data_dir = data_output_dir(config)
        data_names = [module.name for module in names.values()]
        if common:
            data_names.append(unmatched.common_module)
        for name in data_names:
            files.append(
                _PlannedFile(
                    f"the data file for module {name!r} ({prefix}{name}.ttl: prefix + name)",
                    f"{prefix}{name}.ttl",
                    data_dir,
                    "the data directory",
                )
            )
    return files


def check_split_outputs(config: SplitConfig, inputs: Sequence[Path] = ()) -> None:
    """Refuse a split whose outputs would collide, leave their directory or replace an input.

    Call it before the source is parsed (#413). Every file the split could write is planned
    from the config: each module's ``output:``, the unmatched module's, the manifest, the
    ``.rdf-construct`` marker and the data files. Each must be a relative path that resolves
    inside its directory, symbolic links followed; no two may be one file
    (``core.output_paths``, so ``A.ttl`` and ``a.ttl`` collide); and none may be an input.
    ``--overwrite`` permits none of these: it only lets a run into a default directory that
    holds other files (#261).

    Args:
        config: Split configuration, with every command-line override applied.
        inputs: Files the run reads besides the source and the data, such as the config file.

    Raises:
        SplitOutputError: Listing every problem found.
    """
    problems: list[str] = []
    files: list[_PlannedFile] = []
    for planned in _plan_files(config, problems):
        if Path(planned.given).is_absolute():
            problems.append(
                f"{planned.label} is an absolute path. Give a path inside "
                f"{planned.directory_key} ({planned.directory})."
            )
            continue
        base = planned.directory.resolve()
        resolved = planned.path.resolve()
        if resolved == base or not resolved.is_relative_to(base):
            problems.append(
                f"{planned.label} is outside {planned.directory_key} ({planned.directory}): it "
                f"resolves to {resolved}. Give a path inside it, or move "
                f"{planned.directory_key} up."
            )
            continue
        if resolved.is_dir():
            problems.append(f"{planned.label} names a directory, {planned.path}.")
            continue
        files.append(planned)

    outputs = [PlannedOutput(planned.path) for planned in files]
    # Two files on one path are equal PlannedOutputs, so each is told apart by identity
    labels = {id(output): planned.label for output, planned in zip(outputs, files, strict=True)}
    for group in colliding_outputs(outputs):
        named = " and ".join(labels[id(output)] for output in group)
        problems.append(f"{named} name one file, {group[0].path}. Choose different paths.")

    read = [config.source, *(config.split_data.sources if config.split_data else []), *inputs]
    for output, existing in outputs_over_inputs(outputs, read):
        problems.append(
            f"{labels[id(output)]} would replace the input {existing}. Choose another path."
        )

    if problems:
        raise SplitOutputError(problems)


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
        ontology_iri: The module's ontology IRI, or None if it has no header.
        rung: Which rung of the ladder gave that IRI (#178).
    """

    name: str
    file: str
    classes: int = 0
    properties: int = 0
    triples: int = 0
    imports: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    ontology_iri: str | None = None
    rung: str = RUNG_NONE


@dataclass
class SplitResult:
    """Result of a split operation.

    Attributes:
        modules: Dictionary of module name -> Graph.
        module_stats: Statistics per module.
        entity_assignments: Mapping of entity URI -> module name.
        unmatched_entities: Subjects not assigned to any module: IRIs, and a label for each
            blank-node structure.
        unmatched_reasons: Why each of `unmatched_entities` is unmatched.
        dependencies: Cross-module dependency graph.
        success: Whether split completed without errors.
        error: Error message if success is False.
        data_modules: Split data graphs by module (if data splitting enabled).
        shared_blank_nodes: Blank nodes copied into more than one module, because subjects in
            different modules refer to them.
        warnings: What the run could not do, such as a module left without a header.
        module_iris: Module name -> its ontology IRI (or None) and the rung that gave it.
    """

    modules: dict[str, Graph] = field(default_factory=dict)
    module_stats: list[ModuleStats] = field(default_factory=list)
    entity_assignments: dict[str, str] = field(default_factory=dict)
    unmatched_entities: set[str] = field(default_factory=set)
    unmatched_reasons: dict[str, str] = field(default_factory=dict)
    dependencies: dict[str, set[str]] = field(default_factory=dict)
    success: bool = True
    error: str | None = None
    data_modules: dict[str, Graph] = field(default_factory=dict)
    shared_blank_nodes: int = 0
    warnings: list[str] = field(default_factory=list)
    module_iris: dict[str, tuple[str | None, str]] = field(default_factory=dict)

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
    2. Assigns classes and properties to modules based on configuration
    3. Routes every other subject: individuals by their rdf:type, SKOS concepts by their scheme
    4. Handles unmatched subjects per strategy
    5. Detects cross-module dependencies
    6. Gives each module an ontology IRI, a derivation stamp and owl:imports
    7. Writes module files
    8. Produces a manifest documenting the split

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
        self.namespace_owner: dict[str, str] = {}  # namespace -> module that claims it
        self.ontologies: list[URIRef] = []  # the source's ontology IRIs
        self.unmatched_subjects: list[Node] = []

    def split(self) -> SplitResult:
        """Execute the split operation.

        Returns:
            SplitResult with module graphs and statistics.

        Raises:
            SplitOutputError: When the config's outputs collide, leave their directory or would
                replace an input, before the source is parsed (#413).
        """
        check_split_outputs(self.config)
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
        self.ontologies = source_ontologies(self.source_graph)

        # Assign entities to modules
        assignments = self._assign_entities(result)

        if not result.success:
            return result

        # Route everything that is not a class or a property (#176)
        self._route_residue(assignments, result)

        # Refuse unmatched subjects the strategy does not allow, before anything is built
        if result.unmatched_entities:
            self._check_unmatched(result)
            if not result.success:
                return result

        # Create module graphs
        self._create_module_graphs(assignments, result)

        # Handle unmatched entities
        if result.unmatched_entities:
            self._handle_unmatched(result)

        # Detect dependencies, then give each module its identity and imports (#178)
        self._detect_dependencies(result)
        self._add_headers(result)

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

        # The file's own prefixes plus the core five, never rdflib's wider table (P10, #177)
        graph = Graph(bind_namespaces="core")

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

        # The longest namespace that contains an entity claims it, whatever order the modules
        # come in; two modules naming the same namespace leave it to the first (#177)
        namespace_owner: dict[str, str] = {}
        for module in self.config.modules:
            for ns in module.namespaces:
                namespace_owner.setdefault(ns, module.name)
        self.namespace_owner = namespace_owner
        owned: dict[str, list[URIRef]] = {}
        for entity in all_entities:
            ns_claim = _claiming_namespace(str(entity), namespace_owner)
            if ns_claim is not None:
                owned.setdefault(namespace_owner[ns_claim], []).append(entity)

        # A listed CURIE whose prefix the source does not bind is refused, not matched to nothing,
        # and so is an import or ontology IRI that is neither an IRI nor a CURIE, such as a file name
        try:
            for module in self.config.modules:
                iris = [*module.imports, *([module.ontology_iri] if module.ontology_iri else [])]
                for curie in [*module.classes, *module.properties, *iris]:
                    self._expand_curie(curie)
        except CurieError as e:
            result.success = False
            result.error = str(e)
            return {}

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
            for entity in owned.get(module.name, []):
                if str(entity) not in result.entity_assignments:
                    assignments[module.name].add(entity)
                    result.entity_assignments[str(entity)] = module.name

        # Find unmatched entities
        for entity in sorted(all_entities):
            if str(entity) not in result.entity_assignments:
                reason = (
                    REASON_BORROWED if is_borrowed(entity, self.ontologies) else REASON_NO_MODULE
                )
                self._unmatch(entity, str(entity), reason, result)

        return assignments

    def _unmatch(self, subject: Node, label: str, reason: str, result: SplitResult) -> None:
        """Send a subject to the unmatched module, recording why.

        Args:
            subject: The subject: an IRI, or the root of a blank-node structure.
            label: How the run names it.
            reason: Why no module took it.
            result: SplitResult to record it in.
        """
        self.unmatched_subjects.append(subject)
        result.unmatched_entities.add(label)
        result.unmatched_reasons[label] = reason

    def _namespace_module(self, subject: URIRef) -> str | None:
        """The module whose namespace claims `subject`, as `_assign_entities` claims entities."""
        claim = _claiming_namespace(str(subject), self.namespace_owner)
        return self.namespace_owner[claim] if claim is not None else None

    def _route_residue(self, assignments: dict[str, set[URIRef]], result: SplitResult) -> None:
        """Route every subject that is not a class or a property (#176).

        - A concept scheme goes to the module claiming its namespace, and its concepts follow
          ``skos:inScheme``, so the scheme is the unit. A concept in no scheme goes to the module
          claiming its namespace, if there is one.
        - Any other named subject goes to the module owning its ``rdf:type``: an individual.
        - A blank-node structure no named subject refers to (``owl:AllDisjointClasses``, a
          general class axiom) goes to the one module owning the terms it names.
        - An ``owl:Ontology`` header goes nowhere: each module gets its own (#178).

        Whatever has no single module goes to the unmatched module, with its reason.

        Args:
            assignments: Module name -> subjects, extended in place.
            result: SplitResult with the class and property assignments so far.
        """
        if self.source_graph is None:
            return
        graph = self.source_graph
        unmatched = None
        placed: dict[Node, str | None] = {
            URIRef(e): m for e, m in result.entity_assignments.items()
        }
        placed.update({URIRef(e): unmatched for e in result.unmatched_entities})
        headers = set(graph.subjects(RDF.type, OWL.Ontology))

        def send(subject: URIRef, module: str | None, reason: str) -> None:
            placed[subject] = module
            if module is None:
                self._unmatch(subject, str(subject), reason, result)
            else:
                assignments[module].add(subject)
                result.entity_assignments[str(subject)] = module

        def named(subjects: Any) -> list[URIRef]:
            return sorted(
                {s for s in subjects if isinstance(s, URIRef) and s not in placed} - headers
            )

        schemes = named(graph.subjects(RDF.type, SKOS.ConceptScheme))
        for scheme in schemes:
            send(scheme, self._namespace_module(scheme), REASON_SCHEME_NO_MODULE)

        for concept in named(graph.subjects(RDF.type, SKOS.Concept)):
            # skos:topConceptOf is a sub-property of skos:inScheme, and skos:hasTopConcept its
            # inverse, so either ties a concept to its scheme as firmly as skos:inScheme does
            in_schemes = {
                *graph.objects(concept, SKOS.inScheme),
                *graph.objects(concept, SKOS.topConceptOf),
                *graph.subjects(SKOS.hasTopConcept, concept),
            }
            owners = {placed[s] for s in in_schemes if s in schemes}
            if len(owners) > 1:
                send(concept, unmatched, REASON_SCHEMES_SPLIT)
            elif owners:
                send(concept, owners.pop(), REASON_SCHEME_UNMATCHED)
            else:
                send(concept, self._namespace_module(concept), REASON_CONCEPT_NO_MODULE)

        for subject in named(graph.subjects()):
            types = set(graph.objects(subject, RDF.type))
            owners = {placed[t] for t in types if t in placed}
            if len(owners) > 1:
                send(subject, unmatched, REASON_TYPES_SPLIT)
            elif owners:
                send(subject, owners.pop(), REASON_TYPE_UNMATCHED)
            else:
                send(subject, unmatched, REASON_FOREIGN_TYPE if types else REASON_UNTYPED)

        # Blank nodes no named subject reaches: roots first, then any cycle left over, each in
        # the order of its content, since a blank node's label differs from parse to parse
        reached = set(bnode_closure(graph, [*placed, *headers]))
        blank = {s for s in graph.subjects() if isinstance(s, BNode)} - reached
        referred = {o for o in graph.objects() if isinstance(o, BNode)}

        def by_content(root: Node) -> str:
            structure = Graph()
            for node in [root, *bnode_closure(graph, [root])]:
                for triple in graph.triples((node, None, None)):
                    structure.add(triple)
            return component_digest(structure)

        roots = sorted(blank - referred, key=by_content) + sorted(blank & referred, key=by_content)
        structures = 0
        for root in roots:
            if root in reached:
                continue
            nodes = [root, *bnode_closure(graph, [root])]
            reached.update(nodes)
            terms = {
                term
                for node in nodes
                for _, _, term in graph.triples((node, None, None))
                if isinstance(term, URIRef) and term in placed
            }
            owners = {placed[t] for t in terms}
            module = owners.pop() if len(owners) == 1 else None
            if module is not None:
                assignments[module].add(root)  # type: ignore[arg-type]
                continue
            structures += 1
            kinds = sorted(graph.qname(str(t)) for t in graph.objects(root, RDF.type))
            label = f"blank-node structure {structures} ({', '.join(kinds) or 'untyped'})"
            reason = REASON_BNODE_SPLIT if len(owners) > 1 else REASON_BNODE_NONE
            self._unmatch(root, label, reason, result)

    def _check_unmatched(self, result: SplitResult) -> None:
        """Refuse unmatched subjects when the strategy is ``error``.

        An unmatched module that would overwrite another (#382) is refused before the parse,
        by `check_split_outputs`.

        Args:
            result: SplitResult with unmatched entities, marked as failed if refused.
        """
        unmatched = self.config.unmatched
        if unmatched.strategy == "error":
            result.success = False
            labels = sorted(result.unmatched_entities)
            result.error = (
                f"Unmatched entities ({len(labels)}): "
                + ", ".join(labels[:5])
                + ("..." if len(labels) > 5 else "")
            )

    def _expand_curie(self, curie: str) -> URIRef:
        """Expand a CURIE to a full URI using the source graph's namespace bindings.

        The bindings are the source file's own prefixes plus the core five (see `_load_source`),
        so ``org:`` means the file's ``org:``, never rdflib's.

        Args:
            curie: CURIE or full URI string.

        Returns:
            URIRef of the expanded URI.

        Raises:
            CurieError: If `curie` is a CURIE whose prefix the source does not bind.
        """
        if self.source_graph is None:
            return URIRef(curie)

        prefixes = {p: str(ns) for p, ns in self.source_graph.namespace_manager.namespaces()}
        return resolve_curie(prefixes, curie)

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
            # A bare Graph() would re-import rdflib's prefix table and write org1: (P10)
            module_graph = Graph(bind_namespaces="core")

            # Copy namespace bindings
            for prefix, ns in self.source_graph.namespace_manager.namespaces():
                module_graph.bind(prefix, ns)

            # Add triples for assigned entities, with the blank nodes they describe (#176)
            self._copy_subjects(sorted(assignments.get(module.name, set())), module_graph)

            result.modules[module.name] = module_graph

        self._count_shared_blank_nodes(result)

    def _copy_subjects(self, subjects: Sequence[Node], graph: Graph) -> None:
        """Copy each subject's triples into `graph`, with every blank node they reach.

        A blank node belongs to the description of whatever refers to it, so a module that took
        ``ex:Building rdfs:subClassOf [ … ]`` without the restriction's own triples would assert
        ``Building ⊑ ⊤`` instead (#176).

        Args:
            subjects: The subjects, named or the roots of blank-node structures.
            graph: The module graph, extended in place.
        """
        if self.source_graph is None:
            return
        for subject in [*subjects, *bnode_closure(self.source_graph, list(subjects))]:
            for triple in self.source_graph.triples((subject, None, None)):
                graph.add(triple)

    def _count_shared_blank_nodes(self, result: SplitResult) -> None:
        """Count the blank nodes that more than one module holds a copy of.

        Args:
            result: SplitResult with every module graph built.
        """
        holders: dict[Node, int] = {}
        for graph in result.modules.values():
            for node in {s for s in graph.subjects() if isinstance(s, BNode)}:
                holders[node] = holders.get(node, 0) + 1
        result.shared_blank_nodes = sum(1 for count in holders.values() if count > 1)

    def _handle_unmatched(self, result: SplitResult) -> None:
        """Handle entities that weren't assigned to any module.

        Args:
            result: SplitResult with unmatched entities.
        """
        if not result.unmatched_entities:
            return

        # Create common module
        common_graph = Graph(bind_namespaces="core")

        if self.source_graph is not None:
            # Copy namespace bindings
            for prefix, ns in self.source_graph.namespace_manager.namespaces():
                common_graph.bind(prefix, ns)

            # Add triples for unmatched subjects, with the blank nodes they describe
            self._copy_subjects(self.unmatched_subjects, common_graph)

            # Record assignment
            for subject in self.unmatched_subjects:
                if isinstance(subject, URIRef):
                    result.entity_assignments[str(subject)] = self.config.unmatched.common_module

        result.modules[self.config.unmatched.common_module] = common_graph
        self._count_shared_blank_nodes(result)

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

    def _add_headers(self, result: SplitResult) -> None:
        """Give each module an ontology header, a derivation stamp and its imports (#178).

        The IRI comes from :meth:`_module_iri`'s ladder. The header holds ``a owl:Ontology``,
        ``prov:wasDerivedFrom`` naming the source as ``core.provenance.derivation_targets`` names
        it, and ``owl:imports`` naming the ontology IRIs of the modules it depends on. Nothing of
        the source's own header is copied, ``owl:versionIRI`` included: a module is not a version
        of the source. A module with no IRI gets no header, and cannot be imported; both are
        reported as warnings.

        Args:
            result: SplitResult with module graphs and dependencies.
        """
        if self.source_graph is None:
            return
        source = self.source_graph

        targets = sorted(
            {
                t
                for o in source.subjects(RDF.type, OWL.Ontology)
                for t in derivation_targets(source, o)
            }
        )
        # PROV-O types the stamp's property itself; a source that says so keeps saying so (P13)
        stamp_description = list(source.triples((WAS_DERIVED_FROM, None, None)))

        iris: dict[str, URIRef | None] = {}
        for name in result.modules:
            iri, rung = self._module_iri(name)
            iris[name] = iri
            result.module_iris[name] = (str(iri) if iri is not None else None, rung)
            if iri is None:
                result.warnings.append(
                    f"{name}: no ontology IRI to give it, so it is written without a header. "
                    "Set ontology_iri: for it in a config."
                )

        for name, graph in result.modules.items():
            module = next((m for m in self.config.modules if m.name == name), None)
            imports: list[URIRef] = []
            if module is not None:
                imports += [self._expand_curie(imp) for imp in module.imports]
            if module is None or module.auto_imports:
                for dep in sorted(result.dependencies.get(name, set())):
                    dep_iri = iris.get(dep)
                    if dep_iri is None:
                        result.warnings.append(
                            f"{name} depends on {dep}, which has no ontology IRI, "
                            "so it cannot import it."
                        )
                    elif dep_iri not in imports:
                        imports.append(dep_iri)

            iri = iris[name]
            if iri is None:
                continue
            graph.add((iri, RDF.type, OWL.Ontology))
            for imp in imports:
                graph.add((iri, OWL.imports, imp))
            if targets:
                for triple in stamp_description:
                    graph.add(triple)
                stamp_derivation(graph, iri, targets)

    def _module_iri(self, name: str) -> tuple[URIRef | None, str]:
        """A module's ontology IRI and the rung of #178's ladder that gave it.

        1. ``ontology_iri:`` in the module's config.
        2. The module's own namespace, ``#`` or ``/`` stripped, when it has exactly one. Not when
           that is the source's own ontology IRI, since a module is not the source, and not when
           the namespace is borrowed (:func:`is_borrowed`), since it would claim someone else's.
           A source that declares no ontology cannot be checked against, and the rung says so.
        3. ``<source ontology IRI>/<module name>``: the source ontology whose IRI contains the
           module's namespace (the longest), else the source's only ontology.
        4. None: no header.

        A derived IRI (rungs 2 and 3) that the source already uses, as a term or otherwise, is
        skipped: the header would be punned onto that term.

        Never ``http://example.org/<module>``.

        Args:
            name: The module's name.

        Returns:
            The IRI, or None, and the rung.
        """
        module = next((m for m in self.config.modules if m.name == name), None)
        if module is not None and module.ontology_iri:
            return self._expand_curie(module.ontology_iri), RUNG_CONFIG

        namespaces = module.namespaces if module is not None else []
        own = {str(o).rstrip("#/") for o in self.ontologies}
        if len(namespaces) == 1:
            candidate = namespaces[0].rstrip("#/")
            if candidate and candidate not in own and not self._in_use(URIRef(candidate)):
                if not self.ontologies:
                    return URIRef(candidate), RUNG_NAMESPACE_UNCHECKED
                if not is_borrowed(candidate, self.ontologies):
                    return URIRef(candidate), RUNG_NAMESPACE

        containing = [
            o for o in self.ontologies if any(in_namespace(ns, str(o)) for ns in namespaces)
        ]
        if containing:
            base: URIRef | None = max(containing, key=lambda o: len(str(o)))
        elif len(self.ontologies) == 1:
            base = self.ontologies[0]
        else:
            base = None
        if base is not None:
            minted = URIRef(f"{str(base).rstrip('#/')}/{quote(name, safe='-._~')}")
            if not self._in_use(minted):
                return minted, RUNG_SOURCE
        return None, RUNG_NONE

    def _in_use(self, iri: URIRef) -> bool:
        """Whether the source uses `iri` anywhere: as a subject, a predicate or an object."""
        graph = self.source_graph
        if graph is None:
            return False
        return (
            (iri, None, None) in graph or (None, iri, None) in graph or (None, None, iri) in graph
        )

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

    def _has_common_module(self, result: SplitResult) -> bool:
        """Whether `result` holds a common module that is not also a defined module.

        A namespace module may be called ``common`` too; it is then reported and written once,
        as itself.

        Args:
            result: SplitResult.

        Returns:
            True if the common module must be reported and written separately.
        """
        name = self.config.unmatched.common_module
        return name in result.modules and all(m.name != name for m in self.config.modules)

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
        if self._has_common_module(result):
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
        # Count classes and properties, leaving out the derivation stamp's own declaration
        classes = select_classes(graph)
        properties = select_properties(graph)
        if self.source_graph is not None and WAS_DERIVED_FROM not in select_properties(
            self.source_graph
        ):
            properties.discard(WAS_DERIVED_FROM)

        # Get imports
        imports = [str(o) for s, p, o in graph.triples((None, OWL.imports, None))]

        # Get dependencies
        deps = list(result.dependencies.get(name, set()))

        iri, rung = result.module_iris.get(name, (None, RUNG_NONE))
        return ModuleStats(
            name=name,
            file=output,
            classes=len(classes),
            properties=len(properties),
            triples=len(graph),
            imports=imports,
            dependencies=deps,
            ontology_iri=iri,
            rung=rung,
        )

    def _split_data(self, result: SplitResult) -> None:
        """Split data files by instance type.

        Instances are assigned to the module containing their rdf:type.

        Args:
            result: SplitResult to populate with data modules.
        """
        if self.config.split_data is None:
            return

        # Load all data files: their own prefixes plus the core five, never rdflib's table (P10)
        data_graph = Graph(bind_namespaces="core")
        for data_path in self.config.split_data.sources:
            if data_path.exists():
                data_graph.parse(data_path.as_posix())

        # Create data graphs per module, bound the same way, or org: comes back as org1:
        data_modules: dict[str, Graph] = {
            m.name: Graph(bind_namespaces="core") for m in self.config.modules
        }
        if self.config.unmatched.common_module in result.modules:
            data_modules[self.config.unmatched.common_module] = Graph(bind_namespaces="core")

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

        The output directory is marked as ``split``'s own with a ``.rdf-construct`` file, written
        just before the first module (#261, see ``rdf_construct.core.outdir``). A dry run writes
        nothing, the marker included.

        Args:
            result: SplitResult with module graphs.
        """
        if self.config.dry_run:
            return

        # Ensure output directory exists, and mark it as split's own before the first file (#261)
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        mark_output_dir(self.config.output_dir, "split")

        # Write module files. check_split_outputs approved each resolved path, inside its
        # directory, so that is the path written: sub/../x.ttl needs no sub/, and leaves none
        for module in self.config.modules:
            if module.name in result.modules:
                output_path = (self.config.output_dir / module.output).resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                result.modules[module.name].serialize(
                    destination=output_path.as_posix(), format="turtle"
                )

        # Write common module
        if self._has_common_module(result):
            output_path = (self.config.output_dir / self.config.unmatched.common_output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result.modules[self.config.unmatched.common_module].serialize(
                destination=output_path.as_posix(), format="turtle"
            )

        # Write data modules, creating their directory only if there is data to write
        if any(len(g) for g in result.data_modules.values()) and self.config.split_data:
            data_dir = data_output_dir(self.config)
            data_dir.mkdir(parents=True, exist_ok=True)

            for module_name, graph in result.data_modules.items():
                if len(graph) > 0:
                    prefix = self.config.split_data.prefix
                    output_path = (data_dir / f"{prefix}{module_name}.ttl").resolve()
                    output_path.parent.mkdir(parents=True, exist_ok=True)
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
            manifest["modules"].append(
                {
                    "name": stats.name,
                    "file": stats.file,
                    "classes": stats.classes,
                    "properties": stats.properties,
                    "triples": stats.triples,
                    "imports": stats.imports,
                    "dependencies": stats.dependencies,
                }
            )

        # Generate dependency graph as ASCII art
        dep_lines = self._format_dependency_graph(result)
        if dep_lines:
            manifest["dependency_graph"] = dep_lines

        manifest_path = self.config.output_dir / MANIFEST_NAME
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
    unmatched: UnmatchedStrategy | None = None,
) -> SplitResult:
    """Convenience function to split an ontology by namespace.

    Automatically detects modules from the namespaces the source's classes, properties and SKOS
    concept schemes live in (#177, #176). An entity belongs to the longest namespace the file
    declares that contains it, or otherwise to the namespace its own IRI implies, cut after its
    last ``#``, ``/`` or ``:``. Each namespace with at least one entity is a module; an empty file
    gives none. A borrowed namespace (:func:`is_borrowed`), such as ``dcterms:`` in a file that
    declares a ``dcterms:title`` it uses, makes no module: its declarations go to the unmatched
    module (#383). Everything else is routed as :meth:`OntologySplitter._route_residue` says.

    A module is named after the prefix the file declares for its namespace, read without rdflib's
    built-in bindings. A namespace with no prefix, or only the empty prefix ``:``, is named after
    its last path segment. Declared prefixes take their names first; where names then clash
    (compared without case, since they become file names), the later namespaces in sorted IRI
    order get ``-2``, ``-3``, ….

    Args:
        source: Path to source ontology.
        output_dir: Directory for output modules.
        dry_run: If True, don't write files.
        unmatched: What to do with subjects no module takes. Defaults to an ``unmatched`` module.

    Returns:
        SplitResult with split information.
    """
    # Load source with exactly the prefixes its author declared, to name modules by
    graph = Graph(bind_namespaces="none")
    graph.parse(source.as_posix())

    declared: dict[str, str] = {}  # namespace -> prefix, "" for the empty prefix
    for prefix, bound in graph.namespace_manager.namespaces():
        declared[str(bound)] = prefix

    # Find the distinct namespaces the ontology's entities and concept schemes use
    ontologies = source_ontologies(graph)
    schemes = {s for s in graph.subjects(RDF.type, SKOS.ConceptScheme) if isinstance(s, URIRef)}
    used: set[str] = set()
    for entity in select_classes(graph) | select_properties(graph) | schemes:
        iri = str(entity)
        namespace = _claiming_namespace(iri, declared) or _derived_namespace(iri)
        if not is_borrowed(namespace, ontologies):
            used.add(namespace)

    # Name them: declared prefixes first, then fallbacks, each in sorted namespace order
    names: dict[str, str] = {}  # namespace -> module name
    taken: set[str] = set()
    for ns in sorted(used, key=lambda n: (not declared.get(n), n)):
        base = declared.get(ns) or _fallback_name(ns)
        name, suffix = base, 1
        while name.casefold() in taken:
            suffix += 1
            name = f"{base}-{suffix}"
        taken.add(name.casefold())
        names[ns] = name

    # Create module definitions
    modules = [
        ModuleDefinition(name=name, output=f"{name}.ttl", namespaces=[ns])
        for ns, name in sorted(names.items(), key=lambda item: item[1])
    ]

    config = SplitConfig(
        source=source,
        output_dir=output_dir,
        modules=modules,
        unmatched=unmatched or UnmatchedStrategy(),
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
    return """# rdf-construct split configuration
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
      # The module's ontology IRI. Without it, a module is named from its own namespace,
      # else from the source ontology's IRI, else it gets no header
      ontology_iri: http://example.org/ontology/core
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
      # owl:imports take ontology IRIs (or CURIEs), never file names
      imports:
        - http://example.org/ontology/core
      auto_imports: true

  # Handling for subjects that don't match any module
  unmatched:
    strategy: common  # "common" (collect them in one module) or "error"
    module: unmatched
    output: unmatched.ttl

  # Generate manifest file
  generate_manifest: true

  # Optional: Split data files by instance type
  # split_data:
  #   sources:
  #     - data/split_instances.ttl
  #   output_dir: data/
  #   prefix: data_
"""
