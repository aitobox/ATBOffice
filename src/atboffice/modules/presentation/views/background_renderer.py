"""High-performance presentation background rendering engine for Lectern.

Supports painting solid, gradient, pattern (54 Office presets), procedural textures
(18 classics), and custom picture backgrounds onto arbitrary QPainter targets.
"""

from __future__ import annotations

import math
import os
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)

from atboffice.modules.presentation.models.shape import Fill
from atboffice.modules.spreadsheet.dialogs.pattern_defs import (
    create_pattern_brush,
)

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.designs import DesignTemplate


# 21 Office 2003 Classic Gradient Presets
GRAD_PRESETS: list[tuple[str, list[tuple[float, str]]]] = [
    ("早期黄昏", [(0.0, "#000082"), (0.3, "#66008F"), (0.65, "#BA0066"), (1.0, "#FF8200")]),
    ("晚霞", [(0.0, "#000000"), (0.5, "#000040"), (1.0, "#FF8C00")]),
    ("夜幕", [(0.0, "#000000"), (0.6, "#0A128C"), (1.0, "#181CC7")]),
    ("黎明", [(0.0, "#5E9EFF"), (0.4, "#85C2FF"), (0.7, "#C4D6EB"), (1.0, "#FFEBFA")]),
    (
        "地平线",
        [(0.0, "#DCEBF5"), (0.4, "#83A7C3"), (0.5, "#768FB9"), (0.6, "#83A7C3"), (1.0, "#FFFFFF")],
    ),
    ("沙漠", [(0.0, "#9C3500"), (0.3, "#E8A15C"), (0.6, "#FFDF9C"), (1.0, "#FFFFFF")]),
    ("海洋", [(0.0, "#03D4A8"), (0.5, "#21D6E0"), (1.0, "#0087E6")]),
    ("平静水面", [(0.0, "#CCCCFF"), (0.5, "#99CCFF"), (1.0, "#CCCCFF")]),
    ("火焰", [(0.0, "#FFF200"), (0.45, "#FF7A00"), (0.7, "#FF0300"), (1.0, "#4D0808")]),
    ("薄雾", [(0.0, "#8488C4"), (0.5, "#D4DEFF"), (1.0, "#96AB94")]),
    ("青苔", [(0.0, "#DDEBCF"), (0.5, "#9CB86E"), (1.0, "#156B13")]),
    (
        "孔雀",
        [(0.0, "#3399FF"), (0.2, "#00CCCC"), (0.5, "#9999FF"), (0.8, "#2E6792"), (1.0, "#3333CC")],
    ),
    (
        "麦浪",
        [(0.0, "#FBEAC7"), (0.2, "#FEE7F2"), (0.5, "#FAC77D"), (0.8, "#FBA97D"), (1.0, "#FBD49C")],
    ),
    ("羊皮纸", [(0.0, "#FFEFD1"), (0.65, "#F0EBD5"), (1.0, "#D1C39F")]),
    ("红木", [(0.0, "#D6B19C"), (0.3, "#D49E6C"), (0.7, "#A65528"), (1.0, "#663012")]),
    (
        "彩虹",
        [
            (0.0, "#A603AB"),
            (0.2, "#0819FB"),
            (0.4, "#1A8D48"),
            (0.6, "#FFFF00"),
            (0.8, "#EE3F17"),
            (1.0, "#E81766"),
        ],
    ),
    (
        "金色",
        [(0.0, "#E6DCAC"), (0.15, "#E6D78A"), (0.4, "#C7AC4C"), (0.6, "#E6D78A"), (1.0, "#E6DCAC")],
    ),
    (
        "黄铜",
        [
            (0.0, "#825600"),
            (0.15, "#FFA800"),
            (0.35, "#825600"),
            (0.55, "#FFA800"),
            (0.8, "#825600"),
            (1.0, "#FFA800"),
        ],
    ),
    (
        "铬黄",
        [
            (0.0, "#FFFFFF"),
            (0.2, "#000000"),
            (0.4, "#FFFFFF"),
            (0.6, "#000000"),
            (0.8, "#FFFFFF"),
            (1.0, "#000000"),
        ],
    ),
    ("银白", [(0.0, "#FFFFFF"), (0.3, "#E6E6E6"), (0.6, "#7D8496"), (1.0, "#FFFFFF")]),
    ("蓝宝石", [(0.0, "#000082"), (0.5, "#0047FF"), (1.0, "#000082")]),
]

# 18 Office 2003 Classic Procedural Textures
TEXTURE_NAMES: list[str] = [
    "画布",
    "牛仔布",
    "牛皮纸袋",
    "报纸",
    "再生纸",
    "羊皮纸",
    "花岗岩",
    "白大理石",
    "绿大理石",
    "沙石",
    "软木",
    "橡木",
    "胡桃木",
    "水滴",
    "蓝色薄纸",
    "草席",
    "信纸",
    "布料",
]

TEXTURE_KEY_MAP: dict[str, str] = {
    "Canvas": "画布",
    "Denim": "牛仔布",
    "Paper bag": "牛皮纸袋",
    "Newsprint": "报纸",
    "Recycled paper": "再生纸",
    "Parchment": "羊皮纸",
    "Granite": "花岗岩",
    "White marble": "白大理石",
    "Green marble": "绿大理石",
    "Sand": "沙石",
    "Cork": "软木",
    "Oak": "橡木",
    "Walnut": "胡桃木",
    "Water droplets": "水滴",
    "Blue tissue paper": "蓝色薄纸",
    "Woven mat": "草席",
    "Stationery": "信纸",
    "Fabric": "布料",
}

_TEXTURE_CACHE: dict[str, QPixmap] = {}


def resolve_fill_color(
    color_val: str | None,
    design: DesignTemplate | None = None,
    default: str = "#FFFFFF",
) -> QColor:
    """Resolve theme tokens, standard names, or hex strings to QColor."""
    if not color_val:
        return QColor(default)

    c_str = str(color_val).strip()
    if c_str.startswith("#") or c_str.startswith("rgb"):
        return QColor(c_str)

    # Check design template color palette if provided
    if design and hasattr(design, "colors"):
        colors = design.colors
        mapping = {
            "dk1": colors.dk1,
            "lt1": colors.lt1,
            "dk2": colors.dk2,
            "lt2": colors.lt2,
            "accent1": colors.accent1,
            "accent2": colors.accent2,
            "accent3": colors.accent3,
            "accent4": colors.accent4,
            "accent5": colors.accent5,
            "accent6": colors.accent6,
            "hlink": colors.hlink,
            "folHlink": colors.folHlink,
            "bg1": colors.lt1,
            "bg2": colors.lt2,
            "tx1": colors.dk1,
            "tx2": colors.dk2,
        }
        if c_str in mapping:
            return QColor(mapping[c_str])

    # Preset fallback mappings
    fallback_map = {
        "accent1": "#2B579A",
        "accent2": "#D24726",
        "accent3": "#008A00",
        "accent4": "#825A2C",
        "accent5": "#002050",
        "accent6": "#E2B200",
        "bg1": "#FFFFFF",
        "bg2": "#F2F2F2",
        "tx1": "#000000",
        "tx2": "#595959",
        "lt1": "#FFFFFF",
        "dk1": "#000000",
        "lt2": "#EBEBEB",
        "dk2": "#1E1E1E",
    }
    return QColor(fallback_map.get(c_str, default))


def get_procedural_texture(name: str) -> QPixmap:
    """Generate or retrieve a cached procedural texture QPixmap (64x64 or 128x128)."""
    norm_name = TEXTURE_KEY_MAP.get(name, name)
    if norm_name in _TEXTURE_CACHE:
        return _TEXTURE_CACHE[norm_name]

    s = 128
    img = QImage(s, s, QImage.Format.Format_ARGB32_Premultiplied)
    rng = random.Random(norm_name)

    def fill_noise(base_hex: str, amt: int) -> None:
        base_c = QColor(base_hex)
        r0, g0, b0 = base_c.red(), base_c.green(), base_c.blue()
        for y in range(s):
            for x in range(s):
                n = int((rng.random() - 0.5) * amt)
                r = max(0, min(255, r0 + n))
                g = max(0, min(255, g0 + n))
                b = max(0, min(255, b0 + n))
                img.setPixelColor(x, y, QColor(r, g, b))

    if norm_name == "画布":
        fill_noise("#E9E1CC", 25)
        p = QPainter(img)
        p.setPen(QPen(QColor(160, 138, 96, 50), 1))
        for i in range(0, s, 3):
            p.drawLine(0, i, s, i)
            p.drawLine(i, 0, i, s)
        p.end()

    elif norm_name == "牛仔布":
        fill_noise("#3E5F8A", 30)
        p = QPainter(img)
        p.setPen(QPen(QColor(207, 224, 245, 60), 1))
        for i in range(-s, s * 2, 4):
            p.drawLine(i, 0, i + s, s)
        p.end()

    elif norm_name == "牛皮纸袋":
        fill_noise("#B8915F", 30)
        p = QPainter(img)
        for _ in range(50):
            c = QColor(138, 106, 62, 70) if rng.random() > 0.5 else QColor(214, 184, 138, 70)
            rx = int(rng.random() * s)
            ry = int(rng.random() * s)
            rw = int(rng.random() * 20 + 2)
            p.fillRect(rx, ry, rw, 1, c)
        p.end()

    elif norm_name == "报纸":
        fill_noise("#E3E0D8", 18)
        p = QPainter(img)
        for _ in range(120):
            p.fillRect(int(rng.random() * s), int(rng.random() * s), 1, 1, QColor(80, 80, 80, 50))
        p.end()

    elif norm_name == "再生纸":
        fill_noise("#DCD3C0", 20)
        p = QPainter(img)
        colors = [
            QColor(122, 107, 85, 120),
            QColor(164, 152, 132, 120),
            QColor(94, 84, 68, 120),
        ]
        for i in range(100):
            rx = int(rng.random() * s)
            ry = int(rng.random() * s)
            rw = int(rng.random() * 3 + 1)
            p.fillRect(rx, ry, rw, 1, colors[i % 3])
        p.end()

    elif norm_name == "羊皮纸":
        p = QPainter(img)
        grad = QRadialGradient(QPointF(s / 2.0, s / 2.0), s * 0.75)
        grad.setColorAt(0.0, QColor("#FBF1D4"))
        grad.setColorAt(1.0, QColor("#E2CC97"))
        p.fillRect(0, 0, s, s, QBrush(grad))
        p.end()
        # overlay subtle noise
        for y in range(s):
            for x in range(s):
                orig = img.pixelColor(x, y)
                n = int((rng.random() - 0.5) * 16)
                r_val = max(0, min(255, orig.red() + n))
                g_val = max(0, min(255, orig.green() + n))
                b_val = max(0, min(255, orig.blue() + n))
                img.setPixelColor(x, y, QColor(r_val, g_val, b_val))

    elif norm_name == "花岗岩":
        fill_noise("#9A9A9A", 50)
        p = QPainter(img)
        for _ in range(300):
            col = rng.choice([QColor("#2B2B2B"), QColor("#E8E8E8"), QColor("#6B4F4F")])
            col.setAlpha(150)
            sz = int(rng.random() * 2 + 1)
            p.fillRect(int(rng.random() * s), int(rng.random() * s), sz, sz, col)
        p.end()

    elif norm_name == "白大理石":
        fill_noise("#F2F2F0", 12)
        p = QPainter(img)
        p.setPen(QPen(QColor(154, 154, 154, 80), 1))
        for _ in range(5):
            x = rng.random() * s
            y = 0.0
            while y < s:
                nx = x + (rng.random() - 0.5) * 16
                ny = y + 8
                p.drawLine(QPointF(x, y), QPointF(nx, ny))
                x, y = nx, ny
        p.end()

    elif norm_name == "绿大理石":
        fill_noise("#2E6B4F", 30)
        p = QPainter(img)
        p.setPen(QPen(QColor(207, 232, 216, 110), 1))
        for _ in range(5):
            x = rng.random() * s
            y = 0.0
            while y < s:
                nx = x + (rng.random() - 0.5) * 16
                ny = y + 8
                p.drawLine(QPointF(x, y), QPointF(nx, ny))
                x, y = nx, ny
        p.end()

    elif norm_name == "沙石":
        fill_noise("#D9C29A", 35)

    elif norm_name == "软木":
        fill_noise("#B07A45", 45)
        p = QPainter(img)
        for _ in range(250):
            col = QColor("#6B4423") if rng.random() > 0.5 else QColor("#D9A066")
            col.setAlpha(130)
            p.fillRect(int(rng.random() * s), int(rng.random() * s), 2, 2, col)
        p.end()

    elif norm_name == "橡木":
        p = QPainter(img)
        p.fillRect(0, 0, s, s, QColor("#C49A6C"))
        for y in range(0, s, 3):
            col = QColor(138, 95, 52, 90) if rng.random() > 0.5 else QColor(224, 189, 143, 90)
            p.setPen(QPen(col, 1))
            for x in range(0, s, 8):
                dy = int(math.sin(x / 15.0 + y / 20.0) * 2.5)
                p.drawLine(x, y + dy, x + 8, y + dy)
        p.end()

    elif norm_name == "胡桃木":
        p = QPainter(img)
        p.fillRect(0, 0, s, s, QColor("#5C3A21"))
        for y in range(0, s, 3):
            col = QColor(58, 35, 18, 90) if rng.random() > 0.5 else QColor(138, 90, 54, 90)
            p.setPen(QPen(col, 1))
            for x in range(0, s, 8):
                dy = int(math.sin(x / 12.0 + y / 18.0) * 3)
                p.drawLine(x, y + dy, x + 8, y + dy)
        p.end()

    elif norm_name == "水滴":
        fill_noise("#9CC3D9", 15)
        p = QPainter(img)
        for _ in range(35):
            cx = rng.random() * s
            cy = rng.random() * s
            r = rng.random() * 5 + 3
            rg = QRadialGradient(QPointF(cx - r / 3.0, cy - r / 3.0), r)
            rg.setColorAt(0.0, QColor(255, 255, 255, 230))
            rg.setColorAt(1.0, QColor(60, 110, 150, 90))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(rg))
            p.drawEllipse(QPointF(cx, cy), r, r)
        p.end()

    elif norm_name == "蓝色薄纸":
        fill_noise("#BFD3EE", 20)
        p = QPainter(img)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        for _ in range(25):
            x1 = rng.random() * s
            y1 = rng.random() * s
            p.drawLine(QPointF(x1, y1), QPointF(x1 + rng.random() * 20, y1 + rng.random() * 20))
        p.end()

    elif norm_name == "草席":
        p = QPainter(img)
        p.fillRect(0, 0, s, s, QColor("#D8C08E"))
        for y in range(0, s, 16):
            for x in range(0, s, 16):
                col = QColor("#C2A46B") if (x + y) % 32 else QColor("#E8D3A5")
                p.fillRect(x, y, 16, 8, col)
                col2 = QColor("#E8D3A5") if (x + y) % 32 else QColor("#C2A46B")
                p.fillRect(x, y + 8, 16, 8, col2)
        p.end()

    elif norm_name == "信纸":
        p = QPainter(img)
        p.fillRect(0, 0, s, s, QColor("#FFFFF4"))
        p.setPen(QPen(QColor("#B9D3EE"), 1))
        for y in range(8, s, 16):
            p.drawLine(0, y, s, y)
        p.end()

    else:  # 布料 or default
        fill_noise("#B04A5A", 30)
        p = QPainter(img)
        p.setPen(QPen(QColor(255, 255, 255, 50), 1))
        for i in range(0, s, 4):
            p.drawLine(i, 0, i, s)
            p.drawLine(0, i, s, i)
        p.end()

    pix = QPixmap.fromImage(img)
    _TEXTURE_CACHE[norm_name] = pix
    return pix


def paint_fill_rect(
    painter: QPainter,
    rect: QRectF,
    fill: Fill | None,
    design: DesignTemplate | None = None,
) -> None:
    """Render any fill type (solid, grad, patt, img) onto a target rectangle using QPainter."""
    if rect.width() <= 0 or rect.height() <= 0:
        return

    # 1. Fallback or None Fill -> inherit from design or pure white
    if fill is None or fill.type == "none":
        if design and hasattr(design, "bg") and design.bg and design.bg.type != "none":
            paint_fill_rect(painter, rect, design.bg, design=None)
        else:
            default_color = (
                design.colors.lt1 if (design and hasattr(design, "colors")) else "#FFFFFF"
            )
            painter.fillRect(rect, QColor(default_color))
        return

    # 2. Solid Fill
    if fill.type == "solid":
        col = resolve_fill_color(fill.color, design, default="#FFFFFF")
        alpha = max(0.0, min(1.0, float(getattr(fill, "alpha", 1.0))))
        col.setAlphaF(alpha)
        painter.fillRect(rect, col)
        return

    # 3. Gradient Fill
    if fill.type == "grad":
        stops = sorted(fill.stops, key=lambda s: s.get("p", 0.0))
        if len(stops) < 2:
            stops = [{"p": 0.0, "c": "#FFFFFF", "a": 1.0}, {"p": 1.0, "c": "#3366CC", "a": 1.0}]

        # Radial Gradient (Circle / Center)
        if fill.path == "circle":
            center = rect.center()
            radius = max(rect.width(), rect.height()) / 1.414
            gradient: QLinearGradient | QRadialGradient = QRadialGradient(center, radius)
        # Radial Gradient (Corner / Rect)
        elif fill.path == "rect":
            gradient = QRadialGradient(rect.topLeft(), math.hypot(rect.width(), rect.height()))
        # Linear Gradient
        else:
            ang = (fill.angle % 360 + 360) % 360
            if abs(ang - 90.0) < 0.1:  # Horizontal: left to right
                p1 = QPointF(rect.left(), rect.top())
                p2 = QPointF(rect.right(), rect.top())
            elif abs(ang - 0.0) < 0.1:  # Vertical: top to bottom
                p1 = QPointF(rect.left(), rect.top())
                p2 = QPointF(rect.left(), rect.bottom())
            elif (
                abs(ang - 315.0) < 0.1
                or (abs(ang - 45.0) < 0.1 and getattr(fill, "path", "") == "dup")
            ):  # Diagonal up
                p1 = QPointF(rect.left(), rect.bottom())
                p2 = QPointF(rect.right(), rect.top())
            elif abs(ang - 45.0) < 0.1 or abs(ang - 135.0) < 0.1:  # Diagonal down
                p1 = QPointF(rect.left(), rect.top())
                p2 = QPointF(rect.right(), rect.bottom())
            else:
                center = rect.center()
                rad = math.radians(ang)
                dx = math.cos(rad) * rect.width() / 2.0
                dy = math.sin(rad) * rect.height() / 2.0
                p1 = QPointF(center.x() - dx, center.y() - dy)
                p2 = QPointF(center.x() + dx, center.y() + dy)

            gradient = QLinearGradient(p1, p2)

        for s in stops:
            pos = max(0.0, min(1.0, float(s.get("p", 0.0))))
            scol = resolve_fill_color(s.get("c"), design, "#FFFFFF")
            salpha = max(0.0, min(1.0, float(s.get("a", 1.0))))
            scol.setAlphaF(salpha)
            gradient.setColorAt(pos, scol)

        painter.fillRect(rect, QBrush(gradient))
        return

    # 4. Pattern Fill
    if fill.type == "patt":
        prst = fill.pattern or "pct50"
        fg_col = resolve_fill_color(fill.fg or "#000000", design)
        bg_col = resolve_fill_color(fill.bg or "#FFFFFF", design)
        brush = create_pattern_brush(prst, fg_col, bg_col)
        painter.fillRect(rect, brush)
        return

    # 5. Image or Procedural Texture Fill
    if fill.type == "img":
        img_key = getattr(fill, "image_path", "") or getattr(fill, "pattern", "")
        tile_mode = getattr(fill, "tile", False)

        # A: Check procedural texture names first
        norm_key = TEXTURE_KEY_MAP.get(img_key, img_key)
        if norm_key in TEXTURE_NAMES:
            tex_pix = get_procedural_texture(norm_key)
            if tile_mode:
                painter.drawTiledPixmap(rect.toRect(), tex_pix)
            else:
                painter.drawPixmap(
                    rect.toRect(),
                    tex_pix.scaled(
                        rect.size().toSize(),
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    ),
                )
            return

        # B: Check local file path on disk
        if img_key and os.path.exists(img_key):
            qimg = QImage(img_key)
            if not qimg.isNull():
                pix = QPixmap.fromImage(qimg)
                if tile_mode:
                    painter.drawTiledPixmap(rect.toRect(), pix)
                else:
                    painter.drawPixmap(
                        rect.toRect(),
                        pix.scaled(
                            rect.size().toSize(),
                            Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        ),
                    )
                return

        # Fallback for missing image
        painter.fillRect(rect, QColor("#E0E0E0"))
        return

    # Default fallback
    painter.fillRect(rect, QColor("#FFFFFF"))
