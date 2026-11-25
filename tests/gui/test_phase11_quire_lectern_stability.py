"""Regression tests for issue #440: Quire undo/caret retention and Lectern editor lifecycle."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent, QTextCursor

from atboffice.modules.presentation.models.designs import build_design
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Fill, Shape
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun
from atboffice.modules.presentation.views.workspace import LecternWorkspace
from atboffice.modules.writer.models.document import TextItem
from atboffice.modules.writer.views.caret_controller import DocPos, Selection
from atboffice.ui.components.undo_history import entry_label
from atboffice.ui.shell.quire_window import QuireWindow

# ---------------------------------------------------------------------------
# Quire
# ---------------------------------------------------------------------------


@pytest.fixture
def quire(qtbot) -> QuireWindow:
    win = QuireWindow()
    qtbot.addWidget(win)
    canvas = win.writer_view.canvas_view
    para = canvas.doc.main.blocks[0]
    para.runs = [TextItem(text="Hello brave new world")]
    canvas.refresh_layout()
    yield win
    win.set_modified(False)


def _select_range(canvas, start: int, end: int) -> None:
    para = canvas.doc.main.blocks[0]
    canvas.controller.pos = DocPos(para.id, end)
    canvas.controller.selection = Selection(DocPos(para.id, start), DocPos(para.id, end))


def test_formatting_keeps_undo_history_caret_and_selection(quire: QuireWindow) -> None:
    canvas = quire.writer_view.canvas_view
    canvas.push_undo_command({"type": "noop_marker"})
    canvas._pixmap_cache["img"] = object()
    _select_range(canvas, 0, 5)

    quire._toggle_bold()
    quire._toggle_italic()

    # Each format change is its own step on top of the earlier history.
    assert canvas.history.labels("undo")[2] == entry_label({"type": "noop_marker"})
    assert len(canvas.history) == 3
    assert "img" in canvas._pixmap_cache
    assert canvas.controller.pos.offset == 5
    sel = canvas.controller.selection
    assert (sel.anchor.offset, sel.focus.offset) == (0, 5)


def test_format_change_is_undoable(quire: QuireWindow) -> None:
    canvas = quire.writer_view.canvas_view
    para = canvas.doc.main.blocks[0]
    _select_range(canvas, 0, 5)

    quire._toggle_bold()
    assert para.runs[0].r_pr.b is True

    assert canvas.undo() is True
    para = canvas.doc.main.blocks[0]
    assert not any(getattr(r.r_pr, "b", None) for r in para.runs)
    sel = canvas.controller.selection
    assert (sel.anchor.offset, sel.focus.offset) == (0, 5)
    canvas.redo()
    assert canvas.doc.main.blocks[0].runs[0].r_pr.b is True


def test_multi_step_format_then_undo_redo(quire: QuireWindow) -> None:
    import copy

    from atboffice.modules.writer.models.properties import TabStop

    canvas = quire.writer_view.canvas_view
    para = canvas.doc.main.blocks[0]
    old_tabs = copy.deepcopy(para.p_pr.tabs)
    para.p_pr.tabs = [TabStop(pos=72.0)]
    canvas.push_undo_command(
        {
            "type": "paragraph_tabs",
            "para_id": para.id,
            "before": old_tabs,
            "after": copy.deepcopy(para.p_pr.tabs),
        }
    )
    _select_range(canvas, 0, 5)

    quire._toggle_bold()
    quire._toggle_underline()

    # The earlier edit is still undoable after formatting, and can be redone.
    assert canvas.history.undo_steps("undo", 3) == 3
    # Undo restores copies of the paragraph: look it up again.
    para = canvas.doc.main.blocks[0]
    assert para.p_pr.tabs == old_tabs
    assert canvas.can_redo()
    canvas.redo()
    assert canvas.doc.main.blocks[0].p_pr.tabs == [TabStop(pos=72.0)]


def test_table_operations_keep_undo_history(quire: QuireWindow) -> None:
    canvas = quire.writer_view.canvas_view
    canvas.push_undo_command({"type": "noop_marker"})

    canvas.insert_table(2, 2)
    assert canvas.get_current_table_context() is not None

    canvas.distribute_table_rows()
    canvas.distribute_table_cols()
    marker = entry_label({"type": "noop_marker"})
    labels = canvas.history.labels("undo")
    assert labels[-1] == marker
    assert labels[-2] == "插入表格"


def test_hidden_review_pane_is_not_rebuilt_per_keystroke(
    quire: QuireWindow, monkeypatch
) -> None:
    view = quire.writer_view
    calls: list[int] = []
    monkeypatch.setattr(view.review_pane, "refresh_items", lambda: calls.append(1))
    assert view.review_pane.isHidden()

    for _ in range(5):
        view.canvas_view.controller.insert_text("x")

    assert calls == []
    view.set_review_pane_visible(True)
    assert calls == [1]
    view.canvas_view.controller.insert_text("y")
    assert calls == [1, 1]


def test_selection_signals_are_coalesced_into_one_toolbar_sync(
    quire: QuireWindow, qapp, monkeypatch
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(quire, "_sync_toolbar_states", lambda: calls.append(1))
    canvas = quire.writer_view.canvas_view
    controller = canvas.controller

    for end in range(1, 5):
        _select_range(canvas, 0, end)
        controller.selection_changed.emit()
    assert calls == []
    qapp.processEvents()

    assert calls == [1]


def test_keystroke_syncs_toolbars_once(quire: QuireWindow, qapp, monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(quire, "_sync_toolbar_states", lambda: calls.append(1))

    quire.writer_view.canvas_view.controller.insert_text("z")
    qapp.processEvents()

    assert len(calls) == 1


# ---------------------------------------------------------------------------
# Lectern
# ---------------------------------------------------------------------------


@pytest.fixture
def presentation() -> Presentation:
    pres = Presentation.create_new(title="Stability", empty=True)
    d = build_design("default", pres.w, pres.h)
    pres.designs[d.id] = d
    s1 = pres.add_slide(layout="text", design_id=d.id)
    s1.add_shape(
        Shape(
            id="box",
            geom="rect",
            x=150.0,
            y=200.0,
            w=250.0,
            h=120.0,
            fill=Fill.solid("#2B579A"),
            text=TextBody.from_plain_text("Initial"),
        )
    )
    s1.add_shape(Shape(id="box2", geom="rect", x=450.0, y=200.0, w=80.0, h=80.0))
    pres.add_slide(layout="text", design_id=d.id)
    return pres


@pytest.fixture
def workspace(qtbot, presentation: Presentation) -> LecternWorkspace:
    ws = LecternWorkspace(presentation=presentation)
    qtbot.addWidget(ws)
    ws.resize(1100, 750)
    ws.show()
    ws.set_current_slide_index(0)
    return ws


def _editing(workspace: LecternWorkspace, text: str):
    scene = workspace.canvas_view.scene()
    item = scene.get_shape_item("box")
    editor = item.start_text_editing()
    editor.setPlainText(text)
    return scene, item, editor


def test_click_outside_commits_typed_text(workspace: LecternWorkspace, qtbot) -> None:
    scene, item, _editor = _editing(workspace, "Typed then clicked away")
    view = workspace.canvas_view
    empty = view.mapFromScene(QPointF(20.0, 20.0))

    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=empty)

    model = presentation_shape(workspace, "box")
    assert model.text.plain_text == "Typed then clicked away"
    assert not item.is_editing_text


def presentation_shape(workspace: LecternWorkspace, shape_id: str) -> Shape:
    slide = workspace.presentation.slides[0]
    return next(sh for sh in slide.shapes if sh.id == shape_id)


def test_focus_to_popup_or_toolbar_keeps_editor_alive(workspace: LecternWorkspace) -> None:
    _scene, item, editor = _editing(workspace, "Keep me open")

    editor.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.PopupFocusReason))
    assert item.is_editing_text

    # The session can still be formatted and later committed.
    editor.set_bold()
    editor.commit_and_finish()
    assert presentation_shape(workspace, "box").text.plain_text == "Keep me open"


def test_toolbar_focus_detection(workspace: LecternWorkspace, qtbot, monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication, QComboBox, QToolBar

    _scene, item, editor = _editing(workspace, "Toolbar combo")
    toolbar = QToolBar()
    combo = QComboBox(toolbar)
    toolbar.addWidget(combo)
    qtbot.addWidget(toolbar)
    monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda: combo))

    editor.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.MouseFocusReason))

    assert item.is_editing_text
    editor.commit_and_finish()


def test_focus_elsewhere_still_commits(workspace: LecternWorkspace, monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication

    _scene, item, editor = _editing(workspace, "Committed on focus loss")
    monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda: None))

    editor.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.OtherFocusReason))

    assert not item.is_editing_text
    assert presentation_shape(workspace, "box").text.plain_text == "Committed on focus loss"


def test_switching_slides_commits_active_editor(workspace: LecternWorkspace) -> None:
    _editing(workspace, "Survives slide switch")

    workspace.set_current_slide_index(1)

    assert presentation_shape(workspace, "box").text.plain_text == "Survives slide switch"


def test_backspace_while_editing_does_not_delete_shape(workspace: LecternWorkspace) -> None:
    scene, item, editor = _editing(workspace, "abc")
    item.setSelected(True)
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)

    for key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete, Qt.Key.Key_Left):
        workspace.canvas_view.keyPressEvent(
            QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
        )

    assert scene.get_shape_item("box") is item
    assert item.is_editing_text
    assert any(sh.id == "box" for sh in workspace.presentation.slides[0].shapes)


def test_delete_group_ungroup_shortcuts_when_not_editing(workspace: LecternWorkspace) -> None:
    scene = workspace.canvas_view.scene()
    for sid in ("box", "box2"):
        scene.get_shape_item(sid).setSelected(True)
    view = workspace.canvas_view

    view.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)
    )
    groups = [sh for sh in scene.slide.shapes if sh.type == "group"]
    assert len(groups) == 1

    scene.get_shape_item(groups[0].id).setSelected(True)
    view.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_G,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
    )
    assert not [sh for sh in scene.slide.shapes if sh.type == "group"]

    scene.clearSelection()
    scene.get_shape_item("box2").setSelected(True)
    view.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    )
    assert scene.get_shape_item("box2") is None


def test_sync_active_text_editing_keeps_session(workspace: LecternWorkspace) -> None:
    scene, item, _editor = _editing(workspace, "Saved mid-edit")

    scene.sync_active_text_editing()

    assert presentation_shape(workspace, "box").text.plain_text == "Saved mid-edit"
    assert item.is_editing_text


# ---------------------------------------------------------------------------
# Outline editor
# ---------------------------------------------------------------------------


def _body_shape(slide):
    return next(
        sh
        for sh in slide.shapes
        if sh.placeholder and sh.placeholder.type in ("body", "subTitle", "obj")
    )


def _title_shape(slide):
    return next(
        sh for sh in slide.shapes if sh.placeholder and sh.placeholder.type in ("title", "ctrTitle")
    )


@pytest.fixture
def outline_ws(workspace: LecternWorkspace) -> LecternWorkspace:
    slide = workspace.presentation.slides[0]
    _title_shape(slide).text = TextBody(
        paragraphs=[Paragraph(runs=[TextRun(text="Agenda", bold=True, size=40.0)])]
    )
    _body_shape(slide).text = TextBody(
        paragraphs=[
            Paragraph(level=0, runs=[TextRun(text="First point", italic=True)]),
            Paragraph(level=1, runs=[TextRun(text="Second point", color="#FF0000")]),
        ]
    )
    workspace.outline_editor.reload(workspace.presentation)
    return workspace


def _replace_outline_text(outline, old: str, new: str) -> None:
    outline.editor.setPlainText(outline.editor.toPlainText().replace(old, new))


def test_editing_title_keeps_body_bullets_and_formatting(outline_ws: LecternWorkspace) -> None:
    outline = outline_ws.outline_editor
    _replace_outline_text(outline, "Agenda", "Agenda 2026")

    slide = outline_ws.presentation.slides[0]
    title = _title_shape(slide).text.paragraphs[0].runs[0]
    assert title.text == "Agenda 2026"
    assert title.bold and title.size == 40.0
    body = _body_shape(slide).text.paragraphs
    assert [p.to_plain_text() for p in body] == ["First point", "Second point"]
    assert body[0].runs[0].italic is True


def test_editing_body_bullet_updates_model(outline_ws: LecternWorkspace) -> None:
    outline = outline_ws.outline_editor
    _replace_outline_text(outline, "Second point", "Second point, revised")

    body = _body_shape(outline_ws.presentation.slides[0]).text.paragraphs
    assert [p.to_plain_text() for p in body] == ["First point", "Second point, revised"]
    assert body[1].level == 1
    assert body[1].runs[0].color == "#FF0000"


def test_adding_body_bullet_line(outline_ws: LecternWorkspace) -> None:
    outline = outline_ws.outline_editor
    _replace_outline_text(outline, "    • Second point", "    • Second point\n    • Third point")

    body = _body_shape(outline_ws.presentation.slides[0]).text.paragraphs
    assert [p.to_plain_text() for p in body] == ["First point", "Second point", "Third point"]


def test_outline_cursor_slide_switch_is_deferred(outline_ws: LecternWorkspace, qapp) -> None:
    outline = outline_ws.outline_editor
    selected: list[int] = []
    outline.slide_selected.connect(selected.append)
    doc = outline.editor.document()
    target = next(
        doc.findBlockByNumber(i)
        for i in range(doc.blockCount())
        if doc.findBlockByNumber(i).text().startswith("[2]")
    )
    cursor = outline.editor.textCursor()
    cursor.setPosition(target.position())

    outline.editor.setTextCursor(cursor)
    assert selected == []
    qapp.processEvents()

    assert selected == [1]
