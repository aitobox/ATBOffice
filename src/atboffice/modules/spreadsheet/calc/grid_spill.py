"""Spill dynamic-array results (SEQUENCE, FILTER, SORT, UNIQUE, …) into the sheet grid.

The anchor cell keeps the formula and shows the top-left value; the other cells of the
result rectangle receive plain values tagged with ``spill_origin``. A blocked rectangle
(non-empty cells that are not part of this spill) makes the anchor show ``#SPILL!``.
Spill rectangles are kept in ``sheet.extra["_spills"]`` ({(r, c): (r2, c2)}) for the
blue spill border.
"""

from __future__ import annotations

from typing import Any

from atboffice.modules.spreadsheet.calc.context import Arr, Ref
from atboffice.modules.spreadsheet.calc.errors import SPILL
from atboffice.modules.spreadsheet.calc.references import MAXC, MAXR


def spills(sheet: Any) -> dict[tuple[int, int], tuple[int, int]]:
    extra = getattr(sheet, "extra", None)
    if not isinstance(extra, dict):
        return {}
    return extra.setdefault("_spills", {})


def spill_rect_at(sheet: Any, r: int, c: int) -> tuple[int, int, int, int] | None:
    """Spill rectangle (r1, c1, r2, c2) containing (r, c), if any."""
    for (r1, c1), (r2, c2) in spills(sheet).items():
        if r1 <= r <= r2 and c1 <= c <= c2:
            return r1, c1, r2, c2
    return None


def clear_spill(sheet: Any, r: int, c: int) -> bool:
    """Remove the spilled values of the array anchored at (r, c). True if one existed."""
    rect = spills(sheet).pop((r, c), None)
    if rect is None:
        return False
    r2, c2 = rect
    for rr in range(r, r2 + 1):
        for cc in range(c, c2 + 1):
            if (rr, cc) == (r, c):
                continue
            cell = sheet.get_cell(rr, cc)
            if cell is not None and getattr(cell, "spill_origin", None) == (r, c):
                cell.value = None
                cell.spill_origin = None
    return True


def _as_matrix(value: Any) -> list[list[Any]] | None:
    if isinstance(value, Arr):
        return [list(row) for row in value.data]
    if isinstance(value, Ref):
        try:
            return [list(row) for row in value.to_array().data]
        except Exception:
            return None
    return None


def _snapshot(sheet: Any, r: int, c: int) -> dict[tuple[int, int], Any]:
    rect = spills(sheet).get((r, c))
    if rect is None:
        return {}
    out = {}
    for rr in range(r, rect[0] + 1):
        for cc in range(c, rect[1] + 1):
            cell = sheet.get_cell(rr, cc)
            out[(rr, cc)] = cell.value if cell is not None else None
    return out


def apply_spill(sheet: Any, r: int, c: int, value: Any) -> tuple[Any, bool]:
    """Spill ``value`` from anchor (r, c).

    Returns (anchor value, changed): ``changed`` is True when the spilled cells (area or
    values) differ from before, so readers of the spill area must be recalculated.
    """
    before = _snapshot(sheet, r, c)
    anchor = _spill(sheet, r, c, value)
    after = _snapshot(sheet, r, c)
    if after:
        after[(r, c)] = anchor
    if before:
        before[(r, c)] = anchor
    return anchor, before != after


def _fit_array_range(sheet: Any, r: int, c: int, matrix: list[list[Any]] | None,
                     value: Any) -> list[list[Any]] | None:
    """Legacy array formula (Ctrl+Shift+Enter): fit the result to its entered range."""
    from atboffice.modules.spreadsheet.calc.errors import NA

    extra = getattr(sheet, "extra", None)
    rect = extra.get("_array_formulas", {}).get((r, c)) if isinstance(extra, dict) else None
    if rect is None:
        return matrix
    rows, cols = rect[2] - rect[0] + 1, rect[3] - rect[1] + 1
    src = matrix if matrix else [[value]]
    out = []
    for i in range(rows):
        row = []
        for j in range(cols):
            if i < len(src) and j < len(src[i]):
                row.append(src[i][j])
            elif len(src) == 1 and len(src[0]) == 1:
                row.append(src[0][0])  # a scalar fills the whole array range
            else:
                row.append(NA)
        out.append(row)
    return out


def _spill(sheet: Any, r: int, c: int, value: Any) -> Any:
    clear_spill(sheet, r, c)
    matrix = _fit_array_range(sheet, r, c, _as_matrix(value), value)
    if matrix is None or not matrix or not matrix[0]:
        return value
    rows, cols = len(matrix), len(matrix[0])
    if rows == 1 and cols == 1:
        return matrix[0][0]
    r2, c2 = r + rows - 1, c + cols - 1
    if r2 >= MAXR or c2 >= MAXC:
        return SPILL
    for rr in range(r, r2 + 1):
        for cc in range(c, c2 + 1):
            if (rr, cc) == (r, c):
                continue
            cell = sheet.get_cell(rr, cc)
            if cell is None:
                continue
            if getattr(cell, "formula", None) or (
                cell.value not in (None, "") and getattr(cell, "spill_origin", None) is None
            ):
                return SPILL  # obstructed by the user's data
            if getattr(cell, "spill_origin", None) not in (None, (r, c)):
                return SPILL  # overlaps another array's spill
    for i, row in enumerate(matrix):
        for j, item in enumerate(row):
            if (i, j) == (0, 0):
                continue
            cell = sheet.ensure_cell(r + i, c + j)
            cell.value = item
            cell.spill_origin = (r, c)
    spills(sheet)[(r, c)] = (r2, c2)
    return matrix[0][0]
