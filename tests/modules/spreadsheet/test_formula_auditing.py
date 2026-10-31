"""Unit tests for Formula Auditing (AuditTracer, Arrows, Evaluate Formula, Watch Window)."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.calc.audit_tracer import (
    AuditArrow,
    AuditTracer,
)
from atboffice.modules.spreadsheet.dialogs.evaluate_formula_dialog import (
    EvaluateFormulaDialog,
)
from atboffice.modules.spreadsheet.dialogs.watch_window_dialog import (
    WatchWindowDialog,
)
from atboffice.modules.spreadsheet.models.selection_model import SelectionModel
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellData,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport
from atboffice.ui.shell.ledger_window import LedgerWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance exists for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ==============================================================================
# AuditTracer Tests
# ==============================================================================


def test_audit_tracer_precedents_single_and_range():
    """Verify tracing precedent single cells and ranges from formula AST."""
    sheet = SheetDataModel(name="Sheet1")
    sheet.set_cell(0, 0, CellData(value=10))  # A1
    sheet.set_cell(1, 1, CellData(value=20))  # B2
    sheet.set_cell(2, 2, CellData(value=30))  # C3

    # D4 has formula referencing A1 and B2:C3
    sheet.set_cell(3, 3, CellData(formula="=A1 + SUM(B2:C3)"))

    wb = WorkbookModel(sheets=[sheet])
    arrows = AuditTracer.trace_precedents(wb, "Sheet1", 3, 3)

    assert len(arrows) == 2
    a1_arrow = next((a for a in arrows if not a.is_range), None)
    range_arrow = next((a for a in arrows if a.is_range), None)

    assert a1_arrow is not None
    assert a1_arrow.from_sheet == "Sheet1"
    assert (a1_arrow.from_r1, a1_arrow.from_c1) == (0, 0)
    assert (a1_arrow.to_r, a1_arrow.to_c) == (3, 3)
    assert not a1_arrow.is_cross_sheet

    assert range_arrow is not None
    assert range_arrow.from_sheet == "Sheet1"
    assert (range_arrow.from_r1, range_arrow.from_c1) == (1, 1)
    assert (range_arrow.from_r2, range_arrow.from_c2) == (2, 2)


def test_audit_tracer_cross_sheet():
    """Verify cross-sheet references are identified properly."""
    sheet1 = SheetDataModel(name="Summary")
    sheet2 = SheetDataModel(name="Data")
    sheet2.set_cell(4, 1, CellData(value=100))  # Data!B5

    # Summary!A1 = Data!B5 * 2
    sheet1.set_cell(0, 0, CellData(formula="=Data!B5 * 2"))

    wb = WorkbookModel(sheets=[sheet1, sheet2])
    arrows = AuditTracer.trace_precedents(wb, "Summary", 0, 0)

    assert len(arrows) == 1
    arrow = arrows[0]
    assert arrow.from_sheet == "Data"
    assert (arrow.from_r1, arrow.from_c1) == (4, 1)
    assert arrow.to_sheet == "Summary"
    assert (arrow.to_r, arrow.to_c) == (0, 0)
    assert arrow.is_cross_sheet


def test_audit_tracer_dependents():
    """Verify querying dependent formula cells across sheets via DAG."""
    sheet = SheetDataModel(name="Sheet1")
    sheet.set_cell(0, 0, CellData(value=5))  # A1
    sheet.set_cell(0, 1, CellData(formula="=A1 * 10"))  # B1 depends on A1
    sheet.set_cell(0, 2, CellData(formula="=SUM(A1:B1)"))  # C1 depends on A1 and B1

    wb = WorkbookModel(sheets=[sheet])
    arrows = AuditTracer.trace_dependents(wb, "Sheet1", 0, 0)

    # Both B1 (0, 1) and C1 (0, 2) depend on A1
    dest_coords = {(a.to_r, a.to_c) for a in arrows}
    assert (0, 1) in dest_coords
    assert (0, 2) in dest_coords


def test_audit_tracer_empty_or_no_formula():
    """Verify trace_precedents returns empty list when cell has no formula."""
    sheet = SheetDataModel(name="Sheet1")
    sheet.set_cell(0, 0, CellData(value=123))  # No formula
    wb = WorkbookModel(sheets=[sheet])

    arrows = AuditTracer.trace_precedents(wb, "Sheet1", 0, 0)
    assert arrows == []


# ==============================================================================
# Grid Viewport Arrow Painting Tests
# ==============================================================================


def test_grid_viewport_arrow_rendering(qapp):
    """Verify GridViewport paints auditing arrows without exceptions."""
    sheet = SheetDataModel(name="Sheet1")
    sheet.set_cell(0, 0, CellData(value=10))
    sheet.set_cell(1, 1, CellData(value=20))

    arrows = [
        AuditArrow(
            from_sheet="Sheet1",
            from_r1=0,
            from_c1=0,
            from_r2=0,
            from_c2=0,
            to_sheet="Sheet1",
            to_r=2,
            to_c=2,
            is_error=False,
        ),
        AuditArrow(
            from_sheet="Sheet1",
            from_r1=0,
            from_c1=0,
            from_r2=1,
            from_c2=1,
            to_sheet="Sheet1",
            to_r=3,
            to_c=3,
            is_error=True,
        ),
        AuditArrow(
            from_sheet="OtherSheet",
            from_r1=0,
            from_c1=0,
            from_r2=0,
            from_c2=0,
            to_sheet="Sheet1",
            to_r=1,
            to_c=1,
            is_error=False,
        ),
    ]
    sheet.audit_arrows = arrows

    sel = SelectionModel()
    viewport = GridViewport(model=sheet, selection=sel)
    viewport.resize(400, 300)

    # Render to offscreen QImage
    img = QImage(400, 300, QImage.Format.Format_ARGB32_Premultiplied)
    viewport.render(img)

    # Viewport rendered with zero crashes
    assert img.width() == 400


# ==============================================================================
# Step-by-Step Evaluate Formula Dialog Tests
# ==============================================================================


def test_evaluate_formula_step_by_step(qapp):
    """Verify step-by-step unrolling of formula evaluation."""
    sheet = SheetDataModel(name="Sheet1")
    sheet.set_cell(0, 0, CellData(value=10))  # A1
    sheet.set_cell(0, 1, CellData(value=20))  # B1
    # C1 = A1 + B1 * 2
    sheet.set_cell(0, 2, CellData(formula="=A1 + B1 * 2"))

    wb = WorkbookModel(sheets=[sheet])
    dlg = EvaluateFormulaDialog(workbook=wb, sheet=sheet, r=0, c=2)

    # Initial state: has evaluable node
    assert dlg.cur_target is not None

    # Step 1
    dlg._on_evaluate_clicked()
    assert dlg.ast is not None

    # Step 2
    dlg._on_evaluate_clicked()
    assert dlg.ast is not None

    # Step 3
    dlg._on_evaluate_clicked()

    # Eventually reaches literal 50
    steps = 0
    while dlg.cur_target is not None and steps < 10:
        dlg._on_evaluate_clicked()
        steps += 1

    assert getattr(dlg.ast, "v", None) == 50
    assert dlg.btn_evaluate.text() == "重新启动(&R)"

    # Restart resets evaluation
    dlg._on_evaluate_clicked()
    assert dlg.cur_target is not None


# ==============================================================================
# Watch Window Tests
# ==============================================================================


def test_watch_window_operations(qapp):
    """Verify Watch Window adding, updating, deleting, and navigation signals."""
    sheet = SheetDataModel(name="Sheet1")
    sheet.set_cell(0, 0, CellData(value=42, formula="=10+32"))  # A1
    wb = WorkbookModel(sheets=[sheet])

    watch_dlg = WatchWindowDialog(workbook=wb, book_name="TestBook")

    # Add watch
    ok = watch_dlg.add_watch(sheet_name="Sheet1", r=0, c=0)
    assert ok is True
    assert watch_dlg.table.rowCount() == 1
    assert watch_dlg.table.item(0, 0).text() == "TestBook"
    assert watch_dlg.table.item(0, 1).text() == "Sheet1"
    assert watch_dlg.table.item(0, 3).text() == "$A$1"
    assert watch_dlg.table.item(0, 4).text() == "42"
    assert watch_dlg.table.item(0, 5).text() == "=10+32"

    # Avoid duplicate watch
    ok_dup = watch_dlg.add_watch(sheet_name="Sheet1", r=0, c=0)
    assert ok_dup is False
    assert watch_dlg.table.rowCount() == 1

    # Update cell value and refresh
    sheet.set_cell(0, 0, CellData(value=99, formula="=50+49"))
    watch_dlg.refresh_watches()
    assert watch_dlg.table.item(0, 4).text() == "99"
    assert watch_dlg.table.item(0, 5).text() == "=50+49"

    # Test double click navigation
    nav_calls = []
    watch_dlg.navigate_requested.connect(lambda s, r, c: nav_calls.append((s, r, c)))
    item = watch_dlg.table.item(0, 0)
    watch_dlg._on_item_double_clicked(item)
    assert nav_calls == [("Sheet1", 0, 0)]

    # Delete watch
    watch_dlg.table.setCurrentCell(0, 0)
    watch_dlg.delete_selected_watch()
    assert watch_dlg.table.rowCount() == 0


# ==============================================================================
# LedgerWindow Actions Integration Tests
# ==============================================================================


def test_ledger_window_auditing_actions(qapp, monkeypatch):
    """Verify LedgerWindow action methods for auditing."""
    window = LedgerWindow()
    sheet = window.spreadsheet_view.model

    # Set up formula at B1: =A1 + 10
    sheet.set_cell(0, 0, CellData(value=5))  # A1
    sheet.set_cell(0, 1, CellData(formula="=A1 + 10"))  # B1

    # Select B1
    window.spreadsheet_view.selection.set_active_cell(0, 1)

    # 1. Trace Precedents
    window.trace_precedents()
    assert len(getattr(sheet, "audit_arrows", [])) == 1
    arrow = sheet.audit_arrows[0]
    assert (arrow.from_r1, arrow.from_c1) == (0, 0)
    assert (arrow.to_r, arrow.to_c) == (0, 1)

    # 2. Trace Dependents from A1
    window.spreadsheet_view.selection.set_active_cell(0, 0)
    window.trace_dependents()
    assert len(sheet.audit_arrows) == 2

    # 3. Remove Arrows
    window.remove_arrows()
    assert len(sheet.audit_arrows) == 0

    # 4. Watch Window toggle
    window.watch_window()
    assert window._watch_window is not None
    assert window._watch_window.isVisible()
    window._watch_window.close()


def test_audit_tracer_error_trace():
    """Verify trace_error marks is_error=True."""
    sheet = SheetDataModel(name="Sheet1")
    sheet.set_cell(0, 0, CellData(value=0))
    sheet.set_cell(0, 1, CellData(value="#DIV/0!", formula="=10/A1"))
    wb = WorkbookModel(sheets=[sheet])

    arrows = AuditTracer.trace_error(wb, "Sheet1", 0, 1)
    assert len(arrows) == 1
    assert arrows[0].is_error is True
    assert (arrows[0].from_r1, arrows[0].from_c1) == (0, 0)
    assert (arrows[0].to_r, arrows[0].to_c) == (0, 1)


def test_evaluate_formula_error(qapp):
    """Verify formula evaluation handles division by zero or errors gracefully."""
    sheet = SheetDataModel(name="Sheet1")
    sheet.set_cell(0, 0, CellData(value=0))
    sheet.set_cell(0, 1, CellData(formula="=10/A1"))
    wb = WorkbookModel(sheets=[sheet])

    dlg = EvaluateFormulaDialog(workbook=wb, sheet=sheet, r=0, c=1)
    while dlg.cur_target is not None:
        dlg._on_evaluate_clicked()

    assert "#DIV/0!" in str(getattr(dlg.ast, "v", ""))


def test_watch_window_cross_sheet_navigation(qapp):
    """Verify double-clicking a watch item navigates to another sheet."""
    sheet1 = SheetDataModel(name="Sheet1")
    sheet2 = SheetDataModel(name="Sheet2")
    sheet2.set_cell(2, 3, CellData(value=999))  # D3
    wb = WorkbookModel(sheets=[sheet1, sheet2])

    window = LedgerWindow()
    window.spreadsheet_view._workbook = wb
    window.spreadsheet_view.grid.model = wb.active_sheet
    window.watch_window()

    window._watch_window.add_watch(sheet_name="Sheet2", r=2, c=3)
    item = window._watch_window.table.item(0, 0)
    window._watch_window._on_item_double_clicked(item)

    assert wb.active_sheet.name == "Sheet2"
    assert window.spreadsheet_view.selection.active_cell == (2, 3)
    window._watch_window.close()
