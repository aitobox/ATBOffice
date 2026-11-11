"""GUI & model regression tests for external data cached values fallback rendering (Issue #335)."""

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.calc.dag import DependencyGraph
from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.models.selection_model import SelectionModel
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport
from atboffice.modules.spreadsheet.views.object_layer import AnchorType


@pytest.fixture(scope="module")
def qapp():
    """Ensure QApplication instance is initialized offscreen."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["pytest_test", "-platform", "offscreen"])
    return app


def test_cell_data_cached_value_storage_and_clone():
    """Verify CellData stores cached_value and preserves it on clone."""
    cell = CellData(
        value="[1]Sheet1!$A$1",
        formula="[1]Sheet1!$A$1",
        cached_value=42.5,
        format_code="#,##0.00",
    )
    assert cell.cached_value == 42.5
    assert cell.formula == "[1]Sheet1!$A$1"

    cloned = cell.clone()
    assert cloned.cached_value == 42.5
    assert cloned.value == "[1]Sheet1!$A$1"
    assert cloned.formula == "[1]Sheet1!$A$1"


def test_sheet_model_get_formatted_text_prioritizes_cached_value():
    """Verify SheetDataModel.get_formatted_text displays cached_value on error or None."""
    sheet = SheetDataModel(name="TestSheet")

    # 1. Cell with None value but cached_value present
    cell1 = CellData(
        value=None,
        formula="[ExtBook.xlsx]Sheet!B2",
        cached_value=123.456,
        format_code="0.00",
    )
    sheet.set_cell(0, 0, cell1)
    assert sheet.get_formatted_text(0, 0) == "123.46"

    # 2. Cell with #NAME? error but cached_value present
    cell2 = CellData(value="#NAME?", formula="[UnknownExt]!Data", cached_value="Precalculated Text")
    sheet.set_cell(0, 1, cell2)
    assert sheet.get_formatted_text(0, 1) == "Precalculated Text"

    # 3. Cell with normal value ignores cached_value
    cell3 = CellData(value=999, formula="1+1", cached_value=2)
    sheet.set_cell(0, 2, cell3)
    assert sheet.get_formatted_text(0, 2) == "999"


def test_dag_recalculate_preserves_cached_value_on_external_error():
    """Verify formula DAG recalculation does not wipe cached_value on unknown name error."""
    sheet = SheetDataModel(name="Sheet1")
    # A cell referencing an external workbook that cannot be evaluated
    cell = CellData(
        value=None,
        formula="[1]ExternalSheet!$A$1 + 10",
        cached_value=150.0,
    )
    sheet.set_cell(0, 0, cell)
    wb = WorkbookModel(sheets=[sheet])

    dag = DependencyGraph()
    dag.recalculate(wb)

    recalculated_cell = sheet.get_cell(0, 0)
    assert recalculated_cell is not None
    # Evaluator returns #NAME? for unknown external reference, DAG falls back to cached_value
    assert recalculated_cell.value == 150.0
    assert recalculated_cell.cached_value == 150.0


def test_xlsx_reader_loads_cached_values_and_one_cell_anchor(qapp):
    """Verify openxml-sdk__NoExtDataB1.xlsx parses cached values and oneCellAnchor properly."""
    fpath = Path("tests/docs/excel/xlsx/openxml-sdk__NoExtDataB1.xlsx")
    assert fpath.exists(), "Sample test workbook openxml-sdk__NoExtDataB1.xlsx missing"

    wb = read_xlsx(str(fpath))
    assert len(wb.sheets) > 0
    sh = wb.sheets[0]

    # Verify formula cells retained cached_value
    b2 = sh.get_cell(1, 1) # B2
    assert b2 is not None
    assert b2.formula == "POWER(A2,2)+2.5"
    assert b2.cached_value == 3.5

    d2 = sh.get_cell(1, 3) # D2
    assert d2 is not None
    assert d2.cached_value is not None

    # Verify drawing oneCellAnchor parsing
    assert hasattr(sh, "drawings")
    assert len(sh.drawings) == 1
    d = sh.drawings[0]
    assert d.kind == "chart"
    assert d.anchor_type == AnchorType.ONE_CELL
    assert d.from_point.col == 1 # Col B
    assert d.from_point.row == 6 # Row 7 (0-indexed 6)
    assert d.abs_rect[2] > 0 # Width > 0
    assert d.abs_rect[3] > 0 # Height > 0

    # Verify chart kind is bar (horizontal bar chart)
    assert isinstance(d.chart_data, dict)
    assert d.chart_data.get("kind") in ("bar", "barStacked", "barPct")


def test_grid_viewport_renders_with_cached_values(qapp):
    """Verify GridViewport does not crash or omit cells when rendering cached values."""
    sheet = SheetDataModel(name="RenderSheet")
    cell = CellData(value=None, formula="[MissingLink]!Val", cached_value=8888, format_code="#,##0")
    sheet.set_cell(2, 2, cell)

    viewport = GridViewport(model=sheet, selection=SelectionModel())
    viewport.resize(400, 300)

    # Trigger formatted text retrieval & verify effective display
    text = sheet.get_formatted_text(2, 2)
    assert text == "8,888"
    assert not sheet.is_empty(2, 2)
