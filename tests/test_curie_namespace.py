"""Tests for strict CURIE resolution and namespace-boundary matching in ``core.utils``.

``resolve_curie`` (#182) never returns its input verbatim and never consults rdflib's built-in
prefix table. ``in_namespace`` and ``rebase_iri`` (#184) match a namespace at a boundary rather
than as a string prefix.
"""

import pytest
from rdflib import Graph, URIRef

from rdf_construct.core import (
    CurieError,
    expand_curie,
    extract_prefix_map,
    in_namespace,
    rebase_iri,
    resolve_curie,
)

PREFIXES = {
    "ex": "http://example.org/ont#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}

ONT = "http://example.org/ont"


class TestResolveCurie:
    """The forms ``resolve_curie`` accepts, and what it refuses."""

    def test_bound_prefix(self) -> None:
        assert resolve_curie(PREFIXES, "ex:Building") == URIRef("http://example.org/ont#Building")

    def test_surrounding_whitespace_is_ignored(self) -> None:
        assert resolve_curie(PREFIXES, "  ex:Building ") == URIRef(
            "http://example.org/ont#Building"
        )

    def test_bracketed_iri_is_taken_verbatim(self) -> None:
        assert resolve_curie(PREFIXES, "<urn:isbn:0451450523>") == URIRef("urn:isbn:0451450523")

    def test_bracketed_iri_is_not_expanded_even_when_it_looks_like_a_curie(self) -> None:
        assert resolve_curie(PREFIXES, "<ex:Building>") == URIRef("ex:Building")

    def test_full_iri(self) -> None:
        assert resolve_curie({}, "http://example.org/ont#Building") == URIRef(
            "http://example.org/ont#Building"
        )

    def test_bound_prefix_wins_over_a_scheme(self) -> None:
        # A Turtle prefixed name: once `urn` is bound, `urn:x` is a CURIE.
        assert resolve_curie({"urn": "http://example.org/u#"}, "urn:x") == URIRef(
            "http://example.org/u#x"
        )

    def test_unbound_prefix_is_refused_and_lists_the_bound_ones(self) -> None:
        with pytest.raises(CurieError) as excinfo:
            resolve_curie(PREFIXES, "zz:Building")
        assert excinfo.value.prefix == "zz"
        assert excinfo.value.bound == ("ex", "rdfs")
        assert "'zz' is not bound" in str(excinfo.value)
        assert "ex, rdfs" in str(excinfo.value)

    def test_bare_urn_is_refused_with_the_bracket_hint(self) -> None:
        with pytest.raises(CurieError, match=r"angle brackets \(<urn:…>\)"):
            resolve_curie(PREFIXES, "urn:isbn:0451450523")

    @pytest.mark.parametrize("text", ["", "   ", "Building", "<>"])
    def test_neither_curie_nor_iri_is_refused(self, text: str) -> None:
        with pytest.raises(CurieError, match="not a CURIE or an IRI"):
            resolve_curie(PREFIXES, text)

    def test_rdflib_default_table_is_not_consulted(self) -> None:
        """A file's own org: is the org: that resolves, and schema: was never declared.

        ``expand_curie`` over a bare ``Graph()`` gets both wrong, which is why the strict
        function exists beside it rather than replacing it.
        """
        source = "@prefix org: <http://example.org/myorg#> .\norg:Team a org:Unit .\n"
        legacy = Graph().parse(data=source, format="turtle")
        assert expand_curie(legacy, "org:Team") == URIRef("http://www.w3.org/ns/org#Team")

        graph = Graph(bind_namespaces="core").parse(data=source, format="turtle")
        prefixes = extract_prefix_map(graph)
        assert resolve_curie(prefixes, "org:Team") == URIRef("http://example.org/myorg#Team")
        assert resolve_curie(prefixes, "rdfs:label") == URIRef(
            "http://www.w3.org/2000/01/rdf-schema#label"
        )
        with pytest.raises(CurieError):
            resolve_curie(prefixes, "schema:Person")


class TestNamespaceBoundary:
    """#184's family: ``…/ont#``, ``…/ontology#`` and ``…/ont/extra#``."""

    @pytest.mark.parametrize(
        ("iri", "expected"),
        [
            (f"{ONT}#One", True),
            (f"{ONT}/extra#Three", True),
            (ONT, True),
            ("http://example.org/ontology#Two", False),
            ("http://example.org/on", False),
        ],
    )
    def test_without_a_delimiter_the_match_ends_at_a_boundary(
        self, iri: str, expected: bool
    ) -> None:
        assert in_namespace(iri, ONT) is expected

    @pytest.mark.parametrize(
        ("iri", "expected"),
        [
            (f"{ONT}#One", True),
            (f"{ONT}/extra#Three", False),
            (ONT, False),
            ("http://example.org/ontology#Two", False),
        ],
    )
    def test_with_a_hash_it_names_one_namespace(self, iri: str, expected: bool) -> None:
        assert in_namespace(iri, f"{ONT}#") is expected

    def test_with_a_slash_it_takes_the_subtree(self) -> None:
        assert in_namespace("http://example.org/ontology#Two", "http://example.org/")
        assert in_namespace("http://example.org/a/b/c", "http://example.org/")

    @pytest.mark.parametrize("namespace", ["urn:old:", "urn:old"])
    def test_colon_is_a_delimiter_for_urn_namespaces(self, namespace: str) -> None:
        assert in_namespace("urn:old:A", namespace)
        assert not in_namespace("urn:older:C", namespace)
        assert rebase_iri("urn:old:A", namespace, namespace.replace("old", "new")) == "urn:new:A"

    def test_empty_namespace_matches_nothing(self) -> None:
        assert not in_namespace("http://example.org/ont#One", "")

    def test_rebase(self) -> None:
        new = "http://example.org/NEW"
        assert rebase_iri(f"{ONT}#One", ONT, new) == f"{new}#One"
        assert rebase_iri(f"{ONT}/extra#Three", ONT, new) == f"{new}/extra#Three"
        assert rebase_iri("http://example.org/ontology#Two", ONT, new) is None
