"""Tests for strict CURIE resolution and namespace-boundary matching in ``core.utils``.

``resolve_curie`` (#182) never returns its input verbatim and never consults rdflib's built-in
prefix table. ``in_namespace`` and ``rebase_iri`` (#184) match a namespace at a boundary rather
than as a string prefix: a namespace ending in anything but a letter or a digit is a plain
prefix (#422), and a ``:`` inside an IRI's authority is never a boundary (#423).
``claiming_namespace`` and ``rebase_by_rules`` resolve overlapping rules by the longest match
(#424).
"""

import pytest
from rdflib import Graph, URIRef

from rdf_construct.core import (
    CurieError,
    claiming_namespace,
    expand_curie,
    extract_prefix_map,
    in_namespace,
    nested_rules,
    rebase_by_rules,
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

    @pytest.mark.parametrize(
        ("namespace", "iri"),
        [
            ("http://purl.obolibrary.org/obo/GO_", "http://purl.obolibrary.org/obo/GO_0008150"),
            ("http://example.org/items?id=", "http://example.org/items?id=7"),
            ("http://example.org/term-", "http://example.org/term-42"),
            ("http://example.org/v1.", "http://example.org/v1.Thing"),
        ],
    )
    def test_a_stem_is_a_plain_prefix(self, namespace: str, iri: str) -> None:
        assert in_namespace(iri, namespace)
        assert (
            rebase_iri(iri, namespace, "http://n.org/") == "http://n.org/" + iri[len(namespace) :]
        )

    def test_a_stem_still_needs_its_whole_text(self) -> None:
        assert not in_namespace(
            "http://purl.obolibrary.org/obo/GOX_1", "http://purl.obolibrary.org/obo/GO_"
        )
        assert not in_namespace("http://example.org/items?id=7", "http://example.org/items?id")

    @pytest.mark.parametrize(
        "iri",
        ["http://example.org:8080/a#X", "http://example.org:8080", "https://example.org:443/"],
    )
    def test_a_port_is_another_authority(self, iri: str) -> None:
        namespace = iri.split(":")[0] + "://example.org"
        assert not in_namespace(iri, namespace)
        assert in_namespace(iri.split(":")[0] + "://example.org/ont#Y", namespace)

    def test_a_namespace_may_name_the_port(self) -> None:
        assert in_namespace("http://example.org:8080/a#X", "http://example.org:8080")
        assert not in_namespace("http://example.org:80801/a#X", "http://example.org:8080")

    def test_colons_in_user_information_are_not_boundaries(self) -> None:
        assert not in_namespace("http://user:pw@example.org/a", "http://user")

    @pytest.mark.parametrize("namespace", ["http://example.org:", "http://example.", "http://ex"])
    def test_a_namespace_that_ends_within_the_authority_takes_nothing_more(
        self, namespace: str
    ) -> None:
        assert not in_namespace("http://example.org:8080/a#X", namespace)
        assert not in_namespace("http://example.org/a#X", namespace)

    @pytest.mark.parametrize("namespace", ["http://", "http:", "http"])
    def test_a_namespace_before_the_authority_takes_the_scheme(self, namespace: str) -> None:
        assert in_namespace("http://example.org:8080/a#X", namespace)

    def test_ipv6_literal(self) -> None:
        assert in_namespace("http://[::1]/a#X", "http://[::1]")
        assert in_namespace("http://[::1]", "http://[::1]")
        assert not in_namespace("http://[::1]:8080/a#X", "http://[::1]")

    def test_colon_after_the_authority_is_a_boundary(self) -> None:
        assert in_namespace("http://example.org/a:b", "http://example.org/a")
        assert in_namespace("tag:example.org,2026:a:b", "tag:example.org,2026")


class TestLongestRule:
    """Overlapping rules resolve by the longest match, whatever their order (#424)."""

    RULES = {
        "http://e.org/core/": "http://n.org/core/",
        "http://e.org/core/sub/": "http://n.org/sub/",
    }

    @pytest.mark.parametrize("reverse", [False, True])
    def test_the_longest_rule_wins_in_either_order(self, reverse: bool) -> None:
        rules = dict(reversed(self.RULES.items())) if reverse else dict(self.RULES)
        assert rebase_by_rules("http://e.org/core/A", rules) == "http://n.org/core/A"
        assert rebase_by_rules("http://e.org/core/sub/B", rules) == "http://n.org/sub/B"
        assert rebase_by_rules("http://e.org/other/C", rules) is None

    def test_one_pass_never_chains(self) -> None:
        rules = {"http://a.org/": "http://b.org/", "http://b.org/": "http://c.org/"}
        assert rebase_by_rules("http://a.org/X", rules) == "http://b.org/X"

    def test_the_boundary_rule_applies(self) -> None:
        rules = {"http://example.org/ont": "http://n.org/ont", "http://example.org": "http://x.org"}
        assert rebase_by_rules("http://example.org/ontology#Two", rules) == (
            "http://x.org/ontology#Two"
        )
        assert rebase_by_rules("http://example.org:8080/a#X", rules) is None

    @pytest.mark.parametrize(
        ("iri", "expected"),
        [
            ("http://e.org/core/sub/B", "http://e.org/core/sub/"),
            ("http://e.org/core/A", "http://e.org/core/"),
            ("http://e.org/coreX/A", None),
        ],
    )
    def test_claiming_namespace(self, iri: str, expected: str | None) -> None:
        assert claiming_namespace(iri, self.RULES) == expected

    def test_nested_rules_are_named(self) -> None:
        rules = [*self.RULES, "http://x.org/", "http://example.org", "http://example.org:8080/"]
        assert nested_rules(rules) == [("http://e.org/core/sub/", "http://e.org/core/")]
        assert nested_rules(["http://x.org/"]) == []
