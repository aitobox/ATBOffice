"""Spreadsheet cell data model and lightweight virtualized geometry."""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Any, Final

from atboffice.drawing.numfmt import format_value
from atboffice.modules.spreadsheet.calc.references import MAXC, MAXR


@dataclass
class CellData:
    """Cell storage representation."""

    value: Any = None
    formula: str | None = None
    format_code: str = "General"
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_size: int = 10
    font_family: str = "Arial"
    fg_color: str | None = None
    bg_color: str | None = None
    align_h: str = "general"  # "general", "left", "center", "right"
    align_v: str = "bottom"  # "top", "center", "bottom"
    wrap_text: bool = False


class SheetGeometry:
    """Maps virtual row and column coordinates to pixel offsets.

    Efficiently supports 1,000,000+ rows and 16,384 columns without large allocations.
    """

    def __init__(
        self,
        default_row_height: int = 20,
        default_col_width: int = 64,
        max_rows: int = MAXR,
        max_cols: int = MAXC,
    ) -> None:
        self.default_row_height = default_row_height
        self.default_col_width = default_col_width
        self.max_rows = max_rows
        self.max_cols = max_cols
        self.custom_row_heights: dict[int, int] = {}
        self.custom_col_widths: dict[int, int] = {}
        self.hidden_rows: set[int] = set()
        self.hidden_cols: set[int] = set()

    def row_size(self, r: int) -> int:
        """Return height in pixels for row r."""
        if r in self.hidden_rows:
            return 0
        return self.custom_row_heights.get(r, self.default_row_height)

    def col_size(self, c: int) -> int:
        """Return width in pixels for column c."""
        if c in self.hidden_cols:
            return 0
        return self.custom_col_widths.get(c, self.default_col_width)

    def set_row_height(self, r: int, height: int) -> None:
        """Set custom height for row r."""
        self.custom_row_heights[r] = max(0, height)

    def set_col_width(self, c: int, width: int) -> None:
        """Set custom width for column c."""
        self.custom_col_widths[c] = max(0, width)

    def row_pos(self, target_r: int) -> int:
        """Calculate cumulative pixel Y offset for row target_r."""
        if not self.custom_row_heights and not self.hidden_rows:
            return target_r * self.default_row_height

        # Sparse calculation
        base = target_r * self.default_row_height
        diff = 0
        for r, h in self.custom_row_heights.items():
            if r < target_r:
                diff += h - self.default_row_height
        for r in self.hidden_rows:
            if r < target_r and r not in self.custom_row_heights:
                diff -= self.default_row_height
        return base + diff

    def col_pos(self, target_c: int) -> int:
        """Calculate cumulative pixel X offset for column target_c."""
        if not self.custom_col_widths and not self.hidden_cols:
            return target_c * self.default_col_width

        base = target_c * self.default_col_width
        diff = 0
        for c, w in self.custom_col_widths.items():
            if c < target_c:
                diff += w - self.default_col_width
        for c in self.hidden_cols:
            if c < target_c and c not in self.custom_col_widths:
                diff -= self.default_col_width
        return base + diff

    def find_row_at(self, y: int) -> int:
        """Find the 0-based row index at pixel offset y."""
        if y <= 0:
            return 0
        if not self.custom_row_heights and not self.hidden_rows:
            return min(self.max_rows - 1, y // self.default_row_height)

        # Approximate start row then scan
        approx = max(0, min(self.max_rows - 1, y // self.default_row_height))
        pos = self.row_pos(approx)
        if pos <= y:
            r = approx
            while r < self.max_rows - 1:
                next_pos = pos + self.row_size(r)
                if next_pos > y:
                    return r
                pos = next_pos
                r += 1
            return self.max_rows - 1
        else:
            r = approx
            while r > 0 and pos > y:
                r -= 1
                pos -= self.row_size(r)
            return r

    def find_col_at(self, x: int) -> int:
        """Find the 0-based column index at pixel offset x."""
        if x <= 0:
            return 0
        if not self.custom_col_widths and not self.hidden_cols:
            return min(self.max_cols - 1, x // self.default_col_width)

        approx = max(0, min(self.max_cols - 1, x // self.default_col_width))
        pos = self.col_pos(approx)
        if pos <= x:
            c = approx
            while c < self.max_cols - 1:
                next_pos = pos + self.col_size(c)
                if next_pos > x:
                    return c
                pos = next_pos
                c += 1
            return self.max_cols - 1
        else:
            c = approx
            while c > 0 and pos > x:
                c -= 1
                pos -= self.col_size(c)
            return c


class SheetDataModel:
    """In-memory sparse cell storage for a worksheet."""

    def __init__(self) -> None:
        self.cells: dict[tuple[int, int], CellData] = {}
        self.geometry = SheetGeometry()

    def get_cell(self, r: int, c: int) -> CellData | None:
        return self.cells.get((r, c))

    def set_cell(self, r: int, c: int, cell: CellData) -> None:
        self.cells[(r, c)] = cell

    def get_cell_value(self, r: int, c: int, default: Any = None) -> Any:
        cell = self.cells.get((r, c))
        return cell.value if cell is not None else default

    def set_cell_value(self, r: int, c: int, value: Any) -> None:
        cell = self.cells.get((r, c))
        if cell is None:
            cell = CellData(value=value)
            self.cells[(r, c)] = cell
        else:
            cell.value = value

    def is_empty(self, r: int, c: int) -> bool:
        cell = self.cells.get((r, c))
        if cell is None:
            return True
        return cell.value is None or cell.value == ""

    def get_formatted_text(self, r: int, c: int) -> str:
        cell = self.cells.get((r, c))
        if cell is None or cell.value is None or cell.value == "":
            return ""
        res = format_value(cell.value, cell.format_code)
        return res.text
