"""Tests for AutoFill sequence extrapolation engine and fill handle GUI interactions."""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.views.autofill import AutoFillEngine
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport, HitZone


# -----------------------------------------------------------------------------
# Unit Tests for AutoFillEngine
# -----------------------------------------------------------------------------
def test_autofill_single_number_no_ctrl():
    """Single numeric cell without Ctrl should duplicate (copy) the value."""
    model = SheetDataModel()
    model.set_cell(0, 0, CellData(value=42))

    src = SelectionRange(0, 0, 0, 0)
    dest = SelectionRange(0, 0, 3, 0)  # Down 3 rows
    AutoFillEngine.auto_fill(model, src, dest, mode="auto", ctrl_pressed=False)

    for r in range(4):
        assert model.get_cell_value(r, 0) == 42


def test_autofill_single_number_with_ctrl():
    """Single numeric cell with Ctrl should increment by 1."""
    model = SheetDataModel()
    model.set_cell(0, 0, CellData(value=10))

    src = SelectionRange(0, 0, 0, 0)
    dest = SelectionRange(0, 0, 4, 0)  # Down 4 rows
    AutoFillEngine.auto_fill(model, src, dest, mode="auto", ctrl_pressed=True)

    assert [model.get_cell_value(r, 0) for r in range(5)] == [10, 11, 12, 13, 14]


def test_autofill_multiple_numbers_linear_trend():
    """Multiple numeric cells should automatically compute linear trend step."""
    model = SheetDataModel()
    model.set_cell(0, 0, CellData(value=5))
    model.set_cell(1, 0, CellData(value=10))

    src = SelectionRange(0, 0, 1, 0)
    dest = SelectionRange(0, 0, 4, 0)
    AutoFillEngine.auto_fill(model, src, dest, mode="auto", ctrl_pressed=False)

    assert [model.get_cell_value(r, 0) for r in range(5)] == [5, 10, 15, 20, 25]


def test_autofill_horizontal_and_reverse_directions():
    """AutoFill should support rightward, upward, and leftward fills."""
    # Rightward fill
    model = SheetDataModel()
    model.set_cell(0, 0, CellData(value=1))
    model.set_cell(0, 1, CellData(value=2))
    AutoFillEngine.auto_fill(
        model, SelectionRange(0, 0, 0, 1), SelectionRange(0, 0, 0, 4)
    )
    assert [model.get_cell_value(0, c) for c in range(5)] == [1, 2, 3, 4, 5]

    # Upward fill (reverse vertical)
    model2 = SheetDataModel()
    model2.set_cell(3, 0, CellData(value=40))
    model2.set_cell(4, 0, CellData(value=50))
    AutoFillEngine.auto_fill(
        model2, SelectionRange(3, 0, 4, 0), SelectionRange(0, 0, 4, 0)
    )
    assert [model2.get_cell_value(r, 0) for r in range(5)] == [
        10,
        20,
        30,
        40,
        50,
    ]

    # Leftward fill (reverse horizontal)
    model3 = SheetDataModel()
    model3.set_cell(0, 3, CellData(value=4))
    model3.set_cell(0, 4, CellData(value=5))
    AutoFillEngine.auto_fill(
        model3, SelectionRange(0, 3, 0, 4), SelectionRange(0, 0, 0, 4)
    )
    assert [model3.get_cell_value(0, c) for c in range(5)] == [1, 2, 3, 4, 5]


def test_autofill_text_with_numbers():
    """Numbered text like 'Item 1' or 'Q01' should increment maintaining zero-padding."""
    model = SheetDataModel()
    model.set_cell(0, 0, CellData(value="Item 1"))
    AutoFillEngine.auto_fill(
        model, SelectionRange(0, 0, 0, 0), SelectionRange(0, 0, 2, 0)
    )
    assert [model.get_cell_value(r, 0) for r in range(3)] == [
        "Item 1",
        "Item 2",
        "Item 3",
    ]

    # Zero-padded
    model2 = SheetDataModel()
    model2.set_cell(0, 0, CellData(value="Section 08"))
    model2.set_cell(1, 0, CellData(value="Section 09"))
    AutoFillEngine.auto_fill(
        model2, SelectionRange(0, 0, 1, 0), SelectionRange(0, 0, 3, 0)
    )
    assert [model2.get_cell_value(r, 0) for r in range(4)] == [
        "Section 08",
        "Section 09",
        "Section 10",
        "Section 11",
    ]


def test_autofill_builtin_lists():
    """Built-in weekday and month lists (English & Chinese) should cycle smoothly."""
    # English days
    model = SheetDataModel()
    model.set_cell(0, 0, CellData(value="Fri"))
    AutoFillEngine.auto_fill(
        model, SelectionRange(0, 0, 0, 0), SelectionRange(0, 0, 3, 0)
    )
    assert [model.get_cell_value(r, 0) for r in range(4)] == [
        "Fri",
        "Sat",
        "Sun",
        "Mon",
    ]

    # Chinese days
    model2 = SheetDataModel()
    model2.set_cell(0, 0, CellData(value="周五"))
    AutoFillEngine.auto_fill(
        model2, SelectionRange(0, 0, 0, 0), SelectionRange(0, 0, 3, 0)
    )
    assert [model2.get_cell_value(r, 0) for r in range(4)] == [
        "周五",
        "周六",
        "周日",
        "周一",
    ]


def test_autofill_formulas_relative_and_absolute_references():
    """Formulas should adjust relative references while preserving absolute references."""
    model = SheetDataModel()
    # Formula =A1+$B$1
    model.set_cell(0, 2, CellData(value=0, formula="=A1+$B$1"))

    # Fill down 2 rows
    src = SelectionRange(0, 2, 0, 2)
    dest = SelectionRange(0, 2, 2, 2)
    AutoFillEngine.auto_fill(model, src, dest)

    assert model.get_cell(0, 2).formula == "=A1+$B$1"
    assert model.get_cell(1, 2).formula == "=A2+$B$1"
    assert model.get_cell(2, 2).formula == "=A3+$B$1"


def test_autofill_shrink_clears_contracted_cells():
    """Dragging fill handle backwards (shrink) clears cells outside new dest."""
    model = SheetDataModel()
    for r in range(4):
        model.set_cell(r, 0, CellData(value=r))

    src = SelectionRange(0, 0, 3, 0)
    dest = SelectionRange(0, 0, 1, 0)
    AutoFillEngine.auto_fill(model, src, dest)

    assert model.get_cell_value(0, 0) == 0
    assert model.get_cell_value(1, 0) == 1
    assert model.get_cell(2, 0) is None
    assert model.get_cell(3, 0) is None


# -----------------------------------------------------------------------------
# GUI Viewport Hit Testing and Interaction Tests
# -----------------------------------------------------------------------------
def test_fill_handle_hit_test(qtbot):
    """Viewport should detect HitZone.FILL_HANDLE within 4px of bottom-right corner."""
    viewport = GridViewport()
    qtbot.addWidget(viewport)
    viewport.resize(600, 400)
    viewport.show()

    viewport.selection.select_cell(0, 0)
    # Cell (0, 0) bounds
    # row_header_width = 46, col_header_height = 22
    # col_pos(1) = 64, row_pos(1) = 20
    # Fill handle is at (46 + 64, 22 + 20) = (110, 42)
    hit = viewport.hit_test(110, 42)
    assert hit.zone == HitZone.FILL_HANDLE

    # Outside threshold (+10px) should not be FILL_HANDLE
    hit_outside = viewport.hit_test(125, 42)
    assert hit_outside.zone != HitZone.FILL_HANDLE


def test_fill_handle_hover_cursor(qtbot):
    """Hovering over fill handle should set cursor to CrossCursor."""
    viewport = GridViewport()
    qtbot.addWidget(viewport)
    viewport.resize(600, 400)
    viewport.show()

    viewport.selection.select_cell(0, 0)
    # Trigger mouseMove at fill handle position (110, 42)
    pos = QPointF(110, 42)
    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        pos,
        pos,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    viewport.mouseMoveEvent(event)

    assert viewport.viewport().cursor().shape() == Qt.CursorShape.CrossCursor


def test_fill_handle_drag_and_release(qtbot):
    """Dragging fill handle down 2 rows should extend data and select new range."""
    viewport = GridViewport()
    qtbot.addWidget(viewport)
    viewport.resize(600, 400)
    viewport.show()

    viewport.model.set_cell(0, 0, CellData(value=100))
    viewport.selection.select_cell(0, 0)

    # 1. Mouse Press on fill handle
    p1 = QPointF(110, 42)
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        p1,
        p1,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,  # Ctrl to increment
    )
    viewport.mousePressEvent(press_event)
    assert viewport._drag_mode == HitZone.FILL_HANDLE

    # 2. Mouse Move down to row 2 (y around 22 + 3 * 20 = 82)
    p2 = QPointF(110, 75)
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        p2,
        p2,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
    )
    viewport.mouseMoveEvent(move_event)
    assert viewport._fill_preview_range is not None
    assert viewport._fill_preview_range.max_r >= 1

    # 3. Mouse Release
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        p2,
        p2,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
    )
    viewport.mouseReleaseEvent(release_event)

    # Assert drag ended, new range selected, and cells filled
    assert viewport._drag_mode == HitZone.NONE
    assert viewport.selection.primary_range.max_r >= 1
    assert viewport.model.get_cell_value(0, 0) == 100
    assert viewport.model.get_cell_value(1, 0) == 101
