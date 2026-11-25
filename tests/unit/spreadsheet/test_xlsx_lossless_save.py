"""Regression tests for XLSX save fidelity (data that used to be lost on save)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.spreadsheet.io.xlsx_reader import _parse_rels, read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.spreadsheet.models.sheet_model import CellData

CORPUS = Path(__file__).resolve().parents[2] / "docs" / "excel" / "xlsx"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/data.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.spreadsheetml.worksheet+xml"/>'
    '<Override PartName="/xl/worksheets/secret.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.spreadsheetml.worksheet+xml"/>'
    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.spreadsheetml.styles+xml"/>'
    "</Types>"
)

STYLES = (
    f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="{NS}">'
    '<numFmts count="1"><numFmt numFmtId="170" formatCode="0.000"/></numFmts>'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="2"><fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill></fills>'
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="1" applyFont="1"/>'
    '<xf numFmtId="170" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    "</cellXfs>"
    '<cellStyles count="2"><cellStyle name="Normal" xfId="0" builtinId="0"/>'
    '<cellStyle name="MyHeading" xfId="1"/></cellStyles>'
    '<dxfs count="1"><dxf><font><color rgb="FF9C0006"/></font></dxf></dxfs>'
    '<tableStyles count="0"/></styleSheet>'
)


def _workbook_xml(prefix: str = "") -> str:
    p = f"{prefix}:" if prefix else ""
    xmlns = f'xmlns:{prefix}="{NS}"' if prefix else f'xmlns="{NS}"'
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<{p}workbook {xmlns} xmlns:r="{NS_R}">'
        f'<{p}fileVersion appName="xl" lastEdited="7" lowestEdited="7" rupBuild="27328"/>'
        f'<{p}workbookPr defaultThemeVersion="166925"/>'
        f'<{p}bookViews><{p}workbookView activeTab="0"/></{p}bookViews>'
        f'<{p}sheets><{p}sheet name="Data" sheetId="3" r:id="rIdData"/>'
        f'<{p}sheet name="Secret" sheetId="7" state="hidden" r:id="rIdSecret"/></{p}sheets>'
        f'<{p}calcPr calcId="191029" iterate="1" iterateCount="50"/>'
        f'<{p}extLst><{p}ext uri="{{140A7094-0E35-4892-8432-C4D2E57EDEB5}}" '
        'xmlns:x15="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main">'
        f'<x15:workbookPr chartTrackingRefBase="1"/></{p}ext></{p}extLst>'
        f"</{p}workbook>"
    )


def _sheet_xml(prefix: str = "", body: str = "") -> str:
    p = f"{prefix}:" if prefix else ""
    xmlns = f'xmlns:{prefix}="{NS}"' if prefix else f'xmlns="{NS}"'
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<{p}worksheet {xmlns}>"
        f'<{p}dimension ref="A1:B3"/>'
        f'<{p}cols><{p}col min="1" max="1" width="12" style="2" customWidth="1"/></{p}cols>'
        f"<{p}sheetData>{body}</{p}sheetData>"
        f'<{p}conditionalFormatting sqref="A1:A3"><{p}cfRule type="cellIs" dxfId="0" '
        f'priority="1" operator="greaterThan"><{p}formula>1</{p}formula></{p}cfRule>'
        f"</{p}conditionalFormatting>"
        f"</{p}worksheet>"
    )


def _shared_formula_rows(prefix: str = "") -> str:
    p = f"{prefix}:" if prefix else ""
    return (
        f'<{p}row r="1"><{p}c r="A1"><{p}v>1</{p}v></{p}c>'
        f'<{p}c r="B1" s="1"><{p}f t="shared" ref="B1:B3" si="0">A1*2</{p}f><{p}v>2</{p}v></{p}c>'
        f"</{p}row>"
        f'<{p}row r="2"><{p}c r="A2"><{p}v>2</{p}v></{p}c>'
        f'<{p}c r="B2"><{p}f t="shared" si="0"/><{p}v>4</{p}v></{p}c></{p}row>'
        f'<{p}row r="3"><{p}c r="A3" s="2"><{p}v>3</{p}v></{p}c>'
        f'<{p}c r="B3"><{p}f t="shared" si="0"/><{p}v>6</{p}v></{p}c></{p}row>'
    )


def build_xlsx(prefix: str = "") -> bytes:
    """Build a small workbook exercising features the writer must not drop."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr(
            "_rels/.rels",
            f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{NS_PKG}">'
            f'<Relationship Id="rId1" Type="{REL}/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        z.writestr("xl/workbook.xml", _workbook_xml(prefix))
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{NS_PKG}">'
            f'<Relationship Id="rIdData" Type="{REL}/worksheet" Target="worksheets/data.xml"/>'
            f'<Relationship Id="rIdSecret" Type="{REL}/worksheet" Target="worksheets/secret.xml"/>'
            f'<Relationship Id="rIdStyles" Type="{REL}/styles" Target="styles.xml"/>'
            "</Relationships>",
        )
        z.writestr("xl/worksheets/data.xml", _sheet_xml(prefix, _shared_formula_rows(prefix)))
        z.writestr("xl/worksheets/secret.xml", _sheet_xml(prefix))
        z.writestr("xl/styles.xml", STYLES)
    return buf.getvalue()


def _parts(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


def _dirty_roundtrip(data: bytes) -> tuple[bytes, object]:
    wb = read_xlsx(data)
    wb.dirty = True
    for s in wb.sheets:
        s.dirty = True
    return write_xlsx(wb), wb


def test_root_rels_resolve_to_package_root() -> None:
    with zipfile.ZipFile(io.BytesIO(build_xlsx())) as z:
        rels = _parse_rels(z, "_rels/.rels")
    assert rels["rId1"] == ("officeDocument", "xl/workbook.xml")


def test_shared_formulas_are_expanded_on_read() -> None:
    wb = read_xlsx(build_xlsx())
    sheet = wb[0]
    assert sheet.get_cell(0, 1).formula == "A1*2"
    assert sheet.get_cell(1, 1).formula == "A2*2"
    assert sheet.get_cell(2, 1).formula == "A3*2"


def test_shared_formulas_survive_dirty_save() -> None:
    out, _ = _dirty_roundtrip(build_xlsx())
    again = read_xlsx(out)
    assert [again[0].get_cell(r, 1).formula for r in range(3)] == ["A1*2", "A2*2", "A3*2"]


def test_corpus_shared_formulas_survive_dirty_save() -> None:
    path = CORPUS / "openxml-sdk__NoExtDataB1.xlsx"
    if not path.exists():
        pytest.skip("corpus file missing")
    src = path.read_bytes()
    before = sum(len([c for c in s.cells.values() if c.formula]) for s in read_xlsx(src).sheets)
    out, _ = _dirty_roundtrip(src)
    after = sum(len([c for c in s.cells.values() if c.formula]) for s in read_xlsx(out).sheets)
    assert before > 3000
    assert after == before


@pytest.mark.parametrize("prefix", ["", "x"])
def test_hidden_sheet_state_and_ids_survive_save(prefix: str) -> None:
    out, _ = _dirty_roundtrip(build_xlsx(prefix))
    wb_xml = _parts(out)["xl/workbook.xml"].decode()
    assert 'state="hidden"' in wb_xml
    assert 'sheetId="7"' in wb_xml and 'sheetId="3"' in wb_xml


@pytest.mark.parametrize("prefix", ["", "x"])
def test_workbook_calcpr_and_extlst_survive_save(prefix: str) -> None:
    out, _ = _dirty_roundtrip(build_xlsx(prefix))
    wb_xml = _parts(out)["xl/workbook.xml"].decode()
    assert 'iterateCount="50"' in wb_xml
    assert "chartTrackingRefBase" in wb_xml


def test_clean_save_keeps_workbook_xml_bytes() -> None:
    src = build_xlsx()
    out = write_xlsx(read_xlsx(src))
    assert _parts(out)["xl/workbook.xml"] == _parts(src)["xl/workbook.xml"]


def test_no_dangling_shared_strings_relationship() -> None:
    out, _ = _dirty_roundtrip(build_xlsx())
    parts = _parts(out)
    rels = parts["xl/_rels/workbook.xml.rels"].decode()
    if "sharedStrings" in rels:
        assert "xl/sharedStrings.xml" in parts
    for name in parts:
        assert not name.endswith("worksheets/sheet1.xml") or "sheet1.xml" in rels


def test_sheet_part_names_are_preserved() -> None:
    out, _ = _dirty_roundtrip(build_xlsx())
    parts = _parts(out)
    assert "xl/worksheets/data.xml" in parts
    assert "xl/worksheets/secret.xml" in parts
    assert "xl/worksheets/sheet1.xml" not in parts


@pytest.mark.parametrize("prefix", ["", "x"])
def test_dirty_save_applies_edits_with_prefixed_markup(prefix: str) -> None:
    wb = read_xlsx(build_xlsx(prefix))
    wb[0].set_cell(0, 0, CellData(value=42))
    wb[0].dirty = True
    wb.dirty = True
    again = read_xlsx(write_xlsx(wb))
    assert again[0].get_cell(0, 0).value == 42
    assert again[0].get_cell(2, 1).formula == "A3*2"


def test_dirty_save_keeps_original_styles() -> None:
    out, _ = _dirty_roundtrip(build_xlsx())
    styles = _parts(out)["xl/styles.xml"].decode()
    # Named cell style, the CF differential format and the custom number format all survive.
    assert "MyHeading" in styles
    assert "FF9C0006" in styles
    assert 'formatCode="0.000"' in styles
    again = read_xlsx(out)
    assert again[0].get_cell(0, 1).bold is True
    assert again[0].get_cell(2, 0).format_code == "0.000"


def test_new_formatting_on_dirty_save_gets_a_fresh_style() -> None:
    wb = read_xlsx(build_xlsx())
    cell = CellData(value="x", italic=True, font_size=14)
    wb[0].set_cell(5, 5, cell)
    wb.dirty = True
    again = read_xlsx(write_xlsx(wb))
    got = again[0].get_cell(5, 5)
    assert got.italic is True and got.font_size == 14
    # Existing styles are untouched
    assert again[0].get_cell(0, 1).bold is True
