"""Word 2003 classic Font Dialog for Quire writer."""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.models.properties import RunProperties


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("FontDialog", text)


CHINESE_FONT_SIZES: list[tuple[str, float]] = [
    ("初号", 42.0),
    ("小初", 36.0),
    ("一号", 26.0),
    ("小一", 24.0),
    ("二号", 22.0),
    ("小二", 18.0),
    ("三号", 16.0),
    ("小三", 15.0),
    ("四号", 14.0),
    ("小四", 12.0),
    ("五号", 10.5),
    ("小五", 9.0),
    ("六号", 7.5),
    ("小六", 6.5),
    ("七号", 5.5),
    ("八号", 5.0),
]

POINT_FONT_SIZES: list[float] = [
    5.0, 5.5, 6.5, 7.5, 8.0, 9.0, 10.0, 10.5, 11.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0, 36.0, 48.0, 72.0
]


class FontPreviewWidget(QWidget):
    """Live preview widget demonstrating selected font formatting."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.props = RunProperties()

    def update_props(self, props: RunProperties) -> None:
        self.props = copy.copy(props)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw border & background
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        painter.setPen(QPen(QColor("#B0B0B0"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        # Setup font
        family = self.props.font or "Times New Roman"
        sz = max(8.0, min(float(self.props.sz or 12.0), 32.0))
        qfont = QFont(family)
        qfont.setPointSizeF(sz)
        qfont.setBold(bool(self.props.b))
        qfont.setItalic(bool(self.props.i))
        if self.props.strike or self.props.dstrike:
            qfont.setStrikeOut(True)
        if self.props.u != "none":
            qfont.setUnderline(True)
        painter.setFont(qfont)

        # Color
        color_val = self.props.color
        if not color_val or color_val.lower() == "auto":
            painter.setPen(QPen(Qt.GlobalColor.black))
        else:
            hex_str = color_val if color_val.startswith("#") else f"#{color_val}"
            painter.setPen(QPen(QColor(hex_str)))

        text = safe_tr("ATBOffice 经典排版预览 The quick brown fox jumps over the lazy dog 1234567890")
        if self.props.caps:
            text = text.upper()
        painter.drawText(self.rect().adjusted(10, 10, -10, -10), Qt.AlignmentFlag.AlignCenter, text)


class FontDialog(QDialog):
    """Word 2003 classic Font Dialog."""

    def __init__(
        self,
        props: RunProperties | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.props = copy.copy(props) if props is not None else RunProperties()
        self.setMinimumWidth(480)
        self.setWindowTitle(safe_tr("字体"))

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        self.tab_widget = QTabWidget(self)

        # --- Tab 1: 字体 (Font) ---
        self.tab_font = QWidget()
        font_layout = QVBoxLayout(self.tab_font)

        # Font families and style row
        top_grid = QGridLayout()

        self.lbl_latin_font = QLabel(self.tab_font)
        self.combo_latin_font = QComboBox(self.tab_font)
        self.combo_latin_font.setEditable(True)
        self.combo_latin_font.addItems([
            "Times New Roman", "Arial", "Courier New", "Calibri", "Georgia", "Tahoma", "Verdana", "Segoe UI"
        ])

        self.lbl_ea_font = QLabel(self.tab_font)
        self.combo_ea_font = QComboBox(self.tab_font)
        self.combo_ea_font.setEditable(True)
        self.combo_ea_font.addItems([
            "宋体", "黑体", "楷体", "仿宋", "微软雅黑", "SimSun", "SimHei", "KaiTi", "FangSong", "Microsoft YaHei"
        ])

        self.lbl_style = QLabel(self.tab_font)
        self.combo_style = QComboBox(self.tab_font)
        self.combo_style.addItems([
            safe_tr("常规"), safe_tr("倾斜"), safe_tr("加粗"), safe_tr("加粗 倾斜")
        ])

        self.lbl_size = QLabel(self.tab_font)
        self.combo_size = QComboBox(self.tab_font)
        self.combo_size.setEditable(True)
        for name, pt in CHINESE_FONT_SIZES:
            self.combo_size.addItem(f"{name} ({pt:g}pt)", pt)
        for pt in POINT_FONT_SIZES:
            self.combo_size.addItem(f"{pt:g}", pt)

        top_grid.addWidget(self.lbl_latin_font, 0, 0)
        top_grid.addWidget(self.combo_latin_font, 1, 0)
        top_grid.addWidget(self.lbl_ea_font, 0, 1)
        top_grid.addWidget(self.combo_ea_font, 1, 1)
        top_grid.addWidget(self.lbl_style, 0, 2)
        top_grid.addWidget(self.combo_style, 1, 2)
        top_grid.addWidget(self.lbl_size, 0, 3)
        top_grid.addWidget(self.combo_size, 1, 3)
        font_layout.addLayout(top_grid)

        # Color and Underline row
        mid_layout = QHBoxLayout()
        self.lbl_color = QLabel(self.tab_font)
        self.btn_color = QPushButton(safe_tr("自动"), self.tab_font)
        self._current_color: str = self.props.color or "auto"
        self.btn_color.clicked.connect(self._choose_color)

        self.lbl_underline = QLabel(self.tab_font)
        self.combo_underline = QComboBox(self.tab_font)
        self.combo_underline.addItem(safe_tr("(无)"), "none")
        self.combo_underline.addItem(safe_tr("单线"), "single")
        self.combo_underline.addItem(safe_tr("双线"), "double")
        self.combo_underline.addItem(safe_tr("点线"), "dotted")
        self.combo_underline.addItem(safe_tr("虚线"), "dashed")
        self.combo_underline.addItem(safe_tr("波浪线"), "wave")

        mid_layout.addWidget(self.lbl_color)
        mid_layout.addWidget(self.btn_color)
        mid_layout.addSpacing(16)
        mid_layout.addWidget(self.lbl_underline)
        mid_layout.addWidget(self.combo_underline)
        mid_layout.addStretch()
        font_layout.addLayout(mid_layout)

        # Effects group
        self.group_effects = QGroupBox(self.tab_font)
        fx_grid = QGridLayout(self.group_effects)
        self.check_strike = QCheckBox(self.group_effects)
        self.check_dstrike = QCheckBox(self.group_effects)
        self.check_superscript = QCheckBox(self.group_effects)
        self.check_subscript = QCheckBox(self.group_effects)
        self.check_small_caps = QCheckBox(self.group_effects)
        self.check_all_caps = QCheckBox(self.group_effects)
        self.check_hidden = QCheckBox(self.group_effects)

        fx_grid.addWidget(self.check_strike, 0, 0)
        fx_grid.addWidget(self.check_dstrike, 0, 1)
        fx_grid.addWidget(self.check_superscript, 0, 2)
        fx_grid.addWidget(self.check_subscript, 1, 0)
        fx_grid.addWidget(self.check_small_caps, 1, 1)
        fx_grid.addWidget(self.check_all_caps, 1, 2)
        fx_grid.addWidget(self.check_hidden, 2, 0)
        font_layout.addWidget(self.group_effects)

        # Effect exclusions
        self.check_strike.toggled.connect(lambda on: on and self.check_dstrike.setChecked(False))
        self.check_dstrike.toggled.connect(lambda on: on and self.check_strike.setChecked(False))
        self.check_superscript.toggled.connect(lambda on: on and self.check_subscript.setChecked(False))
        self.check_subscript.toggled.connect(lambda on: on and self.check_superscript.setChecked(False))
        self.check_small_caps.toggled.connect(lambda on: on and self.check_all_caps.setChecked(False))
        self.check_all_caps.toggled.connect(lambda on: on and self.check_small_caps.setChecked(False))

        self.tab_widget.addTab(self.tab_font, safe_tr("字体"))

        # --- Tab 2: 字符间距 (Character Spacing) ---
        self.tab_spacing = QWidget()
        spacing_layout = QFormLayout(self.tab_spacing)

        self.lbl_scale = QLabel(self.tab_spacing)
        self.combo_scale = QComboBox(self.tab_spacing)
        self.combo_scale.setEditable(True)
        self.combo_scale.addItems(["200%", "150%", "100%", "90%", "80%", "66%", "50%", "33%"])
        self.combo_scale.setCurrentText("100%")

        self.lbl_spacing = QLabel(self.tab_spacing)
        spacing_h = QHBoxLayout()
        self.combo_spacing = QComboBox(self.tab_spacing)
        self.combo_spacing.addItem(safe_tr("标准"), "normal")
        self.combo_spacing.addItem(safe_tr("加宽"), "expanded")
        self.combo_spacing.addItem(safe_tr("紧缩"), "condensed")
        self.lbl_spacing_by = QLabel(safe_tr("磅值:"), self.tab_spacing)
        self.spin_spacing_by = QDoubleSpinBox(self.tab_spacing)
        self.spin_spacing_by.setRange(0.0, 100.0)
        self.spin_spacing_by.setSingleStep(0.5)
        self.spin_spacing_by.setValue(0.0)
        spacing_h.addWidget(self.combo_spacing)
        spacing_h.addWidget(self.lbl_spacing_by)
        spacing_h.addWidget(self.spin_spacing_by)

        self.lbl_position = QLabel(self.tab_spacing)
        position_h = QHBoxLayout()
        self.combo_position = QComboBox(self.tab_spacing)
        self.combo_position.addItem(safe_tr("标准"), "normal")
        self.combo_position.addItem(safe_tr("提升"), "raised")
        self.combo_position.addItem(safe_tr("降低"), "lowered")
        self.lbl_position_by = QLabel(safe_tr("磅值:"), self.tab_spacing)
        self.spin_position_by = QDoubleSpinBox(self.tab_spacing)
        self.spin_position_by.setRange(0.0, 100.0)
        self.spin_position_by.setSingleStep(0.5)
        self.spin_position_by.setValue(0.0)
        position_h.addWidget(self.combo_position)
        position_h.addWidget(self.lbl_position_by)
        position_h.addWidget(self.spin_position_by)

        self.lbl_kerning = QLabel(self.tab_spacing)
        kerning_h = QHBoxLayout()
        self.check_kerning = QCheckBox(self.tab_spacing)
        self.spin_kerning_min = QDoubleSpinBox(self.tab_spacing)
        self.spin_kerning_min.setRange(1.0, 72.0)
        self.spin_kerning_min.setValue(10.5)
        self.lbl_kerning_unit = QLabel(safe_tr("磅或以上"), self.tab_spacing)
        kerning_h.addWidget(self.check_kerning)
        kerning_h.addWidget(self.spin_kerning_min)
        kerning_h.addWidget(self.lbl_kerning_unit)
        kerning_h.addStretch()

        spacing_layout.addRow(self.lbl_scale, self.combo_scale)
        spacing_layout.addRow(self.lbl_spacing, spacing_h)
        spacing_layout.addRow(self.lbl_position, position_h)
        spacing_layout.addRow(self.lbl_kerning, kerning_h)

        self.tab_widget.addTab(self.tab_spacing, safe_tr("字符间距"))
        main_layout.addWidget(self.tab_widget)

        # Preview box
        self.group_preview = QGroupBox(self)
        preview_layout = QVBoxLayout(self.group_preview)
        self.preview_widget = FontPreviewWidget(self.group_preview)
        preview_layout.addWidget(self.preview_widget)
        main_layout.addWidget(self.group_preview)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Connect live preview triggers
        self._connect_triggers()

        # Load initial values
        self._load_from_props()
        self.retranslate_ui()

    def _choose_color(self) -> None:
        init_col = QColor(f"#{self._current_color}") if self._current_color != "auto" else Qt.GlobalColor.black
        color = QColorDialog.getColor(init_col, self, safe_tr("选择字体颜色"))
        if color.isValid():
            self._current_color = color.name().lstrip("#").upper()
            self.btn_color.setText(f"#{self._current_color}")
            self._trigger_preview()

    def _connect_triggers(self) -> None:
        for cb in [
            self.combo_latin_font, self.combo_ea_font, self.combo_style, self.combo_size,
            self.combo_underline, self.combo_scale, self.combo_spacing, self.combo_position
        ]:
            cb.currentIndexChanged.connect(self._trigger_preview)
            if cb.isEditable():
                cb.editTextChanged.connect(self._trigger_preview)

        for chk in [
            self.check_strike, self.check_dstrike, self.check_superscript,
            self.check_subscript, self.check_small_caps, self.check_all_caps
        ]:
            chk.toggled.connect(self._trigger_preview)

    def _trigger_preview(self) -> None:
        updated = self.get_properties()
        self.preview_widget.update_props(updated)

    def _load_from_props(self) -> None:
        if self.props.font:
            idx = self.combo_latin_font.findText(self.props.font)
            if idx >= 0:
                self.combo_latin_font.setCurrentIndex(idx)
            else:
                self.combo_latin_font.setEditText(self.props.font)

        if self.props.font_ea:
            idx = self.combo_ea_font.findText(self.props.font_ea)
            if idx >= 0:
                self.combo_ea_font.setCurrentIndex(idx)
            else:
                self.combo_ea_font.setEditText(self.props.font_ea)

        # Style
        if self.props.b and self.props.i:
            self.combo_style.setCurrentIndex(3)
        elif self.props.b:
            self.combo_style.setCurrentIndex(2)
        elif self.props.i:
            self.combo_style.setCurrentIndex(1)
        else:
            self.combo_style.setCurrentIndex(0)

        # Size
        sz_val = float(self.props.sz or 12.0)
        found = False
        for i in range(self.combo_size.count()):
            val = self.combo_size.itemData(i)
            if val is not None and abs(float(val) - sz_val) < 0.01:
                self.combo_size.setCurrentIndex(i)
                found = True
                break
        if not found:
            self.combo_size.setEditText(f"{sz_val:g}")

        # Color
        self._current_color = self.props.color or "auto"
        self.btn_color.setText(safe_tr("自动") if self._current_color == "auto" else f"#{self._current_color}")

        # Underline
        idx = self.combo_underline.findData(self.props.u or "none")
        if idx >= 0:
            self.combo_underline.setCurrentIndex(idx)

        # Effects
        self.check_strike.setChecked(bool(self.props.strike))
        self.check_dstrike.setChecked(bool(self.props.dstrike))
        self.check_superscript.setChecked(self.props.vert == "superscript")
        self.check_subscript.setChecked(self.props.vert == "subscript")
        self.check_small_caps.setChecked(bool(self.props.small_caps))
        self.check_all_caps.setChecked(bool(self.props.caps))

        if self.props.spacing:
            if self.props.spacing > 0:
                self.combo_spacing.setCurrentIndex(1)
                self.spin_spacing_by.setValue(self.props.spacing)
            elif self.props.spacing < 0:
                self.combo_spacing.setCurrentIndex(2)
                self.spin_spacing_by.setValue(abs(self.props.spacing))

        if self.props.kern is not None:
            self.check_kerning.setChecked(True)
            self.spin_kerning_min.setValue(self.props.kern)

        self._trigger_preview()

    def get_properties(self) -> RunProperties:
        """Construct updated RunProperties from dialog controls."""
        res = copy.copy(self.props)
        res.font = self.combo_latin_font.currentText().strip() or "Times New Roman"
        res.font_ea = self.combo_ea_font.currentText().strip() or "SimSun"

        # Style
        st_idx = self.combo_style.currentIndex()
        res.b = st_idx in (2, 3)
        res.i = st_idx in (1, 3)

        # Size
        data_sz = self.combo_size.currentData()
        if data_sz is not None:
            res.sz = float(data_sz)
        else:
            txt = self.combo_size.currentText().replace("pt", "").strip()
            try:
                res.sz = max(1.0, float(txt))
            except ValueError:
                res.sz = 12.0

        # Color & Underline
        res.color = self._current_color
        res.u = self.combo_underline.currentData() or "none"

        # Effects
        res.strike = self.check_strike.isChecked()
        res.dstrike = self.check_dstrike.isChecked()
        if self.check_superscript.isChecked():
            res.vert = "superscript"
        elif self.check_subscript.isChecked():
            res.vert = "subscript"
        else:
            res.vert = "baseline"

        res.small_caps = self.check_small_caps.isChecked()
        res.caps = self.check_all_caps.isChecked()

        # Spacing
        sp_type = self.combo_spacing.currentData()
        if sp_type == "expanded":
            res.spacing = self.spin_spacing_by.value()
        elif sp_type == "condensed":
            res.spacing = -self.spin_spacing_by.value()
        else:
            res.spacing = 0.0

        if self.check_kerning.isChecked():
            res.kern = self.spin_kerning_min.value()
        else:
            res.kern = None

        return res

    def retranslate_ui(self) -> None:
        """Localize UI strings."""
        self.setWindowTitle(safe_tr("字体"))
        self.tab_widget.setTabText(0, safe_tr("字体"))
        self.tab_widget.setTabText(1, safe_tr("字符间距"))

        self.lbl_latin_font.setText(safe_tr("西文字体(&L):"))
        self.lbl_ea_font.setText(safe_tr("中文字体(&T):"))
        self.lbl_style.setText(safe_tr("字形(&Y):"))
        self.lbl_size.setText(safe_tr("字号(&S):"))

        self.lbl_color.setText(safe_tr("字体颜色(&C):"))
        self.lbl_underline.setText(safe_tr("下划线线型(&U):"))

        self.group_effects.setTitle(safe_tr("效果"))
        self.check_strike.setText(safe_tr("删除线(&K)"))
        self.check_dstrike.setText(safe_tr("双删除线(&L)"))
        self.check_superscript.setText(safe_tr("上标(&P)"))
        self.check_subscript.setText(safe_tr("下标(&B)"))
        self.check_small_caps.setText(safe_tr("小型大写字母(&M)"))
        self.check_all_caps.setText(safe_tr("全部大写字母(&A)"))
        self.check_hidden.setText(safe_tr("隐藏(&H)"))

        self.lbl_scale.setText(safe_tr("缩放(&C):"))
        self.lbl_spacing.setText(safe_tr("间距(&S):"))
        self.lbl_position.setText(safe_tr("位置(&P):"))
        self.lbl_kerning.setText(safe_tr("字距微调(&K):"))

        self.group_preview.setTitle(safe_tr("预览"))
