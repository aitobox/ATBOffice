"""Unit tests for SheetTabBar bottom worksheet tab bar component."""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.modules.spreadsheet.views.sheet_tab_bar import SheetTabBar


class TestSheetTabBar:
    """Test suite for SheetTabBar Excel 2003 classic bottom tab bar component."""

    def test_init_default(self, qapp: QApplication) -> None:
        wb = WorkbookModel()
        tab_bar = SheetTabBar(workbook=wb)

        assert tab_bar.workbook is wb
        assert tab_bar.tab_count == 1
        assert tab_bar.active_index == 0
        assert tab_bar.tab_text(0) == "Sheet1"
        assert tab_bar.btn_first is not None
        assert tab_bar.btn_prev is not None
        assert tab_bar.btn_next is not None
        assert tab_bar.btn_last is not None

    def test_init_multi_sheets(self, qapp: QApplication) -> None:
        s1 = SheetDataModel(name="Jan")
        s2 = SheetDataModel(name="Feb")
        s3 = SheetDataModel(name="Mar")
        wb = WorkbookModel(sheets=[s1, s2, s3])
        tab_bar = SheetTabBar(workbook=wb)

        assert tab_bar.tab_count == 3
        assert [tab_bar.tab_text(i) for i in range(3)] == ["Jan", "Feb", "Mar"]
        assert tab_bar.active_index == 0

    def test_click_tab_activates_sheet(self, qapp: QApplication) -> None:
        s1 = SheetDataModel(name="Sheet1")
        s2 = SheetDataModel(name="Sheet2")
        wb = WorkbookModel(sheets=[s1, s2])
        tab_bar = SheetTabBar(workbook=wb)

        # Activate tab 1
        tab_bar.set_active_index(1)
        assert tab_bar.active_index == 1
        assert wb.active_sheet_index == 1
        assert wb.active_sheet is s2

    def test_navigation_buttons(self, qapp: QApplication) -> None:
        sheets = [SheetDataModel(name=f"Sheet{i}") for i in range(1, 10)]
        wb = WorkbookModel(sheets=sheets)
        tab_bar = SheetTabBar(workbook=wb)

        # Trigger navigation buttons
        tab_bar.btn_last.click()
        assert tab_bar.active_index == 8

        tab_bar.btn_first.click()
        assert tab_bar.active_index == 0

        tab_bar.btn_next.click()
        assert tab_bar.active_index == 1

        tab_bar.btn_prev.click()
        assert tab_bar.active_index == 0

    def test_inline_rename_valid(self, qapp: QApplication) -> None:
        wb = WorkbookModel()
        tab_bar = SheetTabBar(workbook=wb)

        # Start inline rename
        tab_bar.start_rename(0)
        assert tab_bar.is_renaming
        assert tab_bar.rename_editor is not None
        assert tab_bar.rename_editor.text() == "Sheet1"

        # Commit new name
        success = tab_bar.commit_rename("2026_Report")
        assert success is True
        assert not tab_bar.is_renaming
        assert wb[0].name == "2026_Report"
        assert tab_bar.tab_text(0) == "2026_Report"

    def test_inline_rename_invalid_rejected(self, qapp: QApplication) -> None:
        s1 = SheetDataModel(name="Sheet1")
        s2 = SheetDataModel(name="Sheet2")
        wb = WorkbookModel(sheets=[s1, s2])
        tab_bar = SheetTabBar(workbook=wb)

        tab_bar.start_rename(0)

        # 1. Reject invalid characters (: \ / ? * [ ])
        assert tab_bar.commit_rename("Invalid:Name") is False
        assert wb[0].name == "Sheet1"

        # 2. Reject empty name
        assert tab_bar.commit_rename("") is False
        assert wb[0].name == "Sheet1"

        # 3. Reject duplicate name
        assert tab_bar.commit_rename("Sheet2") is False
        assert wb[0].name == "Sheet1"

        # 4. Cancel rename restores original state
        tab_bar.cancel_rename()
        assert not tab_bar.is_renaming
        assert wb[0].name == "Sheet1"

    def test_insert_sheet_action(self, qapp: QApplication) -> None:
        wb = WorkbookModel()
        tab_bar = SheetTabBar(workbook=wb)

        new_sheet = tab_bar.insert_sheet()
        assert len(wb) == 2
        assert tab_bar.tab_count == 2
        assert new_sheet.name == "Sheet2"
        assert wb.active_sheet is new_sheet
        assert tab_bar.active_index == 1

    def test_delete_sheet_action(self, qapp: QApplication) -> None:
        s1 = SheetDataModel(name="Sheet1")
        s2 = SheetDataModel(name="Sheet2")
        wb = WorkbookModel(sheets=[s1, s2])
        tab_bar = SheetTabBar(workbook=wb)

        # Delete tab 1
        deleted = tab_bar.delete_sheet(1)
        assert deleted is True
        assert len(wb) == 1
        assert tab_bar.tab_count == 1
        assert wb.active_sheet.name == "Sheet1"

        # Cannot delete the only remaining sheet
        deleted_only = tab_bar.delete_sheet(0)
        assert deleted_only is False
        assert len(wb) == 1

    def test_move_or_copy_sheet(self, qapp: QApplication) -> None:
        s1 = SheetDataModel(name="Sheet1")
        s2 = SheetDataModel(name="Sheet2")
        wb = WorkbookModel(sheets=[s1, s2])
        tab_bar = SheetTabBar(workbook=wb)

        # Copy sheet 0
        copy_sheet = tab_bar.duplicate_sheet(0)
        assert copy_sheet is not None
        assert len(wb) == 3
        assert copy_sheet.name.startswith("Sheet1")
        assert tab_bar.tab_count == 3

    def test_tab_color(self, qapp: QApplication) -> None:
        wb = WorkbookModel()
        tab_bar = SheetTabBar(workbook=wb)

        color = QColor(255, 0, 0)
        tab_bar.set_tab_color(0, color)
        assert tab_bar.tab_color(0) == color

    def test_workbook_signals_sync(self, qapp: QApplication) -> None:
        wb = WorkbookModel()
        tab_bar = SheetTabBar(workbook=wb)

        # Add sheet on workbook directly
        wb.add_sheet(name="ExternalAdd")
        assert tab_bar.tab_count == 2
        assert tab_bar.tab_text(1) == "ExternalAdd"

        # Rename sheet directly on workbook
        wb.rename_sheet(1, "ExternalRename")
        assert tab_bar.tab_text(1) == "ExternalRename"

        # Move sheet
        wb.move_sheet(0, 1)
        assert tab_bar.tab_text(0) == "ExternalRename"
        assert tab_bar.tab_text(1) == "Sheet1"

        # Remove sheet
        wb.remove_sheet(1)
        assert tab_bar.tab_count == 1
        assert tab_bar.tab_text(0) == "ExternalRename"

    def test_retranslate_ui(self, qapp: QApplication) -> None:
        wb = WorkbookModel()
        tab_bar = SheetTabBar(workbook=wb)
        # Should not raise exception
        tab_bar.retranslate_ui()

    def test_spreadsheet_view_embedding(self, qapp: QApplication) -> None:
        s1 = SheetDataModel(name="Sales")
        s2 = SheetDataModel(name="Expenses")
        wb = WorkbookModel(sheets=[s1, s2])
        view = SpreadsheetView(workbook=wb)

        assert hasattr(view, "sheet_tab_bar")
        assert view.sheet_tab_bar is not None
        assert view.sheet_tab_bar.tab_count == 2

        # Changing tab via sheet_tab_bar updates SpreadsheetView model
        view.sheet_tab_bar.set_active_index(1)
        assert view.workbook.active_sheet_index == 1
        assert view.model is s2
        assert view.grid.model is s2
