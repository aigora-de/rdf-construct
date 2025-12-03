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
    """Test with just fill color.

    Note: ColorPalette applies default border (#000000) when not specified,
    so output includes both fill and line components.
    """
    palette = ColorPalette({"fill": "#FFFFFF"})
    # Default border (#000000) is applied
    assert palette.to_plantuml() == "#back:FFFFFF;line:000000"


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
    """Test with no colors specified.

    Note: ColorPalette applies defaults (fill=#FFFFFF, border=#000000)
    when config is empty, so output includes default styling.
    """
    palette = ColorPalette({})
    # Defaults are applied: fill=#FFFFFF, border=#000000
    assert palette.to_plantuml() == "#back:FFFFFF;line:000000"


def test_to_plantuml_explicit_none():
    """Test that explicit None values override defaults."""
    palette = ColorPalette({
        "fill": None,
        "border": None,
        "text": None
    })
    # When explicitly set to None, config.get() returns None (not default)
    # But ColorPalette uses config.get("fill", "#FFFFFF") so None becomes the value
    # Actually this still returns the default because get() with default only
    # applies when key is missing, not when value is None
    # So this test documents current behavior
    assert palette.fill is None
    assert palette.border is None
    assert palette.to_plantuml() == ""
