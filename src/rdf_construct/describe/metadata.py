"""Metadata extraction for ontology description.

Extracts ontology-level metadata like IRI, title, description, license, creators.
"""

from rdflib import Graph, URIRef, Literal, RDF, RDFS
from rdflib.namespace import OWL

from rdf_construct.describe.models import OntologyMetadata


# Dublin Core namespaces
DC = URIRef("http://purl.org/dc/elements/1.1/")
DCTERMS = URIRef("http://purl.org/dc/terms/")

# Common metadata predicates
DC_TITLE = URIRef(str(DC) + "title")
DC_DESCRIPTION = URIRef(str(DC) + "description")
DC_CREATOR = URIRef(str(DC) + "creator")
DC_RIGHTS = URIRef(str(DC) + "rights")

DCTERMS_TITLE = URIRef(str(DCTERMS) + "title")
DCTERMS_DESCRIPTION = URIRef(str(DCTERMS) + "description")
DCTERMS_CREATOR = URIRef(str(DCTERMS) + "creator")
DCTERMS_LICENSE = URIRef(str(DCTERMS) + "license")
DCTERMS_RIGHTS = URIRef(str(DCTERMS) + "rights")

# Creative Commons namespace
CC = URIRef("http://creativecommons.org/ns#")
CC_LICENSE = URIRef(str(CC) + "license")


def extract_metadata(graph: Graph) -> OntologyMetadata:
    """Extract ontology-level metadata.

    Looks for owl:Ontology declaration and extracts common metadata
    properties like title, description, license, and creators.

    Args:
        graph: RDF graph to analyse.

    Returns:
        OntologyMetadata with extracted values.
    """
    metadata = OntologyMetadata()

    # Find ontology subject(s)
    ontology_subjects = list(graph.subjects(RDF.type, OWL.Ontology))

    if not ontology_subjects:
        return metadata

    # Use first ontology subject (typically there's only one)
    ontology = ontology_subjects[0]

    # Ontology IRI
    if isinstance(ontology, URIRef):
        metadata.ontology_iri = str(ontology)

    # Version IRI
    version_iri = _get_single_value(graph, ontology, OWL.versionIRI)
    if version_iri:
        metadata.version_iri = str(version_iri)

    # Version info
    version_info = _get_single_literal(graph, ontology, OWL.versionInfo)
    if version_info:
        metadata.version_info = version_info

    # Title (try multiple predicates)
    title = (
        _get_single_literal(graph, ontology, RDFS.label)
        or _get_single_literal(graph, ontology, DCTERMS_TITLE)
        or _get_single_literal(graph, ontology, DC_TITLE)
    )
    if title:
        metadata.title = title

    # Description (try multiple predicates)
    description = (
        _get_single_literal(graph, ontology, RDFS.comment)
        or _get_single_literal(graph, ontology, DCTERMS_DESCRIPTION)
        or _get_single_literal(graph, ontology, DC_DESCRIPTION)
    )
    if description:
        metadata.description = description

    # License
    license_uri = (
        _get_single_value(graph, ontology, DCTERMS_LICENSE)
        or _get_single_value(graph, ontology, CC_LICENSE)
    )
    if license_uri:
        metadata.license_uri = str(license_uri)
        # Try to get a label for the license
        if isinstance(license_uri, URIRef):
            license_label = _get_single_literal(graph, license_uri, RDFS.label)
            if license_label:
                metadata.license_label = license_label

    # If no structured license, check for rights statement
    if not metadata.license_uri:
        rights = (
            _get_single_literal(graph, ontology, DCTERMS_RIGHTS)
            or _get_single_literal(graph, ontology, DC_RIGHTS)
        )
        if rights:
            metadata.license_label = rights

    # Creators
    creators = []
    for pred in [DCTERMS_CREATOR, DC_CREATOR]:
        for creator in graph.objects(ontology, pred):
            if isinstance(creator, Literal):
                creators.append(str(creator))
            elif isinstance(creator, URIRef):
                # Try to get a label for the creator
                label = _get_single_literal(graph, creator, RDFS.label)
                if label:
                    creators.append(label)
                else:
                    # Use URI local name
                    creators.append(_local_name(str(creator)))

    if creators:
        metadata.creators = creators

    return metadata


def _get_single_value(graph: Graph, subject: URIRef, predicate: URIRef):
    """Get a single value for a predicate (URI or literal).

    Args:
        graph: RDF graph to query.
        subject: Subject to query.
        predicate: Predicate to look for.

    Returns:
        First value found or None.
    """
    for obj in graph.objects(subject, predicate):
        return obj
    return None


def _get_single_literal(graph: Graph, subject: URIRef, predicate: URIRef) -> str | None:
    """Get a single literal value for a predicate.

    Prefers English language literals if multiple exist.

    Args:
        graph: RDF graph to query.
        subject: Subject to query.
        predicate: Predicate to look for.

    Returns:
        Literal string value or None.
    """
    english_value = None
    any_value = None

    for obj in graph.objects(subject, predicate):
        if isinstance(obj, Literal):
            value = str(obj)
            if obj.language == "en":
                english_value = value
            elif any_value is None:
                any_value = value

    return english_value or any_value


def _local_name(uri: str) -> str:
    """Extract local name from a URI.

    Args:
        uri: Full URI string.

    Returns:
        Local name portion.
    """
    if "#" in uri:
        return uri.split("#")[-1]
    elif "/" in uri:
        return uri.split("/")[-1]
    return uri
