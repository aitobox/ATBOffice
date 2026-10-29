"""Runtime calculation context, reference wrappers, and 2-D array representations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class Arr:
    """A 2-D array of evaluated scalar values."""

    __slots__ = ("data",)

    def __init__(self, data: list[list[Any]]) -> None:
        self.data: list[list[Any]] = data

    @property
    def rows(self) -> int:
        return len(self.data)

    @property
    def cols(self) -> int:
        return len(self.data[0]) if self.data else 0

    def get(self, r: int, c: int, default: Any = None) -> Any:
        if 0 <= r < len(self.data) and 0 <= c < len(self.data[r]):
            return self.data[r][c]
        return default

    def to_flat_list(self) -> list[Any]:
        return [item for row in self.data for item in row]

    def __repr__(self) -> str:
        return f"Arr(rows={self.rows}, cols={self.cols}, data={self.data!r})"


class Ref:
    """A rectangular cell range reference on a worksheet."""

    __slots__ = ("sheet", "r1", "c1", "r2", "c2", "getter")

    def __init__(
        self,
        sheet: str,
        r1: int,
        c1: int,
        r2: int | None = None,
        c2: int | None = None,
        getter: Callable[[str, int, int], Any] | None = None,
    ) -> None:
        self.sheet: str = sheet
        self.r1: int = min(r1, r1 if r2 is None else r2)
        self.c1: int = min(c1, c1 if c2 is None else c2)
        self.r2: int = max(r1, r1 if r2 is None else r2)
        self.c2: int = max(c1, c1 if c2 is None else c2)
        self.getter: Callable[[str, int, int], Any] | None = getter

    @property
    def rows(self) -> int:
        return self.r2 - self.r1 + 1

    @property
    def cols(self) -> int:
        return self.c2 - self.c1 + 1

    @property
    def single(self) -> bool:
        return self.r1 == self.r2 and self.c1 == self.c2

    def cell_value(self, r: int, c: int) -> Any:
        if self.getter is not None:
            return self.getter(self.sheet, r, c)
        return None

    def to_array(self) -> Arr:
        out: list[list[Any]] = []
        for r in range(self.r1, self.r2 + 1):
            row: list[Any] = []
            for c in range(self.c1, self.c2 + 1):
                row.append(self.cell_value(r, c))
            out.append(row)
        return Arr(out)

    def __repr__(self) -> str:
        return f"Ref(sheet={self.sheet!r}, r1={self.r1}, c1={self.c1}, r2={self.r2}, c2={self.c2})"


@dataclass
class EvalContext:
    """Evaluation state and cell resolving hooks for formula calculation."""

    cell_getter: Callable[[str, int, int], Any] | None = None
    date1904: bool = False
    array_mode: bool = False
    current_sheet: str = "Sheet1"
    current_row: int = 0
    current_col: int = 0
    workbook_data: dict[str, dict[tuple[int, int], Any]] = field(default_factory=dict)
    vars: dict[str, Any] = field(default_factory=dict)
    workbook: Any | None = None
    visiting: set[tuple[str, int, int]] = field(default_factory=set)

    def with_vars(self, extra_vars: dict[str, Any]) -> EvalContext:
        """Create a child evaluation context with additional local variables."""
        merged_vars = dict(self.vars)
        merged_vars.update(extra_vars)
        return EvalContext(
            cell_getter=self.cell_getter,
            date1904=self.date1904,
            array_mode=self.array_mode,
            current_sheet=self.current_sheet,
            current_row=self.current_row,
            current_col=self.current_col,
            workbook_data=self.workbook_data,
            vars=merged_vars,
            workbook=self.workbook,
            visiting=self.visiting,
        )

    def get_cell_value(self, sheet: str, r: int, c: int) -> Any:
        target_sheet = sheet or self.current_sheet
        key = (target_sheet.lower(), r, c)

        if self.cell_getter is not None:
            return self.cell_getter(target_sheet, r, c)

        if self.workbook is not None:
            sh = None
            if hasattr(self.workbook, "get_sheet_by_name"):
                sh = self.workbook.get_sheet_by_name(target_sheet)
            if sh is not None:
                if hasattr(sh, "get_cell"):
                    cell = sh.get_cell(r, c)
                    if cell is not None:
                        formula = getattr(cell, "formula", None)
                        if formula and cell.value is None:
                            if key in self.visiting:
                                from atboffice.modules.spreadsheet.calc.errors import CYCLE

                                return CYCLE
                            from atboffice.modules.spreadsheet.calc.evaluator import evaluate

                            self.visiting.add(key)
                            try:
                                return evaluate(formula, self)
                            finally:
                                self.visiting.discard(key)
                        return getattr(cell, "value", None)
                    return None
                if hasattr(sh, "get_cell_value"):
                    return sh.get_cell_value(r, c)
            else:
                from atboffice.modules.spreadsheet.calc.errors import REF

                return REF

        if target_sheet in self.workbook_data:
            return self.workbook_data[target_sheet].get((r, c), None)

        for s_name, s_data in self.workbook_data.items():
            if s_name.lower() == target_sheet.lower():
                return s_data.get((r, c), None)

        return None

    def create_ref(
        self, sheet: str, r1: int, c1: int, r2: int | None = None, c2: int | None = None
    ) -> Ref:
        target_sheet = sheet or self.current_sheet
        return Ref(target_sheet, r1, c1, r2, c2, getter=self.get_cell_value)
