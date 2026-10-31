"""Enhanced Metafile (EMF) 32-bit binary stream parser."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING, Any

from .constants import (
    EMF_SIGNATURE,
    EMR_ABORTPATH,
    EMR_ARC,
    EMR_ARCTO,
    EMR_BEGINPATH,
    EMR_BITBLT,
    EMR_CHORD,
    EMR_CLOSEFIGURE,
    EMR_CREATEBRUSHINDIRECT,
    EMR_CREATEDIBPATTERNBRUSHPT,
    EMR_CREATEPEN,
    EMR_DELETEOBJECT,
    EMR_ELLIPSE,
    EMR_ENDPATH,
    EMR_EOF,
    EMR_EXTCREATEFONTINDIRECTW,
    EMR_EXTCREATEPEN,
    EMR_EXTTEXTOUTA,
    EMR_EXTTEXTOUTW,
    EMR_FILLPATH,
    EMR_HEADER,
    EMR_INTERSECTCLIPRECT,
    EMR_LINETO,
    EMR_MODIFYWORLDTRANSFORM,
    EMR_MOVETOEX,
    EMR_PIE,
    EMR_POLYBEZIER,
    EMR_POLYBEZIER16,
    EMR_POLYBEZIERTO,
    EMR_POLYBEZIERTO16,
    EMR_POLYGON,
    EMR_POLYGON16,
    EMR_POLYLINE,
    EMR_POLYLINE16,
    EMR_POLYLINETO,
    EMR_POLYLINETO16,
    EMR_POLYPOLYGON,
    EMR_POLYPOLYGON16,
    EMR_POLYPOLYLINE,
    EMR_POLYPOLYLINE16,
    EMR_RECTANGLE,
    EMR_RESTOREDC,
    EMR_ROUNDRECT,
    EMR_SAVEDC,
    EMR_SELECTCLIPPATH,
    EMR_SELECTOBJECT,
    EMR_SETBKCOLOR,
    EMR_SETBKMODE,
    EMR_SETMAPMODE,
    EMR_SETPOLYFILLMODE,
    EMR_SETTEXTALIGN,
    EMR_SETTEXTCOLOR,
    EMR_SETVIEWPORTEXTEX,
    EMR_SETVIEWPORTORGEX,
    EMR_SETWINDOWEXTEX,
    EMR_SETWINDOWORGEX,
    EMR_SETWORLDTRANSFORM,
    EMR_STRETCHBLT,
    EMR_STRETCHDIBITS,
    EMR_STROKEANDFILLPATH,
    EMR_STROKEPATH,
    STOCK_OBJECTS,
)
from .dib import decode_dib_to_image
from .state import GdiBrush, GdiFont, GdiPen

if TYPE_CHECKING:
    from .player import MetafilePlayer


def _mul_matrix(a: list[float], b: list[float]) -> list[float]:
    """Multiply two 2D affine transformation matrices [m11, m12, m21, m22, dx, dy]."""
    return [
        a[0] * b[0] + a[1] * b[2],
        a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2],
        a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4],
        a[4] * b[1] + a[5] * b[3] + b[5],
    ]


class EMFParser:
    """Parses 32-bit EMF records and invokes MetafilePlayer drawing methods."""

    @staticmethod
    def is_emf(data: bytes) -> bool:
        """Check if data matches standard 32-bit EMF header signature."""
        if len(data) < 88:
            return False
        rec_type = struct.unpack_from("<I", data, 0)[0]
        sig = struct.unpack_from("<I", data, 40)[0]
        return rec_type == EMR_HEADER and sig == EMF_SIGNATURE

    @classmethod
    def get_bounds_and_metrics(
        cls, data: bytes, max_px: int = 1200
    ) -> tuple[list[float], int, int] | None:
        """Extract frame/bounds metrics and calculated canvas dimensions (cw, ch)."""
        if not cls.is_emf(data):
            return None

        bounds = struct.unpack_from("<iiii", data, 8)
        frame = struct.unpack_from("<iiii", data, 24)
        dev_px = struct.unpack_from("<ii", data, 72)
        dev_mm = struct.unpack_from("<ii", data, 80)

        px_per_mm_x = (dev_px[0] / dev_mm[0]) if dev_mm[0] > 0 else (96.0 / 25.4)
        px_per_mm_y = (dev_px[1] / dev_mm[1]) if dev_mm[1] > 0 else (96.0 / 25.4)

        fr = [
            (frame[0] / 100.0) * px_per_mm_x,
            (frame[1] / 100.0) * px_per_mm_y,
            (frame[2] / 100.0) * px_per_mm_x,
            (frame[3] / 100.0) * px_per_mm_y,
        ]

        if not (fr[2] - fr[0] > 0) or not (fr[3] - fr[1] > 0):
            fr = [float(bounds[0]), float(bounds[1]), float(bounds[2] + 1), float(bounds[3] + 1)]

        fw = fr[2] - fr[0]
        fh = fr[3] - fr[1]

        frame_w_mm = (frame[2] - frame[0]) / 100.0
        frame_h_mm = (frame[3] - frame[1]) / 100.0
        nat_w = (frame_w_mm / 25.4 * 96.0) if frame_w_mm > 0 else fw
        nat_h = (frame_h_mm / 25.4 * 96.0) if frame_h_mm > 0 else fh
        max_dim = max(nat_w, nat_h, 1.0)

        k = min(max_px / max_dim, 4.0) or 1.0
        cw = max(1, round(nat_w * k))
        ch = max(1, round(nat_h * k))

        return fr, cw, ch

    @classmethod
    def parse_and_play(cls, data: bytes, player: MetafilePlayer) -> bool:
        """Parse EMF binary data and play onto player."""
        metrics = cls.get_bounds_and_metrics(data, max_px=1200)
        if not metrics:
            return False

        fr, cw, ch = metrics
        player.setup_emf_mapping(fr)

        objs: dict[int, Any] = {}

        def select_object(ih: int) -> None:
            if ih & 0x80000000:
                stock_id = ih & 0x7FFFFFFF
                stock_data = STOCK_OBJECTS.get(stock_id)
                if not stock_data:
                    return
                kind = stock_data["kind"]
                if kind == "pen":
                    player.state.pen = GdiPen(
                        "pen",
                        stock_data.get("style", 0),
                        stock_data.get("w", 1),
                        stock_data.get("color", 0),
                    )
                elif kind == "brush":
                    player.state.brush = GdiBrush(
                        "brush",
                        stock_data.get("style", 0),
                        stock_data.get("color", 0xFFFFFF),
                    )
                elif kind == "font":
                    player.state.font = GdiFont(
                        "font",
                        stock_data.get("h", -12),
                        stock_data.get("w", 400),
                        face=stock_data.get("face", "Arial"),
                    )
                return

            o = objs.get(ih)
            if not o:
                return
            if isinstance(o, GdiPen):
                player.state.pen = o
            elif isinstance(o, GdiBrush):
                player.state.brush = o
            elif isinstance(o, GdiFont):
                player.state.font = o

        def pts16(off: int, cnt: int) -> list[list[float]]:
            res: list[list[float]] = []
            for i in range(cnt):
                x, y = struct.unpack_from("<hh", data, off + i * 4)
                res.append([float(x), float(y)])
            return res

        def pts32(off: int, cnt: int) -> list[list[float]]:
            res: list[list[float]] = []
            for i in range(cnt):
                x, y = struct.unpack_from("<ii", data, off + i * 8)
                res.append([float(x), float(y)])
            return res

        p = struct.unpack_from("<I", data, 4)[0]
        record_count = 0

        while p + 8 <= len(data) and record_count < 400000:
            record_count += 1
            rec_type, rec_size = struct.unpack_from("<II", data, p)
            if rec_size < 8 or p + rec_size > len(data) + 4:
                break

            d = p + 8
            s = player.state

            try:
                if rec_type == EMR_EOF:
                    break
                elif rec_type == EMR_SETWINDOWEXTEX:
                    ex, ey = struct.unpack_from("<ii", data, d)
                    s.we = [float(ex), float(ey)]
                elif rec_type == EMR_SETWINDOWORGEX:
                    ox, oy = struct.unpack_from("<ii", data, d)
                    s.wo = [float(ox), float(oy)]
                elif rec_type == EMR_SETVIEWPORTEXTEX:
                    vex, vey = struct.unpack_from("<ii", data, d)
                    s.ve = [float(vex), float(vey)]
                elif rec_type == EMR_SETVIEWPORTORGEX:
                    vox, voy = struct.unpack_from("<ii", data, d)
                    s.vo = [float(vox), float(voy)]
                elif rec_type == EMR_SETMAPMODE:
                    s.map_mode = struct.unpack_from("<I", data, d)[0]
                elif rec_type == EMR_SETBKMODE:
                    s.bk_mode = struct.unpack_from("<I", data, d)[0]
                elif rec_type == EMR_SETPOLYFILLMODE:
                    s.fill = struct.unpack_from("<I", data, d)[0]
                elif rec_type == EMR_SETTEXTALIGN:
                    s.align = struct.unpack_from("<I", data, d)[0]
                elif rec_type == EMR_SETTEXTCOLOR:
                    s.text = struct.unpack_from("<I", data, d)[0]
                elif rec_type == EMR_SETBKCOLOR:
                    s.bk = struct.unpack_from("<I", data, d)[0]
                elif rec_type == EMR_MOVETOEX:
                    s.x = float(struct.unpack_from("<i", data, d)[0])
                    s.y = float(struct.unpack_from("<i", data, d + 4)[0])
                    if player.in_path:
                        player.path_move_to(s.x, s.y)
                elif rec_type == EMR_LINETO:
                    lx = float(struct.unpack_from("<i", data, d)[0])
                    ly = float(struct.unpack_from("<i", data, d + 4)[0])
                    if player.in_path:
                        player.path_line_to(lx, ly)
                    else:
                        player.draw_poly([[s.x, s.y], [lx, ly]], closed=False)
                    s.x = lx
                    s.y = ly
                elif rec_type == EMR_SAVEDC:
                    player.save()
                elif rec_type == EMR_RESTOREDC:
                    rel = struct.unpack_from("<i", data, d)[0]
                    player.restore(rel)
                elif rec_type == EMR_SETWORLDTRANSFORM:
                    s.xf = list(struct.unpack_from("<ffffff", data, d))
                elif rec_type == EMR_MODIFYWORLDTRANSFORM:
                    m = list(struct.unpack_from("<ffffff", data, d))
                    mode = struct.unpack_from("<I", data, d + 24)[0]
                    if mode == 1:
                        s.xf = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
                    elif mode == 2:
                        s.xf = _mul_matrix(m, s.xf)
                    elif mode == 3:
                        s.xf = _mul_matrix(s.xf, m)
                    else:
                        s.xf = m
                elif rec_type == EMR_INTERSECTCLIPRECT:
                    cl, ct, cr, cb = struct.unpack_from("<iiii", data, d)
                    player.intersect_clip(cl, ct, cr, cb)
                elif rec_type == EMR_SELECTCLIPPATH:
                    mode = struct.unpack_from("<I", data, d)[0]
                    if mode in (0, 5):
                        s.clip = None
                elif rec_type == EMR_RECTANGLE:
                    rl, rt, rr, rb = struct.unpack_from("<iiii", data, d)
                    player.draw_rect(rl, rt, rr, rb)
                elif rec_type == EMR_ROUNDRECT:
                    rl, rt, rr, rb, rw, rh = struct.unpack_from("<iiiiii", data, d)
                    player.draw_rect(rl, rt, rr, rb, rx=rw, ry=rh)
                elif rec_type == EMR_ELLIPSE:
                    el, et, er, eb = struct.unpack_from("<iiii", data, d)
                    player.draw_ellipse(el, et, er, eb)
                elif rec_type in (EMR_ARC, EMR_CHORD, EMR_PIE, EMR_ARCTO):
                    al, at, ar, ab, xs, ys, xe, ye = struct.unpack_from("<iiiiiiii", data, d)
                    if rec_type == EMR_PIE:
                        arc_kind = "pie"
                    elif rec_type == EMR_CHORD:
                        arc_kind = "chord"
                    else:
                        arc_kind = "arc"
                    player.draw_arc(al, at, ar, ab, xs, ys, xe, ye, kind=arc_kind)
                elif rec_type in (EMR_POLYGON, EMR_POLYLINE):
                    cnt = struct.unpack_from("<I", data, d + 16)[0]
                    player.draw_poly(pts32(d + 20, cnt), closed=(rec_type == EMR_POLYGON))
                elif rec_type in (EMR_POLYGON16, EMR_POLYLINE16):
                    cnt = struct.unpack_from("<I", data, d + 16)[0]
                    player.draw_poly(pts16(d + 20, cnt), closed=(rec_type == EMR_POLYGON16))
                elif rec_type == EMR_POLYBEZIER:
                    cnt = struct.unpack_from("<I", data, d + 16)[0]
                    player.draw_bezier(pts32(d + 20, cnt), from_current=False)
                elif rec_type == EMR_POLYBEZIER16:
                    cnt = struct.unpack_from("<I", data, d + 16)[0]
                    player.draw_bezier(pts16(d + 20, cnt), from_current=False)
                elif rec_type == EMR_POLYBEZIERTO:
                    cnt = struct.unpack_from("<I", data, d + 16)[0]
                    player.draw_bezier(pts32(d + 20, cnt), from_current=True)
                elif rec_type == EMR_POLYBEZIERTO16:
                    cnt = struct.unpack_from("<I", data, d + 16)[0]
                    player.draw_bezier(pts16(d + 20, cnt), from_current=True)
                elif rec_type in (EMR_POLYLINETO, EMR_POLYLINETO16):
                    cnt = struct.unpack_from("<I", data, d + 16)[0]
                    poly_pts = (
                        pts32(d + 20, cnt) if rec_type == EMR_POLYLINETO else pts16(d + 20, cnt)
                    )
                    if player.in_path:
                        for q in poly_pts:
                            player.path_line_to(q[0], q[1])
                    else:
                        player.draw_poly([[s.x, s.y]] + poly_pts, closed=False)
                    if cnt > 0:
                        s.x = poly_pts[-1][0]
                        s.y = poly_pts[-1][1]
                elif rec_type in (
                    EMR_POLYPOLYLINE,
                    EMR_POLYPOLYGON,
                    EMR_POLYPOLYLINE16,
                    EMR_POLYPOLYGON16,
                ):
                    np = struct.unpack_from("<I", data, d + 16)[0]
                    counts = [struct.unpack_from("<I", data, d + 24 + i * 4)[0] for i in range(np)]
                    off_pts = d + 24 + np * 4
                    small = rec_type in (EMR_POLYPOLYLINE16, EMR_POLYPOLYGON16)
                    polys = []
                    for cnt in counts:
                        polys.append(pts16(off_pts, cnt) if small else pts32(off_pts, cnt))
                        off_pts += cnt * (4 if small else 8)
                    player.draw_poly_poly(
                        polys, closed=rec_type in (EMR_POLYPOLYGON, EMR_POLYPOLYGON16)
                    )
                elif rec_type == EMR_BEGINPATH:
                    player.begin_path()
                elif rec_type == EMR_ENDPATH:
                    player.end_path()
                elif rec_type == EMR_CLOSEFIGURE:
                    player.close_figure()
                elif rec_type == EMR_FILLPATH:
                    player.fill_path(mode="fill")
                elif rec_type == EMR_STROKEANDFILLPATH:
                    player.fill_path(mode="both")
                elif rec_type == EMR_STROKEPATH:
                    player.fill_path(mode="stroke")
                elif rec_type == EMR_ABORTPATH:
                    player.abort_path()
                elif rec_type == EMR_CREATEPEN:
                    ih = struct.unpack_from("<I", data, d)[0]
                    style = struct.unpack_from("<I", data, d + 4)[0]
                    w = struct.unpack_from("<i", data, d + 8)[0]
                    col = struct.unpack_from("<I", data, d + 16)[0]
                    objs[ih] = GdiPen("pen", style, w, col)
                elif rec_type == EMR_EXTCREATEPEN:
                    ih = struct.unpack_from("<I", data, d)[0]
                    st = struct.unpack_from("<I", data, d + 20)[0]
                    geometric = (st & 0xF0000) == 0x10000
                    pen_w = struct.unpack_from("<I", data, d + 24)[0] if geometric else 0
                    is_null_pen = struct.unpack_from("<I", data, d + 28)[0] == 1
                    pen_style = 5 if is_null_pen else (st & 0xFFFF)
                    pen_col = struct.unpack_from("<I", data, d + 32)[0]
                    objs[ih] = GdiPen("pen", pen_style, pen_w, pen_col)
                elif rec_type == EMR_CREATEBRUSHINDIRECT:
                    ih = struct.unpack_from("<I", data, d)[0]
                    style = struct.unpack_from("<I", data, d + 4)[0]
                    col = struct.unpack_from("<I", data, d + 8)[0]
                    hatch = struct.unpack_from("<I", data, d + 12)[0]
                    objs[ih] = GdiBrush("brush", style, col, hatch)
                elif rec_type == EMR_CREATEDIBPATTERNBRUSHPT:
                    ih = struct.unpack_from("<I", data, d)[0]
                    usage = struct.unpack_from("<I", data, d + 4)[0]
                    off_bmi = struct.unpack_from("<I", data, d + 8)[0]
                    off_bits = struct.unpack_from("<I", data, d + 16)[0]
                    img = decode_dib_to_image(data, p + off_bmi, bits_off=p + off_bits, usage=usage)
                    objs[ih] = GdiBrush("brush", 6, 0x808080, pat=img, dib=True)
                elif rec_type == EMR_EXTCREATEFONTINDIRECTW:
                    ih = struct.unpack_from("<I", data, d)[0]
                    lf = d + 4
                    fh = struct.unpack_from("<i", data, lf)[0]
                    esc = struct.unpack_from("<i", data, lf + 8)[0]
                    fw = struct.unpack_from("<i", data, lf + 16)[0]
                    italic = bool(data[lf + 20])
                    charset = data[lf + 23]
                    face_chars = []
                    for i in range(32):
                        ch = struct.unpack_from("<H", data, lf + 28 + i * 2)[0]
                        if ch == 0:
                            break
                        face_chars.append(chr(ch))
                    face_name = "".join(face_chars) or "Arial"
                    objs[ih] = GdiFont("font", fh, fw, italic, face_name, esc, charset)
                elif rec_type == EMR_SELECTOBJECT:
                    ih = struct.unpack_from("<I", data, d)[0]
                    select_object(ih)
                elif rec_type == EMR_DELETEOBJECT:
                    ih = struct.unpack_from("<I", data, d)[0]
                    objs.pop(ih, None)
                elif rec_type in (EMR_EXTTEXTOUTW, EMR_EXTTEXTOUTA):
                    em = d + 28
                    tx, ty, cnt, off_str, off_dx = (
                        struct.unpack_from("<i", data, em)[0],
                        struct.unpack_from("<i", data, em + 4)[0],
                        struct.unpack_from("<I", data, em + 8)[0],
                        struct.unpack_from("<I", data, em + 12)[0],
                        struct.unpack_from("<I", data, em + 32)[0],
                    )
                    if rec_type == EMR_EXTTEXTOUTW:
                        txt_chars = []
                        for i in range(cnt):
                            ch = struct.unpack_from("<H", data, p + off_str + i * 2)[0]
                            txt_chars.append(chr(ch))
                        txt = "".join(txt_chars)
                    else:
                        txt = data[p + off_str : p + off_str + cnt].decode(
                            "cp1252", errors="replace"
                        )

                    dxs = []
                    if off_dx > 0 and p + off_dx + cnt * 4 <= p + rec_size:
                        for i in range(cnt):
                            dxs.append(struct.unpack_from("<i", data, p + off_dx + i * 4)[0])
                    player.draw_text(tx, ty, txt, dxs=dxs if len(dxs) == cnt else None)
                elif rec_type == EMR_STRETCHDIBITS:
                    (
                        x_dst,
                        y_dst,
                        x_src,
                        y_src,
                        cx_src,
                        cy_src,
                    ) = struct.unpack_from("<iiiiii", data, d + 16)
                    off_bmi, off_bits, usage, rop, cx_dst, cy_dst = (
                        struct.unpack_from("<I", data, d + 40)[0],
                        struct.unpack_from("<I", data, d + 48)[0],
                        struct.unpack_from("<I", data, d + 56)[0],
                        struct.unpack_from("<I", data, d + 60)[0],
                        struct.unpack_from("<i", data, d + 64)[0],
                        struct.unpack_from("<i", data, d + 68)[0],
                    )
                    img = decode_dib_to_image(data, p + off_bmi, bits_off=p + off_bits, usage=usage)
                    player.draw_blit(
                        img, x_src, y_src, cx_src, cy_src, x_dst, y_dst, cx_dst, cy_dst, rop
                    )
                elif rec_type in (EMR_BITBLT, EMR_STRETCHBLT):
                    x_dst, y_dst, cx_dst, cy_dst = struct.unpack_from("<iiii", data, d + 16)
                    rop = struct.unpack_from("<I", data, d + 32)[0]
                    x_src, y_src = struct.unpack_from("<ii", data, d + 36)
                    usage, off_bmi, cb_bmi, off_bits = (
                        struct.unpack_from("<I", data, d + 68)[0],
                        struct.unpack_from("<I", data, d + 72)[0],
                        struct.unpack_from("<I", data, d + 76)[0],
                        struct.unpack_from("<I", data, d + 80)[0],
                    )
                    if cb_bmi == 0:
                        player.pat_blt(rop, x_dst, y_dst, cx_dst, cy_dst)
                    else:
                        img = decode_dib_to_image(
                            data, p + off_bmi, bits_off=p + off_bits, usage=usage
                        )
                        if rec_type == EMR_STRETCHBLT:
                            cx_src, cy_src = struct.unpack_from("<ii", data, d + 88)
                        else:
                            cx_src, cy_src = cx_dst, cy_dst
                        player.draw_blit(
                            img, x_src, y_src, cx_src, cy_src, x_dst, y_dst, cx_dst, cy_dst, rop
                        )
            except Exception:
                pass

            p += rec_size

        return True
