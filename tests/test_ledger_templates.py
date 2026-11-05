"""Unit and GUI tests for Ledger built-in spreadsheet templates.

Verifies alignment with .vibeoffice/public/ledger/js/panes.js for all 8 templates:
loan, expense, invoice, timecard, budget, tasks, shopping, and schedule.
"""

import pytest

from atboffice.core.templates import TemplateRegistry
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.templates import (
    LEDGER_TEMPLATE_IDS,
    LEDGER_TEMPLATE_NAMES,
    build_ledger_template,
)
from atboffice.ui.shell.ledger_window import LedgerWindow


@pytest.fixture(autouse=True)
def reset_registry():
    """Ensure clean registry singleton state before and after each test."""
    TemplateRegistry.reset_instance()
    yield
    TemplateRegistry.reset_instance()


def test_ledger_template_ids_list():
    """Verify that all 8 canonical templates are declared."""
    expected = [
        "loan",
        "expense",
        "invoice",
        "timecard",
        "budget",
        "tasks",
        "shopping",
        "schedule",
    ]
    assert LEDGER_TEMPLATE_IDS == expected


def test_build_ledger_template_invalid():
    """Verify requesting an invalid template raises KeyError."""
    with pytest.raises(KeyError):
        build_ledger_template("non_existent_id")


@pytest.mark.parametrize("tid", LEDGER_TEMPLATE_IDS)
def test_all_eight_templates_build_valid_workbook(tid):
    """Verify template builder produces valid WorkbookModel with sheets, cells, and metadata."""
    wb = build_ledger_template(tid)
    assert isinstance(wb, WorkbookModel)
    assert len(wb.sheets) >= 1
    sheet = wb.active_sheet
    assert isinstance(sheet, SheetDataModel)
    assert len(sheet.cells) > 0
    assert wb.extra.get("template") == tid
    assert wb.extra.get("template_name") == LEDGER_TEMPLATE_NAMES[tid]
    assert not wb.dirty


def test_loan_template():
    """Verify Loan Amortization template structure, inputs, and PMT formula."""
    wb = build_ledger_template("loan")
    sheet = wb.active_sheet
    assert sheet.name == "Loan"
    assert sheet.freeze_rows == 10
    assert sheet.freeze_cols == 0
    assert sheet.extra.get("initial_selection") == "C3"

    # Title & Inputs
    assert sheet.get_cell(0, 0).value == "Loan Amortization Schedule"
    assert sheet.get_cell(0, 0).bold is True
    assert sheet.get_cell(0, 0).font_size == 16
    assert sheet.get_cell(2, 2).value == 25000  # C3 Loan amount
    assert sheet.get_cell(3, 2).value == 0.065  # C4 Annual interest
    assert sheet.get_cell(4, 2).value == 5  # C5 Period years
    assert sheet.get_cell(5, 2).value == 12  # C6 Payments/year

    # Scheduled payment formula in G3 (row 2, col 6)
    g3 = sheet.get_cell(2, 6)
    assert g3 is not None
    assert g3.formula == '=IF(C3*C4*C5*C6>0,-PMT(C4/C6,C5*C6,C3),"")'
    if g3.value is not None:
        # PMT(0.065/12, 60, 25000) approx 489.15
        assert pytest.approx(float(g3.value), 0.1) == 489.15

    # Column widths (A=160, B=104, etc.)
    assert sheet.geometry.col_size(0) == 20 * 8
    assert sheet.geometry.col_size(1) == 13 * 8

    # 60 schedule rows (A11 to A70)
    for r in range(10, 70):
        cell_a = sheet.get_cell(r, 0)
        assert cell_a is not None
        assert "ROW()-10" in cell_a.formula


def test_expense_template():
    """Verify Expense Statement template with mileage calculation and categories."""
    wb = build_ledger_template("expense")
    sheet = wb.active_sheet
    assert sheet.name == "Expenses"
    assert sheet.extra.get("initial_selection") == "B3"

    # Title & Headers
    assert sheet.get_cell(0, 0).value == "Expense Statement"
    assert sheet.get_cell(4, 0).value == "Date"
    assert sheet.get_cell(4, 4).value == "Mileage ($0.67/mi)"

    # Subtotal and totals
    g20 = sheet.get_cell(19, 6)
    assert g20 is not None
    assert g20.formula == "=SUM(G6:G19)"

    g22 = sheet.get_cell(21, 6)
    assert g22 is not None
    assert g22.formula == "=G20-G21"

    # Category summaries (SUMIF)
    b25 = sheet.get_cell(24, 1)
    assert b25 is not None
    assert b25.formula == "=SUMIF($C$6:$C$19,A25,$G$6:$G$19)"

    # Data validation dropdown
    assert len(sheet.data_validations) >= 1
    dv = sheet.data_validations[0]
    assert dv.sqref == "C6:C19"
    assert "Travel" in dv.formula1


def test_invoice_template():
    """Verify Sales Invoice template with line totals, sales tax, and merged header."""
    wb = build_ledger_template("invoice")
    sheet = wb.active_sheet
    assert sheet.name == "Invoice"
    assert sheet.extra.get("show_grid") is False
    assert sheet.extra.get("initial_selection") == "A5"

    # Merged header B9:D9 (rows 8, cols 1-3)
    assert sheet.is_merged(8, 1)
    assert sheet.is_merged(8, 3)

    # Line item formulas
    f10 = sheet.get_cell(9, 5)
    assert f10 is not None
    assert f10.formula == '=IF(A10*E10=0,"",A10*E10)'

    # Totals formulas
    f21 = sheet.get_cell(20, 5)
    assert f21 is not None
    assert f21.formula == "=SUM(F10:F20)"

    f23 = sheet.get_cell(22, 5)
    assert f23 is not None
    assert f23.formula == "=ROUND(F21*F22,2)"

    f24 = sheet.get_cell(23, 5)
    assert f24 is not None
    assert f24.formula == "=F21+F23"


def test_timecard_template():
    """Verify Weekly Timecard template with daily clock times and overtime formulas."""
    wb = build_ledger_template("timecard")
    sheet = wb.active_sheet
    assert sheet.name == "Timecard"
    assert sheet.extra.get("initial_selection") == "B3"

    # Daily hours formula in row 7 (G7)
    g7 = sheet.get_cell(6, 6)
    assert g7 is not None
    assert "ROUND(((F7-C7)-(E7-D7))*24,2)" in g7.formula

    # Summary formulas
    g15 = sheet.get_cell(14, 6)  # Total hours
    assert g15.formula == "=SUM(G7:G13)"

    g16 = sheet.get_cell(15, 6)  # Regular hours
    assert g16.formula == "=MIN(40,G15)"

    g17 = sheet.get_cell(16, 6)  # Overtime
    assert g17.formula == "=MAX(0,G15-40)"

    g19 = sheet.get_cell(18, 6)  # Total pay
    assert g19.formula == "=G16*E3+G17*E3*1.5"


def test_budget_template():
    """Verify Personal Monthly Budget template with 12 months, freeze, and income/expense sums."""
    wb = build_ledger_template("budget")
    sheet = wb.active_sheet
    assert sheet.name == "Budget"
    assert sheet.freeze_rows == 3
    assert sheet.freeze_cols == 1
    assert sheet.extra.get("initial_selection") == "B4"

    # Months headers
    assert sheet.get_cell(2, 0).value == "Income"
    assert sheet.get_cell(2, 1).value == "Jan"
    assert sheet.get_cell(2, 12).value == "Dec"
    assert sheet.get_cell(2, 13).value == "Year"

    # Total income formula
    assert sheet.get_cell(5, 0).value == "Total income"
    b6 = sheet.get_cell(5, 1)
    assert b6.formula == "=SUM(B4:B5)"

    # Total expenses formula
    b17 = sheet.get_cell(16, 1)
    assert b17.formula == "=SUM(B9:B16)"

    # Net formula
    b19 = sheet.get_cell(18, 1)
    assert b19.formula == "=B6-B17"


def test_tasks_template():
    """Verify Task Tracker template with COUNTIFS KPIs, countdown formula, and data validations."""
    wb = build_ledger_template("tasks")
    sheet = wb.active_sheet
    assert sheet.name == "Tasks"
    assert sheet.freeze_rows == 4
    assert sheet.freeze_cols == 0
    assert sheet.extra.get("initial_selection") == "A9"

    # Open and overdue KPI formulas
    b2 = sheet.get_cell(1, 1)
    assert b2.formula == '=COUNTIFS(A5:A104,"<>",E5:E104,"<>Done")'

    d2 = sheet.get_cell(1, 3)
    assert (
        d2.formula == '=COUNTIFS(A5:A104,"<>",E5:E104,"<>Done",D5:D104,"<"&TODAY())'
    )

    # Days left formula
    f5 = sheet.get_cell(4, 5)
    assert f5.formula == '=IF(OR(A5="",D5="",E5="Done"),"",D5-TODAY())'

    # Validations on priority and status
    assert len(sheet.data_validations) == 2
    f1_list = [v.formula1 for v in sheet.data_validations]
    assert any("High,Medium,Low" in s for s in f1_list)
    assert any("Not started,In progress,Waiting,Done" in s for s in f1_list)


def test_shopping_template():
    """Verify Shopping List template with list totals and budget difference check."""
    wb = build_ledger_template("shopping")
    sheet = wb.active_sheet
    assert sheet.name == "Shopping"
    assert sheet.freeze_rows == 4
    assert sheet.freeze_cols == 0
    assert sheet.extra.get("initial_selection") == "B13"

    # Top KPI formulas
    e2 = sheet.get_cell(1, 4)
    assert e2.formula == "=SUM(F5:F44)"

    e3 = sheet.get_cell(2, 4)
    assert e3.formula == '=SUMIF(A5:A44,"",F5:F44)'

    f2 = sheet.get_cell(1, 5)
    expected_f2 = (
        '=IF(B2="","",IF(E2>B2,"Over budget by "&TEXT(E2-B2,"$0.00"),'
        'TEXT(B2-E2,"$0.00")&" left"))'
    )
    assert f2.formula == expected_f2

    # Items calculation
    f5 = sheet.get_cell(4, 5)
    assert f5.formula == '=IF(B5="","",IF(D5="",1,D5)*E5)'


def test_schedule_template():
    """Verify Weekly Schedule template with weekday offset, 16 slots, and calendar events."""
    wb = build_ledger_template("schedule")
    sheet = wb.active_sheet
    assert sheet.name == "Schedule"
    assert sheet.freeze_rows == 5
    assert sheet.freeze_cols == 1
    assert sheet.extra.get("initial_selection") == "C6"

    # Week of formula
    b2 = sheet.get_cell(1, 1)
    assert b2.formula == "=TODAY()-WEEKDAY(TODAY(),3)"

    # Monday date formula
    b5 = sheet.get_cell(4, 1)
    assert b5.formula == "=$B$2+0"

    # Sunday date formula
    h5 = sheet.get_cell(4, 7)
    assert h5.formula == "=$B$2+6"

    # Sample appointment cells
    assert sheet.get_cell(7, 1).value == "Team stand-up"
    assert sheet.get_cell(10, 2).value == "Lunch with Sam"


def test_template_registry_integration():
    """Verify TemplateRegistry registers builders for all 8 Ledger templates."""
    reg = TemplateRegistry.get_instance()
    for tid in LEDGER_TEMPLATE_IDS:
        tpl = reg.get(tid, app="ledger")
        assert tpl is not None
        assert tpl.app == "ledger"
        assert callable(tpl.builder)
        built = tpl.builder()
        assert isinstance(built, WorkbookModel)
        assert built.extra.get("template") == tid


def test_ledger_window_load_template(qtbot):
    """Verify LedgerWindow loads template into spreadsheet view and updates window title."""
    win = LedgerWindow()
    qtbot.addWidget(win)

    loaded = win.load_template("loan")
    assert loaded is True
    assert win.active_template is not None
    assert win.active_template.id == "loan"
    assert win.spreadsheet_view.workbook.extra.get("template") == "loan"
    assert "贷款分期偿还表" in win.windowTitle() or "Loan" in win.windowTitle()

    # Reset with new_file
    win.new_file()
    assert win.active_template is None
    assert win.spreadsheet_view.workbook.extra.get("template") is None
