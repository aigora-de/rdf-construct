"""PlantUML parser for class diagram syntax.

This module provides regex-based parsing of PlantUML class diagrams,
extracting classes, relationships, packages, and notes into an
intermediate model representation.

The parser uses a multi-pass approach:
1. Extract packages and set up namespaces
2. Extract classes with attributes
3. Extract relationships
4. Attach notes to entities
"""

import re
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rdflib import RDF, RDFS, Graph, URIRef
from rdflib.namespace import OWL

from rdf_construct.core.vocab import (
    ALL_PROPERTY_TYPES,
    ANNOTATION_PROPERTY_TYPES,
    DATATYPE_PROPERTY_TYPES,
    OBJECT_PROPERTY_TYPES,
)
from rdf_construct.puml2rdf.model import (
    PumlAttribute,
    PumlClass,
    PumlModel,
    PumlNote,
    PumlPackage,
    PumlRelationship,
    RelationshipType,
)
from rdf_construct.uml.odm_renderer import ODM_INDIVIDUAL_STEREOTYPE, ODM_PROPERTY_STEREOTYPES

# A URI starts with a scheme, so `urn:` counts as well as `http:` (#150).
URI_SCHEME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")

# Turtle's PN_PREFIX: what may stand before the colon of a prefixed name.
_PN_CHARS_BASE = "A-Za-zÀ-ÖØ-öø-˿Ͱ-ͽͿ-῿‌-‍" "⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�\U00010000-\U000effff"
_PN_CHARS = _PN_CHARS_BASE + "_0-9·̀-ͯ‿-⁀\\-"
PN_PREFIX_PATTERN = re.compile(f"[{_PN_CHARS_BASE}](?:[{_PN_CHARS}.]*[{_PN_CHARS}])?")

# The prefixes the output graph binds before any package (bind_namespaces="core"). A package
# may claim one only for that prefix's own namespace.
CORE_PREFIXES: dict[str, str] = {
    prefix: str(namespace) for prefix, namespace in Graph(bind_namespaces="core").namespaces()
}

# A diagram is the text between `@startuml` and `@enduml`, each starting a line (#151).
STARTUML_PATTERN = re.compile(r"^[ \t]*@startuml\b", re.MULTILINE)
ENDUML_PATTERN = re.compile(r"^[ \t]*@enduml\b", re.MULTILINE)

# Lines no pass reads that are known to carry nothing for the ontology: comments, layout and
# presentation (#151). A line no pass reads and nothing here matches is reported.
IGNORABLE_LINE_PATTERNS = [
    re.compile(r"^\s*'"),  # ' comment
    re.compile(r"^\s*\}\s*$"),  # a package's or group's closing brace
    re.compile(r"^\s*(?:hide|show)\b"),
    re.compile(r"^\s*(?:left\s+to\s+right|top\s+to\s+bottom)\s+direction\s*$"),
    re.compile(r"^\s*!(?:include\w*|theme)\b"),
    re.compile(r"^\s*(?:(?:left|right|center)\s+)?(?:header|footer)\b"),
    re.compile(r"^\s*caption\b"),
    re.compile(r"^\s*together\s*\{\s*$"),
]

# Ignorable blocks: (opening line, closing line). Every line from one to the other is skipped,
# so a block-form `skinparam` is not read as `skinparam class {`, nor a legend's text as a line.
IGNORABLE_BLOCK_PATTERNS = [
    (re.compile(r"^\s*/'"), re.compile(r"'/")),
    (re.compile(r"^\s*skinparam\s+\w+\s*\{\s*$"), re.compile(r"^\s*\}\s*$")),
    (
        re.compile(r"^\s*legend(?:\s+(?:top|bottom|left|right|center))*\s*$"),
        re.compile(r"^\s*end\s*legend\b"),
    ),
    (re.compile(r"^\s*title\s*$"), re.compile(r"^\s*end\s*title\b")),
    (
        re.compile(r"^\s*(?:(?:left|right|center)\s+)?(?:header|footer)\s*$"),
        re.compile(r"^\s*end\s*(?:header|footer)\b"),
    ),
]

# Declarations of kinds the converter does not model (#151): named, because each is a type or
# a relationship the author declared and the output does not contain.
UNMODELLED_DECLARATION_PATTERN = re.compile(
    r'^\s*(interface|enum|annotation|entity|struct)\s+("[^"]+"|[\w.]+)'
)
# `class Car extends Base`: the class pass reads the declaration, not the clause (#398).
CLASS_CLAUSE_PATTERN = re.compile(
    r'^\s*(?:abstract\s+)?class\s+(?:"[^"]+"\s+as\s+)?("[^"]+"|[\w.]+)'
    r".*?\s(extends|implements)\s+([\w.]+(?:\s*,\s*[\w.]+)*)"
)
BARE_ABSTRACT_PATTERN = re.compile(r'^\s*abstract\s+(?!class\b)("[^"]+"|[\w.]+)')
REALISATION_PATTERN = re.compile(r"\.\.\|>|<\|\.\.")
DEPENDENCY_PATTERN = re.compile(r"\.\.>|<\.\.")

# A class box `uml` draws for a property or an individual is not converted (#395). The default
# rendering marks it with a spot, `(O, #FFFFFF)`, inside or outside `<< >>`; ODM with the first
# stereotype name, `<<objectProperty, functionalProperty>>`; either may be a prefixed type name.
BOX_SPOT_PATTERN = re.compile(r"\(\s*([A-Za-z])\s*,[^)]*\)")
BOX_STEREOTYPE_PATTERN = re.compile(r"<<\s*(\w+(?::\w+)?)")
SPOT_KINDS = {
    "O": "object property",
    "D": "datatype property",
    "A": "annotation property",
    "P": "property",
    "I": "individual",
}
STEREOTYPE_NAMESPACES = {"owl": OWL, "rdf": RDF, "rdfs": RDFS}


def _property_kind(type_iri: URIRef) -> str:
    """Name the kind of property *type_iri* declares, by :mod:`rdf_construct.core.vocab`."""
    if type_iri in OBJECT_PROPERTY_TYPES:
        return "object property"
    if type_iri in DATATYPE_PROPERTY_TYPES:
        return "datatype property"
    if type_iri in ANNOTATION_PROPERTY_TYPES:
        return "annotation property"
    return "property"


# Every name ODM draws a property with is a property; the IRI it stands for gives the kind
ODM_BOX_KINDS = {
    name: _property_kind(URIRef(iri)) for iri, name in ODM_PROPERTY_STEREOTYPES.items()
}
ODM_BOX_KINDS[ODM_INDIVIDUAL_STEREOTYPE] = "individual"


def _box_kind(stereotype: str) -> str | None:
    """Name what a class box's stereotype says it is, if that is not a class (#395).

    Args:
        stereotype: The declaration's text after the box's name.

    Returns:
        ``object property``, ``datatype property``, ``annotation property``, ``property`` or
        ``individual``; or None for a class, or a stereotype that does not say.
    """
    spot = BOX_SPOT_PATTERN.search(stereotype)
    if spot:
        return SPOT_KINDS.get(spot.group(1).upper())
    first = BOX_STEREOTYPE_PATTERN.search(stereotype)
    if first is None:
        return None
    name = first.group(1)
    if name in ODM_BOX_KINDS:
        return ODM_BOX_KINDS[name]
    prefix, _, local = name.partition(":")
    if prefix == ODM_INDIVIDUAL_STEREOTYPE:
        return "individual"
    namespace = STEREOTYPE_NAMESPACES.get(prefix)
    if namespace is None or not local:
        return None
    iri = namespace[local]
    if iri in ALL_PROPERTY_TYPES:
        return _property_kind(iri)
    if iri == OWL.NamedIndividual:
        return "individual"
    return None


def parse_dotted_name(dotted: str) -> tuple[Optional[str], str]:
    """Split a dotted name into package and local name.

    Examples:
        "building.Building" -> ("building", "Building")
        "ies.ArtificialFeature" -> ("ies", "ArtificialFeature")
        "Building" -> (None, "Building")
    """
    if "." in dotted:
        parts = dotted.rsplit(".", 1)  # Split on last dot
        return (parts[0], parts[1])
    return (None, dotted)


@dataclass
class ParseError:
    """An error encountered during parsing.

    Attributes:
        line_number: Line where the error occurred, or None for one about the whole file
        message: Description of the error
        line_content: The actual line content
    """

    line_number: int | None
    message: str
    line_content: str


@dataclass
class ParseWarning:
    """Something the parser read but did not convert, or chose on the author's behalf.

    Attributes:
        line_number: Line it was found on, or None for one about the whole diagram
        message: Description of it
        line_content: The actual line content
        code: What kind it is: ``not-understood``, ``unmodelled``, ``note-unknown-class``,
            ``empty-diagram`` or ``derived-prefix``
        kind: For an ``unmodelled`` box that is not a class, what it was drawn as
            (``object property``, ``datatype property``, ``annotation property``,
            ``property`` or ``individual``), or ``relationship`` for a line naming one (#395);
            otherwise empty
    """

    line_number: int | None
    message: str
    line_content: str = ""
    code: str = "not-understood"
    kind: str = ""

    def __str__(self) -> str:
        if self.line_number is None:
            return self.message
        return f"Line {self.line_number}: {self.message}"


@dataclass
class ParseResult:
    """Result of parsing a PlantUML file.

    Attributes:
        model: The parsed model (may be partial if errors occurred)
        errors: List of parse errors encountered
        warnings: Content the parser did not convert; ``--strict`` makes these fatal
        notes: Choices made on the author's behalf, such as a derived prefix; never fatal
    """

    model: PumlModel
    errors: list[ParseError]
    warnings: list[ParseWarning]
    notes: list[ParseWarning] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Return True if parsing completed without errors."""
        return len(self.errors) == 0


class PlantUMLParser:
    """Parser for PlantUML class diagram syntax.

    Parses PlantUML text and produces a PumlModel containing all
    extracted entities ready for RDF conversion.

    Example:
        parser = PlantUMLParser()
        result = parser.parse('''
            @startuml
            class Building {
                floorArea : decimal
            }
            @enduml
        ''')
        if result.success:
            model = result.model
    """

    # ==========================================================================
    # Regex patterns for PlantUML syntax elements
    # ==========================================================================

    # Package: package "Name" as ns { ... } or package Name { ... }
    PACKAGE_PATTERN = re.compile(
        r'package\s+(?:"([^"]+)"|(\S+))'  # Package name (quoted or unquoted)
        r"(?:\s+as\s+(\S+))?"  # Optional 'as namespace'
        r"(?:\s*<<(\w+)>>)?"  # Optional stereotype
        r"\s*\{",  # Opening brace
        re.MULTILINE,
    )

    # Class declaration: class Name <<stereotype>> { ... } or class "Name" { ... }
    CLASS_PATTERN = re.compile(
        r"(?:^|\n)\s*"
        r"(abstract\s+)?"  # Group 1: Optional abstract keyword
        r"class\s+"
        r"(?:"
        r'"([^"]+)"\s+as\s+([\w.]+)'  # Groups 2,3: "Display Name" as alias
        r"|"
        r'"([^"]+)"'  # Group 4: Just "Quoted Name"
        r"|"
        r"([\w.]+)"  # Group 5: Unquoted name (may include dots)
        r")"
        r"(?:\s*<<(\w+)>>)?"  # Group 6: Optional stereotype
        r"(?:\s*#[^\s{]*)?"  # Optional styling - ignore
        r"[ \t]*(?:\{([^}]*)\})?",  # Group 7: Optional body
        re.MULTILINE | re.DOTALL,
    )

    # Attribute: visibility name : type
    ATTRIBUTE_PATTERN = re.compile(
        r"^\s*"
        r"([+\-#~])?\s*"  # Optional visibility
        r"(\{static\})?\s*"  # Optional static marker
        r"(\w+)"  # Attribute name
        r"(?:\s*:\s*(\w+))?"  # Optional : type
        r"\s*$",
        re.MULTILINE,
    )

    # Relationships - various arrow styles
    # A --|> B (inheritance)
    # A --> B : label (association)
    # A "1" --> "*" B : label (with cardinalities)
    # A o-- B (aggregation)
    # A *-- B (composition)
    RELATIONSHIP_PATTERN = re.compile(
        r"(?:^|\n)\s*"
        r'(?:"([^"]+)"|(\w+))'  # Source class (quoted or not)
        r"\s*"
        r'(?:"([^"]*)")?\s*'  # Optional source cardinality
        r"([o*])?"  # Optional aggregation/composition marker at source
        r"(--?|\.\.)"  # Line style (-- or ..)
        r"([|>o*])?"  # Arrow head or aggregation marker at target
        r"\s*"
        r'(?:"([^"]*)")?\s*'  # Optional target cardinality
        r'(?:"([^"]+)"|(\w+))'  # Target class (quoted or not)
        r"(?:\s*:\s*([^\n]+))?",  # Optional label
        re.MULTILINE,
    )

    # Note attached to element: note right of Class : text
    NOTE_ATTACHED_PATTERN = re.compile(
        r"note\s+(right|left|top|bottom)\s+of\s+(\w+)\s*"
        r"(?::\s*([^\n]+))?"  # Single line note
        r"|"
        r"note\s+(right|left|top|bottom)\s+of\s+(\w+)\s*\n"
        r"(.*?)"  # Multi-line content
        r"\s*end\s*note",
        re.MULTILINE | re.DOTALL,
    )

    # Standalone note block: note "text" as N1
    NOTE_STANDALONE_PATTERN = re.compile(r'note\s+"([^"]+)"\s+as\s+(\w+)', re.MULTILINE)

    # Diagram title
    TITLE_PATTERN = re.compile(r"title\s+(.+?)(?:\n|$)", re.MULTILINE)

    # Skinparam settings
    SKINPARAM_PATTERN = re.compile(r"skinparam\s+(\w+)\s+(\S+)", re.MULTILINE)

    def __init__(self) -> None:
        """Initialise the parser."""
        self._errors: list[ParseError] = []
        self._warnings: list[ParseWarning] = []
        self._notes: list[ParseWarning] = []
        self._consumed: list[tuple[int, int]] = []
        self._dropped: dict[str, str] = {}
        self._current_package: Optional[str] = None
        self._package_stack: list[str] = []

    def parse(self, content: str) -> ParseResult:
        """Parse PlantUML content into a model.

        Args:
            content: PlantUML diagram text

        Returns:
            ParseResult containing the model and any errors/warnings
        """
        self._errors = []
        self._warnings = []
        self._notes = []
        self._consumed = []
        self._dropped = {}

        model = PumlModel()

        # A byte-order mark is not part of the diagram (#397)
        content = content.removeprefix("\ufeff")

        # Without both markers this is not a diagram, or not all of one: refuse it whole (#151)
        span = self._check_markers(content)
        if span is None:
            return ParseResult(model=model, errors=self._errors, warnings=[])

        source = content

        # Only the diagram is read: text outside @startuml … @enduml is blanked, and reported
        # by _report_unread_lines (#400)
        content = self._blank_outside(content, span)

        # Prefixes are checked before the markers are blanked, so a refusal names the file's line
        self._check_prefixes(content)

        # Blank out @startuml / @enduml, so offsets in what the passes read are the file's own
        content = self._strip_diagram_markers(content)

        # Pass 1: Extract packages and namespaces
        model.packages = self._parse_packages(content)

        # Pass 2: Extract classes with attributes
        model.classes = self._parse_classes(content)

        # Pass 3: Extract relationships
        model.relationships = self._parse_relationships(content)

        # Pass 4: Extract and attach notes
        notes = self._parse_notes(content)
        self._attach_notes(model, notes)
        model.notes = [n for n in notes if n.attached_to is None]

        # Extract title
        model.title = self._parse_title(content)

        # Extract skinparams
        model.skin_params = self._parse_skinparams(content)

        # Report every line no pass read, by the file's line number (#151)
        self._report_unread_lines(source, content, span)

        if not model.classes and not model.relationships:
            self._warnings.append(
                ParseWarning(
                    line_number=None,
                    message="nothing converted: the diagram has no classes or relationships",
                    code="empty-diagram",
                )
            )

        return ParseResult(
            model=model, errors=self._errors, warnings=self._warnings, notes=self._notes
        )

    def parse_file(self, path: Path) -> ParseResult:
        """Parse a PlantUML file.

        Args:
            path: Path to the .puml file

        Returns:
            ParseResult containing the model and any errors/warnings
        """
        content = path.read_text(encoding="utf-8")
        return self.parse(content)

    def _check_markers(self, source: str) -> tuple[int, int] | None:
        """Refuse a file that is not a whole PlantUML diagram (#151).

        Without ``@startuml`` the file does not look like a diagram at all; without
        ``@enduml`` after it, nothing shows the diagram was not cut short.

        Args:
            source: The file's text.

        Returns:
            The diagram's span, from the start of the first ``@startuml`` line to the end of
            the ``@enduml`` line that closes it; or None, with a :class:`ParseError` recorded.
        """
        start = STARTUML_PATTERN.search(source)
        if start is None:
            self._errors.append(
                ParseError(
                    line_number=None,
                    message="no @startuml found — this does not look like a PlantUML diagram. "
                    "A fragment must be wrapped in @startuml … @enduml.",
                    line_content="",
                )
            )
            return None
        end = ENDUML_PATTERN.search(source, start.end())
        if end is None:
            self._errors.append(
                ParseError(
                    line_number=None,
                    message="no @enduml found — the diagram may have been cut short. "
                    "A diagram must end with @enduml.",
                    line_content="",
                )
            )
            return None
        line_end = source.find("\n", end.end())
        return start.start(), len(source) if line_end == -1 else line_end

    @staticmethod
    def _blank_outside(content: str, span: tuple[int, int]) -> str:
        """Blank everything outside *span*, keeping every newline, so offsets do not move."""

        def blank(text: str) -> str:
            return re.sub(r"[^\n]", " ", text)

        start, end = span
        return blank(content[:start]) + content[start:end] + blank(content[end:])

    def _strip_diagram_markers(self, content: str) -> str:
        """Blank out @startuml and @enduml markers, keeping every newline.

        The markers are replaced by spaces rather than removed, so an offset into the result
        is an offset into the file, and its line numbers are the file's own.
        """

        def blank(match: re.Match[str]) -> str:
            return re.sub(r"[^\n]", " ", match.group(0))

        # Blank @startuml (with optional name)
        content = re.sub(r"@startuml\s*(?:\([^)]*\))?\s*\n?", blank, content)
        # Blank @enduml
        content = re.sub(r"@enduml\s*", blank, content)
        return content

    def _consume(self, match: re.Match[str]) -> None:
        """Record that a pass read *match*'s text into the model."""
        self._consumed.append(match.span())

    def _report_unread_lines(self, source: str, content: str, span: tuple[int, int]) -> None:
        """Warn about every line no pass read, unless it is known to be ignorable (#151).

        A line counts as read when a match a pass kept touches it; that is generous to a
        line a pass read only part of. Declarations of kinds the converter does not model
        are named; any other line is reported as not understood.

        Args:
            source: The diagram text as given, for the markers and the reported lines.
            content: The text the passes read, with the markers blanked; same offsets.
            span: The diagram's span in both; a line outside it is reported as such (#400).
        """
        # Lines are numbered by "\n" only, as offsets are mapped below (#401)
        lines = source.split("\n")
        line_starts = [0]
        line_starts.extend(i + 1 for i, char in enumerate(content) if char == "\n")
        first_line = bisect_right(line_starts, span[0])
        last_line = bisect_right(line_starts, span[1] - 1)

        for number, text in enumerate(lines, 1):
            if text.strip() and not first_line <= number <= last_line:
                self._warnings.append(
                    ParseWarning(
                        number,
                        f"outside @startuml … @enduml, so not converted: {text.strip()}",
                        line_content=text.strip(),
                        code="outside-diagram",
                    )
                )

        read: set[int] = set()
        for start, end in self._consumed:
            while start < end and content[start].isspace():
                start += 1
            while end > start and content[end - 1].isspace():
                end -= 1
            if start < end:
                first = bisect_right(line_starts, start)
                read.update(range(first, bisect_right(line_starts, end - 1) + 1))

        block_end: re.Pattern[str] | None = None
        body_depth = 0
        opened_on = 0
        for number in range(first_line, last_line + 1):
            text = lines[number - 1]
            if block_end is not None:
                if block_end.search(text):
                    block_end = None
                continue
            if body_depth:
                body_depth += text.count("{") - text.count("}")
                continue
            if not text.strip() or STARTUML_PATTERN.match(text) or ENDUML_PATTERN.match(text):
                continue
            opened = next(
                (
                    (match, closer)
                    for opener, closer in IGNORABLE_BLOCK_PATTERNS
                    if (match := opener.match(text))
                ),
                None,
            )
            if opened is not None:
                match, closer = opened
                # A block may close on the line it opens, as /' … '/ can
                if not closer.search(text[match.end() :]):
                    block_end, opened_on = closer, number
                continue
            clause = CLASS_CLAUSE_PATTERN.match(text)
            if clause:
                self._warnings.append(
                    ParseWarning(
                        number,
                        self._clause_message(*clause.groups()),
                        line_content=text.strip(),
                        code="unmodelled",
                    )
                )
                continue
            if number in read:
                continue
            message = self._unmodelled(text)
            if message is not None:
                self._warnings.append(
                    ParseWarning(number, message, line_content=text.strip(), code="unmodelled")
                )
                body_depth = max(text.count("{") - text.count("}"), 0)
                opened_on = number
                continue
            if any(pattern.match(text) for pattern in IGNORABLE_LINE_PATTERNS):
                continue
            self._warnings.append(
                ParseWarning(
                    number,
                    f"not understood: {text.strip()}",
                    line_content=text.strip(),
                    code="not-understood",
                )
            )

        # A block that never closes would otherwise hide the rest of the diagram (#399)
        if block_end is not None or body_depth > 0:
            opener = lines[opened_on - 1].strip()
            self._warnings.append(
                ParseWarning(
                    opened_on,
                    f"this block is never closed, so the lines after it, up to @enduml, were not "
                    f"checked: {opener}",
                    line_content=opener,
                    code="unclosed-block",
                )
            )

    @staticmethod
    def _clause_message(name: str, keyword: str, targets: str) -> str:
        """Name an ``extends`` or ``implements`` clause the class pass does not read (#398)."""
        name = name.strip('"')
        message = (
            f"{keyword} {targets} on class {name} is not converted, so it is not in the output"
        )
        if keyword == "extends":
            first = targets.split(",")[0].strip()
            message += f'; write "{name} --|> {first}"'
        return message

    @staticmethod
    def _unmodelled(text: str) -> str | None:
        """Name the declaration on *text* if it is of a kind the converter does not model."""
        declaration = UNMODELLED_DECLARATION_PATTERN.match(text)
        if declaration:
            kind, name = declaration.group(1), declaration.group(2).strip('"')
            return (
                f"{kind} {name} is not converted: only classes are, "
                f"so {name} is not in the output"
            )
        abstract = BARE_ABSTRACT_PATTERN.match(text)
        if abstract:
            name = abstract.group(1).strip('"')
            return (
                f"abstract {name} is not converted, so it is not in the output; "
                f'write "abstract class {name}" to convert it'
            )
        if REALISATION_PATTERN.search(text):
            return f"realisation is not converted, so it is not in the output: {text.strip()}"
        if DEPENDENCY_PATTERN.search(text):
            return f"dependency is not converted, so it is not in the output: {text.strip()}"
        return None

    def _parse_packages(self, content: str) -> list[PumlPackage]:
        """Extract package definitions from content."""
        packages = []

        for match in self.PACKAGE_PATTERN.finditer(content):
            self._consume(match)
            name = match.group(1) or match.group(2)  # Quoted or unquoted
            stereotype = match.group(4)

            package_name, namespace_uri = self._package_identity(name, match.group(3))

            packages.append(
                PumlPackage(
                    name=package_name,
                    namespace_uri=namespace_uri,
                    stereotype=stereotype,
                )
            )

        return packages

    @staticmethod
    def _looks_like_uri(value: str) -> bool:
        """Return True when *value* starts with a URI scheme, such as ``http:`` or ``urn:``."""
        return URI_SCHEME_PATTERN.match(value) is not None

    @classmethod
    def _package_identity(cls, name: str, alias: str | None) -> tuple[str, str | None]:
        """Interpret a package declaration as (package name, namespace URI).

        The guide leads with ``package "http://example.org/x#" as pfx``: the
        quoted string is the namespace URI and the alias is the prefix
        (#150). Read the other way round, the URI becomes the package name,
        the alias is discarded, and the converter binds the whole URI as a
        Turtle prefix. A URI with no alias still names the namespace, and
        its prefix is derived from it. A quoted name that is not a URI is
        display text, so ``package "Building Things" as bld`` is ``package bld``.
        The reverse spelling, ``package Name as URI``, is refused by
        :meth:`_check_prefixes`.

        Args:
            name: The quoted or unquoted package name.
            alias: The value of the optional ``as`` clause, or None.

        Returns:
            The package name (the key classes are filed under, and the
            prefix it is bound to) and the namespace URI the package
            declares, if any.
        """
        if alias is None:
            if cls._looks_like_uri(name):
                # `package "http://x#" { … }`: no prefix is named, so one is derived.
                return cls._generate_prefix(name), name
            return name, None
        if cls._looks_like_uri(name):
            # `package "http://x#" as pfx` — the guide's form.
            return alias, name
        return alias, None

    @staticmethod
    def _generate_prefix(name: str) -> str:
        """Generate a namespace prefix from a package name.

        Args:
            name: Package name (may be a URI or display name)

        Returns:
            Short lowercase prefix string
        """
        # If it looks like a URI, extract the last segment
        if URI_SCHEME_PATTERN.match(name):
            # Extract meaningful part from URI
            name = name.rstrip("#/:")
            if "/" in name:
                name = name.rsplit("/", 1)[-1]
            if "#" in name:
                name = name.rsplit("#", 1)[-1]
            if ":" in name:
                name = name.rsplit(":", 1)[-1]

        # Clean and shorten
        prefix = re.sub(r"[^a-zA-Z0-9]", "", name).lower()
        return prefix[:10] if len(prefix) > 10 else prefix or "ns"

    @staticmethod
    def _namespace_iri(uri: str) -> str:
        """Return *uri* as the converter binds it: ending in ``#``, ``/`` or ``:``."""
        return uri if uri.endswith(("#", "/", ":")) else f"{uri}#"

    def _check_prefixes(self, source: str) -> None:
        """Refuse every prefix that cannot be written as the diagram gives it (#150).

        A prefix the diagram names, as a package's alias, a package's own name or
        a dotted class name, is used as written or refused: it must be a legal
        Turtle prefix, may claim a core prefix only for that prefix's own
        namespace, and may name only one namespace, which no other prefix names.
        A prefix derived for a URI package with no alias is held to the same
        rules, and is reported as a warning so the run says which it chose.
        Each refusal is a :class:`ParseError` on the declaration's line, so
        nothing is converted or written.

        Args:
            source: The diagram text before its markers are stripped, so that
                line numbers are the file's own.
        """
        lines = source.split("\n")
        # prefix -> (namespace IRI, or None for one generated from the default namespace, line)
        bound: dict[str, tuple[str | None, int]] = {}
        # namespace IRI -> (prefix, line)
        named: dict[str, tuple[str, int]] = {}
        derived: list[tuple[str, str, int]] = []

        def line_of(position: int) -> int:
            return source.count("\n", 0, position) + 1

        def refuse(line: int, message: str) -> None:
            content = lines[line - 1].strip() if line <= len(lines) else ""
            self._errors.append(ParseError(line_number=line, message=message, line_content=content))

        def claim(prefix: str, iri: str | None, line: int) -> None:
            if not PN_PREFIX_PATTERN.fullmatch(prefix):
                refuse(
                    line,
                    f'"{prefix}" is not a legal Turtle prefix: it must start with a letter, '
                    'hold only letters, digits, "_", "-" and ".", and not end with "."',
                )
                return
            core = CORE_PREFIXES.get(prefix)
            if core is not None and iri != core:
                refuse(
                    line,
                    f'"{prefix}" is a core prefix, bound to <{core}>; it cannot name '
                    f"{f'<{iri}>' if iri else 'a namespace of this diagram'}. "
                    "Choose another prefix",
                )
                return
            if prefix in bound:
                earlier, earlier_line = bound[prefix]
                if iri is not None and earlier is not None and iri != earlier:
                    refuse(
                        line,
                        f'"{prefix}" is already the prefix for <{earlier}> (line {earlier_line}); '
                        f"one prefix cannot name <{iri}> as well",
                    )
                    return
            if iri is not None:
                if iri in named and named[iri][0] != prefix:
                    other, other_line = named[iri]
                    refuse(
                        line,
                        f'<{iri}> already has the prefix "{other}" (line {other_line}); '
                        f'one namespace cannot have "{prefix}" as well',
                    )
                    return
                named.setdefault(iri, (prefix, line))
            if prefix not in bound or bound[prefix][0] is None:
                bound[prefix] = (iri, line)

        for match in self.PACKAGE_PATTERN.finditer(source):
            line = line_of(match.start())
            name = match.group(1) or match.group(2)
            alias = match.group(3)
            if alias is not None and self._looks_like_uri(alias.strip('"')):
                refuse(
                    line,
                    'the namespace IRI goes in quotes before "as", and the prefix after it: '
                    f'package "{alias.strip(chr(34))}" as {name}',
                )
                continue
            prefix, uri = self._package_identity(name, alias)
            if alias is None and uri is not None:
                derived.append((prefix, uri, line))
                continue
            claim(prefix, self._namespace_iri(uri) if uri else None, line)

        for prefix, uri, line in derived:
            iri = self._namespace_iri(uri)
            if prefix in bound and bound[prefix][0] == iri:
                continue
            if iri in named:
                other, other_line = named[iri]
                refuse(
                    line,
                    f'<{iri}> already has the prefix "{other}" (line {other_line}); '
                    f'write package "{uri}" as {other}',
                )
                continue
            if not PN_PREFIX_PATTERN.fullmatch(prefix):
                problem = "is not a legal Turtle prefix"
            elif prefix in CORE_PREFIXES and CORE_PREFIXES[prefix] != iri:
                problem = f"is a core prefix, bound to <{CORE_PREFIXES[prefix]}>"
            elif prefix in bound:
                earlier, earlier_line = bound[prefix]
                target = f"<{earlier}>" if earlier else "another package"
                problem = f"already names {target} (line {earlier_line})"
            else:
                bound[prefix] = (iri, line)
                named[iri] = (prefix, line)
                self._notes.append(
                    ParseWarning(
                        line,
                        f'derived the prefix "{prefix}" for <{iri}>; '
                        f'to choose it, write package "{uri}" as <prefix>',
                        line_content=lines[line - 1].strip(),
                        code="derived-prefix",
                    )
                )
                continue
            refuse(
                line,
                f'no prefix is named for <{iri}>, and "{prefix}", derived from it, {problem}. '
                f'Name one: package "{uri}" as <prefix>',
            )

        for match in self.CLASS_PATTERN.finditer(source):
            dotted = match.group(3) or match.group(5)
            package = parse_dotted_name(dotted)[0] if dotted else None
            if package is None:
                continue
            line = line_of(match.start() + match.group(0).index("class"))
            claim(package, bound[package][0] if package in bound else None, line)

    def _parse_classes(self, content: str) -> list[PumlClass]:
        """Extract class definitions from content."""
        classes = []
        package_map = self._build_package_map(content)

        for match in self.CLASS_PATTERN.finditer(content):
            self._consume(match)
            is_abstract = match.group(1) is not None
            display_name = None

            if match.group(3):  # "Display Name" as alias pattern
                display_name = match.group(2)  # "Building"
                alias = match.group(3)  # "building.Building"
                package, name = parse_dotted_name(alias)
            elif match.group(4):  # Just "Quoted Name"
                package, name = None, match.group(4)
            else:  # Unquoted name (group 5), may be dotted
                package, name = parse_dotted_name(match.group(5))

            stereotype = match.group(6)
            body = match.group(7) or ""

            # Package from dotted name takes precedence over positional package
            if package is None:
                pos = match.start()
                package = self._find_package_at_position(pos, package_map)

            # A box drawn as a property or an individual is named, not converted (#395)
            named = next(group for group in (3, 4, 5) if match.group(group))
            line_end = content.find("\n", match.end(named))
            declared = content[match.end(named) : len(content) if line_end == -1 else line_end]
            kind = _box_kind(declared.split("{", 1)[0])
            if kind is not None:
                written = match.group(named)
                start = match.start(named)
                line = content.count("\n", 0, start) + 1
                text = content[content.rfind("\n", 0, start) + 1 : match.end(named)] + declared
                self._warnings.append(
                    ParseWarning(
                        line,
                        f"{kind} {written} is not converted: only classes are, "
                        f"so {written} is not in the output",
                        line_content=text.strip(),
                        code="unmodelled",
                        kind=kind,
                    )
                )
                for dropped in (written, name, f"{package}.{name}" if package else name):
                    self._dropped.setdefault(dropped, kind)
                continue

            # Parse attributes from body
            attributes = self._parse_attributes(body)

            classes.append(
                PumlClass(
                    name=name,
                    package=package,
                    stereotype=stereotype,
                    attributes=attributes,
                    is_abstract=is_abstract or stereotype == "abstract",
                    display_name=display_name,
                )
            )

        # A name a class box also declares, as a punned term's is, still names the class
        for cls in classes:
            self._dropped.pop(cls.name, None)
            self._dropped.pop(cls.qualified_name, None)

        return classes

    def _parse_attributes(self, body: str) -> list[PumlAttribute]:
        """Extract attributes from a class body."""
        attributes = []

        for line in body.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("--"):
                continue  # Skip separators

            match = self.ATTRIBUTE_PATTERN.match(line)
            if match:
                visibility = match.group(1) or "+"
                is_static = match.group(2) is not None
                name = match.group(3)
                datatype = match.group(4)

                attributes.append(
                    PumlAttribute(
                        name=name,
                        datatype=datatype,
                        visibility=visibility,
                        is_static=is_static,
                    )
                )
            else:
                # Try simpler pattern: just "name" or "name : type"
                simple_match = re.match(r"(\w+)(?:\s*:\s*(\w+))?", line)
                if simple_match:
                    attributes.append(
                        PumlAttribute(
                            name=simple_match.group(1),
                            datatype=simple_match.group(2),
                        )
                    )

        return attributes

    def _parse_relationships(self, content: str) -> list[PumlRelationship]:
        """Extract relationship definitions from content."""
        relationships = []

        # Pattern for inheritance with direction hints
        inheritance_pattern = re.compile(
            r"(?:^|\n)\s*"
            r"([\w.]+)"  # Source (dotted names)
            r"\s*"
            r"(<\|)?"  # Left arrow head
            r"(-[udlr]?-)"  # Line with optional direction
            r"(\|>)?"  # Right arrow head
            r"\s*"
            r"([\w.]+)",  # Target (dotted names)
            re.MULTILINE,
        )

        for match in inheritance_pattern.finditer(content):
            source_full = match.group(1)
            left_head = match.group(2)
            right_head = match.group(4)
            target_full = match.group(5)

            # Split into package.name - store qualified name for lookup
            if left_head and not right_head:
                # <|-- pattern: target extends source
                self._consume(match)
                if self._names_dropped(content, match, source_full, target_full):
                    continue
                relationships.append(
                    PumlRelationship(
                        source=target_full,  # Keep full qualified name for lookup
                        target=source_full,
                        rel_type=RelationshipType.INHERITANCE,
                    )
                )
            elif right_head and not left_head:
                # --|> pattern: source extends target
                self._consume(match)
                if self._names_dropped(content, match, source_full, target_full):
                    continue
                relationships.append(
                    PumlRelationship(
                        source=source_full,
                        target=target_full,
                        rel_type=RelationshipType.INHERITANCE,
                    )
                )

        # Association pattern (unchanged but now with --)
        assoc_pattern = re.compile(
            r"(?:^|\n)\s*"
            r"([\w.]+)"
            r"\s*"
            r'(?:"([^"]*)")?\s*'
            r"([o*])?"
            r"--"  # Require two dashes
            r"([o*>])?"
            r"\s*"
            r'(?:"([^"]*)")?\s*'
            r"([\w.]+)"
            r"(?:\s*:\s*([^\n]+))?",
            re.MULTILINE,
        )

        for match in assoc_pattern.finditer(content):
            source = match.group(1)
            source_card = match.group(2)
            source_marker = match.group(3)
            target_marker = match.group(4)
            target_card = match.group(5)
            target = match.group(6)
            label = match.group(7)

            # Skip if this looks like inheritance (already handled)
            if "|" in str(target_marker) or "|" in str(source_marker):
                continue
            self._consume(match)
            if self._names_dropped(content, match, source, target):
                continue

            # Determine relationship type
            if source_marker == "*" or target_marker == "*":
                rel_type = RelationshipType.COMPOSITION
            elif source_marker == "o" or target_marker == "o":
                rel_type = RelationshipType.AGGREGATION
            else:
                rel_type = RelationshipType.ASSOCIATION

            if label:
                label = label.strip()

            relationships.append(
                PumlRelationship(
                    source=source,
                    target=target,
                    rel_type=rel_type,
                    label=label,
                    source_cardinality=source_card,
                    target_cardinality=target_card,
                )
            )

        return relationships

    def _names_dropped(self, content: str, match: re.Match[str], *ends: str) -> bool:
        """Name a relationship to a box that is not converted, and say whether there was one.

        A box drawn as a property or an individual is not in the output (#395), so a line
        naming one is not either; kept, it would name an undeclared class and refuse the file.

        Args:
            content: The text the passes read.
            match: The relationship's match.
            ends: The names at either end, as the line writes them.

        Returns:
            True if an end names a box that is not converted, with an ``unmodelled`` warning.
        """
        end = next((name for name in ends if name in self._dropped), None)
        if end is None:
            return False
        start = match.start() + len(match.group(0)) - len(match.group(0).lstrip())
        line_end = content.find("\n", start)
        text = content[start : len(content) if line_end == -1 else line_end].strip()
        self._warnings.append(
            ParseWarning(
                content.count("\n", 0, start) + 1,
                f"{text} names {self._dropped[end]} {end}, which is not converted, "
                f"so this line is not in the output",
                line_content=text,
                code="unmodelled",
                kind="relationship",
            )
        )
        return True

    def _parse_notes(self, content: str) -> list[PumlNote]:
        """Extract note definitions from content."""
        notes = []

        # Multi-line notes: note right of Class\n...\nend note
        multiline_pattern = re.compile(
            r"note\s+(right|left|top|bottom)\s+of\s+(\w+)\s*\n" r"(.*?)" r"\n\s*end\s*note",
            re.MULTILINE | re.DOTALL,
        )

        for match in multiline_pattern.finditer(content):
            self._consume(match)
            position = match.group(1)
            attached_to = match.group(2)
            text = match.group(3).strip()

            notes.append(
                PumlNote(
                    content=text,
                    attached_to=attached_to,
                    position=position,
                )
            )

        # Single-line notes: note right of Class : text
        inline_pattern = re.compile(
            r"note\s+(right|left|top|bottom)\s+of\s+(\w+)\s*:\s*([^\n]+)",
            re.MULTILINE,
        )

        for match in inline_pattern.finditer(content):
            self._consume(match)
            position = match.group(1)
            attached_to = match.group(2)
            text = match.group(3).strip()

            notes.append(
                PumlNote(
                    content=text,
                    attached_to=attached_to,
                    position=position,
                )
            )

        return notes

    def _attach_notes(self, model: PumlModel, notes: list[PumlNote]) -> None:
        """Attach notes to their referenced classes."""
        for note in notes:
            if note.attached_to:
                cls = model.get_class(note.attached_to)
                if cls:
                    cls.note = note.content
                else:
                    self._warnings.append(
                        ParseWarning(
                            line_number=None,
                            message=f"Note attached to unknown class: {note.attached_to}",
                            code="note-unknown-class",
                        )
                    )

    def _parse_title(self, content: str) -> Optional[str]:
        """Extract diagram title."""
        match = self.TITLE_PATTERN.search(content)
        if match:
            self._consume(match)
            return match.group(1).strip()
        return None

    def _parse_skinparams(self, content: str) -> dict[str, str]:
        """Extract skinparam settings."""
        params = {}
        for match in self.SKINPARAM_PATTERN.finditer(content):
            self._consume(match)
            key = match.group(1)
            value = match.group(2)
            params[key] = value
        return params

    def _build_package_map(self, content: str) -> list[tuple[int, int, str]]:
        """Build a map of character positions to package names.

        The package name is the same one :meth:`_parse_packages` records, so a
        class inside ``package "URI" as pfx`` is filed under ``pfx`` and not
        under the URI (#150).

        Returns a list of (start, end, package_name) tuples.
        """
        package_map = []

        for match in self.PACKAGE_PATTERN.finditer(content):
            name = match.group(1) or match.group(2)
            package_name, _namespace_uri = self._package_identity(name, match.group(3))
            start = match.end()

            # Find matching closing brace
            brace_count = 1
            pos = start
            while pos < len(content) and brace_count > 0:
                if content[pos] == "{":
                    brace_count += 1
                elif content[pos] == "}":
                    brace_count -= 1
                pos += 1

            package_map.append((start, pos - 1, package_name))

        return package_map

    def _find_package_at_position(
        self, pos: int, package_map: list[tuple[int, int, str]]
    ) -> Optional[str]:
        """Find which package contains a given character position."""
        for start, end, name in package_map:
            if start <= pos <= end:
                return name
        return None
