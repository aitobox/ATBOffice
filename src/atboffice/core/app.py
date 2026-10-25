"""Application entry point and macOS native event dispatcher."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QFileOpenEvent, QGuiApplication
from PySide6.QtWidgets import QApplication

if TYPE_CHECKING:
    from atboffice.ui.shell.main_window import MainWindow


class _AppDispatcher(QObject):
    """Auxiliary dispatcher object for dynamic signal binding."""

    file_open_requested = Signal(str)


class _FileOpenEventFilter(QObject):
    """Event filter for intercepting QFileOpenEvent on existing QApplication instances."""

    def __init__(self, app: QApplication, dispatcher: _AppDispatcher) -> None:
        super().__init__(app)
        self.app = app
        self.dispatcher = dispatcher

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.FileOpen:
            file_path = ""
            if isinstance(event, QFileOpenEvent):
                file_path = event.file()
                if not file_path and event.url().isValid():
                    file_path = event.url().toLocalFile()

            if file_path:
                self.dispatcher.file_open_requested.emit(file_path)
                main_win = getattr(self.app, "_main_window", None)
                if main_win is not None and hasattr(main_win, "open_file"):
                    main_win.open_file(file_path)
                else:
                    pending = getattr(self.app, "_pending_files", None)
                    if pending is not None:
                        pending.append(file_path)
                event.accept()
                return True
        return super().eventFilter(watched, event)


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
                if (
                    self._main_window is not None
                    and hasattr(self._main_window, "open_file")
                ):
                    self._main_window.open_file(file_path)
                else:
                    self._pending_files.append(file_path)
                event.accept()
                return True

        return super().event(event)


def create_application(argv: list[str] | None = None) -> ATBApplication:
    """Create or return the singleton ATBApplication instance."""
    existing = QApplication.instance()
    if existing is not None:
        if isinstance(existing, ATBApplication):
            return existing

        # Wrap existing QApplication dynamically for robust fallback
        if not hasattr(existing, "_dispatcher"):
            dispatcher = _AppDispatcher()
            setattr(existing, "_dispatcher", dispatcher)
            setattr(existing, "file_open_requested", dispatcher.file_open_requested)
            setattr(existing, "_pending_files", [])
            setattr(existing, "_main_window", None)

            def get_pending(self: Any = existing) -> list[str]:
                return list(self._pending_files)

            setattr(existing, "pending_files", property(get_pending).__get__(existing))

            orig_event = existing.event

            def wrapped_event(ev: QEvent) -> bool:
                if ev.type() == QEvent.Type.FileOpen:
                    fpath = ""
                    if isinstance(ev, QFileOpenEvent):
                        fpath = ev.file()
                        if not fpath and ev.url().isValid():
                            fpath = ev.url().toLocalFile()
                    if fpath:
                        dispatcher.file_open_requested.emit(fpath)
                        mwin = getattr(existing, "_main_window", None)
                        if mwin is not None and hasattr(mwin, "open_file"):
                            mwin.open_file(fpath)
                        else:
                            existing._pending_files.append(fpath)
                        ev.accept()
                        return True
                return orig_event(ev)

            setattr(existing, "event", wrapped_event)

            def _register_main_window(window: Any) -> None:
                setattr(existing, "_main_window", window)
                while existing._pending_files:
                    path = existing._pending_files.pop(0)
                    if hasattr(window, "open_file"):
                        window.open_file(path)

            setattr(existing, "register_main_window", _register_main_window)

            event_filter = _FileOpenEventFilter(existing, dispatcher)
            setattr(existing, "_file_event_filter", event_filter)
            existing.installEventFilter(event_filter)

        return existing  # type: ignore[return-value]

    return ATBApplication(argv)
