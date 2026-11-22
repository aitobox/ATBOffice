"""Phase 11 / #444: Ledger chart, picture, data-tool, and menu wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QDialog

from atboffice.modules.spreadsheet.dialogs.chart_wizard import ChartWizardDialog
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.tools.chart_builder import build_chart_data
from atboffice.ui.shell.ledger_window import LedgerWindow


@pytest.fixture
def win(qapp: QApplication) -> LedgerWindow:
    w = LedgerWindow()
    yield w
    w.set_modified(False) if hasattr(w, "set_modified") else None
    w.close()
    w.deleteLater()


def _sales_sheet(sheet: SheetDataModel) -> None:
    rows = [
        ["Region", "Q1", "Q2"],
        ["East", 10, 20],
        ["West", 30, 40],
        ["North", 50, 60],
    ]
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            sheet.set_cell_value(r, c, v)


def _select(win: LedgerWindow, r1: int, c1: int, r2: int, c2: int) -> None:
    sel = win.spreadsheet_view.selection
    sel.select_cell(r1, c1)
    sel.extend_to(r2, c2)


# ---------------------------------------------------------------- charts
def test_chart_builder_reads_headers_and_series_in_columns() -> None:
    sheet = SheetDataModel(name="Sheet1")
    _sales_sheet(sheet)
    data = build_chart_data({"data_range": "=Sheet1!$A$1:$C$4", "type": "column"}, None, sheet)
    assert data["kind"] == "col"
    assert data["cats"] == ["East", "West", "North"]
    assert [s["name"] for s in data["series"]] == ["Q1", "Q2"]
    assert data["series"][0]["vals"] == [10.0, 30.0, 50.0]


def test_chart_builder_series_in_rows_and_subtypes() -> None:
    sheet = SheetDataModel(name="Sheet1")
    _sales_sheet(sheet)
    spec = {
        "data_range": "A1:C4",
        "series_in": "rows",
        "type": "bar",
        "sub_type": "stacked_bar",
        "show_legend": False,
    }
    data = build_chart_data(spec, None, sheet)
    assert data["kind"] == "barStacked"
    assert data["legend"] == "none"
    assert data["cats"] == ["Q1", "Q2"]
    assert [s["name"] for s in data["series"]] == ["East", "West", "North"]
    assert data["series"][2]["vals"] == [50.0, 60.0]


def test_chart_wizard_finish_binds_real_data(qapp: QApplication) -> None:
    wb = WorkbookModel()
    sheet = wb.sheets[0]
    _sales_sheet(sheet)
    dlg = ChartWizardDialog(sheet_model=sheet, workbook_model=wb, initial_range="=Sheet1!$A$1:$C$4")
    dlg._on_finish()
    assert len(sheet.drawings) == 1
    chart = sheet.drawings[0]
    assert chart.chart_data["series"][1]["vals"] == [20.0, 40.0, 60.0]
    assert chart.chart_data["cats"] == ["East", "West", "North"]


def test_chart_wizard_as_new_sheet_creates_chart_sheet(qapp: QApplication) -> None:
    wb = WorkbookModel()
    sheet = wb.sheets[0]
    _sales_sheet(sheet)
    dlg = ChartWizardDialog(sheet_model=sheet, workbook_model=wb, initial_range="=Sheet1!$A$1:$C$4")
    dlg.radio_loc_new.setChecked(True)
    dlg.edit_new_sheet_name.setText("Chart1")
    dlg._on_finish()
    assert [s.name for s in wb.sheets] == ["Sheet1", "Chart1"]
    chart_sheet = wb.sheets[1]
    assert chart_sheet.extra.get("chart_sheet") is True
    assert len(chart_sheet.drawings) == 1 and not sheet.drawings
    assert chart_sheet.drawings[0].chart_data["series"]


def test_chart_wizard_custom_series_tab(qapp: QApplication) -> None:
    wb = WorkbookModel()
    sheet = wb.sheets[0]
    _sales_sheet(sheet)
    dlg = ChartWizardDialog(sheet_model=sheet, workbook_model=wb)
    dlg.list_series.setCurrentRow(0)
    dlg.edit_series_name.setText("=Sheet1!$B$1")
    dlg.edit_series_values.setText("=Sheet1!$B$2:$B$4")
    dlg.edit_series_x.setText("=Sheet1!$A$2:$A$4")
    while len(dlg.series_list) > 1:
        dlg.list_series.setCurrentRow(len(dlg.series_list) - 1)
        dlg._on_del_series()
    spec = dlg.get_chart_spec()
    assert spec["custom_series"]
    dlg._on_finish()
    data = sheet.drawings[0].chart_data
    assert data["series"][0]["name"] == "Q1"
    assert data["series"][0]["vals"] == [10.0, 30.0, 50.0]
    assert data["cats"] == ["East", "West", "North"]


def test_toolbar_chart_wizard_opens_dialog_and_binds_selection(win: LedgerWindow) -> None:
    sheet = win.spreadsheet_view.model
    _sales_sheet(sheet)
    _select(win, 0, 0, 3, 2)

    def fake_exec(dlg: ChartWizardDialog) -> int:
        assert "$A$1:$C$4" in dlg.edit_data_range.text()
        dlg._on_finish()
        return QDialog.DialogCode.Accepted

    with patch.object(ChartWizardDialog, "exec", fake_exec):
        win.action_registry.trigger_action("chartWizard")
    assert len(sheet.drawings) == 1
    chart = sheet.drawings[0]
    assert chart.chart_data["cats"] == ["East", "West", "North"]
    assert win.spreadsheet_view.object_layer.selected_object is chart


def test_chart_type_button_changes_selected_chart_kind(win: LedgerWindow) -> None:
    sheet = win.spreadsheet_view.model
    _sales_sheet(sheet)
    _select(win, 0, 0, 3, 2)
    with patch.object(
        ChartWizardDialog,
        "exec",
        lambda d: (d._on_finish(), QDialog.DialogCode.Accepted)[1],
    ):
        win.open_chart_wizard()
    win.set_chart_type("line")
    assert sheet.drawings[0].chart_data["kind"] == "line"


# ---------------------------------------------------------------- pictures
def test_insert_picture_stores_bytes(win: LedgerWindow, tmp_path: Path) -> None:
    img = QImage(80, 40, QImage.Format.Format_ARGB32)
    img.fill(QColor("#336699"))
    path = tmp_path / "logo.png"
    assert img.save(str(path))
    win.insert_picture(str(path))
    objs = win.spreadsheet_view.model.drawings
    assert len(objs) == 1
    pic = objs[0]
    assert pic.kind == "image"
    assert pic.image_data == path.read_bytes()
    assert pic.image_mime == "image/png"
    assert pic.name == "logo"


def test_insert_picture_rejects_non_image(win: LedgerWindow, tmp_path: Path) -> None:
    bad = tmp_path / "bad.png"
    bad.write_text("not an image")
    with patch("atboffice.ui.shell.ledger_window.QMessageBox.warning") as warn:
        win.insert_picture(str(bad))
    assert warn.called
    assert not win.spreadsheet_view.model.drawings


# ---------------------------------------------------------------- data tools
from atboffice.modules.spreadsheet.tools import data_tools  # noqa: E402


def _region_sheet(wb: WorkbookModel) -> SheetDataModel:
    sheet = wb.sheets[0]
    rows = [["Region", "Amount"], ["East", 10], ["East", 20], ["West", 5], ["West", 7]]
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            sheet.set_cell_value(r, c, v)
    return sheet


def test_apply_and_remove_subtotals(qapp: QApplication) -> None:
    wb = WorkbookModel()
    sheet = _region_sheet(wb)
    sheet.set_cell_value(7, 0, "below")
    cfg = {"group_by_col": 0, "function_code": 9, "subtotal_cols": [1], "summary_below": True}
    rect = data_tools.apply_subtotals(sheet, (0, 0, 4, 1), cfg)
    wb.recalculate()
    assert rect == (0, 0, 7, 1)
    assert sheet.get_cell_value(3, 0) == "East 汇总"
    assert sheet.get_cell(3, 1).formula == "SUBTOTAL(9,B2:B3)"
    assert sheet.get_cell_value(3, 1) == 30
    assert sheet.get_cell_value(6, 0) == "West 汇总"
    assert sheet.get_cell_value(6, 1) == 12
    assert sheet.get_cell_value(7, 0) == "总计"
    assert sheet.get_cell_value(7, 1) == 42
    # Content below the list was pushed down, not overwritten.
    assert sheet.get_cell_value(10, 0) == "below"

    back = data_tools.remove_subtotals(sheet, rect)
    assert back == (0, 0, 4, 1)
    assert sheet.get_cell_value(4, 1) == 7
    assert sheet.get_cell_value(7, 0) == "below"


def test_consolidate_by_position_and_labels(qapp: QApplication) -> None:
    wb = WorkbookModel()
    s1 = wb.sheets[0]
    s2 = wb.add_sheet(name="Sheet2")
    for sh, vals in ((s1, [("A", 1), ("B", 2)]), (s2, [("B", 10), ("C", 20)])):
        sh.set_cell_value(0, 0, "Item")
        sh.set_cell_value(0, 1, "Qty")
        for i, (k, v) in enumerate(vals, start=1):
            sh.set_cell_value(i, 0, k)
            sh.set_cell_value(i, 1, v)
    out = wb.add_sheet(name="Total")
    cfg = {
        "function": "SUM",
        "references": ["Sheet1!$A$1:$B$3", "Sheet2!$A$1:$B$3"],
        "top_row": True,
        "left_column": True,
    }
    data_tools.consolidate(wb, out, (0, 0), cfg)
    got = {out.get_cell_value(r, 0): out.get_cell_value(r, 1) for r in range(1, 4)}
    assert got == {"A": 1, "B": 12, "C": 20}
    assert out.get_cell_value(0, 1) == "Qty"

    pos = wb.add_sheet(name="Pos")
    cfg = {"function": "MAX", "references": ["Sheet1!$B$2:$B$3", "Sheet2!$B$2:$B$3"]}
    data_tools.consolidate(wb, pos, (0, 0), cfg)
    assert [pos.get_cell_value(0, 0), pos.get_cell_value(1, 0)] == [10, 20]


def test_advanced_filter_in_place_copy_and_unique(qapp: QApplication) -> None:
    wb = WorkbookModel()
    sheet = _region_sheet(wb)
    sheet.set_cell_value(5, 0, "East")
    sheet.set_cell_value(5, 1, 20)
    sheet.set_cell_value(0, 4, "Amount")
    sheet.set_cell_value(1, 4, ">=10")
    params = {"list_range": "$A$1:$B$6", "criteria_range": "$E$1:$E$2", "action": "in_place"}
    info = data_tools.advanced_filter(wb, sheet, params)
    assert info["matched"] == 3
    assert sheet.geometry.hidden_rows >= {3, 4}
    assert 1 not in sheet.geometry.hidden_rows
    assert data_tools.show_all_after_filter(sheet)
    assert not ({3, 4} & sheet.geometry.hidden_rows)

    params.update(action="copy_to", copy_to="$G$1", unique_only=True)
    info = data_tools.advanced_filter(wb, sheet, params)
    assert info["matched"] == 2  # duplicate East/20 collapsed
    assert sheet.get_cell_value(0, 6) == "Region"
    assert [sheet.get_cell_value(r, 7) for r in (1, 2)] == [10, 20]


def test_criteria_semantics() -> None:
    m = data_tools.criterion_matches
    assert m("Eastern", "East") and not m("West", "East")
    assert m(5, "<>4") and m("abc", "=a*") and not m("abc", "=b*")
    assert m(None, "=") and not m("x", "=")


def test_data_table_two_inputs_recalculates(qapp: QApplication) -> None:
    wb = WorkbookModel()
    sheet = wb.sheets[0]
    sheet.set_cell_value(0, 5, 1)  # F1 rate input
    sheet.set_cell_value(1, 5, 1)  # F2 qty input
    corner = sheet.ensure_cell(3, 0)
    corner.formula = "F1*F2"
    for j, v in enumerate([10, 20], start=1):
        sheet.set_cell_value(3, j, v)
    for i, v in enumerate([2, 3], start=1):
        sheet.set_cell_value(3 + i, 0, v)
    n = data_tools.compute_data_table(wb, sheet, (3, 0, 5, 2), "$F$1", "$F$2")
    assert n == 4
    assert [sheet.get_cell_value(4, 1), sheet.get_cell_value(4, 2)] == [20, 40]
    assert [sheet.get_cell_value(5, 1), sheet.get_cell_value(5, 2)] == [30, 60]
    # Inputs are restored after the what-if run.
    assert sheet.get_cell_value(0, 5) == 1 and sheet.get_cell_value(1, 5) == 1


def test_data_table_column_input_only(qapp: QApplication) -> None:
    wb = WorkbookModel()
    sheet = wb.sheets[0]
    sheet.set_cell_value(0, 4, 0)  # E1 input
    sheet.ensure_cell(0, 1).formula = "E1*2"
    sheet.ensure_cell(0, 2).formula = "E1+100"
    for i, v in enumerate([1, 5], start=1):
        sheet.set_cell_value(i, 0, v)
    data_tools.compute_data_table(wb, sheet, (0, 0, 2, 2), "", "E1")
    assert [sheet.get_cell_value(1, 1), sheet.get_cell_value(1, 2)] == [2, 101]
    assert [sheet.get_cell_value(2, 1), sheet.get_cell_value(2, 2)] == [10, 105]


def test_data_table_requires_input() -> None:
    sheet = SheetDataModel(name="Sheet1")
    with pytest.raises(ValueError):
        data_tools.compute_data_table(None, sheet, (0, 0, 2, 2), "", "")


def test_scenario_summary_sheet(qapp: QApplication) -> None:
    wb = WorkbookModel()
    sheet = wb.sheets[0]
    sheet.set_cell_value(0, 1, 100)  # B1
    sheet.ensure_cell(1, 1).formula = "B1*2"  # B2
    wb.recalculate()
    scenarios = [
        {"name": "Low", "values": {"$B$1": "10"}},
        {"name": "High", "values": {"$B$1": "50"}},
    ]
    out = data_tools.scenario_summary(wb, sheet, scenarios, "$B$2")
    assert out.name == "方案摘要"
    assert out.get_cell_value(1, 3) == "Low" and out.get_cell_value(1, 4) == "High"
    assert [out.get_cell_value(3, c) for c in (1, 2, 3, 4)] == ["$B$1", 100, 10, 50]
    assert [out.get_cell_value(5, c) for c in (2, 3, 4)] == [200, 20, 100]
    assert sheet.get_cell_value(0, 1) == 100  # original value restored


def test_split_fixed_width() -> None:
    assert data_tools.split_fixed_width("AB  12345", [4]) == ["AB", "12345"]
    assert data_tools.suggest_fixed_breaks(["AB  123", "CD  456"]) == [4]


# ---------------------------------------------------------------- window wiring
from PySide6.QtWidgets import QInputDialog, QMessageBox  # noqa: E402

from atboffice.modules.spreadsheet.dialogs.data_table_dialog import DataTableDialog  # noqa: E402
from atboffice.modules.spreadsheet.dialogs.subtotal_dialog import SubtotalDialog  # noqa: E402
from atboffice.modules.spreadsheet.views.object_layer import (  # noqa: E402
    AnchorType,
    FloatingObject,
)


def _unbound_visible_actions(win: LedgerWindow) -> list[str]:
    reg = win.action_registry
    out = []
    for aid, spec in reg._specs.items():
        act = reg._actions.get(aid)
        if spec.handler is None and not reg.is_whitelisted_action(aid):
            if act is not None and act.isVisible() and act.isEnabled():
                out.append(aid)
    return sorted(out)


def test_menu_ids_reconciled_and_ledger_items_present(win: LedgerWindow) -> None:
    menu = win.menu_bar
    for aid in (
        "data_filter", "data_validation", "insert_page_break", "insert_symbol", "insert_shape",
        "format_font", "format_borders", "selectAll", "clearAll", "clearFormats",
        "clearContents", "clearComments", "defineName", "headerFooter", "condFormat",
        "autoFormat", "sortDlg", "advancedFilter", "showAllFilter", "textToColumns",
        "consolidate", "dataTable", "scenarios", "protectSheet", "protectWorkbook",
        "insertComment", "insertChart", "drawBorder", "draw_ungroup", "spelling",
    ):
        spec = win.action_registry.get_spec(aid)
        assert spec is not None and spec.handler is not None, aid
    # Word-only items are hidden in Ledger.
    for aid in ("format_paragraph", "bullets", "format_tabs", "view_ruler", "tools_language"):
        assert not menu.action_map[aid].isVisible(), aid
    assert menu.menu_map["edit_clear"].menuAction().isVisible()
    # Only menus that Ledger never mounts (Table / Slide Show) still lack handlers.
    leftovers = [
        a for a in _unbound_visible_actions(win)
        if not (a.startswith(("table_", "slideshow_", "start_slideshow"))
                or a in ("drawTable", "mergeCells", "splitCells"))
    ]
    assert leftovers == []
    assert not win.action_registry.is_enabled("draw_group")


def test_ledger_only_menu_items_hidden_in_other_apps(qapp: QApplication) -> None:
    from atboffice.ui.shell.mac_menu import MacMenuBar

    bar = MacMenuBar(app_type="lectern")
    try:
        assert not bar.action_map["condFormat"].isVisible()
        assert not bar.menu_map["edit_clear"].menuAction().isVisible()
        assert bar.action_map["insertChart"].isVisible()
        bar.set_app_type("quire")
        assert bar.action_map["format_paragraph"].isVisible()
        assert bar.action_map["headerFooter"].isVisible()
    finally:
        bar.deleteLater()


def test_sort_dialog_opens_real_dialog(win: LedgerWindow) -> None:
    with patch.object(type(win.spreadsheet_view.grid), "open_sort_dialog") as op:
        win.action_registry.trigger_action("sortDlg")
    assert op.called


def test_clear_formats_and_all_are_undoable(win: LedgerWindow) -> None:
    sheet = win.spreadsheet_view.model
    cell = sheet.ensure_cell(0, 0)
    cell.value = "x"
    cell.bold = True
    sheet.set_comment(0, 0, "note", "me") if hasattr(sheet, "set_comment") else None
    _select(win, 0, 0, 0, 0)
    win.action_registry.trigger_action("clearFormats")
    assert sheet.get_cell(0, 0).value == "x" and not sheet.get_cell(0, 0).bold
    win.action_registry.trigger_action("clearAll")
    assert sheet.get_cell(0, 0) is None
    assert not sheet.comments
    win.spreadsheet_view.grid.undo()
    assert sheet.get_cell_value(0, 0) == "x"


def test_define_name_and_page_break(win: LedgerWindow) -> None:
    _select(win, 0, 0, 2, 1)
    assert win.ledger_commands.define_name("Sales")
    xml = win.spreadsheet_view.workbook.extra["defined_names"]
    assert '<definedName name="Sales">Sheet1!$A$1:$B$3</definedName>' in xml
    with patch.object(QMessageBox, "warning") as warn:
        assert not win.ledger_commands.define_name("A1")
    assert warn.called

    _select(win, 5, 0, 5, 0)
    win.action_registry.trigger_action("insert_page_break")
    assert 5 in win.spreadsheet_view.model.view_state.row_breaks
    win.action_registry.trigger_action("insert_page_break")
    assert 5 not in win.spreadsheet_view.model.view_state.row_breaks


def test_header_footer_and_autoformat(win: LedgerWindow) -> None:
    from atboffice.ui.shell import ledger_commands

    def fake_exec(dlg: QDialog) -> int:
        dlg.edit_header.setText("Quarterly")
        dlg.edit_footer.setText("Page &[Page]")
        return QDialog.DialogCode.Accepted

    with patch.object(ledger_commands.HeaderFooterDialog, "exec", fake_exec):
        win.action_registry.trigger_action("headerFooter")
    assert win.spreadsheet_view.model.extra["header_footer"]["header"] == "Quarterly"

    sheet = win.spreadsheet_view.model
    _sales_sheet(sheet)
    _select(win, 0, 0, 0, 0)
    win.ledger_commands.auto_format("colorful1")
    assert sheet.get_cell(0, 1).bg_color == "#000080"
    assert sheet.get_cell(3, 2).bg_color in ("#CCFFFF", "#FFFFFF")


def test_conditional_format_color_scale_and_icons(win: LedgerWindow) -> None:
    from atboffice.modules.spreadsheet.dialogs.conditional_format_dialog import (
        KIND_ICON_SET,
        KIND_SCALE3,
        ConditionalFormatDialog,
    )

    sheet = win.spreadsheet_view.model
    _sales_sheet(sheet)
    _select(win, 1, 1, 3, 1)

    def fake_exec(dlg: ConditionalFormatDialog) -> int:
        row = dlg.rows[0]
        row.combo_type.setCurrentIndex(row.combo_type.findData(KIND_SCALE3))
        dlg._add_row()
        second = dlg.rows[1]
        second.combo_type.setCurrentIndex(second.combo_type.findData(KIND_ICON_SET))
        return QDialog.DialogCode.Accepted

    with patch.object(ConditionalFormatDialog, "exec", fake_exec):
        win.action_registry.trigger_action("condFormat")
    cf = sheet.conditional_formats[-1]
    assert cf.ranges == [(1, 1, 3, 1)]
    assert cf.rules[0].color_scale is not None and len(cf.rules[0].color_scale.colors) == 3
    assert cf.rules[1].icon_set is not None and cf.rules[1].icon_set.set_name == "3Arrows"
    from atboffice.modules.spreadsheet.models.conditional_format import evaluate_cf_for_cell

    result = evaluate_cf_for_cell(sheet, 3, 1)
    assert result is not None and result.bg_color and result.icon


def test_conditional_format_dialog_round_trips_data_bar(qapp: QApplication) -> None:
    from atboffice.modules.spreadsheet.dialogs.conditional_format_dialog import (
        KIND_DATA_BAR,
        ConditionalFormatDialog,
    )

    dlg = ConditionalFormatDialog(sqref="A1:A3", ranges=[(0, 0, 2, 0)])
    row = dlg.rows[0]
    row.combo_type.setCurrentIndex(row.combo_type.findData(KIND_DATA_BAR))
    row.bar_color = "#FF0000"
    cf = dlg.get_conditional_format()
    assert cf.rules[0].data_bar.color == "#FF0000"
    again = ConditionalFormatDialog(existing_cf=cf, sqref="A1:A3", ranges=[(0, 0, 2, 0)])
    assert again.rows[0].combo_type.currentData() == KIND_DATA_BAR
    assert again.rows[0].bar_color == "#FF0000"


def test_window_subtotal_dialog_applies_and_undoes(win: LedgerWindow) -> None:
    sheet = win.spreadsheet_view.model
    _region_sheet(win.spreadsheet_view.workbook)
    _select(win, 0, 0, 4, 1)

    def fake_exec(dlg: SubtotalDialog) -> int:
        dlg._on_ok()
        return QDialog.DialogCode.Accepted

    with patch.object(SubtotalDialog, "exec", fake_exec):
        win.action_registry.trigger_action("subtotals")
    assert sheet.get_cell_value(7, 0) == "总计"
    assert sheet.get_cell_value(7, 1) == 42
    win.spreadsheet_view.grid.undo()
    assert sheet.get_cell(7, 0) is None
    assert sheet.get_cell_value(4, 1) == 7


def test_window_data_table_uses_workbook_recalc(win: LedgerWindow) -> None:
    sheet = win.spreadsheet_view.model
    sheet.set_cell_value(0, 4, 0)
    sheet.ensure_cell(0, 1).formula = "E1*3"
    sheet.set_cell_value(1, 0, 2)
    sheet.set_cell_value(2, 0, 4)
    _select(win, 0, 0, 2, 1)

    def fake_exec(dlg: DataTableDialog) -> int:
        dlg.edit_col_input.setText("E1")
        dlg._on_ok()
        return dlg.result()

    with patch.object(DataTableDialog, "exec", fake_exec):
        win.action_registry.trigger_action("dataTable")
    assert [sheet.get_cell_value(1, 1), sheet.get_cell_value(2, 1)] == [6, 12]
    win.spreadsheet_view.grid.undo()
    assert sheet.get_cell(1, 1) is None


def test_window_zoom_to_selection(win: LedgerWindow) -> None:
    win.resize(1000, 700)
    win.show()
    qapp = QApplication.instance()
    qapp.processEvents()
    _select(win, 0, 0, 1, 1)
    win._apply_zoom("选定区域")
    assert win.spreadsheet_view.grid.zoom > 1.0


def test_ungroup_splits_group_children(win: LedgerWindow) -> None:
    layer = win.spreadsheet_view.object_layer
    group = FloatingObject(id=1, kind="rect", anchor_type=AnchorType.ABSOLUTE,
                           abs_rect=(100, 100, 200, 100))
    group.children = [
        FloatingObject(id=2, kind="oval", group_frac=(0.0, 0.0, 0.5, 1.0)),
        FloatingObject(id=3, kind="rect", group_frac=(0.5, 0.0, 0.5, 1.0)),
    ]
    layer.add_object(group)
    layer.select_object(group)
    assert win.ledger_commands.ungroup()
    kinds = sorted(o.kind for o in win.spreadsheet_view.model.drawings)
    assert kinds == ["oval", "rect"]
    rects = sorted(o.abs_rect for o in win.spreadsheet_view.model.drawings)
    assert rects == [(100, 100, 100, 100), (200, 100, 100, 100)]


class _FakeEngine:
    def is_valid_word(self, word: str) -> bool:
        return word.lower() not in {"teh", "recieve"}

    def suggest(self, word: str, max_suggestions: int = 8) -> list[str]:
        return {"teh": ["the"], "recieve": ["receive"]}.get(word.lower(), [])

    def add_to_custom_dict(self, word: str) -> None:
        pass


def test_sheet_spell_checker_change_all_and_ignore() -> None:
    from atboffice.modules.spreadsheet.tools.sheet_spelling import SheetSpellChecker, text_cells

    sheet = SheetDataModel(name="Sheet1")
    sheet.set_cell_value(0, 0, "teh cat and teh dog")
    sheet.set_cell_value(1, 0, "recieve NASA teh")
    sheet.ensure_cell(2, 0).formula = "A1"
    checker = SheetSpellChecker(sheet, text_cells(sheet), _FakeEngine())
    issue = checker.next_issue()
    assert (issue.r, issue.word) == (0, "teh")
    checker.change_everywhere(issue, "the")
    issue = checker.next_issue()
    assert (issue.r, issue.word) == (1, "recieve")
    checker.ignore(issue)
    assert checker.next_issue() is None
    assert sheet.get_cell_value(0, 0) == "the cat and the dog"
    assert sheet.get_cell_value(1, 0) == "recieve NASA the"


def test_spelling_command_uses_engine(win: LedgerWindow) -> None:
    from atboffice.modules.spreadsheet.dialogs.sheet_spelling_dialog import SheetSpellingDialog
    from atboffice.modules.writer.spell import SpellEngine

    sheet = win.spreadsheet_view.model
    sheet.set_cell_value(0, 0, "teh report")

    def fake_exec(dlg: SheetSpellingDialog) -> int:
        assert dlg.edit_word.text() == "the"
        with patch.object(QMessageBox, "information"):
            dlg._on_change()
        return QDialog.DialogCode.Accepted

    with patch.object(SpellEngine, "get_instance", return_value=_FakeEngine()), \
            patch.object(SheetSpellingDialog, "exec", fake_exec):
        win.action_registry.trigger_action("spelling")
    assert sheet.get_cell_value(0, 0) == "the report"

    sheet.set_cell_value(0, 0, "clean report")
    with patch.object(SpellEngine, "get_instance", return_value=_FakeEngine()), \
            patch.object(QMessageBox, "information") as info:
        win.action_registry.trigger_action("spelling")
    assert info.called


def test_scenario_summary_from_window(win: LedgerWindow) -> None:
    from atboffice.modules.spreadsheet.dialogs.scenario_manager_dialog import (
        ScenarioManagerDialog,
    )

    sheet = win.spreadsheet_view.model
    sheet.set_cell_value(1, 1, 5)

    def fake_exec(dlg: ScenarioManagerDialog) -> int:
        dlg._on_summary("")
        return dlg.result()

    with patch.object(ScenarioManagerDialog, "exec", fake_exec):
        win.action_registry.trigger_action("scenarios")
    names = [s.name for s in win.spreadsheet_view.workbook.sheets]
    assert "方案摘要" in names
    assert win.spreadsheet_view.model.name == "方案摘要"


def test_advanced_filter_from_window_error_is_reported(win: LedgerWindow) -> None:
    from atboffice.modules.spreadsheet.dialogs.advanced_filter_dialog import (
        AdvancedFilterDialog,
    )

    def fake_exec(dlg: AdvancedFilterDialog) -> int:
        dlg.edit_list.setText("not a range")
        dlg.edit_criteria.setText("??")
        dlg._on_ok()
        return dlg.result()

    with patch.object(AdvancedFilterDialog, "exec", fake_exec), \
            patch("atboffice.ui.shell.ledger_window.QMessageBox.warning") as warn:
        win.action_registry.trigger_action("advancedFilter")
    assert warn.called


def test_input_dialog_symbol_insert(win: LedgerWindow) -> None:
    from atboffice.modules.writer.dialogs.reference_dialogs import SymbolDialog

    _select(win, 0, 0, 0, 0)
    win.spreadsheet_view.model.set_cell_value(0, 0, "x")
    with patch.object(SymbolDialog, "exec", return_value=QDialog.DialogCode.Accepted), \
            patch.object(SymbolDialog, "get_selected_character", return_value="©"):
        win.action_registry.trigger_action("insert_symbol")
    assert win.spreadsheet_view.model.get_cell_value(0, 0) == "x©"
    assert QInputDialog is not None
