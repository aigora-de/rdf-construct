"""Smoke tests for the pinned IES ontologies in ``tests/fixtures/ies/``.

Every other fixture in the repository was written for this tool, which makes
them toys: they exercise what their author thought of. The three IES files were
not written for it. They are committed verbatim from pinned upstream commits
(see ``tests/fixtures/ies/README.md``) so that the release checklist, and the
regression tests that need a realistic ontology, have one to run against.

That value depends on the copies staying verbatim. These tests fail if a file
is swapped for another upstream version, trimmed, or rewritten in any byte,
including whitespace stripped by a formatter or line endings converted on
checkout.

Relates to: #307
"""

import hashlib
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF

IES_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ies"

# (file, git blob SHA at the pinned upstream commit, {ontology IRI: owl:versionInfo})
PINNED = [
    (
        "ies-common.ttl",
        "fbe5fc7fbd39c59546d1d8acc9aa9b291cb151fa",
        {"http://informationexchangestandard.org/ont/ies/common/": "5.0.3"},
    ),
    (
        "ies-env-building.ttl",
        "cacf389cf61241bfa207c563544297e74170c5f4",
        {
            "http://informationexchangestandard.org/ont/ies/env/building/": "1.0.0",
            # The file declares a second owl:Ontology header (#90, #171, #178).
            "http://informationexchangestandard.org/ont/ies/env/": "0.1.0-rc1",
        },
    ),
    (
        "ies-env-building-classification.ttl",
        "b8a354e32219d6e85b7402531821a5ba8c728e43",
        {"http://informationexchangestandard.org/ont/ies/env/building-classification/": "1.0.0"},
    ),
]


def _git_blob_sha(data: bytes) -> str:
    """Return the SHA-1 git assigns these bytes as a blob.

    It is the hash GitHub reports for the file at the pinned commit, so a
    mismatch can be checked against upstream directly.
    """
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


@pytest.mark.parametrize(
    ("filename", "blob_sha", "versions"),
    PINNED,
    ids=[filename for filename, _, _ in PINNED],
)
class TestPinnedIesOntology:
    """Each pinned file is byte-identical to upstream, parses, and declares its version."""

    def test_bytes_match_the_pinned_commit(
        self, filename: str, blob_sha: str, versions: dict[str, str]
    ) -> None:
        data = (IES_FIXTURES / filename).read_bytes()
        assert (
            _git_blob_sha(data) == blob_sha
        ), f"{filename} differs from the pinned upstream blob; see tests/fixtures/ies/README.md"

    def test_parses_and_declares_its_version(
        self, filename: str, blob_sha: str, versions: dict[str, str]
    ) -> None:
        graph = Graph().parse(IES_FIXTURES / filename, format="turtle")

        declared = {str(o) for o in graph.subjects(RDF.type, OWL.Ontology)}
        assert declared == set(versions)

        for iri, version in versions.items():
            assert list(graph.objects(URIRef(iri), OWL.versionInfo)) == [Literal(version)]
