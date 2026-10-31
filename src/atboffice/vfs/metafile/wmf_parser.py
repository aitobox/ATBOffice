"""Windows Metafile (WMF) 16-bit binary stream parser."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING, Any

from .constants import (
    WMF_PLACEABLE_KEY,
    WMF_RECORD_ARC,
    WMF_RECORD_CHORD,
    WMF_RECORD_CREATEBRUSHINDIRECT,
    WMF_RECORD_CREATEFONTINDIRECT,
    WMF_RECORD_CREATEPALETTE,
    WMF_RECORD_CREATEPENINDIRECT,
    WMF_RECORD_DELETEOBJECT,
    WMF_RECORD_DIBBITBLT,
    WMF_RECORD_DIBCREATEPATTERNBRUSH,
    WMF_RECORD_DIBSTRETCHBLT,
    WMF_RECORD_ELLIPSE,
    WMF_RECORD_EOF,
    WMF_RECORD_EXTTEXTOUT,
    WMF_RECORD_INTERSECTCLIPRECT,
    WMF_RECORD_LINETO,
    WMF_RECORD_MOVETO,
    WMF_RECORD_OFFSETWINDOWORG,
    WMF_RECORD_PATBLT,
    WMF_RECORD_PIE,
    WMF_RECORD_POLYGON,
    WMF_RECORD_POLYLINE,
    WMF_RECORD_POLYPOLYGON,
    WMF_RECORD_RECTANGLE,
    WMF_RECORD_RESTOREDC,
    WMF_RECORD_ROUNDRECT,
    WMF_RECORD_SAVEDC,
    WMF_RECORD_SCALEWINDOWEXT,
    WMF_RECORD_SELECTCLIPREGION,
    WMF_RECORD_SELECTOBJECT,
    WMF_RECORD_SELECTPALETTE,
    WMF_RECORD_SETBKCOLOR,
    WMF_RECORD_SETBKMODE,
    WMF_RECORD_SETMAPMODE,
    WMF_RECORD_SETPOLYFILLMODE,
    WMF_RECORD_SETTEXTALIGN,
    WMF_RECORD_SETTEXTCOLOR,
    WMF_RECORD_SETWINDOWEXT,
    WMF_RECORD_SETWINDOWORG,
    WMF_RECORD_STRETCHDIB,
    WMF_RECORD_TEXTOUT,
)
from .dib import decode_dib_to_image
from .state import GdiBrush, GdiFont, GdiPen, decode_gdi_text

if TYPE_CHECKING:
    from .player import MetafilePlayer


class WMFParser:
    """Parses 16-bit WMF records and invokes MetafilePlayer drawing methods."""

    @staticmethod
    def is_wmf(data: bytes) -> bool:
        """Check if data matches WMF placeable or standard header signature."""
        if len(data) < 18:
            return False
        # Placeable header key: 0x9AC6CDD7
        if struct.unpack_from("<I", data, 0)[0] == WMF_PLACEABLE_KEY:
            return True
        # Standard WMF header: file_type in (1, 2) and header_size == 9
        file_type, hdr_size = struct.unpack_from("<HH", data, 0)
        return file_type in (1, 2) and hdr_size == 9

    @classmethod
    def get_bounds_and_metrics(
        cls, data: bytes, max_px: int = 1200
    ) -> tuple[list[int], int, int, int] | None:
        """Extract bounding box [l, t, r, b], inch, and calculated canvas dimensions (cw, ch)."""
        if len(data) < 18:
            return None

        p = 0
        bbox: list[int] | None = None
        inch = 1440

        # Placeable header (22 bytes)
        if struct.unpack_from("<I", data, 0)[0] == WMF_PLACEABLE_KEY:
            left, top, right, bottom = struct.unpack_from("<hhhh", data, 6)
            inch_val = struct.unpack_from("<H", data, 14)[0]
            inch = inch_val if inch_val > 0 else 1440
            bbox = [left, top, right, bottom]
            p = 22

        if p + 4 > len(data):
            return None
        file_type, hdr_words = struct.unpack_from("<HH", data, p)
        if hdr_words < 9:
            return None
        p += hdr_words * 2

        # Pre-scan for SETWINDOWEXT/SETWINDOWORG if no placeable header
        if not bbox:
            win = None
            org = [0, 0]
            q = p
            while q + 6 <= len(data):
                size = struct.unpack_from("<I", data, q)[0] * 2
                fn = struct.unpack_from("<H", data, q + 4)[0]
                if size < 6 or fn == WMF_RECORD_EOF:
                    break
                if fn == WMF_RECORD_SETWINDOWEXT and not win and q + 10 <= len(data):
                    ey, ex = struct.unpack_from("<hh", data, q + 6)
                    win = [ex, ey]
                if fn == WMF_RECORD_SETWINDOWORG and not win and q + 10 <= len(data):
                    oy, ox = struct.unpack_from("<hh", data, q + 6)
                    org = [ox, oy]
                q += size

            if win:
                bbox = [org[0], org[1], org[0] + win[0], org[1] + win[1]]
            else:
                bbox = [0, 0, 1000, 1000]

        bw = abs(bbox[2] - bbox[0]) or 1
        bh = abs(bbox[3] - bbox[1]) or 1
        placeable = p == 22 + hdr_words * 2

        nat_w = (bw / inch) * 96 if placeable else bw
        nat_h = (bh / inch) * 96 if placeable else bh
        max_dim = max(nat_w, nat_h, 1)

        k = min(max_px / max_dim, 4.0) if placeable else (max_px / max_dim)
        cw = max(1, round(nat_w * k))
        ch = max(1, round(nat_h * k))

        return bbox, inch, cw, ch

    @classmethod
    def parse_and_play(cls, data: bytes, player: MetafilePlayer) -> bool:
        """Parse WMF binary data and play onto player."""
        metrics = cls.get_bounds_and_metrics(data, max_px=1200)
        if not metrics:
            return False

        bbox, inch, cw, ch = metrics
        player.setup_wmf_mapping(bbox)

        p = 0
        if struct.unpack_from("<I", data, 0)[0] == WMF_PLACEABLE_KEY:
            p = 22

        hdr_words = struct.unpack_from("<HH", data, p + 2)[0]
        n_objects = struct.unpack_from("<H", data, p + 10)[0]
        p += hdr_words * 2

        objs: list[Any] = [None] * max(n_objects, 1)

        def add_obj(o: Any) -> None:
            try:
                idx = objs.index(None)
                objs[idx] = o
            except ValueError:
                objs.append(o)

        record_count = 0
        while p + 6 <= len(data) and record_count < 200000:
            record_count += 1
            size = struct.unpack_from("<I", data, p)[0] * 2
            fn = struct.unpack_from("<H", data, p + 4)[0]
            if size < 6:
                break

            payload_off = p + 6
            s = player.state

            try:
                if fn == WMF_RECORD_EOF:
                    break
                elif fn == WMF_RECORD_SETBKMODE:
                    s.bk_mode = struct.unpack_from("<H", data, payload_off)[0]
                elif fn == WMF_RECORD_SETMAPMODE:
                    s.map_mode = struct.unpack_from("<H", data, payload_off)[0]
                elif fn == WMF_RECORD_SETPOLYFILLMODE:
                    s.fill = struct.unpack_from("<H", data, payload_off)[0]
                elif fn == WMF_RECORD_SETTEXTALIGN:
                    s.align = struct.unpack_from("<H", data, payload_off)[0]
                elif fn == WMF_RECORD_SETBKCOLOR:
                    s.bk = struct.unpack_from("<I", data, payload_off)[0]
                elif fn == WMF_RECORD_SETTEXTCOLOR:
                    s.text = struct.unpack_from("<I", data, payload_off)[0]
                elif fn == WMF_RECORD_SETWINDOWORG:
                    oy, ox = struct.unpack_from("<hh", data, payload_off)
                    s.wo = [float(ox), float(oy)]
                elif fn == WMF_RECORD_SETWINDOWEXT:
                    ey, ex = struct.unpack_from("<hh", data, payload_off)
                    s.we = [float(ex), float(ey)]
                elif fn == WMF_RECORD_OFFSETWINDOWORG:
                    dy, dx = struct.unpack_from("<hh", data, payload_off)
                    s.wo = [s.wo[0] + dx, s.wo[1] + dy]
                elif fn == WMF_RECORD_SCALEWINDOWEXT:
                    if s.we:
                        yd, ynum, xd, xnum = struct.unpack_from("<hhhh", data, payload_off)
                        s.we = [
                            (s.we[0] * xnum) / (xd or 1),
                            (s.we[1] * ynum) / (yd or 1),
                        ]
                elif fn == WMF_RECORD_SAVEDC:
                    player.save()
                elif fn == WMF_RECORD_RESTOREDC:
                    idx = struct.unpack_from("<h", data, payload_off)[0]
                    player.restore(idx)
                elif fn == WMF_RECORD_MOVETO:
                    my, mx = struct.unpack_from("<hh", data, payload_off)
                    s.x = float(mx)
                    s.y = float(my)
                elif fn == WMF_RECORD_LINETO:
                    ly, lx = struct.unpack_from("<hh", data, payload_off)
                    player.draw_poly([[s.x, s.y], [float(lx), float(ly)]], closed=False)
                    s.x = float(lx)
                    s.y = float(ly)
                elif fn == WMF_RECORD_INTERSECTCLIPRECT:
                    bottom, right, top, left = struct.unpack_from("<hhhh", data, payload_off)
                    player.intersect_clip(left, top, right, bottom)
                elif fn == WMF_RECORD_SELECTCLIPREGION:
                    s.clip = None
                elif fn == WMF_RECORD_RECTANGLE:
                    bottom, right, top, left = struct.unpack_from("<hhhh", data, payload_off)
                    player.draw_rect(left, top, right, bottom)
                elif fn == WMF_RECORD_ROUNDRECT:
                    rh, rw, bottom, right, top, left = struct.unpack_from(
                        "<hhhhhh", data, payload_off
                    )
                    player.draw_rect(left, top, right, bottom, rx=rw, ry=rh)
                elif fn == WMF_RECORD_ELLIPSE:
                    bottom, right, top, left = struct.unpack_from("<hhhh", data, payload_off)
                    player.draw_ellipse(left, top, right, bottom)
                elif fn in (WMF_RECORD_ARC, WMF_RECORD_PIE, WMF_RECORD_CHORD):
                    ye, xe, ys, xs, bottom, right, top, left = struct.unpack_from(
                        "<hhhhhhhh", data, payload_off
                    )
                    if fn == WMF_RECORD_PIE:
                        arc_kind = "pie"
                    elif fn == WMF_RECORD_CHORD:
                        arc_kind = "chord"
                    else:
                        arc_kind = "arc"
                    player.draw_arc(left, top, right, bottom, xs, ys, xe, ye, kind=arc_kind)
                elif fn in (WMF_RECORD_POLYGON, WMF_RECORD_POLYLINE):
                    cnt = struct.unpack_from("<h", data, payload_off)[0]
                    pts: list[list[float]] = []
                    for i in range(cnt):
                        px, py = struct.unpack_from("<hh", data, payload_off + 2 + i * 4)
                        pts.append([float(px), float(py)])
                    player.draw_poly(pts, closed=(fn == WMF_RECORD_POLYGON))
                elif fn == WMF_RECORD_POLYPOLYGON:
                    np = struct.unpack_from("<H", data, payload_off)[0]
                    counts = [
                        struct.unpack_from("<H", data, payload_off + 2 + i * 2)[0]
                        for i in range(np)
                    ]
                    k2 = payload_off + 2 + np * 2
                    polys: list[list[list[float]]] = []
                    for cnt in counts:
                        poly_pts: list[list[float]] = []
                        for _ in range(cnt):
                            px, py = struct.unpack_from("<hh", data, k2)
                            poly_pts.append([float(px), float(py)])
                            k2 += 4
                        polys.append(poly_pts)
                    player.draw_poly_poly(polys, closed=True)
                elif fn == WMF_RECORD_PATBLT:
                    rop, h, w, y, x = struct.unpack_from("<Ihhhh", data, payload_off)
                    player.pat_blt(rop, x, y, w, h)
                elif fn == WMF_RECORD_CREATEPENINDIRECT:
                    st, w, col = struct.unpack_from("<HhI", data, payload_off)
                    add_obj(GdiPen("pen", st, w, col))
                elif fn == WMF_RECORD_CREATEBRUSHINDIRECT:
                    st, col, hatch = struct.unpack_from("<HIH", data, payload_off)
                    add_obj(GdiBrush("brush", st, col, hatch))
                elif fn == WMF_RECORD_CREATEFONTINDIRECT:
                    fh, fw, esc, _, weight = struct.unpack_from("<hhhhh", data, payload_off)
                    italic = bool(data[payload_off + 10])
                    charset = data[payload_off + 13]
                    face_bytes = data[payload_off + 18 : min(payload_off + 50, p + size)]
                    z_idx = face_bytes.find(0)
                    if z_idx >= 0:
                        face_bytes = face_bytes[:z_idx]
                    face = decode_gdi_text(face_bytes, charset=charset)
                    add_obj(GdiFont("font", fh, weight, italic, face or "Arial", esc, charset))
                elif fn == WMF_RECORD_DIBCREATEPATTERNBRUSH:
                    usage_val = struct.unpack_from("<H", data, payload_off + 2)[0]
                    img = decode_dib_to_image(
                        data,
                        payload_off + 4,
                        bits_off=None,
                        usage=usage_val,
                        end=p + size,
                        ext_pal=s.palette,
                    )
                    add_obj(GdiBrush("brush", 5, 0x808080, pat=img, dib=True))
                elif fn == WMF_RECORD_CREATEPALETTE:
                    cnt = struct.unpack_from("<H", data, payload_off + 2)[0]
                    pal = []
                    for i in range(cnt):
                        off = payload_off + 4 + i * 4
                        pal.append([data[off], data[off + 1], data[off + 2]])
                    add_obj({"kind": "palette", "pal": pal})
                elif fn == WMF_RECORD_SELECTPALETTE:
                    idx = struct.unpack_from("<H", data, payload_off)[0]
                    if idx < len(objs) and objs[idx] and objs[idx].get("kind") == "palette":
                        s.palette = objs[idx]["pal"]
                elif fn == WMF_RECORD_SELECTOBJECT:
                    idx = struct.unpack_from("<H", data, payload_off)[0]
                    if idx < len(objs) and objs[idx]:
                        obj = objs[idx]
                        if isinstance(obj, GdiPen):
                            s.pen = obj
                        elif isinstance(obj, GdiBrush):
                            s.brush = obj
                        elif isinstance(obj, GdiFont):
                            s.font = obj
                elif fn == WMF_RECORD_DELETEOBJECT:
                    idx = struct.unpack_from("<H", data, payload_off)[0]
                    if idx < len(objs):
                        objs[idx] = None
                elif fn == WMF_RECORD_TEXTOUT:
                    cnt = struct.unpack_from("<h", data, payload_off)[0]
                    text_bytes = data[payload_off + 2 : payload_off + 2 + cnt]
                    txt = decode_gdi_text(text_bytes, charset=s.font.charset, face=s.font.face)
                    off = 2 + ((cnt + 1) // 2) * 2
                    ty, tx = struct.unpack_from("<hh", data, payload_off + off)
                    player.draw_text(tx, ty, txt)
                elif fn == WMF_RECORD_EXTTEXTOUT:
                    ty, tx, cnt, opts = struct.unpack_from("<hhhh", data, payload_off)
                    off = payload_off + 8 + (8 if (opts & 6) else 0)
                    text_bytes = data[off : off + cnt]
                    txt = decode_gdi_text(text_bytes, charset=s.font.charset, face=s.font.face)
                    off += cnt + (cnt & 1)
                    dxs = []
                    if off + cnt * 2 <= p + size:
                        for i in range(cnt):
                            dxs.append(struct.unpack_from("<h", data, off + i * 2)[0])
                    player.draw_text(tx, ty, txt, dxs=dxs if len(dxs) == cnt else None)
                elif fn == WMF_RECORD_STRETCHDIB:
                    usage = struct.unpack_from("<H", data, payload_off + 4)[0]
                    img = decode_dib_to_image(
                        data,
                        payload_off + 22,
                        bits_off=None,
                        usage=usage,
                        end=p + size,
                        ext_pal=s.palette,
                    )
                    rop = struct.unpack_from("<I", data, payload_off)[0]
                    src_y, src_x, src_h, src_w = struct.unpack_from("<hhhh", data, payload_off + 6)
                    dst_y, dst_x, dst_h, dst_w = struct.unpack_from("<hhhh", data, payload_off + 14)
                    player.draw_blit(
                        img, src_x, src_y, src_w, src_h, dst_x, dst_y, dst_w, dst_h, rop
                    )
                elif fn == WMF_RECORD_DIBSTRETCHBLT:
                    if size > 6 + 22:
                        img = decode_dib_to_image(
                            data,
                            payload_off + 20,
                            bits_off=None,
                            usage=0,
                            end=p + size,
                            ext_pal=s.palette,
                        )
                        rop = struct.unpack_from("<I", data, payload_off)[0]
                        src_y, src_x, src_h, src_w = struct.unpack_from(
                            "<hhhh", data, payload_off + 4
                        )
                        dst_y, dst_x, dst_h, dst_w = struct.unpack_from(
                            "<hhhh", data, payload_off + 12
                        )
                        player.draw_blit(
                            img, src_x, src_y, src_w, src_h, dst_x, dst_y, dst_w, dst_h, rop
                        )
                elif fn == WMF_RECORD_DIBBITBLT:
                    if size > 6 + 18:
                        img = decode_dib_to_image(
                            data,
                            payload_off + 16,
                            bits_off=None,
                            usage=0,
                            end=p + size,
                            ext_pal=s.palette,
                        )
                        rop = struct.unpack_from("<I", data, payload_off)[0]
                        src_y, src_x = struct.unpack_from("<hh", data, payload_off + 4)
                        h, w = struct.unpack_from("<hh", data, payload_off + 8)
                        dst_y, dst_x = struct.unpack_from("<hh", data, payload_off + 12)
                        player.draw_blit(img, src_x, src_y, w, h, dst_x, dst_y, w, h, rop)
            except Exception:
                pass

            p += size

        return True
