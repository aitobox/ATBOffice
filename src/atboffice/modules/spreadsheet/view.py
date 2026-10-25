"""Spreadsheet view component containing the virtualized grid viewport."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QVBoxLayout, QWidget

from atboffice.modules.spreadsheet.models.selection_model import SelectionModel
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
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

        self.grid = GridViewport(
            model=self.model, selection=self.selection, parent=self
        )
        layout.addWidget(self.grid)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Retranslate all UI strings in this view."""
        self.grid.retranslate_ui()
