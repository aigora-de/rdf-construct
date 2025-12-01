"""Search index generation for client-side documentation search."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rdf_construct.docs.config import DocsConfig
    from rdf_construct.docs.extractors import ClassInfo, ExtractedEntities, InstanceInfo, PropertyInfo


@dataclass
class SearchEntry:
    """A single entry in the search index."""

    uri: str
    qname: str
    entity_type: str  # class, object_property, datatype_property, instance
    label: str
    keywords: list[str]
    url: str


def extract_keywords(text: str | None) -> list[str]:
    """Extract searchable keywords from text.

    Splits on whitespace and punctuation, lowercases, and removes
    common stop words.

    Args:
        text: Text to extract keywords from.

    Returns:
        List of keyword strings.
    """
    if not text:
        return []

    # Split on non-alphanumeric characters
    words = re.split(r"[^a-zA-Z0-9]+", text.lower())

    # Remove stop words and short words
    stop_words = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "shall",
        "can", "need", "of", "to", "in", "for", "on", "with", "at",
        "by", "from", "as", "or", "and", "but", "if", "this", "that",
        "which", "who", "whom", "whose", "what", "when", "where", "why",
        "how", "all", "each", "every", "both", "few", "more", "most",
        "other", "some", "such", "no", "not", "only", "same", "so",
        "than", "too", "very", "just", "also", "any",
    }

    keywords = [w for w in words if w and len(w) > 2 and w not in stop_words]
    return list(set(keywords))  # Remove duplicates


def class_to_search_entry(
    class_info: "ClassInfo",
    config: "DocsConfig",
) -> SearchEntry:
    """Convert a ClassInfo to a SearchEntry.

    Args:
        class_info: Class information.
        config: Documentation configuration.

    Returns:
        SearchEntry for the class.
    """
    # Build keywords from various sources
    keywords = []

    # QName parts
    if ":" in class_info.qname:
        prefix, local = class_info.qname.split(":", 1)
        keywords.extend(extract_keywords(local))
        keywords.append(prefix.lower())

    # Label
    if class_info.label:
        keywords.extend(extract_keywords(class_info.label))

    # Definition
    if class_info.definition:
        keywords.extend(extract_keywords(class_info.definition))

    # Superclass names
    for uri in class_info.superclasses:
        if "#" in str(uri):
            keywords.extend(extract_keywords(str(uri).split("#")[-1]))
        elif "/" in str(uri):
            keywords.extend(extract_keywords(str(uri).split("/")[-1]))

    from .config import entity_to_url
    return SearchEntry(
        uri=str(class_info.uri),
        qname=class_info.qname,
        entity_type="class",
        label=class_info.label or class_info.qname,
        keywords=list(set(keywords)),
        url=entity_to_url(class_info.qname, "class", config),
    )


def property_to_search_entry(
    prop_info: "PropertyInfo",
    config: "DocsConfig",
) -> SearchEntry:
    """Convert a PropertyInfo to a SearchEntry.

    Args:
        prop_info: Property information.
        config: Documentation configuration.

    Returns:
        SearchEntry for the property.
    """
    keywords = []

    # QName parts
    if ":" in prop_info.qname:
        prefix, local = prop_info.qname.split(":", 1)
        keywords.extend(extract_keywords(local))
        keywords.append(prefix.lower())

    # Label
    if prop_info.label:
        keywords.extend(extract_keywords(prop_info.label))

    # Definition
    if prop_info.definition:
        keywords.extend(extract_keywords(prop_info.definition))

    # Property type
    keywords.append(prop_info.property_type)

    # Domain/range class names
    for uri in prop_info.domain + prop_info.range:
        if "#" in str(uri):
            keywords.extend(extract_keywords(str(uri).split("#")[-1]))
        elif "/" in str(uri):
            keywords.extend(extract_keywords(str(uri).split("/")[-1]))

    entity_type = f"{prop_info.property_type}_property"

    from .config import entity_to_url
    return SearchEntry(
        uri=str(prop_info.uri),
        qname=prop_info.qname,
        entity_type=entity_type,
        label=prop_info.label or prop_info.qname,
        keywords=list(set(keywords)),
        url=entity_to_url(prop_info.qname, entity_type, config),
    )


def instance_to_search_entry(
    instance_info: "InstanceInfo",
    config: "DocsConfig",
) -> SearchEntry:
    """Convert an InstanceInfo to a SearchEntry.

    Args:
        instance_info: Instance information.
        config: Documentation configuration.

    Returns:
        SearchEntry for the instance.
    """
    keywords = []

    # QName parts
    if ":" in instance_info.qname:
        prefix, local = instance_info.qname.split(":", 1)
        keywords.extend(extract_keywords(local))
        keywords.append(prefix.lower())

    # Label
    if instance_info.label:
        keywords.extend(extract_keywords(instance_info.label))

    # Definition
    if instance_info.definition:
        keywords.extend(extract_keywords(instance_info.definition))

    # Type names
    for uri in instance_info.types:
        if "#" in str(uri):
            keywords.extend(extract_keywords(str(uri).split("#")[-1]))
        elif "/" in str(uri):
            keywords.extend(extract_keywords(str(uri).split("/")[-1]))

    # Add "instance" as a keyword
    keywords.append("instance")

    from .config import entity_to_url
    return SearchEntry(
        uri=str(instance_info.uri),
        qname=instance_info.qname,
        entity_type="instance",
        label=instance_info.label or instance_info.qname,
        keywords=list(set(keywords)),
        url=entity_to_url(instance_info.qname, "instance", config),
    )


def generate_search_index(
    entities: "ExtractedEntities",
    config: "DocsConfig",
) -> list[SearchEntry]:
    """Generate a search index from extracted entities.

    Args:
        entities: All extracted entities from the ontology.
        config: Documentation configuration.

    Returns:
        List of SearchEntry objects for all entities.
    """
    entries: list[SearchEntry] = []

    # Classes
    if config.include_classes:
        for class_info in entities.classes:
            entries.append(class_to_search_entry(class_info, config))

    # Properties
    if config.include_object_properties:
        for prop_info in entities.object_properties:
            entries.append(property_to_search_entry(prop_info, config))

    if config.include_datatype_properties:
        for prop_info in entities.datatype_properties:
            entries.append(property_to_search_entry(prop_info, config))

    if config.include_annotation_properties:
        for prop_info in entities.annotation_properties:
            entries.append(property_to_search_entry(prop_info, config))

    # Instances
    if config.include_instances:
        for instance_info in entities.instances:
            entries.append(instance_to_search_entry(instance_info, config))

    return entries


def write_search_index(
    entries: list[SearchEntry],
    output_dir: Path,
) -> Path:
    """Write the search index to a JSON file.

    Args:
        entries: List of search entries.
        output_dir: Output directory.

    Returns:
        Path to the written search index file.
    """
    output_path = output_dir / "search.json"

    # Convert to serialisable format
    data = {
        "entities": [asdict(entry) for entry in entries],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    return output_path
