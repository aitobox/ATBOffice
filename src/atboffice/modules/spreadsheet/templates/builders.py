"""Concrete template specifications for 8 Ledger business spreadsheet formats.

Faithfully aligned with .vibeoffice/public/ledger/js/panes.js TPL object.
"""

from __future__ import annotations

from typing import Any

from atboffice.modules.spreadsheet.models.sheet_model import BorderStyle
from atboffice.modules.spreadsheet.templates.base import (
    BOX,
    HDR,
    INPUT,
    MONEY,
    TITLE,
    B,
    merge_styles,
)


def build_loan_spec() -> dict[str, Any]:
    """1. Loan Amortization Schedule (60 installments with PMT calculation)."""
    cells: list[list[Any]] = [
        ["A1", "Loan Amortization Schedule", TITLE],
        ["A3", "Loan amount", B],
        ["C3", 25000, merge_styles(MONEY, INPUT, BOX)],
        ["A4", "Annual interest rate", B],
        ["C4", 0.065, merge_styles({"nf": "0.00%"}, INPUT, BOX)],
        ["A5", "Loan period in years", B],
        ["C5", 5, merge_styles(INPUT, BOX)],
        ["A6", "Payments per year", B],
        ["C6", 12, merge_styles(INPUT, BOX)],
        ["A7", "Start date of loan", B],
        ["C7", 46113, merge_styles({"nf": "m/d/yyyy"}, INPUT, BOX)],
        ["E3", "Scheduled payment", B],
        ["G3", '=IF(C3*C4*C5*C6>0,-PMT(C4/C6,C5*C6,C3),"")', merge_styles(MONEY, BOX)],
        ["E4", "Number of payments", B],
        ["G4", "=C5*C6", BOX],
        ["E5", "Total interest", B],
        ["G5", "=SUM(F11:F370)", merge_styles(MONEY, BOX)],
        ["E6", "Total cost of loan", B],
        ["G6", "=C3+G5", merge_styles(MONEY, BOX)],
        ["A10", "Pmt No.", HDR],
        ["B10", "Payment Date", HDR],
        ["C10", "Beginning Balance", HDR],
        ["D10", "Payment", HDR],
        ["E10", "Principal", HDR],
        ["F10", "Interest", HDR],
        ["G10", "Ending Balance", HDR],
        ["H10", "Cumulative Interest", HDR],
    ]
    for i in range(60):
        r = 11 + i
        cells.append(["A" + str(r), '=IF(ROW()-10<=$G$4,ROW()-10,"")'])
        cells.append(
            [
                "B" + str(r),
                f'=IF(A{r}="","",EDATE($C$7,(A{r}-1)*12/$C$6))',
                {"nf": "m/d/yyyy"},
            ]
        )
        c_form = f'=IF(A{r}="","",$C$3)' if i == 0 else f'=IF(A{r}="","",G{r - 1})'
        cells.append(["C" + str(r), c_form, MONEY])
        cells.append(["D" + str(r), f'=IF(A{r}="","",MIN($G$3,C{r}+F{r}))', MONEY])
        cells.append(["E" + str(r), f'=IF(A{r}="","",D{r}-F{r})', MONEY])
        cells.append(["F" + str(r), f'=IF(A{r}="","",C{r}*$C$4/$C$6)', MONEY])
        cells.append(["G" + str(r), f'=IF(A{r}="","",C{r}-E{r})', MONEY])
        h_form = f'=IF(A{r}="","",F{r})' if i == 0 else f'=IF(A{r}="","",H{r - 1}+F{r})'
        cells.append(["H" + str(r), h_form, MONEY])

    return {
        "sheets": [
            {
                "name": "Loan",
                "cells": cells,
                "cols": {
                    "A": 20,
                    "B": 13,
                    "C": 16,
                    "D": 13,
                    "E": 18,
                    "F": 13,
                    "G": 15,
                    "H": 14,
                },
                "freeze": [10, 0],
                "sel": "C3",
            }
        ]
    }


def build_expense_spec() -> dict[str, Any]:
    """2. Expense Statement (Category breakdown and mileage)."""
    cells: list[list[Any]] = [
        ["A1", "Expense Statement", TITLE],
        ["A3", "Employee", B],
        ["B3", "", merge_styles(INPUT, BOX)],
        ["D3", "Period from", B],
        ["E3", "", merge_styles({"nf": "m/d/yyyy"}, INPUT, BOX)],
        ["F3", "to", B],
        ["G3", "", merge_styles({"nf": "m/d/yyyy"}, INPUT, BOX)],
        ["A5", "Date", HDR],
        ["B5", "Description", HDR],
        ["C5", "Category", HDR],
        ["D5", "Miles", HDR],
        ["E5", "Mileage ($0.67/mi)", HDR],
        ["F5", "Amount", HDR],
        ["G5", "Total", HDR],
        ["A6", 46120, {"nf": "m/d/yyyy"}],
        ["B6", "Client visit, Springfield"],
        ["C6", "Travel"],
        ["D6", 84],
        ["F6", 18.5, MONEY],
        ["A7", 46121, {"nf": "m/d/yyyy"}],
        ["B7", "Lunch with client"],
        ["C7", "Meals"],
        ["F7", 46.2, MONEY],
        ["A8", 46124, {"nf": "m/d/yyyy"}],
        ["B8", "Conference registration"],
        ["C8", "Training"],
        ["F8", 395, MONEY],
        ["F20", "Subtotal", B],
        [
            "G20",
            "=SUM(G6:G19)",
            merge_styles(
                {
                    "bold": True,
                    "border_top": BorderStyle(style="thin"),
                    "border_bottom": BorderStyle(style="double"),
                },
                MONEY,
            ),
        ],
        ["F21", "Less advances", B],
        ["G21", 0, merge_styles(MONEY, INPUT)],
        ["F22", "Total due", B],
        ["G22", "=G20-G21", merge_styles({"bold": True}, MONEY)],
        ["A24", "Summary by category", B],
    ]
    for r in range(6, 20):
        cells.append(["E" + str(r), f'=IF(D{r}="","",D{r}*0.67)', MONEY])
        cells.append(["G" + str(r), f'=IF(COUNT(E{r}:F{r})=0,"",SUM(E{r}:F{r}))', MONEY])
        if r > 8:
            cells.append(["A" + str(r), None, {"nf": "m/d/yyyy"}])
            cells.append(["F" + str(r), None, MONEY])

    categories = ["Travel", "Meals", "Lodging", "Training", "Supplies", "Other"]
    for i, cat in enumerate(categories):
        row = 25 + i
        cells.append(["A" + str(row), cat])
        cells.append(["B" + str(row), f"=SUMIF($C$6:$C$19,A{row},$G$6:$G$19)", MONEY])

    return {
        "sheets": [
            {
                "name": "Expenses",
                "cells": cells,
                "cols": {
                    "A": 12,
                    "B": 30,
                    "C": 12,
                    "D": 8,
                    "E": 12,
                    "F": 12,
                    "G": 13,
                },
                "dv": [
                    {
                        "ref": "C6:C19",
                        "type": "list",
                        "f1": '"Travel,Meals,Lodging,Training,Supplies,Other"',
                        "prompt": "Pick a category",
                        "promptTitle": "Category",
                    }
                ],
                "sel": "B3",
            }
        ]
    }


def build_invoice_spec() -> dict[str, Any]:
    """3. Sales Invoice (Itemized billing and tax)."""
    cells: list[list[Any]] = [
        ["A1", "INVOICE", {"bold": True, "font_size": 20, "fg_color": "#336699"}],
        ["E1", "Invoice No.", B],
        ["F1", 1001, merge_styles(INPUT, BOX)],
        ["E2", "Date", B],
        ["F2", "=TODAY()", merge_styles({"nf": "mmmm d, yyyy"}, BOX)],
        ["A4", "Bill to:", B],
        ["A5", "Customer name", INPUT],
        ["A6", "Street address", INPUT],
        ["A7", "City, State ZIP", INPUT],
        ["A9", "Qty", HDR],
        ["B9", "Description", HDR],
        ["E9", "Unit Price", HDR],
        ["F9", "Line Total", HDR],
        ["A10", 4],
        ["B10", "Widget, standard"],
        ["E10", 12.5, MONEY],
        ["A11", 1],
        ["B11", "Installation service"],
        ["E11", 85, MONEY],
        ["E21", "Subtotal", B],
        ["F21", "=SUM(F10:F20)", MONEY],
        ["E22", "Sales tax rate", B],
        ["F22", 0.0725, merge_styles({"nf": "0.00%"}, INPUT)],
        ["E23", "Sales tax", B],
        ["F23", "=ROUND(F21*F22,2)", MONEY],
        ["E24", "TOTAL", {"bold": True, "font_size": 12}],
        [
            "F24",
            "=F21+F23",
            merge_styles(
                {
                    "bold": True,
                    "font_size": 12,
                    "border_top": BorderStyle(style="thin"),
                    "border_bottom": BorderStyle(style="double"),
                },
                MONEY,
            ),
        ],
        [
            "A27",
            "Make all checks payable to your company name. Thank you for your business!",
            {"italic": True},
        ],
    ]
    for r in range(10, 21):
        cells.append(["F" + str(r), f'=IF(A{r}*E{r}=0,"",A{r}*E{r})', MONEY])

    return {
        "sheets": [
            {
                "name": "Invoice",
                "cells": cells,
                "cols": {"A": 8, "B": 30, "C": 8, "D": 8, "E": 14, "F": 15},
                "merges": ["B9:D9"],
                "grid": False,
                "sel": "A5",
            }
        ]
    }


def build_timecard_spec() -> dict[str, Any]:
    """4. Weekly Timecard (Regular and overtime payroll tracking)."""
    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    t_style = {"nf": "h:mm AM/PM"}
    cells: list[list[Any]] = [
        ["A1", "Weekly Timecard", TITLE],
        ["A3", "Employee", B],
        ["B3", "", INPUT],
        ["A4", "Week starting", B],
        ["B4", 46118, merge_styles({"nf": "m/d/yyyy"}, INPUT)],
        ["D3", "Hourly rate", B],
        ["E3", 22.5, merge_styles(MONEY, INPUT)],
        ["A6", "Day", HDR],
        ["B6", "Date", HDR],
        ["C6", "Time in", HDR],
        ["D6", "Lunch out", HDR],
        ["E6", "Lunch in", HDR],
        ["F6", "Time out", HDR],
        ["G6", "Hours", HDR],
    ]
    for i, d in enumerate(days):
        r = 7 + i
        cells.append(["A" + str(r), d])
        cells.append(["B" + str(r), f"=$B$4+{i}", {"nf": "m/d"}])
        cells.append(["C" + str(r), 0.375 if i < 5 else None, t_style])
        cells.append(["D" + str(r), 0.5 if i < 5 else None, t_style])
        cells.append(["E" + str(r), 0.53125 if i < 5 else None, t_style])
        cells.append(["F" + str(r), 0.7083333333 if i < 5 else None, t_style])
        cells.append(
            [
                "G" + str(r),
                f'=IF(COUNT(C{r}:F{r})<2,0,ROUND(((F{r}-C{r})-(E{r}-D{r}))*24,2))',
                {"nf": "0.00"},
            ]
        )

    cells.extend(
        [
            ["F15", "Total hours", B],
            ["G15", "=SUM(G7:G13)", {"nf": "0.00", "bold": True}],
            ["F16", "Regular (≤40)", B],
            ["G16", "=MIN(40,G15)", {"nf": "0.00"}],
            ["F17", "Overtime", B],
            ["G17", "=MAX(0,G15-40)", {"nf": "0.00"}],
            ["F19", "Total pay", B],
            ["G19", "=G16*E3+G17*E3*1.5", merge_styles({"bold": True}, MONEY)],
        ]
    )

    return {
        "sheets": [
            {
                "name": "Timecard",
                "cells": cells,
                "cols": {
                    "A": 12,
                    "B": 11,
                    "C": 11,
                    "D": 11,
                    "E": 11,
                    "F": 13,
                    "G": 11,
                },
                "sel": "B3",
            }
        ]
    }


def build_budget_spec() -> dict[str, Any]:
    """5. Personal Monthly Budget (12-month income/expense matrix)."""
    months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    cols = "BCDEFGHIJKLM"
    n_style = {"nf": "#,##0"}
    cells: list[list[Any]] = [
        ["A1", "Personal Monthly Budget", TITLE],
        ["A3", "Income", HDR],
        ["N3", "Year", HDR],
    ]
    for i, m in enumerate(months):
        cells.append([cols[i] + "3", m, HDR])

    income = [["Salary", 4200], ["Other income", 150]]
    exp = [
        ["Rent / mortgage", 1450],
        ["Utilities", 210],
        ["Groceries", 520],
        ["Transport", 260],
        ["Insurance", 180],
        ["Phone & internet", 95],
        ["Entertainment", 140],
        ["Savings", 400],
    ]
    for k, (n, v) in enumerate(income):
        r = 4 + k
        cells.append(["A" + str(r), n])
        for i in range(len(months)):
            cells.append([cols[i] + str(r), v, n_style])
        cells.append(["N" + str(r), f"=SUM(B{r}:M{r})", n_style])

    cells.append(["A6", "Total income", B])
    for c in cols + "N":
        cells.append(
            [
                c + "6",
                f"=SUM({c}4:{c}5)",
                merge_styles(
                    {"bold": True, "border_top": BorderStyle(style="thin")},
                    n_style,
                ),
            ]
        )

    cells.append(["A8", "Expenses", HDR])
    for i, m in enumerate(months):
        cells.append([cols[i] + "8", m, HDR])
    cells.append(["N8", "Year", HDR])

    for k, (n, v) in enumerate(exp):
        r = 9 + k
        cells.append(["A" + str(r), n])
        for i in range(len(months)):
            cells.append([cols[i] + str(r), v, n_style])
        cells.append(["N" + str(r), f"=SUM(B{r}:M{r})", n_style])

    last = 8 + len(exp)
    cells.append(["A" + str(last + 1), "Total expenses", B])
    for c in cols + "N":
        cells.append(
            [
                c + str(last + 1),
                f"=SUM({c}9:{c}{last})",
                merge_styles(
                    {"bold": True, "border_top": BorderStyle(style="thin")},
                    n_style,
                ),
            ]
        )

    cells.append(["A" + str(last + 3), "Net (income − expenses)", B])
    for c in cols + "N":
        cells.append(
            [
                c + str(last + 3),
                f"={c}6-{c}{last + 1}",
                {"bold": True, "nf": "#,##0;[Red]-#,##0"},
            ]
        )

    return {
        "sheets": [
            {
                "name": "Budget",
                "cells": cells,
                "cols": {"A": 24},
                "freeze": [3, 1],
                "sel": "B4",
            }
        ]
    }


def build_tasks_spec() -> dict[str, Any]:
    """6. Task Tracker (Priority, status, and days remaining)."""
    day_style = {"nf": "m/d/yyyy"}
    cells: list[list[Any]] = [
        ["A1", "Task Tracker", TITLE],
        ["A2", "Open", B],
        [
            "B2",
            '=COUNTIFS(A5:A104,"<>",E5:E104,"<>Done")',
            {"bold": True},
        ],
        ["C2", "Overdue", B],
        [
            "D2",
            '=COUNTIFS(A5:A104,"<>",E5:E104,"<>Done",D5:D104,"<"&TODAY())',
            {"bold": True, "fg_color": "#C00000"},
        ],
        ["A4", "Task", HDR],
        ["B4", "Owner", HDR],
        ["C4", "Priority", HDR],
        ["D4", "Due", HDR],
        ["E4", "Status", HDR],
        ["F4", "Days left", HDR],
        ["G4", "Notes", HDR],
        ["A5", "Book the venue"],
        ["B5", "Sam"],
        ["C5", "High"],
        ["D5", "=TODAY()+2", day_style],
        ["E5", "In progress"],
        ["A6", "Send invitations"],
        ["B6", "Alex"],
        ["C6", "Medium"],
        ["D6", "=TODAY()+7", day_style],
        ["E6", "Not started"],
        ["A7", "Order supplies"],
        ["B7", "Sam"],
        ["C7", "Low"],
        ["D7", "=TODAY()-1", day_style],
        ["E7", "Waiting"],
        ["G7", "Quote requested"],
        ["A8", "Draft the budget"],
        ["B8", "Alex"],
        ["C8", "High"],
        ["D8", "=TODAY()-3", day_style],
        ["E8", "Done"],
    ]
    for r in range(5, 105):
        cells.append(
            [
                "F" + str(r),
                f'=IF(OR(A{r}="",D{r}="",E{r}="Done"),"",D{r}-TODAY())',
                {"nf": "0;[Red]-0", "align_h": "center"},
            ]
        )
        if r > 8:
            cells.append(["D" + str(r), None, day_style])

    return {
        "sheets": [
            {
                "name": "Tasks",
                "cells": cells,
                "cols": {
                    "A": 32,
                    "B": 12,
                    "C": 10,
                    "D": 11,
                    "E": 13,
                    "F": 10,
                    "G": 30,
                },
                "freeze": [4, 0],
                "dv": [
                    {
                        "ref": "C5:C104",
                        "type": "list",
                        "f1": '"High,Medium,Low"',
                    },
                    {
                        "ref": "E5:E104",
                        "type": "list",
                        "f1": '"Not started,In progress,Waiting,Done"',
                        "prompt": "Pick a status",
                        "promptTitle": "Status",
                    },
                ],
                "sel": "A9",
            }
        ]
    }


def build_shopping_spec() -> dict[str, Any]:
    """7. Shopping List (Basket checklist, price summation, budget delta)."""
    cells: list[list[Any]] = [
        ["A1", "Shopping List", TITLE],
        ["A2", "Budget", B],
        ["B2", 80, merge_styles(MONEY, INPUT, BOX)],
        ["D2", "List total", B],
        ["E2", "=SUM(F5:F44)", MONEY],
        ["D3", "Still to buy", B],
        ["E3", '=SUMIF(A5:A44,"",F5:F44)', MONEY],
        [
            "F2",
            (
                '=IF(B2="","",IF(E2>B2,"Over budget by "&TEXT(E2-B2,"$0.00"),'
                'TEXT(B2-E2,"$0.00")&" left"))'
            ),
            {"italic": True},
        ],
        ["A4", "✓", HDR],
        ["B4", "Item", HDR],
        ["C4", "Category", HDR],
        ["D4", "Qty", HDR],
        ["E4", "Price each", HDR],
        ["F4", "Total", HDR],
    ]
    items = [
        ["Apples", "Produce", 6, 0.5],
        ["Milk", "Dairy", 2, 1.29],
        ["Bread", "Bakery", 1, 2.99],
        ["Eggs (dozen)", "Dairy", 1, 3.49],
        ["Chicken breast", "Meat & fish", 1, 7.5],
        ["Pasta", "Pantry", 2, 1.19],
        ["Coffee", "Pantry", 1, 8.99],
        ["Dish soap", "Household", 1, 2.49],
    ]
    for i, (n, c, q, p) in enumerate(items):
        r = 5 + i
        cells.extend(
            [
                ["B" + str(r), n],
                ["C" + str(r), c],
                ["D" + str(r), q],
                ["E" + str(r), p, MONEY],
            ]
        )
    for r in range(5, 45):
        cells.append(["F" + str(r), f'=IF(B{r}="","",IF(D{r}="",1,D{r})*E{r})', MONEY])
        cells.append(
            [
                "A" + str(r),
                None,
                {"align_h": "center", "bold": True, "fg_color": "#1F8A4C"},
            ]
        )
        if r >= 5 + len(items):
            cells.append(["E" + str(r), None, MONEY])

    return {
        "sheets": [
            {
                "name": "Shopping",
                "cells": cells,
                "cols": {"A": 5, "B": 28, "C": 14, "D": 7, "E": 12, "F": 12},
                "freeze": [4, 0],
                "dv": [
                    {
                        "ref": "A5:A44",
                        "type": "list",
                        "f1": '"✓"',
                        "prompt": "Tick what is in the basket",
                        "promptTitle": "Bought",
                    },
                    {
                        "ref": "C5:C44",
                        "type": "list",
                        "f1": (
                            '"Produce,Dairy,Bakery,Meat & fish,Pantry,Frozen,'
                            'Drinks,Household,Other"'
                        ),
                    },
                ],
                "sel": "B13",
            }
        ]
    }


def build_schedule_spec() -> dict[str, Any]:
    """8. Weekly Schedule (7 AM - 10 PM calendar slots)."""
    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    cols = "BCDEFGH"
    slot_style = merge_styles({"align_v": "center", "wrap_text": True}, BOX)
    cells: list[list[Any]] = [
        ["A1", "Weekly Schedule", TITLE],
        ["A2", "Week of", B],
        [
            "B2",
            "=TODAY()-WEEKDAY(TODAY(),3)",
            merge_styles({"nf": "mmmm d, yyyy"}, INPUT),
        ],
        ["A4", "Time", HDR],
    ]
    for i, d in enumerate(days):
        c_letter = cols[i]
        cells.append([c_letter + "4", d, HDR])
        cells.append(
            [
                c_letter + "5",
                f"=$B$2+{i}",
                {"nf": "mmm d", "align_h": "center", "fg_color": "#595959"},
            ]
        )
    for k in range(16):
        r = 6 + k
        cells.append(
            [
                "A" + str(r),
                (7 + k) / 24,
                {"nf": "h:mm AM/PM", "bold": True, "align_v": "center"},
            ]
        )
        for c in cols:
            cells.append([c + str(r), None, slot_style])

    plan = [
        ["B8", "Team stand-up"],
        ["D8", "Team stand-up"],
        ["F8", "Team stand-up"],
        ["C11", "Lunch with Sam"],
        ["E17", "Swimming"],
        ["G10", "Groceries"],
        ["H11", "Family brunch"],
        ["B19", "Piano lesson"],
    ]
    for addr, v in plan:
        cells.append(
            [
                addr,
                v,
                merge_styles({"bg_color": "#DDEBF7", "pattern": "solid"}, slot_style),
            ]
        )
    cells.append(["A23", "Notes", B])
    cells.append(["B23", "", INPUT])

    return {
        "sheets": [
            {
                "name": "Schedule",
                "cells": cells,
                "cols": {
                    "A": 10,
                    "B": 15,
                    "C": 15,
                    "D": 15,
                    "E": 15,
                    "F": 15,
                    "G": 15,
                    "H": 15,
                },
                "freeze": [5, 1],
                "sel": "C6",
            }
        ]
    }
