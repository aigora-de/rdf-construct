"""Deprecation workflow for ontology entities.

This module handles marking ontology entities as deprecated:
- Adds owl:deprecated true
- Adds dcterms:isReplacedBy with replacement URI
- Updates rdfs:comment with deprecation notice
- Preserves all existing properties

Deprecation marks entities but does NOT rename or migrate references.
Use 'refactor rename' to actually migrate references after deprecation.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL, DCTERMS

from rdf_construct.refactor.config import DeprecationSpec, DeprecationConfig


# Dublin Core Terms namespace
DCTERMS = Namespace("http://purl.org/dc/terms/")


@dataclass
class EntityDeprecationInfo:
    """Information about a deprecated entity.

    Attributes:
        uri: URI of the deprecated entity.
        found: Whether the entity was found in the graph.
        current_labels: Current rdfs:label values.
        current_comments: Current rdfs:comment values.
        was_already_deprecated: Whether owl:deprecated was already present.
        triples_added: Number of triples added.
        reference_count: Number of references to this entity in the graph.
        replaced_by: Replacement entity URI (if specified).
        message: Deprecation message added.
    """

    uri: str
    found: bool = True
    current_labels: list[str] = field(default_factory=list)
    current_comments: list[str] = field(default_factory=list)
    was_already_deprecated: bool = False
    triples_added: int = 0
    reference_count: int = 0
    replaced_by: str | None = None
    message: str | None = None


@dataclass
class DeprecationStats:
    """Statistics from a deprecation operation.

    Attributes:
        entities_deprecated: Number of entities marked deprecated.
        entities_not_found: Number of entities not found in graph.
        entities_already_deprecated: Entities that were already deprecated.
        triples_added: Total triples added.
    """

    entities_deprecated: int = 0
    entities_not_found: int = 0
    entities_already_deprecated: int = 0
    triples_added: int = 0


@dataclass
class DeprecationResult:
    """Result of a deprecation operation.

    Attributes:
        deprecated_graph: The graph with deprecations added.
        stats: Deprecation statistics.
        success: Whether the operation succeeded.
        error: Error message if success is False.
        entity_info: Detailed info about each entity processed.
        source_triples: Original triple count.
        result_triples: Final triple count.
    """

    deprecated_graph: Graph | None = None
    stats: DeprecationStats = field(default_factory=DeprecationStats)
    success: bool = True
    error: str | None = None
    entity_info: list[EntityDeprecationInfo] = field(default_factory=list)
    source_triples: int = 0
    result_triples: int = 0


class OntologyDeprecator:
    """Marks ontology entities as deprecated.

    Adds standard OWL deprecation annotations:
    - owl:deprecated true
    - dcterms:isReplacedBy (if replacement specified)
    - Prepends "DEPRECATED: " to rdfs:comment

    Example usage:
        deprecator = OntologyDeprecator()
        result = deprecator.deprecate(
            graph,
            entity="http://example.org/OldClass",
            replaced_by="http://example.org/NewClass",
            message="Use NewClass instead."
        )
    """

    def deprecate(
        self,
        graph: Graph,
        entity: str,
        replaced_by: str | None = None,
        message: str | None = None,
        version: str | None = None,
    ) -> DeprecationResult:
        """Mark a single entity as deprecated.

        Args:
            graph: Source RDF graph (will be modified in-place).
            entity: URI of entity to deprecate.
            replaced_by: Optional URI of replacement entity.
            message: Optional deprecation message.
            version: Optional version when deprecated.

        Returns:
            DeprecationResult with updated graph.
        """
        result = DeprecationResult()
        result.source_triples = len(graph)

        entity_uri = URIRef(entity)
        info = EntityDeprecationInfo(uri=entity)

        # Check if entity exists in the graph
        entity_exists = False
        for s, p, o in graph:
            if s == entity_uri:
                entity_exists = True
                break
            if o == entity_uri:
                info.reference_count += 1

        if not entity_exists:
            # Entity not found as subject - check if it's referenced
            info.found = False
            result.stats.entities_not_found += 1
            result.entity_info.append(info)
            result.deprecated_graph = graph
            result.result_triples = len(graph)
            return result

        # Get current labels and comments
        for label in graph.objects(entity_uri, RDFS.label):
            if isinstance(label, Literal):
                info.current_labels.append(str(label))

        for comment in graph.objects(entity_uri, RDFS.comment):
            if isinstance(comment, Literal):
                info.current_comments.append(str(comment))

        # Check if already deprecated
        for obj in graph.objects(entity_uri, OWL.deprecated):
            if str(obj).lower() == "true":
                info.was_already_deprecated = True
                result.stats.entities_already_deprecated += 1
                break

        # Add owl:deprecated true (if not already present)
        if not info.was_already_deprecated:
            graph.add((entity_uri, OWL.deprecated, Literal(True)))
            info.triples_added += 1
            result.stats.entities_deprecated += 1

        # Add dcterms:isReplacedBy if replacement specified
        if replaced_by:
            replaced_by_uri = URIRef(replaced_by)
            # Remove any existing isReplacedBy
            graph.remove((entity_uri, DCTERMS.isReplacedBy, None))
            graph.add((entity_uri, DCTERMS.isReplacedBy, replaced_by_uri))
            info.triples_added += 1
            info.replaced_by = replaced_by

        # Add/update deprecation comment
        if message:
            # Build full deprecation message
            deprecation_msg = f"DEPRECATED: {message}"
            if version:
                deprecation_msg = f"DEPRECATED (v{version}): {message}"
            info.message = deprecation_msg

            # Check if there's an existing comment to update
            existing_deprecated_comment = None
            for comment in list(graph.objects(entity_uri, RDFS.comment)):
                if isinstance(comment, Literal) and str(comment).startswith("DEPRECATED"):
                    existing_deprecated_comment = comment
                    break

            if existing_deprecated_comment:
                # Remove old deprecation comment
                graph.remove((entity_uri, RDFS.comment, existing_deprecated_comment))

            # Add new deprecation comment
            graph.add((entity_uri, RDFS.comment, Literal(deprecation_msg, lang="en")))
            info.triples_added += 1

        # Ensure dcterms namespace is bound
        graph.bind("dcterms", DCTERMS, override=False)

        result.stats.triples_added += info.triples_added
        result.entity_info.append(info)
        result.deprecated_graph = graph
        result.result_triples = len(graph)
        result.success = True

        return result

    def deprecate_bulk(
        self,
        graph: Graph,
        specs: list[DeprecationSpec],
    ) -> DeprecationResult:
        """Mark multiple entities as deprecated.

        Args:
            graph: Source RDF graph (will be modified in-place).
            specs: List of deprecation specifications.

        Returns:
            DeprecationResult with updated graph.
        """
        combined_result = DeprecationResult()
        combined_result.source_triples = len(graph)

        for spec in specs:
            result = self.deprecate(
                graph=graph,
                entity=spec.entity,
                replaced_by=spec.replaced_by,
                message=spec.message,
                version=spec.version,
            )

            # Combine stats
            combined_result.stats.entities_deprecated += result.stats.entities_deprecated
            combined_result.stats.entities_not_found += result.stats.entities_not_found
            combined_result.stats.entities_already_deprecated += (
                result.stats.entities_already_deprecated
            )
            combined_result.stats.triples_added += result.stats.triples_added

            # Combine entity info
            combined_result.entity_info.extend(result.entity_info)

        combined_result.deprecated_graph = graph
        combined_result.result_triples = len(graph)
        combined_result.success = True

        return combined_result


def deprecate_file(
    source_path: Path,
    output_path: Path,
    specs: list[DeprecationSpec],
) -> DeprecationResult:
    """Convenience function to deprecate entities in a file.

    Args:
        source_path: Path to source RDF file.
        output_path: Path to write updated output.
        specs: List of deprecation specifications.

    Returns:
        DeprecationResult with statistics.
    """
    # Load source graph
    graph = Graph()
    try:
        graph.parse(source_path.as_posix())
    except Exception as e:
        result = DeprecationResult()
        result.success = False
        result.error = f"Failed to parse {source_path}: {e}"
        return result

    # Perform deprecation
    deprecator = OntologyDeprecator()
    result = deprecator.deprecate_bulk(graph, specs)

    if not result.success:
        return result

    # Write output
    if result.deprecated_graph:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.deprecated_graph.serialize(destination=output_path.as_posix(), format="turtle")

    return result


def generate_deprecation_message(
    replaced_by: str | None,
    message: str | None,
    version: str | None,
) -> str:
    """Generate a standard deprecation message.

    Args:
        replaced_by: Replacement entity URI.
        message: Custom message.
        version: Version when deprecated.

    Returns:
        Formatted deprecation message.
    """
    if message:
        return message

    if replaced_by:
        # Extract local name from URI
        local_name = replaced_by.split("#")[-1].split("/")[-1]
        return f"Use {local_name} instead."

    return "This entity is deprecated and should not be used."
