"""Phase 12 Wave 1 gate: open real docx/xlsx/pptx, insert elements, edit, undo, save, reopen."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from atboffice.core.diagnostics import CrashDiagnostics
from atboffice.core.window_manager import WindowManager

DOCS = Path(__file__).resolve().parents[1] / "docs"

QUIRE_FILES = [
    DOCS / "word/docx/libreoffice__A019_min.docx",
    DOCS / "word/docx/openxml-sdk__bullet-complex.docx",
]
LEDGER_FILES = [
    DOCS / "excel/xlsx/libreoffice__cell-value.xlsx",
    DOCS / "excel/xlsx/libreoffice__totalsRowFunction.xlsx",
]
LECTERN_FILES = [
    DOCS / "powerpoint/pptx/libreoffice__master-slides.pptx",
    DOCS / "powerpoint/pptx/libreoffice__smartart-text.pptx",
]


@pytest.fixture
def guarded(qapp, tmp_path, monkeypatch):
    errors: list[str] = []
    prev_hook = sys.excepthook

    def hook(exc_type, exc, _tb):
        errors.append(f"{exc_type.__name__}: {exc}")

    sys.excepthook = hook
    crash = CrashDiagnostics(tmp_path / "crash.log")
    crash.enable()
    for name in ("critical", "warning", "information"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Phase12", True))
    WindowManager.reset_instance()
    yield errors, tmp_path
    wm = WindowManager.get_instance()
    wm._is_quitting = True
    for win in list(wm.active_windows):
        win.set_modified(False)
        win.close()
    qapp.processEvents()
    WindowManager.reset_instance()
    sys.excepthook = prev_hook
    crash.disable()
    log = tmp_path / "crash.log"
    assert not log.exists() or log.read_text(encoding="utf-8").strip() == "", log.read_text()
    assert errors == []


def _png_bytes(tmp_path: Path) -> tuple[Path, bytes]:
    img = QImage(16, 16, QImage.Format.Format_RGBA8888)
    img.fill(QColor("#336699"))
    p = tmp_path / "probe.png"
    img.save(str(p), "PNG")
    return p, p.read_bytes()


def test_quire_open_insert_elements_edit_undo_save(qapp, guarded) -> None:
    from atboffice.ui.shell.quire_window import QuireWindow

    _errors, tmp_path = guarded
    _, png = _png_bytes(tmp_path)
    for idx, src in enumerate(p for p in QUIRE_FILES if p.exists()):
        win = QuireWindow()
        win.resize(1100, 800)
        win.show()
        assert win.open_file(src) is True
        canvas = win.writer_view.canvas_view
        canvas.insert_table(2, 2)
        win.insert_shape("rect")
        win.insert_shape("textbox")
        win.insert_image_bytes(png, "png", "probe")
        win.writer_view._on_new_comment()
        QTest.mouseClick(
            canvas.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(300, 200),
        )
        QTest.keyClicks(canvas, "Wave1Edit ")
        win.action_registry.trigger_action("bold")
        canvas.grab()
        for _ in range(4):
            win.undo()
        for _ in range(2):
            win.redo()
        out = tmp_path / f"quire_{idx}.docx"
        win._compat_confirmed = True
        assert win.save_file(out, confirm_overwrite=False) is True
        assert out.stat().st_size > 0
        again = QuireWindow()
        assert again.open_file(out) is True
        for w in (win, again):
            w.set_modified(False)
            w.close()
        qapp.processEvents()


def test_ledger_open_insert_elements_edit_undo_save(qapp, guarded, monkeypatch) -> None:
    from atboffice.modules.spreadsheet.dialogs.comment_dialog import CommentDialog
    from atboffice.ui.shell.ledger_window import LedgerWindow

    _errors, tmp_path = guarded
    img_path, _ = _png_bytes(tmp_path)
    monkeypatch.setattr(CommentDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(CommentDialog, "get_text", lambda self: "Cell note")
    monkeypatch.setattr(CommentDialog, "get_author", lambda self: "Tester")

    for idx, src in enumerate(p for p in LEDGER_FILES if p.exists()):
        win = LedgerWindow()
        win.resize(1100, 800)
        win.show()
        assert win.open_file(src) is True
        win.insert_shape("rect")
        win.insert_textbox()
        win.insert_picture(str(img_path))
        win.insert_comment()
        win.spreadsheet_view.model.set_cell_value(0, 0, '=INDIRECT("B1")')
        win.spreadsheet_view.grab()
        for _ in range(3):
            win.undo()
        for _ in range(2):
            win.redo()
        out = tmp_path / f"ledger_{idx}.xlsx"
        win._compat_confirmed = True
        assert win.save_file(out, confirm_overwrite=False) is True
        assert out.stat().st_size > 0
        again = LedgerWindow()
        assert again.open_file(out) is True
        for w in (win, again):
            w.set_modified(False)
            w.close()
        qapp.processEvents()


def test_lectern_open_insert_elements_edit_undo_save(qapp, guarded) -> None:
    from atboffice.ui.shell.lectern_window import LecternWindow

    _errors, tmp_path = guarded
    _, png = _png_bytes(tmp_path)
    for idx, src in enumerate(p for p in LECTERN_FILES if p.exists()):
        win = LecternWindow()
        win.resize(1100, 800)
        win.show()
        assert win.open_file(src) is True
        ws = win.presentation_view.workspace
        canvas = ws.canvas_view
        win.action_registry.trigger_action("newSlide")
        win.set_drawing_tool({"kind": "shape", "geom": "rect"})
        QTest.mousePress(
            canvas.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(180, 160),
        )
        QTest.mouseMove(canvas.viewport(), QPoint(300, 240))
        QTest.mouseRelease(
            canvas.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(300, 240),
        )
        win.insert_table(2, 2)
        win.insert_image_bytes(png, "png", "probe")
        win.insert_chart(edit_data=False)
        ws.insert_smartart("list")
        win.action_registry.trigger_action("insertComment")
        win.insert_wordart(png, {"text": "Wave1"})
        win.flush_pending_edits()
        ws.grab()
        for _ in range(4):
            win.undo()
        for _ in range(2):
            win.redo()
        out = tmp_path / f"lectern_{idx}.pptx"
        win._compat_confirmed = True
        assert win.save_file(out, confirm_overwrite=False) is True
        assert out.stat().st_size > 0
        again = LecternWindow()
        assert again.open_file(out) is True
        for w in (win, again):
            w.set_modified(False)
            w.close()
        qapp.processEvents()
