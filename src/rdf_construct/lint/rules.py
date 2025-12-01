"""Lint rules for RDF ontology quality checking.

Each rule is a function that takes a graph and returns a list of LintIssue objects.
Rules are registered with the @lint_rule decorator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from rdflib import Graph, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL


class Severity(Enum):
    """Severity levels for lint issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def __lt__(self, other: Severity) -> bool:
        order = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}
        return order[self] < order[other]


@dataclass
class LintIssue:
    """A single lint issue found in an ontology.

    Attributes:
        rule_id: Identifier for the rule that found this issue.
        severity: How serious the issue is (error/warning/info).
        entity: The URI of the entity with the issue.
        message: Human-readable description of the issue.
        line: Approximate line number in source (if available).
    """

    rule_id: str
    severity: Severity
    entity: URIRef | None
    message: str
    line: int | None = None

    def __str__(self) -> str:
        entity_str = f" '{self.entity}'" if self.entity else ""
        line_str = f":{self.line}" if self.line else ""
        return f"{line_str} {self.severity.value}[{self.rule_id}]:{entity_str} {self.message}"


@dataclass
class RuleSpec:
    """Specification for a lint rule.

    Attributes:
        rule_id: Unique identifier for this rule.
        description: What this rule checks for.
        category: Category grouping (structural/documentation/best-practice).
        default_severity: Default severity level.
        check_fn: Function that performs the check.
    """

    rule_id: str
    description: str
    category: str
    default_severity: Severity
    check_fn: Callable[[Graph], list[LintIssue]]


# Registry of all lint rules
_RULE_REGISTRY: dict[str, RuleSpec] = {}


def lint_rule(
        rule_id: str,
        description: str,
        category: str,
        default_severity: Severity,
) -> Callable:
    """Decorator to register a lint rule.

    Args:
        rule_id: Unique identifier (e.g., 'orphan-class').
        description: What this rule checks.
        category: 'structural', 'documentation', or 'best-practice'.
        default_severity: Default severity level.

    Returns:
        Decorator function.
    """

    def decorator(fn: Callable[[Graph], list[LintIssue]]) -> Callable:
        spec = RuleSpec(
            rule_id=rule_id,
            description=description,
            category=category,
            default_severity=default_severity,
            check_fn=fn,
        )
        _RULE_REGISTRY[rule_id] = spec
        return fn

    return decorator


def get_all_rules() -> dict[str, RuleSpec]:
    """Return all registered rules."""
    return _RULE_REGISTRY.copy()


def get_rule(rule_id: str) -> RuleSpec | None:
    """Get a rule by ID."""
    return _RULE_REGISTRY.get(rule_id)


def list_rules() -> list[str]:
    """List all rule IDs."""
    return list(_RULE_REGISTRY.keys())


# -----------------------------------------------------------------------------
# Helper functions for rules
# -----------------------------------------------------------------------------


def get_classes(graph: Graph) -> set[URIRef]:
    """Get all classes (owl:Class and rdfs:Class)."""
    classes: set[URIRef] = set()
    for cls in graph.subjects(RDF.type, OWL.Class):
        if isinstance(cls, URIRef):
            classes.add(cls)
    for cls in graph.subjects(RDF.type, RDFS.Class):
        if isinstance(cls, URIRef):
            classes.add(cls)
    return classes


def get_properties(graph: Graph) -> set[URIRef]:
    """Get all properties (all property types)."""
    props: set[URIRef] = set()
    for prop_type in (
            RDF.Property,
            OWL.ObjectProperty,
            OWL.DatatypeProperty,
            OWL.AnnotationProperty,
    ):
        for prop in graph.subjects(RDF.type, prop_type):
            if isinstance(prop, URIRef):
                props.add(prop)
    return props


def get_object_properties(graph: Graph) -> set[URIRef]:
    """Get owl:ObjectProperty entities."""
    return {p for p in graph.subjects(RDF.type, OWL.ObjectProperty) if isinstance(p, URIRef)}


def get_datatype_properties(graph: Graph) -> set[URIRef]:
    """Get owl:DatatypeProperty entities."""
    return {p for p in graph.subjects(RDF.type, OWL.DatatypeProperty) if isinstance(p, URIRef)}


def get_superclasses(graph: Graph, cls: URIRef) -> set[URIRef]:
    """Get direct superclasses of a class."""
    return {o for o in graph.objects(cls, RDFS.subClassOf) if isinstance(o, URIRef)}


def get_superproperties(graph: Graph, prop: URIRef) -> set[URIRef]:
    """Get direct superproperties of a property."""
    return {o for o in graph.objects(prop, RDFS.subPropertyOf) if isinstance(o, URIRef)}


def has_inherited_domain(graph: Graph, prop: URIRef, visited: set[URIRef] | None = None) -> bool:
    """Check if property has domain (directly or inherited from superproperty)."""
    if visited is None:
        visited = set()
    if prop in visited:
        return False
    visited.add(prop)

    if (prop, RDFS.domain, None) in graph:
        return True

    for superprop in get_superproperties(graph, prop):
        if has_inherited_domain(graph, superprop, visited):
            return True
    return False


def has_inherited_range(graph: Graph, prop: URIRef, visited: set[URIRef] | None = None) -> bool:
    """Check if property has range (directly or inherited from superproperty)."""
    if visited is None:
        visited = set()
    if prop in visited:
        return False
    visited.add(prop)

    if (prop, RDFS.range, None) in graph:
        return True

    for superprop in get_superproperties(graph, prop):
        if has_inherited_range(graph, superprop, visited):
            return True
    return False


def get_all_referenced_uris(graph: Graph) -> set[URIRef]:
    """Get all URIs referenced in the graph (subjects, predicates, objects)."""
    uris: set[URIRef] = set()
    for s, p, o in graph:
        if isinstance(s, URIRef):
            uris.add(s)
        if isinstance(p, URIRef):
            uris.add(p)
        if isinstance(o, URIRef):
            uris.add(o)
    return uris


def get_defined_entities(graph: Graph) -> set[URIRef]:
    """Get all entities that are defined as subjects with rdf:type."""
    return {s for s in graph.subjects(RDF.type, None) if isinstance(s, URIRef)}


def is_builtin(uri: URIRef) -> bool:
    """Check if a URI is from a built-in namespace (RDF, RDFS, OWL, XSD)."""
    builtin_namespaces = [
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "http://www.w3.org/2000/01/rdf-schema#",
        "http://www.w3.org/2002/07/owl#",
        "http://www.w3.org/2001/XMLSchema#",
    ]
    uri_str = str(uri)
    return any(uri_str.startswith(ns) for ns in builtin_namespaces)


def get_namespace(uri: URIRef) -> str:
    """Extract namespace from a URI (everything before the local name)."""
    uri_str = str(uri)
    if "#" in uri_str:
        return uri_str.rsplit("#", 1)[0] + "#"
    elif "/" in uri_str:
        return uri_str.rsplit("/", 1)[0] + "/"
    return uri_str


# -----------------------------------------------------------------------------
# Structural Rules (default: ERROR)
# -----------------------------------------------------------------------------


@lint_rule(
    rule_id="orphan-class",
    description="Class has no rdfs:subClassOf declaration and isn't owl:Thing or rdfs:Resource",
    category="structural",
    default_severity=Severity.ERROR,
)
def check_orphan_class(graph: Graph) -> list[LintIssue]:
    """Check for classes with no superclass."""
    issues = []
    classes = get_classes(graph)

    # Exempt top-level classes
    top_classes = {OWL.Thing, RDFS.Resource, RDFS.Class, OWL.Class}

    for cls in classes:
        if cls in top_classes or is_builtin(cls):
            continue

        superclasses = get_superclasses(graph, cls)
        if not superclasses:
            issues.append(
                LintIssue(
                    rule_id="orphan-class",
                    severity=Severity.ERROR,
                    entity=cls,
                    message="Class has no rdfs:subClassOf declaration",
                )
            )

    return issues


@lint_rule(
    rule_id="dangling-reference",
    description="Reference to an entity that is not defined in the ontology",
    category="structural",
    default_severity=Severity.ERROR,
)
def check_dangling_reference(graph: Graph) -> list[LintIssue]:
    """Check for references to undefined entities."""
    issues = []
    defined = get_defined_entities(graph)
    referenced = get_all_referenced_uris(graph)

    # Get namespaces of all defined entities
    defined_namespaces = {get_namespace(d) for d in defined}

    for uri in referenced:
        if is_builtin(uri):
            continue
        if uri not in defined:
            # Only report if it's in a namespace we define things in
            uri_namespace = get_namespace(uri)
            if uri_namespace in defined_namespaces:
                issues.append(
                    LintIssue(
                        rule_id="dangling-reference",
                        severity=Severity.ERROR,
                        entity=uri,
                        message="Referenced entity is not defined in this ontology",
                    )
                )

    return issues


@lint_rule(
    rule_id="circular-subclass",
    description="Class is a subclass of itself (directly or transitively)",
    category="structural",
    default_severity=Severity.ERROR,
)
def check_circular_subclass(graph: Graph) -> list[LintIssue]:
    """Check for circular subclass relationships."""
    issues = []
    classes = get_classes(graph)

    for cls in classes:
        # BFS to find if cls is reachable from itself via subClassOf
        visited: set[URIRef] = set()
        queue = list(get_superclasses(graph, cls))

        while queue:
            current = queue.pop(0)
            if current == cls:
                issues.append(
                    LintIssue(
                        rule_id="circular-subclass",
                        severity=Severity.ERROR,
                        entity=cls,
                        message="Class is a subclass of itself (circular hierarchy)",
                    )
                )
                break

            if current not in visited and isinstance(current, URIRef):
                visited.add(current)
                queue.extend(get_superclasses(graph, current))

    return issues


@lint_rule(
    rule_id="property-no-type",
    description="Property lacks explicit rdf:type declaration",
    category="structural",
    default_severity=Severity.ERROR,
)
def check_property_no_type(graph: Graph) -> list[LintIssue]:
    """Check for properties without explicit type.

    This catches subjects that have domain/range but no property type.
    """
    issues = []

    # Find all subjects that have domain or range but no property type
    property_types = {
        RDF.Property,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
    }

    for subj in graph.subjects(RDFS.domain, None):
        if isinstance(subj, URIRef) and not is_builtin(subj):
            types = set(graph.objects(subj, RDF.type))
            if not types.intersection(property_types):
                issues.append(
                    LintIssue(
                        rule_id="property-no-type",
                        severity=Severity.ERROR,
                        entity=subj,
                        message="Has rdfs:domain but no property type declaration",
                    )
                )

    for subj in graph.subjects(RDFS.range, None):
        if isinstance(subj, URIRef) and not is_builtin(subj):
            types = set(graph.objects(subj, RDF.type))
            if not types.intersection(property_types):
                # Avoid duplicates if already reported
                existing = [i for i in issues if i.entity == subj]
                if not existing:
                    issues.append(
                        LintIssue(
                            rule_id="property-no-type",
                            severity=Severity.ERROR,
                            entity=subj,
                            message="Has rdfs:range but no property type declaration",
                        )
                    )

    return issues


@lint_rule(
    rule_id="empty-ontology",
    description="owl:Ontology declaration has no metadata (label, version, etc.)",
    category="structural",
    default_severity=Severity.ERROR,
)
def check_empty_ontology(graph: Graph) -> list[LintIssue]:
    """Check for owl:Ontology with no metadata."""
    issues = []

    # Common ontology metadata predicates
    metadata_predicates = {
        RDFS.label,
        RDFS.comment,
        OWL.versionInfo,
        OWL.versionIRI,
    }

    for ont in graph.subjects(RDF.type, OWL.Ontology):
        if isinstance(ont, URIRef):
            has_metadata = False
            for pred in metadata_predicates:
                if (ont, pred, None) in graph:
                    has_metadata = True
                    break

            if not has_metadata:
                issues.append(
                    LintIssue(
                        rule_id="empty-ontology",
                        severity=Severity.ERROR,
                        entity=ont,
                        message="owl:Ontology has no metadata (label, comment, or version)",
                    )
                )

    return issues


# -----------------------------------------------------------------------------
# Documentation Rules (default: WARNING)
# -----------------------------------------------------------------------------


@lint_rule(
    rule_id="missing-label",
    description="Entity lacks rdfs:label annotation",
    category="documentation",
    default_severity=Severity.WARNING,
)
def check_missing_label(graph: Graph) -> list[LintIssue]:
    """Check for classes and properties without labels."""
    issues = []

    # Check classes
    for cls in get_classes(graph):
        if is_builtin(cls):
            continue
        if (cls, RDFS.label, None) not in graph:
            issues.append(
                LintIssue(
                    rule_id="missing-label",
                    severity=Severity.WARNING,
                    entity=cls,
                    message="Class lacks rdfs:label",
                )
            )

    # Check properties
    for prop in get_properties(graph):
        if is_builtin(prop):
            continue
        if (prop, RDFS.label, None) not in graph:
            issues.append(
                LintIssue(
                    rule_id="missing-label",
                    severity=Severity.WARNING,
                    entity=prop,
                    message="Property lacks rdfs:label",
                )
            )

    return issues


@lint_rule(
    rule_id="missing-comment",
    description="Class or property lacks rdfs:comment annotation",
    category="documentation",
    default_severity=Severity.WARNING,
)
def check_missing_comment(graph: Graph) -> list[LintIssue]:
    """Check for classes and properties without comments."""
    issues = []

    # Check classes
    for cls in get_classes(graph):
        if is_builtin(cls):
            continue
        if (cls, RDFS.comment, None) not in graph:
            issues.append(
                LintIssue(
                    rule_id="missing-comment",
                    severity=Severity.WARNING,
                    entity=cls,
                    message="Class lacks rdfs:comment",
                )
            )

    # Check properties
    for prop in get_properties(graph):
        if is_builtin(prop):
            continue
        if (prop, RDFS.comment, None) not in graph:
            issues.append(
                LintIssue(
                    rule_id="missing-comment",
                    severity=Severity.WARNING,
                    entity=prop,
                    message="Property lacks rdfs:comment",
                )
            )

    return issues


# -----------------------------------------------------------------------------
# Best Practice Rules (default: INFO)
# -----------------------------------------------------------------------------


@lint_rule(
    rule_id="redundant-subclass",
    description="Class has redundant subclass declaration (A → B → C, but also A → C)",
    category="best-practice",
    default_severity=Severity.INFO,
)
def check_redundant_subclass(graph: Graph) -> list[LintIssue]:
    """Check for redundant subclass relationships."""
    issues = []
    classes = get_classes(graph)

    for cls in classes:
        superclasses = get_superclasses(graph, cls)

        # For each pair of direct superclasses, check if one is an ancestor of the other
        superclass_list = list(superclasses)
        for i, sup1 in enumerate(superclass_list):
            for sup2 in superclass_list[i + 1:]:
                # Check if sup1 is an ancestor of sup2 (or vice versa)
                if _is_ancestor(graph, sup1, sup2):
                    issues.append(
                        LintIssue(
                            rule_id="redundant-subclass",
                            severity=Severity.INFO,
                            entity=cls,
                            message=f"Redundant subclass: inherits from both {sup1} and {sup2} "
                                    f"(but {sup2} already inherits from {sup1})",
                        )
                    )
                elif _is_ancestor(graph, sup2, sup1):
                    issues.append(
                        LintIssue(
                            rule_id="redundant-subclass",
                            severity=Severity.INFO,
                            entity=cls,
                            message=f"Redundant subclass: inherits from both {sup1} and {sup2} "
                                    f"(but {sup1} already inherits from {sup2})",
                        )
                    )

    return issues


def _is_ancestor(graph: Graph, potential_ancestor: URIRef, cls: URIRef) -> bool:
    """Check if potential_ancestor is an ancestor of cls via subClassOf."""
    visited: set[URIRef] = set()
    queue = list(get_superclasses(graph, cls))

    while queue:
        current = queue.pop(0)
        if current == potential_ancestor:
            return True
        if current not in visited and isinstance(current, URIRef):
            visited.add(current)
            queue.extend(get_superclasses(graph, current))

    return False


@lint_rule(
    rule_id="property-no-domain",
    description="Object property has no rdfs:domain declaration (direct or inherited)",
    category="best-practice",
    default_severity=Severity.INFO,
)
def check_property_no_domain(graph: Graph) -> list[LintIssue]:
    """Check for object properties without domain (including inherited)."""
    issues = []

    for prop in get_object_properties(graph):
        if is_builtin(prop):
            continue
        if not has_inherited_domain(graph, prop):
            issues.append(
                LintIssue(
                    rule_id="property-no-domain",
                    severity=Severity.INFO,
                    entity=prop,
                    message="Object property has no rdfs:domain (direct or inherited)",
                )
            )

    return issues

@lint_rule(
    rule_id="property-no-range",
    description="Object property has no rdfs:range declaration (direct or inherited)",
    category="best-practice",
    default_severity=Severity.INFO,
)
def check_property_no_range(graph: Graph) -> list[LintIssue]:
    """Check for object properties without range (including inherited)."""
    issues = []

    for prop in get_object_properties(graph):
        if is_builtin(prop):
            continue
        if not has_inherited_range(graph, prop):
            issues.append(
                LintIssue(
                    rule_id="property-no-range",
                    severity=Severity.INFO,
                    entity=prop,
                    message="Object property has no rdfs:range (direct or inherited)",
                )
            )

    return issues

@lint_rule(
    rule_id="inconsistent-naming",
    description="Entity names don't follow consistent convention (CamelCase vs snake_case)",
    category="best-practice",
    default_severity=Severity.INFO,
)
def check_inconsistent_naming(graph: Graph) -> list[LintIssue]:
    """Check for inconsistent naming conventions.

    OWL convention: Classes use UpperCamelCase, properties use lowerCamelCase.
    """
    issues = []

    # Check classes - should be UpperCamelCase
    for cls in get_classes(graph):
        if is_builtin(cls):
            continue
        local_name = str(cls).split("#")[-1].split("/")[-1]
        if local_name and not local_name[0].isupper():
            issues.append(
                LintIssue(
                    rule_id="inconsistent-naming",
                    severity=Severity.INFO,
                    entity=cls,
                    message=f"Class name '{local_name}' should start with uppercase (UpperCamelCase)",
                )
            )

    # Check properties - should be lowerCamelCase
    for prop in get_properties(graph):
        if is_builtin(prop):
            continue
        local_name = str(prop).split("#")[-1].split("/")[-1]
        if local_name and local_name[0].isupper():
            issues.append(
                LintIssue(
                    rule_id="inconsistent-naming",
                    severity=Severity.INFO,
                    entity=prop,
                    message=f"Property name '{local_name}' should start with lowercase (lowerCamelCase)",
                )
            )

    return issues
