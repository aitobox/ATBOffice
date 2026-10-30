"""Base window class providing document lifecycle, dirty tracking, theme, and prompts."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QWidget

from atboffice.core.i18n import get_i18n_manager
from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.ui.styles.luna_2003 import apply_luna_theme


def safe_tr(text: str) -> str:
    """Translate UI text safely for BaseOfficeWindow."""
    return core_safe_tr(text)


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
        if not hasattr(self, "app_type"):
            self.app_type: str = "generic"

        self.update_window_title()
        self.apply_theme(self.current_theme)
        try:
            get_i18n_manager().locale_changed.connect(self._on_locale_changed)
        except Exception:
            pass

    def _on_locale_changed(self, _locale: str) -> None:
        """Handle dynamic language change and trigger retranslate_ui."""
        self.retranslate_ui()

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

    def set_theme(self, theme: str) -> None:
        """Switch active Office 2003 Luna theme ('blue' or 'silver')."""
        self.current_theme = theme.lower()
        self.apply_theme(self.current_theme)

        if hasattr(self, "menu_bar") and hasattr(self.menu_bar, "action_map"):
            if "theme_luna_blue" in self.menu_bar.action_map:
                self.menu_bar.action_map["theme_luna_blue"].setChecked(self.current_theme == "blue")
            if "theme_luna_silver" in self.menu_bar.action_map:
                self.menu_bar.action_map["theme_luna_silver"].setChecked(
                    self.current_theme == "silver"
                )

    def new_file(self) -> bool:
        """Create a new blank document, prompting to save changes if modified."""
        if not self.maybe_save_prompt():
            return False
        self.current_file_path = None
        self.set_modified(False)
        self.update_window_title()
        return True

    def open_file_dialog(self) -> bool:
        """Present standard file dialog to select and open a document."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            safe_tr("打开文档"),
            "",
            self.get_file_filter(),
        )
        if file_path:
            return self.open_file(file_path)
        return False

    def open_file(self, file_path: str | Path) -> bool:
        """Open a file from the specified path, prompting to save if dirty."""
        if not self.maybe_save_prompt():
            return False

        path = Path(file_path).resolve()
        if not path.exists():
            QMessageBox.critical(
                self,
                safe_tr("打开失败"),
                safe_tr("找不到指定的文件：{path}").format(path=path),
            )
            return False

        self.current_file_path = path
        self.set_modified(False)
        self.update_window_title()

        try:
            from atboffice.core.window_manager import WindowManager

            wm = WindowManager.get_instance()
            app_type = wm.detect_app_type(path)
            wm.recent_files.add_file(path, app_type)
        except Exception:
            pass

        return True

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
        """Undo last action placeholder."""
        pass

    def redo(self) -> None:
        """Redo last action placeholder."""
        pass

    def cut(self) -> None:
        """Cut selection placeholder."""
        pass

    def copy(self) -> None:
        """Copy selection placeholder."""
        pass

    def paste(self) -> None:
        """Paste selection placeholder."""
        pass

    def zoom_in(self) -> None:
        """Zoom in placeholder."""
        pass

    def zoom_out(self) -> None:
        """Zoom out placeholder."""
        pass

    def zoom_reset(self) -> None:
        """Zoom reset placeholder."""
        pass

    def show_help(self) -> None:
        """Display help documentation placeholder."""
        pass

    def show_about(self) -> None:
        """Display application about dialog."""
        QMessageBox.about(
            self,
            safe_tr("关于 {app_name}").format(app_name=self.app_name),
            safe_tr("<h3>{app_name}</h3><p>ATBOffice 原生办公套件。</p>").format(
                app_name=self.app_name
            ),
        )

    @property
    def default_doc_name(self) -> str:
        """Default document name when no file is currently associated."""
        return safe_tr("未命名文档")

    def maybe_save_prompt(self) -> bool:
        """Prompt to save unsaved modifications before navigating or closing."""
        if not self.is_modified:
            return True

        doc_name = (
            self.current_file_path.name
            if self.current_file_path is not None
            else self.default_doc_name
        )
        res = QMessageBox.warning(
            self,
            self.app_name,
            safe_tr("是否保存对“{name}”的更改？\n如果您不保存，所做的修改将会永久丢失。").format(
                name=doc_name
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

        target = Path(file_path).resolve() if file_path is not None else self.current_file_path
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
                safe_tr("无法保存文件“{target}”：\n{exc}").format(target=target, exc=exc),
            )
            return False

    def get_file_filter(self) -> str:
        """Return file filter pattern for save/open dialogs."""
        return safe_tr("所有支持的格式 (*.*);;所有文件 (*.*)")

    def save_file_as(self) -> bool:
        """Prompt user with standard file dialog to save document to a new path."""
        default_path = str(self.current_file_path) if self.current_file_path is not None else ""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            safe_tr("另存为"),
            default_path,
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
