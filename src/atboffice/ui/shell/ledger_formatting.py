"""Ledger window: Formatting toolbar, cell formats, borders and the Format Painter."""

from __future__ import annotations

import re

from PySide6.QtWidgets import QComboBox

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
)
from atboffice.ui.shell.ledger_common import (
    _cell_edit,
)


class LedgerFormattingMixin:
    """Formatting toolbar state and commands, number formats, borders and the Format Painter."""

    def _get_selected_cell_range(self) -> tuple[int, int, int, int]:
        sel = self.spreadsheet_view.selection
        pr = sel.primary_range
        if pr is not None:
            return (pr.min_r, pr.min_c, pr.max_r, pr.max_c)
        box = sel.bounding_box
        if box:
            return (box.top, box.left, box.bottom, box.right)
        r, c = sel.active_cell
        return (r, c, r, c)

    def _sync_formatting_toolbar_states(self) -> None:
        """Synchronize toolbar toggle buttons, combos, and status to the active cell format."""
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        model = self.spreadsheet_view.model
        cell = model.get_cell(r, c)
        if cell is None:
            cell = CellData()

        act_bold = self.action_registry.get_action("bold")
        if act_bold:
            act_bold.setChecked(bool(cell.bold))

        act_italic = self.action_registry.get_action("italic")
        if act_italic:
            act_italic.setChecked(bool(cell.italic))

        act_underline = self.action_registry.get_action("underline")
        if act_underline:
            act_underline.setChecked(bool(cell.underline))

        eff_h = cell.get_effective_align_h()
        is_left = eff_h == "left"
        is_center = eff_h == "center"
        is_right = eff_h == "right"

        act_left = self.action_registry.get_action("alignLeft")
        if act_left:
            act_left.setChecked(is_left)

        act_center = self.action_registry.get_action("alignCenter")
        if act_center:
            act_center.setChecked(is_center)

        act_right = self.action_registry.get_action("alignRight")
        if act_right:
            act_right.setChecked(is_right)

        act_merge = self.action_registry.get_action("mergeCenter")
        if act_merge:
            act_merge.setChecked(model.is_merged(r, c))

        fmt_tb = self.toolbars.get("formatting")
        if fmt_tb:
            font_combo = fmt_tb.findChild(QComboBox, "Ledger_FontCombo")
            if font_combo and cell.font_family:
                font_combo.blockSignals(True)
                font_combo.setCurrentText(cell.font_family)
                font_combo.blockSignals(False)

            size_combo = fmt_tb.findChild(QComboBox, "Ledger_SizeCombo")
            if size_combo and cell.font_size:
                size_combo.blockSignals(True)
                size_combo.setCurrentText(str(cell.font_size))
                size_combo.blockSignals(False)

        act_total = self.action_registry.get_action("totalRow")
        if act_total:
            act_total.setChecked(bool(getattr(self, "_total_row_active", False)))

        act_fp = self.action_registry.get_action("formatPainter")
        if act_fp:
            act_fp.setChecked(bool(getattr(self, "_format_painter_active", False)))

    @_cell_edit("format", scope="selection")
    def _apply_font_family(self, family: str) -> None:
        if not family:
            return
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.ensure_cell(r, c)
                cell.font_family = family
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    @_cell_edit("format", scope="selection")
    def _apply_font_size(self, size_str: str) -> None:
        try:
            pt = int(size_str.strip())
        except (ValueError, TypeError):
            return
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.ensure_cell(r, c)
                cell.font_size = pt
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    @staticmethod
    def _sync_zoom_combo(combo: QComboBox, zoom: float) -> None:
        """Show ``zoom`` in the zoom combo without re-applying it."""
        text = f"{round(zoom * 100)}%"
        if combo.currentText() == text:
            return
        combo.blockSignals(True)
        try:
            combo.setCurrentText(text)
        finally:
            combo.blockSignals(False)

    def _apply_zoom(self, zoom_text: str) -> None:
        if zoom_text.strip() in ("选定区域", safe_tr("选定区域"), "Selection"):
            commands = getattr(self, "ledger_commands", None)
            if commands is not None:
                commands.zoom_to_selection()
            return
        clean = zoom_text.replace("%", "").strip()
        try:
            val = float(clean) / 100.0
            if hasattr(self.spreadsheet_view, "grid") and hasattr(
                self.spreadsheet_view.grid, "set_zoom"
            ):
                self.spreadsheet_view.grid.set_zoom(val)
        except (ValueError, TypeError):
            pass

    @_cell_edit("format", scope="selection")
    def _toggle_bold(self) -> None:
        """Toggle bold formatting on selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        active_cell = model.get_cell(r1, c1) or CellData()
        new_val = not active_cell.bold
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.ensure_cell(r, c)
                cell.bold = new_val
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        if self.act_bold:
            self.act_bold.setChecked(new_val)
        self.set_modified(True)

    @_cell_edit("format", scope="selection")
    def _toggle_italic(self) -> None:
        """Toggle italic formatting on selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        active_cell = model.get_cell(r1, c1) or CellData()
        new_val = not active_cell.italic
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.ensure_cell(r, c)
                cell.italic = new_val
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        if self.act_italic:
            self.act_italic.setChecked(new_val)
        self.set_modified(True)

    @_cell_edit("format", scope="selection")
    def _toggle_underline(self) -> None:
        """Toggle underline formatting on selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        active_cell = model.get_cell(r1, c1) or CellData()
        new_val = not active_cell.underline
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.ensure_cell(r, c)
                cell.underline = new_val
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        if self.act_underline:
            self.act_underline.setChecked(new_val)
        self.set_modified(True)

    @_cell_edit("format", scope="selection")
    def set_horizontal_alignment(self, align: str) -> None:
        """Set horizontal text alignment for selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.ensure_cell(r, c)
                cell.align_h = align
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self._sync_formatting_toolbar_states()
        self.set_modified(True)

    @_cell_edit("format", scope="selection")
    def change_cell_indent(self, delta: int) -> None:
        """Increase or decrease cell text indentation level."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.ensure_cell(r, c)
                cur = getattr(cell, "indent", 0) or 0
                cell.indent = max(0, cur + delta)
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    @_cell_edit("merge", scope="selection")
    def toggle_merge_and_center(self) -> None:
        """Toggle merge and center formatting on selected cell range."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        act_merge = self.action_registry.get_action("mergeCenter")

        is_already_merged = False
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                if model.is_merged(r, c):
                    is_already_merged = True
                    break
            if is_already_merged:
                break

        if is_already_merged:
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    model.remove_merge(r, c)
            if act_merge:
                act_merge.setChecked(False)
        else:
            if r1 != r2 or c1 != c2:
                model.add_merge(r1, c1, r2, c2)
                for r in range(r1, r2 + 1):
                    for c in range(c1, c2 + 1):
                        cell = model.ensure_cell(r, c)
                        cell.align_h = "center"
                        model.set_cell(r, c, cell)
                if act_merge:
                    act_merge.setChecked(True)

        self.spreadsheet_view.grid.viewport().update()
        self._sync_formatting_toolbar_states()
        self.set_modified(True)

    @_cell_edit("format", scope="selection")
    def apply_number_format(self, format_code: str) -> None:
        """Apply number formatting code to selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.ensure_cell(r, c)
                cell.format_code = format_code
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    @staticmethod
    def _adjust_format_decimals(fmt: str | None, delta: int) -> str:
        """Adjust the number of decimal places in a number formatting code."""
        if not fmt or fmt == "General":
            if delta > 0:
                return "0." + "0" * delta
            return "General"

        m = re.search(r"\.(0+)", fmt)
        if m:
            cur_dec = len(m.group(1))
            new_dec = max(0, cur_dec + delta)
            if new_dec == 0:
                return fmt[: m.start()] + fmt[m.end() :]
            return fmt[: m.start()] + "." + ("0" * new_dec) + fmt[m.end() :]
        if delta > 0:
            if "%" in fmt:
                return fmt.replace("%", "." + ("0" * delta) + "%")
            return fmt + "." + ("0" * delta)
        return fmt

    @_cell_edit("format", scope="selection")
    def change_decimal_places(self, delta: int) -> None:
        """Increase or decrease visible decimal places for selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.ensure_cell(r, c)
                cur_fmt = cell.format_code or "General"
                new_fmt = self._adjust_format_decimals(cur_fmt, delta)
                cell.format_code = new_fmt
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    @_cell_edit("format", scope="selection")
    def apply_border_preset(self, preset: str) -> None:
        """Apply predefined border style preset to selected cell range."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model

        color = getattr(self, "last_border_color", None)
        thin = BorderStyle(style="thin", color=color)
        thick = BorderStyle(style="medium", color=color)
        double = BorderStyle(style="double", color=color)

        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                if cell is None:
                    cell = CellData()
                if preset == "none":
                    cell.border_top = None
                    cell.border_bottom = None
                    cell.border_left = None
                    cell.border_right = None
                elif preset == "all":
                    cell.border_top = thin
                    cell.border_bottom = thin
                    cell.border_left = thin
                    cell.border_right = thin
                elif preset == "outline":
                    if r == r1:
                        cell.border_top = thin
                    if r == r2:
                        cell.border_bottom = thin
                    if c == c1:
                        cell.border_left = thin
                    if c == c2:
                        cell.border_right = thin
                elif preset in ("thickOutline", "thickBox", "thick_box"):
                    if r == r1:
                        cell.border_top = thick
                    if r == r2:
                        cell.border_bottom = thick
                    if c == c1:
                        cell.border_left = thick
                    if c == c2:
                        cell.border_right = thick
                elif preset == "bottom":
                    if r == r2:
                        cell.border_bottom = thin
                elif preset == "thickBottom":
                    if r == r2:
                        cell.border_bottom = thick
                elif preset in ("bottomDouble", "bottom_double", "doubleBottom"):
                    if r == r2:
                        cell.border_bottom = double
                elif preset == "top":
                    if r == r1:
                        cell.border_top = thin
                elif preset == "left":
                    if c == c1:
                        cell.border_left = thin
                elif preset == "right":
                    if c == c2:
                        cell.border_right = thin
                model.set_cell(r, c, cell)

        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    @_cell_edit("format", scope="selection")
    def apply_border_color(self, color: str | None) -> None:
        """Apply border line color to existing borders of selected cells."""
        self.last_border_color = color
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                if cell:
                    for side in ("border_top", "border_bottom", "border_left", "border_right"):
                        b = getattr(cell, side, None)
                        if b is not None:
                            setattr(cell, side, BorderStyle(style=b.style, color=color))
                    model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    @_cell_edit("format", scope="selection")
    def _apply_font_color(self, color: str) -> None:
        """Apply font color to selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        fg = None if color == "auto" else color
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.ensure_cell(r, c)
                cell.fg_color = fg
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    @_cell_edit("format", scope="selection")
    def _apply_fill_color(self, color: str) -> None:
        """Apply fill background color to selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        bg = None if color in ("none", "auto") else color
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.ensure_cell(r, c)
                cell.bg_color = bg
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    def format_cells(self) -> None:
        """Open classic Format Cells dialog for the active spreadsheet grid."""
        if hasattr(self.spreadsheet_view, "grid") and hasattr(
            self.spreadsheet_view.grid, "open_format_cells_dialog"
        ):
            self.spreadsheet_view.grid.open_format_cells_dialog()

    def toggle_format_painter(self, double_click: bool = False) -> None:
        """Toggle format painter mode."""
        grid = getattr(self.spreadsheet_view, "grid", None)
        if not grid:
            return

        if getattr(self, "_format_painter_active", False):
            self._cancel_format_painter()
            return

        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        src_cell = model.get_cell(r1, c1) or CellData()

        self._format_painter_active = True
        self._format_painter_sticky = bool(double_click)
        self._format_painter_source = src_cell.clone()
        self.action_registry.set_checked("formatPainter", True)

        grid.set_format_painter_armed(self)
        self.statusBar().showMessage(safe_tr("请选择要应用格式的目标单元格或区域"), 5000)

    def _cancel_format_painter(self) -> None:
        """Cancel format painter state without altering any cells."""
        self._format_painter_active = False
        self._format_painter_sticky = False
        self._format_painter_source = None
        self.action_registry.set_checked("formatPainter", False)
        grid = getattr(self.spreadsheet_view, "grid", None)
        if grid:
            grid.set_format_painter_armed(None)
        self.statusBar().clearMessage()

    @_cell_edit("format_painter")
    def apply_format_painter_to_range(self, r1: int, c1: int, r2: int, c2: int) -> None:
        """Apply captured format painter styles to target range."""
        if not getattr(self, "_format_painter_active", False) or not self._format_painter_source:
            return
        model = self.spreadsheet_view.model
        grid = getattr(self.spreadsheet_view, "grid", None)
        src = self._format_painter_source
        before_cells = {k: v.clone() for k, v in model.cells.items()}

        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.ensure_cell(r, c)
                cell.bold = src.bold
                cell.italic = src.italic
                cell.underline = src.underline
                cell.underline_style = src.underline_style
                cell.strike = src.strike
                cell.vert_align = src.vert_align
                cell.font_size = src.font_size
                cell.font_family = src.font_family
                cell.fg_color = src.fg_color
                cell.bg_color = src.bg_color
                cell.align_h = src.align_h
                cell.align_v = src.align_v
                cell.indent = src.indent
                cell.wrap_text = src.wrap_text
                cell.format_code = src.format_code
                cell.border_top = src.border_top.clone() if src.border_top else None
                cell.border_bottom = src.border_bottom.clone() if src.border_bottom else None
                cell.border_left = src.border_left.clone() if src.border_left else None
                cell.border_right = src.border_right.clone() if src.border_right else None
                cell.border_diag_up = src.border_diag_up.clone() if src.border_diag_up else None
                cell.border_diag_down = (
                    src.border_diag_down.clone() if src.border_diag_down else None
                )
                cell.pattern = src.pattern
                cell.pattern_color = src.pattern_color
                cell.locked = src.locked
                cell.hidden = src.hidden
                model.set_cell(r, c, cell)

        if grid and hasattr(grid, "_record_entry"):
            grid._record_entry(
                {
                    "action": "format_painter",
                    "before_cells": before_cells,
                    "after_cells": {k: v.clone() for k, v in model.cells.items()},
                    "before_merges": list(model.merges),
                    "after_merges": list(model.merges),
                    "before_sel": grid.selection.snapshot(),
                    "after_sel": grid.selection.snapshot(),
                }
            )

        if grid:
            grid.viewport().update()
        self.set_modified(True)

        if not getattr(self, "_format_painter_sticky", False):
            self._cancel_format_painter()
