"""GUI tests verifying spreadsheet grid viewport alignment rendering and editor behavior."""

import datetime

from PySide6.QtCore import Qt

from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.views.editor_controller import EditorController
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport


def test_grid_viewport_rendering_alignment(qtbot):
    """Test that GridViewport paints without error with various cell alignments."""
    sheet = SheetDataModel("AlignmentSheet")
    sheet.set_cell(0, 0, CellData(value=-2012, align_h="general"))
    sheet.set_cell(0, 1, CellData(value=3.1415, align_h="general"))
    sheet.set_cell(0, 2, CellData(value="Hello World", align_h="general"))
    sheet.set_cell(0, 3, CellData(value=True, align_h="general"))
    sheet.set_cell(0, 4, CellData(value="#DIV/0!", align_h="general"))
    sheet.set_cell(0, 5, CellData(value=datetime.date(2026, 11, 7), align_h="general"))
    # Explicit alignments
    sheet.set_cell(1, 0, CellData(value=999, align_h="left"))
    sheet.set_cell(1, 1, CellData(value="Center Text", align_h="center"))
    sheet.set_cell(1, 2, CellData(value="Right Text", align_h="right"))

    viewport = GridViewport(model=sheet)
    viewport.resize(800, 600)
    viewport.show()
    qtbot.addWidget(viewport)
    qtbot.waitExposed(viewport)

    # Force a repaint to execute paintEvent with all alignments
    viewport.viewport().repaint()

    # Verify editor controller receives correct alignment when editing different cells
    editor_ctrl = EditorController(viewport, sheet, viewport.selection)

    # Edit number cell (0, 0) -> editor should be right-aligned
    editor_ctrl.begin_edit(0, 0, initial_text="-2012")
    assert editor_ctrl.in_cell_editor.alignment() == Qt.AlignmentFlag.AlignRight
    editor_ctrl.cancel()

    # Edit text cell (0, 2) -> editor should be left-aligned
    editor_ctrl.begin_edit(0, 2, initial_text="Hello World")
    assert editor_ctrl.in_cell_editor.alignment() == Qt.AlignmentFlag.AlignLeft
    editor_ctrl.cancel()

    # Edit boolean cell (0, 3) -> editor should be center-aligned
    editor_ctrl.begin_edit(0, 3, initial_text="TRUE")
    assert editor_ctrl.in_cell_editor.alignment() == Qt.AlignmentFlag.AlignCenter
    editor_ctrl.cancel()

    # Edit explicitly left-aligned number (1, 0) -> editor should be left-aligned
    editor_ctrl.begin_edit(1, 0, initial_text="999")
    assert editor_ctrl.in_cell_editor.alignment() == Qt.AlignmentFlag.AlignLeft
    editor_ctrl.cancel()


def test_numeric_no_overflow_span(qtbot):
    """Verify that numbers and right-aligned cells do not calculate overflow into neighbors."""
    sheet = SheetDataModel("OverflowSheet")
    # Narrow column 0
    sheet.geometry.set_col_width(0, 20)
    sheet.geometry.set_col_width(1, 50)
    sheet.geometry.set_col_width(2, 50)

    viewport = GridViewport(model=sheet)

    # A large number in narrow column
    sheet.set_cell(0, 0, CellData(value=123456789, align_h="general"))
    # Left-aligned text in narrow column
    sheet.set_cell(1, 0, CellData(value="A very long text label", align_h="left"))

    # For left-aligned text, calculate_overflow_span will allow spanning into empty columns
    text_w = 120
    span_text = viewport.calculate_overflow_span(1, 0, text_w, 20)
    assert span_text > 1


def _region_has_dark_pixel(img, x1: int, y1: int, x2: int, y2: int) -> bool:
    for py in range(max(0, y1), min(img.height(), y2)):
        for px in range(max(0, x1), min(img.width(), x2)):
            c = img.pixelColor(px, py)
            if c.red() < 120 and c.green() < 120 and c.blue() < 120:
                return True
    return False


def test_accounting_fill_alignment_b3_totals_row_shown(qtbot):
    """Verify B3 in libreoffice__totalsRowShown.xlsx paints '$' at left pad and '1.00' at right pad."""
    from PySide6.QtGui import QFont, QFontMetricsF, QImage, QPainter

    from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx

    book = read_xlsx("tests/docs/excel/xlsx/libreoffice__totalsRowShown.xlsx")
    sheet = book.sheets[0]
    viewport = GridViewport(model=sheet)
    viewport.resize(600, 300)
    qtbot.addWidget(viewport)

    # Check formatter helper directly
    b3_cell = sheet.get_cell(2, 1)
    assert b3_cell is not None
    b3_font = QFont(b3_cell.font_family, b3_cell.font_size)
    b3_fm = QFontMetricsF(b3_font)
    b3_w = sheet.geometry.col_size(1)
    res = viewport._format_cell_for_paint(b3_cell, b3_cell.get_display_value(), b3_fm, b3_w)
    assert res.has_fill is True
    assert res.fill_pos is not None
    assert "$" in res.text[: res.fill_pos]
    assert "1.00" in res.text[res.fill_pos :]
    for ch in ("_", "*", "("):
        assert ch not in res.text

    # Render viewport to QImage and verify pixel placement inside B3
    img = QImage(viewport.viewport().size(), QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    viewport._render_paint_event(painter, None)
    painter.end()

    rect = viewport.cell_rect(2, 1)
    # Left zone (~x+4..x+20) should have dark '$' pixels
    assert _region_has_dark_pixel(img, rect.left() + 3, rect.top() + 2, rect.left() + 22, rect.bottom() - 1)
    # Middle fill zone (~x+30..x+60) should be blank white (no dark text pixels)
    assert not _region_has_dark_pixel(img, rect.left() + 30, rect.top() + 2, rect.right() - 32, rect.bottom() - 2)
    # Right zone (~right-28..right-2) should have dark '1.00' pixels
    assert _region_has_dark_pixel(img, rect.right() - 30, rect.top() + 2, rect.right() - 2, rect.bottom() - 1)


def test_general_rounding_poi_60509_e3(qtbot):
    """Verify E3 in poi__60509.xlsx displays '5715.046' at its stored column width without clipping."""
    from PySide6.QtGui import QFont, QFontMetricsF

    from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx

    book = read_xlsx("tests/docs/excel/xlsx/poi__60509.xlsx")
    sheet = book.sheets[0]
    viewport = GridViewport(model=sheet)
    viewport.resize(800, 300)
    qtbot.addWidget(viewport)

    e3_cell = sheet.get_cell(2, 4)
    assert e3_cell is not None
    col_w = sheet.geometry.col_size(4)
    e3_font = QFont(e3_cell.font_family, e3_cell.font_size)
    e3_fm = QFontMetricsF(e3_font)

    res = viewport._format_cell_for_paint(e3_cell, e3_cell.get_display_value(), e3_fm, col_w)
    assert res.text == "5715.046"
    assert e3_fm.horizontalAdvance(res.text) <= col_w - 6


def test_narrow_column_renders_hashes(qtbot):
    """Verify numeric cells in too-narrow columns render '####' instead of clipping digits."""
    from PySide6.QtGui import QFont, QFontMetricsF

    sheet = SheetDataModel("NarrowSheet")
    sheet.geometry.set_col_width(0, 24)
    sheet.set_cell(0, 0, CellData(value=12345.67, format_code="#,##0.00"))
    sheet.set_cell(1, 0, CellData(value=123456, format_code="General"))

    viewport = GridViewport(model=sheet)
    qtbot.addWidget(viewport)

    for r in (0, 1):
        cell = sheet.get_cell(r, 0)
        assert cell is not None
        fm = QFontMetricsF(QFont(cell.font_family, cell.font_size))
        res = viewport._format_cell_for_paint(cell, cell.get_display_value(), fm, 24)
        assert res.text.startswith("#")
        assert set(res.text) == {"#"}
        assert fm.horizontalAdvance(res.text) <= 24 - 6
