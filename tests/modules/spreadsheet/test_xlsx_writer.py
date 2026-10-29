"""Unit tests for pure Python XLSX writer (xlsx_writer.py)."""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
    FormatDelta,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.vfs.opc import SourcePackage


def test_write_xlsx_basic_values():
    """Verify writing basic values (strings, numbers, booleans) and reading them back."""
    wb = WorkbookModel()
    sheet = wb.active_sheet
    sheet.name = "Data"

    sheet.set_cell(0, 0, CellData(value="Hello World"))
    sheet.set_cell(0, 1, CellData(value=123))
    sheet.set_cell(1, 0, CellData(value=45.67))
    sheet.set_cell(1, 1, CellData(value=True))
    sheet.set_cell(2, 0, CellData(value=False))

    raw_bytes = write_xlsx(wb)
    assert isinstance(raw_bytes, bytes)
    assert len(raw_bytes) > 0

    # Verify zip structure
    with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as z:
        names = z.namelist()
        assert "[Content_Types].xml" in names
        assert "_rels/.rels" in names
        assert "xl/workbook.xml" in names
        assert "xl/_rels/workbook.xml.rels" in names
        assert "xl/styles.xml" in names
        assert "xl/sharedStrings.xml" in names
        assert "xl/worksheets/sheet1.xml" in names

    # Read back with read_xlsx
    loaded_wb = read_xlsx(raw_bytes)
    assert len(loaded_wb) == 1
    loaded_sheet = loaded_wb[0]
    assert loaded_sheet.name == "Data"

    c00 = loaded_sheet.get_cell(0, 0)
    assert c00 is not None and c00.value == "Hello World"

    c01 = loaded_sheet.get_cell(0, 1)
    assert c01 is not None and c01.value == 123

    c10 = loaded_sheet.get_cell(1, 0)
    assert c10 is not None and abs(c10.value - 45.67) < 1e-5

    c11 = loaded_sheet.get_cell(1, 1)
    assert c11 is not None and c11.value is True

    c20 = loaded_sheet.get_cell(2, 0)
    assert c20 is not None and c20.value is False


def test_write_xlsx_multi_sheet_and_active_tab():
    """Verify multiple worksheets and active tab selection."""
    wb = WorkbookModel()
    wb.rename_sheet(0, "Summary")
    sheet2 = wb.add_sheet(name="Details")
    sheet3 = wb.add_sheet(name="Archive")

    sheet2.set_cell(0, 0, CellData(value="Detailed report"))
    sheet3.set_cell(5, 5, CellData(value=999))

    # Set active sheet to "Details" (index 1)
    wb.set_active_sheet_index(1)

    raw_bytes = write_xlsx(wb)
    loaded_wb = read_xlsx(raw_bytes)

    assert len(loaded_wb) == 3
    assert [s.name for s in loaded_wb.sheets] == ["Summary", "Details", "Archive"]
    assert loaded_wb.active_sheet_index == 1

    c00 = loaded_wb[1].get_cell(0, 0)
    assert c00 is not None and c00.value == "Detailed report"

    c55 = loaded_wb[2].get_cell(5, 5)
    assert c55 is not None and c55.value == 999


def test_write_xlsx_formulas():
    """Verify formulas with cached values and leading = handling."""
    wb = WorkbookModel()
    sheet = wb.active_sheet

    sheet.set_cell(0, 0, CellData(value=10))
    sheet.set_cell(1, 0, CellData(value=20))
    # Formula without leading '='
    sheet.set_cell(2, 0, CellData(value=30, formula="SUM(A1:A2)"))
    # Formula with leading '='
    sheet.set_cell(3, 0, CellData(value=200, formula="=A1*A2"))

    raw_bytes = write_xlsx(wb)
    loaded_wb = read_xlsx(raw_bytes)
    loaded_sheet = loaded_wb[0]

    f_cell = loaded_sheet.get_cell(2, 0)
    assert f_cell is not None
    assert f_cell.formula == "SUM(A1:A2)"
    assert f_cell.value == 30

    f_cell2 = loaded_sheet.get_cell(3, 0)
    assert f_cell2 is not None
    assert f_cell2.formula in ("A1*A2", "=A1*A2")
    assert f_cell2.value == 200


def test_write_xlsx_cell_formatting():
    """Verify fonts, colors, fills, borders, alignments, and number formats."""
    wb = WorkbookModel()
    sheet = wb.active_sheet

    # Styled cell
    cell = CellData(
        value="Formatted Text",
        bold=True,
        italic=True,
        underline=True,
        strike=True,
        font_family="Calibri",
        font_size=14,
        fg_color="FF0000",
        bg_color="FFFF00",
        align_h="center",
        align_v="center",
        wrap_text=True,
        format_code="#,##0.00",
        border_top=BorderStyle(style="thin", color="000000"),
        border_bottom=BorderStyle(style="double", color="FF0000"),
        border_left=BorderStyle(style="thick", color="00FF00"),
        border_right=BorderStyle(style="dashed", color="0000FF"),
    )
    sheet.set_cell(0, 0, cell)

    raw_bytes = write_xlsx(wb)
    loaded_wb = read_xlsx(raw_bytes)
    c = loaded_wb[0].get_cell(0, 0)

    assert c is not None
    assert c.value == "Formatted Text"
    assert c.bold is True
    assert c.italic is True
    assert c.underline is True
    assert c.strike is True
    assert c.font_family == "Calibri"
    assert c.font_size == 14
    assert c.fg_color in ("FF0000", "FFFF0000")
    assert c.bg_color in ("FFFF00", "FFFFFF00")
    assert c.align_h == "center"
    assert c.align_v == "center"
    assert c.wrap_text is True
    assert c.format_code == "#,##0.00"
    assert c.border_top is not None and c.border_top.style == "thin"
    assert c.border_bottom is not None and c.border_bottom.style == "double"
    assert c.border_left is not None and c.border_left.style == "thick"
    assert c.border_right is not None and c.border_right.style == "dashed"


def test_write_xlsx_merged_cells():
    """Verify merged cell regions persistence."""
    wb = WorkbookModel()
    sheet = wb.active_sheet
    sheet.set_cell(1, 1, CellData(value="Merged Region"))
    sheet.add_merge(1, 1, 3, 4)  # B2:E4

    raw_bytes = write_xlsx(wb)
    loaded_wb = read_xlsx(raw_bytes)
    loaded_sheet = loaded_wb[0]

    assert len(loaded_sheet.merges) == 1
    m = loaded_sheet.merges[0]
    assert m == (1, 1, 3, 4)
    assert loaded_sheet.is_merged(2, 2) is True
    assert loaded_sheet.is_merged(0, 0) is False


def test_write_xlsx_column_widths_and_row_heights():
    """Verify custom column widths and row heights persistence."""
    wb = WorkbookModel()
    sheet = wb.active_sheet
    sheet.geometry.set_col_width(1, 120)  # Column B
    sheet.geometry.set_row_height(3, 45)  # Row 4

    sheet.set_cell(3, 1, CellData(value="Custom Sized"))

    raw_bytes = write_xlsx(wb)
    loaded_wb = read_xlsx(raw_bytes)
    loaded_sheet = loaded_wb[0]

    assert loaded_sheet.geometry.col_size(1) == 120
    assert loaded_sheet.geometry.row_size(3) == 45


def test_write_xlsx_whitespace_and_special_characters():
    """Verify XML escaping and whitespace preservation."""
    wb = WorkbookModel()
    sheet = wb.active_sheet

    special_str = " <Leading space & <xml> tags> \n"
    sheet.set_cell(0, 0, CellData(value=special_str))
    sheet.set_cell(0, 1, CellData(value="Normal"))

    raw_bytes = write_xlsx(wb)
    loaded_wb = read_xlsx(raw_bytes)
    c = loaded_wb[0].get_cell(0, 0)

    assert c is not None
    assert c.value == special_str


def test_write_xlsx_output_path_and_stream():
    """Verify writing to filesystem path (str/Path) and binary stream."""
    wb = WorkbookModel()
    wb.active_sheet.set_cell(0, 0, CellData(value="Disk Test"))

    # 1. Test io.BytesIO stream
    buf = io.BytesIO()
    res_bytes = write_xlsx(wb, output_path=buf)
    assert len(buf.getvalue()) > 0
    assert res_bytes == buf.getvalue()

    # 2. Test Path / file write
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test_out.xlsx"
        write_xlsx(wb, output_path=file_path)
        assert file_path.exists()
        loaded = read_xlsx(file_path)
        assert loaded[0].get_cell(0, 0).value == "Disk Test"


def test_write_xlsx_source_opc_carry():
    """Verify part-level carry when source_opc is provided."""
    # First, construct a base package with an extra custom part
    wb = WorkbookModel()
    wb.active_sheet.set_cell(0, 0, CellData(value="Initial"))
    base_bytes = write_xlsx(wb)

    # Inject a custom part into this zip archive (simulating VBA or custom XML)
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base_bytes), "r") as zin:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                zout.writestr(item.filename, zin.read(item.filename))
            zout.writestr("custom/data.bin", b"UNMODIFIED_CUSTOM_PAYLOAD_12345")

    enriched_bytes = buf.getvalue()
    source_pkg = SourcePackage.from_bytes(enriched_bytes)

    # Modify the workbook and write out with source_opc
    wb.active_sheet.set_cell(0, 0, CellData(value="Modified"))
    out_bytes = write_xlsx(wb, source_opc=source_pkg)

    # Check that custom/data.bin was preserved byte-for-byte
    with zipfile.ZipFile(io.BytesIO(out_bytes), "r") as z:
        names = z.namelist()
        assert "custom/data.bin" in names
        assert z.read("custom/data.bin") == b"UNMODIFIED_CUSTOM_PAYLOAD_12345"

    loaded = read_xlsx(out_bytes)
    assert loaded[0].get_cell(0, 0).value == "Modified"
