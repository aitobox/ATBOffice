"""Quire toolbar command handlers (issue #443).

Header & Footer, Reviewing, Outlining, Standard (marks / Format Painter), Tables and
Borders, Mail Merge and Reading Layout commands, bound onto ``QuireWindow``'s
ActionRegistry by :func:`bind_quire_toolbar_commands`.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QComboBox, QFileDialog

from atboffice.core.i18n import safe_tr
from atboffice.modules.writer.models.document import (
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    TabItem,
    TextItem,
)
from atboffice.modules.writer.models.properties import BorderProperties, ShadingProperties
from atboffice.modules.writer.views import canvas_object_commands, doc_actions
from atboffice.modules.writer.views.caret_controller import DocPos, Selection

if TYPE_CHECKING:
    from atboffice.ui.shell.quire_window import QuireWindow

# Object-scoped commands implemented in ``canvas_object_commands`` that are enabled
# when a floating object is selected on the canvas.
FLOAT_SCOPED_COMMANDS: tuple[str, ...] = (
    "wrap_inline",
    "wrap_square",
    "wrap_tight",
    "wrap_behind",
    "wrap_front",
    "picRotate",
    "picReset",
    "picMoreBright",
    "picLessBright",
    "picMoreContrast",
    "picLessContrast",
    "pic_color_auto",
    "pic_color_gray",
    "pic_color_bw",
    "pic_color_wash",
    "draw_weight_075",
    "draw_dash_dash",
    "draw_arrow_1",
    "draw_shadow_1",
    "formatObject",
)

# Commands of floating-object toolbars (Picture, Drawing, WordArt, wrapping) that are
# not wired to canvas selection yet, so they stay disabled with OBJECT_REASON.
OBJECT_COMMANDS: tuple[str, ...] = (
    "picCrop",
    "pic_color_mode",
    "pic_line_style",
    "pic_wrap_mode",
    "draw_arrow_style",
    "draw_dash_style",
    "draw_group",
    "draw_line_style",
    "draw_shadow_style",
    "draw_ungroup",
    "selectObjects",
    "wa_format",
    "wa_shape_arch_down",
    "wa_shape_arch_up",
    "wa_shape_circle",
    "wa_shape_plain",
    "wa_shape_wave",
    "wa_wrap_mode",
    "insertClipArt",
    "insertDiagram",
    "insertExcel",
    "insert_shape",
    "permission",
    "sendMail",
)
OBJECT_REASON = "请先在文档中选择图片或图形对象"

# Drop-down containers and empty-history placeholders: they open a menu, never a command.
CONTAINER_COMMANDS: tuple[str, ...] = (
    "autoshapes_menu",
    "columns_menu",
    "draw_menu",
    "hf_autotext_menu",
    "lineSpacing_menu",
    "rev_display_mode",
    "rev_show_menu",
    "tbl_align_menu",
    "tbl_insert_menu",
    "tbl_dash_style",
    "tbl_line_weight",
    "tbl_line_color",
    "tbl_shading_color",
    "wa_shape_menu",
    "redo_empty",
    "undo_empty",
)

_TBL_WEIGHTS = {
    "tbl_weight_05": 0.5,
    "tbl_weight_075": 0.75,
    "tbl_weight_10": 1.0,
    "tbl_weight_15": 1.5,
    "tbl_weight_225": 2.25,
    "tbl_weight_30": 3.0,
}
_TBL_STYLES = {
    "tbl_line_single": "single",
    "tbl_line_double": "double",
    "tbl_line_dot": "dotted",
    "tbl_line_dash": "dashed",
}
_TBL_COLORS = {
    "tbl_color_auto": "auto",
    "tbl_color_black": "000000",
    "tbl_color_red": "FF0000",
    "tbl_color_blue": "0000FF",
}


class QuireToolbarCommands:
    """State and handlers for Quire's contextual toolbars."""

    def __init__(self, window: QuireWindow) -> None:
        self.window = window
        self.hf_kind = "hdr"  # the header/footer story the HF toolbar edits
        self.border_style = "single"
        self.border_weight = 0.5
        self.border_color = "auto"

    @property
    def canvas(self) -> Any:
        return self.window.writer_view.canvas_view

    def _apply(self, mutate: Any) -> Any:
        return self.window._apply_dialog(mutate)

    def _status(self, text: str) -> None:
        bar = self.window.statusBar()
        if bar is not None:
            bar.showMessage(text, 3000)

    # ------------------------------------------------------------- Header & Footer
    def enter_header_footer(self, kind: str = "hdr") -> None:
        self.hf_kind = kind
        if self.canvas.hf_edit_kind != kind:
            self.canvas.hf_edit_kind = kind
            self.canvas.viewport().update()
        self.window.update_context_toolbars({"hf_edit": True})
        self._status(safe_tr("正在编辑页眉") if kind == "hdr" else safe_tr("正在编辑页脚"))

    def open_header_footer(self) -> None:
        """View > Header and Footer: switch to Print Layout and edit the header."""
        from atboffice.modules.writer.views.view_modes import ViewMode

        if self.canvas.view_mode != ViewMode.PRINT:
            self.window.switch_view_mode(ViewMode.PRINT)
        self.canvas.enter_header_footer_mode("hdr")

    def close_header_footer(self) -> None:
        self.window.update_context_toolbars({"hf_edit": False})
        self.canvas.exit_header_footer_mode()
        self.canvas.doc.settings.pop("hideBodyText", None)
        self.canvas.viewport().update()

    def switch_header_footer(self) -> None:
        self.enter_header_footer("ftr" if self.hf_kind == "hdr" else "hdr")

    def show_adjacent_header_footer(self, step: int) -> None:
        """Show Previous/Next: walk the sections' header/footer stories."""
        doc = self.canvas.doc
        sections = [doc.sect] + [
            b.sect for b in doc.main.blocks if isinstance(b, Paragraph) and b.sect is not None
        ]
        if len(sections) < 2:
            self._status(safe_tr("文档只有一节，没有其他页眉或页脚"))
            return
        self.switch_header_footer()

    def _hf_append(self, items: list[Any]) -> None:
        def mutate() -> None:
            story = doc_actions._hf_story(self.canvas.doc, self.hf_kind)
            assert story is not None
            para = (
                story.blocks[-1]
                if story.blocks and isinstance(story.blocks[-1], Paragraph)
                else None
            )
            if para is None:
                para = Paragraph()
                story.blocks.append(para)
            para.runs.extend(items)

        self._apply(mutate)

    @staticmethod
    def _field(name: str, result: str, instr: str | None = None) -> list[Any]:
        return [
            FieldBeginItem(field_type=name, instr=f" {instr or name} "),
            FieldSeparateItem(),
            TextItem(result),
            FieldEndItem(),
        ]

    def hf_page_number(self) -> None:
        self._hf_append(self._field("PAGE", "1"))

    def hf_num_pages(self) -> None:
        pages = len(getattr(self.canvas.pagination, "pages", []) or []) or 1
        self._hf_append(self._field("NUMPAGES", str(pages)))

    def hf_date(self) -> None:
        self._hf_append(self._field("DATE", doc_actions._format_date("M/d/yyyy")))

    def hf_time(self) -> None:
        self._hf_append(self._field("TIME", doc_actions._format_date("h:mm am/pm")))

    def hf_autotext(self, entry: str) -> None:
        page = self._field("PAGE", "1")
        pages = self._field("NUMPAGES", str(len(self.canvas.pagination.pages or []) or 1))
        date = self._field("DATE", doc_actions._format_date("M/d/yyyy"))
        author = str(self.canvas.doc.props.get("creator", "")) or safe_tr("作者")
        items: list[Any]
        if entry == "page":
            items = [TextItem("- "), *page, TextItem(" -")]
        elif entry == "page_x_of_y":
            items = [
                TextItem(safe_tr("第 ")),
                *page,
                TextItem(safe_tr(" 页，共 ")),
                *pages,
                TextItem(safe_tr(" 页")),
            ]
        elif entry == "confidential":
            items = [TextItem(safe_tr("机密")), TabItem(), *page, TabItem(), *date]
        else:  # author, page, date
            items = [TextItem(author), TabItem(), *page, TabItem(), *date]
        self._hf_append(items)

    def hf_toggle_body_text(self) -> None:
        settings = self.canvas.doc.settings
        settings["hideBodyText"] = not settings.get("hideBodyText", False)
        self.canvas.viewport().update()

    def hf_link_previous(self) -> None:
        settings = self.canvas.doc.settings
        settings["hfLinkToPrevious"] = not settings.get("hfLinkToPrevious", True)
        self._status(
            safe_tr("已链接到前一节")
            if settings["hfLinkToPrevious"]
            else safe_tr("已断开与前一节的链接")
        )

    # ------------------------------------------------------------------- Reviewing
    def set_revision_view(self, mode: str) -> None:
        """Display for Review: Final Showing Markup / Final / Original … (relayouts)."""
        self.canvas.revision_view = mode
        self.canvas.doc.settings["revisionView"] = mode
        self.canvas.refresh_layout()

    def toggle_show(self, attr: str) -> None:
        setattr(self.canvas, attr, not getattr(self.canvas, attr))
        setting = {"show_ins_del": "showInsDel", "show_formatting_changes": "showFormatting"}.get(
            attr
        )
        if setting:
            self.canvas.doc.settings[setting] = bool(getattr(self.canvas, attr))
            self.canvas.refresh_layout()
        else:
            self.canvas.viewport().update()

    def goto_change(self, step: int) -> bool:
        """Previous/Next Change: move to the neighbouring revision or comment mark."""
        canvas = self.canvas
        marks: list[tuple[int, int]] = []
        for para in canvas.doc.all_paras():
            off = 0
            for it in para.runs:
                rp = getattr(it, "r_pr", None)
                is_rev = rp is not None and bool(
                    getattr(rp, "ins", None) or getattr(rp, "del_rev", None)
                )
                if is_rev or getattr(it, "t", "") in ("cs", "cref"):
                    marks.append((para.id, off))
                off += (
                    len(getattr(it, "text", ""))
                    if getattr(it, "t", "") == "text"
                    else (
                        0
                        if getattr(it, "t", "") in ("cs", "ce", "bs", "be", "fb", "fs", "fe")
                        else 1
                    )
                )
        if not marks:
            self._status(safe_tr("文档中没有修订或批注"))
            return False
        order = [p.id for p in canvas.doc.all_paras()]
        cur = (order.index(canvas.controller.pos.para_id), canvas.controller.pos.offset)
        keyed = [((order.index(pid), off), (pid, off)) for pid, off in marks]
        keyed.sort()
        if step > 0:
            nxt = next((m for k, m in keyed if k > cur), keyed[0][1])
        else:
            nxt = next((m for k, m in reversed(keyed) if k < cur), keyed[-1][1])
        canvas.controller.pos = DocPos(*nxt)
        canvas.controller.selection = Selection(canvas.controller.pos, canvas.controller.pos)
        canvas.controller.caret_changed.emit()
        canvas.scroll_to_caret()
        return True

    # ------------------------------------------------------------------- Outlining
    def set_first_line_only(self) -> None:
        widget = self.window.writer_view.outline_widget
        widget.set_first_line_only(not widget.first_line_only)

    def set_show_formatting(self) -> None:
        widget = self.window.writer_view.outline_widget
        widget.set_show_formatting(not widget.show_formatting)

    def on_show_level(self, index: int) -> None:
        widget = self.window.writer_view.outline_widget
        if hasattr(widget, "set_show_level"):
            widget.set_show_level(index if index > 0 else 9)

    def update_toc(self) -> None:
        if doc_actions.toc_paragraph(self.canvas.doc) is None:
            self._status(safe_tr("文档中没有目录"))
            return
        self._apply(lambda: doc_actions.update_table_of_contents(self.canvas))

    def goto_toc(self) -> None:
        para = doc_actions.toc_paragraph(self.canvas.doc)
        if para is None:
            self._status(safe_tr("文档中没有目录"))
            return
        self.canvas.controller.set_caret(para.id, 0)
        self.canvas.scroll_to_paragraph(para.id)

    # ---------------------------------------------------------- Standard toolbar
    def toggle_marks(self) -> None:
        self.canvas.show_formatting_marks = not self.canvas.show_formatting_marks
        self.canvas.viewport().update()

    def format_painter(self) -> None:
        if self.canvas.format_painter_props is not None:
            self.canvas.stop_format_painter()
            return
        self.canvas.start_format_painter()

    def insert_picture(self) -> bool:
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            safe_tr("插入图片"),
            "",
            safe_tr("图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"),
        )
        if not path:
            return False
        return bool(self._apply(lambda: insert_picture_file(self.canvas, Path(path))))

    # --------------------------------------------------------- Tables and Borders
    def set_border_style(self, aid: str) -> None:
        self.border_style = _TBL_STYLES[aid]

    def set_border_weight(self, aid: str) -> None:
        self.border_weight = _TBL_WEIGHTS[aid]

    def set_border_color(self, aid: str) -> None:
        self.border_color = _TBL_COLORS[aid]
        self.apply_cell_borders()

    def apply_cell_borders(self) -> None:
        ctx = self.canvas.get_current_table_context()
        if ctx is None:
            self._status(safe_tr("请先将光标置于表格中"))
            return
        border = BorderProperties(
            val=self.border_style, sz=self.border_weight, color=self.border_color
        )

        def mutate() -> None:
            ctx["cell"].tc_pr.borders = {
                side: copy.deepcopy(border) for side in ("top", "left", "bottom", "right")
            }

        self._apply(mutate)

    def set_cell_shading(self, fill: str | None) -> None:
        ctx = self.canvas.get_current_table_context()
        if ctx is None:
            self._status(safe_tr("请先将光标置于表格中"))
            return

        def mutate() -> None:
            ctx["cell"].tc_pr.shd = ShadingProperties(fill=fill or "auto")

        self._apply(mutate)

    def draw_table(self) -> None:
        next_tool = None if getattr(self.canvas, "table_tool", None) == "draw" else "draw"
        self.canvas.set_table_tool(next_tool)

    def eraser(self) -> None:
        next_tool = None if getattr(self.canvas, "table_tool", None) == "erase" else "erase"
        self.canvas.set_table_tool(next_tool)

    # ------------------------------------------------------------------ Mail merge
    def merge_to_new_document(self) -> bool:
        engine = getattr(self.window.writer_view, "mailmerge_engine", None)
        merged = engine.build_merged_document(self.canvas.doc) if engine is not None else None
        if merged is None:
            self._status(safe_tr("请先打开邮件合并数据源"))
            return False
        from atboffice.core.window_manager import WindowManager

        win = WindowManager.get_instance().open_quire()
        win.writer_view.canvas_view.set_document(merged)
        win.set_modified(True)
        return True

    def merge_to_printer(self) -> bool:
        engine = getattr(self.window.writer_view, "mailmerge_engine", None)
        merged = engine.build_merged_document(self.canvas.doc) if engine is not None else None
        if merged is None:
            self._status(safe_tr("请先打开邮件合并数据源"))
            return False
        original = self.canvas.doc
        self.canvas.set_document(merged)
        try:
            self.window.print_document()
        finally:
            self.canvas.set_document(original)
        return True

    def on_record_combo(self, text: str) -> None:
        if text.strip().isdigit():
            engine = getattr(self.window.writer_view, "mailmerge_engine", None)
            if engine is not None:
                engine.go(self.canvas.doc, int(text) - 1)
                self.canvas.refresh_layout()


def insert_picture_bytes(canvas: Any, data: bytes, name: str, ext: str = "png") -> bool:
    """Insert an inline picture from encoded image bytes, scaled to fit the text width."""
    from PySide6.QtGui import QImage

    from atboffice.modules.writer.models.drawing import PictureItem

    image = QImage()
    if not data or not image.loadFromData(data) or image.isNull():
        return False
    ext = (ext or "png").lower().lstrip(".")
    sect = canvas.doc.sect
    max_w = max(36.0, sect.pg_w - sect.ml - sect.mr)
    w_pt = image.width() * 0.75
    h_pt = image.height() * 0.75
    if w_pt > max_w:
        h_pt *= max_w / w_pt
        w_pt = max_w
    stem = Path(name).stem or "picture"
    part = name if "." in name else f"{stem}.{ext}"
    pic = PictureItem(
        name=name,
        width=w_pt,
        height=h_pt,
        raw_data={"bytes": data, "ext": ext},
        image_part=f"media/{part}",
        alt_text=stem,
    )
    pic.natural_width, pic.natural_height = w_pt, h_pt
    with canvas.controller.edit_scope("插入图片"):
        doc_actions.insert_items(canvas, [pic])
    canvas.refresh_layout()
    return True


def insert_picture_file(canvas: Any, path: Path) -> bool:
    """Insert an inline picture from ``path`` scaled to fit the text width."""
    return insert_picture_bytes(canvas, path.read_bytes(), path.name, path.suffix)


def bind_quire_toolbar_commands(window: QuireWindow) -> QuireToolbarCommands:
    """Bind every contextual-toolbar command of a Quire window."""
    cmds = QuireToolbarCommands(window)
    reg = window.action_registry
    canvas = window.writer_view.canvas_view

    # Header & Footer (double-clicking a page's header/footer area enters editing too)
    canvas.header_footer_requested.connect(cmds.enter_header_footer)
    reg.set_handler("headerFooter", cmds.open_header_footer)
    reg.set_handler("hfPageNum", cmds.hf_page_number)
    reg.set_handler("hfNumPages", cmds.hf_num_pages)
    reg.set_handler("hfDate", cmds.hf_date)
    reg.set_handler("hfTime", cmds.hf_time)
    reg.set_handler("hfFormatPageNum", window.open_page_numbers_dialog)
    reg.set_handler("hfSwitch", cmds.switch_header_footer)
    reg.set_handler("hfPrev", lambda: cmds.show_adjacent_header_footer(-1))
    reg.set_handler("hfNext", lambda: cmds.show_adjacent_header_footer(1))
    reg.set_handler("hfClose", cmds.close_header_footer)
    reg.set_handler("hfShowText", cmds.hf_toggle_body_text)
    reg.set_handler("hfLinkPrev", cmds.hf_link_previous)
    for aid, entry in (
        ("hf_at_page", "page"),
        ("hf_at_page_x_of_y", "page_x_of_y"),
        ("hf_at_confidential", "confidential"),
        ("hf_at_author_date", "author_date"),
    ):
        reg.set_handler(aid, lambda e=entry: cmds.hf_autotext(e))

    # Reviewing
    for aid, mode in (
        ("rev_final_markup", "final_markup"),
        ("rev_final", "final"),
        ("rev_original_markup", "original_markup"),
        ("rev_original", "original"),
    ):
        reg.set_handler(aid, lambda m=mode: cmds.set_revision_view(m))
    reg.set_handler("rev_show_comments", lambda: cmds.toggle_show("show_comments"))
    reg.set_handler("rev_show_ins_del", lambda: cmds.toggle_show("show_ins_del"))
    reg.set_handler("rev_show_formatting", lambda: cmds.toggle_show("show_formatting_changes"))
    reg.set_handler("rev_show_ink", lambda: None)
    reg.set_handler("prevChange", lambda: cmds.goto_change(-1))
    reg.set_handler("nextChange", lambda: cmds.goto_change(1))

    # Outlining
    reg.set_handler("olFirstLine", cmds.set_first_line_only)
    reg.set_handler("olFormatting", cmds.set_show_formatting)
    reg.set_handler("updateTOC", cmds.update_toc)
    reg.set_handler("gotoTOC", cmds.goto_toc)

    # Proofing & Research
    reg.set_handler("research", lambda: window.open_research())
    reg.set_handler("thesaurus", lambda: window.open_research("thesaurus"))

    # Standard / Formatting
    reg.set_handler("showMarks", cmds.toggle_marks)
    reg.set_handler("painter", cmds.format_painter)
    reg.set_handler(
        "selectAll", lambda: (canvas.controller.select_all(), canvas.viewport().update())
    )
    for aid in ("insertPicture", "insert_picture", "pic_insert"):
        reg.set_handler(aid, cmds.insert_picture)

    # Tables and Borders
    for aid in _TBL_STYLES:
        reg.set_handler(aid, lambda a=aid: cmds.set_border_style(a))
    for aid in _TBL_WEIGHTS:
        reg.set_handler(aid, lambda a=aid: cmds.set_border_weight(a))
    for aid in _TBL_COLORS:
        reg.set_handler(aid, lambda a=aid: cmds.set_border_color(a))
    reg.set_handler("tbl_shade_none", lambda: cmds.set_cell_shading(None))
    reg.set_handler("tbl_shade_gray", lambda: cmds.set_cell_shading("D9D9D9"))
    reg.set_handler("drawTable", cmds.draw_table)
    reg.set_handler("eraser", cmds.eraser)

    # Mail merge
    reg.set_handler("mmMergeNew", cmds.merge_to_new_document)
    reg.set_handler("mmMergePrint", cmds.merge_to_printer)

    # Floating-object commands (wrap, picture, drawing styling, Format Object)
    def _run_float(fn: Any) -> bool:
        ok = bool(fn())
        if ok:
            window.set_modified(True)
            window._sync_toolbar_states()
        return ok

    float_handlers: dict[str, Any] = {
        "wrap_inline": lambda: canvas_object_commands.wrap_inline(canvas, status_cb=cmds._status),
        "wrap_square": lambda: canvas_object_commands.wrap_square(canvas, status_cb=cmds._status),
        "wrap_tight": lambda: canvas_object_commands.wrap_tight(canvas, status_cb=cmds._status),
        "wrap_behind": lambda: canvas_object_commands.wrap_behind(canvas, status_cb=cmds._status),
        "wrap_front": lambda: canvas_object_commands.wrap_front(canvas, status_cb=cmds._status),
        "picRotate": lambda: canvas_object_commands.pic_rotate(canvas, status_cb=cmds._status),
        "picReset": lambda: canvas_object_commands.pic_reset(canvas, status_cb=cmds._status),
        "picMoreBright": lambda: canvas_object_commands.pic_adjust_brightness(
            canvas, 0.1, status_cb=cmds._status
        ),
        "picLessBright": lambda: canvas_object_commands.pic_adjust_brightness(
            canvas, -0.1, status_cb=cmds._status
        ),
        "picMoreContrast": lambda: canvas_object_commands.pic_adjust_contrast(
            canvas, 0.1, status_cb=cmds._status
        ),
        "picLessContrast": lambda: canvas_object_commands.pic_adjust_contrast(
            canvas, -0.1, status_cb=cmds._status
        ),
        "pic_color_auto": lambda: canvas_object_commands.pic_set_color_mode(
            canvas, "auto", status_cb=cmds._status
        ),
        "pic_color_gray": lambda: canvas_object_commands.pic_set_color_mode(
            canvas, "gray", status_cb=cmds._status
        ),
        "pic_color_bw": lambda: canvas_object_commands.pic_set_color_mode(
            canvas, "bw", status_cb=cmds._status
        ),
        "pic_color_wash": lambda: canvas_object_commands.pic_set_color_mode(
            canvas, "washout", status_cb=cmds._status
        ),
        "draw_weight_075": lambda: canvas_object_commands.draw_line_weight(
            canvas, 0.75, status_cb=cmds._status
        ),
        "draw_dash_dash": lambda: canvas_object_commands.draw_dash_style(
            canvas, "dash", status_cb=cmds._status
        ),
        "draw_arrow_1": lambda: canvas_object_commands.draw_arrow_style(
            canvas, "style1", status_cb=cmds._status
        ),
        "draw_shadow_1": lambda: canvas_object_commands.draw_shadow_style(
            canvas, True, status_cb=cmds._status
        ),
        "formatObject": lambda: canvas_object_commands.format_object(
            canvas, parent=window, status_cb=cmds._status
        ),
    }
    has_float = canvas.selected_float() is not None
    for aid, fn in float_handlers.items():
        reg.set_handler(aid, lambda f=fn: _run_float(f))
        spec = reg.get_spec(aid)
        if spec is not None:
            spec.disabled_reason = safe_tr(OBJECT_REASON)
        reg.set_enabled(aid, has_float)

    # Containers open menus; object toolbars wait for a selected object (#447).
    for aid in CONTAINER_COMMANDS:
        if reg.has_action(aid):
            reg.register_whitelist_action(aid, kind="setMenu", reason=safe_tr("打开下拉菜单"))
    for aid in OBJECT_COMMANDS:
        spec = reg.get_spec(aid)
        if spec is not None and spec.handler is None:
            spec.disabled_reason = safe_tr(OBJECT_REASON)
            reg.set_enabled(aid, False)

    # Toolbar widgets that were never connected
    for combo in window.findChildren(QComboBox):
        name = combo.objectName()
        if name == "Quire_ShowLevelCombo":
            combo.currentIndexChanged.connect(cmds.on_show_level)
        elif name == "Quire_MMRecordCombo":
            combo.currentTextChanged.connect(cmds.on_record_combo)

    reading = getattr(window.writer_view, "reading_toolbar", None)
    if reading is not None:
        reading.single_page_requested.connect(lambda: _set_reading_pages(window, 1))
        reading.multi_page_requested.connect(lambda: _set_reading_pages(window, 2))
    return cmds


def _set_reading_pages(window: QuireWindow, pages: int) -> None:
    view = window.writer_view
    if hasattr(view, "set_reading_pages"):
        view.set_reading_pages(pages)
    else:
        view.canvas_view.reading_pages = pages  # type: ignore[attr-defined]
        view.canvas_view.viewport().update()
