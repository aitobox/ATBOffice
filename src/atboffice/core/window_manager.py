"""Core window lifecycle manager, extension dispatcher, and coordinator."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, QObject
from PySide6.QtWidgets import QApplication

from atboffice.core.recent_files import RecentFilesManager

if TYPE_CHECKING:
    from atboffice.ui.shell.base_window import BaseOfficeWindow

logger = logging.getLogger(__name__)


def safe_tr(text: str) -> str:
    """Translate UI text safely for WindowManager."""
    return QCoreApplication.translate("WindowManager", text)


class WindowManager(QObject):
    """Central singleton managing window lifecycle, routing, and auto-resurrection."""

    _instance: WindowManager | None = None

    # Extension routing lookup tables
    QUIRE_EXTENSIONS: frozenset[str] = frozenset(
        {".docx", ".doc", ".odt", ".rtf", ".txt", ".html", ".htm"}
    )
    LEDGER_EXTENSIONS: frozenset[str] = frozenset(
        {".xlsx", ".xls", ".csv", ".tsv", ".ods"}
    )
    LECTERN_EXTENSIONS: frozenset[str] = frozenset({".pptx", ".ppt", ".odp"})

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize WindowManager instance."""
        super().__init__(parent)
        self._start_center: BaseOfficeWindow | None = None
        self._active_windows: set[BaseOfficeWindow] = set()
        self.recent_files: RecentFilesManager = RecentFilesManager()
        self._is_quitting: bool = False

        if WindowManager._instance is None:
            WindowManager._instance = self

    @classmethod
    def get_instance(cls) -> WindowManager:
        """Return the global WindowManager singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for clean unit testing)."""
        cls._instance = None

    @property
    def start_center(self) -> BaseOfficeWindow | None:
        """Return the start center window instance if created."""
        return self._start_center

    @property
    def active_windows(self) -> set[BaseOfficeWindow]:
        """Return a copy of the active document windows set."""
        return set(self._active_windows)

    def detect_app_type(self, path: str | Path) -> str:
        """Determine module routing key from file extension.

        Args:
            path: Target file path or filename.

        Returns:
            One of 'quire', 'ledger', 'lectern', or 'generic'.
        """
        if not path:
            return "generic"

        ext = Path(path).suffix.lower()
        if ext in self.QUIRE_EXTENSIONS:
            return "quire"
        if ext in self.LEDGER_EXTENSIONS:
            return "ledger"
        if ext in self.LECTERN_EXTENSIONS:
            return "lectern"
        return "generic"

    def show_start_center(self) -> BaseOfficeWindow:
        """Create or reveal and raise the Start Center window."""
        if self._start_center is None:
            try:
                from atboffice.ui.shell.start_center import StartCenterWindow

                self._start_center = StartCenterWindow()
            except (ImportError, Exception) as exc:
                logger.debug(
                    "StartCenterWindow not yet available, falling back to BaseOfficeWindow: %s",
                    exc,
                )
                from atboffice.ui.shell.base_window import BaseOfficeWindow

                self._start_center = BaseOfficeWindow()
                self._start_center.setWindowTitle("ATBOffice Start Center")

        # Refresh recent files view if the window supports it
        if hasattr(self._start_center, "refresh_recent_files"):
            try:
                self._start_center.refresh_recent_files()
            except Exception as exc:
                logger.warning("Error refreshing start center recents: %s", exc)

        self._start_center.show()
        self._start_center.raise_()
        self._start_center.activateWindow()
        return self._start_center

    def register_window(self, win: BaseOfficeWindow) -> None:
        """Register an active document window and connect its close signal.

        Args:
            win: Active document window to register.
        """
        if win is self._start_center:
            return

        if win not in self._active_windows:
            self._active_windows.add(win)
            try:
                win.window_closed.connect(self.unregister_window)
            except (TypeError, RuntimeError):
                pass

        # Hide start center when a document window is displayed
        if (
            self._start_center is not None
            and self._start_center is not win
            and self._start_center.isVisible()
        ):
            self._start_center.hide()

    def unregister_window(self, win: Any) -> None:
        """Unregister a closed window and resurrect Start Center if active windows reach 0.

        Args:
            win: Window instance being closed.
        """
        was_active = win in self._active_windows
        if was_active:
            self._active_windows.remove(win)
            try:
                win.window_closed.disconnect(self.unregister_window)
            except (TypeError, RuntimeError):
                pass

        if was_active and not self._is_quitting and len(self._active_windows) == 0:
            self.show_start_center()

    def open_quire(self, path: str | Path | None = None) -> BaseOfficeWindow:
        """Open a Quire word-processing window.

        Args:
            path: Optional document file path to load.

        Returns:
            The created and registered Quire window.
        """
        win: BaseOfficeWindow
        try:
            from atboffice.ui.shell.quire_window import QuireWindow

            win = QuireWindow()
        except (ImportError, Exception) as exc:
            logger.debug(
                "QuireWindow not yet available, falling back to BaseOfficeWindow: %s",
                exc,
            )
            from atboffice.ui.shell.base_window import BaseOfficeWindow

            win = BaseOfficeWindow()
            win.app_name = "Quire"

        if path is not None:
            resolved = Path(path).resolve()
            win.current_file_path = resolved
            win.update_window_title()
            self.recent_files.add_file(resolved, "quire")

        self.register_window(win)
        win.show()
        win.raise_()
        win.activateWindow()
        return win

    def open_ledger(self, path: str | Path | None = None) -> BaseOfficeWindow:
        """Open a Ledger spreadsheet window.

        Args:
            path: Optional spreadsheet file path to load.

        Returns:
            The created and registered Ledger window.
        """
        win: BaseOfficeWindow
        try:
            from atboffice.ui.shell.ledger_window import LedgerWindow

            win = LedgerWindow()
        except (ImportError, Exception) as exc:
            logger.debug(
                "LedgerWindow not yet available, falling back to BaseOfficeWindow: %s",
                exc,
            )
            from atboffice.ui.shell.base_window import BaseOfficeWindow

            win = BaseOfficeWindow()
            win.app_name = "Ledger"

        if path is not None:
            resolved = Path(path).resolve()
            win.current_file_path = resolved
            win.update_window_title()
            self.recent_files.add_file(resolved, "ledger")

        self.register_window(win)
        win.show()
        win.raise_()
        win.activateWindow()
        return win

    def open_lectern(self, path: str | Path | None = None) -> BaseOfficeWindow:
        """Open a Lectern presentation window.

        Args:
            path: Optional presentation file path to load.

        Returns:
            The created and registered Lectern window.
        """
        win: BaseOfficeWindow
        try:
            from atboffice.ui.shell.lectern_window import LecternWindow

            win = LecternWindow()
        except (ImportError, Exception) as exc:
            logger.debug(
                "LecternWindow not yet available, falling back to BaseOfficeWindow: %s",
                exc,
            )
            from atboffice.ui.shell.base_window import BaseOfficeWindow

            win = BaseOfficeWindow()
            win.app_name = "Lectern"

        if path is not None:
            resolved = Path(path).resolve()
            win.current_file_path = resolved
            win.update_window_title()
            self.recent_files.add_file(resolved, "lectern")

        self.register_window(win)
        win.show()
        win.raise_()
        win.activateWindow()
        return win

    def open_file_auto(self, path: str | Path) -> BaseOfficeWindow:
        """Open a file with appropriate office window based on its extension.

        Args:
            path: Target document path.

        Returns:
            The created and registered document window.
        """
        app_type = self.detect_app_type(path)
        if app_type == "quire":
            return self.open_quire(path)
        if app_type == "ledger":
            return self.open_ledger(path)
        if app_type == "lectern":
            return self.open_lectern(path)
        return self.open_quire(path)

    def quit_application(self) -> bool:
        """Check all modified windows and quit the application if approved.

        Returns:
            True if application quit cleanly, False if cancelled by user.
        """
        windows_to_check = list(self._active_windows)

        # First pass: check unsaved modifications with atomic cancel
        for win in windows_to_check:
            if win.is_modified:
                if not win.maybe_save_prompt():
                    # User clicked Cancel; abort exit immediately
                    return False

        # All windows saved or discarded; proceed with shutdown
        self._is_quitting = True

        for win in windows_to_check:
            win.set_modified(False)
            self.unregister_window(win)
            win.close()

        if self._start_center is not None:
            self._start_center.close()
            self._start_center = None

        app = QApplication.instance()
        if app is not None:
            app.quit()

        return True
