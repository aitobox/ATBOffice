"""macOS shell main window with workbook lifecycle management and dirty tracking."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QTabWidget

from atboffice.core.i18n import get_i18n_manager
from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.modules.presentation.view import PresentationView
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.modules.writer.view import WriterView
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.status_bar import StatusBar
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu
from atboffice.ui.styles.luna_2003 import apply_luna_theme


def safe_tr(text: str) -> str:
    """Translate UI text safely for MainWindow."""
    return core_safe_tr(text)


class MainWindow(QMainWindow):
    """Top-level shell window with native macOS HIG menu and workbook management."""

    def __init__(self) -> None:
        super().__init__()
        self.current_file_path: Path | None = None
        self._is_modified: bool = False

        self.resize(1100, 720)
        self._update_window_title()
        try:
            get_i18n_manager().locale_changed.connect(self._on_locale_changed)
        except Exception:
            pass

        # Core Office modules tab widget
        self.tabs = QTabWidget(self)
        self.writer_view = WriterView()
        self.spreadsheet_view = SpreadsheetView()
        self.presentation_view = PresentationView()

        self.tabs.addTab(self.writer_view, safe_tr("文字处理"))
        self.tabs.addTab(self.spreadsheet_view, safe_tr("电子表格"))
        self.tabs.addTab(self.presentation_view, safe_tr("演示文稿"))
        self.setCentralWidget(self.tabs)

        # Setup native macOS menu bar
        self.menu_bar: MacMenuBar = setup_mac_menu(self)

        # Setup Office 2003 Luna command toolbars
        self.current_theme = "blue"
        self._setup_toolbars()
        apply_luna_theme(self, self.current_theme)

        # Setup AutoCalculate status bar
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

        # Connect spreadsheet selection and mode to status bar
        self.spreadsheet_view.selection.selection_changed.connect(
            self._update_spreadsheet_status
        )
        self.spreadsheet_view.selection.active_cell_changed.connect(
            self._update_spreadsheet_status
        )
        self.spreadsheet_view.editor_controller.mode_changed.connect(
            self.status_bar.set_mode
        )
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _update_spreadsheet_status(self, *_: Any) -> None:
        """Forward spreadsheet selection updates to status bar."""
        if self.tabs.currentWidget() == self.spreadsheet_view:
            self.status_bar.update_calculation(
                self.spreadsheet_view.model, self.spreadsheet_view.selection
            )

    def _on_tab_changed(self, index: int) -> None:
        """Handle active module tab switch."""
        if self.tabs.widget(index) == self.spreadsheet_view:
            self._update_spreadsheet_status()
        else:
            self.status_bar.lbl_calc.setText("")

    @property
    def is_modified(self) -> bool:
        """Return whether the current document has unsaved modifications."""
        return self._is_modified

    def set_modified(self, modified: bool) -> None:
        """Update document dirty status and macOS window modified dot."""
        self._is_modified = modified
        self.setWindowModified(modified)
        self._update_window_title()

    def _update_window_title(self) -> None:
        """Set window title according to active document and dirty flag."""
        if self.current_file_path is not None:
            title = f"{self.current_file_path.name} — ATBOffice [*]"
        else:
            title = "ATBOffice [*]"
        self.setWindowTitle(title)

    def new_file(self) -> bool:
        """Create a new blank document, prompting to save changes if modified."""
        if not self._maybe_save_prompt():
            return False

        self.current_file_path = None
        self.set_modified(False)
        return True

    def open_file_dialog(self) -> bool:
        """Present standard file dialog to select and open a document."""
        filters = safe_tr(
            "所有支持的格式 (*.xlsx *.xls *.csv);;"
            "Excel 工作簿 (*.xlsx *.xls);;"
            "CSV 逗号分隔文本 (*.csv);;"
            "所有文件 (*.*)"
        )
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            safe_tr("打开工作簿"),
            "",
            filters,
        )
        if file_path:
            return self.open_file(file_path)
        return False

    def open_file(self, file_path: str | Path) -> bool:
        """Open a file from the specified path, prompting to save if dirty."""
        if not self._maybe_save_prompt():
            return False

        path = Path(file_path).resolve()
        if not path.exists():
            QMessageBox.critical(
                self,
                safe_tr("打开失败"),
                safe_tr(f"无法打开文件：找不到指定的文件“{path}”。"),
            )
            return False

        self.current_file_path = path
        self.set_modified(False)

        # Automatically select the spreadsheet tab when opening a spreadsheet
        ext = path.suffix.lower()
        if ext in (".xlsx", ".xls", ".csv", ".tsv"):
            self.tabs.setCurrentWidget(self.spreadsheet_view)

        return True

    def save_file(self, file_path: str | Path | None = None) -> bool:
        """Save the active document to its existing path or prompt Save As."""
        if file_path is None and self.current_file_path is None:
            return self.save_file_as()

        target = (
            Path(file_path).resolve()
            if file_path is not None
            else self.current_file_path
        )
        if target is None:
            return False

        try:
            target.touch(exist_ok=True)
            self.current_file_path = target
            self.set_modified(False)
            return True
        except Exception as exc:
            QMessageBox.critical(
                self,
                safe_tr("保存失败"),
                safe_tr(f"无法保存文件“{target}”：\n{exc}"),
            )
            return False

    def save_file_as(self) -> bool:
        """Prompt user with standard file dialog to save document to a new path."""
        default_dir = (
            str(self.current_file_path.parent)
            if self.current_file_path is not None
            else ""
        )
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            safe_tr("另存为"),
            default_dir,
            safe_tr("Excel 工作簿 (*.xlsx);;CSV 逗号分隔文件 (*.csv);;所有文件 (*.*)"),
        )
        if file_path:
            return self.save_file(file_path)
        return False

    def _maybe_save_prompt(self) -> bool:
        """Prompt to save unsaved modifications before navigating or closing."""
        if not self.is_modified:
            return True

        doc_name = (
            self.current_file_path.name
            if self.current_file_path is not None
            else safe_tr("未命名工作簿")
        )
        res = QMessageBox.warning(
            self,
            "ATBOffice",
            safe_tr(
                f"是否保存对“{doc_name}”的更改？\n如果您不保存，所做的修改将会永久丢失。"
            ),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

        if res == QMessageBox.StandardButton.Save:
            return self.save_file()
        if res == QMessageBox.StandardButton.Discard:
            return True
        return False

    def closeEvent(self, event: QCloseEvent) -> None:
        """Intercept window close to prompt for unsaved changes."""
        if self._maybe_save_prompt():
            event.accept()
        else:
            event.ignore()

    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def toggle_maximized(self) -> None:
        """Toggle maximized window mode."""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def undo(self) -> None:
        """Placeholder for edit undo."""
        pass

    def redo(self) -> None:
        """Placeholder for edit redo."""
        pass

    def cut(self) -> None:
        """Placeholder for edit cut."""
        pass

    def copy(self) -> None:
        """Placeholder for edit copy."""
        pass

    def paste(self) -> None:
        """Placeholder for edit paste."""
        pass

    def format_cells(self) -> None:
        """Open the classic Format Cells dialog for the active spreadsheet view."""
        current = self.tabs.currentWidget()
        if hasattr(current, "grid") and hasattr(
            current.grid, "open_format_cells_dialog"
        ):
            current.grid.open_format_cells_dialog()
        elif hasattr(self, "spreadsheet_view") and hasattr(
            self.spreadsheet_view, "grid"
        ):
            self.spreadsheet_view.grid.open_format_cells_dialog()

    def zoom_in(self) -> None:
        """Placeholder for zoom in."""
        pass

    def zoom_out(self) -> None:
        """Placeholder for zoom out."""
        pass

    def zoom_reset(self) -> None:
        """Placeholder for zoom reset."""
        pass

    def show_help(self) -> None:
        """Display help documentation."""
        pass

    def show_about(self) -> None:
        """Display application about dialog."""
        QMessageBox.about(
            self,
            safe_tr("关于 ATBOffice"),
            safe_tr("<h3>ATBOffice</h3><p>跨平台原生办公套件与电子表格引擎。</p>"),
        )

    def _setup_toolbars(self) -> None:
        """Initialize Office 2003 Standard and Formatting toolbars."""
        # 1. Standard Toolbar
        self.toolbar_standard = OfficeToolBar(safe_tr("常用"), self)
        self.addToolBar(self.toolbar_standard)

        self.toolbar_standard.add_office_action(
            safe_tr("新建(&N)"),
            tooltip=safe_tr("新建工作簿 (Ctrl+N)"),
            callback=self.new_file,
        )
        self.toolbar_standard.add_office_action(
            safe_tr("打开(&O)..."),
            tooltip=safe_tr("打开工作簿 (Ctrl+O)"),
            callback=self.open_file_dialog,
        )
        self.toolbar_standard.add_office_action(
            safe_tr("保存(&S)"),
            tooltip=safe_tr("保存当前工作簿 (Ctrl+S)"),
            callback=self.save_file,
        )
        self.toolbar_standard.add_office_separator()
        self.toolbar_standard.add_office_action(
            safe_tr("剪切(&T)"),
            tooltip=safe_tr("剪切 (Ctrl+X)"),
            callback=self.cut,
        )
        self.toolbar_standard.add_office_action(
            safe_tr("复制(&C)"),
            tooltip=safe_tr("复制 (Ctrl+C)"),
            callback=self.copy,
        )
        self.toolbar_standard.add_office_action(
            safe_tr("粘贴(&P)"),
            tooltip=safe_tr("粘贴 (Ctrl+V)"),
            callback=self.paste,
        )
        self.toolbar_standard.add_office_separator()
        self.toolbar_standard.add_office_action(
            safe_tr("撤销(&U)"),
            tooltip=safe_tr("撤销 (Ctrl+Z)"),
            callback=self.undo,
        )
        self.toolbar_standard.add_office_action(
            safe_tr("重做(&R)"),
            tooltip=safe_tr("重做 (Ctrl+Y)"),
            callback=self.redo,
        )

        # 2. Formatting Toolbar
        self.toolbar_formatting = OfficeToolBar(safe_tr("格式"), self)
        self.addToolBar(self.toolbar_formatting)

        self.act_bold = self.toolbar_formatting.add_office_action(
            safe_tr("加粗(&B)"),
            tooltip=safe_tr("加粗 (Ctrl+B)"),
            callback=self._toggle_bold,
            checkable=True,
        )
        self.act_italic = self.toolbar_formatting.add_office_action(
            safe_tr("倾斜(&I)"),
            tooltip=safe_tr("倾斜 (Ctrl+I)"),
            callback=self._toggle_italic,
            checkable=True,
        )
        self.act_underline = self.toolbar_formatting.add_office_action(
            safe_tr("下划线(&U)"),
            tooltip=safe_tr("下划线 (Ctrl+U)"),
            callback=self._toggle_underline,
            checkable=True,
        )
        self.toolbar_formatting.add_office_separator()

        # Color Pickers
        self.btn_font_color = ColorPickerButton(
            mode="font", default_color="#000000", parent=self.toolbar_formatting
        )
        self.btn_font_color.setToolTip(safe_tr("字体颜色"))
        self.btn_font_color.setStatusTip(safe_tr("更改文字颜色"))
        self.btn_font_color.color_applied.connect(self._apply_font_color)
        self.toolbar_formatting.addWidget(self.btn_font_color)

        self.btn_fill_color = ColorPickerButton(
            mode="fill", default_color="#FFFF00", parent=self.toolbar_formatting
        )
        self.btn_fill_color.setToolTip(safe_tr("填充颜色"))
        self.btn_fill_color.setStatusTip(safe_tr("更改单元格背景颜色"))
        self.btn_fill_color.color_applied.connect(self._apply_fill_color)
        self.toolbar_formatting.addWidget(self.btn_fill_color)

    def set_theme(self, theme: str) -> None:
        """Switch active Office 2003 Luna theme ('blue' or 'silver')."""
        self.current_theme = theme.lower()
        apply_luna_theme(self, self.current_theme)

        if hasattr(self, "menu_bar"):
            if "theme_luna_blue" in self.menu_bar.action_map:
                self.menu_bar.action_map["theme_luna_blue"].setChecked(
                    self.current_theme == "blue"
                )
            if "theme_luna_silver" in self.menu_bar.action_map:
                self.menu_bar.action_map["theme_luna_silver"].setChecked(
                    self.current_theme == "silver"
                )

    def _get_selected_cell_range(self) -> tuple[int, int, int, int]:
        sel = self.spreadsheet_view.selection
        box = sel.bounding_box
        if box:
            return (box.top, box.left, box.bottom, box.right)
        return (sel.active_row, sel.active_col, sel.active_row, sel.active_col)

    def _toggle_bold(self) -> None:
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        active_cell = model.get_cell(r1, c1)
        new_val = not active_cell.bold
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cell.bold = new_val
                model.set_cell(r, c, cell)
        self.spreadsheet_view.viewport.update()
        self.act_bold.setChecked(new_val)

    def _toggle_italic(self) -> None:
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        active_cell = model.get_cell(r1, c1)
        new_val = not active_cell.italic
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cell.italic = new_val
                model.set_cell(r, c, cell)
        self.spreadsheet_view.viewport.update()
        self.act_italic.setChecked(new_val)

    def _toggle_underline(self) -> None:
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        active_cell = model.get_cell(r1, c1)
        new_val = not active_cell.underline
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cell.underline = new_val
                model.set_cell(r, c, cell)
        self.spreadsheet_view.viewport.update()
        self.act_underline.setChecked(new_val)

    def _apply_font_color(self, color: str) -> None:
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        fg = None if color == "auto" else color
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cell.fg_color = fg
                model.set_cell(r, c, cell)
        self.spreadsheet_view.viewport.update()

    def _apply_fill_color(self, color: str) -> None:
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        bg = None if color in ("none", "auto") else color
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = model.get_cell(r, c)
                cell.bg_color = bg
                model.set_cell(r, c, cell)
        self.spreadsheet_view.viewport.update()

    def _on_locale_changed(self, _locale: str) -> None:
        """Handle locale switch."""
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Retranslate all UI strings in the main window."""
        self._update_window_title()
        self.tabs.setTabText(0, safe_tr("文字处理"))
        self.tabs.setTabText(1, safe_tr("电子表格"))
        self.tabs.setTabText(2, safe_tr("演示文稿"))
        self.menu_bar.retranslate_ui()
