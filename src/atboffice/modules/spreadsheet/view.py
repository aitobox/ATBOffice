"""Spreadsheet view component containing the FormulaBar, GridViewport, and EditorController."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QVBoxLayout, QWidget

from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionModel,
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.views.editor_controller import (
    EditorController,
)
from atboffice.modules.spreadsheet.views.formula_bar import FormulaBar
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("SpreadsheetView", text)


class SpreadsheetView(QWidget):
    """Top-level view for ATBOffice Ledger spreadsheet editing."""

    def __init__(
        self,
        model: SheetDataModel | None = None,
        selection: SelectionModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.model = model if model is not None else SheetDataModel()
        self.selection = selection if selection is not None else SelectionModel()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Top Formula Bar
        self.formula_bar = FormulaBar(self)
        layout.addWidget(self.formula_bar)

        # 2. Virtualized Grid Viewport
        self.grid = GridViewport(
            model=self.model, selection=self.selection, parent=self
        )
        layout.addWidget(self.grid)

        # 3. In-cell editor & formula controller
        self.editor_controller = EditorController(
            viewport=self.grid,
            model=self.model,
            selection=self.selection,
            formula_bar=self.formula_bar,
            parent=self,
        )
        self.grid.editor_controller = self.editor_controller

        # Connect navigation requests from NameBox
        self.formula_bar.navigate_requested.connect(self._on_navigate_requested)
        self.formula_bar.range_navigate_requested.connect(
            self._on_range_navigate_requested
        )

        self.retranslate_ui()

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
