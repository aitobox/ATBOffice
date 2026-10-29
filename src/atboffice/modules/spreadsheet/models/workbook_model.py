"""Workbook container model managing multiple SheetDataModel worksheets."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QObject, Signal

from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel

INVALID_SHEET_CHARS = set(r":\/?*[]")
MAX_SHEET_NAME_LEN = 31


def is_valid_sheet_name(name: str) -> bool:
    """Validate sheet name against Excel naming constraints."""
    if not name or not name.strip():
        return False
    if len(name) > MAX_SHEET_NAME_LEN:
        return False
    if any(c in INVALID_SHEET_CHARS for c in name):
        return False
    if name.startswith("'") or name.endswith("'"):
        return False
    return True


class WorkbookModel(QObject):
    """Multi-sheet workbook data model container for Ledger spreadsheet.

    Emits Qt signals when worksheets are added, removed, renamed, reordered,
    or when the active worksheet changes.
    """

    sheet_added = Signal(int, str)  # (index, sheet_name)
    sheet_removed = Signal(int, str)  # (index, sheet_name)
    sheet_renamed = Signal(int, str, str)  # (index, old_name, new_name)
    sheet_moved = Signal(int, int)  # (from_index, to_index)
    active_sheet_changed = Signal(int)  # (new_active_index)

    def __init__(
        self,
        sheets: Sequence[SheetDataModel] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sheets: list[SheetDataModel] = []
        self._active_sheet_index: int = 0

        if sheets:
            for s in sheets:
                self.add_sheet(name=s.name, sheet=s)
        else:
            # Default single worksheet
            self._sheets.append(SheetDataModel(name="Sheet1"))
            self._active_sheet_index = 0

    @property
    def sheets(self) -> list[SheetDataModel]:
        """Return shallow copy of worksheets in workbook."""
        return list(self._sheets)

    def __len__(self) -> int:
        return len(self._sheets)

    def __getitem__(self, index: int) -> SheetDataModel:
        return self._sheets[index]

    @property
    def active_sheet_index(self) -> int:
        """Return index of current active worksheet."""
        return self._active_sheet_index

    @property
    def active_sheet(self) -> SheetDataModel:
        """Return currently active SheetDataModel."""
        if not self._sheets:
            raise IndexError("Workbook contains no worksheets.")
        return self._sheets[self._active_sheet_index]

    def set_active_sheet_index(self, index: int) -> None:
        """Set the active worksheet by its 0-based index."""
        if index < 0 or index >= len(self._sheets):
            raise IndexError(
                f"Worksheet index {index} out of range [0, {len(self._sheets) - 1}]."
            )
        if index != self._active_sheet_index:
            self._active_sheet_index = index
            self.active_sheet_changed.emit(self._active_sheet_index)

    def set_active_sheet(self, sheet: SheetDataModel) -> None:
        """Set the active worksheet by SheetDataModel reference."""
        idx = self.sheet_index(sheet)
        if idx == -1:
            raise ValueError(f"Worksheet '{sheet.name}' not found in workbook.")
        self.set_active_sheet_index(idx)

    def sheet_index(self, sheet: SheetDataModel) -> int:
        """Return 0-based index of worksheet or -1 if not found."""
        try:
            return self._sheets.index(sheet)
        except ValueError:
            return -1

    def get_sheet_by_name(self, name: str) -> SheetDataModel | None:
        """Case-insensitive search for a worksheet by name."""
        if not name:
            return None
        target = name.strip().lower()
        for s in self._sheets:
            if s.name.lower() == target:
                return s
        return None

    def next_sheet_name(self, prefix: str = "Sheet") -> str:
        """Generate next available non-conflicting default worksheet name."""
        i = 1
        while self.get_sheet_by_name(f"{prefix}{i}") is not None:
            i += 1
        return f"{prefix}{i}"

    def validate_new_name(self, name: str, current_index: int | None = None) -> None:
        """Validate a proposed worksheet name against Excel constraints and duplicates."""
        if not is_valid_sheet_name(name):
            raise ValueError(
                f"Invalid sheet name '{name}'. Names must be 1-31 characters, "
                "cannot start or end with single quotes, and cannot contain :\\/?*[]"
            )
        target = name.strip().lower()
        for idx, s in enumerate(self._sheets):
            if current_index is not None and idx == current_index:
                continue
            if s.name.lower() == target:
                raise ValueError(
                    f"A worksheet named '{s.name}' already exists in the workbook."
                )

    def add_sheet(
        self,
        name: str | None = None,
        index: int | None = None,
        sheet: SheetDataModel | None = None,
    ) -> SheetDataModel:
        """Add a new or existing SheetDataModel into the workbook."""
        final_name = name or (sheet.name if sheet and sheet.name else self.next_sheet_name())
        self.validate_new_name(final_name)

        new_sheet = sheet if sheet is not None else SheetDataModel(name=final_name)
        new_sheet.name = final_name

        if index is None or index >= len(self._sheets):
            insert_idx = len(self._sheets)
            self._sheets.append(new_sheet)
        else:
            insert_idx = max(0, index)
            self._sheets.insert(insert_idx, new_sheet)
            # If inserted before or at active sheet, bump active index
            if insert_idx <= self._active_sheet_index and len(self._sheets) > 1:
                self._active_sheet_index += 1

        self.sheet_added.emit(insert_idx, final_name)
        return new_sheet

    def remove_sheet(self, index: int) -> SheetDataModel:
        """Remove worksheet at index. Prevents deleting the only remaining worksheet."""
        if len(self._sheets) <= 1:
            raise ValueError("Cannot remove the only remaining worksheet in the workbook.")
        if index < 0 or index >= len(self._sheets):
            raise IndexError(f"Worksheet index {index} out of range [0, {len(self._sheets) - 1}].")

        removed = self._sheets.pop(index)
        old_active = self._active_sheet_index

        if index < old_active:
            self._active_sheet_index -= 1
        elif index == old_active:
            # Active sheet was removed; clamp to valid range
            self._active_sheet_index = min(index, len(self._sheets) - 1)
            self.active_sheet_changed.emit(self._active_sheet_index)

        self.sheet_removed.emit(index, removed.name)
        return removed

    def rename_sheet(self, index: int, new_name: str) -> None:
        """Rename worksheet at index."""
        if index < 0 or index >= len(self._sheets):
            raise IndexError(f"Worksheet index {index} out of range [0, {len(self._sheets) - 1}].")

        sheet = self._sheets[index]
        if sheet.name == new_name:
            return  # No-op

        self.validate_new_name(new_name, current_index=index)
        old_name = sheet.name
        sheet.name = new_name
        self.sheet_renamed.emit(index, old_name, new_name)

    def move_sheet(self, from_index: int, to_index: int) -> None:
        """Move worksheet from from_index to to_index."""
        count = len(self._sheets)
        if from_index < 0 or from_index >= count:
            raise IndexError(f"from_index {from_index} out of range [0, {count - 1}].")
        if to_index < 0 or to_index >= count:
            raise IndexError(f"to_index {to_index} out of range [0, {count - 1}].")
        if from_index == to_index:
            return

        active_sheet_ref = self.active_sheet
        sheet = self._sheets.pop(from_index)
        self._sheets.insert(to_index, sheet)

        # Recalculate active index so the active sheet pointer remains unchanged
        self._active_sheet_index = self._sheets.index(active_sheet_ref)

        self.sheet_moved.emit(from_index, to_index)

    def recalculate(self) -> Any:
        """Recalculate all formulas across all worksheets using dependency DAG."""
        from atboffice.modules.spreadsheet.calc.dag import DependencyGraph

        graph = DependencyGraph()
        return graph.recalculate(self)
