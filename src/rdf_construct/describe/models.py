"""Data models for ontology description analysis.

Provides dataclasses representing all analysis results from the describe
command, designed for easy serialization to JSON and formatting.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class OntologyProfile(Enum):
    """Detected ontology profile/expressiveness level.

    Ordered from least to most expressive. Each level implies
    capability for reasoning at that level.
    """

    RDF = "rdf"
    RDFS = "rdfs"
    OWL_DL_SIMPLE = "owl_dl_simple"
    OWL_DL_EXPRESSIVE = "owl_dl_expressive"
    OWL_FULL = "owl_full"

    @property
    def display_name(self) -> str:
        """Human-readable name for the profile."""
        names = {
            OntologyProfile.RDF: "RDF",
            OntologyProfile.RDFS: "RDFS",
            OntologyProfile.OWL_DL_SIMPLE: "OWL 2 DL (simple)",
            OntologyProfile.OWL_DL_EXPRESSIVE: "OWL 2 DL (expressive)",
            OntologyProfile.OWL_FULL: "OWL 2 Full",
        }
        return names[self]

    @property
    def reasoning_guidance(self) -> str:
        """Guidance on reasoning value for this profile."""
        guidance = {
            OntologyProfile.RDF: "No schema; reasoning not applicable",
            OntologyProfile.RDFS: "Subclass/subproperty inference available",
            OntologyProfile.OWL_DL_SIMPLE: "Standard DL reasoning; efficient",
            OntologyProfile.OWL_DL_EXPRESSIVE: "Full DL reasoning; may be computationally expensive",
            OntologyProfile.OWL_FULL: "Undecidable; reasoning may not terminate",
        }
        return guidance[self]


class NamespaceCategory(Enum):
    """Category of namespace usage in the ontology."""

    LOCAL = "local"  # Defined in this ontology
    IMPORTED = "imported"  # Declared via owl:imports
    EXTERNAL = "external"  # Referenced but not imported


class ImportStatus(Enum):
    """Status of an import resolution check."""

    RESOLVABLE = "resolvable"
    UNRESOLVABLE = "unresolvable"
    UNCHECKED = "unchecked"


@dataclass
class OntologyMetadata:
    """Extracted ontology metadata.

    Attributes:
        ontology_iri: The ontology IRI (from owl:Ontology declaration).
        version_iri: The version IRI (owl:versionIRI), if present.
        title: Human-readable title from rdfs:label, dcterms:title, or dc:title.
        description: Description from rdfs:comment, dcterms:description, or dc:description.
        license_uri: License URI, if declared.
        license_label: License label, if available.
        creators: List of creator names/IRIs.
        version_info: Version string from owl:versionInfo.
    """

    ontology_iri: str | None = None
    version_iri: str | None = None
    title: str | None = None
    description: str | None = None
    license_uri: str | None = None
    license_label: str | None = None
    creators: list[str] = field(default_factory=list)
    version_info: str | None = None

    @property
    def has_iri(self) -> bool:
        """Whether an ontology IRI is declared."""
        return self.ontology_iri is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return {
            "ontology_iri": self.ontology_iri,
            "version_iri": self.version_iri,
            "title": self.title,
            "description": self.description,
            "license_uri": self.license_uri,
            "license_label": self.license_label,
            "creators": self.creators,
            "version_info": self.version_info,
        }


@dataclass
class BasicMetrics:
    """Basic ontology metrics.

    Attributes:
        total_triples: Total triple count in the graph.
        classes: Number of classes (owl:Class + rdfs:Class).
        object_properties: Number of owl:ObjectProperty entities.
        datatype_properties: Number of owl:DatatypeProperty entities.
        annotation_properties: Number of owl:AnnotationProperty entities.
        rdf_properties: Number of rdf:Property entities (not typed as OWL).
        individuals: Number of named individuals.
    """

    total_triples: int = 0
    classes: int = 0
    object_properties: int = 0
    datatype_properties: int = 0
    annotation_properties: int = 0
    rdf_properties: int = 0
    individuals: int = 0

    @property
    def total_properties(self) -> int:
        """Total count of all property types."""
        return (
            self.object_properties
            + self.datatype_properties
            + self.annotation_properties
            + self.rdf_properties
        )

    @property
    def summary_line(self) -> str:
        """One-line summary of metrics."""
        parts = [f"{self.total_triples} triples"]
        if self.classes:
            parts.append(f"{self.classes} classes")
        if self.total_properties:
            parts.append(f"{self.total_properties} properties")
        if self.individuals:
            parts.append(f"{self.individuals} individuals")
        return ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return {
            "total_triples": self.total_triples,
            "classes": self.classes,
            "object_properties": self.object_properties,
            "datatype_properties": self.datatype_properties,
            "annotation_properties": self.annotation_properties,
            "rdf_properties": self.rdf_properties,
            "individuals": self.individuals,
            "total_properties": self.total_properties,
        }


@dataclass
class ProfileDetection:
    """Result of ontology profile detection.

    Attributes:
        profile: Detected ontology profile.
        detected_features: List of features that influenced detection.
        owl_constructs_found: Specific OWL constructs found (for DL/Full distinction).
        violating_constructs: Constructs that pushed profile to OWL Full.
    """

    profile: OntologyProfile = OntologyProfile.RDF
    detected_features: list[str] = field(default_factory=list)
    owl_constructs_found: list[str] = field(default_factory=list)
    violating_constructs: list[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """Human-readable profile name."""
        return self.profile.display_name

    @property
    def reasoning_guidance(self) -> str:
        """Guidance on reasoning value."""
        return self.profile.reasoning_guidance

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return {
            "profile": self.profile.value,
            "display_name": self.display_name,
            "reasoning_guidance": self.reasoning_guidance,
            "detected_features": self.detected_features,
            "owl_constructs_found": self.owl_constructs_found,
            "violating_constructs": self.violating_constructs,
        }


@dataclass
class NamespaceInfo:
    """Information about a namespace used in the ontology.

    Attributes:
        uri: The namespace URI.
        prefix: Bound prefix (if any).
        category: Whether local, imported, or external.
        usage_count: Number of times URIs from this namespace appear.
    """

    uri: str
    prefix: str | None = None
    category: NamespaceCategory = NamespaceCategory.EXTERNAL
    usage_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return {
            "uri": self.uri,
            "prefix": self.prefix,
            "category": self.category.value,
            "usage_count": self.usage_count,
        }


@dataclass
class NamespaceAnalysis:
    """Complete namespace analysis for the ontology.

    Attributes:
        local_namespace: The primary/local namespace (if identifiable).
        namespaces: List of all namespaces found.
        unimported_external: Namespaces that are used but not imported.
    """

    local_namespace: str | None = None
    namespaces: list[NamespaceInfo] = field(default_factory=list)
    unimported_external: list[str] = field(default_factory=list)

    @property
    def local_count(self) -> int:
        """Number of local namespaces."""
        return sum(1 for ns in self.namespaces if ns.category == NamespaceCategory.LOCAL)

    @property
    def imported_count(self) -> int:
        """Number of imported namespaces."""
        return sum(1 for ns in self.namespaces if ns.category == NamespaceCategory.IMPORTED)

    @property
    def external_count(self) -> int:
        """Number of external (unimported) namespaces."""
        return sum(1 for ns in self.namespaces if ns.category == NamespaceCategory.EXTERNAL)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return {
            "local_namespace": self.local_namespace,
            "namespaces": [ns.to_dict() for ns in self.namespaces],
            "unimported_external": self.unimported_external,
            "counts": {
                "local": self.local_count,
                "imported": self.imported_count,
                "external": self.external_count,
            },
        }


@dataclass
class ImportInfo:
    """Information about a declared import.

    Attributes:
        uri: The imported ontology URI.
        status: Resolution status.
        error: Error message if unresolvable.
    """

    uri: str
    status: ImportStatus = ImportStatus.UNCHECKED
    error: str | None = None

    @property
    def is_resolvable(self) -> bool:
        """Whether the import was resolved successfully."""
        return self.status == ImportStatus.RESOLVABLE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return {
            "uri": self.uri,
            "status": self.status.value,
            "error": self.error,
        }


@dataclass
class ImportAnalysis:
    """Analysis of ontology imports.

    Attributes:
        imports: List of declared imports with resolution status.
        resolve_attempted: Whether resolution was attempted.
    """

    imports: list[ImportInfo] = field(default_factory=list)
    resolve_attempted: bool = False

    @property
    def count(self) -> int:
        """Number of declared imports."""
        return len(self.imports)

    @property
    def resolvable_count(self) -> int:
        """Number of resolvable imports."""
        return sum(1 for imp in self.imports if imp.is_resolvable)

    @property
    def unresolvable_count(self) -> int:
        """Number of unresolvable imports."""
        return sum(
            1 for imp in self.imports if imp.status == ImportStatus.UNRESOLVABLE
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return {
            "imports": [imp.to_dict() for imp in self.imports],
            "resolve_attempted": self.resolve_attempted,
            "counts": {
                "total": self.count,
                "resolvable": self.resolvable_count if self.resolve_attempted else None,
                "unresolvable": self.unresolvable_count if self.resolve_attempted else None,
            },
        }


@dataclass
class HierarchyAnalysis:
    """Class hierarchy analysis.

    Attributes:
        root_classes: Classes with no superclass (except owl:Thing/rdfs:Resource).
        max_depth: Maximum depth of the hierarchy.
        orphan_classes: Classes that are neither parent nor child of anything.
        has_cycles: Whether cycles were detected.
        cycle_members: URIs involved in cycles (if any).
    """

    root_classes: list[str] = field(default_factory=list)
    max_depth: int = 0
    orphan_classes: list[str] = field(default_factory=list)
    has_cycles: bool = False
    cycle_members: list[str] = field(default_factory=list)

    @property
    def root_count(self) -> int:
        """Number of root classes."""
        return len(self.root_classes)

    @property
    def orphan_count(self) -> int:
        """Number of orphan classes."""
        return len(self.orphan_classes)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return {
            "root_classes": self.root_classes,
            "root_count": self.root_count,
            "max_depth": self.max_depth,
            "orphan_classes": self.orphan_classes,
            "orphan_count": self.orphan_count,
            "has_cycles": self.has_cycles,
            "cycle_members": self.cycle_members,
        }


@dataclass
class DocumentationCoverage:
    """Documentation coverage metrics.

    Attributes:
        classes_with_label: Number of classes with rdfs:label.
        classes_total: Total number of classes.
        classes_with_definition: Number of classes with rdfs:comment or skos:definition.
        properties_with_label: Number of properties with rdfs:label.
        properties_total: Total number of properties.
        properties_with_definition: Number of properties with definitions.
    """

    classes_with_label: int = 0
    classes_total: int = 0
    classes_with_definition: int = 0
    properties_with_label: int = 0
    properties_total: int = 0
    properties_with_definition: int = 0

    @property
    def class_label_pct(self) -> float:
        """Percentage of classes with labels."""
        if self.classes_total == 0:
            return 100.0
        return (self.classes_with_label / self.classes_total) * 100

    @property
    def class_definition_pct(self) -> float:
        """Percentage of classes with definitions."""
        if self.classes_total == 0:
            return 100.0
        return (self.classes_with_definition / self.classes_total) * 100

    @property
    def property_label_pct(self) -> float:
        """Percentage of properties with labels."""
        if self.properties_total == 0:
            return 100.0
        return (self.properties_with_label / self.properties_total) * 100

    @property
    def property_definition_pct(self) -> float:
        """Percentage of properties with definitions."""
        if self.properties_total == 0:
            return 100.0
        return (self.properties_with_definition / self.properties_total) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return {
            "classes": {
                "with_label": self.classes_with_label,
                "with_definition": self.classes_with_definition,
                "total": self.classes_total,
                "label_pct": round(self.class_label_pct, 1),
                "definition_pct": round(self.class_definition_pct, 1),
            },
            "properties": {
                "with_label": self.properties_with_label,
                "with_definition": self.properties_with_definition,
                "total": self.properties_total,
                "label_pct": round(self.property_label_pct, 1),
                "definition_pct": round(self.property_definition_pct, 1),
            },
        }


@dataclass
class ReasoningAnalysis:
    """Analysis of reasoning implications (optional, off by default).

    Attributes:
        entailment_regime: Applicable entailment regime.
        inferred_superclasses: Sample of superclass inferences.
        inferred_types: Sample of type inferences.
        consistency_notes: Notes on potential consistency issues.
    """

    entailment_regime: str = "none"
    inferred_superclasses: list[str] = field(default_factory=list)
    inferred_types: list[str] = field(default_factory=list)
    consistency_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return {
            "entailment_regime": self.entailment_regime,
            "inferred_superclasses": self.inferred_superclasses,
            "inferred_types": self.inferred_types,
            "consistency_notes": self.consistency_notes,
        }


@dataclass
class OntologyDescription:
    """Complete description of an ontology.

    Aggregates all analysis results into a single structure for
    formatting and serialisation.
    """

    # Source information
    source: str | Path
    timestamp: datetime = field(default_factory=datetime.now)

    # Analysis results
    metadata: OntologyMetadata = field(default_factory=OntologyMetadata)
    metrics: BasicMetrics = field(default_factory=BasicMetrics)
    profile: ProfileDetection = field(default_factory=ProfileDetection)
    namespaces: NamespaceAnalysis = field(default_factory=NamespaceAnalysis)
    imports: ImportAnalysis = field(default_factory=ImportAnalysis)
    hierarchy: HierarchyAnalysis = field(default_factory=HierarchyAnalysis)
    documentation: DocumentationCoverage = field(default_factory=DocumentationCoverage)
    reasoning: ReasoningAnalysis | None = None

    # Analysis settings
    brief: bool = False
    include_reasoning: bool = False

    @property
    def verdict(self) -> str:
        """One-line summary verdict for the ontology."""
        parts = []

        # Profile
        parts.append(self.profile.display_name)

        # Size
        parts.append(self.metrics.summary_line)

        # Import status
        if self.imports.count > 0:
            if self.imports.resolve_attempted:
                if self.imports.unresolvable_count > 0:
                    parts.append(
                        f"{self.imports.unresolvable_count}/{self.imports.count} imports unresolvable"
                    )
                else:
                    parts.append(f"{self.imports.count} imports OK")
            else:
                parts.append(f"{self.imports.count} imports")

        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        result = {
            "source": str(self.source),
            "timestamp": self.timestamp.isoformat(),
            "verdict": self.verdict,
            "metadata": self.metadata.to_dict(),
            "metrics": self.metrics.to_dict(),
            "profile": self.profile.to_dict(),
        }

        if not self.brief:
            result["namespaces"] = self.namespaces.to_dict()
            result["imports"] = self.imports.to_dict()
            result["hierarchy"] = self.hierarchy.to_dict()
            result["documentation"] = self.documentation.to_dict()

            if self.reasoning is not None:
                result["reasoning"] = self.reasoning.to_dict()

        return result
