"""Tests for Ledger bidirectional text spill, merged cell blocks, and line breaks."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport


def _render_to_image(viewport: GridViewport) -> QImage:
    img = QImage(viewport.viewport().size(), QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    try:
        viewport._render_paint_event(painter, None)
    finally:
        if painter.isActive():
            painter.end()
    return img


def _has_dark_pixel(img: QImage, x1: int, y1: int, x2: int, y2: int) -> bool:
    for py in range(max(0, y1), min(img.height(), y2)):
        for px in range(max(0, x1), min(img.width(), x2)):
            c = img.pixelColor(px, py)
            if c.red() < 110 and c.green() < 110 and c.blue() < 110:
                return True
    return False


def _has_light_pixel(img: QImage, x1: int, y1: int, x2: int, y2: int) -> bool:
    for py in range(max(0, y1), min(img.height(), y2)):
        for px in range(max(0, x1), min(img.width(), x2)):
            c = img.pixelColor(px, py)
            if c.red() > 220 and c.green() > 220 and c.blue() > 220:
                return True
    return False


def _count_dark_rows(img: QImage, x1: int, y1: int, x2: int, y2: int) -> int:
    rows = 0
    for py in range(max(0, y1), min(img.height(), y2)):
        if _has_dark_pixel(img, x1, py, x2, py + 1):
            rows += 1
    return rows


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


def test_render_right_aligned_spill_c5_into_b5(qtbot):
    """Right-aligned text in C5 paints across styled-empty neighbor B5."""
    sheet = SheetDataModel("RightSpillRender")
    for c in range(4):
        sheet.geometry.set_col_width(c, 55)
    # B5 has a style (white fill) but no value — must NOT overwrite C5's spill
    sheet.set_cell(4, 1, CellData(value=None, bg_color="#FFFFFF"))
    sheet.set_cell(4, 2, CellData(value="Long Right Label", align_h="right"))

    viewport = GridViewport(model=sheet)
    viewport.resize(400, 250)
    qtbot.addWidget(viewport)

    img = _render_to_image(viewport)
    b5 = viewport.cell_rect(4, 1)
    assert _has_dark_pixel(img, b5.left() + 4, b5.top() + 2, b5.right() - 2, b5.bottom() - 2)


def test_render_center_aligned_spill_both_sides(qtbot):
    """Centered text in C5 spills into both B5 and D5, and stops at occupied E5."""
    sheet = SheetDataModel("CenterSpillRender")
    for c in range(6):
        sheet.geometry.set_col_width(c, 50)
    sheet.set_cell(4, 2, CellData(value="Very Long Centered Title", align_h="center"))
    sheet.set_cell(4, 4, CellData(value="STOP"))

    viewport = GridViewport(model=sheet)
    viewport.resize(450, 250)
    qtbot.addWidget(viewport)

    img = _render_to_image(viewport)
    b5 = viewport.cell_rect(4, 1)
    d5 = viewport.cell_rect(4, 3)
    assert _has_dark_pixel(img, b5.left() + 4, b5.top() + 2, b5.right() - 2, b5.bottom() - 2)
    assert _has_dark_pixel(img, d5.left() + 2, d5.top() + 2, d5.right() - 4, d5.bottom() - 2)


def test_render_offscreen_spill_left_and_right(qtbot):
    """Spill from cells outside the visible viewport still paints inside visible neighbors."""
    sheet = SheetDataModel("OffscreenSpill")
    for c in range(10):
        sheet.geometry.set_col_width(c, 60)
    sheet.set_cell(0, 0, CellData(value="Offscreen Left Text Spilling Right", align_h="left"))
    sheet.set_cell(1, 5, CellData(value="Offscreen Right Text Spilling Left", align_h="right"))

    viewport = GridViewport(model=sheet)
    viewport.resize(300, 200)
    qtbot.addWidget(viewport)
    viewport._update_scrollbars()
    # Scroll horizontally past col 0 so col 0 is offscreen left and col 5 is offscreen right
    viewport.horizontalScrollBar().setValue(70)  # hides col 0 (0..60), visible cols 1..4 (~254px)

    img = _render_to_image(viewport)
    b1 = viewport.cell_rect(0, 1)
    d2 = viewport.cell_rect(1, 3)
    assert _has_dark_pixel(img, max(viewport.row_header_width, b1.left() + 2), b1.top() + 2, b1.right() - 2, b1.bottom() - 2)
    assert _has_dark_pixel(img, d2.left() + 2, d2.top() + 2, d2.right() - 2, d2.bottom() - 2)


def test_render_unfilled_merge_erases_internal_gridlines(qtbot):
    """Unfilled merged region suppresses internal gridlines while keeping outer gridlines."""
    sheet = SheetDataModel("MergeGrid")
    sheet.set_cell(0, 0, CellData(value="Merged"))
    sheet.add_merge(0, 0, 1, 2)

    viewport = GridViewport(model=sheet)
    viewport.resize(400, 200)
    qtbot.addWidget(viewport)

    img = _render_to_image(viewport)
    c00 = viewport.cell_rect(0, 0)
    c01 = viewport.cell_rect(0, 1)
    c11 = viewport.cell_rect(1, 1)
    # Internal vertical gridline between col 0 and col 1 at row 1 (c11.left()) must be white
    mid_y = c11.top() + c11.height() // 2
    assert img.pixelColor(c11.left(), mid_y) == QColor(Qt.GlobalColor.white)
    # Internal horizontal gridline between row 0 and row 1 at col 1 (c11.top()) must be white
    mid_x = c01.left() + c01.width() // 2
    assert img.pixelColor(mid_x, c11.top()) == QColor(Qt.GlobalColor.white)
    # Outer right gridline of merge (c02.right() + 1) must still be gridline color (non-white)
    c02 = viewport.cell_rect(0, 2)
    assert img.pixelColor(c02.right() + 1, mid_y) != QColor(Qt.GlobalColor.white)


def test_render_poi_45540_a3_and_k1_o1_merged_blocks(qtbot):
    """Acceptance 1 & 2: A3 paints full sentence; K1:O1 paints gray fill and both white title lines."""
    wb = read_xlsx("tests/docs/excel/xlsx/poi__45540_form_Header.xlsx")
    sh = wb.sheets[0]
    viewport = GridViewport(model=sh)
    viewport.resize(1178, 798)
    qtbot.addWidget(viewport)

    img = _render_to_image(viewport)

    # 1. A3 (row 2) merged A3:O3 — full sentence reaches across cols 8..11
    a3_right = viewport.cell_rect(2, 9)
    assert _has_dark_pixel(
        img, a3_right.left() + 2, a3_right.top() + 2, a3_right.right() - 2, a3_right.bottom() - 2
    )

    # 2. K1:O1 (row 0, cols 10..14) — gray #808080 background and white wrapped 2-line title
    k1 = viewport.cell_rect(0, 10)
    o1 = viewport.cell_rect(0, 14)
    # Background pixel inside K1:O1 corner is gray (#808080)
    bg_px = img.pixelColor(k1.left() + 4, k1.top() + 4)
    assert (bg_px.red(), bg_px.green(), bg_px.blue()) == (128, 128, 128)
    # Top half ("China Expatriate Programme") and bottom half ("APPLICATION FORM") both have white ink
    mid_y = k1.top() + k1.height() // 2
    assert _has_light_pixel(img, k1.left() + 10, k1.top() + 4, o1.right() - 10, mid_y)
    assert _has_light_pixel(img, k1.left() + 10, mid_y, o1.right() - 10, k1.bottom() - 4)


def test_render_totals_row_function_b1_unclipped(qtbot):
    """libreoffice__totalsRowFunction.xlsx B1 ('PRESENT PLANNER') spills cleanly across C1."""
    wb = read_xlsx("tests/docs/excel/xlsx/libreoffice__totalsRowFunction.xlsx")
    sh = wb.sheets[0]
    viewport = GridViewport(model=sh)
    viewport.resize(1178, 798)
    qtbot.addWidget(viewport)

    img = _render_to_image(viewport)
    c1 = viewport.cell_rect(0, 2)
    # C1 background is #1594A0 and B1 white text ("PLANNER") spills into C1
    assert _has_light_pixel(img, c1.left() + 4, c1.top() + 4, c1.left() + 90, c1.bottom() - 4)


def test_render_tdf169326_b2_single_line(qtbot):
    """Acceptance 3: libreoffice__tdf169326...xlsx B2 paints 'Hello World' on ONE line."""
    wb = read_xlsx(
        "tests/docs/excel/xlsx/libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx"
    )
    sh = wb.sheets[0]
    viewport = GridViewport(model=sh)
    viewport.resize(600, 300)
    qtbot.addWidget(viewport)

    img = _render_to_image(viewport)
    b2 = viewport.cell_rect(1, 1)
    # All dark ink in B2 must stay within one single line band (<= 16px tall)
    dark_rows = _count_dark_rows(img, b2.left() + 2, b2.top() + 1, b2.right() - 2, b2.bottom() - 1)
    assert 4 <= dark_rows <= 16
    # "Hello World" on one line is wider than "Hello" (~28px) -> ink appears beyond x + 42
    assert _has_dark_pixel(img, b2.left() + 42, b2.top() + 2, b2.right() - 2, b2.bottom() - 2)
