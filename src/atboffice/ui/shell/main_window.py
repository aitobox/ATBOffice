"""macOS shell main window with workbook lifecycle management and dirty tracking."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QTabWidget

from atboffice.modules.presentation.view import PresentationView
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.modules.writer.view import WriterView
from atboffice.ui.components.status_bar import StatusBar
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu


def safe_tr(text: str) -> str:
    """Translate UI text safely for MainWindow."""
    return QCoreApplication.translate("MainWindow", text)


class MainWindow(QMainWindow):
    """Top-level shell window with native macOS HIG menu and workbook management."""

    def __init__(self) -> None:
        super().__init__()
        self.current_file_path: Path | None = None
        self._is_modified: bool = False

        self.resize(1100, 720)
        self._update_window_title()

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

    def retranslate_ui(self) -> None:
        """Retranslate all UI strings in the main window."""
        self._update_window_title()
        self.tabs.setTabText(0, safe_tr("文字处理"))
        self.tabs.setTabText(1, safe_tr("电子表格"))
        self.tabs.setTabText(2, safe_tr("演示文稿"))
        self.menu_bar.retranslate_ui()
