"""GUI tests for mouse drag gestures, drag cancel on Escape, and selection state.

Ported from .vibeoffice/tests/ui/drag.test.mjs and gestures.test.mjs.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from atboffice.modules.spreadsheet.models.sheet_model import CellData
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport, HitZone
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TextItem,
    reindex,
)
from atboffice.modules.writer.views.canvas_view import WriterCanvasView


def test_spreadsheet_fill_handle_drag_escape_cancel(qtbot):
    """Pressing Escape during a fill handle drag cancels the drag and keeps original data.

    Matches .vibeoffice drag.test.mjs 'Esc, Ctrl+Z, cancel'.
    """
    viewport = GridViewport()
    qtbot.addWidget(viewport)
    viewport.resize(600, 400)
    viewport.show()

    viewport.model.set_cell(0, 0, CellData(value=999))
    viewport.selection.select_cell(0, 0)

    # 1. Mouse press on fill handle (110, 42)
    p1 = QPointF(110, 42)
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        p1,
        p1,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    viewport.mousePressEvent(press_event)
    assert viewport._drag_mode == HitZone.FILL_HANDLE

    # 2. Mouse move down to row 3
    p2 = QPointF(110, 85)
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        p2,
        p2,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    viewport.mouseMoveEvent(move_event)
    assert viewport._fill_preview_range is not None

    # 3. Press Escape to cancel mid-drag
    esc_event = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )
    viewport.keyPressEvent(esc_event)

    # Verify drag cancelled and preview removed
    assert viewport._drag_mode == HitZone.NONE
    assert viewport._fill_preview_range is None

    # Cells below must remain empty (untouched)
    assert viewport.model.get_cell_value(1, 0) is None
    assert viewport.model.get_cell_value(2, 0) is None
    assert viewport.model.get_cell_value(0, 0) == 999


def test_spreadsheet_selection_drag_and_extend(qtbot):
    """Dragging across cells selects a multi-cell rectangular range."""
    viewport = GridViewport()
    qtbot.addWidget(viewport)
    viewport.resize(600, 400)
    viewport.show()

    # Start press in cell (0, 0)
    p_start = QPointF(60, 30)
    viewport.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p_start,
            p_start,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    # Drag to cell (2, 2)
    p_end = QPointF(200, 75)
    viewport.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p_end,
            p_end,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    viewport.mouseReleaseEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            p_end,
            p_end,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    pr = viewport.selection.primary_range
    assert pr.min_r == 0
    assert pr.max_r >= 1
    assert pr.max_c >= 1


def test_writer_canvas_mouse_selection_and_escape(qtbot):
    """Click and drag in Writer canvas selects text, Escape clears selection."""
    doc = Document()
    doc.main.blocks.clear()
    p = Paragraph()
    p.runs.append(TextItem("ATBOffice Enterprise Suite Test Document"))
    doc.main.blocks.append(p)
    reindex(doc)

    canvas = WriterCanvasView(doc=doc)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()

    # Click inside first page content area
    p1 = QPointF(150, 150)
    canvas.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p1,
            p1,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    # Drag across to select text
    p2 = QPointF(350, 150)
    canvas.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p2,
            p2,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    canvas.mouseReleaseEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            p2,
            p2,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    # Escape clears active selection
    esc = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    canvas.keyPressEvent(esc)
    assert canvas.controller.selection.is_collapsed
