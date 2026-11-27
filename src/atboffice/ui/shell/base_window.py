"""Base window class providing document lifecycle, dirty tracking, theme, and prompts."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QDialog, QFileDialog, QMainWindow, QMessageBox, QWidget

from atboffice.core.fault_guard import is_alive
from atboffice.core.i18n import get_i18n_manager, safe_tr
from atboffice.core.undo import UndoService
from atboffice.ui.styles.luna_2003 import apply_luna_theme

logger = logging.getLogger(__name__)


# OOXML package formats that can be wrapped in an encrypted OLE container.
ENCRYPTABLE_SUFFIXES: frozenset[str] = frozenset(
    {".docx", ".docm", ".dotx", ".xlsx", ".xlsm", ".xltx", ".pptx", ".pptm", ".ppsx", ".potx"}
)


class UnsupportedSaveFormatError(ValueError):
    """Raised by ``do_save`` when the editor cannot serialize the requested format."""

    def __init__(self, suffix: str) -> None:
        self.suffix = suffix
        super().__init__(
            safe_tr("不支持保存为“{suffix}”格式，请选择“另存为”中列出的格式。").format(
                suffix=suffix or safe_tr("无扩展名")
            )
        )


class FileOpenCancelled(Exception):
    """Raised when user cleanly cancels file opening (e.g. password dialog)."""


class FileOpenWarningHandled(Exception):
    """Raised when an informative message or rejection was already displayed to the user."""


class BaseOfficeWindow(QMainWindow):
    """Universal office window base class with document lifecycle and dirty tracking."""

    window_closed = Signal(QMainWindow)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_file_path: Path | None = None
        self.active_template: Any | None = None
        self._is_modified: bool = False
        self._in_close_event: bool = False
        self._is_closed: bool = False
        self._owned_timers: list[QTimer] = []
        self.current_theme: str = "blue"
        self.task_pane_dock: Any | None = None
        self.clipboard_pane: Any | None = None
        self.context_pane_controller: Any | None = None
        self.command_search_box: Any | None = None
        self._document_metadata: Any | None = None
        # Password of the encrypted package currently open (in memory only).
        self._package_password: str | None = None
        self._pending_package_password: str | None = None
        # True while RecoveryService writes a draft: suppresses interactive prompts.
        self._is_autosaving: bool = False
        from atboffice.core.recovery_service import RecoveryService

        self.recovery_service: RecoveryService = RecoveryService(self)
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
        self._start_recovery_service()

    # Native draft format for crash-recovery snapshots; ``None`` disables autosave.
    recovery_suffix: str | None = None

    def _start_recovery_service(self) -> None:
        """Start periodic crash-recovery autosave for editors that declare a draft format."""
        if self.recovery_suffix is None:
            return
        minutes = 10
        try:
            from atboffice.core.settings import get_app_settings

            minutes = int(get_app_settings().get_value("save/auto_save_interval", 10))
        except Exception as exc:
            logger.debug("Falling back to default autosave interval: %s", exc)
        minutes = min(max(minutes, 1), 60)
        self.recovery_service.start(minutes * 60 * 1000)

    _compat_confirmed: bool = False

    def confirm_compatibility_losses(self, losses: Any, target_name: str = "") -> bool:
        """Compatibility Checker for ``losses``; True when saving may proceed.

        Only ``notify`` losses are shown. Autosave never prompts, and a save already
        confirmed by :meth:`run_compatibility_check` is not asked again.
        """
        from atboffice.core.compat import coerce, notify_only

        if self._is_autosaving or self._compat_confirmed:
            return True
        shown = notify_only(coerce(losses))
        if not shown:
            return True
        from atboffice.ui.dialogs.compatibility_dialog import CompatibilityDialog

        dlg = CompatibilityDialog(shown, target_name or self.default_doc_name, parent=self)
        return dlg.exec() == QDialog.DialogCode.Accepted

    def compat_model_losses(self) -> list[Any]:
        """Losses recorded while loading the document (subclass hook)."""
        return []

    def save_losses(self, target: Path) -> list[Any]:
        """Losses specific to saving into ``target``'s format (subclass hook)."""
        return []

    def run_compatibility_check(self, target: Path) -> bool:
        """Collect model + format losses for ``target`` and ask once before saving."""
        from atboffice.core.compat import coerce, macro_loss

        try:
            losses = (
                coerce(self.compat_model_losses())
                + macro_loss(self.current_file_path, target)
                + coerce(self.save_losses(target))
            )
        except Exception:
            logger.debug("Compatibility check failed for %s", target, exc_info=True)
            return True
        return self.confirm_compatibility_losses(losses, target.name)

    def encrypt_saved_package(self, path: Path, target_suffix: str) -> None:
        """Re-encrypt a freshly written package with the password it was opened with."""
        if self._package_password is None:
            return
        if target_suffix.lower() not in ENCRYPTABLE_SUFFIXES:
            return
        from atboffice.vfs.crypto import encrypt_package

        path.write_bytes(encrypt_package(path.read_bytes(), passcode=self._package_password))

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
        if not modified:
            svc = self.undo_service()
            if svc is not None:
                svc.set_clean()
        self.setWindowModified(modified)
        self.update_window_title()

    def update_window_title(self) -> None:
        """Set window title according to active document and dirty placeholder."""
        if self.current_file_path is not None:
            title = f"{self.current_file_path.name} — {self.app_name} [*]"
        elif getattr(self, "active_template", None) is not None:
            tag = safe_tr("基于模板")
            tname = self.active_template.name
            title = f"{self.default_doc_name} [{tag}: {tname}] — {self.app_name} [*]"
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
        self.active_template = None
        self._package_password = None
        self.set_modified(False)
        self.update_window_title()
        return True

    def load_template(self, template_id: str) -> bool:
        """Load a template by ID into the window as a new unsaved document.

        Args:
            template_id: Template identifier (e.g. 'letter', 'loan', 'status').

        Returns:
            True if template was found and loaded successfully, False otherwise.
        """
        if not self.maybe_save_prompt():
            return False

        from atboffice.core.templates import TemplateRegistry

        reg = TemplateRegistry.get_instance()
        tpl = reg.get(template_id, app=self.app_name.lower())
        if tpl is None:
            tpl = reg.get(template_id)

        if tpl is None:
            logger.warning("Template %r not found for %s", template_id, self.app_name)
            return False

        # Reset path to None to guarantee this is an unsaved new document
        self.current_file_path = None
        self.active_template = tpl

        # Invoke custom builder if present
        if callable(tpl.builder):
            try:
                res = tpl.builder(self)
                self._apply_template_result(res)
            except Exception as exc:
                logger.exception("Error executing builder for template %s: %s", template_id, exc)
                self.active_template = None
                return False

        # Mark as modified so user is prompted to save/name the new document
        self.set_modified(True)
        self.update_window_title()
        return True

    def _apply_template_result(self, result: Any) -> None:
        """Subclass hook to handle custom builder return values."""
        pass

    def do_open(self, path: Path) -> bool:
        """Subclass hook to parse and load document from disk.

        Subclasses should raise an exception or return False if the file is
        corrupted or incompatible.
        """
        return True

    def prompt_for_package_password(self, file_name: str) -> str | None:
        """Prompt user for document open password.

        Returns:
            Password string if user confirmed, or None if user clicked Cancel.
        """
        from PySide6.QtWidgets import QInputDialog, QLineEdit

        pwd, ok = QInputDialog.getText(
            self,
            safe_tr("输入密码"),
            safe_tr("“{name}”受密码保护，请输入密码：").format(name=file_name),
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return None
        return pwd

    def try_decrypt_if_encrypted(self, path: Path) -> tuple[bytes | None, bool]:
        """Check if file is an encrypted package; decrypt with user password if so.

        Returns:
            (bytes_data, is_encrypted)
            If not encrypted: returns (None, False).
            If encrypted and successfully decrypted: returns (decrypted_bytes, True).

        Raises:
            FileOpenCancelled: If user clicked Cancel on password dialog.
            FileOpenWarningHandled: If password was invalid and warning was shown.
        """
        from atboffice.vfs.crypto import decrypt_package, is_encrypted_package

        if not is_encrypted_package(path):
            return (None, False)

        pwd = self.prompt_for_package_password(path.name)
        if pwd is None:
            raise FileOpenCancelled("User cancelled password prompt")

        try:
            decrypted = decrypt_package(path, passcode=pwd)
            # Committed by open_file only once the document has loaded successfully.
            self._pending_package_password = pwd
            return (decrypted, True)
        except ValueError as err:
            err_msg = str(err)
            if "invalid password" in err_msg.lower():
                QMessageBox.warning(
                    self,
                    safe_tr("打开失败"),
                    safe_tr("密码不正确，无法打开文档。"),
                )
                raise FileOpenWarningHandled("Incorrect password") from err
            raise

    def check_legacy_or_disguised_file(
        self, path: Path, app_name: str, allow_excel97: bool = False
    ) -> None:
        """Inspect file format and handle legacy 97-2003 or disguised binary documents.

        Raises:
            FileOpenWarningHandled: If the file is an unsupported legacy or disguised
                binary document and an informative warning dialog has been presented.
        """
        from atboffice.vfs.crypto import inspect_file_format

        inspection = inspect_file_format(path, expected_app=app_name, allow_excel97=allow_excel97)
        if inspection.should_reject:
            title = inspection.guidance_title or safe_tr("文件格式提示")
            msg = inspection.guidance_message or safe_tr("不支持的旧版二进制文件格式。")
            QMessageBox.warning(self, title, msg)
            raise FileOpenWarningHandled(f"Legacy or disguised binary file rejected: {path.name}")

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

    def _show_unreadable_file_error(self, path: Path) -> None:
        """Tell the user, in the UI language, that the named file is unreadable."""
        QMessageBox.critical(
            self,
            safe_tr("Open Failed"),
            safe_tr('Cannot open "{name}": the file is corrupt or unreadable.').format(
                name=path.name
            ),
        )

    def open_file(self, file_path: str | Path) -> bool:
        """Open a file from the specified path, prompting to save if dirty."""
        if not self.maybe_save_prompt():
            return False

        raw_path = Path(file_path)
        if raw_path.is_symlink() and not raw_path.exists():
            target_str = ""
            try:
                target_str = str(os.readlink(file_path))
            except OSError:
                pass
            if "atboffice_corpora" in target_str or "atboffice_corpora" in str(file_path):
                QMessageBox.warning(
                    self,
                    safe_tr("测试语料未下载"),
                    safe_tr(
                        "该文件为测试语料库软链接，目标语料尚未下载。\n"
                        "请先在终端运行以下命令下载语料包：\n"
                        "python scripts/fetch_corpora.py\n\n"
                        "链接路径：{path}\n"
                        "目标路径：{target}"
                    ).format(path=file_path, target=target_str or safe_tr("未知")),
                )
                return False

        path = raw_path.resolve()
        if not path.exists():
            QMessageBox.critical(
                self,
                safe_tr("打开失败"),
                safe_tr("找不到指定的文件：{path}").format(path=path),
            )
            return False

        self._pending_package_password = None
        try:
            if not self.do_open(path):
                logger.error("do_open returned False for %s", path)
                self._show_unreadable_file_error(path)
                return False
        except FileOpenCancelled:
            # User cleanly cancelled the operation (e.g. password dialog)
            return False
        except FileOpenWarningHandled:
            # Informative message or rejection guidance was already presented
            return False
        except Exception:
            # Keep the raw parser diagnostic in the logs, out of the dialog.
            logger.exception("Failed to open %s", path)
            self._show_unreadable_file_error(path)
            return False

        self.current_file_path = path
        self.active_template = None
        self._package_password = self._pending_package_password
        self._pending_package_password = None
        self.set_modified(False)
        self.update_window_title()

        try:
            from atboffice.core.window_manager import WindowManager

            wm = WindowManager.get_instance()
            app_type = getattr(self, "app_type", wm.detect_app_type(path))
            wm.recent_files.add_file(path, app_type)
            self._cache_thumbnail(path, wm.recent_files)
        except Exception:
            logger.warning("Could not add %s to the recent files", path, exc_info=True)

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

    # -- Focus ---------------------------------------------------------------

    def document_widget(self) -> QWidget | None:
        """The widget that shows the document and takes the keyboard (subclass hook)."""
        return None

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not getattr(self, "_initial_focus_done", False):
            self._initial_focus_done = True
            # After the window is laid out, so the toolbars can't grab focus first.
            QTimer.singleShot(0, self.focus_document)

    def focus_document(self) -> None:
        """Give the keyboard to the document instead of a toolbar box or tab bar."""
        target = self.document_widget()
        if target is None or not target.isVisible():
            return
        current = self.focusWidget()
        if current is None or not (current is target or target.isAncestorOf(current)):
            target.setFocus()

    # -- Undo / Redo ---------------------------------------------------------

    def undo_service(self) -> UndoService | None:
        """The active document's undo history (subclass hook)."""
        return None

    def flush_pending_edits(self) -> None:
        """Record edits that are still waiting to become an undo step (subclass hook)."""

    def bind_undo_service(self) -> None:
        """Connect the document's undo history to the window's modified flag.

        Call after the editing view (and so its history) exists. Moving away
        from the saved position marks the document modified; saving or loading
        marks the current position as clean.
        """
        svc = self.undo_service()
        if svc is None or getattr(svc, "_bound_window", None) is self:
            return
        svc._bound_window = self  # type: ignore[attr-defined]
        svc.stack.cleanChanged.connect(self._on_undo_clean_changed)

    def _on_undo_clean_changed(self, clean: bool) -> None:
        if not clean:
            self.set_modified(True)

    def _focused_text_input(self, kind: str) -> Any | None:
        """The focused line / text edit when it has its own step to undo or redo."""
        from PySide6.QtWidgets import QLineEdit, QPlainTextEdit, QTextEdit

        fw = self.focusWidget()
        if isinstance(fw, QLineEdit) and not fw.isReadOnly():
            available = fw.isUndoAvailable() if kind == "undo" else fw.isRedoAvailable()
            return fw if available else None
        if isinstance(fw, (QTextEdit, QPlainTextEdit)) and not fw.isReadOnly():
            doc = fw.document()
            available = doc.isUndoAvailable() if kind == "undo" else doc.isRedoAvailable()
            return fw if available else None
        return None

    def undo(self) -> None:
        """Undo the last step: in the focused text box, else in the document."""
        self._undo_redo("undo")

    def redo(self) -> None:
        """Redo the last undone step: in the focused text box, else in the document."""
        self._undo_redo("redo")

    def _undo_redo(self, kind: str) -> None:
        text_input = self._focused_text_input(kind)
        if text_input is not None:
            getattr(text_input, kind)()
            return
        self.flush_pending_edits()
        svc = self.undo_service()
        if svc is not None:
            if svc.undo_steps(kind, 1):
                self.after_undo_redo()
            return
        # Editors without a shared history: let the focused widget or the
        # central widget handle it.
        fw = self.focusWidget()
        if fw is not None and hasattr(fw, kind):
            getattr(fw, kind)()
        elif hasattr(self.centralWidget(), kind):
            getattr(self.centralWidget(), kind)()

    def after_undo_redo(self) -> None:
        """Refresh after the document history moved (subclass hook)."""
        self.set_modified(True)

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

    def open_clipart_dialog(self) -> None:
        """Open Clipart Gallery dialog and insert selected clipart into document/canvas."""
        from atboffice.modules.common.clipart_dialog import prompt_insert_clipart

        prompt_insert_clipart(self)

    def toggle_assistant(self) -> None:
        """Toggle global Scout desktop companion assistant visibility."""
        from atboffice.modules.common.assistant_scout import toggle_assistant

        toggle_assistant(getattr(self, "action_registry", None))

    def check_for_updates(self) -> None:
        """Check for ATBOffice updates."""
        from atboffice.core.updater import check_for_updates

        check_for_updates(parent=self, manual=True)

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

    def save_file(
        self,
        file_path: str | Path | None = None,
        confirm_overwrite: bool = True,
    ) -> bool:
        """Save the active document to its existing path or prompt Save As.

        Guarantees atomic saving: Writes to a temporary staging file in the target's
        directory first, and atomically replaces the target file upon success. If an
        error occurs or the user declines overwrite, any existing file on disk remains
        100% intact, and in-memory document state and dirty flags are preserved.
        """
        if isinstance(file_path, bool):
            file_path = None

        if file_path is None and self.current_file_path is None:
            return self.save_file_as()

        target = Path(file_path).resolve() if file_path is not None else self.current_file_path
        if target is None:
            return False

        # 1. Overwrite confirmation if saving to an existing file different from current path
        if (
            confirm_overwrite
            and target.exists()
            and (self.current_file_path is None or target != self.current_file_path)
        ):
            res = QMessageBox.warning(
                self,
                self.app_name,
                safe_tr("文件“{name}”已存在。\n是否替换现有文件？").format(name=target.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if res != QMessageBox.StandardButton.Yes:
                return False

        # 1b. Compatibility Checker: what the chosen format cannot keep (asked once)
        if not self._is_autosaving and not self.run_compatibility_check(target):
            return False
        self._compat_confirmed = True

        # 2. Atomic save staging in target directory
        staged_temp_path: Path | None = None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            import uuid

            staging_name = f".~{target.stem}.tmp.{uuid.uuid4().hex[:8]}{target.suffix}"
            staged_temp_path = target.parent / staging_name

            # Execute serialization to the staging file
            save_ok = self.do_save(staged_temp_path)
            if not save_ok:
                logger.error("do_save returned False for %s", target)
                if staged_temp_path.exists():
                    try:
                        staged_temp_path.unlink()
                    except Exception:
                        pass
                QMessageBox.critical(
                    self,
                    safe_tr("保存失败"),
                    safe_tr("无法保存文件“{target}”：序列化失败。").format(target=target),
                )
                return False

            self.encrypt_saved_package(staged_temp_path, target.suffix)

            # Atomically replace target
            os.replace(staged_temp_path, target)
            staged_temp_path = None

            self.current_file_path = target
            self.set_modified(False)
            self.update_window_title()
            self.recovery_service.clear_draft()

            try:
                from atboffice.core.window_manager import WindowManager

                wm = WindowManager.get_instance()
                app_type = getattr(self, "app_type", wm.detect_app_type(target))
                wm.recent_files.add_file(target, app_type)
                self._cache_thumbnail(target, wm.recent_files)
            except Exception:
                logger.warning("Could not add %s to the recent files", target, exc_info=True)

            return True

        except PermissionError as exc:
            logger.warning("No permission to save %s: %s", target, exc)
            if staged_temp_path and staged_temp_path.exists():
                try:
                    staged_temp_path.unlink()
                except Exception:
                    pass
            QMessageBox.critical(
                self,
                safe_tr("保存失败"),
                safe_tr("无法保存文件“{target}”：权限不足，无法写入目标目录或文件。\n{exc}").format(
                    target=target, exc=exc
                ),
            )
            return False
        except Exception as exc:
            logger.exception("Failed to save %s", target)
            if staged_temp_path and staged_temp_path.exists():
                try:
                    staged_temp_path.unlink()
                except Exception:
                    pass
            QMessageBox.critical(
                self,
                safe_tr("保存失败"),
                safe_tr("无法保存文件“{target}”：\n{exc}").format(target=target, exc=exc),
            )
            return False
        finally:
            self._compat_confirmed = False

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

    def print_document(self, printer: QPrinter | None = None) -> bool:
        """Prompt system print dialog and print current document to printer."""
        if printer is None:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
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
        """File > Print Preview: open the in-window Office 2003 preview (non-modal)."""
        if printer is None:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)

        try:
            self.open_print_preview_panel(printer)
            return True
        except Exception as exc:
            QMessageBox.critical(
                self,
                safe_tr("打印预览失败"),
                safe_tr("无法打开打印预览视口：\n{exc}").format(exc=exc),
            )
            return False

    def open_print_preview_panel(self, printer: QPrinter | None = None) -> Any:
        """Show the preview over the document area; returns the ``PrintPreviewPanel``."""
        from atboffice.ui.printing.preview_panel import PrintPreviewPanel

        existing = getattr(self, "_print_preview_panel", None)
        if existing is not None:
            try:
                existing.close_preview()
            except RuntimeError:
                pass
        if printer is None:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        host = self.centralWidget()
        panel = PrintPreviewPanel(printer, self.render_to_printer, parent=self, host=host)
        panel.print_requested.connect(lambda: self.print_document())
        panel.page_setup_requested.connect(lambda: self._preview_page_setup(panel))
        panel.closed.connect(self._on_print_preview_closed)
        self.print_preview_extras(panel)
        self._print_preview_panel = panel
        panel.show()
        panel.raise_()
        panel.setFocus()
        panel.refresh()
        return panel

    def _preview_page_setup(self, panel: Any) -> None:
        if self.open_page_setup():
            panel.refresh()

    def _on_print_preview_closed(self) -> None:
        self._print_preview_panel = None

    def print_preview_extras(self, panel: Any) -> None:
        """Subclass hook: add module controls (Print What, Color, Margins) to the preview."""

    def open_page_setup(self) -> bool:
        """Subclass hook for File > Page Setup; returns True when settings changed."""
        return False

    def export_pdf(self, output_path: str | Path | None = None) -> bool:
        """Export current document as lossless vector PDF file."""
        if output_path is None:
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

    def register_owned_timer(self, timer: QTimer) -> None:
        """Track a timer so ``cleanup_resources`` stops it even if not parented to self."""
        if timer not in self._owned_timers:
            self._owned_timers.append(timer)

    def stop_owned_timers(self) -> None:
        """Stop all timers explicitly registered with this window."""
        for timer in list(getattr(self, "_owned_timers", [])):
            try:
                if is_alive(timer) and timer.isActive():
                    timer.stop()
            except Exception:
                logger.debug("Failed to stop timer during window cleanup", exc_info=True)
        if hasattr(self, "_owned_timers"):
            self._owned_timers.clear()

    def cleanup_resources(self) -> None:
        """Explicitly disconnect model/window signals and stop pending QTimer instances.

        Called during window closing and prior to widget destruction to prevent
        dangling references, deferred event loops from dispatching into dead widgets,
        or background threads from lingering.
        """
        # 1. Stop recovery service autosave timer & background threads cleanly
        if hasattr(self, "recovery_service") and self.recovery_service is not None:
            try:
                self.recovery_service.cleanup()
            except Exception as exc:
                logger.debug("Error cleaning up recovery service: %s", exc)

        # 2. Stop explicitly owned timers and all descendant QTimer instances
        self.stop_owned_timers()
        from PySide6.QtCore import QTimer

        for timer in self.findChildren(QTimer):
            try:
                if is_alive(timer) and timer.isActive():
                    timer.stop()
            except Exception:
                logger.debug("Failed to stop timer during window cleanup", exc_info=True)

        # 3. Cancel any in-progress view gestures or edits
        cw = self.centralWidget()
        if cw is not None:
            grid = getattr(cw, "grid", None)
            if grid is not None and hasattr(grid, "cancel_drag"):
                try:
                    grid.cancel_drag(why="api")
                except Exception:
                    pass
            ec = getattr(cw, "editor_controller", None)
            if ec is not None and hasattr(ec, "cancel_editing"):
                try:
                    ec.cancel_editing()
                except Exception:
                    pass
            cleanup_hook = getattr(cw, "cleanup", None) or getattr(cw, "cleanup_resources", None)
            if callable(cleanup_hook):
                try:
                    cleanup_hook()
                except Exception:
                    pass

        # 4. Disconnect locale change listener
        try:
            get_i18n_manager().locale_changed.disconnect(self._on_locale_changed)
        except Exception:
            pass

    def closeEvent(self, event: QCloseEvent) -> None:
        """Intercept window close to prompt for unsaved changes and emit signal."""
        if getattr(self, "_is_closed", False):
            event.accept()
            return
        if getattr(self, "_in_close_event", False):
            event.accept()
            return

        self._in_close_event = True
        try:
            if self.maybe_save_prompt():
                self._is_closed = True
                from atboffice.core.diagnostics import record_action

                record_action("window_close_accepted", "base_window", {"app_name": self.app_name})

                # The user saved or discarded changes: the crash-recovery draft is obsolete.
                try:
                    self.recovery_service.clear_draft()
                except Exception as exc:
                    logger.debug("Could not clear recovery draft: %s", exc)
                self.cleanup_resources()

                event.accept()
                # Never spin the event loop or flush DeferredDelete here: Qt is still inside
                # QWidget::close() for this window. WindowManager keeps the window alive
                # until control returns to the outer event loop.
                self.window_closed.emit(self)
            else:
                event.ignore()
        finally:
            self._in_close_event = False

    def init_task_pane_dock(self, doc_type_name: str = "文档") -> Any:
        """Initialize and attach universal TaskPaneDock to right dock area."""
        from PySide6.QtCore import Qt

        from atboffice.ui.components.task_pane import TaskPaneDock
        from atboffice.ui.panes.clipboard_pane import ClipboardTaskPane

        if self.task_pane_dock is None:
            self.task_pane_dock = TaskPaneDock(self)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.task_pane_dock)
            self.task_pane_dock.action_requested.connect(self._on_task_pane_action)
            self.task_pane_dock.visibilityChanged.connect(self._on_task_pane_visibility_changed)

            # Register 24-item Office Clipboard Task Pane
            self.clipboard_pane = ClipboardTaskPane(parent=self.task_pane_dock)
            self.clipboard_pane.item_clicked.connect(self._on_clipboard_item_clicked)
            self.clipboard_pane.paste_all_requested.connect(self._on_clipboard_paste_all)
            self.task_pane_dock.register_pane("clipboard", safe_tr("剪贴板"), self.clipboard_pane)

            self.task_pane_dock.hide()
        return self.task_pane_dock

    def init_command_search_box(self) -> Any:
        """Initialize and attach universal CommandSearchBox to top right of menu bar."""
        if getattr(self, "command_search_box", None) is None:
            from PySide6.QtCore import Qt

            from atboffice.ui.components.command_search_box import CommandSearchBox

            reg = getattr(self, "action_registry", None)
            if (
                reg is None
                and hasattr(self, "menu_bar")
                and hasattr(self.menu_bar, "action_registry")
            ):
                reg = self.menu_bar.action_registry

            self.command_search_box = CommandSearchBox(action_registry=reg, parent=self)
            if hasattr(self, "menu_bar") and self.menu_bar is not None:
                self.menu_bar.setCornerWidget(self.command_search_box, Qt.Corner.TopRightCorner)
            elif self.menuBar() is not None:
                self.menuBar().setCornerWidget(self.command_search_box, Qt.Corner.TopRightCorner)

        return self.command_search_box

    def _on_clipboard_item_clicked(self, item: Any) -> None:
        """Paste a clip: images go through the editor's picture adapter, the rest via Paste."""
        mime = getattr(item, "mime_data", None)
        if (
            getattr(item, "item_type", "") == "image"
            and mime is not None
            and mime.hasImage()
            and hasattr(self, "insert_image_bytes")
        ):
            from PySide6.QtCore import QBuffer, QByteArray, QIODevice
            from PySide6.QtGui import QImage

            image = QImage(mime.imageData())
            if not image.isNull():
                buf = QByteArray()
                dev = QBuffer(buf)
                dev.open(QIODevice.OpenModeFlag.WriteOnly)
                image.save(dev, "PNG")
                dev.close()
                if self.insert_image_bytes(bytes(buf.data()), "png", safe_tr("剪贴板图片")):
                    return
        self.paste()

    def _on_clipboard_paste_all(self, items: list[Any]) -> None:
        """Handle Paste All by executing paste for all clippings."""
        for item in items:
            if hasattr(self, "clipboard_pane") and self.clipboard_pane is not None:
                self.clipboard_pane.paste_item(item)
            else:
                self.paste()

    def open_clipboard_pane(self) -> None:
        """Open or activate the Office Clipboard task pane."""
        if self.task_pane_dock is not None:
            self.task_pane_dock.show()
            self.task_pane_dock.show_pane("clipboard")

    def toggle_task_pane(self, pane_id: str | None = None) -> None:
        """Toggle or switch active task pane."""
        if self.task_pane_dock is not None:
            self.task_pane_dock.toggle_task_pane(pane_id)

    def show_task_pane(self, pane_id: str) -> None:
        """Display specified task pane."""
        if self.task_pane_dock is not None:
            self.task_pane_dock.show_pane(pane_id)

    def init_context_pane_follow(
        self, sets: list[Any], pane_aliases: dict[str, str] | None = None
    ) -> Any:
        """Initialize contextual task pane auto-follow (``RB.follow``) on TaskPaneDock."""
        reg = getattr(self, "action_registry", None)
        if self.task_pane_dock is None or reg is None:
            return None
        from atboffice.ui.panes.context_tools_pane import TaskPaneFollowController

        self.context_pane_controller = TaskPaneFollowController(
            window=self,
            task_pane_dock=self.task_pane_dock,
            action_registry=reg,
            sets=sets,
            pane_aliases=pane_aliases,
        )
        return self.context_pane_controller

    def notify_selection_context(self, context_kind: str | None) -> None:
        """Synchronize contextual task pane (and Ribbon if built) with selection."""
        ctrl = getattr(self, "context_pane_controller", None)
        if ctrl is not None:
            ctrl.sync_context(context_kind)
        ribbon = getattr(self, "_ribbon_bar", None)
        if ribbon is not None and hasattr(ribbon, "refresh_context"):
            ribbon.refresh_context()

    def _on_task_pane_visibility_changed(self, visible: bool) -> None:
        """Sync check state in view menu when task pane is opened or closed."""
        if hasattr(self, "menu_bar") and hasattr(self.menu_bar, "action_map"):
            if "taskPane" in self.menu_bar.action_map:
                self.menu_bar.action_map["taskPane"].setChecked(visible)

    def _on_task_pane_action(self, action: str) -> None:
        """Handle common action link clicks originating from task panes."""
        if action == "open_file":
            self.open_file_dialog()
        elif action == "new_blank":
            self.new_file()
        elif action == "new_web":
            self.new_web_page()
        elif action == "templates":
            self.show_templates_dialog()
        elif action == "help":
            self.show_help()
        elif action.startswith("search:"):
            self.show_help()

    THUMBNAIL_WIDTH = 240

    def render_thumbnail(self, width: int = THUMBNAIL_WIDTH) -> Any:
        """QImage preview of page 1 / the grid / slide 1 (subclass hook; None = none)."""
        return None

    def _cache_thumbnail(self, path: Path, recent: Any) -> None:
        try:
            image = self.render_thumbnail()
        except Exception:
            logger.debug("Thumbnail rendering failed for %s", path, exc_info=True)
            return
        if image is not None:
            recent.save_thumbnail(path, image)

    def undo_history(self, kind: str) -> list[str]:
        """Labels of the undo (or redo) history, most recent first."""
        self.flush_pending_edits()
        svc = self.undo_service()
        return svc.labels(kind) if svc is not None else []

    def undo_steps(self, kind: str, steps: int) -> None:
        """Undo (or redo) ``steps`` actions at once (Undo/Redo drop-down)."""
        self.flush_pending_edits()
        svc = self.undo_service()
        if svc is not None:
            if svc.undo_steps(kind, steps):
                self.after_undo_redo()
            return
        for _ in range(max(0, steps)):
            self._undo_redo(kind)

    def attach_undo_history(self) -> None:
        """Make the toolbar Undo/Redo drop-downs list the real history."""
        from atboffice.ui.components.undo_history import attach_undo_history

        attach_undo_history(self)

    def new_web_page(self) -> None:
        """New Document pane > Blank Web page (editors without a web view: a new document)."""
        self.new_file()

    def show_templates_dialog(self) -> int:
        """Open the Templates dialog to choose and instantiate a template."""
        from atboffice.ui.dialogs.templates_dialog import TemplatesDialog

        app_name = getattr(self, "app_name", "").lower()
        dlg = TemplatesDialog(app=app_name if app_name else None, parent=self)
        res = dlg.exec()
        if res == TemplatesDialog.DialogCode.Accepted:
            selected_id = dlg.get_selected_template_id()
            if selected_id:
                self.load_template(selected_id)
        return res

    def show_document_properties_dialog(self) -> int:
        """Open 5-tab Document Properties dialog."""
        from atboffice.ui.dialogs.document_properties_dialog import (
            DocumentPropertiesDialog,
        )

        meta = self.get_document_metadata()
        dlg = DocumentPropertiesDialog(meta, self)
        res = dlg.exec()
        if res == DocumentPropertiesDialog.DialogCode.Accepted:
            self.set_document_metadata(dlg.metadata)
        return res

    def get_document_metadata(self) -> Any:
        """Return document metadata for properties dialog."""
        import datetime

        from atboffice.ui.dialogs.document_properties_dialog import DocumentMetadata

        now = datetime.datetime.now()
        meta = DocumentMetadata(
            file_path=self.current_file_path,
            file_type=f"{self.app_name} 文档",
            title=self.current_file_path.stem if self.current_file_path else self.default_doc_name,
            created=now,
            modified=now,
            accessed=now,
        )
        if hasattr(self, "_document_metadata") and self._document_metadata is not None:
            meta = self._document_metadata
            meta.file_path = self.current_file_path
        return meta

    def set_document_metadata(self, metadata: Any) -> None:
        """Store updated document metadata."""
        self._document_metadata = metadata
        self.set_modified(True)

    def retranslate_ui(self) -> None:
        """Update localized UI strings when application language changes."""
        self.update_window_title()
        if self.task_pane_dock is not None:
            self.task_pane_dock.retranslate_ui()
        if getattr(self, "context_pane_controller", None) is not None:
            self.context_pane_controller.retranslate_ui()
        if getattr(self, "command_search_box", None) is not None:
            self.command_search_box.retranslate_ui()
        if getattr(self, "clipboard_pane", None) is not None:
            self.clipboard_pane.retranslate_ui()
