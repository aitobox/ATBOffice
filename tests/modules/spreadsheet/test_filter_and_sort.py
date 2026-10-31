"""Tests for AutoFilter, multi-column sorting, and CustomFilterDialog."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.dialogs.custom_filter import CustomFilterDialog
from atboffice.modules.spreadsheet.models.filter_model import (
    AutoFilter,
    ColumnFilter,
    apply_auto_filter,
    clear_auto_filter,
    excel_sort_cmp,
    sort_sheet_range,
)
from atboffice.modules.spreadsheet.models.filter_model import (
    test_custom_condition as eval_custom_cond,
)
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.views.filter_dropdown import FilterDropdown


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# =============================================================================
# 1. Excel Sort & Comparator Tests
# =============================================================================


def test_excel_sort_cmp_types():
    # Number < String < Boolean < Error < Blank
    assert excel_sort_cmp(10, 20) < 0
    assert excel_sort_cmp(10, "10") < 0
    assert excel_sort_cmp("apple", True) < 0
    assert excel_sort_cmp(True, "#VALUE!") < 0
    # Blanks are always placed at the bottom regardless of asc/desc
    assert excel_sort_cmp(10, None, desc=False) < 0
    assert excel_sort_cmp(10, None, desc=True) < 0
    assert excel_sort_cmp(None, 10, desc=False) > 0
    assert excel_sort_cmp(None, 10, desc=True) > 0
    assert excel_sort_cmp(None, "", desc=False) == 0


def test_sort_sheet_range():
    model = SheetDataModel("Sheet1")
    # Header: row 0
    model.set_cell(0, 0, CellData(value="Name"))
    model.set_cell(0, 1, CellData(value="Score"))

    # Data: rows 1..4
    rows = [
        ("Charlie", 85),
        ("Alice", 95),
        ("Bob", 85),
        ("David", 70),
    ]
    for idx, (name, score) in enumerate(rows, start=1):
        model.set_cell(idx, 0, CellData(value=name))
        model.set_cell(idx, 1, CellData(value=score))

    # Sort by Score descending, then Name ascending
    sort_sheet_range(
        model,
        r1=0,
        c1=0,
        r2=4,
        c2=1,
        keys=[(1, True), (0, False)],
        has_header=True,
    )

    result = [(model.get_cell_value(r, 0), model.get_cell_value(r, 1)) for r in range(1, 5)]
    assert result == [
        ("Alice", 95),
        ("Bob", 85),
        ("Charlie", 85),
        ("David", 70),
    ]


# =============================================================================
# 2. Custom Condition Evaluator Tests
# =============================================================================


def test_custom_condition_equality_and_wildcards():
    # Equals
    assert eval_custom_cond("equal", "100", 100, "100") is True
    assert eval_custom_cond("equal", "100", 200, "200") is False
    assert eval_custom_cond("notEqual", "100", 200, "200") is True

    # Case insensitive string equality
    assert eval_custom_cond("equal", "Beijing", "Beijing", "Beijing") is True
    assert eval_custom_cond("equal", "beijing", "Beijing", "Beijing") is True
    assert eval_custom_cond("notEqual", "Shanghai", "Beijing", "Beijing") is True

    # Wildcards: * (any chars) and ? (single char)
    assert eval_custom_cond("equal", "A*", "Apple", "Apple") is True
    assert eval_custom_cond("equal", "*e", "Apple", "Apple") is True
    assert eval_custom_cond("equal", "*pp*", "Apple", "Apple") is True
    assert eval_custom_cond("equal", "A???e", "Apple", "Apple") is True
    assert eval_custom_cond("equal", "A??e", "Apple", "Apple") is False
    assert eval_custom_cond("notEqual", "A*", "Banana", "Banana") is True


def test_custom_condition_comparisons():
    # Numeric comparisons
    assert eval_custom_cond("greaterThan", "50", 100, "100") is True
    assert eval_custom_cond("greaterThan", "100", 100, "100") is False
    assert eval_custom_cond("greaterThanOrEqual", "100", 100, "100") is True
    assert eval_custom_cond("lessThan", "100", 50, "50") is True
    assert eval_custom_cond("lessThan", "50", 100, "100") is False
    assert eval_custom_cond("lessThanOrEqual", "50", 50, "50") is True

    # Text comparisons
    assert eval_custom_cond("greaterThan", "Banana", "Cherry", "Cherry") is True
    assert eval_custom_cond("lessThan", "Banana", "Apple", "Apple") is True


def test_custom_condition_text_operators():
    # begins, notBegins
    assert eval_custom_cond("begins", "Tech", "Technology", "Technology") is True
    assert eval_custom_cond("begins", "bio", "Technology", "Technology") is False
    assert eval_custom_cond("notBegins", "bio", "Technology", "Technology") is True

    # ends, notEnds
    assert eval_custom_cond("ends", "Inc", "Apple Inc", "Apple Inc") is True
    assert eval_custom_cond("ends", "Ltd", "Apple Inc", "Apple Inc") is False
    assert eval_custom_cond("notEnds", "Ltd", "Apple Inc", "Apple Inc") is True

    # contains, notContains
    assert eval_custom_cond("contains", "soft", "Microsoft", "Microsoft") is True
    assert eval_custom_cond("contains", "goo", "Microsoft", "Microsoft") is False
    assert eval_custom_cond("notContains", "goo", "Microsoft", "Microsoft") is True


# =============================================================================
# 3. AutoFilter Model Integration with Custom Filters
# =============================================================================


def test_apply_auto_filter_custom_and_or():
    model = SheetDataModel("Sheet1")
    # Header: row 0
    model.set_cell(0, 0, CellData(value="Product"))
    model.set_cell(0, 1, CellData(value="Price"))

    # Rows 1..6
    data = [
        ("Widget A", 10),
        ("Widget B", 25),
        ("Gadget X", 50),
        ("Gadget Y", 80),
        ("Tool Z", 120),
        ("Sample", 200),
    ]
    for idx, (prod, price) in enumerate(data, start=1):
        model.set_cell(idx, 0, CellData(value=prod))
        model.set_cell(idx, 1, CellData(value=price))

    af = AutoFilter(r1=0, c1=0, r2=6, c2=1)

    # 1. Custom Filter on Price: >= 25 AND <= 80 (should show rows 2, 3, 4; hide 1, 5, 6)
    crit_and = ColumnFilter(
        custom_list=[("greaterThanOrEqual", "25"), ("lessThanOrEqual", "80")],
        custom_and=True,
    )
    af.cols[1] = crit_and
    apply_auto_filter(model, af)

    visible_rows = [r for r in range(1, 7) if r not in model.geometry.hidden_rows]
    assert visible_rows == [2, 3, 4]

    # 2. Custom Filter on Price: < 20 OR > 100 (should show rows 1, 5, 6; hide 2, 3, 4)
    crit_or = ColumnFilter(
        custom_list=[("lessThan", "20"), ("greaterThan", "100")],
        custom_and=False,
    )
    af.cols[1] = crit_or
    apply_auto_filter(model, af)

    visible_rows = [r for r in range(1, 7) if r not in model.geometry.hidden_rows]
    assert visible_rows == [1, 5, 6]

    # 3. Clear filter
    clear_auto_filter(model, af)
    assert len(model.geometry.hidden_rows) == 0


# =============================================================================
# 4. CustomFilterDialog GUI Tests
# =============================================================================


def test_custom_filter_dialog_init_and_get_criteria(qapp):
    unique_vals = ["10", "25", "50", "80", "120", "200"]
    dlg = CustomFilterDialog(
        column_header="Price",
        unique_values=unique_vals,
    )

    # Check window title and header label
    assert "Custom AutoFilter" in dlg.windowTitle() or "自定义" in dlg.windowTitle()
    assert "Price" in dlg.label_col.text()

    # Check operators list
    assert dlg.op1.count() == 12
    # op2 includes empty option first, so count == 13
    assert dlg.op2.count() == 13

    # Set condition 1: >= 25
    idx1 = dlg.op1.findData("greaterThanOrEqual")
    assert idx1 >= 0
    dlg.op1.setCurrentIndex(idx1)
    dlg.val1.setEditText("25")

    # Set radio to And (default)
    dlg.radio_and.setChecked(True)

    # Set condition 2: <= 80
    idx2 = dlg.op2.findData("lessThanOrEqual")
    assert idx2 >= 0
    dlg.op2.setCurrentIndex(idx2)
    dlg.val2.setEditText("80")

    conds, is_and = dlg.get_custom_criteria()
    assert conds == [("greaterThanOrEqual", "25"), ("lessThanOrEqual", "80")]
    assert is_and is True

    # Test single condition when condition 2 is left blank
    dlg.op2.setCurrentIndex(0)  # blank operator
    conds_single, is_and_single = dlg.get_custom_criteria()
    assert conds_single == [("greaterThanOrEqual", "25")]
    assert is_and_single is True


def test_custom_filter_dialog_initial_conditions_restore(qapp):
    # Pre-populate with existing criteria
    initial_conds = [("begins", "Widget"), ("contains", "A")]
    dlg = CustomFilterDialog(
        column_header="Product",
        unique_values=["Widget A", "Widget B", "Gadget X"],
        initial_conditions=initial_conds,
        initial_and=False,
    )

    assert dlg.op1.currentData() == "begins"
    assert dlg.val1.currentText() == "Widget"
    assert dlg.radio_or.isChecked() is True
    assert dlg.op2.currentData() == "contains"
    assert dlg.val2.currentText() == "A"

    conds, is_and = dlg.get_custom_criteria()
    assert conds == initial_conds
    assert is_and is False


def test_custom_filter_dialog_retranslate_ui(qapp):
    dlg = CustomFilterDialog(
        column_header="TestCol",
        unique_values=["A", "B"],
    )
    # Call retranslate_ui and verify no crash
    dlg.retranslate_ui()
    assert dlg.label_hint.text() != ""
    assert dlg.radio_and.text() != ""
    assert dlg.radio_or.text() != ""


# =============================================================================
# 5. FilterDropdown Integration
# =============================================================================


def test_filter_dropdown_custom_action(qapp):
    model = SheetDataModel("Sheet1")
    model.set_cell(0, 0, CellData(value="Category"))
    model.set_cell(1, 0, CellData(value="Electronics"))
    model.set_cell(2, 0, CellData(value="Clothing"))
    model.set_cell(3, 0, CellData(value="Food"))

    af = AutoFilter(r1=0, c1=0, r2=3, c2=0)

    dropdown = FilterDropdown(model=model, af=af, col=0)
    assert dropdown.btn_custom is not None
    assert dropdown.btn_custom.text() in ("(Custom...)", "(自定义...)")

    applied_criteria: list[ColumnFilter] = []
    dropdown.filter_applied.connect(lambda crit: applied_criteria.append(crit))

    # Test applying custom filter programmatically
    crit = ColumnFilter(
        custom_list=[("begins", "Elect")],
        custom_and=True,
    )
    dropdown.filter_applied.emit(crit)
    assert len(applied_criteria) == 1
    assert applied_criteria[0].custom_list == [("begins", "Elect")]

    dropdown.close()
