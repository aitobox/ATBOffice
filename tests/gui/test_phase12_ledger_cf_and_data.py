"""Tests for Phase 12 Wave 3 Task 4: Ledger CF E2E, Fixed-Width Ruler, and PivotChart."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent
from PySide6.QtWidgets import QApplication, QDialog

from atboffice.modules.spreadsheet.calc.pivots import (
    PivotFieldSpec,
    PivotLayoutSpec,
    PivotValueSpec,
    build_interactive_pivot,
)
from atboffice.modules.spreadsheet.dialogs.conditional_format_dialog import (
    KIND_DATA_BAR,
    KIND_ICON_SET,
    KIND_SCALE2,
    KIND_SCALE3,
    ConditionalFormatDialog,
)
from atboffice.modules.spreadsheet.dialogs.text_to_columns_wizard import (
    FixedWidthRulerWidget,
    TextToColumnsWizard,
)
from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.spreadsheet.models.conditional_format import (
    CFVO,
    CFRule,
    CFRuleType,
    ColorScaleRule,
    ConditionalFormat,
    DataBarRule,
    IconSetRule,
    evaluate_cf_for_cell,
)
from atboffice.modules.spreadsheet.models.sheet_model import CellData
from atboffice.ui.shell.ledger_window import LedgerWindow


@pytest.fixture
def ledger_win(qapp: QApplication) -> LedgerWindow:
    win = LedgerWindow()
    win.resize(1100, 760)
    yield win
    win.set_modified(False)
    win.close()
    qapp.processEvents()


def _select_range(win: LedgerWindow, r1: int, c1: int, r2: int, c2: int) -> None:
    sel = win.spreadsheet_view.selection
    sel.select_cell(r1, c1)
    sel.extend_to(r2, c2)


def _mouse_event(
    etype: QEvent.Type,
    pos: QPointF,
    button: Qt.MouseButton,
    buttons: Qt.MouseButtons,
) -> QMouseEvent:
    return QMouseEvent(etype, pos, pos, button, buttons, Qt.KeyboardModifier.NoModifier)


# =============================================================================
# 1. Conditional Formatting E2E (Color Scales, Data Bars, Icon Sets)
# =============================================================================


class TestConditionalFormattingE2E:
    """E2E: dialog -> echo -> undo/redo -> QImage paint -> XLSX round-trip."""

    @pytest.mark.parametrize(
        "rule_kind",
        ["scale2", "scale3", "data_bar", "icon_set"],
    )
    def test_cf_dialog_undo_paint_and_xlsx_roundtrip(
        self,
        ledger_win: LedgerWindow,
        tmp_path: Path,
        rule_kind: str,
    ) -> None:
        sheet = ledger_win.spreadsheet_view.model
        for idx, val in enumerate((10, 50, 90)):
            sheet.set_cell(idx, 0, CellData(value=val))
        _select_range(ledger_win, 0, 0, 2, 0)

        def configure_dialog(dlg: ConditionalFormatDialog) -> int:
            row = dlg.rows[0]
            if rule_kind == "scale2":
                row.combo_type.setCurrentIndex(row.combo_type.findData(KIND_SCALE2))
                row.scale_colors[0] = "#AA1122"
                row.scale_colors[2] = "#22AA44"
                row._update_color_buttons()
            elif rule_kind == "scale3":
                row.combo_type.setCurrentIndex(row.combo_type.findData(KIND_SCALE3))
                row.scale_colors = ["#CC0000", "#FFFF00", "#00AA00"]
                row._update_color_buttons()
            elif rule_kind == "data_bar":
                row.combo_type.setCurrentIndex(row.combo_type.findData(KIND_DATA_BAR))
                row.bar_color = "#1E88E5"
                row._update_color_buttons()
            elif rule_kind == "icon_set":
                row.combo_type.setCurrentIndex(row.combo_type.findData(KIND_ICON_SET))
                icon_idx = row.combo_icons.findData("4Arrows")
                assert icon_idx >= 0
                row.combo_icons.setCurrentIndex(icon_idx)
                row.chk_reverse.setChecked(True)
            return QDialog.DialogCode.Accepted

        with patch.object(ConditionalFormatDialog, "exec", configure_dialog):
            ledger_win.action_registry.trigger_action("condFormat")

        assert len(sheet.conditional_formats) == 1
        cf = sheet.conditional_formats[0]

        # Reopen dialog and verify rule echoes cleanly
        reopened = ConditionalFormatDialog(existing_cf=cf, sqref=cf.sqref, ranges=cf.ranges)
        r0 = reopened.rows[0]
        if rule_kind == "scale2":
            assert r0.combo_type.currentData() == KIND_SCALE2
            assert r0._scale_stops() == ["#AA1122", "#22AA44"]
        elif rule_kind == "scale3":
            assert r0.combo_type.currentData() == KIND_SCALE3
            assert r0._scale_stops() == ["#CC0000", "#FFFF00", "#00AA00"]
        elif rule_kind == "data_bar":
            assert r0.combo_type.currentData() == KIND_DATA_BAR
            assert r0.bar_color == "#1E88E5"
        elif rule_kind == "icon_set":
            assert r0.combo_type.currentData() == KIND_ICON_SET
            assert r0.combo_icons.currentData() == "4Arrows"
            assert r0.chk_reverse.isChecked() is True

        # Undo removes CF rule; Redo restores it
        ledger_win.undo()
        assert len(sheet.conditional_formats) == 0
        assert evaluate_cf_for_cell(sheet, 1, 0) is None

        ledger_win.redo()
        assert len(sheet.conditional_formats) == 1
        res_mid = evaluate_cf_for_cell(sheet, 1, 0)
        assert res_mid is not None

        # Offscreen QImage render of GridViewport
        grid = ledger_win.spreadsheet_view.grid
        grid.resize(500, 300)
        img = QImage(500, 300, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        grid.render(img)
        assert not img.isNull()
        cell_rect = grid.cell_rect(0, 0)
        center_px = img.pixelColor(cell_rect.center())
        assert center_px.isValid()

        # XLSX write -> read round-trip preserves rule
        out_path = tmp_path / f"cf_{rule_kind}.xlsx"
        write_xlsx(ledger_win.workbook, out_path)
        wb_read = read_xlsx(out_path)
        sh_read = wb_read.sheets[0]
        assert len(sh_read.conditional_formats) == 1
        rule_read = sh_read.conditional_formats[0].rules[0]
        if rule_kind == "scale2":
            assert isinstance(rule_read.color_scale, ColorScaleRule)
            assert rule_read.color_scale.colors == ["#AA1122", "#22AA44"]
        elif rule_kind == "scale3":
            assert isinstance(rule_read.color_scale, ColorScaleRule)
            assert rule_read.color_scale.colors == ["#CC0000", "#FFFF00", "#00AA00"]
        elif rule_kind == "data_bar":
            assert isinstance(rule_read.data_bar, DataBarRule)
            assert rule_read.data_bar.color == "#1E88E5"
        elif rule_kind == "icon_set":
            assert isinstance(rule_read.icon_set, IconSetRule)
            assert rule_read.icon_set.set_name == "4Arrows"
            assert rule_read.icon_set.reverse is True

    def test_data_bar_extra_attrs_roundtrip_xlsx(self, tmp_path: Path) -> None:
        from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

        wb = WorkbookModel()
        sh = wb.sheets[0]
        sh.set_cell_value(0, 0, 10)
        sh.set_cell_value(1, 0, 100)
        rule = CFRule(
            type=CFRuleType.DATA_BAR.value,
            data_bar=DataBarRule(
                cfvos=[CFVO("min"), CFVO("max")],
                color="#336699",
                min_len=0.0,
                max_len=1.0,
                show_value=False,
            ),
        )
        sh.add_conditional_format(
            ConditionalFormat(sqref="A1:A2", ranges=[(0, 0, 1, 0)], rules=[rule])
        )
        path = tmp_path / "databar_attrs.xlsx"
        write_xlsx(wb, path)
        wb2 = read_xlsx(path)
        db = wb2.sheets[0].conditional_formats[0].rules[0].data_bar
        assert db is not None
        assert db.color == "#336699"
        assert db.min_len == pytest.approx(0.0)
        assert db.max_len == pytest.approx(1.0)
        assert db.show_value is False


# =============================================================================
# 2. Interactive Fixed-Width Ruler + Undoable Text-to-Columns
# =============================================================================


class TestFixedWidthRulerAndTextToColumns:
    """Interactive FixedWidthRulerWidget and undoable TextToColumnsWizard."""

    def test_fixed_width_ruler_click_drag_double_click_and_sync(self, qapp: QApplication) -> None:
        lines = ["Alice  25 Engineer", "Bob    30 Designer", "Carol  35 Manager "]
        dlg = TextToColumnsWizard(sample_texts=lines)
        dlg.radio_fixed.setChecked(True)
        dlg.btn_next.click()
        assert dlg.current_step == 1

        ruler = dlg.ruler_widget
        assert isinstance(ruler, FixedWidthRulerWidget)
        assert ruler.parent() is dlg.grp_fixed
        ruler.resize(520, 220)
        ruler.show()
        qapp.processEvents()

        # Paint ruler offscreen to verify no painting crash
        img = QImage(520, 220, QImage.Format.Format_ARGB32)
        ruler.render(img)
        assert not img.isNull()

        # Clear breaks via edit_breaks -> ruler syncs
        dlg.edit_breaks.setText("")
        assert ruler.breaks == []

        # Typing into edit_breaks updates ruler breaks and preview table
        dlg.edit_breaks.setText("7, 10")
        assert ruler.breaks == [7, 10]
        assert dlg.table_p2.columnCount() == 3
        assert dlg.table_p2.item(0, 0).text() == "Alice"
        assert dlg.table_p2.item(0, 1).text() == "25"
        assert dlg.table_p2.item(0, 2).text() == "Engineer"

        # Click empty offset on ruler -> inserts new break & syncs edit_breaks
        emitted: list[list[int]] = []
        ruler.breaks_changed.connect(emitted.append)

        x_col_4 = ruler._x_for_col(4)
        ruler.mousePressEvent(
            _mouse_event(
                QEvent.Type.MouseButtonPress,
                QPointF(x_col_4, 40.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
            )
        )
        ruler.mouseReleaseEvent(
            _mouse_event(
                QEvent.Type.MouseButtonRelease,
                QPointF(x_col_4, 40.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
            )
        )
        assert 4 in ruler.breaks
        assert emitted and 4 in emitted[-1]
        assert dlg.get_fixed_breaks() == [4, 7, 10]

        # Drag break from col 4 -> col 5
        x_col_5 = ruler._x_for_col(5)
        ruler.mousePressEvent(
            _mouse_event(
                QEvent.Type.MouseButtonPress,
                QPointF(x_col_4, 40.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
            )
        )
        ruler.mouseMoveEvent(
            _mouse_event(
                QEvent.Type.MouseMove,
                QPointF(x_col_5, 40.0),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
            )
        )
        ruler.mouseReleaseEvent(
            _mouse_event(
                QEvent.Type.MouseButtonRelease,
                QPointF(x_col_5, 40.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
            )
        )
        assert 4 not in ruler.breaks
        assert 5 in ruler.breaks
        assert dlg.get_fixed_breaks() == [5, 7, 10]

        # Double-click break at col 5 -> removes it
        ruler.mouseDoubleClickEvent(
            _mouse_event(
                QEvent.Type.MouseButtonDblClick,
                QPointF(x_col_5, 40.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
            )
        )
        assert 5 not in ruler.breaks
        assert dlg.get_fixed_breaks() == [7, 10]

        ruler.retranslate_ui()
        dlg.retranslate_ui()
        dlg.close()

    def test_open_text_to_columns_wizard_undo_redo(self, ledger_win: LedgerWindow) -> None:
        sheet = ledger_win.spreadsheet_view.model
        sheet.set_cell_value(0, 0, "Alice  25 Engineer")
        sheet.set_cell_value(1, 0, "Bob    30 Designer")
        _select_range(ledger_win, 0, 0, 1, 0)

        def fake_exec(dlg: TextToColumnsWizard) -> int:
            dlg.radio_fixed.setChecked(True)
            dlg.btn_next.click()
            dlg.edit_breaks.setText("7, 10")
            dlg.btn_next.click()
            dlg.btn_finish.click()
            return QDialog.DialogCode.Accepted

        with patch.object(TextToColumnsWizard, "exec", fake_exec):
            ledger_win.action_registry.trigger_action("textToColumns")

        assert sheet.get_cell_value(0, 0) == "Alice"
        assert sheet.get_cell_value(0, 1) == 25
        assert sheet.get_cell_value(0, 2) == "Engineer"
        assert sheet.get_cell_value(1, 0) == "Bob"
        assert sheet.get_cell_value(1, 1) == 30
        assert sheet.get_cell_value(1, 2) == "Designer"

        # Undo restores original single-column text
        ledger_win.undo()
        assert sheet.get_cell_value(0, 0) == "Alice  25 Engineer"
        assert sheet.get_cell_value(0, 1) is None
        assert sheet.get_cell_value(0, 2) is None

        # Redo re-applies split columns
        ledger_win.redo()
        assert sheet.get_cell_value(0, 0) == "Alice"
        assert sheet.get_cell_value(0, 1) == 25
        assert sheet.get_cell_value(0, 2) == "Engineer"


# =============================================================================
# 3. PivotChart Creation, Undo/Redo, Live Auto-Sync, and XLSX Round-Trip
# =============================================================================


def _populate_sales_sheet(win: LedgerWindow) -> None:
    wb = win.workbook
    src = wb.sheets[0]
    src.name = "SalesData"
    rows = [
        ["Region", "Quarter", "Sales"],
        ["East", "Q1", 100],
        ["East", "Q2", 200],
        ["West", "Q1", 150],
        ["West", "Q2", 250],
    ]
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            src.set_cell_value(r, c, v)


class TestPivotChartAndLiveSync:
    """PivotChart creation, undo/redo, live refresh/pane auto-sync, and XLSX persistence."""

    def test_pivot_chart_create_undo_sync_and_xlsx(
        self, ledger_win: LedgerWindow, tmp_path: Path
    ) -> None:
        _populate_sales_sheet(ledger_win)
        wb = ledger_win.workbook
        layout = PivotLayoutSpec(
            source_sheet="SalesData",
            source_range=(0, 0, 4, 2),
            rows=[PivotFieldSpec(col_idx=0, name="Region")],
            columns=[PivotFieldSpec(col_idx=1, name="Quarter")],
            values=[PivotValueSpec(col_idx=2, name="Sales", agg_func="sum")],
            target_sheet="PivotSheet",
            target_cell=(0, 0),
            name="SalesPivot",
        )
        report = build_interactive_pivot(wb, layout)
        pivot_sheet = wb.get_sheet_by_name("PivotSheet")
        assert pivot_sheet is not None

        idx = wb.sheet_index(pivot_sheet)
        ledger_win.spreadsheet_view.set_active_sheet_index(idx)
        _select_range(ledger_win, report.bbox[0], report.bbox[1], report.bbox[0], report.bbox[1])

        # Context menu on PivotTable includes PivotChart action
        grid = ledger_win.spreadsheet_view.grid
        menu = grid._build_cell_menu(report.bbox[0], report.bbox[1])
        menu_texts = [a.text() for a in menu.actions()]
        assert any("数据透视图" in t for t in menu_texts)

        # Trigger insertPivotChart via ActionRegistry
        assert ledger_win.action_registry.has_command("insertPivotChart")
        ledger_win.action_registry.trigger_action("insertPivotChart")

        assert len(pivot_sheet.drawings) == 1
        chart_obj = pivot_sheet.drawings[0]
        assert chart_obj.kind == "chart"
        assert chart_obj.chart_data is not None
        assert chart_obj.chart_data["pivot_id"] == report.id
        assert chart_obj.chart_data["cats"] == ["East", "West"]
        series_map = {s["name"]: s["vals"] for s in chart_obj.chart_data["series"]}
        assert series_map == {"Q1": [100.0, 150.0], "Q2": [200.0, 250.0]}

        # Undo removes chart; Redo restores it
        ledger_win.undo()
        assert len(pivot_sheet.drawings) == 0

        ledger_win.redo()
        assert len(pivot_sheet.drawings) == 1
        restored_chart = pivot_sheet.drawings[0]
        assert restored_chart.chart_data["pivot_id"] == report.id

        # Mutate source data and refresh PivotTable -> linked PivotChart auto-syncs
        wb.get_sheet_by_name("SalesData").set_cell_value(1, 2, 999)  # East Q1: 100 -> 999
        assert grid.refresh_pivot_table(report) is True

        updated_map = {s["name"]: s["vals"] for s in restored_chart.chart_data["series"]}
        assert updated_map["Q1"] == [999.0, 150.0]

        # Change PivotTable layout via PivotFieldsTaskPane -> linked PivotChart auto-syncs
        ledger_win.open_pivot_fields_pane(report)
        pane = ledger_win.pivot_fields_pane
        assert hasattr(pane, "btn_pivot_chart")
        # Change chart type to line, then update layout -> kind="line" must be preserved
        ledger_win.spreadsheet_view.object_layer.select_object(restored_chart)
        ledger_win.set_chart_type("line")
        assert restored_chart.chart_data["kind"] == "line"
        # Remove Quarter from columns -> chart should collapse to 1 total series
        pane.remove_field_from_zone(1, "columns")
        assert restored_chart.chart_data["kind"] == "line"
        assert len(restored_chart.chart_data["series"]) == 1
        assert restored_chart.chart_data["series"][0]["vals"] == [1199.0, 400.0]

        # Clicking PivotFieldsTaskPane's Insert PivotChart button also creates a chart
        pane.btn_pivot_chart.click()
        assert len(pivot_sheet.drawings) == 2
        assert pivot_sheet.drawings[1].chart_data["pivot_id"] == report.id
        ledger_win.undo()
        assert len(pivot_sheet.drawings) == 1

        # Save to XLSX and reopen -> chart is preserved
        out_path = tmp_path / "pivot_chart.xlsx"
        write_xlsx(wb, out_path)
        wb_read = read_xlsx(out_path)
        sh_read = wb_read.get_sheet_by_name("PivotSheet")
        assert sh_read is not None
        assert len(sh_read.drawings) == 1
        c_read = sh_read.drawings[0]
        assert c_read.kind == "chart"
        assert c_read.chart_data is not None
        assert c_read.chart_data["cats"] == ["East", "West"]
        assert c_read.chart_data["series"][0]["vals"] == [1199.0, 400.0]
