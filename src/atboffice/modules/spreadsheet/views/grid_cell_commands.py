"""Row, column, comment, hyperlink and format commands of the spreadsheet grid."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtGui import (
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QInputDialog,
)

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.calc.references import (
    cell_name,
)
from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellData,
)
from atboffice.modules.spreadsheet.views.autofill import AutoFillEngine

if TYPE_CHECKING:
    pass


class GridCellCommandsMixin:
    """Insert/delete/resize/hide rows and columns, comments, hyperlinks and format dialogs."""

    def fill_down_to_data(self) -> None:
        """Double click on fill handle: fill down as far as the adjacent column has data."""
        if len(self.selection.ranges) != 1:
            return
        if self.guard_protect(cell_edit=True):
            return

        src = self.selection.primary_range
        max_rows = self.geometry_mapper.max_rows

        def has_data(r: int, c: int) -> bool:
            cl = self.model.get_cell(r, c)
            return cl is not None and (cl.value is not None or cl.formula is not None)

        last = src.max_r
        # Probe left column first, then right column
        probe = -1
        if src.min_c > 0 and has_data(src.max_r + 1, src.min_c - 1):
            probe = src.min_c - 1
        elif has_data(src.max_r + 1, src.max_c + 1):
            probe = src.max_c + 1

        if probe < 0:
            return

        while (
            last + 1 < max_rows and has_data(last + 1, probe) and not has_data(last + 1, src.min_c)
        ):
            last += 1

        if last == src.max_r:
            return

        dest = SelectionRange(src.min_r, src.min_c, last, src.max_c)
        ctrl = False
        fill_mode = "copy" if ctrl else "auto"

        affected_coords = [
            (r, c) for r in range(src.min_r, last + 1) for c in range(src.min_c, src.max_c + 1)
        ]
        before_delta = {
            (r, c): (self.model.get_cell(r, c).clone() if self.model.get_cell(r, c) else None)
            for (r, c) in affected_coords
        }
        before_sel = self.selection.snapshot()

        AutoFillEngine.auto_fill(
            self.model,
            src,
            dest,
            mode=fill_mode,
            ctrl_pressed=ctrl,
        )
        self.selection.select_cell(dest.min_r, dest.min_c)
        self.selection.extend_to(dest.max_r, dest.max_c)

        after_delta = {
            (r, c): (self.model.get_cell(r, c).clone() if self.model.get_cell(r, c) else None)
            for (r, c) in affected_coords
        }
        after_sel = self.selection.snapshot()

        self._record_entry(
            {
                "action": "autofill",
                "affected_coords": affected_coords,
                "before_delta_cells": before_delta,
                "after_delta_cells": after_delta,
                "before_sel": before_sel,
                "after_sel": after_sel,
            }
        )
        self.mark_dirty()
        if hasattr(self.model, "recalculate"):
            self.model.recalculate()
        elif hasattr(self, "workbook") and self.workbook and hasattr(self.workbook, "recalculate"):
            self.workbook.recalculate()
        self.viewport().update()

    def insert_selected_cols(self) -> None:
        """Insert columns to the left of the current selection."""
        with self.undoable_edit("insert_cols"):
            if self.guard_protect("insertColumns"):
                return
            pr = self.selection.primary_range
            c1, c2 = pr.min_c, pr.max_c
            count = c2 - c1 + 1
            new_cells: dict[tuple[int, int], CellData] = {}
            for (r, c), cell in self.model.cells.items():
                if c >= c1:
                    new_cells[(r, c + count)] = cell
                else:
                    new_cells[(r, c)] = cell
            self.model.cells = new_cells
            new_merges: list[tuple[int, int, int, int]] = []
            for mr1, mc1, mr2, mc2 in self.model.merges:
                if mc1 >= c1:
                    new_merges.append((mr1, mc1 + count, mr2, mc2 + count))
                elif mc2 >= c1:
                    new_merges.append((mr1, mc1, mr2, mc2 + count))
                else:
                    new_merges.append((mr1, mc1, mr2, mc2))
            self.model.merges = new_merges
            self.viewport().update()

    def delete_selected_cols(self) -> None:
        """Delete columns in the current selection."""
        with self.undoable_edit("delete_cols"):
            if self.guard_protect("deleteColumns"):
                return
            pr = self.selection.primary_range
            c1, c2 = pr.min_c, pr.max_c
            count = c2 - c1 + 1
            new_cells: dict[tuple[int, int], CellData] = {}
            for (r, c), cell in self.model.cells.items():
                if c1 <= c <= c2:
                    continue
                elif c > c2:
                    new_cells[(r, c - count)] = cell
                else:
                    new_cells[(r, c)] = cell
            self.model.cells = new_cells
            new_merges: list[tuple[int, int, int, int]] = []
            for mr1, mc1, mr2, mc2 in self.model.merges:
                if mc1 > c2:
                    new_merges.append((mr1, mc1 - count, mr2, mc2 - count))
                elif mc2 < c1:
                    new_merges.append((mr1, mc1, mr2, mc2))
            self.model.merges = new_merges
            self.viewport().update()

    def insert_selected_rows(self) -> None:
        """Insert rows above the current selection."""
        with self.undoable_edit("insert_rows"):
            if self.guard_protect("insertRows"):
                return
            pr = self.selection.primary_range
            r1, r2 = pr.min_r, pr.max_r
            count = r2 - r1 + 1
            new_cells: dict[tuple[int, int], CellData] = {}
            for (r, c), cell in self.model.cells.items():
                if r >= r1:
                    new_cells[(r + count, c)] = cell
                else:
                    new_cells[(r, c)] = cell
            self.model.cells = new_cells
            new_merges: list[tuple[int, int, int, int]] = []
            for mr1, mc1, mr2, mc2 in self.model.merges:
                if mr1 >= r1:
                    new_merges.append((mr1 + count, mc1, mr2 + count, mc2))
                elif mr2 >= r1:
                    new_merges.append((mr1, mc1, mr2 + count, mc2))
                else:
                    new_merges.append((mr1, mc1, mr2, mc2))
            self.model.merges = new_merges
            self.viewport().update()

    def delete_selected_rows(self) -> None:
        """Delete rows in the current selection."""
        with self.undoable_edit("delete_rows"):
            if self.guard_protect("deleteRows"):
                return
            pr = self.selection.primary_range
            r1, r2 = pr.min_r, pr.max_r
            count = r2 - r1 + 1
            new_cells: dict[tuple[int, int], CellData] = {}
            for (r, c), cell in self.model.cells.items():
                if r1 <= r <= r2:
                    continue
                elif r > r2:
                    new_cells[(r - count, c)] = cell
                else:
                    new_cells[(r, c)] = cell
            self.model.cells = new_cells
            new_merges: list[tuple[int, int, int, int]] = []
            for mr1, mc1, mr2, mc2 in self.model.merges:
                if mr1 > r2:
                    new_merges.append((mr1 - count, mc1, mr2 - count, mc2))
                elif mr2 < r1:
                    new_merges.append((mr1, mc1, mr2, mc2))
            self.model.merges = new_merges
            self.viewport().update()

    def set_col_width_dialog(self) -> None:
        """Show dialog to set column width for selected columns."""
        if self.guard_protect("formatColumns"):
            return
        pr = self.selection.primary_range
        curr = self.geometry_mapper.col_size(pr.min_c)
        val, ok = QInputDialog.getInt(
            self,
            safe_tr("列宽"),
            safe_tr("列宽(&C):"),
            curr,
            0,
            1000,
        )
        if ok:
            for c in range(pr.min_c, pr.max_c + 1):
                self.geometry_mapper.set_col_width(c, val)
            self._update_scrollbars()
            self.viewport().update()

    def set_row_height_dialog(self) -> None:
        """Show dialog to set row height for selected rows."""
        if self.guard_protect("formatRows"):
            return
        pr = self.selection.primary_range
        curr = self.geometry_mapper.row_size(pr.min_r)
        val, ok = QInputDialog.getInt(
            self,
            safe_tr("行高"),
            safe_tr("行高(&R):"),
            curr,
            0,
            409,
        )
        if ok:
            for r in range(pr.min_r, pr.max_r + 1):
                self.geometry_mapper.set_row_height(r, val)
            self._update_scrollbars()
            self.viewport().update()

    def autofit_selected_rows(self) -> None:
        """Autofit row heights for selected rows based on cell contents."""
        if self.guard_protect("formatRows"):
            return
        pr = self.selection.primary_range
        fm = QFontMetrics(self.font())
        default_h = 20
        for r in range(pr.min_r, pr.max_r + 1):
            max_h = default_h
            for c in range(min(100, self.selection.max_cols)):
                cell = self.model.get_cell(r, c)
                if cell is not None and cell.value is not None and str(cell.value) != "":
                    lines = str(cell.value).split("\n")
                    needed_h = max(default_h, len(lines) * (fm.height() + 4) + 4)
                    if needed_h > max_h:
                        max_h = min(needed_h, 409)
            self.geometry_mapper.set_row_height(r, max_h)
        self._update_scrollbars()
        self.viewport().update()

    def autofit_selected_cols(self) -> None:
        """Autofit column widths for selected columns based on cell contents."""
        if self.guard_protect("formatColumns"):
            return
        pr = self.selection.primary_range
        fm = QFontMetrics(self.font())
        min_w = 40
        for c in range(pr.min_c, pr.max_c + 1):
            max_w = min_w
            for r in range(min(500, self.selection.max_rows)):
                cell = self.model.get_cell(r, c)
                if cell is not None and cell.value is not None and str(cell.value) != "":
                    val_str = str(getattr(cell, "formatted_value", None) or cell.value)
                    w = fm.horizontalAdvance(val_str) + 16
                    if w > max_w:
                        max_w = min(w, 500)
            self.geometry_mapper.set_col_width(c, max_w)
        self._update_scrollbars()
        self.viewport().update()

    def set_standard_col_width_dialog(self) -> None:
        """Show dialog to set standard column width."""
        if self.guard_protect("formatColumns"):
            return
        curr = 72
        val, ok = QInputDialog.getInt(
            self,
            safe_tr("标准列宽"),
            safe_tr("标准列宽(&S):"),
            curr,
            0,
            1000,
        )
        if ok:
            pr = self.selection.primary_range
            for c in range(pr.min_c, pr.max_c + 1):
                self.geometry_mapper.set_col_width(c, val)
            self._update_scrollbars()
            self.viewport().update()

    def hide_selected_cols(self) -> None:
        """Hide columns in current selection."""
        if self.guard_protect("formatColumns"):
            return
        pr = self.selection.primary_range
        for c in range(pr.min_c, pr.max_c + 1):
            self.geometry_mapper.hidden_cols.add(c)
        self._update_scrollbars()
        self.viewport().update()

    def unhide_selected_cols(self) -> None:
        """Unhide columns in and around current selection."""
        if self.guard_protect("formatColumns"):
            return
        pr = self.selection.primary_range
        start = max(0, pr.min_c - 1)
        end = min(self.selection.max_cols - 1, pr.max_c + 1)
        for c in range(start, end + 1):
            self.geometry_mapper.hidden_cols.discard(c)
        self._update_scrollbars()
        self.viewport().update()

    def hide_selected_rows(self) -> None:
        """Hide rows in current selection."""
        if self.guard_protect("formatRows"):
            return
        pr = self.selection.primary_range
        for r in range(pr.min_r, pr.max_r + 1):
            self.geometry_mapper.hidden_rows.add(r)
        self._update_scrollbars()
        self.viewport().update()

    def unhide_selected_rows(self) -> None:
        """Unhide rows in and around current selection."""
        if self.guard_protect("formatRows"):
            return
        pr = self.selection.primary_range
        start = max(0, pr.min_r - 1)
        end = min(self.selection.max_rows - 1, pr.max_r + 1)
        for r in range(start, end + 1):
            self.geometry_mapper.hidden_rows.discard(r)
        self._update_scrollbars()
        self.viewport().update()

    def insert_cells_dialog(self) -> None:
        """Insert cells shifting down in current column span."""
        if self.guard_protect("insertRows"):
            return
        pr = self.selection.primary_range
        count = pr.max_r - pr.min_r + 1
        new_cells: dict[tuple[int, int], CellData] = {}
        for (r, c), cell in self.model.cells.items():
            if pr.min_c <= c <= pr.max_c and r >= pr.min_r:
                new_cells[(r + count, c)] = cell
            else:
                new_cells[(r, c)] = cell
        self.model.cells = new_cells
        self.viewport().update()

    def delete_cells_dialog(self) -> None:
        """Delete cells shifting up in current column span."""
        if self.guard_protect("deleteRows"):
            return
        pr = self.selection.primary_range
        count = pr.max_r - pr.min_r + 1
        new_cells: dict[tuple[int, int], CellData] = {}
        for (r, c), cell in self.model.cells.items():
            if pr.min_c <= c <= pr.max_c:
                if pr.min_r <= r <= pr.max_r:
                    continue
                elif r > pr.max_r:
                    new_cells[(r - count, c)] = cell
                else:
                    new_cells[(r, c)] = cell
            else:
                new_cells[(r, c)] = cell
        self.model.cells = new_cells
        self.viewport().update()

    def insert_comment(self, r: int, c: int) -> None:
        """Insert a comment on cell (r, c)."""
        if self.guard_protect(cell_edit=True):
            return
        text, ok = QInputDialog.getMultiLineText(
            self, safe_tr("插入批注"), safe_tr("批注内容:"), ""
        )
        if ok and text:
            self.model.set_comment(r, c, text, visible=True)
            self.viewport().update()

    def edit_comment(self, r: int, c: int) -> None:
        """Edit existing comment on cell (r, c)."""
        if self.guard_protect(cell_edit=True):
            return
        cm = self.model.get_comment(r, c)
        curr = cm.text if cm else ""
        text, ok = QInputDialog.getMultiLineText(
            self, safe_tr("编辑批注"), safe_tr("批注内容:"), curr
        )
        if ok:
            self.model.set_comment(r, c, text, visible=True)
            self.viewport().update()

    def delete_comment(self, r: int, c: int) -> None:
        """Delete comment on cell (r, c)."""
        if self.guard_protect(cell_edit=True):
            return
        self.model.delete_comment(r, c)
        self.viewport().update()

    def toggle_comment_visibility(self, r: int, c: int) -> None:
        """Toggle comment visibility on cell (r, c)."""
        cm = self.model.get_comment(r, c)
        if cm:
            cm.visible = not cm.visible
            self.viewport().update()

    def _has_hyperlink(self, r: int, c: int) -> bool:
        """Check whether cell (r, c) contains a hyperlink."""
        links = getattr(self.model, "links", [])

        cname = cell_name(r, c)
        for link_item in links:
            if isinstance(link_item, dict) and (
                link_item.get("ref") == cname
                or (link_item.get("r") == r and link_item.get("c") == c)
            ):
                return True
        return False

    def insert_hyperlink(self, r: int, c: int) -> None:
        """Insert hyperlink into cell (r, c)."""
        win = self.window()
        if hasattr(win, "insert_hyperlink"):
            win.insert_hyperlink()
        else:
            url, ok = QInputDialog.getText(self, safe_tr("插入超链接"), safe_tr("地址(&E):"))
            if ok and url:
                links = getattr(self.model, "links", [])
                links.append({"r": r, "c": c, "target": url})
                self.viewport().update()

    def edit_hyperlink(self, r: int, c: int) -> None:
        """Edit hyperlink in cell (r, c)."""
        self.insert_hyperlink(r, c)

    def open_hyperlink(self, r: int, c: int) -> None:
        """Open hyperlink in cell (r, c)."""
        links = getattr(self.model, "links", [])

        cname = cell_name(r, c)
        target = None
        for link_item in links:
            if isinstance(link_item, dict) and (
                link_item.get("ref") == cname
                or (link_item.get("r") == r and link_item.get("c") == c)
            ):
                target = link_item.get("target")
                break
        if target:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl(target))

    def remove_hyperlink(self, r: int, c: int) -> None:
        """Remove hyperlink from cell (r, c)."""
        links = getattr(self.model, "links", [])

        cname = cell_name(r, c)
        self.model.links = [
            link_item
            for link_item in links
            if not (
                isinstance(link_item, dict)
                and (
                    link_item.get("ref") == cname
                    or (link_item.get("r") == r and link_item.get("c") == c)
                )
            )
        ]
        self.viewport().update()

    def open_format_object_dialog(self, obj: Any) -> None:
        """Open formatting dialog for the selected floating object."""
        win = self.window()
        if hasattr(win, "format_object"):
            win.format_object()

    def open_format_cells_dialog(self, initial_tab: int = 0) -> None:
        """Open the classic 6-tab Format Cells dialog for the active selection."""
        from atboffice.modules.spreadsheet.dialogs.format_cells import (
            FormatCellsDialog,
        )

        r, c = self.selection.active_cell
        target = self.model.get_cell(r, c)
        dlg = FormatCellsDialog(
            target_cell=target,
            model=self.model,
            selection=self.selection,
            initial_tab=initial_tab,
            parent=self,
        )
        if dlg.exec():
            self.viewport().update()
            # If top-level window has set_modified, flag it
            top = self.window()
            if hasattr(top, "set_modified"):
                top.set_modified(True)
