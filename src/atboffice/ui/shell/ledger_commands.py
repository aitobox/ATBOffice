"""Ledger menu & toolbar command bindings (Excel 2003 Edit/Insert/Format/Data/Tools).

``LedgerWindow`` owns the dialogs; this module reconciles the shared ``MacMenuBar`` IDs
with Ledger's handlers and implements the smaller commands that had no handler.
"""

from __future__ import annotations

import re
from html import escape
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.calc.references import abs_range_name, parse_cell
from atboffice.modules.spreadsheet.models.sheet_model import CellData

if TYPE_CHECKING:
    from atboffice.ui.shell.ledger_window import LedgerWindow


# Toolbar buttons that only open a drop-down menu.
CONTAINER_COMMANDS = ("list_menu", "chart_type_menu", "draw_menu", "border_line_color")
# Disabled placeholder rows shown in empty undo/redo drop-downs.
PLACEHOLDER_COMMANDS = ("undo_empty", "redo_empty")
GROUP_REASON = "请先选择多个图形对象再组合（多选功能将在后续版本提供）"

_NAME_RE = re.compile(r"^[A-Za-z_一-鿿\\][A-Za-z0-9_.一-鿿]*$")


class HeaderFooterDialog(QDialog):
    """Ledger Page Setup > Header/Footer text (centre section)."""

    def __init__(self, header: str = "", footer: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(safe_tr("页眉和页脚"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.edit_header = QLineEdit(header, self)
        self.edit_footer = QLineEdit(footer, self)
        self.edit_header.setPlaceholderText(safe_tr("例如：&[页码] / &[文件]"))
        form.addRow(safe_tr("页眉(&A):"), self.edit_header)
        form.addRow(safe_tr("页脚(&F):"), self.edit_footer)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str]:
        return self.edit_header.text(), self.edit_footer.text()


class LedgerCommands:
    """Implements and binds Ledger commands that the menu/toolbars expose."""

    def __init__(self, window: LedgerWindow) -> None:
        self.w = window

    # ---------------------------------------------------------------- helpers
    @property
    def view(self) -> Any:
        return self.w.spreadsheet_view

    @property
    def sheet(self) -> Any:
        return self.view.model

    @property
    def grid(self) -> Any:
        return getattr(self.view, "grid", None)

    def _range(self) -> tuple[int, int, int, int]:
        return self.w._get_selected_cell_range()

    def _cells_in(self, rect: tuple[int, int, int, int]) -> list[tuple[int, int]]:
        r1, c1, r2, c2 = rect
        return [k for k in self.sheet.cells if r1 <= k[0] <= r2 and c1 <= k[1] <= c2]

    # ---------------------------------------------------------------- Edit > Clear
    def clear_all(self) -> None:
        rect = self._range()

        def mutate() -> None:
            for key in self._cells_in(rect):
                self.sheet.cells.pop(key, None)
            for key in [k for k in self.sheet.comments if self._inside(k, rect)]:
                self.sheet.comments.pop(key, None)
            self.sheet.dirty = True

        self.w.run_cell_edit(mutate, "clear_all")

    def clear_formats(self) -> None:
        rect = self._range()

        def mutate() -> None:
            for key in self._cells_in(rect):
                old = self.sheet.cells[key]
                self.sheet.cells[key] = CellData(
                    value=old.value, formula=old.formula, cached_value=old.cached_value
                )
            self.sheet.dirty = True

        self.w.run_cell_edit(mutate, "clear_formats")

    def clear_contents(self) -> None:
        if self.grid is not None and hasattr(self.grid, "clear_contents"):
            self.grid.clear_contents()
            self.w.set_modified(True)

    def clear_comments(self) -> None:
        rect = self._range()

        def mutate() -> bool:
            keys = [k for k in self.sheet.comments if self._inside(k, rect)]
            for key in keys:
                self.sheet.comments.pop(key, None)
            return bool(keys)

        self.w.run_cell_edit(mutate, "clear_comments")

    @staticmethod
    def _inside(key: tuple[int, int], rect: tuple[int, int, int, int]) -> bool:
        return rect[0] <= key[0] <= rect[2] and rect[1] <= key[1] <= rect[3]

    def select_all(self) -> None:
        if self.grid is not None:
            self.grid.selection.select_all()
            self.grid.viewport().update()

    # ---------------------------------------------------------------- Insert
    def toggle_page_break(self) -> None:
        """Insert > Page Break above the active row (or remove an existing one)."""
        r, _c = self.view.selection.active_cell
        if r == 0:
            return
        breaks = self.sheet.view_state.row_breaks
        if r in breaks:
            breaks.remove(r)
        else:
            breaks.append(r)
            breaks.sort()
        self.sheet.dirty = True
        self.w._refresh_after_cell_edit()
        self.w.set_modified(True)

    def insert_symbol(self) -> None:
        from atboffice.modules.writer.dialogs.reference_dialogs import SymbolDialog

        dlg = SymbolDialog(parent=self.w)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        char = dlg.get_selected_character()
        if not char:
            return
        r, c = self.view.selection.active_cell

        def mutate() -> None:
            cell = self.sheet.ensure_cell(r, c)
            current = cell.value if isinstance(cell.value, str) and not cell.formula else ""
            cell.formula = None
            cell.value = f"{current}{char}"
            self.sheet.dirty = True

        self.w.run_cell_edit(mutate, "insert_symbol")

    def define_name(self, name: str | None = None) -> bool:
        """Insert > Name > Define for the current selection."""
        rect = self._range()
        ref = abs_range_name({"r1": rect[0], "c1": rect[1], "r2": rect[2], "c2": rect[3]})
        sheet_name = self.sheet.name
        quoted = sheet_name if re.fullmatch(r"\w+", sheet_name) else f"'{sheet_name}'"
        target = f"{quoted}!{ref}"
        if name is None:
            name, ok = QInputDialog.getText(
                self.w,
                safe_tr("定义名称"),
                safe_tr("在当前工作簿中的名称(&W)（引用位置：{0}）:").format(target),
            )
            if not ok:
                return False
        name = (name or "").strip()
        if not _NAME_RE.match(name) or parse_cell(name) is not None:
            QMessageBox.warning(
                self.w, safe_tr("定义名称"), safe_tr("输入的名称无效：{0}").format(name)
            )
            return False
        wb = self.view.workbook
        xml = wb.extra.get("defined_names") or "<definedNames></definedNames>"
        xml = re.sub(
            rf'<definedName\b[^>]*\bname="{re.escape(escape(name))}"[^>]*>.*?</definedName>',
            "",
            xml,
            flags=re.S | re.I,
        )
        entry = f'<definedName name="{escape(name)}">{escape(target)}</definedName>'
        xml = xml.replace("</definedNames>", entry + "</definedNames>", 1)
        wb.extra["defined_names"] = xml
        self.w.set_modified(True)
        return True

    # ---------------------------------------------------------------- View
    def header_footer(self) -> None:
        data = self.sheet.extra.get("header_footer") or {}
        dlg = HeaderFooterDialog(data.get("header", ""), data.get("footer", ""), self.w)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        header, footer = dlg.values()
        self.sheet.extra["header_footer"] = {"header": header, "footer": footer}
        self.w.set_modified(True)

    def zoom_to_selection(self) -> None:
        """Zoom combo "选定区域": fit the selected range into the visible grid."""
        grid = self.grid
        if grid is None:
            return
        r1, c1, r2, c2 = self._range()
        geom = self.sheet.geometry
        width = sum(geom.col_size(c) for c in range(c1, c2 + 1)) or 1
        height = sum(geom.row_size(r) for r in range(r1, r2 + 1)) or 1
        avail_w = max(1, grid.viewport().width() - getattr(grid, "row_header_width", 0))
        avail_h = max(1, grid.viewport().height() - getattr(grid, "col_header_height", 0))
        zoom = min(avail_w / width, avail_h / height, 4.0)
        grid.set_zoom(max(0.1, zoom))
        layer = getattr(self.view, "object_layer", None)
        if layer is not None and hasattr(layer, "set_zoom"):
            layer.set_zoom(grid.zoom)

    # ---------------------------------------------------------------- Format
    def auto_format(self, preset: str | None = None) -> None:
        from atboffice.modules.spreadsheet.tools.autoformat import apply_autoformat, preset_names

        names = preset_names()
        if preset is None:
            labels = [label for _, label in names]
            label, ok = QInputDialog.getItem(
                self.w, safe_tr("自动套用格式"), safe_tr("格式(&F):"), labels, 0, False
            )
            if not ok:
                return
            preset = next(pid for pid, lab in names if lab == label)
        rect = self.w._selection_or_region()
        self.w.run_cell_edit(lambda: apply_autoformat(self.sheet, rect, preset), "autoformat")

    def conditional_format(self) -> None:
        import copy as _copy

        from atboffice.modules.spreadsheet.dialogs.conditional_format_dialog import (
            ConditionalFormatDialog,
        )

        sheet = self.sheet
        rect = self._range()
        sqref = abs_range_name({"r1": rect[0], "c1": rect[1], "r2": rect[2], "c2": rect[3]})
        sqref = sqref.replace("$", "")
        existing = next((cf for cf in sheet.conditional_formats if list(cf.ranges) == [rect]), None)
        dlg = ConditionalFormatDialog(
            existing_cf=existing, sqref=sqref, ranges=[rect], parent=self.w
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        before_cfs = _copy.deepcopy(list(sheet.conditional_formats))
        before_cf_dirty = sheet.extra.get("cf_dirty")
        new_cf = dlg.get_conditional_format()
        if existing is not None:
            idx = sheet.conditional_formats.index(existing)
            sheet.conditional_formats[idx] = new_cf
        else:
            sheet.add_conditional_format(new_cf)
        sheet.extra["cf_dirty"] = True
        sheet.dirty = True
        after_cfs = _copy.deepcopy(list(sheet.conditional_formats))

        svc = self.w.undo_service() if hasattr(self.w, "undo_service") else None
        if svc is not None and svc.is_recording:
            grid = self.grid

            def _restore(snapshot: list[Any], cf_dirty_val: Any) -> None:
                if hasattr(grid, "_activate_sheet"):
                    grid._activate_sheet(sheet)
                sheet.conditional_formats = _copy.deepcopy(snapshot)
                if cf_dirty_val is None:
                    sheet.extra.pop("cf_dirty", None)
                else:
                    sheet.extra["cf_dirty"] = cf_dirty_val
                sheet.dirty = True
                self.w._refresh_after_cell_edit()
                self.w.set_modified(True)

            svc.record(
                safe_tr("条件格式"),
                lambda s=before_cfs, d=before_cf_dirty: _restore(s, d),
                lambda s=after_cfs: _restore(s, True),
            )

        self.w._refresh_after_cell_edit()
        self.w.set_modified(True)

    # ---------------------------------------------------------------- Drawing
    def draw_border(self) -> None:
        """Borders toolbar pen: draw an outside border around the selection."""
        self.w.apply_border_preset("outline")

    def ungroup(self) -> bool:
        """Split the selected group shape into independent, absolutely placed shapes."""
        from atboffice.modules.spreadsheet.models.sheet_model import SheetGeometry
        from atboffice.modules.spreadsheet.views.object_layer import AnchorType, object_to_rect
        from atboffice.modules.spreadsheet.views.object_painting import child_rect

        layer = getattr(self.view, "object_layer", None)
        obj = getattr(layer, "selected_object", None) if layer else None
        if obj is None or not obj.children:
            QMessageBox.information(self.w, safe_tr("取消组合"), safe_tr("请先选择一个组合图形。"))
            return False
        geom = self.sheet.geometry if self.sheet is not None else SheetGeometry()
        frame = object_to_rect(
            obj=obj,
            geometry=geom,
            scroll_x=0,
            scroll_y=0,
            row_header_width=0,
            col_header_height=0,
            freeze_rows=0,
            freeze_cols=0,
        )
        drawings = self.sheet.drawings
        idx = drawings.index(obj) if obj in drawings else len(drawings)
        pieces = []
        for child in obj.children:
            rect = child_rect(frame, child.group_frac)
            piece = child.clone()
            piece.group_frac = None
            piece.anchor_type = AnchorType.ABSOLUTE
            piece.abs_rect = (rect.x(), rect.y(), rect.width(), rect.height())
            piece.anchor_resolved = True
            piece.z_index = obj.z_index
            pieces.append(piece)
        layer.remove_object(obj)
        for offset, piece in enumerate(pieces):
            piece.id = max((o.id for o in drawings), default=0) + 1
            drawings.insert(min(idx + offset, len(drawings)), piece)
        layer.select_object(pieces[0] if pieces else None)
        layer.update()
        self.w.set_modified(True)
        return True

    # ---------------------------------------------------------------- Tools
    def check_spelling(self) -> None:
        from atboffice.modules.spreadsheet.dialogs.sheet_spelling_dialog import (
            SheetSpellingDialog,
        )
        from atboffice.modules.spreadsheet.tools.sheet_spelling import (
            SheetSpellChecker,
            text_cells,
        )
        from atboffice.modules.writer.spell import SpellEngine

        rect = self._range()
        scope = rect if (rect[0], rect[1]) != (rect[2], rect[3]) else None
        checker = SheetSpellChecker(
            self.sheet, text_cells(self.sheet, scope), SpellEngine.get_instance()
        )
        dlg = SheetSpellingDialog(checker, parent=self.w)
        if not dlg.start():
            QMessageBox.information(
                self.w, safe_tr("拼写检查"), safe_tr("已完成对整个工作表的拼写检查。")
            )
            return
        self.w._exec_cell_dialog(dlg, "spelling")

    # ---------------------------------------------------------------- outline / split
    def _outline_axis_and_span(self) -> tuple[str, int, int]:
        """Whole columns selected -> columns; otherwise the selected rows."""
        r1, c1, r2, c2 = self._range()
        geo = self.sheet.geometry
        if r1 == 0 and r2 >= geo.max_rows - 1 and not (c1 == 0 and c2 >= geo.max_cols - 1):
            return "col", c1, c2
        return "row", r1, r2

    def outline_group(self) -> None:
        from atboffice.modules.spreadsheet.models import outline

        axis, a, b = self._outline_axis_and_span()
        if not outline.group(self.sheet, axis, a, b):
            QMessageBox.information(self.w, safe_tr("组合"), safe_tr("分组最多只能有 7 级。"))
            return
        self.grid.outline_changed()

    def outline_ungroup(self) -> None:
        from atboffice.modules.spreadsheet.models import outline

        axis, a, b = self._outline_axis_and_span()
        if outline.ungroup(self.sheet, axis, a, b):
            self.grid.outline_changed()

    def outline_detail(self, show: bool) -> None:
        from atboffice.modules.spreadsheet.models import outline

        axis, a, _b = self._outline_axis_and_span()
        grp = outline.group_at(self.sheet, axis, a)
        if grp is None:
            QMessageBox.information(
                self.w, safe_tr("分级显示"), safe_tr("所选区域不在任何分组中。")
            )
            return
        outline.set_collapsed(self.sheet, axis, grp, not show)
        self.grid.outline_changed()

    def outline_clear(self) -> None:
        from atboffice.modules.spreadsheet.models import outline

        outline.clear(self.sheet, "row")
        outline.clear(self.sheet, "col")
        self.grid.outline_changed()

    def import_html(self, path: str | None = None) -> bool:
        """Data > Import web table: the first table of an HTML file at the active cell."""
        from PySide6.QtWidgets import QFileDialog

        from atboffice.modules.spreadsheet.io.html_io import import_table, read_html_file

        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self.w, safe_tr("导入网页表格"), "", safe_tr("网页 (*.html *.htm);;所有文件 (*.*)")
            )
            if not path:
                return False
        try:
            tables = read_html_file(path)
        except OSError as exc:
            QMessageBox.warning(self.w, safe_tr("导入网页表格"), str(exc))
            return False
        if not tables:
            QMessageBox.information(self.w, safe_tr("导入网页表格"), safe_tr("该网页中没有表格。"))
            return False
        at = self.view.selection.active_cell

        def mutate() -> None:
            import_table(self.sheet, tables[0], at)

        self.w.run_cell_edit(mutate, "paste")
        return True

    def toggle_split(self) -> None:
        split = self.w.spreadsheet_view.toggle_split()
        act = self.w.action_registry.get_action("windowSplit")
        if act is not None:
            act.setCheckable(True)
            act.setChecked(split)

    # ---------------------------------------------------------------- binding
    def bind(self) -> None:
        reg = self.w.action_registry
        w = self.w
        handlers: dict[str, Any] = {
            # MacMenuBar IDs that differ from Ledger's toolbar IDs
            "data_filter": w.toggle_auto_filter,
            "data_validation": w.data_validation,
            "insert_page_break": self.toggle_page_break,
            "insert_symbol": self.insert_symbol,
            "insert_shape": lambda: w.insert_shape("rect"),
            "format_font": lambda: self.grid.open_format_cells_dialog(2),
            "format_borders": lambda: self.grid.open_format_cells_dialog(3),
            "selectAll": self.select_all,
            "sortDlg": lambda: self.grid.open_sort_dialog(),
            # Ledger-only menu items
            "clearAll": self.clear_all,
            "clearFormats": self.clear_formats,
            "clearContents": self.clear_contents,
            "clearComments": self.clear_comments,
            "defineName": lambda: self.define_name(),
            "headerFooter": self.header_footer,
            "autoFormat": lambda: self.auto_format(),
            "condFormat": self.conditional_format,
            "showAllFilter": w.show_all_filtered_rows,
            "insertChart": w.open_chart_wizard,
            "spelling": self.check_spelling,
            "pageSetup": w.open_page_setup,
            "outlineGroup": self.outline_group,
            "outlineUngroup": self.outline_ungroup,
            "outlineHideDetail": lambda: self.outline_detail(False),
            "outlineShowDetail": lambda: self.outline_detail(True),
            "outlineClear": self.outline_clear,
            "importHtml": self.import_html,
            "windowSplit": self.toggle_split,
            # Toolbar buttons
            "drawBorder": self.draw_border,
            "draw_ungroup": self.ungroup,
        }
        for aid, handler in handlers.items():
            reg.set_handler(aid, handler)
        for aid in CONTAINER_COMMANDS:
            reg.register_whitelist_action(aid, kind="setMenu", reason="drop-down menu button")
        for aid in PLACEHOLDER_COMMANDS:
            reg.register_whitelist_action(aid, kind="abstract", reason="empty-history placeholder")
            reg.set_enabled(aid, False)
        spec = reg.get_spec("draw_group")
        if spec is not None:
            spec.disabled_reason = GROUP_REASON
        reg.set_enabled("draw_group", False)


def bind_ledger_commands(window: LedgerWindow) -> LedgerCommands:
    commands = LedgerCommands(window)
    commands.bind()
    return commands
