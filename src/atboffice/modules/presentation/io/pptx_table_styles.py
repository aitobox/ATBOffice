"""PowerPoint table styles (``ppt/tableStyles.xml``): catalog, resolution and application.

Port of ``lectern/js/pptx-read.js`` (table styles section). A resolved style is a mapping
``part name -> {"fill": dict | None, "bd": {side: line}, "tx": {"b", "i", "color"}}`` where
the part names follow DrawingML (``wholeTbl``, ``band1H`` ... ``firstRow``) and the sides are
``left/right/top/bottom/insideH/insideV``.

Cells (plain dicts inside ``Shape.tbl["rows"][i]["cells"]``) receive:
``fill`` ``{"t": "solid", "c": str, "a": float}`` or ``{"t": "none"}``; ``bd`` ``{"l"|"r"|"t"|"b":
{"c": str | None, "w": float, "dash": str}}`` (``w == 0`` means "no border"); and ``own``
``{"fill": bool, "bd": [sides]}`` marking properties that came from the cell's own ``tcPr``.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

ColorFn = Callable[[ET.Element], tuple[str | None, float]]
LineFn = Callable[[ET.Element], dict[str, Any]]
HexFn = Callable[[str], str]

STYLE_PARTS = (
    "wholeTbl",
    "band1H",
    "band2H",
    "band1V",
    "band2V",
    "firstCol",
    "lastCol",
    "firstRow",
    "lastRow",
)

TABLE_GRID = "{5940675A-B579-460E-94D1-54222C63F5DA}"
NO_STYLE_NO_GRID = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"
MEDIUM_STYLE_2 = {
    "{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}": "accent1",
    "{21E4AEA4-8DFA-4A89-87EB-49C32662AFE8}": "accent2",
    "{F5AB1C69-6EDB-4FF4-983F-18BD219EF322}": "accent3",
    "{00A15C55-8517-42AA-B614-E9B94910E393}": "accent4",
    "{7DF18680-E054-41AD-8BC1-D1AEF772440D}": "accent5",
    "{93296810-A885-4BE3-A3E7-6D5BEEA58F35}": "accent6",
    "{073A0DAA-6AF3-43AB-8588-CEC1D06C72B9}": "dk1",
}

_FILL_TAGS = ("noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill")
_CELL_SIDES = (("l", "lnL"), ("r", "lnR"), ("t", "lnT"), ("b", "lnB"))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(elem: ET.Element | None, name: str) -> ET.Element | None:
    if elem is None:
        return None
    for c in elem:
        if _local(c.tag) == name:
            return c
    return None


def normalize_style_id(raw: str | None) -> str:
    return (raw or "").strip().upper()


@dataclass
class TableStyleCatalog:
    """Table styles declared in ``tableStyles.xml``, keyed by upper-cased style id."""

    styles: dict[str, ET.Element] = field(default_factory=dict)
    default_id: str = ""

    @classmethod
    def from_xml(cls, data: bytes | None) -> TableStyleCatalog:
        """Parse ``<a:tblStyleLst>``; raises ``ET.ParseError`` on malformed XML."""
        if not data:
            return cls()
        root = ET.fromstring(data)
        styles = {
            normalize_style_id(st.attrib.get("styleId")): st
            for st in root
            if _local(st.tag) == "tblStyle" and st.attrib.get("styleId")
        }
        return cls(styles=styles, default_id=normalize_style_id(root.attrib.get("def")))


def table_style_id(tbl_pr: ET.Element | None) -> str:
    """Return the ``tableStyleId`` of a ``<a:tblPr>`` (element text or ``val``), or ""."""
    sid = _child(tbl_pr, "tableStyleId")
    if sid is None:
        return ""
    return normalize_style_id(sid.text or sid.attrib.get("val"))


def _fill_from_container(container: ET.Element | None, color_of: ColorFn) -> dict[str, Any] | None:
    """Fill dict from the first DrawingML fill child of ``container`` (None if absent)."""
    if container is None:
        return None
    for c in container:
        tag = _local(c.tag)
        if tag == "noFill":
            return {"t": "none"}
        if tag == "solidFill":
            clr, alpha = color_of(c)
            return {"t": "solid", "c": clr or "#FFFFFF", "a": alpha}
        if tag == "gradFill":
            gs_lst = _child(c, "gsLst")
            first = next(
                (g for g in (gs_lst if gs_lst is not None else []) if _local(g.tag) == "gs"), None
            )
            if first is not None:
                clr, alpha = color_of(first)
                if clr:
                    return {"t": "solid", "c": clr, "a": alpha}
    return None


def parse_cell_properties(
    tc_pr: ET.Element | None, color_of: ColorFn, line_of: LineFn
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    """Return ``(fill, borders, own)`` for a ``<a:tcPr>``."""
    fill = _fill_from_container(tc_pr, color_of)
    bd: dict[str, dict[str, Any]] = {}
    for side, tag in _CELL_SIDES:
        ln = _child(tc_pr, tag)
        if ln is not None:
            bd[side] = line_of(ln)
    own = {"fill": fill is not None, "bd": list(bd)}
    return fill or {"t": "none"}, bd, own


def _style_part(el: ET.Element | None, color_of: ColorFn, line_of: LineFn) -> dict[str, Any] | None:
    if el is None:
        return None
    out: dict[str, Any] = {"fill": None, "bd": {}, "tx": {}}
    ts = _child(el, "tcTxStyle")
    if ts is not None:
        if ts.attrib.get("b"):
            out["tx"]["b"] = ts.attrib["b"] == "on"
        if ts.attrib.get("i"):
            out["tx"]["i"] = ts.attrib["i"] == "on"
        clr, _ = color_of(ts)
        if not clr:
            font_ref = _child(ts, "fontRef")
            if font_ref is not None:
                clr, _ = color_of(font_ref)
        if clr:
            out["tx"]["color"] = clr
    tcs = _child(el, "tcStyle")
    if tcs is not None:
        bdr = _child(tcs, "tcBdr")
        for side in ("left", "right", "top", "bottom", "insideH", "insideV"):
            e = _child(bdr, side)
            if e is None:
                continue
            ln = _child(e, "ln")
            ln_ref = _child(e, "lnRef")
            if ln is not None:
                out["bd"][side] = line_of(ln)
            elif ln_ref is not None:
                clr, _ = color_of(ln_ref)
                out["bd"][side] = {"c": clr or "tx1", "w": 1.0, "dash": "solid"}
        fill = _fill_from_container(_child(tcs, "fill"), color_of)
        if fill is None:
            fill_ref = _child(tcs, "fillRef")
            if fill_ref is not None:
                clr, alpha = color_of(fill_ref)
                if clr:
                    fill = {"t": "solid", "c": clr, "a": alpha}
        out["fill"] = fill
    return out


def builtin_style(
    style_id: str, scheme_hex: HexFn, tint: Callable[[str, float], str]
) -> dict[str, Any] | None:
    """Synthesize parts for the built-in styles PowerPoint does not always write out."""
    if style_id == TABLE_GRID:
        b = {"c": "tx1", "w": 1.0, "dash": "solid"}
        sides = {s: dict(b) for s in ("left", "right", "top", "bottom", "insideH", "insideV")}
        return {"wholeTbl": {"fill": None, "bd": sides, "tx": {"color": "tx1"}}}
    if style_id == NO_STYLE_NO_GRID:
        return {"wholeTbl": {"fill": None, "bd": {}, "tx": {"color": "tx1"}}}
    if style_id not in MEDIUM_STYLE_2:
        return None
    accent = MEDIUM_STYLE_2[style_id]
    base = scheme_hex(accent)
    thin = {"c": "lt1", "w": 1.0, "dash": "solid"}
    thick = {"c": "lt1", "w": 3.0, "dash": "solid"}

    def strong(bd: dict[str, Any]) -> dict[str, Any]:
        return {
            "fill": {"t": "solid", "c": accent, "a": 1.0},
            "bd": bd,
            "tx": {"b": True, "color": "lt1"},
        }

    band = {"fill": {"t": "solid", "c": tint(base, 40000), "a": 1.0}, "bd": {}, "tx": {}}
    return {
        "wholeTbl": {
            "fill": {"t": "solid", "c": tint(base, 20000), "a": 1.0},
            "bd": {s: dict(thin) for s in ("left", "right", "top", "bottom", "insideH", "insideV")},
            "tx": {"color": "dk1"},
        },
        "band1H": band,
        "band1V": copy.deepcopy(band),
        "firstCol": strong({}),
        "lastCol": strong({}),
        "lastRow": strong({"top": thick}),
        "firstRow": strong({"bottom": thick}),
    }


def resolve_style_parts(
    style_id: str,
    catalog: TableStyleCatalog,
    color_of: ColorFn,
    line_of: LineFn,
    scheme_hex: HexFn,
    tint: Callable[[str, float], str],
) -> dict[str, Any] | None:
    """Resolve a style id: catalog → built-in → catalog default style → None."""
    candidates = [style_id]
    if catalog.default_id and catalog.default_id != style_id:
        candidates.append(catalog.default_id)
    for sid in candidates:
        el = catalog.styles.get(sid)
        if el is not None:
            parts: dict[str, Any] = {}
            for name in STYLE_PARTS:
                part = _style_part(_child(el, name), color_of, line_of)
                if part is not None:
                    parts[name] = part
            return parts
        built = builtin_style(sid, scheme_hex, tint)
        if built is not None:
            return built
    return None


def apply_table_style(
    rows: list[dict[str, Any]], n_cols: int, parts: dict[str, Any], flags: dict[str, bool]
) -> None:
    """Apply resolved style ``parts`` to cell dicts in place (cell-own values win)."""
    n_rows = len(rows)
    if n_rows == 0 or n_cols <= 0:
        return
    r0 = 1 if flags.get("firstRow") else 0
    r1 = n_rows - 1 - (1 if flags.get("lastRow") else 0)
    c0 = 1 if flags.get("firstCol") else 0
    c1 = n_cols - 1 - (1 if flags.get("lastCol") else 0)
    for r in range(n_rows):
        cells = rows[r].get("cells", [])
        for c in range(min(n_cols, len(cells))):
            cell = cells[c]
            regions: list[tuple[str, int, int, int, int]] = [
                ("wholeTbl", 0, n_rows - 1, 0, n_cols - 1)
            ]
            if flags.get("bandCol") and c0 <= c <= c1:
                regions.append(("band1V" if (c - c0) % 2 == 0 else "band2V", 0, n_rows - 1, c, c))
            if flags.get("bandRow") and r0 <= r <= r1:
                regions.append(("band1H" if (r - r0) % 2 == 0 else "band2H", r, r, 0, n_cols - 1))
            if flags.get("lastCol") and c == n_cols - 1:
                regions.append(("lastCol", 0, n_rows - 1, c, c))
            if flags.get("firstCol") and c == 0:
                regions.append(("firstCol", 0, n_rows - 1, 0, 0))
            if flags.get("lastRow") and r == n_rows - 1:
                regions.append(("lastRow", r, r, 0, n_cols - 1))
            if flags.get("firstRow") and r == 0:
                regions.append(("firstRow", 0, 0, 0, n_cols - 1))

            fill: dict[str, Any] | None = None
            bd: dict[str, dict[str, Any]] = {}
            tx: dict[str, Any] = {}
            for name, ra, rb, ca, cb in regions:
                part = parts.get(name)
                if not part:
                    continue
                if part.get("fill"):
                    fill = part["fill"]
                tx.update(part.get("tx") or {})
                pbd = part.get("bd") or {}
                for key, outer, inner, edge in (
                    ("l", "left", "insideV", c == ca),
                    ("r", "right", "insideV", c == cb),
                    ("t", "top", "insideH", r == ra),
                    ("b", "bottom", "insideH", r == rb),
                ):
                    line = pbd.get(outer if edge else inner)
                    if line:
                        bd[key] = line

            own = cell.setdefault("own", {"fill": False, "bd": []})
            if not own.get("fill") and fill:
                cell["fill"] = copy.deepcopy(fill)
            cell_bd = cell.setdefault("bd", {})
            for key, line in bd.items():
                if key not in own.get("bd", []):
                    cell_bd[key] = copy.deepcopy(line)
            _apply_text_style(cell.get("tx"), tx)


def _apply_text_style(text_body: Any, tx: dict[str, Any]) -> None:
    if text_body is None or not tx:
        return
    color = tx.get("color")
    for para in getattr(text_body, "paragraphs", []):
        for run in para.runs:
            if run.color is None and color:
                run.color = color
            # TextRun has no tri-state bold/italic: the style can only turn them on.
            if tx.get("b"):
                run.bold = True
            if tx.get("i"):
                run.italic = True
