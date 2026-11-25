"""Issue #445: Lectern toast-only stubs, ID collisions and broken insertion are wired."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox, QToolBar, QToolButton

from atboffice.modules.presentation.io.pptx_reader import read_pptx
from atboffice.modules.presentation.io.pptx_writer import write_pptx
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.text import TextBody, TextRun
from atboffice.modules.presentation.tools import table_ops
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.mac_menu import MacMenuBar


@pytest.fixture
def win(qtbot) -> LecternWindow:
    w = LecternWindow()
    qtbot.addWidget(w)
    w.resize(1280, 860)
    w.show()
    return w


def _ws(win: LecternWindow):
    return win.presentation_view.workspace


def _png(path: Path, w: int = 40, h: int = 20, color: str = "#FF0000") -> Path:
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor(color))
    img.setPixelColor(0, 0, QColor("#00FF00"))
    img.save(str(path), "PNG")
    return path


def _add_box(win: LecternWindow, sid: str, x: float, text: str = "") -> Shape:
    shape = Shape(id=sid, type="shape", name=sid, x=x, y=100.0, w=120.0, h=60.0)
    if text:
        shape.text = TextBody.from_plain_text(text)
    win.add_shape(shape)
    return shape


def _select(win: LecternWindow, *ids: str):
    sc = _ws(win).scene
    sc.clearSelection()
    items = []
    for sid in ids:
        item = sc.get_shape_item(sid)
        item.setSelected(True)
        items.append(item)
    return items


def _insert_table(win: LecternWindow, rows: int = 3, cols: int = 3):
    win.insert_table(rows, cols)
    item = _ws(win).scene.selectedItems()[0]
    return item, item.model


# ---------------------------------------------------------------- file & insertion
def test_save_as_prompts_instead_of_overwriting(win, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(win, "save_file", lambda *a, **k: calls.append("save") or True)
    monkeypatch.setattr(win, "save_file_as", lambda *a, **k: calls.append("save_as") or True)
    assert win.action_registry.trigger_action("save_as")
    assert calls == ["save_as"]


def test_insert_chart_creates_real_chart_and_opens_datasheet(win, monkeypatch) -> None:
    from atboffice.modules.presentation.dialogs import datasheet_dialog
    from atboffice.modules.presentation.views.chart_item import ChartGraphicsItem

    opened: list[bool] = []
    monkeypatch.setattr(
        datasheet_dialog.DatasheetDialog,
        "exec",
        lambda self: opened.append(True) or QDialog.DialogCode.Rejected,
    )
    win.action_registry.trigger_action("insertChart")
    shape = _ws(win).current_slide.shapes[-1]
    assert shape.type == "chart" and shape.is_chart
    assert shape.chart["series"], "sample chart data present"
    assert isinstance(_ws(win).scene.get_shape_item(shape.id), ChartGraphicsItem)
    assert opened == [True]


def test_insert_picture_embeds_bytes_with_aspect(win, tmp_path) -> None:
    path = _png(tmp_path / "wide.png", 400, 100)
    item = win.insert_picture_from_file(path)
    shape = item.model
    pres = win.presentation_view.presentation
    assert shape.type == "image"
    assert pres.props["_media_map"][shape.media] == path.read_bytes()
    assert shape.w / shape.h == pytest.approx(4.0, rel=0.01)
    assert win.is_modified


def test_insert_picture_prompts_and_rejects_bad_files(win, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QFileDialog

    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not an image")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(bad), ""))
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a[2]))
    before = len(_ws(win).current_slide.shapes)
    win.action_registry.trigger_action("insert_picture")
    assert warnings and "broken.png" in warnings[0]
    assert len(_ws(win).current_slide.shapes) == before

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    assert win.insert_picture_from_file() is None  # cancelled


def test_clipart_is_routed_to_clipart_gallery(win, monkeypatch) -> None:
    from atboffice.modules.common import clipart_dialog

    monkeypatch.setattr(
        clipart_dialog.ClipartDialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    monkeypatch.setattr(
        clipart_dialog.ClipartDialog,
        "get_selected_clipart",
        lambda self: (
            clipart_dialog.CLIPART_LIBRARY[0]
            if hasattr(clipart_dialog, "CLIPART_LIBRARY")
            else clipart_dialog.search_clipart("")[0]
        ),
    )
    win.action_registry.trigger_action("insertClipArt")
    shape = _ws(win).current_slide.shapes[-1]
    assert shape.type == "image" and shape.media
    assert shape.name.startswith("Clip Art")


def test_wordart_and_clipart_helpers_use_add_shape(win) -> None:
    from atboffice.modules.common.wordart_gallery import WordArtStyle, _try_insert_into_window

    _try_insert_into_window(win, {"style": WordArtStyle(id=0, name="x"), "text": "Hello"})
    assert _ws(win).current_slide.shapes[-1].name.startswith("WordArt")


def test_photo_album_uses_picture_factory(win, tmp_path, monkeypatch) -> None:
    good = _png(tmp_path / "a.png")
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a[2]))
    pres = win.presentation_view.presentation
    before = len(pres.slides)
    win._create_photo_album_slides({"pictures": [str(good), str(tmp_path / "missing.png")]})
    assert len(pres.slides) == before + 1
    assert pres.slides[-1].shapes[0].type == "image"
    assert warnings and "missing.png" in warnings[0]


# ---------------------------------------------------------------- alignment IDs
def test_draw_align_is_distinct_from_paragraph_align(win) -> None:
    reg = win.action_registry
    draw = reg.get_action("draw_align_left")
    para = reg.get_action("alignLeft")
    assert draw is not None and para is not None and draw is not para
    assert para.isCheckable() and not draw.isCheckable()

    a = _add_box(win, "a", 100.0, "text a")
    b = _add_box(win, "b", 400.0, "text b")
    _select(win, "a", "b")
    reg.trigger_action("draw_align_right")
    assert a.x + a.w == pytest.approx(b.x + b.w)
    assert a.text.paragraphs[0].props.get("algn") is None  # text untouched


# ---------------------------------------------------------------- tables
def test_insert_table_has_real_empty_cells(win) -> None:
    _item, shape = _insert_table(win, 2, 3)
    assert table_ops.dims(shape.tbl) == (2, 3)
    assert all(isinstance(c["tx"], TextBody) for r in shape.tbl["rows"] for c in r["cells"])


def test_table_merge_split_insert_delete(win) -> None:
    item, shape = _insert_table(win)
    item.table_sel = (0, 0, 1, 1)
    win.action_registry.trigger_action("tableMergeCells")
    assert table_ops.span_of(shape.tbl, 1, 1) == (0, 0, 1, 1)
    win.action_registry.trigger_action("tableSplitCell")
    assert table_ops.span_of(shape.tbl, 1, 1) == (1, 1, 1, 1)

    item.table_sel = (1, 1, 1, 1)
    win.action_registry.trigger_action("tbl_insert_row_below")
    assert table_ops.dims(shape.tbl) == (4, 3)
    assert shape.h == pytest.approx(table_ops.table_height(shape.tbl))
    width = shape.w
    win.action_registry.trigger_action("tbl_insert_col_left")
    assert table_ops.dims(shape.tbl)[1] == 4
    assert sum(shape.tbl["cols"]) == pytest.approx(width)
    item.table_sel = (0, 0, 0, 0)
    win.action_registry.trigger_action("tbl_delete_row")
    win.action_registry.trigger_action("tbl_delete_col")
    assert table_ops.dims(shape.tbl) == (3, 3)


def test_merge_needs_a_range(win) -> None:
    item, shape = _insert_table(win)
    item.table_sel = (0, 0, 0, 0)
    win.action_registry.trigger_action("tableMergeCells")
    assert all(not c.get("gs") for c in shape.tbl["rows"][0]["cells"])


def test_deleting_all_rows_asks_then_removes_table(win, monkeypatch) -> None:
    item, shape = _insert_table(win, 2, 2)
    item.table_sel = (0, 0, 1, 1)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    win.action_registry.trigger_action("tbl_delete_row")
    assert shape in _ws(win).current_slide.shapes
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    win.action_registry.trigger_action("tbl_delete_row")
    assert shape not in _ws(win).current_slide.shapes


def test_table_pen_borders_shading_valign(win) -> None:
    item, shape = _insert_table(win)
    reg = win.action_registry
    reg.trigger_action("tbl_weight_30")
    reg.trigger_action("tbl_color_red")
    reg.trigger_action("tbl_line_dash")
    item.table_sel = (0, 0, 2, 2)
    reg.trigger_action("tbl_border_outside")
    assert shape.tbl["rows"][0]["cells"][0]["bd"]["t"] == {"w": 3.0, "c": "#FF0000", "dash": "dash"}
    assert "b" not in shape.tbl["rows"][0]["cells"][0]["bd"]
    item.table_sel = (1, 1, 1, 1)
    reg.trigger_action("tbl_shade_yellow")
    assert shape.tbl["rows"][1]["cells"][1]["fill"] == {"t": "solid", "c": "#FFFF99"}
    reg.trigger_action("cellBottom")
    assert shape.tbl["rows"][1]["cells"][1]["tx"].anchor == "b"
    reg.trigger_action("tbl_select_table")
    assert item.table_sel == (0, 0, 2, 2)


def test_double_click_edits_the_clicked_cell(win, qtbot) -> None:
    item, shape = _insert_table(win, 2, 2)
    x, y, w, h = table_ops.cell_rect(shape.tbl, shape.w, 1, 1)
    hit = item._select_table_cell_at(QPointF(x + w / 2, y + h / 2))
    assert hit == (1, 1)
    editor = item.start_cell_editing(*hit)
    editor.textCursor().insertText("cell text")
    editor.commit_and_finish()
    assert table_ops.cell_plain_text(shape.tbl, 1, 1) == "cell text"
    assert table_ops.cell_plain_text(shape.tbl, 0, 0) == ""
    assert shape.text is None  # the table shape's own text body is not edited
    assert not item.is_editing_text


def test_table_round_trips_merges_borders_and_anchor(win, tmp_path) -> None:
    item, shape = _insert_table(win)
    table_ops.ensure_tx(shape.tbl["rows"][0]["cells"][0]).set_plain_text("Head")
    item.table_sel = (0, 0, 0, 1)
    win.action_registry.trigger_action("tableMergeCells")
    win.action_registry.trigger_action("tbl_border_all")
    win.action_registry.trigger_action("cellMiddle")
    out = tmp_path / "t.pptx"
    write_pptx(win.presentation_view.presentation, out)
    loaded = read_pptx(out)
    tbl = next(s for s in loaded.slides[0].shapes if s.tbl).tbl
    origin = tbl["rows"][0]["cells"][0]
    assert int(origin.get("gs") or 1) == 2
    assert origin["tx"].anchor == "ctr"
    assert origin["tx"].plain_text == "Head"
    assert float(origin["bd"]["t"]["w"]) == pytest.approx(1.0)


# ---------------------------------------------------------------- drawing styles
def test_dash_arrow_shadow_and_picture_weight(win, tmp_path) -> None:
    line = Shape(id="ln", type="line", name="ln", geom="line", x=50, y=50, w=200, h=0.1)
    win.add_shape(line)
    reg = win.action_registry
    reg.trigger_action("draw_dash_long_dash")
    reg.trigger_action("draw_arrow_double")
    reg.trigger_action("draw_shadow_style2")
    assert line.line.dash == "lgDash"
    assert line.line.head["type"] == line.line.tail["type"] == "triangle"
    assert line.shadow is not None and line.shadow.angle == 135.0

    # arrowheads paint and survive save/load
    item = _ws(win).scene.get_shape_item("ln")
    img = QImage(300, 100, QImage.Format.Format_ARGB32)
    painter = QPainter(img)
    item.paint(painter, None)
    painter.end()
    out = tmp_path / "ln.pptx"
    write_pptx(win.presentation_view.presentation, out)
    loaded = next(s for s in read_pptx(out).slides[0].shapes if s.name == "ln")
    assert loaded.line.tail["type"] == "triangle"

    pic = win.insert_picture_from_file(_png(tmp_path / "p.png")).model
    reg.trigger_action("pic_weight_45")
    assert pic.line.width == 4.5 and pic.line.type == "solid"


def test_arrows_only_apply_to_lines(win, monkeypatch) -> None:
    box = _add_box(win, "box", 100.0)
    _select(win, "box")
    win.action_registry.trigger_action("draw_arrow_style1")
    assert box.line.tail is None


def test_transparent_color_pick_and_round_trip(win, tmp_path) -> None:
    item = win.insert_picture_from_file(_png(tmp_path / "t.png", 40, 20))
    win.action_registry.trigger_action("picTransparent")
    assert win.lectern_commands._pick_filter is not None
    # click the green top-left pixel
    scene_pos = item.mapToScene(QPointF(0.2, 0.2))
    assert win.lectern_commands._pick_color(item, scene_pos)
    assert item.model.clr_change == "#00FF00"
    out = tmp_path / "pic.pptx"
    write_pptx(win.presentation_view.presentation, out)
    loaded = next(s for s in read_pptx(out).slides[0].shapes if s.type == "image")
    assert loaded.clr_change == "#00FF00"


# ---------------------------------------------------------------- text commands
def test_find_replace_preserves_run_formatting(win) -> None:
    from atboffice.core.search import SearchOptions
    from atboffice.modules.presentation.tools.text_search import PresentationSearchAdapter

    box = _add_box(win, "t1", 100.0)
    body = TextBody.create_empty()
    body.paragraphs[0].runs = [TextRun(text="Hello ", bold=True), TextRun(text="World")]
    box.text = body
    pres = win.presentation_view.presentation
    focused: list = []
    adapter = PresentationSearchAdapter(pres, on_focus=lambda *a: focused.append(a))
    opts = SearchOptions(text="lo Wo", replace_text="p-wo")
    m = adapter.find_next(opts)
    assert m is not None
    adapter.replace_one(opts, m)
    runs = box.text.paragraphs[0].runs
    assert "".join(r.text for r in runs) == "Help-world"
    assert runs[0].bold
    assert adapter.replace_all(SearchOptions(text="o", replace_text="0")) == 1


def test_find_dialog_opens_with_presentation_adapter(win) -> None:
    from atboffice.modules.presentation.tools.text_search import PresentationSearchAdapter

    win.action_registry.trigger_action("find")
    dlg = win.lectern_commands._find_dialog
    assert dlg is not None and dlg.isVisible()
    assert isinstance(dlg.controller._adapter, PresentationSearchAdapter)
    dlg.close()


def test_spelling_checker_changes_words(win) -> None:
    from atboffice.modules.presentation.tools.spelling import PresentationSpellChecker

    class Engine:
        def is_valid_word(self, word: str) -> bool:
            return word.lower() != "teh"

        def suggest(self, word: str) -> list[str]:
            return ["the"]

    box = _add_box(win, "sp", 100.0, "teh cat and teh dog")
    checker = PresentationSpellChecker(win.presentation_view.presentation, Engine())
    issue = checker.next_issue()
    assert issue.word == "teh" and "1" in checker.describe_issue(issue)
    checker.change_everywhere(issue, "the")
    assert checker.next_issue() is None
    assert box.text.plain_text == "the cat and the dog"


def test_summary_slide_lists_titles(win) -> None:
    pres = win.presentation_view.presentation
    for title in ("Intro", "Plan"):
        slide = pres.add_slide("text")
        for sh in slide.shapes:
            if sh.placeholder and sh.placeholder.type == "title":
                sh.text = TextBody.from_plain_text(title)
    count = len(pres.slides)
    win.action_registry.trigger_action("summarySlide")
    assert len(pres.slides) == count + 1
    summary = pres.slides[_ws(win).current_slide_index]
    body = next(s for s in summary.shapes if s.placeholder and s.placeholder.type == "body")
    assert [p.plain_text for p in body.text.paragraphs][-2:] == ["Intro", "Plan"]


def test_move_paragraph_in_editor(win) -> None:
    box = _add_box(win, "mp", 100.0, "one\ntwo")
    item = _select(win, "mp")[0]
    editor = item.start_text_editing()
    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)
    win.action_registry.trigger_action("moveParaDown")
    editor.commit_and_finish()
    assert [p.plain_text for p in box.text.paragraphs] == ["two", "one"]


def test_action_settings_saved_on_model(win, monkeypatch) -> None:
    from atboffice.modules.presentation.dialogs import ActionSettingsDialog

    box = _add_box(win, "act", 100.0)
    _select(win, "act")
    monkeypatch.setattr(ActionSettingsDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        ActionSettingsDialog, "get_action_settings", lambda self: {"click": {"action": "next"}}
    )
    win.action_registry.trigger_action("actionSettings")
    assert box.link["actions"] == {"click": {"action": "next"}}


def test_hyperlink_on_shape(win, monkeypatch) -> None:
    from atboffice.modules.writer.dialogs import reference_dialogs

    box = _add_box(win, "hl", 100.0, "link")
    _select(win, "hl")
    monkeypatch.setattr(
        reference_dialogs.HyperlinkDialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    monkeypatch.setattr(
        reference_dialogs.HyperlinkDialog,
        "get_hyperlink_data",
        lambda self: {
            "text": "",
            "target": "https://example.com",
            "kind": "external",
            "screentip": "tip",
        },
    )
    win.action_registry.trigger_action("hyperlink")
    assert box.link["url"] == "https://example.com" and box.link["tooltip"] == "tip"


def test_format_painter_copies_shape_format(win) -> None:
    src = _add_box(win, "src", 100.0, "a")
    dst = _add_box(win, "dst", 400.0, "b")
    src.fill.color = "#123456"
    src.text.paragraphs[0].runs[0].bold = True
    _select(win, "src")
    win.action_registry.trigger_action("formatPainter")
    assert win.action_registry.get_action("formatPainter").isChecked()
    item = _ws(win).scene.get_shape_item("dst")
    assert win.lectern_commands._paint_format_at(item.mapToScene(QPointF(10, 10)))
    assert dst.fill.color == "#123456"
    assert dst.text.paragraphs[0].runs[0].bold
    assert not win.action_registry.get_action("formatPainter").isChecked()


def test_help_uses_base_window_help(win) -> None:
    from atboffice.ui.shell.base_window import BaseOfficeWindow

    assert type(win).show_help is BaseOfficeWindow.show_help


# ---------------------------------------------------------------- masters & panes
def test_master_view_uses_master_view_widget_and_shared_scene(win, monkeypatch) -> None:
    ws = _ws(win)
    win.action_registry.trigger_action("viewMaster")
    assert ws.center_stack.currentWidget() is ws.master_view
    assert ws.master_view.scene is ws.scene
    win.action_registry.trigger_action("insertTitleMaster")
    design = win.presentation_view.presentation.get_design_for_slide(None)
    assert design.title_decorations is not None
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("My Master", True))
    win.action_registry.trigger_action("renameMaster")
    assert design.name == "My Master"
    win.action_registry.trigger_action("preserveMaster")
    assert design.id in win.presentation_view.presentation.props["preserved_masters"]
    win.action_registry.trigger_action("deleteTitleMaster")
    assert design.title_decorations is None
    count = len(win.presentation_view.presentation.designs)
    win.action_registry.trigger_action("insertSlideMaster")
    assert len(win.presentation_view.presentation.designs) == count + 1
    win.action_registry.trigger_action("closeMaster")
    assert ws.center_stack.currentWidget() is ws.center_normal_widget


def test_task_pane_deduplicated_and_transition_pane_in_dock(win) -> None:
    ws = _ws(win)
    assert not ws.task_pane.isVisible()
    win.set_view_mode("sorter")
    win.set_view_mode("normal")
    assert not ws.task_pane.isVisible()
    win.action_registry.trigger_action("slideshow_transition")
    assert win.task_pane_dock.isVisible()
    assert win.task_pane_dock.get_pane("transition") is ws.transition_pane


def test_speaker_notes_and_ruler(win, monkeypatch) -> None:
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *a, **k: ("My notes", True))
    win.action_registry.trigger_action("speakerNotes")
    assert _ws(win).current_slide.notes == "My notes"
    win.action_registry.trigger_action("view_ruler")
    assert _ws(win).canvas_view.show_rulers
    _ws(win).canvas_view.viewport().repaint()


def test_insert_diagram_and_change_layout(win, monkeypatch) -> None:
    from atboffice.modules.presentation.dialogs import diagram_gallery_dialog

    monkeypatch.setattr(
        diagram_gallery_dialog.DiagramGalleryDialog,
        "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        diagram_gallery_dialog.DiagramGalleryDialog, "selected_layout", lambda self: "cycle"
    )
    win.action_registry.trigger_action("draw_insertDiagram")
    diag = _ws(win).current_slide.shapes[-1]
    assert diag.sa["layout"] == "cycle" and diag.kids
    _select(win, diag.id)
    win.action_registry.trigger_action("diag_layout_pyramid")
    win.action_registry.trigger_action("diag_color_dark")
    win.action_registry.trigger_action("diag_style_3d")
    assert (diag.sa["layout"], diag.sa["colors"], diag.sa["style"]) == (
        "pyramid",
        "midnight",
        "lifted",
    )


# ---------------------------------------------------------------- audit
def test_no_reachable_lectern_action_is_unbound(win) -> None:
    reg = win.action_registry
    reach: dict[int, object] = {}

    def walk(menu) -> None:
        for act in menu.actions():
            if not act.isVisible():
                continue
            if act.menu():
                walk(act.menu())
            else:
                reach[id(act)] = act

    mb = win.findChild(MacMenuBar)
    for act in mb.actions():
        if act.isVisible() and act.menu():
            walk(act.menu())
    for tb in win.findChildren(QToolBar):
        for act in tb.actions():
            if act.menu():
                walk(act.menu())
            reach.setdefault(id(act), act)
        for btn in tb.findChildren(QToolButton):
            if btn.menu():
                walk(btn.menu())
    ids = {id(act): aid for aid, act in reg._actions.items()}
    unbound = sorted(
        ids[k]
        for k, act in reach.items()
        if k in ids
        and not act.menu()
        and reg._specs[ids[k]].handler is None
        and not reg.is_whitelisted_action(ids[k])
    )
    assert unbound == []


def test_word_only_menu_items_hidden_in_lectern(win) -> None:
    mb = win.findChild(MacMenuBar)
    for aid in ("insert_page_break", "format_tabs", "format_borders"):
        assert not mb.action_map[aid].isVisible(), aid
    assert mb.action_map["headerFooter"].isVisible()


def test_record_narration_disabled_with_reason(win) -> None:
    act = win.action_registry.get_action("slideshow_record")
    assert act is not None and not act.isEnabled()


def test_status_messages_never_report_unwired(win, qtbot) -> None:
    """Triggering wired, dialog-free commands never produces the 'not wired' toast."""
    messages: list[str] = []
    win.statusBar().messageChanged.connect(messages.append)
    for aid in (
        "view_normal",
        "expandAll",
        "showFormatting",
        "view_ruler",
        "tbl_weight_15",
        "tbl_color_blue",
        "tbl_line_dot",
        "draw_align_left",
        "insert_shape",
    ):
        win.action_registry.trigger_action(aid)
    assert not any("联调" in m for m in messages)
    assert Qt  # keep import used
