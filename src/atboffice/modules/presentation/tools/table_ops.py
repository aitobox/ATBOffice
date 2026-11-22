"""Pure operations on a Lectern table shape's ``tbl`` dictionary.

Schema (as read by ``ShapeGraphicsItem._paint_table`` and the PPTX reader/writer)::

    tbl = {"cols": [w, ...], "rows": [{"h": h, "cells": [cell, ...]}, ...]}
    cell = {"tx": TextBody, "gs": colspan, "rs": rowspan,
            "hm": True (horizontal continuation), "vm": True (vertical continuation),
            "bd": {"l"|"r"|"t"|"b": {"w": pt, "c": color, "dash": str}},
            "fill": {"t": "solid", "c": color},
            "own": {"fill": bool, "bd": [sides]}}   # which values the writer must emit

Cell text is a ``TextBody`` (the reader and the PPTX writer both use objects); dicts from
older in-app tables are coerced by :func:`ensure_tx`.

A *range* is ``(r1, c1, r2, c2)`` inclusive, in grid coordinates.
"""

from __future__ import annotations

import copy
from typing import Any

from atboffice.modules.presentation.models.text import TextBody

Rect = tuple[int, int, int, int]

MIN_ROW_H = 12.0
MIN_COL_W = 12.0


def empty_cell() -> dict[str, Any]:
    return {"tx": TextBody.create_empty()}


def ensure_tx(cl: dict[str, Any]) -> TextBody:
    """The cell's TextBody, converting legacy dict / missing values in place."""
    tx = cl.get("tx")
    if isinstance(tx, TextBody):
        return tx
    if isinstance(tx, dict):
        if "ps" in tx:
            body = TextBody.from_dict(tx)
        else:  # legacy {"paragraphs": [{"runs": [{"text"|"t": ...}]}]}
            lines = [
                "".join(str(r.get("t", r.get("text", ""))) for r in p.get("runs") or [])
                for p in tx.get("paragraphs") or []
            ]
            body = TextBody.from_plain_text("\n".join(lines))
            body.anchor = tx.get("anchor", body.anchor)
    else:
        body = TextBody.from_plain_text(str(cl.get("text") or ""))
    cl["tx"] = body
    return body


def _own(cl: dict[str, Any]) -> dict[str, Any]:
    own = cl.get("own")
    if own is None:
        own = {"fill": bool(cl.get("fill")), "bd": list((cl.get("bd") or {}).keys())}
        cl["own"] = own
    return own


def dims(tbl: dict[str, Any]) -> tuple[int, int]:
    rows = tbl.get("rows") or []
    n_cols = len(tbl.get("cols") or [])
    if not n_cols and rows:
        n_cols = max(len(r.get("cells") or []) for r in rows)
    return len(rows), n_cols


def normalize(tbl: dict[str, Any]) -> None:
    """Pad every row to the grid width so index arithmetic is safe."""
    n_rows, n_cols = dims(tbl)
    if not tbl.get("cols") and n_cols:
        tbl["cols"] = [100.0] * n_cols
    for row in tbl.get("rows") or []:
        cells = row.setdefault("cells", [])
        while len(cells) < n_cols:
            cells.append(empty_cell())
        del cells[n_cols:]
        row.setdefault("h", 30.0)
        for cl in cells:
            ensure_tx(cl)


def cell(tbl: dict[str, Any], r: int, c: int) -> dict[str, Any]:
    return tbl["rows"][r]["cells"][c]


def origin_of(tbl: dict[str, Any], r: int, c: int) -> tuple[int, int]:
    """Top-left cell of the merge area covering (r, c)."""
    while c > 0 and cell(tbl, r, c).get("hm"):
        c -= 1
    while r > 0 and cell(tbl, r, c).get("vm"):
        r -= 1
    return r, c


def span_of(tbl: dict[str, Any], r: int, c: int) -> Rect:
    """Full merge rectangle for the cell at (r, c)."""
    r0, c0 = origin_of(tbl, r, c)
    o = cell(tbl, r0, c0)
    n_rows, n_cols = dims(tbl)
    return (
        r0,
        c0,
        min(n_rows, r0 + max(1, int(o.get("rs") or 1))) - 1,
        min(n_cols, c0 + max(1, int(o.get("gs") or 1))) - 1,
    )


def expand_to_merges(tbl: dict[str, Any], rect: Rect) -> Rect:
    """Grow ``rect`` until it does not cut through any merged cell."""
    r1, c1, r2, c2 = rect
    changed = True
    while changed:
        changed = False
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                a, b, e, f = span_of(tbl, r, c)
                if a < r1 or b < c1 or e > r2 or f > c2:
                    r1, c1, r2, c2 = min(r1, a), min(c1, b), max(r2, e), max(c2, f)
                    changed = True
    return r1, c1, r2, c2


def scaled_cols(tbl: dict[str, Any], width: float) -> list[float]:
    cols = [float(x) for x in tbl.get("cols") or []]
    total = sum(cols)
    if not cols or total <= 0.001:
        n = max(1, dims(tbl)[1])
        return [width / n] * n
    return [c * width / total for c in cols]


def cell_rect(
    tbl: dict[str, Any], width: float, r: int, c: int
) -> tuple[float, float, float, float]:
    """Local (x, y, w, h) of the merge area containing (r, c)."""
    r1, c1, r2, c2 = span_of(tbl, r, c)
    cols = scaled_cols(tbl, width)
    heights = [float(row.get("h", 30.0)) for row in tbl["rows"]]
    x = sum(cols[:c1])
    y = sum(heights[:r1])
    return x, y, sum(cols[c1 : c2 + 1]), sum(heights[r1 : r2 + 1])


def hit_test(tbl: dict[str, Any], width: float, x: float, y: float) -> tuple[int, int] | None:
    """Grid cell (origin of its merge) under local point (x, y)."""
    n_rows, n_cols = dims(tbl)
    if not n_rows or not n_cols or x < 0 or y < 0:
        return None
    cols = scaled_cols(tbl, width)
    acc = 0.0
    col = None
    for i, w in enumerate(cols):
        acc += w
        if x < acc:
            col = i
            break
    acc = 0.0
    row = None
    for i, r in enumerate(tbl["rows"]):
        acc += float(r.get("h", 30.0))
        if y < acc:
            row = i
            break
    if row is None or col is None:
        return None
    return origin_of(tbl, row, col)


def table_height(tbl: dict[str, Any]) -> float:
    return sum(float(r.get("h", 30.0)) for r in tbl.get("rows") or [])


# ------------------------------------------------------------------ merge / split
def merge(tbl: dict[str, Any], rect: Rect) -> Rect:
    """Merge ``rect`` (expanded to whole merges) into its top-left cell.

    Text of the absorbed cells is appended as extra paragraphs, like PowerPoint.
    Returns the merged rectangle.
    """
    normalize(tbl)
    r1, c1, r2, c2 = expand_to_merges(tbl, rect)
    if (r1, c1) == (r2, c2):
        return r1, c1, r2, c2
    origin = cell(tbl, r1, c1)
    body = ensure_tx(origin)
    paras = [p for p in body.paragraphs if p.plain_text.strip()]
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            if (r, c) == (r1, c1):
                continue
            cl = cell(tbl, r, c)
            paras.extend(
                copy.deepcopy(p) for p in ensure_tx(cl).paragraphs if p.plain_text.strip()
            )
            cl["tx"] = TextBody.create_empty()
            cl.pop("gs", None)
            cl.pop("rs", None)
            cl["hm"] = c > c1
            cl["vm"] = r > r1
            if not cl["hm"]:
                cl.pop("hm")
            if not cl["vm"]:
                cl.pop("vm")
    body.paragraphs = paras or TextBody.create_empty().paragraphs
    origin["gs"] = c2 - c1 + 1
    origin["rs"] = r2 - r1 + 1
    if origin["gs"] == 1:
        origin.pop("gs")
    if origin["rs"] == 1:
        origin.pop("rs")
    return r1, c1, r2, c2


def split(tbl: dict[str, Any], r: int, c: int) -> bool:
    """Undo the merge covering (r, c). Returns False when the cell is not merged."""
    normalize(tbl)
    r1, c1, r2, c2 = span_of(tbl, r, c)
    if (r1, c1) == (r2, c2):
        return False
    for rr in range(r1, r2 + 1):
        for cc in range(c1, c2 + 1):
            cl = cell(tbl, rr, cc)
            for key in ("gs", "rs", "hm", "vm"):
                cl.pop(key, None)
    return True


# ------------------------------------------------------------------ rows / cols
def _unmerge_crossing_row(tbl: dict[str, Any], at: int) -> None:
    """Split merges that span across the boundary above row ``at``."""
    n_rows, n_cols = dims(tbl)
    if at <= 0 or at >= n_rows:
        return
    for c in range(n_cols):
        r1, c1, r2, _ = span_of(tbl, at, c)
        if r1 < at <= r2:
            split(tbl, r1, c1)


def _unmerge_crossing_col(tbl: dict[str, Any], at: int) -> None:
    n_rows, n_cols = dims(tbl)
    if at <= 0 or at >= n_cols:
        return
    for r in range(n_rows):
        _, c1, r2, c2 = span_of(tbl, r, at)
        if c1 < at <= c2:
            split(tbl, r, c1)


def insert_row(tbl: dict[str, Any], at: int, height: float | None = None) -> None:
    """Insert an empty row so it becomes index ``at`` (0..n_rows)."""
    normalize(tbl)
    n_rows, n_cols = dims(tbl)
    at = max(0, min(at, n_rows))
    _unmerge_crossing_row(tbl, at)
    ref = tbl["rows"][min(at, n_rows - 1)] if n_rows else {"h": 30.0}
    tbl["rows"].insert(
        at,
        {"h": float(height or ref.get("h", 30.0)), "cells": [empty_cell() for _ in range(n_cols)]},
    )


def insert_col(tbl: dict[str, Any], at: int, width: float | None = None) -> None:
    """Insert an empty column at index ``at``; the table grows by that width."""
    normalize(tbl)
    _n_rows, n_cols = dims(tbl)
    at = max(0, min(at, n_cols))
    _unmerge_crossing_col(tbl, at)
    cols = tbl["cols"]
    ref = cols[min(at, n_cols - 1)] if n_cols else 100.0
    cols.insert(at, float(width or ref))
    for row in tbl["rows"]:
        row["cells"].insert(at, empty_cell())


def delete_rows(tbl: dict[str, Any], r1: int, r2: int) -> bool:
    """Delete rows r1..r2. Refuses to delete every row (returns False)."""
    normalize(tbl)
    n_rows, _ = dims(tbl)
    r1, r2 = max(0, r1), min(n_rows - 1, r2)
    if r1 > r2 or (r2 - r1 + 1) >= n_rows:
        return False
    _unmerge_crossing_row(tbl, r1)
    _unmerge_crossing_row(tbl, r2 + 1)
    # merges starting inside but extending beyond are already split by the line above
    del tbl["rows"][r1 : r2 + 1]
    return True


def delete_cols(tbl: dict[str, Any], c1: int, c2: int) -> bool:
    normalize(tbl)
    _, n_cols = dims(tbl)
    c1, c2 = max(0, c1), min(n_cols - 1, c2)
    if c1 > c2 or (c2 - c1 + 1) >= n_cols:
        return False
    _unmerge_crossing_col(tbl, c1)
    _unmerge_crossing_col(tbl, c2 + 1)
    del tbl["cols"][c1 : c2 + 1]
    for row in tbl["rows"]:
        del row["cells"][c1 : c2 + 1]
    return True


def distribute_rows(tbl: dict[str, Any], r1: int = 0, r2: int | None = None) -> None:
    rows = tbl.get("rows") or []
    if not rows:
        return
    r2 = len(rows) - 1 if r2 is None else r2
    sel = rows[r1 : r2 + 1]
    avg = max(MIN_ROW_H, sum(float(r.get("h", 30.0)) for r in sel) / len(sel))
    for r in sel:
        r["h"] = avg


def distribute_cols(tbl: dict[str, Any], c1: int = 0, c2: int | None = None) -> None:
    cols = tbl.get("cols") or []
    if not cols:
        return
    c2 = len(cols) - 1 if c2 is None else c2
    sel = cols[c1 : c2 + 1]
    avg = max(MIN_COL_W, sum(sel) / len(sel))
    tbl["cols"][c1 : c2 + 1] = [avg] * len(sel)


# ------------------------------------------------------------------ formatting
def _origins(tbl: dict[str, Any], rect: Rect) -> list[tuple[int, int]]:
    r1, c1, r2, c2 = rect
    seen: list[tuple[int, int]] = []
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            o = origin_of(tbl, r, c)
            if o not in seen:
                seen.append(o)
    return seen


def apply_borders(
    tbl: dict[str, Any], rect: Rect, mode: str, line: dict[str, Any] | None
) -> None:
    """Apply a Tables & Borders preset to ``rect``.

    ``mode``: all, outside, inside, none, top, bottom, left, right.
    ``line``: ``{"w": pt, "c": color, "dash": str}``; None/``w == 0`` removes the border.
    """
    normalize(tbl)
    rect = expand_to_merges(tbl, rect)
    r1, c1, r2, c2 = rect
    pen = dict(line) if line and float(line.get("w") or 0) > 0 else None
    for r, c in _origins(tbl, rect):
        a, b, e, f = span_of(tbl, r, c)
        sides: dict[str, bool] = {
            "t": a == r1,
            "b": e == r2,
            "l": b == c1,
            "r": f == c2,
        }
        if mode == "all":
            wanted = {"t", "b", "l", "r"}
        elif mode == "none":
            wanted = {"t", "b", "l", "r"}
        elif mode == "outside":
            wanted = {s for s, edge in sides.items() if edge}
        elif mode == "inside":
            wanted = {s for s, edge in sides.items() if not edge}
        elif mode in ("top", "bottom", "left", "right"):
            key = mode[0]
            wanted = {key} if sides[key] else set()
        else:
            raise ValueError(f"unknown border mode {mode!r}")
        cl = cell(tbl, r, c)
        bd = cl.setdefault("bd", {})
        own_bd = _own(cl).setdefault("bd", [])
        for side in wanted:
            if mode == "none" or pen is None:
                bd[side] = {"w": 0.0, "c": None}
            else:
                bd[side] = dict(pen)
            if side not in own_bd:
                own_bd.append(side)


def apply_shading(tbl: dict[str, Any], rect: Rect, color: str | None) -> None:
    """Solid cell fill for ``rect``; ``None`` sets "No Fill" (overrides a table style)."""
    normalize(tbl)
    for r, c in _origins(tbl, expand_to_merges(tbl, rect)):
        cl = cell(tbl, r, c)
        cl["fill"] = {"t": "solid", "c": color} if color else {"t": "none"}
        _own(cl)["fill"] = True


VALIGN_CODES = {"top": "t", "middle": "ctr", "bottom": "b"}


def apply_valign(tbl: dict[str, Any], rect: Rect, valign: str) -> None:
    """Vertical text anchor for cells in ``rect`` ("top" / "middle" / "bottom")."""
    code = VALIGN_CODES.get(valign, valign)
    if code not in ("t", "ctr", "b"):
        raise ValueError(f"unknown vertical alignment {valign!r}")
    normalize(tbl)
    for r, c in _origins(tbl, expand_to_merges(tbl, rect)):
        ensure_tx(cell(tbl, r, c)).anchor = code


def cell_plain_text(tbl: dict[str, Any], r: int, c: int) -> str:
    return ensure_tx(cell(tbl, r, c)).plain_text


def new_table(rows: int, cols: int, width: float, height: float) -> dict[str, Any]:
    """Grid for Insert > Table (cells empty, like PowerPoint)."""
    rows, cols = max(1, rows), max(1, cols)
    return {
        "cols": [width / cols] * cols,
        "rows": [
            {"h": height / rows, "cells": [empty_cell() for _ in range(cols)]}
            for _ in range(rows)
        ],
    }
