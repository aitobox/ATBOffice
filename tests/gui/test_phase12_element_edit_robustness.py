"""Phase 12 Wave 1 gate: open real docx/xlsx/pptx, insert elements, edit, undo, save, reopen."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from atboffice.core.diagnostics import CrashDiagnostics
from atboffice.core.window_manager import WindowManager
from atboffice.modules.writer.models.document import Paragraph, Table, all_stories, plain_text
from atboffice.modules.writer.models.drawing import ChartItem, PictureItem, ShapeItem

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
    popups: list[tuple[str, str]] = []
    prev_hook = sys.excepthook

    def hook(exc_type, exc, _tb):
        errors.append(f"{exc_type.__name__}: {exc}")

    sys.excepthook = hook
    crash = CrashDiagnostics(tmp_path / "crash.log")
    crash.enable()

    def _record_popup(kind: str):
        def _handler(*args, **kwargs):
            title = str(args[1]) if len(args) > 1 else str(kwargs.get("title", ""))
            text = str(args[2]) if len(args) > 2 else str(kwargs.get("text", ""))
            popups.append((kind, f"{title}: {text}"))
            return QMessageBox.StandardButton.Ok

        return _handler

    monkeypatch.setattr(QMessageBox, "critical", _record_popup("critical"))
    monkeypatch.setattr(QMessageBox, "warning", _record_popup("warning"))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Phase12", True))
    WindowManager.reset_instance()
    try:
        yield errors, tmp_path
    finally:
        try:
            wm = WindowManager.get_instance()
            wm._is_quitting = True
            for win in list(wm.active_windows):
                win.set_modified(False)
                win.close()
            qapp.processEvents()
            WindowManager.reset_instance()
        finally:
            sys.excepthook = prev_hook
            crash.disable()
    log = tmp_path / "crash.log"
    if log.exists():
        log_text = log.read_text(encoding="utf-8")
        assert log_text.strip() == "", log_text
    assert errors == []
    assert popups == []


def _png_bytes(tmp_path: Path) -> tuple[Path, bytes]:
    img = QImage(16, 16, QImage.Format.Format_RGBA8888)
    img.fill(QColor("#336699"))
    p = tmp_path / "probe.png"
    img.save(str(p), "PNG")
    return p, p.read_bytes()


def _quire_tables(doc) -> list[Table]:
    return [b for st in all_stories(doc) for b in st.blocks if isinstance(b, Table)]


def _quire_shapes(doc) -> list[ShapeItem]:
    return [
        r for st in all_stories(doc) for p in st.paras for r in p.runs if isinstance(r, ShapeItem)
    ]


def _quire_pics(doc) -> list[PictureItem]:
    return [
        r
        for st in all_stories(doc)
        for p in st.paras
        for r in p.runs
        if isinstance(r, PictureItem) and not isinstance(r, (ShapeItem, ChartItem))
    ]


def test_quire_open_insert_elements_edit_undo_save(qapp, guarded) -> None:
    from atboffice.ui.shell.quire_window import QuireWindow

    _errors, tmp_path = guarded
    _, png = _png_bytes(tmp_path)
    for idx, src in enumerate(QUIRE_FILES):
        assert src.exists(), f"Missing corpus fixture: {src}"
        win = QuireWindow()
        win.resize(1100, 800)
        win.show()
        assert win.open_file(src) is True
        canvas = win.writer_view.canvas_view
        initial_tables = len(_quire_tables(canvas.doc))
        initial_shapes = len(_quire_shapes(canvas.doc))
        initial_pics = len(_quire_pics(canvas.doc))

        canvas.insert_table(2, 2)
        win.insert_shape("rect")
        win.insert_shape("textbox")
        assert win.insert_image_bytes(png, "png", "probe") is True
        canvas.insert_comment(author="Tester", text="Phase12")
        win.writer_view.review_pane.refresh_items()
        QTest.mouseClick(
            canvas.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(300, 200),
        )
        QTest.keyClicks(canvas, "Wave1Edit ")
        win.action_registry.trigger_action("bold")
        canvas.grab()
        for _ in range(2):
            win.undo()
        for _ in range(2):
            win.redo()

        pre_tables = _quire_tables(canvas.doc)
        pre_shapes = _quire_shapes(canvas.doc)
        pre_pics = _quire_pics(canvas.doc)
        assert len(pre_tables) == initial_tables + 1
        assert len(pre_shapes) == initial_shapes + 2
        assert len(pre_pics) == initial_pics + 1
        assert any(
            "Phase12" in plain_text(b)
            for cm in canvas.doc.comments.values()
            for b in getattr(cm, "blocks", [])
        )
        assert any("Wave1Edit" in plain_text(p) for st in all_stories(canvas.doc) for p in st.paras)

        out = tmp_path / f"quire_{idx}.docx"
        win._compat_confirmed = True
        assert win.save_file(out, confirm_overwrite=False) is True
        assert out.stat().st_size > 0
        again = QuireWindow()
        assert again.open_file(out) is True
        reopened = again.writer_view.canvas_view.doc

        reopened_tables = _quire_tables(reopened)
        assert len(reopened_tables) == len(pre_tables)
        assert len(reopened_tables[-1].rows) == 2
        assert len(reopened_tables[-1].rows[0].cells) == 2

        reopened_shapes = _quire_shapes(reopened)
        assert len(reopened_shapes) == len(pre_shapes)
        assert any(s.geometry == "rect" and s.story is None for s in reopened_shapes)
        pre_tb_texts = {
            "".join(plain_text(b) for b in s.story.blocks if isinstance(b, Paragraph))
            for s in pre_shapes
            if s.story is not None
        }
        reopened_tb_texts = {
            "".join(plain_text(b) for b in s.story.blocks if isinstance(b, Paragraph))
            for s in reopened_shapes
            if s.story is not None
        }
        assert pre_tb_texts <= reopened_tb_texts
        assert any(t.strip() for t in reopened_tb_texts)

        reopened_pics = _quire_pics(reopened)
        assert len(reopened_pics) == len(pre_pics)
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
            assert reopened_pics[-1].image_part in names
            assert zf.read(reopened_pics[-1].image_part) == png

        assert any(
            "Phase12" in plain_text(b)
            for cm in reopened.comments.values()
            for b in getattr(cm, "blocks", [])
        )
        assert any("Wave1Edit" in plain_text(p) for st in all_stories(reopened) for p in st.paras)

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

    for idx, src in enumerate(LEDGER_FILES):
        assert src.exists(), f"Missing corpus fixture: {src}"
        win = LedgerWindow()
        win.resize(1100, 800)
        win.show()
        assert win.open_file(src) is True
        win.insert_shape("rect")
        win.insert_textbox()
        win.insert_picture(str(img_path))
        win.spreadsheet_view.selection.select_cell(0, 0)
        win.insert_comment()
        win.spreadsheet_view.model.set_cell_value(0, 0, '=INDIRECT("B1")')
        win.spreadsheet_view.grab()
        for _ in range(2):
            win.undo()
        for _ in range(2):
            win.redo()

        pre_sheet = win.spreadsheet_view.model
        pre_kinds = [d.kind for d in pre_sheet.drawings]
        pre_cm = pre_sheet.get_comment(0, 0)
        pre_cell = pre_sheet.get_cell(0, 0)
        assert len(pre_kinds) >= 3
        assert pre_cm is not None and pre_cm.text == "Cell note"
        assert pre_cell is not None and (
            pre_cell.formula == '=INDIRECT("B1")' or pre_cell.value == '=INDIRECT("B1")'
        )

        out = tmp_path / f"ledger_{idx}.xlsx"
        win._compat_confirmed = True
        assert win.save_file(out, confirm_overwrite=False) is True
        assert out.stat().st_size > 0
        again = LedgerWindow()
        assert again.open_file(out) is True
        post_sheet = again.spreadsheet_view.model

        assert [d.kind for d in post_sheet.drawings] == pre_kinds
        post_cm = post_sheet.get_comment(0, 0)
        assert post_cm is not None and post_cm.text == "Cell note"
        post_cell = post_sheet.get_cell(0, 0)
        assert post_cell is not None and post_cell.formula == pre_cell.formula
        assert post_cell.value == pre_cell.value

        for w in (win, again):
            w.set_modified(False)
            w.close()
        qapp.processEvents()


def test_lectern_open_insert_elements_edit_undo_save(qapp, guarded) -> None:
    from atboffice.ui.shell.lectern_window import LecternWindow

    _errors, tmp_path = guarded
    _, png = _png_bytes(tmp_path)
    for idx, src in enumerate(LECTERN_FILES):
        assert src.exists(), f"Missing corpus fixture: {src}"
        win = LecternWindow()
        win.resize(1100, 800)
        win.show()
        assert win.open_file(src) is True
        initial_slides = len(win.presentation.slides)
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
        canvas.insert_comment_at(100.0, 100.0, text="Slide comment")
        if canvas._active_card is not None:
            canvas._active_card.close()
            canvas._active_card = None
        win.insert_wordart(png, {"text": "Wave1"})
        win.flush_pending_edits()
        ws.grab()
        for _ in range(2):
            win.undo()
        for _ in range(2):
            win.redo()

        pre_slides = len(win.presentation.slides)
        assert pre_slides > initial_slides
        pre_added = win.presentation.slides[-1]
        pre_shapes = len(pre_added.shapes)
        pre_comments = [cm.text for cm in pre_added.comments]

        out = tmp_path / f"lectern_{idx}.pptx"
        win._compat_confirmed = True
        assert win.save_file(out, confirm_overwrite=False) is True
        assert out.stat().st_size > 0
        again = LecternWindow()
        assert again.open_file(out) is True
        assert len(again.presentation.slides) == pre_slides > initial_slides
        post_added = again.presentation.slides[-1]
        assert len(post_added.shapes) == pre_shapes
        assert any(s.geom == "rect" for s in post_added.shapes)
        assert any(s.type == "table" and s.tbl is not None for s in post_added.shapes)
        assert any(s.type == "image" or s.media is not None for s in post_added.shapes)
        assert any(s.type == "chart" or s.chart is not None for s in post_added.shapes)
        assert any(s.type == "smartart" or s.sa is not None for s in post_added.shapes)
        assert [cm.text for cm in post_added.comments] == pre_comments

        for w in (win, again):
            w.set_modified(False)
            w.close()
        qapp.processEvents()
