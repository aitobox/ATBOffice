"""Office 2003 classic 40-color standard palette and color picker components."""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPolygon
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QPushButton,
    QStyle,
    QStyleOptionToolButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.ui.icons import get_office_icon
from atboffice.ui.styles.luna_2003 import LUNA_BLUE_HOT_BORDER


def safe_tr(text: str) -> str:
    """Translate UI text safely for ColorPicker."""
    return core_safe_tr(text)


# Standard 40 colors of Office 2003 (5 rows x 8 columns)
OFFICE_2003_STANDARD_COLORS: Final[list[str]] = [
    "#000000", "#993300", "#333300", "#003300", "#003366", "#000080", "#333399", "#333333",
    "#800000", "#FF6600", "#808000", "#008000", "#008080", "#0000FF", "#666699", "#808080",
    "#FF0000", "#FF9900", "#99CC00", "#339966", "#33CCCC", "#3366FF", "#800080", "#969696",
    "#FF00FF", "#FFCC00", "#FFFF00", "#00FF00", "#00FFFF", "#00CCFF", "#993366", "#C0C0C0",
    "#FF99CC", "#FFCC99", "#FFFF99", "#CCFFCC", "#CCFFFF", "#99CCFF", "#CC99FF", "#FFFFFF",
]

# Accurate Office 2003 localized Chinese names for the 40 standard colors
COLOR_NAMES: Final[dict[str, str]] = {
    "#000000": "黑色",
    "#993300": "褐色",
    "#333300": "橄榄绿",
    "#003300": "深绿",
    "#003366": "深青",
    "#000080": "深蓝",
    "#333399": "靛青",
    "#333333": "80% 灰色",
    "#800000": "深红",
    "#FF6600": "橙色",
    "#808000": "暗黄",
    "#008000": "绿色",
    "#008080": "青色",
    "#0000FF": "蓝色",
    "#666699": "蓝灰",
    "#808080": "50% 灰色",
    "#FF0000": "红色",
    "#FF9900": "浅橙色",
    "#99CC00": "酸橙色",
    "#339966": "海绿",
    "#33CCCC": "水绿色",
    "#3366FF": "浅蓝",
    "#800080": "紫罗兰",
    "#969696": "40% 灰色",
    "#FF00FF": "粉红",
    "#FFCC00": "金色",
    "#FFFF00": "黄色",
    "#00FF00": "鲜绿",
    "#00FFFF": "青绿",
    "#00CCFF": "天蓝",
    "#993366": "梅红",
    "#C0C0C0": "25% 灰色",
    "#FF99CC": "玫瑰红",
    "#FFCC99": "浅黄褐色",
    "#FFFF99": "浅黄",
    "#CCFFCC": "浅绿",
    "#CCFFFF": "浅青绿",
    "#99CCFF": "淡蓝",
    "#CC99FF": "浅紫",
    "#FFFFFF": "白色",
}


class SwatchButton(QPushButton):
    """Single color swatch cell in the 40-color grid."""

    def __init__(self, hex_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.hex_color = hex_color.upper()
        self.setFixedSize(18, 18)
        self.retranslate_ui()

        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {self.hex_color};
                border: 1px solid #7B9EBD;
                border-radius: 1px;
            }}
            QPushButton:hover {{
                border: 1px solid #000080;
                outline: 1px solid #FFE7A2;
            }}
            """
        )

    def retranslate_ui(self, tr_func: Callable[[str], str] | None = None) -> None:
        translate = tr_func or safe_tr
        name = COLOR_NAMES.get(self.hex_color, self.hex_color)
        tip_text = translate(name)
        self.setToolTip(tip_text)
        self.setStatusTip(tip_text)
        self.setAccessibleName(tip_text)


class ColorPickerPopup(QFrame):
    """Popup frame containing the Office 2003 40-color grid and special actions."""

    color_selected = Signal(str)

    def __init__(self, mode: str = "fill", parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.mode = mode
        self.setAccessibleName("OfficeColorPicker")
        self.setStyleSheet(
            """
            QFrame {
                background-color: #FCFCF9;
                border: 1px solid #002D96;
                padding: 3px;
            }
            QPushButton.action-btn {
                background: transparent;
                border: 1px solid transparent;
                padding: 4px;
                text-align: left;
                font-family: Tahoma, "Segoe UI", "PingFang SC", sans-serif;
                font-size: 11px;
                color: #000000;
            }
            QPushButton.action-btn:hover {
                background-color: #FFEEC2;
                border: 1px solid #000080;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 1. Top Action Button: Automatic or No Fill / No Line
        self.btn_auto_or_none = QPushButton(self)
        self.btn_auto_or_none.setProperty("class", "action-btn")
        if self.mode in ("fill", "line"):
            btn_text = safe_tr("无填充颜色") if self.mode == "fill" else safe_tr("无线条颜色")
            self.btn_auto_or_none.setText(btn_text)
            self.btn_auto_or_none.clicked.connect(lambda: self._select_special("none"))
        else:
            self.btn_auto_or_none.setText(safe_tr("自动"))
            self.btn_auto_or_none.clicked.connect(lambda: self._select_special("auto"))
        layout.addWidget(self.btn_auto_or_none)

        # Separator line
        sep1 = QFrame(self)
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep1)

        # 2. 40-Color Grid (5 rows x 8 cols)
        grid_widget = QWidget(self)
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(2)

        self.swatch_buttons: list[SwatchButton] = []
        for index, hex_code in enumerate(OFFICE_2003_STANDARD_COLORS):
            row = index // 8
            col = index % 8
            btn = SwatchButton(hex_code, grid_widget)
            btn.clicked.connect(lambda checked=False, c=hex_code: self._select_color(c))
            grid_layout.addWidget(btn, row, col)
            self.swatch_buttons.append(btn)

        layout.addWidget(grid_widget)

        # Separator line
        sep2 = QFrame(self)
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep2)

        # 3. Bottom Action Button: More Colors...
        self.btn_more_colors = QPushButton(safe_tr("其他颜色..."), self)
        self.btn_more_colors.setProperty("class", "action-btn")
        self.btn_more_colors.clicked.connect(self._open_more_colors_dialog)
        layout.addWidget(self.btn_more_colors)

    def retranslate_ui(self, tr_func: Callable[[str], str] | None = None) -> None:
        """Update localized text for action buttons and color swatches."""
        translate = tr_func or safe_tr
        if self.mode in ("fill", "line"):
            btn_text = translate("无填充颜色") if self.mode == "fill" else translate("无线条颜色")
        else:
            btn_text = translate("自动")
        self.btn_auto_or_none.setText(btn_text)
        self.btn_more_colors.setText(translate("其他颜色..."))
        for btn in self.swatch_buttons:
            btn.retranslate_ui(translate)

    def _select_special(self, value: str) -> None:
        self.color_selected.emit(value)
        self.close()

    def _select_color(self, hex_code: str) -> None:
        self.color_selected.emit(hex_code.upper())
        self.close()

    def _open_more_colors_dialog(self) -> None:
        self.close()
        from atboffice.ui.components.honeycomb_color_dialog import HoneycombColorDialog

        selected = HoneycombColorDialog.getColor(
            initial="#3366FF",
            parent=self.parentWidget(),
            title=safe_tr("颜色"),
        )
        if selected is not None and selected.isValid():
            self.color_selected.emit(selected.name().upper())


class ColorPickerButton(QToolButton):
    """Split tool button with a dropdown arrow and bottom color indicator bar."""

    color_applied = Signal(str)

    def __init__(
        self,
        mode: str = "font",
        default_color: str = "#000000",
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        self._current_color = default_color.upper()
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setIconSize(QSize(16, 16))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        default_tip = (
            "字体颜色"
            if mode == "font"
            else ("突出显示" if mode == "highlight" else "填充颜色")
        )
        self._raw_tip = tooltip or default_tip
        tip_text = safe_tr(self._raw_tip)
        self.setToolTip(tip_text)
        self.setStatusTip(tip_text)
        self.setAccessibleName(tip_text)

        icon_key = (
            "fontColor"
            if mode == "font"
            else ("highlight" if mode == "highlight" else "fillColor")
        )
        self.setIcon(get_office_icon(icon_key))

        self.popup = ColorPickerPopup(mode=self.mode, parent=self)
        self.popup.color_selected.connect(self._on_color_picked)

        self.clicked.connect(self._on_main_button_clicked)

    @property
    def current_color(self) -> str:
        return self._current_color

    def sizeHint(self) -> QSize:
        return QSize(34, 22)

    def set_color(self, color_hex: str) -> None:
        """Update current color indicator bar."""
        self._current_color = color_hex.upper() if color_hex.startswith("#") else color_hex
        self.update()

    def _on_color_picked(self, color: str) -> None:
        self.set_color(color)
        self.color_applied.emit(color)

    def _on_main_button_clicked(self) -> None:
        self.color_applied.emit(self._current_color)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Check if dropdown arrow area was clicked
        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)
        arrow_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ToolButton,
            opt,
            QStyle.SubControl.SC_ToolButtonMenu,
            self,
        )
        if not arrow_rect.isValid() or arrow_rect.width() <= 0:
            arrow_rect = QRect(self.width() - 12, 0, 12, self.height())

        pt = event.position().toPoint() if hasattr(event, "position") else event.pos()
        if event.button() == Qt.MouseButton.LeftButton and arrow_rect.contains(pt):
            self._show_popup()
            event.accept()
            return

        super().mousePressEvent(event)

    def _show_popup(self) -> None:
        pos = self.mapToGlobal(QPoint(0, self.height()))
        self.popup.move(pos)
        self.popup.show()

    def retranslate_ui(self, tr_func: Callable[[str], str] | None = None) -> None:
        """Update localized tooltips and delegate to popup."""
        translate = tr_func or safe_tr
        if self._raw_tip:
            tip_formatted = translate(self._raw_tip)
            self.setToolTip(tip_formatted)
            self.setStatusTip(tip_formatted)
            self.setAccessibleName(tip_formatted)
        self.popup.retranslate_ui(translate)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)

        arrow_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ToolButton,
            opt,
            QStyle.SubControl.SC_ToolButtonMenu,
            self,
        )
        if not arrow_rect.isValid() or arrow_rect.width() <= 0:
            arrow_rect = QRect(self.width() - 12, 0, 12, self.height())

        btn_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ToolButton,
            opt,
            QStyle.SubControl.SC_ToolButton,
            self,
        )
        if not btn_rect.isValid() or btn_rect.width() <= 0:
            btn_rect = QRect(0, 0, self.width() - 12, self.height())

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        is_hovered = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        is_enabled = bool(opt.state & QStyle.StateFlag.State_Enabled)

        # 1. Draw 1px vertical divider between main button and arrow area
        divider_x = arrow_rect.left()
        top_y = opt.rect.top() + 2
        bottom_y = opt.rect.bottom() - 2

        if is_hovered and is_enabled:
            painter.setPen(QColor(LUNA_BLUE_HOT_BORDER))
            painter.drawLine(divider_x, top_y, divider_x, bottom_y)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawLine(divider_x + 1, top_y, divider_x + 1, bottom_y)
        else:
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

        points = [
            QPoint(cx - 2, cy - 1),
            QPoint(cx + 2, cy - 1),
            QPoint(cx, cy + 1),
        ]
        painter.drawPolygon(QPolygon(points))

        # 3. Draw Office 2003 colored indicator bar at the bottom of main button
        bar_height = 3
        margin_x = 3
        bar_rect = QRect(
            btn_rect.left() + margin_x,
            self.height() - bar_height - 2,
            max(btn_rect.width() - (margin_x * 2), 10),
            bar_height,
        )

        if self._current_color.startswith("#"):
            painter.fillRect(bar_rect, QColor(self._current_color))
        elif self._current_color == "none":
            painter.fillRect(bar_rect, QColor("#FFFFFF"))
            painter.setPen(QColor("#FF0000"))
            painter.drawLine(bar_rect.topLeft(), bar_rect.bottomRight())
        else:
            painter.fillRect(bar_rect, QColor("#000000"))

        painter.end()
