"""Grid painting outside the cells: headers, page breaks, audit arrows, pivot chrome."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import (
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
)

from atboffice.modules.spreadsheet.calc.references import (
    col_name,
)

if TYPE_CHECKING:
    pass


class GridOverlayPaintMixin:
    """Paints headers, page-break preview, audit arrows, spill borders and pivot chrome."""

    def _paint_spill_border(self, painter: QPainter, psx: int, psy: int, clip: QRect) -> None:
        from atboffice.modules.spreadsheet.calc.grid_spill import spill_rect_at

        ar, ac = self.selection.active_cell
        rect = spill_rect_at(self.model, ar, ac)
        if rect is None:
            return
        r1, c1, r2, c2 = rect
        geo = self.geometry_mapper
        x1 = self.row_header_width + geo.col_pos(c1) - psx
        y1 = self.col_header_height + geo.row_pos(r1) - psy
        x2 = self.row_header_width + geo.col_pos(c2 + 1) - psx
        y2 = self.col_header_height + geo.row_pos(r2 + 1) - psy
        painter.save()
        painter.setClipRect(clip)
        painter.setPen(QPen(QColor(68, 114, 196), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRect(x1, y1, x2 - x1 - 1, y2 - y1 - 1))
        painter.restore()

    def _comment_callout_rect(self, r: int, c: int, cm: Any, cell: QRect | None = None) -> QRect:
        """Viewport rect of the note callout for cell (r, c).

        The box sits to the right of the cell; it flips to the left when it
        would overflow the right edge and shifts up to stay above the bottom.
        """
        if cell is None:
            cell = self.cell_rect(r, c)
        bw = int(getattr(cm, "w", 140) or 140)
        bh = int(getattr(cm, "h", 65) or 65)
        view_w, view_h = self._view_size()
        right = cell.x() + cell.width()

        bx = right + self._COMMENT_GAP
        if bx + bw > view_w:
            left_x = cell.x() - self._COMMENT_GAP - bw
            if left_x >= self.row_header_width:
                bx = left_x
            else:
                bx = max(self.row_header_width, view_w - bw - 1)

        top_min = self.col_header_height + 2
        by = max(top_min, cell.y() - 6)
        if by + bh > view_h:
            by = max(top_min, view_h - bh - 1)
        return QRect(bx, by, bw, bh)

    def _paint_page_break_preview(
        self,
        painter: QPainter,
        cell_clip: QRect,
        scroll_x: int,
        scroll_y: int,
        vw: int,
        vh: int,
    ) -> None:
        """Render Excel 2003 Page Break Preview mode."""
        if self._view_mode != "page_break":
            return

        row_bounds, col_bounds = self.page_break_bounds()
        page_rows = row_bounds[-1]
        page_cols = col_bounds[-1]

        print_x1 = self.row_header_width + self.geometry_mapper.col_pos(col_bounds[0]) - scroll_x
        print_y1 = self.col_header_height + self.geometry_mapper.row_pos(row_bounds[0]) - scroll_y
        print_x2 = self.row_header_width + self.geometry_mapper.col_pos(page_cols) - scroll_x
        print_y2 = self.col_header_height + self.geometry_mapper.row_pos(page_rows) - scroll_y
        total_print_rect = QRect(print_x1, print_y1, print_x2 - print_x1, print_y2 - print_y1)

        painter.save()
        painter.setClipRect(cell_clip)

        # 1. Dim outside background with gray overlay
        gray_color = QColor(160, 160, 160, 150)
        if total_print_rect.intersects(cell_clip):
            if total_print_rect.left() > cell_clip.left():
                w = total_print_rect.left() - cell_clip.left()
                painter.fillRect(
                    QRect(cell_clip.left(), cell_clip.top(), w, cell_clip.height()),
                    gray_color,
                )
            if total_print_rect.right() < cell_clip.right():
                w = cell_clip.right() - total_print_rect.right()
                painter.fillRect(
                    QRect(total_print_rect.right() + 1, cell_clip.top(), w, cell_clip.height()),
                    gray_color,
                )
            if total_print_rect.top() > cell_clip.top():
                x = max(cell_clip.left(), total_print_rect.left())
                w = min(cell_clip.width(), total_print_rect.width())
                h = total_print_rect.top() - cell_clip.top()
                painter.fillRect(QRect(x, cell_clip.top(), w, h), gray_color)
            if total_print_rect.bottom() < cell_clip.bottom():
                x = max(cell_clip.left(), total_print_rect.left())
                w = min(cell_clip.width(), total_print_rect.width())
                h = cell_clip.bottom() - total_print_rect.bottom()
                painter.fillRect(QRect(x, total_print_rect.bottom() + 1, w, h), gray_color)
        else:
            painter.fillRect(cell_clip, gray_color)

        # 2. Draw Page Watermarks and internal dashed lines
        page_num = 1

        watermark_font = QFont("Arial", 46, QFont.Weight.Bold)
        watermark_color = QColor(160, 160, 160, 130)

        for py in range(len(row_bounds) - 1):
            r_start, r_end = row_bounds[py], row_bounds[py + 1]
            for px in range(len(col_bounds) - 1):
                c_start, c_end = col_bounds[px], col_bounds[px + 1]

                pg_x1 = self.row_header_width + self.geometry_mapper.col_pos(c_start) - scroll_x
                pg_y1 = self.col_header_height + self.geometry_mapper.row_pos(r_start) - scroll_y
                pg_x2 = self.row_header_width + self.geometry_mapper.col_pos(c_end) - scroll_x
                pg_y2 = self.col_header_height + self.geometry_mapper.row_pos(r_end) - scroll_y
                pg_rect = QRect(pg_x1, pg_y1, pg_x2 - pg_x1, pg_y2 - pg_y1)

                if pg_rect.intersects(cell_clip):
                    painter.setFont(watermark_font)
                    painter.setPen(QPen(watermark_color))
                    painter.drawText(pg_rect, Qt.AlignmentFlag.AlignCenter, f"Page {page_num}")

                    # Internal dashed break lines
                    if px > 0:
                        dash_pen = QPen(QColor(0, 0, 255), 1, Qt.PenStyle.DashLine)
                        painter.setPen(dash_pen)
                        painter.drawLine(pg_x1, pg_y1, pg_x1, pg_y2)
                    if py > 0:
                        dash_pen = QPen(QColor(0, 0, 255), 1, Qt.PenStyle.DashLine)
                        painter.setPen(dash_pen)
                        painter.drawLine(pg_x1, pg_y1, pg_x2, pg_y1)

                page_num += 1

        # 3. Outer boundary: bold solid blue border
        outer_pen = QPen(QColor(0, 0, 255), 2, Qt.PenStyle.SolidLine)
        painter.setPen(outer_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(total_print_rect)

        # 4. Break line being dragged (solid: it becomes a manual break)
        drag = getattr(self, "_page_break_drag", None)
        if drag is not None and drag.get("target") is not None:
            painter.setPen(QPen(QColor(0, 0, 255), 3, Qt.PenStyle.SolidLine))
            if drag["axis"] == "row":
                y = self.col_header_height + self.geometry_mapper.row_pos(drag["target"]) - scroll_y
                painter.drawLine(total_print_rect.left(), y, total_print_rect.right(), y)
            else:
                x = self.row_header_width + self.geometry_mapper.col_pos(drag["target"]) - scroll_x
                painter.drawLine(x, total_print_rect.top(), x, total_print_rect.bottom())

        painter.restore()

    def _paint_audit_arrows(
        self,
        painter: QPainter,
        clip_rect: QRect,
        scroll_x: int,
        scroll_y: int,
    ) -> None:
        """Render formula auditing tracer arrows connecting precedents and dependents."""
        arrows = getattr(self.model, "audit_arrows", [])
        if not arrows:
            return

        painter.save()
        painter.setClipRect(clip_rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        cur_sheet = getattr(self.model, "name", "Sheet1")

        def cell_center(r: int, c: int) -> QPointF:
            cr = self.cell_rect(r, c)
            return QPointF(cr.center().x() + 0.5, cr.center().y() + 0.5)

        def draw_arrow_head(p_from: QPointF, p_to: QPointF, color: QColor) -> None:
            angle = math.atan2(p_to.y() - p_from.y(), p_to.x() - p_from.x())
            arrow_len = 8.0
            arrow_angle = math.pi / 6.0
            p1 = QPointF(
                p_to.x() - arrow_len * math.cos(angle - arrow_angle),
                p_to.y() - arrow_len * math.sin(angle - arrow_angle),
            )
            p2 = QPointF(
                p_to.x() - arrow_len * math.cos(angle + arrow_angle),
                p_to.y() - arrow_len * math.sin(angle + arrow_angle),
            )
            poly = QPolygonF([p_to, p1, p2])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawPolygon(poly)

        for a in arrows:
            col = QColor(255, 0, 0) if a.is_error else QColor(0, 0, 255)
            pen = QPen(col, 1.5)

            # Case 1: Intra-sheet: both on current sheet
            if a.from_sheet == cur_sheet and a.to_sheet == cur_sheet:
                p_to = cell_center(a.to_r, a.to_c)
                p_from = cell_center(a.from_r1, a.from_c1)

                if a.is_range:
                    r_min = min(a.from_r1, a.from_r2)
                    r_max = max(a.from_r1, a.from_r2)
                    c_min = min(a.from_c1, a.from_c2)
                    c_max = max(a.from_c1, a.from_c2)
                    x1 = self.row_header_width + self.geometry_mapper.col_pos(c_min) - scroll_x
                    y1 = self.col_header_height + self.geometry_mapper.row_pos(r_min) - scroll_y
                    x2 = (
                        self.row_header_width
                        + self.geometry_mapper.col_pos(c_max)
                        + self.geometry_mapper.col_size(c_max)
                        - scroll_x
                    )
                    y2 = (
                        self.col_header_height
                        + self.geometry_mapper.row_pos(r_max)
                        + self.geometry_mapper.row_size(r_max)
                        - scroll_y
                    )
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(col))
                painter.drawEllipse(p_from, 3.0, 3.0)

                painter.setPen(pen)
                painter.drawLine(p_from, p_to)
                draw_arrow_head(p_from, p_to, col)

            # Case 2: Cross-sheet incoming: from another sheet into current sheet
            elif a.to_sheet == cur_sheet and a.from_sheet != cur_sheet:
                p_to = cell_center(a.to_r, a.to_c)
                p_origin = QPointF(p_to.x() - 40.0, p_to.y() - 30.0)

                dash_pen = QPen(QColor(0, 0, 0), 1.2, Qt.PenStyle.DashLine)
                painter.setPen(dash_pen)
                painter.drawLine(p_origin, p_to)
                draw_arrow_head(p_origin, p_to, QColor(0, 0, 0))

                sheet_rect = QRectF(p_to.x() - 52.0, p_to.y() - 40.0, 14.0, 11.0)
                painter.setPen(QPen(QColor(0, 0, 0), 1.0))
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.drawRect(sheet_rect)
                painter.drawLine(
                    QPointF(sheet_rect.left() + 2, sheet_rect.top() + 3),
                    QPointF(sheet_rect.right() - 2, sheet_rect.top() + 3),
                )
                painter.drawLine(
                    QPointF(sheet_rect.left() + 2, sheet_rect.top() + 6),
                    QPointF(sheet_rect.right() - 2, sheet_rect.top() + 6),
                )

            # Case 3: Cross-sheet outgoing: from current sheet to another sheet
            elif a.from_sheet == cur_sheet and a.to_sheet != cur_sheet:
                p_from = cell_center(a.from_r1, a.from_c1)
                p_dest = QPointF(p_from.x() + 40.0, p_from.y() + 30.0)

                dash_pen = QPen(QColor(0, 0, 0), 1.2, Qt.PenStyle.DashLine)
                painter.setPen(dash_pen)
                painter.drawLine(p_from, p_dest)
                draw_arrow_head(p_from, p_dest, QColor(0, 0, 0))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(col))
                painter.drawEllipse(p_from, 3.0, 3.0)

                sheet_rect = QRectF(p_dest.x() + 2.0, p_dest.y() - 5.0, 14.0, 11.0)
                painter.setPen(QPen(QColor(0, 0, 0), 1.0))
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.drawRect(sheet_rect)
                painter.drawLine(
                    QPointF(sheet_rect.left() + 2, sheet_rect.top() + 3),
                    QPointF(sheet_rect.right() - 2, sheet_rect.top() + 3),
                )
                painter.drawLine(
                    QPointF(sheet_rect.left() + 2, sheet_rect.top() + 6),
                    QPointF(sheet_rect.right() - 2, sheet_rect.top() + 6),
                )

        painter.restore()

    def _header_font(self) -> QFont:
        """Header label font: Arial 10pt (13.33 css px), as render.js ``hdrFont``."""
        font = QFont("Arial")
        font.setPixelSize(13)
        return font

    def update_header_dimensions(self) -> bool:
        """Size the headers like render.js RD.frame; return True when they changed.

        Row header width fits the last visible row number plus 10px (at least 25px);
        the column header is as tall as a default row (at least 17px).
        """
        model = getattr(self, "model", None)
        geo = getattr(self, "geometry_mapper", None)
        if model is None or geo is None:
            return False
        z = self.zoom if self.zoom > 0 else 1.0
        view_h = self.viewport().height() / z
        scroll_y = max(0, self.verticalScrollBar().value())
        last_row = geo.find_row_at(int(scroll_y + view_h)) + 2
        metrics = QFontMetrics(self._header_font())
        label_w = metrics.horizontalAdvance(str(last_row))
        width = max(self.MIN_ROW_HEADER_WIDTH, math.ceil(label_w + 10))
        height = max(self.MIN_COL_HEADER_HEIGHT, int(round(geo.default_row_height)))
        changed = (width, height) != (self.row_header_width, self.col_header_height)
        self.row_header_width = width
        self.col_header_height = height
        if changed:
            self.header_dimensions_changed.emit(width, height)
        return changed

    def _fill_header_cell(
        self, painter: QPainter, rect: QRect, selected: bool, vertical: bool
    ) -> None:
        """Fill a header cell with the render.js gradient (top-down or left-right)."""
        if vertical:
            grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
        else:
            grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
        top = self.COLOR_HDR_SEL_TOP if selected else self.COLOR_HDR_TOP
        bottom = self.COLOR_HDR_SEL_BG if selected else self.COLOR_HDR_BG
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, bottom)
        painter.fillRect(rect, QBrush(grad))

    def _paint_headers(
        self,
        painter: QPainter,
        start_row: int,
        end_row: int,
        start_col: int,
        end_col: int,
        scroll_x: int,
        scroll_y: int,
        vw: int,
        vh: int,
    ) -> None:
        """Render column headers, row headers, and corner box."""
        fz_r = self.freeze_rows
        fz_c = self.freeze_cols
        fz_r_h = self.geometry_mapper.row_pos(fz_r) if fz_r > 0 else 0
        fz_c_w = self.geometry_mapper.col_pos(fz_c) if fz_c > 0 else 0

        painter.setFont(self._header_font())
        # A. Top-Left Corner Box
        self._fill_header_cell(
            painter,
            QRect(0, 0, self.row_header_width, self.col_header_height),
            False,
            vertical=True,
        )
        painter.setPen(QPen(self.COLOR_HDR_BORDER, 1))
        painter.drawRect(0, 0, self.row_header_width, self.col_header_height)

        # Draw diagonal triangle in corner box
        painter.setBrush(QBrush(QColor(160, 160, 160)))
        corner_poly = [
            QPoint(self.row_header_width - 8, self.col_header_height - 3),
            QPoint(self.row_header_width - 3, self.col_header_height - 3),
            QPoint(self.row_header_width - 3, self.col_header_height - 8),
        ]
        painter.drawPolygon(corner_poly)

        # B. Column Headers (A, B, C...)
        # B1. Scrollable Column Headers (clipped to right of frozen cols)
        painter.save()
        painter.setClipRect(
            QRect(
                self.row_header_width + fz_c_w,
                0,
                max(0, vw - self.row_header_width - fz_c_w),
                self.col_header_height,
            )
        )
        for c in range(start_col, end_col + 1):
            if fz_c > 0 and c < fz_c:
                continue
            cx = self.row_header_width + self.geometry_mapper.col_pos(c) - scroll_x
            cw = self.geometry_mapper.col_size(c)
            if cw <= 0:
                continue

            is_sel = self.selection.is_col_selected(c)
            self._fill_header_cell(
                painter, QRect(cx, 0, cw, self.col_header_height), is_sel, vertical=True
            )

            painter.setPen(QPen(self.COLOR_HDR_BORDER, 1))
            painter.drawLine(cx + cw, 0, cx + cw, self.col_header_height)
            painter.drawLine(
                cx,
                self.col_header_height - 1,
                cx + cw,
                self.col_header_height - 1,
            )

            # Header text
            painter.setPen(self.COLOR_HDR_TEXT)
            painter.drawText(
                QRect(cx, 0, cw, self.col_header_height),
                Qt.AlignmentFlag.AlignCenter,
                col_name(c),
            )
        painter.restore()

        # B2. Frozen Column Headers (pinned)
        if fz_c > 0:
            painter.save()
            painter.setClipRect(
                QRect(
                    self.row_header_width,
                    0,
                    fz_c_w,
                    self.col_header_height,
                )
            )
            for c in range(0, fz_c):
                cx = self.row_header_width + self.geometry_mapper.col_pos(c)
                cw = self.geometry_mapper.col_size(c)
                if cw <= 0:
                    continue

                is_sel = self.selection.is_col_selected(c)
                self._fill_header_cell(
                    painter, QRect(cx, 0, cw, self.col_header_height), is_sel, vertical=True
                )

                painter.setPen(QPen(self.COLOR_HDR_BORDER, 1))
                painter.drawLine(cx + cw, 0, cx + cw, self.col_header_height)
                painter.drawLine(
                    cx,
                    self.col_header_height - 1,
                    cx + cw,
                    self.col_header_height - 1,
                )

                painter.setPen(self.COLOR_HDR_TEXT)
                painter.drawText(
                    QRect(cx, 0, cw, self.col_header_height),
                    Qt.AlignmentFlag.AlignCenter,
                    col_name(c),
                )
            painter.restore()

        # C. Row Headers (1, 2, 3...)
        # C1. Scrollable Row Headers (clipped to below frozen rows)
        painter.save()
        painter.setClipRect(
            QRect(
                0,
                self.col_header_height + fz_r_h,
                self.row_header_width,
                max(0, vh - self.col_header_height - fz_r_h),
            )
        )
        for r in range(start_row, end_row + 1):
            if fz_r > 0 and r < fz_r:
                continue
            ry = self.col_header_height + self.geometry_mapper.row_pos(r) - scroll_y
            rh = self.geometry_mapper.row_size(r)
            if rh <= 0:
                continue

            is_sel = self.selection.is_row_selected(r)
            self._fill_header_cell(
                painter, QRect(0, ry, self.row_header_width, rh), is_sel, vertical=False
            )

            painter.setPen(QPen(self.COLOR_HDR_BORDER, 1))
            painter.drawLine(0, ry + rh, self.row_header_width, ry + rh)
            painter.drawLine(
                self.row_header_width - 1,
                ry,
                self.row_header_width - 1,
                ry + rh,
            )

            # Header text (1-based row number)
            painter.setPen(self.COLOR_HDR_TEXT)
            painter.drawText(
                QRect(0, ry, self.row_header_width, rh),
                Qt.AlignmentFlag.AlignCenter,
                str(r + 1),
            )
        painter.restore()

        # C2. Frozen Row Headers (pinned)
        if fz_r > 0:
            painter.save()
            painter.setClipRect(
                QRect(
                    0,
                    self.col_header_height,
                    self.row_header_width,
                    fz_r_h,
                )
            )
            for r in range(0, fz_r):
                ry = self.col_header_height + self.geometry_mapper.row_pos(r)
                rh = self.geometry_mapper.row_size(r)
                if rh <= 0:
                    continue

                is_sel = self.selection.is_row_selected(r)
                self._fill_header_cell(
                    painter, QRect(0, ry, self.row_header_width, rh), is_sel, vertical=False
                )

                painter.setPen(QPen(self.COLOR_HDR_BORDER, 1))
                painter.drawLine(0, ry + rh, self.row_header_width, ry + rh)
                painter.drawLine(
                    self.row_header_width - 1,
                    ry,
                    self.row_header_width - 1,
                    ry + rh,
                )

                painter.setPen(self.COLOR_HDR_TEXT)
                painter.drawText(
                    QRect(0, ry, self.row_header_width, rh),
                    Qt.AlignmentFlag.AlignCenter,
                    str(r + 1),
                )
            painter.restore()

        # D. Freeze Dividers across headers
        if fz_c > 0:
            painter.save()
            painter.setPen(QPen(QColor(128, 128, 128), 2))
            painter.drawLine(
                self.row_header_width + fz_c_w,
                0,
                self.row_header_width + fz_c_w,
                self.col_header_height,
            )
            painter.restore()

        if fz_r > 0:
            painter.save()
            painter.setPen(QPen(QColor(128, 128, 128), 2))
            painter.drawLine(
                0,
                self.col_header_height + fz_r_h,
                self.row_header_width,
                self.col_header_height + fz_r_h,
            )
            painter.restore()

    def _paint_pivot_reports(
        self,
        painter: QPainter,
        pr_start: int,
        pr_end: int,
        pc_start: int,
        pc_end: int,
        psx: int,
        psy: int,
        pane_clip: QRect,
    ) -> None:
        """Render dynamic pivot headers, banded rows, subtotals, and grand totals."""
        reports = getattr(self.model, "pivot_reports", [])
        if not reports:
            return

        painter.save()
        painter.setClipRect(pane_clip)

        color_head = QColor("#DCE6F2")
        color_band = QColor("#F4F7FC")
        color_subtotal = QColor("#E9EDF4")
        color_grand = QColor("#D9E1F2")
        pen_head = QPen(QColor("#9EB6CE"), 1)
        pen_subtotal = QPen(QColor("#8EA9DB"), 1)
        pen_grand = QPen(QColor("#4F81BD"), 1)

        for report in reports:
            meta = getattr(report, "meta", None)
            bbox = getattr(report, "bbox", None)
            if meta is None or bbox is None:
                continue
            b_r1, b_c1, b_r2, b_c2 = bbox
            vis_r1 = max(pr_start, b_r1)
            vis_r2 = min(pr_end, b_r2)
            vis_c1 = max(pc_start, b_c1)
            vis_c2 = min(pc_end, b_c2)
            if vis_r1 > vis_r2 or vis_c1 > vis_c2:
                continue

            band_parity_map = {r: idx % 2 for idx, r in enumerate(meta.data_rows)}

            for r in range(vis_r1, vis_r2 + 1):
                row_y = self.col_header_height + self.geometry_mapper.row_pos(r) - psy
                row_h = self.geometry_mapper.row_size(r)
                if row_h <= 0:
                    continue

                is_header = r in meta.header_rows
                is_subtotal = r in meta.subtotal_rows
                is_grand = r in meta.grand_total_rows
                is_odd_band = band_parity_map.get(r, 0) == 1

                for c in range(vis_c1, vis_c2 + 1):
                    col_x = self.row_header_width + self.geometry_mapper.col_pos(c) - psx
                    col_w = self.geometry_mapper.col_size(c)
                    if col_w <= 0:
                        continue
                    rect = QRect(col_x, row_y, col_w, row_h)

                    if is_header:
                        painter.fillRect(rect, color_head)
                        painter.setPen(pen_head)
                        painter.drawLine(col_x, row_y + row_h - 1, col_x + col_w, row_y + row_h - 1)
                    elif is_grand:
                        painter.fillRect(rect, color_grand)
                        painter.setPen(pen_grand)
                        painter.drawLine(col_x, row_y, col_x + col_w, row_y)
                        painter.drawLine(col_x, row_y + row_h - 3, col_x + col_w, row_y + row_h - 3)
                        painter.drawLine(col_x, row_y + row_h - 1, col_x + col_w, row_y + row_h - 1)
                    elif is_subtotal:
                        painter.fillRect(rect, color_subtotal)
                        painter.setPen(pen_subtotal)
                        painter.drawLine(col_x, row_y, col_x + col_w, row_y)
                        painter.drawLine(col_x, row_y + row_h - 1, col_x + col_w, row_y + row_h - 1)
                    elif c in meta.grand_total_cols and r not in meta.filter_rows:
                        painter.fillRect(rect, color_band)
                    elif is_odd_band:
                        painter.fillRect(rect, color_band)

        painter.restore()

    def _paint_pivot_dropdowns(
        self,
        painter: QPainter,
        pr_start: int,
        pr_end: int,
        pc_start: int,
        pc_end: int,
        psx: int,
        psy: int,
        pane_clip: QRect,
    ) -> None:
        """Draw dropdown buttons on PivotTable filter/header cells and active pivot outline."""
        reports = getattr(self.model, "pivot_reports", [])
        if not reports:
            return

        ar, ac = self.selection.active_cell
        painter.save()
        painter.setClipRect(pane_clip)

        for report in reports:
            meta = getattr(report, "meta", None)
            layout = getattr(report, "layout", None)
            if meta is None or layout is None:
                continue

            # Map col_idx -> whether filter is active
            active_filters: set[int] = set()
            for f_list in (layout.filters, layout.rows, layout.columns):
                for fs in f_list:
                    if fs.selected_values is not None:
                        active_filters.add(fs.col_idx)

            for (r_cell, c_cell), (_zone_type, col_idx) in meta.filter_dropdown_cells.items():
                if not (pr_start <= r_cell <= pr_end and pc_start <= c_cell <= pc_end):
                    continue
                row_y = self.col_header_height + self.geometry_mapper.row_pos(r_cell) - psy
                row_h = self.geometry_mapper.row_size(r_cell)
                col_x = self.row_header_width + self.geometry_mapper.col_pos(c_cell) - psx
                col_w = self.geometry_mapper.col_size(c_cell)
                btn_size = min(16, max(12, row_h - 2))
                if col_w <= btn_size or row_h <= 0:
                    continue

                bx = col_x + col_w - btn_size - 1
                by = row_y + row_h - btn_size - 1

                painter.fillRect(bx, by, btn_size, btn_size, QColor(236, 233, 216))
                painter.setPen(QPen(QColor(128, 128, 128), 1))
                painter.drawRect(bx, by, btn_size - 1, btn_size - 1)
                painter.setPen(QPen(Qt.GlobalColor.white, 1))
                painter.drawLine(bx + 1, by + 1, bx + btn_size - 2, by + 1)
                painter.drawLine(bx + 1, by + 1, bx + 1, by + btn_size - 2)

                arrow_color = QColor(0, 0, 255) if col_idx in active_filters else QColor(0, 0, 0)
                painter.setBrush(QBrush(arrow_color))
                painter.setPen(QPen(arrow_color, 1))
                cx = bx + btn_size // 2
                cy = by + btn_size // 2
                painter.drawPolygon(
                    [
                        QPoint(cx - 3, cy - 1),
                        QPoint(cx + 3, cy - 1),
                        QPoint(cx, cy + 2),
                    ]
                )

            # Active PivotTable outline when active cell is inside this report
            if hasattr(report, "contains_cell") and report.contains_cell(ar, ac):
                b_r1, b_c1, b_r2, b_c2 = report.bbox
                ox1 = self.row_header_width + self.geometry_mapper.col_pos(b_c1) - psx
                oy1 = self.col_header_height + self.geometry_mapper.row_pos(b_r1) - psy
                ox2 = self.row_header_width + self.geometry_mapper.col_pos(b_c2 + 1) - psx
                oy2 = self.col_header_height + self.geometry_mapper.row_pos(b_r2 + 1) - psy
                painter.setPen(QPen(QColor("#4F81BD"), 1, Qt.PenStyle.DotLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRect(ox1, oy1, ox2 - ox1 - 1, oy2 - oy1 - 1))

        painter.restore()
