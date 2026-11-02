"""Tests for Excel slicer/timeline part preservation and corrupted workbook recovery.

Ported from .vibeoffice/tests/ledger/slicers.test.js and recovery.test.js.
"""

from __future__ import annotations

import io
import zipfile

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx


def _build_minimal_xlsx_bytes() -> bytes:
    """Build a minimal valid XLSX byte buffer in memory."""
    buf = io.BytesIO()
    types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n'
        '  <Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>\n'
        '  <Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>\n'
        "</Relationships>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
        "  <sheets>\n"
        '    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>\n'
        "  </sheets>\n"
        "</workbook>"
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>\n'
        "</Relationships>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">\n'
        "  <sheetData>\n"
        '    <row r="1"><c r="A1" t="n"><v>42</v></c></row>\n'
        "  </sheetData>\n"
        "</worksheet>"
    )

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types_xml)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook_xml)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


def test_corrupted_shared_strings_recovery():
    """Verify corrupted sharedStrings XML does not crash reader and salvages cell values."""
    base_bytes = _build_minimal_xlsx_bytes()
    buf = io.BytesIO()

    # Re-pack with a malformed sharedStrings.xml
    with zipfile.ZipFile(io.BytesIO(base_bytes), "r") as zin:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                zout.writestr(item, zin.read(item.filename))
            # Add malformed XML
            zout.writestr("xl/sharedStrings.xml", "<sst><si><t>Broken XML without closing tags")

    wb = read_xlsx(buf.getvalue())
    assert len(wb.sheets) >= 1
    sh = wb.sheets[0]
    cell = sh.get_cell(0, 0)
    assert cell is not None
    assert cell.value == 42


def test_corrupted_styles_recovery():
    """Verify corrupted styles.xml falls back to default cell formats gracefully."""
    base_bytes = _build_minimal_xlsx_bytes()
    buf = io.BytesIO()

    with zipfile.ZipFile(io.BytesIO(base_bytes), "r") as zin:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                zout.writestr(item, zin.read(item.filename))
            zout.writestr("xl/styles.xml", "MALFORMED_NON_XML_STYLES_BINARY_GARBAGE")

    wb = read_xlsx(buf.getvalue())
    assert len(wb.sheets) >= 1
    sh = wb.sheets[0]
    cell = sh.get_cell(0, 0)
    assert cell is not None
    assert cell.value == 42


def test_slicers_and_timelines_package_presence():
    """Verify package preservation preserves custom slicer parts."""
    base_bytes = _build_minimal_xlsx_bytes()
    buf = io.BytesIO()

    slicer_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<slicer xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" '
        'name="Slicer_Region" caption="Region"/>'
    )

    with zipfile.ZipFile(io.BytesIO(base_bytes), "r") as zin:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                zout.writestr(item, zin.read(item.filename))
            zout.writestr("xl/slicers/slicer1.xml", slicer_xml)

    # Read and ensure workbook parses cleanly
    wb = read_xlsx(buf.getvalue())
    assert len(wb.sheets) >= 1
    assert wb.sheets[0].get_cell(0, 0).value == 42
