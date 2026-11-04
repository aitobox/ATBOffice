"""Cross-platform cursor compatibility utilities.

Workarounds for known macOS Cocoa (libqcocoa) cursor crashes:
In macOS Cocoa and PySide6, certain Qt system cursor shapes like
``Qt.CursorShape.SizeAllCursor`` and ``Qt.CursorShape.WaitCursor``
trigger SIGTRAP (Trace/BPT trap: 5) or SIGSEGV inside Cocoa's event loop.
This module provides safe fallback mappings on macOS while preserving native
cursor shapes on Windows and Linux.
"""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication

# Mappings on macOS to avoid Cocoa trap/segfault
_MACOS_CURSOR_REPLACEMENTS: dict[Qt.CursorShape, Qt.CursorShape] = {
    Qt.CursorShape.SizeAllCursor: Qt.CursorShape.OpenHandCursor,
    Qt.CursorShape.WaitCursor: Qt.CursorShape.BusyCursor,
}


def get_safe_cursor(
    shape: Qt.CursorShape | QCursor,
    platform_name: str | None = None,
) -> Qt.CursorShape | QCursor:
    """Return a platform-safe cursor shape or QCursor.

    On macOS (Darwin), maps unstable cursor shapes (such as SizeAllCursor and
    WaitCursor) to safe alternatives (OpenHandCursor and BusyCursor).
    On other platforms, returns the cursor unmodified.

    Args:
        shape: Qt.CursorShape enum or QCursor instance.
        platform_name: Optional override for platform detection (default: sys.platform).

    Returns:
        A platform-safe Qt.CursorShape or QCursor.
    """
    current_platform = platform_name if platform_name is not None else sys.platform
    is_macos = current_platform == "darwin"

    if not is_macos:
        return shape

    if isinstance(shape, QCursor):
        underlying_shape = shape.shape()
        replacement = _MACOS_CURSOR_REPLACEMENTS.get(underlying_shape)
        if replacement is not None:
            return QCursor(replacement)
        return shape

    if isinstance(shape, Qt.CursorShape):
        return _MACOS_CURSOR_REPLACEMENTS.get(shape, shape)

    return shape


def set_safe_cursor(target: Any, shape: Qt.CursorShape | QCursor) -> None:
    """Safely apply a cursor to a QWidget, QGraphicsItem, or viewport.

    Args:
        target: Any object supporting ``setCursor()`` (e.g., QWidget, QGraphicsItem).
        shape: Desired cursor shape or QCursor.
    """
    if target is None:
        return
    safe_cursor = get_safe_cursor(shape)
    if hasattr(target, "setCursor"):
        target.setCursor(safe_cursor)


def safe_set_override_cursor(shape: Qt.CursorShape | QCursor) -> None:
    """Safely set the application override cursor with macOS protection."""
    safe_cursor = get_safe_cursor(shape)
    if isinstance(safe_cursor, Qt.CursorShape):
        QApplication.setOverrideCursor(QCursor(safe_cursor))
    else:
        QApplication.setOverrideCursor(safe_cursor)


def safe_restore_override_cursor() -> None:
    """Restore the application override cursor."""
    QApplication.restoreOverrideCursor()
