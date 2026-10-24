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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rdflib import Graph

from rdf_construct.puml2rdf.model import (
    PumlAttribute,
    PumlClass,
    PumlModel,
    PumlNote,
    PumlPackage,
    PumlRelationship,
    RelationshipType,
)

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
        line_number: Line where the error occurred
        message: Description of the error
        line_content: The actual line content
    """

    line_number: int
    message: str
    line_content: str


@dataclass
class ParseResult:
    """Result of parsing a PlantUML file.

    Attributes:
        model: The parsed model (may be partial if errors occurred)
        errors: List of parse errors encountered
        warnings: List of non-fatal warnings
    """

    model: PumlModel
    errors: list[ParseError]
    warnings: list[str]

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
        self._warnings: list[str] = []
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

        model = PumlModel()

        # Prefixes are checked against the text as given, so a refusal names the file's line
        self._check_prefixes(content)

        # Strip @startuml / @enduml
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

        return ParseResult(model=model, errors=self._errors, warnings=self._warnings)

    def parse_file(self, path: Path) -> ParseResult:
        """Parse a PlantUML file.

        Args:
            path: Path to the .puml file

        Returns:
            ParseResult containing the model and any errors/warnings
        """
        content = path.read_text(encoding="utf-8")
        return self.parse(content)

    def _strip_diagram_markers(self, content: str) -> str:
        """Remove @startuml and @enduml markers."""
        # Remove @startuml (with optional name)
        content = re.sub(r"@startuml\s*(?:\([^)]*\))?\s*\n?", "", content)
        # Remove @enduml
        content = re.sub(r"@enduml\s*", "", content)
        return content

    def _parse_packages(self, content: str) -> list[PumlPackage]:
        """Extract package definitions from content."""
        packages = []

        for match in self.PACKAGE_PATTERN.finditer(content):
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
        """Return *uri* as the converter binds it: ending in ``#`` or ``/``."""
        return uri if uri.endswith(("#", "/")) else f"{uri}#"

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
        lines = source.splitlines()
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
                self._warnings.append(
                    f'Line {line}: derived the prefix "{prefix}" for <{iri}>; '
                    f'to choose it, write package "{uri}" as <prefix>'
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

            # Parse attributes from body
            attributes = self._parse_attributes(body)

            # Package from dotted name takes precedence over positional package
            if package is None:
                pos = match.start()
                package = self._find_package_at_position(pos, package_map)

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
                relationships.append(
                    PumlRelationship(
                        source=target_full,  # Keep full qualified name for lookup
                        target=source_full,
                        rel_type=RelationshipType.INHERITANCE,
                    )
                )
            elif right_head and not left_head:
                # --|> pattern: source extends target
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

    def _parse_notes(self, content: str) -> list[PumlNote]:
        """Extract note definitions from content."""
        notes = []

        # Multi-line notes: note right of Class\n...\nend note
        multiline_pattern = re.compile(
            r"note\s+(right|left|top|bottom)\s+of\s+(\w+)\s*\n" r"(.*?)" r"\n\s*end\s*note",
            re.MULTILINE | re.DOTALL,
        )

        for match in multiline_pattern.finditer(content):
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
                    self._warnings.append(f"Note attached to unknown class: {note.attached_to}")

    def _parse_title(self, content: str) -> Optional[str]:
        """Extract diagram title."""
        match = self.TITLE_PATTERN.search(content)
        if match:
            return match.group(1).strip()
        return None

    def _parse_skinparams(self, content: str) -> dict[str, str]:
        """Extract skinparam settings."""
        params = {}
        for match in self.SKINPARAM_PATTERN.finditer(content):
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
