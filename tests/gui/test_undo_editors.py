"""Undo / redo in the three editors (shared undo service, phase 2 of the review)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from atboffice.modules.spreadsheet.models.selection_model import SelectionRange
from atboffice.modules.spreadsheet.models.sheet_model import CellData
from atboffice.modules.writer.models.document import Paragraph, TextItem, ptext
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


@pytest.fixture
def quire(qtbot):
    win = QuireWindow()
    qtbot.addWidget(win)
    win.show()
    canvas = win.writer_view.canvas_view
    canvas.setFocus()
    yield win, canvas
    win.set_modified(False)


@pytest.fixture
def ledger(qtbot):
    win = LedgerWindow()
    qtbot.addWidget(win)
    yield win
    win.set_modified(False)


@pytest.fixture
def lectern(qtbot, qapp):
    win = LecternWindow()
    qtbot.addWidget(win)
    win.show()
    qapp.processEvents()
    yield win
    win.set_modified(False)


def _texts(canvas) -> list[str]:
    return [ptext(b) for b in canvas.doc.main.blocks if isinstance(b, Paragraph)]


# -- Quire ----------------------------------------------------------------------


def test_quire_typing_is_undone_word_by_word(quire) -> None:
    win, canvas = quire
    QTest.keyClicks(canvas, "hello world")
    assert _texts(canvas) == ["hello world"]
    assert len(canvas.history) == 2  # "hello " and "world"
    win.undo()
    assert _texts(canvas) == ["hello "]
    assert canvas.controller.pos.offset == 6
    win.undo()
    assert _texts(canvas) == [""]
    win.redo()
    win.redo()
    assert _texts(canvas) == ["hello world"]


def test_quire_enter_and_backspace_are_undoable(quire) -> None:
    win, canvas = quire
    QTest.keyClicks(canvas, "one")
    QTest.keyClick(canvas, Qt.Key.Key_Return)
    QTest.keyClicks(canvas, "two")
    QTest.keyClick(canvas, Qt.Key.Key_Home)
    QTest.keyClick(canvas, Qt.Key.Key_Backspace)  # merges the paragraphs
    assert _texts(canvas) == ["onetwo"]
    win.undo()
    assert _texts(canvas) == ["one", "two"]
    win.undo()
    win.undo()
    assert _texts(canvas) == ["one"]
    win.redo()
    win.redo()
    win.redo()
    assert _texts(canvas) == ["onetwo"]


def test_quire_typing_step_copies_only_nearby_blocks(quire) -> None:
    win, canvas = quire
    canvas.doc.main.blocks = [Paragraph(runs=[TextItem(f"para {i}")]) for i in range(200)]
    canvas.refresh_layout()
    QTest.keyClicks(canvas, "x")
    step = canvas.history.stack.command(0).data
    assert len(step.before) <= 3
    win.undo()
    assert _texts(canvas)[0] == "para 0"


def test_quire_undo_marks_saved_document_modified(quire) -> None:
    win, canvas = quire
    QTest.keyClicks(canvas, "abc")
    win.set_modified(False)
    win.undo()
    assert win.is_modified


# -- Ledger ---------------------------------------------------------------------


def _type_into(win: LedgerWindow, r: int, c: int, text: str) -> None:
    ec = win.spreadsheet_view.editor_controller
    ec.begin_edit(r, c)
    ec.in_cell_editor.setText(text)
    ec.commit()


def test_ledger_typed_value_is_undoable(ledger) -> None:
    grid = ledger.spreadsheet_view.grid
    _type_into(ledger, 0, 0, "42")
    assert grid.model.get_cell_value(0, 0) == 42
    assert ledger.is_modified
    ledger.undo()
    assert grid.model.get_cell(0, 0) is None
    ledger.redo()
    assert grid.model.get_cell_value(0, 0) == 42


def test_ledger_formatting_is_undoable(ledger) -> None:
    grid = ledger.spreadsheet_view.grid
    grid.model.set_cell(0, 0, CellData(value="x"))
    grid.selection.select_cell(0, 0)
    ledger._toggle_bold()
    assert grid.model.get_cell(0, 0).bold
    ledger.undo()
    assert not grid.model.get_cell(0, 0).bold


def test_ledger_steps_store_only_changed_cells(ledger) -> None:
    grid = ledger.spreadsheet_view.grid
    for r in range(300):
        for c in range(10):
            grid.model.set_cell(r, c, CellData(value=r * c))
    grid.selection.select_cell(5, 5)
    ledger._toggle_bold()
    _type_into(ledger, 7, 7, "x")
    stack = grid.history.stack
    for i in range(stack.count()):
        entry = stack.command(i).data
        assert len(entry["before_delta_cells"]) == 1
        assert len(entry["after_delta_cells"]) == 1


def test_ledger_insert_rows_is_undoable(ledger) -> None:
    grid = ledger.spreadsheet_view.grid
    grid.model.set_cell(2, 0, CellData(value="keep"))
    grid.selection.select_cell(1, 0)
    ledger.insert_rows()
    assert grid.model.get_cell_value(3, 0) == "keep"
    ledger.undo()
    assert grid.model.get_cell_value(2, 0) == "keep"
    assert grid.model.get_cell(3, 0) is None


def test_ledger_history_survives_sheet_switch(ledger) -> None:
    view = ledger.spreadsheet_view
    _type_into(ledger, 0, 0, "first")
    first = view.workbook.active_sheet
    view.workbook.add_sheet()
    view.set_active_sheet_index(1)
    assert ledger.undo_history("undo")
    ledger.undo()
    # Undo switches back to the sheet that was edited.
    assert view.workbook.active_sheet is first
    assert first.get_cell(0, 0) is None


def test_ledger_clear_contents_scope(ledger) -> None:
    grid = ledger.spreadsheet_view.grid
    grid.model.set_cell(0, 0, CellData(value=1))
    grid.model.set_cell(9, 9, CellData(value=2))
    grid.selection.select_cell(0, 0)
    before = grid._snapshot_state(SelectionRange(0, 0, 0, 0))
    assert set(before["before_cells"]) == {(0, 0)}


# -- Lectern --------------------------------------------------------------------


def test_lectern_canvas_move_is_undoable(lectern, qapp) -> None:
    ws = lectern.presentation_view.workspace
    shape = ws.current_slide.shapes[0]
    x0 = shape.x
    item = ws.scene.get_shape_item(shape.id)
    item.setPos(item.pos().x() + 40, item.pos().y())
    ws.scene.contentEdited.emit()
    qapp.processEvents()
    assert lectern.is_modified
    assert lectern.undo_history("undo")
    lectern.undo()
    assert lectern.presentation.slides[0].shapes[0].x == x0
    lectern.redo()
    assert lectern.presentation.slides[0].shapes[0].x == x0 + 40


def test_lectern_command_is_undoable(lectern, qapp) -> None:
    before = len(lectern.presentation.slides)
    assert lectern.action_registry.trigger_action("newSlide")
    qapp.processEvents()
    assert len(lectern.presentation.slides) == before + 1
    lectern.undo()
    assert len(lectern.presentation.slides) == before


def test_lectern_notes_typing_merges_into_one_step(lectern, qapp) -> None:
    ws = lectern.presentation_view.workspace
    for text in ("a", "ab", "abc"):
        ws._on_notes_changed(text)
        qapp.processEvents()
    assert len(lectern.history.service) == 1
    lectern.undo()
    assert lectern.presentation.slides[0].notes in ("", None)


def test_lectern_open_starts_a_new_history(lectern, qapp) -> None:
    from atboffice.modules.presentation.models.presentation import Presentation

    lectern.action_registry.trigger_action("newSlide")
    qapp.processEvents()
    lectern.presentation_view.load_presentation(Presentation.create_new())
    assert lectern.undo_history("undo") == []
