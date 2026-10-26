"""Tab selector corner button widget for Quire rulers."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from atboffice.modules.writer.views.rulers.types import (
    TAB_KINDS,
    TabKind,
    draw_tab_glyph,
    safe_tr,
)


class TabSelectorWidget(QWidget):
    """Word 2003 corner button cycling through tab stops and indent selector modes."""

    tab_kind_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_index: int = 0
        self._is_pressed: bool = False
        self._hovered: bool = False

        self.setFixedSize(QSize(24, 24))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retranslate_ui()

    @property
    def current_kind(self) -> TabKind:
        """Currently active tab kind."""
        return TAB_KINDS[self._current_index][0]

    def set_kind(self, kind: TabKind | str) -> None:
        """Set the active tab kind explicitly."""
        target = kind if isinstance(kind, TabKind) else TabKind(kind)
        for i, (k, _) in enumerate(TAB_KINDS):
            if k == target:
                if self._current_index != i:
                    self._current_index = i
                    self._update_tooltip()
                    self.tab_kind_changed.emit(self.current_kind.value)
                    self.update()
                break

    def cycle_next(self) -> TabKind:
        """Cycle to the next tab kind."""
        self._current_index = (self._current_index + 1) % len(TAB_KINDS)
        self._update_tooltip()
        self.tab_kind_changed.emit(self.current_kind.value)
        self.update()
        return self.current_kind

    def _update_tooltip(self) -> None:
        raw_name = TAB_KINDS[self._current_index][1]
        self.setToolTip(safe_tr(raw_name))

    def retranslate_ui(self) -> None:
        """Update localized tooltip string."""
        self._update_tooltip()

    # -----------------------------------------------------------------------
    # Events
    # -----------------------------------------------------------------------

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._is_pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_pressed = True
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._is_pressed:
            self._is_pressed = False
            self.cycle_next()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        rect = self.rect()

        # Word 2003 toolbar/ruler button bevel style
        bg_color = QColor(220, 226, 236) if self._hovered else QColor(236, 233, 216)
        if self._is_pressed:
            bg_color = QColor(200, 210, 225)
        painter.fillRect(rect, bg_color)

        # Draw border
        pen_dark = QColor(140, 140, 140)
        pen_light = QColor(255, 255, 255)

        if self._is_pressed:
            painter.setPen(QPen(pen_dark, 1.0))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
        else:
            painter.setPen(QPen(pen_light, 1.0))
            painter.drawLine(rect.topLeft(), rect.topRight())
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
            painter.setPen(QPen(pen_dark, 1.0))
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomRight())

        # Draw the active glyph centered
        center = QPointF(rect.width() / 2.0, rect.height() / 2.0)
        draw_tab_glyph(painter, self.current_kind, center, size=11.0)
