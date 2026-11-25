"""Application entry point and macOS native event dispatcher."""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFileOpenEvent, QGuiApplication
from PySide6.QtWidgets import QApplication


class ATBApplication(QApplication):
    """Custom QApplication providing High-DPI configuration and macOS file dispatch."""

    file_open_requested = Signal(str)

    def __init__(self, argv: list[str] | None = None) -> None:
        # Configure High DPI scaling policy before Qt constructs display surfaces
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        super().__init__(argv if argv is not None else sys.argv)
        self.setApplicationName("ATBOffice")
        self.setOrganizationName("ATBOffice")

        self._pending_files: list[str] = []
        self._main_window: Any | None = None

        from atboffice.core.diagnostics import drain_event_loop

        self.aboutToQuit.connect(drain_event_loop)

        from atboffice.utils.font_registry import register_bundled_fonts

        register_bundled_fonts()

        # The same light Luna look on every platform, whatever the system
        # theme; the saved theme is applied later by the startup settings.
        from atboffice.ui.styles.luna_2003 import apply_application_look

        apply_application_look(self)

    @property
    def pending_files(self) -> list[str]:
        """Return a copy of the pending file queue."""
        return list(self._pending_files)

    def register_main_window(self, window: Any) -> None:
        """Register the primary active window and flush pending file open events."""
        self._main_window = window
        while self._pending_files:
            file_path = self._pending_files.pop(0)
            if hasattr(window, "open_file"):
                window.open_file(file_path)

    def event(self, event: QEvent) -> bool:
        """Intercept application-level events including macOS QFileOpenEvent."""
        if event.type() == QEvent.Type.FileOpen:
            file_path = ""
            if isinstance(event, QFileOpenEvent):
                file_path = event.file()
                if not file_path and event.url().isValid():
                    file_path = event.url().toLocalFile()

            if file_path:
                self.file_open_requested.emit(file_path)
                if self._main_window is not None and hasattr(self._main_window, "open_file"):
                    self._main_window.open_file(file_path)
                else:
                    self._pending_files.append(file_path)
                event.accept()
                return True

        return super().event(event)


def create_application(argv: list[str] | None = None) -> ATBApplication:
    """Create the ATBApplication, or return the one that already exists.

    Only one QApplication can exist per process, and the suite relies on the
    ATBApplication behavior (file-open events, fonts, the Luna look), so a
    plain QApplication created by someone else is an error.
    """
    existing = QApplication.instance()
    if existing is None:
        return ATBApplication(argv)
    if isinstance(existing, ATBApplication):
        return existing
    raise RuntimeError(
        "A plain QApplication already exists; create the application with "
        "atboffice.core.app.create_application() instead."
    )
