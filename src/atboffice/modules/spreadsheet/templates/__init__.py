"""Ledger built-in spreadsheet template system.

Provides template definitions, metadata, and builders for 8 canonical business formats
aligned with .vibeoffice/public/ledger/js/panes.js.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.templates.base import build_sheet_from_spec
from atboffice.modules.spreadsheet.templates.builders import (
    build_budget_spec,
    build_expense_spec,
    build_invoice_spec,
    build_loan_spec,
    build_schedule_spec,
    build_shopping_spec,
    build_tasks_spec,
    build_timecard_spec,
)

if TYPE_CHECKING:
    from atboffice.core.templates import TemplateRegistry

LEDGER_TEMPLATE_IDS: list[str] = [
    "loan",
    "expense",
    "invoice",
    "timecard",
    "budget",
    "tasks",
    "shopping",
    "schedule",
]

BUILDER_SPECS: dict[str, Callable[[], dict[str, Any]]] = {
    "loan": build_loan_spec,
    "expense": build_expense_spec,
    "invoice": build_invoice_spec,
    "timecard": build_timecard_spec,
    "budget": build_budget_spec,
    "tasks": build_tasks_spec,
    "shopping": build_shopping_spec,
    "schedule": build_schedule_spec,
}

LEDGER_TEMPLATE_NAMES: dict[str, str] = {
    "loan": "Loan Amortization",
    "expense": "Expense Statement",
    "invoice": "Sales Invoice",
    "timecard": "Timecard",
    "budget": "Personal Monthly Budget",
    "tasks": "Task Tracker",
    "shopping": "Shopping List",
    "schedule": "Weekly Schedule",
}


def build_ledger_template(template_id: str) -> WorkbookModel:
    """Build and return a fully structured WorkbookModel for the specified template ID.

    Args:
        template_id: Identifier of the template (e.g. 'loan', 'budget', 'invoice').

    Returns:
        Populated WorkbookModel ready for calculation, display, or editing.

    Raises:
        KeyError: If template_id is not in LEDGER_TEMPLATE_IDS.
    """
    tid = template_id.lower()
    if tid not in BUILDER_SPECS:
        raise KeyError(f"Unknown Ledger template identifier: {template_id!r}")

    spec_fn = BUILDER_SPECS[tid]
    spec = spec_fn()

    wb = WorkbookModel()
    build_sheet_from_spec(spec, wb)

    # Remove the initial default empty Sheet1 so only the template sheet exists
    if len(wb.sheets) > 1:
        wb.remove_sheet(0)

    wb.set_active_sheet_index(0)

    # Recalculate formulas so initial values are immediately available
    try:
        wb.recalculate()
    except Exception:
        # Continue gracefully if DAG encounters any formula parser quirks
        pass

    wb.dirty = False
    wb.extra["template"] = tid
    wb.extra["template_name"] = LEDGER_TEMPLATE_NAMES.get(tid, tid.capitalize())
    return wb


def register_ledger_templates(registry: TemplateRegistry | None = None) -> None:
    """Register or update builder callbacks for Ledger templates in TemplateRegistry."""
    from atboffice.core.templates import TemplateRegistry

    reg = registry or TemplateRegistry.get_instance()
    for tid in LEDGER_TEMPLATE_IDS:
        tpl = reg.get(tid, app="ledger")
        if tpl is not None:
            tpl.builder = lambda win=None, target_id=tid: build_ledger_template(target_id)


__all__ = [
    "BUILDER_SPECS",
    "LEDGER_TEMPLATE_IDS",
    "LEDGER_TEMPLATE_NAMES",
    "build_ledger_template",
    "register_ledger_templates",
]
