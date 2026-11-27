"""Tests for Lectern PresentationHistory timer cancellation and SlideScene lifecycle safety."""

from __future__ import annotations

import shiboken6
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest

from atboffice.ui.shell.lectern_window import LecternWindow


def test_lectern_rapid_edit_and_close_does_not_flush_after_close(
    qtbot, qapp, caplog, monkeypatch
) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()
    qapp.processEvents()

    flush_calls = 0
    orig_flush = win.history.flush

    def tracked_flush() -> None:
        nonlocal flush_calls
        flush_calls += 1
        orig_flush()

    monkeypatch.setattr(win.history, "flush", tracked_flush)

    win.history.note_edit("canvas", "Edit before close")
    assert win.history._pending is True
    win.set_modified(False)
    win.close()
    assert win.history._pending is False
    qapp.processEvents()
    assert win.history._pending is False
    assert flush_calls == 0
    assert "Failed" not in caplog.text


def test_lectern_draw_shape_and_textbox_undo_redo_and_roundtrip(qtbot, qapp, tmp_path) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()
    qapp.processEvents()

    ws = win.presentation_view.workspace
    canvas = ws.canvas_view
    slide = canvas.scene().slide
    initial_count = len(slide.shapes)

    win.set_drawing_tool({"kind": "shape", "geom": "rect"})
    QTest.mousePress(
        canvas.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(180, 160),
    )
    QTest.mouseMove(canvas.viewport(), QPoint(320, 260))
    QTest.mouseRelease(
        canvas.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(320, 260),
    )
    win.flush_pending_edits()

    win.set_drawing_tool({"kind": "textbox"})
    QTest.mousePress(
        canvas.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(120, 100),
    )
    QTest.mouseMove(canvas.viewport(), QPoint(260, 150))
    QTest.mouseRelease(
        canvas.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(260, 150),
    )
    win.flush_pending_edits()

    assert len(ws.current_slide.shapes) == initial_count + 2
    win.undo()
    assert len(ws.current_slide.shapes) == initial_count + 1
    win.redo()
    assert len(ws.current_slide.shapes) == initial_count + 2

    out = tmp_path / "shapes.pptx"
    assert win.save_file(out, confirm_overwrite=False) is True
    assert out.stat().st_size > 0
    win.set_modified(False)


def test_slide_scene_mouse_move_with_deleted_dragged_item_is_safe(qtbot, qapp) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()
    qapp.processEvents()

    canvas = win.presentation_view.workspace.canvas_view
    scene = canvas.scene()

    # Add a shape first so _items_by_id has a real ShapeGraphicsItem
    win.set_drawing_tool({"kind": "shape", "geom": "rect"})
    QTest.mousePress(
        canvas.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(180, 160),
    )
    QTest.mouseMove(canvas.viewport(), QPoint(280, 240))
    QTest.mouseRelease(
        canvas.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(280, 240),
    )
    win.flush_pending_edits()

    item = next(iter(scene._items_by_id.values()))
    scene._is_dragging_item = True
    scene._dragged_item = item
    shiboken6.delete(item)

    ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(240, 200),
        QPointF(240, 200),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    # Must not crash with RuntimeError: Internal C++ object already deleted
    qapp.sendEvent(canvas.viewport(), ev)
    win.set_modified(False)
