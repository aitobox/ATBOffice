"""Interactive GUI & calculation tests for Phase 9 PivotTable enhancements (Issue #340).

Covers:
1. Multi-dimensional pivot calculation engine (src/atboffice/modules/spreadsheet/calc/pivots.py):
   - Aggregations: SUM, COUNT, AVERAGE, MAX, MIN, PRODUCT, COUNTNUMS
   - Multi-level Row Labels with automatic subtotals
   - Multi-level Column Labels and multiple Value fields
   - Report Filters and clearing stale output cells on refresh
2. PivotFieldsTaskPane (src/atboffice/modules/spreadsheet/panes/pivot_fields_pane.py):
   - Field list checkboxes (smart routing numeric -> Values, text -> Rows, uncheck -> remove)
   - 4 drop zones (Filters, Columns, Rows, Values) and drag-and-drop MIME handling
   - Value aggregation switching & Defer Layout Update
   - i18n / retranslate_ui
3. GridViewport dynamic pivot rendering & context menu (views/grid_viewport.py):
   - pivot_table_at detection
   - Dynamic paint of headers, banded rows, subtotals, grand totals, and filter dropdowns
   - "Refresh Data" & "Show Field List" context menu entries and live refresh
4. LedgerWindow integration
"""

from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QMimeData, QPoint, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def create_multi_dim_sales_workbook() -> WorkbookModel:
    """Create a multi-dimensional sales dataset for pivot testing."""
    wb = WorkbookModel()
    sheet = wb[0]
    sheet.name = "SalesData"

    rows = [
        ["Region", "Category", "Product", "Quarter", "Units", "Sales"],
        ["East", "Tech", "Widget", "Q1", 2, 100],
        ["East", "Tech", "Gadget", "Q1", 4, 200],
        ["East", "Office", "Paper", "Q2", 5, 50],
        ["West", "Tech", "Widget", "Q1", 3, 150],
        ["West", "Tech", "Gadget", "Q2", 6, 300],
        ["North", "Office", "Paper", "Q2", 10, 120],
        ["North", "Tech", "Widget", "Q1", 2, 180],
    ]
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            sheet.set_cell_value(r, c, val)
    return wb


class TestPhase9PivotCalculationEngine:
    """Tests for multi-dimensional pivot calculation engine in calc/pivots.py."""

    def test_aggregations_including_product(self) -> None:
        from atboffice.modules.spreadsheet.calc.pivots import aggregate_values

        vals = [2, 3, 4, "ignored", None]
        assert aggregate_values(vals, "sum") == 9.0
        assert aggregate_values(vals, "count") == 4  # 2, 3, 4, "ignored"
        assert aggregate_values(vals, "countNums") == 3
        assert aggregate_values(vals, "average") == 3.0
        assert aggregate_values(vals, "max") == 4.0
        assert aggregate_values(vals, "min") == 2.0
        assert aggregate_values(vals, "product") == 24.0
        assert aggregate_values(["text"], "average") == "#DIV/0!"
        assert aggregate_values(["text"], "product") == 0

    def test_multi_level_rows_with_subtotals_and_grand_totals(self) -> None:
        from atboffice.modules.spreadsheet.calc.pivots import (
            PivotFieldSpec,
            PivotLayoutSpec,
            PivotValueSpec,
            build_interactive_pivot,
        )

        wb = create_multi_dim_sales_workbook()
        layout = PivotLayoutSpec(
            source_sheet="SalesData",
            source_range=(0, 0, 7, 5),
            rows=[
                PivotFieldSpec(col_idx=0, name="Region"),
                PivotFieldSpec(col_idx=1, name="Category"),
            ],
            columns=[PivotFieldSpec(col_idx=3, name="Quarter")],
            values=[PivotValueSpec(col_idx=5, name="Sales", agg_func="sum")],
            target_sheet="PivotMultiRow",
            target_cell=(0, 0),
        )
        report = build_interactive_pivot(wb, layout)
        dst = wb.get_sheet_by_name("PivotMultiRow")
        assert dst is not None
        assert report in dst.pivot_reports

        # Collect row texts to verify subtotals and grand total
        r0, c0, r2, c2 = report.bbox
        col0_vals = [dst.get_cell_value(r, c0) for r in range(r0, r2 + 1)]
        assert "East Total" in col0_vals
        assert "North Total" in col0_vals
        assert "West Total" in col0_vals
        assert "Grand Total" in col0_vals

        # Verify subtotal row metadata and values
        assert len(report.meta.subtotal_rows) == 3
        assert len(report.meta.grand_total_rows) == 1

        east_sub_r = next(
            r for r in report.meta.subtotal_rows if dst.get_cell_value(r, c0) == "East Total"
        )
        # East Q1 = 100+200=300, East Q2 = 50, Total = 350
        assert dst.get_cell_value(east_sub_r, c0 + 2) == 300.0
        assert dst.get_cell_value(east_sub_r, c0 + 3) == 50.0
        assert dst.get_cell_value(east_sub_r, c0 + 4) == 350.0

        # Grand Total: Q1 = 100+200+150+180 = 630, Q2 = 50+300+120 = 470, Grand = 1100
        gt_r = next(iter(report.meta.grand_total_rows))
        assert dst.get_cell_value(gt_r, c0 + 2) == 630.0
        assert dst.get_cell_value(gt_r, c0 + 3) == 470.0
        assert dst.get_cell_value(gt_r, c0 + 4) == 1100.0

    def test_multiple_values_and_product_aggregation(self) -> None:
        from atboffice.modules.spreadsheet.calc.pivots import (
            PivotFieldSpec,
            PivotLayoutSpec,
            PivotValueSpec,
            build_interactive_pivot,
        )

        wb = create_multi_dim_sales_workbook()
        layout = PivotLayoutSpec(
            source_sheet="SalesData",
            source_range=(0, 0, 7, 5),
            rows=[PivotFieldSpec(col_idx=0, name="Region")],
            columns=[],
            values=[
                PivotValueSpec(col_idx=5, name="Sales", agg_func="sum"),
                PivotValueSpec(col_idx=4, name="Units", agg_func="product"),
            ],
            target_sheet="MultiVals",
            target_cell=(0, 0),
        )
        report = build_interactive_pivot(wb, layout)
        dst = wb.get_sheet_by_name("MultiVals")
        assert dst is not None

        hr = max(report.meta.header_rows)
        assert dst.get_cell_value(hr, 0) == "Region"
        assert dst.get_cell_value(hr, 1) == "Sum of Sales"
        assert dst.get_cell_value(hr, 2) == "Product of Units"

        # East Units: 2 * 4 * 5 = 40.0
        east_r = next(r for r in report.meta.data_rows if dst.get_cell_value(r, 0) == "East")
        assert dst.get_cell_value(east_r, 1) == 350.0
        assert dst.get_cell_value(east_r, 2) == 40.0

    def test_report_filter_and_refresh_clears_stale_cells(self) -> None:
        from atboffice.modules.spreadsheet.calc.pivots import (
            PivotFieldSpec,
            PivotLayoutSpec,
            PivotValueSpec,
            build_interactive_pivot,
            refresh_pivot_report,
        )

        wb = create_multi_dim_sales_workbook()
        layout = PivotLayoutSpec(
            source_sheet="SalesData",
            source_range=(0, 0, 7, 5),
            filters=[PivotFieldSpec(col_idx=3, name="Quarter", selected_values=None)],
            rows=[PivotFieldSpec(col_idx=0, name="Region")],
            columns=[PivotFieldSpec(col_idx=1, name="Category")],
            values=[PivotValueSpec(col_idx=5, name="Sales", agg_func="sum")],
            target_sheet="FilteredPivot",
            target_cell=(0, 0),
        )
        report = build_interactive_pivot(wb, layout)
        dst = wb.get_sheet_by_name("FilteredPivot")
        assert dst is not None
        old_bbox = report.bbox

        # Verify filter row is recorded
        assert 0 in report.meta.filter_rows
        assert dst.get_cell_value(0, 0) == "Quarter"
        assert dst.get_cell_value(0, 1) == "(All)"
        assert (0, 1) in report.meta.filter_dropdown_cells

        # Apply filter Quarter = {"Q1"} -> Office category disappears completely
        report.layout.filters[0].selected_values = {"Q1"}
        assert refresh_pivot_report(wb, report) is True

        new_bbox = report.bbox
        assert dst.get_cell_value(0, 1) == "Q1"
        # Column count shrank (Office disappeared); stale right-hand cells must be cleared
        assert new_bbox[3] < old_bbox[3]
        for r in range(old_bbox[0], old_bbox[2] + 1):
            for c in range(new_bbox[3] + 1, old_bbox[3] + 1):
                assert dst.get_cell_value(r, c) is None

        # Modify source data (SalesData row 1: East Tech Widget Q1 Sales 100 -> 500)
        wb.get_sheet_by_name("SalesData").set_cell_value(1, 5, 500)
        assert refresh_pivot_report(wb, report) is True
        gt_r = next(iter(report.meta.grand_total_rows))
        # Q1 Sales: East 500+200=700, North 180, West 150 -> Grand = 1030
        assert dst.get_cell_value(gt_r, new_bbox[3]) == 1030.0


class TestPhase9PivotFieldsTaskPane:
    """Interactive tests for PivotFieldsTaskPane with 4 drop zones & drag-drop."""

    def test_pane_binding_checkbox_smart_routing_and_uncheck(
        self, qapp: QApplication
    ) -> None:
        from atboffice.modules.spreadsheet.calc.pivots import (
            PivotFieldSpec,
            PivotLayoutSpec,
            PivotValueSpec,
            build_interactive_pivot,
        )
        from atboffice.modules.spreadsheet.panes.pivot_fields_pane import (
            PivotFieldsTaskPane,
        )

        wb = create_multi_dim_sales_workbook()
        layout = PivotLayoutSpec(
            source_sheet="SalesData",
            source_range=(0, 0, 7, 5),
            rows=[PivotFieldSpec(col_idx=0, name="Region")],
            values=[PivotValueSpec(col_idx=5, name="Sales", agg_func="sum")],
            target_sheet="PanePivot",
            target_cell=(0, 0),
        )
        report = build_interactive_pivot(wb, layout)

        pane = PivotFieldsTaskPane(workbook=wb)
        pane.bind_pivot_report(report, wb)

        # All 6 source fields appear in top field_list
        assert pane.field_list.count() == 6
        assert pane.field_list.item(0).text() == "Region"
        assert pane.field_list.item(0).checkState() == Qt.CheckState.Checked
        assert pane.field_list.item(1).checkState() == Qt.CheckState.Unchecked  # Category
        assert pane.field_list.item(5).checkState() == Qt.CheckState.Checked  # Sales

        # Verify 4 drop zones exist and reflect initial layout
        assert pane.zone_rows.count() == 1
        assert pane.zone_values.count() == 1
        assert pane.zone_columns.count() == 0
        assert pane.zone_filters.count() == 0

        # Check Category (text field, row 1) -> smart-routed to Rows and live-recalculated
        pane.field_list.item(1).setCheckState(Qt.CheckState.Checked)
        assert pane.zone_rows.count() == 2
        assert len(report.layout.rows) == 2
        assert len(report.meta.subtotal_rows) == 3  # East/North/West subtotals appear!

        # Check Units (numeric field, row 4) -> smart-routed to Values
        pane.field_list.item(4).setCheckState(Qt.CheckState.Checked)
        assert pane.zone_values.count() == 2
        assert len(report.layout.values) == 2

        # Uncheck Region (row 0) -> removed from Rows
        pane.field_list.item(0).setCheckState(Qt.CheckState.Unchecked)
        assert pane.zone_rows.count() == 1
        assert [f.name for f in report.layout.rows] == ["Category"]

    def test_drag_and_drop_between_zones_and_aggregation_change(
        self, qapp: QApplication
    ) -> None:
        from atboffice.modules.spreadsheet.calc.pivots import (
            PivotFieldSpec,
            PivotLayoutSpec,
            PivotValueSpec,
            build_interactive_pivot,
        )
        from atboffice.modules.spreadsheet.panes.pivot_fields_pane import (
            PIVOT_FIELD_MIME,
            PivotFieldsTaskPane,
        )

        wb = create_multi_dim_sales_workbook()
        layout = PivotLayoutSpec(
            source_sheet="SalesData",
            source_range=(0, 0, 7, 5),
            rows=[PivotFieldSpec(col_idx=0, name="Region")],
            values=[PivotValueSpec(col_idx=5, name="Sales", agg_func="sum")],
            target_sheet="DragPivot",
            target_cell=(0, 0),
        )
        report = build_interactive_pivot(wb, layout)
        pane = PivotFieldsTaskPane(workbook=wb)
        pane.bind_pivot_report(report, wb)

        # Simulate MIME drop of "Quarter" (col_idx=3) from field list into Columns zone
        mime = QMimeData()
        mime.setData(
            PIVOT_FIELD_MIME,
            json.dumps(
                {
                    "col_idx": 3,
                    "name": "Quarter",
                    "source_zone": None,
                    "source_index": -1,
                    "agg_func": None,
                }
            ).encode("utf-8"),
        )
        drop_ev = QDropEvent(
            QPoint(10, 10),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        pane.zone_columns.dropEvent(drop_ev)

        assert pane.zone_columns.count() == 1
        assert [f.name for f in report.layout.columns] == ["Quarter"]
        assert pane.field_list.item(3).checkState() == Qt.CheckState.Checked

        # Simulate MIME drag from Columns ("Quarter") to Filters
        mime2 = QMimeData()
        mime2.setData(
            PIVOT_FIELD_MIME,
            json.dumps(
                {
                    "col_idx": 3,
                    "name": "Quarter",
                    "source_zone": "columns",
                    "source_index": 0,
                    "agg_func": None,
                }
            ).encode("utf-8"),
        )
        drop_ev2 = QDropEvent(
            QPoint(10, 10),
            Qt.DropAction.MoveAction,
            mime2,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        pane.zone_filters.dropEvent(drop_ev2)

        assert pane.zone_columns.count() == 0
        assert pane.zone_filters.count() == 1
        assert [f.name for f in report.layout.filters] == ["Quarter"]
        assert len(report.meta.filter_rows) == 1

        # Change Value aggregation to PRODUCT
        pane.set_value_aggregation(0, "product")
        assert report.layout.values[0].agg_func == "product"
        dst = wb.get_sheet_by_name("DragPivot")
        assert dst is not None
        east_r = next(r for r in report.meta.data_rows if dst.get_cell_value(r, 0) == "East")
        # East Sales: 100 * 200 * 50 = 1,000,000.0
        assert dst.get_cell_value(east_r, 1) == 1000000.0

    def test_defer_layout_update_and_retranslate_ui(
        self, qapp: QApplication
    ) -> None:
        from atboffice.modules.spreadsheet.calc.pivots import (
            PivotFieldSpec,
            PivotLayoutSpec,
            PivotValueSpec,
            build_interactive_pivot,
        )
        from atboffice.modules.spreadsheet.panes.pivot_fields_pane import (
            PivotFieldsTaskPane,
        )

        wb = create_multi_dim_sales_workbook()
        layout = PivotLayoutSpec(
            source_sheet="SalesData",
            source_range=(0, 0, 7, 5),
            rows=[PivotFieldSpec(col_idx=0, name="Region")],
            values=[PivotValueSpec(col_idx=5, name="Sales", agg_func="sum")],
            target_sheet="DeferPivot",
            target_cell=(0, 0),
        )
        report = build_interactive_pivot(wb, layout)
        pane = PivotFieldsTaskPane(workbook=wb)
        pane.bind_pivot_report(report, wb)

        # Enable defer update
        pane.chk_defer.setChecked(True)
        pane.add_field_to_zone(col_idx=3, zone="columns")
        # Layout in UI updated, but report not yet recalculated
        assert pane.zone_columns.count() == 1
        assert len(report.layout.columns) == 0

        # Click Update button -> applies deferred layout
        pane.btn_update.click()
        assert len(report.layout.columns) == 1
        assert report.layout.columns[0].name == "Quarter"

        # Verify retranslate_ui executes cleanly
        pane.retranslate_ui()


class TestPhase9GridViewportPivotRenderingAndMenu:
    """Interactive GUI tests for GridViewport pivot rendering, dropdowns, and context menu."""

    def test_pivot_detection_context_menu_and_refresh_data(
        self, qapp: QApplication
    ) -> None:
        from atboffice.modules.spreadsheet.calc.pivots import (
            PivotFieldSpec,
            PivotLayoutSpec,
            PivotValueSpec,
            build_interactive_pivot,
        )
        from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport

        wb = create_multi_dim_sales_workbook()
        layout = PivotLayoutSpec(
            source_sheet="SalesData",
            source_range=(0, 0, 7, 5),
            filters=[PivotFieldSpec(col_idx=3, name="Quarter")],
            rows=[PivotFieldSpec(col_idx=0, name="Region")],
            columns=[PivotFieldSpec(col_idx=1, name="Category")],
            values=[PivotValueSpec(col_idx=5, name="Sales", agg_func="sum")],
            target_sheet="GridPivot",
            target_cell=(1, 1),
        )
        report = build_interactive_pivot(wb, layout)
        dst = wb.get_sheet_by_name("GridPivot")
        assert dst is not None

        vp = GridViewport(model=dst)
        vp.workbook = wb
        vp.resize(900, 600)

        # Detection inside vs outside pivot bbox
        r0, c0, r2, c2 = report.bbox
        assert vp.pivot_table_at(r0, c0) is report
        assert vp.pivot_table_at(r2, c2) is report
        assert vp.pivot_table_at(0, 0) is None
        assert vp.pivot_table_at(r2 + 5, c2 + 5) is None

        # Context menu inside pivot includes Refresh Data & Show Field List
        menu_inside = vp._build_cell_menu(r0 + 2, c0)
        texts_inside = [a.text() for a in menu_inside.actions() if not a.isSeparator()]
        assert any("刷新数据" in t for t in texts_inside)
        assert any("字段列表" in t for t in texts_inside)

        # Context menu outside pivot does NOT include Pivot actions
        menu_outside = vp._build_cell_menu(r2 + 5, c2 + 5)
        texts_outside = [a.text() for a in menu_outside.actions() if not a.isSeparator()]
        assert not any("刷新数据" in t for t in texts_outside)

        # Modify source data and invoke Refresh Data
        wb.get_sheet_by_name("SalesData").set_cell_value(1, 5, 1100)  # +1000
        vp.selection.set_active_cell(r0 + 3, c0 + 1)
        assert vp.refresh_pivot_table() is True
        gt_r = next(iter(report.meta.grand_total_rows))
        # Old grand total was 1100, +1000 = 2100
        assert dst.get_cell_value(gt_r, report.bbox[3]) == 2100.0
        assert vp.last_status_message != ""

    def test_grid_viewport_dynamic_paint_and_filter_dropdown_hit(
        self, qapp: QApplication
    ) -> None:
        from atboffice.modules.spreadsheet.calc.pivots import (
            PivotFieldSpec,
            PivotLayoutSpec,
            PivotValueSpec,
            build_interactive_pivot,
        )
        from atboffice.modules.spreadsheet.views.grid_viewport import (
            GridViewport,
            HitZone,
        )

        wb = create_multi_dim_sales_workbook()
        layout = PivotLayoutSpec(
            source_sheet="SalesData",
            source_range=(0, 0, 7, 5),
            filters=[PivotFieldSpec(col_idx=3, name="Quarter")],
            rows=[
                PivotFieldSpec(col_idx=0, name="Region"),
                PivotFieldSpec(col_idx=1, name="Category"),
            ],
            values=[PivotValueSpec(col_idx=5, name="Sales", agg_func="sum")],
            target_sheet="PaintPivot",
            target_cell=(0, 0),
        )
        report = build_interactive_pivot(wb, layout)
        dst = wb.get_sheet_by_name("PaintPivot")
        assert dst is not None

        vp = GridViewport(model=dst)
        vp.workbook = wb
        vp.resize(900, 600)
        vp.selection.set_active_cell(report.bbox[0], report.bbox[1])

        # Verify dynamic paint renders cleanly without errors
        pixmap = vp.grab()
        assert not pixmap.isNull()
        assert pixmap.width() > 0 and pixmap.height() > 0

        # Verify hit_test detects PIVOT_FILTER_BUTTON on the filter dropdown cell (0, 1)
        flt_rect = vp.cell_rect(0, 1)
        btn_x = flt_rect.right() - 4
        btn_y = flt_rect.bottom() - 4
        hit = vp.hit_test(btn_x, btn_y)
        assert hit.zone == HitZone.PIVOT_FILTER_BUTTON
        assert hit.row == 0 and hit.col == 1

        # Verify filter application via _apply_pivot_field_filter
        vp._apply_pivot_field_filter(report, col_idx=3, selected_values={"Q1"})
        assert dst.get_cell_value(0, 1) == "Q1"
        gt_r = next(iter(report.meta.grand_total_rows))
        assert dst.get_cell_value(gt_r, report.bbox[3]) == 630.0


class TestPhase9LedgerWindowPivotIntegration:
    """End-to-end LedgerWindow integration tests for PivotTable pane and wizard."""

    def test_ledger_window_registers_pivot_fields_pane_and_live_updates(
        self, qapp: QApplication
    ) -> None:
        from atboffice.modules.spreadsheet.calc.pivots import (
            PivotFieldSpec,
            PivotLayoutSpec,
            PivotValueSpec,
            build_interactive_pivot,
        )
        from atboffice.modules.spreadsheet.panes.pivot_fields_pane import (
            PivotFieldsTaskPane,
        )
        from atboffice.ui.shell.ledger_window import LedgerWindow

        win = LedgerWindow()
        try:
            # 1. Verify PivotFieldsTaskPane is registered in TaskPaneDock
            assert hasattr(win, "pivot_fields_pane")
            assert isinstance(win.pivot_fields_pane, PivotFieldsTaskPane)
            assert win.task_pane_dock.get_pane("pivot_fields") is win.pivot_fields_pane

            # 2. Populate workbook and build an interactive pivot report
            wb = win.workbook
            src = wb[0]
            src.name = "SalesData"
            sample_rows = [
                ["Region", "Product", "Quarter", "Sales"],
                ["East", "Widget", "Q1", 100],
                ["East", "Gadget", "Q1", 200],
                ["West", "Widget", "Q2", 150],
            ]
            for r, row in enumerate(sample_rows):
                for c, val in enumerate(row):
                    src.set_cell_value(r, c, val)

            layout = PivotLayoutSpec(
                source_sheet="SalesData",
                source_range=(0, 0, 3, 3),
                rows=[PivotFieldSpec(col_idx=0, name="Region")],
                values=[PivotValueSpec(col_idx=3, name="Sales", agg_func="sum")],
                target_sheet="new",
            )
            report = build_interactive_pivot(wb, layout)
            win.open_pivot_fields_pane(report)

            # 3. Verify pane is active & bound
            assert win.task_pane_dock.current_pane_id() == "pivot_fields"
            assert win.pivot_fields_pane.zone_rows.count() == 1
            assert win.pivot_fields_pane.zone_values.count() == 1

            # 4. Add Column field via pane and verify live update on worksheet
            win.pivot_fields_pane.add_field_to_zone(col_idx=1, zone="columns")
            assert len(report.layout.columns) == 1
            dst = wb.get_sheet_by_name(report.sheet_name)
            assert dst is not None
            gt_r = next(iter(report.meta.grand_total_rows))
            assert dst.get_cell_value(gt_r, report.bbox[3]) == 450.0

            # 5. Retranslate UI runs cleanly
            win.retranslate_ui()

            # 6. Switching to a new workbook clears stale PivotFieldsTaskPane binding
            win.new_file()
            assert win.pivot_fields_pane.field_list.count() == 0
            assert win.pivot_fields_pane.zone_rows.count() == 0
        finally:
            win.close()

    def test_wizard_dialog_product_and_header_only_edge_cases(
        self, qapp: QApplication
    ) -> None:
        from atboffice.modules.spreadsheet.calc.pivots import (
            PivotFieldSpec,
            PivotLayoutSpec,
            PivotValueSpec,
            build_interactive_pivot,
        )
        from atboffice.modules.spreadsheet.dialogs.pivot_dialog import (
            PivotTableWizardDialog,
        )

        wb = create_multi_dim_sales_workbook()
        dlg = PivotTableWizardDialog(
            workbook=wb,
            initial_sheet_name="SalesData",
            initial_range=(0, 0, 7, 5),
        )
        # Verify "product" aggregation is offered in Wizard
        fn_codes = [dlg.combo_fn.itemData(i) for i in range(dlg.combo_fn.count())]
        assert "product" in fn_codes
        prod_idx = fn_codes.index("product")
        dlg.combo_fn.setCurrentIndex(prod_idx)
        dlg.combo_data.setCurrentIndex(4)  # Units
        dlg._on_finish()
        assert dlg.created_report is not None
        assert dlg.created_report in dlg.created_sheet.pivot_reports

        # Header-only edge case (r1 == r2): should render cleanly without error
        empty_wb = WorkbookModel()
        s = empty_wb[0]
        s.name = "HeaderOnly"
        s.set_cell_value(0, 0, "Region")
        s.set_cell_value(0, 1, "Sales")
        rep = build_interactive_pivot(
            empty_wb,
            PivotLayoutSpec(
                source_sheet="HeaderOnly",
                source_range=(0, 0, 0, 1),
                rows=[PivotFieldSpec(col_idx=0, name="Region")],
                values=[PivotValueSpec(col_idx=1, name="Sales", agg_func="sum")],
                target_sheet="EmptyPivot",
                target_cell=(0, 0),
            ),
        )
        assert rep.bbox[0] == 0 and rep.bbox[1] == 0
        assert len(rep.meta.data_rows) == 0

        # Multi-level columns (Category, Quarter)
        multi_col_rep = build_interactive_pivot(
            wb,
            PivotLayoutSpec(
                source_sheet="SalesData",
                source_range=(0, 0, 7, 5),
                rows=[PivotFieldSpec(col_idx=0, name="Region")],
                columns=[
                    PivotFieldSpec(col_idx=1, name="Category"),
                    PivotFieldSpec(col_idx=3, name="Quarter"),
                ],
                values=[PivotValueSpec(col_idx=5, name="Sales", agg_func="average")],
                target_sheet="MultiColPivot",
                target_cell=(0, 0),
            ),
        )
        assert len(multi_col_rep.meta.header_rows) == 3
        assert len(multi_col_rep.meta.grand_total_cols) == 1


