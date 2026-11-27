"""Data commands of the spreadsheet grid: filters, sort, tables, pivots, charts, lists."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import (
    QPoint,
)
from PySide6.QtWidgets import (
    QMenu,
)

from atboffice.core.i18n import safe_tr

if TYPE_CHECKING:
    pass


class GridDataMixin:
    """AutoFilter, sort, tables, PivotTables, charts and validation drop-downs."""

    def _open_dv_dropdown(self) -> None:
        """Open the List Data Validation dropdown popup for the active cell."""
        ar, ac = self.selection.active_cell
        dv = self.model.get_validation_at(ar, ac)
        if dv is None or dv.type != "list":
            return
        from atboffice.modules.spreadsheet.models.validation import get_list_items

        items = get_list_items(self.model, dv, ar, ac)
        if not items:
            return

        menu = QMenu(self)
        for item in items:
            action = menu.addAction(str(item))

            def on_triggered(checked: bool = False, val=item) -> None:
                self.model.set_cell_value(ar, ac, val)
                if (
                    self.editor_controller is not None
                    and self.editor_controller.formula_bar is not None
                ):
                    self.editor_controller.formula_bar.set_cell_value(val)
                self.viewport().update()

            action.triggered.connect(on_triggered)

        if self._dv_dropdown_rect is not None:
            pt = self._global_pos(self._dv_dropdown_rect.bottomLeft())
            menu.exec(pt)

    def table_at(self, r: int, c: int) -> Any | None:
        """Check if cell (r, c) is part of a list/table."""
        for t in getattr(self.model, "tables", []):
            if hasattr(t, "range"):
                r1, c1, r2, c2 = t.range
            elif isinstance(t, dict):
                r1, c1 = t.get("r1", 0), t.get("c1", 0)
                r2, c2 = t.get("r2", 0), t.get("c2", 0)
            else:
                continue
            if r1 <= r <= r2 and c1 <= c <= c2:
                return t

        af = getattr(self.model, "auto_filter", None)
        if af is not None:
            r1, c1 = getattr(af, "min_r", 0), getattr(af, "min_c", 0)
            r2, c2 = getattr(af, "max_r", 0), getattr(af, "max_c", 0)
            if r1 <= r <= r2 and c1 <= c <= c2:
                return af

        win = self.window()
        if getattr(win, "_total_row_active", False):
            total_r = getattr(win, "_total_row_r", None)
            c1, c2 = getattr(win, "_total_row_cols", (0, 0))
            if total_r is not None and r <= total_r and c1 <= c <= c2:
                return {"r1": 0, "c1": c1, "r2": total_r, "c2": c2}

        return None

    def create_list(self) -> None:
        """Create a list/table from current selection."""
        pr = self.selection.primary_range
        if not hasattr(self.model, "tables"):
            self.model.tables = []
        table_info = {
            "name": f"Table{len(self.model.tables) + 1}",
            "r1": pr.min_r,
            "c1": pr.min_c,
            "r2": pr.max_r,
            "c2": pr.max_c,
            "has_headers": True,
            "totalRow": False,
        }
        self.model.tables.append(table_info)
        self.toggle_auto_filter()
        self.mark_dirty()
        self.viewport().update()

    def toggle_total_row(self, target_table: dict | None = None) -> None:
        """Toggle total row on the active table/list."""
        win = self.window()
        if win is not self and hasattr(win, "toggle_total_row"):
            win.toggle_total_row()
        active_pos = self.selection.active_cell
        tbl = target_table or (self.table_at(*active_pos) if hasattr(self, "table_at") else None)
        if tbl is not None:
            tbl["totalRow"] = not tbl.get("totalRow", False)
        self.mark_dirty()
        self.viewport().update()

    def convert_table_to_range(self, target_table: dict | None = None) -> None:
        """Convert list/table back to normal range."""
        win = self.window()
        if win is not self and hasattr(win, "convert_table_to_range"):
            win.convert_table_to_range()
        if hasattr(self.model, "tables"):
            if target_table is not None and target_table in self.model.tables:
                self.model.tables.remove(target_table)
            else:
                pr = self.selection.primary_range
                self.model.tables = [
                    t
                    for t in self.model.tables
                    if not (
                        t.get("r1", 0) <= pr.min_r
                        and t.get("r2", 0) >= pr.max_r
                        and t.get("c1", 0) <= pr.min_c
                        and t.get("c2", 0) >= pr.max_c
                    )
                ]
        self.mark_dirty()
        self.viewport().update()

    def _resolve_workbook(self) -> Any | None:
        """Resolve owning WorkbookModel from self, parent SpreadsheetView, or window."""
        wb = getattr(self, "workbook", None)
        if wb is not None:
            return wb
        parent = self.parent()
        if parent is not None and getattr(parent, "workbook", None) is not None:
            return parent.workbook
        win = self.window()
        if win is not self and getattr(win, "workbook", None) is not None:
            return win.workbook
        return None

    def pivot_table_at(self, r: int, c: int) -> Any | None:
        """Return the PivotReport (or OOXML PivotTable) containing cell (r, c), or None."""
        for report in getattr(self.model, "pivot_reports", []):
            if hasattr(report, "contains_cell") and report.contains_cell(r, c):
                return report

        wb = self._resolve_workbook()
        if wb is not None:
            pivots = getattr(wb, "extra", {}).get("pivots")
            sheet_name = getattr(self.model, "name", "")
            if pivots is not None:
                for tbl in getattr(pivots, "tables", []):
                    if (
                        not getattr(tbl, "drop", None)
                        and getattr(tbl, "sheet_name", "").lower() == sheet_name.lower()
                        and getattr(tbl, "location_ref", None) is not None
                    ):
                        r1, c1, r2, c2 = tbl.location_ref
                        if r1 <= r <= r2 and c1 <= c <= c2:
                            return tbl
        return None

    def refresh_pivot_table(self, target_pivot: Any | None = None) -> bool:
        """Recalculate and refresh the active or specified PivotTable."""
        pvt = target_pivot or self.pivot_table_at(*self.selection.active_cell)
        if pvt is None:
            return False

        wb = self._resolve_workbook()
        from atboffice.modules.spreadsheet.calc.pivots import (
            PivotReport,
            refresh_pivot_report,
        )

        if isinstance(pvt, PivotReport):
            if wb is None:
                return False
            ok = refresh_pivot_report(wb, pvt)
            if ok:
                from atboffice.modules.spreadsheet.tools.chart_builder import sync_pivot_charts

                sync_pivot_charts(wb, pvt)
                self.last_status_message = safe_tr("数据透视表数据已刷新。")
                self.mark_dirty()
                self.viewport().update()
                if getattr(self, "object_layer", None) is not None:
                    self.object_layer.update()
                self.pivot_refresh_requested.emit(pvt)
                win = self.window()
                if win is not self and hasattr(win, "statusBar"):
                    win.statusBar().showMessage(self.last_status_message, 3000)
            return ok

        # OOXML preserved PivotTable fallback
        if wb is not None:
            pivots = getattr(wb, "extra", {}).get("pivots")
            if pivots is not None and hasattr(pivots, "find_cache"):
                cache = pivots.find_cache(getattr(pvt, "cache_id", -1))
                if cache is not None:
                    cache.refresh = False
            self.last_status_message = safe_tr("已标记刷新数据透视表缓存。")
            self.mark_dirty()
            self.viewport().update()
            self.pivot_refresh_requested.emit(pvt)
            return True
        return False

    def show_pivot_field_list(self, target_pivot: Any | None = None) -> None:
        """Request displaying the PivotTable Field List task pane for target_pivot."""
        pvt = target_pivot or self.pivot_table_at(*self.selection.active_cell)
        self.pivot_field_list_requested.emit(pvt)
        win = self.window()
        if win is not self and hasattr(win, "open_pivot_fields_pane"):
            win.open_pivot_fields_pane(pvt)

    def open_pivot_wizard_for(self, target_pivot: Any | None = None) -> None:
        """Open PivotTable Wizard dialog for the sheet or active pivot."""
        win = self.window()
        if win is not self and hasattr(win, "open_pivot_wizard"):
            win.open_pivot_wizard()

    def insert_pivot_chart_for(self, target_pivot: Any | None = None) -> None:
        """Insert a linked PivotChart for the active or specified PivotTable."""
        pvt = target_pivot or self.pivot_table_at(*self.selection.active_cell)
        win = self.window()
        if win is not self and hasattr(win, "insert_pivot_chart"):
            win.insert_pivot_chart(target_pivot=pvt)

    def _apply_pivot_field_filter(
        self,
        report: Any,
        col_idx: int,
        selected_values: set[str] | None,
    ) -> None:
        """Apply filter criteria on a PivotReport field and refresh in place."""
        layout = getattr(report, "layout", None)
        if layout is None:
            return
        for f_list in (layout.filters, layout.rows, layout.columns):
            for fs in f_list:
                if fs.col_idx == col_idx:
                    fs.selected_values = (
                        set(selected_values) if selected_values is not None else None
                    )
        self.refresh_pivot_table(report)

    def _open_pivot_filter_dropdown(self, r: int, c: int) -> None:
        """Show filter selection popup menu for a PivotTable dropdown button cell."""
        report = self.pivot_table_at(r, c)
        if report is None:
            return
        entry = report.meta.filter_dropdown_cells.get((r, c))
        if not entry:
            return
        _zone_type, col_idx = entry
        wb = self._resolve_workbook()
        if wb is None:
            return

        from atboffice.modules.spreadsheet.calc.pivots import get_unique_field_values

        unique_vals = get_unique_field_values(
            wb,
            report.layout.source_sheet,
            report.layout.source_range,
            col_idx,
        )

        # Find current selection state
        cur_sel: set[str] | None = None
        for f_list in (report.layout.filters, report.layout.rows, report.layout.columns):
            for fs in f_list:
                if fs.col_idx == col_idx:
                    cur_sel = fs.selected_values
                    break

        menu = QMenu(self)
        act_all = menu.addAction(safe_tr("(全部)"))
        act_all.setCheckable(True)
        act_all.setChecked(cur_sel is None)
        act_all.triggered.connect(lambda: self._apply_pivot_field_filter(report, col_idx, None))
        menu.addSeparator()

        for val in unique_vals:
            act = menu.addAction(val)
            act.setCheckable(True)
            act.setChecked(cur_sel is not None and val in cur_sel)
            act.triggered.connect(
                lambda _checked=False, v=val: self._apply_pivot_field_filter(report, col_idx, {v})
            )

        c_rect = self.cell_rect(r, c)
        pt = self._global_pos(c_rect.bottomLeft())
        menu.exec(pt)

    def open_chart_type_dialog(self, obj: Any) -> None:
        """Open chart type selector for chart object."""
        win = self.window()
        if win is not self and hasattr(win, "chart_wizard"):
            win.chart_wizard()
        else:
            from atboffice.modules.spreadsheet.dialogs.chart_wizard import (
                ChartWizardDialog,
            )

            dlg = ChartWizardDialog(parent=self)
            dlg.exec()

    def open_chart_options_dialog(self, obj: Any) -> None:
        """Open chart wizard / options for chart object."""
        self.open_chart_type_dialog(obj)

    def edit_object_text(self, obj: Any) -> None:
        """Begin editing text inside shape/textbox."""
        if self.object_layer is not None and hasattr(self.object_layer, "start_text_editing"):
            self.object_layer.start_text_editing(obj)

    def pick_list(self) -> None:
        """Show dropdown validation or distinct column items for active cell."""
        if self._dv_dropdown_rect is not None:
            self._open_dv_dropdown()
            return

        ar, ac = self.selection.active_cell
        distinct_vals: list[str] = []
        seen: set[str] = set()
        for r in range(max(0, ar - 100), min(self.selection.max_rows, ar + 100)):
            if r == ar:
                continue
            v = self.model.get_cell_value(r, ac)
            if v is not None and str(v).strip() and str(v) not in seen:
                seen.add(str(v))
                distinct_vals.append(str(v))
        distinct_vals.sort()
        if distinct_vals:
            menu = QMenu(self)
            for item in distinct_vals:

                def on_sel(val=item) -> None:
                    self.model.set_cell_value(ar, ac, val)
                    self.viewport().update()

                menu.addAction(item, on_sel)
            rect = self.cell_rect(ar, ac)
            menu.exec(self._global_pos(rect.bottomLeft()))

    def add_watch(self, r: int, c: int) -> None:
        """Add cell to Watch Window dialog."""
        win = self.window()
        if hasattr(win, "show_watch_window"):
            win.show_watch_window(True)

    def _update_filter_status(self, af: Any) -> None:
        """Calculate visible vs total records and show in status bar."""
        if not af or not getattr(af, "cols", None):
            msg = ""
        else:
            has_active = any(crit.has_criteria() for crit in af.cols.values())
            if not has_active:
                msg = ""
            else:
                total = max(0, af.r2 - af.r1)
                vis = sum(
                    1
                    for r in range(af.r1 + 1, af.r2 + 1)
                    if r not in self.model.geometry.hidden_rows
                )
                msg = f"{vis} of {total} records found"

        self.last_status_message = msg
        win = self.window()
        if hasattr(win, "statusBar") and win.statusBar():
            if msg:
                win.statusBar().showMessage(msg, 5000)
            else:
                win.statusBar().clearMessage()

    def _apply_column_filter(self, af: Any, col: int, crit: Any) -> None:
        """Apply column filter criteria, record undo snapshot, and update status bar."""
        from atboffice.modules.spreadsheet.models.filter_model import (
            ColumnFilter,
            apply_auto_filter,
        )

        before_cols = {
            c: ColumnFilter(**(vars(cf) if hasattr(cf, "__dict__") else cf))
            if isinstance(cf, ColumnFilter)
            else cf
            for c, cf in af.cols.items()
        }

        col_offset = col - af.c1
        af.cols[col_offset] = crit
        apply_auto_filter(self.model, af)

        after_cols = {
            c: ColumnFilter(**(vars(cf) if hasattr(cf, "__dict__") else cf))
            if isinstance(cf, ColumnFilter)
            else cf
            for c, cf in af.cols.items()
        }

        self._record_entry(
            {
                "action": "filter",
                "af": af,
                "col": col,
                "before_cols": before_cols,
                "after_cols": after_cols,
            }
        )

        self._update_filter_status(af)
        self._update_scrollbars()
        self.viewport().update()

    def _clear_column_filter(self, af: Any, col: int) -> None:
        """Clear filter for a column, record undo snapshot, and update status bar."""
        from atboffice.modules.spreadsheet.models.filter_model import (
            ColumnFilter,
            clear_auto_filter,
        )

        before_cols = {
            c: ColumnFilter(**(vars(cf) if hasattr(cf, "__dict__") else cf))
            if isinstance(cf, ColumnFilter)
            else cf
            for c, cf in af.cols.items()
        }

        col_offset = col - af.c1
        clear_auto_filter(self.model, af, col_offset)

        after_cols = {
            c: ColumnFilter(**(vars(cf) if hasattr(cf, "__dict__") else cf))
            if isinstance(cf, ColumnFilter)
            else cf
            for c, cf in af.cols.items()
        }

        self._record_entry(
            {
                "action": "filter",
                "af": af,
                "col": col,
                "before_cols": before_cols,
                "after_cols": after_cols,
            }
        )

        self._update_filter_status(af)
        self._update_scrollbars()
        self.viewport().update()

    def _open_filter_dropdown(self, col: int) -> None:
        """Open the AutoFilter dropdown popup for the specified column."""
        af = getattr(self.model, "auto_filter", None)
        if af is None or not hasattr(af, "r1") or not hasattr(af, "c1") or not hasattr(af, "c2"):
            return
        from atboffice.modules.spreadsheet.models.filter_model import (
            sort_sheet_range,
        )
        from atboffice.modules.spreadsheet.views.filter_dropdown import (
            FilterDropdownPopup,
        )

        dropdown = FilterDropdownPopup(self.model, af, col, self.viewport())

        def on_sort(desc: bool) -> None:
            sort_sheet_range(
                self.model,
                af.r1,
                af.c1,
                af.r2,
                af.c2,
                [(col, desc)],
                has_header=True,
            )
            self.viewport().update()

        dropdown.filter_applied.connect(lambda crit: self._apply_column_filter(af, col, crit))
        dropdown.filter_cleared.connect(lambda: self._clear_column_filter(af, col))
        dropdown.sort_requested.connect(on_sort)

        # Position popup directly under the cell
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        col_x = self.row_header_width + self.geometry_mapper.col_pos(col) - scroll_x
        row_y = self.col_header_height + self.geometry_mapper.row_pos(af.r1) - scroll_y
        row_h = self.geometry_mapper.row_size(af.r1)
        global_pos = self._global_pos(QPoint(col_x, row_y + row_h))
        dropdown.move(global_pos)
        dropdown.show()

    def toggle_auto_filter(self) -> None:
        """Toggle AutoFilter on current selection or surrounding data range."""
        from atboffice.modules.spreadsheet.models.filter_model import (
            AutoFilter,
            clear_auto_filter,
        )

        if getattr(self.model, "auto_filter", None) is not None:
            af = self.model.auto_filter
            if hasattr(af, "r1"):
                clear_auto_filter(self.model, af)
            self.model.auto_filter = None
            self.last_status_message = ""
            win = self.window()
            if hasattr(win, "statusBar") and win.statusBar():
                win.statusBar().clearMessage()
            self._update_scrollbars()
            self.viewport().update()
            return

        # Determine range from current selection
        pr = self.selection.primary_range
        r1, c1, r2, c2 = pr.min_r, pr.min_c, pr.max_r, pr.max_c
        if r1 == r2 and c1 == c2:
            # Single cell selected: expand to bounding box of active cells
            min_r, min_c, max_r, max_c = r1, c1, r2, c2
            for (cr, cc), cell in self.model.cells.items():
                if cell.value is not None and cell.value != "":
                    min_r = min(min_r, cr)
                    max_r = max(max_r, cr)
                    min_c = min(min_c, cc)
                    max_c = max(max_c, cc)
            r1, c1, r2, c2 = min_r, min_c, max_r, max_c

        af = AutoFilter(r1=r1, c1=c1, r2=r2, c2=c2)
        self.model.auto_filter = af
        self.viewport().update()

    def open_sort_dialog(self) -> None:
        """Open SortDialog for current selection or surrounding data range."""
        pr = self.selection.primary_range
        r1, c1, r2, c2 = pr.min_r, pr.min_c, pr.max_r, pr.max_c
        if r1 == r2 and c1 == c2:
            min_r, min_c, max_r, max_c = r1, c1, r2, c2
            for (cr, cc), cell in self.model.cells.items():
                if cell.value is not None and cell.value != "":
                    min_r = min(min_r, cr)
                    max_r = max(max_r, cr)
                    min_c = min(min_c, cc)
                    max_c = max(max_c, cc)
            r1, c1, r2, c2 = min_r, min_c, max_r, max_c

        from atboffice.modules.spreadsheet.dialogs.sort_dialog import SortDialog
        from atboffice.modules.spreadsheet.models.filter_model import (
            sort_sheet_range,
        )

        dlg = SortDialog(self.model, r1, c1, r2, c2, self)
        if dlg.exec() == SortDialog.DialogCode.Accepted:
            keys = dlg.get_sort_keys()
            if keys:
                sort_sheet_range(
                    self.model,
                    r1,
                    c1,
                    r2,
                    c2,
                    keys,
                    has_header=dlg.has_header(),
                    case_sensitive=dlg.is_case_sensitive(),
                )
                self.viewport().update()
