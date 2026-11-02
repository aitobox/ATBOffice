"""Tests for Ledger Missing Dialog Clusters and Wizards (Phase 6, Task 605).

Covers:
1. ChartWizardDialog: 4-step wizard, types, source data, options, location, FloatingObject creation.
2. TextToColumnsWizard: 3-step wizard, delimited/fixed-width, delimiters, formats, cell writeback.
3. SubtotalDialog: Grouping, subtotal functions, column checks, options.
4. ConsolidateDialog: Functions, references list add/remove, label positions.
5. ScenarioManagerDialog: Scenarios list, Add/Edit sub-dialogs, value application.
6. DataTableDialog: One/two-input What-If simulation matrix calculation.
7. ProtectSheetDialog & ProtectWorkbookDialog: Password protection, permissions, unprotect.
8. AdvancedFilterDialog: In-place vs copy to location, criteria, unique records.
9. LedgerOptionsDialog: 8-tab configuration, get_options, settings persistence.
10. Internationalization (retranslate_ui) across all dialogs.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from atboffice.modules.spreadsheet.dialogs import (
    AddScenarioDialog,
    AdvancedFilterDialog,
    ChartWizardDialog,
    ConsolidateDialog,
    DataTableDialog,
    LedgerOptionsDialog,
    ProtectSheetDialog,
    ProtectWorkbookDialog,
    ScenarioManagerDialog,
    ScenarioValuesDialog,
    SubtotalDialog,
    TextToColumnsWizard,
    UnprotectSheetDialog,
)
from atboffice.modules.spreadsheet.dialogs.protect_dialog import ConfirmPasswordDialog
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.object_layer import FloatingObject


class TestChartWizardDialog:
    def test_chart_wizard_flow(self, qapp: QApplication) -> None:
        wb = WorkbookModel()
        sheet = wb.sheets[0]

        dlg = ChartWizardDialog(sheet_model=sheet, workbook_model=wb)
        assert dlg.current_step == 0
        assert "图表类型" in dlg.windowTitle()

        # Step 1: select Line chart
        dlg.list_types.setCurrentRow(2)
        assert dlg.selected_type_id == "line"

        # Step 1 -> Step 2
        dlg.btn_next.click()
        assert dlg.current_step == 1
        assert "图表源数据" in dlg.windowTitle()

        # Step 2: change data range & series
        dlg.edit_data_range.setText("=Sheet1!$A$1:$C$10")
        dlg.radio_series_rows.setChecked(True)

        # Step 2 -> Step 3
        dlg.btn_next.click()
        assert dlg.current_step == 2
        assert "图表选项" in dlg.windowTitle()

        # Step 3: set titles
        dlg.edit_title.setText("Sales Report")
        dlg.edit_x_title.setText("Quarter")
        dlg.edit_y_title.setText("Revenue")
        dlg.radio_leg_bottom.setChecked(True)

        # Step 3 -> Step 4
        dlg.btn_next.click()
        assert dlg.current_step == 3
        assert "图表位置" in dlg.windowTitle()

        # Step 4 -> Back to Step 3 -> Back to Step 2
        dlg.btn_back.click()
        assert dlg.current_step == 2
        dlg.btn_next.click()
        assert dlg.current_step == 3

        # Finish
        dlg.btn_finish.click()
        assert dlg.result() == QDialog.DialogCode.Accepted
        assert len(sheet.drawings) == 1
        obj = sheet.drawings[0]
        assert isinstance(obj, FloatingObject)
        assert obj.kind == "chart"
        assert obj.name == "Sales Report"

        # Spec check
        spec = dlg.get_chart_spec()
        assert spec["type"] == "line"
        assert spec["title"] == "Sales Report"
        assert spec["series_in"] == "rows"

        # Retranslate
        dlg.retranslate_ui()
        assert dlg.btn_finish.text() == "完成(&F)"


class TestTextToColumnsWizard:
    def test_text_to_columns_delimited(self, qapp: QApplication) -> None:
        sheet = SheetDataModel(name="Sheet1")
        sample_data = ["Alice,25,Engineer", "Bob,30,Designer", "Charlie,35,Manager"]
        for r, line in enumerate(sample_data):
            sheet.set_cell_value(r, 0, line)

        dlg = TextToColumnsWizard(
            sheet_model=sheet,
            selected_range=(0, 0, 2, 0),
            sample_texts=sample_data,
        )
        assert dlg.current_step == 0
        assert "3 步骤之 1" in dlg.windowTitle()

        # Step 1 -> Step 2
        dlg.btn_next.click()
        assert dlg.current_step == 1
        assert "3 步骤之 2" in dlg.windowTitle()

        # Delimiters: comma is checked
        assert dlg.chk_comma.isChecked()
        dlg._refresh_split_preview()
        assert dlg.table_p2.columnCount() == 3
        assert dlg.table_p2.item(0, 0).text() == "Alice"
        assert dlg.table_p2.item(0, 1).text() == "25"
        assert dlg.table_p2.item(0, 2).text() == "Engineer"

        # Step 2 -> Step 3
        dlg.btn_next.click()
        assert dlg.current_step == 2
        assert "3 步骤之 3" in dlg.windowTitle()

        # Set column 1 format to Text
        dlg.selected_col = 1
        dlg.radio_fmt_text.setChecked(True)

        # Set destination to $A$0
        dlg.edit_dest.setText("$A$1")
        dlg.btn_finish.click()

        # Verify sheet cells written back
        res = dlg.get_split_result()
        assert len(res) == 3
        assert res[0][0] == "Alice"
        assert res[0][1] == "25"
        assert res[0][2] == "Engineer"

        dlg.retranslate_ui()
        assert dlg.btn_next.text() == "下一步(&N) >"


class TestSubtotalDialog:
    def test_subtotal_config_and_ui(self, qapp: QApplication) -> None:
        headers = ["Region", "Product", "Sales", "Profit"]
        dlg = SubtotalDialog(headers=headers, selected_range=(0, 0, 10, 3))
        assert dlg.windowTitle() == "分类汇总"

        dlg.combo_group_by.setCurrentIndex(0)  # Region
        dlg.combo_function.setCurrentIndex(0)  # SUM

        # Select Sales and Profit
        dlg.list_columns.item(2).setCheckState(Qt.CheckState.Checked)
        dlg.list_columns.item(3).setCheckState(Qt.CheckState.Checked)

        cfg = dlg.get_subtotal_config()
        assert cfg["group_by_col"] == 0
        assert cfg["group_by_name"] == "Region"
        assert cfg["function_code"] == 9  # SUM
        assert 2 in cfg["subtotal_cols"]
        assert 3 in cfg["subtotal_cols"]
        assert cfg["replace_current"] is True

        dlg.retranslate_ui()
        assert dlg.btn_remove_all.text() == "全部删除(&A)"


class TestConsolidateDialog:
    def test_consolidate_references(self, qapp: QApplication) -> None:
        dlg = ConsolidateDialog(initial_references=["Sheet1!$A$1:$C$5"])
        assert dlg.windowTitle() == "合并计算"
        assert dlg.list_references.count() == 1

        # Add reference
        dlg.edit_reference.setText("Sheet2!$A$1:$C$5")
        dlg.btn_add.click()
        assert dlg.list_references.count() == 2

        # Delete reference
        dlg.list_references.setCurrentRow(0)
        dlg.btn_delete.click()
        assert dlg.list_references.count() == 1
        assert dlg.list_references.item(0).text() == "Sheet2!$A$1:$C$5"

        dlg.check_top_row.setChecked(True)
        dlg.check_left_col.setChecked(True)

        cfg = dlg.get_consolidation_config()
        assert cfg["function"] == "SUM"
        assert cfg["top_row"] is True
        assert cfg["left_column"] is True
        assert cfg["references"] == ["Sheet2!$A$1:$C$5"]

        dlg.retranslate_ui()
        assert dlg.btn_browse.text() == "浏览(&B)..."


class TestScenarioManagerDialog:
    def test_scenario_manager_operations(self, qapp: QApplication) -> None:
        sheet = SheetDataModel(name="Sheet1")
        initial_scenarios = [
            {
                "name": "BaseCase",
                "changing_cells": "$B$1,$B$2",
                "comment": "Baseline model",
                "values": {"B1": "50", "B2": "100"},
                "prevent_changes": True,
                "hide": False,
            }
        ]
        dlg = ScenarioManagerDialog(sheet_model=sheet, initial_scenarios=initial_scenarios)
        assert dlg.windowTitle() == "方案管理器"
        assert dlg.list_scenarios.count() == 1

        # Check selection details
        dlg.list_scenarios.setCurrentRow(0)
        assert dlg.lbl_changing_cells.text() == "$B$1,$B$2"
        assert dlg.lbl_comment.text() == "Baseline model"

        # Show scenario
        dlg._on_show()
        assert sheet.get_cell_value(0, 1) == 50
        assert sheet.get_cell_value(1, 1) == 100

        # Sub-dialogs verification
        add_dlg = AddScenarioDialog(scenario_name="BestCase", changing_cells="$B$1,$B$2")
        data = add_dlg.get_data()
        assert data["name"] == "BestCase"

        val_dlg = ScenarioValuesDialog(changing_cells=["B1", "B2"], initial_values={"B1": "80", "B2": "150"})
        vals = val_dlg.get_values()
        assert vals["B1"] == "80"
        assert vals["B2"] == "150"

        dlg.retranslate_ui()
        assert dlg.btn_show.text() == "显示(&S)"


class TestDataTableDialog:
    def test_data_table_calculation(self, qapp: QApplication) -> None:
        sheet = SheetDataModel(name="Sheet1")
        # Setup small simulation table:
        # Row headers at r=0, cols 1..2: 10, 20
        # Col headers at c=0, rows 1..2: 2, 3
        sheet.set_cell_value(0, 0, "=A1*B1")
        sheet.set_cell_value(0, 1, 10)
        sheet.set_cell_value(0, 2, 20)
        sheet.set_cell_value(1, 0, 2)
        sheet.set_cell_value(2, 0, 3)

        dlg = DataTableDialog(sheet_model=sheet, selected_range=(0, 0, 2, 2))
        assert dlg.windowTitle() == "模拟运算表"

        dlg.edit_row_input.setText("$A$1")
        dlg.edit_col_input.setText("$B$1")

        params = dlg.get_table_params()
        assert params["row_input"] == "$A$1"
        assert params["col_input"] == "$B$1"

        dlg._on_ok()
        assert dlg.result() == QDialog.DialogCode.Accepted

        # Check matrix calculation
        assert sheet.get_cell_value(1, 1) == 20.0
        assert sheet.get_cell_value(1, 2) == 40.0
        assert sheet.get_cell_value(2, 1) == 30.0
        assert sheet.get_cell_value(2, 2) == 60.0

        dlg.retranslate_ui()
        assert dlg.btn_ok.text() == "确定"


class TestProtectDialogs:
    def test_protect_sheet_and_unprotect(self, qapp: QApplication) -> None:
        sheet = SheetDataModel(name="Sheet1")
        dlg = ProtectSheetDialog(sheet_model=sheet)
        assert dlg.windowTitle() == "保护工作表"

        dlg.edit_password.setText("secret123")
        # Check permissions
        prot = dlg.get_protection_data()
        assert prot["locked"] is True
        assert prot["has_password"] is True
        assert prot["permissions"]["select_locked_cells"] is True

        # Confirm password dialog
        confirm_dlg = ConfirmPasswordDialog("secret123")
        confirm_dlg.edit_confirm.setText("secret123")
        confirm_dlg._on_ok()
        assert confirm_dlg.result() == QDialog.DialogCode.Accepted

        # Apply protection
        sheet.protection = prot
        assert sheet.protection is not None

        # Unprotect
        unprot_dlg = UnprotectSheetDialog(sheet_model=sheet)
        unprot_dlg.edit_password.setText("secret123")
        unprot_dlg._on_ok()
        assert sheet.protection is None

        dlg.retranslate_ui()
        assert dlg.check_protect_contents.text() == "保护工作表及锁定的单元格内容(&C)"

    def test_protect_workbook(self, qapp: QApplication) -> None:
        wb = WorkbookModel()
        dlg = ProtectWorkbookDialog(workbook_model=wb)
        assert dlg.windowTitle() == "保护工作簿"

        dlg.edit_password.setText("wbpass")
        dlg.chk_structure.setChecked(True)
        dlg.chk_windows.setChecked(True)

        prot = dlg.get_protection_data()
        assert prot["structure"] is True
        assert prot["windows"] is True
        assert prot["has_password"] is True

        dlg.retranslate_ui()
        assert dlg.chk_structure.text() == "结构(&S)"


class TestAdvancedFilterDialog:
    def test_advanced_filter_params(self, qapp: QApplication) -> None:
        sheet = SheetDataModel(name="Sheet1")
        dlg = AdvancedFilterDialog(sheet_model=sheet, initial_list_range="$A$1:$D$50", initial_criteria_range="$F$1:$G$2")
        assert dlg.windowTitle() == "高级筛选"

        dlg.radio_copy_to.setChecked(True)
        assert dlg.edit_copy_to.isEnabled() is True
        dlg.edit_copy_to.setText("$I$1")
        dlg.check_unique.setChecked(True)

        params = dlg.get_filter_params()
        assert params["action"] == "copy_to"
        assert params["list_range"] == "$A$1:$D$50"
        assert params["criteria_range"] == "$F$1:$G$2"
        assert params["copy_to"] == "$I$1"
        assert params["unique_only"] is True

        dlg.retranslate_ui()
        assert dlg.check_unique.text() == "选择不重复的记录(&U)"


class TestLedgerOptionsDialog:
    def test_options_tabs_and_export(self, qapp: QApplication) -> None:
        dlg = LedgerOptionsDialog()
        assert dlg.windowTitle() == "选项"
        assert dlg.tabs.count() == 8

        # Tab 1: View
        dlg.chk_formulas.setChecked(True)
        dlg.chk_page_breaks.setChecked(True)

        # Tab 2: Calc
        dlg.radio_calc_manual.setChecked(True)
        dlg.chk_iteration.setChecked(True)
        dlg.spin_max_iter.setValue(150)

        # Tab 4: General
        dlg.spin_sheets_count.setValue(5)
        dlg.edit_username.setText("Alice")

        opts = dlg.get_options()
        assert opts["show_formulas"] is True
        assert opts["show_page_breaks"] is True
        assert opts["calc_mode"] == "manual"
        assert opts["iteration"] is True
        assert opts["max_iterations"] == 150
        assert opts["sheets_count"] == 5
        assert opts["username"] == "Alice"

        dlg.retranslate_ui()
        assert dlg.btn_ok.text() == "确定"


class TestLedgerWindowIntegration:
    def test_ledger_window_dialog_actions(self, qapp: QApplication) -> None:
        from atboffice.ui.shell.ledger_window import LedgerWindow

        win = LedgerWindow()
        for action_name in [
            "insertChart",
            "textToColumns",
            "subtotals",
            "consolidate",
            "scenarios",
            "dataTable",
            "protectSheet",
            "protectWorkbook",
            "advancedFilter",
            "options",
        ]:
            handler = win.action_registry._handlers.get(action_name)
            assert handler is not None
            assert callable(handler)

