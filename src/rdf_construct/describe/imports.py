"""Import analysis for ontology description.

Handles owl:imports declarations and optional resolvability checking.
"""

import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Optional

from rdflib import Graph, URIRef
from rdflib.namespace import OWL

from rdf_construct.describe.models import ImportAnalysis, ImportInfo, ImportStatus


# Timeout for HTTP requests (seconds)
REQUEST_TIMEOUT = 10

# Maximum concurrent resolution checks
MAX_WORKERS = 5


def analyse_imports(
    graph: Graph,
    resolve: bool = True,
    timeout: int = REQUEST_TIMEOUT,
) -> ImportAnalysis:
    """Analyse owl:imports declarations in the ontology.

    Args:
        graph: RDF graph to analyse.
        resolve: Whether to check resolvability of imports.
        timeout: Timeout for resolution checks in seconds.

    Returns:
        ImportAnalysis with import information.
    """
    # Find all owl:imports declarations
    import_uris: list[URIRef] = []
    for ontology in graph.subjects(None, OWL.Ontology):
        for import_uri in graph.objects(ontology, OWL.imports):
            if isinstance(import_uri, URIRef):
                import_uris.append(import_uri)

    if not import_uris:
        return ImportAnalysis(imports=[], resolve_attempted=False)

    # Build import info list
    imports: list[ImportInfo] = []

    if resolve:
        # Resolve imports in parallel with timeout
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_check_resolvable, str(uri), timeout): uri
                for uri in import_uris
            }

            for future in futures:
                uri = futures[future]
                try:
                    status, error = future.result(timeout=timeout + 5)
                    imports.append(ImportInfo(
                        uri=str(uri),
                        status=status,
                        error=error,
                    ))
                except FuturesTimeout:
                    imports.append(ImportInfo(
                        uri=str(uri),
                        status=ImportStatus.UNRESOLVABLE,
                        error="Resolution timed out",
                    ))
                except Exception as e:
                    imports.append(ImportInfo(
                        uri=str(uri),
                        status=ImportStatus.UNRESOLVABLE,
                        error=str(e),
                    ))
    else:
        # Just list imports without resolution
        imports = [
            ImportInfo(uri=str(uri), status=ImportStatus.UNCHECKED)
            for uri in import_uris
        ]

    return ImportAnalysis(
        imports=imports,
        resolve_attempted=resolve,
    )


def _check_resolvable(uri: str, timeout: int) -> tuple[ImportStatus, Optional[str]]:
    """Check if a URI is resolvable via HTTP HEAD request.

    Args:
        uri: URI to check.
        timeout: Request timeout in seconds.

    Returns:
        Tuple of (status, error_message).
    """
    try:
        # Create a HEAD request to check resolvability without downloading
        request = urllib.request.Request(
            uri,
            method="HEAD",
            headers={
                "Accept": "application/rdf+xml, text/turtle, application/ld+json, */*",
                "User-Agent": "rdf-construct/describe",
            },
        )

        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status == 200:
                return ImportStatus.RESOLVABLE, None
            else:
                return ImportStatus.UNRESOLVABLE, f"HTTP {response.status}"

    except urllib.error.HTTPError as e:
        # Some servers don't support HEAD but work with GET
        if e.code == 405:  # Method Not Allowed
            return _try_get_request(uri, timeout)
        return ImportStatus.UNRESOLVABLE, f"HTTP {e.code}: {e.reason}"

    except urllib.error.URLError as e:
        return ImportStatus.UNRESOLVABLE, f"Network error: {e.reason}"

    except TimeoutError:
        return ImportStatus.UNRESOLVABLE, "Request timed out"

    except Exception as e:
        return ImportStatus.UNRESOLVABLE, str(e)


def _try_get_request(uri: str, timeout: int) -> tuple[ImportStatus, Optional[str]]:
    """Fall back to GET request if HEAD is not allowed.

    Args:
        uri: URI to check.
        timeout: Request timeout in seconds.

    Returns:
        Tuple of (status, error_message).
    """
    try:
        request = urllib.request.Request(
            uri,
            headers={
                "Accept": "application/rdf+xml, text/turtle, application/ld+json, */*",
                "User-Agent": "rdf-construct/describe",
            },
        )

        # Only read a small amount to check availability
        with urllib.request.urlopen(request, timeout=timeout) as response:
            # Read just enough to confirm it's responding
            response.read(1024)
            return ImportStatus.RESOLVABLE, None

    except urllib.error.HTTPError as e:
        return ImportStatus.UNRESOLVABLE, f"HTTP {e.code}: {e.reason}"

    except urllib.error.URLError as e:
        return ImportStatus.UNRESOLVABLE, f"Network error: {e.reason}"

    except Exception as e:
        return ImportStatus.UNRESOLVABLE, str(e)


def get_imported_namespaces(graph: Graph) -> set[str]:
    """Get the namespace URIs of imported ontologies.

    Used for namespace categorisation.

    Args:
        graph: RDF graph to analyse.

    Returns:
        Set of namespace URI strings.
    """
    namespaces = set()

    for ontology in graph.subjects(None, OWL.Ontology):
        for import_uri in graph.objects(ontology, OWL.imports):
            if isinstance(import_uri, URIRef):
                # The import URI is typically the namespace or close to it
                ns = _extract_namespace(str(import_uri))
                namespaces.add(ns)

    return namespaces


def _extract_namespace(uri: str) -> str:
    """Extract namespace from an ontology URI.

    Args:
        uri: Ontology URI.

    Returns:
        Namespace string.
    """
    # Common patterns:
    # - http://example.org/ontology# -> http://example.org/ontology#
    # - http://example.org/ontology/ -> http://example.org/ontology/
    # - http://example.org/ontology -> http://example.org/ontology#

    if uri.endswith("#") or uri.endswith("/"):
        return uri

    # Add hash if no separator at end
    return uri + "#"
