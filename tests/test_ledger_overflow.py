"""Tests for Ledger bidirectional text spill, merged cell blocks, and line breaks."""

from __future__ import annotations

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx


def test_tdf169326_b2_inherits_default_workbook_font():
    """Verify B2 inherits workbook cellXfs[0] font (Calibri 11) when cell s is omitted."""
    wb = read_xlsx(
        "tests/docs/excel/xlsx/libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx"
    )
    sh = wb.sheets[0]
    a1 = sh.get_cell(0, 0)
    b2 = sh.get_cell(1, 1)
    assert a1 is not None and b2 is not None
    assert b2.font_family == "Calibri"
    assert b2.font_size == 11
    assert b2.wrap_text is False
