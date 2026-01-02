"""JSON formatter for ontology description output.

Produces structured JSON for programmatic consumption.
"""

import json
from typing import Any

from rdf_construct.describe.models import OntologyDescription


def format_json(
    description: OntologyDescription,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> str:
    """Format ontology description as JSON.

    Args:
        description: OntologyDescription to format.
        indent: Indentation level for pretty printing.
        ensure_ascii: If True, escape non-ASCII characters.

    Returns:
        JSON string.
    """
    data = description.to_dict()

    return json.dumps(
        data,
        indent=indent,
        ensure_ascii=ensure_ascii,
        default=_json_serializer,
    )


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for non-standard types.

    Args:
        obj: Object to serialize.

    Returns:
        JSON-serializable representation.

    Raises:
        TypeError: If object cannot be serialized.
    """
    # Handle Path objects
    if hasattr(obj, "__fspath__"):
        return str(obj)

    # Handle datetime
    if hasattr(obj, "isoformat"):
        return obj.isoformat()

    # Handle enums
    if hasattr(obj, "value"):
        return obj.value

    # Handle dataclasses with to_dict method
    if hasattr(obj, "to_dict"):
        return obj.to_dict()

    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
