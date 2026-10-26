"""Common types, conversion helpers, and styling constants for Quire rulers."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import QCoreApplication, QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("QuireRuler", text)


class RulerUnit(StrEnum):
    """Supported ruler measurement units."""

    CM = "cm"
    INCH = "inch"
    PT = "pt"


class TabKind(StrEnum):
    """Tab stop and ruler drag selector kinds."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    DECIMAL = "decimal"
    BAR = "bar"
    FIRST_LINE = "firstLine"
    HANGING = "hanging"


TAB_KINDS: list[tuple[TabKind, str]] = [
    (TabKind.LEFT, "Left Tab"),
    (TabKind.CENTER, "Center Tab"),
    (TabKind.RIGHT, "Right Tab"),
    (TabKind.DECIMAL, "Decimal Tab"),
    (TabKind.BAR, "Bar Tab"),
    (TabKind.FIRST_LINE, "First Line Indent"),
    (TabKind.HANGING, "Hanging Indent"),
]

# Physical measurement conversion factors
PT_PER_INCH: float = 72.0
PT_PER_CM: float = 28.3465  # 72.0 / 2.54
PT_PER_MM: float = 2.83465

# Classic Word 2003 visual styling constants
COLOR_RULER_BG_PAGE = QColor(255, 255, 255)  # Pure white active text body
COLOR_RULER_BG_MARGIN = QColor(201, 214, 238)  # Classic Word 2003 soft blue-gray margin
COLOR_RULER_BORDER = QColor(140, 140, 140)  # Ruler frame outline
COLOR_RULER_TICK = QColor(68, 68, 68)  # Tick marks
COLOR_RULER_TEXT = QColor(34, 34, 34)  # Numeric labels
COLOR_MARKER_FILL = QColor(245, 245, 245)  # Marker fill
COLOR_MARKER_BORDER = QColor(40, 40, 40)  # Marker border
COLOR_MARKER_HIGHLIGHT = QColor(0, 102, 204)  # Active dragged marker
COLOR_DEFTAB_TICK = QColor(119, 119, 119)  # Subtle default tab tick


def pt_to_unit(pt: float, unit: RulerUnit | str) -> float:
    """Convert points to the specified ruler unit."""
    u = str(unit).lower()
    if u in ("cm", "rulerunit.cm"):
        return pt / PT_PER_CM
    if u in ("in", "inch", "rulerunit.inch"):
        return pt / PT_PER_INCH
    return pt


def unit_to_pt(val: float, unit: RulerUnit | str) -> float:
    """Convert a value in ruler units to points."""
    u = str(unit).lower()
    if u in ("cm", "rulerunit.cm"):
        return val * PT_PER_CM
    if u in ("in", "inch", "rulerunit.inch"):
        return val * PT_PER_INCH
    return val


def snap_to_grid(pt: float, unit: RulerUnit | str, disable_snap: bool = False) -> float:
    """Snap point value to nearest ruler sub-grid interval, or round to 0.1 pt if disabled."""
    if disable_snap:
        return round(pt, 2)
    u = str(unit).lower()
    if u in ("cm", "rulerunit.cm"):
        step = PT_PER_MM * 2.5  # 2.5 mm step
    else:
        step = 4.5  # 1/16 inch (4.5 pt)
    return round(pt / step) * step


def draw_tab_glyph(
    painter: QPainter, kind: TabKind | str, center: QPointF, size: float = 9.0
) -> None:
    """Draw a vector glyph for a tab stop or indent selector."""
    k = TabKind(kind) if isinstance(kind, str) and kind in TabKind._value2member_map_ else kind
    cx = center.x()
    cy = center.y()
    half = size / 2.0

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(COLOR_RULER_TEXT, 1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if k == TabKind.LEFT:
        # L shape: vertical line down, horizontal line right
        path = QPainterPath()
        path.moveTo(cx - 2.5, cy - half)
        path.lineTo(cx - 2.5, cy + half - 1)
        path.lineTo(cx + half, cy + half - 1)
        painter.drawPath(path)

    elif k == TabKind.CENTER:
        # Inverted T: vertical line down, horizontal base
        path = QPainterPath()
        path.moveTo(cx, cy - half)
        path.lineTo(cx, cy + half - 1)
        path.moveTo(cx - half, cy + half - 1)
        path.lineTo(cx + half, cy + half - 1)
        painter.drawPath(path)

    elif k == TabKind.RIGHT:
        # Reversed L: vertical line down, horizontal line left
        path = QPainterPath()
        path.moveTo(cx + 2.5, cy - half)
        path.lineTo(cx + 2.5, cy + half - 1)
        path.lineTo(cx - half, cy + half - 1)
        painter.drawPath(path)

    elif k == TabKind.DECIMAL:
        # Inverted T with decimal dot on the right
        path = QPainterPath()
        path.moveTo(cx - 1, cy - half)
        path.lineTo(cx - 1, cy + half - 1)
        path.moveTo(cx - half, cy + half - 1)
        path.lineTo(cx + half - 1, cy + half - 1)
        painter.drawPath(path)
        painter.setBrush(QBrush(COLOR_RULER_TEXT))
        painter.drawEllipse(QPointF(cx + 2.5, cy + 1), 1.2, 1.2)

    elif k == TabKind.BAR:
        # Vertical bar
        painter.drawLine(QPointF(cx, cy - half), QPointF(cx, cy + half))

    elif k == TabKind.FIRST_LINE:
        # Downward pointing triangle
        path = QPainterPath()
        path.moveTo(cx - half, cy - half)
        path.lineTo(cx + half, cy - half)
        path.lineTo(cx, cy + half - 1)
        path.closeSubpath()
        painter.setBrush(QBrush(COLOR_MARKER_FILL))
        painter.drawPath(path)

    elif k == TabKind.HANGING:
        # Upward pointing triangle
        path = QPainterPath()
        path.moveTo(cx, cy - half + 1)
        path.lineTo(cx + half, cy + half)
        path.lineTo(cx - half, cy + half)
        path.closeSubpath()
        painter.setBrush(QBrush(COLOR_MARKER_FILL))
        painter.drawPath(path)

    painter.restore()
