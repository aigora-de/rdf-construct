"""Translation coverage reporting.

Analyses ontologies and reports translation coverage across languages,
identifying missing translations and tracking progress.
"""

from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS


@dataclass
class PropertyCoverage:
    """Coverage for a single property.

    Attributes:
        property: Property URI (shortened).
        total: Total strings in source language.
        translated: Number translated.
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
        total_strings: Total translatable strings.
        translated: Number translated.
        by_property: Coverage broken down by property.
        missing_entities: URIs of entities missing translations.
    """

    language: str
    is_source: bool = False
    total_strings: int = 0
    translated: int = 0
    by_property: dict[str, PropertyCoverage] = field(default_factory=dict)
    missing_entities: list[str] = field(default_factory=list)

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
        total_entities: Total entities in ontology.
        properties: Properties analysed.
        languages: Coverage by language.
    """

    source_file: str
    source_language: str
    total_entities: int = 0
    properties: list[str] = field(default_factory=list)
    languages: dict[str, LanguageCoverage] = field(default_factory=dict)


class CoverageReporter:
    """Analyses and reports translation coverage.

    The reporter examines an ontology and determines what percentage
    of translatable content has been translated into each target language.
    """

    def __init__(
        self,
        source_language: str = "en",
        properties: list[str] | None = None,
    ):
        """Initialise the reporter.

        Args:
            source_language: Base language code.
            properties: Properties to check. Uses defaults if not provided.
        """
        self.source_language = source_language
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
        entities = self._collect_entities(graph)

        # Build report
        report = CoverageReport(
            source_file=str(source_file),
            source_language=self.source_language,
            total_entities=len(entities),
            properties=[self._shorten_property(p) for p in self.properties],
        )

        # Analyse source language first
        source_coverage = self._analyse_language(
            graph, entities, self.source_language, is_source=True
        )
        report.languages[self.source_language] = source_coverage

        # Analyse each target language
        for lang in languages:
            if lang == self.source_language:
                continue

            lang_coverage = self._analyse_language(
                graph,
                entities,
                lang,
                is_source=False,
                source_coverage=source_coverage,
            )
            report.languages[lang] = lang_coverage

        return report

    def _collect_entities(self, graph: Graph) -> list[URIRef]:
        """Collect all entities from the graph.

        Args:
            graph: RDF graph.

        Returns:
            List of entity URIs.
        """
        entities: set[URIRef] = set()

        # Classes
        for cls_type in [OWL.Class, RDFS.Class]:
            for s in graph.subjects(RDF.type, cls_type):
                if isinstance(s, URIRef):
                    entities.add(s)

        # Properties
        property_types = [
            OWL.ObjectProperty,
            OWL.DatatypeProperty,
            OWL.AnnotationProperty,
            RDF.Property,
        ]
        for prop_type in property_types:
            for s in graph.subjects(RDF.type, prop_type):
                if isinstance(s, URIRef):
                    entities.add(s)

        # Named Individuals
        for s in graph.subjects(RDF.type, OWL.NamedIndividual):
            if isinstance(s, URIRef):
                entities.add(s)

        return sorted(entities, key=str)

    def _analyse_language(
        self,
        graph: Graph,
        entities: list[URIRef],
        language: str,
        is_source: bool = False,
        source_coverage: LanguageCoverage | None = None,
    ) -> LanguageCoverage:
        """Analyse coverage for a single language.

        Args:
            graph: RDF graph.
            entities: List of entity URIs.
            language: Language code to analyse.
            is_source: Whether this is the source language.
            source_coverage: Source language coverage (for comparison).

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
            entity_has_any = False
            entity_missing_any = False

            for prop_uri_str in self.properties:
                prop_uri = URIRef(prop_uri_str)
                short_prop = self._shorten_property(prop_uri_str)

                # Count strings in this language
                count = self._count_language_literals(graph, entity, prop_uri, language)

                if is_source:
                    # For source language, all found strings count as "total"
                    coverage.by_property[short_prop].total += count
                    coverage.by_property[short_prop].translated += count
                    coverage.total_strings += count
                    coverage.translated += count
                    if count > 0:
                        entity_has_any = True
                else:
                    # For target languages, compare against source
                    if source_coverage:
                        source_count = self._count_language_literals(
                            graph, entity, prop_uri, self.source_language
                        )
                        coverage.by_property[short_prop].total += source_count
                        coverage.total_strings += source_count

                        if count > 0:
                            coverage.by_property[short_prop].translated += count
                            coverage.translated += count
                            entity_has_any = True

                        if source_count > 0 and count == 0:
                            entity_missing_any = True

            # Track missing entities (have source but no target)
            if entity_missing_any and not is_source:
                missing.append(str(entity))

        coverage.missing_entities = missing
        return coverage

    def _count_language_literals(
        self,
        graph: Graph,
        subject: URIRef,
        predicate: URIRef,
        language: str,
    ) -> int:
        """Count literals with a specific language tag.

        Args:
            graph: RDF graph.
            subject: Subject URI.
            predicate: Predicate URI.
            language: Language code.

        Returns:
            Count of matching literals.
        """
        count = 0

        for obj in graph.objects(subject, predicate):
            if isinstance(obj, Literal):
                if obj.language == language:
                    count += 1
                elif obj.language is None and language == self.source_language:
                    # Treat untagged as source language
                    count += 1

        return count

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
) -> CoverageReport:
    """Generate translation coverage report for an ontology.

    Convenience function for simple reporting.

    Args:
        source: Source ontology file.
        languages: List of language codes to check.
        source_language: Base language code.
        properties: Properties to analyse.

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
    )

    return reporter.report(graph, languages, source)
