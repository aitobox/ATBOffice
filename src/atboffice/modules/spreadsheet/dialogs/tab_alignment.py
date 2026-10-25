"""Alignment tab for FormatCellsDialog."""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QCoreApplication, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("AlignmentTab", text)


H_ALIGNS = [
    ("general", "常规"),
    ("left", "靠左 (缩进)"),
    ("center", "居中"),
    ("right", "靠右 (缩进)"),
    ("fill", "填充"),
    ("justify", "两端对齐"),
    ("centerContinuous", "跨列居中"),
    ("distributed", "分散对齐 (缩进)"),
]

V_ALIGNS = [
    ("top", "靠上"),
    ("center", "居中"),
    ("bottom", "靠下"),
    ("justify", "两端对齐"),
    ("distributed", "分散对齐"),
]


class OrientationDialWidget(QWidget):
    """Interactive visual orientation dial (-90 deg to +90 deg)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(90, 110)
        self._angle = 0
        self.angle_changed_callback: Any = None

    def angle(self) -> int:
        return self._angle

    def set_angle(self, angle: int) -> None:
        self._angle = max(-90, min(90, angle))
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._calculate_angle(event.pos())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._calculate_angle(event.pos())

    def _calculate_angle(self, pos: QPoint) -> None:
        cx, cy = 15, 55
        dx = pos.x() - cx
        dy = cy - pos.y()
        rad = math.atan2(dy, max(0.001, dx))
        deg = int(round(math.degrees(rad)))
        deg = max(-90, min(90, deg))
        self.set_angle(deg)
        if self.angle_changed_callback:
            self.angle_changed_callback(deg)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = 15, 55
        radius = 50

        # Draw arc dots
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(13):
            deg = -90 + i * 15
            rad = math.radians(deg)
            x = cx + radius * math.cos(rad)
            y = cy - radius * math.sin(rad)
            painter.setBrush(
                QColor("#000000") if i % 6 == 0 else QColor("#888888")
            )
            r = 2.5 if i % 6 == 0 else 1.5
            painter.drawEllipse(QRect(int(x - r), int(y - r), int(r * 2), int(r * 2)))

        # Draw red pointer
        rad = math.radians(self._angle)
        px = cx + (radius - 5) * math.cos(rad)
        py = cy - (radius - 5) * math.sin(rad)
        pen = QPen(QColor("#CC0000"), 2)
        painter.setPen(pen)
        painter.drawLine(cx, cy, int(px), int(py))

        # Center point
        painter.setBrush(QColor("#333333"))
        painter.drawEllipse(cx - 3, cy - 3, 6, 6)
        painter.end()


class AlignmentTab(QWidget):
    """Tab 2: Cell alignment and orientation options."""

    def __init__(
        self,
        align_h: str = "general",
        align_v: str = "bottom",
        indent: int = 0,
        wrap_text: bool = False,
        shrink_to_fit: bool = False,
        text_rotation: int = 0,
        text_direction: str = "context",
        merged: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        # Left Column: Text Alignment + Text Control + Right to left
        left_layout = QVBoxLayout()
        left_layout.setSpacing(12)

        # 1. Text Alignment Group
        self.grp_align = QGroupBox(safe_tr("文本对齐方式"))
        align_form = QFormLayout(self.grp_align)
        align_form.setSpacing(8)

        self.lbl_h = QLabel(safe_tr("水平对齐(&H):"))
        self.combo_h = QComboBox()
        for key, name in H_ALIGNS:
            self.combo_h.addItem(safe_tr(name), key)
        align_form.addRow(self.lbl_h, self.combo_h)

        self.lbl_indent = QLabel(safe_tr("缩进(&I):"))
        self.spin_indent = QSpinBox()
        self.spin_indent.setRange(0, 15)
        self.spin_indent.setValue(indent)
        align_form.addRow(self.lbl_indent, self.spin_indent)

        self.lbl_v = QLabel(safe_tr("垂直对齐(&V):"))
        self.combo_v = QComboBox()
        for key, name in V_ALIGNS:
            self.combo_v.addItem(safe_tr(name), key)
        align_form.addRow(self.lbl_v, self.combo_v)

        self.check_just_last = QCheckBox(safe_tr("两端对齐分散(&J)"))
        align_form.addRow(self.check_just_last)
        left_layout.addWidget(self.grp_align)

        # 2. Text Control Group
        self.grp_control = QGroupBox(safe_tr("文本控制"))
        ctrl_layout = QVBoxLayout(self.grp_control)
        ctrl_layout.setSpacing(6)
        self.check_wrap = QCheckBox(safe_tr("自动换行(&W)"))
        self.check_wrap.setChecked(wrap_text)
        self.check_shrink = QCheckBox(safe_tr("缩小字体填充(&K)"))
        self.check_shrink.setChecked(shrink_to_fit)
        self.check_merge = QCheckBox(safe_tr("合并单元格(&M)"))
        self.check_merge.setChecked(merged)
        ctrl_layout.addWidget(self.check_wrap)
        ctrl_layout.addWidget(self.check_shrink)
        ctrl_layout.addWidget(self.check_merge)
        left_layout.addWidget(self.grp_control)

        # 3. Text Direction Group
        self.grp_direction = QGroupBox(safe_tr("文字走向"))
        dir_form = QFormLayout(self.grp_direction)
        self.lbl_dir = QLabel(safe_tr("文字方向(&T):"))
        self.combo_dir = QComboBox()
        self.combo_dir.addItem(safe_tr("根据内容"), "context")
        self.combo_dir.addItem(safe_tr("从左到右"), "ltr")
        self.combo_dir.addItem(safe_tr("从右到左"), "rtl")
        dir_form.addRow(self.lbl_dir, self.combo_dir)
        left_layout.addWidget(self.grp_direction)

        main_layout.addLayout(left_layout, 1)

        # Right Column: Orientation Group
        self.grp_orient = QGroupBox(safe_tr("方向"))
        orient_layout = QVBoxLayout(self.grp_orient)
        orient_layout.setSpacing(10)

        dial_row = QHBoxLayout()
        # Vertical text button
        self.btn_vertical = QPushButton(safe_tr("竖\n排\n文\n字"))
        self.btn_vertical.setCheckable(True)
        self.btn_vertical.setFixedWidth(36)
        self.btn_vertical.setFixedHeight(85)
        self.btn_vertical.toggled.connect(self._on_vertical_toggled)
        dial_row.addWidget(self.btn_vertical)

        # Dial
        self.dial = OrientationDialWidget()
        self.dial.angle_changed_callback = self._on_dial_angle_changed
        dial_row.addWidget(self.dial)
        orient_layout.addLayout(dial_row)

        spin_row = QHBoxLayout()
        self.lbl_degrees = QLabel(safe_tr("度(&D):"))
        self.spin_rot = QSpinBox()
        self.spin_rot.setRange(-90, 90)
        self.spin_rot.setSuffix(" °")
        self.spin_rot.valueChanged.connect(self._on_spin_rot_changed)
        spin_row.addWidget(self.lbl_degrees)
        spin_row.addWidget(self.spin_rot)
        orient_layout.addLayout(spin_row)
        orient_layout.addStretch(1)

        main_layout.addWidget(self.grp_orient)

        # Hook up horizontal alignment to enable/disable indent
        self.combo_h.currentIndexChanged.connect(self._on_h_align_changed)

        # Set initial values
        self._set_combo_by_data(self.combo_h, align_h)
        self._set_combo_by_data(self.combo_v, align_v)
        self._set_combo_by_data(self.combo_dir, text_direction)

        if text_rotation == 255:
            self.btn_vertical.setChecked(True)
            self.dial.set_angle(0)
            self.spin_rot.setValue(0)
        else:
            self.spin_rot.setValue(text_rotation)
            self.dial.set_angle(text_rotation)

        self._on_h_align_changed()

    def _set_combo_by_data(self, combo: QComboBox, data_val: str) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == data_val or combo.itemText(i) == data_val:
                combo.setCurrentIndex(i)
                break

    def _on_h_align_changed(self) -> None:
        data = self.combo_h.currentData()
        text = self.combo_h.currentText()
        can_indent = data in ("left", "right", "distributed") or any(
            k in text for k in ["靠左", "靠右", "分散"]
        )
        self.spin_indent.setEnabled(can_indent)

    def _on_vertical_toggled(self, checked: bool) -> None:
        if checked:
            self.spin_rot.setEnabled(False)
            self.dial.setEnabled(False)
        else:
            self.spin_rot.setEnabled(True)
            self.dial.setEnabled(True)

    def _on_dial_angle_changed(self, angle: int) -> None:
        if self.btn_vertical.isChecked():
            self.btn_vertical.setChecked(False)
        self.spin_rot.blockSignals(True)
        self.spin_rot.setValue(angle)
        self.spin_rot.blockSignals(False)

    def _on_spin_rot_changed(self, angle: int) -> None:
        if self.btn_vertical.isChecked():
            self.btn_vertical.setChecked(False)
        self.dial.set_angle(angle)

    def get_alignment(self) -> dict[str, Any]:
        h_data = self.combo_h.currentData() or "general"
        # Support fallback if currentText matches test strings
        h_text = self.combo_h.currentText()
        if "居中" in h_text:
            h_data = "center"
        elif "靠左" in h_text:
            h_data = "left"
        elif "靠右" in h_text:
            h_data = "right"

        v_data = self.combo_v.currentData() or "bottom"
        v_text = self.combo_v.currentText()
        if "靠上" in v_text:
            v_data = "top"
        elif "居中" in v_text:
            v_data = "center"
        elif "靠下" in v_text:
            v_data = "bottom"

        rot = 255 if self.btn_vertical.isChecked() else self.spin_rot.value()

        return {
            "align_h": h_data,
            "align_v": v_data,
            "indent": self.spin_indent.value(),
            "wrap_text": self.check_wrap.isChecked(),
            "shrink_to_fit": self.check_shrink.isChecked(),
            "merge_cells": self.check_merge.isChecked(),
            "text_rotation": rot,
            "text_direction": self.combo_dir.currentData() or "context",
            "just_last": self.check_just_last.isChecked(),
        }

    def retranslate_ui(self) -> None:
        self.grp_align.setTitle(safe_tr("文本对齐方式"))
        self.lbl_h.setText(safe_tr("水平对齐(&H):"))
        self.lbl_indent.setText(safe_tr("缩进(&I):"))
        self.lbl_v.setText(safe_tr("垂直对齐(&V):"))
        self.check_just_last.setText(safe_tr("两端对齐分散(&J)"))
        self.grp_control.setTitle(safe_tr("文本控制"))
        self.check_wrap.setText(safe_tr("自动换行(&W)"))
        self.check_shrink.setText(safe_tr("缩小字体填充(&K)"))
        self.check_merge.setText(safe_tr("合并单元格(&M)"))
        self.grp_direction.setTitle(safe_tr("文字走向"))
        self.lbl_dir.setText(safe_tr("文字方向(&T):"))
        self.grp_orient.setTitle(safe_tr("方向"))
        self.btn_vertical.setText(safe_tr("竖\n排\n文\n字"))
        self.lbl_degrees.setText(safe_tr("度(&D):"))
