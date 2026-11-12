"""Regression and acceptance tests for Issue #360 (TASK-DOC-L01):
Theme, indexed palette, and tint color resolution in XLSX reading & round-trip writing.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
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


XLSX_CORPUS = Path("tests/docs/excel/xlsx")


def test_totals_row_shown_theme_and_tint_colors() -> None:
    """AC 1: libreoffice__totalsRowShown.xlsx A2 red fill + white text, B3 light blue fill."""
    wb = read_xlsx(XLSX_CORPUS / "libreoffice__totalsRowShown.xlsx")
    sh = wb[0]
    a2 = sh.get_cell(1, 0)
    b3 = sh.get_cell(2, 1)
    assert a2 is not None and b3 is not None
    assert a2.bg_color == "#C0504D"  # theme 5 (accent2 red)
    assert a2.fg_color == "#FFFFFF"  # theme 0 (lt1 white)
    assert b3.bg_color == apply_tint("#4F81BD", 0.59999389629810485)  # light blue


def test_sortconditionref_orange_fill_and_black_text() -> None:
    """AC 2: libreoffice__sortconditionref.xlsx B2 fill #FFC000 and readable black text."""
    wb = read_xlsx(XLSX_CORPUS / "libreoffice__sortconditionref.xlsx")
    b2 = wb[0].get_cell(1, 1)
    assert b2 is not None
    assert b2.bg_color == "#FFC000"
    assert b2.fg_color == "#000000"


def test_poi_49156_indexed_fills() -> None:
    """AC 3: poi__49156.xlsx indexed fills 41->#CCFFFF, 45->#FF99CC, 22->#C0C0C0."""
    wb = read_xlsx(XLSX_CORPUS / "poi__49156.xlsx")
    sh = wb[0]
    d10 = sh.get_cell(9, 3)
    e10 = sh.get_cell(9, 4)
    f10 = sh.get_cell(9, 5)
    assert d10 is not None and d10.bg_color == "#CCFFFF"
    assert e10 is not None and e10.bg_color == "#FF99CC"
    assert f10 is not None and f10.bg_color == "#C0C0C0"


def test_openxml_noextdatab1_indexed_53_font() -> None:
    """AC 4: openxml-sdk__NoExtDataB1.xlsx font indexed=53 resolves to #FF6600."""
    wb = read_xlsx(XLSX_CORPUS / "openxml-sdk__NoExtDataB1.xlsx")
    b1 = wb[0].get_cell(0, 1)
    assert b1 is not None
    assert b1.fg_color == "#FF6600"


def test_totals_row_function_custom_theme_teal_banner() -> None:
    """libreoffice__totalsRowFunction.xlsx B1 uses custom theme accent1 + negative tint."""
    wb = read_xlsx(XLSX_CORPUS / "libreoffice__totalsRowFunction.xlsx")
    b1 = wb[0].get_cell(0, 1)
    assert b1 is not None
    assert b1.fg_color == "#FFFFFF"
    assert b1.bg_color == apply_tint("#1CC5D5", -0.24994659260841701)


FIVE_FIXTURES = [
    "libreoffice__totalsRowShown.xlsx",
    "libreoffice__sortconditionref.xlsx",
    "poi__49156.xlsx",
    "openxml-sdk__NoExtDataB1.xlsx",
    "libreoffice__totalsRowFunction.xlsx",
]


@pytest.mark.parametrize("filename", FIVE_FIXTURES)
def test_roundtrip_preserves_theme_and_indexed_attributes(filename: str) -> None:
    """AC 5: Reading then writing each fixture keeps every theme= and indexed= attribute."""
    orig_bytes = (XLSX_CORPUS / filename).read_bytes()
    wb = read_xlsx(orig_bytes)
    saved_bytes = write_xlsx(wb)

    with zipfile.ZipFile(io.BytesIO(orig_bytes)) as z_orig, zipfile.ZipFile(
        io.BytesIO(saved_bytes)
    ) as z_saved:
        for part in z_orig.namelist():
            if not part.endswith(".xml"):
                continue
            orig_xml = z_orig.read(part).decode("utf-8", "replace")
            if "theme=" in orig_xml or "indexed=" in orig_xml:
                assert part in z_saved.namelist(), f"Missing part {part} after round-trip"
                saved_xml = z_saved.read(part).decode("utf-8", "replace")
                assert saved_xml.count("theme=") >= orig_xml.count("theme=")
                assert saved_xml.count("indexed=") >= orig_xml.count("indexed=")

    # Dirty regeneration path: StyleManager rebuilds styles.xml from model + color_specs
    wb.dirty = True
    wb[0].dirty = True
    dirty_bytes = write_xlsx(wb)
    wb_reloaded = read_xlsx(dirty_bytes)
    with zipfile.ZipFile(io.BytesIO(dirty_bytes)) as z_dirty:
        dirty_styles = z_dirty.read("xl/styles.xml").decode("utf-8", "replace")
        if filename in (
            "libreoffice__totalsRowShown.xlsx",
            "libreoffice__sortconditionref.xlsx",
            "libreoffice__totalsRowFunction.xlsx",
        ):
            assert "theme=" in dirty_styles
        if filename in ("poi__49156.xlsx", "openxml-sdk__NoExtDataB1.xlsx"):
            assert "indexed=" in dirty_styles
    assert len(wb_reloaded.sheets) == len(wb.sheets)


def test_dirty_cell_color_edit_overrides_stale_theme_spec() -> None:
    """Editing a cell color emits rgb= instead of stale theme= spec."""
    wb = read_xlsx(XLSX_CORPUS / "libreoffice__totalsRowShown.xlsx")
    a2 = wb[0].get_cell(1, 0)
    assert a2 is not None
    assert a2.bg_color == "#C0504D"
    # Simulate user picking a custom RGB fill color without clearing spec manually
    a2.bg_color = "#123456"
    wb[0].dirty = True
    out = write_xlsx(wb)
    reloaded = read_xlsx(out)
    a2_new = reloaded[0].get_cell(1, 0)
    assert a2_new is not None
    assert a2_new.bg_color == "#123456"
