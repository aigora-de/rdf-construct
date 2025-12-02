"""SHACL namespace definitions and utilities."""

from rdflib import Namespace
from rdflib.namespace import DefinedNamespace

# SHACL namespace
SH = Namespace("http://www.w3.org/ns/shacl#")


class SHACL(DefinedNamespace):
    """SHACL namespace with commonly used terms.

    Provides typed access to SHACL vocabulary terms for shape generation.
    """

    # Core shape types
    NodeShape: str
    PropertyShape: str
    Shape: str

    # Targeting
    targetClass: str
    targetNode: str
    targetSubjectsOf: str
    targetObjectsOf: str

    # Property constraints
    property: str
    path: str
    name: str
    description: str
    order: str
    group: str

    # Cardinality
    minCount: str
    maxCount: str

    # Value type constraints
    datatype: str
    nodeKind: str

    # Node kinds
    BlankNode: str
    IRI: str
    Literal: str
    BlankNodeOrIRI: str
    BlankNodeOrLiteral: str
    IRIOrLiteral: str

    # Value constraints
    node: str  # For sh:class equivalent - but we use class directly
    hasValue: str

    # Note: 'class' is a Python reserved word, access via SH["class"] or SH.class_

    # Value range
    minExclusive: str
    minInclusive: str
    maxExclusive: str
    maxInclusive: str
    minLength: str
    maxLength: str
    pattern: str

    # Logical constraints
    closed: str
    ignoredProperties: str

    # List constraints
    in_: str  # sh:in (Python reserved word)

    # Severity
    severity: str
    Violation: str
    Warning: str
    Info: str

    # Property paths
    alternativePath: str
    inversePath: str
    oneOrMorePath: str
    zeroOrMorePath: str
    zeroOrOnePath: str

    # Namespace
    _NS = Namespace("http://www.w3.org/ns/shacl#")


# Standard SHACL prefix bindings for serialisation
SHACL_PREFIXES = {
    "sh": SH,
}
