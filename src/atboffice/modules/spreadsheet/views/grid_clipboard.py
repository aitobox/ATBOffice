"""Cut, copy, paste, Paste Special and moving ranges in the spreadsheet grid."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.calc.parser import parse, to_text
from atboffice.modules.spreadsheet.calc.references import (
    adjust_move,
    cell_name,
    map_ast,
    ref_err,
    translate,
    transpose_formula,
)
from atboffice.modules.spreadsheet.calc.tokens import CellRefNode
from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellComment,
    CellData,
)

if TYPE_CHECKING:
    pass


class GridClipboardMixin:
    """Clipboard commands and range moves."""

    def cut(self) -> None:
        """Cut selection to clipboard."""
        if self.guard_protect(cell_edit=True):
            return
        if (
            self.object_layer is not None
            and getattr(self.object_layer, "selected_object", None) is not None
        ):
            self.object_layer.copy_selected()
            self.object_layer.delete_selected()
            return

        self.copy()
        if self._internal_clipboard is not None:
            self._internal_clipboard["is_cut"] = True

    def copy(self) -> None:
        """Copy selection to clipboard using sparse boundaries."""
        if (
            self.object_layer is not None
            and getattr(self.object_layer, "selected_object", None) is not None
        ):
            self.object_layer.copy_selected()
            return

        pr = self.selection.primary_range
        # Calculate sparse bounds to prevent 10^6 iteration on whole column/row selection
        max_alloc_r = max(
            (r for (r, c) in self.model.cells.keys() if pr.min_c <= c <= pr.max_c),
            default=pr.min_r,
        )
        max_alloc_c = max(
            (c for (r, c) in self.model.cells.keys() if pr.min_r <= r <= pr.max_r),
            default=pr.min_c,
        )

        eff_max_r = min(pr.max_r, max(pr.min_r, max_alloc_r))
        eff_max_c = min(pr.max_c, max(pr.min_c, max_alloc_c))
        eff_range = SelectionRange(pr.min_r, pr.min_c, eff_max_r, eff_max_c)

        lines: list[str] = []
        for r in range(eff_range.min_r, eff_range.max_r + 1):
            row_vals: list[str] = []
            for c in range(eff_range.min_c, eff_range.max_c + 1):
                val = self.model.get_cell_value(r, c)
                row_vals.append("" if val is None else str(val))
            lines.append("\t".join(row_vals))
        tsv = "\n".join(lines)
        QApplication.clipboard().setText(tsv)

        col_widths = {
            c - pr.min_c: self.geometry_mapper.col_size(c)
            for c in range(eff_range.min_c, eff_range.max_c + 1)
        }

        copied_merges: list[dict[str, int]] = []
        for m in getattr(self.model, "merges", []):
            if hasattr(m, "min_r"):
                mr1, mc1, mr2, mc2 = m.min_r, m.min_c, m.max_r, m.max_c
            elif isinstance(m, (tuple, list)) and len(m) == 4:
                mr1, mc1, mr2, mc2 = m[0], m[1], m[2], m[3]
            elif isinstance(m, dict):
                mr1, mc1, mr2, mc2 = m.get("r1", 0), m.get("c1", 0), m.get("r2", 0), m.get("c2", 0)
            else:
                continue
            if mr1 >= pr.min_r and mr2 <= pr.max_r and mc1 >= pr.min_c and mc2 <= pr.max_c:
                copied_merges.append(
                    {
                        "r1": mr1 - pr.min_r,
                        "c1": mc1 - pr.min_c,
                        "r2": mr2 - pr.min_r,
                        "c2": mc2 - pr.min_c,
                    }
                )

        copied_comments: dict[tuple[int, int], Any] = {}
        if hasattr(self.model, "comments"):
            for (cr, cc), cm in self.model.comments.items():
                if pr.min_r <= cr <= pr.max_r and pr.min_c <= cc <= pr.max_c:
                    copied_comments[(cr - pr.min_r, cc - pr.min_c)] = (
                        CellComment(**cm.__dict__) if hasattr(cm, "__dict__") else cm
                    )

        self._internal_clipboard = {
            "range": pr,
            "effective_range": eff_range,
            "h": eff_range.max_r - eff_range.min_r + 1,
            "w": eff_range.max_c - eff_range.min_c + 1,
            "col_widths": col_widths,
            "merges": copied_merges,
            "comments": copied_comments,
            "cells": {
                (r - pr.min_r, c - pr.min_c): (
                    self.model.get_cell(r, c).clone() if self.model.get_cell(r, c) else None
                )
                for r in range(eff_range.min_r, eff_range.max_r + 1)
                for c in range(eff_range.min_c, eff_range.max_c + 1)
            },
            "is_cut": False,
        }

    def _clone_cells(
        self, scope: list[SelectionRange] | None, model: Any = None
    ) -> dict[tuple[int, int], CellData]:
        """Clones of the cells inside ``scope`` (every cell when ``scope`` is None)."""
        cells = (model or self.model).cells
        if scope is None:
            return {k: v.clone() for k, v in cells.items()}
        out: dict[tuple[int, int], CellData] = {}
        for rg in scope:
            area = (rg.max_r - rg.min_r + 1) * (rg.max_c - rg.min_c + 1)
            if area <= len(cells):
                for r in range(rg.min_r, rg.max_r + 1):
                    for c in range(rg.min_c, rg.max_c + 1):
                        cell = cells.get((r, c))
                        if cell is not None:
                            out[(r, c)] = cell.clone()
            else:
                for (r, c), cell in cells.items():
                    if rg.min_r <= r <= rg.max_r and rg.min_c <= c <= rg.max_c:
                        out[(r, c)] = cell.clone()
        return out

    def paste(self) -> None:
        """Paste clipboard content to active cell with undo support."""
        if self.guard_protect(cell_edit=True):
            return
        if (
            self.object_layer is not None
            and getattr(self.object_layer, "selected_object", None) is not None
        ):
            self.object_layer.paste()
            return

        before_state = self._snapshot_state()
        ar, ac = self.selection.active_cell
        if self._internal_clipboard:
            cells_data = self._internal_clipboard.get("cells", {})
            is_cut = self._internal_clipboard.get("is_cut", False)
            src_range = self._internal_clipboard.get("range")
            for (dr, dc), cell_copy in cells_data.items():
                target_r, target_c = ar + dr, ac + dc
                if cell_copy is not None:
                    cloned = cell_copy.clone()
                    if cloned.formula and src_range is not None:
                        shift_r = target_r - (src_range.min_r + dr)
                        shift_c = target_c - (src_range.min_c + dc)
                        cloned.formula = translate(cloned.formula, shift_r, shift_c)
                    self.model.set_cell(target_r, target_c, cloned)
                else:
                    self.model.set_cell(target_r, target_c, CellData())
            if is_cut and src_range:
                for r in range(src_range.min_r, src_range.max_r + 1):
                    for c in range(src_range.min_c, src_range.max_c + 1):
                        tr = ar + (r - src_range.min_r)
                        tc = ac + (c - src_range.min_c)
                        if not (
                            src_range.min_r <= tr <= src_range.max_r
                            and src_range.min_c <= tc <= src_range.max_c
                        ):
                            self.model.set_cell(r, c, CellData())
                self._internal_clipboard = None
        else:
            text = QApplication.clipboard().text()
            if text:
                rows = text.splitlines()
                for dr, row_str in enumerate(rows):
                    cols = row_str.split("\t")
                    for dc, cell_str in enumerate(cols):
                        val: Any = cell_str
                        try:
                            if "." in cell_str:
                                val = float(cell_str)
                            else:
                                val = int(cell_str)
                        except ValueError:
                            pass
                        self.model.set_cell_value(ar + dr, ac + dc, val)
        self._commit_undo(before_state, action="paste")

    def paste_special(self, options: dict[str, Any] | None = None) -> None:
        """Paste values / special options from clipboard with real business transformations."""
        if self.guard_protect(cell_edit=True):
            return

        if options is None:
            from atboffice.modules.spreadsheet.dialogs.paste_special_dialog import (
                PasteSpecialDialog,
            )

            dlg = PasteSpecialDialog(self)
            if not dlg.exec():
                return
            options = dlg.options

        # Ensure internal clipboard or fallback to parsed clipboard text
        if not self._internal_clipboard:
            text = QApplication.clipboard().text()
            if not text:
                return
            rows = text.splitlines()
            cells = {}
            for dr, row_str in enumerate(rows):
                for dc, cell_str in enumerate(row_str.split("\t")):
                    val: Any = cell_str
                    try:
                        if "." in cell_str:
                            val = float(cell_str)
                        else:
                            val = int(cell_str)
                    except ValueError:
                        pass
                    cells[(dr, dc)] = CellData(value=val)
            h = len(rows)
            w = max((len(r.split("\t")) for r in rows), default=1)
            self._internal_clipboard = {
                "range": SelectionRange(0, 0, h - 1, w - 1),
                "effective_range": SelectionRange(0, 0, h - 1, w - 1),
                "h": h,
                "w": w,
                "col_widths": {},
                "merges": [],
                "comments": {},
                "cells": cells,
                "is_cut": False,
            }

        before_state = self._snapshot_state()

        src_h = self._internal_clipboard.get("h", 1)
        src_w = self._internal_clipboard.get("w", 1)
        src_cells = self._internal_clipboard.get("cells", {})
        src_range = self._internal_clipboard.get("range", SelectionRange(0, 0, 0, 0))
        col_widths = self._internal_clipboard.get("col_widths", {})

        transpose = bool(options.get("transpose", False))
        skip_blanks = bool(options.get("skip_blanks", False))
        what = options.get("what") or options.get("type") or "all"
        raw_op = options.get("op") or options.get("operation") or "none"
        op = {
            "subtract": "sub",
            "multiply": "mul",
            "divide": "div",
        }.get(raw_op, raw_op)
        if op not in ("add", "sub", "mul", "div"):
            op = "none"

        is_link = bool(options.get("link", False) or what in ("paste_link", "link"))

        dest_h = src_w if transpose else src_h
        dest_w = src_h if transpose else src_w
        pr = self.selection.primary_range
        sel_h = pr.max_r - pr.min_r + 1
        sel_w = pr.max_c - pr.min_c + 1
        ar, ac = self.selection.active_cell

        # Selection tiling: if user selected multiple cells that form a multiple of source block
        if (sel_h > 1 or sel_w > 1) and (sel_h % dest_h == 0 and sel_w % dest_w == 0):
            tile_h = sel_h
            tile_w = sel_w
            start_r = pr.min_r
            start_c = pr.min_c
        else:
            tile_h = dest_h
            tile_w = dest_w
            start_r = ar
            start_c = ac

        # Special case: Column widths only
        if what == "colWidths":
            for j in range(tile_w):
                src_j = j % dest_w
                src_col_idx = 0 if transpose else src_j
                width = col_widths.get(src_col_idx)
                if width is not None:
                    self.geometry_mapper.set_col_width(start_c + j, width)
                    self.model.geometry.set_col_width(start_c + j, width)
            self._commit_undo(before_state, action="paste_special")
            self.viewport().update()
            return

        take_val = what in ("all", "values", "valuesNF", "allTheme")
        take_formula = what in (
            "all",
            "formulas",
            "noBorders",
            "allExceptBorders",
            "formulasNF",
            "allTheme",
        )
        take_format = what in (
            "all",
            "formats",
            "noBorders",
            "allExceptBorders",
            "allTheme",
        )
        take_nf = what in ("formulasNF", "valuesNF")

        def to_num(val: Any) -> float | int | None:
            if val is None or val == "":
                return 0
            if isinstance(val, (int, float)):
                return val
            try:
                s = str(val).strip()
                return float(s) if "." in s else int(s)
            except ValueError:
                return None

        for dr in range(tile_h):
            for dc in range(tile_w):
                block_r = dr % dest_h
                block_c = dc % dest_w
                if transpose:
                    src_i = block_c
                    src_j = block_r
                else:
                    src_i = block_r
                    src_j = block_c

                src_cell = src_cells.get((src_i, src_j))
                target_r = start_r + dr
                target_c = start_c + dc

                if skip_blanks and (
                    src_cell is None
                    or ((src_cell.value is None or src_cell.value == "") and not src_cell.formula)
                ):
                    continue

                curr_cell = self.model.get_cell(target_r, target_c)
                new_cell = curr_cell.clone() if curr_cell else CellData()

                if is_link:
                    src_abs_r = src_range.min_r + src_i
                    src_abs_c = src_range.min_c + src_j
                    sheet_name = getattr(self.model, "name", "")
                    sheet_ref = f"{sheet_name}!" if sheet_name else ""
                    ref_str = cell_name(src_abs_r, src_abs_c, False, False)
                    new_cell.formula = f"={sheet_ref}{ref_str}"
                    new_cell.value = None
                    self.model.set_cell(target_r, target_c, new_cell)
                    continue

                if what == "comments":
                    src_abs_r = src_range.min_r + src_i
                    src_abs_c = src_range.min_c + src_j
                    cm = self.model.get_comment(src_abs_r, src_abs_c)
                    if cm:
                        self.model.set_comment(target_r, target_c, cm.text, cm.author, cm.visible)
                    continue

                if what == "validation":
                    src_abs_r = src_range.min_r + src_i
                    src_abs_c = src_range.min_c + src_j
                    dv = self.model.get_validation_at(src_abs_r, src_abs_c)
                    if dv and hasattr(self.model, "add_data_validation"):
                        self.model.add_data_validation(dv)
                    continue

                if take_val or take_formula:
                    src_v = src_cell.value if src_cell else None
                    src_f = src_cell.formula if (src_cell and take_formula) else None

                    if src_f is not None:
                        src_abs_r = src_range.min_r + src_i
                        src_abs_c = src_range.min_c + src_j
                        if transpose:
                            src_f = transpose_formula(
                                src_f, src_abs_r, src_abs_c, target_r, target_c
                            )
                        else:
                            shift_r = target_r - src_abs_r
                            shift_c = target_c - src_abs_c
                            src_f = translate(src_f, shift_r, shift_c)

                    if op != "none":
                        cur_v = curr_cell.value if curr_cell else None
                        base_num = to_num(cur_v)
                        val_num = to_num(src_v)

                        if base_num is not None and val_num is not None:
                            if op == "add":
                                src_v = base_num + val_num
                            elif op == "sub":
                                src_v = base_num - val_num
                            elif op == "mul":
                                src_v = base_num * val_num
                            elif op == "div":
                                if val_num == 0:
                                    src_v = "#DIV/0!"
                                else:
                                    if (
                                        isinstance(base_num, int)
                                        and isinstance(val_num, int)
                                        and base_num % val_num == 0
                                    ):
                                        src_v = base_num // val_num
                                    else:
                                        src_v = base_num / val_num
                        elif val_num is not None and val_num == 0 and op == "div":
                            src_v = "#DIV/0!"

                        src_f = None

                    new_cell.value = src_v
                    new_cell.formula = src_f

                if take_format and src_cell is not None:
                    new_cell.font_family = src_cell.font_family
                    new_cell.font_size = src_cell.font_size
                    new_cell.bold = src_cell.bold
                    new_cell.italic = src_cell.italic
                    new_cell.underline = src_cell.underline
                    new_cell.fg_color = src_cell.fg_color
                    new_cell.bg_color = src_cell.bg_color
                    new_cell.align_h = src_cell.align_h
                    new_cell.align_v = src_cell.align_v
                    new_cell.format_code = src_cell.format_code
                    if what not in ("noBorders", "allExceptBorders"):
                        new_cell.border_top = src_cell.border_top
                        new_cell.border_bottom = src_cell.border_bottom
                        new_cell.border_left = src_cell.border_left
                        new_cell.border_right = src_cell.border_right

                if take_nf and src_cell is not None:
                    new_cell.format_code = src_cell.format_code

                self.model.set_cell(target_r, target_c, new_cell)

        # Merges
        copied_merges = self._internal_clipboard.get("merges", [])
        if copied_merges and (
            what in ("all", "formats", "allTheme", "noBorders", "allExceptBorders")
        ):
            new_merges = list(self.model.merges)
            for r0 in range(start_r, start_r + tile_h, dest_h):
                for c0 in range(start_c, start_c + tile_w, dest_w):
                    for m in copied_merges:
                        if transpose:
                            tr_rg = SelectionRange(
                                r0 + m["c1"],
                                c0 + m["r1"],
                                r0 + m["c2"],
                                c0 + m["r2"],
                            )
                        else:
                            tr_rg = SelectionRange(
                                r0 + m["r1"],
                                c0 + m["c1"],
                                r0 + m["r2"],
                                c0 + m["c2"],
                            )
                        new_merges.append(tr_rg)
            self.model.merges = new_merges

        # Comments
        copied_comments = self._internal_clipboard.get("comments", {})
        if copied_comments and (what in ("all", "comments")):
            for (ci, cj), cm in copied_comments.items():
                for r0 in range(start_r, start_r + tile_h, dest_h):
                    for c0 in range(start_c, start_c + tile_w, dest_w):
                        if transpose:
                            target_cr = r0 + cj
                            target_cc = c0 + ci
                        else:
                            target_cr = r0 + ci
                            target_cc = c0 + cj
                        self.model.set_comment(target_cr, target_cc, cm.text, cm.author, cm.visible)

        self.selection.select_cell(start_r, start_c)
        if tile_h > 1 or tile_w > 1:
            self.selection.extend_to(start_r + tile_h - 1, start_c + tile_w - 1)

        self._commit_undo(before_state, action="paste_special")
        self.viewport().update()

    def clear_contents(self) -> None:
        """Clear values and formulas in the current selection with sparse optimization."""
        if self.guard_protect(cell_edit=True):
            return
        if (
            self.object_layer is not None
            and getattr(self.object_layer, "selected_object", None) is not None
        ):
            self.object_layer.delete_selected()
            return

        before_state = self._snapshot_state()

        for rg in self.selection.ranges:
            total_cells = (rg.max_r - rg.min_r + 1) * (rg.max_c - rg.min_c + 1)
            if total_cells > len(self.model.cells):
                for (r, c), cell in list(self.model.cells.items()):
                    if rg.contains(r, c):
                        cell.value = None
                        cell.formula = None
            else:
                for r in range(rg.min_r, rg.max_r + 1):
                    for c in range(rg.min_c, rg.max_c + 1):
                        cell = self.model.get_cell(r, c)
                        if cell is not None:
                            cell.value = None
                            cell.formula = None

        self._commit_undo(before_state, action="clear_contents")

    def _holds_data(
        self,
        to_range: SelectionRange,
        except_range: SelectionRange | None = None,
    ) -> bool:
        """Check if any cell in to_range outside except_range holds a value or formula."""
        for r in range(to_range.min_r, to_range.max_r + 1):
            for c in range(to_range.min_c, to_range.max_c + 1):
                if except_range is not None and except_range.contains(r, c):
                    continue
                cell = self.model.get_cell(r, c)
                if cell is not None and (cell.value is not None or cell.formula is not None):
                    return True
        return False

    def move_range(
        self,
        src: SelectionRange,
        to: SelectionRange,
        copy: bool = False,
    ) -> bool:
        """Move or copy cell range src to to.

        Handles formulas, merges, comments, confirmation, and undo.
        """
        if self.guard_protect(cell_edit=True):
            return False

        if (
            src.min_r == to.min_r
            and src.min_c == to.min_c
            and src.max_r == to.max_r
            and src.max_c == to.max_c
        ):
            return True

        # Overwrite confirmation check
        except_rg = None if copy else src
        if self._holds_data(to, except_rg):
            ret = QMessageBox.question(
                self,
                safe_tr("ATBOffice Ledger"),
                safe_tr("是否替换目标单元格内容？"),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if ret != QMessageBox.StandardButton.Ok:
                return False

        # Snapshot state for undo/redo
        before_cells = {k: v.clone() for k, v in self.model.cells.items()}
        before_merges = list(self.model.merges)
        before_comments = (
            {k: CellComment(**v.__dict__) for k, v in self.model.comments.items()}
            if hasattr(self.model, "comments")
            else {}
        )
        before_sel = self.selection.snapshot()

        dr = to.min_r - src.min_r
        dc = to.min_c - src.min_c

        # Snapshot source cells
        src_cells: dict[tuple[int, int], CellData | None] = {}
        for r in range(src.min_r, src.max_r + 1):
            for c in range(src.min_c, src.max_c + 1):
                cl = self.model.get_cell(r, c)
                src_cells[(r - src.min_r, c - src.min_c)] = cl.clone() if cl else None

        # Snapshot source merges
        src_merges: list[tuple[int, int, int, int]] = [
            (
                m[0] - src.min_r,
                m[1] - src.min_c,
                m[2] - src.min_r,
                m[3] - src.min_c,
            )
            for m in self.model.merges
            if (m[0] >= src.min_r and m[2] <= src.max_r and m[1] >= src.min_c and m[3] <= src.max_c)
        ]

        # Snapshot source comments
        src_comments: dict[tuple[int, int], Any] = {}
        if hasattr(self.model, "comments"):
            for (r, c), cm in self.model.comments.items():
                if src.min_r <= r <= src.max_r and src.min_c <= c <= src.max_c:
                    src_comments[(r - src.min_r, c - src.min_c)] = cm

        if copy:
            # Remove merges overlapping destination
            self.model.merges = [
                m
                for m in self.model.merges
                if not (
                    max(m[0], to.min_r) <= min(m[2], to.max_r)
                    and max(m[1], to.min_c) <= min(m[3], to.max_c)
                )
            ]
            # Write cells to destination with translated formulas
            for (dr_i, dc_j), cell in src_cells.items():
                tr = to.min_r + dr_i
                tc = to.min_c + dc_j
                if cell is not None:
                    new_cell = cell.clone()
                    if new_cell.formula:
                        new_cell.formula = translate(new_cell.formula, dr, dc)
                    self.model.set_cell(tr, tc, new_cell)
                else:
                    self.model.set_cell(tr, tc, CellData())
            # Replicate merges
            for sm in src_merges:
                self.model.merges.append(
                    (
                        to.min_r + sm[0],
                        to.min_c + sm[1],
                        to.min_r + sm[2],
                        to.min_c + sm[3],
                    )
                )
            # Replicate comments
            if hasattr(self.model, "set_comment"):
                for (dr_i, dc_j), cm in src_comments.items():
                    self.model.set_comment(
                        to.min_r + dr_i,
                        to.min_c + dc_j,
                        text=cm.text,
                        author=cm.author,
                        visible=cm.visible,
                    )

        else:
            # Move
            sheet_name = getattr(self.model, "sheet_name", "Sheet1")
            src_dict = {
                "r1": src.min_r,
                "c1": src.min_c,
                "r2": src.max_r,
                "c2": src.max_c,
                "sheet": sheet_name,
            }

            # Update external formulas pointing to moved source or overwritten destination
            for (r, c), cell in list(self.model.cells.items()):
                if src.min_r <= r <= src.max_r and src.min_c <= c <= src.max_c:
                    continue
                if cell and cell.formula:
                    try:
                        ast = parse(cell.formula)

                        # Check if formula references overwritten cells in destination
                        def mapper_dest(n):
                            if isinstance(n, CellRefNode):
                                if (
                                    to.min_r <= n.r <= to.max_r
                                    and to.min_c <= n.c <= to.max_c
                                    and not (
                                        src.min_r <= n.r <= src.max_r
                                        and src.min_c <= n.c <= src.max_c
                                    )
                                ):
                                    return ref_err(n)
                            return None

                        ast_dest = map_ast(ast, mapper_dest)
                        if ast_dest is not None:
                            ast = ast_dest

                        new_ast, ch = adjust_move(
                            ast, src_dict, dr, dc, home=sheet_name, to_sheet=sheet_name
                        )
                        pref = "=" if cell.formula.startswith("=") else ""
                        cell.formula = pref + to_text(new_ast)
                    except Exception:
                        pass

            # Clear source cells that do not overlap destination
            for r in range(src.min_r, src.max_r + 1):
                for c in range(src.min_c, src.max_c + 1):
                    if not (to.min_r <= r <= to.max_r and to.min_c <= c <= to.max_c):
                        self.model.set_cell(r, c, CellData())

            # Write moved cells to destination
            for (dr_i, dc_j), cell in src_cells.items():
                tr = to.min_r + dr_i
                tc = to.min_c + dc_j
                if cell is not None:
                    new_cell = cell.clone()
                    if new_cell.formula:
                        try:
                            ast = parse(new_cell.formula)
                            new_ast, ch = adjust_move(
                                ast, src_dict, dr, dc, home=sheet_name, to_sheet=sheet_name
                            )
                            pref = "=" if new_cell.formula.startswith("=") else ""
                            new_cell.formula = pref + to_text(new_ast)
                        except Exception:
                            pass
                    self.model.set_cell(tr, tc, new_cell)
                else:
                    self.model.set_cell(tr, tc, CellData())

            # Remove source merges and destination overwritten merges
            self.model.merges = [
                m
                for m in self.model.merges
                if not (
                    (
                        m[0] >= src.min_r
                        and m[2] <= src.max_r
                        and m[1] >= src.min_c
                        and m[3] <= src.max_c
                    )
                    or (
                        max(m[0], to.min_r) <= min(m[2], to.max_r)
                        and max(m[1], to.min_c) <= min(m[3], to.max_c)
                    )
                )
            ]
            for sm in src_merges:
                self.model.merges.append(
                    (
                        to.min_r + sm[0],
                        to.min_c + sm[1],
                        to.min_r + sm[2],
                        to.min_c + sm[3],
                    )
                )

            # Move comments
            if hasattr(self.model, "comments"):
                for r in range(src.min_r, src.max_r + 1):
                    for c in range(src.min_c, src.max_c + 1):
                        if (r, c) in self.model.comments:
                            del self.model.comments[(r, c)]
                for (dr_i, dc_j), cm in src_comments.items():
                    self.model.set_comment(
                        to.min_r + dr_i,
                        to.min_c + dc_j,
                        text=cm.text,
                        author=cm.author,
                        visible=cm.visible,
                    )

        # Update selection
        self.selection.select_cell(to.min_r, to.min_c)
        self.selection.extend_to(to.max_r, to.max_c)

        # Record in undo stack
        after_cells = {k: v.clone() for k, v in self.model.cells.items()}
        after_merges = list(self.model.merges)
        after_comments = (
            {k: CellComment(**v.__dict__) for k, v in self.model.comments.items()}
            if hasattr(self.model, "comments")
            else {}
        )
        after_sel = self.selection.snapshot()

        self._record_entry(
            {
                "before_cells": before_cells,
                "before_merges": before_merges,
                "before_comments": before_comments,
                "before_sel": before_sel,
                "after_cells": after_cells,
                "after_merges": after_merges,
                "after_comments": after_comments,
                "after_sel": after_sel,
            }
        )
        self.viewport().update()
        return True
