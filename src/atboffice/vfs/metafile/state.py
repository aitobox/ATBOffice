"""GDI device context state machine and object models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtGui import QColor

from .constants import CHARSET_ENCODINGS


def gdi_color_to_qcolor(cr: int, alpha: int = 255) -> QColor:
    """Convert Windows GDI COLORREF (0x00BBGGRR) to PySide6 QColor."""
    r = cr & 0xFF
    g = (cr >> 8) & 0xFF
    b = (cr >> 16) & 0xFF
    return QColor(r, g, b, alpha)


def decode_gdi_text(raw_bytes: bytes, charset: int = 0, face: str = "") -> str:
    """Decode GDI text bytes using font charset and East Asian font name heuristics."""
    enc = CHARSET_ENCODINGS.get(charset, "cp1252")

    # If default charset (0 or 1) and contains non-ASCII, infer encoding from font face
    if (charset in (0, 1)) and face and any(b > 127 for b in raw_bytes):
        cjk_face = face.lower()
        cjk_gbk = r"yahei|simsun|simhei|kaiti|fangsong|dengxian|nsimsun|宋体|黑体|微软雅黑"
        if re.search(cjk_gbk, cjk_face):
            enc = "gbk"
        elif re.search(r"mingliu|jhenghei|細明|新細明", cjk_face):
            enc = "big5"
        elif re.search(r"ms (p)?(gothic|mincho)|meiryo|yu (gothic|mincho)|ms ui gothic", cjk_face):
            enc = "shift_jis"
        elif re.search(r"gulim|dotum|batang|gungsuh|malgun", cjk_face):
            enc = "euc_kr"

    try:
        return raw_bytes.decode(enc, errors="replace")
    except Exception:
        return raw_bytes.decode("latin1", errors="replace")


@dataclass
class GdiPen:
    kind: str = "pen"
    style: int = 0  # 0=SOLID, 1=DASH, 2=DOT, 3=DASHDOT, 4=DASHDOTDOT, 5=NULL
    w: int = 1
    color: int = 0


@dataclass
class GdiBrush:
    kind: str = "brush"
    style: int = 0  # 0=SOLID, 1=HOLLOW/NULL, 2=HATCHED, 3=PATTERN, 5=DIBPATTERN, 6=DIBPATTERNPT
    color: int = 0xFFFFFF
    hatch: int = 0
    pat: Any = None  # QImage or None
    dib: bool = False


@dataclass
class GdiFont:
    kind: str = "font"
    h: int = -12
    w: int = 400
    i: bool = False
    face: str = "Arial"
    esc: int = 0
    charset: int = 0


@dataclass
class GdiState:
    pen: GdiPen = field(default_factory=GdiPen)
    brush: GdiBrush = field(default_factory=GdiBrush)
    font: GdiFont = field(default_factory=GdiFont)
    text: int = 0  # Text color (0x00BBGGRR)
    bk: int = 0xFFFFFF  # Background color
    bk_mode: int = 2  # 1=TRANSPARENT, 2=OPAQUE
    align: int = 0  # Text alignment
    fill: int = 1  # 1=ALTERNATE, 2=WINDING
    x: float = 0.0
    y: float = 0.0
    wo: list[float] = field(default_factory=lambda: [0.0, 0.0])  # Window Org [x, y]
    we: list[float] | None = None  # Window Ext [w, h]
    vo: list[float] = field(default_factory=lambda: [0.0, 0.0])  # Viewport Org [x, y]
    ve: list[float] | None = None  # Viewport Ext [w, h]
    map_mode: int = 1  # MM_TEXT
    # [m11, m12, m21, m22, dx, dy]
    xf: list[float] = field(default_factory=lambda: [1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    clip: list[float] | None = None  # [l, t, r, b]
    palette: list[list[int]] | None = None

    def clone(self) -> GdiState:
        """Create a deep copy of the DC state for SaveDC / RestoreDC."""
        return GdiState(
            pen=self.pen,
            brush=self.brush,
            font=self.font,
            text=self.text,
            bk=self.bk,
            bk_mode=self.bk_mode,
            align=self.align,
            fill=self.fill,
            x=self.x,
            y=self.y,
            wo=list(self.wo),
            we=list(self.we) if self.we is not None else None,
            vo=list(self.vo),
            ve=list(self.ve) if self.ve is not None else None,
            map_mode=self.map_mode,
            xf=list(self.xf),
            clip=list(self.clip) if self.clip is not None else None,
            palette=[list(p) for p in self.palette] if self.palette is not None else None,
        )
