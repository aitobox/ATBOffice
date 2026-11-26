"""Regression tests for Quire insert_shape, float operations, and fast typing on numbered docs."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from atboffice.modules.writer.models.document import all_stories
from atboffice.modules.writer.models.drawing import ShapeItem
from atboffice.ui.shell.quire_window import QuireWindow

BULLET_DOC = Path(__file__).resolve().parents[1] / "docs/word/docx/openxml-sdk__bullet-complex.docx"


def _shape_items(doc) -> list[ShapeItem]:
    items: list[ShapeItem] = []
    for story in all_stories(doc):
        for para in story.paras:
            for run in para.runs:
                if isinstance(run, ShapeItem):
                    items.append(run)
    return items


def test_quire_insert_shape_and_float_ops_are_undoable_and_persist(qtbot, tmp_path) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()
    canvas = win.writer_view.canvas_view

    win.insert_shape("rect")
    win.insert_shape("textbox")
    shapes = _shape_items(canvas.doc)
    assert len(shapes) == 2
    assert shapes[0].geometry == "rect"
    assert shapes[1].story is not None

    # Float manipulation ops work on selected shape and are undoable
    assert canvas.selected_float() is shapes[1]
    start_x = shapes[1].float_pr.pos_h.offset
    win.nudge_selected_object(12, 8)
    assert shapes[1].float_pr.pos_h.offset > start_x
    win.rotate_selected_object(15.0)
    assert shapes[1].rotation == 15.0

    win.undo()  # undo rotate
    assert _shape_items(canvas.doc)[1].rotation == 0.0
    win.undo()  # undo nudge
    assert _shape_items(canvas.doc)[1].float_pr.pos_h.offset == start_x
    win.undo()  # undo textbox insert
    assert len(_shape_items(canvas.doc)) == 1
    win.redo()
    assert len(_shape_items(canvas.doc)) == 2

    out = tmp_path / "with_shapes.docx"
    assert win.save_file(out, confirm_overwrite=False) is True
    assert out.stat().st_size > 0
    win.set_modified(False)


def test_quire_click_and_type_after_shape_on_numbered_docx_is_fast(qtbot, qapp) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()
    assert win.open_file(BULLET_DOC) is True
    canvas = win.writer_view.canvas_view

    win.insert_shape("rect")
    win.insert_shape("textbox")
    QTest.mouseClick(
        canvas.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(300, 200),
    )
    t0 = time.monotonic()
    QTest.keyClicks(canvas, "Hello")
    qapp.processEvents()
    elapsed = time.monotonic() - t0
    assert elapsed < 2.0, f"Typing stalled for {elapsed:.2f}s"
    win.set_modified(False)


def test_quire_reorder_and_align_selected_object(qtbot) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()
    canvas = win.writer_view.canvas_view

    win.insert_shape("rect")
    shape = _shape_items(canvas.doc)[0]
    base_z = shape.float_pr.z_index

    win.reorder_selected_object("front")
    assert _shape_items(canvas.doc)[0].float_pr.z_index == base_z + 10
    win.undo()
    assert _shape_items(canvas.doc)[0].float_pr.z_index == base_z

    win.align_selected_objects("center")
    aligned = _shape_items(canvas.doc)[0]
    assert aligned.float_pr.pos_h.rel == "margin"
    assert aligned.float_pr.pos_h.align == "center"

    win.align_selected_objects("middle")
    aligned_v = _shape_items(canvas.doc)[0]
    assert aligned_v.float_pr.pos_v.rel == "margin"
    assert aligned_v.float_pr.pos_v.align == "center"
    win.set_modified(False)
