"""Row / column outline grouping (Data > Group and Outline), Excel 2003 semantics.

Levels live in ``sheet.extra["outline_rows"]`` / ``["outline_cols"]`` ({index: level},
level 1..7). A collapsed group hides its rows/columns through the sheet geometry; the
summary row/column sits directly below/right of a group (Excel's default).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_LEVEL = 7


@dataclass(frozen=True)
class OutlineGroup:
    start: int
    end: int
    level: int

    @property
    def summary(self) -> int:
        """Index of the summary row/column that carries the +/- button."""
        return self.end + 1


def _key(axis: str) -> str:
    return "outline_rows" if axis == "row" else "outline_cols"


def levels(sheet: Any, axis: str) -> dict[int, int]:
    return sheet.extra.setdefault(_key(axis), {})


def _hidden(sheet: Any, axis: str) -> set[int]:
    geo = sheet.geometry
    return geo.hidden_rows if axis == "row" else geo.hidden_cols


def max_level(sheet: Any, axis: str) -> int:
    lv = levels(sheet, axis)
    return max(lv.values(), default=0)


def group(sheet: Any, axis: str, start: int, end: int) -> bool:
    """Data > Group: one level deeper for start..end (False when already at level 7)."""
    lv = levels(sheet, axis)
    if any(lv.get(i, 0) >= MAX_LEVEL for i in range(start, end + 1)):
        return False
    for i in range(start, end + 1):
        lv[i] = lv.get(i, 0) + 1
    sheet.dirty = True
    return True


def ungroup(sheet: Any, axis: str, start: int, end: int) -> bool:
    """Data > Ungroup: one level shallower (shown again when leaving every group)."""
    lv = levels(sheet, axis)
    changed = False
    hidden = _hidden(sheet, axis)
    for i in range(start, end + 1):
        if lv.get(i, 0) > 0:
            lv[i] -= 1
            changed = True
            if lv[i] == 0:
                del lv[i]
                hidden.discard(i)
    if changed:
        sheet.dirty = True
    return changed


def clear(sheet: Any, axis: str) -> None:
    """Data > Group and Outline > Clear Outline."""
    hidden = _hidden(sheet, axis)
    for i in list(levels(sheet, axis)):
        hidden.discard(i)
    sheet.extra[_key(axis)] = {}
    sheet.dirty = True


def groups(sheet: Any, axis: str) -> list[OutlineGroup]:
    """Every group: maximal runs of indices whose level is >= L, for each level L."""
    lv = levels(sheet, axis)
    out: list[OutlineGroup] = []
    if not lv:
        return out
    indices = sorted(lv)
    for level in range(1, max_level(sheet, axis) + 1):
        run_start = prev = None
        for i in indices:
            if lv[i] < level:
                continue
            if run_start is None:
                run_start = prev = i
            elif i == prev + 1:
                prev = i
            else:
                out.append(OutlineGroup(run_start, prev, level))
                run_start = prev = i
        if run_start is not None:
            out.append(OutlineGroup(run_start, prev, level))
    return out


def is_collapsed(sheet: Any, axis: str, grp: OutlineGroup) -> bool:
    hidden = _hidden(sheet, axis)
    return all(i in hidden for i in range(grp.start, grp.end + 1))


def set_collapsed(sheet: Any, axis: str, grp: OutlineGroup, collapsed: bool) -> None:
    """Hide or show a group's detail (inner groups that were collapsed stay collapsed)."""
    hidden = _hidden(sheet, axis)
    if collapsed:
        hidden.update(range(grp.start, grp.end + 1))
    else:
        inner = [
            g for g in groups(sheet, axis)
            if g.level > grp.level and grp.start <= g.start and g.end <= grp.end
        ]
        # An inner group counts as collapsed when its summary stays visible but its
        # detail is hidden (when the outer group is collapsed, both are hidden).
        keep = [g for g in inner if is_collapsed(sheet, axis, g) and g.summary not in hidden]
        hidden.difference_update(range(grp.start, grp.end + 1))
        for g in keep:
            hidden.update(range(g.start, g.end + 1))
    sheet.dirty = True


def show_level(sheet: Any, axis: str, level: int) -> None:
    """Level button ``level``: show groups up to that level, collapse deeper ones."""
    hidden = _hidden(sheet, axis)
    lv = levels(sheet, axis)
    for i, lvl in lv.items():
        if lvl >= level:
            hidden.add(i)
        else:
            hidden.discard(i)
    sheet.dirty = True


def group_at(sheet: Any, axis: str, index: int) -> OutlineGroup | None:
    """Deepest group containing ``index`` or whose summary is ``index``."""
    best = None
    for grp in groups(sheet, axis):
        if grp.start <= index <= grp.end or index == grp.summary:
            if best is None or grp.level > best.level:
                best = grp
    return best
