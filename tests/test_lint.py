"""Tests for rdf-construct lint module."""

from pathlib import Path
import pytest
from rdflib import Graph, Namespace, RDF, RDFS, Literal
from rdflib.namespace import OWL

# Import the modules to test
# Note: Adjust imports based on actual package structure
from src_rdf_construct_lint_rules import (
    Severity,
    LintIssue,
    get_all_rules,
    list_rules,
    check_orphan_class,
    check_dangling_reference,
    check_circular_subclass,
    check_property_no_type,
    check_empty_ontology,
    check_missing_label,
    check_missing_comment,
    check_redundant_subclass,
    check_property_no_domain,
    check_property_no_range,
    check_inconsistent_naming,
)
from src_rdf_construct_lint_engine import LintConfig, LintEngine, LintResult

# Test namespace
EX = Namespace("http://example.org/")


class TestRuleRegistry:
    """Tests for the rule registry."""

    def test_rules_registered(self):
        """Check that all expected rules are registered."""
        rules = list_rules()
        expected = [
            "orphan-class",
            "dangling-reference",
            "circular-subclass",
            "property-no-type",
            "empty-ontology",
            "missing-label",
            "missing-comment",
            "redundant-subclass",
            "property-no-domain",
            "property-no-range",
            "inconsistent-naming",
        ]
        for rule_id in expected:
            assert rule_id in rules, f"Rule '{rule_id}' not registered"

    def test_get_all_rules(self):
        """Check that get_all_rules returns specs."""
        rules = get_all_rules()
        assert len(rules) >= 10  # Minimum 10 rules as per spec
        for rule_id, spec in rules.items():
            assert spec.rule_id == rule_id
            assert spec.description
            assert spec.category in ("structural", "documentation", "best-practice")


class TestOrphanClassRule:
    """Tests for orphan-class rule."""

    def test_detects_orphan_class(self):
        """Class without rdfs:subClassOf should be flagged."""
        g = Graph()
        g.add((EX.Building, RDF.type, OWL.Class))
        g.add((EX.Building, RDFS.label, Literal("Building")))

        issues = check_orphan_class(g)
        assert len(issues) == 1
        assert issues[0].rule_id == "orphan-class"
        assert issues[0].entity == EX.Building

    def test_ignores_class_with_superclass(self):
        """Class with rdfs:subClassOf should not be flagged."""
        g = Graph()
        g.add((EX.Building, RDF.type, OWL.Class))
        g.add((EX.Building, RDFS.subClassOf, OWL.Thing))

        issues = check_orphan_class(g)
        assert len(issues) == 0

    def test_ignores_owl_thing(self):
        """owl:Thing should not be flagged as orphan."""
        g = Graph()
        g.add((OWL.Thing, RDF.type, OWL.Class))

        issues = check_orphan_class(g)
        assert len(issues) == 0


class TestDanglingReferenceRule:
    """Tests for dangling-reference rule."""

    def test_detects_dangling_reference(self):
        """Reference to undefined entity should be flagged."""
        g = Graph()
        g.add((EX.Building, RDF.type, OWL.Class))
        g.add((EX.Building, RDFS.subClassOf, EX.Structure))  # Structure not defined

        issues = check_dangling_reference(g)
        # Should find EX.Structure as dangling
        dangling = [i for i in issues if i.entity == EX.Structure]
        assert len(dangling) == 1

    def test_ignores_defined_entity(self):
        """Reference to defined entity should not be flagged."""
        g = Graph()
        g.add((EX.Structure, RDF.type, OWL.Class))
        g.add((EX.Building, RDF.type, OWL.Class))
        g.add((EX.Building, RDFS.subClassOf, EX.Structure))

        issues = check_dangling_reference(g)
        dangling = [i for i in issues if i.entity == EX.Structure]
        assert len(dangling) == 0


class TestCircularSubclassRule:
    """Tests for circular-subclass rule."""

    def test_detects_direct_circular(self):
        """Class that is subclass of itself should be flagged."""
        g = Graph()
        g.add((EX.Thing, RDF.type, OWL.Class))
        g.add((EX.Thing, RDFS.subClassOf, EX.Thing))

        issues = check_circular_subclass(g)
        assert len(issues) == 1
        assert issues[0].entity == EX.Thing

    def test_detects_transitive_circular(self):
        """Circular inheritance chain should be flagged."""
        g = Graph()
        g.add((EX.A, RDF.type, OWL.Class))
        g.add((EX.B, RDF.type, OWL.Class))
        g.add((EX.C, RDF.type, OWL.Class))
        g.add((EX.A, RDFS.subClassOf, EX.B))
        g.add((EX.B, RDFS.subClassOf, EX.C))
        g.add((EX.C, RDFS.subClassOf, EX.A))

        issues = check_circular_subclass(g)
        assert len(issues) >= 1  # At least one class should be flagged


class TestPropertyNoTypeRule:
    """Tests for property-no-type rule."""

    def test_detects_property_without_type(self):
        """Property with domain but no type should be flagged."""
        g = Graph()
        g.add((EX.hasName, RDFS.domain, EX.Person))

        issues = check_property_no_type(g)
        assert len(issues) == 1
        assert issues[0].entity == EX.hasName

    def test_ignores_typed_property(self):
        """Property with explicit type should not be flagged."""
        g = Graph()
        g.add((EX.hasName, RDF.type, OWL.DatatypeProperty))
        g.add((EX.hasName, RDFS.domain, EX.Person))

        issues = check_property_no_type(g)
        assert len(issues) == 0


class TestEmptyOntologyRule:
    """Tests for empty-ontology rule."""

    def test_detects_empty_ontology(self):
        """Ontology without metadata should be flagged."""
        g = Graph()
        g.add((EX.myOnt, RDF.type, OWL.Ontology))

        issues = check_empty_ontology(g)
        assert len(issues) == 1

    def test_ignores_ontology_with_label(self):
        """Ontology with label should not be flagged."""
        g = Graph()
        g.add((EX.myOnt, RDF.type, OWL.Ontology))
        g.add((EX.myOnt, RDFS.label, Literal("My Ontology")))

        issues = check_empty_ontology(g)
        assert len(issues) == 0


class TestMissingLabelRule:
    """Tests for missing-label rule."""

    def test_detects_class_without_label(self):
        """Class without label should be flagged."""
        g = Graph()
        g.add((EX.Building, RDF.type, OWL.Class))

        issues = check_missing_label(g)
        class_issues = [i for i in issues if i.entity == EX.Building]
        assert len(class_issues) == 1

    def test_ignores_class_with_label(self):
        """Class with label should not be flagged."""
        g = Graph()
        g.add((EX.Building, RDF.type, OWL.Class))
        g.add((EX.Building, RDFS.label, Literal("Building")))

        issues = check_missing_label(g)
        class_issues = [i for i in issues if i.entity == EX.Building]
        assert len(class_issues) == 0


class TestMissingCommentRule:
    """Tests for missing-comment rule."""

    def test_detects_class_without_comment(self):
        """Class without comment should be flagged."""
        g = Graph()
        g.add((EX.Building, RDF.type, OWL.Class))

        issues = check_missing_comment(g)
        class_issues = [i for i in issues if i.entity == EX.Building]
        assert len(class_issues) == 1


class TestRedundantSubclassRule:
    """Tests for redundant-subclass rule."""

    def test_detects_redundant_inheritance(self):
        """A -> B -> C with direct A -> C should flag redundancy."""
        g = Graph()
        g.add((EX.A, RDF.type, OWL.Class))
        g.add((EX.B, RDF.type, OWL.Class))
        g.add((EX.C, RDF.type, OWL.Class))
        g.add((EX.B, RDFS.subClassOf, EX.A))
        g.add((EX.C, RDFS.subClassOf, EX.B))
        g.add((EX.C, RDFS.subClassOf, EX.A))  # Redundant!

        issues = check_redundant_subclass(g)
        assert len(issues) >= 1


class TestPropertyNoDomainRule:
    """Tests for property-no-domain rule."""

    def test_detects_property_without_domain(self):
        """Object property without domain should be flagged."""
        g = Graph()
        g.add((EX.hasPart, RDF.type, OWL.ObjectProperty))
        g.add((EX.hasPart, RDFS.range, EX.Part))

        issues = check_property_no_domain(g)
        assert len(issues) == 1
        assert issues[0].entity == EX.hasPart


class TestPropertyNoRangeRule:
    """Tests for property-no-range rule."""

    def test_detects_property_without_range(self):
        """Object property without range should be flagged."""
        g = Graph()
        g.add((EX.hasPart, RDF.type, OWL.ObjectProperty))
        g.add((EX.hasPart, RDFS.domain, EX.Whole))

        issues = check_property_no_range(g)
        assert len(issues) == 1


class TestInconsistentNamingRule:
    """Tests for inconsistent-naming rule."""

    def test_detects_lowercase_class(self):
        """Class starting with lowercase should be flagged."""
        g = Graph()
        g.add((EX.building, RDF.type, OWL.Class))

        issues = check_inconsistent_naming(g)
        assert len(issues) == 1
        assert "lowercase" not in issues[0].message.lower() or "uppercase" in issues[0].message.lower()

    def test_detects_uppercase_property(self):
        """Property starting with uppercase should be flagged."""
        g = Graph()
        g.add((EX.HasPart, RDF.type, OWL.ObjectProperty))

        issues = check_inconsistent_naming(g)
        assert len(issues) == 1


class TestLintConfig:
    """Tests for LintConfig."""

    def test_default_config(self):
        """Default config should have standard level."""
        config = LintConfig()
        assert config.level == "standard"
        assert len(config.enabled_rules) == 0
        assert len(config.disabled_rules) == 0

    def test_effective_rules_with_disabled(self):
        """Disabled rules should be excluded."""
        config = LintConfig(disabled_rules={"orphan-class"})
        rules = config.get_effective_rules()
        rule_ids = [r.rule_id for r in rules]
        assert "orphan-class" not in rule_ids

    def test_strict_level_severity(self):
        """Strict level should upgrade warnings to errors."""
        config = LintConfig(level="strict")
        # missing-label has default severity WARNING
        severity = config.get_effective_severity("missing-label")
        assert severity == Severity.ERROR

    def test_relaxed_level_severity(self):
        """Relaxed level should downgrade warnings to info."""
        config = LintConfig(level="relaxed")
        severity = config.get_effective_severity("missing-label")
        assert severity == Severity.INFO


class TestLintEngine:
    """Tests for LintEngine."""

    def test_lint_graph(self):
        """Engine should lint an in-memory graph."""
        g = Graph()
        g.add((EX.Building, RDF.type, OWL.Class))  # Orphan, no label, no comment

        engine = LintEngine()
        result = engine.lint_graph(g)

        assert result.total_issues > 0
        assert result.error_count > 0  # orphan-class is an error

    def test_lint_with_config(self):
        """Engine should respect config."""
        g = Graph()
        g.add((EX.Building, RDF.type, OWL.Class))

        # Disable all structural rules
        config = LintConfig(disabled_rules={"orphan-class"})
        engine = LintEngine(config)
        result = engine.lint_graph(g)

        orphan_issues = [i for i in result.issues if i.rule_id == "orphan-class"]
        assert len(orphan_issues) == 0


class TestLintResult:
    """Tests for LintResult."""

    def test_counts(self):
        """Result should correctly count by severity."""
        result = LintResult(file_path=Path("test.ttl"))
        result.add_issue(LintIssue("r1", Severity.ERROR, None, "Error"))
        result.add_issue(LintIssue("r2", Severity.WARNING, None, "Warning"))
        result.add_issue(LintIssue("r3", Severity.INFO, None, "Info"))

        assert result.error_count == 1
        assert result.warning_count == 1
        assert result.info_count == 1
        assert result.total_issues == 3
        assert result.has_errors
        assert result.has_warnings


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
