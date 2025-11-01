"""Subject selection logic for RDF graphs."""

from rdflib import Graph, RDF, RDFS
from rdflib.namespace import OWL


def select_subjects(
        graph: Graph, selector_key: str, selectors: dict[str, str]
) -> set:
    """Select subjects from a graph based on selector criteria.

    Supports several selector shorthands:
    - classes: owl:Class and rdfs:Class entities
    - obj_props: owl:ObjectProperty entities
    - data_props: owl:DatatypeProperty entities
    - ann_props: owl:AnnotationProperty entities
    - individuals: All subjects that aren't classes or properties

    Args:
        graph: RDF graph to select from
        selector_key: Key identifying the selection type
        selectors: Dictionary of selector definitions

    Returns:
        Set of URIRefs matching the selection criteria
    """
    sel = selectors.get(selector_key, "").strip()
    subjects: set = set()

    # Classes - check both owl:Class and rdfs:Class
    if sel in ("owl:Class", "rdf:type owl:Class") or selector_key == "classes":
        subjects = {s for s in graph.subjects(RDF.type, OWL.Class)}
        subjects |= {s for s in graph.subjects(RDF.type, RDFS.Class)}

    # Object properties
    elif sel in ("owl:ObjectProperty",) or selector_key == "obj_props":
        subjects = {s for s in graph.subjects(RDF.type, OWL.ObjectProperty)}

    # Datatype properties
    elif sel in ("owl:DatatypeProperty",) or selector_key == "data_props":
        subjects = {s for s in graph.subjects(RDF.type, OWL.DatatypeProperty)}

    # Annotation properties
    elif sel in ("owl:AnnotationProperty",) or selector_key == "ann_props":
        subjects = {s for s in graph.subjects(RDF.type, OWL.AnnotationProperty)}

    # Individuals - everything that's not a class or property
    elif selector_key == "individuals" or sel.startswith("FILTER"):
        classes = {s for s in graph.subjects(RDF.type, OWL.Class)}
        classes |= {s for s in graph.subjects(RDF.type, RDFS.Class)}

        properties = set()
        for prop_type in (
                RDF.Property,
                OWL.ObjectProperty,
                OWL.DatatypeProperty,
                OWL.AnnotationProperty,
        ):
            properties |= {s for s in graph.subjects(RDF.type, prop_type)}

        all_subjects = {s for (s, _, _) in graph}
        subjects = all_subjects - classes - properties

    return subjects
