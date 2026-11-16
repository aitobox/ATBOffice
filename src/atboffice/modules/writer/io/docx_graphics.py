"""WordprocessingML graphic frames: charts (``c:chart``) and SmartArt (``dgm:relIds``).

Charts are parsed with the shared presentation chart reader into a :class:`ChartItem`.
SmartArt uses the diagram drawing Word stores next to the data model
(``word/diagrams/drawing*.xml``): every ``dsp:sp`` becomes a child of a group
:class:`ShapeItem`, painted by the same shape painter as text boxes. Diagrams saved
without a drawing are laid out from the data model (process row, cycle, hierarchy, list),
like the original ``smartArtFromData``.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Any

from atboffice.drawing.dml import DmlFill, child, first_color, local_name
from atboffice.drawing.shape_style import (
    DmlLine,
    font_ref_color,
    parse_shape_geometry,
    resolve_shape_fill,
    resolve_shape_line,
)
from atboffice.modules.writer.io.docx_shapes import EMU_PER_PT, parse_xfrm
from atboffice.modules.writer.models.document import BreakItem, Paragraph, Story, TextItem
from atboffice.modules.writer.models.drawing import ShapeChild, ShapeItem
from atboffice.modules.writer.models.properties import (
    ParagraphProperties,
    RunProperties,
    SpacingProperties,
)

_PERCENT_RE = re.compile(r"^-?\d+(\.\d+)?%$")
_JC = {"l": "left", "ctr": "center", "r": "right", "just": "both", "dist": "distribute"}


def normalize_percentages(root: ET.Element) -> ET.Element:
    """Strict OOXML writes percentages as ``"60%"``; turn them into 1/1000ths (``60000``)."""
    for el in root.iter():
        for key, val in el.attrib.items():
            if _PERCENT_RE.match(val):
                el.set(key, str(round(float(val[:-1]) * 1000)))
    return root


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


def read_chart(xml_text: str) -> Any | None:
    """Parse chart part XML (namespaces already transitional) into ``ChartData``.

    Returns ``None`` when the part has no ``c:chart`` (the shared parser would
    otherwise invent a sample chart).
    """
    from atboffice.modules.presentation.chart.io import parse_chart_xml

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    chart_el = next((c for c in root if local_name(c.tag) == "chart"), None)
    if chart_el is None:
        return None
    try:
        data = parse_chart_xml(xml_text)
    except Exception:
        return None
    # Office auto title: a title element without text on a one-series chart shows the
    # series name (unless the auto title is deleted).
    title_el = child(chart_el, "title")
    deleted = child(chart_el, "autoTitleDeleted")
    if (
        title_el is not None
        and not data.title
        and len(data.series) == 1
        and (deleted is None or deleted.get("val") in ("0", "false"))
    ):
        data.title = data.series[0].name or ""
    return data


# ---------------------------------------------------------------------------
# DrawingML text bodies
# ---------------------------------------------------------------------------


def _bool_attr(raw: str | None) -> bool | None:
    if raw is None:
        return None
    return raw in ("1", "true", "on")


def dml_text_story(tx_body: ET.Element | None, theme: Mapping[str, str]) -> Story | None:
    """Convert a DrawingML ``txBody`` (``a:p`` paragraphs) into a writer :class:`Story`."""
    if tx_body is None:
        return None
    blocks: list[Any] = []
    for ap in tx_body:
        if local_name(ap.tag) != "p":
            continue
        p_pr_el = child(ap, "pPr")
        sp = SpacingProperties(before=0.0, after=0.0, line=0.9, line_rule="auto")
        ln_spc = child(child(p_pr_el, "lnSpc"), "spcPct")
        if ln_spc is not None:
            try:
                sp.line = max(0.1, float(ln_spc.get("val", "100000")) / 100000.0)
            except ValueError:
                pass
        for tag, attr in (("spcBef", "before"), ("spcAft", "after")):
            pts = child(child(p_pr_el, tag), "spcPts")
            if pts is not None:
                try:
                    setattr(sp, attr, float(pts.get("val", "0")) / 100.0)
                except ValueError:
                    pass
        algn = p_pr_el.get("algn") if p_pr_el is not None else None
        p_pr = ParagraphProperties(jc=_JC.get(algn or "ctr", "center"), sp=sp)
        p_pr.jc_explicit = True
        para = Paragraph(p_pr=p_pr)
        end_sz = None
        end_rpr = child(ap, "endParaRPr")
        if end_rpr is not None and end_rpr.get("sz"):
            try:
                end_sz = float(end_rpr.get("sz", "1800")) / 100.0
            except ValueError:
                end_sz = None
        for r in ap:
            name = local_name(r.tag)
            if name == "br":
                para.runs.append(BreakItem(break_type="line"))
                continue
            if name not in ("r", "fld"):
                continue
            t = child(r, "t")
            if t is None or not t.text:
                continue
            para.runs.append(TextItem(t.text, _run_props(child(r, "rPr"), theme)))
        if not para.runs and end_sz is not None:
            para.r_pr = RunProperties(sz=end_sz)
        elif para.runs:
            para.r_pr = para.runs[0].r_pr
        blocks.append(para)
    if not blocks:
        return None
    return Story(kind="textbox", blocks=blocks)


def _run_props(r_pr: ET.Element | None, theme: Mapping[str, str]) -> RunProperties:
    rp = RunProperties(sz=18.0, color="auto")
    if r_pr is None:
        return rp
    try:
        if r_pr.get("sz"):
            rp.sz = max(1.0, float(r_pr.get("sz", "1800")) / 100.0)
    except ValueError:
        pass
    b, i = _bool_attr(r_pr.get("b")), _bool_attr(r_pr.get("i"))
    rp.b = bool(b)
    rp.i = bool(i)
    color = first_color(child(r_pr, "solidFill"), theme)
    if color is not None:
        rp.color = color[0].lstrip("#").upper()
    latin = child(r_pr, "latin")
    face = latin.get("typeface", "") if latin is not None else ""
    if face and not face.startswith("+"):
        rp.font = face
    return rp


# ---------------------------------------------------------------------------
# SmartArt from the stored drawing
# ---------------------------------------------------------------------------


def _sp_to_shape(sp: ET.Element, theme: Mapping[str, str]) -> ShapeChild | None:
    sp_pr = child(sp, "spPr")
    xf = parse_xfrm(sp_pr)
    if xf is None or xf.w <= 0 or xf.h <= 0:
        return None
    style = child(sp, "style")
    geom, adj, custom = parse_shape_geometry(sp_pr)
    tx_body = child(sp, "txBody")
    story = dml_text_story(tx_body, theme)
    body_pr = child(tx_body, "bodyPr")

    insets = [0.0, 0.0, 0.0, 0.0]
    if body_pr is not None:
        for k, attr in enumerate(("lIns", "tIns", "rIns", "bIns")):
            raw = body_pr.get(attr)
            try:
                insets[k] = float(raw) / EMU_PER_PT if raw is not None else (7.2, 3.6)[k % 2]
            except ValueError:
                insets[k] = 0.0
    tx_el = child(sp, "txXfrm")
    tx = parse_xfrm(_as_sp_pr(tx_el)) if tx_el is not None else None
    if tx is not None and tx.w > 0 and tx.h > 0:
        # The text rectangle may be smaller than the shape (circles, arrows).
        insets[0] += max(0.0, tx.x - xf.x)
        insets[1] += max(0.0, tx.y - xf.y)
        insets[2] += max(0.0, (xf.x + xf.w) - (tx.x + tx.w))
        insets[3] += max(0.0, (xf.y + xf.h) - (tx.y + tx.h))

    shape = ShapeItem(
        width=xf.w,
        height=xf.h,
        rotation=xf.rot,
        geometry=geom,
        adjustments=adj,
        custom_path=custom,
        fill=resolve_shape_fill(sp_pr, style, theme),
        line=resolve_shape_line(sp_pr, style, theme),
        flip_h=xf.flip_h,
        flip_v=xf.flip_v,
        story=story,
        insets=(insets[0], insets[1], insets[2], insets[3]),
        v_anchor=(body_pr.get("anchor", "ctr") if body_pr is not None else "ctr") or "ctr",
        text_color=font_ref_color(style, theme),
    )
    return ShapeChild(item=shape, x=xf.x, y=xf.y)


def _as_sp_pr(txxfrm: ET.Element) -> ET.Element:
    """Wrap ``dsp:txXfrm`` (an xfrm-shaped element) so :func:`parse_xfrm` can read it."""
    holder = ET.Element("spPr")
    xf = ET.SubElement(holder, "xfrm")
    for c in txxfrm:
        xf.append(c)
    return holder


def smartart_from_drawing(
    drawing: ET.Element, width: float, height: float, theme: Mapping[str, str]
) -> ShapeItem | None:
    """Build a group :class:`ShapeItem` from a ``dsp:drawing`` part; ``None`` if empty."""
    normalize_percentages(drawing)
    tree = next((e for e in drawing.iter() if local_name(e.tag) == "spTree"), None)
    if tree is None:
        return None
    group = ShapeItem(width=width, height=height, fill=DmlFill(kind="none"), line=DmlLine())
    for sp in tree.iter():
        if local_name(sp.tag) != "sp":
            continue
        ch = _sp_to_shape(sp, theme)
        if ch is not None:
            group.children.append(ch)
    return group if group.children else None


# ---------------------------------------------------------------------------
# SmartArt from the data model (no stored drawing)
# ---------------------------------------------------------------------------


class _Node:
    __slots__ = ("id", "type", "text", "kids")

    def __init__(self, node_id: str, node_type: str, text: str) -> None:
        self.id = node_id
        self.type = node_type
        self.text = text
        self.kids: list[_Node] = []


def _data_nodes(data: ET.Element) -> list[_Node]:
    """Top-level nodes of a ``dgm:dataModel`` with their children, in source order."""
    pts: dict[str, _Node] = {}
    for pt in data.iter():
        if local_name(pt.tag) != "pt":
            continue
        typ = pt.get("type", "node") or "node"
        if typ not in ("node", "doc"):
            continue
        t_el = child(pt, "t")
        text = ""
        if t_el is not None:
            paras = [
                "".join(t.text or "" for t in ap.iter() if local_name(t.tag) == "t")
                for ap in t_el
                if local_name(ap.tag) == "p"
            ]
            text = " ".join(paras).strip()
        pts[pt.get("modelId", "")] = _Node(pt.get("modelId", ""), typ, text)

    parent: dict[str, _Node] = {}
    links: dict[str, list[tuple[int, _Node]]] = {}
    for cxn in data.iter():
        if local_name(cxn.tag) != "cxn" or (cxn.get("type", "parOf") or "parOf") != "parOf":
            continue
        src, dst = pts.get(cxn.get("srcId", "")), pts.get(cxn.get("destId", ""))
        if src is None or dst is None:
            continue
        try:
            order = int(cxn.get("srcOrd", "0") or "0")
        except ValueError:
            order = 0
        links.setdefault(src.id, []).append((order, dst))
        parent[dst.id] = src
    for node in pts.values():
        node.kids = [n for _, n in sorted(links.get(node.id, []), key=lambda t: t[0])]
    root = next((n for n in pts.values() if n.type == "doc"), None)
    if root is not None:
        return root.kids
    return [n for n in pts.values() if n.id not in parent]


def _text_story(lines: list[str], size: float, bullets: bool) -> Story:
    blocks = []
    for k, text in enumerate(lines):
        sub = bullets and k > 0
        rp = RunProperties(sz=round(size * (0.85 if sub else 1.0) * 2) / 2, color="FFFFFF")
        p_pr = ParagraphProperties(
            jc="left" if sub else "center",
            sp=SpacingProperties(before=0.0, after=0.0, line=0.95, line_rule="auto"),
        )
        p_pr.jc_explicit = True
        run = TextItem(("• " if sub else "") + text, rp)
        blocks.append(Paragraph(runs=[run], p_pr=p_pr, r_pr=rp))
    return Story(kind="textbox", blocks=blocks or [Paragraph()])


def smartart_from_data(
    data: ET.Element,
    layout_id: str,
    width: float,
    height: float,
    theme: Mapping[str, str],
) -> ShapeItem | None:
    """Lay out a SmartArt data model without a stored drawing (``None`` if it has no nodes)."""
    tops = _data_nodes(data)
    if not tops or width <= 0 or height <= 0:
        return None
    accent = theme.get("accent1", "#4F81BD")
    fill = DmlFill(kind="solid", color=accent, alpha=1.0)
    line = DmlLine(visible=True, color="#FFFFFF", width=1.5)
    group = ShapeItem(width=width, height=height, fill=DmlFill(kind="none"), line=DmlLine())

    def box(x: float, y: float, bw: float, bh: float, text: str, sub: list[str] | None,
            geom: str = "roundRect") -> None:
        lines = [t for t in [text, *(sub or [])] if t]
        longest = max([4, *(len(t) for t in lines)])
        size = max(7.0, min(18.0, bh / (len(lines) * 1.6 + 0.6), bw / longest * 1.7))
        shape = ShapeItem(
            width=bw, height=bh, geometry=geom, fill=fill, line=line,
            story=_text_story(lines, size, bool(sub)), insets=(4.0, 3.0, 4.0, 3.0),
            v_anchor="ctr", text_color="#FFFFFF",
        )
        group.children.append(ShapeChild(item=shape, x=x, y=y))

    def arrow(x: float, y: float, aw: float, ah: float) -> None:
        shape = ShapeItem(
            width=aw, height=ah, geometry="rightArrow",
            fill=DmlFill(kind="solid", color=accent, alpha=0.45), line=DmlLine(),
        )
        group.children.append(ShapeChild(item=shape, x=x, y=y))

    kind = (layout_id or "").lower()
    n = len(tops)
    w, h = width, height
    if re.search(r"process|chevron|arrow", kind):
        gap = min(w / (n * 4), 30.0)
        bw = (w - gap * (n - 1)) / n
        bh = min(h, bw * 0.75)
        y = (h - bh) / 2
        for i, node in enumerate(tops):
            box(i * (bw + gap), y, bw, bh, node.text, [k.text for k in node.kids])
            if i < n - 1:
                arrow(i * (bw + gap) + bw + gap * 0.15, h / 2 - gap * 0.35, gap * 0.7, gap * 0.7)
    elif "cycle" in kind:
        r = min(w, h) / 2
        bw = min(r * 0.8, (2 * math.pi * r * 0.55) / n)
        bh = bw * 0.6
        for i, node in enumerate(tops):
            a = -math.pi / 2 + i * 2 * math.pi / n
            box(w / 2 + (r - bw / 2) * math.cos(a) - bw / 2,
                h / 2 + (r - bh / 2) * math.sin(a) - bh / 2, bw, bh, node.text, None, "ellipse")
    elif re.search(r"hierarchy|orgchart", kind):
        levels: list[list[_Node]] = []

        def walk(node: _Node, depth: int) -> None:
            while len(levels) <= depth:
                levels.append([])
            levels[depth].append(node)
            for k in node.kids:
                walk(k, depth + 1)

        for t in tops:
            walk(t, 0)
        lh = h / len(levels)
        for depth, row in enumerate(levels):
            bw = min(w / len(row) * 0.85, w * 0.3)
            gap = (w - bw * len(row)) / (len(row) + 1)
            for i, node in enumerate(row):
                box(gap + i * (bw + gap), depth * lh + lh * 0.12, bw, lh * 0.7, node.text, None)
    else:
        gap = min(h / (n * 6), 8.0)
        bh = (h - gap * (n - 1)) / n
        for i, node in enumerate(tops):
            box(0.0, i * (bh + gap), w, bh, node.text, [k.text for k in node.kids])
    return group
