"""Writer canvas input: mouse, keyboard, floating objects, context menu, clipboard."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    QPoint,
    QPointF,
    Qt,
)
from PySide6.QtGui import (
    QContextMenuEvent,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QMenu,
)

from atboffice.core.i18n import safe_tr
from atboffice.modules.writer.models.document import (
    Paragraph,
    paras_between,
    ptext,
)
from atboffice.modules.writer.models.properties import (
    RunProperties,
)
from atboffice.modules.writer.views.caret_controller import (
    DocPos,
    Selection,
    delete_range_in_paragraph,
    insert_text_in_paragraph,
)
from atboffice.modules.writer.views.view_modes import ViewMode


class CanvasInputMixin:
    """Mouse and keyboard, floating objects, spelling menu, clipboard and format painter."""

    def start_format_painter(self, sticky: bool = False) -> bool:
        """Copy the caret's character formatting for the next selection (Format Painter)."""
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if p is None:
            return False
        import copy as _copy

        offset = self.controller.pos.offset
        props = None
        cur = 0
        for it in p.runs:
            n = len(getattr(it, "text", "")) if getattr(it, "t", "") == "text" else 1
            if cur <= offset <= cur + n and getattr(it, "t", "") == "text":
                props = it.r_pr
                break
            cur += n
        self.format_painter_props = _copy.deepcopy(props or p.r_pr)
        self.format_painter_sticky = sticky
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        return True

    def stop_format_painter(self) -> None:
        self.format_painter_props = None
        self.format_painter_sticky = False
        self.viewport().unsetCursor()

    def _apply_format_painter(self) -> bool:
        props = self.format_painter_props
        if props is None or self.controller.selection.is_collapsed:
            return False
        import copy as _copy

        fields = (
            "font",
            "font_ea",
            "font_cs",
            "sz",
            "b",
            "i",
            "u",
            "color",
            "vert",
            "highlight",
            "strike",
            "dstrike",
            "caps",
            "small_caps",
            "spacing",
        )

        def apply(r_pr: RunProperties) -> None:
            for name in fields:
                setattr(r_pr, name, _copy.deepcopy(getattr(props, name)))

        self.run_undoable(lambda: self.format_range(apply))
        if not self.format_painter_sticky:
            self.stop_format_painter()
        return True

    def _hit_test_table_divider(self, vp_pt: QPoint) -> dict[str, Any] | None:
        """Hit test viewport position against table column or row dividers."""
        if not self.pagination or not self.pagination.pages:
            return None

        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        threshold = 4.0

        for p_idx, page in enumerate(self.pagination.pages):
            page_rect = self.page_rect_canvas(p_idx)
            page_vp_left = page_rect.left() - scroll_x
            page_vp_top = page_rect.top() - scroll_y

            for reg in page.regions:
                for col in reg.columns:
                    for frag in col.fragments:
                        if frag.table_layout is None:
                            continue
                        tl = frag.table_layout
                        frag_x = page.body_left + col.left
                        frag_y = page.body_top + col.top + frag.top

                        frag_vp_top = page_vp_top + self.pt_to_px(frag_y)
                        frag_vp_bottom = frag_vp_top + self.pt_to_px(tl.height)
                        frag_vp_left = page_vp_left + self.pt_to_px(frag_x)
                        frag_vp_right = frag_vp_left + self.pt_to_px(tl.width)

                        # Test vertical column dividers
                        cur_x = frag_x
                        for c_idx, col_w in enumerate(tl.grid):
                            cur_x += col_w
                            div_vp_x = page_vp_left + self.pt_to_px(cur_x)
                            if (
                                abs(vp_pt.x() - div_vp_x) <= threshold
                                and frag_vp_top - 2 <= vp_pt.y() <= frag_vp_bottom + 2
                            ):
                                return {
                                    "table": tl.table,
                                    "kind": "col",
                                    "index": c_idx,
                                    "start_pt": vp_pt,
                                    "initial_size": col_w,
                                }

                        # Test horizontal row dividers
                        for r_idx, rl in enumerate(tl.rows):
                            div_y = frag_y + rl.y + rl.height
                            div_vp_y = page_vp_top + self.pt_to_px(div_y)
                            if (
                                abs(vp_pt.y() - div_vp_y) <= threshold
                                and frag_vp_left - 2 <= vp_pt.x() <= frag_vp_right + 2
                            ):
                                return {
                                    "table": tl.table,
                                    "kind": "row",
                                    "index": rl.row_idx,
                                    "start_pt": vp_pt,
                                    "initial_size": rl.height,
                                }

        return None

    def _event_pos(self, event: QMouseEvent) -> QPoint:
        """Extract integer pixel QPoint from QMouseEvent safely across Qt versions."""
        if hasattr(event, "position"):
            return event.position().toPoint()
        return event.pos()

    def jump_to_bookmark(self, name: str) -> bool:
        """Jump to bookmark target by scrolling canvas and setting caret position."""
        from atboffice.modules.writer.models.field import find_bookmarks
        from atboffice.modules.writer.views.caret_controller import DocPos

        bms = find_bookmarks(self.doc)
        b = bms.get(name)
        if not b:
            return False
        target_pos = DocPos(b.p.id, b.offset)
        self.controller.set_pos(target_pos, extend_selection=False)
        self.scroll_to_caret()
        self.viewport().update()
        return True

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle single-click, double-click, triple-click, and table divider resize."""
        pos_pt = self._event_pos(event)
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_test_table_divider(pos_pt)
            if hit is not None:
                self._resizing_table = True
                self._resize_info = hit
                self._resize_guide_pos = pos_pt
                self.viewport().update()
                return

            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            if self._float_press(page_idx, pt_doc):
                return
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)

            # Hyperlink navigation check
            p = self.controller._paragraph_by_id(pos.para_id)
            if p:
                from atboffice.modules.writer.models.document import locate

                item_idx, _, _ = locate(p, pos.offset, side="after")
                if 0 <= item_idx < len(p.runs):
                    it = p.runs[item_idx]
                    link = getattr(it.r_pr, "link", None) if hasattr(it, "r_pr") else None
                    if link and isinstance(link, dict) and "anchor" in link:
                        if self.jump_to_bookmark(link["anchor"]):
                            return

            modifiers = event.modifiers()
            shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

            self._is_dragging = True
            self.setFocus()
            self.controller.set_pos(pos, extend_selection=shift)
            self.viewport().update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse dragging for continuous selection and table resizing."""
        pos_pt = self._event_pos(event)
        if self._resizing_table:
            self._resize_guide_pos = pos_pt
            self.viewport().update()
            return
        if self._float_drag is not None:
            _page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            self._float_drag.current = pt_doc
            self.viewport().update()
            return
        if self._float_hover_cursor(pos_pt):
            return

        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)
            self.controller.set_pos(pos, extend_selection=True)
            self.viewport().update()
            return

        # Divider cursor hover detection
        hit = self._hit_test_table_divider(pos_pt)
        if hit is not None:
            if hit["kind"] == "col":
                self.viewport().setCursor(Qt.CursorShape.SplitHCursor)
            else:
                self.viewport().setCursor(Qt.CursorShape.SplitVCursor)
        else:
            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)
            p = self.controller._paragraph_by_id(pos.para_id)
            is_link = False
            if p:
                from atboffice.modules.writer.models.document import locate

                item_idx, _, _ = locate(p, pos.offset, side="after")
                if 0 <= item_idx < len(p.runs):
                    it = p.runs[item_idx]
                    link = getattr(it.r_pr, "link", None) if hasattr(it, "r_pr") else None
                    if link and isinstance(link, dict) and "anchor" in link:
                        is_link = True
            if is_link:
                self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.viewport().setCursor(Qt.CursorShape.IBeamCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """End mouse selection drag or commit table resize."""
        pos_pt = self._event_pos(event)
        if event.button() == Qt.MouseButton.LeftButton:
            if self._resizing_table and self._resize_info:
                table = self._resize_info["table"]
                idx = self._resize_info["index"]
                kind = self._resize_info["kind"]
                init_sz = self._resize_info["initial_size"]

                if kind == "col":
                    delta_px = pos_pt.x() - self._resize_info["start_pt"].x()
                    delta_pt = self.px_to_pt(delta_px)
                    if 0 <= idx < len(table.grid):
                        table.grid[idx] = max(12.0, round(init_sz + delta_pt, 2))
                elif kind == "row":
                    delta_px = pos_pt.y() - self._resize_info["start_pt"].y()
                    delta_pt = self.px_to_pt(delta_px)
                    if 0 <= idx < len(table.rows):
                        table.rows[idx].tr_pr.h = max(12.0, round(init_sz + delta_pt, 2))
                        table.rows[idx].tr_pr.h_rule = "exact"

                self._resizing_table = False
                self._resize_info = None
                self._resize_guide_pos = None
                self.refresh_layout()
                return

            if self._float_drag is not None:
                _page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
                self._float_release(
                    pt_doc, bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                )
                return

            self._is_dragging = False
            if self.format_painter_props is not None:
                self._apply_format_painter()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Double-click: header/footer area enters header/footer editing, else select a word."""
        pos_pt = self._event_pos(event)
        if event.button() == Qt.MouseButton.LeftButton:
            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            kind = self.header_footer_zone(page_idx, pt_doc)
            if kind is not None:
                self.enter_header_footer_mode(kind)
                return
            if self.hf_edit_kind is not None:
                self.exit_header_footer_mode()
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)
            self.controller.select_word_at(pos)
            self.viewport().update()

    # ------------------------------------------------------------ header/footer mode
    def header_footer_zone(self, page_idx: int, pt: QPointF) -> str | None:
        """ "hdr"/"ftr" when ``pt`` (page points) lies in a page's top/bottom margin.

        Only paper views show the margins, so Normal/Web/Reading never match.
        """
        if self.view_mode != ViewMode.PRINT or not self.pagination.pages:
            return None
        page = self.pagination.pages[max(0, min(page_idx, len(self.pagination.pages) - 1))]
        if not 0.0 <= pt.x() <= page.width:
            return None
        if 0.0 <= pt.y() < page.body_top:
            return "hdr"
        if page.height - page.body_bottom_gap < pt.y() <= page.height:
            return "ftr"
        return None

    def enter_header_footer_mode(self, kind: str) -> None:
        self.hf_edit_kind = kind
        self.header_footer_requested.emit(kind)
        self.viewport().update()

    def exit_header_footer_mode(self) -> None:
        self.hf_edit_kind = None
        self.viewport().update()

    # ------------------------------------------------------------ floating objects
    def selected_float(self) -> Any | None:
        return self._float_sel[1] if self._float_sel else None

    def select_float(self, page_idx: int | None, item: Any | None) -> None:
        self._float_sel = (page_idx, item) if item is not None and page_idx is not None else None
        self.viewport().update()

    def _selected_float_box(self) -> tuple[int, Any] | None:
        if not self._float_sel or not self.pagination.pages:
            return None
        from atboffice.modules.writer.views import float_edit

        page_idx, item = self._float_sel
        pages = self.pagination.pages
        order = [page_idx] + [i for i in range(len(pages)) if i != page_idx]
        for idx in order:  # relayout may move the object to another page
            if 0 <= idx < len(pages):
                fb = float_edit.box_for_item(pages[idx], item)
                if fb is not None:
                    return idx, fb
        return None

    def _float_press(self, page_idx: int, pt: QPointF) -> bool:
        """Start selecting/moving/resizing a floating object. True when consumed."""
        from atboffice.modules.writer.views import float_edit

        if not self.pagination.pages:
            return False
        tol = self.px_to_pt(5.0)
        found = self._selected_float_box()
        if found is not None and found[0] == page_idx:
            handle = float_edit.handle_at(found[1], pt, tol)
            if handle is not None:
                fb = found[1]
                self._float_drag = float_edit.FloatDrag(
                    page_idx, fb.item, handle, QPointF(pt), (fb.x, fb.y, fb.w, fb.h)
                )
                return True
        page = self.pagination.pages[max(0, min(page_idx, len(self.pagination.pages) - 1))]
        fb = float_edit.float_at(page, pt)
        if fb is None or getattr(fb.item, "float_pr", None) is None:
            if self._float_sel is not None:
                self.select_float(None, None)
            return False
        self.setFocus()
        self.select_float(page_idx, fb.item)
        self._float_drag = float_edit.FloatDrag(
            page_idx, fb.item, None, QPointF(pt), (fb.x, fb.y, fb.w, fb.h)
        )
        return True

    def _float_release(self, pt: QPointF, lock_aspect: bool = False) -> None:
        from atboffice.modules.writer.views import float_edit

        drag, self._float_drag = self._float_drag, None
        if drag is None:
            return
        changed = self.run_undoable(lambda: float_edit.apply_drag(drag, pt, lock_aspect))
        if changed is False:
            self.viewport().update()

    def delete_selected_float(self) -> bool:
        """Remove the selected floating object from its paragraph (one undo step)."""
        item = self.selected_float()
        if item is None:
            return False

        from atboffice.modules.writer.models.document import all_stories

        def mutate() -> bool:
            for story in all_stories(self.doc):
                for para in story.paras:
                    for i, run in enumerate(para.runs):
                        if run is item:
                            del para.runs[i]
                            return True
            return False

        self._float_sel = None
        return bool(self.run_undoable(mutate))

    def _float_key(self, event: QKeyEvent) -> bool:
        key = event.key()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            return self.delete_selected_float()
        if key == Qt.Key.Key_Escape:
            self.select_float(None, None)
            return True
        self.select_float(None, None)  # typing returns to the text
        return False

    def _float_hover_cursor(self, vp_pt: QPoint) -> bool:
        from atboffice.modules.writer.views import float_edit

        if not self.pagination.pages:
            return False
        page_idx, pt = self.viewport_to_doc_coords(vp_pt)
        found = self._selected_float_box()
        if found is not None and found[0] == page_idx:
            handle = float_edit.handle_at(found[1], pt, self.px_to_pt(5.0))
            if handle is not None:
                self.viewport().setCursor(float_edit.cursor_for(handle))
                return True
        page = self.pagination.pages[max(0, min(page_idx, len(self.pagination.pages) - 1))]
        fb = float_edit.float_at(page, pt)
        if fb is not None and getattr(fb.item, "float_pr", None) is not None:
            self.viewport().setCursor(float_edit.cursor_for(None))
            return True
        return False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Dispatch keyboard events to CaretController or trigger F7 spelling dialog."""
        if event.key() == Qt.Key.Key_F7:
            self.open_spelling_dialog()
            event.accept()
            return

        if self._float_sel is not None and self._float_key(event):
            event.accept()
            return

        if self.controller.handle_key_event(event):
            event.accept()
            self.scroll_to_caret()
            self.viewport().update()
        else:
            super().keyPressEvent(event)

    def open_spelling_dialog(self) -> None:
        """Open Spelling and Grammar check modal dialog (F7)."""
        from atboffice.modules.writer.dialogs.spelling_dialog import SpellingGrammarDialog

        dlg = SpellingGrammarDialog(self.doc, controller=self.controller, parent=self)
        dlg.exec()
        self.viewport().update()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Display right-click context menu with spelling corrections or standard actions."""
        pos_pt = self._event_pos(event)
        page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
        pos = self.controller.canvas_to_pos(page_idx, pt_doc)

        menu = QMenu(self)
        p = self.controller._paragraph_by_id(pos.para_id)
        misspelled_word = None
        word_start = 0
        word_end = 0

        if p:
            pt = ptext(p)
            for w, s, e in self.spell_engine.tokenize_words(pt):
                if s <= pos.offset <= e:
                    if not self.spell_engine.is_valid_word(w):
                        misspelled_word = w
                        word_start = s
                        word_end = e
                    break

        if misspelled_word and p is not None:
            suggestions = self.spell_engine.suggest(misspelled_word, max_suggestions=5)
            if suggestions:
                for sugg in suggestions:
                    act = menu.addAction(sugg)
                    bold_font = act.font()
                    bold_font.setBold(True)
                    act.setFont(bold_font)

                    def _make_handler(target_sugg: str, para: Paragraph, s: int, e: int):
                        return lambda: self._replace_word_in_para(para, s, e, target_sugg)

                    act.triggered.connect(_make_handler(sugg, p, word_start, word_end))
            else:
                act_no_sugg = menu.addAction(safe_tr("(无拼写建议)"))
                act_no_sugg.setEnabled(False)

            menu.addSeparator()

            act_ignore = menu.addAction(safe_tr("全部忽略(&I)"))
            act_ignore.triggered.connect(
                lambda checked=False, w=misspelled_word: self._ignore_word_all(w)
            )

            act_add = menu.addAction(safe_tr("添加到词典(&A)"))
            act_add.triggered.connect(
                lambda checked=False, w=misspelled_word: self._add_word_to_dict(w)
            )

            menu.addSeparator()

        # Standard editing actions
        act_cut = menu.addAction(safe_tr("剪切(&T)"))
        act_cut.setEnabled(not self.controller.selection.is_collapsed)
        act_cut.triggered.connect(self.cut_selection)

        act_copy = menu.addAction(safe_tr("复制(&C)"))
        act_copy.setEnabled(not self.controller.selection.is_collapsed)
        act_copy.triggered.connect(self.copy_selection)

        act_paste = menu.addAction(safe_tr("粘贴(&P)"))
        act_paste.triggered.connect(self.paste_from_clipboard)

        menu.addSeparator()
        act_select_all = menu.addAction(safe_tr("全选(&A)"))
        act_select_all.triggered.connect(self.controller.select_all)

        menu.exec(event.globalPos())

    def _replace_word_in_para(self, p: Paragraph, start: int, end: int, replacement: str) -> None:
        """Replace text span in paragraph and refresh canvas."""
        delete_range_in_paragraph(p, start, end)
        insert_text_in_paragraph(p, start, replacement)
        self.controller.pos = DocPos(p.id, start + len(replacement))
        self.controller.selection = Selection(self.controller.pos, self.controller.pos)
        self.controller.repaginate_and_refresh()
        self.viewport().update()

    def _ignore_word_all(self, word: str) -> None:
        """Ignore word in session and repaint."""
        self.spell_engine.ignore_all(word)
        self.viewport().update()

    def _add_word_to_dict(self, word: str) -> None:
        """Add word to custom dictionary and repaint."""
        self.spell_engine.add_to_custom_dict(word)
        self.viewport().update()

    def copy_selection(self) -> None:
        """Copy the selection as plain text and formatted HTML (Office Clipboard keeps both)."""
        from PySide6.QtCore import QMimeData

        text = self.controller.get_selected_text()
        if not text:
            return
        cb = QGuiApplication.clipboard()
        if not cb:
            return
        mime = QMimeData()
        mime.setText(text)
        html_text = self._selection_html()
        if html_text:
            mime.setHtml(html_text)
        cb.setMimeData(mime)

    def _selection_html(self) -> str:
        from atboffice.modules.writer.io.clipboard_html import selection_html

        ctl = self.controller
        if ctl.selection.is_collapsed:
            return ""
        start, end = ctl.selection.ordered_range(self.doc)
        p_start = ctl._paragraph_by_id(start.para_id)
        p_end = ctl._paragraph_by_id(end.para_id)
        if p_start is None or p_end is None:
            return ""
        if p_start is p_end:
            return selection_html([(p_start, start.offset, end.offset)])
        paras = paras_between(self.doc, p_start, p_end)
        segments = []
        for i, para in enumerate(paras):
            a = start.offset if i == 0 else 0
            b = end.offset if i == len(paras) - 1 else None
            segments.append((para, a, b))
        return selection_html(segments)

    def cut_selection(self) -> None:
        """Cut selected text to system clipboard."""
        self.copy_selection()
        with self.controller.edit_scope("剪切"):
            self.controller.delete_selection()

    def paste_from_clipboard(self) -> None:
        """Paste plain text from system clipboard."""
        cb = QGuiApplication.clipboard()
        if cb:
            text = cb.text()
            if text:
                with self.controller.edit_scope("粘贴"):
                    self.controller.insert_text(text)
