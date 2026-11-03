"""The one datatype map ``puml2rdf`` reads (#155).

The converter and the validator both resolve an attribute's type through a
:class:`DatatypeMap`, so they cannot disagree about which types are known. A
``-C`` config's ``datatype_mappings`` are merged into the same map (#152).

Type names in a diagram are free text, so every lookup is case-folded: ``String``,
``string`` and ``STRING`` are the same type. A type written as a CURIE whose prefix
is ``xsd``, ``rdf``, ``rdfs`` or ``owl`` is checked against the datatypes those
vocabularies define (#480); one they do not define is not a datatype.
"""

import re
from collections.abc import Mapping

from rdflib import URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

# A URI scheme, as in `http:` or `urn:` (RFC 3986, section 3.1)
_SCHEME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")

# Common PlantUML/UML type names, keyed case-folded: lookups fold before matching
BUILTIN_DATATYPES: dict[str, URIRef] = {
    # String types
    "string": XSD.string,
    "str": XSD.string,
    "text": XSD.string,
    # Numeric types
    "integer": XSD.integer,
    "int": XSD.integer,
    "decimal": XSD.decimal,
    "float": XSD.float,
    "double": XSD.double,
    "number": XSD.decimal,
    # Boolean
    "boolean": XSD.boolean,
    "bool": XSD.boolean,
    # Date/time types
    "date": XSD.date,
    "datetime": XSD.dateTime,
    "time": XSD.time,
    "gyear": XSD.gYear,
    "gyearmonth": XSD.gYearMonth,
    "duration": XSD.duration,
    # URI types
    "uri": XSD.anyURI,
    "anyuri": XSD.anyURI,
    "url": XSD.anyURI,
    # Other common types
    "base64": XSD.base64Binary,
    "hexbinary": XSD.hexBinary,
    "language": XSD.language,
    "token": XSD.token,
}

# The XSD 1.1 built-in datatypes (XML Schema 1.1 Part 2, section 3), less the ur-types
# anyType, anySimpleType and anyAtomicType, and NOTATION, none of which a value can have.
XSD_DATATYPE_NAMES: frozenset[str] = frozenset(
    {
        "anyURI",
        "base64Binary",
        "boolean",
        "byte",
        "date",
        "dateTime",
        "dateTimeStamp",
        "dayTimeDuration",
        "decimal",
        "double",
        "duration",
        "ENTITIES",
        "ENTITY",
        "float",
        "gDay",
        "gMonth",
        "gMonthDay",
        "gYear",
        "gYearMonth",
        "hexBinary",
        "ID",
        "IDREF",
        "IDREFS",
        "int",
        "integer",
        "language",
        "long",
        "Name",
        "NCName",
        "negativeInteger",
        "NMTOKEN",
        "NMTOKENS",
        "nonNegativeInteger",
        "nonPositiveInteger",
        "normalizedString",
        "positiveInteger",
        "QName",
        "short",
        "string",
        "time",
        "token",
        "unsignedByte",
        "unsignedInt",
        "unsignedLong",
        "unsignedShort",
        "yearMonthDuration",
    }
)

# The datatypes of RDF 1.1 and the OWL 2 datatype map outside the XSD namespace
OTHER_DATATYPES: dict[str, URIRef] = {
    "rdf:langString": RDF.langString,
    "rdf:PlainLiteral": RDF.PlainLiteral,
    "rdf:XMLLiteral": RDF.XMLLiteral,
    "rdf:HTML": RDF.HTML,
    "rdfs:Literal": RDFS.Literal,
    "owl:real": URIRef(f"{OWL}real"),
    "owl:rational": URIRef(f"{OWL}rational"),
}

# The prefixes whose datatypes are known, so a CURIE with one of them is checked
_DATATYPE_NAMESPACES: dict[str, str] = {
    "xsd": str(XSD),
    "rdf": str(RDF),
    "rdfs": str(RDFS),
    "owl": str(OWL),
}

_KNOWN_IRIS: frozenset[str] = frozenset(
    {f"{XSD}{name}" for name in XSD_DATATYPE_NAMES} | {str(iri) for iri in OTHER_DATATYPES.values()}
)


class NotADatatype(ValueError):
    """A type written in a vocabulary whose datatypes are known, naming none of them."""


def _known_curie(curie: str) -> URIRef | None:
    """Return the datatype *curie* names, None if its prefix is not a datatype vocabulary.

    Raises:
        NotADatatype: If the prefix is ``xsd``, ``rdf``, ``rdfs`` or ``owl`` and the
            vocabulary defines no datatype of that name.
    """
    prefix, _, local = curie.partition(":")
    namespace = _DATATYPE_NAMESPACES.get(prefix)
    if namespace is None:
        return None
    iri = f"{namespace}{local}"
    if iri not in _KNOWN_IRIS:
        raise NotADatatype(_not_a_datatype(curie, namespace, local))
    return URIRef(iri)


def _not_a_datatype(written: str, namespace: str, local: str) -> str:
    """Say that *written* is not a datatype, naming the one it differs from only in case."""
    message = f"'{written}' is not a datatype: <{namespace}> defines no '{local}'"
    for iri in sorted(_KNOWN_IRIS):
        if iri.startswith(namespace) and iri[len(namespace) :].casefold() == local.casefold():
            prefix = next(p for p, ns in _DATATYPE_NAMESPACES.items() if ns == namespace)
            return f"{message}. Did you mean {prefix}:{iri[len(namespace):]}?"
    return message


def parse_datatype_value(value: str) -> URIRef:
    """Read a ``datatype_mappings`` value as the datatype IRI it names.

    Accepted: an ``xsd:`` CURIE naming an XSD 1.1 built-in datatype; ``rdf:langString``,
    ``rdf:PlainLiteral``, ``rdf:XMLLiteral``, ``rdf:HTML``, ``rdfs:Literal``, ``owl:real``
    or ``owl:rational``; or a full IRI, in ``<…>`` or bare when it starts ``http://``,
    ``https://`` or ``urn:``. A full IRI in one of those vocabularies must still name one
    of their datatypes.

    Args:
        value: The value as the config gives it.

    Returns:
        The datatype IRI.

    Raises:
        ValueError: If the value names no datatype, or uses a prefix other than those above.
    """
    text = value.strip()
    if text.startswith("<") and text.endswith(">"):
        iri = text[1:-1].strip()
        if not _SCHEME_PATTERN.match(iri):
            raise ValueError(f"'{value}' is not an IRI: it has no scheme, such as http:")
    elif text.startswith(("http://", "https://", "urn:")):
        iri = text
    elif text.partition(":")[0] in _DATATYPE_NAMESPACES:
        known = _known_curie(text)
        assert known is not None  # its prefix is a datatype vocabulary
        return known
    else:
        raise ValueError(
            f"'{value}' is not a datatype: give an xsd: CURIE such as xsd:decimal; "
            "rdf:langString, rdf:PlainLiteral, rdf:XMLLiteral, rdf:HTML, rdfs:Literal, "
            "owl:real or owl:rational; or a full IRI, such as <http://example.org/dt#money>"
        )
    for namespace in _DATATYPE_NAMESPACES.values():
        if iri.startswith(namespace) and iri not in _KNOWN_IRIS:
            raise NotADatatype(_not_a_datatype(value, namespace, iri[len(namespace) :]))
    return URIRef(iri)


class DatatypeMap:
    """The built-in type names, with a config's ``datatype_mappings`` merged over them.

    Attributes:
        overrides: Built-in names a user mapping replaced, in the config's order.
    """

    def __init__(self, user: Mapping[str, str] | None = None) -> None:
        """Build the map.

        Args:
            user: Type name to datatype value, as a config gives them.

        Raises:
            ValueError: If a value names no datatype, or two names are the same once
                case-folded.
        """
        self._user: dict[str, URIRef] = {}
        self._spelling: dict[str, str] = {}
        self.overrides: list[str] = []
        for name, value in (user or {}).items():
            key = name.strip().casefold()
            if not key:
                raise ValueError("a datatype mapping has an empty type name")
            if key in self._user:
                raise ValueError(
                    f"'{self._spelling[key]}' and '{name}' are the same type name: "
                    "type names are matched without regard to case, so map only one of them"
                )
            try:
                self._user[key] = parse_datatype_value(value)
            except ValueError as error:
                raise ValueError(f"'{name}': {error}") from error
            self._spelling[key] = name
            if key in BUILTIN_DATATYPES:
                self.overrides.append(name)

    def resolve(self, name: str) -> URIRef | None:
        """Return the datatype a type name stands for.

        Args:
            name: The type as the diagram writes it.

        Returns:
            The datatype IRI, or None for a name the map does not know.

        Raises:
            NotADatatype: If *name* is a CURIE in ``xsd``, ``rdf``, ``rdfs`` or ``owl``
                that names none of their datatypes, such as ``xsd:Foo``.
        """
        key = name.strip().casefold()
        if key in self._user:
            return self._user[key]
        if key in BUILTIN_DATATYPES:
            return BUILTIN_DATATYPES[key]
        if ":" in name:
            return _known_curie(name.strip())
        return None
