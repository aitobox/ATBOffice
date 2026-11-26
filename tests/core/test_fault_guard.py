"""Unit tests for core.fault_guard lifetime checks, safe timers, and exception isolation."""

from __future__ import annotations

import logging

import shiboken6
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMainWindow

from atboffice.core.diagnostics import ActionRecorder
from atboffice.core.fault_guard import (
    guard_qt_event,
    guard_qt_slot,
    is_alive,
    safe_single_shot,
)


def test_is_alive_handles_none_plain_and_deleted_qobject(qapp) -> None:
    assert is_alive(None) is False
    assert is_alive(object()) is True
    obj = QObject()
    assert is_alive(obj) is True
    shiboken6.delete(obj)
    assert is_alive(obj) is False


def test_is_alive_respects_closed_window_flag(qtbot) -> None:
    win = QMainWindow()
    qtbot.addWidget(win)
    assert is_alive(win) is True
    win._is_closed = True  # type: ignore[attr-defined]
    assert is_alive(win) is False


def test_safe_single_shot_skips_callback_when_owner_destroyed(qapp) -> None:
    owner = QObject()
    called: list[str] = []
    timer = safe_single_shot(0, owner, lambda: called.append("ran"))
    assert timer is not None
    shiboken6.delete(owner)
    qapp.processEvents()
    assert called == []


def test_guard_qt_slot_and_event_isolate_exceptions_and_record_breadcrumb(caplog) -> None:
    ActionRecorder.reset_instance()

    class Dummy(QObject):
        @guard_qt_slot("dummy", "explode", default="fallback")
        def boom_slot(self) -> str:
            raise RuntimeError("slot failed")

        @guard_qt_event("dummy", "mouse_press", default=True)
        def boom_event(self, _ev: object) -> bool:
            raise ValueError("event failed")

    d = Dummy()
    with caplog.at_level(logging.ERROR):
        assert d.boom_slot() == "fallback"
        assert d.boom_event(None) is True

    actions = [a["action"] for a in ActionRecorder.get_instance().get_recent_actions()]
    assert "qt_slot_error:explode" in actions
    assert "qt_event_error:mouse_press" in actions
    assert "slot failed" in caplog.text
    assert "event failed" in caplog.text


def test_base_window_stops_registered_owned_timers_on_cleanup(qtbot) -> None:
    from PySide6.QtCore import QTimer

    from atboffice.ui.shell.base_window import BaseOfficeWindow

    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    timer = QTimer()
    timer.start(10_000)
    win.register_owned_timer(timer)
    assert timer.isActive()
    win.cleanup_resources()
    assert not timer.isActive()
