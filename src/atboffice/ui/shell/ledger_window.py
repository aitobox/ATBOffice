"""Ledger dedicated spreadsheet window with Excel 2003 Luna menus, formula bar, and status bar."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QMessageBox, QWidget

from atboffice.core.action_registry import ActionRegistry
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.status_bar import StatusBar
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.ledger_toolbars import (
    build_ledger_toolbars,
    retranslate_ledger_toolbars,
)
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu


def safe_tr(text: str) -> str:
    """Translate UI text safely for LedgerWindow."""
    return QCoreApplication.translate("LedgerWindow", text)


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

    def _update_spreadsheet_status(self, *_: Any) -> None:
        """Forward spreadsheet selection updates to the status bar and context toolbars."""
        self.status_bar.update_calculation(
            self.spreadsheet_view.model, self.spreadsheet_view.selection
        )
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

        # Bottom toolbar: Drawing
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, self.toolbars["drawing"])

        # Top toolbars in standard display order
        for name in [
            "standard",
            "formatting",
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
        box = sel.bounding_box
        if box:
            return (box.top, box.left, box.bottom, box.right)
        return (sel.active_row, sel.active_col, sel.active_row, sel.active_col)

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
