"""Hierarchy category layouts for SmartArt (orgChart, hierarchy, hHierarchy)."""

from __future__ import annotations

from typing import Any

from atboffice.modules.presentation.smartart.item import SmartArtItem
from atboffice.modules.presentation.smartart.layouts.base import node_shape


def layout_tree(
    items: list[SmartArtItem],
    box: dict[str, float],
    opts: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Generic hierarchical tree layout engine for top-down or left-to-right graphs."""
    if not items:
        return []

    o = opts or {}
    across = bool(o.get("across", False))
    gap_x = 0.25
    a = float(o.get("aspect", 0.55))
    gap_y = float(o.get("gapY", 0.4))

    def width(it: SmartArtItem) -> float:
        if it.kids:
            return max(1.0, sum(width(k) for k in it.kids) + (len(it.kids) - 1) * gap_x)
        return 1.0

    def depth(it: SmartArtItem) -> int:
        if it.kids:
            return 1 + max(depth(k) for k in it.kids)
        return 1

    wu = sum(width(it) for it in items) + (len(items) - 1) * gap_x
    d_depth = max(depth(it) for it in items)

    spread = box["h"] if across else box["w"]
    levels = box["w"] if across else box["h"]

    if across:
        u = min(spread / (wu * a) if (wu * a) > 0 else spread, levels / (d_depth + (d_depth - 1) * gap_y) if (d_depth + (d_depth - 1) * gap_y) > 0 else levels)
    else:
        u = min(spread / wu if wu > 0 else spread, levels / (d_depth * a + (d_depth - 1) * gap_y) if (d_depth * a + (d_depth - 1) * gap_y) > 0 else levels)

    nw = u
    nh = a * u
    sib = nh if across else nw
    lev = nw if across else nh
    gap = gap_y * (nw if across else u)

    start0 = (box["y"] if across else box["x"]) + (spread - wu * sib) / 2.0
    top = (box["x"] if across else box["y"]) + (levels - (d_depth * lev + (d_depth - 1) * gap)) / 2.0

    out: list[dict[str, Any]] = []
    count = 0

    def at_box(along: float, down: float, w: float, h: float) -> dict[str, float]:
        return {"x": down, "y": along, "w": w, "h": h} if across else {"x": along, "y": down, "w": w, "h": h}

    def pt(along: float, down: float) -> list[float]:
        return [down, along] if across else [along, down]

    def place(it: SmartArtItem, left: float, lvl: int) -> None:
        nonlocal count
        item_w = width(it)
        a0 = left + (item_w * sib - sib) / 2.0
        d0 = top + lvl * (lev + gap)
        r = at_box(a0, d0, nw, nh)

        node_dict = node_shape(
            it,
            count,
            0,
            o.get("geom", "rect"),
            r["x"],
            r["y"],
            r["w"],
            r["h"],
            {"level": lvl, "adj": o.get("adj")},
        )
        count += 1
        out.append(node_dict)

        if not it.kids:
            return

        kids_w = sum(width(k) for k in it.kids) + (len(it.kids) - 1) * gap_x
        cl = left + (item_w - kids_w) * sib / 2.0
        pa = a0 + sib / 2.0
        pd = d0 + lev
        mid = pd + gap / 2.0

        for k in it.kids:
            ka = cl + (width(k) * sib - sib) / 2.0 + sib / 2.0
            if o.get("straight"):
                path = [pt(pa, pd), pt(ka, pd + gap)]
            else:
                path = [pt(pa, pd), pt(pa, mid), pt(ka, mid), pt(ka, pd + gap)]

            xs = [q[0] for q in path]
            ys = [q[1] for q in path]
            out.append(
                {
                    "role": "conn",
                    "geom": "path",
                    "path": path,
                    "x": min(xs),
                    "y": min(ys),
                    "w": max(0.01, max(xs) - min(xs)),
                    "h": max(0.01, max(ys) - min(ys)),
                    "rot": 0.0,
                    "itemId": k.id,
                    "level": lvl + 1,
                    "styleLbl": "parChTrans1D2",
                    "colorIdx": 0,
                    "colorCnt": 1,
                }
            )
            place(k, cl, lvl + 1)
            cl += (width(k) + gap_x) * sib

    left = start0
    for it in items:
        place(it, left, 0)
        left += (width(it) + gap_x) * sib

    for sh in out:
        if sh.get("role") == "node":
            sh["colorCnt"] = count
            if o.get("byLevel"):
                sh["colorIdx"] = sh.get("level", 0)
                sh["colorCnt"] = d_depth

    return out


def make_org_chart(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Organization Chart."""
    return layout_tree(items, box, {})


def make_hierarchy(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Vertical Straight-line Hierarchy."""
    return layout_tree(
        items,
        box,
        {"geom": "roundRect", "adj": [10000], "straight": True, "byLevel": True, "aspect": 0.6},
    )


def make_h_hierarchy(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Horizontal Hierarchy."""
    return layout_tree(
        items,
        box,
        {"across": True, "geom": "roundRect", "adj": [10000], "aspect": 0.5, "gapY": 0.35},
    )
