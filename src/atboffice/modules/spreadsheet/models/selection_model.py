"""Spreadsheet selection state machine and range primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QObject, Signal

MAXR: Final[int] = 1048576
MAXC: Final[int] = 16384


@dataclass(frozen=True)
class SelectionRange:
    """A rectangular range of cells with normalized coordinates."""

    r1: int
    c1: int
    r2: int
    c2: int

    @property
    def min_r(self) -> int:
        return min(self.r1, self.r2)

    @property
    def max_r(self) -> int:
        return max(self.r1, self.r2)

    @property
    def min_c(self) -> int:
        return min(self.c1, self.c2)

    @property
    def max_c(self) -> int:
        return max(self.c1, self.c2)

    def contains(self, r: int, c: int) -> bool:
        """Check if cell (r, c) is inside this rectangular range."""
        return self.min_r <= r <= self.max_r and self.min_c <= c <= self.max_c

    def overlaps(self, other: SelectionRange) -> bool:
        """Check if this range overlaps with another range."""
        return not (
            self.max_r < other.min_r
            or self.min_r > other.max_r
            or self.max_c < other.min_c
            or self.min_c > other.max_c
        )


class SelectionModel(QObject):
    """Multi-mode selection state machine supporting single, marquee, and multi-range selections."""

    active_cell_changed = Signal(int, int)
    selection_changed = Signal()

    def __init__(
        self,
        max_rows: int = MAXR,
        max_cols: int = MAXC,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.max_rows = max_rows
        self.max_cols = max_cols
        self._active_cell: tuple[int, int] = (0, 0)
        self._anchor_cell: tuple[int, int] = (0, 0)
        self._ranges: list[SelectionRange] = [SelectionRange(0, 0, 0, 0)]

    @property
    def active_cell(self) -> tuple[int, int]:
        return self._active_cell

    @property
    def anchor_cell(self) -> tuple[int, int]:
        return self._anchor_cell

    @property
    def ranges(self) -> list[SelectionRange]:
        return self._ranges

    @property
    def primary_range(self) -> SelectionRange:
        return self._ranges[-1] if self._ranges else SelectionRange(0, 0, 0, 0)

    def set_active_cell(self, r: int, c: int) -> None:
        """Explicitly set active cell coordinates."""
        r = max(0, min(self.max_rows - 1, r))
        c = max(0, min(self.max_cols - 1, c))
        self._active_cell = (r, c)
        self.active_cell_changed.emit(r, c)
        self.selection_changed.emit()

    def clear(self) -> None:
        """Clear all active selection ranges."""
        self._ranges = []
        self.selection_changed.emit()

    def select_cell(self, r: int, c: int) -> None:
        """Select a single cell, resetting active, anchor, and ranges."""
        r = max(0, min(self.max_rows - 1, r))
        c = max(0, min(self.max_cols - 1, c))
        self._active_cell = (r, c)
        self._anchor_cell = (r, c)
        self._ranges = [SelectionRange(r, c, r, c)]
        self.active_cell_changed.emit(r, c)
        self.selection_changed.emit()

    def extend_to(self, r: int, c: int) -> None:
        """Extend the current selection range from the anchor to (r, c)."""
        r = max(0, min(self.max_rows - 1, r))
        c = max(0, min(self.max_cols - 1, c))
        self._active_cell = (r, c)
        new_range = SelectionRange(self._anchor_cell[0], self._anchor_cell[1], r, c)
        if self._ranges:
            self._ranges[-1] = new_range
        else:
            self._ranges = [new_range]
        self.active_cell_changed.emit(r, c)
        self.selection_changed.emit()

    def add_range(self, rg: SelectionRange) -> None:
        """Add an additional range (for Ctrl/Cmd click)."""
        self._ranges.append(rg)
        self._active_cell = (rg.r2, rg.c2)
        self._anchor_cell = (rg.r1, rg.c1)
        self.active_cell_changed.emit(self._active_cell[0], self._active_cell[1])
        self.selection_changed.emit()

    def select_rows(self, r1: int, r2: int) -> None:
        """Select entire rows across all columns."""
        min_r = max(0, min(r1, r2))
        max_r = min(self.max_rows - 1, max(r1, r2))
        self._active_cell = (min_r, 0)
        self._anchor_cell = (min_r, 0)
        self._ranges = [SelectionRange(min_r, 0, max_r, self.max_cols - 1)]
        self.active_cell_changed.emit(min_r, 0)
        self.selection_changed.emit()

    def select_cols(self, c1: int, c2: int) -> None:
        """Select entire columns across all rows."""
        min_c = max(0, min(c1, c2))
        max_c = min(self.max_cols - 1, max(c1, c2))
        self._active_cell = (0, min_c)
        self._anchor_cell = (0, min_c)
        self._ranges = [SelectionRange(0, min_c, self.max_rows - 1, max_c)]
        self.active_cell_changed.emit(0, min_c)
        self.selection_changed.emit()

    def select_all(self) -> None:
        """Select the entire worksheet."""
        self._active_cell = (0, 0)
        self._anchor_cell = (0, 0)
        self._ranges = [SelectionRange(0, 0, self.max_rows - 1, self.max_cols - 1)]
        self.active_cell_changed.emit(0, 0)
        self.selection_changed.emit()

    def is_selected(self, r: int, c: int) -> bool:
        """Check if cell (r, c) falls within any active selection range."""
        return any(rg.contains(r, c) for rg in self._ranges)

    def is_row_selected(self, r: int) -> bool:
        """Check if row r is within any selection range."""
        return any(rg.min_r <= r <= rg.max_r for rg in self._ranges)

    def is_col_selected(self, c: int) -> bool:
        """Check if column c is within any selection range."""
        return any(rg.min_c <= c <= rg.max_c for rg in self._ranges)
