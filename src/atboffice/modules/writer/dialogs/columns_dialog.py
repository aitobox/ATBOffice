"""Classic Columns Dialog for Quire Writer."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.models.properties import ColumnsProperties


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("ColumnsDialog", text)


class ColumnsPreviewWidget(QWidget):
    """Visual preview of columns layout with optional separator lines."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(110, 130)
        self.num_cols: int = 1
        self.widths: list[float] = []
        self.has_sep: bool = False

    def update_layout(self, num_cols: int, widths: list[float], has_sep: bool) -> None:
        self.num_cols = max(1, num_cols)
        self.widths = widths
        self.has_sep = has_sep
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Page container
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#A0A0A0"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        content_rect = self.rect().adjusted(10, 10, -10, -10)
        tot_w = content_rect.width()

        # Compute column ratios
        if self.widths and len(self.widths) == self.num_cols:
            sum_w = sum(self.widths) or 1.0
            ratios = [w / sum_w for w in self.widths]
        else:
            ratios = [1.0 / self.num_cols] * self.num_cols

        cur_x = content_rect.left()
        spacing_px = 6 if self.num_cols > 1 else 0
        avail_w = tot_w - spacing_px * (self.num_cols - 1)

        for i, ratio in enumerate(ratios):
            cw = int(avail_w * ratio)
            c_rect = QRect(cur_x, content_rect.top(), cw, content_rect.height())

            # Simulate text lines in column
            painter.setPen(QPen(QColor("#C0C0C0"), 2))
            for y in range(c_rect.top() + 6, c_rect.bottom() - 6, 8):
                painter.drawLine(c_rect.left() + 2, y, c_rect.right() - 2, y)

            # Draw separator line between columns
            if self.has_sep and i < self.num_cols - 1:
                sep_x = cur_x + cw + spacing_px // 2
                painter.setPen(QPen(QColor("#000000"), 1))
                painter.drawLine(sep_x, content_rect.top() + 2, sep_x, content_rect.bottom() - 2)

            cur_x += cw + spacing_px


class ColumnsDialog(QDialog):
    """Word 2003 classic Columns modal dialog."""

    def __init__(
        self,
        parent: QWidget | None = None,
        cols: ColumnsProperties | None = None,
        page_width: float = 612.0,
        margins: tuple[float, float] = (90.0, 90.0),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("分栏"))
        self.setModal(True)
        self.setMinimumWidth(440)

        self._page_w = page_width
        self._ml, self._mr = margins
        self._body_w = max(100.0, self._page_w - self._ml - self._mr)

        init_cols = cols or ColumnsProperties()
        self._num = max(1, min(13, init_cols.num))
        self._equal = init_cols.equal_width
        self._sep = init_cols.sep
        self._space = init_cols.space or 36.0
        self._widths = list(init_cols.widths) if init_cols.widths else []

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # 1. Presets Group
        self.group_presets = QGroupBox(self)
        row_presets = QHBoxLayout(self.group_presets)
        row_presets.setSpacing(8)

        self.btn_preset_one = QPushButton(safe_tr("一栏"), self.group_presets)
        self.btn_preset_two = QPushButton(safe_tr("两栏"), self.group_presets)
        self.btn_preset_three = QPushButton(safe_tr("三栏"), self.group_presets)
        self.btn_preset_left = QPushButton(safe_tr("偏左"), self.group_presets)
        self.btn_preset_right = QPushButton(safe_tr("偏右"), self.group_presets)

        self.btn_preset_one.clicked.connect(lambda: self._apply_preset(1, True))
        self.btn_preset_two.clicked.connect(lambda: self._apply_preset(2, True))
        self.btn_preset_three.clicked.connect(lambda: self._apply_preset(3, True))
        self.btn_preset_left.clicked.connect(lambda: self._apply_preset(2, False, [0.35, 0.65]))
        self.btn_preset_right.clicked.connect(lambda: self._apply_preset(2, False, [0.65, 0.35]))

        for b in [
            self.btn_preset_one,
            self.btn_preset_two,
            self.btn_preset_three,
            self.btn_preset_left,
            self.btn_preset_right,
        ]:
            row_presets.addWidget(b)
        main_layout.addWidget(self.group_presets)

        # 2. Number of columns & Line between
        row_num = QHBoxLayout()
        self.label_num = QLabel(self)
        self.spin_num = QSpinBox(self)
        self.spin_num.setRange(1, 13)
        self.spin_num.setValue(self._num)
        self.spin_num.valueChanged.connect(self._on_num_changed)

        self.check_sep = QCheckBox(self)
        self.check_sep.setChecked(self._sep)
        self.check_sep.toggled.connect(self._on_sep_toggled)

        row_num.addWidget(self.label_num)
        row_num.addWidget(self.spin_num)
        row_num.addSpacing(20)
        row_num.addWidget(self.check_sep)
        row_num.addStretch(1)
        main_layout.addLayout(row_num)

        # 3. Width and Spacing Group
        self.group_width_spacing = QGroupBox(self)
        self.grid_ws = QGridLayout(self.group_width_spacing)
        self.grid_ws.setSpacing(6)

        self.label_header_col = QLabel(safe_tr("栏:"), self.group_width_spacing)
        self.label_header_width = QLabel(safe_tr("宽度:"), self.group_width_spacing)
        self.label_header_spacing = QLabel(safe_tr("间距:"), self.group_width_spacing)

        self.grid_ws.addWidget(self.label_header_col, 0, 0)
        self.grid_ws.addWidget(self.label_header_width, 0, 1)
        self.grid_ws.addWidget(self.label_header_spacing, 0, 2)

        self.spin_widths: list[QDoubleSpinBox] = []
        self.spin_spacings: list[QDoubleSpinBox] = []

        for i in range(4):
            lbl = QLabel(f"{i + 1}:", self.group_width_spacing)
            w_box = QDoubleSpinBox(self.group_width_spacing)
            w_box.setRange(36.0, 1000.0)
            w_box.setSuffix(" pt")
            w_box.valueChanged.connect(self._on_width_edited)

            s_box = QDoubleSpinBox(self.group_width_spacing)
            s_box.setRange(0.0, 500.0)
            s_box.setSuffix(" pt")
            s_box.setValue(self._space)
            s_box.valueChanged.connect(self._on_spacing_edited)

            self.grid_ws.addWidget(lbl, i + 1, 0)
            self.grid_ws.addWidget(w_box, i + 1, 1)
            self.grid_ws.addWidget(s_box, i + 1, 2)
            self.spin_widths.append(w_box)
            self.spin_spacings.append(s_box)

        self.check_equal_width = QCheckBox(self.group_width_spacing)
        self.check_equal_width.setChecked(self._equal)
        self.check_equal_width.toggled.connect(self._on_equal_width_toggled)
        self.grid_ws.addWidget(self.check_equal_width, 5, 0, 1, 3)

        main_layout.addWidget(self.group_width_spacing)

        # 4. Apply To & Preview
        row_apply_pv = QHBoxLayout()
        col_apply = QVBoxLayout()
        self.label_apply = QLabel(self)
        self.combo_apply = QComboBox(self)
        self.combo_apply.addItem(safe_tr("本节"), "section")
        self.combo_apply.addItem(safe_tr("整篇文档"), "all")
        self.combo_apply.addItem(safe_tr("插入点之后"), "forward")

        self.check_new_col = QCheckBox(self)

        col_apply.addWidget(self.label_apply)
        col_apply.addWidget(self.combo_apply)
        col_apply.addWidget(self.check_new_col)
        col_apply.addStretch(1)
        row_apply_pv.addLayout(col_apply)

        col_pv = QVBoxLayout()
        self.label_pv = QLabel(safe_tr("预览"), self)
        self.pv_columns = ColumnsPreviewWidget(self)
        col_pv.addWidget(self.label_pv)
        col_pv.addWidget(self.pv_columns)
        row_apply_pv.addLayout(col_pv)

        main_layout.addLayout(row_apply_pv)

        # 5. Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self._rebuild_width_table()
        self.retranslate_ui()

    def _apply_preset(self, num: int, equal: bool, ratios: list[float] | None = None) -> None:
        self._num = num
        self._equal = equal
        self.spin_num.setValue(num)
        self.check_equal_width.setChecked(equal)
        if ratios:
            avail = max(36.0, self._body_w - self._space * (num - 1))
            self._widths = [round(avail * r, 2) for r in ratios]
        else:
            self._widths = []
        self._rebuild_width_table()

    def _on_num_changed(self, val: int) -> None:
        self._num = val
        self._rebuild_width_table()

    def _on_sep_toggled(self, checked: bool) -> None:
        self._sep = checked
        self._update_preview()

    def _on_equal_width_toggled(self, checked: bool) -> None:
        self._equal = checked
        self._rebuild_width_table()

    def _on_width_edited(self) -> None:
        self._update_preview()

    def _on_spacing_edited(self) -> None:
        self._space = self.spin_spacings[0].value()
        self._update_preview()

    def _rebuild_width_table(self) -> None:
        nn = self._num
        space = self.spin_spacings[0].value() if self.spin_spacings else self._space
        eq_w = max(36.0, (self._body_w - space * (nn - 1)) / nn)

        for i in range(4):
            w_box = self.spin_widths[i]
            s_box = self.spin_spacings[i]

            if i < nn:
                w_box.setEnabled(not self._equal or i == 0)
                s_box.setEnabled(i < nn - 1 and (not self._equal or i == 0))

                if self._equal:
                    w_box.setValue(eq_w)
                    s_box.setValue(space)
                else:
                    if i < len(self._widths):
                        w_box.setValue(self._widths[i])
                    else:
                        w_box.setValue(eq_w)
            else:
                w_box.setEnabled(False)
                s_box.setEnabled(False)

        self._update_preview()

    def _update_preview(self) -> None:
        nn = self._num
        if self._equal:
            w = [self.spin_widths[0].value()] * nn
        else:
            w = [
                self.spin_widths[i].value() if i < 4 else self.spin_widths[0].value()
                for i in range(nn)
            ]
        self.pv_columns.update_layout(nn, w, self._sep)

    def retranslate_ui(self) -> None:
        """Update all translatable strings dynamically."""
        self.setWindowTitle(safe_tr("分栏"))
        self.group_presets.setTitle(safe_tr("预设"))
        self.btn_preset_one.setText(safe_tr("一栏"))
        self.btn_preset_two.setText(safe_tr("两栏"))
        self.btn_preset_three.setText(safe_tr("三栏"))
        self.btn_preset_left.setText(safe_tr("偏左"))
        self.btn_preset_right.setText(safe_tr("偏右"))

        self.label_num.setText(safe_tr("栏数(&N):"))
        self.check_sep.setText(safe_tr("分隔线(&B)"))

        self.group_width_spacing.setTitle(safe_tr("宽度和间距"))
        self.label_header_col.setText(safe_tr("栏:"))
        self.label_header_width.setText(safe_tr("宽度:"))
        self.label_header_spacing.setText(safe_tr("间距:"))
        self.check_equal_width.setText(safe_tr("栏宽相等(&E)"))

        self.label_apply.setText(safe_tr("应用于(&A):"))
        self.check_new_col.setText(safe_tr("开始新栏(&C)"))

        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(safe_tr("确定"))
        cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(safe_tr("取消"))

    def get_columns(self) -> ColumnsProperties:
        """Return configured ColumnsProperties."""
        nn = self.spin_num.value()
        space = self.spin_spacings[0].value()
        equal = self.check_equal_width.isChecked()
        widths = [self.spin_widths[i].value() for i in range(min(nn, 4))] if not equal else []
        return ColumnsProperties(
            num=nn,
            space=space,
            sep=self.check_sep.isChecked(),
            equal_width=equal,
            widths=widths,
        )

    def get_apply_to(self) -> str:
        """Return target section apply mode: 'section', 'all', or 'forward'."""
        return str(self.combo_apply.currentData())
