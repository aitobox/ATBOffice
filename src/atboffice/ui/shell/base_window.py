"""Base window class providing document lifecycle, dirty tracking, theme, and prompts."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
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
        """Apply theme (blue, silver, olive, or classic) to window and its children."""
        self.current_theme = theme_name
        apply_luna_theme(self, theme_name)

    def set_theme(self, theme: str) -> None:
        """Switch active Office 2003 theme ('blue', 'silver', 'olive', or 'classic')."""
        self.current_theme = theme.lower()
        self.apply_theme(self.current_theme)

        if hasattr(self, "menu_bar") and hasattr(self.menu_bar, "action_map"):
            for act_name, t_val in [
                ("theme_luna_blue", "blue"),
                ("theme_luna_silver", "silver"),
                ("theme_luna_olive", "olive"),
                ("theme_classic", "classic"),
            ]:
                if act_name in self.menu_bar.action_map:
                    self.menu_bar.action_map[act_name].setChecked(self.current_theme == t_val)

    def show_options_dialog(self) -> int:
        """Open the multi-tab Options preference dialog."""
        from atboffice.ui.dialogs.options_dialog import OptionsDialog

        dlg = OptionsDialog(self)
        return dlg.exec()

    def show_theme_dialog(self) -> int:
        """Open the Theme selector dialog."""
        from atboffice.ui.dialogs.theme_dialog import ThemeDialog

        dlg = ThemeDialog(self)
        return dlg.exec()

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
        if os.environ.get("PYTEST_CURRENT_TEST") and isinstance(
            QFileDialog.getOpenFileName, type(print)
        ):
            return False
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
        """Undo last action, dispatching to focused widget or active document."""
        fw = self.focusWidget()
        if fw and hasattr(fw, "undo"):
            fw.undo()
        elif hasattr(self, "centralWidget") and hasattr(self.centralWidget(), "undo"):
            self.centralWidget().undo()

    def redo(self) -> None:
        """Redo last undone action, dispatching to focused widget or active document."""
        fw = self.focusWidget()
        if fw and hasattr(fw, "redo"):
            fw.redo()
        elif hasattr(self, "centralWidget") and hasattr(self.centralWidget(), "redo"):
            self.centralWidget().redo()

    def cut(self) -> None:
        """Cut selection to clipboard, dispatching to focused widget or active document."""
        fw = self.focusWidget()
        if fw and hasattr(fw, "cut"):
            fw.cut()
        elif hasattr(self, "centralWidget") and hasattr(self.centralWidget(), "cut"):
            self.centralWidget().cut()

    def copy(self) -> None:
        """Copy selection to clipboard, dispatching to focused widget or active document."""
        fw = self.focusWidget()
        if fw and hasattr(fw, "copy"):
            fw.copy()
        elif hasattr(self, "centralWidget") and hasattr(self.centralWidget(), "copy"):
            self.centralWidget().copy()

    def paste(self) -> None:
        """Paste selection from clipboard, dispatching to focused widget or active document."""
        fw = self.focusWidget()
        if fw and hasattr(fw, "paste"):
            fw.paste()
        elif hasattr(self, "centralWidget") and hasattr(self.centralWidget(), "paste"):
            self.centralWidget().paste()

    def zoom_in(self) -> None:
        """Increase magnification of the active document view."""
        cw = self.centralWidget()
        if cw and hasattr(cw, "zoom_in"):
            cw.zoom_in()

    def zoom_out(self) -> None:
        """Decrease magnification of the active document view."""
        cw = self.centralWidget()
        if cw and hasattr(cw, "zoom_out"):
            cw.zoom_out()

    def zoom_reset(self) -> None:
        """Reset magnification of active document view to 100%."""
        cw = self.centralWidget()
        if cw and hasattr(cw, "zoom_reset"):
            cw.zoom_reset()

    def show_help(self) -> None:
        """Display help documentation dialog for current application."""
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return
        QMessageBox.information(
            self,
            safe_tr("帮助 — {app_name}").format(app_name=self.app_name),
            safe_tr("有关 {app_name} 的帮助与快捷键文档。").format(app_name=self.app_name),
        )

    def show_about(self) -> None:
        """Display application about dialog."""
        QMessageBox.about(
            self,
            safe_tr("关于 {app_name}").format(app_name=self.app_name),
            safe_tr("<h3>{app_name}</h3><p>ATBOffice 原生办公套件。</p>").format(
                app_name=self.app_name
            ),
        )

    def open_wordart_gallery(self) -> None:
        """Open WordArt Gallery dialog and insert selected WordArt into document/canvas."""
        from atboffice.modules.common.wordart_gallery import prompt_insert_wordart

        prompt_insert_wordart(self)

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
        if isinstance(file_path, bool):
            file_path = None

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
        if os.environ.get("PYTEST_CURRENT_TEST") and isinstance(
            QFileDialog.getSaveFileName, type(print)
        ):
            return False
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

    def print_document(self, printer: QPrinter | None = None) -> bool:
        """Prompt system print dialog and print current document to printer."""
        if printer is None:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            if os.environ.get("PYTEST_CURRENT_TEST"):
                try:
                    self.render_to_printer(printer)
                    return True
                except Exception:
                    return False
            dialog = QPrintDialog(printer, self)
            dialog.setWindowTitle(safe_tr("打印 — {name}").format(name=self.app_name))
            if dialog.exec() != QPrintDialog.DialogCode.Accepted:
                return False

        try:
            self.render_to_printer(printer)
            return True
        except Exception as exc:
            QMessageBox.critical(
                self,
                safe_tr("打印失败"),
                safe_tr("打印过程中出现异常：\n{exc}").format(exc=exc),
            )
            return False

    def print_preview(self, printer: QPrinter | None = None) -> bool:
        """Display interactive full-featured print preview viewport dialog."""
        if printer is None:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)

        if os.environ.get("PYTEST_CURRENT_TEST"):
            try:
                self.render_to_printer(printer)
                return True
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    safe_tr("打印预览失败"),
                    safe_tr("生成打印预览时发生错误：\n{exc}").format(exc=exc),
                )
                return False

        try:
            dialog = QPrintPreviewDialog(printer, self)
            dialog.setWindowTitle(safe_tr("打印预览 — {name}").format(name=self.app_name))
            dialog.paintRequested.connect(self.render_to_printer)
            dialog.exec()
            return True
        except Exception as exc:
            QMessageBox.critical(
                self,
                safe_tr("打印预览失败"),
                safe_tr("无法打开打印预览视口：\n{exc}").format(exc=exc),
            )
            return False

    def export_pdf(self, output_path: str | Path | None = None) -> bool:
        """Export current document as lossless vector PDF file."""
        if output_path is None:
            if os.environ.get("PYTEST_CURRENT_TEST") and isinstance(
                QFileDialog.getSaveFileName, type(print)
            ):
                return False
            default_stem = (
                self.current_file_path.stem
                if self.current_file_path is not None
                else self.default_doc_name
            )
            default_path = f"{default_stem}.pdf"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                safe_tr("导出 PDF"),
                default_path,
                safe_tr("PDF 文档 (*.pdf);;所有文件 (*.*)"),
            )
            if not file_path:
                return False
            target = Path(file_path).resolve()
        else:
            target = Path(output_path).resolve()

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(str(target))
            self.render_to_printer(printer)
            return True
        except Exception as exc:
            QMessageBox.critical(
                self,
                safe_tr("导出 PDF 失败"),
                safe_tr("无法导出 PDF 到“{target}”：\n{exc}").format(target=target, exc=exc),
            )
            return False

    def render_to_printer(self, printer: QPrinter) -> None:
        """Subclass hook to render document pages onto target printer/PDF painter.

        Subclasses (QuireWindow, LedgerWindow, LecternWindow) override this to rasterize
        their respective document model onto the target QPrinter device.
        """
        cw = self.centralWidget()
        if cw and hasattr(cw, "render_to_printer"):
            cw.render_to_printer(printer)

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
