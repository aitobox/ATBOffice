"""Writer canvas painting of pages, text, selection and caret."""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QTextLayout,
    QTextOption,
)

from atboffice.modules.writer.layout.math_layout import paint_math
from atboffice.modules.writer.layout.pagination import (
    Page,
)
from atboffice.modules.writer.layout.portions import (
    PortionType,
    measure_text_width,
)
from atboffice.modules.writer.models.document import (
    info,
    plen,
)
from atboffice.modules.writer.models.drawing import PictureItem
from atboffice.modules.writer.models.omml import OfficeMathItem
from atboffice.modules.writer.views.canvas_common import (
    _UNDERLINE_PEN_STYLES,
    _WAVY_UNDERLINES,
    COLOR_CARET,
    COLOR_PAGE_BORDER,
    COLOR_PAGE_PAPER,
    COLOR_SELECTION,
    COLOR_WORKSPACE_BG,
    WORD_HIGHLIGHT_COLORS,
)
from atboffice.modules.writer.views.caret_controller import (
    DocPos,
)
from atboffice.modules.writer.views.view_modes import ViewMode


class CanvasPaintMixin:
    """Paints pages, text runs and their decorations, the selection and the caret."""

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint workspace background, paper pages, shadow, text portions, selection, and caret."""
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # 1. Paint Workspace Background
        painter.fillRect(self.viewport().rect(), COLOR_WORKSPACE_BG)

        if not self.pagination or not self.pagination.pages:
            painter.end()
            return

        visible_rect = self.viewport().rect()
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()

        paper_view = self.view_mode in (ViewMode.PRINT, ViewMode.READING)
        if not paper_view:
            # Normal / Web layout: one continuous white sheet, no paper
            painter.fillRect(self.viewport().rect(), COLOR_PAGE_PAPER)
        slots = self.page_slots() if not paper_view else None

        # Render each page
        for p_idx, page in enumerate(self.pagination.pages):
            rect_canvas = self.page_rect_canvas(p_idx)
            if rect_canvas.isEmpty():
                continue
            rect_vp = QRectF(
                rect_canvas.left() - scroll_x,
                rect_canvas.top() - scroll_y,
                rect_canvas.width(),
                rect_canvas.height(),
            )
            clip_vp = rect_vp
            if slots is not None:
                clip = slots[p_idx][1]
                clip_vp = QRectF(
                    clip.left() - scroll_x, clip.top() - scroll_y, clip.width(), clip.height()
                )

            # Viewport culling
            if not clip_vp.intersects(QRectF(visible_rect)):
                continue

            painter.save()
            if not paper_view:
                painter.setClipRect(clip_vp)

            # 2. Paint Page Drop Shadow (only in PRINT and READING modes)
            if paper_view:
                self._paint_page_shadow(painter, rect_vp)

                # 3. Paint Page Sheet Background & Border
                painter.fillRect(rect_vp, COLOR_PAGE_PAPER)
                painter.setPen(QPen(COLOR_PAGE_BORDER, 1.0))
                painter.drawRect(rect_vp)

            # 4. Paint Selection Highlights on this page
            self._paint_selection(painter, p_idx, rect_vp, page)

            # 5. Paint Document Content (Text Lines & Portions)
            self._paint_page_content(painter, rect_vp, page)

            # 5.05 Header/footer editing: dim the body, frame the header/footer area
            if self.hf_edit_kind and paper_view:
                self._paint_hf_edit_overlay(painter, rect_vp, page)

            # 5.06 Selected floating object: frame and sizing handles
            self._paint_float_selection(painter, p_idx, rect_vp, page)

            # 5.1 Paint Comment Balloons & Range Annotations
            if self.show_comments and paper_view:
                self._paint_comments(painter, rect_vp, page)
            painter.restore()

            # Normal view: a dotted line where one page ends and the next begins
            if self.view_mode == ViewMode.NORMAL and p_idx > 0:
                painter.setPen(QPen(QColor(128, 128, 128), 1.0, Qt.PenStyle.DotLine))
                painter.drawLine(
                    QPointF(0.0, clip_vp.top()),
                    QPointF(float(self.viewport().width()), clip_vp.top()),
                )

        # 5.2 Formatting marks (¶ at each paragraph end) when toggled on
        if self.show_formatting_marks:
            self._paint_formatting_marks(painter)

        # 6. Paint Blinking Caret
        if self.hasFocus() and self.controller.caret_visible:
            self._paint_caret(painter)

        # 7. Paint Table Resize Guide Line
        if self._resizing_table and self._resize_guide_pos and self._resize_info:
            guide_pen = QPen(QColor(0, 51, 153), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(guide_pen)
            if self._resize_info.get("kind") == "col":
                gx = float(self._resize_guide_pos.x())
                painter.drawLine(QPointF(gx, 0), QPointF(gx, self.viewport().height()))
            elif self._resize_info.get("kind") == "row":
                gy = float(self._resize_guide_pos.y())
                painter.drawLine(QPointF(0, gy), QPointF(self.viewport().width(), gy))

        # 8. Paint Ruler Guide Line
        if self._ruler_guide_x is not None or self._ruler_guide_y is not None:
            ruler_pen = QPen(QColor(60, 60, 60, 200), 1.0, Qt.PenStyle.DashLine)
            painter.setPen(ruler_pen)
            if self._ruler_guide_x is not None:
                gx = self._ruler_guide_x - scroll_x
                painter.drawLine(QPointF(gx, 0), QPointF(gx, float(self.viewport().height())))
            if self._ruler_guide_y is not None:
                gy = self._ruler_guide_y - scroll_y
                painter.drawLine(QPointF(0, gy), QPointF(float(self.viewport().width()), gy))

        painter.end()

    def _draw_wavy_line(
        self,
        painter: QPainter,
        x1: float,
        x2: float,
        y: float,
        color: QColor = QColor(255, 0, 0),
        amplitude: float = 1.2,
        pen_width: float = 1.0,
    ) -> None:
        """Draw a wavy line; the defaults are the classic red spellcheck squiggle."""
        if x2 <= x1:
            return
        path = QPainterPath()
        path.moveTo(x1, y)
        step = max(2.0, amplitude * 5.0 / 3.0)
        curr_x = x1
        up = True
        while curr_x < x2:
            next_x = min(curr_x + step, x2)
            target_y = y - amplitude if up else y + amplitude
            path.lineTo(next_x, target_y)
            curr_x = next_x
            up = not up

        old_pen = painter.pen()
        painter.setPen(QPen(color, pen_width))
        painter.drawPath(path)
        painter.setPen(old_pen)

    def _build_portion_font(self, po: Any) -> tuple[QFont, QColor]:
        """Construct styled QFont and QColor for a layout portion under active zoom."""
        font_family = getattr(po, "font_family", None) or "Times New Roman"
        font_size_pt = getattr(po, "font_size", None) or 12.0
        font = QFont(font_family)
        font.setPointSizeF(font_size_pt * self._zoom)
        if getattr(po, "bold", False):
            font.setBold(True)
        if getattr(po, "italic", False):
            font.setItalic(True)
        color_str = getattr(po, "color", None) or "#000000"
        if color_str == "auto":
            color_str = "#000000"
        return font, QColor(color_str)

    def _draw_text_decorations(
        self,
        painter: QPainter,
        po: Any,
        font: QFont,
        color: QColor,
        x1_px: float,
        x2_px: float,
        baseline_px: float,
    ) -> None:
        """Draw a portion's underline and strike over the given horizontal span."""
        self._draw_underline_decoration(painter, po, font, color, x1_px, x2_px, baseline_px)
        self._draw_strike_decoration(painter, po, font, color, x1_px, x2_px, baseline_px)

    def _draw_underline_decoration(
        self,
        painter: QPainter,
        po: Any,
        font: QFont,
        color: QColor,
        x1_px: float,
        x2_px: float,
        baseline_px: float,
    ) -> None:
        """Draw a portion's underline in its Word style; unknown styles draw a single line."""
        style = getattr(po, "underline", None)
        if not style or style == "none" or x2_px <= x1_px:
            return
        if style == "words" and po.type == PortionType.BLANK:
            return
        font_size_pt = getattr(po, "font_size", None) or 12.0
        y_px = baseline_px + font_size_pt * self._zoom * 0.12
        thickness = max(0.75 * self._zoom, self._metrics(font).lineWidth())
        if style == "thick" or "Heavy" in style:
            thickness *= 2.0
        if style in _WAVY_UNDERLINES:
            self._draw_wavy_line(painter, x1_px, x2_px, y_px, color, max(1.2, thickness), thickness)
            return
        pen = QPen(color, thickness, _UNDERLINE_PEN_STYLES.get(style, Qt.PenStyle.SolidLine))
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(x1_px, y_px), QPointF(x2_px, y_px))
        if style == "double":
            second_y = y_px + max(1.5 * self._zoom, thickness * 2.0)
            painter.drawLine(QPointF(x1_px, second_y), QPointF(x2_px, second_y))

    def _paint_highlight(
        self, painter: QPainter, po: Any, font: QFont, x1: float, x2: float, baseline: float
    ) -> None:
        """Fill the text-highlight colour (w:highlight) behind a portion."""
        name = getattr(po, "highlight", None)
        if not name or name == "none" or x2 <= x1:
            return
        hex_color = WORD_HIGHLIGHT_COLORS.get(name, name if str(name).startswith("#") else None)
        if not hex_color:
            return
        fm = self._metrics(font)
        painter.fillRect(
            QRectF(x1, baseline - fm.ascent(), x2 - x1, fm.ascent() + fm.descent()),
            QColor(hex_color),
        )

    def _draw_strike_decoration(
        self,
        painter: QPainter,
        po: Any,
        font: QFont,
        color: QColor,
        x1_px: float,
        x2_px: float,
        baseline_px: float,
    ) -> None:
        """Draw a portion's strike; double strike wins when both flags are set."""
        is_double = bool(getattr(po, "dstrike", False))
        if not is_double and not getattr(po, "strikethrough", False):
            return
        font_size_pt = getattr(po, "font_size", None) or 12.0
        mid_y = baseline_px - font_size_pt * self._zoom * 0.3
        thickness = max(0.75 * self._zoom, self._metrics(font).lineWidth())
        pen = QPen(color, thickness)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        gap = max(1.5 * self._zoom, thickness)
        for offset in (-gap, gap) if is_double else (0.0,):
            painter.drawLine(QPointF(x1_px, mid_y + offset), QPointF(x2_px, mid_y + offset))

    def _draw_spellcheck_for_text(
        self,
        painter: QPainter,
        font: QFont,
        text: str,
        x_px: float,
        baseline_px: float,
    ) -> None:
        """Draw wavy red spellcheck underlines for misspelled tokens in text."""
        if getattr(self, "_printing", False):
            return
        fm = self._metrics(font)
        for w, w_start, w_end in self.spell_engine.tokenize_words(text):
            if not self.spell_engine.is_valid_word(w):
                w_x1 = x_px + fm.horizontalAdvance(text[:w_start])
                w_x2 = x_px + fm.horizontalAdvance(text[:w_end])
                self._draw_wavy_line(painter, w_x1, w_x2, baseline_px + 2.5, QColor(255, 0, 0))

    def _paint_line_portions(
        self,
        painter: QPainter,
        page_rect: QRectF,
        line: Any,
        start_x_pt: float,
        line_y_pt: float,
        check_spell: bool = True,
    ) -> None:
        """Render line portions with RTL BiDi, style coalescing, tabs, graphics, and spellcheck."""
        y_px = page_rect.top() + self.pt_to_px(line_y_pt)
        baseline_px = y_px + self.pt_to_px(line.baseline - line.top)
        should_spell = (
            check_spell
            and not getattr(self.doc, "hide_spelling_errors", False)
            and self.spell_engine.is_enabled("spelling/check_as_you_type", True)
        )

        # RTL BiDi lines: draw unified text via QTextLayout for natural Unicode BiDi shaping
        if getattr(line, "is_rtl", False):
            trimmed = list(line.portions)
            while trimmed and trimmed[-1].type == PortionType.BLANK:
                trimmed.pop()
            text_pts = [po for po in trimmed if po.type in (PortionType.TEXT, PortionType.BLANK)]
            if text_pts and len(text_pts) == len(trimmed):
                full_text = "".join(po.text for po in text_pts)
                if full_text:
                    rep_po = next(
                        (po for po in text_pts if po.type == PortionType.TEXT), text_pts[0]
                    )
                    font, pen_col = self._build_portion_font(rep_po)
                    painter.setFont(font)
                    painter.setPen(QPen(pen_col))
                    tl = self._text_layout(full_text, font)
                    opt = QTextOption(Qt.AlignmentFlag.AlignRight)
                    opt.setTextDirection(Qt.LayoutDirection.RightToLeft)
                    tl.setTextOption(opt)
                    tl.beginLayout()
                    box_w_px = max(20.0, self.pt_to_px(max(line.width, 10.0)) + 8.0)
                    tline = tl.createLine()
                    if tline.isValid():
                        tline.setLineWidth(box_w_px)
                    tl.endLayout()
                    if tline.isValid():
                        right_px = page_rect.left() + self.pt_to_px(start_x_pt + line.width)
                        left_px = right_px - box_w_px
                        tline.draw(painter, QPointF(left_px, baseline_px - tline.ascent()))
                        char_pos = 0
                        for po in text_pts:
                            char_end = char_pos + len(po.text)
                            edge_a = left_px + tline.cursorToX(char_pos)[0]
                            edge_b = left_px + tline.cursorToX(char_end)[0]
                            po_font, po_col = self._build_portion_font(po)
                            self._draw_text_decorations(
                                painter,
                                po,
                                po_font,
                                po_col,
                                min(edge_a, edge_b),
                                max(edge_a, edge_b),
                                baseline_px,
                            )
                            char_pos = char_end
                        return

        portions = line.portions
        extra_blank = getattr(line, "extra_space_per_blank", 0.0)
        can_coalesce = math.isclose(extra_blank, 0.0, abs_tol=1e-6)

        # For justified pure-text lines, distribute actual Qt visual slack across blanks so
        # font substitution differences (e.g. missing Calibri -> system font) never overlap words.
        if not can_coalesce and portions:
            trimmed_j = list(portions)
            while trimmed_j and trimmed_j[-1].type == PortionType.BLANK:
                trimmed_j.pop()
            if trimmed_j and all(
                p.type in (PortionType.TEXT, PortionType.BLANK) for p in trimmed_j
            ):
                target_w_px = self.pt_to_px(line.width)
                word_adv_px: list[float] = []
                blank_indices: list[int] = []
                for p_i, pt in enumerate(trimmed_j):
                    if pt.type == PortionType.BLANK:
                        blank_indices.append(p_i)
                        word_adv_px.append(0.0)
                    else:
                        f, _ = self._build_portion_font(pt)
                        word_adv_px.append(self._metrics(f).horizontalAdvance(pt.text))
                total_words_px = sum(word_adv_px)
                if blank_indices:
                    per_blank_px = max(2.5, (target_w_px - total_words_px) / len(blank_indices))
                    cur_px = page_rect.left() + self.pt_to_px(start_x_pt)
                    for p_i, pt in enumerate(trimmed_j):
                        if pt.type == PortionType.BLANK:
                            f, blank_col = self._build_portion_font(pt)
                            self._draw_text_decorations(
                                painter,
                                pt,
                                f,
                                blank_col,
                                cur_px,
                                cur_px + per_blank_px,
                                baseline_px,
                            )
                            cur_px += per_blank_px
                        elif pt.text:
                            font, pen_col = self._build_portion_font(pt)
                            pt_base_px = baseline_px - self.pt_to_px(pt.baseline_shift)
                            self._paint_highlight(
                                painter, pt, font, cur_px, cur_px + word_adv_px[p_i], pt_base_px
                            )
                            painter.setFont(font)
                            painter.setPen(QPen(pen_col))
                            painter.drawText(QPointF(cur_px, pt_base_px), pt.text)
                            if should_spell:
                                self._draw_spellcheck_for_text(
                                    painter, font, pt.text, cur_px, pt_base_px
                                )
                            self._draw_text_decorations(
                                painter,
                                pt,
                                font,
                                pen_col,
                                cur_px,
                                cur_px + word_adv_px[p_i],
                                pt_base_px,
                            )
                            cur_px += word_adv_px[p_i]
                    return

        cur_px = page_rect.left() + self.pt_to_px(start_x_pt)
        line_jc = getattr(line, "jc", "left")
        if can_coalesce and line_jc in ("center", "right") and portions:
            trimmed_a = list(portions)
            while trimmed_a and trimmed_a[-1].type == PortionType.BLANK:
                trimmed_a.pop()
            if trimmed_a and all(
                p.type in (PortionType.TEXT, PortionType.BLANK) for p in trimmed_a
            ):
                qt_w_px = 0.0
                for pt in trimmed_a:
                    if pt.text:
                        f, _ = self._build_portion_font(pt)
                        qt_w_px += self._metrics(f).horizontalAdvance(pt.text)
                layout_w_px = self.pt_to_px(line.width)
                if line_jc == "center":
                    cur_px += (layout_w_px - qt_w_px) / 2.0
                else:
                    cur_px += layout_w_px - qt_w_px

        last_ink_idx = max(
            (i for i, po in enumerate(portions) if po.type != PortionType.BLANK), default=-1
        )
        for po_idx, po in enumerate(portions):
            po_w_px = self.pt_to_px(po.width)
            if po.type == PortionType.TEXT and po.text:
                font, pen_col = self._build_portion_font(po)
                po_base_px = baseline_px - self.pt_to_px(po.baseline_shift)
                self._paint_highlight(
                    painter,
                    po,
                    font,
                    cur_px,
                    cur_px + self._metrics(font).horizontalAdvance(po.text),
                    po_base_px,
                )
                painter.setFont(font)
                painter.setPen(QPen(pen_col))
                painter.drawText(QPointF(cur_px, po_base_px), po.text)
                if should_spell:
                    self._draw_spellcheck_for_text(painter, font, po.text, cur_px, po_base_px)
                text_adv_px = self._metrics(font).horizontalAdvance(po.text)
                self._draw_text_decorations(
                    painter, po, font, pen_col, cur_px, cur_px + text_adv_px, po_base_px
                )
                cur_px += text_adv_px
                continue
            if po.type == PortionType.BLANK and po.text:
                font, pen_col = self._build_portion_font(po)
                blank_adv_px = (
                    self._metrics(font).horizontalAdvance(po.text) if can_coalesce else po_w_px
                )
                if po_idx < last_ink_idx:
                    self._draw_text_decorations(
                        painter, po, font, pen_col, cur_px, cur_px + blank_adv_px, baseline_px
                    )
                cur_px += blank_adv_px
                continue
            if po.type == PortionType.TAB and po.width > 0:
                tab_data = getattr(po, "data", None)
                leader = getattr(tab_data, "leader", "none") if tab_data else "none"
                if leader and leader != "none":
                    p1 = QPointF(cur_px, baseline_px)
                    p2 = QPointF(cur_px + po_w_px, baseline_px)
                    if leader == "dot":
                        painter.setPen(QPen(QColor(100, 100, 100), 1.0, Qt.PenStyle.DotLine))
                        painter.drawLine(p1, p2)
                    elif leader == "hyphen":
                        painter.setPen(QPen(QColor(100, 100, 100), 1.0, Qt.PenStyle.DashLine))
                        painter.drawLine(p1, p2)
                    elif leader == "underscore":
                        painter.setPen(QPen(QColor(100, 100, 100), 1.0, Qt.PenStyle.SolidLine))
                        painter.drawLine(
                            QPointF(cur_px, baseline_px + 2),
                            QPointF(cur_px + po_w_px, baseline_px + 2),
                        )
            elif po.type == PortionType.GRAPHIC:
                if isinstance(po.data, OfficeMathItem):
                    paint_math(painter, po.data, cur_px, baseline_px, self._zoom)
                elif isinstance(po.data, PictureItem) or getattr(po.data, "t", "") in (
                    "picture",
                    "img",
                ):
                    pic_h_px = self.pt_to_px(po.ascent)
                    dest_rect = QRectF(cur_px, baseline_px - pic_h_px, po_w_px, pic_h_px)
                    self._paint_picture(painter, po.data, dest_rect, self._zoom)

            cur_px += po_w_px

    def _paint_page_content(self, painter: QPainter, page_rect: QRectF, page: Page) -> None:
        """Render lines, formatted portions, and table structures on a single page."""
        # 1. Render Header if present
        if page.header:
            self._paint_header_footer(painter, page_rect, page, page.header, is_header=True)

        # 1.5. Render background floating shapes (behind == True)
        for fb in getattr(page, "float_boxes", []):
            if fb.behind:
                self._paint_float_box(painter, page_rect, page, fb)

        # 2. Render Page Regions and Paragraphs/Tables
        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    if frag.table_layout is not None:
                        tl = frag.table_layout
                        frag_x = page.body_left + col.left
                        frag_y = page.body_top + col.top + frag.top

                        self._paint_table_layout(painter, page_rect, tl, frag_x + tl.x, frag_y)
                        continue

                    frag_top = page.body_top + col.top + frag.top
                    for line in frag.lines:
                        line_y = frag_top + line.top
                        cur_x = page.body_left + col.left + line.indent_left
                        self._paint_line_portions(
                            painter, page_rect, line, cur_x, line_y, check_spell=True
                        )

        # 2.5. Render foreground floating shapes (behind == False)
        for fb in getattr(page, "float_boxes", []):
            if not fb.behind:
                self._paint_float_box(painter, page_rect, page, fb)

        # 2.6. Render Footnote Area if present
        if getattr(page, "footnote_area", None) and page.footnote_area.fragments:
            self._paint_footnote_area(painter, page_rect, page, page.footnote_area)

        # 3. Render Footer if present
        if page.footer:
            self._paint_header_footer(painter, page_rect, page, page.footer, is_header=False)

    def _metrics(self, font: QFont) -> QFontMetricsF:
        """Font metrics for the device being painted (the printer while printing)."""
        device = getattr(self, "_print_device", None)
        return QFontMetricsF(font, device) if device is not None else QFontMetricsF(font)

    def _text_layout(self, text: str, font: QFont) -> QTextLayout:
        device = getattr(self, "_print_device", None)
        return QTextLayout(text, font, device) if device is not None else QTextLayout(text, font)

    def render_page_to_painter(
        self,
        painter: QPainter,
        page: Page,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
    ) -> None:
        """Paint ``page`` in points onto ``painter`` (printer, PDF, image) with screen fidelity.

        Uses the on-screen page painter (bullets, highlights, justification, borders and
        shading, watermarks, charts, shapes, headers/footers) in a print mode: coordinates
        are points, fonts are sized for the target device, and editing aids (selection,
        caret, spell-check squiggles, comments, formatting marks) are not drawn.
        """
        device = painter.device()
        dpi = float(device.logicalDpiY()) if device is not None else 72.0
        if dpi <= 0:
            dpi = 72.0
        saved = (
            self.pt_to_px_ratio,
            self._zoom,
            getattr(self, "_printing", False),
            getattr(self, "_print_device", None),
        )
        self.pt_to_px_ratio = dpi / 72.0
        self._zoom = 72.0 / dpi
        self._printing = True
        self._print_device = device
        painter.save()
        try:
            painter.translate(origin_x, origin_y)
            page_rect = QRectF(0.0, 0.0, float(page.width), float(page.height))
            painter.fillRect(page_rect, COLOR_PAGE_PAPER)
            self._paint_page_content(painter, page_rect, page)
        finally:
            painter.restore()
            (self.pt_to_px_ratio, self._zoom, self._printing, self._print_device) = saved

    def _paint_selection(
        self, painter: QPainter, page_idx: int, page_rect: QRectF, page: Page
    ) -> None:
        """Render selection highlight rects for active text selection."""
        sel = self.controller.selection
        if sel.is_collapsed:
            return

        start, end = sel.ordered_range(self.doc)

        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    if frag.paragraph is None:
                        continue
                    pid = frag.paragraph.id
                    inf = info(self.doc, pid)
                    if not inf or "p" not in inf:
                        continue
                    p_order = inf["p"]._o

                    inf_s = info(self.doc, start.para_id)
                    inf_e = info(self.doc, end.para_id)
                    order_s = inf_s["p"]._o if inf_s and "p" in inf_s else 0
                    order_e = inf_e["p"]._o if inf_e and "p" in inf_e else 0

                    # Check if paragraph is within selection range
                    if p_order < order_s or p_order > order_e:
                        continue

                    p_len = plen(frag.paragraph)
                    sel_start_in_p = start.offset if p_order == order_s else 0
                    sel_end_in_p = end.offset if p_order == order_e else p_len

                    frag_top = page.body_top + col.top + frag.top
                    for line in frag.lines:
                        if not line.portions:
                            continue
                        l_start = line.portions[0].char_offset
                        l_end = line.portions[-1].char_offset + line.portions[-1].length

                        # Check line overlap with paragraph selection
                        inter_start = max(l_start, sel_start_in_p)
                        inter_end = min(l_end, sel_end_in_p)

                        if inter_start < inter_end:
                            # Calculate x coordinates of selection on this line
                            x1 = page.body_left + col.left + line.indent_left
                            for po in line.portions:
                                if inter_start >= po.char_offset + po.length:
                                    x1 += po.width
                                else:
                                    sub = max(0, inter_start - po.char_offset)
                                    x1 += measure_text_width(
                                        po.text[:sub], po.font_size, po.font_family
                                    )
                                    break

                            x2 = page.body_left + col.left + line.indent_left
                            for po in line.portions:
                                if inter_end >= po.char_offset + po.length:
                                    x2 += po.width
                                else:
                                    sub = max(0, inter_end - po.char_offset)
                                    x2 += measure_text_width(
                                        po.text[:sub], po.font_size, po.font_family
                                    )
                                    break

                            rect_x = page_rect.left() + self.pt_to_px(x1)
                            rect_y = page_rect.top() + self.pt_to_px(frag_top + line.top)
                            rect_w = max(4.0, self.pt_to_px(x2 - x1))
                            rect_h = self.pt_to_px(max(line.height, 14.0))

                            painter.fillRect(
                                QRectF(rect_x, rect_y, rect_w, rect_h),
                                COLOR_SELECTION,
                            )

    def _paint_formatting_marks(self, painter: QPainter) -> None:
        """Draw a pilcrow at the end of every visible paragraph (Show/Hide ¶)."""
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        vp_h = self.viewport().height()
        painter.save()
        mark_font = QFont("Arial")
        painter.setPen(QColor(74, 111, 165))
        for p in self.doc.all_paras():
            end = plen(p)
            try:
                page_idx, pt_page, h_pt = self.controller.pos_to_canvas(DocPos(p.id, end))
            except Exception:
                continue
            page_rect = self.page_rect_canvas(page_idx)
            x = page_rect.left() - scroll_x + self.pt_to_px(pt_page.x()) + 1
            y = page_rect.top() - scroll_y + self.pt_to_px(pt_page.y())
            h = max(6.0, self.pt_to_px(h_pt))
            if y + h < 0 or y > vp_h:
                continue
            mark_font.setPixelSize(max(6, int(h * 0.8)))
            painter.setFont(mark_font)
            painter.drawText(QPointF(x, y + h * 0.8), "\u00b6")
        painter.restore()

    def _paint_caret(self, painter: QPainter) -> None:
        """Render blinking caret at active position."""
        page_idx, pt_page, h_pt = self.controller.pos_to_canvas(self.controller.pos)
        page_rect = self.page_rect_canvas(page_idx)

        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()

        caret_vp_x = page_rect.left() - scroll_x + self.pt_to_px(pt_page.x())
        caret_vp_y = page_rect.top() - scroll_y + self.pt_to_px(pt_page.y())
        caret_vp_h = self.pt_to_px(h_pt)

        painter.setPen(QPen(COLOR_CARET, 1.5))
        painter.drawLine(
            QPointF(caret_vp_x, caret_vp_y),
            QPointF(caret_vp_x, caret_vp_y + caret_vp_h),
        )
