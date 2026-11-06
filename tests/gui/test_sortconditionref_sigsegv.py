"""Regression tests for Issue #290: sortconditionref.xlsx offscreen event loop crash."""

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.models.filter_model import AutoFilter
from atboffice.modules.spreadsheet.models.selection_model import SelectionModel
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport


def test_sortconditionref_autofilter_parsing():
    """Verify <autoFilter> with sortCondition is parsed into AutoFilter dataclass."""
    doc_path = Path("tests/docs/excel/xlsx/libreoffice__sortconditionref.xlsx")
    assert doc_path.exists(), f"Sample file not found: {doc_path}"

    wb = read_xlsx(doc_path)
    assert len(wb.sheets) >= 1
    sheet = wb.sheets[0]

    # Verify auto_filter is an instance of AutoFilter
    assert isinstance(sheet.auto_filter, AutoFilter)
    assert sheet.auto_filter.r1 == 1
    assert sheet.auto_filter.c1 == 1
    assert sheet.auto_filter.r2 == 1
    assert sheet.auto_filter.c2 == 1
    assert "auto_filter_xml" in sheet.extra


def test_grid_viewport_painting_with_sortconditionref(qapp: QApplication):
    """Verify GridViewport paints sortconditionref sheet without crash or event loop failure."""
    doc_path = Path("tests/docs/excel/xlsx/libreoffice__sortconditionref.xlsx")
    wb = read_xlsx(doc_path)
    sheet = wb.sheets[0]

    sel = SelectionModel()
    grid = GridViewport(model=sheet, selection=sel)
    grid.resize(1000, 800)
    grid.show()

    # Process events repeatedly to simulate event loop draining
    for _ in range(5):
        qapp.processEvents()

    # Manual paint call
    grid.viewport().repaint()
    qapp.processEvents()

    grid.close()


def test_grid_viewport_defensive_against_malformed_autofilter(qapp: QApplication):
    """Verify GridViewport does not crash if auto_filter is malformed."""
    sheet = SheetDataModel()
    sheet.set_cell_value(0, 0, "Col A")
    sheet.set_cell_value(0, 1, "Col B")
    sheet.set_cell_value(1, 0, 100)
    sheet.set_cell_value(1, 1, 200)

    # Deliberately set malformed dictionary (prior bug pattern)
    sheet.auto_filter = {"ref": "B2"}

    sel = SelectionModel()
    grid = GridViewport(model=sheet, selection=sel)
    grid.resize(800, 600)
    grid.show()

    # Must not raise AttributeError: 'dict' object has no attribute 'r1' or crash
    grid.viewport().paintEvent(QPaintEvent(QRect(0, 0, 800, 600)))
    for _ in range(3):
        qapp.processEvents()

    # Hit test must also be safe
    hit = grid.hit_test(50, 50)
    assert hit is not None

    grid.close()


def test_isolated_subprocess_capture():
    """Verify offscreen document capture tool runs in separate process without SIGSEGV."""
    script_path = Path(".agents/skills/atb-office-diff/scripts/capture_doc_atboffice.py")
    doc_path = Path("tests/docs/excel/xlsx/libreoffice__sortconditionref.xlsx")
    out_dir = Path("/tmp/atb-sort-test-verify")

    cmd = [
        sys.executable,
        str(script_path),
        "--file",
        str(doc_path),
        "--out",
        str(out_dir),
    ]

    merged_env = os.environ.copy()
    merged_env["PYTHONPATH"] = "src"
    merged_env["PYTHONFAULTHANDLER"] = "1"

    res = subprocess.run(cmd, env=merged_env, capture_output=True, text=True)
    msg = f"Process crashed or failed with code {res.returncode}:\n{res.stderr}\n{res.stdout}"
    assert res.returncode == 0, msg
    assert "captured" in res.stdout
