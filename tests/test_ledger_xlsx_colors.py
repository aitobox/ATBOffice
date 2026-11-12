"""Regression and acceptance tests for Issue #360 (TASK-DOC-L01):
Theme, indexed palette, and tint color resolution in XLSX reading & round-trip writing.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from atboffice.modules.spreadsheet.models.color_utils import (
    DEFAULT_INDEXED_PALETTE,
    DEFAULT_THEME_COLORS,
    apply_tint,
    normalize_hex_color,
    parse_color_element,
    parse_theme_xml,
    resolve_color_spec,
)


def test_default_indexed_palette_entries() -> None:
    assert len(DEFAULT_INDEXED_PALETTE) == 64
    assert DEFAULT_INDEXED_PALETTE[22] == "#C0C0C0"
    assert DEFAULT_INDEXED_PALETTE[41] == "#CCFFFF"
    assert DEFAULT_INDEXED_PALETTE[45] == "#FF99CC"
    assert DEFAULT_INDEXED_PALETTE[53] == "#FF6600"


def test_normalize_hex_color() -> None:
    assert normalize_hex_color("FFFFC000") == "#FFC000"
    assert normalize_hex_color("ffc000") == "#FFC000"
    assert normalize_hex_color("#00ff00") == "#00FF00"
    assert normalize_hex_color("80FF0000") == "#80FF0000"
    assert normalize_hex_color(None) is None
    assert normalize_hex_color("") is None


def test_color_priority_theme_beats_rgb_beats_indexed() -> None:
    el = ET.fromstring(
        '<color theme="5" rgb="FF112233" indexed="41" tint="0.5"/>'
    )
    spec = parse_color_element(el)
    assert spec == {"theme": 5, "tint": 0.5}
    resolved = resolve_color_spec(spec, DEFAULT_THEME_COLORS, DEFAULT_INDEXED_PALETTE)
    assert resolved == apply_tint("#C0504D", 0.5)

    el_rgb = ET.fromstring('<color rgb="FF112233" indexed="41"/>')
    spec_rgb = parse_color_element(el_rgb)
    assert spec_rgb == {"rgb": "FF112233"}
    assert resolve_color_spec(spec_rgb) == "#112233"


def test_indexed_64_and_65_and_auto() -> None:
    assert resolve_color_spec({"indexed": 64}, auto="#000000") == "#000000"
    assert resolve_color_spec({"indexed": 64}) == "#000000"
    assert resolve_color_spec({"indexed": 65}) == "#FFFFFF"
    assert resolve_color_spec({"auto": True}, auto=None) is None
    assert resolve_color_spec({"auto": True}, auto="#000000") == "#000000"


def test_negative_and_positive_tint_math() -> None:
    # Darken accent1 (#4F81BD) by -0.25 and lighten by +0.6
    dark = apply_tint("#4F81BD", -0.25)
    light = apply_tint("#4F81BD", 0.6)
    assert dark.startswith("#") and len(dark) == 7
    assert light.startswith("#") and len(light) == 7
    assert dark != "#4F81BD"
    assert light != "#4F81BD"
    # Extreme negative tint -> black, extreme positive -> white
    assert apply_tint("#4F81BD", -1.0) == "#000000"
    assert apply_tint("#4F81BD", 1.0) == "#FFFFFF"


def test_parse_theme_xml_extracts_12_colors_in_spreadsheetml_order() -> None:
    theme_xml = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Custom">
      <a:themeElements>
        <a:clrScheme name="Custom">
          <a:dk1><a:sysClr val="windowText" lastClr="111111"/></a:dk1>
          <a:lt1><a:sysClr val="window" lastClr="FAFAFA"/></a:lt1>
          <a:dk2><a:srgbClr val="222222"/></a:dk2>
          <a:lt2><a:srgbClr val="EEEEEE"/></a:lt2>
          <a:accent1><a:srgbClr val="1CC5D5"/></a:accent1>
          <a:accent2><a:srgbClr val="FF8F0E"/></a:accent2>
          <a:accent3><a:srgbClr val="9A47A8"/></a:accent3>
          <a:accent4><a:srgbClr val="6DCC5C"/></a:accent4>
          <a:accent5><a:srgbClr val="EF3252"/></a:accent5>
          <a:accent6><a:srgbClr val="F4D347"/></a:accent6>
          <a:hlink><a:srgbClr val="0000FF"/></a:hlink>
          <a:folHlink><a:srgbClr val="800080"/></a:folHlink>
        </a:clrScheme>
        <a:fontScheme name="Custom">
          <a:majorFont><a:latin typeface="Century Gothic"/></a:majorFont>
          <a:minorFont><a:latin typeface="Calibri"/></a:minorFont>
        </a:fontScheme>
      </a:themeElements>
    </a:theme>'''
    parsed = parse_theme_xml(theme_xml)
    assert parsed["name"] == "Custom"
    assert parsed["colors"][0] == "#FAFAFA"  # lt1
    assert parsed["colors"][1] == "#111111"  # dk1
    assert parsed["colors"][2] == "#EEEEEE"  # lt2
    assert parsed["colors"][3] == "#222222"  # dk2
    assert parsed["colors"][4] == "#1CC5D5"  # accent1
    assert len(parsed["colors"]) == 12
    assert parsed["major"] == "Century Gothic"
    assert parsed["minor"] == "Calibri"
