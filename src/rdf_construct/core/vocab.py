"""Vocabulary type sets used when classifying subjects as classes or properties.

Ontologies declare classes and properties in more ways than the obvious four
property types. A term may be declared *solely* by an OWL characteristic — for
example ``ex:hasParent a owl:TransitiveProperty`` with no accompanying
``owl:ObjectProperty`` triple — which is legal RDF and common in older
ontologies. Code that recognises only ``owl:ObjectProperty``,
``owl:DatatypeProperty``, ``owl:AnnotationProperty`` and ``rdf:Property`` treats
such a term as an ordinary individual.

These sets are the single place that knowledge lives, so a consumer does not
have to reproduce (and inevitably shorten) the list.
"""

from rdflib import RDF, RDFS
from rdflib.namespace import OWL
from rdflib.term import URIRef

#: Types whose subjects are classes.
CLASS_TYPES: frozenset[URIRef] = frozenset(
    {
        OWL.Class,
        RDFS.Class,
        OWL.DeprecatedClass,
    }
)

#: Types whose subjects are object properties. Every OWL characteristic here is
#: a subclass of ``owl:ObjectProperty`` in OWL 2, so a term declared only with
#: one of them is an object property.
OBJECT_PROPERTY_TYPES: frozenset[URIRef] = frozenset(
    {
        OWL.ObjectProperty,
        OWL.TransitiveProperty,
        OWL.SymmetricProperty,
        OWL.AsymmetricProperty,
        OWL.ReflexiveProperty,
        OWL.IrreflexiveProperty,
        OWL.InverseFunctionalProperty,
    }
)

#: Types whose subjects are datatype properties.
DATATYPE_PROPERTY_TYPES: frozenset[URIRef] = frozenset({OWL.DatatypeProperty})

#: Types whose subjects are annotation properties.
ANNOTATION_PROPERTY_TYPES: frozenset[URIRef] = frozenset({OWL.AnnotationProperty})

#: Property types that do not imply a *kind* of property. ``owl:FunctionalProperty``
#: and ``owl:DeprecatedProperty`` are subclasses of ``rdf:Property`` only, so a term
#: declared with one of these alone cannot be placed in the object, datatype or
#: annotation bucket without guessing.
GENERIC_PROPERTY_TYPES: frozenset[URIRef] = frozenset(
    {
        RDF.Property,
        OWL.FunctionalProperty,
        OWL.DeprecatedProperty,
    }
)

#: Property types that one of the kind-specific selectors will claim.
KIND_SPECIFIC_PROPERTY_TYPES: frozenset[URIRef] = (
    OBJECT_PROPERTY_TYPES | DATATYPE_PROPERTY_TYPES | ANNOTATION_PROPERTY_TYPES
)

#: Every type that declares its subject to be a property.
ALL_PROPERTY_TYPES: frozenset[URIRef] = KIND_SPECIFIC_PROPERTY_TYPES | GENERIC_PROPERTY_TYPES
