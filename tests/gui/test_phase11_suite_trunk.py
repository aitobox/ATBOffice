"""Issue #446: shared Clip Art / WordArt, Office Clipboard, Undo history, Start Center."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtWidgets import QDialog, QMenu, QMessageBox

from atboffice.modules.common.clipart_dialog import (
    _try_insert_clipart_into_window,
    search_clipart,
)
from atboffice.modules.common.wordart_gallery import (
    WarpMode,
    WordArtStyle,
    _try_insert_into_window,
)
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow

WINDOWS = [QuireWindow, LedgerWindow, LecternWindow]


def _wordart(text: str = "Hello", warp: str = WarpMode.ARCH_UP) -> dict:
    return {
        "style": WordArtStyle(id=3, name="s", warp=warp),
        "text": text,
        "font": "Arial",
        "size": 36,
        "bold": True,
        "italic": False,
    }


def _picture_count(win) -> int:
    if isinstance(win, QuireWindow):
        from atboffice.modules.writer.models.document import all_paragraphs

        return sum(
            1
            for p in all_paragraphs(win.writer_view.canvas_view.doc)
            for r in p.runs
            if type(r).__name__ == "PictureItem"
        )
    if isinstance(win, LedgerWindow):
        return sum(1 for o in win.spreadsheet_view.model.drawings if o.kind == "image")
    return sum(1 for s in win.presentation_view.workspace.current_slide.shapes if s.type == "image")


# ---------------------------------------------------------------- Clip Art / WordArt
@pytest.mark.parametrize("window_cls", WINDOWS)
def test_clipart_and_wordart_insert_into_every_editor(qtbot, window_cls) -> None:
    win = window_cls()
    qtbot.addWidget(win)
    before = _picture_count(win)
    assert _try_insert_clipart_into_window(win, search_clipart("")[0])
    assert _try_insert_into_window(win, _wordart())
    assert _picture_count(win) == before + 2
    assert win.is_modified


@pytest.mark.parametrize("window_cls", WINDOWS)
def test_clipart_dialog_path(qtbot, monkeypatch, window_cls) -> None:
    from atboffice.modules.common import clipart_dialog

    win = window_cls()
    qtbot.addWidget(win)
    monkeypatch.setattr(
        clipart_dialog.ClipartDialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    monkeypatch.setattr(
        clipart_dialog.ClipartDialog, "get_selected_clipart", lambda self: search_clipart("")[1]
    )
    before = _picture_count(win)
    win.open_clipart_dialog()
    assert _picture_count(win) == before + 1


def test_wordart_keeps_warp_and_rerenders_in_lectern(qtbot) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    _try_insert_into_window(win, _wordart("Arc"))
    shape = win.presentation_view.workspace.current_slide.shapes[-1]
    assert shape.wordart["style"]["warp"] == WarpMode.ARCH_UP
    media = win.presentation_view.presentation.props["_media_map"]
    before = media[shape.media]
    item = win.presentation_view.workspace.scene.get_shape_item(shape.id)
    win.presentation_view.workspace.scene.clearSelection()
    item.setSelected(True)
    win.action_registry.trigger_action("wa_shape_circle")
    assert shape.wordart["style"]["warp"] == "textCircle"
    assert media[shape.media] != before
    # transparent background, coloured glyphs
    img = QImage.fromData(media[shape.media])
    assert img.hasAlphaChannel() and img.pixelColor(0, 0).alpha() == 0


# ---------------------------------------------------------------- Office Clipboard
def test_clipboard_pane_restores_image(qtbot) -> None:
    from atboffice.ui.panes.clipboard_pane import ClipboardTaskPane, ClipItem

    pane = ClipboardTaskPane()
    qtbot.addWidget(pane)
    img = QImage(20, 10, QImage.Format.Format_ARGB32)
    img.fill(QColor("#FF0000"))
    mime = QMimeData()
    mime.setImageData(img)
    pane.paste_item(ClipItem(item_type="image", mime_data=mime))
    assert QGuiApplication.clipboard().mimeData().hasImage()


@pytest.mark.parametrize("window_cls", WINDOWS)
def test_image_clip_pastes_as_picture(qtbot, window_cls) -> None:
    from atboffice.ui.panes.clipboard_pane import ClipItem

    win = window_cls()
    qtbot.addWidget(win)
    img = QImage(40, 20, QImage.Format.Format_ARGB32)
    img.fill(QColor("#00FF00"))
    mime = QMimeData()
    mime.setImageData(img)
    before = _picture_count(win)
    win._on_clipboard_item_clicked(ClipItem(item_type="image", mime_data=mime))
    assert _picture_count(win) == before + 1


def test_quire_copy_puts_formatted_html(qtbot) -> None:
    from atboffice.modules.writer.models.document import Document, Paragraph, TextItem
    from atboffice.modules.writer.models.properties import RunProperties

    win = QuireWindow()
    qtbot.addWidget(win)
    canvas = win.writer_view.canvas_view
    doc = Document()
    p = Paragraph()
    p.runs = [TextItem("Bold", RunProperties(b=True)), TextItem(" plain")]
    doc.main.blocks = [p]
    canvas.set_document(doc)
    canvas.controller.select_all()
    canvas.copy_selection()
    mime = QGuiApplication.clipboard().mimeData()
    assert mime.text() == "Bold plain"
    assert "<b>Bold</b>" in mime.html()


def test_office_clipboard_menu_and_new_web(qtbot) -> None:
    from atboffice.modules.writer.views.view_modes import ViewMode

    win = QuireWindow()
    qtbot.addWidget(win)
    win.show()
    assert win.action_registry.trigger_action("officeClipboard")
    assert win.task_pane_dock.isVisible()
    assert win.task_pane_dock.current_pane_id() == "clipboard"
    win._on_task_pane_action("new_web")
    assert win.writer_view.canvas_view.view_mode == ViewMode.WEB


# ---------------------------------------------------------------- Undo history
def _undo_menu(win, kind: str) -> QMenu:
    return next(m for m in win.findChildren(QMenu) if m.property("split_aid") == kind)


def test_ledger_undo_dropdown_lists_history_and_undoes_several(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)
    grid = win.spreadsheet_view.grid
    menu = _undo_menu(win, "undo")
    menu.aboutToShow.emit()
    assert [a.isEnabled() for a in menu.actions()] == [False]  # nothing to undo
    for value in ("a", "b", "c"):
        before = grid._snapshot_state()
        grid.model.set_cell_value(0, 0, value)
        grid._commit_undo(before, "edit")
    menu.aboutToShow.emit()
    assert len(menu.actions()) == 3
    menu.actions()[1].trigger()  # undo two steps
    assert grid.model.get_cell_value(0, 0) == "a"
    redo = _undo_menu(win, "redo")
    redo.aboutToShow.emit()
    assert len(redo.actions()) == 2
    redo.actions()[1].trigger()
    assert grid.model.get_cell_value(0, 0) == "c"


def test_quire_undo_dropdown(qtbot) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)
    canvas = win.writer_view.canvas_view
    for i in range(3):
        canvas.run_undoable(lambda i=i: setattr(canvas.doc.sect, "ml", 100.0 + i))
    assert len(win.undo_history("undo")) == 3
    win.undo_steps("undo", 3)
    assert canvas.doc.sect.ml == pytest.approx(90.0)
    assert len(win.undo_history("redo")) == 3


def test_lectern_undo_dropdown_reports_empty(qtbot) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    menu = _undo_menu(win, "undo")
    menu.aboutToShow.emit()
    assert len(menu.actions()) == 1 and not menu.actions()[0].isEnabled()


# ---------------------------------------------------------------- Start Center
def test_start_center_lists_all_templates(qtbot) -> None:
    from atboffice.core.templates import TemplateRegistry
    from atboffice.ui.shell.start_center import StartCenterWindow

    win = StartCenterWindow()
    qtbot.addWidget(win)
    ids = {c.template_id for c in win.template_cards if c.template_id}
    assert ids == {t.id for t in TemplateRegistry.get_instance().list_templates()}
    assert len(ids) == 22


@pytest.mark.parametrize(
    "window_cls,suffix", [(QuireWindow, ".docx"), (LedgerWindow, ".xlsx"), (LecternWindow, ".pptx")]
)
def test_thumbnail_cached_on_save_and_shown(qtbot, tmp_path, window_cls, suffix) -> None:
    from atboffice.core.recent_files import RecentFilesManager
    from atboffice.core.window_manager import WindowManager
    from atboffice.ui.shell.start_center import RecentItemWidget

    wm = WindowManager.get_instance()
    original = wm.recent_files
    wm.recent_files = RecentFilesManager(storage_path=tmp_path / "recent.json")
    try:
        win = window_cls()
        qtbot.addWidget(win)
        target = tmp_path / f"doc{suffix}"
        assert win.save_file(target, confirm_overwrite=False)
        thumb = wm.recent_files.thumbnail_for(target)
        assert thumb.exists() and not QImage(str(thumb)).isNull()
        entry = wm.recent_files.get_entries()[0]
        widget = RecentItemWidget(entry, lambda _p: None, thumbnail=thumb)
        qtbot.addWidget(widget)
        assert widget.has_thumbnail
        wm.recent_files.remove_file(target)
        assert not thumb.exists()
    finally:
        wm.recent_files = original


def test_recovery_drafts_listed_and_discarded(qtbot, tmp_path, monkeypatch) -> None:
    from atboffice.core.recovery_service import list_orphan_drafts
    from atboffice.ui.shell.start_center import StartCenterWindow

    dead_pid = 999_999
    (tmp_path / f"Report_recovery_{dead_pid}.docx").write_bytes(b"x")
    (tmp_path / f"Live_recovery_{os.getpid()}.docx").write_bytes(b"y")
    (tmp_path / "unrelated.txt").write_text("z")
    drafts = list_orphan_drafts(tmp_path)
    assert [d.name for d in drafts] == ["Report"]

    win = StartCenterWindow()
    qtbot.addWidget(win)
    assert win.refresh_recovery_drafts(tmp_path) == 1
    assert win.recovery_box.isVisibleTo(win)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    win._discard_recovery_draft(drafts[0])
    assert not drafts[0].path.exists()
    assert not win.recovery_box.isVisibleTo(win)


# ---------------------------------------------------------------- Command search
def test_command_search_recents_breadcrumbs_typos(qtbot) -> None:
    from atboffice.ui.components import command_search_box as csb

    win = QuireWindow()
    qtbot.addWidget(win)
    box = win.init_command_search_box()
    csb._RECENT_COMMANDS.clear()
    box.execute_action("save")
    assert csb.recent_commands()[0] == "save"
    assert [r.action_id for r in box.recent_results()] == ["save"]
    results = box.search_commands("savw")  # one typo away from "save"
    assert any(r.action_id in ("save", "file_save") for r in results)
    crumbs = {r.action_id: r.breadcrumb for r in box.search_commands("save")}
    assert any(crumbs.values())
    assert csb.within_one_edit("print", "prnt") and not csb.within_one_edit("print", "pt")


# ---------------------------------------------------------------- Scout
def test_scout_is_idle_between_bursts(qtbot) -> None:
    from atboffice.core.action_registry import ActionRegistry
    from atboffice.modules.common.assistant_scout import ScoutWidget

    scout = ScoutWidget()
    qtbot.addWidget(scout)
    assert not scout._idle_timer.isActive()  # not animating while hidden
    scout.show()
    assert scout._idle_timer.isActive()
    scout._end_burst()
    assert not scout._idle_timer.isActive()
    reg = ActionRegistry()
    scout.attach_registry(reg)
    reg.action_triggered.emit("save")
    assert "保存" in scout.balloon.label_text.text()
    assert scout.balloon.btn_search.text() and scout.balloon.btn_hide_scout.text()
    scout.balloon.btn_hide_scout.click()
    assert not scout.isVisible() and not scout._blink_timer.isActive()


# ---------------------------------------------------------------- Compatibility
def test_csv_save_lists_real_losses_and_can_cancel(qtbot, tmp_path, monkeypatch) -> None:
    from atboffice.ui.dialogs.compatibility_dialog import CompatibilityDialog

    win = LedgerWindow()
    qtbot.addWidget(win)
    workbook = win.spreadsheet_view.workbook
    workbook.add_sheet("Second") if hasattr(workbook, "add_sheet") else None
    sheet = win.spreadsheet_view.grid.model
    sheet.set_cell_value(0, 0, 1)
    sheet.ensure_cell(0, 1).formula = "A1*2"
    seen: list[list[str]] = []

    def cancel(dlg):
        seen.append([loss.feature for loss in dlg.losses])
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(CompatibilityDialog, "exec", cancel)
    target = tmp_path / "out.csv"
    assert win.save_file(target, confirm_overwrite=False) is False
    assert not target.exists()
    assert any("公式" in f for f in seen[0])


def test_plain_documents_never_prompt(qtbot, tmp_path, monkeypatch) -> None:
    from atboffice.ui.dialogs.compatibility_dialog import CompatibilityDialog

    def boom(_dlg):
        raise AssertionError("no losses: no dialog")

    monkeypatch.setattr(CompatibilityDialog, "exec", boom)
    win = QuireWindow()
    qtbot.addWidget(win)
    assert win.save_file(tmp_path / "plain.txt", confirm_overwrite=False)


def test_macro_loss_detected() -> None:
    from atboffice.core.compat import macro_loss

    assert macro_loss(Path("a.xlsm"), Path("a.xlsx"))
    assert not macro_loss(Path("a.xlsm"), Path("a.xlsm"))
    assert not macro_loss(None, Path("a.xlsx"))


def test_paper2016_card_describes_classic_toolbars(qtbot) -> None:
    from atboffice.ui.dialogs.theme_dialog import SUITE_THEMES

    desc = dict((k, d) for k, _n, d, _l in SUITE_THEMES)["paper2016"]
    assert "classic menus and toolbars" in desc
