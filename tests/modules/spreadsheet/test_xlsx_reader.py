"""Unit tests for pure Python XLSX reader."""

from __future__ import annotations

import io
import zipfile

import pytest

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx


def build_test_xlsx(
    sheets: list[dict[str, str]],
    shared_strings: list[str] | None = None,
    styles_xml: str | None = None,
    active_tab: int = 0,
) -> bytes:
    """Build an in-memory valid XLSX zip file with provided parts."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # [Content_Types].xml
        sheet_ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
        wb_ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
        sst_ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"
        styles_ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"
        rels_ct = "application/vnd.openxmlformats-package.relationships+xml"

        sheet_types = "".join(
            f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" ContentType="{sheet_ct}"/>'
            for i in range(len(sheets))
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            f'  <Default Extension="rels" ContentType="{rels_ct}"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            f'  <Override PartName="/xl/workbook.xml" ContentType="{wb_ct}"/>\n'
            f"  {sheet_types}\n"
            f'  <Override PartName="/xl/sharedStrings.xml" ContentType="{sst_ct}"/>\n'
            f'  <Override PartName="/xl/styles.xml" ContentType="{styles_ct}"/>\n'
            "</Types>"
        )
        z.writestr("[Content_Types].xml", content_types)

        # _rels/.rels
        doc_rel_type = (
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
        )
        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{doc_rel_type}" Target="xl/workbook.xml"/>\n'
            "</Relationships>"
        )
        z.writestr("_rels/.rels", root_rels)

        # xl/_rels/workbook.xml.rels
        ws_rel_type = (
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
        )
        wb_rels_items = [
            f'<Relationship Id="rId{i+1}" Type="{ws_rel_type}" '
            f'Target="worksheets/sheet{i+1}.xml"/>'
            for i in range(len(sheets))
        ]
        sst_rel_type = (
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings"
        )
        sst_rel_id = f"rId{len(sheets) + 1}"
        wb_rels_items.append(
            f'<Relationship Id="{sst_rel_id}" Type="{sst_rel_type}" Target="sharedStrings.xml"/>'
        )
        style_rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
        style_rel_id = f"rId{len(sheets) + 2}"
        wb_rels_items.append(
            f'<Relationship Id="{style_rel_id}" Type="{style_rel_type}" Target="styles.xml"/>'
        )

        wb_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  {"".join(wb_rels_items)}\n'
            "</Relationships>"
        )
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)

        # xl/workbook.xml
        sheets_xml = "".join(
            f'<sheet name="{s.get("name", f"Sheet{i+1}")}" sheetId="{i+1}" r:id="rId{i+1}"/>'
            for i, s in enumerate(sheets)
        )
        wb_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
            "  <bookViews>\n"
            f'    <workbookView activeTab="{active_tab}"/>\n'
            "  </bookViews>\n"
            "  <sheets>\n"
            f"    {sheets_xml}\n"
            "  </sheets>\n"
            "</workbook>"
        )
        z.writestr("xl/workbook.xml", wb_xml)

        # xl/sharedStrings.xml
        if shared_strings is not None:
            si_items = []
            for s in shared_strings:
                if s.startswith("<r>"):
                    si_items.append(f"<si>{s}</si>")
                else:
                    si_items.append(f"<si><t>{s}</t></si>")
            sst_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                f'count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">\n'
                f'  {"".join(si_items)}\n'
                "</sst>"
            )
            z.writestr("xl/sharedStrings.xml", sst_xml)

        # xl/styles.xml
        default_styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1">
    <font><name val="Calibri"/><sz val="11"/></font>
  </fonts>
  <fills count="2">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
  </fills>
  <borders count="1">
    <border><left/><right/><top/><bottom/><diagonal/></border>
  </borders>
  <cellXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
  </cellXfs>
</styleSheet>"""
        z.writestr("xl/styles.xml", styles_xml or default_styles)

        # Worksheets
        for i, s in enumerate(sheets):
            xml_content = s.get("xml", "<worksheet><sheetData/></worksheet>")
            z.writestr(f"xl/worksheets/sheet{i+1}.xml", xml_content)

    return buf.getvalue()


def test_read_simple_xlsx():
    """Verify reading a basic sheet with numbers and strings."""
    ws_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
      <c r="B1"><v>123.45</v></c>
      <c r="C1"><v>100</v></c>
    </row>
  </sheetData>
</worksheet>"""
    data = build_test_xlsx(
        sheets=[{"name": "Summary", "xml": ws_xml}],
        shared_strings=["Revenue"],
    )

    wb = read_xlsx(data)
    assert len(wb) == 1
    sheet = wb[0]
    assert sheet.name == "Summary"
    assert sheet.get_cell_value(0, 0) == "Revenue"
    assert sheet.get_cell_value(0, 1) == 123.45
    assert sheet.get_cell_value(0, 2) == 100


def test_read_cell_types():
    """Verify boolean, error, date, inline string and empty cells."""
    ws_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="b"><v>1</v></c>
      <c r="B1" t="b"><v>0</v></c>
      <c r="C1" t="e"><v>#REF!</v></c>
      <c r="D1" t="inlineStr"><is><t>Inline text</t></is></c>
      <c r="E1" t="str"><v>DirectStr</v></c>
      <c r="F1" t="d"><v>2026-10-29</v></c>
    </row>
  </sheetData>
</worksheet>"""
    data = build_test_xlsx(sheets=[{"name": "Types", "xml": ws_xml}])
    wb = read_xlsx(data)
    sheet = wb[0]

    assert sheet.get_cell_value(0, 0) is True
    assert sheet.get_cell_value(0, 1) is False
    assert sheet.get_cell_value(0, 2) == "#REF!"
    assert sheet.get_cell_value(0, 3) == "Inline text"
    assert sheet.get_cell_value(0, 4) == "DirectStr"
    assert sheet.get_cell_value(0, 5) == "2026-10-29"


def test_read_formulas():
    """Verify formula extraction and pre-calculated value preservation."""
    ws_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1"><v>10</v></c>
      <c r="B1"><v>20</v></c>
      <c r="C1"><f>SUM(A1:B1)</f><v>30</v></c>
    </row>
  </sheetData>
</worksheet>"""
    data = build_test_xlsx(sheets=[{"name": "Calc", "xml": ws_xml}])
    wb = read_xlsx(data)
    sheet = wb[0]

    cell_c1 = sheet.get_cell(0, 2)
    assert cell_c1 is not None
    assert cell_c1.formula == "SUM(A1:B1)"
    assert cell_c1.value == 30


def test_read_shared_strings_rich_text():
    """Verify shared strings with rich text runs (<r><t>)."""
    rich_str = "<r><t>Hello </t></r><r><rPr><b/></rPr><t>World</t></r>"
    ws_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
    </row>
  </sheetData>
</worksheet>"""
    data = build_test_xlsx(
        sheets=[{"name": "Rich", "xml": ws_xml}],
        shared_strings=[rich_str],
    )
    wb = read_xlsx(data)
    sheet = wb[0]
    assert sheet.get_cell_value(0, 0) == "Hello World"


def test_read_styles():
    """Verify fonts, fills, borders, alignments, and number formats."""
    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="1">
    <numFmt numFmtId="164" formatCode="$#,##0.00"/>
  </numFmts>
  <fonts count="2">
    <font><name val="Calibri"/><sz val="11"/></font>
    <font>
      <b/>
      <i/>
      <u val="single"/>
      <strike/>
      <sz val="14"/>
      <color rgb="FFFF0000"/>
      <name val="Helvetica"/>
    </font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill>
      <patternFill patternType="solid">
        <fgColor rgb="FF00FF00"/>
      </patternFill>
    </fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FF0000FF"/></left>
      <right style="thick"><color rgb="FF000000"/></right>
      <top style="dashed"/>
      <bottom style="double"/>
    </border>
  </borders>
  <cellXfs count="2">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="164" fontId="1" fillId="2" borderId="1" xfId="0"
        applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="top" wrapText="1"/>
    </xf>
  </cellXfs>
</styleSheet>"""

    ws_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" s="1"><v>1234.5</v></c>
    </row>
  </sheetData>
</worksheet>"""

    data = build_test_xlsx(
        sheets=[{"name": "Styled", "xml": ws_xml}],
        styles_xml=styles_xml,
    )
    wb = read_xlsx(data)
    cell = wb[0].get_cell(0, 0)
    assert cell is not None
    assert cell.bold is True
    assert cell.italic is True
    assert cell.underline is True
    assert cell.strike is True
    assert cell.font_size == 14
    assert cell.font_family == "Helvetica"
    assert cell.fg_color == "FFFF0000"
    assert cell.bg_color == "FF00FF00"
    assert cell.align_h == "center"
    assert cell.align_v == "top"
    assert cell.wrap_text is True
    assert cell.format_code == "$#,##0.00"
    assert cell.border_left is not None and cell.border_left.style == "thin"
    assert cell.border_right is not None and cell.border_right.style == "thick"


def test_read_geometry_and_merges():
    """Verify row heights, col widths, hidden flags, and merged cell regions."""
    ws_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <cols>
    <col min="2" max="2" width="20" customWidth="1"/>
    <col min="3" max="3" width="10" hidden="1"/>
  </cols>
  <sheetData>
    <row r="1" ht="30" customHeight="1">
      <c r="A1"><v>Header</v></c>
    </row>
    <row r="2" hidden="1">
      <c r="A2"><v>Hidden</v></c>
    </row>
  </sheetData>
  <mergeCells count="1">
    <mergeCell ref="A1:C2"/>
  </mergeCells>
</worksheet>"""
    data = build_test_xlsx(sheets=[{"name": "Layout", "xml": ws_xml}])
    wb = read_xlsx(data)
    sheet = wb[0]

    # Geometry
    # col 2 (1-based B) is col index 1
    assert sheet.geometry.col_size(1) > sheet.geometry.default_col_width
    assert 2 in sheet.geometry.hidden_cols  # col 3 (1-based C) is col index 2
    assert sheet.geometry.row_size(0) > sheet.geometry.default_row_height
    assert 1 in sheet.geometry.hidden_rows  # row 2 is index 1

    # Merges: A1:C2 -> (r1=0, c1=0, r2=1, c2=2)
    assert len(sheet.merges) == 1
    assert sheet.merges[0] == (0, 0, 1, 2)
    assert sheet.is_merged(0, 0) is True
    assert sheet.is_merged(1, 2) is True
    assert sheet.is_merged(2, 2) is False


def test_read_multi_sheet_and_active_tab():
    """Verify multi-sheet workbook structure and active sheet selection."""
    ws1 = "<worksheet><sheetData><row r='1'><c r='A1'><v>1</v></c></row></sheetData></worksheet>"
    ws2 = "<worksheet><sheetData><row r='1'><c r='A1'><v>2</v></c></row></sheetData></worksheet>"
    ws3 = "<worksheet><sheetData><row r='1'><c r='A1'><v>3</v></c></row></sheetData></worksheet>"

    data = build_test_xlsx(
        sheets=[
            {"name": "First", "xml": ws1},
            {"name": "Second", "xml": ws2},
            {"name": "Third", "xml": ws3},
        ],
        active_tab=1,
    )
    wb = read_xlsx(data)
    assert len(wb) == 3
    assert [s.name for s in wb.sheets] == ["First", "Second", "Third"]
    assert wb.active_sheet_index == 1
    assert wb.active_sheet.name == "Second"
    assert wb[0].get_cell_value(0, 0) == 1
    assert wb[1].get_cell_value(0, 0) == 2
    assert wb[2].get_cell_value(0, 0) == 3


def test_invalid_input_error_handling():
    """Verify corrupted or invalid archives raise ValueError."""
    with pytest.raises(ValueError, match="not a valid XLSX"):
        read_xlsx(b"not a zip file")

    with pytest.raises(ValueError, match="not a valid XLSX|damaged"):
        # Valid zip but missing workbook.xml
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("test.txt", "hello")
        read_xlsx(buf.getvalue())
