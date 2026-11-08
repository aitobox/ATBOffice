"""Document auto-recovery and draft persistence service.

Manages periodic background snapshots and crash-recovery drafts for active documents.
Ensures timers and background tasks terminate cleanly upon window or application close.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import QCoreApplication, QObject, QTimer

if TYPE_CHECKING:
    from atboffice.ui.shell.base_window import BaseOfficeWindow

logger = logging.getLogger(__name__)


def safe_tr(text: str) -> str:
    """Translate UI text safely for RecoveryService."""
    return QCoreApplication.translate("RecoveryService", text)


class RecoveryService(QObject):
    """Manages document autosave timers and recovery draft files for a window.

    Designed with robust lifecycle management so timers and worker threads
    stop cleanly and immediately during window close sequences.
    """

    DEFAULT_AUTOSAVE_INTERVAL_MS: int = 120000  # 2 minutes default

    def __init__(
        self,
        window: BaseOfficeWindow | None = None,
        recovery_dir: Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the recovery service for a target window.

        Args:
            window: Target office window being protected.
            recovery_dir: Directory where recovery drafts are written.
            parent: Optional QObject parent.
        """
        super().__init__(parent or window)
        self._window: BaseOfficeWindow | None = window
        self._recovery_dir: Path = recovery_dir or (
            Path(tempfile.gettempdir()) / "atboffice_recovery"
        )
        self._timer: QTimer = QTimer(self)
        self._timer.timeout.connect(self._on_autosave_timer_tick)
        self._is_running: bool = False
        self._worker_thread: threading.Thread | None = None
        self._stop_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()
        self._current_draft_file: Path | None = None

        try:
            self._recovery_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("Could not create recovery directory %s: %s", self._recovery_dir, exc)

    @property
    def window(self) -> BaseOfficeWindow | None:
        """Return attached window instance."""
        return self._window

    @property
    def recovery_dir(self) -> Path:
        """Return directory where drafts are stored."""
        return self._recovery_dir

    def is_running(self) -> bool:
        """Check whether the autosave timer is currently active."""
        return self._is_running and self._timer.isActive()

    def start(self, interval_ms: int | None = None) -> None:
        """Start or restart the periodic autosave timer.

        Args:
            interval_ms: Timer interval in milliseconds (defaults to DEFAULT_AUTOSAVE_INTERVAL_MS).
        """
        with self._lock:
            interval = interval_ms if interval_ms is not None else self.DEFAULT_AUTOSAVE_INTERVAL_MS
            self._stop_event.clear()
            self._is_running = True
            if not self._timer.isActive():
                self._timer.start(interval)
            logger.debug("RecoveryService started with interval %d ms", interval)

    def stop(self, timeout_ms: int = 1000) -> None:
        """Stop autosave timers and wait for background threads to terminate cleanly.

        Args:
            timeout_ms: Maximum milliseconds to wait for lingering background worker thread.
        """
        with self._lock:
            self._is_running = False
            self._stop_event.set()

            # 1. Stop pending QTimer instance cleanly
            try:
                if self._timer.isActive():
                    self._timer.stop()
            except (RuntimeError, Exception):
                pass

            # 2. Join background worker thread if active
            if self._worker_thread is not None and self._worker_thread.is_alive():
                logger.debug("Waiting for recovery worker thread to terminate...")
                self._worker_thread.join(timeout=timeout_ms / 1000.0)
                self._worker_thread = None

    def cleanup(self) -> None:
        """Full cleanup hook invoked during window close or destruction."""
        self.stop()
        self._window = None

    def trigger_autosave(self) -> bool:
        """Trigger an immediate autosave checkpoint if document is modified."""
        if self._window is None:
            return False

        try:
            is_modified = getattr(self._window, "is_modified", None)
            if callable(is_modified) and not is_modified():
                return False

            return self.save_draft()
        except Exception as exc:
            logger.warning("Autosave trigger encountered error: %s", exc)
            return False

    def save_draft(self, custom_content: bytes | None = None) -> bool:
        """Write a recovery draft file to disk.

        Args:
            custom_content: Optional raw bytes to write instead of reading from window.

        Returns:
            True if draft was written successfully.
        """
        if self._stop_event.is_set():
            return False

        try:
            doc_name = (
                getattr(self._window, "default_doc_name", lambda: "untitled")()
                if self._window
                else "untitled"
            )
            file_path = getattr(self._window, "current_file_path", None) if self._window else None
            base_name = file_path.stem if file_path else doc_name
            ext = file_path.suffix if file_path else ".bak"

            draft_filename = f"{base_name}_recovery_{os.getpid()}{ext}"
            target_path = self._recovery_dir / draft_filename

            if custom_content is not None:
                target_path.write_bytes(custom_content)
            elif self._window is not None:
                # If window provides do_save or snapshot hook
                do_save = getattr(self._window, "do_save", None)
                if callable(do_save):
                    do_save(target_path)
                else:
                    target_path.write_text("autosave_placeholder", encoding="utf-8")

            self._current_draft_file = target_path
            logger.debug("Saved recovery draft to %s", target_path)
            return True
        except Exception as exc:
            logger.warning("Failed to save recovery draft: %s", exc)
            return False

    def clear_draft(self) -> None:
        """Remove existing draft file upon successful user save or clean exit."""
        if self._current_draft_file is not None and self._current_draft_file.exists():
            try:
                self._current_draft_file.unlink(missing_ok=True)
                self._current_draft_file = None
            except Exception as exc:
                logger.warning("Could not remove draft %s: %s", self._current_draft_file, exc)

    def _on_autosave_timer_tick(self) -> None:
        """Timer callback triggering periodic autosave."""
        if not self._is_running or self._stop_event.is_set():
            return
        self.trigger_autosave()
