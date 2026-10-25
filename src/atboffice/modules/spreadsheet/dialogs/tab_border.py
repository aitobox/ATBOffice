"""Border tab for FormatCellsDialog."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QColorDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.models.sheet_model import BorderStyle


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("BorderTab", text)


LINE_STYLES = [
    ("none", "无"),
    ("thin", "细线"),
    ("medium", "中粗线"),
    ("thick", "粗线"),
    ("double", "双线"),
    ("hairline", "发丝线"),
    ("dashed", "虚线"),
    ("dotted", "点线"),
    ("dashDot", "点划线"),
    ("dashDotDot", "双点划线"),
    ("mediumDashDot", "中粗点划线"),
    ("slantDashDot", "斜点划线"),
    ("mediumDashDotDot", "中粗双点划线"),
    ("mediumDashed", "中粗虚线"),
]


class BorderPreviewCanvas(QWidget):
    """Interactive visual border diagram allowing click-to-toggle."""

    def __init__(
        self,
        borders: dict[str, BorderStyle | None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(160, 120)
        self.borders = borders
        self.border_clicked_callback: Any = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.pos()
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        x0, y0 = 20, 15
        x1, y1 = w - 20, h - 15
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2

        dists = {
            "top": abs(y - y0),
            "bottom": abs(y - y1),
            "left": abs(x - x0),
            "right": abs(x - x1),
            "inside_h": abs(y - my),
            "inside_v": abs(x - mx),
        }
        best_k = min(dists, key=dists.get)
        if dists[best_k] < 14:
            if self.border_clicked_callback:
                self.border_clicked_callback(best_k)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        w, h = self.width(), self.height()
        x0, y0 = 20, 15
        x1, y1 = w - 20, h - 15
        mx, my = int((x0 + x1) / 2), int((y0 + y1) / 2)

        # White background
        painter.fillRect(x0, y0, x1 - x0, y1 - y0, Qt.GlobalColor.white)

        # Corner guide ticks
        pen_tick = QPen(QColor("#B0B0B0"), 1)
        painter.setPen(pen_tick)
        painter.drawLine(x0, y0 - 6, x0, y0)
        painter.drawLine(x0 - 6, y0, x0, y0)
        painter.drawLine(x1, y0 - 6, x1, y0)
        painter.drawLine(x1, y0, x1 + 6, y0)
        painter.drawLine(x0, y1, x0, y1 + 6)
        painter.drawLine(x0 - 6, y1, x0, y1)
        painter.drawLine(x1, y1, x1, y1 + 6)
        painter.drawLine(x1, y1, x1 + 6, y1)

        # Text in 4 quadrants
        painter.setPen(QColor("#999999"))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(
            QRect(x0, y0, mx - x0, my - y0),
            Qt.AlignmentFlag.AlignCenter,
            safe_tr("文本"),
        )
        painter.drawText(
            QRect(mx, y0, x1 - mx, my - y0),
            Qt.AlignmentFlag.AlignCenter,
            safe_tr("文本"),
        )
        painter.drawText(
            QRect(x0, my, mx - x0, y1 - my),
            Qt.AlignmentFlag.AlignCenter,
            safe_tr("文本"),
        )
        painter.drawText(
            QRect(mx, my, x1 - mx, y1 - my),
            Qt.AlignmentFlag.AlignCenter,
            safe_tr("文本"),
        )

        def draw_border_line(
            bs: BorderStyle | None, xa: int, ya: int, xb: int, yb: int
        ) -> None:
            if not bs or bs.style == "none":
                return
            col = QColor(bs.color) if bs.color else QColor("#000000")
            st = bs.style

            if st == "double":
                painter.setPen(QPen(col, 1))
                if ya == yb:  # horizontal double
                    painter.drawLine(xa, ya - 1, xb, ya - 1)
                    painter.drawLine(xa, ya + 1, xb, ya + 1)
                else:  # vertical double
                    painter.drawLine(xa - 1, ya, xa - 1, yb)
                    painter.drawLine(xa + 1, ya, xa + 1, yb)
                return

            pen = QPen(col)
            if st in ("thick", "medium"):
                pen.setWidth(2 if st == "medium" else 3)
            else:
                pen.setWidth(1)

            if "dash" in st.lower():
                pen.setStyle(Qt.PenStyle.DashLine)
            elif "dot" in st.lower():
                pen.setStyle(Qt.PenStyle.DotLine)
            else:
                pen.setStyle(Qt.PenStyle.SolidLine)

            painter.setPen(pen)
            painter.drawLine(xa, ya, xb, yb)

        # Draw borders
        draw_border_line(self.borders.get("top"), x0, y0, x1, y0)
        draw_border_line(self.borders.get("bottom"), x0, y1, x1, y1)
        draw_border_line(self.borders.get("left"), x0, y0, x0, y1)
        draw_border_line(self.borders.get("right"), x1, y0, x1, y1)
        draw_border_line(self.borders.get("inside_h"), x0, my, x1, my)
        draw_border_line(self.borders.get("inside_v"), mx, y0, mx, y1)
        draw_border_line(self.borders.get("diag_up"), x0, y1, x1, y0)
        draw_border_line(self.borders.get("diag_down"), x0, y0, x1, y1)
        painter.end()


class BorderTab(QWidget):
    """Tab 4: Cell border configuration and interactive diagram."""

    def __init__(
        self,
        borders: dict[str, BorderStyle | None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._borders = borders.copy() if borders else {}
        for key in [
            "top",
            "bottom",
            "left",
            "right",
            "inside_h",
            "inside_v",
            "diag_up",
            "diag_down",
        ]:
            if key not in self._borders:
                self._borders[key] = None

        self._active_style = "thin"
        self._active_color = "#000000"

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        # Left Column: Presets + Border Buttons & Diagram
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)

        # 1. Presets
        self.grp_presets = QGroupBox(safe_tr("预设"))
        preset_layout = QHBoxLayout(self.grp_presets)
        self.btn_preset_none = QPushButton(safe_tr("无(&N)"))
        self.btn_preset_outline = QPushButton(safe_tr("外边框(&O)"))
        self.btn_preset_inside = QPushButton(safe_tr("内部(&I)"))

        self.btn_preset_none.clicked.connect(self._preset_none)
        self.btn_preset_outline.clicked.connect(self._preset_outline)
        self.btn_preset_inside.clicked.connect(self._preset_inside)

        preset_layout.addWidget(self.btn_preset_none)
        preset_layout.addWidget(self.btn_preset_outline)
        preset_layout.addWidget(self.btn_preset_inside)
        left_layout.addWidget(self.grp_presets)

        # 2. Border controls
        self.grp_border = QGroupBox(safe_tr("边框"))
        b_outer = QVBoxLayout(self.grp_border)

        diag_row = QHBoxLayout()
        # Left buttons (Top, InsideH, Bottom)
        left_btns = QVBoxLayout()
        self.btn_top = QPushButton(safe_tr("上"))
        self.btn_inside_h = QPushButton(safe_tr("中横"))
        self.btn_bottom = QPushButton(safe_tr("下"))

        self.btn_top.clicked.connect(lambda: self.toggle_border("top"))
        self.btn_inside_h.clicked.connect(
            lambda: self.toggle_border("inside_h")
        )
        self.btn_bottom.clicked.connect(lambda: self.toggle_border("bottom"))

        left_btns.addWidget(self.btn_top)
        left_btns.addWidget(self.btn_inside_h)
        left_btns.addWidget(self.btn_bottom)
        diag_row.addLayout(left_btns)

        # Center canvas
        self.canvas = BorderPreviewCanvas(self._borders)
        self.canvas.border_clicked_callback = self.toggle_border
        diag_row.addWidget(self.canvas)
        b_outer.addLayout(diag_row)

        # Bottom buttons (DiagUp, Left, InsideV, Right, DiagDown)
        bot_btns = QHBoxLayout()
        self.btn_diag_up = QPushButton(safe_tr("斜上"))
        self.btn_left = QPushButton(safe_tr("左"))
        self.btn_inside_v = QPushButton(safe_tr("中竖"))
        self.btn_right = QPushButton(safe_tr("右"))
        self.btn_diag_down = QPushButton(safe_tr("斜下"))

        self.btn_diag_up.clicked.connect(lambda: self.toggle_border("diag_up"))
        self.btn_left.clicked.connect(lambda: self.toggle_border("left"))
        self.btn_inside_v.clicked.connect(
            lambda: self.toggle_border("inside_v")
        )
        self.btn_right.clicked.connect(lambda: self.toggle_border("right"))
        self.btn_diag_down.clicked.connect(
            lambda: self.toggle_border("diag_down")
        )

        bot_btns.addWidget(self.btn_diag_up)
        bot_btns.addWidget(self.btn_left)
        bot_btns.addWidget(self.btn_inside_v)
        bot_btns.addWidget(self.btn_right)
        bot_btns.addWidget(self.btn_diag_down)
        b_outer.addLayout(bot_btns)

        left_layout.addWidget(self.grp_border)
        main_layout.addLayout(left_layout, 2)

        # Right Column: Line Style and Color
        self.grp_line = QGroupBox(safe_tr("线条"))
        line_layout = QVBoxLayout(self.grp_line)
        line_layout.setSpacing(8)

        self.lbl_style = QLabel(safe_tr("样式(&S):"))
        self.list_style = QListWidget()
        for key, name in LINE_STYLES:
            item = QListWidgetItem(safe_tr(name))
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.list_style.addItem(item)
        self.list_style.setCurrentRow(1)  # thin
        self.list_style.currentRowChanged.connect(self._on_style_row_changed)

        line_layout.addWidget(self.lbl_style)
        line_layout.addWidget(self.list_style)

        c_form = QFormLayout()
        self.lbl_color = QLabel(safe_tr("颜色(&C):"))
        self.btn_color = QPushButton(safe_tr("自动"))
        self.btn_color.clicked.connect(self._choose_color)
        c_form.addRow(self.lbl_color, self.btn_color)
        line_layout.addLayout(c_form)

        main_layout.addWidget(self.grp_line, 1)

    def _choose_color(self) -> None:
        col = QColorDialog.getColor(QColor(self._active_color), self)
        if col.isValid():
            self.set_line_color(col.name())

    def set_line_style(self, style_name: str) -> None:
        self._active_style = style_name
        for i in range(self.list_style.count()):
            if self.list_style.item(i).data(Qt.ItemDataRole.UserRole) == style_name:
                self.list_style.setCurrentRow(i)
                break

    def set_line_color(self, color_hex: str) -> None:
        self._active_color = color_hex
        if color_hex and color_hex.lower() != "#000000":
            self.btn_color.setText("")
            self.btn_color.setStyleSheet(
                f"background-color: {color_hex}; border: 1px solid #888;"
            )
        else:
            self.btn_color.setText(safe_tr("自动"))
            self.btn_color.setStyleSheet("")

    def _on_style_row_changed(self, row: int) -> None:
        item = self.list_style.item(row)
        if item is not None:
            self._active_style = item.data(Qt.ItemDataRole.UserRole)

    def _current_border_style(self) -> BorderStyle | None:
        if self._active_style == "none":
            return None
        return BorderStyle(style=self._active_style, color=self._active_color)

    def _preset_none(self) -> None:
        for k in self._borders:
            self._borders[k] = None
        self.canvas.update()

    def _preset_outline(self) -> None:
        bs = self._current_border_style()
        for k in ["top", "bottom", "left", "right"]:
            self._borders[k] = bs
        self.canvas.update()

    def _preset_inside(self) -> None:
        bs = self._current_border_style()
        self._borders["inside_h"] = bs
        self._borders["inside_v"] = bs
        self.canvas.update()

    def toggle_border(self, key: str) -> None:
        cur = self._borders.get(key)
        target = self._current_border_style()
        if (
            cur is not None
            and target is not None
            and cur.style == target.style
            and cur.color == target.color
        ):
            self._borders[key] = None
        else:
            self._borders[key] = target
        self.canvas.update()

    def get_borders(self) -> dict[str, BorderStyle | None]:
        return self._borders.copy()

    def retranslate_ui(self) -> None:
        self.grp_presets.setTitle(safe_tr("预设"))
        self.btn_preset_none.setText(safe_tr("无(&N)"))
        self.btn_preset_outline.setText(safe_tr("外边框(&O)"))
        self.btn_preset_inside.setText(safe_tr("内部(&I)"))
        self.grp_border.setTitle(safe_tr("边框"))
        self.btn_top.setText(safe_tr("上"))
        self.btn_inside_h.setText(safe_tr("中横"))
        self.btn_bottom.setText(safe_tr("下"))
        self.btn_diag_up.setText(safe_tr("斜上"))
        self.btn_left.setText(safe_tr("左"))
        self.btn_inside_v.setText(safe_tr("中竖"))
        self.btn_right.setText(safe_tr("右"))
        self.btn_diag_down.setText(safe_tr("斜下"))
        self.grp_line.setTitle(safe_tr("线条"))
        self.lbl_style.setText(safe_tr("样式(&S):"))
        self.lbl_color.setText(safe_tr("颜色(&C):"))
        self.canvas.update()
