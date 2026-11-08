"""Unit and integration tests for window close re-entrancy prevention and lifecycle cleanup."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QWidget

from atboffice.core.diagnostics import drain_event_loop
from atboffice.core.recovery_service import RecoveryService
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


@pytest.fixture(scope="module")
def qapp():
    """Ensure QApplication instance is initialized."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_drain_event_loop_reentrancy_guard(qapp):
    """Calling drain_event_loop re-entrantly must not cause recursion or deadlock."""
    recursion_attempted = False
    nested_executed = False

    def on_timer():
        nonlocal recursion_attempted, nested_executed
        recursion_attempted = True
        # Recursive invocation inside event loop processing
        drain_event_loop(2)
        nested_executed = True

    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(on_timer)
    timer.start(0)

    # Trigger outer event loop drain
    drain_event_loop(5)

    assert recursion_attempted is True
    assert nested_executed is True


def test_recovery_service_lifecycle_and_clean_stop(qapp, tmp_path):
    """RecoveryService must start and stop timer and background tasks cleanly."""
    service = RecoveryService(recovery_dir=tmp_path)
    service.start(interval_ms=50)

    assert service.is_running() is True
    assert service._timer.isActive() is True

    # Test draft saving
    saved = service.save_draft(custom_content=b"test_draft_content")
    assert saved is True
    assert service._current_draft_file is not None
    assert service._current_draft_file.exists()
    assert service._current_draft_file.read_bytes() == b"test_draft_content"

    # Stop service
    service.stop(timeout_ms=500)
    assert service.is_running() is False
    assert service._timer.isActive() is False

    # Clear draft
    service.clear_draft()
    assert service._current_draft_file is None


def test_base_office_window_close_stops_child_timers(qapp):
    """Closing BaseOfficeWindow must stop all child QTimer instances and recovery service."""
    win = BaseOfficeWindow()
    win.show()

    child_widget = QWidget(win)
    timer1 = QTimer(win)
    timer2 = QTimer(child_widget)

    timer1.start(1000)
    timer2.start(1000)
    win.recovery_service.start(1000)

    assert timer1.isActive() is True
    assert timer2.isActive() is True
    assert win.recovery_service.is_running() is True

    # Close window
    win.close()
    drain_event_loop(2)

    assert timer1.isActive() is False
    assert timer2.isActive() is False
    assert win.recovery_service.is_running() is False
    assert win._is_closed is True


def test_window_close_reentrancy_prevention(qapp):
    """Rapid repeated close calls must be intercepted by re-entrancy guards."""
    win = BaseOfficeWindow()
    win.show()

    drain_count = 0
    original_drain = drain_event_loop

    def counted_drain(iters=2):
        nonlocal drain_count
        drain_count += 1
        original_drain(iters)

    event1 = QCloseEvent()
    win.closeEvent(event1)
    assert event1.isAccepted() is True
    assert win._is_closed is True

    # Immediate second close event
    event2 = QCloseEvent()
    win.closeEvent(event2)
    assert event2.isAccepted() is True

    drain_event_loop(2)


def test_rapid_multi_window_lifecycle(qapp):
    """Rapid open/close across Quire, Ledger, and Lectern windows must not hang or crash."""
    for cls in (QuireWindow, LedgerWindow, LecternWindow):
        win = cls()
        win.show()
        # Verify recovery service is attached and active
        assert hasattr(win, "recovery_service")
        win.recovery_service.start(5000)

        # Trigger rapid close
        win.close()
        drain_event_loop(2)

        assert win._is_closed is True
        assert win.recovery_service.is_running() is False
