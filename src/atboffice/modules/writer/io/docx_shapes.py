"""WordprocessingML shape parsing: ``wps:wsp`` shapes, ``wpg:wgp`` groups, VML frames.

Builds :class:`ShapeItem` objects (geometry, fill, outline, text box story) for
``DocxReader``. Colors resolve against the document theme; fills and outlines use
the shared Qt-free helpers in ``atboffice.drawing``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from atboffice.drawing.dml import DmlFill, child, local_name, parse_fill, theme_map
from atboffice.drawing.shape_style import (
    DmlLine,
    font_ref_color,
    parse_shape_geometry,
    resolve_shape_fill,
    resolve_shape_line,
)
from atboffice.modules.writer.models.document import Story
from atboffice.modules.writer.models.drawing import ShapeChild, ShapeItem
from atboffice.vfs import etree as ET

EMU_PER_PT = 12700.0
DEFAULT_INSETS = (7.2, 3.6, 7.2, 3.6)

# Blocks collector: (container element, out list) -> None. Supplied by DocxReader.
CollectBlocks = Callable[[ET.Element, list[Any]], None]
# Picture resolver: (pic element) -> word/ part path ("" if none). Supplied by DocxReader.
ResolveBlip = Callable[[ET.Element], str]


def load_theme_colors(theme_xml: bytes | None) -> dict[str, str]:
    """Theme slot -> ``#RRGGBB`` map from a theme part (Office defaults when missing)."""
    from atboffice.modules.spreadsheet.models.color_utils import parse_theme_xml

    parsed = parse_theme_xml(theme_xml or b"")
    return theme_map(parsed.get("colors"))


@dataclass
class Xfrm:
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    ch_x: float = 0.0
    ch_y: float = 0.0
    ch_w: float = 0.0
    ch_h: float = 0.0
    flip_h: bool = False
    flip_v: bool = False
    rot: float = 0.0


def _num(el: ET.Element | None, attr: str) -> float:
    if el is None:
        return 0.0
    try:
        return float(el.get(attr, "0") or "0")
    except ValueError:
        return 0.0


def parse_xfrm(sp_pr: ET.Element | None) -> Xfrm | None:
    """Read ``a:xfrm`` (offsets/extents in points); ``None`` when absent."""
    xf = child(sp_pr, "xfrm")
    if xf is None:
        return None
    off, ext = child(xf, "off"), child(xf, "ext")
    ch_off, ch_ext = child(xf, "chOff"), child(xf, "chExt")
    return Xfrm(
        x=_num(off, "x") / EMU_PER_PT,
        y=_num(off, "y") / EMU_PER_PT,
        w=_num(ext, "cx") / EMU_PER_PT,
        h=_num(ext, "cy") / EMU_PER_PT,
        ch_x=_num(ch_off, "x") / EMU_PER_PT,
        ch_y=_num(ch_off, "y") / EMU_PER_PT,
        ch_w=_num(ch_ext, "cx") / EMU_PER_PT,
        ch_h=_num(ch_ext, "cy") / EMU_PER_PT,
        flip_h=xf.get("flipH") in ("1", "true"),
        flip_v=xf.get("flipV") in ("1", "true"),
        rot=_num(xf, "rot") / 60000.0,
    )


def _body_insets(body_pr: ET.Element | None) -> tuple[float, float, float, float]:
    if body_pr is None:
        return DEFAULT_INSETS
    vals = []
    for attr, default in zip(("lIns", "tIns", "rIns", "bIns"), DEFAULT_INSETS):
        raw = body_pr.get(attr)
        try:
            vals.append(float(raw) / EMU_PER_PT if raw is not None else default)
        except ValueError:
            vals.append(default)
    return vals[0], vals[1], vals[2], vals[3]


def _text_story(txbx: ET.Element | None, collect: CollectBlocks) -> Story | None:
    content = child(txbx, "txbxContent")
    if content is None:
        return None
    blocks: list[Any] = []
    collect(content, blocks)
    return Story(kind="textbox", blocks=blocks)


def parse_wsp(
    wsp: ET.Element,
    width: float,
    height: float,
    theme: Mapping[str, str],
    collect: CollectBlocks,
    group_fill: DmlFill | None = None,
) -> ShapeItem:
    """Parse a ``wps:wsp`` into a :class:`ShapeItem` sized ``width`` x ``height`` points."""
    sp_pr = child(wsp, "spPr")
    style = child(wsp, "style")
    geom, adj, custom = parse_shape_geometry(sp_pr)
    xf = parse_xfrm(sp_pr)
    body_pr = child(wsp, "bodyPr")
    c_nv_pr = child(wsp, "cNvPr")
    return ShapeItem(
        name=(c_nv_pr.get("name", "") if c_nv_pr is not None else ""),
        width=width,
        height=height,
        rotation=xf.rot if xf else 0.0,
        geometry=geom,
        adjustments=adj,
        custom_path=custom,
        fill=resolve_shape_fill(sp_pr, style, theme, group_fill),
        line=resolve_shape_line(sp_pr, style, theme),
        flip_h=bool(xf and xf.flip_h),
        flip_v=bool(xf and xf.flip_v),
        story=_text_story(child(wsp, "txbx"), collect),
        insets=_body_insets(body_pr),
        v_anchor=(body_pr.get("anchor", "t") if body_pr is not None else "t") or "t",
        text_color=font_ref_color(style, theme),
    )


def _parse_pic_child(
    pic: ET.Element, width: float, height: float, resolve: ResolveBlip
) -> ShapeItem:
    sp_pr = child(pic, "spPr")
    geom, adj, custom = parse_shape_geometry(sp_pr)
    xf = parse_xfrm(sp_pr)
    return ShapeItem(
        width=width,
        height=height,
        rotation=xf.rot if xf else 0.0,
        geometry=geom,
        adjustments=adj,
        custom_path=custom,
        fill=DmlFill(kind="none"),
        line=DmlLine(),
        image_part=resolve(pic),
    )


def parse_group(
    grp: ET.Element,
    width: float,
    height: float,
    theme: Mapping[str, str],
    collect: CollectBlocks,
    resolve: ResolveBlip,
    group_fill: DmlFill | None = None,
) -> ShapeItem:
    """Parse ``wpg:wgp`` / ``wpg:grpSp`` / ``wpc:wpc`` into a group :class:`ShapeItem`.

    Children are mapped from the group's child coordinate space (``chOff``/``chExt``)
    into its ``width`` x ``height`` box.
    """
    grp_sp_pr = child(grp, "grpSpPr")
    xf = parse_xfrm(grp_sp_pr)
    own_fill = parse_fill(grp_sp_pr, theme, group_fill)
    fill_ctx = own_fill if own_fill is not None else group_fill
    ch_x = xf.ch_x if xf else 0.0
    ch_y = xf.ch_y if xf else 0.0
    sx = width / xf.ch_w if xf and xf.ch_w > 0 else 1.0
    sy = height / xf.ch_h if xf and xf.ch_h > 0 else 1.0

    group = ShapeItem(
        width=width,
        height=height,
        rotation=xf.rot if xf else 0.0,
        fill=DmlFill(kind="none"),
        line=DmlLine(),
        flip_h=bool(xf and xf.flip_h),
        flip_v=bool(xf and xf.flip_v),
    )
    if local_name(grp.tag) == "wpc":
        bg = child(grp, "bg")
        bg_fill = parse_fill(bg, theme) if bg is not None else None
        if bg_fill is not None:
            group.fill = bg_fill

    for c in grp:
        name = local_name(c.tag)
        if name not in ("wsp", "pic", "grpSp", "wgp", "cxnSp"):
            continue
        sp_pr = child(c, "spPr") if name not in ("grpSp", "wgp") else child(c, "grpSpPr")
        cx = parse_xfrm(sp_pr)
        if cx is None:
            continue
        cw, chh = cx.w * sx, cx.h * sy
        if name in ("grpSp", "wgp"):
            item = parse_group(c, cw, chh, theme, collect, resolve, fill_ctx)
        elif name == "pic":
            item = _parse_pic_child(c, cw, chh, resolve)
        else:
            item = parse_wsp(c, cw, chh, theme, collect, fill_ctx)
            if name == "cxnSp":
                item.fill = DmlFill(kind="none")
        group.children.append(
            ShapeChild(item=item, x=(cx.x - ch_x) * sx, y=(cx.y - ch_y) * sy)
        )
    return group


# ---------------------------------------------------------------------------
# VML
# ---------------------------------------------------------------------------

_VML_GEOMETRY = {"rect": "rect", "roundrect": "roundRect", "oval": "ellipse"}
_VML_COLOR_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_VML_NAMED = {
    "black": "#000000", "white": "#FFFFFF", "red": "#FF0000", "green": "#008000",
    "blue": "#0000FF", "yellow": "#FFFF00", "gray": "#808080", "silver": "#C0C0C0",
    "navy": "#000080", "maroon": "#800000", "purple": "#800080", "teal": "#008080",
    "lime": "#00FF00", "aqua": "#00FFFF", "fuchsia": "#FF00FF", "olive": "#808000",
}


def vml_color(raw: str | None) -> str | None:
    """Parse a VML color (``#d99594 [1941]``, ``#abc``, ``red``) to ``#RRGGBB``."""
    if not raw:
        return None
    m = _VML_COLOR_RE.search(raw)
    if m:
        hx = m.group(1)
        if len(hx) == 3:
            hx = "".join(ch * 2 for ch in hx)
        return f"#{hx.upper()}"
    return _VML_NAMED.get(raw.strip().split()[0].lower())


def _vml_length_pt(raw: str | None, default: float) -> float:
    if not raw:
        return default
    raw = raw.strip()
    units = {
        "emu": 1 / EMU_PER_PT,
        "pt": 1.0,
        "in": 72.0,
        "px": 0.75,
        "cm": 72.0 / 2.54,
        "mm": 72.0 / 25.4,
    }
    for unit, scale in units.items():
        if raw.endswith(unit):
            try:
                return float(raw[: -len(unit)]) * scale
            except ValueError:
                return default
    try:  # bare numbers are EMU for strokeweight
        return float(raw) / EMU_PER_PT
    except ValueError:
        return default


def _vml_inset(raw: str | None) -> tuple[float, float, float, float]:
    if not raw:
        return DEFAULT_INSETS
    parts = [p.strip() for p in raw.split(",")]
    vals = list(DEFAULT_INSETS)
    for i, p in enumerate(parts[:4]):
        if p:
            vals[i] = _vml_length_pt(p, vals[i])
    return vals[0], vals[1], vals[2], vals[3]


def is_vml_shape(shape: ET.Element) -> bool:
    """True for a VML shape that should paint as a :class:`ShapeItem` (not an image)."""
    if local_name(shape.tag) not in _VML_GEOMETRY:
        return False
    return not any(local_name(c.tag) == "imagedata" for c in shape.iter())


def parse_vml_shape(
    shape: ET.Element,
    width: float,
    height: float,
    collect: CollectBlocks,
    attr: Callable[[ET.Element, str], str | None],
) -> ShapeItem:
    """Parse ``v:rect`` / ``v:roundrect`` / ``v:oval`` with fill, stroke and text box."""
    filled = (attr(shape, "filled") or "t").lower() not in ("f", "false")
    stroked = (attr(shape, "stroked") or "t").lower() not in ("f", "false")
    fill_color = vml_color(attr(shape, "fillcolor")) or "#FFFFFF"
    stroke_color = vml_color(attr(shape, "strokecolor")) or "#000000"
    stroke_w = _vml_length_pt(attr(shape, "strokeweight"), 0.75)
    for c in shape:
        name = local_name(c.tag)
        if name == "fill":
            on = (attr(c, "on") or "t").lower()
            if on in ("f", "false"):
                filled = False
            fill_color = vml_color(attr(c, "color")) or fill_color
        elif name == "stroke":
            on = (attr(c, "on") or "t").lower()
            if on in ("f", "false"):
                stroked = False
            stroke_color = vml_color(attr(c, "color")) or stroke_color
            stroke_w = _vml_length_pt(attr(c, "weight"), stroke_w)

    textbox = next((c for c in shape if local_name(c.tag) == "textbox"), None)
    story = _text_story(textbox, collect) if textbox is not None else None
    insets = _vml_inset(attr(textbox, "inset")) if textbox is not None else DEFAULT_INSETS
    return ShapeItem(
        name=attr(shape, "id") or "",
        width=width,
        height=height,
        geometry=_VML_GEOMETRY[local_name(shape.tag)],
        fill=DmlFill(kind="solid", color=fill_color) if filled else DmlFill(kind="none"),
        line=DmlLine(visible=stroked, color=stroke_color, width=stroke_w),
        story=story,
        insets=insets,
    )
