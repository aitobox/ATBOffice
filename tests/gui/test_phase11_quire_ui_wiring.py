"""Regression tests for issue #443: Quire dialogs, menu and toolbar commands."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog

from atboffice.modules.writer import dialogs as wd
from atboffice.modules.writer.models.document import Paragraph, TextItem
from atboffice.modules.writer.views.caret_controller import DocPos, Selection
from atboffice.ui.shell.quire_commands import OBJECT_COMMANDS, OBJECT_REASON
from atboffice.ui.shell.quire_window import QuireWindow

FALLBACK = "正在联调中"
ACCEPTED = QDialog.DialogCode.Accepted


@pytest.fixture
def quire(qtbot) -> QuireWindow:
    win = QuireWindow()
    qtbot.addWidget(win)
    canvas = win.writer_view.canvas_view
    para = canvas.doc.main.blocks[0]
    para.runs = [TextItem("hello world")]
    canvas.refresh_layout()
    canvas.controller.pos = DocPos(para.id, 5)
    canvas.controller.selection = Selection(canvas.controller.pos, canvas.controller.pos)
    yield win
    win.set_modified(False)


def _accept(monkeypatch, cls, **getters) -> None:
    monkeypatch.setattr(cls, "exec", lambda self: ACCEPTED)
    for name, value in getters.items():
        monkeypatch.setattr(cls, name, lambda self, v=value: v)


def _para(win: QuireWindow) -> Paragraph:
    return win.writer_view.canvas_view.doc.main.blocks[0]


def _types(p: Paragraph) -> list[str]:
    return [getattr(it, "t", "") for it in p.runs]


# ---------------------------------------------------------------------------
# Dialog results reach the document (and are undoable)
# ---------------------------------------------------------------------------


def test_break_dialog_inserts_page_break(quire, monkeypatch) -> None:
    _accept(monkeypatch, wd.BreakDialog, get_break_type=("break", "page"))
    quire.open_break_dialog()
    assert "br" in _types(_para(quire))

    canvas = quire.writer_view.canvas_view
    assert canvas.undo() is True
    assert "br" not in _types(canvas.doc.main.blocks[0])


def test_symbol_and_date_dialogs_insert_text(quire, monkeypatch) -> None:
    _accept(monkeypatch, wd.SymbolDialog, get_selected_character="©")
    quire.open_symbol_dialog()
    _accept(monkeypatch, wd.DateTimeDialog, get_selected_format=("2026-11-22", False))
    quire.open_date_time_dialog()
    text = "".join(getattr(it, "text", "") for it in _para(quire).runs)
    assert "hello©2026-11-22 world" == text


def test_hyperlink_dialog_creates_link_run(quire, monkeypatch) -> None:
    _accept(monkeypatch, wd.HyperlinkDialog, get_hyperlink_data={
        "text": "site", "target": "https://example.com", "kind": "url", "screentip": ""})
    quire.open_hyperlink_dialog()
    links = [it for it in _para(quire).runs if getattr(it.r_pr, "link", None)]
    assert links and links[0].text == "site"
    assert links[0].r_pr.link["url"] == "https://example.com"


def test_footnote_dialog_adds_reference_and_note(quire, monkeypatch) -> None:
    _accept(monkeypatch, wd.FootnoteDialog, get_footnote_settings={"type": "footnote"})
    quire.open_footnote_dialog()
    refs = [it for it in _para(quire).runs if getattr(it, "t", "") == "noteRef"
            or it.__class__.__name__ == "NoteRefItem"]
    assert refs
    assert refs[0].note_id in quire.writer_view.canvas_view.doc.fn


def test_caption_and_toc(quire, monkeypatch) -> None:
    canvas = quire.writer_view.canvas_view
    _para(quire).p_pr.style = "Heading1"
    _accept(monkeypatch, wd.CaptionDialog, get_caption_data={
        "caption": ": Overview", "label": "Figure", "position": "below", "exclude_label": False})
    quire.open_caption_dialog()
    captions = [p for p in canvas.doc.main.blocks if p.p_pr.style == "Caption"]
    assert captions and captions[0].runs[0].text == "Figure 1: Overview"

    _accept(monkeypatch, wd.IndexTablesDialog, get_index_tables_data={
        "active_tab": 1, "toc_levels": 3, "toc_show_pages": True})
    monkeypatch.setattr(wd.IndexTablesDialog, "exec", lambda self: (
        self.tab_widget.setCurrentWidget(self.tab_toc), ACCEPTED)[1])
    quire.open_index_tables_dialog()
    toc = [p for p in canvas.doc.main.blocks if p.p_pr.style.startswith("TOC")]
    assert any("hello world" in "".join(getattr(i, "text", "") for i in p.runs) for p in toc)

    quire.action_registry.trigger_action("gotoTOC")
    assert canvas.controller.pos.para_id == toc[0].id or canvas.controller.pos.offset == 0


def test_bookmark_dialog_adds_and_deletes(quire, monkeypatch) -> None:
    canvas = quire.writer_view.canvas_view
    _accept(monkeypatch, wd.BookmarkDialog, get_bookmarks=["intro"], get_selected_bookmark="")
    quire.open_bookmark_dialog()
    from atboffice.modules.writer.views import doc_actions

    assert doc_actions.document_bookmarks(canvas.doc) == ["intro"]
    _accept(monkeypatch, wd.BookmarkDialog, get_bookmarks=[], get_selected_bookmark="")
    quire.open_bookmark_dialog()
    assert doc_actions.document_bookmarks(canvas.doc) == []


def test_page_numbers_dialog_adds_page_field_to_footer(quire, monkeypatch) -> None:
    _accept(monkeypatch, wd.PageNumbersDialog, get_page_number_settings={
        "position": "bottom", "alignment": "center", "show_first_page": False,
        "number_format": "decimal", "continue_numbering": True, "start_at": 1})
    quire.open_page_numbers_dialog()
    doc = quire.writer_view.canvas_view.doc
    rid = doc.sect.refs["ftr"]["default"]
    para = doc.hf[rid].blocks[-1]
    assert para.p_pr.jc == "center"
    assert any(getattr(it, "field_type", "") == "PAGE" for it in para.runs)
    assert doc.sect.title_pg is True


def test_change_case_drop_cap_watermark_hyphenation(quire, monkeypatch) -> None:
    canvas = quire.writer_view.canvas_view
    para = _para(quire)
    canvas.controller.selection = Selection(DocPos(para.id, 0), DocPos(para.id, 5))
    _accept(monkeypatch, wd.ChangeCaseDialog, get_case_mode="upper")
    quire.open_change_case_dialog()
    assert para.runs[0].text.startswith("HELLO")

    _accept(monkeypatch, wd.DropCapDialog, get_drop_cap_data={
        "position": "dropped", "font": "", "lines": 3, "distance_cm": 0})
    quire.open_drop_cap_dialog()
    assert _para(quire).p_pr.frame_pr["dropCap"] == "drop"

    _accept(monkeypatch, wd.WatermarkDialog, get_watermark_data={"type": "text", "text": "DRAFT"})
    quire.open_watermark_dialog()
    assert canvas.doc.settings["watermark"]["text"] == "DRAFT"

    _accept(monkeypatch, wd.HyphenationDialog, get_hyphenation_settings={
        "auto": True, "hyphenate_caps": False, "zone_pt": 18.0, "limit": "2"})
    quire.open_hyphenation_dialog()
    assert canvas.doc.settings["autoHyphenation"] is True
    assert canvas.doc.settings["consecutiveHyphenLimit"] == 2


def test_table_dialogs(quire, monkeypatch) -> None:
    canvas = quire.writer_view.canvas_view
    canvas.insert_table(2, 2)
    ctx = canvas.get_current_table_context()
    tbl = ctx["tbl"]
    tbl.rows[0].cells[0].blocks[0].runs = [TextItem("3")]
    tbl.rows[1].cells[0].blocks[0].runs = []
    canvas.controller.pos = DocPos(tbl.rows[1].cells[0].blocks[0].id, 0)

    _accept(monkeypatch, wd.TableFormulaDialog, get_formula_data=("=SUM(ABOVE)", ""))
    quire.open_table_formula_dialog()
    texts = [getattr(it, "text", "") for it in tbl.rows[1].cells[0].blocks[0].runs]
    assert "3" in texts

    _accept(monkeypatch, wd.InsertCellsDialog, get_action="row")
    quire.open_insert_cells_dialog()
    assert len(tbl.rows) == 3

    _accept(monkeypatch, wd.TableAutoFormatDialog, get_format_settings={"style": "TableGrid"})
    quire.open_table_autoformat_dialog()
    assert tbl.tbl_pr.style == "TableGrid"


def test_font_dialog_applies_to_selection(quire, monkeypatch) -> None:
    from atboffice.modules.writer.dialogs.font_dialog import FontDialog
    from atboffice.modules.writer.models.properties import RunProperties

    canvas = quire.writer_view.canvas_view
    para = _para(quire)
    canvas.controller.selection = Selection(DocPos(para.id, 0), DocPos(para.id, 5))
    props = RunProperties()
    props.b = True
    props.sz = 20.0
    _accept(monkeypatch, FontDialog, get_properties=props)

    quire.action_registry.trigger_action("format_font")

    assert para.runs[0].text == "hello" and para.runs[0].r_pr.b is True


# ---------------------------------------------------------------------------
# Toolbar commands
# ---------------------------------------------------------------------------


def test_header_footer_toolbar(quire) -> None:
    reg = quire.action_registry
    doc = quire.writer_view.canvas_view.doc
    reg.trigger_action("hfPageNum")
    reg.trigger_action("hfSwitch")
    reg.trigger_action("hfDate")
    hdr = doc.hf[doc.sect.refs["hdr"]["default"]]
    ftr = doc.hf[doc.sect.refs["ftr"]["default"]]
    assert any(getattr(it, "field_type", "") == "PAGE" for it in hdr.blocks[-1].runs)
    assert any(getattr(it, "field_type", "") == "DATE" for it in ftr.blocks[-1].runs)
    reg.trigger_action("hf_at_page_x_of_y")
    assert any(getattr(it, "field_type", "") == "NUMPAGES" for it in ftr.blocks[-1].runs)


def test_show_marks_and_format_painter(quire) -> None:
    canvas = quire.writer_view.canvas_view
    quire.action_registry.trigger_action("showMarks")
    assert canvas.show_formatting_marks is True
    canvas.viewport().grab()  # paints the ¶ overlay without errors

    para = _para(quire)
    para.runs = [TextItem("bold"), TextItem(" plain")]
    para.runs[0].r_pr.b = True
    canvas.refresh_layout()
    canvas.controller.pos = DocPos(para.id, 1)
    quire.action_registry.trigger_action("painter")
    assert canvas.format_painter_props is not None
    canvas.controller.selection = Selection(DocPos(para.id, 5), DocPos(para.id, 10))
    assert canvas._apply_format_painter() is True
    assert all(it.r_pr.b for it in para.runs if getattr(it, "text", "").strip())
    assert canvas.format_painter_props is None


def test_review_navigation_and_display(quire) -> None:
    canvas = quire.writer_view.canvas_view
    reg = quire.action_registry
    reg.trigger_action("rev_final")
    assert canvas.revision_view == "final"
    reg.trigger_action("rev_show_comments")
    assert canvas.show_comments is False

    canvas.insert_comment(author="A", text="note")
    canvas.controller.pos = DocPos(_para(quire).id, 0)
    assert quire.toolbar_commands.goto_change(1) is True


def test_highlight_palette_and_values(quire, qtbot) -> None:
    from atboffice.ui.components.color_picker import ColorPickerPopup

    popup = ColorPickerPopup(mode="highlight")
    qtbot.addWidget(popup)
    assert len(popup.swatch_buttons) == 15
    assert not popup.btn_more_colors.isVisibleTo(popup)

    canvas = quire.writer_view.canvas_view
    para = _para(quire)
    canvas.controller.selection = Selection(DocPos(para.id, 0), DocPos(para.id, 5))
    canvas.set_highlight_color("#FFFF00")
    assert para.runs[0].r_pr.highlight == "yellow"
    canvas.set_highlight_color("none")
    assert para.runs[0].r_pr.highlight is None


def test_border_presets_use_dataclasses(quire) -> None:
    from atboffice.modules.writer.models.properties import BorderProperties

    quire.apply_border_preset("bottom")
    borders = _para(quire).p_pr.borders
    assert set(borders) == {"bottom"} and isinstance(borders["bottom"], BorderProperties)


def test_style_and_zoom_combos(quire) -> None:
    from atboffice.core.i18n import safe_tr

    quire._on_style_combo_changed(safe_tr("副标题"))
    assert _para(quire).p_pr.style == "Subtitle"
    canvas = quire.writer_view.canvas_view
    quire.resize(1400, 900)
    quire.show()
    canvas.set_zoom(0.5)
    quire._on_zoom_combo_changed(safe_tr("页宽"))
    assert canvas.zoom > 0.5


def test_outline_commands_follow_view_mode(quire, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(quire.writer_view.canvas_view, "set_outline_level",
                        lambda lvl: calls.append("canvas"))
    quire.action_registry.trigger_action("promoteH1")
    assert calls == ["canvas"]


def test_column_presets(quire) -> None:
    sect = quire.writer_view.canvas_view.doc.sect
    quire.action_registry.trigger_action("col_left")
    assert sect.cols.num == 2 and sect.cols.widths[0] < sect.cols.widths[1]
    quire.action_registry.trigger_action("col_3")
    assert sect.cols.num == 3 and sect.cols.equal_width


def test_object_commands_disabled_with_reason(quire) -> None:
    reg = quire.action_registry
    for aid in OBJECT_COMMANDS:
        if reg.has_action(aid) and reg.get_spec(aid).handler is None:
            assert not reg.is_enabled(aid), aid
            assert reg.get_spec(aid).disabled_reason


# ---------------------------------------------------------------------------
# No fallback toast for wired Quire actions
# ---------------------------------------------------------------------------

WIRED = [
    "format_font", "format_paragraph", "format_borders", "format_tabs", "tools_language",
    "table_insert", "table_delete", "table_select", "table_properties", "insert_page_break",
    "insert_page_number", "insert_date_time", "insert_symbol", "docMap", "viewReading",
    "col_left", "col_right", "col_1", "col_2", "col_3", "hfPageNum", "hfNumPages", "hfDate",
    "hfTime", "hfSwitch", "hfPrev", "hfNext", "hfClose", "hfShowText", "hfLinkPrev",
    "rev_final", "rev_final_markup", "rev_original", "rev_original_markup", "prevChange",
    "nextChange", "olFirstLine", "olFormatting", "updateTOC", "gotoTOC", "showMarks", "painter",
    "drawTable", "eraser", "tbl_line_single", "tbl_weight_10", "tbl_shade_none", "mmMergeNew",
]


def test_wired_actions_never_show_fallback_toast(quire, monkeypatch) -> None:
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    from PySide6.QtWidgets import QFileDialog, QInputDialog

    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    reg = quire.action_registry
    for aid in WIRED:
        assert reg.has_action(aid), aid
        spec = reg.get_spec(aid)
        assert spec is not None and spec.handler is not None, aid
        quire.statusBar().clearMessage()
        reg.trigger_action(aid)
        assert FALLBACK not in quire.statusBar().currentMessage(), aid
    assert OBJECT_REASON
