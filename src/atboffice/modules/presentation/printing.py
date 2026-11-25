"""Lectern printing: Slides, Handouts (1/2/3/4/6/9), Notes Pages and Outline View."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtPrintSupport import QPrinter

from atboffice.core.i18n import safe_tr
from atboffice.ui.printing.printer_setup import (
    A4_PT,
    begin_points_painter,
    configure_page,
    new_page,
    print_font_scale,
)

PRINT_WHAT = ("slides", "handouts", "notes", "outline")
HANDOUT_COUNTS = (1, 2, 3, 4, 6, 9)
COLOR_MODES = ("color", "grayscale", "bw")

# per-page -> (columns, rows)
HANDOUT_GRID = {1: (1, 1), 2: (1, 2), 3: (1, 3), 4: (2, 2), 6: (2, 3), 9: (3, 3)}

MARGIN = 36.0
HEADER_H = 22.0
FOOTER_H = 22.0


@dataclass
class PresentationPrintOptions:
    what: str = "slides"
    per_page: int = 6
    color: str = "color"
    frame_slides: bool = False
    print_hidden: bool = False
    order: str = "horizontal"  # handouts: "horizontal" (rows first) or "vertical"
    title: str = ""


def printable_slides(pres: Any, options: PresentationPrintOptions) -> list[tuple[int, Any]]:
    """(index, slide) pairs to print; hidden slides only with "Print hidden slides"."""
    return [
        (i, s)
        for i, s in enumerate(pres.slides)
        if options.print_hidden or not getattr(s, "hidden", False)
    ]


def page_size(pres: Any, options: PresentationPrintOptions) -> tuple[float, float]:
    """Slides print at the presentation's own size and orientation; the rest on A4."""
    if options.what == "slides":
        return float(pres.w or 960.0), float(pres.h or 540.0)
    return A4_PT


def page_count(pres: Any, options: PresentationPrintOptions) -> int:
    n = len(printable_slides(pres, options))
    if options.what == "handouts":
        per = options.per_page if options.per_page in HANDOUT_GRID else 6
        return (n + per - 1) // per
    if options.what == "outline":
        return max(1, len(_outline_pages(pres, options)))
    return n


# ---------------------------------------------------------------------------- slide paint
def _to_print_color(img: QImage, mode: str) -> QImage:
    if mode == "grayscale":
        return img.convertToFormat(QImage.Format.Format_Grayscale8)
    if mode == "bw":
        mono = img.convertToFormat(
            QImage.Format.Format_Mono, Qt.ImageConversionFlag.ThresholdDither
        )
        return mono.convertToFormat(QImage.Format.Format_RGB32)
    return img


def paint_slide(
    painter: QPainter,
    slide: Any,
    pres: Any,
    rect: QRectF,
    color: str = "color",
    frame: bool = False,
) -> None:
    """Paint ``slide`` (with its design background and master) into ``rect``."""
    from atboffice.modules.presentation.views.slide_canvas import SlideScene

    w = float(pres.w or 960.0)
    h = float(pres.h or 540.0)
    scene = SlideScene(slide=slide, presentation=pres)
    scene.show_placeholder_prompts = False
    source = QRectF(0.0, 0.0, w, h)
    try:
        if color == "color":
            painter.save()
            painter.setClipRect(rect)
            scene.render(painter, rect, source, Qt.AspectRatioMode.IgnoreAspectRatio)
            painter.restore()
        else:
            # Grayscale / pure B&W: rasterise at ~200 dpi, convert, place.
            px_w = max(64, int(rect.width() * 200.0 / 72.0))
            px_h = max(36, int(rect.height() * 200.0 / 72.0))
            img = QImage(px_w, px_h, QImage.Format.Format_ARGB32)
            img.fill(QColor("#FFFFFF"))
            ip = QPainter(img)
            ip.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            ip.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            scene.render(ip, QRectF(0, 0, px_w, px_h), source)
            ip.end()
            painter.drawImage(rect, _to_print_color(img, color))
    finally:
        scene.clear()
        scene.deleteLater()
    if frame:
        painter.save()
        painter.setPen(QPen(QColor("#000000"), 0.75))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        painter.restore()


def _fit(rect: QRectF, aspect: float) -> QRectF:
    """Largest rect of ``aspect`` (w/h) centred in ``rect``."""
    w = rect.width()
    h = w / aspect
    if h > rect.height():
        h = rect.height()
        w = h * aspect
    return QRectF(rect.x() + (rect.width() - w) / 2, rect.y() + (rect.height() - h) / 2, w, h)


def _font(painter: QPainter, size: float, bold: bool = False) -> QFont:
    f = QFont("Arial")
    f.setPointSizeF(size * print_font_scale(painter))
    f.setBold(bold)
    return f


def _header_footer(
    painter: QPainter, page_w: float, page_h: float, title: str, page_no: int
) -> None:
    painter.save()
    painter.setFont(_font(painter, 9))
    painter.setPen(QColor("#555555"))
    if title:
        painter.drawText(
            QRectF(MARGIN, 10.0, page_w - 2 * MARGIN, HEADER_H),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            title,
        )
    painter.drawText(
        QRectF(MARGIN, page_h - FOOTER_H - 8.0, page_w - 2 * MARGIN, FOOTER_H),
        int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
        str(page_no),
    )
    painter.restore()


# ---------------------------------------------------------------------------- layouts
def handout_slots(
    page_w: float, page_h: float, per_page: int, aspect: float, order: str = "horizontal"
) -> list[QRectF]:
    """Slide rectangles of a handout page, in reading order."""
    cols, rows = HANDOUT_GRID.get(per_page, (2, 3))
    body = QRectF(
        MARGIN, MARGIN + HEADER_H, page_w - 2 * MARGIN, page_h - 2 * MARGIN - HEADER_H - FOOTER_H
    )
    if per_page == 3:
        # Slides on the left half, note lines on the right
        body = QRectF(body.x(), body.y(), body.width() * 0.5, body.height())
    gap = 18.0
    cell_w = (body.width() - gap * (cols - 1)) / cols
    cell_h = (body.height() - gap * (rows - 1)) / rows
    cells = []
    for r in range(rows):
        for c in range(cols):
            cells.append((r, c))
    if order == "vertical":
        cells.sort(key=lambda rc: (rc[1], rc[0]))
    return [
        _fit(
            QRectF(body.x() + c * (cell_w + gap), body.y() + r * (cell_h + gap), cell_w, cell_h),
            aspect,
        )
        for r, c in cells
    ]


def _paint_note_lines(painter: QPainter, slot: QRectF, page_w: float) -> None:
    x1 = slot.right() + 24.0
    x2 = page_w - MARGIN
    painter.save()
    painter.setPen(QPen(QColor("#999999"), 0.5))
    step = slot.height() / 6.0
    for i in range(1, 6):
        y = slot.y() + i * step
        painter.drawLine(QPointF(x1, y), QPointF(x2, y))
    painter.restore()


def _outline_lines(pres: Any, options: PresentationPrintOptions) -> list[tuple[int, str, bool]]:
    """(indent level, text, is_title) for every printable slide."""
    from atboffice.modules.presentation.tools.outline_ops import BODY_TYPES, TITLE_TYPES

    out: list[tuple[int, str, bool]] = []
    for idx, slide in printable_slides(pres, options):
        title = ""
        bodies: list[tuple[int, str]] = []
        for sh in slide.shapes:
            ph = getattr(sh, "placeholder", None)
            text = getattr(sh, "text", None)
            if ph is None or text is None:
                continue
            if ph.type in TITLE_TYPES:
                title = " ".join(text.plain_text.split())
            elif ph.type in BODY_TYPES:
                bodies.extend((p.level, p.plain_text) for p in text.paragraphs if p.plain_text)
        out.append((0, f"{idx + 1}  {title or safe_tr('(无标题)')}", True))
        out.extend((lvl + 1, line, False) for lvl, line in bodies)
    return out


def _outline_pages(
    pres: Any, options: PresentationPrintOptions
) -> list[list[tuple[int, str, bool, float]]]:
    """Lines (with y positions) split into A4 pages."""
    _page_w, page_h = A4_PT
    top = MARGIN + HEADER_H
    bottom = page_h - MARGIN - FOOTER_H
    pages: list[list[tuple[int, str, bool, float]]] = [[]]
    y = top
    for level, text, is_title in _outline_lines(pres, options):
        line_h = 20.0 if is_title else 16.0
        if is_title and pages[-1]:
            y += 6.0
        if y + line_h > bottom and pages[-1]:
            pages.append([])
            y = top
        pages[-1].append((level, text, is_title, y))
        y += line_h
    return pages


# ---------------------------------------------------------------------------- entry
def render_presentation(printer: QPrinter, pres: Any, options: PresentationPrintOptions) -> int:
    """Paint every page; returns the number of pages produced."""
    slides = printable_slides(pres, options)
    if not slides:
        return 0
    page_w, page_h = page_size(pres, options)
    aspect = float(pres.w or 960.0) / float(pres.h or 540.0)
    configure_page(printer, page_w, page_h)
    painter = begin_points_painter(printer)
    pages = 0
    try:

        def start() -> None:
            nonlocal pages
            if pages:
                new_page(printer, page_w, page_h)
            pages += 1

        if options.what == "slides":
            for _idx, slide in slides:
                start()
                paint_slide(
                    painter,
                    slide,
                    pres,
                    QRectF(0, 0, page_w, page_h),
                    options.color,
                    options.frame_slides,
                )
        elif options.what == "handouts":
            per = options.per_page if options.per_page in HANDOUT_GRID else 6
            total = (len(slides) + per - 1) // per
            for p in range(total):
                start()
                _header_footer(painter, page_w, page_h, options.title, p + 1)
                slots = handout_slots(page_w, page_h, per, aspect, options.order)
                for slot, (_idx, slide) in zip(slots, slides[p * per : (p + 1) * per]):
                    # Handouts always frame slides (PowerPoint draws a border)
                    paint_slide(painter, slide, pres, slot, options.color, True)
                    if per == 3:
                        _paint_note_lines(painter, slot, page_w)
        elif options.what == "notes":
            for idx, slide in slides:
                start()
                _header_footer(painter, page_w, page_h, options.title, idx + 1)
                top = QRectF(
                    MARGIN + 36,
                    MARGIN + HEADER_H,
                    page_w - 2 * MARGIN - 72,
                    (page_h - 2 * MARGIN) * 0.42,
                )
                paint_slide(painter, slide, pres, _fit(top, aspect), options.color, True)
                notes_rect = QRectF(
                    MARGIN + 36,
                    top.bottom() + 24.0,
                    page_w - 2 * MARGIN - 72,
                    page_h - top.bottom() - 24.0 - MARGIN - FOOTER_H,
                )
                painter.save()
                painter.setFont(_font(painter, 12))
                painter.setPen(QColor("#000000"))
                painter.drawText(
                    notes_rect,
                    int(
                        Qt.AlignmentFlag.AlignLeft
                        | Qt.AlignmentFlag.AlignTop
                        | Qt.TextFlag.TextWordWrap
                    ),
                    getattr(slide, "notes", "") or "",
                )
                painter.restore()
        elif options.what == "outline":
            outline = _outline_pages(pres, options)
            for p, lines in enumerate(outline):
                start()
                _header_footer(painter, page_w, page_h, options.title, p + 1)
                for level, text, is_title, y in lines:
                    painter.setFont(_font(painter, 13 if is_title else 11, bold=is_title))
                    painter.setPen(QColor("#000000"))
                    x = MARGIN + 18.0 * level
                    painter.drawText(
                        QRectF(x, y, page_w - MARGIN - x, 20.0),
                        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                        ("• " if not is_title else "") + text,
                    )
        else:
            raise ValueError(f"unknown print layout {options.what!r}")
    finally:
        painter.end()
    return pages
