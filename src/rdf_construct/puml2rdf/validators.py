"""Validation for PlantUML import.

This module provides validation of parsed PlantUML models and
generated RDF, ensuring consistency and flagging potential issues.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from rdflib import Graph, URIRef, RDF, RDFS
from rdflib.namespace import OWL

from rdf_construct.puml2rdf.model import PumlModel, PumlRelationship, RelationshipType


class Severity(Enum):
    """Severity level for validation issues."""

    ERROR = "error"  # Must be fixed
    WARNING = "warning"  # Should be reviewed
    INFO = "info"  # Informational


@dataclass
class ValidationIssue:
    """A validation issue found during checking.

    Attributes:
        severity: How serious the issue is
        code: Machine-readable issue code
        message: Human-readable description
        entity: The entity this issue relates to
        suggestion: Optional fix suggestion
    """

    severity: Severity
    code: str
    message: str
    entity: Optional[str] = None
    suggestion: Optional[str] = None

    def __str__(self) -> str:
        prefix = f"[{self.severity.value.upper()}]"
        entity_str = f" ({self.entity})" if self.entity else ""
        return f"{prefix} {self.code}: {self.message}{entity_str}"


@dataclass
class ValidationResult:
    """Result of validation.

    Attributes:
        issues: List of validation issues found
    """

    issues: list[ValidationIssue]

    @property
    def has_errors(self) -> bool:
        """Return True if any errors were found."""
        return any(i.severity == Severity.ERROR for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Return True if any warnings were found."""
        return any(i.severity == Severity.WARNING for i in self.issues)

    @property
    def error_count(self) -> int:
        """Count of errors."""
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of warnings."""
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    def errors(self) -> list[ValidationIssue]:
        """Return only error-level issues."""
        return [i for i in self.issues if i.severity == Severity.ERROR]

    def warnings(self) -> list[ValidationIssue]:
        """Return only warning-level issues."""
        return [i for i in self.issues if i.severity == Severity.WARNING]


class PumlModelValidator:
    """Validates parsed PlantUML models for consistency.

    Checks include:
    - Relationships reference existing classes
    - No duplicate class names
    - Attributes have valid types
    - Inheritance doesn't create cycles
    """

    def validate(self, model: PumlModel) -> ValidationResult:
        """Validate a parsed PlantUML model.

        Args:
            model: The parsed model to validate

        Returns:
            ValidationResult with any issues found
        """
        issues: list[ValidationIssue] = []

        # Check for duplicate class names
        issues.extend(self._check_duplicate_classes(model))

        # Check relationship references
        issues.extend(self._check_relationship_references(model))

        # Check for inheritance cycles
        issues.extend(self._check_inheritance_cycles(model))

        # Check attribute types
        issues.extend(self._check_attribute_types(model))

        # Check for classes without any relationships
        issues.extend(self._check_orphan_classes(model))

        return ValidationResult(issues=issues)

    def _check_duplicate_classes(self, model: PumlModel) -> list[ValidationIssue]:
        """Check for duplicate class names."""
        issues = []
        seen = set()

        for cls in model.classes:
            if cls.name in seen:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        code="DUPLICATE_CLASS",
                        message=f"Duplicate class name: {cls.name}",
                        entity=cls.name,
                        suggestion="Rename one of the classes or use packages to distinguish them",
                    )
                )
            seen.add(cls.name)

        return issues

    def _check_relationship_references(self, model: PumlModel) -> list[ValidationIssue]:
        """Check that relationships reference existing classes."""
        issues = []

        # Include both local and qualified names for lookup
        class_names = set()
        for cls in model.classes:
            class_names.add(cls.name)  # Local name: "Building"
            class_names.add(cls.qualified_name)  # Qualified: "building.Building"

        for rel in model.relationships:
            if rel.source not in class_names:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        code="UNKNOWN_CLASS",
                        message=f"Relationship references unknown source class: {rel.source}",
                        entity=rel.source,
                        suggestion=f"Add class declaration for '{rel.source}'",
                    )
                )
            if rel.target not in class_names:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        code="UNKNOWN_CLASS",
                        message=f"Relationship references unknown target class: {rel.target}",
                        entity=rel.target,
                        suggestion=f"Add class declaration for '{rel.target}'",
                    )
                )

        return issues

    def _check_inheritance_cycles(self, model: PumlModel) -> list[ValidationIssue]:
        """Check for cycles in inheritance hierarchy."""
        issues = []

        # Build inheritance graph
        inheritance: dict[str, set[str]] = {}
        for rel in model.inheritance_relationships():
            if rel.source not in inheritance:
                inheritance[rel.source] = set()
            inheritance[rel.source].add(rel.target)

        # Check for cycles using DFS
        def has_cycle(start: str, visited: set[str], path: list[str]) -> Optional[list[str]]:
            if start in path:
                cycle_start = path.index(start)
                return path[cycle_start:] + [start]

            if start in visited:
                return None

            visited.add(start)
            path.append(start)

            for parent in inheritance.get(start, set()):
                cycle = has_cycle(parent, visited, path)
                if cycle:
                    return cycle

            path.pop()
            return None

        for cls in model.classes:
            cycle = has_cycle(cls.name, set(), [])
            if cycle:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        code="INHERITANCE_CYCLE",
                        message=f"Inheritance cycle detected: {' -> '.join(cycle)}",
                        entity=cls.name,
                        suggestion="Break the cycle by removing one of the inheritance relationships",
                    )
                )
                break  # Only report once

        return issues

    def _check_attribute_types(self, model: PumlModel) -> list[ValidationIssue]:
        """Check that attribute types are recognized."""
        issues = []

        known_types = {
            "string", "str", "text",
            "integer", "int",
            "decimal", "float", "double", "number",
            "boolean", "bool",
            "date", "datetime", "time",
            "gYear", "gyear", "gYearMonth",
            "duration",
            "uri", "anyURI", "anyuri", "url",
            "base64", "hexBinary",
            "language", "token",
        }

        for cls in model.classes:
            for attr in cls.attributes:
                if attr.datatype and attr.datatype.lower() not in known_types:
                    if not attr.datatype.startswith("xsd:"):
                        issues.append(
                            ValidationIssue(
                                severity=Severity.WARNING,
                                code="UNKNOWN_DATATYPE",
                                message=f"Unknown datatype '{attr.datatype}' for attribute '{attr.name}'",
                                entity=f"{cls.name}.{attr.name}",
                                suggestion="Use standard XSD type or add custom mapping in config",
                            )
                        )

        return issues

    def _check_orphan_classes(self, model: PumlModel) -> list[ValidationIssue]:
        """Check for classes with no relationships."""
        issues = []

        # Get all classes involved in relationships
        related_classes = set()
        for rel in model.relationships:
            related_classes.add(rel.source)
            related_classes.add(rel.target)

        for cls in model.classes:
            if cls.name not in related_classes and not cls.attributes:
                issues.append(
                    ValidationIssue(
                        severity=Severity.INFO,
                        code="ISOLATED_CLASS",
                        message=f"Class '{cls.name}' has no relationships or attributes",
                        entity=cls.name,
                        suggestion="Consider adding relationships or attributes",
                    )
                )

        return issues


class RdfValidator:
    """Validates generated RDF for OWL/RDFS consistency.

    Checks include:
    - Classes are typed as owl:Class
    - Properties have domain and range
    - No dangling references
    """

    def validate(self, graph: Graph) -> ValidationResult:
        """Validate an RDF graph.

        Args:
            graph: The graph to validate

        Returns:
            ValidationResult with any issues found
        """
        issues: list[ValidationIssue] = []

        # Check class typing
        issues.extend(self._check_class_typing(graph))

        # Check property completeness
        issues.extend(self._check_property_completeness(graph))

        # Check for dangling references
        issues.extend(self._check_dangling_references(graph))

        return ValidationResult(issues=issues)

    def _check_class_typing(self, graph: Graph) -> list[ValidationIssue]:
        """Check that classes are properly typed."""
        issues = []

        # Find subjects of rdfs:subClassOf that aren't typed as classes
        for s in graph.subjects(RDFS.subClassOf, None):
            if not isinstance(s, URIRef):
                continue

            is_class = (
                (s, RDF.type, OWL.Class) in graph
                or (s, RDF.type, RDFS.Class) in graph
            )
            if not is_class:
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        code="UNTYPED_CLASS",
                        message=f"Subject of rdfs:subClassOf not typed as class",
                        entity=str(s),
                        suggestion="Add rdf:type owl:Class triple",
                    )
                )

        return issues

    def _check_property_completeness(self, graph: Graph) -> list[ValidationIssue]:
        """Check that properties have domain and range."""
        issues = []

        for prop in graph.subjects(RDF.type, OWL.ObjectProperty):
            if not isinstance(prop, URIRef):
                continue

            has_domain = any(graph.objects(prop, RDFS.domain))
            has_range = any(graph.objects(prop, RDFS.range))

            if not has_domain:
                issues.append(
                    ValidationIssue(
                        severity=Severity.INFO,
                        code="MISSING_DOMAIN",
                        message="Object property has no domain",
                        entity=str(prop),
                    )
                )
            if not has_range:
                issues.append(
                    ValidationIssue(
                        severity=Severity.INFO,
                        code="MISSING_RANGE",
                        message="Object property has no range",
                        entity=str(prop),
                    )
                )

        for prop in graph.subjects(RDF.type, OWL.DatatypeProperty):
            if not isinstance(prop, URIRef):
                continue

            has_range = any(graph.objects(prop, RDFS.range))
            if not has_range:
                issues.append(
                    ValidationIssue(
                        severity=Severity.INFO,
                        code="MISSING_RANGE",
                        message="Datatype property has no range (XSD type)",
                        entity=str(prop),
                    )
                )

        return issues

    def _check_dangling_references(self, graph: Graph) -> list[ValidationIssue]:
        """Check for references to undefined entities."""
        issues = []

        # Get all defined classes
        defined_classes = set()
        for cls in graph.subjects(RDF.type, OWL.Class):
            defined_classes.add(cls)
        for cls in graph.subjects(RDF.type, RDFS.Class):
            defined_classes.add(cls)

        # Check domain and range references
        for prop in graph.subjects(RDF.type, OWL.ObjectProperty):
            for domain in graph.objects(prop, RDFS.domain):
                if isinstance(domain, URIRef) and domain not in defined_classes:
                    issues.append(
                        ValidationIssue(
                            severity=Severity.WARNING,
                            code="UNDEFINED_DOMAIN",
                            message=f"Property domain references undefined class",
                            entity=f"{prop} -> {domain}",
                        )
                    )

            for rng in graph.objects(prop, RDFS.range):
                if isinstance(rng, URIRef) and rng not in defined_classes:
                    # Could be external class - just info
                    issues.append(
                        ValidationIssue(
                            severity=Severity.INFO,
                            code="EXTERNAL_RANGE",
                            message=f"Property range references class not in this graph",
                            entity=f"{prop} -> {rng}",
                        )
                    )

        return issues


def validate_puml(model: PumlModel) -> ValidationResult:
    """Convenience function to validate a PlantUML model.

    Args:
        model: The parsed model to validate

    Returns:
        ValidationResult with any issues found
    """
    validator = PumlModelValidator()
    return validator.validate(model)


def validate_rdf(graph: Graph) -> ValidationResult:
    """Convenience function to validate an RDF graph.

    Args:
        graph: The graph to validate

    Returns:
        ValidationResult with any issues found
    """
    validator = RdfValidator()
    return validator.validate(graph)
