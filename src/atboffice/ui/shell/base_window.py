"""Base window class providing document lifecycle, dirty tracking, theme, and prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QWidget

from atboffice.ui.styles.luna_2003 import apply_luna_theme


def safe_tr(text: str) -> str:
    """Translate UI text safely for BaseOfficeWindow."""
    return QCoreApplication.translate("BaseOfficeWindow", text)


class BaseOfficeWindow(QMainWindow):
    """Universal office window base class with document lifecycle and dirty tracking."""

    window_closed = Signal(QMainWindow)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_file_path: Path | None = None
        self._is_modified: bool = False
        self.current_theme: str = "blue"
        if not hasattr(self, "app_name"):
            self.app_name: str = "ATBOffice"

        self.update_window_title()
        self.apply_theme(self.current_theme)

    @property
    def is_modified(self) -> bool:
        """Return whether the current document has unsaved modifications."""
        return self._is_modified

    def set_modified(self, modified: bool) -> None:
        """Update document dirty status and window modified dot."""
        self._is_modified = modified
        self.setWindowModified(modified)
        self.update_window_title()

    def update_window_title(self) -> None:
        """Set window title according to active document and dirty placeholder."""
        if self.current_file_path is not None:
            title = f"{self.current_file_path.name} — {self.app_name} [*]"
        else:
            title = f"{self.app_name} [*]"
        self.setWindowTitle(title)

    def apply_theme(self, theme_name: str) -> None:
        """Apply Luna 2003 theme (blue or silver) to window and its children."""
        self.current_theme = theme_name
        apply_luna_theme(self, theme_name)

    def maybe_save_prompt(self) -> bool:
        """Prompt to save unsaved modifications before navigating or closing."""
        if not self.is_modified:
            return True

        doc_name = (
            self.current_file_path.name
            if self.current_file_path is not None
            else safe_tr("未命名文档")
        )
        res = QMessageBox.warning(
            self,
            self.app_name,
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

    def do_save(self, path: Path) -> bool:
        """Subclass hook to perform actual file serialization."""
        path.touch(exist_ok=True)
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
            if not self.do_save(target):
                return False
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

    def get_file_filter(self) -> str:
        """Return file filter pattern for save/open dialogs."""
        return safe_tr("所有支持的格式 (*.*);;所有文件 (*.*)")

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
            self.get_file_filter(),
        )
        if file_path:
            return self.save_file(file_path)
        return False

    def closeEvent(self, event: QCloseEvent) -> None:
        """Intercept window close to prompt for unsaved changes and emit signal."""
        if self.maybe_save_prompt():
            event.accept()
            self.window_closed.emit(self)
        else:
            event.ignore()

    def retranslate_ui(self) -> None:
        """Update localized UI strings when application language changes."""
        self.update_window_title()
