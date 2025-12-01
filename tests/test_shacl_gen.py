"""Tests for SHACL shape generation."""

import pytest
from pathlib import Path
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef, XSD
from rdflib.namespace import OWL

from rdf_construct.shacl import (
    generate_shapes,
    PropertyConstraint,
    SH,
    ShaclConfig,
    ShapeGenerator,
    StrictnessLevel,
)
from rdf_construct.shacl.converters import (
    CardinalityConverter,
    DomainRangeConverter,
    EnumerationConverter,
    FunctionalPropertyConverter,
)

# Test namespace
EX = Namespace("http://example.org/")
SHAPES = Namespace("http://example.org/-shapes#")


class TestPropertyConstraint:
    """Tests for PropertyConstraint dataclass."""

    def test_basic_constraint(self):
        """Test creating a basic property constraint."""
        constraint = PropertyConstraint(path=EX.hasName)
        assert constraint.path == EX.hasName
        assert constraint.node_class is None
        assert constraint.datatype is None

    def test_constraint_with_class(self):
        """Test constraint with object class."""
        constraint = PropertyConstraint(path=EX.hasPart, node_class=EX.Component)
        assert constraint.node_class == EX.Component

    def test_constraint_with_datatype(self):
        """Test constraint with datatype."""
        constraint = PropertyConstraint(path=EX.hasName, datatype=XSD.string)
        assert constraint.datatype == XSD.string

    def test_constraint_with_cardinality(self):
        """Test constraint with cardinality."""
        constraint = PropertyConstraint(
            path=EX.hasId, min_count=1, max_count=1
        )
        assert constraint.min_count == 1
        assert constraint.max_count == 1

    def test_merge_constraints(self):
        """Test merging two constraints."""
        c1 = PropertyConstraint(path=EX.prop, node_class=EX.Thing)
        c2 = PropertyConstraint(path=EX.prop, min_count=1)

        merged = c1.merge(c2)

        assert merged.node_class == EX.Thing
        assert merged.min_count == 1

    def test_merge_takes_stricter_cardinality(self):
        """Test that merge takes stricter cardinality values."""
        c1 = PropertyConstraint(path=EX.prop, min_count=1, max_count=10)
        c2 = PropertyConstraint(path=EX.prop, min_count=2, max_count=5)

        merged = c1.merge(c2)

        # Should take higher min and lower max
        assert merged.min_count == 2
        assert merged.max_count == 5

    def test_to_rdf(self):
        """Test converting constraint to RDF."""
        constraint = PropertyConstraint(
            path=EX.hasName,
            datatype=XSD.string,
            min_count=1,
            max_count=1,
            name="name",
        )

        graph = Graph()
        prop_node = constraint.to_rdf(graph)

        assert (prop_node, SH.path, EX.hasName) in graph
        assert (prop_node, SH.datatype, XSD.string) in graph
        assert (prop_node, SH.minCount, Literal(1)) in graph
        assert (prop_node, SH.maxCount, Literal(1)) in graph
        assert (prop_node, SH.name, Literal("name")) in graph


class TestDomainRangeConverter:
    """Tests for domain/range to SHACL conversion."""

    @pytest.fixture
    def source_graph(self) -> Graph:
        """Create a test ontology graph."""
        g = Graph()
        g.bind("ex", EX)

        # Define a class
        g.add((EX.Person, RDF.type, OWL.Class))
        g.add((EX.Person, RDFS.label, Literal("Person")))

        # Object property with domain and range
        g.add((EX.hasParent, RDF.type, OWL.ObjectProperty))
        g.add((EX.hasParent, RDFS.domain, EX.Person))
        g.add((EX.hasParent, RDFS.range, EX.Person))
        g.add((EX.hasParent, RDFS.label, Literal("has parent")))

        # Datatype property
        g.add((EX.hasName, RDF.type, OWL.DatatypeProperty))
        g.add((EX.hasName, RDFS.domain, EX.Person))
        g.add((EX.hasName, RDFS.range, XSD.string))

        return g

    def test_object_property_domain_range(self, source_graph):
        """Test converting object property with domain/range."""
        converter = DomainRangeConverter()
        config = ShaclConfig()

        constraints = converter.convert_for_class(EX.Person, source_graph, config)

        # Should find hasParent
        paths = {c.path for c in constraints}
        assert EX.hasParent in paths

        parent_constraint = next(c for c in constraints if c.path == EX.hasParent)
        assert parent_constraint.node_class == EX.Person
        assert parent_constraint.name == "has parent"

    def test_datatype_property(self, source_graph):
        """Test converting datatype property."""
        converter = DomainRangeConverter()
        config = ShaclConfig()

        constraints = converter.convert_for_class(EX.Person, source_graph, config)

        name_constraint = next(c for c in constraints if c.path == EX.hasName)
        assert name_constraint.datatype == XSD.string
        assert name_constraint.node_class is None

    def test_no_labels_when_disabled(self, source_graph):
        """Test that labels are not included when disabled."""
        converter = DomainRangeConverter()
        config = ShaclConfig(include_labels=False)

        constraints = converter.convert_for_class(EX.Person, source_graph, config)

        parent_constraint = next(c for c in constraints if c.path == EX.hasParent)
        assert parent_constraint.name is None


class TestCardinalityConverter:
    """Tests for OWL cardinality to SHACL conversion."""

    @pytest.fixture
    def cardinality_graph(self) -> Graph:
        """Create a graph with cardinality restrictions."""
        g = Graph()
        g.bind("ex", EX)

        # Class with exact cardinality restriction
        g.add((EX.Person, RDF.type, OWL.Class))

        from rdflib import BNode

        # Exact cardinality: Person has exactly 1 ID
        restriction1 = BNode()
        g.add((EX.Person, RDFS.subClassOf, restriction1))
        g.add((restriction1, RDF.type, OWL.Restriction))
        g.add((restriction1, OWL.onProperty, EX.hasId))
        g.add((restriction1, OWL.cardinality, Literal(1)))

        # Min cardinality: Person has at least 1 parent
        restriction2 = BNode()
        g.add((EX.Person, RDFS.subClassOf, restriction2))
        g.add((restriction2, RDF.type, OWL.Restriction))
        g.add((restriction2, OWL.onProperty, EX.hasParent))
        g.add((restriction2, OWL.minCardinality, Literal(1)))

        # Max cardinality: Person has at most 2 parents
        restriction3 = BNode()
        g.add((EX.Person, RDFS.subClassOf, restriction3))
        g.add((restriction3, RDF.type, OWL.Restriction))
        g.add((restriction3, OWL.onProperty, EX.hasParent))
        g.add((restriction3, OWL.maxCardinality, Literal(2)))

        # someValuesFrom: Person has at least one name
        restriction4 = BNode()
        g.add((EX.Person, RDFS.subClassOf, restriction4))
        g.add((restriction4, RDF.type, OWL.Restriction))
        g.add((restriction4, OWL.onProperty, EX.hasName))
        g.add((restriction4, OWL.someValuesFrom, XSD.string))

        return g

    def test_exact_cardinality(self, cardinality_graph):
        """Test converting exact cardinality."""
        converter = CardinalityConverter()
        config = ShaclConfig()

        constraints = converter.convert_for_class(EX.Person, cardinality_graph, config)

        id_constraint = next(c for c in constraints if c.path == EX.hasId)
        assert id_constraint.min_count == 1
        assert id_constraint.max_count == 1

    def test_min_max_cardinality(self, cardinality_graph):
        """Test converting min/max cardinality."""
        converter = CardinalityConverter()
        config = ShaclConfig()

        constraints = converter.convert_for_class(EX.Person, cardinality_graph, config)

        # Find parent constraints
        parent_constraints = [c for c in constraints if c.path == EX.hasParent]
        assert len(parent_constraints) == 2

        # Check we have both min and max
        min_vals = [c.min_count for c in parent_constraints if c.min_count]
        max_vals = [c.max_count for c in parent_constraints if c.max_count]

        assert 1 in min_vals
        assert 2 in max_vals

    def test_some_values_from(self, cardinality_graph):
        """Test converting someValuesFrom."""
        converter = CardinalityConverter()
        config = ShaclConfig()

        constraints = converter.convert_for_class(EX.Person, cardinality_graph, config)

        name_constraint = next(c for c in constraints if c.path == EX.hasName)
        assert name_constraint.min_count == 1
        assert name_constraint.datatype == XSD.string


class TestFunctionalPropertyConverter:
    """Tests for functional property to SHACL conversion."""

    @pytest.fixture
    def functional_graph(self) -> Graph:
        """Create a graph with functional properties."""
        g = Graph()
        g.bind("ex", EX)

        g.add((EX.Person, RDF.type, OWL.Class))

        # Functional property
        g.add((EX.hasSSN, RDF.type, OWL.DatatypeProperty))
        g.add((EX.hasSSN, RDF.type, OWL.FunctionalProperty))
        g.add((EX.hasSSN, RDFS.domain, EX.Person))

        # Non-functional property
        g.add((EX.hasNickname, RDF.type, OWL.DatatypeProperty))
        g.add((EX.hasNickname, RDFS.domain, EX.Person))

        return g

    def test_functional_property(self, functional_graph):
        """Test converting functional property."""
        converter = FunctionalPropertyConverter()
        config = ShaclConfig()

        constraints = converter.convert_for_class(EX.Person, functional_graph, config)

        # Should only have constraint for functional property
        assert len(constraints) == 1
        assert constraints[0].path == EX.hasSSN
        assert constraints[0].max_count == 1


class TestShapeGenerator:
    """Tests for the main shape generator."""

    @pytest.fixture
    def simple_ontology(self) -> Graph:
        """Create a simple test ontology."""
        g = Graph()
        g.bind("ex", EX)

        # Ontology header
        g.add((EX[""], RDF.type, OWL.Ontology))

        # Classes
        g.add((EX.Person, RDF.type, OWL.Class))
        g.add((EX.Person, RDFS.label, Literal("Person")))
        g.add((EX.Person, RDFS.comment, Literal("A human being")))

        g.add((EX.Employee, RDF.type, OWL.Class))
        g.add((EX.Employee, RDFS.subClassOf, EX.Person))
        g.add((EX.Employee, RDFS.label, Literal("Employee")))

        # Properties
        g.add((EX.hasName, RDF.type, OWL.DatatypeProperty))
        g.add((EX.hasName, RDFS.domain, EX.Person))
        g.add((EX.hasName, RDFS.range, XSD.string))
        g.add((EX.hasName, RDF.type, OWL.FunctionalProperty))

        g.add((EX.worksFor, RDF.type, OWL.ObjectProperty))
        g.add((EX.worksFor, RDFS.domain, EX.Employee))
        g.add((EX.worksFor, RDFS.range, EX.Organisation))

        g.add((EX.Organisation, RDF.type, OWL.Class))

        return g

    def test_generates_node_shapes(self, simple_ontology):
        """Test that NodeShapes are generated for classes."""
        generator = ShapeGenerator(simple_ontology)
        shapes = generator.generate()

        # Should have shapes for Person, Employee, Organisation
        shape_targets = set(shapes.objects(predicate=SH.targetClass))
        assert EX.Person in shape_targets
        assert EX.Employee in shape_targets
        assert EX.Organisation in shape_targets

    def test_includes_labels(self, simple_ontology):
        """Test that rdfs:label becomes sh:name."""
        config = ShaclConfig(include_labels=True)
        generator = ShapeGenerator(simple_ontology, config)
        shapes = generator.generate()

        # Find Person shape
        person_shape = None
        for shape in shapes.subjects(SH.targetClass, EX.Person):
            person_shape = shape
            break

        assert person_shape is not None
        name = shapes.value(person_shape, SH.name)
        assert str(name) == "Person"

    def test_includes_descriptions(self, simple_ontology):
        """Test that rdfs:comment becomes sh:description."""
        config = ShaclConfig(include_descriptions=True)
        generator = ShapeGenerator(simple_ontology, config)
        shapes = generator.generate()

        # Find Person shape
        person_shape = None
        for shape in shapes.subjects(SH.targetClass, EX.Person):
            person_shape = shape
            break

        desc = shapes.value(person_shape, SH.description)
        assert "human being" in str(desc)

    def test_minimal_level(self, simple_ontology):
        """Test minimal strictness level."""
        config = ShaclConfig(level=StrictnessLevel.MINIMAL)
        generator = ShapeGenerator(simple_ontology, config)
        shapes = generator.generate()

        # Should have property shapes with sh:class/sh:datatype
        # but no cardinality
        for prop_shape in shapes.objects(predicate=SH.property):
            # Check we have path
            assert shapes.value(prop_shape, SH.path) is not None
            # Minimal level shouldn't have maxCount from functional property
            # (that's standard level)

    def test_standard_level(self, simple_ontology):
        """Test standard strictness level."""
        config = ShaclConfig(level=StrictnessLevel.STANDARD)
        generator = ShapeGenerator(simple_ontology, config)
        shapes = generator.generate()

        # Find Person shape
        person_shape = None
        for shape in shapes.subjects(SH.targetClass, EX.Person):
            person_shape = shape
            break

        # Find hasName property shape - should have maxCount 1 from FunctionalProperty
        found_max_count = False
        for prop_shape in shapes.objects(person_shape, SH.property):
            path = shapes.value(prop_shape, SH.path)
            if path == EX.hasName:
                max_count = shapes.value(prop_shape, SH.maxCount)
                if max_count:
                    assert int(max_count) == 1
                    found_max_count = True

        assert found_max_count, "Should have maxCount 1 for functional property"

    def test_inherits_constraints(self, simple_ontology):
        """Test constraint inheritance from superclasses."""
        config = ShaclConfig(inherit_constraints=True)
        generator = ShapeGenerator(simple_ontology, config)
        shapes = generator.generate()

        # Employee should inherit hasName constraint from Person
        employee_shape = None
        for shape in shapes.subjects(SH.targetClass, EX.Employee):
            employee_shape = shape
            break

        # Check Employee has hasName property shape
        has_name_prop = False
        for prop_shape in shapes.objects(employee_shape, SH.property):
            path = shapes.value(prop_shape, SH.path)
            if path == EX.hasName:
                has_name_prop = True

        assert has_name_prop, "Employee should inherit hasName from Person"

    def test_target_classes_filter(self, simple_ontology):
        """Test filtering to specific target classes."""
        config = ShaclConfig(target_classes=["Person"])
        generator = ShapeGenerator(simple_ontology, config)
        shapes = generator.generate()

        shape_targets = set(shapes.objects(predicate=SH.targetClass))
        assert EX.Person in shape_targets
        assert EX.Employee not in shape_targets

    def test_exclude_classes(self, simple_ontology):
        """Test excluding specific classes."""
        config = ShaclConfig(exclude_classes=["Organisation"])
        generator = ShapeGenerator(simple_ontology, config)
        shapes = generator.generate()

        shape_targets = set(shapes.objects(predicate=SH.targetClass))
        assert EX.Person in shape_targets
        assert EX.Organisation not in shape_targets


class TestGenerateShapes:
    """Tests for the generate_shapes function."""

    def test_from_graph(self):
        """Test generating shapes from a Graph object."""
        g = Graph()
        g.bind("ex", EX)
        g.add((EX.Thing, RDF.type, OWL.Class))
        g.add((EX.hasPart, RDF.type, OWL.ObjectProperty))
        g.add((EX.hasPart, RDFS.domain, EX.Thing))
        g.add((EX.hasPart, RDFS.range, EX.Thing))

        shapes_graph, turtle = generate_shapes(g)

        assert isinstance(shapes_graph, Graph)
        assert len(turtle) > 0
        assert "sh:NodeShape" in turtle

    def test_output_format_jsonld(self):
        """Test generating JSON-LD output."""
        g = Graph()
        g.add((EX.Thing, RDF.type, OWL.Class))

        shapes_graph, output = generate_shapes(g, output_format="json-ld")

        assert "@" in output  # JSON-LD marker


class TestShaclConfig:
    """Tests for ShaclConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ShaclConfig()

        assert config.level == StrictnessLevel.STANDARD
        assert config.closed is False
        assert config.include_labels is True
        assert config.inherit_constraints is True

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "level": "strict",
            "closed": True,
            "target_classes": ["Building", "Floor"],
            "include_labels": False,
        }

        config = ShaclConfig.from_dict(data)

        assert config.level == StrictnessLevel.STRICT
        assert config.closed is True
        assert config.target_classes == ["Building", "Floor"]
        assert config.include_labels is False

    def test_invalid_level_raises(self):
        """Test that invalid strictness level raises ValueError."""
        with pytest.raises(ValueError, match="Invalid strictness level"):
            ShaclConfig.from_dict({"level": "invalid"})

    def test_should_generate_for_with_targets(self):
        """Test should_generate_for with target classes."""
        config = ShaclConfig(target_classes=["Building"])
        g = Graph()

        assert config.should_generate_for(
            URIRef("http://example.org/Building"), g
        )
        assert not config.should_generate_for(
            URIRef("http://example.org/Floor"), g
        )

    def test_should_generate_for_with_excludes(self):
        """Test should_generate_for with excluded classes."""
        config = ShaclConfig(exclude_classes=["Thing"])
        g = Graph()

        assert config.should_generate_for(URIRef("http://example.org/Building"), g)
        assert not config.should_generate_for(
            URIRef("http://example.org/Thing"), g
        )


class TestEnumerationConverter:
    """Tests for enumeration (owl:oneOf) conversion."""

    @pytest.fixture
    def enum_graph(self) -> Graph:
        """Create a graph with enumerated values."""
        g = Graph()
        g.bind("ex", EX)

        from rdflib import BNode

        # Create an enumeration
        g.add((EX.Person, RDF.type, OWL.Class))
        g.add((EX.hasStatus, RDF.type, OWL.DatatypeProperty))
        g.add((EX.hasStatus, RDFS.domain, EX.Person))
        g.add((EX.hasStatus, RDFS.range, EX.Status))

        # Define Status as enumeration
        list_head = BNode()
        g.add((EX.Status, OWL.oneOf, list_head))

        # Build RDF list: (Active, Inactive, Pending)
        g.add((list_head, RDF.first, EX.Active))
        node2 = BNode()
        g.add((list_head, RDF.rest, node2))
        g.add((node2, RDF.first, EX.Inactive))
        node3 = BNode()
        g.add((node2, RDF.rest, node3))
        g.add((node3, RDF.first, EX.Pending))
        g.add((node3, RDF.rest, RDF.nil))

        return g

    def test_enumeration_to_sh_in(self, enum_graph):
        """Test converting enumeration to sh:in."""
        converter = EnumerationConverter()
        config = ShaclConfig()

        constraints = converter.convert_for_class(EX.Person, enum_graph, config)

        assert len(constraints) == 1
        constraint = constraints[0]
        assert constraint.path == EX.hasStatus
        assert EX.Active in constraint.in_values
        assert EX.Inactive in constraint.in_values
        assert EX.Pending in constraint.in_values
