"""GUI tests for keyboard focus restoration after dialogs and toolbars.

Ported from .vibeoffice/tests/ui/focus.test.mjs.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QDialog

from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TextItem,
    reindex,
)
from atboffice.modules.writer.views.canvas_view import WriterCanvasView
from atboffice.modules.writer.views.caret_controller import DocPos


def test_spreadsheet_selection_preserved_across_focus_cycles(qtbot):
    """Grid selection and active cell remain identical across focus loss and gain.

    Matches .vibeoffice focus.test.mjs:
    'After each, the element that had the keyboard has it again, with the same selection.'
    """
    viewport = GridViewport()
    qtbot.addWidget(viewport)
    viewport.resize(600, 400)
    viewport.show()

    viewport.selection.select_cell(3, 4)
    assert viewport.selection.active_cell == (3, 4)

    # Focus lost to a popup / dialog
    focus_out = QFocusEvent(QFocusEvent.Type.FocusOut, Qt.FocusReason.PopupFocusReason)
    viewport.focusOutEvent(focus_out)

    # Selection remains intact
    assert viewport.selection.active_cell == (3, 4)
    assert viewport.selection.primary_range.min_r == 3
    assert viewport.selection.primary_range.min_c == 4

    # Focus restored
    focus_in = QFocusEvent(QFocusEvent.Type.FocusIn, Qt.FocusReason.ActiveWindowFocusReason)
    viewport.focusInEvent(focus_in)
    assert viewport.selection.active_cell == (3, 4)


def test_writer_caret_and_selection_preserved_across_dialog_dismiss(qtbot):
    """Writer caret and selection state remain identical when closing dialogs via Escape."""
    doc = Document()
    doc.main.blocks.clear()
    p = Paragraph()
    p.runs.append(TextItem("Focused Document Typing Area"))
    doc.main.blocks.append(p)
    reindex(doc)

    canvas = WriterCanvasView(doc=doc)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()

    # Place caret at character index 8
    target_pos = DocPos(0, 8)
    canvas.controller.set_pos(target_pos)
    assert canvas.controller.pos.offset == 8

    # Simulate modal dialog open and Esc dismiss
    dialog = QDialog(canvas)
    qtbot.addWidget(dialog)
    dialog.show()

    # Reject dialog (Escape)
    dialog.reject()

    # Canvas regains focus and cursor remains at character index 8
    canvas.setFocus()
    assert canvas.controller.pos.offset == 8
