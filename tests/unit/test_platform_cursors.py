"""Unit tests for platform-specific cursor adaptation."""

import sys
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QWidget

from atboffice.platform.cursors import (
    get_safe_cursor,
    set_safe_cursor,
    safe_set_override_cursor,
    safe_restore_override_cursor,
)


class TestPlatformCursors:
    def test_macos_cursor_mapping(self) -> None:
        # SizeAllCursor must map to OpenHandCursor on macOS
        safe_size_all = get_safe_cursor(Qt.CursorShape.SizeAllCursor, platform_name="darwin")
        assert safe_size_all == Qt.CursorShape.OpenHandCursor

        # WaitCursor must map to BusyCursor on macOS
        safe_wait = get_safe_cursor(Qt.CursorShape.WaitCursor, platform_name="darwin")
        assert safe_wait == Qt.CursorShape.BusyCursor

        # Other standard cursors must remain unchanged
        assert get_safe_cursor(Qt.CursorShape.ArrowCursor, platform_name="darwin") == Qt.CursorShape.ArrowCursor
        assert get_safe_cursor(Qt.CursorShape.PointingHandCursor, platform_name="darwin") == Qt.CursorShape.PointingHandCursor
        assert get_safe_cursor(Qt.CursorShape.CrossCursor, platform_name="darwin") == Qt.CursorShape.CrossCursor
        assert get_safe_cursor(Qt.CursorShape.SplitHCursor, platform_name="darwin") == Qt.CursorShape.SplitHCursor
        assert get_safe_cursor(Qt.CursorShape.SplitVCursor, platform_name="darwin") == Qt.CursorShape.SplitVCursor

    def test_non_macos_cursor_preservation(self) -> None:
        # On Linux/Windows, shapes should not be altered
        for plat in ["linux", "win32"]:
            assert get_safe_cursor(Qt.CursorShape.SizeAllCursor, platform_name=plat) == Qt.CursorShape.SizeAllCursor
            assert get_safe_cursor(Qt.CursorShape.WaitCursor, platform_name=plat) == Qt.CursorShape.WaitCursor
            assert get_safe_cursor(Qt.CursorShape.ArrowCursor, platform_name=plat) == Qt.CursorShape.ArrowCursor

    def test_qcursor_instance_handling(self, qapp: QApplication) -> None:
        # Handling when QCursor object is passed
        cursor_size_all = QCursor(Qt.CursorShape.SizeAllCursor)
        safe_cursor = get_safe_cursor(cursor_size_all, platform_name="darwin")
        assert isinstance(safe_cursor, QCursor)
        assert safe_cursor.shape() == Qt.CursorShape.OpenHandCursor

        cursor_arrow = QCursor(Qt.CursorShape.ArrowCursor)
        safe_arrow = get_safe_cursor(cursor_arrow, platform_name="darwin")
        assert safe_arrow.shape() == Qt.CursorShape.ArrowCursor

    def test_set_safe_cursor(self, qapp: QApplication) -> None:
        widget = QWidget()
        set_safe_cursor(widget, Qt.CursorShape.SizeAllCursor)
        expected_shape = (
            Qt.CursorShape.OpenHandCursor if sys.platform == "darwin" else Qt.CursorShape.SizeAllCursor
        )
        assert widget.cursor().shape() == expected_shape

    def test_safe_override_cursor(self, qapp: QApplication) -> None:
        safe_set_override_cursor(Qt.CursorShape.WaitCursor)
        expected_shape = (
            Qt.CursorShape.BusyCursor if sys.platform == "darwin" else Qt.CursorShape.WaitCursor
        )
        assert QApplication.overrideCursor().shape() == expected_shape
        safe_restore_override_cursor()
        assert QApplication.overrideCursor() is None
