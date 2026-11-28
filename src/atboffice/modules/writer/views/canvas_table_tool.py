"""Quire interactive Draw Table pen and Eraser canvas tool controller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen

from atboffice.core.i18n import safe_tr
from atboffice.modules.writer.models.document import info, reindex
from atboffice.modules.writer.models.table import (
    create_simple_table,
    merge_cells,
    split_cell_at_x,
    split_cell_rows,
    table_map,
)
from atboffice.modules.writer.views.caret_controller import DocPos, Selection
from atboffice.ui.styles.luna_2003 import theme_tokens

if TYPE_CHECKING:
    from atboffice.modules.writer.views.canvas_view import WriterCanvasView

_MIN_DRAG_PT = 4.0


def set_table_tool(canvas: WriterCanvasView, kind: str | None) -> None:
    """Switch active table tool (``'draw'``, ``'erase'``, or ``None``) and reset active drags."""
    if kind not in (None, "draw", "erase"):
        kind = None
    canvas._is_dragging = False
    canvas._resizing_table = False
    canvas._resize_info = None
    canvas._resize_guide_pos = None
    canvas._float_drag = None
    canvas._table_draw_start = None
    canvas._table_draw_current = None
    canvas._table_draw_start_cell = None

    changed = canvas._table_tool != kind
    canvas._table_tool = kind

    if kind == "draw":
        canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
    elif kind == "erase":
        canvas.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
    else:
        canvas.viewport().setCursor(Qt.CursorShape.IBeamCursor)

    if changed:
        canvas.table_tool_changed.emit(kind)
    canvas.viewport().update()


def _iter_table_layouts(canvas: WriterCanvasView):
    """Yield ``(page_idx, page, frag_x_pt, frag_y_pt, tl, rect_vp)`` per rendered table slice."""
    if not canvas.pagination or not canvas.pagination.pages:
        return
    scroll_x = canvas.horizontalScrollBar().value()
    scroll_y = canvas.verticalScrollBar().value()

    for p_idx, page in enumerate(canvas.pagination.pages):
        page_rect = canvas.page_rect_canvas(p_idx)
        page_vp_left = page_rect.left() - scroll_x
        page_vp_top = page_rect.top() - scroll_y

        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    tl = frag.table_layout
                    if tl is None:
                        continue
                    frag_x = page.body_left + col.left
                    frag_y = page.body_top + col.top + frag.top
                    tbl_rect_vp = QRectF(
                        page_vp_left + canvas.pt_to_px(frag_x + tl.x),
                        page_vp_top + canvas.pt_to_px(frag_y + tl.y),
                        canvas.pt_to_px(tl.width),
                        canvas.pt_to_px(tl.height),
                    )
                    yield p_idx, page, page_vp_left, page_vp_top, frag_x, frag_y, tl, tbl_rect_vp


def hit_test_table_cell(
    canvas: WriterCanvasView, vp_pt: QPoint, tol_px: float = 0.0
) -> dict[str, Any] | None:
    """Return layout & model metadata for the table cell at viewport coordinate ``vp_pt``."""
    pt_f = QPointF(float(vp_pt.x()), float(vp_pt.y()))
    for (
        p_idx,
        _page,
        page_vp_left,
        page_vp_top,
        frag_x,
        frag_y,
        tl,
        _tbl_rect,
    ) in _iter_table_layouts(canvas):
        for rl in tl.rows:
            for cell_idx, cl in enumerate(rl.cells):
                rect_vp = QRectF(
                    page_vp_left + canvas.pt_to_px(frag_x + cl.x),
                    page_vp_top + canvas.pt_to_px(frag_y + cl.y),
                    canvas.pt_to_px(cl.width),
                    canvas.pt_to_px(cl.height),
                )
                hit_rect = rect_vp.adjusted(-tol_px, -tol_px, tol_px, tol_px)
                if hit_rect.contains(pt_f):
                    m = table_map(tl.table)
                    row_entries = m[rl.row_idx]
                    entry = next((e for e in row_entries if e.cell is cl.cell), None)
                    if entry is None:
                        entry = next((e for e in row_entries if e.col_idx == cl.col_idx), None)
                    live_cell = entry.cell if entry is not None else cl.cell
                    actual_cell_idx = tl.table.rows[rl.row_idx].cells.index(live_cell)
                    return {
                        "page_idx": p_idx,
                        "table": tl.table,
                        "table_layout": tl,
                        "row_idx": rl.row_idx,
                        "cell_idx": actual_cell_idx,
                        "layout_cell_idx": cell_idx,
                        "cell": live_cell,
                        "col_idx": entry.col_idx if entry else cl.col_idx,
                        "span": entry.span if entry else 1,
                        "rowspan": entry.rowspan if entry else 1,
                        "rect_vp": rect_vp,
                    }
    return None


def hit_test_internal_border(
    canvas: WriterCanvasView, vp_pt: QPoint, tol_px: float = 10.0
) -> dict[str, Any] | None:
    """Detect an internal border between two visible adjacent cells within ``tol_px``."""
    cell_hit = hit_test_table_cell(canvas, vp_pt, tol_px=tol_px)
    if cell_hit is None:
        return None

    rect: QRectF = cell_hit["rect_vp"]
    dists = {
        "left": abs(vp_pt.x() - rect.left()),
        "right": abs(rect.right() - vp_pt.x()),
        "top": abs(vp_pt.y() - rect.top()),
        "bottom": abs(rect.bottom() - vp_pt.y()),
    }
    side = min(dists, key=lambda k: dists[k])
    if dists[side] > tol_px:
        return None

    table = cell_hit["table"]
    ri = cell_hit["row_idx"]
    c0 = cell_hit["col_idx"]
    span = cell_hit["span"]
    rowspan = cell_hit["rowspan"]
    m = table_map(table)

    other = None
    if side in ("left", "right"):
        adj_col = c0 - 1 if side == "left" else c0 + span
        if adj_col < 0 or adj_col >= len(table.grid):
            return None
        other = next((e for e in m[ri] if e.col_idx <= adj_col < e.col_idx + e.span), None)
        if other is None or other.is_hidden:
            return None
        r0 = min(ri, other.row_idx)
        r1 = max(ri + rowspan - 1, other.row_idx + other.rowspan - 1)
        col_a = min(c0, other.col_idx)
        col_b = max(c0 + span - 1, other.col_idx + other.span - 1)
        return {"table": table, "r0": r0, "r1": r1, "c0": col_a, "c1": col_b, "side": side}

    adj_row = ri - 1 if side == "top" else ri + rowspan
    if adj_row < 0 or adj_row >= len(m):
        return None
    if side == "top":
        # Walk up if adj_row is a hidden continuation of a restart cell above
        other = next(
            (
                e
                for r_probe in range(adj_row, -1, -1)
                for e in m[r_probe]
                if not e.is_hidden
                and e.col_idx == c0
                and e.span == span
                and r_probe + e.rowspan - 1 == adj_row
            ),
            None,
        )
    else:
        other = next(
            (e for e in m[adj_row] if not e.is_hidden and e.col_idx == c0 and e.span == span),
            None,
        )
    if other is None:
        return None
    r0 = min(ri, other.row_idx)
    r1 = max(ri + rowspan - 1, other.row_idx + other.rowspan - 1)
    return {"table": table, "r0": r0, "r1": r1, "c0": c0, "c1": c0 + span - 1, "side": side}


def handle_table_tool_press(canvas: WriterCanvasView, event: QMouseEvent) -> bool:
    """Handle LeftButton press when ``canvas.table_tool`` is ``'draw'`` or ``'erase'``."""
    tool = canvas.table_tool
    if tool is None or event.button() != Qt.MouseButton.LeftButton:
        return False

    vp_pt = canvas._event_pos(event)
    canvas.setFocus()

    if tool == "erase":
        hit = hit_test_internal_border(canvas, vp_pt, tol_px=10.0)
        if hit is not None:
            tbl = hit["table"]
            r0, r1, c0, c1 = hit["r0"], hit["r1"], hit["c0"], hit["c1"]
            canvas.run_undoable(lambda: merge_cells(tbl, r0, r1, c0, c1), safe_tr("擦除表格线"))
        return True

    # Draw pencil press: start drag tracking
    canvas._table_draw_start = vp_pt
    canvas._table_draw_current = vp_pt
    canvas._table_draw_start_cell = hit_test_table_cell(canvas, vp_pt, tol_px=0.0)
    canvas.viewport().update()
    return True


def handle_table_tool_move(canvas: WriterCanvasView, event: QMouseEvent) -> bool:
    """Update dashed preview while dragging in Draw mode or keep tool cursor active."""
    tool = canvas.table_tool
    if tool is None:
        return False

    if tool == "draw" and canvas._table_draw_start is not None:
        canvas._table_draw_current = canvas._event_pos(event)
        canvas.viewport().update()
        return True

    if tool == "draw":
        canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
    else:
        canvas.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
    return True


def handle_table_tool_release(canvas: WriterCanvasView, event: QMouseEvent) -> bool:
    """Commit drawn 1x1 table or horizontal/vertical cell split on LeftButton release."""
    tool = canvas.table_tool
    if tool is None or event.button() != Qt.MouseButton.LeftButton:
        return False

    if tool == "erase":
        return True

    start_vp = canvas._table_draw_start
    end_vp = canvas._event_pos(event)
    start_cell = canvas._table_draw_start_cell
    canvas._table_draw_start = None
    canvas._table_draw_current = None
    canvas._table_draw_start_cell = None
    canvas.viewport().update()

    if start_vp is None:
        return True

    dx_pt = canvas.px_to_pt(abs(end_vp.x() - start_vp.x()))
    dy_pt = canvas.px_to_pt(abs(end_vp.y() - start_vp.y()))
    if dx_pt < _MIN_DRAG_PT and dy_pt < _MIN_DRAG_PT:
        return True

    if start_cell is not None:
        tbl = start_cell["table"]
        cell = start_cell["cell"]
        row_idx = start_cell["row_idx"]
        cell_idx = start_cell["cell_idx"]
        c0 = start_cell["col_idx"]
        span = start_cell["span"]
        rect_vp: QRectF = start_cell["rect_vp"]

        if dx_pt > dy_pt:
            canvas.run_undoable(
                lambda: split_cell_rows(tbl, cell, num_rows=2), safe_tr("绘制表格线")
            )
        else:
            mid_x_vp = (min(start_vp.x(), end_vp.x()) + max(start_vp.x(), end_vp.x())) / 2.0
            rel = (mid_x_vp - rect_vp.left()) / max(1.0, rect_vp.width())
            frac = max(0.1, min(0.9, rel))
            xs = [0.0]
            for w in tbl.grid:
                xs.append(xs[-1] + w)
            x_left = xs[min(c0, len(xs) - 1)]
            x_right = xs[min(c0 + span, len(xs) - 1)]
            cut_pt = x_left + (x_right - x_left) * frac
            canvas.run_undoable(
                lambda: split_cell_at_x(tbl, row_idx, cell_idx, cut_pt),
                safe_tr("绘制表格线"),
            )
        return True

    # Drag started outside any table: insert 1x1 table at start DocPos with drawn size.
    page_idx, pt_doc = canvas.viewport_to_doc_coords(start_vp)
    page = (
        canvas.pagination.pages[max(0, min(page_idx, len(canvas.pagination.pages) - 1))]
        if canvas.pagination and canvas.pagination.pages
        else None
    )
    body_w = float(page.body_width) if page is not None else 468.0
    target_w = max(18.0, min(round(dx_pt, 2), body_w))
    pos = canvas.controller.canvas_to_pos(page_idx, pt_doc)
    canvas.controller.set_pos(pos, extend_selection=False)

    def _insert_drawn_table() -> bool:
        tbl = create_simple_table(1, 1, width=target_w)
        if dy_pt >= 14.0:
            tbl.rows[0].tr_pr.h = round(dy_pt, 2)
            tbl.rows[0].tr_pr.h_rule = "atLeast"
        inf = info(canvas.doc, canvas.controller.pos.para_id)
        story = inf["story"] if inf and "story" in inf else canvas.doc.main
        curr_p = canvas.controller._paragraph_by_id(canvas.controller.pos.para_id)
        idx = story.blocks.index(curr_p) if curr_p in story.blocks else len(story.blocks)
        story.blocks.insert(idx + 1, tbl)
        reindex(canvas.doc)
        first_p = tbl.rows[0].cells[0].blocks[0]
        canvas.controller.pos = DocPos(first_p.id, 0)
        canvas.controller.selection = Selection(canvas.controller.pos, canvas.controller.pos)
        return True

    canvas.run_undoable(_insert_drawn_table, safe_tr("绘制表格"))
    return True


def handle_table_tool_key_press(canvas: WriterCanvasView, event: QKeyEvent) -> bool:
    """Exit active table tool when user presses Escape."""
    if canvas.table_tool is None:
        return False
    if event.key() == Qt.Key.Key_Escape:
        set_table_tool(canvas, None)
        event.accept()
        return True
    return False


def paint_table_tool_overlay(canvas: WriterCanvasView, painter: QPainter) -> None:
    """Paint dashed preview box or split line while dragging with the Draw Table pencil."""
    if canvas.table_tool != "draw":
        return
    start_vp = getattr(canvas, "_table_draw_start", None)
    cur_vp = getattr(canvas, "_table_draw_current", None)
    if start_vp is None or cur_vp is None:
        return

    tok = theme_tokens()
    accent = QColor(tok.hot_border)
    pen = QPen(accent, 1.5, Qt.PenStyle.DashLine)
    painter.save()
    painter.setPen(pen)

    start_cell = getattr(canvas, "_table_draw_start_cell", None)
    x0, y0 = float(start_vp.x()), float(start_vp.y())
    x1, y1 = float(cur_vp.x()), float(cur_vp.y())
    if start_cell is not None:
        rect: QRectF = start_cell["rect_vp"]
        if abs(x1 - x0) > abs(y1 - y0):
            ym = max(rect.top(), min(rect.bottom(), (y0 + y1) / 2.0))
            painter.drawLine(QPointF(rect.left(), ym), QPointF(rect.right(), ym))
        else:
            xm = max(rect.left(), min(rect.right(), (x0 + x1) / 2.0))
            painter.drawLine(QPointF(xm, rect.top()), QPointF(xm, rect.bottom()))
    else:
        left = min(x0, x1)
        top = min(y0, y1)
        w = max(4.0, abs(x1 - x0))
        h = max(4.0, abs(y1 - y0))
        fill = QColor(accent)
        fill.setAlpha(28)
        painter.fillRect(QRectF(left, top, w, h), fill)
        painter.drawRect(QRectF(left, top, w, h))
    painter.restore()
