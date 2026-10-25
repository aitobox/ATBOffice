"""Dynamic array spill manager and #SPILL! collision resolution engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext
from atboffice.modules.spreadsheet.calc.errors import SPILL, is_error
from atboffice.modules.spreadsheet.calc.evaluator import evaluate, evaluate_ast
from atboffice.modules.spreadsheet.calc.parser import ASTNode
from atboffice.modules.spreadsheet.calc.references import MAXC, MAXR


@dataclass(frozen=True, slots=True)
class SpillRange:
    """Rectangular range of cells covered by a spilled dynamic array."""

    sheet: str
    origin_r: int
    origin_c: int
    r1: int
    c1: int
    r2: int
    c2: int

    @property
    def rows(self) -> int:
        return self.r2 - self.r1 + 1

    @property
    def cols(self) -> int:
        return self.c2 - self.c1 + 1

    def contains(self, r: int, c: int) -> bool:
        return self.r1 <= r <= self.r2 and self.c1 <= c <= self.c2


class SpillManager:
    """Tracks and coordinates dynamic array spills and handles obstruction collisions."""

    def __init__(self) -> None:
        # Maps (sheet, origin_r, origin_c) -> SpillRange
        self.spills: dict[tuple[str, int, int], SpillRange] = {}
        # Maps (sheet, r, c) -> (origin_r, origin_c)
        self.spill_cells: dict[tuple[str, int, int], tuple[int, int]] = {}

    def get_spill_range(self, sheet: str, r: int, c: int) -> SpillRange | None:
        """Return SpillRange if (sheet, r, c) is an origin or spilled cell."""
        origin = self.spill_cells.get((sheet, r, c))
        if origin is not None:
            return self.spills.get((sheet, origin[0], origin[1]))
        return self.spills.get((sheet, r, c))

    def is_spilled_cell(self, sheet: str, r: int, c: int) -> bool:
        """Return True if (r, c) is an extension cell of an array spill."""
        return (sheet, r, c) in self.spill_cells

    def clear_spill(self, sheet: str, r: int, c: int, ctx: EvalContext | None = None) -> None:
        """Remove any active spill originating from (sheet, r, c)."""
        key = (sheet, r, c)
        if key in self.spills:
            spill = self.spills.pop(key)
            for rr in range(spill.r1, spill.r2 + 1):
                for cc in range(spill.c1, spill.c2 + 1):
                    cell_key = (sheet, rr, cc)
                    if self.spill_cells.get(cell_key) == (r, c):
                        del self.spill_cells[cell_key]
                        if (rr, cc) != (r, c) and ctx is not None and sheet in ctx.workbook_data:
                            ctx.workbook_data[sheet].pop((rr, cc), None)

    def evaluate_and_spill(
        self,
        sheet: str,
        r: int,
        c: int,
        formula_or_ast: str | ASTNode,
        ctx: EvalContext,
    ) -> Any:
        """Evaluate formula, manage spill rectangle, and detect #SPILL! collisions."""
        # Clear existing spill from this origin cell
        self.clear_spill(sheet, r, c, ctx)

        # Ensure sheet dictionary exists in ctx.workbook_data
        if sheet not in ctx.workbook_data:
            ctx.workbook_data[sheet] = {}

        # Set evaluation origin coordinates
        ctx.current_sheet = sheet
        ctx.current_row = r
        ctx.current_col = c

        if isinstance(formula_or_ast, str):
            res = evaluate(formula_or_ast, ctx)
        else:
            res = evaluate_ast(formula_or_ast, ctx)

        if is_error(res):
            ctx.workbook_data[sheet][(r, c)] = res
            return res

        if not isinstance(res, Arr):
            ctx.workbook_data[sheet][(r, c)] = res
            return res

        # Handle Array result
        rows = res.rows
        cols = res.cols
        if rows == 0 or cols == 0:
            ctx.workbook_data[sheet][(r, c)] = res
            return res

        r2 = r + rows - 1
        c2 = c + cols - 1

        # Check bounds
        if r2 >= MAXR or c2 >= MAXC:
            ctx.workbook_data[sheet][(r, c)] = SPILL
            return SPILL

        # Check for collisions with non-empty cells or other spills
        for rr in range(r, r2 + 1):
            for cc in range(c, c2 + 1):
                if (rr, cc) == (r, c):
                    continue

                # Check if cell has static or formula data
                existing = ctx.get_cell_value(sheet, rr, cc)
                if existing is not None and existing != "":
                    ctx.workbook_data[sheet][(r, c)] = SPILL
                    return SPILL

                # Check if occupied by another spill
                occupying_origin = self.spill_cells.get((sheet, rr, cc))
                if occupying_origin is not None and occupying_origin != (r, c):
                    ctx.workbook_data[sheet][(r, c)] = SPILL
                    return SPILL

        # No collision: register spill and write matrix values
        spill_range = SpillRange(sheet=sheet, origin_r=r, origin_c=c, r1=r, c1=c, r2=r2, c2=c2)
        self.spills[(sheet, r, c)] = spill_range

        for rr in range(r, r2 + 1):
            for cc in range(c, c2 + 1):
                cell_val = res.get(rr - r, cc - c)
                ctx.workbook_data[sheet][(rr, cc)] = cell_val
                if (rr, cc) != (r, c):
                    self.spill_cells[(sheet, rr, cc)] = (r, c)

        return res
