"""Render a worksheet onto a printer / PDF / preview using its Page Setup."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtPrintSupport import QPrinter

from atboffice.modules.spreadsheet.printing import header_footer
from atboffice.modules.spreadsheet.printing.layout import (
    HEADING_H,
    HEADING_W,
    PX_TO_PT,
    PrintLayout,
    PrintPage,
    paginate,
)
from atboffice.modules.spreadsheet.printing.setup import SheetPrintSetup
from atboffice.ui.printing.printer_setup import begin_points_painter, configure_page, new_page

# Cell point sizes are drawn in grid pixels (96 dpi); points -> grid px is 4/3.
CELL_FONT_FACTOR = 1.0 / PX_TO_PT


def _col_letters(c: int) -> str:
    out = ""
    c += 1
    while c:
        c, rem = divmod(c - 1, 26)
        out = chr(65 + rem) + out
    return out


def _segments(page: PrintPage) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    rows = ([page.repeat_rows] if page.repeat_rows else []) + [page.rows]
    cols = ([page.repeat_cols] if page.repeat_cols else []) + [page.cols]
    return rows, cols


def _span_px(geo: Any, span: tuple[int, int], is_row: bool) -> float:
    pos = geo.row_pos if is_row else geo.col_pos
    return float(pos(span[1] + 1) - pos(span[0]))


def block_size(geo: Any, page: PrintPage, scale: float, headings: bool) -> tuple[float, float]:
    """Printed size (points) of a page's cell block, titles and headings included."""
    rows, cols = _segments(page)
    w = sum(_span_px(geo, s, False) for s in cols) * scale
    h = sum(_span_px(geo, s, True) for s in rows) * scale
    if headings:
        w += HEADING_W * scale / PX_TO_PT
        h += HEADING_H * scale / PX_TO_PT
    return w, h


def _paint_headings(
    painter: QPainter,
    geo: Any,
    rows: list[tuple[int, int]],
    cols: list[tuple[int, int]],
    hw: float,
    hh: float,
) -> None:
    """Row numbers and column letters (grid-pixel units, painter already scaled)."""
    painter.save()
    pen = QPen(QColor("#808080"), 0)
    painter.setPen(pen)
    font = QFont("Arial")
    font.setPixelSize(11)
    painter.setFont(font)
    center = int(Qt.AlignmentFlag.AlignCenter)
    x = hw
    for c1, c2 in cols:
        for c in range(c1, c2 + 1):
            w = float(geo.col_size(c))
            if w <= 0:
                continue
            rect = QRectF(x, 0, w, hh)
            painter.fillRect(rect, QColor("#F0F0F0"))
            painter.drawRect(rect)
            painter.drawText(rect, center, _col_letters(c))
            x += w
    y = hh
    for r1, r2 in rows:
        for r in range(r1, r2 + 1):
            h = float(geo.row_size(r))
            if h <= 0:
                continue
            rect = QRectF(0, y, hw, h)
            painter.fillRect(rect, QColor("#F0F0F0"))
            painter.drawRect(rect)
            painter.drawText(rect, center, str(r + 1))
            y += h
    painter.restore()


def _paint_drawings(
    painter: QPainter,
    grid: Any,
    sheet: Any,
    rows: tuple[int, int],
    cols: tuple[int, int],
) -> None:
    """Charts, pictures and shapes overlapping this cell block (grid-pixel units)."""
    from atboffice.modules.spreadsheet.views.object_layer import object_to_rect

    layer = getattr(grid, "object_layer", None)
    if layer is None:
        return
    geo = sheet.geometry
    ox, oy = geo.col_pos(cols[0]), geo.row_pos(rows[0])
    block = QRect(0, 0, int(_span_px(geo, cols, False)), int(_span_px(geo, rows, True)))
    for obj in sorted(getattr(sheet, "drawings", []) or [], key=lambda o: o.z_index):
        if getattr(obj, "print_object", True) is False:
            continue
        rect = object_to_rect(obj, geo, 0, 0, 0, 0).translated(-ox, -oy)
        if not rect.intersects(block):
            continue
        painter.save()
        painter.setClipRect(block)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        layer._paint_object(painter, obj, rect)
        painter.restore()


def _paint_block(
    painter: QPainter,
    grid: Any,
    sheet: Any,
    page: PrintPage,
    setup: SheetPrintSetup,
) -> None:
    """Cells (+ titles, headings, drawings) of one page; painter in grid pixels."""
    geo = sheet.geometry
    rows, cols = _segments(page)
    hw = HEADING_W / PX_TO_PT if setup.headings else 0.0
    hh = HEADING_H / PX_TO_PT if setup.headings else 0.0
    if setup.headings:
        _paint_headings(painter, geo, rows, cols, hw, hh)
    y = hh
    for rs in rows:
        x = hw
        for cs in cols:
            painter.save()
            painter.translate(x, y)
            grid.paint_print_region(
                painter,
                rs[0],
                rs[1],
                cs[0],
                cs[1],
                gridlines=setup.gridlines,
                font_factor=CELL_FONT_FACTOR,
            )
            _paint_drawings(painter, grid, sheet, rs, cs)
            painter.restore()
            x += _span_px(geo, cs, False)
        y += _span_px(geo, rs, True)


def _paint_header_footer(
    painter: QPainter,
    setup: SheetPrintSetup,
    page_w: float,
    page_h: float,
    page_no: int,
    pages: int,
    sheet_name: str,
    file_name: str,
    file_path: str,
) -> None:
    m = setup.margins
    font = QFont("Arial")
    font.setPointSizeF(10.0)
    painter.save()
    painter.setFont(font)
    painter.setPen(QColor("#000000"))
    for text, top in ((setup.header, True), (setup.footer, False)):
        if not text:
            continue
        y = m["header"] if top else page_h - m["footer"] - 14.0
        rect = QRectF(m["left"], y, page_w - m["left"] - m["right"], 14.0)
        for section, align in zip(
            header_footer.split_sections(text),
            (
                Qt.AlignmentFlag.AlignLeft,
                Qt.AlignmentFlag.AlignHCenter,
                Qt.AlignmentFlag.AlignRight,
            ),
        ):
            if section:
                painter.drawText(
                    rect,
                    int(align | Qt.AlignmentFlag.AlignVCenter),
                    header_footer.expand(section, page_no, pages, sheet_name, file_name, file_path),
                )
    painter.restore()


def _paint_margin_guides(
    painter: QPainter, setup: SheetPrintSetup, page_w: float, page_h: float
) -> None:
    m = setup.margins
    painter.save()
    painter.setPen(QPen(QColor("#7F7F7F"), 0.5, Qt.PenStyle.DashLine))
    for x in (m["left"], page_w - m["right"]):
        painter.drawLine(QPointF(x, 0), QPointF(x, page_h))
    for y in (m["top"], page_h - m["bottom"], m["header"], page_h - m["footer"]):
        painter.drawLine(QPointF(0, y), QPointF(page_w, y))
    painter.restore()


def render_sheet(
    printer: QPrinter,
    grid: Any,
    sheet: Any,
    setup: SheetPrintSetup,
    file_name: str = "",
    file_path: str = "",
    show_margins: bool = False,
) -> PrintLayout:
    """Paint every page of ``sheet``; returns the computed layout.

    ``show_margins`` draws the Print Preview margin guides (never used for real output).
    """
    layout = paginate(sheet, setup)
    page_w, page_h = setup.paper_size()
    m = setup.margins
    first_no = setup.first_page_number or 1
    total = len(layout.pages)
    configure_page(printer, page_w, page_h)
    painter = begin_points_painter(printer)
    try:
        for i, page in enumerate(layout.pages):
            if i:
                new_page(printer, page_w, page_h)
            bw, bh = block_size(sheet.geometry, page, layout.scale, setup.headings)
            avail_w = page_w - m["left"] - m["right"]
            avail_h = page_h - m["top"] - m["bottom"]
            x = m["left"] + (max(0.0, avail_w - bw) / 2 if setup.center_h else 0.0)
            y = m["top"] + (max(0.0, avail_h - bh) / 2 if setup.center_v else 0.0)
            if setup.black_white:
                _paint_block_bw(
                    painter, grid, sheet, page, setup, layout.scale, QRectF(x, y, bw, bh)
                )
            else:
                painter.save()
                painter.translate(x, y)
                painter.scale(layout.scale, layout.scale)
                painter.setClipRect(QRectF(0, 0, bw / layout.scale, bh / layout.scale))
                _paint_block(painter, grid, sheet, page, setup)
                painter.restore()
            _paint_header_footer(
                painter,
                setup,
                page_w,
                page_h,
                first_no + i,
                first_no + total - 1,
                sheet.name,
                file_name,
                file_path,
            )
            if show_margins:
                _paint_margin_guides(painter, setup, page_w, page_h)
    finally:
        painter.end()
    return layout


def _paint_block_bw(
    painter: QPainter,
    grid: Any,
    sheet: Any,
    page: PrintPage,
    setup: SheetPrintSetup,
    scale: float,
    target: QRectF,
) -> None:
    """Black & white: rasterise at ~200 dpi, threshold to pure black and white."""
    dpi = 200.0
    px_w = max(1, int(target.width() * dpi / 72.0))
    px_h = max(1, int(target.height() * dpi / 72.0))
    img = QImage(px_w, px_h, QImage.Format.Format_ARGB32)
    img.fill(QColor("#FFFFFF"))
    # Logical DPI 72 like the printer, so point fonts resolve 1:1; the painter scale
    # supersamples to ~200 dpi.
    dpm = int(round(72.0 / 0.0254))
    img.setDotsPerMeterX(dpm)
    img.setDotsPerMeterY(dpm)
    ip = QPainter(img)
    ip.scale(dpi / 72.0, dpi / 72.0)
    ip.scale(scale, scale)
    _paint_block(ip, grid, sheet, page, setup)
    ip.end()
    mono = img.convertToFormat(QImage.Format.Format_Mono, Qt.ImageConversionFlag.ThresholdDither)
    painter.drawImage(target, mono.convertToFormat(QImage.Format.Format_RGB32))
