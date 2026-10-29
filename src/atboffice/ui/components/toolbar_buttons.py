"""Office 2003 Luna-style complex toolbar buttons: SplitButton and DropDownButton."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QPoint, QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPaintEvent, QPolygon
from PySide6.QtWidgets import (
    QMenu,
    QStyle,
    QStyleOptionToolButton,
    QToolButton,
    QWidget,
)

from atboffice.ui.styles.luna_2003 import (
    LUNA_BLUE_HOT_BORDER,
    format_mnemonic,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for toolbar buttons."""
    return QCoreApplication.translate("ToolbarButtons", text)


class OfficeSplitButton(QToolButton):
    """Office 2003 split tool button with default action and dropdown menu arrow.

    Clicking the main area executes the default action.
    Clicking the arrow area pops up the dropdown menu.
    Features a classic Luna 2003 vertical divider line between the action and arrow.
    """

    def __init__(
        self,
        action: QAction | None = None,
        menu: QMenu | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        if action:
            self.setDefaultAction(action)
        if menu:
            self.setMenu(menu)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        # Ensure standard Office 2003 height and room for the drop arrow
        return QSize(max(hint.width() + 4, 36), max(hint.height(), 22))

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        # Draw classic Office 2003 vertical separator and drop-down arrow
        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)

        arrow_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ToolButton,
            opt,
            QStyle.SubControl.SC_ToolButtonMenu,
            self,
        )

        if arrow_rect.isValid() and arrow_rect.width() > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

            # 1. Draw 1px vertical divider between main button and arrow area
            divider_x = arrow_rect.left()
            top_y = opt.rect.top() + 3
            bottom_y = opt.rect.bottom() - 3

            is_hovered = opt.state & QStyle.StateFlag.State_MouseOver
            is_enabled = opt.state & QStyle.StateFlag.State_Enabled

            if is_hovered and is_enabled:
                # Hot state divider
                painter.setPen(QColor(LUNA_BLUE_HOT_BORDER))
                painter.drawLine(divider_x, top_y, divider_x, bottom_y)
                painter.setPen(QColor("#FFFFFF"))
                painter.drawLine(divider_x + 1, top_y, divider_x + 1, bottom_y)
            else:
                # Subtle resting divider
                painter.setPen(QColor("#7BA4E0"))
                painter.drawLine(divider_x, top_y, divider_x, bottom_y)
                painter.setPen(QColor("#F1F9FF"))
                painter.drawLine(divider_x + 1, top_y, divider_x + 1, bottom_y)

            # 2. Draw down-arrow triangle centered in arrow_rect
            cx = arrow_rect.left() + arrow_rect.width() // 2
            cy = arrow_rect.top() + arrow_rect.height() // 2 - 1

            arrow_color = QColor("#000000") if is_enabled else QColor("#8D8D8D")
            painter.setBrush(arrow_color)
            painter.setPen(arrow_color)

            # 5px wide, 3px high down-pointing triangle
            points = [
                QPoint(cx - 2, cy - 1),
                QPoint(cx + 2, cy - 1),
                QPoint(cx, cy + 1),
            ]
            painter.drawPolygon(QPolygon(points))
            painter.end()


class OfficeDropDownButton(QToolButton):
    """Office 2003 dropdown tool button.

    Clicking anywhere on the button immediately displays the attached dropdown menu.
    Displays icon and/or text with a downward arrow indicator.
    """

    def __init__(
        self,
        text: str = "",
        icon: QIcon | None = None,
        menu: QMenu | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        if text:
            formatted = format_mnemonic(text)
            self.setText(formatted)
            self.setToolTip(formatted)
            self.setStatusTip(formatted)
            self.setAccessibleName(formatted)
        if icon:
            self.setIcon(icon)
        if menu:
            self.setMenu(menu)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(hint.width() + 10, max(hint.height(), 22))

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        # Draw down-arrow on the right side
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)

        is_enabled = opt.state & QStyle.StateFlag.State_Enabled
        arrow_color = QColor("#000000") if is_enabled else QColor("#8D8D8D")

        painter.setBrush(arrow_color)
        painter.setPen(arrow_color)

        cx = self.width() - 8
        cy = self.height() // 2 - 1

        points = [
            QPoint(cx - 2, cy - 1),
            QPoint(cx + 2, cy - 1),
            QPoint(cx, cy + 1),
        ]
        painter.drawPolygon(QPolygon(points))
        painter.end()
