"""Tests for Insert Function (fx) Wizard and Function Arguments Dialog."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.fn_info import (
    ALL_FUNCTIONS_CATALOG,
    FunctionInfo,
    get_function_info,
)
from atboffice.modules.spreadsheet.dialogs.function_wizard import (
    ARG_HELP_DATA,
    DEFAULT_MRU,
    STANDARD_CATEGORIES,
    FunctionArgumentsDialog,
    FunctionCatalogService,
    InsertFunctionDialog,
    launch_function_wizard,
    safe_tr,
)
from atboffice.modules.spreadsheet.models.selection_model import SelectionModel
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.editor_controller import EditorController
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport
from atboffice.ui.shell.ledger_window import LedgerWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QApplication instance exists."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ==============================================================================
# Catalog & Service Tests
# ==============================================================================


def test_catalog_service_categories():
    """Verify standard categories and retrieval of functions."""
    assert len(STANDARD_CATEGORIES) >= 12
    assert "Math & Trig" in STANDARD_CATEGORIES
    assert "Financial" in STANDARD_CATEGORIES

    math_fns = FunctionCatalogService.get_functions_by_category("Math & Trig")
    assert "SUM" in math_fns
    assert "SIN" in math_fns
    assert "ABS" in math_fns

    all_fns = FunctionCatalogService.get_functions_by_category("All")
    assert len(all_fns) >= 500
    assert "SUM" in all_fns
    assert "VLOOKUP" in all_fns


def test_catalog_service_mru(monkeypatch):
    """Verify MRU retrieval, recording, and deduplication."""
    fake_store = {}

    class FakeSettings:
        def __init__(self, *args, **kwargs):
            pass

        def value(self, key, default=None):
            return fake_store.get(key, default)

        def setValue(self, key, val):
            fake_store[key] = val

    monkeypatch.setattr("atboffice.modules.spreadsheet.dialogs.function_wizard.QSettings", FakeSettings)

    # Initial fallback
    mru = FunctionCatalogService.get_mru_list()
    assert mru == DEFAULT_MRU

    # Record usage
    FunctionCatalogService.record_mru("VLOOKUP")
    mru = FunctionCatalogService.get_mru_list()
    assert mru[0] == "VLOOKUP"
    assert len(mru) <= 10

    # Record existing to test move-to-front
    FunctionCatalogService.record_mru("SUM")
    mru = FunctionCatalogService.get_mru_list()
    assert mru[0] == "SUM"
    assert mru[1] == "VLOOKUP"


def test_catalog_service_search():
    """Verify search scoring matches function names and keywords."""
    res = FunctionCatalogService.search("sum")
    assert "SUM" in res
    assert "SUMIF" in res
    assert "SUMIFS" in res
    assert res[0] == "SUM"  # Exact match scores highest

    res_avg = FunctionCatalogService.search("average")
    assert "AVERAGE" in res_avg

    res_empty = FunctionCatalogService.search("")
    assert res_empty == []


def test_catalog_service_arg_help():
    """Verify argument help resolution for standard and suffixed parameters."""
    help_num = FunctionCatalogService.get_arg_help("number")
    assert "数字" in help_num or "number" in help_num.lower()

    help_num1 = FunctionCatalogService.get_arg_help("number1")
    assert len(help_num1) > 0

    help_num2 = FunctionCatalogService.get_arg_help("[number2]")
    assert len(help_num2) > 0

    help_unknown = FunctionCatalogService.get_arg_help("custom_foo_param")
    assert len(help_unknown) > 0


def test_catalog_service_syntax():
    """Verify syntax string formatting."""
    info = get_function_info("SUM")
    assert info is not None
    syntax = FunctionCatalogService.format_syntax(info)
    assert syntax.startswith("SUM(")
    assert "number1" in syntax


# ==============================================================================
# Step 1: InsertFunctionDialog Tests
# ==============================================================================


def test_insert_function_dialog_init(qapp):
    """Verify InsertFunctionDialog creates controls and populates MRU."""
    dlg = InsertFunctionDialog(initial_fn="AVERAGE")
    assert dlg.windowTitle() == safe_tr("插入函数")
    assert dlg.selected_function == "AVERAGE"
    assert dlg.list_functions.count() > 0
    assert dlg.lbl_syntax.text().startswith("AVERAGE(")
    assert len(dlg.lbl_desc.text()) > 0


def test_insert_function_dialog_category_change(qapp):
    """Verify changing category filters the function list."""
    dlg = InsertFunctionDialog()
    idx = dlg.combo_category.findData("Date & Time")
    assert idx >= 0
    dlg.combo_category.setCurrentIndex(idx)

    # List should contain date functions
    items = [dlg.list_functions.item(i).text() for i in range(dlg.list_functions.count())]
    assert "DATE" in items
    assert "TODAY" in items
    assert "SUM" not in items


def test_insert_function_dialog_search(qapp):
    """Verify search input filters list and selects best result."""
    dlg = InsertFunctionDialog()
    dlg.edit_search.setText("lookup")
    dlg.btn_go.click()

    items = [dlg.list_functions.item(i).text() for i in range(dlg.list_functions.count())]
    assert "VLOOKUP" in items
    assert "HLOOKUP" in items
    assert "LOOKUP" in items
    assert dlg.selected_function in ("VLOOKUP", "LOOKUP", "HLOOKUP", "XLOOKUP")


def test_insert_function_dialog_accept_and_mru(qapp, monkeypatch):
    """Verify accepting dialog records selected function in MRU."""
    recorded = []
    monkeypatch.setattr(FunctionCatalogService, "record_mru", lambda name: recorded.append(name))

    dlg = InsertFunctionDialog(initial_fn="MAX")
    dlg._on_accept()
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert "MAX" in recorded


# ==============================================================================
# Step 2: FunctionArgumentsDialog Tests
# ==============================================================================


def test_function_arguments_dialog_init(qapp):
    """Verify FunctionArgumentsDialog builds rows for function arguments."""
    dlg = FunctionArgumentsDialog(func_name="SUM")
    assert dlg.func_name == "SUM"
    assert dlg.windowTitle() == safe_tr("函数参数")
    assert len(dlg.arg_rows) >= 2  # number1, [number2]
    assert dlg.is_repeating is True


def test_function_arguments_dialog_evaluation(qapp):
    """Verify real-time calculation preview with numeric values."""
    dlg = FunctionArgumentsDialog(func_name="SUM")
    # arg 0: number1
    dlg.arg_rows[0][1].setText("10")
    # arg 1: number2
    dlg.arg_rows[1][1].setText("20")

    call_str = dlg.build_call_string()
    assert call_str == "SUM(10, 20)"
    assert dlg.lbl_result_val.text() in ("30", "30.0")
    assert "30" in dlg.lbl_formula_result_summary.text()


def test_function_arguments_dialog_with_workbook_data(qapp):
    """Verify real-time evaluation against workbook cells."""
    wb = WorkbookModel()
    sheet = wb.active_sheet
    sheet.set_cell_value(0, 0, 50)  # A1
    sheet.set_cell_value(1, 0, 150)  # A2

    dlg = FunctionArgumentsDialog(
        func_name="AVERAGE",
        workbook=wb,
        sheet=sheet,
        active_r=0,
        active_c=1,
    )
    dlg.arg_rows[0][1].setText("A1:A2")

    call_str = dlg.build_call_string()
    assert call_str == "AVERAGE(A1:A2)"
    assert dlg.lbl_result_val.text() in ("100", "100.0")


def test_function_arguments_dialog_trailing_optional_trimming(qapp):
    """Verify trailing empty optional arguments are trimmed from call string."""
    dlg = FunctionArgumentsDialog(func_name="IF")
    # IF(logical_test, [value_if_true], [value_if_false])
    dlg.arg_rows[0][1].setText("1>0")
    dlg.arg_rows[1][1].setText('"YES"')
    # Leave value_if_false empty
    dlg.arg_rows[2][1].setText("")

    call_str = dlg.build_call_string()
    assert call_str == 'IF(1>0, "YES")'


def test_function_arguments_dialog_repeating_expansion(qapp):
    """Verify repeating argument expansion when focusing last row."""
    dlg = FunctionArgumentsDialog(func_name="SUM")
    initial_count = len(dlg.arg_rows)
    assert dlg.is_repeating is True

    # Simulate focus on last argument edit
    last_edit = dlg.arg_rows[-1][1]
    from PySide6.QtGui import QFocusEvent
    from PySide6.QtCore import QEvent

    focus_ev = QFocusEvent(QEvent.Type.FocusIn)
    dlg.eventFilter(last_edit, focus_ev)

    assert len(dlg.arg_rows) == initial_count + 1
    new_arg_name = dlg.arg_rows[-1][0]
    assert "number" in new_arg_name


def test_function_arguments_dialog_invalid_formula_graceful(qapp):
    """Verify invalid argument expressions do not crash and display waiting state."""
    dlg = FunctionArgumentsDialog(func_name="SUM")
    dlg.arg_rows[0][1].setText("SUM(invalid(")
    dlg._update_evaluation()

    assert dlg.lbl_result_val.text() == safe_tr("(等待有效参数)")
    assert dlg.lbl_formula_result_summary.text() == safe_tr("公式结果 = ")


# ==============================================================================
# Wizard Launcher & Window Integration Tests
# ==============================================================================


def test_launch_function_wizard_direct_function(qapp, monkeypatch):
    """Verify launching wizard directly with default_fn opens step 2 and returns formula."""
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)

    wb = WorkbookModel()
    sheet = wb.active_sheet

    formula = launch_function_wizard(
        workbook=wb,
        sheet=sheet,
        active_r=2,
        active_c=3,
        default_fn="SUM",
    )
    assert formula is not None
    assert formula.startswith("=SUM(")
    cell = sheet.get_cell(2, 3)
    assert cell is not None
    assert cell.formula.startswith("SUM(")


def test_launch_function_wizard_with_editor_controller(qapp, monkeypatch):
    """Verify wizard injects formula into active editor_controller."""
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)

    wb = WorkbookModel()
    sheet = wb.active_sheet
    sel = SelectionModel()
    grid = GridViewport(model=sheet, selection=sel)
    editor = EditorController(viewport=grid, model=sheet, selection=sel)

    # Inactive editor: should begin edit and commit
    formula = launch_function_wizard(
        workbook=wb,
        sheet=sheet,
        active_r=0,
        active_c=0,
        editor_controller=editor,
        default_fn="AVERAGE",
    )
    assert formula is not None
    cell = sheet.get_cell(0, 0)
    assert cell is not None
    assert cell.formula.startswith("AVERAGE(")


def test_ledger_window_open_function_wizard(qapp, monkeypatch):
    """Verify LedgerWindow.open_function_wizard delegates to launch_function_wizard."""
    called = []

    def mock_launch(**kwargs):
        called.append(kwargs)
        return "=SUM(1, 2)"

    monkeypatch.setattr(
        "atboffice.modules.spreadsheet.dialogs.function_wizard.launch_function_wizard",
        mock_launch,
    )

    win = LedgerWindow()
    win.open_function_wizard()

    assert len(called) == 1
    assert called[0]["parent"] == win
    assert called[0]["workbook"] == win.spreadsheet_view.workbook
    assert called[0]["sheet"] == win.spreadsheet_view.model
    win.close()
