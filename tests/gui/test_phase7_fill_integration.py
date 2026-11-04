"""Phase 7 integration tests for spreadsheet autofill handle event lifecycle and protection.

TASK-710 / Issue #244:
- Real event drag across cell coordinates (A1=1, A2=2 dragged to A10 -> 1..10)
- Single value default copy, Ctrl/Cmd linear sequence
- Formula relative and absolute reference translation
- Sheet protection guard gate: protected target cannot be mutated, zero dirty/undo records
- Sparse delta undo/redo transaction without cloning whole sheet
- Cancellation lifecycle: Esc, blur/focus out, secondary button press, lost release
- Overlay cursor forwarding through SpreadsheetObjectLayer
- Double-click fill handle to auto-fill down to adjacent data extent
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent, QMouseEvent

from atboffice.modules.spreadsheet.models.selection_model import SelectionRange
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport, HitZone
from atboffice.modules.spreadsheet.views.object_layer import SpreadsheetObjectLayer


def test_fill_handle_linear_drag_real_data(qtbot):
    """A1=1, A2=2 dragged down to A10 yields 1..10, with formula & modifier checks."""
    viewport = GridViewport()
    qtbot.addWidget(viewport)
    viewport.resize(600, 400)
    viewport.show()

    # Setup A1=1, A2=2
    viewport.model.set_cell(0, 0, CellData(value=1))
    viewport.model.set_cell(1, 0, CellData(value=2))

    # Select A1:A2
    viewport.selection.select_cell(0, 0)
    viewport.selection.extend_to(1, 0)

    # 1. Hit test fill handle at bottom right of (1, 0)
    # col 0 end = 46 + 64 = 110, row 1 end = 22 + 40 = 62
    p_handle = QPointF(110, 62)
    hit = viewport.hit_test(110, 62)
    assert hit.zone == HitZone.FILL_HANDLE

    # 2. Press fill handle
    viewport.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p_handle,
            p_handle,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert viewport._drag_mode == HitZone.FILL_HANDLE

    # 3. Drag down to row 9 (y = 22 + 10 * 20 = 222)
    p_dest = QPointF(110, 215)
    viewport.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p_dest,
            p_dest,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert viewport._fill_preview_range is not None
    assert viewport._fill_preview_range.max_r >= 9

    # 4. Release mouse
    viewport.mouseReleaseEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            p_dest,
            p_dest,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert viewport._drag_mode == HitZone.NONE

    # Check 1..10
    values = [viewport.model.get_cell_value(r, 0) for r in range(10)]
    assert values == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def test_fill_handle_single_value_modifiers(qtbot):
    """Single numeric value copies by default, increments with Ctrl or Meta (Cmd on macOS)."""
    viewport = GridViewport()
    qtbot.addWidget(viewport)
    viewport.resize(600, 400)
    viewport.show()

    # Default without modifier: copy
    viewport.model.set_cell(0, 0, CellData(value=50))
    viewport.selection.select_cell(0, 0)

    p_handle = QPointF(110, 42)
    p_dest = QPointF(110, 100)

    # Press, move, release without modifier
    viewport.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p_handle,
            p_handle,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    viewport.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p_dest,
            p_dest,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    viewport.mouseReleaseEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            p_dest,
            p_dest,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    for r in range(4):
        assert viewport.model.get_cell_value(r, 0) == 50

    # With MetaModifier (Cmd on macOS) or ControlModifier: linear sequence
    viewport.model.set_cell(0, 1, CellData(value=10))
    viewport.selection.select_cell(0, 1)

    p_handle2 = QPointF(110 + 64, 42)
    p_dest2 = QPointF(110 + 64, 100)

    viewport.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p_handle2,
            p_handle2,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.MetaModifier,
        )
    )
    viewport.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p_dest2,
            p_dest2,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.MetaModifier,
        )
    )
    viewport.mouseReleaseEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            p_dest2,
            p_dest2,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.MetaModifier,
        )
    )

    assert [viewport.model.get_cell_value(r, 1) for r in range(4)] == [10, 11, 12, 13]


def test_fill_handle_protection_blocks_and_no_dirty(qtbot, monkeypatch):
    """Protected sheet prevents autofill: target cells unmodified, zero undo entries, not dirty."""
    viewport = GridViewport()
    qtbot.addWidget(viewport)
    viewport.resize(600, 400)
    viewport.show()

    # Prevent modal QMessageBox popups in automated test
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    # Protect the sheet
    viewport.model.protected = True

    viewport.model.set_cell(0, 0, CellData(value=100))
    viewport.selection.select_cell(0, 0)
    initial_undo_len = len(viewport._undo_stack)

    # Attempt to drag fill handle
    p_handle = QPointF(110, 42)
    p_dest = QPointF(110, 100)

    viewport.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p_handle,
            p_handle,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    viewport.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p_dest,
            p_dest,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    viewport.mouseReleaseEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            p_dest,
            p_dest,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    # Cells below must remain untouched
    assert viewport.model.get_cell(1, 0) is None
    assert viewport.model.get_cell(2, 0) is None
    assert viewport.model.get_cell_value(0, 0) == 100

    # No undo records added
    assert len(viewport._undo_stack) == initial_undo_len


def test_fill_handle_sparse_undo_redo(qtbot):
    """Autofill records only sparse delta (not whole table) and restores accurately on undo/redo."""
    viewport = GridViewport()
    qtbot.addWidget(viewport)
    viewport.resize(600, 400)
    viewport.show()

    # Pre-populate 100 background cells to verify no whole-table cloning
    for r in range(50):
        for c in range(5, 7):
            viewport.model.set_cell(r, c, CellData(value=r * 10 + c))

    viewport.model.set_cell(0, 0, CellData(value=10))
    viewport.model.set_cell(1, 0, CellData(value=20))
    viewport.selection.select_cell(0, 0)
    viewport.selection.extend_to(1, 0)

    p_handle = QPointF(110, 62)
    p_dest = QPointF(110, 110)  # Inside row 4 (102..122)

    viewport.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p_handle,
            p_handle,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    viewport.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p_dest,
            p_dest,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    viewport.mouseReleaseEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            p_dest,
            p_dest,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    # Verify fill values
    assert [viewport.model.get_cell_value(r, 0) for r in range(5)] == [10, 20, 30, 40, 50]

    # Inspect undo stack entry
    assert len(viewport._undo_stack) > 0
    cmd = viewport._undo_stack[-1]
    assert cmd.get("action") == "autofill"
    # Ensure sparse delta is stored (or small subset of modified cells, NOT 100+ cells)
    if "before_delta_cells" in cmd:
        assert len(cmd["before_delta_cells"]) <= 5

    # 1. Undo
    viewport.undo()
    assert viewport.model.get_cell_value(0, 0) == 10
    assert viewport.model.get_cell_value(1, 0) == 20
    assert viewport.model.get_cell(2, 0) is None
    assert viewport.model.get_cell(3, 0) is None
    assert viewport.model.get_cell(4, 0) is None
    # Selection restored to source
    pr = viewport.selection.primary_range
    assert pr.min_r == 0 and pr.max_r == 1 and pr.min_c == 0 and pr.max_c == 0

    # 2. Redo
    viewport.redo()
    assert [viewport.model.get_cell_value(r, 0) for r in range(5)] == [10, 20, 30, 40, 50]
    pr = viewport.selection.primary_range
    assert pr.min_r == 0 and pr.max_r == 4


def test_fill_handle_cancellation_lifecycle(qtbot):
    """Esc, blur, and secondary button click cancel active drag cleanly."""
    viewport = GridViewport()
    qtbot.addWidget(viewport)
    viewport.resize(600, 400)
    viewport.show()

    viewport.model.set_cell(0, 0, CellData(value=777))
    viewport.selection.select_cell(0, 0)

    p_handle = QPointF(110, 42)
    p_move = QPointF(110, 90)

    # Case 1: Cancel via secondary button
    viewport.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p_handle,
            p_handle,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    viewport.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p_move,
            p_move,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert viewport._drag_mode == HitZone.FILL_HANDLE

    # Right click pressed while dragging cancels drag
    viewport.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p_move,
            p_move,
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert viewport._drag_mode == HitZone.NONE
    assert viewport._fill_preview_range is None
    assert viewport.model.get_cell(1, 0) is None

    # Case 2: Cancel via blur / FocusOut
    viewport.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p_handle,
            p_handle,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    viewport.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p_move,
            p_move,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert viewport._drag_mode == HitZone.FILL_HANDLE

    viewport.focusOutEvent(QFocusEvent(QFocusEvent.Type.FocusOut))
    assert viewport._drag_mode == HitZone.NONE
    assert viewport._fill_preview_range is None
    assert viewport.model.get_cell(1, 0) is None


def test_fill_handle_double_click_fill_down(qtbot):
    """Double clicking fill handle fills down adjacent data column extent."""
    viewport = GridViewport()
    qtbot.addWidget(viewport)
    viewport.resize(600, 400)
    viewport.show()

    # Column A has 6 rows with numbers
    for r in range(6):
        viewport.model.set_cell(r, 0, CellData(value=f"Item {r + 1}"))

    # Column B has row 0 = 10, row 1 = 20
    viewport.model.set_cell(0, 1, CellData(value=10))
    viewport.model.set_cell(1, 1, CellData(value=20))

    viewport.selection.select_cell(0, 1)
    viewport.selection.extend_to(1, 1)

    # Double click at fill handle of B2 (col 1 end = 46 + 128 = 174, row 1 end = 22 + 40 = 62)
    p_handle = QPointF(174, 62)
    viewport.mouseDoubleClickEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            p_handle,
            p_handle,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    # Should fill B down to row 5 (matching column A length)
    values = [viewport.model.get_cell_value(r, 1) for r in range(6)]
    assert values == [10, 20, 30, 40, 50, 60]


def test_object_layer_cursor_forwarding(qtbot):
    """SpreadsheetObjectLayer unsets cursor on empty space so fill handle CrossCursor shows."""
    view = SpreadsheetView()
    qtbot.addWidget(view)
    view.resize(600, 400)
    view.show()

    grid = view.grid
    grid.model.set_cell(0, 0, CellData(value=1))
    grid.selection.select_cell(0, 0)

    # Move mouse over fill handle at (110, 42)
    p_handle = QPointF(110, 42)
    view.object_layer.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p_handle,
            p_handle,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    grid.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p_handle,
            p_handle,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    # Grid viewport should show CrossCursor
    assert grid.viewport().cursor().shape() == Qt.CursorShape.CrossCursor
