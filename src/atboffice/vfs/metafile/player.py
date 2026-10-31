"""High-fidelity GDI metafile playback engine targeting PySide6 QPainter."""

from __future__ import annotations

import math

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)

from .constants import (
    ROP_BLACKNESS,
    ROP_PATCOPY,
    ROP_SRCAND,
    ROP_SRCINVERT,
    ROP_WHITENESS,
)
from .dib import compose_mask_xor
from .state import GdiBrush, GdiPen, GdiState, gdi_color_to_qcolor


class MetafilePlayer:
    """Plays WMF and EMF vector graphics commands onto a PySide6 QPainter."""

    def __init__(
        self,
        painter: QPainter | None = None,
        target_rect: QRectF | None = None,
    ) -> None:
        self.painter = painter
        self.target_rect = target_rect or QRectF(0, 0, 1000, 1000)
        self.state = GdiState()
        self.stack: list[GdiState] = []
        self.path: QPainterPath | None = None
        self.last_path: QPainterPath | None = None
        self._wmf_mode = False
        self._wmf_bbox = [0, 0, 1000, 1000]
        self._emf_fr = [0.0, 0.0, 1000.0, 1000.0]
        self._pending_mask: dict | None = None

    @property
    def in_path(self) -> bool:
        """Whether the player is currently recording commands into a path bracket."""
        return self.path is not None

    def setup_wmf_mapping(self, bbox: list[int]) -> None:
        """Set up coordinate mapping for 16-bit WMF."""
        self._wmf_mode = True
        self._wmf_bbox = list(bbox)
        self.state = GdiState()
        self.stack.clear()
        self.path = None
        self.last_path = None
        self._pending_mask = None

    def setup_emf_mapping(self, fr: list[float]) -> None:
        """Set up coordinate mapping for 32-bit EMF."""
        self._wmf_mode = False
        self._emf_fr = list(fr)
        self.state = GdiState()
        self.stack.clear()
        self.path = None
        self.last_path = None
        self._pending_mask = None

    # ---------- Coordinate transforms ----------

    def pt(self, x: float, y: float) -> tuple[float, float]:
        """Convert logical GDI coordinates (x, y) to canvas pixel coordinates."""
        s = self.state
        tr = self.target_rect

        if self._wmf_mode:
            bbox = self._wmf_bbox
            bw = (bbox[2] - bbox[0]) or 1.0
            bh = (bbox[3] - bbox[1]) or 1.0

            if s.we is not None:
                we_x = s.we[0] or 1.0
                we_y = s.we[1] or 1.0
                big_x = bbox[0] + ((x - s.wo[0]) * bw) / we_x
                big_y = bbox[1] + ((y - s.wo[1]) * bh) / we_y
            else:
                big_x = x
                big_y = y

            cx = tr.left() + ((big_x - bbox[0]) * tr.width()) / bw
            cy = tr.top() + ((big_y - bbox[1]) * tr.height()) / bh
            return cx, cy

        # EMF mapping
        xf = s.xf
        big_x = xf[0] * x + xf[2] * y + xf[4]
        big_y = xf[1] * x + xf[3] * y + xf[5]

        if s.we is not None and s.map_mode >= 7:
            ve = s.ve or s.we
            we_x = s.we[0] or 1.0
            we_y = s.we[1] or 1.0
            dx = ((big_x - s.wo[0]) * ve[0]) / we_x + s.vo[0]
            dy = ((big_y - s.wo[1]) * ve[1]) / we_y + s.vo[1]
        else:
            dx = big_x - s.wo[0] + s.vo[0]
            dy = big_y - s.wo[1] + s.vo[1]

        fr = self._emf_fr
        fw = (fr[2] - fr[0]) or 1.0
        fh = (fr[3] - fr[1]) or 1.0

        cx = tr.left() + ((dx - fr[0]) * tr.width()) / fw
        cy = tr.top() + ((dy - fr[1]) * tr.height()) / fh
        return cx, cy

    def scale_factor(self) -> tuple[float, float]:
        """Compute horizontal and vertical scaling factors from logical units to canvas pixels."""
        p0 = self.pt(0.0, 0.0)
        p1 = self.pt(1000.0, 1000.0)
        sx = abs(p1[0] - p0[0]) / 1000.0
        sy = abs(p1[1] - p0[1]) / 1000.0
        return max(sx, 1e-6), max(sy, 1e-6)

    # ---------- Styling helpers ----------

    def is_pen_on(self) -> bool:
        p = self.state.pen
        return p is not None and (p.style & 0xF) != 5

    def is_brush_on(self) -> bool:
        b = self.state.brush
        return b is not None and b.style != 1

    def make_qpen(self) -> QPen:
        p = self.state.pen
        sx, sy = self.scale_factor()
        color = gdi_color_to_qcolor(p.color)
        lw = max(1.0, (p.w or 0) * (sx + sy) / 2.0)

        st = p.style & 0xF
        pen_style = Qt.PenStyle.SolidLine
        if st == 1:
            pen_style = Qt.PenStyle.DashLine
        elif st == 2:
            pen_style = Qt.PenStyle.DotLine
        elif st == 3:
            pen_style = Qt.PenStyle.DashDotLine
        elif st == 4:
            pen_style = Qt.PenStyle.DashDotDotLine
        elif st == 5:
            pen_style = Qt.PenStyle.NoPen

        cap_raw = (p.style >> 8) & 0xF
        cap = Qt.PenCapStyle.RoundCap
        if cap_raw == 1:
            cap = Qt.PenCapStyle.SquareCap
        elif cap_raw == 2:
            cap = Qt.PenCapStyle.FlatCap

        join_raw = (p.style >> 12) & 0xF
        join = Qt.PenJoinStyle.RoundJoin
        if join_raw == 1:
            join = Qt.PenJoinStyle.BevelJoin
        elif join_raw == 2:
            join = Qt.PenJoinStyle.MiterJoin

        pen = QPen(color, lw, pen_style, cap, join)
        return pen

    def make_qbrush(self) -> QBrush:
        b = self.state.brush
        if b.style == 2:  # HATCHED
            hatch_styles = [
                Qt.BrushStyle.HorPattern,
                Qt.BrushStyle.VerPattern,
                Qt.BrushStyle.FDiagPattern,
                Qt.BrushStyle.BDiagPattern,
                Qt.BrushStyle.CrossPattern,
                Qt.BrushStyle.DiagCrossPattern,
            ]
            if b.hatch is not None:
                style = hatch_styles[b.hatch % len(hatch_styles)]
            else:
                style = Qt.BrushStyle.HorPattern
            return QBrush(gdi_color_to_qcolor(b.color), style)
        elif b.style in (3, 5, 6) and b.pat is not None:
            if isinstance(b.pat, QImage):
                return QBrush(b.pat)
        elif b.style == 1:
            return QBrush(Qt.BrushStyle.NoBrush)

        return QBrush(gdi_color_to_qcolor(b.color))

    # ---------- State Management ----------

    def save(self) -> None:
        self.stack.append(self.state.clone())
        if self.painter:
            self.painter.save()

    def restore(self, count: int = 1) -> None:
        k = -count if count < 0 else 1
        st = None
        while k > 0 and self.stack:
            st = self.stack.pop()
            k -= 1
        if st is not None:
            self.state = st
        if self.painter:
            self.painter.restore()

    def intersect_clip(self, left: float, top: float, right: float, bottom: float) -> None:
        p0 = self.pt(left, top)
        p1 = self.pt(right, bottom)
        nc = [min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])]
        s = self.state
        if s.clip:
            s.clip = [
                max(s.clip[0], nc[0]),
                max(s.clip[1], nc[1]),
                min(s.clip[2], nc[2]),
                min(s.clip[3], nc[3]),
            ]
        else:
            s.clip = nc

    # ---------- Path Operations ----------

    def begin_path(self) -> None:
        self.path = QPainterPath()

    def end_path(self) -> None:
        self.last_path = self.path
        self.path = None

    def close_figure(self) -> None:
        if self.path is not None:
            self.path.closeSubpath()

    def abort_path(self) -> None:
        self.path = None
        self.last_path = None

    def path_move_to(self, x: float, y: float) -> None:
        if self.path is not None:
            px, py = self.pt(x, y)
            self.path.moveTo(px, py)

    def path_line_to(self, x: float, y: float) -> None:
        if self.path is not None:
            px, py = self.pt(x, y)
            self.path.lineTo(px, py)

    def fill_path(self, mode: str = "both") -> None:
        target_path = self.path or self.last_path
        self.path = None
        self.last_path = None
        if target_path is None or not self.painter:
            return

        fill_rule = Qt.FillRule.OddEvenFill if self.state.fill == 1 else Qt.FillRule.WindingFill
        target_path.setFillRule(fill_rule)

        self._render_path(target_path, fill_it=(mode != "stroke"), stroke_it=(mode != "fill"))

    # ---------- Drawing Primitives ----------

    def _render_path(
        self, path: QPainterPath, fill_it: bool = True, stroke_it: bool = True
    ) -> None:
        if not self.painter:
            return

        p = self.painter
        p.save()

        # Apply clipping if present
        if self.state.clip:
            c = self.state.clip
            p.setClipRect(QRectF(c[0], c[1], max(0.0, c[2] - c[0]), max(0.0, c[3] - c[1])))

        if fill_it and self.is_brush_on():
            p.setBrush(self.make_qbrush())
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(path)

        if stroke_it and self.is_pen_on():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(self.make_qpen())
            p.drawPath(path)

        p.restore()

    def draw_rect(
        self,
        left: float,
        top: float,
        right: float,
        bottom: float,
        rx: float | None = None,
        ry: float | None = None,
    ) -> None:
        p0 = self.pt(left, top)
        p1 = self.pt(right, bottom)
        x = min(p0[0], p1[0])
        y = min(p0[1], p1[1])
        w = abs(p1[0] - p0[0])
        h = abs(p1[1] - p0[1])

        path = QPainterPath()
        if rx and ry and rx > 0 and ry > 0:
            sx, sy = self.scale_factor()
            cx = min(w / 2.0, (rx * sx) / 2.0)
            cy = min(h / 2.0, (ry * sy) / 2.0)
            path.addRoundedRect(QRectF(x, y, w, h), cx, cy)
        else:
            path.addRect(QRectF(x, y, w, h))

        if self.in_path:
            self.path.addPath(path)
        else:
            self._render_path(path, fill_it=True, stroke_it=True)

    def draw_ellipse(self, left: float, top: float, right: float, bottom: float) -> None:
        p0 = self.pt(left, top)
        p1 = self.pt(right, bottom)
        x = min(p0[0], p1[0])
        y = min(p0[1], p1[1])
        w = abs(p1[0] - p0[0])
        h = abs(p1[1] - p0[1])

        path = QPainterPath()
        path.addEllipse(QRectF(x, y, w, h))

        if self.in_path:
            self.path.addPath(path)
        else:
            self._render_path(path, fill_it=True, stroke_it=True)

    def draw_poly(self, pts: list[list[float]], closed: bool = True) -> None:
        if len(pts) < 2:
            return

        canvas_pts = [self.pt(p[0], p[1]) for p in pts]
        path = QPainterPath()
        path.moveTo(QPointF(canvas_pts[0][0], canvas_pts[0][1]))
        for i in range(1, len(canvas_pts)):
            path.lineTo(QPointF(canvas_pts[i][0], canvas_pts[i][1]))
        if closed:
            path.closeSubpath()

        if self.in_path:
            self.path.addPath(path)
        else:
            self._render_path(path, fill_it=closed, stroke_it=True)

    def draw_poly_poly(self, polys: list[list[list[float]]], closed: bool = True) -> None:
        valid_polys = [p for p in polys if len(p) > 1]
        if not valid_polys:
            return

        path = QPainterPath()
        for poly in valid_polys:
            cpts = [self.pt(pt[0], pt[1]) for pt in poly]
            path.moveTo(QPointF(cpts[0][0], cpts[0][1]))
            for i in range(1, len(cpts)):
                path.lineTo(QPointF(cpts[i][0], cpts[i][1]))
            if closed:
                path.closeSubpath()

        if self.in_path:
            self.path.addPath(path)
        else:
            self._render_path(path, fill_it=closed, stroke_it=True)

    def draw_bezier(self, pts: list[list[float]], from_current: bool = False) -> None:
        all_pts = [[self.state.x, self.state.y]] + pts if from_current else pts
        if len(all_pts) < 4:
            return

        cpts = [self.pt(p[0], p[1]) for p in all_pts]
        path = QPainterPath()
        path.moveTo(QPointF(cpts[0][0], cpts[0][1]))

        i = 1
        while i + 2 < len(cpts):
            path.cubicTo(
                QPointF(cpts[i][0], cpts[i][1]),
                QPointF(cpts[i + 1][0], cpts[i + 1][1]),
                QPointF(cpts[i + 2][0], cpts[i + 2][1]),
            )
            i += 3

        last = all_pts[-1]
        self.state.x = last[0]
        self.state.y = last[1]

        if self.in_path:
            self.path.addPath(path)
        else:
            self._render_path(path, fill_it=False, stroke_it=True)

    def draw_arc(
        self,
        left: float,
        top: float,
        right: float,
        bottom: float,
        xs: float,
        ys: float,
        xe: float,
        ye: float,
        kind: str = "arc",
    ) -> None:
        p0 = self.pt(left, top)
        p1 = self.pt(right, bottom)
        s0 = self.pt(xs, ys)
        e0 = self.pt(xe, ye)

        cx = (p0[0] + p1[0]) / 2.0
        cy = (p0[1] + p1[1]) / 2.0
        rx = abs(p1[0] - p0[0]) / 2.0
        ry = abs(p1[1] - p0[1]) / 2.0
        if rx <= 0 or ry <= 0:
            return

        a0 = math.atan2((s0[1] - cy) / ry, (s0[0] - cx) / rx)
        a1 = math.atan2((e0[1] - cy) / ry, (e0[0] - cx) / rx)

        start_deg = -math.degrees(a0)
        end_deg = -math.degrees(a1)
        sweep_deg = (end_deg - start_deg) % 360.0
        if sweep_deg == 0 and a0 != a1:
            sweep_deg = 360.0

        rect = QRectF(cx - rx, cy - ry, rx * 2.0, ry * 2.0)
        path = QPainterPath()

        if kind == "pie":
            path.moveTo(QPointF(cx, cy))
            path.arcTo(rect, start_deg, sweep_deg)
            path.closeSubpath()
        elif kind == "chord":
            path.arcMoveTo(rect, start_deg)
            path.arcTo(rect, start_deg, sweep_deg)
            path.closeSubpath()
        else:
            path.arcMoveTo(rect, start_deg)
            path.arcTo(rect, start_deg, sweep_deg)

        if self.in_path:
            self.path.addPath(path)
        else:
            self._render_path(path, fill_it=(kind != "arc"), stroke_it=True)

    def draw_text(
        self,
        x: float,
        y: float,
        txt: str,
        dxs: list[int] | None = None,
    ) -> None:
        if not txt or not self.painter:
            return

        p = self.painter
        s = self.state
        f = s.font
        sx, sy = self.scale_factor()

        size = max(1.0, abs(f.h or 12) * sy * (0.82 if f.h > 0 else 1.0))
        weight = QFont.Weight.Bold if f.w >= 600 else QFont.Weight.Normal
        font = QFont(f.face or "Arial", round(size))
        font.setWeight(weight)
        font.setItalic(f.i)

        p.save()
        if s.clip:
            c = s.clip
            p.setClipRect(QRectF(c[0], c[1], max(0.0, c[2] - c[0]), max(0.0, c[3] - c[1])))

        p.setFont(font)
        p.setPen(gdi_color_to_qcolor(s.text))

        use_cp = bool(s.align & 1)
        pt_x, pt_y = (s.x, s.y) if use_cp else (x, y)
        cx, cy = self.pt(pt_x, pt_y)

        p.translate(cx, cy)
        if f.esc:
            p.rotate(-f.esc / 10.0)

        # Text alignment
        ha = s.align & 6
        va = s.align & 24
        flags = 0
        if ha == 6:
            flags |= Qt.AlignmentFlag.AlignHCenter
        elif ha == 2:
            flags |= Qt.AlignmentFlag.AlignRight
        else:
            flags |= Qt.AlignmentFlag.AlignLeft

        if va == 24:
            flags |= Qt.AlignmentFlag.AlignBaseline
        elif va == 8:
            flags |= Qt.AlignmentFlag.AlignBottom
        else:
            flags |= Qt.AlignmentFlag.AlignTop

        if dxs and len(dxs) == len(txt) and ha == 0:
            cur_x = 0.0
            for char, dx in zip(txt, dxs):
                p.drawText(round(cur_x), 0, char)
                cur_x += dx * sx
        else:
            p.drawText(0, 0, txt)

        p.restore()

        if use_cp:
            w_px = p.fontMetrics().horizontalAdvance(txt)
            s.x += w_px / sx

    def draw_blit(
        self,
        img: QImage | None,
        sx: int,
        sy: int,
        sw: int,
        sh: int,
        dx: int,
        dy: int,
        dw: int,
        dh: int,
        rop: int,
    ) -> None:
        if img is None:
            return

        key = (dx, dy, dw, dh)
        if rop == ROP_SRCAND:
            self._pending_mask = {
                "img": img,
                "sx": sx,
                "sy": sy,
                "sw": sw,
                "sh": sh,
                "key": key,
            }
            return

        if rop == ROP_SRCINVERT and self._pending_mask and self._pending_mask["key"] == key:
            m = self._pending_mask
            self._pending_mask = None
            composed = compose_mask_xor(m["img"], img, sw, sh, m["sw"], m["sh"])
            self._paint_image(composed, 0, 0, composed.width(), composed.height(), dx, dy, dw, dh)
            return

        self._pending_mask = None
        self._paint_image(img, sx, sy, sw, sh, dx, dy, dw, dh)

    def _paint_image(
        self,
        img: QImage,
        sx: int,
        sy: int,
        sw: int,
        sh: int,
        dx: int,
        dy: int,
        dw: int,
        dh: int,
    ) -> None:
        if not self.painter:
            return

        p0 = self.pt(dx, dy)
        p1 = self.pt(dx + dw, dy + dh)
        x = min(p0[0], p1[0])
        y = min(p0[1], p1[1])
        w = abs(p1[0] - p0[0])
        h = abs(p1[1] - p0[1])

        p = self.painter
        p.save()
        if self.state.clip:
            c = self.state.clip
            p.setClipRect(QRectF(c[0], c[1], max(0.0, c[2] - c[0]), max(0.0, c[3] - c[1])))

        src_rect = QRectF(
            max(0, sx),
            max(0, sy),
            max(1, abs(sw) or img.width()),
            max(1, abs(sh) or img.height()),
        )
        p.drawImage(QRectF(x, y, w, h), img, src_rect)
        p.restore()

    def pat_blt(self, rop: int, x: float, y: float, w: float, h: float) -> None:
        keep_pen = self.state.pen
        keep_brush = self.state.brush

        if rop == ROP_PATCOPY:
            pass
        elif rop == ROP_WHITENESS:
            self.state.brush = GdiBrush("brush", 0, 0xFFFFFF)
        elif rop == ROP_BLACKNESS:
            self.state.brush = GdiBrush("brush", 0, 0x000000)
        else:
            return

        self.state.pen = GdiPen("pen", 5)  # NULL_PEN
        self.draw_rect(x, y, x + w, y + h)
        self.state.pen = keep_pen
        self.state.brush = keep_brush

    # ---------- High-Level Playback & Rendering API ----------

    def play(
        self,
        data: bytes,
        painter: QPainter,
        target_rect: QRectF | None = None,
        kind: str = "auto",
    ) -> bool:
        """Play metafile data onto the given QPainter."""
        if not data or len(data) < 18:
            return False

        from .emf_parser import EMFParser
        from .wmf_parser import WMFParser

        self.painter = painter
        self.target_rect = target_rect or QRectF(0, 0, 1000, 1000)

        is_emf = kind == "emf" or (kind == "auto" and EMFParser.is_emf(data))
        is_wmf = kind == "wmf" or (kind == "auto" and WMFParser.is_wmf(data))

        painter.save()
        try:
            if is_emf:
                return EMFParser.parse_and_play(data, self)
            elif is_wmf:
                return WMFParser.parse_and_play(data, self)
            return False
        finally:
            painter.restore()

    def render_to_image(
        self,
        data: bytes,
        kind: str = "auto",
        max_px: int = 1200,
    ) -> QImage | None:
        """Render metafile data to a high-resolution QImage."""
        if not data or len(data) < 18:
            return None

        from .emf_parser import EMFParser
        from .wmf_parser import WMFParser

        is_emf = kind == "emf" or (kind == "auto" and EMFParser.is_emf(data))
        is_wmf = kind == "wmf" or (kind == "auto" and WMFParser.is_wmf(data))

        if is_emf:
            metrics = EMFParser.get_bounds_and_metrics(data, max_px=max_px)
            if not metrics:
                return None
            _, cw, ch = metrics
        elif is_wmf:
            metrics = WMFParser.get_bounds_and_metrics(data, max_px=max_px)
            if not metrics:
                return None
            _, _, cw, ch = metrics
        else:
            return None

        cw = max(1, min(cw, max_px))
        ch = max(1, min(ch, max_px))

        img = QImage(cw, ch, QImage.Format.Format_ARGB32)
        img.fill(0)  # Transparent background

        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        play_kind = "emf" if is_emf else "wmf"
        ok = self.play(data, painter, target_rect=QRectF(0, 0, cw, ch), kind=play_kind)
        painter.end()

        return img if ok else None

    def render_to_bytes(
        self,
        data: bytes,
        kind: str = "auto",
        format: str = "PNG",
        max_px: int = 1200,
    ) -> bytes | None:
        """Render metafile to compressed image bytes (PNG, JPEG, etc.)."""
        img = self.render_to_image(data, kind=kind, max_px=max_px)
        if img is None or img.isNull():
            return None

        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        ok = img.save(buf, format)
        buf.close()

        return bytes(buf.data()) if ok else None

    def get_dimensions(self, data: bytes, kind: str = "auto") -> tuple[int, int] | None:
        """Get calculated pixel width and height of metafile without rasterizing."""
        if not data or len(data) < 18:
            return None

        from .emf_parser import EMFParser
        from .wmf_parser import WMFParser

        is_emf = kind == "emf" or (kind == "auto" and EMFParser.is_emf(data))
        is_wmf = kind == "wmf" or (kind == "auto" and WMFParser.is_wmf(data))

        if is_emf:
            metrics = EMFParser.get_bounds_and_metrics(data)
            return (metrics[1], metrics[2]) if metrics else None
        elif is_wmf:
            metrics = WMFParser.get_bounds_and_metrics(data)
            return (metrics[2], metrics[3]) if metrics else None
        return None
