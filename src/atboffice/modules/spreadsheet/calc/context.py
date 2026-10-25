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

    def get_cell_value(self, sheet: str, r: int, c: int) -> Any:
        if self.cell_getter is not None:
            return self.cell_getter(sheet, r, c)
        if sheet in self.workbook_data:
            return self.workbook_data[sheet].get((r, c), None)
        return None

    def create_ref(
        self, sheet: str, r1: int, c1: int, r2: int | None = None, c2: int | None = None
    ) -> Ref:
        return Ref(sheet, r1, c1, r2, c2, getter=self.get_cell_value)
