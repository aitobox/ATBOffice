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
