"""Printer page geometry shared by Quire, Ledger and Lectern.

Every module renders in *points*: the printer resolution is 72 dpi, so device units are
points and point-sized fonts need no compensation. Pages are
"full page" with zero printer margins: document margins are the only margins, so content is
neither shifted down-right nor clipped at the right/bottom edge.
"""

from __future__ import annotations

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter
from PySide6.QtPrintSupport import QPrinter

A4_PT = (595.276, 841.89)
LETTER_PT = (612.0, 792.0)


def page_size_for(width_pt: float, height_pt: float) -> tuple[QPageSize, QPageLayout.Orientation]:
    """Portrait-normalised page size plus orientation for a ``width × height`` page."""
    w, h = max(1.0, float(width_pt)), max(1.0, float(height_pt))
    landscape = w > h
    portrait = QSizeF(min(w, h), max(w, h))
    size = QPageSize(portrait, QPageSize.Unit.Point, "", QPageSize.SizeMatchPolicy.FuzzyMatch)
    orientation = (
        QPageLayout.Orientation.Landscape if landscape else QPageLayout.Orientation.Portrait
    )
    return size, orientation


def configure_page(printer: QPrinter, width_pt: float, height_pt: float) -> None:
    """Make the next page exactly ``width × height`` points with no hardware margins."""
    size, orientation = page_size_for(width_pt, height_pt)
    # Device units = points: every point-sized font (charts, shapes, cells, slides) then
    # resolves 1:1, and PDF / preview output stays vector.
    if printer.resolution() != 72:
        printer.setResolution(72)
    printer.setFullPage(True)
    layout = QPageLayout(size, orientation, QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Point)
    layout.setMode(QPageLayout.Mode.FullPageMode)
    if not printer.setPageLayout(layout):
        printer.setPageSize(size)
        printer.setPageOrientation(orientation)
        printer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Point)


def paper_size_pt(printer: QPrinter) -> tuple[float, float]:
    """Width and height (points) of the printer's current full page, orientation applied."""
    rect = printer.pageLayout().fullRect(QPageLayout.Unit.Point)
    return rect.width(), rect.height()


def begin_points_painter(printer: QPrinter) -> QPainter:
    """Painter on ``printer`` whose user space is points from the paper's top-left corner."""
    painter = QPainter(printer)
    scale = printer.resolution() / 72.0
    painter.scale(scale, scale)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    return painter


def print_font_scale(painter: QPainter) -> float:
    """Factor for ``QFont.setPointSizeF`` so N pt text measures N pt on a points painter.

    The device resolves point sizes at its own DPI and the painter scale is applied on top,
    so sizes must be divided by ``dpi / 72`` once.
    """
    device = painter.device()
    dpi = device.logicalDpiY() if device is not None else 72
    return 72.0 / dpi if dpi > 0 else 1.0


def new_page(printer: QPrinter, width_pt: float, height_pt: float) -> bool:
    """Start another page with its own size/orientation (sections, mixed slides)."""
    configure_page(printer, width_pt, height_pt)
    return printer.newPage()
