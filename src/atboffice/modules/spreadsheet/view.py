"""Spreadsheet view component containing the FormulaBar, GridViewport, and EditorController."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionModel,
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.editor_controller import (
    EditorController,
)
from atboffice.modules.spreadsheet.views.formula_bar import FormulaBar
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport
from atboffice.modules.spreadsheet.views.sheet_tab_bar import SheetTabBar


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("SpreadsheetView", text)


class SpreadsheetView(QWidget):
    """Top-level view for ATBOffice Ledger spreadsheet editing."""

    def __init__(
        self,
        workbook: WorkbookModel | None = None,
        model: SheetDataModel | None = None,
        selection: SelectionModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # 1. Manage WorkbookModel and per-sheet selections
        if workbook is not None:
            self._workbook = workbook
        elif model is not None:
            self._workbook = WorkbookModel(sheets=[model])
        else:
            self._workbook = WorkbookModel()

        self._sheet_selections: dict[SheetDataModel, SelectionModel] = {}
        active_sheet = self._workbook.active_sheet
        if selection is not None:
            self._sheet_selections[active_sheet] = selection
        else:
            self._sheet_selections[active_sheet] = SelectionModel()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 2. Top Formula Bar
        self.formula_bar = FormulaBar(self)
        layout.addWidget(self.formula_bar)

        # 3. Virtualized Grid Viewport
        active_sel = self._sheet_selections[active_sheet]
        self.grid = GridViewport(
            model=active_sheet, selection=active_sel, parent=self
        )
        layout.addWidget(self.grid)

        # 4. In-cell editor & formula controller
        self.editor_controller = EditorController(
            viewport=self.grid,
            model=active_sheet,
            selection=active_sel,
            formula_bar=self.formula_bar,
            parent=self,
        )
        self.grid.editor_controller = self.editor_controller

        # Connect navigation requests from NameBox
        self.formula_bar.navigate_requested.connect(self._on_navigate_requested)
        self.formula_bar.range_navigate_requested.connect(
            self._on_range_navigate_requested
        )

        # Connect workbook signals for active sheet synchronization and cleanup
        self._workbook.active_sheet_changed.connect(self._on_active_sheet_changed)
        self._workbook.sheet_removed.connect(self._on_sheet_removed)

        # 5. Bottom SheetTabBar embedded in grid viewport scrollbar
        self.sheet_tab_bar = SheetTabBar(workbook=self._workbook, parent=self)
        self.grid.addScrollBarWidget(self.sheet_tab_bar, Qt.AlignmentFlag.AlignLeft)

        self.retranslate_ui()

    @property
    def workbook(self) -> WorkbookModel:
        """Return the bound WorkbookModel."""
        return self._workbook

    @property
    def model(self) -> SheetDataModel:
        """Return the active SheetDataModel for backward compatibility."""
        return self._workbook.active_sheet

    @model.setter
    def model(self, value: SheetDataModel) -> None:
        idx = self._workbook.sheet_index(value)
        if idx != -1:
            self.set_active_sheet_index(idx)
        else:
            self._workbook.add_sheet(sheet=value)
            self.set_active_sheet_index(len(self._workbook) - 1)

    @property
    def selection(self) -> SelectionModel:
        """Return the active SelectionModel for the current worksheet."""
        return self._get_selection_for_sheet(self._workbook.active_sheet)

    def _get_selection_for_sheet(self, sheet: SheetDataModel) -> SelectionModel:
        if sheet not in self._sheet_selections:
            self._sheet_selections[sheet] = SelectionModel()
        return self._sheet_selections[sheet]

    def set_active_sheet_index(self, index: int) -> None:
        """Switch active worksheet by index."""
        self._workbook.set_active_sheet_index(index)

    def _on_active_sheet_changed(self, index: int) -> None:
        """Synchronize viewport and editor with newly activated worksheet."""
        active_sheet = self._workbook.active_sheet
        active_sel = self._get_selection_for_sheet(active_sheet)

        self.grid.set_model_and_selection(active_sheet, active_sel)
        self.editor_controller.set_model_and_selection(active_sheet, active_sel)
        self.grid.viewport().update()

    def _on_sheet_removed(self, index: int, name: str) -> None:
        """Clean up cached selections for removed worksheets."""
        current_sheets = set(self._workbook.sheets)
        dead_keys = [s for s in self._sheet_selections if s not in current_sheets]
        for s in dead_keys:
            self._sheet_selections.pop(s, None)

    def _on_navigate_requested(self, r: int, c: int) -> None:
        """Handle single cell navigation requested from NameBox."""
        self.selection.select_cell(r, c)
        self.grid.reveal(r, c)
        self.grid.viewport().update()

    def _on_range_navigate_requested(
        self, r1: int, c1: int, r2: int, c2: int
    ) -> None:
        """Handle range navigation requested from NameBox."""
        self.selection.clear()
        self.selection.add_range(SelectionRange(r1, c1, r2, c2))
        self.selection.set_active_cell(r1, c1)
        self.grid.reveal(r1, c1)
        self.grid.viewport().update()

    def retranslate_ui(self) -> None:
        """Retranslate all UI strings in this view."""
        self.formula_bar.retranslate_ui()
        self.grid.retranslate_ui()
        if hasattr(self, "sheet_tab_bar") and self.sheet_tab_bar is not None:
            self.sheet_tab_bar.retranslate_ui()
