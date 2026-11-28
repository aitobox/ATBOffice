"""Luna 2003 Format Object modal dialog for Quire floating pictures, shapes and text boxes."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr
from atboffice.modules.writer.models.drawing import WrapMode
from atboffice.ui.styles.luna_2003 import theme_tokens, ui_font

_WRAP_CHOICES: tuple[tuple[str, str], ...] = (
    ("嵌入型", WrapMode.INLINE.value),
    ("四周型", WrapMode.SQUARE.value),
    ("紧密型", WrapMode.TIGHT.value),
    ("衬于文字下方", WrapMode.BEHIND.value),
    ("浮于文字上方", WrapMode.IN_FRONT.value),
    ("上下型", WrapMode.TOP_BOTTOM.value),
)


def _normalize_hex(color: str | None, fallback: str) -> str:
    if not color or str(color).lower() in ("auto", "none", ""):
        return fallback
    val = str(color).strip()
    return val.upper() if val.startswith("#") else f"#{val.upper()}"


class FormatObjectDialog(QDialog):
    """Word 2003 Luna Format Object dialog for Quire drawing objects."""

    def __init__(self, obj: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.obj = obj
        self.setObjectName("QuireFormatObjectDialog")
        self.setModal(True)
        self.setMinimumWidth(380)

        line = getattr(obj, "line", None)
        self._line_visible = bool(getattr(line, "visible", False)) if line is not None else False
        self._line_color = _normalize_hex(getattr(line, "color", None), "#000000")
        init_line_width = float(getattr(line, "width", 0.75) or 0.75) if self._line_visible else 0.0

        fill = getattr(obj, "fill", None)
        fill_kind = getattr(fill, "kind", "none") if fill is not None else "none"
        self._fill_enabled = fill is not None and fill_kind != "none"
        self._fill_color = _normalize_hex(getattr(fill, "color", None), "#FFFFFF")

        self._init_ui(obj, init_line_width)
        self._apply_theme()
        self.retranslate_ui()

    def _init_ui(self, obj: Any, init_line_width: float) -> None:
        self.setFont(ui_font())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Size & rotation
        self.grp_size = QGroupBox(self)
        form_size = QFormLayout(self.grp_size)
        form_size.setSpacing(6)

        self.lbl_width = QLabel(self.grp_size)
        self.spin_width = QDoubleSpinBox(self.grp_size)
        self.spin_width.setObjectName("FormatObjectWidthSpin")
        self.spin_width.setRange(1.0, 2000.0)
        self.spin_width.setDecimals(1)
        self.spin_width.setSingleStep(1.0)
        self.spin_width.setSuffix(" pt")
        self.spin_width.setValue(max(1.0, float(getattr(obj, "width", 72.0) or 72.0)))
        self.lbl_width.setBuddy(self.spin_width)
        form_size.addRow(self.lbl_width, self.spin_width)

        self.lbl_height = QLabel(self.grp_size)
        self.spin_height = QDoubleSpinBox(self.grp_size)
        self.spin_height.setObjectName("FormatObjectHeightSpin")
        self.spin_height.setRange(1.0, 2000.0)
        self.spin_height.setDecimals(1)
        self.spin_height.setSingleStep(1.0)
        self.spin_height.setSuffix(" pt")
        self.spin_height.setValue(max(1.0, float(getattr(obj, "height", 72.0) or 72.0)))
        self.lbl_height.setBuddy(self.spin_height)
        form_size.addRow(self.lbl_height, self.spin_height)

        self.lbl_rotation = QLabel(self.grp_size)
        self.spin_rotation = QDoubleSpinBox(self.grp_size)
        self.spin_rotation.setObjectName("FormatObjectRotationSpin")
        self.spin_rotation.setRange(0.0, 360.0)
        self.spin_rotation.setWrapping(True)
        self.spin_rotation.setDecimals(1)
        self.spin_rotation.setSingleStep(15.0)
        self.spin_rotation.setSuffix("°")
        self.spin_rotation.setValue(float(getattr(obj, "rotation", 0.0) or 0.0) % 360.0)
        self.lbl_rotation.setBuddy(self.spin_rotation)
        form_size.addRow(self.lbl_rotation, self.spin_rotation)
        layout.addWidget(self.grp_size)

        # 2. Wrapping
        self.grp_wrap = QGroupBox(self)
        form_wrap = QFormLayout(self.grp_wrap)
        form_wrap.setSpacing(6)

        self.lbl_wrap = QLabel(self.grp_wrap)
        self.combo_wrap = QComboBox(self.grp_wrap)
        self.combo_wrap.setObjectName("FormatObjectWrapCombo")
        for label_key, mode_val in _WRAP_CHOICES:
            self.combo_wrap.addItem(safe_tr(label_key), mode_val)

        fp = getattr(obj, "float_pr", None)
        if fp is None:
            cur_wrap = WrapMode.INLINE.value
        elif getattr(fp, "behind", False) or getattr(fp, "wrap", None) == WrapMode.BEHIND:
            cur_wrap = WrapMode.BEHIND.value
        else:
            raw_wrap = getattr(fp, "wrap", WrapMode.SQUARE)
            cur_wrap = str(getattr(raw_wrap, "value", raw_wrap) or WrapMode.SQUARE.value)
        idx = self.combo_wrap.findData(cur_wrap)
        if idx >= 0:
            self.combo_wrap.setCurrentIndex(idx)
        self.lbl_wrap.setBuddy(self.combo_wrap)
        form_wrap.addRow(self.lbl_wrap, self.combo_wrap)
        layout.addWidget(self.grp_wrap)

        # 3. Colors, Line & Shadow
        self.grp_style = QGroupBox(self)
        form_style = QFormLayout(self.grp_style)
        form_style.setSpacing(6)

        self.lbl_fill_color = QLabel(self.grp_style)
        self.btn_fill_color = QPushButton(self.grp_style)
        self.btn_fill_color.setObjectName("FormatObjectFillBtn")
        self.btn_fill_color.clicked.connect(self._choose_fill_color)
        form_style.addRow(self.lbl_fill_color, self.btn_fill_color)

        self.lbl_line_color = QLabel(self.grp_style)
        self.btn_line_color = QPushButton(self.grp_style)
        self.btn_line_color.setObjectName("FormatObjectLineColorBtn")
        self.btn_line_color.clicked.connect(self._choose_line_color)
        form_style.addRow(self.lbl_line_color, self.btn_line_color)

        self.lbl_line_width = QLabel(self.grp_style)
        self.spin_line_width = QDoubleSpinBox(self.grp_style)
        self.spin_line_width.setObjectName("FormatObjectLineWidthSpin")
        self.spin_line_width.setRange(0.0, 72.0)
        self.spin_line_width.setDecimals(2)
        self.spin_line_width.setSingleStep(0.25)
        self.spin_line_width.setSuffix(" pt")
        self.spin_line_width.setValue(max(0.0, init_line_width))
        self.spin_line_width.valueChanged.connect(self._on_line_width_changed)
        self.lbl_line_width.setBuddy(self.spin_line_width)
        form_style.addRow(self.lbl_line_width, self.spin_line_width)

        self.chk_shadow = QCheckBox(self.grp_style)
        self.chk_shadow.setObjectName("FormatObjectShadowCheck")
        raw_data = getattr(obj, "raw_data", None)
        has_shadow = bool(getattr(obj, "shadow", False)) or bool(
            isinstance(raw_data, dict) and raw_data.get("shadow")
        )
        self.chk_shadow.setChecked(has_shadow)
        form_style.addRow("", self.chk_shadow)
        layout.addWidget(self.grp_style)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._refresh_color_buttons()

    def _apply_theme(self) -> None:
        tok = theme_tokens()
        self.setStyleSheet(
            f"QDialog {{ background-color: {tok.face}; }}"
            f"QGroupBox {{ border: 1px solid {tok.tb_border}; border-radius: 3px; "
            f"margin-top: 8px; padding-top: 8px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; }}"
        )
        for widget in (
            self.grp_size,
            self.grp_wrap,
            self.grp_style,
            self.lbl_width,
            self.lbl_height,
            self.lbl_rotation,
            self.lbl_wrap,
            self.lbl_fill_color,
            self.lbl_line_color,
            self.lbl_line_width,
            self.spin_width,
            self.spin_height,
            self.spin_rotation,
            self.combo_wrap,
            self.btn_fill_color,
            self.btn_line_color,
            self.spin_line_width,
            self.chk_shadow,
            self.button_box,
        ):
            widget.setFont(ui_font())

    def _refresh_color_buttons(self) -> None:
        tok = theme_tokens()
        if self._fill_enabled:
            qc = QColor(self._fill_color)
            fg = "#FFFFFF" if qc.lightness() < 128 else "#000000"
            self.btn_fill_color.setStyleSheet(
                f"background-color: {self._fill_color}; color: {fg}; "
                f"border: 1px solid {tok.tb_border}; min-height: 22px; padding: 2px 8px;"
            )
            self.btn_fill_color.setText(self._fill_color)
        else:
            self.btn_fill_color.setStyleSheet(
                f"background-color: {tok.menu_face}; color: #000000; "
                f"border: 1px solid {tok.tb_border}; min-height: 22px; padding: 2px 8px;"
            )
            self.btn_fill_color.setText(safe_tr("无填充"))

        if self._line_visible:
            qc = QColor(self._line_color)
            fg = "#FFFFFF" if qc.lightness() < 128 else "#000000"
            self.btn_line_color.setStyleSheet(
                f"background-color: {self._line_color}; color: {fg}; "
                f"border: 1px solid {tok.tb_border}; min-height: 22px; padding: 2px 8px;"
            )
            self.btn_line_color.setText(self._line_color)
        else:
            self.btn_line_color.setStyleSheet(
                f"background-color: {tok.menu_face}; color: #000000; "
                f"border: 1px solid {tok.tb_border}; min-height: 22px; padding: 2px 8px;"
            )
            self.btn_line_color.setText(safe_tr("无线条"))

    def _on_line_width_changed(self, value: float) -> None:
        self._line_visible = float(value) > 0.0
        self._refresh_color_buttons()

    def set_fill_color(self, color: str | None) -> None:
        """Programmatically set fill color (or None/'none' for no fill)."""
        if color is None or str(color).lower() == "none":
            self._fill_enabled = False
        else:
            self._fill_enabled = True
            self._fill_color = _normalize_hex(color, "#FFFFFF")
        self._refresh_color_buttons()

    def set_line_color(self, color: str) -> None:
        """Programmatically set stroke color and ensure outline is visible."""
        self._line_color = _normalize_hex(color, "#000000")
        if self.spin_line_width.value() <= 0.0:
            self.spin_line_width.setValue(0.75)
        self._line_visible = self.spin_line_width.value() > 0.0
        self._refresh_color_buttons()

    def _choose_fill_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._fill_color), self, safe_tr("选择颜色"))
        if chosen.isValid():
            self.set_fill_color(chosen.name())

    def _choose_line_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._line_color), self, safe_tr("选择颜色"))
        if chosen.isValid():
            self.set_line_color(chosen.name())

    def get_settings(self) -> dict[str, Any]:
        """Return edited object geometry, wrapping, line, fill and shadow values."""
        line_width = float(self.spin_line_width.value())
        return {
            "width": float(self.spin_width.value()),
            "height": float(self.spin_height.value()),
            "rotation": float(self.spin_rotation.value()) % 360.0,
            "wrap_mode": str(self.combo_wrap.currentData() or WrapMode.SQUARE.value),
            "line_color": self._line_color,
            "line_width": line_width,
            "line_visible": self._line_visible and line_width > 0.0,
            "fill_enabled": self._fill_enabled,
            "fill_color": self._fill_color,
            "shadow": bool(self.chk_shadow.isChecked()),
        }

    def retranslate_ui(self) -> None:
        """Update all visible text strings for the active locale."""
        self.setWindowTitle(safe_tr("设置对象格式"))
        self.grp_size.setTitle(safe_tr("大小和旋转"))
        self.lbl_width.setText(safe_tr("宽度(&W)："))
        self.lbl_height.setText(safe_tr("高度(&H)："))
        self.lbl_rotation.setText(safe_tr("旋转(&t)："))

        self.grp_wrap.setTitle(safe_tr("文字环绕"))
        self.lbl_wrap.setText(safe_tr("环绕方式"))
        cur_idx = self.combo_wrap.currentIndex()
        for idx, (label_key, _mode_val) in enumerate(_WRAP_CHOICES):
            self.combo_wrap.setItemText(idx, safe_tr(label_key))
        if cur_idx >= 0:
            self.combo_wrap.setCurrentIndex(cur_idx)

        self.grp_style.setTitle(safe_tr("颜色与线条"))
        self.lbl_fill_color.setText(safe_tr("填充颜色："))
        self.lbl_line_color.setText(safe_tr("线条颜色"))
        self.lbl_line_width.setText(safe_tr("粗细(&W)："))
        self.chk_shadow.setText(safe_tr("阴影(&S)"))

        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText(safe_tr("确定"))
        cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn is not None:
            cancel_btn.setText(safe_tr("取消"))
        self._refresh_color_buttons()
