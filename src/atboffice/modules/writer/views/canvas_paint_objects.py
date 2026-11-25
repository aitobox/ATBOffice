"""Writer canvas painting of objects: pictures, charts, shapes, tables, comments, headers."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)

from atboffice.modules.presentation.chart.painter import ChartPainter
from atboffice.modules.writer.layout.math_layout import paint_math
from atboffice.modules.writer.layout.pagination import (
    Page,
    PageFootnoteArea,
    PageHeaderFooter,
)
from atboffice.modules.writer.layout.portions import (
    PortionType,
)
from atboffice.modules.writer.layout.table_layout import TableLayout
from atboffice.modules.writer.layout.wrap import FloatBox
from atboffice.modules.writer.models.document import (
    Paragraph,
)
from atboffice.modules.writer.models.drawing import ChartItem, PictureItem, ShapeItem
from atboffice.modules.writer.models.omml import OfficeMathItem
from atboffice.modules.writer.views.canvas_common import (
    COLOR_SHADOW_DARK,
    COLOR_SHADOW_LIGHT,
)
from atboffice.modules.writer.views.shape_painter import paint_shape

logger = logging.getLogger(__name__)


class CanvasObjectPaintMixin:
    """Paints pictures, charts, shapes, floating boxes, tables, comments, footnotes and headers."""

    def _get_border_pen(self, bp: Any, zoom: float) -> QPen | None:
        """Resolve a QPen for a BorderProperties object under active zoom."""
        if not bp or getattr(bp, "val", "none") in ("none", "nil", "hidden", "", None):
            return None
        val = str(bp.val).lower()
        sz_pt = max(0.5, float(getattr(bp, "sz", 0.5) or 0.5))
        pen_w = max(1.0, sz_pt * self.pt_to_px_ratio * zoom)
        color_val = getattr(bp, "color", "auto") or "auto"
        if color_val in ("auto", "none", ""):
            # "auto" border colour resolves to black (Word renders it as windowText).
            color = QColor(0, 0, 0)
        else:
            hex_c = color_val if color_val.startswith("#") else f"#{color_val}"
            color = QColor(hex_c)
        pen = QPen(color, pen_w)
        if "dash" in val:
            pen.setStyle(Qt.PenStyle.DashLine)
        elif "dot" in val:
            pen.setStyle(Qt.PenStyle.DotLine)
        else:
            pen.setStyle(Qt.PenStyle.SolidLine)
        return pen

    def _paint_page_shadow(self, painter: QPainter, page_rect: QRectF) -> None:
        """Draw classic Word 2003 physical paper drop shadow."""
        # Multi-layer shadow offset
        offset_x = 4.0
        offset_y = 4.0

        # Light ambient outer shadow
        outer_shadow = QRectF(
            page_rect.left() + 1.0,
            page_rect.top() + 1.0,
            page_rect.width() + offset_x + 1.0,
            page_rect.height() + offset_y + 1.0,
        )
        painter.fillRect(outer_shadow, COLOR_SHADOW_LIGHT)

        # Dark primary shadow
        primary_shadow = QRectF(
            page_rect.left() + 2.0,
            page_rect.top() + 2.0,
            page_rect.width() + offset_x - 1.0,
            page_rect.height() + offset_y - 1.0,
        )
        painter.fillRect(primary_shadow, COLOR_SHADOW_DARK)

    def _resolve_pixmap(self, pic: Any) -> QPixmap | None:
        """Resolve QPixmap for a PictureItem from cache, package, file, or raw data."""
        cache_key = getattr(pic, "image_part", "") or str(id(pic))
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        # 1. Check raw_data dict
        raw = getattr(pic, "raw_data", None)
        if isinstance(raw, dict):
            if "pixmap" in raw and isinstance(raw["pixmap"], QPixmap):
                if not raw["pixmap"].isNull():
                    self._pixmap_cache[cache_key] = raw["pixmap"]
                    return raw["pixmap"]
            if "image" in raw and isinstance(raw["image"], QImage) and not raw["image"].isNull():
                pm = QPixmap.fromImage(raw["image"])
                self._pixmap_cache[cache_key] = pm
                return pm
            if "bytes" in raw and isinstance(raw["bytes"], (bytes, bytearray)):
                pm = QPixmap()
                if pm.loadFromData(raw["bytes"]) and not pm.isNull():
                    self._pixmap_cache[cache_key] = pm
                    return pm

        # 2. Check source package parts
        part_name = getattr(pic, "image_part", "") or ""
        if part_name:
            pkg = getattr(self.doc, "_source_pkg", None) or self.doc.keep.get("source_pkg")
            if pkg is not None:
                candidates = [part_name, part_name.lstrip("/"), f"word/{part_name.lstrip('/')}"]
                for c in candidates:
                    try:
                        if hasattr(pkg, "has_part") and pkg.has_part(c):
                            data = pkg.read_part(c)
                            pm = QPixmap()
                            if pm.loadFromData(data) and not pm.isNull():
                                self._pixmap_cache[cache_key] = pm
                                return pm
                    except Exception:
                        pass

            # 3. Check local filesystem path
            import os

            if os.path.isfile(part_name):
                pm = QPixmap(part_name)
                if not pm.isNull():
                    self._pixmap_cache[cache_key] = pm
                    return pm

            # 4. Check doc.keep media dictionary
            media_dict = self.doc.keep.get("media", {})
            if isinstance(media_dict, dict) and part_name in media_dict:
                media_val = media_dict[part_name]
                if isinstance(media_val, (bytes, bytearray)):
                    pm = QPixmap()
                    if pm.loadFromData(media_val) and not pm.isNull():
                        self._pixmap_cache[cache_key] = pm
                        return pm

        return None

    def _paint_picture(
        self,
        painter: QPainter,
        pic: Any,
        dest_rect: QRectF,
        zoom: float = 1.0,
        is_vector: bool = False,
    ) -> None:
        """Render a PictureItem onto the canvas with DPR awareness, cropping, and rotation."""
        if dest_rect.width() <= 0 or dest_rect.height() <= 0:
            return

        if isinstance(pic, ShapeItem) and not pic.image_part:
            self._paint_shape(painter, pic, dest_rect, is_vector)
            return

        if isinstance(pic, ChartItem) and pic.chart is not None:
            self._paint_chart(painter, pic, dest_rect, is_vector)
            return

        pixmap = self._resolve_pixmap(pic)
        if pixmap is not None and not pixmap.isNull():
            painter.save()
            try:
                # Enable high-quality bilinear filtering for DPR scaling
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

                # Device pixel ratio awareness
                dpr = 1.0
                if hasattr(self, "devicePixelRatioF"):
                    try:
                        dpr = float(self.devicePixelRatioF())
                    except Exception:
                        dpr = 1.0
                elif painter.device() is not None and hasattr(
                    painter.device(), "devicePixelRatioF"
                ):
                    try:
                        dpr = float(painter.device().devicePixelRatioF())
                    except Exception:
                        dpr = 1.0
                if dpr > 1.0 and hasattr(pixmap, "setDevicePixelRatio"):
                    pixmap.setDevicePixelRatio(dpr)

                # Calculate source rect taking Crop into account
                pw = float(pixmap.width())
                ph = float(pixmap.height())
                crop = getattr(pic, "crop", None)
                if crop and (
                    getattr(crop, "left", 0.0)
                    or getattr(crop, "top", 0.0)
                    or getattr(crop, "right", 0.0)
                    or getattr(crop, "bottom", 0.0)
                ):
                    cl = max(0.0, float(getattr(crop, "left", 0.0) or 0.0))
                    ct = max(0.0, float(getattr(crop, "top", 0.0) or 0.0))
                    cr = max(0.0, float(getattr(crop, "right", 0.0) or 0.0))
                    cb = max(0.0, float(getattr(crop, "bottom", 0.0) or 0.0))
                    src_x = pw * cl
                    src_y = ph * ct
                    src_w = max(1.0, pw * max(0.01, 1.0 - cl - cr))
                    src_h = max(1.0, ph * max(0.01, 1.0 - ct - cb))
                    src_rect = QRectF(src_x, src_y, src_w, src_h)
                else:
                    src_rect = QRectF(0.0, 0.0, pw, ph)

                # Handle rotation
                rot = float(getattr(pic, "rotation", 0.0) or 0.0)
                if rot != 0.0:
                    center = dest_rect.center()
                    painter.translate(center)
                    painter.rotate(rot)
                    draw_box = QRectF(
                        -dest_rect.width() / 2.0,
                        -dest_rect.height() / 2.0,
                        dest_rect.width(),
                        dest_rect.height(),
                    )
                    painter.drawPixmap(draw_box, pixmap, src_rect)
                else:
                    painter.drawPixmap(dest_rect, pixmap, src_rect)
            finally:
                painter.restore()
        else:
            # Fallback placeholder for missing or unresolvable image
            painter.save()
            try:
                painter.fillRect(dest_rect, QColor("#F4F4F4"))
                painter.setPen(QPen(QColor("#B0B0B0"), 1.0, Qt.PenStyle.DashLine))
                painter.drawRect(dest_rect)
                painter.setPen(QPen(QColor("#777777")))
                font = QFont("Helvetica", max(7, int(9 * zoom)))
                painter.setFont(font)
                label = (
                    getattr(pic, "alt_text", "") or getattr(pic, "name", "") or self.tr("Picture")
                )
                painter.drawText(dest_rect, Qt.AlignmentFlag.AlignCenter, label)
            finally:
                painter.restore()

    def _paint_chart(
        self,
        painter: QPainter,
        item: ChartItem,
        dest_rect: QRectF,
        is_vector: bool = False,
    ) -> None:
        """Paint an embedded chart with the shared chart painter.

        The chart is laid out in points (fonts, insets) and scaled to the device so it
        looks the same at every zoom and in print.
        """
        scale = 1.0 if is_vector else self.pt_to_px(1.0)
        if scale <= 0:
            return
        painter.save()
        try:
            painter.translate(dest_rect.topLeft())
            painter.scale(scale, scale)
            ChartPainter.paint_chart(
                painter,
                item.chart,
                QRectF(0.0, 0.0, dest_rect.width() / scale, dest_rect.height() / scale),
            )
        except Exception:
            logger.debug("Chart painting failed for %s", item.name, exc_info=True)
        finally:
            painter.restore()

    def _paint_shape(
        self,
        painter: QPainter,
        shape: ShapeItem,
        dest_rect: QRectF,
        is_vector: bool = False,
    ) -> None:
        """Render a DrawingML/VML shape: geometry, fill, outline and text box content."""
        if is_vector:
            scale = 1.0

            def line_cb(p: QPainter, origin: QPointF, line: Any, x: float, y: float) -> None:
                self._paint_vector_line(p, line, origin.x() + x, origin.y() + y)

            table_cb = None
        else:
            scale = self.pt_to_px(1.0)

            def line_cb(p: QPainter, origin: QPointF, line: Any, x: float, y: float) -> None:
                self._paint_line_portions(
                    p, QRectF(origin.x(), origin.y(), 0.0, 0.0), line, x, y, check_spell=False
                )

            def table_cb(p: QPainter, origin: QPointF, tl: Any, x: float, y: float) -> None:
                self._paint_table_layout(p, QRectF(origin.x(), origin.y(), 0.0, 0.0), tl, x, y)

        def image_cb(p: QPainter, item: ShapeItem, rect: QRectF) -> None:
            self._paint_picture(p, item, rect, self._zoom if not is_vector else 1.0, is_vector)

        paint_shape(
            painter,
            shape,
            dest_rect,
            scale,
            paint_line=line_cb,
            paint_table=table_cb,
            paint_image=image_cb,
            doc=getattr(self, "doc", None),
        )

    def _paint_vector_line(self, painter: QPainter, line: Any, x_pt: float, y_pt: float) -> None:
        """Paint the text portions of one laid-out line in point coordinates (print/PDF)."""
        baseline = y_pt + (line.baseline - line.top)
        cur_x = x_pt
        for po in line.portions:
            if po.type == PortionType.TEXT and po.text:
                font = QFont(po.font_family or "Times New Roman")
                font.setPointSizeF(po.font_size or 12.0)
                font.setBold(bool(getattr(po, "bold", False)))
                font.setItalic(bool(getattr(po, "italic", False)))
                painter.setFont(font)
                color_str = getattr(po, "color", None) or "#000000"
                if color_str == "auto":
                    color_str = "#000000"
                painter.setPen(QPen(QColor(color_str)))
                painter.drawText(QPointF(cur_x, baseline - po.baseline_shift), po.text)
            cur_x += po.width

    def _paint_header_footer(
        self,
        painter: QPainter,
        page_rect: QRectF,
        page: Page,
        hf: PageHeaderFooter | None,
        is_header: bool,
    ) -> None:
        """Render header or footer text and portions on screen canvas in subdued gray."""
        if not hf or not hf.fragments:
            return

        hf_top = hf.y
        for frag in hf.fragments:
            for line in frag.lines:
                line_y = hf_top + line.top
                cur_x = page.body_left + line.indent_left
                for po in line.portions:
                    po_w = po.width
                    if po.type == PortionType.TEXT and po.text:
                        text_str = po.text
                        if text_str == "PAGE":
                            from atboffice.modules.writer.layout.pagination import format_number

                            text_str = format_number(page.page_number, page.page_number_format)
                        elif text_str == "NUMPAGES":
                            total_pgs = (
                                len(self.pagination.pages)
                                if (self.pagination and self.pagination.pages)
                                else (page.index + 1)
                            )
                            text_str = str(total_pgs)

                        font_family = po.font_family or "Times New Roman"
                        font_size_pt = po.font_size or 10.0
                        font = QFont(font_family)
                        font.setPointSizeF(font_size_pt * self._zoom)
                        if getattr(po, "bold", False):
                            font.setBold(True)
                        if getattr(po, "italic", False):
                            font.setItalic(True)
                        painter.setFont(font)

                        x_px = page_rect.left() + self.pt_to_px(cur_x)
                        y_px = page_rect.top() + self.pt_to_px(line_y)
                        baseline_px = y_px + self.pt_to_px(line.baseline - line.top)

                        # Subdued gray for screen view (#666666)
                        painter.setPen(QPen(QColor("#666666")))
                        painter.drawText(
                            QPointF(x_px, baseline_px - self.pt_to_px(po.baseline_shift)), text_str
                        )

                        _ul = getattr(po, "underline", None)
                        if _ul and _ul != "none":
                            pen_u = QPen(QColor("#666666"), 0.75 * self._zoom)
                            painter.setPen(pen_u)
                            painter.drawLine(
                                QPointF(x_px, baseline_px + 1.5 * self._zoom),
                                QPointF(x_px + self.pt_to_px(po_w), baseline_px + 1.5 * self._zoom),
                            )
                        if getattr(po, "strikethrough", False):
                            pen_s = QPen(QColor("#666666"), 0.75 * self._zoom)
                            painter.setPen(pen_s)
                            mid_y = baseline_px - (font_size_pt * self._zoom) * 0.3
                            painter.drawLine(
                                QPointF(x_px, mid_y),
                                QPointF(x_px + self.pt_to_px(po_w), mid_y),
                            )
                        if getattr(po, "dstrike", False):
                            pen_ds = QPen(QColor("#666666"), 0.75 * self._zoom)
                            painter.setPen(pen_ds)
                            mid_y = baseline_px - (font_size_pt * self._zoom) * 0.3
                            gap = 1.5 * self._zoom
                            painter.drawLine(
                                QPointF(x_px, mid_y - gap),
                                QPointF(x_px + self.pt_to_px(po_w), mid_y - gap),
                            )
                            painter.drawLine(
                                QPointF(x_px, mid_y + gap),
                                QPointF(x_px + self.pt_to_px(po_w), mid_y + gap),
                            )

                    elif po.type == PortionType.TAB and po_w > 0:
                        tab_data = getattr(po, "data", None)
                        leader = getattr(tab_data, "leader", "none") if tab_data else "none"
                        if leader and leader != "none":
                            x_px = page_rect.left() + self.pt_to_px(cur_x)
                            y_px = page_rect.top() + self.pt_to_px(line_y)
                            baseline_px = y_px + self.pt_to_px(line.baseline - line.top)
                            w_px = self.pt_to_px(po_w)
                            p1 = QPointF(x_px, baseline_px)
                            p2 = QPointF(x_px + w_px, baseline_px)
                            pen_style = Qt.PenStyle.SolidLine
                            if leader == "dot":
                                pen_style = Qt.PenStyle.DotLine
                            elif leader == "hyphen":
                                pen_style = Qt.PenStyle.DashLine
                            elif leader == "underscore":
                                p1 = QPointF(x_px, baseline_px + 1.5 * self._zoom)
                                p2 = QPointF(x_px + w_px, baseline_px + 1.5 * self._zoom)
                            painter.setPen(QPen(QColor("#666666"), 0.75 * self._zoom, pen_style))
                            painter.drawLine(p1, p2)

                    elif po.type == PortionType.GRAPHIC:
                        x_px = page_rect.left() + self.pt_to_px(cur_x)
                        y_px = page_rect.top() + self.pt_to_px(line_y)
                        baseline_px = y_px + self.pt_to_px(line.baseline - line.top)
                        if isinstance(po.data, OfficeMathItem):
                            paint_math(painter, po.data, x_px, baseline_px, self._zoom)
                        elif isinstance(po.data, PictureItem) or getattr(po.data, "t", "") in (
                            "picture",
                            "img",
                        ):
                            pic_w_px = self.pt_to_px(po.width)
                            pic_h_px = self.pt_to_px(po.ascent)
                            dest_rect = QRectF(x_px, baseline_px - pic_h_px, pic_w_px, pic_h_px)
                            self._paint_picture(painter, po.data, dest_rect, self._zoom)

                    cur_x += po_w

    def _paint_float_box(
        self,
        painter: QPainter,
        page_rect: QRectF,
        page: Page,
        fb: FloatBox,
    ) -> None:
        """Render a floating drawing, picture, or shape object on screen canvas."""
        item = fb.item
        if not item:
            return
        x_px = page_rect.left() + self.pt_to_px(fb.x)
        y_px = page_rect.top() + self.pt_to_px(fb.y)
        w_px = self.pt_to_px(fb.w)
        h_px = self.pt_to_px(fb.h)
        dest_rect = QRectF(x_px, y_px, w_px, h_px)

        if fb.lines:
            for line in fb.lines:
                line_y = fb.y + line.top
                cur_x = fb.x + line.indent_left
                self._paint_line_portions(
                    painter, page_rect, line, cur_x, line_y, check_spell=False
                )
            return

        if isinstance(item, PictureItem) or getattr(item, "t", "") in ("picture", "img"):
            self._paint_picture(painter, item, dest_rect, self._zoom)
        else:
            fill_color = getattr(item, "fill_color", None) or "#E8EEF5"
            stroke_color = getattr(item, "stroke_color", None) or "#4A709C"
            stroke_width = getattr(item, "stroke_width", 1.0) or 1.0

            painter.save()
            painter.setBrush(QColor(fill_color))
            painter.setPen(QPen(QColor(stroke_color), self.pt_to_px(stroke_width)))
            painter.drawRect(dest_rect)
            painter.restore()

    def _author_comment_color(self, author: str) -> QColor:
        """Return deterministic author color matching .vibeoffice review palette."""
        palette = (
            "#B5382B",
            "#1F5EA8",
            "#2A7B4F",
            "#7B3E94",
            "#B36B00",
            "#0E7490",
        )
        key = author or "Author"
        idx = sum(ord(ch) for ch in key) % len(palette)
        return QColor(palette[idx])

    def _paint_comments(self, painter: QPainter, page_rect: QRectF, page: Page) -> None:
        """Render comment range highlights, margin connector lines, and callout balloons."""
        if not getattr(self, "doc", None) or not getattr(self.doc, "comments", None):
            return

        comments_dict = self.doc.comments
        if not comments_dict:
            return

        # Compute 1-based document comment order matching RV.commentNumber
        comment_order: dict[str, int] = {}
        order_idx = 1
        for b in getattr(self.doc.main, "blocks", []):
            if hasattr(b, "runs"):
                for item in b.runs:
                    c_id = getattr(item, "comment_id", None)
                    if c_id is not None:
                        cid_s = str(c_id)
                        if cid_s in comments_dict and cid_s not in comment_order:
                            comment_order[cid_s] = order_idx
                            order_idx += 1

        placed_balloons: list[tuple[str, float]] = []
        placed_set: set[str] = set()
        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    if frag.paragraph is None:
                        continue
                    runs = getattr(frag.paragraph, "runs", [])
                    frag_top = page.body_top + col.top + frag.top
                    for item in runs:
                        c_id = getattr(item, "comment_id", None)
                        if c_id is not None and str(c_id) in comments_dict:
                            cid_str = str(c_id)
                            if cid_str not in placed_set:
                                anchor_y = frag_top + (frag.lines[0].top if frag.lines else 0.0)
                                placed_balloons.append((cid_str, anchor_y))
                                placed_set.add(cid_str)
                                for k, st in comments_dict.items():
                                    if (
                                        getattr(st, "parent_id", "") == cid_str
                                        and k not in placed_set
                                    ):
                                        placed_balloons.append((k, anchor_y))
                                        placed_set.add(k)

        if not placed_balloons:
            return

        painter.save()
        balloon_w_px = 200.0 * self._zoom
        balloon_h_px = 42.0 * self._zoom
        balloon_x_px = page_rect.right() + 12.0 * self._zoom
        prev_bottom_px = page_rect.top()

        for cid_str, anchor_y_pt in placed_balloons:
            story = comments_dict[cid_str]
            anchor_y_px = page_rect.top() + self.pt_to_px(anchor_y_pt)
            balloon_y_px = max(anchor_y_px - 2.0, prev_bottom_px + 4.0)
            prev_bottom_px = balloon_y_px + balloon_h_px

            border_col = self._author_comment_color(getattr(story, "author", ""))
            bg_col = QColor(
                int(border_col.red() * 0.15 + 255 * 0.85),
                int(border_col.green() * 0.15 + 255 * 0.85),
                int(border_col.blue() * 0.15 + 255 * 0.85),
            )

            # Orthogonal dashed connector from right margin to balloon
            connector_pen = QPen(border_col, 1.0, Qt.PenStyle.DashLine)
            painter.setPen(connector_pen)
            line_start_x = page_rect.right() - self.pt_to_px(10.0)
            line_y = anchor_y_px + 10.0
            mid_y = balloon_y_px + 8.0
            if abs(line_y - mid_y) > 2.0:
                elbow_x = page_rect.right() + 2.0
                painter.drawLine(QPointF(line_start_x, line_y), QPointF(elbow_x, line_y))
                painter.drawLine(QPointF(elbow_x, line_y), QPointF(elbow_x, mid_y))
                painter.drawLine(QPointF(elbow_x, mid_y), QPointF(balloon_x_px, mid_y))
            else:
                painter.drawLine(QPointF(line_start_x, mid_y), QPointF(balloon_x_px, mid_y))

            # Balloon box
            balloon_rect = QRectF(balloon_x_px, balloon_y_px, balloon_w_px, balloon_h_px)
            painter.setBrush(bg_col)
            painter.setPen(QPen(border_col, 1.0))
            painter.drawRoundedRect(balloon_rect, 4.0, 4.0)

            # Balloon text: Header (initials + 1-based number + reply tag)
            header_font = QFont("Tahoma")
            header_font.setPointSizeF(7.5 * self._zoom)
            header_font.setBold(True)
            painter.setFont(header_font)
            painter.setPen(QPen(QColor(0, 0, 0)))

            num_val = comment_order.get(cid_str)
            if num_val is None:
                try:
                    num_val = int(cid_str) + 1
                except ValueError:
                    num_val = 1
            initials = story.initials or story.author or ""
            is_reply = bool(getattr(story, "parent_id", ""))
            suffix = " (reply):" if is_reply else ":"
            head_text = f"Comment [{initials}{num_val}]{suffix}"
            painter.drawText(
                QRectF(
                    balloon_rect.left() + 5.0,
                    balloon_rect.top() + 3.0,
                    balloon_w_px - 10.0,
                    14.0,
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                head_text,
            )

            # Balloon body text
            body_text = ""
            for b in getattr(story, "blocks", []):
                if isinstance(b, Paragraph):
                    body_text = "".join(r.text for r in b.runs if hasattr(r, "text"))
                    if body_text:
                        break
            if body_text:
                body_font = QFont("Tahoma")
                body_font.setPointSizeF(7.5 * self._zoom)
                painter.setFont(body_font)
                painter.setPen(QPen(QColor(0, 0, 0)))
                painter.drawText(
                    QRectF(
                        balloon_rect.left() + 5.0,
                        balloon_rect.top() + 17.0,
                        balloon_w_px - 10.0,
                        balloon_h_px - 19.0,
                    ),
                    (
                        Qt.AlignmentFlag.AlignLeft
                        | Qt.AlignmentFlag.AlignTop
                        | Qt.TextFlag.TextWordWrap
                    ),
                    body_text[:80],
                )

        painter.restore()

    def _paint_footnote_area(
        self,
        painter: QPainter,
        page_rect: QRectF,
        page: Page,
        fn_area: PageFootnoteArea,
    ) -> None:
        """Render the 2-inch footnote separator rule and footnote paragraph text."""
        # 1. Standard Word 2003 2-inch (144.0 pt) Footnote Separator Rule
        sep_x = page_rect.left() + self.pt_to_px(page.body_left)
        sep_y = page_rect.top() + self.pt_to_px(fn_area.y)
        sep_w = self.pt_to_px(fn_area.separator_width)

        sep_pen = QPen(QColor(0, 0, 0), max(0.75, self.pt_to_px(0.75)))
        painter.setPen(sep_pen)
        painter.drawLine(QPointF(sep_x, sep_y), QPointF(sep_x + sep_w, sep_y))

        # 2. Footnote paragraph fragments
        for frag in fn_area.fragments:
            frag_top = fn_area.y + frag.top
            for line in frag.lines:
                line_y = frag_top + line.top
                cur_x = page.body_left + line.indent_left
                for po in line.portions:
                    po_w = po.width
                    if po.type == PortionType.TEXT and po.text:
                        font_family = po.font_family or "Times New Roman"
                        font_size_pt = po.font_size or 10.0
                        font = QFont(font_family)
                        font.setPointSizeF(font_size_pt * self._zoom)
                        if getattr(po, "bold", False):
                            font.setBold(True)
                        if getattr(po, "italic", False):
                            font.setItalic(True)
                        painter.setFont(font)

                        x_px = page_rect.left() + self.pt_to_px(cur_x)
                        y_px = page_rect.top() + self.pt_to_px(line_y)
                        baseline_px = y_px + self.pt_to_px(line.baseline - line.top)

                        painter.setPen(QPen(QColor(0, 0, 0)))
                        painter.drawText(
                            QPointF(x_px, baseline_px - self.pt_to_px(po.baseline_shift)), po.text
                        )
                    cur_x += po_w

    def _paint_table_layout(
        self,
        painter: QPainter,
        page_rect: QRectF,
        tl: TableLayout,
        frag_x: float,
        frag_y: float,
    ) -> None:
        """Paint a table, and recursively its nested tables, at origin (frag_x, frag_y) in pt."""
        for rl in tl.rows:
            for cl in rl.cells:
                cell_x_px = page_rect.left() + self.pt_to_px(frag_x + cl.x)
                cell_y_px = page_rect.top() + self.pt_to_px(frag_y + cl.y)
                cell_w_px = self.pt_to_px(cl.width)
                cell_h_px = self.pt_to_px(cl.height)
                cell_rect = QRectF(cell_x_px, cell_y_px, cell_w_px, cell_h_px)

                # Shading
                fill_val = getattr(cl.shd, "fill", "auto")
                if fill_val and fill_val not in ("auto", "clear", "none"):
                    hex_fill = fill_val if fill_val.startswith("#") else f"#{fill_val}"
                    painter.fillRect(cell_rect, QColor(hex_fill))

                # Borders
                bds = getattr(cl, "borders", {}) or {}
                has_explicit_borders = any(
                    getattr(b, "val", "none") not in ("none", "nil", "hidden", "", None)
                    for b in bds.values()
                )
                if has_explicit_borders:
                    top_p = self._get_border_pen(bds.get("top"), self._zoom)
                    if top_p:
                        painter.setPen(top_p)
                        painter.drawLine(
                            QPointF(cell_rect.left(), cell_rect.top()),
                            QPointF(cell_rect.right(), cell_rect.top()),
                        )
                    bot_p = self._get_border_pen(bds.get("bottom"), self._zoom)
                    if bot_p:
                        painter.setPen(bot_p)
                        painter.drawLine(
                            QPointF(cell_rect.left(), cell_rect.bottom()),
                            QPointF(cell_rect.right(), cell_rect.bottom()),
                        )
                    left_p = self._get_border_pen(bds.get("left"), self._zoom)
                    if left_p:
                        painter.setPen(left_p)
                        painter.drawLine(
                            QPointF(cell_rect.left(), cell_rect.top()),
                            QPointF(cell_rect.left(), cell_rect.bottom()),
                        )
                    right_p = self._get_border_pen(bds.get("right"), self._zoom)
                    if right_p:
                        painter.setPen(right_p)
                        painter.drawLine(
                            QPointF(cell_rect.right(), cell_rect.top()),
                            QPointF(cell_rect.right(), cell_rect.bottom()),
                        )
                else:
                    # Fallback default subtle table grid boundary
                    painter.setPen(QPen(QColor(180, 180, 180), 1.0))
                    painter.drawRect(cell_rect)

                # Cell text content with margins and multi-paragraph layout
                mar_l = getattr(cl, "mar_l", 5.4)
                mar_t = getattr(cl, "mar_t", 0.0)
                cell_inner_x = frag_x + cl.x + mar_l
                content_y = frag_y + cl.y + cl.content_offset_y + mar_t

                for item, item_top in zip(cl.block_layouts, cl.block_tops):
                    if isinstance(item, TableLayout):
                        # Nested table: recurse, clipped to the parent cell.
                        painter.save()
                        painter.setClipRect(cell_rect, Qt.ClipOperation.IntersectClip)
                        self._paint_table_layout(
                            painter, page_rect, item, cell_inner_x + item.x, content_y + item_top
                        )
                        painter.restore()
                        continue
                    playout = item
                    p_top = content_y + item_top + playout.effective_space_before
                    for line in playout.lines:
                        line_y = p_top + line.top
                        cur_x = cell_inner_x + line.indent_left
                        for po in line.portions:
                            po_w = po.width
                            if po.type == PortionType.TEXT and po.text:
                                font_family = po.font_family or "Times New Roman"
                                font_size_pt = po.font_size or 12.0
                                font = QFont(font_family)
                                font.setPointSizeF(font_size_pt * self._zoom)
                                if getattr(po, "bold", False):
                                    font.setBold(True)
                                if getattr(po, "italic", False):
                                    font.setItalic(True)
                                painter.setFont(font)
                                x_px = page_rect.left() + self.pt_to_px(cur_x)
                                y_px = page_rect.top() + self.pt_to_px(line_y)
                                baseline_px = y_px + self.pt_to_px(line.baseline_offset)
                                painter.setPen(QPen(QColor(0, 0, 0)))
                                po_base_px = baseline_px - self.pt_to_px(po.baseline_shift)
                                painter.drawText(QPointF(x_px, po_base_px), po.text)
                                if (
                                    self.spell_engine.is_enabled("spelling/check_as_you_type", True)
                                    and po.text
                                ):
                                    fm = self._metrics(font)
                                    for (
                                        w,
                                        w_start,
                                        w_end,
                                    ) in self.spell_engine.tokenize_words(po.text):
                                        if not self.spell_engine.is_valid_word(w):
                                            w_x1 = x_px + fm.horizontalAdvance(po.text[:w_start])
                                            w_x2 = x_px + fm.horizontalAdvance(po.text[:w_end])
                                            self._draw_wavy_line(
                                                painter,
                                                w_x1,
                                                w_x2,
                                                baseline_px + 2.5,
                                                QColor(255, 0, 0),
                                            )
                            elif po.type == PortionType.GRAPHIC:
                                x_px = page_rect.left() + self.pt_to_px(cur_x)
                                y_px = page_rect.top() + self.pt_to_px(line_y)
                                baseline_px = y_px + self.pt_to_px(line.baseline_offset)
                                if isinstance(po.data, OfficeMathItem):
                                    paint_math(
                                        painter,
                                        po.data,
                                        x_px,
                                        baseline_px,
                                        self._zoom,
                                    )
                                elif isinstance(po.data, PictureItem) or getattr(
                                    po.data, "t", ""
                                ) in ("picture", "img"):
                                    pic_w_px = self.pt_to_px(po.width)
                                    pic_h_px = self.pt_to_px(po.ascent)
                                    dest_rect = QRectF(
                                        x_px,
                                        baseline_px - pic_h_px,
                                        pic_w_px,
                                        pic_h_px,
                                    )
                                    self._paint_picture(painter, po.data, dest_rect, self._zoom)
                            cur_x += po_w

    def _paint_hf_edit_overlay(self, painter: QPainter, page_rect: QRectF, page: Page) -> None:
        body = QRectF(
            page_rect.left(),
            page_rect.top() + self.pt_to_px(page.body_top),
            page_rect.width(),
            self.pt_to_px(page.height - page.body_top - page.body_bottom_gap),
        )
        painter.save()
        painter.fillRect(body, QColor(255, 255, 255, 150))
        pen = QPen(QColor(128, 128, 128), 1.0, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        left = page_rect.left() + self.pt_to_px(page.body_left)
        width = self.pt_to_px(page.body_width)
        if self.hf_edit_kind == "hdr":
            top = page_rect.top() + self.pt_to_px(float(getattr(page.section, "hdr", 36.0)))
            painter.drawRect(QRectF(left, top, width, max(0.0, body.top() - top)))
        else:
            bottom = page_rect.bottom() - self.pt_to_px(float(getattr(page.section, "ftr", 36.0)))
            painter.drawRect(QRectF(left, body.bottom(), width, max(0.0, bottom - body.bottom())))
        painter.restore()

    def _paint_float_selection(
        self, painter: QPainter, p_idx: int, page_rect: QRectF, page: Page
    ) -> None:
        from atboffice.modules.writer.views import float_edit

        drag = self._float_drag
        if drag is not None and drag.page_index == p_idx and drag.current is not None:
            float_edit.paint_selection(
                painter, page_rect, self.pt_to_px, float_edit.preview_box(drag), dashed=True
            )
        found = self._selected_float_box()
        if found is not None and found[0] == p_idx:
            fb = found[1]
            float_edit.paint_selection(painter, page_rect, self.pt_to_px, (fb.x, fb.y, fb.w, fb.h))
