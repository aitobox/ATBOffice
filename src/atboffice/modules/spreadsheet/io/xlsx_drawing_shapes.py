"""SpreadsheetML drawing content parsing: pictures, shapes, connectors and groups.

Turns the content element of an ``xdr:*Anchor`` (``xdr:pic``, ``xdr:sp``,
``xdr:cxnSp``, ``xdr:grpSp``) into a :class:`FloatingObject`. Anchor geometry is
handled by the caller in ``xlsx_reader``.
"""

from __future__ import annotations

import zipfile
from collections.abc import Mapping
from dataclasses import dataclass

from atboffice.drawing.dml import (
    DmlFill,
    child,
    first_color,
    local_name,
    parse_cust_geom,
    parse_fill,
)
from atboffice.modules.spreadsheet.views.object_layer import FloatingObject
from atboffice.vfs import etree as ET

EMU_PER_PX = 9525
EMU_PER_PT = 12700

# Office theme line style list (a:lnStyleLst) widths in points, by lnRef idx.
_THEME_LINE_WIDTHS_PT = {1: 0.75, 2: 2.0, 3: 3.0}

SHAPE_TAGS = ("pic", "sp", "cxnSp", "grpSp", "graphicFrame")


@dataclass
class DrawingContext:
    """Shared state while parsing one drawing part."""

    zip_file: zipfile.ZipFile
    rels: Mapping[str, tuple[str, str]]
    theme: Mapping[str, str]


@dataclass
class Xfrm:
    """An ``a:xfrm`` in EMU (``ch_*`` only for group transforms)."""

    x: int = 0
    y: int = 0
    cx: int = 0
    cy: int = 0
    ch_x: int = 0
    ch_y: int = 0
    ch_cx: int = 0
    ch_cy: int = 0
    flip_h: bool = False
    flip_v: bool = False


def _int_attr(el: ET.Element | None, name: str) -> int:
    if el is None:
        return 0
    try:
        return int(el.get(name, "0"))
    except ValueError:
        return 0


def _bool_attr(el: ET.Element | None, name: str) -> bool:
    return el is not None and el.get(name, "0") in ("1", "true")


def first_shape_element(anchor_el: ET.Element) -> ET.Element | None:
    """Return the drawing content of an anchor, unwrapping ``mc:AlternateContent``."""
    for c in anchor_el:
        name = local_name(c.tag)
        if name in SHAPE_TAGS:
            return c
        if name == "AlternateContent":
            # Prefer the Fallback branch: it uses only core DrawingML.
            branches = [b for b in c if local_name(b.tag) == "Fallback"]
            branches += [b for b in c if local_name(b.tag) == "Choice"]
            for branch in branches:
                for g in branch:
                    if local_name(g.tag) in SHAPE_TAGS:
                        return g
    return None


def element_xfrm(el: ET.Element) -> Xfrm | None:
    """Return the transform from an element's ``spPr``/``grpSpPr``."""
    props = child(el, "grpSpPr") if local_name(el.tag) == "grpSp" else child(el, "spPr")
    if props is None and local_name(el.tag) == "graphicFrame":
        props = el  # xdr:graphicFrame carries xdr:xfrm directly
    xfrm = child(props, "xfrm")
    if xfrm is None:
        return None
    off, ext = child(xfrm, "off"), child(xfrm, "ext")
    ch_off, ch_ext = child(xfrm, "chOff"), child(xfrm, "chExt")
    return Xfrm(
        x=_int_attr(off, "x"),
        y=_int_attr(off, "y"),
        cx=_int_attr(ext, "cx"),
        cy=_int_attr(ext, "cy"),
        ch_x=_int_attr(ch_off, "x"),
        ch_y=_int_attr(ch_off, "y"),
        ch_cx=_int_attr(ch_ext, "cx"),
        ch_cy=_int_attr(ch_ext, "cy"),
        flip_h=_bool_attr(xfrm, "flipH"),
        flip_v=_bool_attr(xfrm, "flipV"),
    )


def _nv_props(el: ET.Element, default_name: str) -> tuple[int, str, ET.Element | None]:
    """Return (id, name, cNv*Pr element) from the element's non-visual properties."""
    for c in el:
        if local_name(c.tag).startswith("nv"):
            c_nv = child(c, "cNvPr")
            obj_id = _int_attr(c_nv, "id") or 1
            name = (c_nv.get("name") if c_nv is not None else None) or default_name
            specific = next(
                (g for g in c if local_name(g.tag).startswith("cNv") and g is not c_nv), None
            )
            return obj_id, name, specific
    return 1, default_name, None


def _apply_fill(obj: FloatingObject, fill: DmlFill | None) -> None:
    if fill is None or fill.kind == "none":
        obj.fill_type = "none"
        return
    obj.fill_type = fill.kind
    obj.fill_color = fill.color
    obj.fill_alpha = fill.alpha
    if fill.kind == "gradient":
        obj.gradient_stops = list(fill.stops)
        obj.gradient_angle = fill.angle
    elif fill.kind == "pattern":
        obj.pattern = fill.pattern
        obj.pattern_bg = fill.bg_color


def parse_shape_element(
    el: ET.Element, ctx: DrawingContext, group_fill: DmlFill | None = None
) -> FloatingObject | None:
    """Parse ``xdr:pic``/``xdr:sp``/``xdr:cxnSp``/``xdr:grpSp`` into a FloatingObject."""
    tag = local_name(el.tag)
    if tag == "pic":
        return _parse_pic(el, ctx)
    if tag in ("sp", "cxnSp"):
        return _parse_sp(el, ctx, group_fill, connector=(tag == "cxnSp"))
    if tag == "grpSp":
        return _parse_group(el, ctx, group_fill)
    return None


def _parse_group(el: ET.Element, ctx: DrawingContext, group_fill: DmlFill | None) -> FloatingObject:
    obj_id, name, _ = _nv_props(el, "Group")
    grp_pr = child(el, "grpSpPr")
    own_fill = parse_fill(grp_pr, ctx.theme, group_fill) or group_fill
    xf = element_xfrm(el) or Xfrm()
    ch_x, ch_y = (xf.ch_x, xf.ch_y) if xf.ch_cx and xf.ch_cy else (xf.x, xf.y)
    ch_cx, ch_cy = (xf.ch_cx, xf.ch_cy) if xf.ch_cx and xf.ch_cy else (xf.cx, xf.cy)

    group = FloatingObject(id=obj_id, name=name, kind="group", fill_type="none")
    group.line_visible = False
    for c in el:
        if local_name(c.tag) not in ("pic", "sp", "cxnSp", "grpSp"):
            continue
        sub = parse_shape_element(c, ctx, own_fill)
        if sub is None:
            continue
        cxf = element_xfrm(c)
        if cxf is not None and ch_cx > 0 and ch_cy > 0:
            sub.group_frac = (
                (cxf.x - ch_x) / ch_cx,
                (cxf.y - ch_y) / ch_cy,
                cxf.cx / ch_cx,
                cxf.cy / ch_cy,
            )
        else:
            sub.group_frac = (0.0, 0.0, 1.0, 1.0)
        sub.z_index = len(group.children)
        group.children.append(sub)
    return group


def _parse_pic(el: ET.Element, ctx: DrawingContext) -> FloatingObject:
    obj_id, name, c_nv_pic = _nv_props(el, "Picture")
    pic_locks = child(c_nv_pic, "picLocks")

    img_bytes: bytes | None = None
    img_mime = "image/png"
    blip = child(child(el, "blipFill"), "blip")
    if blip is not None:
        embed_id = next((v for k, v in blip.attrib.items() if local_name(k) == "embed"), None)
        if embed_id and embed_id in ctx.rels:
            target = ctx.rels[embed_id][1]
            if target in ctx.zip_file.namelist():
                img_bytes = ctx.zip_file.read(target)
                if target.lower().endswith((".jpg", ".jpeg")):
                    img_mime = "image/jpeg"

    obj = FloatingObject(
        id=obj_id,
        name=name,
        kind="image",
        image_data=img_bytes,
        image_mime=img_mime,
        fill_type="none",
        lock_aspect=_bool_attr(pic_locks, "noChangeAspect"),
    )
    _apply_line(obj, child(el, "spPr"), None, ctx)
    return obj


def _style_ref(style: ET.Element | None, name: str) -> tuple[int, ET.Element | None]:
    ref = child(style, name)
    if ref is None:
        return -1, None
    try:
        return int(ref.get("idx", "0")), ref
    except ValueError:
        return 0, ref


def _apply_line(
    obj: FloatingObject,
    sp_pr: ET.Element | None,
    style: ET.Element | None,
    ctx: DrawingContext,
) -> None:
    """Resolve outline from ``a:ln`` with ``lnRef`` style fallback; default is no line."""
    ln = child(sp_pr, "ln")
    ln_idx, ln_ref = _style_ref(style, "lnRef")
    ref_color = first_color(ln_ref, ctx.theme) if ln_idx > 0 else None

    visible = ref_color is not None
    color = ref_color[0] if ref_color else obj.line_color
    width_pt = _THEME_LINE_WIDTHS_PT.get(ln_idx, 0.75)

    if ln is not None:
        w = _int_attr(ln, "w")
        if w > 0:
            width_pt = w / EMU_PER_PT
        for c in ln:
            name = local_name(c.tag)
            if name == "noFill":
                visible = False
            elif name == "solidFill":
                res = first_color(c, ctx.theme)
                if res is not None:
                    color, visible = res[0], True
            elif name in ("headEnd", "tailEnd"):
                end_type = c.get("type", "none")
                if end_type and end_type != "none":
                    setattr(obj, "head_end" if name == "headEnd" else "tail_end", end_type)
    obj.line_visible = visible
    obj.line_color = color
    obj.line_width = max(0.5, width_pt)


def _parse_text(
    sp_el: ET.Element, ctx: DrawingContext, default_color: str
) -> tuple[str, int, str, str]:
    lines: list[str] = []
    font_sz, font_fam, txt_col = 11, "Calibri", default_color
    tx_body = child(sp_el, "txBody")
    for p_el in tx_body if tx_body is not None else []:
        if local_name(p_el.tag) != "p":
            continue
        parts: list[str] = []
        for r_el in p_el:
            if local_name(r_el.tag) not in ("r", "fld"):
                continue
            r_pr = child(r_el, "rPr")
            if r_pr is not None:
                sz = _int_attr(r_pr, "sz")
                if sz:
                    font_sz = max(6, sz // 100)
                latin = child(r_pr, "latin")
                face = latin.get("typeface") if latin is not None else None
                if face and not face.startswith("+"):
                    font_fam = face
                res = first_color(child(r_pr, "solidFill"), ctx.theme)
                if res is not None:
                    txt_col = res[0]
            t_el = child(r_el, "t")
            if t_el is not None and t_el.text:
                parts.append(t_el.text)
        lines.append("".join(parts))
    return "\n".join(lines), font_sz, font_fam, txt_col


_KIND_BY_PRESET = {
    "roundRect": "roundRect",
    "ellipse": "oval",
    "oval": "oval",
    "line": "line",
    "straightConnector1": "line",
    "rightArrow": "arrow",
    "arrow": "arrow",
}


def _parse_sp(
    el: ET.Element,
    ctx: DrawingContext,
    group_fill: DmlFill | None,
    connector: bool,
) -> FloatingObject:
    obj_id, name, c_nv_sp = _nv_props(el, "Connector" if connector else "Shape")
    sp_pr = child(el, "spPr")
    style = child(el, "style")

    geometry, adj, custom = "rect", {}, None
    prst = child(sp_pr, "prstGeom")
    cust = child(sp_pr, "custGeom")
    if prst is not None:
        geometry = prst.get("prst", "rect") or "rect"
        for gd in child(prst, "avLst") if child(prst, "avLst") is not None else []:
            fmla = (gd.get("fmla") or "").split()
            if len(fmla) == 2 and fmla[0] == "val":
                try:
                    adj[gd.get("name", "adj")] = float(fmla[1])
                except ValueError:
                    pass
    elif cust is not None:
        custom = parse_cust_geom(cust)
        geometry = "custom" if custom else "rect"

    obj = FloatingObject(id=obj_id, name=name, geometry=geometry, geometry_adj=adj)
    obj.custom_path = custom

    # Fill: explicit spPr fill, else the style's fillRef (idx 0 = no fill).
    fill = parse_fill(sp_pr, ctx.theme, group_fill)
    if fill is None:
        fill_idx, fill_ref = _style_ref(style, "fillRef")
        res = first_color(fill_ref, ctx.theme) if fill_idx > 0 else None
        fill = DmlFill(kind="solid", color=res[0], alpha=res[1]) if res else None
    if connector:
        fill = None
    _apply_fill(obj, fill)
    _apply_line(obj, sp_pr, style, ctx)

    xf = element_xfrm(el)
    if xf is not None:
        obj.flip_h, obj.flip_v = xf.flip_h, xf.flip_v

    font_ref = first_color(_style_ref(style, "fontRef")[1], ctx.theme)
    text, font_sz, font_fam, txt_col = _parse_text(el, ctx, font_ref[0] if font_ref else "#000000")
    obj.text, obj.font_size, obj.font_family, obj.text_color = text, font_sz, font_fam, txt_col

    is_tb = _bool_attr(c_nv_sp, "txBox")
    white = obj.fill_type == "solid" and obj.fill_color.upper() in ("#FFFFFF", "#FFF")
    if connector:
        obj.kind = "line"
    elif is_tb or (geometry == "rect" and text and (white or obj.fill_type == "none")):
        obj.kind = "textbox"
    else:
        obj.kind = _KIND_BY_PRESET.get(geometry, "rect")
    return obj


_SIGNATURE_ATTRS = (
    "id",
    "name",
    "kind",
    "from_point",
    "to_point",
    "text",
    "text_color",
    "font_size",
    "font_family",
    "fill_color",
    "fill_alpha",
    "fill_type",
    "line_color",
    "line_width",
    "line_visible",
    "geometry",
    "flip_h",
    "flip_v",
    "z_index",
)


def drawings_signature(drawings: list[FloatingObject] | None) -> tuple:
    """Fingerprint of the user-editable state of a sheet's drawings.

    The writer compares this with the fingerprint taken at load time: while it is
    unchanged, the original drawing part (with charts, SmartArt and anything else the
    model cannot express) is carried verbatim instead of being regenerated.
    """
    out = []
    for obj in drawings or []:
        values = []
        for attr in _SIGNATURE_ATTRS:
            v = getattr(obj, attr, None)
            if hasattr(v, "__dataclass_fields__"):
                v = tuple(getattr(v, f) for f in v.__dataclass_fields__)
            values.append(v)
        data = getattr(obj, "image_data", None)
        values.append(hash(data) if data else None)
        values.append(drawings_signature(getattr(obj, "children", None)))
        out.append(tuple(values))
    return tuple(out)
