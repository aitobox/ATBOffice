"""Floating Close Full Screen bar for Quire."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


def safe_tr(text: str) -> str:
    """Translate UI text safely for CloseFullScreenBar."""
    return QCoreApplication.translate("CloseFullScreenBar", text)


class CloseFullScreenBar(QWidget):
    """Floating floating bar showing 'Close Full Screen' button."""

    close_full_screen_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._drag_pos: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._btn_close = QPushButton(safe_tr("关闭全屏"), self)
        self._btn_close.setToolTip(safe_tr("退出全屏模式并还原窗口 (Esc)"))
        self._btn_close.clicked.connect(self.close_full_screen_requested.emit)
        layout.addWidget(self._btn_close)

        self.setStyleSheet(
            """
            CloseFullScreenBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #EAF2FB, stop:1 #B9D1EA);
                border: 1px solid #7F9DB9;
                border-radius: 4px;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #DDE7EE);
                border: 1px solid #003C74;
                border-radius: 3px;
                padding: 4px 10px;
                font-size: 11px;
                color: #000000;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFF6D9, stop:1 #FEDC75);
                border-color: #E59700;
            }
            QPushButton:pressed {
                background: #E0C263;
            }
            """
        )
        self.adjustSize()
        self.retranslate_ui()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("全屏"))
        self._btn_close.setText(safe_tr("关闭全屏"))
        self._btn_close.setToolTip(safe_tr("退出全屏模式并还原窗口 (Esc)"))
