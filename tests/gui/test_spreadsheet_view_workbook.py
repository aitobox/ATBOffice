"""GUI integration tests for SpreadsheetView and WorkbookModel."""

from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.view import SpreadsheetView


class TestSpreadsheetViewWorkbook:
    """Integration test suite for SpreadsheetView multi-sheet support."""

    def test_default_initialization(self, qapp: QApplication) -> None:
        view = SpreadsheetView()
        assert view.workbook is not None
        assert len(view.workbook) == 1
        assert view.model is view.workbook.active_sheet
        assert view.model.name == "Sheet1"

    def test_backward_compatibility_with_model(self, qapp: QApplication) -> None:
        custom_sheet = SheetDataModel(name="ImportedData")
        custom_sheet.set_cell_value(0, 0, "Hello")

        view = SpreadsheetView(model=custom_sheet)
        assert len(view.workbook) == 1
        assert view.model is custom_sheet
        assert view.model.get_cell_value(0, 0) == "Hello"

    def test_multi_sheet_selection_isolation(self, qapp: QApplication) -> None:
        s1 = SheetDataModel(name="Sheet1")
        s2 = SheetDataModel(name="Sheet2")
        s1.set_cell_value(0, 0, "S1_A1")
        s2.set_cell_value(0, 0, "S2_A1")

        wb = WorkbookModel(sheets=[s1, s2])
        view = SpreadsheetView(workbook=wb)

        # 1. On Sheet 1, move selection to (3, 4)
        view.selection.select_cell(3, 4)
        assert view.selection.active_cell == (3, 4)
        assert view.grid.selection.active_cell == (3, 4)
        assert view.model.get_cell_value(0, 0) == "S1_A1"

        # 2. Switch to Sheet 2
        view.set_active_sheet_index(1)
        assert view.workbook.active_sheet_index == 1
        assert view.model is s2
        assert view.grid.model is s2
        # Sheet 2 selection should be at default (0, 0), isolated from Sheet 1
        assert view.selection.active_cell == (0, 0)
        assert view.grid.selection.active_cell == (0, 0)

        # 3. Modify selection on Sheet 2 to (1, 1)
        view.selection.select_cell(1, 1)
        assert view.selection.active_cell == (1, 1)

        # 4. Switch back to Sheet 1
        view.set_active_sheet_index(0)
        assert view.model is s1
        assert view.grid.model is s1
        # Sheet 1 selection must still be (3, 4)!
        assert view.selection.active_cell == (3, 4)
        assert view.grid.selection.active_cell == (3, 4)

    def test_remove_sheet_selection_cleanup(self, qapp: QApplication) -> None:
        s1 = SheetDataModel(name="Sheet1")
        s2 = SheetDataModel(name="Sheet2")
        wb = WorkbookModel(sheets=[s1, s2])
        view = SpreadsheetView(workbook=wb)

        # Activate sheet 2 to initialize its selection
        view.set_active_sheet_index(1)
        assert s2 in view._sheet_selections

        # Remove sheet 2
        wb.remove_sheet(1)
        assert len(view.workbook) == 1
        assert s2 not in view._sheet_selections
        assert view.model is s1
