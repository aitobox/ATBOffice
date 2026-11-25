"""Ledger window: formula auditing, comments, validation, Watch Window and task panes."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QMessageBox

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.calc.references import cell_name


class LedgerAuditingMixin:
    """Formula auditing, comments, data validation, the Watch Window and task panes."""

    def trace_error(self) -> None:
        """Check worksheet for formula calculation errors and trace error source."""
        sheet = self.spreadsheet_view.model
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        cell = sheet.get_cell(r, c)
        is_cell_err = False
        if cell:
            v = str(cell.value) if cell.value is not None else ""
            if v.startswith("#"):
                is_cell_err = True

        if not is_cell_err:
            QMessageBox.information(
                self,
                safe_tr("错误检查"),
                safe_tr("活动单元格不包含错误值。"),
            )
            return

        from atboffice.modules.spreadsheet.calc.audit_tracer import AuditTracer

        workbook = getattr(self.spreadsheet_view, "workbook", None)
        arrows = AuditTracer.trace_error(workbook, sheet.name, r, c)
        if not arrows:
            QMessageBox.information(
                self,
                safe_tr("错误检查"),
                safe_tr("未找到导致该错误的单元格引用。"),
            )
            return

        existing = getattr(sheet, "audit_arrows", [])
        sheet.audit_arrows = existing + arrows
        self.spreadsheet_view.grid.viewport().update()
        self.statusBar().showMessage(safe_tr("已追踪公式错误源。"), 3000)

    def trace_precedents(self) -> None:
        """Trace precedent cells for the active formula."""
        sheet = self.spreadsheet_view.model
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        cell = sheet.get_cell(r, c)
        if cell is None or not cell.formula:
            QMessageBox.information(
                self,
                safe_tr("追踪前驱"),
                safe_tr("活动单元格不包含引用其他单元格的有效公式。"),
            )
            return

        from atboffice.modules.spreadsheet.calc.audit_tracer import AuditTracer

        workbook = getattr(self.spreadsheet_view, "workbook", None)
        arrows = AuditTracer.trace_precedents(workbook, sheet.name, r, c)
        if not arrows:
            QMessageBox.information(
                self,
                safe_tr("追踪前驱"),
                safe_tr("活动单元格公式不包含任何单元格或区域引用。"),
            )
            return

        existing = getattr(sheet, "audit_arrows", [])
        sheet.audit_arrows = existing + arrows
        self.spreadsheet_view.grid.viewport().update()
        self.statusBar().showMessage(safe_tr("已追踪公式前驱引用箭头。"), 3000)

    def trace_dependents(self) -> None:
        """Trace dependent cells referencing the active cell."""
        sheet = self.spreadsheet_view.model
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        workbook = getattr(self.spreadsheet_view, "workbook", None)

        from atboffice.modules.spreadsheet.calc.audit_tracer import AuditTracer

        arrows = AuditTracer.trace_dependents(workbook, sheet.name, r, c)
        if not arrows:
            QMessageBox.information(
                self,
                safe_tr("追踪从属"),
                safe_tr("未找到引用当前单元格的公式。"),
            )
            return

        existing = getattr(sheet, "audit_arrows", [])
        sheet.audit_arrows = existing + arrows
        self.spreadsheet_view.grid.viewport().update()
        self.statusBar().showMessage(safe_tr("已追踪公式从属引用箭头。"), 3000)

    def remove_arrows(self) -> None:
        """Remove all audit tracer arrows from worksheet."""
        sheet = self.spreadsheet_view.model
        sheet.audit_arrows = []
        self.spreadsheet_view.grid.viewport().update()
        self.statusBar().showMessage(safe_tr("已移去所有公式审核箭头。"), 3000)

    def insert_comment(self) -> None:
        """Insert or edit comment for the active cell."""
        sheet = self.spreadsheet_view.model
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        cm = sheet.get_comment(r, c)
        from atboffice.modules.spreadsheet.calc.references import to_a1

        cell_ref = to_a1(r, c)
        from atboffice.modules.spreadsheet.dialogs.comment_dialog import (
            CommentDialog,
        )

        existing_text = cm.text if cm else ""
        author = cm.author if (cm and cm.author) else "Ledger User"

        dlg = CommentDialog(
            existing_text=existing_text,
            author=author,
            cell_ref=cell_ref,
            parent=self,
        )
        if dlg.exec():
            new_text = dlg.get_text()
            new_author = dlg.get_author()
            if new_text:
                sheet.set_comment(
                    r,
                    c,
                    text=new_text,
                    author=new_author,
                    visible=cm.visible if cm else False,
                )
            else:
                sheet.delete_comment(r, c)
            self.spreadsheet_view.grid.viewport().update()

    def show_hide_comment(self) -> None:
        """Toggle visibility of comment for the active cell."""
        sheet = self.spreadsheet_view.model
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        cm = sheet.get_comment(r, c)
        if cm:
            cm.visible = not cm.visible
            self.spreadsheet_view.grid.viewport().update()
        else:
            self.statusBar().showMessage(safe_tr("当前单元格没有批注。"), 3000)

    def delete_comment(self) -> None:
        """Delete comment on the active cell."""
        sheet = self.spreadsheet_view.model
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        deleted = sheet.delete_comment(r, c)
        if deleted:
            self.spreadsheet_view.grid.viewport().update()
            self.statusBar().showMessage(safe_tr("已删除单元格批注。"), 3000)
        else:
            self.statusBar().showMessage(safe_tr("当前单元格没有批注。"), 3000)

    def toggle_show_all_comments(self) -> None:
        """Toggle visibility of all worksheet comments."""
        sheet = self.spreadsheet_view.model
        sheet.show_all_comments = not getattr(sheet, "show_all_comments", False)
        self.spreadsheet_view.grid.viewport().update()
        msg = (
            safe_tr("已显示所有批注。") if sheet.show_all_comments else safe_tr("已隐藏所有批注。")
        )
        self.statusBar().showMessage(msg, 3000)

    def data_validation(self) -> None:
        """Open data validation rule configuration dialog."""
        sheet = self.spreadsheet_view.model
        sel = self.spreadsheet_view.selection
        ar, ac = sel.active_cell
        existing_dv = sheet.get_validation_at(ar, ac)
        pr = sel.primary_range
        from atboffice.modules.spreadsheet.calc.references import to_a1

        if pr.min_r == pr.max_r and pr.min_c == pr.max_c:
            sqref = to_a1(pr.min_r, pr.min_c)
        else:
            sqref = f"{to_a1(pr.min_r, pr.min_c)}:{to_a1(pr.max_r, pr.max_c)}"
        ranges = [(rg.min_r, rg.min_c, rg.max_r, rg.max_c) for rg in sel.ranges]

        from atboffice.modules.spreadsheet.dialogs.data_validation_dialog import (
            DataValidationDialog,
        )

        dlg = DataValidationDialog(
            existing_dv=existing_dv,
            sqref=sqref,
            ranges=ranges,
            parent=self,
        )
        if dlg.exec():
            from atboffice.modules.spreadsheet.models.validation import (
                ValidationType,
            )

            dv = dlg.get_data_validation()
            if dv.type in (ValidationType.ANY.value, "none"):
                new_dvs = []
                for existing in sheet.data_validations:
                    rem_ranges = [rng for rng in existing.ranges if rng not in ranges]
                    if rem_ranges:
                        existing.ranges = rem_ranges
                        new_dvs.append(existing)
                sheet.data_validations = new_dvs
            else:
                sheet.add_data_validation(dv)
            self.spreadsheet_view.grid.viewport().update()

    def circle_invalid(self) -> None:
        """Circle invalid data in worksheet according to validation rules."""
        sheet = self.spreadsheet_view.model
        if not sheet.data_validations:
            self.statusBar().showMessage(safe_tr("当前工作表没有数据有效性规则。"), 3000)
            return

        from atboffice.modules.spreadsheet.models.validation import (
            validate_cell_value,
        )

        invalid_cells: list[tuple[int, int]] = []
        more = False

        checked_cells: set[tuple[int, int]] = set()
        for dv in sheet.data_validations:
            for r1, c1, r2, c2 in dv.ranges:
                for r in range(r1, r2 + 1):
                    for c in range(c1, c2 + 1):
                        checked_cells.add((r, c))

        for r, c in checked_cells:
            val = sheet.get_cell_value(r, c)
            if val is None or val == "":
                continue
            is_valid, _ = validate_cell_value(sheet, r, c, val)
            if not is_valid:
                if len(invalid_cells) < 255:
                    invalid_cells.append((r, c))
                else:
                    more = True
                    break

        sheet.invalid_circles = invalid_cells
        self.spreadsheet_view.grid.viewport().update()

        if more:
            QMessageBox.warning(
                self,
                safe_tr("数据有效性"),
                safe_tr("此工作表包含超过 255 个无效单元格，仅圈释前 255 个。"),
            )
        elif not invalid_cells:
            self.statusBar().showMessage(safe_tr("当前工作表中没有无效数据。"), 3000)
        else:
            self.statusBar().showMessage(
                safe_tr("已圈释 {count} 个无效数据单元格。").format(count=len(invalid_cells)),
                3000,
            )

    def clear_circles(self) -> None:
        """Clear all invalid data validation circles."""
        sheet = self.spreadsheet_view.model
        sheet.invalid_circles = []
        self.spreadsheet_view.grid.viewport().update()
        self.statusBar().showMessage(safe_tr("已清除所有无效数据圈释。"), 3000)

    def watch_window(self) -> None:
        """Open or activate watch window for inspecting formula values."""
        if self._watch_window is None:
            from atboffice.modules.spreadsheet.dialogs.watch_window_dialog import (
                WatchWindowDialog,
            )

            workbook = getattr(self.spreadsheet_view, "workbook", None)
            book_name = (
                self.current_file_path.name
                if getattr(self, "current_file_path", None)
                else getattr(self, "default_doc_name", "Book1")
            )
            self._watch_window = WatchWindowDialog(
                workbook=workbook,
                book_name=book_name,
                parent=self,
            )
            self._watch_window.navigate_requested.connect(self._on_watch_navigate)
            self._watch_window.add_watch_requested.connect(self._on_watch_add_current)
            self.spreadsheet_view.editor_controller.cell_committed.connect(
                lambda *_: (
                    self._watch_window.refresh_watches()
                    if self._watch_window and self._watch_window.isVisible()
                    else None
                )
            )

        self._watch_window.refresh_watches()
        self._watch_window.show()
        self._watch_window.raise_()
        self._watch_window.activateWindow()
        self.statusBar().showMessage(safe_tr("已打开公式监视窗口。"), 3000)

    def _on_watch_navigate(self, sheet_name: str, r: int, c: int) -> None:
        """Navigate to sheet and cell selected in Watch Window."""
        wb = getattr(self.spreadsheet_view, "workbook", None)
        if wb:
            for idx, s in enumerate(wb.sheets):
                if s.name == sheet_name:
                    if wb.active_sheet_index != idx:
                        wb.set_active_sheet_index(idx)
                    break
        self.spreadsheet_view.selection.set_active_cell(r, c)
        self.spreadsheet_view.grid.reveal(r, c)
        self.spreadsheet_view.grid.viewport().update()

    def _on_watch_add_current(self) -> None:
        """Add current active cell to Watch Window."""
        if not self._watch_window:
            return
        sheet = self.spreadsheet_view.model
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        self._watch_window.add_watch(sheet.name, r, c)

    def _setup_ledger_task_panes(self) -> None:
        """Register Ledger specific task panes (Watch Window)."""
        if not self.task_pane_dock:
            return

        from atboffice.modules.spreadsheet.panes import (
            PivotFieldsTaskPane,
            WatchWindowPane,
        )

        wb = getattr(self.spreadsheet_view, "workbook", None)
        book_name = (
            self.current_file_path.name
            if getattr(self, "current_file_path", None)
            else getattr(self, "default_doc_name", "Book1")
        )

        self.watch_pane = WatchWindowPane(
            workbook=wb,
            book_name=book_name,
            parent=self.task_pane_dock,
        )
        self.watch_pane.navigate_requested.connect(self._on_watch_navigate)
        self.watch_pane.add_watch_requested.connect(self._on_watch_pane_add_current)

        self.spreadsheet_view.editor_controller.cell_committed.connect(
            lambda *_: self.watch_pane.refresh_watches() if hasattr(self, "watch_pane") else None
        )

        self.task_pane_dock.register_pane(
            "watch_window",
            safe_tr("监视窗口"),
            self.watch_pane,
        )

        self.pivot_fields_pane = PivotFieldsTaskPane(
            workbook=wb,
            parent=self.task_pane_dock,
        )
        self.pivot_fields_pane.report_refreshed.connect(self._on_pivot_report_refreshed)
        self.task_pane_dock.register_pane(
            "pivot_fields",
            safe_tr("数据透视表字段列表"),
            self.pivot_fields_pane,
        )

        self.spreadsheet_view.grid.pivot_selection_changed.connect(self._on_pivot_selection_changed)
        self.spreadsheet_view.grid.pivot_refresh_requested.connect(self._on_pivot_report_refreshed)
        self.spreadsheet_view.workbook_changed.connect(self._on_workbook_changed)

    def _on_watch_pane_add_current(self) -> None:
        """Add current active cell to Watch Window task pane."""
        if not hasattr(self, "watch_pane"):
            return
        sheet = self.spreadsheet_view.model
        if not sheet:
            return
        r, c = self.spreadsheet_view.selection.active_cell
        self.watch_pane.add_watch(sheet.name, r, c)
        cname = f"{sheet.name}!${cell_name(r, c)}"
        self.statusBar().showMessage(safe_tr("已添加到监视窗口: {0}", cname), 3000)

    def open_watch_pane(self) -> None:
        """Open or activate Watch Window task pane."""
        if self.task_pane_dock is not None:
            self.task_pane_dock.show()
            self.task_pane_dock.show_pane("watch_window")
        self.statusBar().showMessage(safe_tr("已打开公式监视任务窗格。"), 3000)

    def open_pivot_fields_pane(self, target_pivot: Any | None = None) -> None:
        """Open and bind the PivotTable Field List task pane."""
        if not hasattr(self, "pivot_fields_pane") or self.task_pane_dock is None:
            return
        from atboffice.modules.spreadsheet.calc.pivots import PivotReport

        if target_pivot is None:
            ar, ac = self.spreadsheet_view.selection.active_cell
            target_pivot = self.spreadsheet_view.grid.pivot_table_at(ar, ac)

        if isinstance(target_pivot, PivotReport):
            self.pivot_fields_pane.bind_pivot_report(target_pivot, self.workbook)

        self.task_pane_dock.show()
        self.task_pane_dock.show_pane("pivot_fields")
        self.statusBar().showMessage(safe_tr("已打开数据透视表字段列表任务窗格。"), 3000)

    def _on_pivot_selection_changed(self, report: Any | None) -> None:
        """Keep PivotFieldsTaskPane synchronized when active cell moves onto a PivotTable."""
        if not hasattr(self, "pivot_fields_pane"):
            return
        from atboffice.modules.spreadsheet.calc.pivots import PivotReport

        if isinstance(report, PivotReport):
            self.pivot_fields_pane.bind_pivot_report(report, self.workbook)

    def _on_pivot_report_refreshed(self, report: Any | None = None) -> None:
        """Update viewport and dirty state after PivotTable recalculation."""
        self.set_modified(True)
        self.spreadsheet_view.grid.viewport().update()

    def evaluate_formula(self) -> None:
        """Step-by-step formula evaluation dialog."""
        sheet = self.spreadsheet_view.model
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        cell = sheet.get_cell(r, c)
        if cell is None or not cell.formula:
            QMessageBox.information(
                self,
                safe_tr("公式求值"),
                safe_tr("活动单元格不包含公式。"),
            )
            return

        from atboffice.modules.spreadsheet.dialogs.evaluate_formula_dialog import (
            EvaluateFormulaDialog,
        )

        workbook = getattr(self.spreadsheet_view, "workbook", None)
        dlg = EvaluateFormulaDialog(
            workbook=workbook,
            sheet=sheet,
            r=r,
            c=c,
            parent=self,
        )
        dlg.exec()

    def open_goal_seek(self) -> None:
        """Open Excel 2003 classic Goal Seek (单变量求解) dialog."""
        from atboffice.modules.spreadsheet.dialogs.goal_seek_dlg import GoalSeekDialog

        sheet = getattr(self.spreadsheet_view, "model", None)
        sel = getattr(self.spreadsheet_view, "selection", None)
        r, c = sel.active_cell if sel else (0, 0)
        workbook = getattr(self.spreadsheet_view, "workbook", None)

        dlg = GoalSeekDialog(
            workbook=workbook,
            current_sheet=sheet,
            initial_r=r,
            initial_c=c,
            parent=self,
        )
        if dlg.exec():
            self.spreadsheet_view.grid.viewport().update()
