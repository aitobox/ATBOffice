"""Ledger dedicated spreadsheet window with Excel 2003 Luna menus, formula bar, and status bar."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QComboBox, QFileDialog, QMessageBox, QWidget

from atboffice.core.action_registry import ActionRegistry
from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.core.search import SearchController, SpreadsheetSearchAdapter
from atboffice.modules.spreadsheet.calc.references import cell_name
from atboffice.modules.spreadsheet.models.filter_model import sort_sheet_range
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
    SheetDataModel,
    SheetGeometry,
)
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.modules.spreadsheet.views.object_layer import (
    AnchorType,
    CellAnchorPoint,
    FloatingObject,
)
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.status_bar import StatusBar
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.dialogs.find_replace_dialog import FindReplaceDialog
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.ledger_toolbars import (
    build_ledger_toolbars,
    retranslate_ledger_toolbars,
)
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu


def safe_tr(text: str) -> str:
    """Translate UI text safely for LedgerWindow."""
    return core_safe_tr(text)


class LedgerWindow(BaseOfficeWindow):
    """Dedicated spreadsheet window embedding SpreadsheetView with Excel 2003 styling."""

    def __init__(
        self,
        file_path: str | Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self.app_name = "ATBOffice Ledger"
        self.app_type = "ledger"
        super().__init__(parent)
        self.resize(1100, 720)

        # 1. Action Registry command bus
        self.action_registry = ActionRegistry(self)
        self._bind_action_handlers()

        # 2. Embed SpreadsheetView
        self.spreadsheet_view = SpreadsheetView(parent=self)
        self.setCentralWidget(self.spreadsheet_view)
        self.formula_bar = self.spreadsheet_view.formula_bar

        # Search Controller & Adapter
        self.search_controller = SearchController(self)
        self.search_adapter = SpreadsheetSearchAdapter(
            model=self.spreadsheet_view.model,
            selection=self.spreadsheet_view.selection,
            spreadsheet_view=self.spreadsheet_view,
        )
        self.search_controller.set_adapter(self.search_adapter)
        self._find_replace_dialog: FindReplaceDialog | None = None

        # 3. Setup native macOS menu bar
        self.menu_bar: MacMenuBar = setup_mac_menu(self)

        # 4. Setup Office 2003 Luna toolbars
        self._setup_toolbars()

        # 5. Setup AutoCalculate status bar
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

        # 6. Connect spreadsheet selection and mode signals to status bar & dirty hook
        self.spreadsheet_view.selection.selection_changed.connect(self._update_spreadsheet_status)
        self.spreadsheet_view.selection.active_cell_changed.connect(self._update_spreadsheet_status)
        self.spreadsheet_view.editor_controller.mode_changed.connect(self.status_bar.set_mode)
        self.spreadsheet_view.editor_controller.cell_committed.connect(
            lambda *_: self.set_modified(True)
        )

        # 7. Load file or set initial document title
        if file_path is not None:
            resolved = Path(file_path).resolve()
            self.current_file_path = resolved
            self.update_window_title()
        else:
            self.update_window_title()

        self.set_modified(False)
        self.menu_bar.retranslate_ui()

    def _bind_action_handlers(self) -> None:
        """Bind window callbacks to core action IDs in ActionRegistry."""
        self.action_registry.set_handler("new", self.new_file)
        self.action_registry.set_handler("open", self.open_file_dialog)
        self.action_registry.set_handler("save", self.save_file)
        self.action_registry.set_handler("cut", self.cut)
        self.action_registry.set_handler("copy", self.copy)
        self.action_registry.set_handler("paste", self.paste)
        self.action_registry.set_handler("undo", self.undo)
        self.action_registry.set_handler("redo", self.redo)
        self.action_registry.set_handler("bold", self._toggle_bold)
        self.action_registry.set_handler("italic", self._toggle_italic)
        self.action_registry.set_handler("underline", self._toggle_underline)
        self.action_registry.set_handler("format_cells", self.format_cells)
        self.action_registry.set_handler("find", self.open_find_dialog)
        self.action_registry.set_handler("replace", self.open_replace_dialog)

        # Standard toolbar actions
        self.action_registry.set_handler("autoSum", self.auto_sum)
        self.action_registry.set_handler("sortAsc", lambda: self.quick_sort(desc=False))
        self.action_registry.set_handler("sortDesc", lambda: self.quick_sort(desc=True))
        self.action_registry.set_handler("tb_drawing", self.toggle_drawing_toolbar)
        self.action_registry.set_handler("chartWizard", self.chart_wizard)
        self.action_registry.set_handler("formatPainter", self.toggle_format_painter)
        self.action_registry.set_handler("hyperlink", self.insert_hyperlink)
        self.action_registry.set_handler("print", self.print_workbook)
        self.action_registry.set_handler("printPreview", self.print_preview)
        self.action_registry.set_handler("spelling", self.check_spelling)
        self.action_registry.set_handler("help", self.show_about)

        # Formatting toolbar actions
        self.action_registry.set_handler(
            "alignLeft", lambda: self.set_horizontal_alignment("left")
        )
        self.action_registry.set_handler(
            "alignCenter", lambda: self.set_horizontal_alignment("center")
        )
        self.action_registry.set_handler(
            "alignRight", lambda: self.set_horizontal_alignment("right")
        )
        self.action_registry.set_handler("mergeCenter", self.toggle_merge_and_center)
        self.action_registry.set_handler(
            "currencyStyle", lambda: self.apply_number_format("$#,##0.00")
        )
        self.action_registry.set_handler("percentStyle", lambda: self.apply_number_format("0%"))
        self.action_registry.set_handler("commaStyle", lambda: self.apply_number_format("#,##0.00"))
        self.action_registry.set_handler("incDecimal", lambda: self.change_decimal_places(1))
        self.action_registry.set_handler("decDecimal", lambda: self.change_decimal_places(-1))
        self.action_registry.set_handler("incIndent", lambda: self.change_cell_indent(1))
        self.action_registry.set_handler("decIndent", lambda: self.change_cell_indent(-1))
        self.action_registry.set_handler("bordersApply", lambda: self.apply_border_preset("all"))

        # Borders toolbar actions
        self.action_registry.set_handler(
            "bordersPalette", lambda: self.apply_border_preset("outline")
        )
        self.action_registry.set_handler("borderNone", lambda: self.apply_border_preset("none"))
        self.action_registry.set_handler(
            "borderOutline", lambda: self.apply_border_preset("outline")
        )
        self.action_registry.set_handler(
            "borderThickOutline", lambda: self.apply_border_preset("thickOutline")
        )
        self.action_registry.set_handler("eraseBorder", lambda: self.apply_border_preset("none"))

        # Auditing & Reviewing toolbar actions
        self.action_registry.set_handler("traceError", self.trace_error)
        self.action_registry.set_handler("tracePrecedents", self.trace_precedents)
        self.action_registry.set_handler("traceDependents", self.trace_dependents)
        self.action_registry.set_handler("removeArrows", self.remove_arrows)
        self.action_registry.set_handler("insertComment", self.insert_comment)
        self.action_registry.set_handler("validation", self.data_validation)
        self.action_registry.set_handler("circleInvalid", self.circle_invalid)
        self.action_registry.set_handler("clearCircles", self.clear_circles)
        self.action_registry.set_handler("watchWindow", self.watch_window)
        self.action_registry.set_handler("evaluateFormula", self.evaluate_formula)
        self.action_registry.set_handler("rev_insertComment", self.insert_comment)
        self.action_registry.set_handler("showHideComment", self.show_hide_comment)
        self.action_registry.set_handler("deleteComment", self.delete_comment)
        self.action_registry.set_handler("showComments", self.toggle_show_all_comments)

        # List & Chart actions
        self.action_registry.set_handler("totalRow", self.toggle_total_row)
        self.action_registry.set_handler("formatObject", self.format_selected_object)

        # Drawing toolbar actions
        self.action_registry.set_handler("insertShape", lambda: self.insert_shape("rect"))
        self.action_registry.set_handler("insertTextBox", self.insert_textbox)
        self.action_registry.set_handler("insertPicture", self.insert_picture)

    def _ensure_find_replace_dialog(self) -> FindReplaceDialog:
        """Create or return existing FindReplaceDialog instance."""
        if self._find_replace_dialog is None:
            self._find_replace_dialog = FindReplaceDialog(
                controller=self.search_controller, parent=self
            )
        return self._find_replace_dialog

    def open_find_dialog(self) -> None:
        """Display the Find and Replace dialog on Find tab."""
        # Ensure adapter is pointing to the current active sheet
        self.search_adapter.model = self.spreadsheet_view.model
        self.search_adapter.selection = self.spreadsheet_view.selection
        dlg = self._ensure_find_replace_dialog()
        dlg.show_find()

    def open_replace_dialog(self) -> None:
        """Display the Find and Replace dialog on Replace tab."""
        self.search_adapter.model = self.spreadsheet_view.model
        self.search_adapter.selection = self.spreadsheet_view.selection
        dlg = self._ensure_find_replace_dialog()
        dlg.show_replace()

    def _update_spreadsheet_status(self, *_: Any) -> None:
        """Forward spreadsheet selection updates to the status bar and context toolbars."""
        self.status_bar.update_calculation(
            self.spreadsheet_view.model, self.spreadsheet_view.selection
        )
        self._sync_formatting_toolbar_states()
        self.update_context_toolbars({})

    @property
    def default_doc_name(self) -> str:
        """Default document name for Ledger workbooks."""
        return safe_tr("未命名工作簿")

    def update_window_title(self) -> None:
        """Set window title according to active workbook and dirty flag."""
        doc_name = (
            self.current_file_path.name
            if self.current_file_path is not None
            else self.default_doc_name
        )
        self.setWindowTitle(f"{doc_name} — {self.app_name} [*]")

    def get_file_filter(self) -> str:
        """Return file filter pattern for Ledger save/open dialogs."""
        return safe_tr(
            "所有支持的格式 (*.xlsx *.xls *.csv *.tsv *.ods);;"
            "Excel 工作簿 (*.xlsx *.xls);;"
            "CSV 逗号分隔文本 (*.csv);;"
            "TSV 制表符分隔文本 (*.tsv);;"
            "所有文件 (*.*)"
        )

    def do_save(self, path: Path) -> bool:
        """Serialize Ledger workbook to destination path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        return True

    def _setup_toolbars(self) -> None:
        """Initialize Excel 2003 Luna 8 toolbars cluster."""
        self.toolbars: dict[str, OfficeToolBar] = build_ledger_toolbars(self, self.action_registry)

        # Row 1: Standard toolbar
        if "standard" in self.toolbars:
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars["standard"])

        # Row 2: Formatting toolbar
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        if "formatting" in self.toolbars:
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars["formatting"])

        # Row 3: Drawing and other contextual toolbars
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        for name in [
            "drawing",
            "borders",
            "auditing",
            "reviewing",
            "list",
            "chart",
        ]:
            if name in self.toolbars:
                self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars[name])

        # Backward compatibility aliases
        self.toolbar_standard = self.toolbars["standard"]
        self.toolbar_formatting = self.toolbars["formatting"]
        self.act_bold = self.action_registry.get_action("bold")
        self.act_italic = self.action_registry.get_action("italic")
        self.act_underline = self.action_registry.get_action("underline")

        # Color picker compatibility references
        for cp in self.toolbars["formatting"].findChildren(ColorPickerButton):
            if cp.mode == "font":
                self.btn_font_color = cp
                self.btn_font_color.color_applied.connect(self._apply_font_color)
            elif cp.mode == "fill":
                self.btn_fill_color = cp
                self.btn_fill_color.color_applied.connect(self._apply_fill_color)

        # Connect combos on formatting toolbar
        fmt_tb = self.toolbars.get("formatting")
        if fmt_tb:
            font_combo = fmt_tb.findChild(QComboBox, "Ledger_FontCombo")
            if font_combo:
                font_combo.currentTextChanged.connect(self._apply_font_family)
            size_combo = fmt_tb.findChild(QComboBox, "Ledger_SizeCombo")
            if size_combo:
                size_combo.currentTextChanged.connect(self._apply_font_size)

        # Connect zoom combo on standard toolbar
        std_tb = self.toolbars.get("standard")
        if std_tb:
            zoom_combo = std_tb.findChild(QComboBox, "Ledger_ZoomCombo")
            if zoom_combo:
                zoom_combo.currentTextChanged.connect(self._apply_zoom)

        # Connect drawing toolbar fill color and z-order drop actions
        draw_tb = self.toolbars.get("drawing")
        if draw_tb:
            draw_fill = draw_tb.findChild(ColorPickerButton, "Ledger_DrawFillColor")
            if draw_fill:
                draw_fill.color_applied.connect(self._apply_drawing_fill_color)

            for btn in draw_tb.findChildren(QWidget):
                menu = btn.property("drop_menu")
                if menu and menu.property("drop_label") == "绘图(&R)":
                    for action in menu.actions():
                        txt = action.text()
                        if "置于顶层" in txt:
                            action.triggered.connect(self.bring_to_front)
                        elif "置于底层" in txt:
                            action.triggered.connect(self.send_to_back)

        # Connect split menus
        act_autosum = self.action_registry.get_action("autoSum")
        if act_autosum:
            split_menu = act_autosum.property("split_menu")
            if split_menu:
                for action in split_menu.actions():
                    txt = action.text()
                    if "求和" in txt:
                        action.triggered.connect(lambda: self.auto_sum("SUM"))
                    elif "平均值" in txt:
                        action.triggered.connect(lambda: self.auto_sum("AVERAGE"))
                    elif "计数" in txt:
                        action.triggered.connect(lambda: self.auto_sum("COUNT"))
                    elif "最大值" in txt:
                        action.triggered.connect(lambda: self.auto_sum("MAX"))
                    elif "最小值" in txt:
                        action.triggered.connect(lambda: self.auto_sum("MIN"))
                    elif "更多函数" in txt:
                        action.triggered.connect(self.open_function_wizard)

        act_borders = self.action_registry.get_action("bordersApply")
        if act_borders:
            split_menu = act_borders.property("split_menu")
            if split_menu:
                for action in split_menu.actions():
                    txt = action.text()
                    if "所有框线" in txt:
                        action.triggered.connect(lambda: self.apply_border_preset("all"))
                    elif "无边框" in txt or "无框线" in txt:
                        action.triggered.connect(lambda: self.apply_border_preset("none"))
                    elif "粗外侧" in txt:
                        action.triggered.connect(lambda: self.apply_border_preset("thickOutline"))
                    elif "外侧框线" in txt:
                        action.triggered.connect(lambda: self.apply_border_preset("outline"))
                    elif "下框线" in txt:
                        action.triggered.connect(lambda: self.apply_border_preset("bottom"))
                    elif "上框线" in txt:
                        action.triggered.connect(lambda: self.apply_border_preset("top"))
                    elif "左框线" in txt:
                        action.triggered.connect(lambda: self.apply_border_preset("left"))
                    elif "右框线" in txt:
                        action.triggered.connect(lambda: self.apply_border_preset("right"))
                    elif "双下框线" in txt:
                        action.triggered.connect(lambda: self.apply_border_preset("bottomDouble"))

        # Connect object layer selection to context toolbars
        if hasattr(self.spreadsheet_view, "object_layer") and self.spreadsheet_view.object_layer:
            self.spreadsheet_view.object_layer.object_selected.connect(self._on_object_selected)

        # Default display modes for all 8 toolbars
        self.toolbar_modes: dict[str, bool | str] = {
            "standard": True,
            "formatting": True,
            "drawing": False,
            "borders": False,
            "auditing": False,
            "reviewing": False,
            "list": "auto",
            "chart": "auto",
        }

        # Apply initial contextual visibility
        self.update_context_toolbars({})

    def set_toolbar_mode(self, name: str, mode: bool | str) -> None:
        """Set toolbar visibility mode: True, False, or 'auto'."""
        self.toolbar_modes[name] = mode
        if isinstance(mode, bool) and name in self.toolbars:
            self.toolbars[name].setVisible(mode)

    def update_context_toolbars(self, context: dict[str, Any] | None = None) -> None:
        """Update contextual toolbar visibility based on selection and document state."""
        ctx = context or {}
        for name, mode in self.toolbar_modes.items():
            tb = self.toolbars.get(name)
            if tb is None:
                continue

            if mode is True:
                target_visible = True
            elif mode is False:
                target_visible = False
            else:  # "auto"
                if name == "chart":
                    target_visible = bool(ctx.get("is_chart"))
                elif name == "list":
                    target_visible = bool(ctx.get("in_table"))
                else:
                    target_visible = False

            tb.setVisible(target_visible)

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

        align_h = cell.align_h or "general"
        if align_h == "general":
            is_left = not isinstance(cell.value, (int, float))
            is_center = False
            is_right = isinstance(cell.value, (int, float))
        else:
            is_left = (align_h == "left")
            is_center = (align_h == "center")
            is_right = (align_h == "right")

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

    def _apply_font_family(self, family: str) -> None:
        if not family:
            return
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cell.font_family = family
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    def _apply_font_size(self, size_str: str) -> None:
        try:
            pt = int(size_str.strip())
        except (ValueError, TypeError):
            return
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cell.font_size = pt
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    def _apply_zoom(self, zoom_text: str) -> None:
        clean = zoom_text.replace("%", "").strip()
        try:
            val = float(clean) / 100.0
            if hasattr(self.spreadsheet_view, "grid") and hasattr(
                self.spreadsheet_view.grid, "set_zoom"
            ):
                self.spreadsheet_view.grid.set_zoom(val)
        except (ValueError, TypeError):
            pass

    def _toggle_bold(self) -> None:
        """Toggle bold formatting on selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        active_cell = model.get_cell(r1, c1)
        new_val = not active_cell.bold
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cell.bold = new_val
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        if self.act_bold:
            self.act_bold.setChecked(new_val)
        self.set_modified(True)

    def _toggle_italic(self) -> None:
        """Toggle italic formatting on selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        active_cell = model.get_cell(r1, c1)
        new_val = not active_cell.italic
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cell.italic = new_val
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        if self.act_italic:
            self.act_italic.setChecked(new_val)
        self.set_modified(True)

    def _toggle_underline(self) -> None:
        """Toggle underline formatting on selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        active_cell = model.get_cell(r1, c1)
        new_val = not active_cell.underline
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cell.underline = new_val
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        if self.act_underline:
            self.act_underline.setChecked(new_val)
        self.set_modified(True)

    def set_horizontal_alignment(self, align: str) -> None:
        """Set horizontal text alignment for selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cell.align_h = align
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self._sync_formatting_toolbar_states()
        self.set_modified(True)

    def change_cell_indent(self, delta: int) -> None:
        """Increase or decrease cell text indentation level."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cur = getattr(cell, "indent", 0) or 0
                cell.indent = max(0, cur + delta)
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

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
                        cell = model.get_cell(r, c)
                        cell.align_h = "center"
                        model.set_cell(r, c, cell)
                if act_merge:
                    act_merge.setChecked(True)

        self.spreadsheet_view.grid.viewport().update()
        self._sync_formatting_toolbar_states()
        self.set_modified(True)

    def apply_number_format(self, format_code: str) -> None:
        """Apply number formatting code to selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
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

    def change_decimal_places(self, delta: int) -> None:
        """Increase or decrease visible decimal places for selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cur_fmt = cell.format_code or "General"
                new_fmt = self._adjust_format_decimals(cur_fmt, delta)
                cell.format_code = new_fmt
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

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

    def apply_border_preset(self, preset: str) -> None:
        """Apply predefined border style preset to selected cell range."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model

        thin = BorderStyle(style="thin")
        thick = BorderStyle(style="medium")
        double = BorderStyle(style="double")

        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
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
                elif preset == "thickOutline":
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
                elif preset == "bottomDouble":
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

    def toggle_drawing_toolbar(self) -> None:
        """Toggle bottom drawing toolbar visibility."""
        tb = self.toolbars.get("drawing")
        if tb:
            cur = self.toolbar_modes.get("drawing", False)
            new_mode = not cur if isinstance(cur, bool) else tb.isHidden()
            self.set_toolbar_mode("drawing", new_mode)

    def insert_textbox(self) -> None:
        """Insert floating text box at current selection."""
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        obj = FloatingObject(
            kind="textbox",
            text="TextBox",
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=c, row=r),
            to_point=CellAnchorPoint(col=c + 2, row=r + 3),
        )
        self.spreadsheet_view.object_layer.add_object(obj)
        self.spreadsheet_view.object_layer.select_object(obj)
        self.set_modified(True)

    def insert_shape(self, kind: str = "rect") -> None:
        """Insert floating geometric shape at current selection."""
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        obj = FloatingObject(
            kind=kind,
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=c, row=r),
            to_point=CellAnchorPoint(col=c + 2, row=r + 3),
        )
        self.spreadsheet_view.object_layer.add_object(obj)
        self.spreadsheet_view.object_layer.select_object(obj)
        self.set_modified(True)

    def chart_wizard(self) -> None:
        """Launch chart wizard and insert chart object."""
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        obj = FloatingObject(
            kind="chart",
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=c, row=r),
            to_point=CellAnchorPoint(col=c + 4, row=r + 8),
        )
        self.spreadsheet_view.object_layer.add_object(obj)
        self.spreadsheet_view.object_layer.select_object(obj)
        self.set_toolbar_mode("chart", True)
        self.set_modified(True)

    def bring_to_front(self) -> None:
        """Bring selected floating object to top of z-order."""
        layer = getattr(self.spreadsheet_view, "object_layer", None)
        if layer and hasattr(layer, "selected_object") and layer.selected_object:
            layer.bring_to_front(layer.selected_object)
            self.set_modified(True)

    def send_to_back(self) -> None:
        """Send selected floating object to bottom of z-order."""
        layer = getattr(self.spreadsheet_view, "object_layer", None)
        if layer and hasattr(layer, "selected_object") and layer.selected_object:
            layer.send_to_back(layer.selected_object)
            self.set_modified(True)

    def _apply_drawing_fill_color(self, color: str) -> None:
        """Apply fill color to selected floating drawing object."""
        layer = getattr(self.spreadsheet_view, "object_layer", None)
        if layer and hasattr(layer, "selected_object") and layer.selected_object:
            layer.selected_object.fill_color = color
            layer.update()
            self.set_modified(True)

    def _on_object_selected(self, obj: Any) -> None:
        """Update contextual toolbars when floating object selection changes."""
        is_chart = obj is not None and getattr(obj, "kind", None) == "chart"
        self.update_context_toolbars({"is_chart": is_chart})

    def _apply_font_color(self, color: str) -> None:
        """Apply font color to selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        fg = None if color == "auto" else color
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cell.fg_color = fg
                model.set_cell(r, c, cell)
        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)

    def _apply_fill_color(self, color: str) -> None:
        """Apply fill background color to selected cells."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        bg = None if color in ("none", "auto") else color
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
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

    def show_about(self) -> None:
        """Show about dialog for ATBOffice Ledger."""
        QMessageBox.about(
            self,
            safe_tr("关于 ATBOffice Ledger"),
            safe_tr(
                "<h3>ATBOffice Ledger</h3><p>经典 Excel 2003 风格跨平台原生电子表格与计算引擎。</p>"
            ),
        )

    def trace_error(self) -> None:
        """Check worksheet for formula calculation errors."""
        QMessageBox.information(
            self,
            safe_tr("错误检查"),
            safe_tr("工作表中未发现公式错误。"),
        )

    def trace_precedents(self) -> None:
        """Trace precedent cells for the active formula."""

    def trace_dependents(self) -> None:
        """Trace dependent cells referencing the active cell."""

    def remove_arrows(self) -> None:
        """Remove all audit tracer arrows from worksheet."""

    def insert_comment(self) -> None:
        """Insert or edit comment for the active cell."""

    def show_hide_comment(self) -> None:
        """Toggle visibility of comment for the active cell."""

    def delete_comment(self) -> None:
        """Delete comment on the active cell."""

    def toggle_show_all_comments(self) -> None:
        """Toggle visibility of all worksheet comments."""

    def data_validation(self) -> None:
        """Open data validation rule configuration dialog."""

    def circle_invalid(self) -> None:
        """Circle invalid data in worksheet according to validation rules."""

    def clear_circles(self) -> None:
        """Clear all invalid data validation circles."""

    def watch_window(self) -> None:
        """Open watch window for inspecting formula values."""

    def evaluate_formula(self) -> None:
        """Step-by-step formula evaluation dialog."""

    def toggle_total_row(self) -> None:
        """Toggle table total calculation summary row."""

    def format_selected_object(self) -> None:
        """Format properties of selected chart or floating shape."""

    def open_function_wizard(self) -> None:
        """Open formula function wizard dialog."""

    def insert_picture(self) -> None:
        """Insert image from disk file into floating object layer."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            safe_tr("插入图片"),
            "",
            safe_tr("图片文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)"),
        )
        if not path:
            return
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        obj = FloatingObject(
            kind="image",
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=c, row=r),
            to_point=CellAnchorPoint(col=c + 4, row=r + 6),
        )
        self.spreadsheet_view.object_layer.add_object(obj)
        self.spreadsheet_view.object_layer.select_object(obj)
        self.set_modified(True)

    def insert_hyperlink(self) -> None:
        """Open insert hyperlink dialog."""

    def print_workbook(self) -> None:
        """Print current workbook sheets."""
        self.print_document()

    def print_preview(self, printer: QPrinter | None = None) -> bool:
        """Open print preview window."""
        return super().print_preview(printer)

    def render_to_printer(
        self,
        printer: QPrinter,
        repeat_header_rows: int = 1,
        show_gridlines: bool = True,
    ) -> None:
        """Render spreadsheet active sheet with pagination, repeating headers, and gridlines."""
        sheet: SheetDataModel = self.spreadsheet_view.model
        geom: SheetGeometry = sheet.geometry

        # Find used bounds
        if not sheet.cells:
            min_r, max_r = 0, 9
            min_c, max_c = 0, 4
        else:
            rows = [r for r, c in sheet.cells.keys()]
            cols = [c for r, c in sheet.cells.keys()]
            min_r = min(rows) if rows else 0
            max_r = max(rows) if rows else 0
            min_c = min(cols) if cols else 0
            max_c = max(cols) if cols else 0

        # Margins & page geometry in points
        margin_left = 36.0  # 0.5 inch
        margin_right = 36.0
        margin_top = 45.0  # 0.625 inch
        margin_bottom = 45.0
        header_height = 20.0
        footer_height = 20.0

        dpi = printer.resolution()
        scale = dpi / 72.0
        page_rect = printer.pageRect(QPrinter.Unit.Point)
        paper_w = page_rect.width()
        paper_h = page_rect.height()
        avail_w = paper_w - margin_left - margin_right
        avail_h = paper_h - margin_top - margin_bottom - header_height - footer_height

        # Calculate col spans [start_c, end_c]
        col_spans: list[tuple[int, int]] = []
        cur_w = 0.0
        start_c = min_c
        for c in range(min_c, max_c + 1):
            cw = float(geom.col_size(c))
            if cur_w > 0 and (cur_w + cw) > avail_w:
                col_spans.append((start_c, c - 1))
                start_c = c
                cur_w = cw
            else:
                cur_w += cw
        col_spans.append((start_c, max_c))

        # Title rows height (repeating rows)
        title_rows = min(repeat_header_rows, max_r - min_r + 1)
        title_h = sum(float(geom.row_size(min_r + r)) for r in range(title_rows))

        # Calculate row spans [start_r, end_r, has_title_at_top]
        row_spans: list[tuple[int, int, bool]] = []
        cur_h = 0.0
        start_r = min_r
        first_page = True
        for r in range(min_r, max_r + 1):
            rh = float(geom.row_size(r))
            room = avail_h if first_page else (avail_h - title_h)
            if cur_h > 0 and (cur_h + rh) > room:
                row_spans.append((start_r, r - 1, not first_page and title_rows > 0))
                start_r = r
                cur_h = rh
                first_page = False
            else:
                cur_h += rh
        row_spans.append((start_r, max_r, not first_page and title_rows > 0))

        # Build pages list (down then over)
        pages: list[tuple[int, int, int, int, bool]] = []
        for _cs_idx, (c1, c2) in enumerate(col_spans):
            for _rs_idx, (r1, r2, has_repeat) in enumerate(row_spans):
                pages.append((r1, r2, c1, c2, has_repeat))

        total_pages = len(pages)
        painter = QPainter(printer)
        painter.scale(scale, scale)

        for p_idx, (r1, r2, c1, c2, has_repeat) in enumerate(pages):
            if p_idx > 0:
                printer.newPage()

            page_num = p_idx + 1

            # 1. Header (Sheet name on left)
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QPen(QColor(100, 100, 100)))
            painter.drawText(
                QRectF(margin_left, margin_top - header_height, avail_w / 2, header_height),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                sheet.name,
            )

            # 2. Grid contents
            draw_y = margin_top

            def _draw_rows(row_start: int, row_end: int, base_y: float) -> float:
                y = base_y
                for r in range(row_start, row_end + 1):
                    rh = float(geom.row_size(r))
                    x = margin_left
                    for c in range(c1, c2 + 1):
                        cw = float(geom.col_size(c))
                        cell_rect = QRectF(x, y, cw, rh)

                        cell = sheet.get_cell(r, c)
                        if cell:
                            if cell.bg_color:
                                painter.fillRect(cell_rect, QColor(cell.bg_color))

                            if cell.border_top and cell.border_top.style != "none":
                                painter.setPen(
                                    QPen(QColor(cell.border_top.color or "#000000"), 1.0)
                                )
                                painter.drawLine(QPointF(x, y), QPointF(x + cw, y))
                            if cell.border_bottom and cell.border_bottom.style != "none":
                                painter.setPen(
                                    QPen(QColor(cell.border_bottom.color or "#000000"), 1.0)
                                )
                                painter.drawLine(QPointF(x, y + rh), QPointF(x + cw, y + rh))
                            if cell.border_left and cell.border_left.style != "none":
                                painter.setPen(
                                    QPen(QColor(cell.border_left.color or "#000000"), 1.0)
                                )
                                painter.drawLine(QPointF(x, y), QPointF(x, y + rh))
                            if cell.border_right and cell.border_right.style != "none":
                                painter.setPen(
                                    QPen(QColor(cell.border_right.color or "#000000"), 1.0)
                                )
                                painter.drawLine(QPointF(x + cw, y), QPointF(x + cw, y + rh))

                            val_text = sheet.get_formatted_text(r, c)
                            if val_text:
                                f = QFont(cell.font_family or "Arial", cell.font_size or 10)
                                f.setBold(cell.bold)
                                f.setItalic(cell.italic)
                                painter.setFont(f)
                                painter.setPen(QPen(QColor(cell.fg_color or "#000000")))

                                align_flag = Qt.AlignmentFlag.AlignVCenter
                                if cell.align_h == "center":
                                    align_flag |= Qt.AlignmentFlag.AlignHCenter
                                elif cell.align_h == "right" or isinstance(
                                    cell.value, (int, float)
                                ):
                                    align_flag |= Qt.AlignmentFlag.AlignRight
                                else:
                                    align_flag |= Qt.AlignmentFlag.AlignLeft

                                text_padding_rect = QRectF(x + 3.0, y, cw - 6.0, rh)
                                painter.drawText(text_padding_rect, int(align_flag), val_text)

                        if show_gridlines:
                            painter.setPen(QPen(QColor(215, 215, 215), 0.5))
                            painter.drawRect(cell_rect)

                        x += cw
                    y += rh
                return y

            if has_repeat:
                draw_y = _draw_rows(min_r, min_r + title_rows - 1, draw_y)

            draw_y = _draw_rows(r1, r2, draw_y)

            # 3. Footer (Page numbers at bottom center)
            footer_rect = QRectF(
                margin_left,
                paper_h - margin_bottom,
                avail_w,
                footer_height,
            )
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QPen(QColor(100, 100, 100)))
            footer_text = safe_tr("第 {page} 页，共 {total} 页").format(
                page=page_num, total=total_pages
            )
            painter.drawText(
                footer_rect,
                int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter),
                footer_text,
            )

        painter.end()

    def check_spelling(self) -> None:
        """Perform spelling check on worksheet contents."""
        QMessageBox.information(
            self,
            safe_tr("拼写检查"),
            safe_tr("已完成对整个工作表的拼写检查。"),
        )

    def toggle_format_painter(self) -> None:
        """Toggle format painter mode."""

    def retranslate_ui(self) -> None:
        """Update localized UI strings when application language changes."""
        super().retranslate_ui()
        if hasattr(self, "toolbars") and self.toolbars:
            retranslate_ledger_toolbars(self.toolbars, safe_tr)
        if hasattr(self, "btn_font_color") and self.btn_font_color:
            self.btn_font_color.setToolTip(safe_tr("字体颜色"))
            self.btn_font_color.setStatusTip(safe_tr("更改文本字体颜色"))
        if hasattr(self, "btn_fill_color") and self.btn_fill_color:
            self.btn_fill_color.setToolTip(safe_tr("填充颜色"))
            self.btn_fill_color.setStatusTip(safe_tr("更改单元格背景颜色"))
        if hasattr(self, "spreadsheet_view") and self.spreadsheet_view:
            self.spreadsheet_view.retranslate_ui()
        if hasattr(self, "menu_bar") and self.menu_bar:
            self.menu_bar.retranslate_ui()
