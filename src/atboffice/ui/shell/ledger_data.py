"""Ledger window: data commands, rows and columns, and the Data menu dialogs."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QDialog, QMessageBox

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.calc.references import cell_name
from atboffice.modules.spreadsheet.models.filter_model import sort_sheet_range
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
)
from atboffice.ui.shell.ledger_common import (
    _cell_edit,
)


class LedgerDataMixin:
    """AutoSum, sort, rows and columns, filters, tables, PivotTables and the Data menu dialogs."""

    @_cell_edit("auto_sum", recalc=True)
    def auto_sum(self, fn: str = "SUM") -> None:
        """Intelligently sniff contiguous numeric cells and inject AutoSum formula."""
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        model = self.spreadsheet_view.model

        # 1. Check numbers above: from r - 1 upwards
        top_r = r - 1
        while top_r >= 0:
            val = model.get_cell_value(top_r, c)
            if isinstance(val, (int, float)):
                top_r -= 1
            else:
                break
        top_r += 1

        formula_range = ""
        if top_r < r:
            start_name = cell_name(top_r, c)
            end_name = cell_name(r - 1, c)
            formula_range = f"{start_name}:{end_name}"
        else:
            left_c = c - 1
            while left_c >= 0:
                val = model.get_cell_value(r, left_c)
                if isinstance(val, (int, float)):
                    left_c -= 1
                else:
                    break
            left_c += 1
            if left_c < c:
                start_name = cell_name(r, left_c)
                end_name = cell_name(r, c - 1)
                formula_range = f"{start_name}:{end_name}"

        if formula_range:
            formula_str = f"{fn}({formula_range})"
        else:
            formula_str = f"{fn}()"

        val = None
        try:
            from atboffice.modules.spreadsheet.calc.context import EvalContext
            from atboffice.modules.spreadsheet.calc.evaluator import evaluate_ast
            from atboffice.modules.spreadsheet.calc.parser import parse

            ctx = EvalContext(cell_getter=lambda sheet, cr, cc: model.get_cell_value(cr, cc))
            ast = parse(formula_str)
            val = evaluate_ast(ast, ctx)
        except Exception:
            val = None

        cell = model.get_cell(r, c)
        if cell is None:
            cell = CellData(value=val, formula=formula_str)
            model.set_cell(r, c, cell)
        else:
            cell.formula = formula_str
            if val is not None:
                cell.value = val
            model.set_cell(r, c, cell)

        if hasattr(self, "formula_bar") and self.formula_bar:
            self.formula_bar.set_cell_text(f"={formula_str}")
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    @_cell_edit("sort", recalc=True)
    def quick_sort(self, desc: bool = False) -> None:
        """Sort selection or surrounding contiguous data table by the active column."""
        pr = self.spreadsheet_view.selection.primary_range
        if pr is not None:
            r1, c1, r2, c2 = pr.min_r, pr.min_c, pr.max_r, pr.max_c
        else:
            r1 = c1 = r2 = c2 = 0

        target_col = self.spreadsheet_view.selection.active_cell[1]

        if r1 == r2 and c1 == c2:
            min_r, min_c, max_r, max_c = r1, c1, r2, c2
            for (cr, cc), cell in self.spreadsheet_view.model.cells.items():
                if cell.value is not None and cell.value != "":
                    min_r = min(min_r, cr)
                    max_r = max(max_r, cr)
                    min_c = min(min_c, cc)
                    max_c = max(max_c, cc)
            r1, c1, r2, c2 = min_r, min_c, max_r, max_c

        has_header = False
        if r1 < r2:
            val0 = self.spreadsheet_view.model.get_cell_value(r1, target_col)
            if not isinstance(val0, (int, float)):
                for r in range(r1 + 1, r2 + 1):
                    v = self.spreadsheet_view.model.get_cell_value(r, target_col)
                    if isinstance(v, (int, float)):
                        has_header = True
                        break

        sort_sheet_range(
            self.spreadsheet_view.model,
            r1,
            c1,
            r2,
            c2,
            [(target_col, desc)],
            has_header=has_header,
            case_sensitive=False,
        )
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    @_cell_edit("insert_rows", recalc=True)
    def insert_rows(self) -> None:
        """Insert rows above current selection, shifting cells down."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        count = r2 - r1 + 1
        model = self.spreadsheet_view.model
        new_cells: dict[tuple[int, int], CellData] = {}
        for (r, c), cell in model.cells.items():
            if r >= r1:
                new_cells[(r + count, c)] = cell
            else:
                new_cells[(r, c)] = cell
        model.cells = new_cells
        new_merges: list[tuple[int, int, int, int]] = []
        for mr1, mc1, mr2, mc2 in model.merges:
            if mr1 >= r1:
                new_merges.append((mr1 + count, mc1, mr2 + count, mc2))
            elif mr2 >= r1:
                new_merges.append((mr1, mc1, mr2 + count, mc2))
            else:
                new_merges.append((mr1, mc1, mr2, mc2))
        model.merges = new_merges
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    @_cell_edit("insert_cols", recalc=True)
    def insert_columns(self) -> None:
        """Insert columns to the left of current selection, shifting cells right."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        count = c2 - c1 + 1
        model = self.spreadsheet_view.model
        new_cells: dict[tuple[int, int], CellData] = {}
        for (r, c), cell in model.cells.items():
            if c >= c1:
                new_cells[(r, c + count)] = cell
            else:
                new_cells[(r, c)] = cell
        model.cells = new_cells
        new_merges: list[tuple[int, int, int, int]] = []
        for mr1, mc1, mr2, mc2 in model.merges:
            if mc1 >= c1:
                new_merges.append((mr1, mc1 + count, mr2, mc2 + count))
            elif mc2 >= c1:
                new_merges.append((mr1, mc1, mr2, mc2 + count))
            else:
                new_merges.append((mr1, mc1, mr2, mc2))
        model.merges = new_merges
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    @_cell_edit("delete_rows", recalc=True)
    def delete_rows(self) -> None:
        """Delete rows in current selection, shifting remaining cells up."""
        if hasattr(self.spreadsheet_view, "grid") and hasattr(
            self.spreadsheet_view.grid, "delete_selected_rows"
        ):
            self.spreadsheet_view.grid.delete_selected_rows()
            self.set_modified(True)

    @_cell_edit("delete_cols", recalc=True)
    def delete_columns(self) -> None:
        """Delete columns in current selection, shifting remaining cells left."""
        if hasattr(self.spreadsheet_view, "grid") and hasattr(
            self.spreadsheet_view.grid, "delete_selected_cols"
        ):
            self.spreadsheet_view.grid.delete_selected_cols()
            self.set_modified(True)

    def toggle_auto_filter(self) -> None:
        """Toggle AutoFilter for the active worksheet."""
        if hasattr(self.spreadsheet_view, "grid") and hasattr(
            self.spreadsheet_view.grid, "toggle_auto_filter"
        ):
            self.spreadsheet_view.grid.toggle_auto_filter()
        is_active = getattr(self.spreadsheet_view.model, "auto_filter", None) is not None
        self.action_registry.set_checked("autoFilter", is_active)
        self.set_modified(True)

    def convert_table_to_range(self) -> None:
        """Convert list/table back to normal range, clearing auto filter and total row."""
        model = self.spreadsheet_view.model
        if getattr(model, "auto_filter", None) is not None:
            self.toggle_auto_filter()
        if hasattr(self, "_total_row_active") and self._total_row_active:
            self.toggle_total_row()
        self.action_registry.set_checked("totalRow", False)
        self.action_registry.set_checked("autoFilter", False)
        self.set_modified(True)

    def open_pivot_wizard(self) -> None:
        """Launch the PivotTable and PivotChart report wizard dialog."""
        from atboffice.modules.spreadsheet.dialogs.pivot_dialog import (
            PivotTableWizardDialog,
        )

        sheet = self.spreadsheet_view.model
        sel = self.spreadsheet_view.selection
        pr = sel.primary_range

        if pr.min_r == pr.max_r and pr.min_c == pr.max_c:
            used_r2 = max(sheet.max_row, pr.min_r)
            used_c2 = max(sheet.max_col, pr.min_c)
            init_range = (0, 0, max(1, used_r2), max(1, used_c2))
        else:
            init_range = (pr.min_r, pr.min_c, pr.max_r, pr.max_c)

        dlg = PivotTableWizardDialog(
            workbook=self.workbook,
            initial_sheet_name=sheet.name,
            initial_range=init_range,
            parent=self,
        )
        if dlg.exec():
            if getattr(dlg, "created_report", None) is not None:
                self.open_pivot_fields_pane(dlg.created_report)
            self.set_modified(True)
            self.spreadsheet_view.grid.viewport().update()
            self.statusBar().showMessage(safe_tr("数据透视表报表已成功生成。"), 4000)

    @staticmethod
    def _current_region(sheet: object, r: int, c: int) -> tuple[int, int, int, int]:
        """Expand a single cell to its contiguous non-empty block (Excel CurrentRegion)."""
        if sheet.is_empty(r, c):
            return r, c, r, c
        r1 = r2 = r
        c1 = c2 = c
        changed = True
        while changed:
            changed = False
            if r1 > 0 and any(not sheet.is_empty(r1 - 1, cc) for cc in range(c1, c2 + 1)):
                r1 -= 1
                changed = True
            if any(not sheet.is_empty(r2 + 1, cc) for cc in range(c1, c2 + 1)):
                r2 += 1
                changed = True
            if c1 > 0 and any(not sheet.is_empty(rr, c1 - 1) for rr in range(r1, r2 + 1)):
                c1 -= 1
                changed = True
            if any(not sheet.is_empty(rr, c2 + 1) for rr in range(r1, r2 + 1)):
                c2 += 1
                changed = True
            if r2 - r1 > 10000 or c2 - c1 > 1000:
                break
        return r1, c1, r2, c2

    # ------------------------------------------------------------------
    # Undoable cell edits shared by the Data / Tools dialogs
    # ------------------------------------------------------------------
    def _refresh_after_cell_edit(self) -> None:
        grid = getattr(self.spreadsheet_view, "grid", None)
        if grid is not None:
            if hasattr(grid, "_update_scrollbars"):
                grid._update_scrollbars()
            grid.viewport().update()
        layer = getattr(self.spreadsheet_view, "object_layer", None)
        if layer is not None:
            layer.update()

    def run_cell_edit(
        self,
        mutate: Any,
        action: str = "edit",
        *,
        scope: str = "sheet",
        recalc: bool = True,
    ) -> Any:
        """Run ``mutate()`` as one undoable worksheet edit and recalculate formulas.

        ``scope`` is ``"sheet"`` when any cell may change, or ``"selection"``
        for edits limited to the selected cells (formatting): only those cells
        are copied for undo. ``mutate`` may return ``False`` when nothing changed.
        """
        grid = getattr(self.spreadsheet_view, "grid", None)
        if grid is None or not hasattr(grid, "undoable_edit"):
            return mutate()
        with grid.undoable_edit(action, scope=scope):
            result = mutate()
            if result is not False and recalc:
                workbook = getattr(self.spreadsheet_view, "workbook", None)
                if workbook is not None and hasattr(workbook, "recalculate"):
                    workbook.recalculate()
        if result is False:
            return result
        self._refresh_after_cell_edit()
        self.set_modified(True)
        return result

    def _exec_cell_dialog(self, dlg: Any, action: str) -> bool:
        """Exec a dialog that edits cells itself; record one undo step when accepted."""
        grid = getattr(self.spreadsheet_view, "grid", None)
        before = grid._snapshot_state() if grid is not None else None
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        if before is not None and before["sheet"] is self.spreadsheet_view.model:
            # Recalculate first so that undo also restores the cached values.
            workbook = getattr(self.spreadsheet_view, "workbook", None)
            if workbook is not None and hasattr(workbook, "recalculate"):
                workbook.recalculate()
            if grid._commit_undo(before, action):
                self.set_modified(True)
        self._refresh_after_cell_edit()
        return accepted

    def _selection_or_region(self) -> tuple[int, int, int, int]:
        """Selected range, or the current region around a single selected cell."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        sheet = getattr(self.spreadsheet_view, "model", None)
        if (r1, c1) == (r2, c2) and sheet is not None:
            return self._current_region(sheet, r1, c1)
        return r1, c1, r2, c2

    def _show_tool_error(self, title: str, exc: Exception) -> None:
        QMessageBox.warning(self, title, str(exc))

    def open_text_to_columns_wizard(self) -> None:
        """Open Excel 2003 classic Convert Text to Columns Wizard (文本分列向导)."""
        from atboffice.modules.spreadsheet.dialogs.text_to_columns_wizard import TextToColumnsWizard

        sheet = getattr(self.spreadsheet_view, "model", None)
        r1, c1, r2, _c2 = self._get_selected_cell_range()
        # Excel converts one column at a time.
        dlg = TextToColumnsWizard(sheet_model=sheet, selected_range=(r1, c1, r2, c1), parent=self)
        self._exec_cell_dialog(dlg, "text_to_columns")

    def open_subtotal_dialog(self) -> None:
        """Open Excel 2003 classic Subtotal Calculation (分类汇总) dialog."""
        from atboffice.modules.spreadsheet.dialogs.subtotal_dialog import SubtotalDialog
        from atboffice.modules.spreadsheet.tools import data_tools

        sheet = getattr(self.spreadsheet_view, "model", None)
        if sheet is None:
            return
        sel_range = self._selection_or_region()
        if sel_range[2] <= sel_range[0]:
            QMessageBox.information(
                self,
                safe_tr("分类汇总"),
                safe_tr("请选择包含标题行的数据列表，再执行分类汇总。"),
            )
            return
        dlg = SubtotalDialog(sheet_model=sheet, selected_range=sel_range, parent=self)
        dlg.subtotal_applied.connect(
            lambda cfg: self.run_cell_edit(
                lambda: data_tools.apply_subtotals(sheet, sel_range, cfg), "subtotal"
            )
        )
        dlg.subtotal_removed.connect(
            lambda: self.run_cell_edit(
                lambda: data_tools.remove_subtotals(sheet, sel_range), "subtotal_remove"
            )
        )
        dlg.exec()

    def open_consolidate_dialog(self) -> None:
        """Open Excel 2003 classic Consolidate (合并计算) dialog."""
        from atboffice.modules.spreadsheet.dialogs.consolidate_dialog import ConsolidateDialog
        from atboffice.modules.spreadsheet.tools import data_tools

        sheet = getattr(self.spreadsheet_view, "model", None)
        workbook = getattr(self.spreadsheet_view, "workbook", None)
        dest = self.spreadsheet_view.selection.active_cell
        dlg = ConsolidateDialog(sheet_model=sheet, workbook_model=workbook, parent=self)

        def apply(cfg: dict) -> None:
            if not cfg.get("references"):
                QMessageBox.information(
                    self, safe_tr("合并计算"), safe_tr("请至少添加一个引用位置。")
                )
                return
            result = self.run_cell_edit(
                lambda: data_tools.consolidate(workbook, sheet, dest, cfg) or False,
                "consolidate",
            )
            if result is False:
                QMessageBox.warning(
                    self, safe_tr("合并计算"), safe_tr("引用位置无效，未能合并任何数据。")
                )

        dlg.consolidate_applied.connect(apply)
        dlg.exec()

    def open_scenario_manager(self) -> None:
        """Open Excel 2003 classic Scenario Manager (方案管理器) dialog."""
        from atboffice.modules.spreadsheet.dialogs.scenario_manager_dialog import (
            ScenarioManagerDialog,
        )

        sheet = getattr(self.spreadsheet_view, "model", None)
        workbook = getattr(self.spreadsheet_view, "workbook", None)
        stored = sheet.extra.get("scenarios") if sheet is not None else None
        dlg = ScenarioManagerDialog(
            sheet_model=sheet,
            initial_scenarios=stored,
            parent=self,
            workbook_model=workbook,
        )
        if sheet is not None:
            dlg.scenarios_updated.connect(
                lambda items: sheet.extra.__setitem__("scenarios", list(items))
            )
        created: list[Any] = []
        dlg.summary_created.connect(created.append)
        self._exec_cell_dialog(dlg, "scenario_show")
        if sheet is not None:
            sheet.extra["scenarios"] = list(dlg.scenarios)
        if created and workbook is not None:
            idx = workbook.sheet_index(created[0])
            if idx >= 0 and hasattr(self.spreadsheet_view, "set_active_sheet_index"):
                self.spreadsheet_view.set_active_sheet_index(idx)
            self.set_modified(True)

    def open_data_table_dialog(self) -> None:
        """Open Excel 2003 classic Data Table (模拟运算表) dialog."""
        from atboffice.modules.spreadsheet.dialogs.data_table_dialog import DataTableDialog

        sheet = getattr(self.spreadsheet_view, "model", None)
        sel_range = self._get_selected_cell_range()
        if sel_range[0] == sel_range[2] or sel_range[1] == sel_range[3]:
            QMessageBox.information(
                self,
                safe_tr("模拟运算表"),
                safe_tr("请先选定包含公式和输入值的单元格区域。"),
            )
            return
        dlg = DataTableDialog(
            sheet_model=sheet,
            selected_range=sel_range,
            parent=self,
            workbook_model=getattr(self.spreadsheet_view, "workbook", None),
        )
        self._exec_cell_dialog(dlg, "data_table")

    def open_protect_sheet_dialog(self) -> None:
        """Open Excel 2003 classic Protect/Unprotect Sheet dialog."""
        from atboffice.modules.spreadsheet.dialogs.protect_dialog import (
            ProtectSheetDialog,
            UnprotectSheetDialog,
        )

        sheet = getattr(self.spreadsheet_view, "model", None)
        if sheet and getattr(sheet, "protection", None):
            dlg = UnprotectSheetDialog(sheet_model=sheet, parent=self)
        else:
            dlg = ProtectSheetDialog(sheet_model=sheet, parent=self)
        dlg.exec()

    def open_protect_workbook_dialog(self) -> None:
        """Open Excel 2003 classic Protect Workbook dialog."""
        from atboffice.modules.spreadsheet.dialogs.protect_dialog import ProtectWorkbookDialog

        workbook = getattr(self.spreadsheet_view, "workbook", None)
        dlg = ProtectWorkbookDialog(workbook_model=workbook, parent=self)
        dlg.exec()

    def open_advanced_filter_dialog(self) -> None:
        """Open Excel 2003 classic Advanced Filter (高级筛选) dialog."""
        from atboffice.modules.spreadsheet.calc.references import abs_range_name
        from atboffice.modules.spreadsheet.dialogs.advanced_filter_dialog import (
            AdvancedFilterDialog,
        )
        from atboffice.modules.spreadsheet.tools import data_tools

        sheet = getattr(self.spreadsheet_view, "model", None)
        workbook = getattr(self.spreadsheet_view, "workbook", None)
        r1, c1, r2, c2 = self._selection_or_region()
        list_range = abs_range_name({"r1": r1, "c1": c1, "r2": r2, "c2": c2})
        dlg = AdvancedFilterDialog(sheet_model=sheet, initial_list_range=list_range, parent=self)

        def apply(params: dict) -> None:
            try:
                self.run_cell_edit(
                    lambda: data_tools.advanced_filter(workbook, sheet, params),
                    "advanced_filter",
                )
            except ValueError as exc:
                self._show_tool_error(safe_tr("高级筛选"), exc)

        dlg.filter_applied.connect(apply)
        dlg.exec()

    def show_all_filtered_rows(self) -> None:
        """Data > Filter > Show All after an in-place advanced filter."""
        from atboffice.modules.spreadsheet.tools import data_tools

        sheet = getattr(self.spreadsheet_view, "model", None)
        if sheet is not None and data_tools.show_all_after_filter(sheet):
            self._refresh_after_cell_edit()
            self.set_modified(True)

    def toggle_total_row(self) -> None:
        """Toggle table total calculation summary row."""
        model = self.spreadsheet_view.model
        grid = getattr(self.spreadsheet_view, "grid", None)

        if getattr(self, "_total_row_active", False):
            # Deactivate total row
            r_total = getattr(self, "_total_row_r", None)
            if r_total is not None:
                before_cells = {k: v.clone() for k, v in model.cells.items()}
                c1, c2 = getattr(self, "_total_row_cols", (0, 0))
                for c in range(c1, c2 + 1):
                    if (r_total, c) in model.cells:
                        del model.cells[(r_total, c)]
                after_cells = {k: v.clone() for k, v in model.cells.items()}
                if grid and hasattr(grid, "_record_entry"):
                    grid._record_entry(
                        {
                            "action": "total_row",
                            "before_cells": before_cells,
                            "after_cells": after_cells,
                            "before_merges": list(model.merges),
                            "after_merges": list(model.merges),
                            "before_sel": grid.selection.snapshot(),
                            "after_sel": grid.selection.snapshot(),
                            "active": False,
                        }
                    )
            self._total_row_active = False
            self._total_row_r = None
            self.action_registry.set_checked("totalRow", False)
            if grid:
                grid._update_scrollbars()
                grid.viewport().update()
            self.set_modified(True)
            return

        # Determine target data range
        af = getattr(model, "auto_filter", None)
        if af is not None:
            r1, c1, r2, c2 = af.r1, af.c1, af.r2, af.c2
        else:
            pr = self.spreadsheet_view.selection.primary_range
            r1, c1, r2, c2 = pr.min_r, pr.min_c, pr.max_r, pr.max_c
            if r1 == r2 and c1 == c2:
                # Expand to bounding box of populated cells
                min_r, min_c, max_r, max_c = r1, c1, r2, c2
                has_data = False
                for (cr, cc), cell in model.cells.items():
                    if cell.value is not None and str(cell.value) != "":
                        min_r = min(min_r, cr)
                        max_r = max(max_r, cr)
                        min_c = min(min_c, cc)
                        max_c = max(max_c, cc)
                        has_data = True
                if not has_data:
                    self.action_registry.set_checked("totalRow", False)
                    return
                r1, c1, r2, c2 = min_r, min_c, max_r, max_c

        r_total = r2 + 1
        before_cells = {k: v.clone() for k, v in model.cells.items()}

        lbl_cell = CellData(
            value=safe_tr("汇总"),
            bold=True,
            border_top=BorderStyle(style="thin", color="#000000"),
            border_bottom=BorderStyle(style="double", color="#000000"),
        )
        model.set_cell(r_total, c1, lbl_cell)

        for c in range(c1 + 1, c2 + 1):
            has_num = False
            for r in range(r1, r2 + 1):
                val = model.get_cell_value(r, c)
                if isinstance(val, (int, float)):
                    has_num = True
                    break
            if has_num or c == c2:
                rng_str = f"{cell_name(r1, c)}:{cell_name(r2, c)}"
                total_val = 0.0
                for r in range(r1, r2 + 1):
                    v = model.get_cell_value(r, c)
                    if isinstance(v, (int, float)):
                        total_val += v
                tot_cell = CellData(
                    value=total_val,
                    formula=f"SUBTOTAL(109,{rng_str})",
                    bold=True,
                    border_top=BorderStyle(style="thin", color="#000000"),
                    border_bottom=BorderStyle(style="double", color="#000000"),
                )
                model.set_cell(r_total, c, tot_cell)
            else:
                empty_tot = CellData(
                    bold=True,
                    border_top=BorderStyle(style="thin", color="#000000"),
                    border_bottom=BorderStyle(style="double", color="#000000"),
                )
                model.set_cell(r_total, c, empty_tot)

        self._total_row_active = True
        self._total_row_r = r_total
        self._total_row_cols = (c1, c2)
        self.action_registry.set_checked("totalRow", True)

        if grid and hasattr(grid, "_record_entry"):
            grid._record_entry(
                {
                    "action": "total_row",
                    "before_cells": before_cells,
                    "after_cells": {k: v.clone() for k, v in model.cells.items()},
                    "before_merges": list(model.merges),
                    "after_merges": list(model.merges),
                    "before_sel": grid.selection.snapshot(),
                    "after_sel": grid.selection.snapshot(),
                    "active": True,
                    "r_total": r_total,
                    "cols": (c1, c2),
                }
            )

        if grid:
            grid._update_scrollbars()
            grid.viewport().update()
        self.set_modified(True)

    def paste_special(self) -> None:
        """Launch Paste Special dialog and dispatch to spreadsheet view."""
        grid = getattr(getattr(self, "spreadsheet_view", None), "grid", None)
        if grid and hasattr(grid, "paste_special"):
            grid.paste_special()

    def open_function_wizard(self) -> None:
        """Open formula function wizard dialog."""
        from atboffice.modules.spreadsheet.dialogs.function_wizard import (
            launch_function_wizard,
        )

        active_sheet = getattr(self.spreadsheet_view, "model", None)
        active_sel = getattr(self.spreadsheet_view, "selection", None)
        r, c = active_sel.active_cell if active_sel else (0, 0)
        launch_function_wizard(
            parent=self,
            workbook=getattr(self.spreadsheet_view, "workbook", None),
            sheet=active_sheet,
            active_r=r,
            active_c=c,
            editor_controller=getattr(self.spreadsheet_view, "editor_controller", None),
        )
