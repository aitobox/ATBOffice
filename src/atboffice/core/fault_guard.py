"""Unified Qt C++ object lifetime checks, safe single-shot timers, and event/slot fault guards."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import shiboken6
from PySide6.QtCore import QObject, QTimer

from atboffice.core.diagnostics import record_action
from atboffice.core.i18n import safe_tr

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def is_alive(obj: Any) -> bool:
    """Return True if ``obj`` is usable (not None, valid Qt C++ wrapper, not closed)."""
    if obj is None:
        return False
    if isinstance(obj, QObject):
        try:
            if not shiboken6.isValid(obj):
                return False
        except Exception:
            return False
    if getattr(obj, "_is_closed", False):
        return False
    win_fn = getattr(obj, "window", None)
    if callable(win_fn):
        try:
            win = win_fn()
            if win is not None and win is not obj and getattr(win, "_is_closed", False):
                return False
        except Exception:
            return False
    return True


def _report_non_paint_error(owner: Any, label: str, exc: Exception) -> None:
    """Surface unexpected UI errors on statusBar when available without blocking painting."""
    if not is_alive(owner):
        return
    try:
        win = owner.window() if callable(getattr(owner, "window", None)) else owner
        if win is not None and is_alive(win) and callable(getattr(win, "statusBar", None)):
            sb = win.statusBar()
            if sb is not None:
                sb.showMessage(safe_tr("操作出现异常（已记录日志）：{0}").format(exc), 4000)
    except Exception:
        logger.debug("Failed to surface status bar error for %s", label, exc_info=True)


def safe_single_shot(
    delay_ms: int,
    owner: QObject | None,
    callback: Callable[[], Any],
) -> QTimer | None:
    """Schedule ``callback`` after ``delay_ms`` only while ``owner`` stays alive."""
    if owner is None or not is_alive(owner):
        return None
    timer = QTimer(owner)
    timer.setSingleShot(True)

    def _fire() -> None:
        if not is_alive(owner):
            return
        try:
            callback()
        except Exception:
            logger.exception("Unhandled error in safe_single_shot callback")
            record_action("qt_timer_error", "fault_guard", {})

    timer.timeout.connect(_fire)
    if hasattr(owner, "destroyed"):
        owner.destroyed.connect(timer.stop)
    timer.start(max(0, int(delay_ms)))
    return timer


def guard_qt_slot(component: str, action_name: str, default: Any = None) -> Callable[[F], F]:
    """Decorator guarding Qt slots against dead C++ wrappers and unhandled Python exceptions."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            if not is_alive(self):
                return default
            try:
                return fn(self, *args, **kwargs)
            except Exception as exc:
                logger.exception("Error in Qt slot %s.%s", component, action_name)
                record_action(
                    f"qt_slot_error:{action_name}",
                    component,
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
                _report_non_paint_error(self, action_name, exc)
                return default

        return wrapper  # type: ignore[return-value]

    return decorator


def guard_qt_event(component: str, event_name: str, default: bool = False) -> Callable[[F], F]:
    """Decorator guarding Qt event overrides against dead objects and unhandled exceptions."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            if not is_alive(self):
                return default
            try:
                return fn(self, *args, **kwargs)
            except Exception as exc:
                logger.exception("Error in Qt event %s.%s", component, event_name)
                record_action(
                    f"qt_event_error:{event_name}",
                    component,
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
                if "paint" not in event_name.lower():
                    _report_non_paint_error(self, event_name, exc)
                return default

        return wrapper  # type: ignore[return-value]

    return decorator
