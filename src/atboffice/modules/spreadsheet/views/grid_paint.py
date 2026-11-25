"""Cell painting for the spreadsheet grid."""

from __future__ import annotations

import logging
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
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)

from atboffice.drawing.numfmt import FormatSegment, FormattedResult, format_value
from atboffice.modules.spreadsheet.models.conditional_format import (
    evaluate_cf_for_cell,
)
from atboffice.modules.spreadsheet.models.excel_units import excel_mdw
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
)
from atboffice.modules.spreadsheet.models.table_style import (
    overlay_table_style,
    table_style_at,
)
from atboffice.modules.spreadsheet.views.cf_icons import draw_icon, icon_size

if TYPE_CHECKING:
    pass
from atboffice.modules.spreadsheet.views.grid_types import (
    HitZone,
)

logger = logging.getLogger(__name__)


class GridPaintMixin:
    """Paints cell fills, borders, text, rich text and overflow for each pane."""

    # -------------------------------------------------------------------------
    # Painting Subsystem
    # -------------------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self.viewport())
        try:
            self._render_paint_event(painter, event)
        except Exception:
            logger.exception("Unexpected error during GridViewport.paintEvent")
        finally:
            if painter.isActive():
                painter.end()

    def _render_paint_event(self, painter: QPainter, event: QPaintEvent) -> None:
        # Header sizes follow the visible rows (wider when row numbers gain a digit).
        self.update_header_dimensions()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # All grid geometry is in unzoomed pixels; scale it once here
        # (ledger/js/render.js multiplies the same geometry by the zoom).
        if self.zoom != 1.0:
            painter.scale(self.zoom, self.zoom)

        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        vw, vh = self._view_size()

        # Background
        painter.fillRect(0, 0, vw, vh, Qt.GlobalColor.white)

        # 1. Determine visible rows and columns
        start_row = self.geometry_mapper.find_row_at(scroll_y)
        end_row = self.geometry_mapper.find_row_at(scroll_y + vh)
        start_col = self.geometry_mapper.find_col_at(scroll_x)
        end_col = self.geometry_mapper.find_col_at(scroll_x + vw)

        # Cell area clip rect
        cell_clip = QRect(
            self.row_header_width,
            self.col_header_height,
            vw - self.row_header_width,
            vh - self.col_header_height,
        )

        # 2. Panes Partitioning (Corner, Top, Left, Main)
        fz_r = self.freeze_rows
        fz_c = self.freeze_cols
        fz_r_h = self.geometry_mapper.row_pos(fz_r) if fz_r > 0 else 0
        fz_c_w = self.geometry_mapper.col_pos(fz_c) if fz_c > 0 else 0
        x0 = self.row_header_width
        y0 = self.col_header_height

        panes: list[tuple[int, int, int, int, int, int, QRect]] = []
        # Main scrollable pane (always present)
        main_r1 = max(fz_r, start_row)
        main_r2 = max(main_r1, end_row)
        main_c1 = max(fz_c, start_col)
        main_c2 = max(main_c1, end_col)
        main_clip = QRect(
            x0 + fz_c_w, y0 + fz_r_h, max(0, vw - x0 - fz_c_w), max(0, vh - y0 - fz_r_h)
        )
        panes.append((main_r1, main_r2, main_c1, main_c2, scroll_x, scroll_y, main_clip))

        # Top frozen pane (pinned vertically, scrolls horizontally)
        if fz_r > 0:
            top_clip = QRect(x0 + fz_c_w, y0, max(0, vw - x0 - fz_c_w), fz_r_h)
            panes.append((0, fz_r - 1, main_c1, main_c2, scroll_x, 0, top_clip))

        # Left frozen pane (pinned horizontally, scrolls vertically)
        if fz_c > 0:
            left_clip = QRect(x0, y0 + fz_r_h, fz_c_w, max(0, vh - y0 - fz_r_h))
            panes.append((main_r1, main_r2, 0, fz_c - 1, 0, scroll_y, left_clip))

        # Corner frozen pane (pinned both horizontally and vertically)
        if fz_r > 0 and fz_c > 0:
            corner_clip = QRect(x0, y0, fz_c_w, fz_r_h)
            panes.append((0, fz_r - 1, 0, fz_c - 1, 0, 0, corner_clip))

        for pr_start, pr_end, pc_start, pc_end, psx, psy, p_clip in panes:
            if p_clip.width() <= 0 or p_clip.height() <= 0:
                continue
            self._paint_pane(painter, pr_start, pr_end, pc_start, pc_end, psx, psy, p_clip)

        # 5.10 Draw Audit Tracer Arrows
        self._paint_audit_arrows(painter, cell_clip, scroll_x, scroll_y)

        # 5.11 Draw Freeze Panes Split Lines
        if self.freeze_rows > 0:
            frozen_y = y0 + fz_r_h
            painter.save()
            painter.setPen(QPen(QColor(128, 128, 128), 2))
            painter.drawLine(x0, frozen_y, vw, frozen_y)
            painter.restore()

        if self.freeze_cols > 0:
            frozen_x = x0 + fz_c_w
            painter.save()
            painter.setPen(QPen(QColor(128, 128, 128), 2))
            painter.drawLine(frozen_x, y0, frozen_x, vh)
            painter.restore()

        # 5.12 Draw Page Break Preview overlay & watermarks if active
        self._paint_page_break_preview(painter, cell_clip, scroll_x, scroll_y, vw, vh)

        # 6. Draw Fixed Headers (Column Headers, Row Headers, Corner)
        self._paint_headers(
            painter, start_row, end_row, start_col, end_col, scroll_x, scroll_y, vw, vh
        )

        # 7. Draw Resize Guide Line (on top of headers and grid)
        if self._drag_mode == HitZone.COL_RESIZE and self._resize_preview_pos is not None:
            painter.save()
            guide_pen = QPen(QColor(0, 0, 0), 1, Qt.PenStyle.DashLine)
            painter.setPen(guide_pen)
            painter.drawLine(self._resize_preview_pos, 0, self._resize_preview_pos, vh)
            painter.restore()
        elif self._drag_mode == HitZone.ROW_RESIZE and self._resize_preview_pos is not None:
            painter.save()
            guide_pen = QPen(QColor(0, 0, 0), 1, Qt.PenStyle.DashLine)
            painter.setPen(guide_pen)
            painter.drawLine(0, self._resize_preview_pos, vw, self._resize_preview_pos)
            painter.restore()

    def _cell_font(self, family: str | None, size: float | None) -> QFont:
        font = QFont(family or "Arial")
        font.setPointSizeF(float(size or 10) * self._print_font_factor)
        return font

    def _fm(self, font: QFont) -> QFontMetricsF:
        device = self._print_device
        return QFontMetricsF(font, device) if device is not None else QFontMetricsF(font)

    def paint_print_region(
        self,
        painter: QPainter,
        r1: int,
        r2: int,
        c1: int,
        c2: int,
        gridlines: bool = False,
        font_factor: float = 1.0,
    ) -> None:
        """Paint cells r1..r2 × c1..c2 with the on-screen painter, origin at (0, 0).

        Units are grid pixels. Fills, conditional formats, merges, wrapped/rotated text,
        rich text, table styles and borders print exactly as on screen; selection, the
        active cell, handles, filter buttons and comment indicators do not.
        ``font_factor`` scales point sizes (the caller maps grid pixels to points).
        """
        geo = self.geometry_mapper
        x0 = self.row_header_width
        y0 = self.col_header_height
        width = geo.col_pos(c2 + 1) - geo.col_pos(c1)
        height = geo.row_pos(r2 + 1) - geo.row_pos(r1)
        saved = (self._printing, self._print_gridlines, self._print_font_factor, self._print_device)
        self._printing = True
        self._print_gridlines = gridlines
        self._print_font_factor = font_factor
        self._print_device = painter.device()
        painter.save()
        try:
            # Pane x = header + col_pos(c) - psx, so psx = col_pos(c1) puts c1 at the
            # clip origin; translating by the header size moves that to (0, 0).
            painter.translate(-x0, -y0)
            psx = geo.col_pos(c1)
            psy = geo.row_pos(r1)
            clip = QRect(x0, y0, int(math.ceil(width)), int(math.ceil(height)))
            self._paint_pane(painter, r1, r2, c1, c2, psx, psy, clip)
        finally:
            painter.restore()
            (self._printing, self._print_gridlines, self._print_font_factor, self._print_device) = (
                saved
            )

    def _paint_pane(
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
        """Render gridlines, selection, cells, and indicators for a single pane."""
        vw, vh = self._view_size()
        printing = self._printing
        if printing:
            vw, vh = pane_clip.right() + 1, pane_clip.bottom() + 1
        # 2. Draw Selection Overlays
        painter.save()
        painter.setClipRect(pane_clip)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.COLOR_SELECTION))

        # Like render.js: single cells are not shaded and the active cell stays white.
        act_r, act_c = self.selection.active_cell
        for rg in [] if printing else self.selection.ranges:
            if rg.min_r == rg.max_r and rg.min_c == rg.max_c:
                continue
            if rg.max_r < pr_start or rg.min_r > pr_end:
                continue
            if rg.max_c < pc_start or rg.min_c > pc_end:
                continue
            x1 = self.row_header_width + self.geometry_mapper.col_pos(rg.min_c) - psx
            y1 = self.col_header_height + self.geometry_mapper.row_pos(rg.min_r) - psy
            x2 = self.row_header_width + self.geometry_mapper.col_pos(rg.max_c + 1) - psx
            y2 = self.col_header_height + self.geometry_mapper.row_pos(rg.max_r + 1) - psy
            shade = QPainterPath()
            shade.setFillRule(Qt.FillRule.OddEvenFill)
            shade.addRect(QRectF(x1, y1, x2 - x1 - 1, y2 - y1 - 1))
            if rg.contains(act_r, act_c):
                ax1 = self.row_header_width + self.geometry_mapper.col_pos(act_c) - psx
                ay1 = self.col_header_height + self.geometry_mapper.row_pos(act_r) - psy
                ax2 = self.row_header_width + self.geometry_mapper.col_pos(act_c + 1) - psx
                ay2 = self.col_header_height + self.geometry_mapper.row_pos(act_r + 1) - psy
                shade.addRect(QRectF(ax1, ay1, ax2 - ax1, ay2 - ay1))
            painter.drawPath(shade)
        painter.restore()

        # 2b. Draw AutoFill Drag Preview Rectangle
        if self._fill_preview_range is not None and not printing:
            painter.save()
            painter.setClipRect(pane_clip)
            pr = self._fill_preview_range
            px1 = self.row_header_width + self.geometry_mapper.col_pos(pr.min_c) - psx
            py1 = self.col_header_height + self.geometry_mapper.row_pos(pr.min_r) - psy
            px2 = self.row_header_width + self.geometry_mapper.col_pos(pr.max_c + 1) - psx
            py2 = self.col_header_height + self.geometry_mapper.row_pos(pr.max_r + 1) - psy
            dash_pen = QPen(QColor(128, 128, 128), 2, Qt.PenStyle.DashLine)
            painter.setPen(dash_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRect(px1, py1, px2 - px1, py2 - py1))
            painter.restore()

        # 2c. Draw Selection Border Drag Preview Rectangle
        if (
            self._move_preview_range is not None
            and self._move_preview_range != self._move_src_range
        ):
            painter.save()
            painter.setClipRect(pane_clip)
            pr = self._move_preview_range
            px1 = self.row_header_width + self.geometry_mapper.col_pos(pr.min_c) - psx
            py1 = self.col_header_height + self.geometry_mapper.row_pos(pr.min_r) - psy
            px2 = self.row_header_width + self.geometry_mapper.col_pos(pr.max_c + 1) - psx
            py2 = self.col_header_height + self.geometry_mapper.row_pos(pr.max_r + 1) - psy
            move_pen = QPen(self.COLOR_ACTIVE_BORDER, 2, Qt.PenStyle.DashLine)
            painter.setPen(move_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRect(px1, py1, px2 - px1, py2 - py1))
            painter.restore()

        # 3. Draw Gridlines (unless the sheet hides them: showGridLines="0")
        if self._print_gridlines if printing else self.show_grid_lines:
            painter.save()
            painter.setClipRect(pane_clip)
            painter.setPen(QPen(self.COLOR_GRIDLINE, 1))

            # Vertical gridlines
            for c in range(pc_start, pc_end + 2):
                x = self.row_header_width + self.geometry_mapper.col_pos(c) - psx
                painter.drawLine(x, self.col_header_height, x, vh)

            # Horizontal gridlines
            for r in range(pr_start, pr_end + 2):
                y = self.col_header_height + self.geometry_mapper.row_pos(r) - psy
                painter.drawLine(self.row_header_width, y, vw, y)
            painter.restore()

        # 3.5 Draw Dynamic PivotTable Bands, Headers, Subtotals & Grand Totals
        self._paint_pivot_reports(painter, pr_start, pr_end, pc_start, pc_end, psx, psy, pane_clip)

        # 4. Draw Cell Contents (Pass 1: Fills/Merges, Pass 2: Text/Spill, Pass 3: Borders)
        painter.save()
        painter.setClipRect(pane_clip)

        fz_c = 0 if printing else self.freeze_cols
        pane_min_col = fz_c if (fz_c > 0 and pc_start >= fz_c) else 0
        pane_max_col = (
            fz_c - 1 if (fz_c > 0 and pc_end < fz_c) else self.geometry_mapper.max_cols - 1
        )
        items, merge_by_cell = self._collect_pane_items(
            pr_start, pr_end, pc_start, pc_end, psx, psy
        )

        # Pass 1: Fills, patterns, data bars, and internal gridline erasure for unfilled merges
        for r, c, cell, merge, item_rect, cf_res in items:
            self._paint_cell_item_fill(
                painter,
                r,
                c,
                cell,
                merge,
                item_rect,
                cf_res,
                pr_start,
                pr_end,
                pc_start,
                pc_end,
                psx,
                psy,
            )

        # Pass 2: Cell text (with bidirectional spill) and offscreen overflow
        for r, c, cell, merge, item_rect, cf_res in items:
            if cell is None:
                continue
            self._paint_cell_item_text(
                painter,
                r,
                c,
                cell,
                merge,
                item_rect,
                cf_res,
                psx,
                pane_min_col,
                pane_max_col,
                merge_by_cell,
            )

        self._paint_offscreen_overflow(
            painter,
            pr_start,
            pr_end,
            pc_start,
            pc_end,
            psx,
            psy,
            pane_min_col,
            pane_max_col,
            merge_by_cell,
        )

        # Pass 3: Borders
        for r, c, cell, merge, item_rect, _cf_res in items:
            ts = table_style_at(self.model, r, c)
            if cell is None and merge is None and ts is None:
                continue
            self._paint_cell_item_borders(
                painter, cell, merge, item_rect, ts.borders if ts is not None else None
            )

        painter.restore()
        if printing:
            return  # editing aids below (active cell, handles, buttons, comments) never print

        # 4b. Dynamic-array spill border (blue) while the active cell is inside the spill
        self._paint_spill_border(painter, psx, psy, pane_clip)

        # 5. Draw Active Cell 2px Border & AutoFill Handle
        painter.save()
        painter.setClipRect(pane_clip)
        ar, ac = self.selection.active_cell
        if pr_start <= ar <= pr_end and pc_start <= ac <= pc_end:
            ax = self.row_header_width + self.geometry_mapper.col_pos(ac) - psx
            ay = self.col_header_height + self.geometry_mapper.row_pos(ar) - psy
            aw = self.geometry_mapper.col_size(ac)
            ah = self.geometry_mapper.row_size(ar)

            painter.setPen(QPen(self.COLOR_ACTIVE_BORDER, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRect(ax, ay, aw, ah))

            # AutoFill handle square at bottom-right of active range
            pr = self.selection.primary_range
            fx = self.row_header_width + self.geometry_mapper.col_pos(pr.max_c + 1) - psx - 3
            fy = self.col_header_height + self.geometry_mapper.row_pos(pr.max_r + 1) - psy - 3
            painter.fillRect(fx - 1, fy - 1, 7, 7, Qt.GlobalColor.white)
            painter.fillRect(fx, fy, 5, 5, self.COLOR_FILL_HANDLE)

            # Dropdown arrow indicator if active cell has list validation
            active_dv = self.model.get_validation_at(ar, ac)
            if active_dv is not None and active_dv.type == "list" and active_dv.show_dropdown:
                btn_w = 16
                btn_h = ah - 2
                btn_x = ax + aw - btn_w - 1
                btn_y = ay + 1
                self._dv_dropdown_rect = QRect(btn_x, btn_y, btn_w, btn_h)
                painter.fillRect(self._dv_dropdown_rect, QColor(236, 233, 216))
                painter.setPen(QPen(QColor(158, 182, 206), 1))
                painter.drawRect(self._dv_dropdown_rect)
                painter.setPen(QPen(Qt.GlobalColor.black, 1))
                mx = btn_x + btn_w // 2
                my = btn_y + btn_h // 2
                painter.drawLine(mx - 3, my - 1, mx + 3, my - 1)
                painter.drawLine(mx - 2, my, mx + 2, my)
                painter.drawLine(mx - 1, my + 1, mx + 1, my + 1)
            else:
                self._dv_dropdown_rect = None
        painter.restore()

        # 5.5 Draw Reference Highlights (if in formula editing / point mode)
        if self.editor_controller is not None and self.editor_controller.highlights:
            painter.save()
            painter.setClipRect(pane_clip)
            for hl in self.editor_controller.highlights:
                hx = self.row_header_width + self.geometry_mapper.col_pos(hl.c1) - psx
                hy = self.col_header_height + self.geometry_mapper.row_pos(hl.r1) - psy
                hw = sum(self.geometry_mapper.col_size(c) for c in range(hl.c1, hl.c2 + 1))
                hh = sum(self.geometry_mapper.row_size(r) for r in range(hl.r1, hl.r2 + 1))

                painter.setPen(QPen(hl.color, 2, Qt.PenStyle.SolidLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRect(hx, hy, hw, hh))

                # Corner handles
                for cx, cy in [
                    (hx, hy),
                    (hx + hw - 4, hy),
                    (hx, hy + hh - 4),
                    (hx + hw - 4, hy + hh - 4),
                ]:
                    painter.fillRect(cx, cy, 4, 4, hl.color)
            painter.restore()

        # 5.6 Draw AutoFilter Buttons (sheet AutoFilter + table header rows,
        # ledger/js/grid.js syncWidgets)
        filter_bands: list[tuple[int, int, int, Any]] = []
        af = getattr(self.model, "auto_filter", None)
        if af is not None and hasattr(af, "r1") and hasattr(af, "c1") and hasattr(af, "c2"):
            filter_bands.append((af.r1, af.c1, af.c2, getattr(af, "cols", {})))
        for tbl in getattr(self.model, "tables", None) or ():
            if tbl.has_auto_filter and tbl.has_header:
                filter_bands.append((tbl.r1, tbl.c1, tbl.c2, {}))
        for r1, band_c1, band_c2, cols in filter_bands:
            if pr_start <= r1 <= pr_end:
                painter.save()
                painter.setClipRect(pane_clip)
                row_y = self.col_header_height + self.geometry_mapper.row_pos(r1) - psy
                row_h = self.geometry_mapper.row_size(r1)
                btn_size = min(16, max(12, row_h - 2))

                for c in range(max(pc_start, band_c1), min(pc_end, band_c2) + 1):
                    col_x = self.row_header_width + self.geometry_mapper.col_pos(c) - psx
                    col_w = self.geometry_mapper.col_size(c)
                    if col_w <= btn_size:
                        continue

                    bx = col_x + col_w - btn_size - 1
                    by = row_y + row_h - btn_size - 1

                    # Draw Office 2003 bevel button
                    painter.fillRect(bx, by, btn_size, btn_size, QColor(236, 233, 216))
                    # Reset the brush: the previous button's arrow left it solid.
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor(128, 128, 128), 1))
                    painter.drawRect(bx, by, btn_size - 1, btn_size - 1)
                    # 1px top/left highlight
                    painter.setPen(QPen(Qt.GlobalColor.white, 1))
                    painter.drawLine(bx + 1, by + 1, bx + btn_size - 2, by + 1)
                    painter.drawLine(bx + 1, by + 1, bx + 1, by + btn_size - 2)

                    # Downward arrow triangle
                    col_offset = c - band_c1
                    has_active_crit = (
                        isinstance(cols, dict)
                        and col_offset in cols
                        and hasattr(cols[col_offset], "has_criteria")
                        and cols[col_offset].has_criteria()
                    )
                    arrow_color = QColor(0, 0, 255) if has_active_crit else QColor(0, 0, 0)
                    painter.setBrush(QBrush(arrow_color))
                    painter.setPen(QPen(arrow_color, 1))

                    cx = bx + btn_size // 2
                    cy = by + btn_size // 2
                    arrow_poly = [
                        QPoint(cx - 3, cy - 1),
                        QPoint(cx + 3, cy - 1),
                        QPoint(cx, cy + 2),
                    ]
                    painter.drawPolygon(arrow_poly)

                painter.restore()

        # 5.6b Draw PivotTable Filter Dropdown Buttons & Active Outline
        self._paint_pivot_dropdowns(
            painter, pr_start, pr_end, pc_start, pc_end, psx, psy, pane_clip
        )

        # 5.7 Draw Invalid Data Validation Circles (red ellipses)
        circles = getattr(self.model, "invalid_circles", [])
        if circles:
            painter.save()
            painter.setClipRect(pane_clip)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            circle_pen = QPen(QColor(255, 0, 0), 1.5)
            painter.setPen(circle_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            for cr, cc in circles:
                if cr < pr_start or cr > pr_end or cc < pc_start or cc > pc_end:
                    continue
                cx = self.row_header_width + self.geometry_mapper.col_pos(cc) - psx
                cy = self.col_header_height + self.geometry_mapper.row_pos(cr) - psy
                cw = self.geometry_mapper.col_size(cc)
                ch = self.geometry_mapper.row_size(cr)
                if cw <= 0 or ch <= 0:
                    continue
                painter.drawEllipse(QRectF(cx - 3, cy - 2, cw + 6, ch + 4))
            painter.restore()

        # 5.8 Draw Comment Red Triangle Indicators
        comments = getattr(self.model, "comments", {})
        if comments:
            painter.save()
            painter.setClipRect(pane_clip)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 0, 0)))
            s = 6
            for cr, cc in comments.keys():
                if cr < pr_start or cr > pr_end or cc < pc_start or cc > pc_end:
                    continue
                cx = self.row_header_width + self.geometry_mapper.col_pos(cc) - psx
                cy = self.col_header_height + self.geometry_mapper.row_pos(cr) - psy
                cw = self.geometry_mapper.col_size(cc)
                ch = self.geometry_mapper.row_size(cr)
                if cw <= 0 or ch <= 0:
                    continue
                right = cx + cw
                poly = [
                    QPoint(right - s, cy),
                    QPoint(right, cy),
                    QPoint(right, cy + s),
                ]
                painter.drawPolygon(poly)
            painter.restore()

        # 5.9 Draw Visible and Hovered Comments Callouts
        show_all = getattr(self.model, "show_all_comments", False)
        if comments:
            painter.save()
            painter.setClipRect(pane_clip)
            for (cr, cc), cm in comments.items():
                is_hovered = self._hover_comment_cell == (cr, cc)
                if not (cm.visible or show_all or is_hovered):
                    continue
                if cr < pr_start or cr > pr_end or cc < pc_start or cc > pc_end:
                    continue
                cx = self.row_header_width + self.geometry_mapper.col_pos(cc) - psx
                cy = self.col_header_height + self.geometry_mapper.row_pos(cr) - psy
                cw = self.geometry_mapper.col_size(cc)
                ch = self.geometry_mapper.row_size(cr)
                if cw <= 0 or ch <= 0:
                    continue

                box = self._comment_callout_rect(cr, cc, cm, QRect(cx, cy, cw, ch))
                bx, by, bw, bh = box.x(), box.y(), box.width(), box.height()
                flipped = bx < cx

                # Connecting leader arrow pointing from the near card edge
                # to cell top-right corner (cx + cw, cy)
                arrow_tip = QPoint(cx + cw, cy)
                arrow_base = QPoint(bx + bw if flipped else bx, by + 8)
                painter.setPen(QPen(QColor(60, 60, 60), 1))
                painter.drawLine(arrow_base, arrow_tip)

                # Leader arrow head pointing towards cell top-right corner
                dx = arrow_tip.x() - arrow_base.x()
                dy = arrow_tip.y() - arrow_base.y()
                ang = math.atan2(dy, dx)
                arrow_sz = 6.0
                p_head1 = QPointF(
                    arrow_tip.x() - arrow_sz * math.cos(ang - math.pi / 6),
                    arrow_tip.y() - arrow_sz * math.sin(ang - math.pi / 6),
                )
                p_head2 = QPointF(
                    arrow_tip.x() - arrow_sz * math.cos(ang + math.pi / 6),
                    arrow_tip.y() - arrow_sz * math.sin(ang + math.pi / 6),
                )
                painter.setBrush(QBrush(QColor(60, 60, 60)))
                painter.drawPolygon([arrow_tip, p_head1.toPoint(), p_head2.toPoint()])

                # Drop shadow behind note box
                painter.fillRect(bx + 3, by + 3, bw, bh, QColor(0, 0, 0, 45))

                # Pale yellow note box (Excel's #FFFFE1), independent of the app palette
                painter.fillRect(bx, by, bw, bh, self._COMMENT_NOTE_BG)
                painter.setPen(QPen(QColor(160, 160, 160), 1))
                # Border only: the arrow-head brush must not flood the note
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(bx, by, bw, bh)

                # Text inside note
                note_font = QFont(self.font())
                note_font.setPointSize(8)
                bold_font = QFont(note_font)
                bold_font.setBold(True)

                inner_rect = QRect(bx + 6, by + 5, bw - 12, bh - 10)
                painter.setPen(QPen(QColor(0, 0, 0), 1))
                if cm.author and cm.author.strip():
                    author_header = f"{cm.author.strip()}:"
                    painter.setFont(bold_font)
                    fm_bold = self._fm(bold_font)
                    author_h = fm_bold.height()
                    painter.drawText(
                        QRect(inner_rect.x(), inner_rect.y(), inner_rect.width(), author_h + 2),
                        Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                        author_header,
                    )
                    body_y = inner_rect.y() + author_h + 3
                    rem_h = max(0, inner_rect.bottom() - body_y)
                    body_rect = QRect(inner_rect.x(), body_y, inner_rect.width(), rem_h)
                    painter.setFont(note_font)
                    painter.drawText(
                        body_rect,
                        Qt.AlignmentFlag.AlignTop
                        | Qt.AlignmentFlag.AlignLeft
                        | Qt.TextFlag.TextWordWrap,
                        cm.text or "",
                    )
                else:
                    painter.setFont(note_font)
                    painter.drawText(
                        inner_rect,
                        Qt.AlignmentFlag.AlignTop
                        | Qt.AlignmentFlag.AlignLeft
                        | Qt.TextFlag.TextWordWrap,
                        cm.text or "",
                    )
            painter.restore()

    @staticmethod
    def _excel_mdw(font_family: str, font_size: int) -> int:
        """Maximum digit width (px) matching Excel/VibeOffice font sizing rules."""
        return excel_mdw(font_family, font_size)

    @classmethod
    def _hinted_text_width(cls, text: str, font_family: str, font_size: int) -> float:
        """Estimate rendered width using Excel's hinted character metrics."""
        mdw = float(cls._excel_mdw(font_family, font_size))
        narrow = max(2.0, mdw * 0.5)
        w = 0.0
        for ch in text:
            w += narrow if ch in ".,:-' " else mdw
        return w

    @staticmethod
    def _measure_formatted_width(fmt_res: FormattedResult, cell_fm: QFontMetricsF) -> float:
        """Measure horizontal advance of formatted segments excluding fill tokens."""
        if not fmt_res.segments:
            return cell_fm.horizontalAdvance(fmt_res.text)
        total = 0.0
        for seg in fmt_res.segments:
            if seg.kind in ("text", "pad"):
                total += cell_fm.horizontalAdvance(seg.value)
        return total

    def _format_cell_for_paint(
        self,
        cell: CellData,
        disp_val: Any,
        cell_fm: QFontMetricsF,
        col_w: int,
    ) -> FormattedResult:
        """Format a cell value for painting, applying General width fitting and #### overflow."""
        is_num = isinstance(disp_val, (int, float)) and not isinstance(disp_val, bool)
        fit_to_width = (
            is_num
            and not cell.wrap_text
            and not cell.shrink_to_fit
            and (cell.text_rotation or 0) == 0
        )
        fmt_code = cell.format_code or "General"
        if not fit_to_width:
            return format_value(disp_val, fmt_code)

        avail = max(1.0, float(col_w - 6))
        hash_w = max(1.0, cell_fm.horizontalAdvance("#"))
        hashes = "#" * max(1, int(avail // hash_w))

        if fmt_code.lower() == "general":
            mdw = float(self._excel_mdw(cell.font_family, cell.font_size))
            chars = max(1, min(11, int((avail - 5.0) // mdw) + 1))
            res = format_value(disp_val, "General", max_chars=chars)
            tw = self._hinted_text_width(res.text, cell.font_family, cell.font_size)
            while tw > avail and chars > 1 and not res.text.startswith("#"):
                chars -= 1
                res = format_value(disp_val, "General", max_chars=chars)
                tw = self._hinted_text_width(res.text, cell.font_family, cell.font_size)
            if res.is_error or res.text.startswith("#") or tw > avail:
                return FormattedResult(
                    text=hashes,
                    color=res.color,
                    is_numeric=True,
                    is_error=True,
                    segments=(FormatSegment("text", hashes),),
                )
            return res

        res = format_value(disp_val, fmt_code)
        hinted_w = self._hinted_text_width(res.text, cell.font_family, cell.font_size)
        if res.is_error or (res.is_numeric and hinted_w > avail + 0.5):
            return FormattedResult(
                text=hashes,
                color=res.color,
                is_numeric=True,
                is_error=True,
                segments=(FormatSegment("text", hashes),),
            )
        return res

    @staticmethod
    def _paint_formatted_segments(
        painter: QPainter,
        segments: tuple[FormatSegment, ...],
        cell_fm: QFontMetricsF,
        text_rect: QRect,
        v_flag: Qt.AlignmentFlag,
        eff_h: str,
    ) -> None:
        """Render formatted segments with exact `_x` padding and `*x` fill expansion."""
        avail = max(0.0, float(text_rect.width()))
        fixed_w = sum(cell_fm.horizontalAdvance(s.value) for s in segments if s.kind != "fill")
        fill_count = sum(1 for s in segments if s.kind == "fill")
        spare = max(0.0, avail - fixed_w)

        if fill_count > 0:
            cur_x = float(text_rect.left())
        elif eff_h == "right":
            cur_x = float(text_rect.right() + 1) - fixed_w
        elif eff_h == "center":
            cur_x = float(text_rect.left()) + (avail - fixed_w) / 2.0
        else:
            cur_x = float(text_rect.left())

        top_y = float(text_rect.top())
        row_h = float(text_rect.height())
        align_seg = v_flag | Qt.AlignmentFlag.AlignLeft

        for seg in segments:
            if seg.kind == "text":
                seg_w = cell_fm.horizontalAdvance(seg.value)
                painter.drawText(
                    QRectF(cur_x, top_y, seg_w + 2.0, row_h),
                    align_seg,
                    seg.value,
                )
                cur_x += seg_w
            elif seg.kind == "pad":
                cur_x += cell_fm.horizontalAdvance(seg.value)
            elif seg.kind == "fill":
                each_fill = spare / fill_count
                if seg.value != " " and each_fill > 0:
                    cw = max(1.0, cell_fm.horizontalAdvance(seg.value))
                    repeat_n = int(each_fill // cw)
                    if repeat_n > 0:
                        painter.drawText(
                            QRectF(cur_x, top_y, each_fill, row_h),
                            align_seg,
                            seg.value * repeat_n,
                        )
                cur_x += each_fill

    def _collect_pane_items(
        self,
        pr_start: int,
        pr_end: int,
        pc_start: int,
        pc_end: int,
        psx: int,
        psy: int,
    ) -> tuple[
        list[tuple[int, int, CellData | None, tuple[int, int, int, int] | None, QRect, Any]],
        dict[tuple[int, int], tuple[int, int, int, int]],
    ]:
        """Collect visible merged blocks and unmerged cells for a pane."""
        items: list[
            tuple[int, int, CellData | None, tuple[int, int, int, int] | None, QRect, Any]
        ] = []
        merge_by_cell: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        seen_merges: set[tuple[int, int, int, int]] = set()

        scan_c_min = max(0, pc_start - 256)
        scan_c_max = min(self.geometry_mapper.max_cols - 1, pc_end + 64)

        for raw_m in getattr(self.model, "merges", []):
            m = self._normalize_merge(raw_m)
            mr1, mc1, mr2, mc2 = m
            if mr2 < pr_start or mr1 > pr_end:
                continue
            # Index cells in visible row band + horizontal spill scan window
            if not (mc2 < scan_c_min or mc1 > scan_c_max):
                ir1 = max(mr1, pr_start)
                ir2 = min(mr2, pr_end)
                ic1 = max(mc1, scan_c_min)
                ic2 = min(mc2, scan_c_max)
                for rr in range(ir1, ir2 + 1):
                    for cc in range(ic1, ic2 + 1):
                        merge_by_cell[(rr, cc)] = m
            if mc2 < pc_start or mc1 > pc_end or m in seen_merges:
                continue
            seen_merges.add(m)

            mx = self.row_header_width + self.geometry_mapper.col_pos(mc1) - psx
            my = self.col_header_height + self.geometry_mapper.row_pos(mr1) - psy
            mx2 = self.row_header_width + self.geometry_mapper.col_pos(mc2 + 1) - psx
            my2 = self.col_header_height + self.geometry_mapper.row_pos(mr2 + 1) - psy
            mw = mx2 - mx
            mh = my2 - my
            if mw <= 0 or mh <= 0:
                continue
            anchor_cell = self.model.get_cell(mr1, mc1)
            cf_res = evaluate_cf_for_cell(self.model, mr1, mc1) if anchor_cell is not None else None
            cf_res = overlay_table_style(
                cf_res,
                table_style_at(self.model, mr1, mc1),
                anchor_cell,
                self._default_font_color(),
            )
            items.append((mr1, mc1, anchor_cell, m, QRect(mx, my, mw, mh), cf_res))

        has_tables = bool(getattr(self.model, "tables", None))
        for r in range(pr_start, pr_end + 1):
            row_h = self.geometry_mapper.row_size(r)
            if row_h <= 0:
                continue
            row_y = self.col_header_height + self.geometry_mapper.row_pos(r) - psy
            for c in range(pc_start, pc_end + 1):
                if (r, c) in merge_by_cell:
                    continue
                cell = self.model.get_cell(r, c)
                # Empty cells inside a table still paint the table style, and
                # empty cells under a filled row/column style paint that fill.
                if (
                    cell is None
                    and not (has_tables and self.model.table_at(r, c))
                    and self._default_fill_at(r, c) is None
                ):
                    continue
                col_w = self.geometry_mapper.col_size(c)
                if col_w <= 0:
                    continue
                col_x = self.row_header_width + self.geometry_mapper.col_pos(c) - psx
                cf_res = self._cell_format_overlay(r, c, cell)
                items.append((r, c, cell, None, QRect(col_x, row_y, col_w, row_h), cf_res))

        return items, merge_by_cell

    def _default_fill_at(self, r: int, c: int) -> str | None:
        """Row/column default-style fill an empty cell inherits (hides gridlines)."""
        lookup = getattr(self.model, "default_fill_at", None)
        return lookup(r, c) if lookup is not None else None

    def _default_font_color(self) -> str | None:
        extra = getattr(self.model, "extra", None)
        return extra.get("default_font_color") if isinstance(extra, dict) else None

    def _cell_format_overlay(self, r: int, c: int, cell: CellData | None) -> Any:
        """Conditional format result with the Excel table style folded underneath."""
        cf_res = evaluate_cf_for_cell(self.model, r, c) if cell is not None else None
        return overlay_table_style(
            cf_res,
            table_style_at(self.model, r, c),
            cell,
            self._default_font_color(),
        )

    def _paint_cell_item_fill(
        self,
        painter: QPainter,
        r: int,
        c: int,
        cell: CellData | None,
        merge: tuple[int, int, int, int] | None,
        item_rect: QRect,
        cf_res: Any,
        pr_start: int,
        pr_end: int,
        pc_start: int,
        pc_end: int,
        psx: int,
        psy: int,
    ) -> None:
        """Paint cell or merge background fill, pattern, data bar, and merge gridline erasure."""
        bg_col = (
            cf_res.bg_color
            if (cf_res and cf_res.bg_color)
            else (cell.bg_color if cell is not None else self._default_fill_at(r, c))
        )
        pattern = cell.pattern if cell is not None else None

        if bg_col or pattern:
            painter.save()
            painter.setClipRect(item_rect, Qt.ClipOperation.IntersectClip)
            if bg_col:
                painter.fillRect(item_rect, QColor(bg_col))
            if pattern and cell is not None:
                from atboffice.modules.spreadsheet.dialogs.pattern_defs import (
                    create_pattern_brush,
                )

                brush = create_pattern_brush(
                    pattern,
                    cell.pattern_color or "#000000",
                    bg_col or "#FFFFFF",
                )
                painter.fillRect(item_rect, brush)
            painter.restore()
        elif merge is not None:
            # Erase internal gridlines inside an unfilled merge while keeping outer gridlines
            mr1, mc1, mr2, mc2 = merge
            painter.save()
            painter.setPen(QPen(Qt.GlobalColor.white, 1))
            y_top = item_rect.top() + 1
            y_bot = item_rect.bottom()
            x_left = item_rect.left() + 1
            x_right = item_rect.right()
            for mc in range(max(mc1 + 1, pc_start), min(mc2, pc_end + 1) + 1):
                gx = self.row_header_width + self.geometry_mapper.col_pos(mc) - psx
                if x_left <= gx <= x_right:
                    painter.drawLine(gx, y_top, gx, y_bot)
            for mr in range(max(mr1 + 1, pr_start), min(mr2, pr_end + 1) + 1):
                gy = self.col_header_height + self.geometry_mapper.row_pos(mr) - psy
                if y_top <= gy <= y_bot:
                    painter.drawLine(x_left, gy, x_right, gy)
            painter.restore()

        if cf_res and cf_res.data_bar:
            col_x = item_rect.x()
            row_y = item_rect.y()
            col_w = item_rect.width()
            row_h = item_rect.height()
            painter.save()
            painter.setClipRect(item_rect, Qt.ClipOperation.IntersectClip)
            bar_frac = max(0.0, min(1.0, float(cf_res.data_bar.get("frac", 0.0))))
            bar_color = QColor(str(cf_res.data_bar.get("color", "#638EC6")))
            bar_w = int((col_w - 2) * bar_frac)
            bar_h = row_h - 2
            bx = col_x + 1
            by = row_y + 1
            if bar_w > 0 and bar_h > 0:
                is_gradient = cf_res.data_bar.get("gradient", True)
                if is_gradient:
                    grad = QLinearGradient(bx, by, bx + bar_w, by)
                    grad.setColorAt(0.0, bar_color)
                    grad.setColorAt(1.0, QColor(255, 255, 255, 220))
                    painter.fillRect(QRect(bx, by, bar_w, bar_h), QBrush(grad))
                else:
                    painter.fillRect(QRect(bx, by, bar_w, bar_h), bar_color)

                if cf_res.data_bar.get("border", True):
                    border_col = cf_res.data_bar.get("border_color")
                    b_pen_color = QColor(border_col) if border_col else bar_color
                    painter.setPen(QPen(b_pen_color, 1))
                    painter.drawRect(QRect(bx, by, max(0, bar_w - 1), max(0, bar_h - 1)))
            painter.restore()

        if cf_res and cf_res.icon:
            # Icon sets: the icon sits at the cell's left edge, bottom-aligned
            # (ledger/js/render.js drawIcon call site).
            size = icon_size(item_rect.height())
            if size > 2:
                pad = 2
                painter.save()
                painter.setClipRect(item_rect, Qt.ClipOperation.IntersectClip)
                draw_icon(
                    painter,
                    str(cf_res.icon.get("set", "3TrafficLights1")),
                    int(cf_res.icon.get("i", 0)),
                    item_rect.x() + pad,
                    item_rect.y() + item_rect.height() - size - 2,
                    size,
                )
                painter.restore()

    def _paint_cell_item_borders(
        self,
        painter: QPainter,
        cell: CellData | None,
        merge: tuple[int, int, int, int] | None,
        item_rect: QRect,
        table_borders: dict[str, BorderStyle] | None = None,
    ) -> None:
        """Paint cell or merged-block outer borders (table-style sides fill the gaps)."""
        b_top = cell.border_top if cell is not None else None
        b_bottom = cell.border_bottom if cell is not None else None
        b_left = cell.border_left if cell is not None else None
        b_right = cell.border_right if cell is not None else None

        if merge is not None:
            mr1, mc1, mr2, mc2 = merge
            if b_bottom is None:
                bl_cell = self.model.get_cell(mr2, mc1)
                if bl_cell is not None:
                    b_bottom = bl_cell.border_bottom
            if b_right is None:
                tr_cell = self.model.get_cell(mr1, mc2)
                if tr_cell is not None:
                    b_right = tr_cell.border_right

        if table_borders:
            b_top = b_top or table_borders.get("t")
            b_bottom = b_bottom or table_borders.get("b")
            b_left = b_left or table_borders.get("l")
            b_right = b_right or table_borders.get("r")

        if not any([b_top, b_bottom, b_left, b_right]):
            return

        col_x = item_rect.x()
        row_y = item_rect.y()
        col_w = item_rect.width()
        row_h = item_rect.height()

        painter.save()
        if b_top and b_top.style != "none":
            col = QColor(b_top.color) if b_top.color else Qt.GlobalColor.black
            painter.setPen(QPen(col, 2 if b_top.style in ("medium", "thick") else 1))
            painter.drawLine(col_x, row_y, col_x + col_w, row_y)
        if b_bottom and b_bottom.style != "none":
            col = QColor(b_bottom.color) if b_bottom.color else Qt.GlobalColor.black
            painter.setPen(QPen(col, 2 if b_bottom.style in ("medium", "thick") else 1))
            painter.drawLine(col_x, row_y + row_h, col_x + col_w, row_y + row_h)
        if b_left and b_left.style != "none":
            col = QColor(b_left.color) if b_left.color else Qt.GlobalColor.black
            painter.setPen(QPen(col, 2 if b_left.style in ("medium", "thick") else 1))
            painter.drawLine(col_x, row_y, col_x, row_y + row_h)
        if b_right and b_right.style != "none":
            col = QColor(b_right.color) if b_right.color else Qt.GlobalColor.black
            painter.setPen(QPen(col, 2 if b_right.style in ("medium", "thick") else 1))
            painter.drawLine(col_x + col_w, row_y, col_x + col_w, row_y + row_h)
        painter.restore()

    def _paint_cell_item_text(
        self,
        painter: QPainter,
        r: int,
        c: int,
        cell: CellData,
        merge: tuple[int, int, int, int] | None,
        item_rect: QRect,
        cf_res: Any,
        psx: int,
        pane_min_col: int,
        pane_max_col: int,
        merge_by_cell: dict[tuple[int, int], tuple[int, int, int, int]],
    ) -> None:
        """Paint cell or merged-block text with bidirectional neighbor spill and wrapping."""
        disp_val = cell.get_display_value() if hasattr(cell, "get_display_value") else cell.value
        if disp_val is None or disp_val == "":
            return

        if cf_res and cf_res.data_bar and not cf_res.data_bar.get("show_value", True):
            return
        if cf_res and cf_res.icon and not cf_res.icon.get("show_value", True):
            return
        icon_w = 16 if (cf_res and cf_res.icon) else 0

        col_x = item_rect.x()
        row_y = item_rect.y()
        col_w = item_rect.width()
        row_h = item_rect.height()
        if col_w <= 1 or row_h <= 1:
            return

        eff_h = cell.get_effective_align_h()
        eff_v = cell.get_effective_align_v()
        indent_px = (cell.indent or 0) * 9

        if cell.rich_runs:
            text_w = int(math.ceil(self._measure_rich_runs_width(cell)))
            can_spill = (
                merge is None
                and not cell.wrap_text
                and not cell.shrink_to_fit
                and (cell.text_rotation or 0) == 0
                and eff_h in ("left", "general", "right", "center", "centerContinuous")
            )
            if can_spill:
                left_c, right_c = self.calculate_spill_bounds(
                    r,
                    c,
                    text_w,
                    col_w,
                    eff_h,
                    indent_px=indent_px,
                    min_col=pane_min_col,
                    max_col=pane_max_col,
                    merge_by_cell=merge_by_cell,
                )
                clip_l = self.row_header_width + self.geometry_mapper.col_pos(left_c) - psx
                clip_r = self.row_header_width + self.geometry_mapper.col_pos(right_c + 1) - psx
            else:
                clip_l = col_x
                clip_r = col_x + col_w
            clip_rect = QRect(clip_l, row_y, max(0, clip_r - clip_l - 1), max(0, row_h - 1))

            if eff_h in ("center", "centerContinuous") and can_spill:
                draw_w = max(col_w, text_w + 8)
                draw_x = int(round(col_x + col_w / 2.0 - draw_w / 2.0))
            elif eff_h == "right" and can_spill:
                draw_w = max(clip_r - clip_l, text_w + 8 + indent_px)
                draw_x = col_x + col_w - draw_w
            else:
                draw_x = col_x
                draw_w = clip_r - col_x

            self._paint_rich_cell(
                painter,
                cell,
                draw_x,
                row_y,
                draw_w,
                row_h,
                eff_h,
                eff_v,
                cf_res,
                clip_rect=clip_rect,
            )
            return

        font = self._cell_font(cell.font_family, cell.font_size)
        is_bold = cf_res.bold if (cf_res and cf_res.bold is not None) else cell.bold
        is_italic = cf_res.italic if (cf_res and cf_res.italic is not None) else cell.italic
        font.setBold(is_bold)
        font.setItalic(is_italic)
        font.setUnderline(cell.underline)
        cell_fm = self._fm(font)

        fmt_res = self._format_cell_for_paint(cell, disp_val, cell_fm, col_w)
        text = self._normalize_unwrapped_text(fmt_res.text, cell.wrap_text)
        if text != fmt_res.text:
            text_w = int(math.ceil(cell_fm.horizontalAdvance(text)))
        else:
            text_w = int(math.ceil(self._measure_formatted_width(fmt_res, cell_fm)))

        can_spill = (
            merge is None
            and not cell.wrap_text
            and not cell.shrink_to_fit
            and (cell.text_rotation or 0) == 0
            and not fmt_res.is_numeric
            and not fmt_res.has_fill
            and not fmt_res.is_error
            and eff_h in ("left", "general", "right", "center", "centerContinuous")
        )
        if can_spill:
            left_c, right_c = self.calculate_spill_bounds(
                r,
                c,
                text_w,
                col_w,
                eff_h,
                indent_px=indent_px,
                min_col=pane_min_col,
                max_col=pane_max_col,
                merge_by_cell=merge_by_cell,
            )
            clip_l = self.row_header_width + self.geometry_mapper.col_pos(left_c) - psx
            clip_r = self.row_header_width + self.geometry_mapper.col_pos(right_c + 1) - psx
        else:
            clip_l = col_x
            clip_r = col_x + col_w

        clip_rect = QRect(clip_l, row_y, max(0, clip_r - clip_l - 1), max(0, row_h - 1))

        painter.save()
        painter.setClipRect(clip_rect, Qt.ClipOperation.IntersectClip)
        painter.setFont(font)

        text_col_str = (
            cf_res.fg_color if (cf_res and cf_res.fg_color) else (fmt_res.color or cell.fg_color)
        )
        text_color = QColor(text_col_str) if text_col_str else Qt.GlobalColor.black
        painter.setPen(text_color)

        if eff_v == "top":
            v_flag = Qt.AlignmentFlag.AlignTop
        elif eff_v == "bottom" and row_h > 26:
            v_flag = Qt.AlignmentFlag.AlignBottom
        else:
            v_flag = Qt.AlignmentFlag.AlignVCenter

        if eff_h in ("center", "centerContinuous"):
            h_flag = Qt.AlignmentFlag.AlignHCenter
        elif eff_h == "right":
            h_flag = Qt.AlignmentFlag.AlignRight
        elif eff_h == "justify":
            h_flag = Qt.AlignmentFlag.AlignJustify
        else:
            h_flag = Qt.AlignmentFlag.AlignLeft

        align_flag = v_flag | h_flag
        if cell.wrap_text:
            align_flag |= Qt.TextFlag.TextWordWrap

        if can_spill and eff_h == "right":
            rect_r = col_x + col_w - 3 - indent_px
            rect_l = min(clip_l + 3, rect_r - text_w - 4)
            text_rect = QRect(rect_l, row_y, max(0, rect_r - rect_l), row_h)
        elif can_spill and eff_h in ("center", "centerContinuous"):
            half_w = max(col_w / 2.0, text_w / 2.0 + 4.0)
            cx = col_x + col_w / 2.0
            rect_l = int(round(cx - half_w)) + 3
            rect_w = max(0, int(round(half_w * 2.0)) - 6)
            text_rect = QRect(rect_l, row_y, rect_w, row_h)
        else:
            span_w = clip_r - col_x
            if eff_h in ("left", "general"):
                text_rect = QRect(
                    col_x + 3 + indent_px,
                    row_y,
                    max(0, span_w - 6 - indent_px),
                    row_h,
                )
            elif eff_h == "right":
                text_rect = QRect(
                    col_x + 3,
                    row_y,
                    max(0, span_w - 6 - indent_px),
                    row_h,
                )
            else:
                text_rect = QRect(col_x + 3, row_y, max(0, span_w - 6), row_h)
        if icon_w:
            # Keep the text clear of the icon drawn at the left edge.
            text_rect = text_rect.adjusted(min(icon_w, text_rect.width()), 0, 0, 0)

        has_pad_or_fill = fmt_res.has_fill or any(s.kind == "pad" for s in fmt_res.segments)
        if has_pad_or_fill and fmt_res.segments:
            self._paint_formatted_segments(
                painter,
                fmt_res.segments,
                cell_fm,
                text_rect,
                v_flag,
                eff_h,
            )
        elif (
            fmt_res.is_numeric
            and not fmt_res.is_error
            and not cell.wrap_text
            and not cell.shrink_to_fit
            and (cell.text_rotation or 0) == 0
            and cell_fm.horizontalAdvance(text) > text_rect.width()
            and text_rect.width() > 0
        ):
            tw_actual = max(1.0, cell_fm.horizontalAdvance(text))
            sx = text_rect.width() / tw_actual
            painter.save()
            painter.translate(text_rect.left(), 0.0)
            painter.scale(sx, 1.0)
            scaled_rect = QRectF(
                0.0,
                float(text_rect.top()),
                tw_actual + 1.0,
                float(text_rect.height()),
            )
            painter.drawText(scaled_rect, align_flag, text)
            painter.restore()
        else:
            painter.drawText(text_rect, align_flag, text)
        painter.restore()

    def _paint_offscreen_overflow(
        self,
        painter: QPainter,
        pr_start: int,
        pr_end: int,
        pc_start: int,
        pc_end: int,
        psx: int,
        psy: int,
        pane_min_col: int,
        pane_max_col: int,
        merge_by_cell: dict[tuple[int, int], tuple[int, int, int, int]],
    ) -> None:
        """Paint text spilling into the visible pane from cells outside [pc_start, pc_end]."""
        for r in range(pr_start, pr_end + 1):
            row_h = self.geometry_mapper.row_size(r)
            if row_h <= 0:
                continue
            row_y = self.col_header_height + self.geometry_mapper.row_pos(r) - psy

            # Left offscreen scan: nearest non-empty cell before pc_start
            if pc_start > pane_min_col:
                limit_l = max(pane_min_col, pc_start - 256)
                cc = pc_start - 1
                while cc >= limit_l:
                    if (r, cc) in merge_by_cell or self._is_merged_cell(r, cc):
                        break
                    cl = self.model.get_cell(r, cc)
                    val = cl.get_display_value() if cl is not None else None
                    if val is not None and val != "":
                        eff_h = cl.get_effective_align_h()
                        if (
                            not cl.wrap_text
                            and not cl.shrink_to_fit
                            and (cl.text_rotation or 0) == 0
                            and eff_h in ("left", "general", "center", "centerContinuous")
                        ):
                            col_x = self.row_header_width + self.geometry_mapper.col_pos(cc) - psx
                            col_w = self.geometry_mapper.col_size(cc)
                            if col_w > 0:
                                cf_res = self._cell_format_overlay(r, cc, cl)
                                self._paint_cell_item_text(
                                    painter,
                                    r,
                                    cc,
                                    cl,
                                    None,
                                    QRect(col_x, row_y, col_w, row_h),
                                    cf_res,
                                    psx,
                                    pane_min_col,
                                    pane_max_col,
                                    merge_by_cell,
                                )
                        break
                    cc -= 1

            # Right offscreen scan: nearest non-empty cell beyond pc_end
            if pc_end < pane_max_col:
                limit_r = min(pane_max_col, pc_end + 64)
                cc = pc_end + 1
                while cc <= limit_r:
                    if (r, cc) in merge_by_cell or self._is_merged_cell(r, cc):
                        break
                    cl = self.model.get_cell(r, cc)
                    val = cl.get_display_value() if cl is not None else None
                    if val is not None and val != "":
                        eff_h = cl.get_effective_align_h()
                        if (
                            not cl.wrap_text
                            and not cl.shrink_to_fit
                            and (cl.text_rotation or 0) == 0
                            and eff_h in ("right", "center")
                        ):
                            col_x = self.row_header_width + self.geometry_mapper.col_pos(cc) - psx
                            col_w = self.geometry_mapper.col_size(cc)
                            if col_w > 0:
                                cf_res = self._cell_format_overlay(r, cc, cl)
                                self._paint_cell_item_text(
                                    painter,
                                    r,
                                    cc,
                                    cl,
                                    None,
                                    QRect(col_x, row_y, col_w, row_h),
                                    cf_res,
                                    psx,
                                    pane_min_col,
                                    pane_max_col,
                                    merge_by_cell,
                                )
                        break
                    cc += 1

    def _paint_rich_cell(
        self,
        painter: QPainter,
        cell: CellData,
        col_x: int,
        row_y: int,
        span_w: int,
        row_h: int,
        eff_h: str,
        eff_v: str,
        cf_res: Any = None,
        clip_rect: QRect | None = None,
    ) -> None:
        """Render in-cell rich text runs with mixed fonts, colors, sub/superscript, and wrapping."""
        runs = cell.rich_runs or []
        if not runs:
            return

        painter.save()
        effective_clip = (
            clip_rect if clip_rect is not None else QRect(col_x, row_y, span_w - 1, row_h - 1)
        )
        painter.setClipRect(effective_clip, Qt.ClipOperation.IntersectClip)

        # Base font metrics for baseline calculation
        base_font = self._cell_font(cell.font_family or "Arial", cell.font_size or 10)
        base_font.setBold(cell.bold)
        base_font.setItalic(cell.italic)
        base_font.setUnderline(cell.underline)
        base_fm = self._fm(base_font)

        avail_w = max(0.0, float(span_w - 6))

        # 1. Break runs into lines (by explicit '\n' and wrapping if wrap_text)
        # Each item in line: (QFont, QColor, vert_align, text, width)
        lines: list[list[tuple[QFont, QColor, str | None, str, float]]] = []
        curr_line: list[tuple[QFont, QColor, str | None, str, float]] = []
        curr_line_w = 0.0

        for r in runs:
            fam = r.font_family or cell.font_family or "Arial"
            sz = r.font_size if r.font_size is not None else (cell.font_size or 10)
            vert = r.vert_align
            if vert in ("subscript", "superscript"):
                sz = max(1.0, sz * 0.7)

            rf = QFont(fam, int(sz) if isinstance(sz, int) else round(sz))
            if isinstance(sz, float):
                rf.setPointSizeF(sz * self._print_font_factor)

            bold = (
                r.bold
                if r.bold is not None
                else (cf_res.bold if (cf_res and cf_res.bold is not None) else cell.bold)
            )
            italic = (
                r.italic
                if r.italic is not None
                else (cf_res.italic if (cf_res and cf_res.italic is not None) else cell.italic)
            )
            under = r.underline if r.underline is not None else cell.underline
            strike = r.strike if r.strike is not None else cell.strike

            rf.setBold(bold)
            rf.setItalic(italic)
            rf.setUnderline(under)
            rf.setStrikeOut(strike)

            col_str = r.fg_color or (
                cf_res.fg_color if (cf_res and cf_res.fg_color) else cell.fg_color
            )
            rc = QColor(col_str) if col_str else Qt.GlobalColor.black

            rfm = self._fm(rf)

            run_text = self._normalize_unwrapped_text(r.text, cell.wrap_text)
            text_parts = run_text.split("\n")
            for idx, part in enumerate(text_parts):
                if idx > 0:
                    lines.append(curr_line)
                    curr_line = []
                    curr_line_w = 0.0

                if not part:
                    continue

                if cell.wrap_text and avail_w > 0:
                    words = part.split(" ")
                    for w_idx, word in enumerate(words):
                        token = (" " if w_idx > 0 else "") + word
                        token_w = rfm.horizontalAdvance(token)
                        if curr_line_w + token_w > avail_w and curr_line:
                            lines.append(curr_line)
                            curr_line = []
                            curr_line_w = 0.0
                            token = word
                            token_w = rfm.horizontalAdvance(token)

                        curr_line.append((rf, rc, vert, token, token_w))
                        curr_line_w += token_w
                else:
                    part_w = rfm.horizontalAdvance(part)
                    curr_line.append((rf, rc, vert, part, part_w))
                    curr_line_w += part_w

        if curr_line or not lines:
            lines.append(curr_line)

        # 2. Vertical layout & line heights
        line_height = max(14.0, base_fm.lineSpacing())
        total_block_h = len(lines) * line_height

        if eff_v == "top":
            start_y = row_y + 2.0
        elif eff_v == "bottom" and row_h > 26:
            start_y = row_y + row_h - total_block_h - 2.0
        else:
            start_y = row_y + max(2.0, (row_h - total_block_h) / 2.0)

        # 3. Render each line
        for l_idx, line in enumerate(lines):
            line_w = sum(item[4] for item in line)

            if eff_h in ("center", "centerContinuous"):
                curr_x = col_x + 3.0 + (avail_w - line_w) / 2.0
            elif eff_h == "right":
                curr_x = col_x + 3.0 + (avail_w - line_w)
            else:
                curr_x = col_x + 3.0

            line_baseline_y = start_y + l_idx * line_height + base_fm.ascent()

            for rf, rc, vert, run_txt, run_w in line:
                painter.setFont(rf)
                painter.setPen(rc)

                if vert == "subscript":
                    offset_y = base_fm.descent() * 0.85
                elif vert == "superscript":
                    offset_y = -base_fm.ascent() * 0.38
                else:
                    offset_y = 0.0

                pos = QPointF(curr_x, line_baseline_y + offset_y)
                painter.drawText(pos, run_txt)
                curr_x += run_w

        painter.restore()
