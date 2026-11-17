"""Tests for restoring saved sheet view state from XLSX (Issue #378, TASK-DOC-L04).

Covers <sheetView> attributes (activeCell/sqref selection, showGridLines,
zoomScale, view, topLeftCell), stored <rowBreaks>/<colBreaks>, the XLSX round
trip, and how the Ledger view applies the state on open.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.spreadsheet.models.selection_model import SelectionRange
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel, SheetViewState
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

FIXTURES = Path(__file__).parent / "docs" / "excel" / "xlsx"


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    if not path.exists():
        pytest.skip(f"fixture missing: {name}")
    return path


def _round_trip(wb: WorkbookModel) -> WorkbookModel:
    buf = io.BytesIO()
    write_xlsx(wb, buf)
    return read_xlsx(buf.getvalue())


def _sheet_xml(wb: WorkbookModel, index: int = 1) -> str:
    buf = io.BytesIO()
    write_xlsx(wb, buf)
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as zf:
        return zf.read(f"xl/worksheets/sheet{index}.xml").decode("utf-8")


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------
def test_view_state_defaults() -> None:
    vs = SheetDataModel().view_state
    assert vs.active_cell is None
    assert vs.sqref is None
    assert vs.show_grid_lines is True
    assert vs.zoom_scale is None
    assert vs.view == "normal"
    assert vs.top_left_cell is None
    assert vs.row_breaks == []
    assert vs.col_breaks == []
    assert vs.active_cell_rc() is None
    assert vs.selection_ranges() == []


def test_view_state_parses_multi_range_sqref() -> None:
    vs = SheetViewState(active_cell="C3", sqref="A1:B2 C3 $D$4:E5")
    assert vs.active_cell_rc() == (2, 2)
    assert vs.selection_ranges() == [(0, 0, 1, 1), (2, 2, 2, 2), (3, 3, 4, 4)]


def test_view_state_ignores_malformed_refs() -> None:
    vs = SheetViewState(active_cell="ZZZZ0", sqref="bogus A1:B2 !!")
    assert vs.active_cell_rc() is None
    assert vs.selection_ranges() == [(0, 0, 1, 1)]


# ---------------------------------------------------------------------------
# Reader (acceptance criteria 1 and 2)
# ---------------------------------------------------------------------------
def test_pivot2_row_active_sheet_active_cell_a9() -> None:
    wb = read_xlsx(_fixture("libreoffice__Pivot2_Row.xlsx"))
    vs = wb.active_sheet.view_state
    assert vs.active_cell == "A9"
    assert vs.sqref == "A9"
    assert wb.sheets[0].view_state.active_cell == "C6"
    assert wb.sheets[0].view_state.sqref == "A1:C6"


def test_conditional_fmt_origin_active_cell_g14() -> None:
    wb = read_xlsx(_fixture("libreoffice__conditional_fmt_origin.xlsx"))
    assert wb.active_sheet.view_state.active_cell == "G14"


def test_poi_49156_view_state() -> None:
    wb = read_xlsx(_fixture("poi__49156.xlsx"))
    vs = wb.active_sheet.view_state
    assert vs.active_cell == "C32"
    assert vs.sqref == "C32:D32"
    assert vs.selection_ranges() == [(31, 2, 31, 3)]
    assert vs.show_grid_lines is False
    assert vs.zoom_scale == 75
    assert vs.view == "pageBreakPreview"
    assert vs.row_breaks == [51]
    assert wb.active_sheet.extra["zoom"] == 75


def test_totals_row_function_hides_gridlines() -> None:
    wb = read_xlsx(_fixture("libreoffice__totalsRowFunction.xlsx"))
    assert wb.active_sheet.view_state.show_grid_lines is False


def _xlsx_with_sheet_view(sheet_views: str, tail: str = "") -> bytes:
    """Build a minimal one-sheet workbook with a custom <sheetViews> block."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pns = "http://schemas.openxmlformats.org/package/2006/relationships"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{pns}">'
            f'<Relationship Id="rId1" Type="{rns}/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "xl/workbook.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{ns}" xmlns:r="{rns}">'
            '<sheets><sheet name="S" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{pns}">'
            f'<Relationship Id="rId1" Type="{rns}/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{ns}" xmlns:r="{rns}">'
            f"{sheet_views}<sheetData/>{tail}</worksheet>",
        )
    return buf.getvalue()


def test_frozen_pane_selection_matches_active_pane() -> None:
    data = _xlsx_with_sheet_view(
        '<sheetViews><sheetView workbookViewId="0" topLeftCell="B5">'
        '<pane ySplit="2" topLeftCell="A3" activePane="bottomLeft" state="frozen"/>'
        '<selection pane="bottomLeft" activeCell="D10" sqref="D10:E11"/>'
        '<selection pane="topLeft" activeCell="A1" sqref="A1"/>'
        "</sheetView></sheetViews>"
    )
    sheet = read_xlsx(data).active_sheet
    assert sheet.freeze_rows == 2
    assert sheet.view_state.active_cell == "D10"
    assert sheet.view_state.sqref == "D10:E11"
    assert sheet.view_state.top_left_cell == "B5"


def test_page_break_preview_prefers_sheet_layout_zoom() -> None:
    data = _xlsx_with_sheet_view(
        '<sheetViews><sheetView view="pageBreakPreview" zoomScale="100" '
        'zoomScaleSheetLayoutView="60" workbookViewId="0"/></sheetViews>',
        '<colBreaks count="1" manualBreakCount="1"><brk id="4" max="1048575" man="1"/></colBreaks>',
    )
    sheet = read_xlsx(data).active_sheet
    assert sheet.view_state.zoom_scale == 60
    assert sheet.view_state.col_breaks == [4]


def test_malformed_view_attributes_are_ignored() -> None:
    data = _xlsx_with_sheet_view(
        '<sheetViews><sheetView zoomScale="abc" view="weird" workbookViewId="0">'
        '<selection activeCell="??" sqref=""/></sheetView></sheetViews>',
        '<rowBreaks><brk id="x"/><brk id="7"/></rowBreaks>',
    )
    vs = read_xlsx(data).active_sheet.view_state
    assert vs.zoom_scale is None
    assert vs.view == "normal"
    assert vs.active_cell_rc() is None
    assert vs.selection_ranges() == []
    assert vs.row_breaks == [7]


# ---------------------------------------------------------------------------
# Writer round trip (acceptance criterion 3)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("carry_source", [True, False], ids=["carry", "serialize"])
def test_round_trip_keeps_view_attributes(carry_source: bool) -> None:
    wb = read_xlsx(_fixture("poi__49156.xlsx"))
    if not carry_source:
        wb.source_package = None
        wb.extra.pop("source_package", None)
    vs2 = _round_trip(wb).active_sheet.view_state
    assert vs2.active_cell == "C32"
    assert vs2.sqref == "C32:D32"
    assert vs2.show_grid_lines is False
    assert vs2.zoom_scale == 75
    assert vs2.view == "pageBreakPreview"
    assert vs2.row_breaks == [51]


def test_writer_emits_schema_ordered_view_xml() -> None:
    sheet = SheetDataModel()
    sheet.set_cell_value(0, 0, 1)
    sheet.view_state = SheetViewState(
        active_cell="B2",
        sqref="B2:C3 E5",
        show_grid_lines=False,
        zoom_scale=150,
        top_left_cell="A2",
        row_breaks=[10],
        col_breaks=[3],
    )
    xml = _sheet_xml(WorkbookModel(sheets=[sheet]))
    assert 'showGridLines="0"' in xml
    assert 'zoomScale="150"' in xml
    assert 'topLeftCell="A2"' in xml
    assert '<selection activeCell="B2" sqref="B2:C3 E5"/>' in xml
    assert xml.index("<pageMargins") < xml.index("<rowBreaks") < xml.index("<colBreaks")
    vs2 = _round_trip(WorkbookModel(sheets=[sheet])).active_sheet.view_state
    assert vs2.row_breaks == [10]
    assert vs2.col_breaks == [3]
    assert vs2.top_left_cell == "A2"


def test_writer_default_view_stays_minimal() -> None:
    sheet = SheetDataModel()
    sheet.set_cell_value(0, 0, 1)
    xml = _sheet_xml(WorkbookModel(sheets=[sheet]))
    assert '<sheetView tabSelected="1" workbookViewId="0"/>' in xml
    assert "<rowBreaks" not in xml
    assert "<colBreaks" not in xml


# ---------------------------------------------------------------------------
# View integration
# ---------------------------------------------------------------------------
@pytest.fixture
def make_view(qtbot):
    from atboffice.modules.spreadsheet.view import SpreadsheetView

    def _make(wb: WorkbookModel) -> SpreadsheetView:
        view = SpreadsheetView(workbook=wb)
        qtbot.addWidget(view)
        view.resize(900, 600)
        return view

    return _make


def test_view_restores_selection_zoom_and_page_break(make_view) -> None:
    view = make_view(read_xlsx(_fixture("poi__49156.xlsx")))
    sel = view.selection
    assert sel.active_cell == (31, 2)
    assert sel.ranges == [SelectionRange(31, 2, 31, 3)]
    assert view.grid.zoom == pytest.approx(0.75)
    assert view.grid.view_mode == "page_break"
    assert view.grid.show_grid_lines is False


def test_view_restores_active_cell_on_active_sheet(make_view) -> None:
    view = make_view(read_xlsx(_fixture("libreoffice__Pivot2_Row.xlsx")))
    assert view.selection.active_cell == (8, 0)
    assert view.grid.show_grid_lines is True
    assert view.grid.view_mode == "normal"


def test_selection_changes_sync_back_to_view_state(make_view) -> None:
    sheet = SheetDataModel()
    view = make_view(WorkbookModel(sheets=[sheet]))
    view.selection.select_cell(4, 1)
    view.selection.extend_to(6, 2)
    assert sheet.view_state.active_cell == "C7"
    assert sheet.view_state.sqref == "B5:C7"


def test_top_left_cell_scrolls_viewport_once(make_view) -> None:
    sheet = SheetDataModel()
    sheet.view_state = SheetViewState(top_left_cell="E20")
    other = SheetDataModel()
    other.name = "Other"
    wb = WorkbookModel(sheets=[sheet, other])
    view = make_view(wb)
    geo = sheet.geometry
    assert view.grid.verticalScrollBar().value() == geo.row_pos(19)
    assert view.grid.horizontalScrollBar().value() == geo.col_pos(4)

    view.grid.verticalScrollBar().setValue(0)
    view.set_active_sheet_index(1)
    view.set_active_sheet_index(0)
    assert view.grid.verticalScrollBar().value() == 0


def test_page_break_bounds_use_stored_breaks() -> None:
    from atboffice.modules.spreadsheet.views.grid_viewport import page_bounds

    assert page_bounds([], 90, 45) == [0, 45, 90]
    assert page_bounds([], 10, 45) == [0, 45]
    assert page_bounds([51], 60, 45) == [0, 45, 51, 96]
    assert page_bounds([20, 30, 500], 40, 45) == [0, 20, 30, 75]
