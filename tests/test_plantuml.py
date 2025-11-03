import pytest
from rdf_construct.uml.uml_style import ColorPalette


def test_to_plantuml_full_spec():
    """Test complete color specification."""
    palette = ColorPalette({
        "border": "#968584",
        "fill": "#FEFE54",
        "text": "#000000",
        "line_style": "bold"
    })

    result = palette.to_plantuml()

    # Should have single # at start
    assert result.startswith("#")
    assert not result.startswith("##")

    # Should use back: prefix
    assert "back:FEFE54" in result

    # Should not have # after colons
    assert ";line:#" not in result
    assert ";text:#" not in result

    # Should have all components
    assert "back:FEFE54" in result
    assert "line:968584" in result
    assert "line.bold" in result
    assert "text:000000" in result

    # Complete check
    assert result == "#back:FEFE54;line:968584;line.bold;text:000000"


def test_to_plantuml_minimal():
    """Test with just fill color."""
    palette = ColorPalette({"fill": "#FFFFFF"})
    assert palette.to_plantuml() == "#back:FFFFFF"


def test_to_plantuml_strips_hash():
    """Test that existing # prefixes are stripped."""
    palette = ColorPalette({
        "fill": "##FEFE54",  # Double hash
        "border": "#968584",  # Single hash
        "text": "000000"  # No hash
    })

    result = palette.to_plantuml()
    assert result == "#back:FEFE54;line:968584;text:000000"


def test_to_plantuml_empty():
    """Test with no colors specified."""
    palette = ColorPalette({})
    assert palette.to_plantuml() == ""
