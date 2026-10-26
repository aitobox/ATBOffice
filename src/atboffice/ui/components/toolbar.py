"""Classic Office 2003 Command Bar and custom dotted grip toolbar components."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPaintEvent
from PySide6.QtWidgets import QToolBar, QWidget

from atboffice.ui.styles.luna_2003 import (
    LUNA_BLUE_GRIP,
    LUNA_BLUE_GRIP_HI,
    format_mnemonic,
)


class DottedGrip(QWidget):
    """Classic Office 2003 3D dotted grip handle with shadow and highlight dots."""

    def __init__(self, parent: QToolBar | None = None) -> None:
        super().__init__(parent)
        self.toolbar = parent
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFixedWidth(7)
        self.setMinimumHeight(18)

    def sizeHint(self) -> QSize:
        if self.toolbar and self.toolbar.orientation() == Qt.Orientation.Vertical:
            return QSize(18, 7)
        return QSize(7, 22)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        is_vertical = self.toolbar and self.toolbar.orientation() == Qt.Orientation.Vertical
        dot_color = QColor(LUNA_BLUE_GRIP)
        hi_color = QColor(LUNA_BLUE_GRIP_HI)

        rect = self.rect()

        if not is_vertical:
            # Horizontal toolbar: draw 2 vertical columns of dots
            x_start = rect.left() + 1
            y_start = rect.top() + (rect.height() - 16) // 2
            for col in range(2):
                x = x_start + col * 3
                for row in range(5):
                    y = y_start + row * 3
                    # Highlight offset by +1, +1
                    painter.fillRect(x + 1, y + 1, 1, 1, hi_color)
                    # Shadow dot
                    painter.fillRect(x, y, 1, 1, dot_color)
        else:
            # Vertical toolbar: draw 2 horizontal rows of dots
            x_start = rect.left() + (rect.width() - 16) // 2
            y_start = rect.top() + 1
            for row in range(2):
                y = y_start + row * 3
                for col in range(5):
                    x = x_start + col * 3
                    painter.fillRect(x + 1, y + 1, 1, 1, hi_color)
                    painter.fillRect(x, y, 1, 1, dot_color)

        painter.end()


class OfficeToolBarSeparator(QWidget):
    """Office 2003 classic double-line 3D separator."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(4)
        self.setMinimumHeight(18)

    def sizeHint(self) -> QSize:
        return QSize(4, 22)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        h = self.height()
        y1 = 2
        y2 = h - 3

        # Dark line on left (#6A8CCB), light line on right (#F1F9FF)
        painter.setPen(QColor("#6A8CCB"))
        painter.drawLine(1, y1, 1, y2)
        painter.setPen(QColor("#F1F9FF"))
        painter.drawLine(2, y1, 2, y2)
        painter.end()


class OfficeToolBar(QToolBar):
    """Office 2003 styled toolbar with custom dotted grip handle and mnemonic actions."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setObjectName(f"OfficeToolBar_{title}")
        self.setMovable(True)
        self.setFloatable(True)
        self.setIconSize(QSize(16, 16))

        # Dotted grip handle at the front
        self.grip_handle = DottedGrip(self)
        self._grip_action = self.addWidget(self.grip_handle)

        self.orientationChanged.connect(self._on_orientation_changed)

    def _on_orientation_changed(self, orientation: Qt.Orientation) -> None:
        if orientation == Qt.Orientation.Vertical:
            self.grip_handle.setFixedHeight(7)
            self.grip_handle.setMinimumWidth(18)
        else:
            self.grip_handle.setFixedWidth(7)
            self.grip_handle.setMinimumHeight(18)
        self.grip_handle.updateGeometry()
        self.grip_handle.update()

    def setMovable(self, movable: bool) -> None:
        super().setMovable(movable)
        if hasattr(self, "grip_handle"):
            self.grip_handle.setVisible(movable)

    def add_office_action(
        self,
        text: str,
        icon: QIcon | None = None,
        tooltip: str = "",
        callback: Callable[..., Any] | None = None,
        checkable: bool = False,
    ) -> QAction:
        """Create and add a toolbar action with platform-aware mnemonic handling."""
        action_text = format_mnemonic(text)
        action = QAction(action_text, self)
        if icon:
            action.setIcon(icon)
        if tooltip:
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
        if checkable:
            action.setCheckable(True)
        if callback:
            action.triggered.connect(callback)

        self.addAction(action)
        return action

    def add_office_separator(self) -> QAction:
        """Add classic Office 2003 double-line separator."""
        sep = OfficeToolBarSeparator(self)
        return self.addWidget(sep)
