"""Issue #448: Phase 11 acceptance — prolonged-operation stress across Quire, Ledger, Lectern.

Each cycle opens a real corpus document, edits, formats, copies/pastes, switches
views/sheets/slides, undoes/redoes, opens Print Preview, saves, re-opens and closes.
The crash handler writes to a temporary crash.log which must stay empty, and any
uncaught Python exception raised inside Qt callbacks fails the test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from atboffice.core.window_manager import WindowManager

DOCS = Path(__file__).resolve().parents[1] / "docs"
CYCLES = 3

QUIRE_DOCS = [
    DOCS / "word/docx/openxml-sdk__bullet-complex.docx",
    DOCS / "word/docx/libreoffice__textframe-borders.docx",
]
LEDGER_DOCS = [
    DOCS / "excel/xlsx/libreoffice__tablerefsnamed.xlsx",
    DOCS / "excel/xlsx/libreoffice__tdf133595.xlsx",
]
LECTERN_DOCS = [
    DOCS / "powerpoint/pptx/libreoffice__bnc887230.pptx",
    DOCS / "powerpoint/pptx/libreoffice__TextFittingComparisonWithMSO_3.pptx",
]


@pytest.fixture
def guarded(qapp, tmp_path, monkeypatch):
    """Collect uncaught exceptions and crash.log output; silence modal message boxes."""
    from atboffice.core.diagnostics import CrashDiagnostics

    errors: list[str] = []
    previous_hook = sys.excepthook

    def hook(exc_type, exc, tb):
        errors.append(f"{exc_type.__name__}: {exc}")

    sys.excepthook = hook
    crash = CrashDiagnostics(tmp_path / "crash.log")
    crash.enable()
    for name in ("critical", "warning", "information"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    WindowManager.reset_instance()
    yield errors
    wm = WindowManager.get_instance()
    wm._is_quitting = True
    for win in list(wm.active_windows):
        win.set_modified(False)
        win.close()
    qapp.processEvents()
    WindowManager.reset_instance()
    sys.excepthook = previous_hook
    crash.disable()
    log = tmp_path / "crash.log"
    assert not log.exists() or log.read_text(encoding="utf-8").strip() == "", log.read_text()
    assert errors == []


def _existing(paths: list[Path]) -> list[Path]:
    found = [p for p in paths if p.exists()]
    if not found:
        pytest.skip("corpus documents not available")
    return found


def _finish(qapp, win, tmp_path: Path, suffix: str, cycle: int) -> Path:
    """Print preview, save, close: shared tail of every cycle."""
    panel = win.open_print_preview_panel()
    qapp.processEvents()
    assert panel.isVisible()
    panel.set_view("all")
    panel.close_preview()
    target = tmp_path / f"out_{cycle}{suffix}"
    win._compat_confirmed = True
    assert win.save_file(target, confirm_overwrite=False) is True
    assert target.stat().st_size > 0
    win.set_modified(False)
    win.close()
    qapp.processEvents()
    return target


def test_quire_prolonged_operation_stress(qapp, guarded, tmp_path, monkeypatch):
    from atboffice.modules.writer.views.view_modes import ViewMode
    from atboffice.ui.shell.quire_window import QuireWindow

    for cycle in range(CYCLES):
        for src in _existing(QUIRE_DOCS):
            win = QuireWindow()
            win.resize(1100, 800)
            win.show()
            assert win.open_file(src) is True
            canvas = win.writer_view.canvas_view
            canvas.controller.insert_text(f"Stress {cycle} ")
            canvas.controller.select_all()
            win.copy()
            win.paste()  # replaces the selection with the copied content
            for mode in (ViewMode.NORMAL, ViewMode.WEB, ViewMode.READING, ViewMode.PRINT):
                win.switch_view_mode(mode)
                qapp.processEvents()
            for _ in range(3):
                win.undo()
            for _ in range(2):
                win.redo()
            target = _finish(qapp, win, tmp_path, ".docx", cycle)
            again = QuireWindow()
            assert again.open_file(target) is True
            again.set_modified(False)
            again.close()
            qapp.processEvents()


def test_ledger_prolonged_operation_stress(qapp, guarded, tmp_path):
    from atboffice.ui.shell.ledger_window import LedgerWindow

    for cycle in range(CYCLES):
        for src in _existing(LEDGER_DOCS):
            win = LedgerWindow()
            win.resize(1100, 800)
            win.show()
            assert win.open_file(src) is True
            view = win.spreadsheet_view
            model = view.model
            model.set_cell_value(0, 0, f"Stress {cycle}")
            # Format painter from a filled cell onto empty cells
            view.grid.selection.select_cell(0, 0)
            win.toggle_format_painter()
            win.apply_format_painter_to_range(40, 5, 45, 8)
            if getattr(win, "_format_painter_active", False):
                win.toggle_format_painter()
            view.grid.selection.select_cell(0, 0)
            win.copy()
            view.grid.selection.select_cell(50, 2)
            win.paste()
            sheets = len(view.workbook.sheets)
            for idx in list(range(sheets)) + [0]:
                view.set_active_sheet_index(idx)
                qapp.processEvents()
            for mode in ("page_break", "page_layout", "normal"):
                try:
                    win.set_view_mode(mode)
                except ValueError:
                    continue
                qapp.processEvents()
            for _ in range(3):
                win.undo()
            for _ in range(2):
                win.redo()
            target = _finish(qapp, win, tmp_path, ".xlsx", cycle)
            again = LedgerWindow()
            assert again.open_file(target) is True
            again.set_modified(False)
            again.close()
            qapp.processEvents()


def test_lectern_prolonged_operation_stress(qapp, guarded, tmp_path):
    from atboffice.ui.shell.lectern_window import LecternWindow

    for cycle in range(CYCLES):
        for src in _existing(LECTERN_DOCS):
            win = LecternWindow()
            win.resize(1100, 800)
            win.show()
            assert win.open_file(src) is True
            pv = win.presentation_view
            pv.presentation.add_slide("text")
            pv.workspace.set_current_slide(len(pv.presentation.slides) - 1)
            win.copy()
            win.paste()
            for idx in range(len(pv.presentation.slides)):
                pv.workspace.set_current_slide(idx)
                qapp.processEvents()
            for mode in ("sorter", "notes", "normal"):
                win.set_view_mode(mode)
                qapp.processEvents()
            for _ in range(3):
                win.undo()
            for _ in range(2):
                win.redo()
            target = _finish(qapp, win, tmp_path, ".pptx", cycle)
            again = LecternWindow()
            assert again.open_file(target) is True
            again.set_modified(False)
            again.close()
            qapp.processEvents()


def test_start_center_cross_app_round_robin(qapp, guarded):
    """Open each app from the Start Center repeatedly without leaking windows."""
    from atboffice.ui.shell.lectern_window import LecternWindow
    from atboffice.ui.shell.ledger_window import LedgerWindow
    from atboffice.ui.shell.quire_window import QuireWindow

    wm = WindowManager.get_instance()
    for _ in range(CYCLES):
        for cls in (QuireWindow, LedgerWindow, LecternWindow):
            win = cls()
            wm.register_window(win)
            win.show()
            qapp.processEvents()
            win.close()
            qapp.processEvents()
    qapp.processEvents()
    assert wm._closing_windows == []


# ---------------------------------------------------------------- UI control audit


def _visible_menu_actions(win) -> set:
    out: set = set()

    def walk(menu) -> None:
        for act in menu.actions():
            if act.menu() is not None:
                if act.isVisible():
                    walk(act.menu())
            elif act.isVisible() and not act.isSeparator():
                out.add(act)

    for act in win.menuBar().actions():
        if act.menu() is not None and act.isVisible():
            walk(act.menu())
    return out


def _visible_actions(win) -> set:
    from PySide6.QtWidgets import QToolBar

    acts = _visible_menu_actions(win)
    for tb in win.findChildren(QToolBar):
        acts.update(a for a in tb.actions() if not a.isSeparator())
    return acts


def _window_classes():
    from atboffice.ui.shell.lectern_window import LecternWindow
    from atboffice.ui.shell.ledger_window import LedgerWindow
    from atboffice.ui.shell.quire_window import QuireWindow

    return [QuireWindow, LedgerWindow, LecternWindow]


@pytest.mark.parametrize("index", [0, 1, 2], ids=["quire", "ledger", "lectern"])
def test_no_visible_command_falls_back_to_not_wired_toast(qapp, guarded, index):
    win = _window_classes()[index]()
    reg = win.action_registry
    by_qaction = {id(a): aid for aid, a in reg._actions.items()}
    unwired = []
    for act in _visible_actions(win):
        aid = by_qaction.get(id(act))
        if aid is None:
            continue
        spec = reg.get_spec(aid)
        canonical = reg._specs.get(reg.resolve_id(aid))
        handled = spec.handler is not None or (
            canonical is not None and canonical.handler is not None
        )
        if not handled and not spec.disabled_reason and aid not in reg._whitelist_actions:
            unwired.append(aid)
    assert unwired == []
    win.close()


def test_alias_qaction_runs_canonical_command(qapp, guarded):
    from atboffice.modules.writer.views.view_modes import ViewMode
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    win.show()
    reg = win.action_registry
    alias_action = reg._actions["viewReading"]
    assert alias_action is not reg._actions["view_reading"]
    alias_action.trigger()
    assert win.writer_view.canvas_view.view_mode == ViewMode.READING
    assert "正在联调中" not in win.statusBar().currentMessage()
    reg._actions["headerFooter"].trigger()
    assert win.writer_view.canvas_view.view_mode == ViewMode.PRINT
    assert win.writer_view.canvas_view.hf_edit_kind == "hdr"
    win.close()


@pytest.mark.parametrize("index", [0, 1, 2], ids=["quire", "ledger", "lectern"])
def test_menu_actions_fire_their_command_exactly_once(qapp, guarded, monkeypatch, index):
    from PySide6.QtWidgets import QDialog, QFileDialog

    monkeypatch.setattr(QDialog, "exec", lambda self, *a: 0)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    win = _window_classes()[index]()
    reg = win.action_registry
    by_qaction = {id(a): aid for aid, a in reg._actions.items()}
    duplicates = []
    for act in _visible_menu_actions(win):
        aid = by_qaction.get(id(act))
        if aid is None or not act.isEnabled():
            continue
        spec = reg.get_spec(aid)
        if spec.handler is None:
            continue
        calls: list[int] = []
        original = spec.handler
        spec.handler = lambda calls=calls: calls.append(1)
        try:
            act.trigger()
        finally:
            spec.handler = original
        if len(calls) != 1:
            duplicates.append((aid, len(calls)))
    assert duplicates == []
    win.set_modified(False)
    win.close()
