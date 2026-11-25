"""Types and helpers shared by the grid_viewport modules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellComment,
    CellData,
)

if TYPE_CHECKING:
    pass


class HitZone(Enum):
    NONE = auto()
    CORNER = auto()
    COL_HEADER = auto()
    ROW_HEADER = auto()
    CELL = auto()
    COL_RESIZE = auto()
    ROW_RESIZE = auto()
    FILL_HANDLE = auto()
    FILTER_BUTTON = auto()
    PIVOT_FILTER_BUTTON = auto()
    BORDER = auto()


class HitResult:
    """Result of hit testing mouse position."""

    def __init__(
        self,
        zone: HitZone,
        row: int | None = None,
        col: int | None = None,
        pos: int | None = None,
    ) -> None:
        self.zone = zone
        self.row = row
        self.col = col
        self.pos = pos


@dataclass
class DragSnapshot:
    """Snapshot of grid state prior to initiating a drag interaction."""

    zone: HitZone
    sheet_index: int
    selection_snapshot: dict[str, Any]
    resize_index: int = -1
    resize_orig_size: int = 0
    resize_orig_sizes: dict[int, int] | None = None
    fill_start_src: SelectionRange | None = None
    move_start_src: SelectionRange | None = None
    move_grab_cell: tuple[int, int] | None = None


def page_bounds(breaks: list[int], total: int, per_page: int) -> list[int]:
    """Return page boundary indices from 0 covering ``total`` rows/cols.

    Stored manual breaks (first index of the next page) are honoured; gaps
    longer than ``per_page`` are split with automatic breaks every ``per_page``.
    """
    per_page = max(1, per_page)
    stored = sorted(b for b in breaks if b > 0)
    bounds = [0]
    cur = 0
    while cur < max(1, total):
        nxt = next((b for b in stored if b > cur), None)
        cur = nxt if nxt is not None and nxt <= cur + per_page else cur + per_page
        bounds.append(cur)
    return bounds


def cell_delta(
    before: dict[tuple[int, int], CellData], after: dict[tuple[int, int], CellData]
) -> tuple[dict[tuple[int, int], CellData | None], dict[tuple[int, int], CellData | None]]:
    """The cells that differ between two copies, as (old values, new values).

    A missing cell is recorded as None on that side.
    """
    old: dict[tuple[int, int], CellData | None] = {}
    new: dict[tuple[int, int], CellData | None] = {}
    for key in before.keys() | after.keys():
        a, b = before.get(key), after.get(key)
        if a is None and b is None:
            continue
        if a is not None and b is not None and vars(a) == vars(b):
            continue
        old[key] = a
        new[key] = b
    return old, new


def _copy_comments(model: Any) -> dict[Any, Any]:
    comments = getattr(model, "comments", None)
    if not comments:
        return {}
    return {k: CellComment(**v.__dict__) for k, v in comments.items()}


def _copy_links(model: Any) -> list[Any]:
    return [dict(lk) if isinstance(lk, dict) else lk for lk in getattr(model, "links", None) or []]
