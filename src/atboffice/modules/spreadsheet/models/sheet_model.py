"""Spreadsheet cell data model and lightweight virtualized geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from atboffice.drawing.numfmt import format_value
from atboffice.modules.spreadsheet.calc.references import MAXC, MAXR


@dataclass
class BorderStyle:
    """Border line style and color."""

    style: str = "thin"
    color: str | None = None


@dataclass
class CellData:
    """Cell storage representation."""

    value: Any = None
    formula: str | None = None
    format_code: str = "General"
    bold: bool = False
    italic: bool = False
    underline: bool = False
    underline_style: str = "none"
    strike: bool = False
    vert_align: str | None = None
    font_size: int = 10
    font_family: str = "Arial"
    fg_color: str | None = None
    bg_color: str | None = None
    align_h: str = "general"
    align_v: str = "bottom"
    indent: int = 0
    wrap_text: bool = False
    shrink_to_fit: bool = False
    text_rotation: int = 0
    text_direction: str = "context"
    just_last: bool = False

    # Borders
    border_top: BorderStyle | None = None
    border_bottom: BorderStyle | None = None
    border_left: BorderStyle | None = None
    border_right: BorderStyle | None = None
    border_diag_up: BorderStyle | None = None
    border_diag_down: BorderStyle | None = None

    # Patterns
    pattern: str | None = None
    pattern_color: str | None = None

    # Protection
    locked: bool = True
    hidden: bool = False


@dataclass
class FormatDelta:
    """Style modification payload to apply to cells."""

    format_code: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    underline_style: str | None = None
    strike: bool | None = None
    vert_align: str | None = None
    font_size: int | None = None
    font_family: str | None = None
    fg_color: str | None = None
    bg_color: str | None = None
    align_h: str | None = None
    align_v: str | None = None
    indent: int | None = None
    wrap_text: bool | None = None
    shrink_to_fit: bool | None = None
    text_rotation: int | None = None
    text_direction: str | None = None
    just_last: bool | None = None

    border_top: BorderStyle | None = None
    border_bottom: BorderStyle | None = None
    border_left: BorderStyle | None = None
    border_right: BorderStyle | None = None
    border_diag_up: BorderStyle | None = None
    border_diag_down: BorderStyle | None = None
    clear_borders: bool = False

    pattern: str | None = None
    pattern_color: str | None = None
    clear_fill: bool = False

    locked: bool | None = None
    hidden: bool | None = None


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
        self.merges: list[tuple[int, int, int, int]] = []
        self.auto_filter: Any | None = None

    def add_merge(self, r1: int, c1: int, r2: int, c2: int) -> None:
        """Add a merged cell region (r1, c1, r2, c2)."""
        min_r, max_r = min(r1, r2), max(r1, r2)
        min_c, max_c = min(c1, c2), max(c1, c2)
        self.merges = [
            m
            for m in self.merges
            if not (
                min_r <= m[2]
                and max_r >= m[0]
                and min_c <= m[3]
                and max_c >= m[1]
            )
        ]
        self.merges.append((min_r, min_c, max_r, max_c))

    def remove_merge(self, r: int, c: int) -> None:
        """Remove any merge containing cell (r, c)."""
        self.merges = [
            m
            for m in self.merges
            if not (m[0] <= r <= m[2] and m[1] <= c <= m[3])
        ]

    def is_merged(self, r: int, c: int) -> bool:
        """Return True if (r, c) is part of a merged region."""
        return any(
            m[0] <= r <= m[2] and m[1] <= c <= m[3] for m in self.merges
        )

    def get_merge_range(
        self, r: int, c: int
    ) -> tuple[int, int, int, int] | None:
        """Return the (min_r, min_c, max_r, max_c) region for cell (r, c) or None."""
        for m in self.merges:
            if m[0] <= r <= m[2] and m[1] <= c <= m[3]:
                return m
        return None

    def apply_format_delta(
        self, r: int, c: int, delta: FormatDelta
    ) -> CellData:
        """Apply style modifications in delta to cell (r, c)."""
        cell = self.get_cell(r, c)
        if cell is None:
            cell = CellData()
            self.set_cell(r, c, cell)

        if delta.format_code is not None:
            cell.format_code = delta.format_code
        if delta.bold is not None:
            cell.bold = delta.bold
        if delta.italic is not None:
            cell.italic = delta.italic
        if delta.underline is not None:
            cell.underline = delta.underline
        if delta.underline_style is not None:
            cell.underline_style = delta.underline_style
            cell.underline = delta.underline_style != "none"
        if delta.strike is not None:
            cell.strike = delta.strike
        if delta.vert_align is not None:
            cell.vert_align = delta.vert_align
        if delta.font_size is not None:
            cell.font_size = delta.font_size
        if delta.font_family is not None:
            cell.font_family = delta.font_family
        if delta.fg_color is not None:
            cell.fg_color = delta.fg_color
        if delta.bg_color is not None:
            cell.bg_color = delta.bg_color
        if delta.align_h is not None:
            cell.align_h = delta.align_h
        if delta.align_v is not None:
            cell.align_v = delta.align_v
        if delta.indent is not None:
            cell.indent = delta.indent
        if delta.wrap_text is not None:
            cell.wrap_text = delta.wrap_text
        if delta.shrink_to_fit is not None:
            cell.shrink_to_fit = delta.shrink_to_fit
        if delta.text_rotation is not None:
            cell.text_rotation = delta.text_rotation
        if delta.text_direction is not None:
            cell.text_direction = delta.text_direction
        if delta.just_last is not None:
            cell.just_last = delta.just_last

        if delta.clear_borders:
            cell.border_top = None
            cell.border_bottom = None
            cell.border_left = None
            cell.border_right = None
            cell.border_diag_up = None
            cell.border_diag_down = None
        else:
            if delta.border_top is not None:
                cell.border_top = delta.border_top
            if delta.border_bottom is not None:
                cell.border_bottom = delta.border_bottom
            if delta.border_left is not None:
                cell.border_left = delta.border_left
            if delta.border_right is not None:
                cell.border_right = delta.border_right
            if delta.border_diag_up is not None:
                cell.border_diag_up = delta.border_diag_up
            if delta.border_diag_down is not None:
                cell.border_diag_down = delta.border_diag_down

        if delta.clear_fill:
            cell.bg_color = None
            cell.pattern = None
            cell.pattern_color = None
        else:
            if delta.pattern is not None:
                cell.pattern = delta.pattern
            if delta.pattern_color is not None:
                cell.pattern_color = delta.pattern_color

        if delta.locked is not None:
            cell.locked = delta.locked
        if delta.hidden is not None:
            cell.hidden = delta.hidden

        return cell

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
