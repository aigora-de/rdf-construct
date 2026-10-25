"""Translation coverage reporting.

Analyses ontologies and reports translation coverage across languages,
identifying missing translations and tracking progress.

Coverage is counted in **entities**, not literals (#158). For each property, the denominator is
the entities carrying that property in at least one language, and a language's figure is how many
of them carry it in that language. The source language is measured the same way, so its row says
how much of the labelled material exists in the source language. A second literal in one language
adds nothing to the figure; for a per-language property such as ``rdfs:label`` it is reported as
a duplicate instead. Which subjects are entities, and which literals are in which language, is
defined once in :mod:`rdf_construct.localise.entities`.
"""

from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph, URIRef

from rdf_construct.core.predicate_tiers import (
    DEFAULT_PREDICATE_TIERS,
    PredicateTier,
    tier_of,
)
from rdf_construct.localise.entities import (
    collect_entities,
    in_language,
    is_deprecated,
    literals,
    related_tags,
    zero_match_warnings,
)


def percent(covered: int, total: int) -> int:
    """Return `covered` as a whole percentage of `total`, the figure a report prints.

    Rounded half up, except that an incomplete figure is never 100 and a non-zero one never 0.
    A status drawn from it therefore agrees with the printed percentage. 0 when `total` is 0.
    """
    if total == 0:
        return 0
    value = (200 * covered + total) // (2 * total)  # half up, in integers
    if covered < total:
        value = min(value, 99)
    if covered > 0:
        value = max(value, 1)
    return value


def format_fraction(covered: int, total: int) -> str:
    """Format a coverage figure as counts beside a percentage: ``42/57 (74%)``.

    The percentage is rounded half up, except that an incomplete figure never reads 100% and a non-zero
    one never reads 0%. A figure with nothing to measure reads ``0/0 (—)``.

    Args:
        covered: Entities covered.
        total: Entities measured.

    Returns:
        The formatted figure.
    """
    if total == 0:
        return "0/0 (—)"
    return f"{covered}/{total} ({percent(covered, total)}%)"


@dataclass
class PropertyCoverage:
    """Coverage for a single property.

    Attributes:
        property: Property URI (shortened).
        total: Entities carrying the property in at least one language.
        translated: Of those, the entities carrying it in this language.
    """

    property: str
    total: int = 0
    translated: int = 0

    @property
    def coverage(self) -> float:
        """Coverage percentage."""
        if self.total == 0:
            return 0.0
        return (self.translated / self.total) * 100


@dataclass
class LanguageCoverage:
    """Coverage statistics for a single language.

    Attributes:
        language: Language code.
        is_source: Whether this is the source language.
        total_strings: Entity and property pairs measured: the sum of every property's total.
        translated: Of those, the pairs present in this language.
        by_property: Coverage broken down by property.
        missing_entities: URIs of entities missing this language for a property they carry.
        duplicates: (entity URI, property) pairs with more than one literal in this language,
            for a property that takes one value per language.
    """

    language: str
    is_source: bool = False
    total_strings: int = 0
    translated: int = 0
    by_property: dict[str, PropertyCoverage] = field(default_factory=dict)
    missing_entities: list[str] = field(default_factory=list)
    duplicates: list[tuple[str, str]] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        """Overall coverage percentage."""
        if self.total_strings == 0:
            return 0.0
        return (self.translated / self.total_strings) * 100

    @property
    def pending(self) -> int:
        """Number of pending translations."""
        return self.total_strings - self.translated


@dataclass
class CoverageReport:
    """Complete translation coverage report.

    Attributes:
        source_file: Source ontology file.
        source_language: Base language.
        total_entities: Entities measured.
        properties: Properties analysed.
        languages: Coverage by language.
        deprecated_entities: Deprecated entities left out of every figure (0 when they are
            included).
        warnings: Languages that matched no literal while a related tag did (#159). Each one
            means the report could not answer what it was asked.
    """

    source_file: str
    source_language: str
    total_entities: int = 0
    properties: list[str] = field(default_factory=list)
    languages: dict[str, LanguageCoverage] = field(default_factory=dict)
    deprecated_entities: int = 0
    warnings: list[str] = field(default_factory=list)


class CoverageReporter:
    """Analyses and reports translation coverage.

    The reporter examines an ontology and determines what percentage
    of translatable content has been translated into each target language.
    """

    def __init__(
        self,
        source_language: str = "en",
        properties: list[str] | None = None,
        include_deprecated: bool = False,
    ):
        """Initialise the reporter.

        Args:
            source_language: Base language code.
            properties: Properties to check. Uses defaults if not provided.
            include_deprecated: Count deprecated entities. By default they are left out, as
                ``extract`` leaves them out.
        """
        self.source_language = source_language
        self.include_deprecated = include_deprecated
        self.properties = properties or [
            "http://www.w3.org/2000/01/rdf-schema#label",
            "http://www.w3.org/2000/01/rdf-schema#comment",
        ]

    def report(
        self,
        graph: Graph,
        languages: list[str],
        source_file: str | Path = "",
    ) -> CoverageReport:
        """Generate coverage report for specified languages.

        Args:
            graph: RDF graph to analyse.
            languages: List of language codes to check.
            source_file: Source file path for metadata.

        Returns:
            CoverageReport with detailed statistics.
        """
        # Collect entities
        prop_uris = [URIRef(p) for p in self.properties]
        entities = collect_entities(graph, prop_uris)
        deprecated = 0
        if not self.include_deprecated:
            kept = [entity for entity in entities if not is_deprecated(graph, entity)]
            deprecated = len(entities) - len(kept)
            entities = kept

        # Build report
        report = CoverageReport(
            source_file=str(source_file),
            source_language=self.source_language,
            total_entities=len(entities),
            properties=[self._shorten_property(p) for p in self.properties],
            deprecated_entities=deprecated,
        )

        # The source language first, then each target once, compared without regard to case
        measured = [(self.source_language, True, "--source-language")]
        seen = {self.source_language.lower()}
        for lang in languages:
            if lang.lower() not in seen:
                seen.add(lang.lower())
                measured.append((lang, False, "-l"))

        for lang, is_source, flag in measured:
            coverage = self._analyse_language(graph, entities, lang, is_source=is_source)
            report.languages[lang] = coverage
            if coverage.translated == 0:
                found = related_tags(graph, entities, prop_uris, lang)
                report.warnings.extend(zero_match_warnings(found, lang, flag))

        return report

    def _analyse_language(
        self,
        graph: Graph,
        entities: list[URIRef],
        language: str,
        is_source: bool = False,
    ) -> LanguageCoverage:
        """Analyse coverage for a single language.

        Args:
            graph: RDF graph.
            entities: List of entity URIs.
            language: Language code to analyse.
            is_source: Whether this is the source language.

        Returns:
            LanguageCoverage statistics.
        """
        coverage = LanguageCoverage(
            language=language,
            is_source=is_source,
        )

        # Initialise property coverage
        for prop_uri_str in self.properties:
            short_prop = self._shorten_property(prop_uri_str)
            coverage.by_property[short_prop] = PropertyCoverage(property=short_prop)

        missing: list[str] = []

        for entity in entities:
            entity_missing_any = False

            for prop_uri_str in self.properties:
                prop_uri = URIRef(prop_uri_str)
                short_prop = self._shorten_property(prop_uri_str)

                values = literals(graph, entity, prop_uri)
                if not values:
                    continue

                # The entity carries the property, so it is measured for every language
                coverage.by_property[short_prop].total += 1
                coverage.total_strings += 1

                count = sum(
                    1 for value in values if in_language(value, language, self.source_language)
                )
                if count > 0:
                    coverage.by_property[short_prop].translated += 1
                    coverage.translated += 1
                else:
                    entity_missing_any = True

                if count > 1 and (
                    tier_of(prop_uri, DEFAULT_PREDICATE_TIERS) is PredicateTier.PER_LANGUAGE
                ):
                    coverage.duplicates.append((str(entity), short_prop))

            if entity_missing_any:
                missing.append(str(entity))

        coverage.missing_entities = missing
        return coverage

    def _shorten_property(self, prop: str) -> str:
        """Shorten a full URI to CURIE if possible.

        Args:
            prop: Full property URI.

        Returns:
            CURIE or original URI.
        """
        namespaces = {
            "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
            "http://www.w3.org/2004/02/skos/core#": "skos:",
            "http://www.w3.org/2002/07/owl#": "owl:",
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
            "http://purl.org/dc/elements/1.1/": "dc:",
            "http://purl.org/dc/terms/": "dcterms:",
        }

        for namespace, prefix in namespaces.items():
            if prop.startswith(namespace):
                return prefix + prop[len(namespace) :]

        return prop


def generate_coverage_report(
    source: Path,
    languages: list[str],
    source_language: str = "en",
    properties: list[str] | None = None,
    include_deprecated: bool = False,
) -> CoverageReport:
    """Generate translation coverage report for an ontology.

    Convenience function for simple reporting.

    Args:
        source: Source ontology file.
        languages: List of language codes to check.
        source_language: Base language code.
        properties: Properties to analyse.
        include_deprecated: Count deprecated entities.

    Returns:
        CoverageReport with detailed statistics.
    """
    # Load graph
    graph = Graph()
    graph.parse(source)

    # Report
    reporter = CoverageReporter(
        source_language=source_language,
        properties=properties,
        include_deprecated=include_deprecated,
    )

    return reporter.report(graph, languages, source)
