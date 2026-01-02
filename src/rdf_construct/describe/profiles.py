"""OWL profile detection for ontologies.

Detects whether an ontology is RDF, RDFS, OWL 2 DL (simple or expressive),
or OWL 2 Full based on the constructs used.
"""

from rdflib import Graph, RDF, RDFS, URIRef
from rdflib.namespace import OWL, XSD

from rdf_construct.describe.models import OntologyProfile, ProfileDetection


# OWL constructs that indicate OWL usage (but not necessarily expressive)
OWL_BASIC_CONSTRUCTS = {
    OWL.Class,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    OWL.AnnotationProperty,
    OWL.Ontology,
    OWL.NamedIndividual,
    OWL.Thing,
    OWL.Nothing,
}

# Property characteristics (simple OWL DL)
OWL_PROPERTY_CHARACTERISTICS = {
    OWL.FunctionalProperty,
    OWL.InverseFunctionalProperty,
    OWL.TransitiveProperty,
    OWL.SymmetricProperty,
    OWL.AsymmetricProperty,
    OWL.ReflexiveProperty,
    OWL.IrreflexiveProperty,
}

# Expressive OWL constructs (restrictions, equivalences, etc.)
OWL_EXPRESSIVE_CONSTRUCTS = {
    OWL.Restriction,
    OWL.equivalentClass,
    OWL.disjointWith,
    OWL.AllDisjointClasses,
    OWL.AllDifferent,
    OWL.unionOf,
    OWL.intersectionOf,
    OWL.complementOf,
    OWL.oneOf,
    OWL.hasValue,
    OWL.someValuesFrom,
    OWL.allValuesFrom,
    OWL.minCardinality,
    OWL.maxCardinality,
    OWL.cardinality,
    OWL.minQualifiedCardinality,
    OWL.maxQualifiedCardinality,
    OWL.qualifiedCardinality,
    OWL.hasSelf,
    OWL.propertyChainAxiom,
    OWL.hasKey,
}

# OWL 2 Full constructs (constructs that violate DL constraints)
# These indicate usage patterns that are undecidable
OWL_FULL_INDICATORS = {
    # Classes used as individuals or vice versa (punning beyond DL limits)
    # Using owl:Class as a property
    # Self-referential class definitions
    # Using rdf:type with complex expressions
}

# RDFS constructs that indicate RDFS-level usage
RDFS_CONSTRUCTS = {
    RDFS.Class,
    RDFS.subClassOf,
    RDFS.subPropertyOf,
    RDFS.domain,
    RDFS.range,
    RDFS.label,
    RDFS.comment,
}

# Well-known vocabulary namespaces that don't indicate OWL usage
VOCABULARY_NAMESPACES = {
    str(RDF),
    str(RDFS),
    str(OWL),
    str(XSD),
    "http://www.w3.org/2004/02/skos/core#",
    "http://purl.org/dc/elements/1.1/",
    "http://purl.org/dc/terms/",
    "http://xmlns.com/foaf/0.1/",
    "http://www.w3.org/ns/prov#",
}


def detect_profile(graph: Graph) -> ProfileDetection:
    """Detect the OWL profile of an ontology.

    Analyses the constructs used in the ontology to determine its
    expressiveness level.

    Args:
        graph: RDF graph to analyse.

    Returns:
        ProfileDetection with profile and supporting evidence.
    """
    detected_features: list[str] = []
    owl_constructs: list[str] = []
    violating_constructs: list[str] = []

    # Check for OWL Full indicators first (these are most restrictive)
    owl_full_issues = _detect_owl_full(graph)
    if owl_full_issues:
        violating_constructs.extend(owl_full_issues)
        return ProfileDetection(
            profile=OntologyProfile.OWL_FULL,
            detected_features=["OWL Full constructs detected"],
            owl_constructs_found=owl_constructs,
            violating_constructs=violating_constructs,
        )

    # Check for expressive OWL constructs
    expressive_found = _find_expressive_constructs(graph)
    if expressive_found:
        owl_constructs.extend(expressive_found)
        detected_features.append("Expressive OWL constructs (restrictions, equivalences)")
        return ProfileDetection(
            profile=OntologyProfile.OWL_DL_EXPRESSIVE,
            detected_features=detected_features,
            owl_constructs_found=owl_constructs,
            violating_constructs=[],
        )

    # Check for basic OWL constructs
    basic_owl_found = _find_basic_owl_constructs(graph)
    property_chars = _find_property_characteristics(graph)

    if basic_owl_found or property_chars:
        owl_constructs.extend(basic_owl_found)
        owl_constructs.extend(property_chars)

        if property_chars:
            detected_features.append("Property characteristics declared")
        if basic_owl_found:
            detected_features.append("OWL class/property declarations")

        return ProfileDetection(
            profile=OntologyProfile.OWL_DL_SIMPLE,
            detected_features=detected_features,
            owl_constructs_found=owl_constructs,
            violating_constructs=[],
        )

    # Check for RDFS constructs
    rdfs_found = _find_rdfs_constructs(graph)
    if rdfs_found:
        detected_features.append("RDFS vocabulary in use")
        return ProfileDetection(
            profile=OntologyProfile.RDFS,
            detected_features=detected_features,
            owl_constructs_found=[],
            violating_constructs=[],
        )

    # Default to pure RDF
    detected_features.append("No schema constructs found")
    return ProfileDetection(
        profile=OntologyProfile.RDF,
        detected_features=detected_features,
        owl_constructs_found=[],
        violating_constructs=[],
    )


def _detect_owl_full(graph: Graph) -> list[str]:
    """Detect constructs that indicate OWL Full.

    OWL Full allows patterns that are undecidable, including:
    - Metaclasses (classes that are instances of other classes)
    - Properties with classes as values
    - Circular definitions in certain ways

    Args:
        graph: RDF graph to analyse.

    Returns:
        List of OWL Full indicator descriptions.
    """
    issues: list[str] = []

    # Check for metaclasses: classes that are rdf:type of other classes
    # This is a common OWL Full pattern
    owl_classes = set(graph.subjects(RDF.type, OWL.Class))
    rdfs_classes = set(graph.subjects(RDF.type, RDFS.Class))
    all_classes = owl_classes | rdfs_classes

    for cls in all_classes:
        # Check if this class is an instance of another class (not owl:Class/rdfs:Class)
        for class_type in graph.objects(cls, RDF.type):
            if class_type not in {OWL.Class, RDFS.Class} and class_type in all_classes:
                issues.append(f"Metaclass: {_curie(graph, cls)} is instance of class {_curie(graph, class_type)}")

    # Check for owl:Class used in unexpected positions
    # For example, as the object of a property that expects individuals
    for s, p, o in graph:
        # Skip type assertions
        if p == RDF.type:
            continue

        # If object is a class and predicate domain/range suggests individuals
        if o in all_classes:
            # Check if predicate is an object property with individual range
            if (p, RDF.type, OWL.ObjectProperty) in graph:
                prop_range = list(graph.objects(p, RDFS.range))
                # If range is defined and is not a class of classes, this might be Full
                # This is a simplified check; full analysis would require more inference

    # Check for problematic self-reference patterns
    # e.g., C owl:equivalentClass [ owl:complementOf C ] could be problematic
    for cls in owl_classes:
        equiv_classes = list(graph.objects(cls, OWL.equivalentClass))
        for equiv in equiv_classes:
            # Check for direct self-equivalence to complement
            complement = list(graph.objects(equiv, OWL.complementOf))
            if cls in complement:
                issues.append(f"Self-contradictory equivalence: {_curie(graph, cls)}")

    return issues


def _find_expressive_constructs(graph: Graph) -> list[str]:
    """Find expressive OWL constructs in the graph.

    Args:
        graph: RDF graph to analyse.

    Returns:
        List of expressive construct descriptions found.
    """
    found: list[str] = []

    # Check for restrictions
    restrictions = set(graph.subjects(RDF.type, OWL.Restriction))
    if restrictions:
        found.append(f"owl:Restriction ({len(restrictions)} found)")

    # Check for class equivalences
    equiv_count = len(list(graph.subject_objects(OWL.equivalentClass)))
    if equiv_count:
        found.append(f"owl:equivalentClass ({equiv_count} axioms)")

    # Check for disjointness
    disjoint_count = len(list(graph.subject_objects(OWL.disjointWith)))
    if disjoint_count:
        found.append(f"owl:disjointWith ({disjoint_count} axioms)")

    all_disjoint = set(graph.subjects(RDF.type, OWL.AllDisjointClasses))
    if all_disjoint:
        found.append(f"owl:AllDisjointClasses ({len(all_disjoint)} found)")

    # Check for set operators
    union_of = len(list(graph.subject_objects(OWL.unionOf)))
    if union_of:
        found.append(f"owl:unionOf ({union_of} uses)")

    intersection_of = len(list(graph.subject_objects(OWL.intersectionOf)))
    if intersection_of:
        found.append(f"owl:intersectionOf ({intersection_of} uses)")

    complement_of = len(list(graph.subject_objects(OWL.complementOf)))
    if complement_of:
        found.append(f"owl:complementOf ({complement_of} uses)")

    one_of = len(list(graph.subject_objects(OWL.oneOf)))
    if one_of:
        found.append(f"owl:oneOf ({one_of} uses)")

    # Check for property chains
    chains = len(list(graph.subject_objects(OWL.propertyChainAxiom)))
    if chains:
        found.append(f"owl:propertyChainAxiom ({chains} chains)")

    # Check for keys
    keys = len(list(graph.subject_objects(OWL.hasKey)))
    if keys:
        found.append(f"owl:hasKey ({keys} keys)")

    return found


def _find_basic_owl_constructs(graph: Graph) -> list[str]:
    """Find basic OWL constructs in the graph.

    Args:
        graph: RDF graph to analyse.

    Returns:
        List of basic OWL construct descriptions found.
    """
    found: list[str] = []

    # Check for owl:Ontology
    ontologies = set(graph.subjects(RDF.type, OWL.Ontology))
    if ontologies:
        found.append("owl:Ontology declaration")

    # Check for owl:Class (distinct from rdfs:Class)
    owl_classes = set(graph.subjects(RDF.type, OWL.Class))
    if owl_classes:
        found.append(f"owl:Class ({len(owl_classes)} found)")

    # Check for OWL property types
    obj_props = set(graph.subjects(RDF.type, OWL.ObjectProperty))
    if obj_props:
        found.append(f"owl:ObjectProperty ({len(obj_props)} found)")

    data_props = set(graph.subjects(RDF.type, OWL.DatatypeProperty))
    if data_props:
        found.append(f"owl:DatatypeProperty ({len(data_props)} found)")

    ann_props = set(graph.subjects(RDF.type, OWL.AnnotationProperty))
    if ann_props:
        found.append(f"owl:AnnotationProperty ({len(ann_props)} found)")

    # Check for named individuals
    individuals = set(graph.subjects(RDF.type, OWL.NamedIndividual))
    if individuals:
        found.append(f"owl:NamedIndividual ({len(individuals)} found)")

    return found


def _find_property_characteristics(graph: Graph) -> list[str]:
    """Find OWL property characteristic declarations.

    Args:
        graph: RDF graph to analyse.

    Returns:
        List of property characteristic descriptions found.
    """
    found: list[str] = []

    for char in OWL_PROPERTY_CHARACTERISTICS:
        props = set(graph.subjects(RDF.type, char))
        if props:
            # Get local name of the characteristic
            char_name = str(char).split("#")[-1]
            found.append(f"owl:{char_name} ({len(props)} properties)")

    # Check for inverse properties
    inverse_of = len(list(graph.subject_objects(OWL.inverseOf)))
    if inverse_of:
        found.append(f"owl:inverseOf ({inverse_of} pairs)")

    return found


def _find_rdfs_constructs(graph: Graph) -> list[str]:
    """Find RDFS-level constructs in the graph.

    Args:
        graph: RDF graph to analyse.

    Returns:
        List of RDFS construct descriptions found.
    """
    found: list[str] = []

    # Check for rdfs:Class (not owl:Class)
    rdfs_classes = set(graph.subjects(RDF.type, RDFS.Class))
    owl_classes = set(graph.subjects(RDF.type, OWL.Class))
    pure_rdfs = rdfs_classes - owl_classes
    if pure_rdfs:
        found.append(f"rdfs:Class ({len(pure_rdfs)} found)")

    # Check for subclass assertions
    subclass = len(list(graph.subject_objects(RDFS.subClassOf)))
    if subclass:
        found.append(f"rdfs:subClassOf ({subclass} axioms)")

    # Check for subproperty assertions
    subprop = len(list(graph.subject_objects(RDFS.subPropertyOf)))
    if subprop:
        found.append(f"rdfs:subPropertyOf ({subprop} axioms)")

    # Check for domain/range
    domain = len(list(graph.subject_objects(RDFS.domain)))
    range_count = len(list(graph.subject_objects(RDFS.range)))
    if domain or range_count:
        found.append(f"Domain/range declarations ({domain + range_count} total)")

    return found


def _curie(graph: Graph, uri: URIRef) -> str:
    """Convert URI to CURIE or short form for display.

    Args:
        graph: Graph with namespace bindings.
        uri: URI to convert.

    Returns:
        CURIE or shortened URI string.
    """
    try:
        return graph.namespace_manager.normalizeUri(uri)
    except Exception:
        # Fall back to just the local name
        s = str(uri)
        if "#" in s:
            return s.split("#")[-1]
        elif "/" in s:
            return s.split("/")[-1]
        return s
