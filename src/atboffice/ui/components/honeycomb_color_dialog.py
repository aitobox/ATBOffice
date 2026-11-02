"""Office 2003 classic Honeycomb color dialog with Standard (127 hexagons) and Custom tabs."""

from __future__ import annotations

import math

from PySide6.QtCore import QCoreApplication, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for HoneycombColorDialog."""
    return QCoreApplication.translate("HoneycombColorDialog", text)


class HoneycombCell:
    """Represents a single hexagonal cell in the standard palette."""

    def __init__(self, row: int, col: int, color: QColor, center: QPointF, radius: float) -> None:
        self.row = row
        self.col = col
        self.color = color
        self.center = center
        self.radius = radius

        # Precompute polygon vertices
        self.polygon = QPolygonF()
        for k in range(6):
            angle_rad = math.radians(30 + 60 * k)
            px = center.x() + radius * math.cos(angle_rad)
            py = center.y() + radius * math.sin(angle_rad)
            self.polygon.append(QPointF(px, py))

    def contains(self, point: QPointF) -> bool:
        return self.polygon.containsPoint(point, Qt.FillRule.OddEvenFill)


class HoneycombWidget(QWidget):
    """Custom canvas rendering the 127-cell hexagonal color honeycomb."""

    color_selected = Signal(QColor)
    color_activated = Signal(QColor)

    def __init__(self, initial_color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self._current_color = QColor(initial_color)
        self._hovered_cell: HoneycombCell | None = None
        self._selected_cell: HoneycombCell | None = None
        self._cells: list[HoneycombCell] = []
        self._cell_radius = 10.0
        self.setFixedSize(290, 260)
        self._generate_honeycomb_cells()

    def _generate_honeycomb_cells(self) -> None:
        """Generate 127 hexagonal cells arranged in 13 rows."""
        self._cells.clear()
        cx = self.width() / 2.0
        cy = self.height() / 2.0 - 5.0
        r_step = self._cell_radius * math.sqrt(3)  # horizontal step between cell centers
        v_step = self._cell_radius * 1.5           # vertical step between row centers

        rows = 13
        for row in range(rows):
            n = 7 + row if row < 7 else 19 - row
            row_y = cy + (row - 6) * v_step
            for col in range(n):
                col_x = cx + (col - (n - 1) / 2.0) * r_step
                center = QPointF(col_x, row_y)

                # Determine color for this cell
                if row == 6 and col == 6:
                    # Absolute center is pure white
                    c = QColor(255, 255, 255)
                else:
                    dx = col - (n - 1) / 2.0
                    dy = (row - 6.0) * (2.0 / math.sqrt(3))
                    dist = math.hypot(dx, dy)
                    norm_dist = min(dist / 6.0, 1.0)
                    ang = (math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0

                    # Map angle to Hue (0..359)
                    hue = int(ang) % 360
                    # Saturation increases towards outer circle
                    sat = int(max(40, min(255, 255 * (0.35 + 0.65 * norm_dist))))
                    # Lightness is brightest near center, medium at mid, darker at outermost
                    if norm_dist < 0.25:
                        light = int(240 - 20 * norm_dist)
                    elif row < 6:
                        light = int(220 - 90 * norm_dist)
                    else:
                        light = int(210 - 130 * norm_dist)
                    light = max(30, min(250, light))

                    c = QColor.fromHsl(hue, sat, light)

                cell = HoneycombCell(row, col, c, center, self._cell_radius)
                self._cells.append(cell)

                if c.name().upper() == self._current_color.name().upper():
                    self._selected_cell = cell

    def set_color(self, color: QColor) -> None:
        self._current_color = QColor(color)
        self._selected_cell = None
        hex_code = self._current_color.name().upper()
        for cell in self._cells:
            if cell.color.name().upper() == hex_code:
                self._selected_cell = cell
                break
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        hovered: HoneycombCell | None = None
        for cell in self._cells:
            if cell.contains(pos):
                hovered = cell
                break
        if hovered != self._hovered_cell:
            self._hovered_cell = hovered
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if self._hovered_cell is not None:
            self._hovered_cell = None
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            for cell in self._cells:
                if cell.contains(pos):
                    self._selected_cell = cell
                    self._current_color = cell.color
                    self.color_selected.emit(cell.color)
                    self.update()
                    break
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            for cell in self._cells:
                if cell.contains(pos):
                    self._selected_cell = cell
                    self._current_color = cell.color
                    self.color_activated.emit(cell.color)
                    break
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Draw all cells
        for cell in self._cells:
            painter.setBrush(cell.color)
            if cell == self._selected_cell:
                painter.setPen(QPen(QColor("#000000"), 2))
            elif cell == self._hovered_cell:
                painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
            else:
                painter.setPen(QPen(QColor(0, 0, 0, 40), 0.5))
            painter.drawPolygon(cell.polygon)

        # Draw extra focus ring around selected cell
        if self._selected_cell is not None:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#FFFFFF"), 1.2))
            painter.drawPolygon(self._selected_cell.polygon)

        painter.end()


class GrayscaleStrip(QWidget):
    """Horizontal 16-shade grayscale color swatch strip."""

    color_selected = Signal(QColor)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(272, 22)
        self.setMouseTracking(True)
        self._hover_index: int = -1
        self._selected_index: int = -1

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        w = self.width() / 16.0
        h = self.height() - 2.0

        for i in range(16):
            v = int(round((255 * i) / 15.0))
            rect = QRectF(i * w, 1, w, h)
            painter.fillRect(rect, QColor(v, v, v))

            if i == self._selected_index:
                painter.setPen(QPen(QColor("#FFCC00"), 2))
                painter.drawRect(rect.adjusted(1, 1, -1, -1))
            elif i == self._hover_index:
                painter.setPen(QPen(QColor("#0000FF"), 1))
                painter.drawRect(rect)
            else:
                painter.setPen(QPen(QColor("#808080"), 0.5))
                painter.drawRect(rect)

        painter.end()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        idx = int(event.position().x() // (self.width() / 16.0))
        idx = max(0, min(15, idx))
        if idx != self._hover_index:
            self._hover_index = idx
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if self._hover_index != -1:
            self._hover_index = -1
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = int(event.position().x() // (self.width() / 16.0))
            idx = max(0, min(15, idx))
            self._selected_index = idx
            v = int(round((255 * idx) / 15.0))
            self.color_selected.emit(QColor(v, v, v))
            self.update()
        super().mousePressEvent(event)


class ColorPreviewBox(QWidget):
    """Side widget showing 'New' vs 'Current' color comparison."""

    def __init__(self, current_color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_color = QColor(current_color)
        self._new_color = QColor(current_color)
        self.setFixedSize(64, 110)

    def set_new_color(self, color: QColor) -> None:
        self._new_color = QColor(color)
        self.update()

    def set_current_color(self, color: QColor) -> None:
        self._current_color = QColor(color)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        rect = self.rect()

        # Top half: New Color
        new_rect = QRectF(0, 0, rect.width(), rect.height() / 2.0)
        painter.fillRect(new_rect, self._new_color)

        # Bottom half: Current Color
        cur_rect = QRectF(0, rect.height() / 2.0, rect.width(), rect.height() / 2.0)
        painter.fillRect(cur_rect, self._current_color)

        # Outer border
        painter.setPen(QColor("#002D96"))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

        # Center split line
        painter.drawLine(0, int(rect.height() / 2.0), rect.width(), int(rect.height() / 2.0))
        painter.end()


class HoneycombColorDialog(QDialog):
    """Standard Office 2003 Colors dialog with Honeycomb Standard palette and Custom tabs."""

    def __init__(
        self,
        initial_color: QColor | str = "#3366FF",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if isinstance(initial_color, str):
            self._current_color = QColor(initial_color)
            if not self._current_color.isValid():
                self._current_color = QColor("#3366FF")
        else:
            self._current_color = QColor(initial_color)

        self._selected_color = QColor(self._current_color)
        self._is_updating = False

        self.setWindowTitle(safe_tr("颜色"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setFixedSize(450, 390)

        self._init_ui()
        self._sync_inputs_from_color(self._selected_color)

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Left: Tabs container
        self.tabs = QTabWidget(self)

        # Tab 1: Standard
        tab_standard = QWidget()
        v_std = QVBoxLayout(tab_standard)
        v_std.setContentsMargins(8, 8, 8, 8)
        v_std.setSpacing(6)

        lbl_colors = QLabel(safe_tr("颜色(&C):"), tab_standard)
        v_std.addWidget(lbl_colors)

        self.honeycomb = HoneycombWidget(self._current_color, tab_standard)
        self.honeycomb.color_selected.connect(self._on_color_picked)
        self.honeycomb.color_activated.connect(self._on_color_activated)
        v_std.addWidget(self.honeycomb, alignment=Qt.AlignmentFlag.AlignCenter)

        self.grays = GrayscaleStrip(tab_standard)
        self.grays.color_selected.connect(self._on_color_picked)
        v_std.addWidget(self.grays, alignment=Qt.AlignmentFlag.AlignCenter)

        self.tabs.addTab(tab_standard, safe_tr("标准(&S)"))

        # Tab 2: Custom
        tab_custom = QWidget()
        v_cust = QVBoxLayout(tab_custom)
        v_cust.setContentsMargins(12, 12, 12, 12)
        v_cust.setSpacing(10)

        # RGB SpinBoxes
        rgb_group = QFrame(tab_custom)
        rgb_layout = QVBoxLayout(rgb_group)
        rgb_layout.setContentsMargins(0, 0, 0, 0)
        rgb_layout.setSpacing(8)

        # Red
        h_r = QHBoxLayout()
        lbl_r = QLabel(safe_tr("红色(&R):"), rgb_group)
        self.spin_r = QSpinBox(rgb_group)
        self.spin_r.setRange(0, 255)
        self.spin_r.valueChanged.connect(self._on_rgb_changed)
        h_r.addWidget(lbl_r)
        h_r.addWidget(self.spin_r)
        rgb_layout.addLayout(h_r)

        # Green
        h_g = QHBoxLayout()
        lbl_g = QLabel(safe_tr("绿色(&G):"), rgb_group)
        self.spin_g = QSpinBox(rgb_group)
        self.spin_g.setRange(0, 255)
        self.spin_g.valueChanged.connect(self._on_rgb_changed)
        h_g.addWidget(lbl_g)
        h_g.addWidget(self.spin_g)
        rgb_layout.addLayout(h_g)

        # Blue
        h_b = QHBoxLayout()
        lbl_b = QLabel(safe_tr("蓝色(&B):"), rgb_group)
        self.spin_b = QSpinBox(rgb_group)
        self.spin_b.setRange(0, 255)
        self.spin_b.valueChanged.connect(self._on_rgb_changed)
        h_b.addWidget(lbl_b)
        h_b.addWidget(self.spin_b)
        rgb_layout.addLayout(h_b)

        # Hex code
        h_hex = QHBoxLayout()
        lbl_hex = QLabel(safe_tr("十六进制(&H):"), rgb_group)
        self.edit_hex = QLineEdit(rgb_group)
        self.edit_hex.setMaxLength(7)
        self.edit_hex.textEdited.connect(self._on_hex_changed)
        h_hex.addWidget(lbl_hex)
        h_hex.addWidget(self.edit_hex)
        rgb_layout.addLayout(h_hex)

        v_cust.addWidget(rgb_group)
        v_cust.addStretch(1)

        self.tabs.addTab(tab_custom, safe_tr("自定义(&U)"))
        main_layout.addWidget(self.tabs, stretch=1)

        # Right: Preview & Buttons column
        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 24, 0, 0)
        right_layout.setSpacing(10)

        lbl_preview = QLabel(safe_tr("预览:"), right_panel)
        right_layout.addWidget(lbl_preview)

        lbl_new = QLabel(safe_tr("新增"), right_panel)
        right_layout.addWidget(lbl_new, alignment=Qt.AlignmentFlag.AlignCenter)

        self.preview_box = ColorPreviewBox(self._current_color, right_panel)
        right_layout.addWidget(self.preview_box, alignment=Qt.AlignmentFlag.AlignCenter)

        lbl_curr = QLabel(safe_tr("当前"), right_panel)
        right_layout.addWidget(lbl_curr, alignment=Qt.AlignmentFlag.AlignCenter)

        right_layout.addSpacing(16)

        # OK / Cancel Buttons
        self.btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Vertical,
            right_panel,
        )
        self.btn_box.button(QDialogButtonBox.StandardButton.Ok).setText(safe_tr("确定"))
        self.btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText(safe_tr("取消"))
        self.btn_box.accepted.connect(self.accept)
        self.btn_box.rejected.connect(self.reject)
        right_layout.addWidget(self.btn_box)

        right_layout.addStretch(1)
        main_layout.addWidget(right_panel)

    def _sync_inputs_from_color(self, color: QColor) -> None:
        self._is_updating = True
        self.spin_r.setValue(color.red())
        self.spin_g.setValue(color.green())
        self.spin_b.setValue(color.blue())
        self.edit_hex.setText(color.name().upper())
        self.preview_box.set_new_color(color)
        self.honeycomb.set_color(color)
        self._is_updating = False

    def _on_color_picked(self, color: QColor) -> None:
        self._selected_color = QColor(color)
        self._sync_inputs_from_color(self._selected_color)

    def _on_color_activated(self, color: QColor) -> None:
        self._selected_color = QColor(color)
        self.accept()

    def _on_rgb_changed(self) -> None:
        if self._is_updating:
            return
        color = QColor(self.spin_r.value(), self.spin_g.value(), self.spin_b.value())
        self._selected_color = color
        self._is_updating = True
        self.edit_hex.setText(color.name().upper())
        self.preview_box.set_new_color(color)
        self.honeycomb.set_color(color)
        self._is_updating = False

    def _on_hex_changed(self, text: str) -> None:
        if self._is_updating:
            return
        clean = text.strip()
        if not clean.startswith("#"):
            clean = "#" + clean
        if len(clean) == 7:
            color = QColor(clean)
            if color.isValid():
                self._selected_color = color
                self._is_updating = True
                self.spin_r.setValue(color.red())
                self.spin_g.setValue(color.green())
                self.spin_b.setValue(color.blue())
                self.preview_box.set_new_color(color)
                self.honeycomb.set_color(color)
                self._is_updating = False

    def selected_color(self) -> QColor:
        """Return the color confirmed by the user."""
        return self._selected_color

    @classmethod
    def getColor(
        cls,
        initial: QColor | str = "#3366FF",
        parent: QWidget | None = None,
        title: str | None = None,
    ) -> QColor | None:
        """Convenience method displaying modal dialog and returning chosen QColor or None."""
        dialog = cls(initial, parent)
        if title:
            dialog.setWindowTitle(title)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_color()
        return None
