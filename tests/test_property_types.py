"""Tests for classifying terms declared only by an OWL property characteristic.

A term may be declared solely as ``owl:TransitiveProperty``, ``owl:FunctionalProperty``
or ``rdf:Property``, with no accompanying ``owl:ObjectProperty`` triple. Selection used
to recognise only the four obvious property types, which classified such terms as
individuals — and, for ``rdf:Property``, dropped them from ordered output entirely,
because ``individuals`` excluded them while no section selected them.
"""

import pytest
from rdflib import Graph

from rdf_construct.core.selector import select_subjects

SELECTORS = {
    "classes": "rdf:type owl:Class",
    "obj_props": "rdf:type owl:ObjectProperty",
    "data_props": "rdf:type owl:DatatypeProperty",
    "ann_props": "rdf:type owl:AnnotationProperty",
    "other_props": "rdf:Property",
    "individuals": "FILTER",
}

ONTOLOGY = """
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix ex:   <http://example.org/> .

ex:Person       a owl:Class .
ex:Legacy       a owl:DeprecatedClass .
ex:knows        a owl:ObjectProperty .
ex:hasParent    a owl:TransitiveProperty .
ex:marriedTo    a owl:SymmetricProperty .
ex:hasAccount   a owl:InverseFunctionalProperty .
ex:age          a owl:DatatypeProperty .
ex:note         a owl:AnnotationProperty .
ex:hasID        a owl:FunctionalProperty .
ex:legacyProp   a rdf:Property .
ex:alice        a ex:Person .
"""


@pytest.fixture
def graph() -> Graph:
    """An ontology exercising every property-declaration style."""
    g = Graph()
    g.parse(data=ONTOLOGY, format="turtle")
    return g


def local_names(subjects) -> set[str]:
    """Reduce a set of URIRefs to their local names for readable assertions."""
    return {str(s).rsplit("/", 1)[-1] for s in subjects}


def test_object_property_characteristics_are_object_properties(graph: Graph) -> None:
    """Characteristic-only declarations select as object properties."""
    selected = local_names(select_subjects(graph, "obj_props", SELECTORS))
    assert selected == {"knows", "hasParent", "marriedTo", "hasAccount"}


def test_deprecated_class_is_a_class(graph: Graph) -> None:
    """owl:DeprecatedClass is a class, not an individual."""
    assert "Legacy" in local_names(select_subjects(graph, "classes", SELECTORS))


def test_characteristic_only_properties_are_not_individuals(graph: Graph) -> None:
    """A property is never classified as an individual because of how it was declared."""
    individuals = local_names(select_subjects(graph, "individuals", SELECTORS))
    assert individuals & {"hasParent", "marriedTo", "hasAccount"} == set()


def test_kind_ambiguous_properties_select_as_other_props(graph: Graph) -> None:
    """rdf:Property and owl:FunctionalProperty declarations are claimable."""
    selected = local_names(select_subjects(graph, "other_props", SELECTORS))
    assert selected == {"hasID", "legacyProp"}


def test_kind_specific_properties_are_excluded_from_other_props(graph: Graph) -> None:
    """A property with a kind-specific type is claimed by that section, not other_props."""
    g = Graph()
    g.parse(
        data="""
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix ex:  <http://example.org/> .
        ex:knows a owl:ObjectProperty, rdf:Property .
        """,
        format="turtle",
    )
    assert select_subjects(g, "other_props", SELECTORS) == set()
    assert local_names(select_subjects(g, "obj_props", SELECTORS)) == {"knows"}


def test_kind_ambiguous_properties_remain_visible_to_individuals(graph: Graph) -> None:
    """Without an other_props section they still reach the output, rather than vanishing.

    This is the regression guard: subtracting them from ``individuals`` without a
    section to claim them silently dropped their triples from ordered output.
    """
    individuals = local_names(select_subjects(graph, "individuals", SELECTORS))
    assert {"hasID", "legacyProp"} <= individuals


def test_no_subject_is_unclassified(graph: Graph) -> None:
    """Every subject is claimed by at least one section, so nothing can be dropped."""
    all_subjects = {s for s, _, _ in graph}
    claimed: set = set()
    for key in ("classes", "obj_props", "data_props", "ann_props", "other_props", "individuals"):
        claimed |= select_subjects(graph, key, SELECTORS)
    assert all_subjects - claimed == set()
