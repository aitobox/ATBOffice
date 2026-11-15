"""Qt-free DrawingML helpers shared by the document readers.

Resolves DrawingML color elements (``a:srgbClr``, ``a:schemeClr`` ...) and fill
elements (``a:solidFill``, ``a:gradFill`` ...) into plain values, and converts
``a:custGeom`` path lists with literal coordinates into the ``custom_path``
dictionary understood by ``geometry_helper.create_shape_path``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from atboffice.modules.presentation.models.designs import apply_color_mods
from atboffice.modules.spreadsheet.models.color_utils import (
    DEFAULT_THEME_COLORS,
    THEME_COLOR_ORDER,
)

# Spreadsheet/default color map: text/background aliases -> theme slots.
SCHEME_ALIASES: dict[str, str] = {"tx1": "dk1", "bg1": "lt1", "tx2": "dk2", "bg2": "lt2"}

PRESET_COLORS: dict[str, str] = {
    "black": "#000000",
    "white": "#FFFFFF",
    "red": "#FF0000",
    "green": "#008000",
    "lime": "#00FF00",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "orange": "#FFA500",
    "gray": "#808080",
    "grey": "#808080",
    "ltGray": "#D3D3D3",
    "dkGray": "#A9A9A9",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "navy": "#000080",
    "purple": "#800080",
    "silver": "#C0C0C0",
    "maroon": "#800000",
}

COLOR_TAGS = ("srgbClr", "schemeClr", "sysClr", "prstClr", "scrgbClr", "hslClr")
FILL_TAGS = ("noFill", "solidFill", "gradFill", "pattFill", "grpFill", "blipFill")


@dataclass
class DmlFill:
    """A resolved DrawingML fill."""

    kind: str = "solid"  # "none", "solid", "gradient", "pattern"
    color: str = "#000000"
    alpha: float = 1.0
    stops: list[tuple[float, str, float]] = field(default_factory=list)  # (pos 0..1, color, alpha)
    angle: float = 90.0  # gradient direction in degrees, clockwise from +x (y down)
    pattern: str = ""
    bg_color: str = "#FFFFFF"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def child(el: ET.Element | None, name: str) -> ET.Element | None:
    if el is None:
        return None
    for c in el:
        if local_name(c.tag) == name:
            return c
    return None


def theme_map(theme_colors: Sequence[str] | None) -> dict[str, str]:
    """Map theme slot names (``accent1`` ...) to ``#RRGGBB`` from an ordered color list."""
    if not theme_colors:
        theme_colors = DEFAULT_THEME_COLORS
    return {name: col for name, col in zip(THEME_COLOR_ORDER, theme_colors)}


def _pct(el: ET.Element, default: float = 0.0) -> float:
    raw = el.get("val")
    try:
        return float(raw) / 100000.0 if raw is not None else default
    except ValueError:
        return default


def resolve_color(
    el: ET.Element | None,
    theme: Mapping[str, str],
    ph_color: tuple[str, float] | None = None,
) -> tuple[str, float] | None:
    """Resolve a DrawingML color element to ``(#RRGGBB, alpha)``; ``None`` if unknown."""
    if el is None:
        return None
    tag = local_name(el.tag)
    base: str | None = None
    alpha = 1.0
    if tag == "srgbClr":
        val = (el.get("val") or "").strip()
        if len(val) == 6:
            base = f"#{val.upper()}"
    elif tag == "schemeClr":
        val = el.get("val") or ""
        if val == "phClr":
            if ph_color is None:
                return None
            base, alpha = ph_color
        else:
            base = theme.get(SCHEME_ALIASES.get(val, val))
    elif tag == "sysClr":
        last = (el.get("lastClr") or "").strip()
        if len(last) == 6:
            base = f"#{last.upper()}"
        else:
            base = "#FFFFFF" if (el.get("val") or "").lower() == "window" else "#000000"
    elif tag == "prstClr":
        base = PRESET_COLORS.get(el.get("val") or "")
    elif tag == "scrgbClr":
        try:
            rgb = [float(el.get(k, "0")) / 100000.0 for k in ("r", "g", "b")]
        except ValueError:
            return None
        comps = [
            round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055))
            for c in (max(0.0, min(1.0, v)) for v in rgb)
        ]
        base = "#{:02X}{:02X}{:02X}".format(*comps)
    if base is None:
        return None

    mods: list[dict[str, float | str]] = []
    for m in el:
        name = local_name(m.tag)
        if name == "alpha":
            alpha = _pct(m, 1.0)
        elif name == "alphaMod":
            alpha *= _pct(m, 1.0)
        elif name == "alphaOff":
            alpha += _pct(m)
        else:
            try:
                mods.append({"name": name, "val": float(m.get("val", "0"))})
            except ValueError:
                continue
    return apply_color_mods(base, mods), max(0.0, min(1.0, alpha))


def first_color(
    el: ET.Element | None,
    theme: Mapping[str, str],
    ph_color: tuple[str, float] | None = None,
) -> tuple[str, float] | None:
    """Resolve the first color child of ``el`` (e.g. a ``solidFill`` or ``fillRef``)."""
    if el is None:
        return None
    for c in el:
        if local_name(c.tag) in COLOR_TAGS:
            return resolve_color(c, theme, ph_color)
    return None


def parse_fill_element(
    el: ET.Element,
    theme: Mapping[str, str],
    group_fill: DmlFill | None = None,
    ph_color: tuple[str, float] | None = None,
) -> DmlFill | None:
    """Resolve one fill element (``solidFill``, ``gradFill`` ...)."""
    tag = local_name(el.tag)
    if tag == "noFill":
        return DmlFill(kind="none")
    if tag == "grpFill":
        return group_fill
    if tag == "solidFill":
        res = first_color(el, theme, ph_color)
        if res is None:
            return None
        return DmlFill(kind="solid", color=res[0], alpha=res[1])
    if tag == "gradFill":
        stops: list[tuple[float, str, float]] = []
        gs_lst = child(el, "gsLst")
        for gs in gs_lst if gs_lst is not None else []:
            if local_name(gs.tag) != "gs":
                continue
            res = first_color(gs, theme, ph_color)
            if res is None:
                continue
            try:
                pos = max(0.0, min(1.0, float(gs.get("pos", "0")) / 100000.0))
            except ValueError:
                pos = 0.0
            stops.append((pos, res[0], res[1]))
        if not stops:
            return None
        stops.sort(key=lambda s: s[0])
        angle = 90.0 if child(el, "path") is not None else 0.0
        lin = child(el, "lin")
        if lin is not None:
            try:
                angle = float(lin.get("ang", "0")) / 60000.0
            except ValueError:
                angle = 0.0
        return DmlFill(
            kind="gradient", color=stops[0][1], alpha=stops[0][2], stops=stops, angle=angle
        )
    if tag == "pattFill":
        fg = first_color(child(el, "fgClr"), theme, ph_color) or ("#000000", 1.0)
        bg = first_color(child(el, "bgClr"), theme, ph_color) or ("#FFFFFF", 1.0)
        return DmlFill(
            kind="pattern",
            color=fg[0],
            alpha=fg[1],
            pattern=el.get("prst", "pct50"),
            bg_color=bg[0],
        )
    return None


def parse_fill(
    sp_pr: ET.Element | None,
    theme: Mapping[str, str],
    group_fill: DmlFill | None = None,
) -> DmlFill | None:
    """Return the explicit fill of a ``spPr``/``grpSpPr`` element, or ``None`` if absent."""
    if sp_pr is None:
        return None
    for c in sp_pr:
        if local_name(c.tag) in FILL_TAGS and local_name(c.tag) != "blipFill":
            return parse_fill_element(c, theme, group_fill)
    return None


def parse_cust_geom(cust: ET.Element | None) -> dict[str, list[dict]] | None:
    """Convert ``a:custGeom/a:pathLst`` with numeric points into a ``custom_path`` dict.

    Paths that reference guide names (formula-driven points) are skipped; returns
    ``None`` when nothing usable remains.
    """
    path_lst = child(cust, "pathLst")
    if path_lst is None:
        return None
    paths: list[dict] = []
    for p in path_lst:
        if local_name(p.tag) != "path":
            continue
        try:
            pw = float(p.get("w", "0"))
            ph = float(p.get("h", "0"))
            cmds: list[list] = []
            for cmd in p:
                op = local_name(cmd.tag)
                pts = [
                    (float(pt.get("x", "0")), float(pt.get("y", "0")))
                    for pt in cmd
                    if local_name(pt.tag) == "pt"
                ]
                if op == "moveTo" and pts:
                    cmds.append(["M", *pts[0]])
                elif op == "lnTo" and pts:
                    cmds.append(["L", *pts[0]])
                elif op == "cubicBezTo" and len(pts) >= 3:
                    cmds.append(["C", *pts[0], *pts[1], *pts[2]])
                elif op == "quadBezTo" and len(pts) >= 2:
                    cmds.append(["Q", *pts[0], *pts[1]])
                elif op == "arcTo":
                    cmds.append(
                        [
                            "A",
                            float(cmd.get("wR", "0")),
                            float(cmd.get("hR", "0")),
                            float(cmd.get("stAng", "0")) / 60000.0,
                            float(cmd.get("swAng", "0")) / 60000.0,
                        ]
                    )
                elif op == "close":
                    cmds.append(["Z"])
        except ValueError:
            continue  # guide-referenced coordinates: not evaluable here
        if cmds:
            paths.append({"w": pw, "h": ph, "cmds": cmds, "fill": p.get("fill", "norm")})
    return {"paths": paths} if paths else None
