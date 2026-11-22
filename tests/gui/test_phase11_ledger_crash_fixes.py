"""Regression tests for issue #439: Ledger focus theft, null-cell formatting, selection wiring."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.object_layer import FloatingObject
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.main_window import MainWindow


class _KeyRecorder(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.keys: list[int] = []

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        # Shortcut keys (Copy/Paste) reach the grid as ShortcutOverride and are then
        # dispatched to the window's actions; plain keys arrive as KeyPress.
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride):
            self.keys.append(event.key())
        return False


@pytest.fixture
def ledger(qtbot) -> LedgerWindow:
    win = LedgerWindow()
    qtbot.addWidget(win)
    win.resize(900, 600)
    win.show()
    qtbot.waitExposed(win)
    yield win
    win.set_modified(False)


def _select(win: LedgerWindow, r1: int, c1: int, r2: int, c2: int) -> None:
    from atboffice.modules.spreadsheet.models.selection_model import SelectionRange

    sel = win.spreadsheet_view.selection
    sel.clear()
    sel.add_range(SelectionRange(r1, c1, r2, c2))
    sel.set_active_cell(r1, c1)


# ---------------------------------------------------------------------------
# SpreadsheetObjectLayer focus & key handling
# ---------------------------------------------------------------------------


def test_object_layer_never_takes_click_focus(ledger: LedgerWindow) -> None:
    layer = ledger.spreadsheet_view.object_layer
    assert layer.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_clicking_empty_cell_returns_focus_to_grid(ledger: LedgerWindow, qtbot) -> None:
    view = ledger.spreadsheet_view
    layer = view.object_layer
    layer.setFocus()

    qtbot.mouseClick(layer, Qt.MouseButton.LeftButton, pos=QPoint(250, 120))

    assert not layer.hasFocus()


@pytest.mark.parametrize(
    ("key", "modifiers", "text"),
    [
        (Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, "a"),
        (Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier, ""),
        (Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier, ""),
        (Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier, ""),
    ],
)
def test_keys_without_selected_object_are_forwarded_to_grid(
    ledger: LedgerWindow, key, modifiers, text
) -> None:
    view = ledger.spreadsheet_view
    layer = view.object_layer
    recorder = _KeyRecorder()
    view.grid.installEventFilter(recorder)

    event = QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text)
    layer.keyPressEvent(event)  # must not raise AttributeError

    assert key in recorder.keys
    view.grid.removeEventFilter(recorder)


def test_copy_paste_selected_object_uses_standard_keys(ledger: LedgerWindow) -> None:
    layer = ledger.spreadsheet_view.object_layer
    obj = FloatingObject(id=1, name="Shape 1")
    layer.internal_objects = [obj]
    if layer.model is not None and hasattr(layer.model, "drawings"):
        layer.model.drawings = [obj]
    layer.select_object(obj)

    copy_evt = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier
    )
    layer.keyPressEvent(copy_evt)
    assert layer._clipboard_object is not None

    paste_evt = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier
    )
    layer.keyPressEvent(paste_evt)
    assert len(layer.objects) == 2


# ---------------------------------------------------------------------------
# Formatting on empty cells
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "check"),
    [
        (lambda w: w._apply_font_family("Arial"), lambda c: c.font_family == "Arial"),
        (lambda w: w._apply_font_size("14"), lambda c: c.font_size == 14),
        (lambda w: w._toggle_bold(), lambda c: c.bold is True),
        (lambda w: w._toggle_italic(), lambda c: c.italic is True),
        (lambda w: w._toggle_underline(), lambda c: bool(c.underline)),
        (lambda w: w.set_horizontal_alignment("right"), lambda c: c.align_h == "right"),
        (lambda w: w.change_cell_indent(1), lambda c: c.indent == 1),
        (lambda w: w.apply_number_format("0.00"), lambda c: c.format_code == "0.00"),
        (lambda w: w.change_decimal_places(1), lambda c: c.format_code not in (None, "")),
        (lambda w: w._apply_font_color("#FF0000"), lambda c: bool(c.fg_color)),
        (lambda w: w._apply_fill_color("#00FF00"), lambda c: bool(c.bg_color)),
    ],
)
def test_formatting_empty_cells_does_not_crash(ledger: LedgerWindow, action, check) -> None:
    model = ledger.spreadsheet_view.model
    assert model.get_cell(5, 5) is None
    _select(ledger, 5, 5, 6, 6)

    action(ledger)

    for r in (5, 6):
        for c in (5, 6):
            cell = model.get_cell(r, c)
            assert cell is not None
            assert check(cell)


def test_merge_and_center_on_empty_cells(ledger: LedgerWindow) -> None:
    _select(ledger, 3, 3, 4, 5)
    ledger.toggle_merge_and_center()
    assert ledger.spreadsheet_view.model.get_cell(3, 3).align_h == "center"


def test_format_painter_onto_empty_cells(ledger: LedgerWindow) -> None:
    ledger._format_painter_active = True
    ledger._format_painter_source = CellData(bold=True, italic=True, bg_color="#FFFF00")

    ledger.apply_format_painter_to_range(10, 1, 11, 2)

    cell = ledger.spreadsheet_view.model.get_cell(11, 2)
    assert cell is not None and cell.bold and cell.italic


def test_sheet_model_ensure_cell(qapp) -> None:
    sheet = SheetDataModel()
    cell = sheet.ensure_cell(2, 3)
    assert isinstance(cell, CellData)
    assert sheet.get_cell(2, 3) is cell
    assert sheet.ensure_cell(2, 3) is cell


@pytest.mark.parametrize(
    "method", ["_toggle_bold", "_toggle_italic", "_toggle_underline"]
)
def test_main_window_formatting_empty_cells(qtbot, method: str) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    if not hasattr(win, method):
        pytest.skip(f"MainWindow has no {method}")
    from atboffice.modules.spreadsheet.models.selection_model import SelectionRange

    sel = win.spreadsheet_view.selection
    sel.clear()
    sel.add_range(SelectionRange(7, 7, 8, 8))
    sel.set_active_cell(7, 7)

    getattr(win, method)()

    assert win.spreadsheet_view.model.get_cell(8, 8) is not None


# ---------------------------------------------------------------------------
# Selection signal wiring across loads and sheet switches
# ---------------------------------------------------------------------------


def _two_sheet_xlsx(path: Path) -> Path:
    wb = WorkbookModel()
    wb.active_sheet.set_cell_value(0, 0, 1)
    wb.add_sheet(name="Second")
    wb.sheets[1].set_cell_value(0, 0, 2)
    write_xlsx(wb, path)
    return path


def test_status_updates_after_open_and_sheet_switch(
    ledger: LedgerWindow, tmp_path: Path, monkeypatch
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        ledger.status_bar, "update_calculation", lambda *a, **k: calls.append(1)
    )
    path = _two_sheet_xlsx(tmp_path / "two.xlsx")
    assert ledger.open_file(path) is True

    calls.clear()
    ledger.spreadsheet_view.selection.select_cell(2, 2)
    assert calls, "status bar must update after opening a workbook"

    ledger.spreadsheet_view.set_active_sheet_index(1)
    calls.clear()
    ledger.spreadsheet_view.selection.select_cell(3, 3)
    assert calls, "status bar must update after switching sheets"


def test_selection_signals_are_not_duplicated(ledger: LedgerWindow) -> None:
    view = ledger.spreadsheet_view
    view.workbook.add_sheet(name="Extra")
    hits: list[int] = []
    view.selection_changed.connect(lambda: hits.append(1))

    for idx in (1, 0, 1, 0):
        view.set_active_sheet_index(idx)
    hits.clear()
    view.selection.select_cell(4, 4)

    assert len(hits) == 1


def test_old_sheet_selection_no_longer_drives_status(ledger: LedgerWindow) -> None:
    view = ledger.spreadsheet_view
    first_sel = view.selection
    view.workbook.add_sheet(name="Other")
    view.set_active_sheet_index(1)
    hits: list[int] = []
    view.selection_changed.connect(lambda: hits.append(1))

    first_sel.select_cell(9, 9)

    assert hits == []


# ---------------------------------------------------------------------------
# GridViewport mouseMoveEvent hardening
# ---------------------------------------------------------------------------


def _move_event(x: float, y: float, buttons=Qt.MouseButton.NoButton) -> QMouseEvent:
    return QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(x, y),
        QPointF(x, y),
        Qt.MouseButton.NoButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def test_hover_state_reset_on_sheet_switch(ledger: LedgerWindow) -> None:
    view = ledger.spreadsheet_view
    view.grid._hover_comment_cell = (1, 1)
    view.workbook.add_sheet(name="Fresh")

    view.set_active_sheet_index(1)

    assert view.grid._hover_comment_cell is None


def test_stale_drag_is_cancelled_on_move(ledger: LedgerWindow) -> None:
    from atboffice.modules.spreadsheet.views.grid_viewport import HitZone

    grid = ledger.spreadsheet_view.grid
    grid._drag_mode = HitZone.CELL
    grid._drag_start_pos = None
    grid._drag_moved = False

    grid.mouseMoveEvent(_move_event(200, 120, Qt.MouseButton.LeftButton))

    assert grid._drag_mode == HitZone.NONE


def test_mouse_move_after_workbook_replacement(ledger: LedgerWindow) -> None:
    view = ledger.spreadsheet_view
    view.workbook = WorkbookModel()
    for x in range(50, 400, 40):
        view.grid.mouseMoveEvent(_move_event(x, x / 2))
