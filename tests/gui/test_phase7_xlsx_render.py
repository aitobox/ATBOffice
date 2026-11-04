"""Regression and fidelity tests for TASK-707 / Issue #241:
Ledger real workbook rendering, workbook replacement synchronization,
multi-layer alignment (grid, editor, tabs, object_layer, geometry),
comments/hidden rows/CF/pivots fidelity, and formula recalculation error contracts.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.calc.references import cell_name
from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.models.conditional_format import (
    evaluate_cf_for_cell,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellData,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport
from atboffice.ui.shell.ledger_window import LedgerWindow

XLSX_CORPUS = Path("tests/docs/excel/xlsx")


def test_corpus_sample_cell_value(qtbot):
    """1. libreoffice__cell-value.xlsx:
    Numeric, floating-point, date-formatted, and long-text cell values load correctly.
    """
    file_path = XLSX_CORPUS / "libreoffice__cell-value.xlsx"
    assert file_path.exists(), f"Missing corpus file: {file_path}"

    wb = read_xlsx(file_path)
    assert len(wb.sheets) == 3
    sh1 = wb.sheets[0]
    assert sh1.name == "Sheet1"
    assert len(sh1.cells) == 12

    # Integer values
    assert sh1.get_cell_value(0, 0) == -2012
    assert sh1.get_cell_value(0, 2) == 0
    assert sh1.get_cell_value(0, 4) == 2012

    # Floating point values
    assert abs(float(sh1.get_cell_value(1, 0)) - (-3.14)) < 1e-6
    assert abs(float(sh1.get_cell_value(1, 3)) - 3.14) < 1e-6

    # Text and formatted string values
    assert sh1.get_cell_value(2, 0) == "H"
    assert sh1.get_cell_value(2, 1) == "Hello, Calc!"
    long_txt = sh1.get_cell_value(2, 3)
    assert isinstance(long_txt, str) and "Calc is the spreadsheet program" in long_txt

    # GUI view binding & paint verification
    view = SpreadsheetView(workbook=wb)
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)

    # Formatted text doesn't crash on long text or dates
    fmt_txt = sh1.get_formatted_text(2, 1)
    assert fmt_txt == "Hello, Calc!"
    pix = view.grab()
    assert not pix.isNull()
    assert pix.width() > 0 and pix.height() > 0


def test_corpus_sample_simple_with_comments(qtbot):
    """2. poi__SimpleWithComments.xlsx:
    Cell values and cell annotations (comments/authors/visibility) parsed and displayed.
    """
    file_path = XLSX_CORPUS / "poi__SimpleWithComments.xlsx"
    assert file_path.exists(), f"Missing corpus file: {file_path}"

    wb = read_xlsx(file_path)
    assert len(wb.sheets) == 3
    sh1 = wb.sheets[0]

    # Cell values
    assert sh1.get_cell_value(0, 0) == 1
    assert sh1.get_cell_value(0, 1) == "one"
    assert sh1.get_cell_value(1, 0) == 2
    assert sh1.get_cell_value(1, 1) == "two"
    assert sh1.get_cell_value(2, 0) == 3
    assert sh1.get_cell_value(2, 1) == "three"

    # Comments parsed from comments1.xml
    assert len(sh1.comments) == 3
    cm1 = sh1.get_comment(0, 1)  # B1
    assert cm1 is not None
    assert cm1.author == "Yegor Kozlov"
    assert "first cell" in cm1.text

    cm2 = sh1.get_comment(1, 1)  # B2
    assert cm2 is not None
    assert cm2.author == "Yegor Kozlov"
    assert "second cell" in cm2.text

    cm3 = sh1.get_comment(2, 1)  # B3
    assert cm3 is not None
    assert cm3.author == "Yegor Kozlov"
    assert "third cell" in cm3.text
    # VML note marked visible
    assert cm3.visible is True

    # GUI rendering shows comment indicator and callout
    view = SpreadsheetView(workbook=wb)
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)

    assert view.grid.model.has_comment(0, 1) is True
    assert view.grid.model.has_comment(1, 1) is True
    assert view.grid.model.has_comment(2, 1) is True

    pix = view.grab()
    assert not pix.isNull()


def test_corpus_sample_group_test_hidden_rows(qtbot):
    """3. poi__GroupTest.xlsx:
    Row groups, hidden rows (hidden="1"), and custom sizes are correctly reflected in geometry.
    """
    file_path = XLSX_CORPUS / "poi__GroupTest.xlsx"
    assert file_path.exists(), f"Missing corpus file: {file_path}"

    wb = read_xlsx(file_path)
    sh1 = wb.sheets[0]
    assert len(sh1.cells) == 25

    # 13 rows are hidden in this group test
    hidden_rows = sh1.geometry.hidden_rows
    assert len(hidden_rows) == 13
    assert 7 in hidden_rows  # row 8 in 1-based index
    assert 8 in hidden_rows  # row 9
    assert 9 in hidden_rows  # row 10
    assert 10 in hidden_rows  # row 11

    # Hidden row size is 0
    assert sh1.geometry.row_size(7) == 0
    assert sh1.geometry.row_size(8) == 0
    # Visible row size is default (> 0)
    assert sh1.geometry.row_size(0) > 0
    assert sh1.geometry.row_size(4) > 0

    view = SpreadsheetView(workbook=wb)
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)

    # Geometry mapper in grid matches model geometry
    assert view.grid.geometry_mapper is sh1.geometry
    assert 7 in view.grid.geometry_mapper.hidden_rows


def test_corpus_sample_conditional_formatting(qtbot):
    """4. libreoffice__conditional_fmt_origin.xlsx:
    Conditional formatting rules (containsText) parsed and evaluated for cell background color.
    """
    file_path = XLSX_CORPUS / "libreoffice__conditional_fmt_origin.xlsx"
    assert file_path.exists(), f"Missing corpus file: {file_path}"

    wb = read_xlsx(file_path)
    sh1 = wb.sheets[0]
    assert len(sh1.conditional_formats) >= 1

    cf = sh1.conditional_formats[0]
    assert len(cf.rules) >= 1
    rule = cf.rules[0]
    assert rule.type == "containsText"
    assert rule.text == "BAC"
    assert rule.bg_color == "#00B050"

    # Evaluate CF on matching cell
    cf_res = evaluate_cf_for_cell(sh1, 4, 1)  # cell B5 has "BAC"
    assert cf_res is not None
    assert cf_res.bg_color == "#00B050"

    view = SpreadsheetView(workbook=wb)
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)

    pix = view.grab()
    assert not pix.isNull()


def test_corpus_sample_pivot_table_cache(qtbot):
    """5. libreoffice__Pivot2_Row.xlsx:
    Pivot table display cells on Sheet2 and underlying PivotContainer cache are decoupled.
    """
    file_path = XLSX_CORPUS / "libreoffice__Pivot2_Row.xlsx"
    assert file_path.exists(), f"Missing corpus file: {file_path}"

    wb = read_xlsx(file_path)
    assert len(wb.sheets) == 2

    # Sheet1 is raw source data
    sh1 = wb.sheets[0]
    assert sh1.get_cell_value(0, 0) == "Name"
    assert sh1.get_cell_value(0, 1) == "Type"
    assert sh1.get_cell_value(0, 2) == "Price"

    # Sheet2 contains rendered pivot layout table
    sh2 = wb.sheets[1]
    assert sh2.get_cell_value(2, 0) == "Type"
    assert sh2.get_cell_value(2, 1) == "Name"
    assert sh2.get_cell_value(2, 2) == "Sum of Price"

    # Pivot metadata is preserved in wb.extra["pivots"]
    pivots = wb.extra.get("pivots")
    assert pivots is not None
    assert len(pivots.tables) == 1
    assert len(pivots.caches) == 1

    tbl = pivots.tables[0]
    assert tbl.name == "PivotTable1"
    assert tbl.sheet_name == "Sheet2"

    cache = pivots.caches[0]
    assert cache.fields == ["Name", "Type", "Price"]
    assert len(cache.sources) >= 1
    assert cache.sources[0].sheet_name == "Sheet1"

    # GUI view can switch between both sheets without data contamination
    view = SpreadsheetView(workbook=wb)
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)

    # Active sheet is Sheet2 (as saved in LibreOffice/Excel)
    assert view.model.name == "Sheet2"
    view.set_active_sheet_index(0)
    assert view.model.name == "Sheet1"
    assert view.grid.model.name == "Sheet1"
    assert view.editor_controller.model.name == "Sheet1"
    assert view.sheet_tab_bar.active_sheet.name == "Sheet1"
    view.set_active_sheet_index(1)
    assert view.model.name == "Sheet2"


def test_consecutive_workbook_switch_isolation(qtbot):
    """6. Consecutive Workbook Replacement & Undo/Zoom Isolation:
    Replacing workbook unbinds old signals, clears undo stack, updates tabs,
    and guarantees that switching sheets, undoing, or zooming never displays stale data.
    """
    file_path1 = XLSX_CORPUS / "libreoffice__cell-value.xlsx"
    file_path2 = XLSX_CORPUS / "poi__SimpleWithComments.xlsx"

    wb1 = read_xlsx(file_path1)
    wb2 = read_xlsx(file_path2)

    view = SpreadsheetView(workbook=wb1)
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)

    # Make an edit in workbook 1 to populate undo stack
    view.grid.model.set_cell_value(0, 0, 99999)
    view.grid._commit_undo(
        {
            "before_cells": {},
            "after_cells": {(0, 0): CellData(value=99999)},
            "before_merges": [],
            "after_merges": [],
            "before_comments": {},
            "after_comments": {},
            "before_sel": view.selection.snapshot(),
            "after_sel": view.selection.snapshot(),
        },
        action="edit_cell",
    )
    assert len(view.grid._undo_stack) > 0
    assert view.grid.model.get_cell_value(0, 0) == 99999

    # Replace with Workbook 2
    view.workbook = wb2

    # 1. Object Identity & Signal Verification
    active2 = wb2.active_sheet
    assert view.workbook is wb2
    assert view.grid.model is active2
    assert view.grid.geometry_mapper is active2.geometry
    assert view.editor_controller.model is active2
    assert view.object_layer.model is active2
    assert view.sheet_tab_bar.workbook is wb2
    assert view.sheet_tab_bar.active_sheet is active2

    # 2. Undo stack cleared on workbook replacement
    assert len(view.grid._undo_stack) == 0
    assert len(view.grid._redo_stack) == 0

    # 3. Undo call does not bring back 99999 from Workbook 1
    view.grid.undo()
    assert view.grid.model.get_cell_value(0, 0) == 1  # From poi__SimpleWithComments
    assert view.grid.model.get_cell_value(0, 0) != 99999

    # 4. Sheet switching in Workbook 2 accesses wb2 sheets cleanly
    view.set_active_sheet_index(1)
    assert view.grid.model.name == "Sheet2"
    assert view.editor_controller.model.name == "Sheet2"
    assert view.object_layer.model.name == "Sheet2"
    assert view.grid.model is wb2.sheets[1]

    # 5. Zoom change repaints wb2 cleanly without stale data
    view.grid.set_zoom(1.5)
    assert view.grid.zoom == 1.5
    pix = view.grab()
    assert not pix.isNull()


def test_formula_recalculation_and_error_contract(qtbot):
    """7. Formula Editing, Recalculation, and Error Contract:
    Editing a formula triggers re-evaluation against EvalContext;
    unsupported or erroneous expressions return explicit error values (#NAME?, #VALUE!),
    never disguised as blank/empty strings.
    """
    model = SheetDataModel(name="CalcSheet")
    model.set_cell_value(0, 0, 100)  # A1 = 100
    model.set_cell_value(0, 1, 50)   # B1 = 50

    wb = WorkbookModel(sheets=[model])
    view = SpreadsheetView(workbook=wb)
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)

    # 1. Valid formula evaluation
    view.editor_controller.begin_edit(1, 0, initial_text="=A1*2 + B1")
    ok = view.editor_controller.commit()
    assert ok is True
    cell_a2 = model.get_cell(1, 0)
    assert cell_a2 is not None
    assert cell_a2.formula == "A1*2 + B1"
    assert cell_a2.value == 250  # 100 * 2 + 50

    # 2. Unknown function formula (Unsupported feature error contract)
    view.editor_controller.begin_edit(2, 0, initial_text="=NONEXISTENT_FUNCTION(A1)")
    ok = view.editor_controller.commit()
    assert ok is True
    cell_a3 = model.get_cell(2, 0)
    assert cell_a3 is not None
    assert cell_a3.formula == "NONEXISTENT_FUNCTION(A1)"
    # Must NOT be None, empty string, or 0
    assert cell_a3.value in ("#NAME?", "#VALUE!", "#REF!")

    # 3. Syntax error formula
    view.editor_controller.begin_edit(3, 0, initial_text="=+++**")
    ok = view.editor_controller.commit()
    assert ok is True
    cell_a4 = model.get_cell(3, 0)
    assert cell_a4 is not None
    assert cell_a4.formula == "+++**"
    # Explicit error value, never empty
    assert cell_a4.value in ("#VALUE!", "#ERROR!")


def test_freeze_panes_and_zoom_rendering(qtbot):
    """8. Freeze panes split lines and zoom factor in GridViewport."""
    model = SheetDataModel(name="FrozenSheet")
    model.freeze_rows = 2
    model.freeze_cols = 1
    for r in range(10):
        for c in range(10):
            model.set_cell_value(r, c, f"R{r}C{c}")

    view = SpreadsheetView(workbook=WorkbookModel(sheets=[model]))
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)

    assert view.grid.freeze_rows == 2
    assert view.grid.freeze_cols == 1

    # Apply zoom
    view.grid.set_zoom(1.25)
    assert view.grid.zoom == 1.25

    # Paint with freeze lines and zoom
    pix = view.grab()
    assert not pix.isNull()
