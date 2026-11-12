"""Tests for Ledger bidirectional text spill, merged cell blocks, and line breaks."""

from __future__ import annotations

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport


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


def test_spill_bounds_right_aligned_c5_into_b5(qtbot):
    """Right-aligned text in C5 must spill leftward into empty B5 (and A5 if needed)."""
    sheet = SheetDataModel("RightSpill")
    sheet.geometry.set_col_width(0, 64)
    sheet.geometry.set_col_width(1, 64)
    sheet.geometry.set_col_width(2, 64)
    sheet.set_cell(4, 2, CellData(value="Right-aligned long label", align_h="right"))
    viewport = GridViewport(model=sheet)
    qtbot.addWidget(viewport)

    left_c, right_c = viewport.calculate_spill_bounds(4, 2, 110, 64, "right")
    assert left_c == 1
    assert right_c == 2


def test_spill_bounds_center_aligned_both_ways(qtbot):
    """Centered text in C5 spills symmetrically into both B5 and D5."""
    sheet = SheetDataModel("CenterSpill")
    for c in range(5):
        sheet.geometry.set_col_width(c, 64)
    sheet.set_cell(4, 2, CellData(value="Centered very long heading", align_h="center"))
    viewport = GridViewport(model=sheet)
    qtbot.addWidget(viewport)

    left_c, right_c = viewport.calculate_spill_bounds(4, 2, 150, 64, "center")
    assert left_c == 1
    assert right_c == 3


def test_spill_allows_styled_empty_but_stops_at_merge_and_value(qtbot):
    """Styled cells with no value allow spill; merged cells and valued cells block spill."""
    sheet = SheetDataModel("SpillStop")
    for c in range(6):
        sheet.geometry.set_col_width(c, 50)
    sheet.set_cell(0, 0, CellData(value="Very long left text", align_h="left"))
    # (0, 1) has background fill & font, but value=None -> empty for spill
    sheet.set_cell(0, 1, CellData(value=None, bg_color="#FFFFFF", bold=True))
    # (0, 2) is part of a merged range -> blocks spill
    sheet.add_merge(0, 2, 0, 3)

    viewport = GridViewport(model=sheet)
    qtbot.addWidget(viewport)

    left_c, right_c = viewport.calculate_spill_bounds(0, 0, 220, 50, "left")
    assert left_c == 0
    assert right_c == 1
    assert viewport.calculate_overflow_span(0, 0, 220, 50) == 2

    # Occupied cell at (1, 1) also stops spill
    sheet.set_cell(1, 0, CellData(value="Very long left text", align_h="left"))
    sheet.set_cell(1, 1, CellData(value="X"))
    assert viewport.calculate_spill_bounds(1, 0, 220, 50, "left") == (0, 0)
