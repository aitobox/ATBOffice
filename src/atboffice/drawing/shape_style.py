"""Qt-free DrawingML shape style resolution shared by the document readers.

Turns a shape's ``spPr`` and its ``style`` references (``a:lnRef``, ``a:fillRef``,
``a:fontRef``) into plain values: preset or custom geometry, a :class:`DmlFill`
and a :class:`DmlLine`. Painting is done with
``geometry_helper.create_shape_path`` by each application.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from atboffice.drawing.dml import (
    DmlFill,
    child,
    first_color,
    local_name,
    parse_cust_geom,
    parse_fill,
)
from atboffice.vfs import etree as ET

EMU_PER_PT = 12700.0

# Office theme line style list (a:lnStyleLst) widths in points, by lnRef idx.
THEME_LINE_WIDTHS_PT: dict[int, float] = {1: 0.75, 2: 2.0, 3: 3.0}

_DASHES = {
    "solid": "solid",
    "dot": "dot",
    "sysDot": "dot",
    "dash": "dash",
    "sysDash": "dash",
    "lgDash": "dash",
    "dashDot": "dashDot",
    "sysDashDot": "dashDot",
    "lgDashDot": "dashDot",
    "lgDashDotDot": "dashDotDot",
    "sysDashDotDot": "dashDotDot",
}


@dataclass
class DmlLine:
    """A resolved DrawingML outline; ``visible`` is false for ``noFill`` / no line."""

    visible: bool = False
    color: str = "#000000"
    alpha: float = 1.0
    width: float = 0.75  # points
    dash: str = "solid"  # solid, dot, dash, dashDot, dashDotDot


def style_ref(style: ET.Element | None, name: str) -> tuple[int, ET.Element | None]:
    """Return ``(idx, element)`` of a ``wps:style``/``p:style`` reference; idx -1 if absent."""
    ref = child(style, name)
    if ref is None:
        return -1, None
    try:
        return int(ref.get("idx", "0")), ref
    except ValueError:
        return 0, ref


def parse_shape_geometry(
    sp_pr: ET.Element | None,
) -> tuple[str, dict[str, Any], dict[str, list[dict]] | None]:
    """Return ``(preset, adjustments, custom_path)`` for a shape's ``spPr``.

    Defaults to ``"rect"``; a ``custGeom`` with evaluable points yields ``"custom"``.
    """
    geom, adj, custom = "rect", {}, None
    prst = child(sp_pr, "prstGeom")
    cust = child(sp_pr, "custGeom")
    if prst is not None:
        geom = prst.get("prst", "rect") or "rect"
        av = child(prst, "avLst")
        for gd in av if av is not None else []:
            fmla = (gd.get("fmla") or "").split()
            if len(fmla) == 2 and fmla[0] == "val":
                try:
                    adj[gd.get("name", "adj")] = float(fmla[1])
                except ValueError:
                    continue
    elif cust is not None:
        custom = parse_cust_geom(cust)
        geom = "custom" if custom else "rect"
    return geom, adj, custom


def resolve_shape_fill(
    sp_pr: ET.Element | None,
    style: ET.Element | None,
    theme: Mapping[str, str],
    group_fill: DmlFill | None = None,
) -> DmlFill:
    """Explicit ``spPr`` fill, else the style's ``fillRef`` (idx 0 = none); never ``None``."""
    fill = parse_fill(sp_pr, theme, group_fill)
    if fill is not None:
        return fill
    idx, ref = style_ref(style, "fillRef")
    res = first_color(ref, theme) if idx > 0 else None
    if res is None:
        return DmlFill(kind="none")
    return DmlFill(kind="solid", color=res[0], alpha=res[1])


def resolve_shape_line(
    sp_pr: ET.Element | None,
    style: ET.Element | None,
    theme: Mapping[str, str],
) -> DmlLine:
    """Outline from ``a:ln`` with ``lnRef`` fallback; no line when neither gives one."""
    idx, ref = style_ref(style, "lnRef")
    ref_color = first_color(ref, theme) if idx > 0 else None
    line = DmlLine(
        visible=ref_color is not None,
        color=ref_color[0] if ref_color else "#000000",
        alpha=ref_color[1] if ref_color else 1.0,
        width=THEME_LINE_WIDTHS_PT.get(idx, 0.75),
    )
    ln = child(sp_pr, "ln")
    if ln is None:
        return line
    try:
        w = int(ln.get("w", "0") or "0")
    except ValueError:
        w = 0
    if w > 0:
        line.width = w / EMU_PER_PT
    for c in ln:
        name = local_name(c.tag)
        if name == "noFill":
            line.visible = False
        elif name in ("solidFill", "gradFill"):
            if name == "gradFill":
                gs = child(child(c, "gsLst"), "gs")
                res = first_color(gs, theme)
            else:
                res = first_color(c, theme)
            if res is not None:
                line.color, line.alpha, line.visible = res[0], res[1], True
        elif name == "prstDash":
            line.dash = _DASHES.get(c.get("val", "solid"), "solid")
    return line


def font_ref_color(style: ET.Element | None, theme: Mapping[str, str]) -> str | None:
    """Return the ``fontRef`` text color of a shape style, if any."""
    res = first_color(style_ref(style, "fontRef")[1], theme)
    return res[0] if res else None
